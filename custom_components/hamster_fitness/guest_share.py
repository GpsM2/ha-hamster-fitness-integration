"""Unauthenticated guest view of one hamster's live status (#147).

The only two routes in this integration that don't require a Home
Assistant login - everything else in `custom_components/hamster_fitness/`
assumes a logged-in session. Kept in this one file, deliberately small and
self-contained, so the entire unauthenticated attack surface is reviewable
in one place:

- `GuestPageView` serves a static, secret-free HTML shell. It carries no
  hamster data at all and does not validate the token - there is nothing
  in the shell worth protecting, and folding "is this token valid" into
  the page load would only tempt a future change to put something real
  there later.
- `GuestDataView` is the actual security boundary. It looks up the token
  against every hamster's own `guest_share_token`
  (`HamsterFitnessCoordinator.guest_share_token`) using a constant-time
  comparison, and returns a small, hardcoded field allowlist - never a
  generic state dump. An unknown or revoked token gets a 404, same as a
  token that never existed; there is nothing to gain by telling a caller
  which.

Authorization here is the token's entropy alone
(`secrets.token_urlsafe(GUEST_SHARE_TOKEN_BYTES)`, see `coordinator.py`'s
`async_set_guest_share()`) - never the requester's network position.
Home Assistant behind Nabu Casa Cloud or a reverse proxy hands every
request to this integration from an internal address; trusting
`request.remote` as any kind of gate would either lock out the exact
"boarding sitter checking in remotely" case this feature exists for, or
be trivially bypassable. The per-IP rate limiting below is a courtesy
against blind guessing from a single source, not a substitute for that.
"""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HAMSTER_NAME,
    DOMAIN,
    GUEST_SHARE_RATE_LIMIT_REQUESTS,
    GUEST_SHARE_RATE_LIMIT_WINDOW_SECONDS,
    GUEST_URL_PREFIX,
)
from .coordinator import HamsterFitnessConfigEntry, hamster_profile

_LOGGER = logging.getLogger(__name__)

_GUEST_HTML_PATH = Path(__file__).parent / "guest" / "index.html"
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
}


