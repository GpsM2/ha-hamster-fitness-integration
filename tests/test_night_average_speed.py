"""Tests for the night's average running speed.

night_avg_speed_kmh divides distance by _night_moving_minutes: the sum of
pulse-to-pulse gaps short enough (MOVING_PULSE_GAP) to mean the wheel kept
turning, across every session so far tonight. Deliberately NOT the same as
night_active_duration_min (the "Läuft seit" chip, current session only) or
the session-stitching SESSION_END_GAP (15 min) used to decide whether a
pause starts a new session - both answer a different question than "how
fast, while moving".

This distinction is the point of this file. Reported from a real instance:
a night with four sessions averaged 1.5 km/h against a 12.6 km/h peak,
because the old denominator credited an entire session's wall-clock span -
including a pause tolerated well past MOVING_PULSE_GAP - as "active".

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
from datetime import datetime, timedelta
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
    MOVING_PULSE_GAP_SECONDS,
)
from custom_components.hamster_fitness.coordinator import HamsterFitnessCoordinator

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
WHEEL_DIAMETER_CM = 28.0
CIRCUMFERENCE_CM = WHEEL_DIAMETER_CM * math.pi

HEALTH_SCORE = "sensor.hamster_taco_health_score"

# Comfortably under MOVING_PULSE_GAP_SECONDS (5s), so tests don't ride the
# exact boundary.
CLOSE_GAP = timedelta(seconds=3)
assert CLOSE_GAP.total_seconds() < MOVING_PULSE_GAP_SECONDS

# A burst this long clears MIN_ACTIVE_MINUTES_FOR_AVERAGE (1 minute) on its
# own, with margin: 25 gaps * 3s = 75s = 1.25 min. Used wherever a test
# needs a defined average from a single burst, so the exact pulse count
# doesn't have to be re-derived at every call site.
QUALIFYING_PULSES = 26


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


async def _set_wheel_at(hass: HomeAssistant, now: datetime, rotations: float) -> None:
    """Move the wheel sensor, with `now` active for the recalculation it triggers."""
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(WHEEL_SENSOR, str(rotations))
        await hass.async_block_till_done()


async def _tick_at(
    hass: HomeAssistant, coordinator: HamsterFitnessCoordinator, now: datetime
) -> None:
    """Simulate the periodic minute tick recomputing at `now`, wheel untouched."""
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        coordinator.async_set_updated_data(coordinator._calculate())
    await hass.async_block_till_done()


async def _burst(
    hass: HomeAssistant,
    start_now: datetime,
    *,
    pulses: int,
    gap: timedelta,
    rotations_start: float,
    rotations_per_pulse: float = 1.0,
) -> tuple[datetime, float, float]:
    """Fire `pulses` wheel events `gap` apart, each `rotations_per_pulse` further on.

    Returns (end_time, rotations_after, moving_minutes_this_burst_should_add) -
    the last purely as a convenience so tests can build `expected` without
    re-deriving the credit rule by hand. The first pulse of any burst never
    adds moving time on its own (nothing to compare its gap against) - only
    matters here if this burst is the very first activity ever for the
    entry; a burst resuming after a longer gap elsewhere in a test doesn't
    get special-cased, its first pulse simply credits nothing either way,
    matching the coordinator.
    """
    now = start_now
    rotations = rotations_start
    for i in range(pulses):
        if i > 0:
            now += gap
        rotations += rotations_per_pulse
        await _set_wheel_at(hass, now, rotations)
    moving_minutes = (pulses - 1) * gap.total_seconds() / 60 if pulses > 1 else 0.0
    return now, rotations, moving_minutes


async def test_no_average_without_enough_moving_time(hass: HomeAssistant) -> None:
    """Two pulses close together, but not enough of them to reach a minute."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    # 3 pulses at 3s apart = 6s of credited moving time - nowhere near the
    # 60s (MIN_ACTIVE_MINUTES_FOR_AVERAGE) needed to show an average.
    await _burst(hass, now, pulses=3, gap=CLOSE_GAP, rotations_start=0)

    assert coordinator.data.night_avg_speed_kmh is None


