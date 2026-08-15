"""Tests for the rolling per-night history behind the Running card.

The card draws seven bars from `night_history`, an array the coordinator
maintains itself and persists - the same approach `score_history` already
uses for the health-score trend, rather than querying Home Assistant's
recorder.

Two things here are easy to get wrong and impossible to notice later:

- Which date a night is filed under. A night runs from the evening into
  the next morning, so keying it by the date it *ends* would put Friday
  night's run under Saturday's bar.
- Personal bests must outlive the seven-night window. They are stored
  separately for exactly that reason, so a record set last month still
  stands after it has rolled out of the history.
"""

from __future__ import annotations

import math
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_HUMIDITY_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    NIGHT_HISTORY_NIGHTS,
)
from custom_components.hamster_fitness.coordinator import HamsterFitnessCoordinator

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
HUMIDITY_SENSOR = "sensor.cage_humidity"
DOOR_SENSOR = "binary_sensor.cage_door"
WHEEL_DIAMETER_CM = 28.0
CIRCUMFERENCE_CM = WHEEL_DIAMETER_CM * math.pi


async def _setup(hass: HomeAssistant) -> HamsterFitnessCoordinator:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(HUMIDITY_SENSOR, "55")
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
            CONF_HUMIDITY_SENSOR: HUMIDITY_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


def _close_night(coordinator: HamsterFitnessCoordinator) -> None:
    """Run the night-window reset, the moment a night is recorded."""
    coordinator._async_handle_night_window_reset(dt_util.utcnow())


async def test_closing_a_night_appends_one_entry(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)

    _close_night(coordinator)
    await hass.async_block_till_done()

    history = coordinator.data.night_history
    assert len(history) == 1
    assert set(history[0]) == {
        "date",
        "distance_km",
        "avg_speed_kmh",
        "max_speed_kmh",
        "sessions",
        "temperature_c",
        "humidity_pct",
    }


async def test_a_night_is_filed_under_the_date_it_started(
    hass: HomeAssistant,
) -> None:
    """A night running into the next morning belongs to the evening's date.

    Filing it by the date it ends would shift every bar on the chart one
    day to the right of the night the user actually remembers.
    """
    coordinator = await _setup(hass)
    window_start = coordinator._night_window_start
    assert window_start is not None

    _close_night(coordinator)
    await hass.async_block_till_done()

    expected = dt_util.as_local(window_start).date().isoformat()
    assert coordinator.data.night_history[0]["date"] == expected


async def test_recording_the_same_night_twice_overwrites(
    hass: HomeAssistant,
) -> None:
    """A restart around the reset hour must not double-count one night."""
    coordinator = await _setup(hass)

    _close_night(coordinator)
    await hass.async_block_till_done()
    # The window start moved on, so force it back to re-close the same night.
    first_date = coordinator.data.night_history[0]["date"]
    coordinator._night_window_start = dt_util.parse_datetime(f"{first_date}T20:00:00+00:00")
    _close_night(coordinator)
    await hass.async_block_till_done()

    dates = [item["date"] for item in coordinator.data.night_history]
    assert dates.count(first_date) == 1


async def test_history_is_capped(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)

    base = dt_util.now().replace(hour=20, minute=0, second=0, microsecond=0)
    for offset in range(NIGHT_HISTORY_NIGHTS + 4):
        coordinator._night_window_start = base - timedelta(days=offset)
        _close_night(coordinator)
    await hass.async_block_till_done()

    history = coordinator.data.night_history
    assert len(history) == NIGHT_HISTORY_NIGHTS
    # Distinct nights, not the same one repeated.
    assert len({item["date"] for item in history}) == NIGHT_HISTORY_NIGHTS


async def test_climate_is_averaged_over_the_night(hass: HomeAssistant) -> None:
    """The stored climate is a mean of the night, not the closing reading."""
    coordinator = await _setup(hass)

    # Three samples at different temperatures; the last one deliberately
    # differs from the average, so a snapshot would be visibly wrong.
    for temperature in (20.0, 22.0, 30.0):
        hass.states.async_set(TEMPERATURE_SENSOR, str(temperature))
        await hass.async_block_till_done()
        coordinator._sample_night_climate()

    _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.night_history[0]["temperature_c"] == 24.0


