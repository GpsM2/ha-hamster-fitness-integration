"""Tests for the unauthenticated guest-share feature (#147).

Covers the switch entity's token lifecycle, the two HTTP views'
authorization boundary (valid/unknown/revoked token, cross-hamster
isolation), and the rate limiter's own threshold logic.
"""

from __future__ import annotations

from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    GUEST_URL_PREFIX,
)
from custom_components.hamster_fitness.guest_share import _RateLimiter

# Entity ids are built from the entity NAME ("Guest access", see
# strings.json), not the translation_key ("guest_share") - see the same
# note in test_health_score.py's test_pillar_scores_are_exposed_as_entities.
SWITCH_ENTITY = "switch.hamster_taco_guest_access"


async def _setup_entry(
    hass: HomeAssistant, *, name: str = "Taco", unique_id: str = "taco"
) -> MockConfigEntry:
    """Set up a minimal hamster entry with its own source entities."""
    wheel_sensor = f"sensor.wheel_rotations_{unique_id}"
    temperature_sensor = f"sensor.cage_temperature_{unique_id}"
    hass.states.async_set(wheel_sensor, "0")
    hass.states.async_set(temperature_sensor, "22")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title=name,
        data={
            CONF_HAMSTER_NAME: name,
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: wheel_sensor,
            CONF_TEMPERATURE_SENSOR: temperature_sensor,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_switch_generates_and_revokes_a_token(hass: HomeAssistant) -> None:
    """Turning the switch on mints a token; off deletes it immediately."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    assert coordinator.guest_share_token is None

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": SWITCH_ENTITY}, blocking=True
    )
    await hass.async_block_till_done()
    token = coordinator.guest_share_token
    assert token is not None
    assert len(token) > 30  # secrets.token_urlsafe(32) - roughly 43 chars

    state = hass.states.get(SWITCH_ENTITY)
    assert state.state == "on"
    # A relative path, not a full URL - the card prefixes it with
    # window.location.origin itself. See switch.py for why: a
    # server-computed URL used Home Assistant's configured external_url,
    # which on the live instance was a stale Fritz!Box address nobody
    # actually used to reach it any more.
    assert state.attributes["guest_path"] == f"{GUEST_URL_PREFIX}/{token}"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )
    await hass.async_block_till_done()
    assert coordinator.guest_share_token is None
    assert hass.states.get(SWITCH_ENTITY).state == "off"


async def test_a_new_token_replaces_the_old_one(hass: HomeAssistant) -> None:
    """Off-then-on is the only 'rotate' story - it must yield a fresh token."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_guest_share(True)
    first_token = coordinator.guest_share_token
    await coordinator.async_set_guest_share(False)
    await coordinator.async_set_guest_share(True)
    second_token = coordinator.guest_share_token

    assert second_token is not None
    assert second_token != first_token


async def test_token_survives_a_reload(hass: HomeAssistant) -> None:
    """The token is persisted, not just held in memory."""
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_guest_share(True)
    token = entry.runtime_data.guest_share_token

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.guest_share_token == token


async def test_guest_page_serves_the_shell_regardless_of_token(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """The HTML shell never depends on token validity - see guest_share.py."""
    await _setup_entry(hass)  # the `http` component only starts once this
    # integration is set up (see manifest.json's dependencies)
    client = await hass_client_no_auth()

    resp = await client.get(f"{GUEST_URL_PREFIX}/whatever-nonsense-token")
    assert resp.status == 200
    assert "text/html" in resp.headers["Content-Type"]
    assert resp.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"


async def test_guest_data_endpoint_returns_the_allowlisted_fields(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """A valid token returns exactly the fixed field set, nothing else."""
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_guest_share(True)
    token = entry.runtime_data.guest_share_token

    client = await hass_client_no_auth()
    resp = await client.get(f"{GUEST_URL_PREFIX}/{token}/data")
    assert resp.status == 200
    body = await resp.json()

    assert body["name"] == "Taco"
    assert set(body.keys()) == {
        "generated_at",
        "name",
        "coat_color_hex",
        "health_score",
        "night_distance_km",
        "current_speed_kmh",
        "active",
        "since_minutes",
    }


async def test_guest_data_generated_at_changes_between_responses(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """Two reads must carry different generated_at values.

    The guest page uses this to tell a fresh answer apart from an older
    one replayed by a caching proxy - reported from a real setup, where
    the page looked healthy while Home Assistant was restarting behind a
    reverse proxy. If the value ever stopped changing per response, the
    page would decide it was permanently offline.

    The clock is advanced explicitly rather than left to run: the suite
    pins it (see conftest's fixed_clock), so two calls in the same test
    would otherwise report the same instant and this would assert on a
    test artefact instead of on the endpoint.
    """
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_guest_share(True)
    token = entry.runtime_data.guest_share_token
    client = await hass_client_no_auth()

    with freeze_time("2026-08-09T05:00:00+00:00"):
        first = await (await client.get(f"{GUEST_URL_PREFIX}/{token}/data")).json()
    with freeze_time("2026-08-09T05:00:25+00:00"):
        second = await (await client.get(f"{GUEST_URL_PREFIX}/{token}/data")).json()

    assert first["generated_at"] != second["generated_at"]


async def test_guest_data_endpoint_404s_for_an_unknown_token(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """A token that never existed gets a plain 404."""
    await _setup_entry(hass)
    client = await hass_client_no_auth()

    resp = await client.get(f"{GUEST_URL_PREFIX}/this-token-was-never-issued/data")
    assert resp.status == 404


async def test_guest_data_endpoint_404s_for_a_non_ascii_token(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """A token with non-ASCII characters is just a miss, not a crash.

    Regression test: secrets.compare_digest raises TypeError on str
    arguments containing non-ASCII characters, and the token comes
    straight off the URL. Requesting /guest/caf%C3%A9/data used to turn
    that into a 500 plus a logged traceback - on a route reachable with
    no authentication at all.
    """
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_guest_share(True)
    client = await hass_client_no_auth()

    for probe in ("caf%C3%A9", "%C3%BC%C3%B6%C3%A4", "%E4%B8%AD%E6%96%87"):
        resp = await client.get(f"{GUEST_URL_PREFIX}/{probe}/data")
        assert resp.status == 404, f"{probe} returned {resp.status}"


async def test_guest_data_endpoint_404s_after_revocation(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """A token stops working the instant sharing is turned off."""
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_guest_share(True)
    token = entry.runtime_data.guest_share_token

    await entry.runtime_data.async_set_guest_share(False)

    client = await hass_client_no_auth()
    resp = await client.get(f"{GUEST_URL_PREFIX}/{token}/data")
    assert resp.status == 404


async def test_a_hamsters_token_cannot_read_another_hamsters_data(
    hass: HomeAssistant, hass_client_no_auth
) -> None:
    """Cross-hamster isolation: token A must never resolve to hamster B."""
    taco = await _setup_entry(hass, name="Taco", unique_id="taco")
    fips = await _setup_entry(hass, name="Fips", unique_id="fips")
    await taco.runtime_data.async_set_guest_share(True)
    await fips.runtime_data.async_set_guest_share(True)
    taco_token = taco.runtime_data.guest_share_token
    fips_token = fips.runtime_data.guest_share_token
    assert taco_token != fips_token

    client = await hass_client_no_auth()

    taco_resp = await client.get(f"{GUEST_URL_PREFIX}/{taco_token}/data")
    assert (await taco_resp.json())["name"] == "Taco"

    fips_resp = await client.get(f"{GUEST_URL_PREFIX}/{fips_token}/data")
    assert (await fips_resp.json())["name"] == "Fips"


def test_rate_limiter_blocks_past_its_threshold() -> None:
    """The sliding window allows exactly max_requests, then rejects."""
    limiter = _RateLimiter(max_requests=3, window_seconds=60)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False

    # A different key has its own, untouched budget.
    assert limiter.allow("5.6.7.8") is True