async def test_a_long_pause_within_a_session_does_not_count(
    hass: HomeAssistant,
) -> None:
    """The exact bug reported from production, reconstructed directly.

    A session that stays open across a multi-minute pause (tolerated by
    SESSION_END_GAP, so it stays one session) must not have that pause
    counted as time spent moving - only the two bursts of real activity
    either side of it.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    # First burst: enough close pulses to clear the 1-minute floor on its own.
    now, rotations, moving_1 = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=0
    )
    assert moving_1 * 60 >= 60, "test setup: first burst alone must already qualify"

    # A real pause: 5 minutes of nothing, well past MOVING_PULSE_GAP but
    # comfortably inside SESSION_END_GAP (15 min), so the session survives.
    now += timedelta(minutes=5)

    # Second burst, resumes the same session.
    now, rotations, moving_2 = await _burst(
        hass, now, pulses=6, gap=CLOSE_GAP, rotations_start=rotations
    )

    await _tick_at(hass, coordinator, now)

    expected_moving_minutes = moving_1 + moving_2
    expected = round(
        _distance_km(rotations) / (expected_moving_minutes / 60),
        1,
    )
    assert coordinator.data.night_avg_speed_kmh == expected

    # And the old, wrong number - distance over the ENTIRE session span,
    # 5-minute pause included - would have been noticeably lower. Pinning
    # this the reader can see the fix actually changed the answer, not
    # just the code path.
    wrong_session_span_minutes = (
        (11 - 1) * CLOSE_GAP.total_seconds() / 60
        + 5
        + (6 - 1) * CLOSE_GAP.total_seconds() / 60
    )
    wrong = round(_distance_km(rotations) / wrong_session_span_minutes, 1)
    assert expected > wrong


async def test_resting_time_before_a_session_does_not_count(
    hass: HomeAssistant,
) -> None:
    """Time before the hamster ever moves must not inflate the average."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    now += timedelta(minutes=5)  # nothing moving yet
    await _tick_at(hass, coordinator, now)

    now, rotations, moving = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=0
    )
    await _tick_at(hass, coordinator, now)

    expected = round(_distance_km(rotations) / (moving / 60), 1)
    assert coordinator.data.night_avg_speed_kmh == expected


async def test_two_separate_sessions_both_count_toward_the_total(
    hass: HomeAssistant,
) -> None:
    """A gap over SESSION_END_GAP starts a new session, not a new night.

    Moving minutes accumulate across the whole night regardless of the
    session boundary - only the size of each burst's own credited gaps
    matters, not which session they belong to.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    now, rotations, moving_1 = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=0
    )

    now += timedelta(minutes=40)  # past SESSION_END_GAP - new session starts next

    now, rotations, moving_2 = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=rotations
    )
    await _tick_at(hass, coordinator, now)

    expected = round(_distance_km(rotations) / ((moving_1 + moving_2) / 60), 1)
    assert coordinator.data.night_avg_speed_kmh == expected


async def test_resets_at_the_night_window(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    now, _rotations, _moving = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=0
    )
    await _tick_at(hass, coordinator, now)
    assert coordinator.data.night_avg_speed_kmh is not None

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        coordinator._async_handle_night_window_reset(now)
    await hass.async_block_till_done()

    assert coordinator.data.night_avg_speed_kmh is None
    assert coordinator._night_moving_minutes == 0.0


async def test_health_score_sensor_exposes_the_average(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    now = dt_util.utcnow()

    now, rotations, moving = await _burst(
        hass, now, pulses=QUALIFYING_PULSES, gap=CLOSE_GAP, rotations_start=0
    )
    await _tick_at(hass, coordinator, now)

    state = hass.states.get(HEALTH_SCORE)
    expected = round(_distance_km(rotations) / (moving / 60), 1)
    assert state.attributes["night_avg_speed_kmh"] == expected