class _RateLimiter:
    """A simple in-memory sliding window, keyed by whatever caller-supplied
    string is passed to `allow()` - here, the request's source IP.

    Explicitly a courtesy layer, not the security boundary - see the
    module docstring. Sized for a household's worth of distinct callers,
    not internet-scale traffic; `_sweep()` keeps memory bounded for a
    long-running Home Assistant instance without needing a background
    task of its own.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._last_sweep = 0.0

    def allow(self, key: str) -> bool:
        """Return True if `key` is still under the limit, recording a hit."""
        now = time.monotonic()
        self._sweep(now)
        cutoff = now - self._window_seconds
        hits = [t for t in self._hits.get(key, []) if t > cutoff]
        if len(hits) >= self._max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < 300:
            return
        self._last_sweep = now
        cutoff = now - self._window_seconds
        self._hits = {
            key: kept
            for key, hits in self._hits.items()
            if (kept := [t for t in hits if t > cutoff])
        }


def _find_entry(
    hass: HomeAssistant, token: str
) -> HamsterFitnessConfigEntry | None:
    """Return the hamster config entry whose guest-share token matches, if any.

    Iterates every hamster's config entry rather than keeping a separate
    token->entry lookup table - there are only ever as many hamsters as a
    household actually has, and this way there is exactly one place
    (`HamsterFitnessCoordinator._guest_share_token`) that owns the token,
    not two that could drift apart. `secrets.compare_digest` avoids
    leaking timing information about how much of a guess matched.

    Both sides are compared as bytes, not str: `compare_digest` raises
    TypeError on str arguments containing non-ASCII characters, and
    `token` comes straight off the URL, where anyone can put anything.
    A request for /hamster_fitness/guest/caf%C3%A9/data used to reach
    this line and turn that TypeError into a 500 plus a logged
    traceback, on a route that is reachable without any authentication.
    Encoding first keeps the comparison constant-time while making every
    possible input merely "not a match".
    """
    probe = token.encode("utf-8")
    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is None:
            continue
        candidate = coordinator.guest_share_token
        if candidate is not None and secrets.compare_digest(
            candidate.encode("utf-8"), probe
        ):
            return entry
    return None


class GuestPageView(HomeAssistantView):
    """Serves the guest page's static HTML shell, unauthenticated."""

    url = f"{GUEST_URL_PREFIX}/{{token}}"
    name = f"{DOMAIN}:guest_page"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, rate_limiter: _RateLimiter) -> None:
        """Initialize the view."""
        self.hass = hass
        self._rate_limiter = rate_limiter
        self._html: str | None = None

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Return the shell HTML - same response regardless of token validity.

        Nothing in the shell is specific to one hamster or reveals
        whether the token in the URL is real; `GuestDataView` is where
        that distinction is made. Rate-limited anyway, purely so an
        unauthenticated route can't be used to churn disk reads for
        free. `token` is unused on purpose - see above - but
        `HomeAssistantView` always calls handlers with every dynamic URL
        segment as a keyword argument, so it has to be accepted.

        The file is read once and kept: it ships with the integration, so
        it can only change via an update, which needs a Home Assistant
        restart anyway - exactly the same lifetime the bundled card files
        already assume. The no-cache headers stay: they are about the
        *viewer's* browser not holding on to a page whose link may since
        have been revoked, which is unrelated to re-reading it from disk
        on every single request.
        """
        if not self._rate_limiter.allow(request.remote or "unknown"):
            return web.Response(status=429, text="Too many requests")
        if self._html is None:
            self._html = await self.hass.async_add_executor_job(
                _GUEST_HTML_PATH.read_text, "utf-8"
            )
        return web.Response(
            text=self._html, content_type="text/html", headers=_NO_CACHE_HEADERS
        )


class GuestDataView(HomeAssistantView):
    """Serves the small, hardcoded JSON allowlist the guest page polls."""

    url = f"{GUEST_URL_PREFIX}/{{token}}/data"
    name = f"{DOMAIN}:guest_data"
    requires_auth = False

    def __init__(self, hass: HomeAssistant, rate_limiter: _RateLimiter) -> None:
        """Initialize the view."""
        self.hass = hass
        self._rate_limiter = rate_limiter

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Return this hamster's guest-facing status, or 404."""
        if not self._rate_limiter.allow(request.remote or "unknown"):
            return web.Response(status=429, text="Too many requests")

        entry = _find_entry(self.hass, token)
        if entry is None:
            # Same response whether the token never existed or was just
            # revoked - nothing useful to a caller either way.
            return web.Response(status=404)

        return web.json_response(_guest_payload(entry), headers=_NO_CACHE_HEADERS)


def _guest_payload(entry: HamsterFitnessConfigEntry) -> dict[str, Any]:
    """Build the fixed, reviewable field set a guest is allowed to see.

    Deliberately not a generic state/attribute dump - every field here is
    named explicitly, so adding a new one is a conscious decision, not
    something that leaks in because it happened to exist on the
    coordinator's data.
    """
    profile = hamster_profile(entry)
    data = entry.runtime_data.data
    active = data.night_active_duration_min > 0
    return {
        "name": entry.data[CONF_HAMSTER_NAME],
        "coat_color_hex": profile["coat_color_hex"],
        "health_score": data.health_score,
        "night_distance_km": data.night_distance_km,
        "current_speed_kmh": data.current_speed_kmh,
        "active": active,
        "since_minutes": (
            data.night_active_duration_min if active else data.day_rest_duration_min
        ),
    }


async def async_setup_guest_share(hass: HomeAssistant) -> None:
    """Register the guest routes once, domain-wide.

    Called from `async_setup()` in `__init__.py`, alongside the
    integration's other domain-level (not per-hamster) registrations -
    these two routes serve every hamster through the same URL prefix, so
    they only need registering once regardless of how many config
    entries exist.
    """
    rate_limiter = _RateLimiter(
        GUEST_SHARE_RATE_LIMIT_REQUESTS, GUEST_SHARE_RATE_LIMIT_WINDOW_SECONDS
    )
    hass.http.register_view(GuestPageView(hass, rate_limiter))
    hass.http.register_view(GuestDataView(hass, rate_limiter))
