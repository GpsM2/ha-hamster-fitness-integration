"""Shared test fixtures for the Hamster Fitness test suite."""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_socket
from freezegun import freeze_time
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState

from custom_components.hamster_fitness.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


if not hasattr(config_entries, "OptionsFlowWithReload"):
    # manifest.json requires Home Assistant 2026.3.0, where
    # OptionsFlowWithReload (added in 2025.8) has long existed. The newest
    # pytest-homeassistant-custom-component release still pins an older
    # Core, so importing config_flow.py - and with it setting up ANY entry -
    # would blow up here for a reason that cannot occur in a supported
    # installation. Backfill the class so the suite is runnable; the only
    # thing lost is the automatic entry reload on option changes, which no
    # test asserts on. Disappears by itself once the pinned Core catches up.
    class _OptionsFlowWithReload(config_entries.OptionsFlow):  # type: ignore[misc]
        """Minimal stand-in for older Home Assistant Core versions."""

    config_entries.OptionsFlowWithReload = _OptionsFlowWithReload  # type: ignore[attr-defined]


if sys.platform == "win32":
    # aiohttp's test client (hass_client/hass_client_no_auth - see
    # test_guest_share.py) builds a real TCPConnector, which resolves
    # DNS through `aiodns` whenever that package happens to be importable
    # (it is here, pulled in transitively). aiodns hard-requires a
    # SelectorEventLoop, but Home Assistant's own event loop policy
    # (HassEventLoopPolicy, subclassing asyncio.DefaultEventLoopPolicy)
    # runs ProactorEventLoop on Windows - so every test that spins up an
    # aiohttp client fails with "aiodns needs a SelectorEventLoop on
    # Windows" before a single request goes out, despite every request
    # in this suite staying on loopback and never needing real DNS at
    # all. `aiohttp.connector` binds `DefaultResolver` into its own
    # module namespace at import time (`from .resolver import
    # DefaultResolver`), so the swap has to happen there, not on
    # `aiohttp.resolver` - by the time this module runs, `homeassistant`
    # has already imported `aiohttp.connector` and captured the old
    # reference.
    import aiohttp.connector
    import aiohttp.resolver

    aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

    def _allow_loopback_sockets(allow_unix_socket: bool = False) -> None:
        """Let asyncio create its self-pipe socket on Windows.

        pytest-homeassistant-custom-component blocks all sockets per test
        and re-allows only AF_UNIX ones, which is enough on Linux/macOS:
        `socket.socketpair()` is an AF_UNIX pair there. Windows has no
        AF_UNIX socketpair, so asyncio's event loop falls back to a
        loopback AF_INET pair - which the blanket block rejects before a
        single test can even get its event loop, making the entire suite
        unrunnable on a Windows dev machine.

        This replaces `pytest_socket.disable_socket` itself rather than
        undoing it from a hook: the plugin re-applies the block on every
        single test from its own `pytest_runtest_setup`, so any attempt to
        re-enable afterwards is a hook-ordering race. Swapping the
        function out once, at import time, is deterministic.

        Sockets stay constructible, but connections remain restricted to
        loopback, so the actual point of the block - no test ever reaching
        the real network - still holds. Other platforms are untouched and
        keep pytest-socket's strict default.
        """
        pytest_socket.enable_socket()
        pytest_socket.socket_allow_hosts(["127.0.0.1", "::1"])

    pytest_socket.disable_socket = _allow_loopback_sockets


@pytest.fixture(autouse=True)
def fixed_clock(request: pytest.FixtureRequest) -> Generator[None]:
    """Pin the wall clock, so the suite doesn't depend on when it runs.

    The health score docks points for disturbances during the hamster's
    main sleep phase (SLEEP_PHASE_START_HOUR..END_HOUR, 10:00-17:00
    *local* time - see _in_sleep_phase). Starting a run session inside
    that window counts as one. Almost every test simulates wheel
    activity, and several then assert `health_score == 100`.

    pytest-homeassistant-custom-component runs Home Assistant on
    US/Pacific, so those assertions quietly held or failed depending on
    the time of day the suite happened to run: green at 13:00 UTC
    (06:00 Pacific), red at 18:00 UTC (11:00 Pacific). That is roughly
    seven hours a day - 17:00 to 24:00 UTC - during which the whole
    suite failed for no reason connected to the code, CI included.

    Freezing at 05:00 UTC puts local time at 22:00 Pacific: the middle of
    a hamster's active phase, which is both outside the sleep window and
    the state these tests are actually describing.

    Tests that need time to pass advance it explicitly - either by
    patching dt_util.utcnow (see test_night_average_speed.py) or through
    async_fire_time_changed - so nothing here depends on the clock
    ticking by itself.
    """
    if "no_fixed_clock" in request.keywords:
        yield
        return
    with freeze_time("2026-08-09T05:00:00+00:00"):
        yield


@pytest.fixture(autouse=True)
async def unload_entries_after_test(request: pytest.FixtureRequest) -> AsyncGenerator[None]:
    """Unload every Hamster Fitness entry a test left behind.

    Stopping Home Assistant does not unload config entries, so the
    listeners each entry registers through `entry.async_on_unload()` -
    the daily-reset timers, the notifier's summary timer - stay armed and
    trip the harness's lingering-timer check. Unloading here is what a
    real Home Assistant does when the integration is removed or reloaded,
    so it also exercises that path on every test for free.

    Skipped for tests that never asked for `hass` (the pure-function
    ones), so they don't pay for spinning one up.
    """
    yield

    hass = request.node.funcargs.get("hass")
    if hass is None:
        return
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def expected_lingering_tasks() -> bool:
    """Tolerate the HTTP server's accept loop outliving a test on Windows.

    This integration depends on `frontend`, which pulls in `http`, so every
    test spins up a real aiohttp server. On Windows its
    `IocpProactor.accept` task survives `hass.async_stop()` long enough for
    the harness to flag it (and to keep port 8123 bound for the next test).
    Nothing in this repo can cancel that task, and the failure is pure
    teardown noise.

    Deliberately narrow: only the *task* check is relaxed, and only here.
    `expected_lingering_timers` stays strict, since that one catches real
    bugs in this integration's own timers - it did exactly that for the
    per-minute duration timer, which was missing `cancel_on_shutdown`.
    """
    return sys.platform == "win32"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Allow hass to load custom_components/ during tests.

    pytest-homeassistant-custom-component blocks loading anything outside
    HA Core by default, as a safety net for HA Core's own test suite. This
    repo IS a custom integration, so every test needs it enabled.
    """
    yield
