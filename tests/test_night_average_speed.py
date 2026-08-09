"""Tests for the night's average running speed.

night_active_duration_min (the "Läuft seit" chip) only ever covers the
*current* unbroken session - it resets to 0 the moment a new one starts.
The average speed needs the sum across every session so far tonight, so
the coordinator tracks that separately (_night_active_minutes). This
file is about that accumulator, not the chip.

Time is controlled explicitly by patching homeassistant.util.dt.utcnow,
not by pytest-homeassistant-custom-component's async_fire_time_changed:
that helper only fools the scheduler into firing callbacks early (via
homeassistant.helpers.event.time_tracker_utcnow) - it does not affect
dt_util.utcnow() itself, which is exactly what _calculate() reads to
compute elapsed time. Patched time has to be active for every recompute
that should observe it, including the ones triggered indirectly by
hass.states.async_set() + async_block_till_done().
"""

from __future__ import annotations

import math
from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    SESSION_END_GAP_MINUTES,
)
from custom_components.hamster_fitness.coordinator import HamsterFitnessCoordinator

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
WHEEL_DIAMETER_CM = 28.0
CIRCUMFERENCE_CM = WHEEL_DIAMETER_CM * math.pi

HEALTH_SCORE = "sensor.hamster_taco_health_score"


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
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
            CONF_WHEEL_DIAMETER: WHEEL_DIAMETER_CM,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _distance_km(rotations: float) -> float:
    """The same formula the coordinator uses, independently re-derived."""
    return rotations * CIRCUMFERENCE_CM / 100_000.0


async def _set_wheel_at(hass: HomeAssistant, now, rotations: float) -> None:
    """Move the wheel sensor, with `now` active for the recalculation it triggers."""
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(WHEEL_SENSOR, str(rotations))
        await hass.async_block_till_done()


async def _tick_at(
    hass: HomeAssistant, coordinator: HamsterFitnessCoordinator, now
) -> None:
    """Simulate the periodic minute tick recomputing at `now`, wheel untouched."""
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        coordinator.async_set_updated_data(coordinator._calculate())
    await hass.async_block_till_done()


async def test_no_average_below_one_minute_of_activity(hass: HomeAssistant) -> None:
    """A few seconds into a session would just read back the current speed."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    await _set_wheel_at(hass, now, 100)
    await _tick_at(hass, coordinator, now + timedelta(seconds=30))

    assert coordinator.data.night_avg_speed_kmh is None


async def test_average_speed_matches_distance_over_active_time(
    hass: HomeAssistant,
) -> None:
    """Distance covered / wall-clock time the session has been open.

    The wheel only moves once, right at the start - the rest of the ten
    minutes is a hamster standing still mid-session, which still counts
    as active time under the same "short pause doesn't end it" rule the
    single-session duration chip already uses.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    await _set_wheel_at(hass, now, 100)
    now += timedelta(minutes=10)
    await _tick_at(hass, coordinator, now)

    expected = round(_distance_km(100) / (10 / 60), 1)
    assert coordinator.data.night_avg_speed_kmh == expected


async def test_resting_time_before_a_session_does_not_count(
    hass: HomeAssistant,
) -> None:
    """Time before the hamster ever moves must not inflate the average."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    now += timedelta(minutes=5)  # nothing moving yet
    await _tick_at(hass, coordinator, now)

    await _set_wheel_at(hass, now, 100)
    now += timedelta(minutes=2)
    await _tick_at(hass, coordinator, now)

    expected = round(_distance_km(100) / (2 / 60), 1)
    assert coordinator.data.night_avg_speed_kmh == expected


async def test_two_separate_sessions_both_count_toward_the_total(
    hass: HomeAssistant,
) -> None:
    """A gap over SESSION_END_GAP starts a new session, not a new night.

    The first session gets exactly one activity pulse and is then left
    alone past the grace period - so its credited duration is exactly
    SESSION_END_GAP_MINUTES, the same as night_active_duration_min would
    have shown climbing right up to the moment the session was declared
    over (see the cap in _update_activity_session). Anything else in that
    40-minute gap is genuine rest and must not be credited.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    # First session: 100 rotations, then silence past SESSION_END_GAP.
    await _set_wheel_at(hass, now, 100)
    now += timedelta(minutes=40)
    await _tick_at(hass, coordinator, now)

    # Second session: another 50 rotations, active for 2 minutes.
    await _set_wheel_at(hass, now, 150)
    now += timedelta(minutes=2)
    await _tick_at(hass, coordinator, now)

    total_minutes = SESSION_END_GAP_MINUTES + 2
    expected = round(_distance_km(150) / (total_minutes / 60), 1)
    assert coordinator.data.night_avg_speed_kmh == expected


async def test_resets_at_the_night_window(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    await _set_wheel_at(hass, now, 100)
    now += timedelta(minutes=5)
    await _tick_at(hass, coordinator, now)
    assert coordinator.data.night_avg_speed_kmh is not None

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        coordinator._async_handle_night_window_reset(now)
    await hass.async_block_till_done()

    assert coordinator.data.night_avg_speed_kmh is None
    assert coordinator._night_active_minutes == 0.0


async def test_health_score_sensor_exposes_the_average(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    await _set_wheel_at(hass, now, 100)
    now += timedelta(minutes=10)
    await _tick_at(hass, coordinator, now)

    state = hass.states.get(HEALTH_SCORE)
    expected = round(_distance_km(100) / (10 / 60), 1)
    assert state.attributes["night_avg_speed_kmh"] == expected