async def test_climate_is_none_without_samples(hass: HomeAssistant) -> None:
    """No readings means no number - not a zero, which would read as freezing."""
    coordinator = await _setup(hass)

    _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.night_history[0]["temperature_c"] is None
    assert coordinator.data.night_history[0]["humidity_pct"] is None


async def test_climate_accumulator_resets_between_nights(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup(hass)

    hass.states.async_set(TEMPERATURE_SENSOR, "30")
    await hass.async_block_till_done()
    coordinator._sample_night_climate()
    _close_night(coordinator)
    await hass.async_block_till_done()

    hass.states.async_set(TEMPERATURE_SENSOR, "18")
    await hass.async_block_till_done()
    coordinator._sample_night_climate()
    coordinator._night_window_start = dt_util.now() - timedelta(days=1)
    _close_night(coordinator)
    await hass.async_block_till_done()

    latest = coordinator.data.night_history[-1]
    assert latest["temperature_c"] == 18.0


async def test_best_night_tracks_the_longest_distance(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)

    base = dt_util.now().replace(hour=20, minute=0, second=0, microsecond=0)
    for offset, distance in enumerate((1.0, 9.0, 4.0)):
        coordinator._night_window_start = base - timedelta(days=offset)
        coordinator.data.night_distance_km = distance
        _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.best_night_km == 9.0
    expected_date = (base - timedelta(days=1)).date().isoformat()
    assert coordinator.data.best_night_date == expected_date


async def test_best_night_outlives_the_rolling_window(hass: HomeAssistant) -> None:
    """A record set long ago still stands once it has rolled out of history."""
    coordinator = await _setup(hass)

    base = dt_util.now().replace(hour=20, minute=0, second=0, microsecond=0)
    coordinator._night_window_start = base - timedelta(days=30)
    coordinator.data.night_distance_km = 42.0
    _close_night(coordinator)

    for offset in range(NIGHT_HISTORY_NIGHTS + 2):
        coordinator._night_window_start = base - timedelta(days=offset)
        coordinator.data.night_distance_km = 1.0
        _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.best_night_km == 42.0
    assert 42.0 not in [
        item["distance_km"] for item in coordinator.data.night_history
    ]


async def test_sessions_are_counted_per_night(hass: HomeAssistant) -> None:
    """Total active time hides the pattern; the count is what shows it.

    Ninety minutes in one go and six bursts of fifteen add up the same,
    so the number of separate sessions is tracked alongside the duration.
    """
    coordinator = await _setup(hass)
    now = dt_util.utcnow()

    # Two pulses inside one session, then a gap long enough to end it,
    # then another pulse - two sessions, not three and not one.
    coordinator._update_activity_session(now, activity_detected=True)
    coordinator._update_activity_session(now + timedelta(minutes=1), True)
    assert coordinator._night_sessions == 1

    later = now + timedelta(hours=3)
    coordinator._update_activity_session(later, activity_detected=False)
    coordinator._update_activity_session(later, activity_detected=True)

    assert coordinator._night_sessions == 2


async def test_session_count_lands_in_the_night_entry(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)

    coordinator._update_activity_session(dt_util.utcnow(), activity_detected=True)
    _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.night_history[0]["sessions"] == 1


async def test_session_count_resets_between_nights(hass: HomeAssistant) -> None:
    """Otherwise every night would inherit the previous night's total."""
    coordinator = await _setup(hass)

    coordinator._update_activity_session(dt_util.utcnow(), activity_detected=True)
    _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.night_sessions == 0

    coordinator._night_window_start = dt_util.now() - timedelta(days=1)
    _close_night(coordinator)
    await hass.async_block_till_done()

    assert coordinator.data.night_history[-1]["sessions"] == 0
