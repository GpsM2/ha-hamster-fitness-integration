"""Tests for boarding mode - a temporary absence, not a departure.

The distinction that matters throughout: a departure date is permanent
and archives the hamster; boarding pauses evaluation and archives
nothing. Both suspend scoring, so the coordinator asks `_is_paused()`
rather than distinguishing them everywhere.
"""

from __future__ import annotations

from datetime import date

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hamster_fitness import archive
from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_NOTIFY_SERVICES,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    OPTION_WEIGHT_REMINDER_ENABLED,
)
from custom_components.hamster_fitness.notify import HamsterFitnessNotifier

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
NOTIFY_TARGET = "notify.mobile_app_phone"

BOARDING_SWITCH = "switch.hamster_taco_boarding"


async def _setup_entry(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    """Set up a Taco entry that has already run a bit."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
            CONF_NOTIFY_SERVICES: [NOTIFY_TARGET],
        },
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(WHEEL_SENSOR, "5000")
    await hass.async_block_till_done()
    return entry


async def test_switch_exists_and_defaults_to_home(hass: HomeAssistant) -> None:
    """Every hamster gets the switch, off by default."""
    await _setup_entry(hass)

    state = hass.states.get(BOARDING_SWITCH)
    assert state is not None
    assert state.state == "off"


async def test_boarding_freezes_the_snapshot(hass: HomeAssistant) -> None:
    """An empty cage must not drag the score down."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    frozen_km = coordinator.data.night_distance_km
    assert frozen_km > 0

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": BOARDING_SWITCH}, blocking=True
    )
    assert coordinator.boarding is True

    # Cage goes cold and the wheel stops - neither should register.
    hass.states.async_set(TEMPERATURE_SENSOR, "5")
    hass.states.async_set(WHEEL_SENSOR, "5000")
    await hass.async_block_till_done()

    assert coordinator.data.night_distance_km == frozen_km
    assert coordinator.data.score_climate == 100
    assert coordinator.data.warning_on is False


async def test_boarding_does_not_archive(hass: HomeAssistant) -> None:
    """The whole point: a temporary absence is not a departure."""
    entry = await _setup_entry(hass)

    await entry.runtime_data.async_set_boarding(True)
    await hass.async_block_till_done()

    assert await archive.async_load(hass) == []
    assert entry.runtime_data.departure_date is None


async def test_returning_home_resumes_without_inventing_distance(
    hass: HomeAssistant,
) -> None:
    """Rotations clocked up while away must not land on the hamster.

    Same hazard as undoing a departure: the wheel keeps counting while
    the coordinator ignores it, so resuming against the old baseline
    would credit somebody else's running to this hamster.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    lifetime_before = coordinator.data.lifetime_distance_km

    await coordinator.async_set_boarding(True)
    await hass.async_block_till_done()

    hass.states.async_set(WHEEL_SENSOR, "900000")
    await hass.async_block_till_done()

    await coordinator.async_set_boarding(False)
    await hass.async_block_till_done()

    assert coordinator.data.night_distance_km == 0.0
    assert coordinator.data.daily_distance_km == 0.0
    assert coordinator.data.lifetime_distance_km == pytest.approx(
        lifetime_before, abs=0.01
    )

    # ...and normal counting works again from here.
    hass.states.async_set(WHEEL_SENSOR, "901000")
    await hass.async_block_till_done()
    assert coordinator.data.night_distance_km > 0.0


async def test_boarding_survives_a_reload(hass: HomeAssistant) -> None:
    """An absent hamster must not silently come back on restart."""
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_boarding(True)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.boarding is True
    assert hass.states.get(BOARDING_SWITCH).state == "on"


async def test_daily_notifications_stay_quiet_while_away(
    hass: HomeAssistant,
) -> None:
    """No summary and no weigh-in nudge for a hamster at the vet."""
    sent = async_mock_service(hass, "notify", "send_message")
    entry = await _setup_entry(hass, options={OPTION_WEIGHT_REMINDER_ENABLED: True})
    coordinator = entry.runtime_data

    await coordinator.async_set_boarding(True)
    await hass.async_block_till_done()
    sent.clear()

    notifier = HamsterFitnessNotifier(hass, entry, coordinator)
    notifier._async_handle_daily_time(None)
    await hass.async_block_till_done()

    assert sent == []


async def test_score_sampling_pauses_while_away(hass: HomeAssistant) -> None:
    """A frozen score shouldn't pad the daily average."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_boarding(True)
    await hass.async_block_till_done()
    before = coordinator._score_samples_today

    coordinator._sample_score()
    assert coordinator._score_samples_today == before


async def test_boarding_and_departure_are_independent(
    hass: HomeAssistant,
) -> None:
    """Coming back from boarding must not resurrect a departed hamster."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_boarding(True)
    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    await coordinator.async_set_boarding(False)
    await hass.async_block_till_done()

    # Still departed, still archived - boarding only owns its own flag.
    assert coordinator.departure_date == date(2026, 8, 1)
    assert len(await archive.async_load(hass)) == 1
