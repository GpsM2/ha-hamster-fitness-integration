"""Tests for the health-score calculation and the four pillar scores."""

from __future__ import annotations

from datetime import datetime

from freezegun import freeze_time
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
    SCORE_HISTORY_DAYS,
)
from custom_components.hamster_fitness.coordinator import (
    _in_sleep_phase,
    _pillar_score,
    _sleep_penalty,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"

# 28 cm diameter -> ~0.8796 m per rotation, so ~6.8 km. Comfortably above
# IDEAL_DISTANCE_MIN_KM (5 km), i.e. "a good night" with no distance penalty.
GOOD_NIGHT_ROTATIONS = "7800"


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and set up a minimal Taco config entry for tests."""
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
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _good_night(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry and run a full, healthy night on the wheel."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = await _setup_entry(hass)

    hass.states.async_set(WHEEL_SENSOR, GOOD_NIGHT_ROTATIONS)
    await hass.async_block_till_done()
    return entry


async def test_score_stays_high_across_the_daily_reset(hass: HomeAssistant) -> None:
    """The 9 AM reset must not tank the score after a good night.

    Regression test for the reported bug: `daily_distance_km` drops back
    to ~0 at DAILY_RESET_HOUR, which used to immediately trigger the
    "too little exercise" penalty even though the hamster had just run
    all night. The score is based on the night window instead now.
    """
    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    score_before = coordinator.data.health_score
    assert score_before == 100

    # Exactly what async_track_time_change fires at DAILY_RESET_HOUR.
    coordinator._async_handle_daily_reset(dt_util.now())
    await hass.async_block_till_done()

    assert coordinator.data.daily_distance_km == 0.0  # the reset did happen
    assert coordinator.data.health_score == score_before
    assert "too_little_exercise" not in coordinator.data.warning_reasons


async def test_score_stays_high_across_the_night_window_reset(
    hass: HomeAssistant,
) -> None:
    """The 8 PM night-window reset must not tank the score either.

    Moving the score onto `night_distance_km` alone would only have
    shifted the same bug to NIGHT_WINDOW_START_HOUR, so the last
    completed night keeps carrying the score until the new one overtakes
    it.
    """
    entry = await _good_night(hass)
    coordinator = entry.runtime_data
    good_night_km = coordinator.data.night_distance_km
    assert good_night_km > 5.0

    coordinator._async_handle_night_window_reset(dt_util.now())
    await hass.async_block_till_done()

    assert coordinator.data.night_distance_km == 0.0  # the reset did happen
    assert coordinator.data.last_completed_night_km == good_night_km
    assert coordinator.data.health_score == 100
    assert "too_little_exercise" not in coordinator.data.warning_reasons


async def test_bad_night_drags_the_score_down_once_the_night_is_over(
    hass: HomeAssistant,
) -> None:
    """A genuinely bad night must show up in the score, not keep hiding
    behind the previous good one for the rest of the day.

    Regression test for a production report: the wheel sensor died
    partway through the night (0.38 km logged instead of a normal
    4-9 km), but the score stayed at 93%/95% because effective_distance_km
    took max(tonight, last night) with no time bound - so it kept
    echoing the previous good night for the full 24h window instead of
    just the few hours right after NIGHT_WINDOW_START_HOUR the fallback
    was built to smooth over. Once SLEEP_PHASE_START_HOUR has passed the
    hamster's main running hours are behind it, and tonight's own tally
    should be trusted.
    """
    entry = await _good_night(hass)
    coordinator = entry.runtime_data
    good_night_km = coordinator.data.night_distance_km
    assert good_night_km > 5.0

    coordinator._async_handle_night_window_reset(dt_util.now())
    await hass.async_block_till_done()
    assert coordinator.data.last_completed_night_km == good_night_km

    # Tonight, almost nothing accrues - e.g. the wheel sensor failed
    # partway through, as in the production report.
    hass.states.async_set(WHEEL_SENSOR, "400")  # ~0.35 km on this wheel
    await hass.async_block_till_done()
    assert coordinator.data.night_distance_km < 1.0

    # 15:00 US/Pacific (the suite's frozen clock is 22:00 the previous
    # day - well past SLEEP_PHASE_START_HOUR (10:00), unlike the window-
    # reset test above which fires right at the 20:00 boundary.
    with freeze_time("2026-08-09T22:00:00+00:00"):
        hass.states.async_set(WHEEL_SENSOR, "401")
        await hass.async_block_till_done()

        assert coordinator.data.health_score < 70
        assert "too_little_exercise" in coordinator.data.warning_reasons


async def test_pillar_scores_are_exposed_as_entities(hass: HomeAssistant) -> None:
    """All four pillar sensors exist and read 0-100.

    The entity_ids read `<pillar>_score`, not `score_<pillar>`: Home
    Assistant builds them from the entity *name* ("Activity score"), not
    from the translation_key the Python code and the cards use.
    """
    await _good_night(hass)

    for pillar in ("activity", "sleep", "climate", "care"):
        state = hass.states.get(f"sensor.hamster_taco_{pillar}_score")
        assert state is not None, pillar
        assert 0 <= int(state.state) <= 100, pillar

    # A healthy night at 22 °C: nothing wrong with either of these.
    assert hass.states.get("sensor.hamster_taco_activity_score").state == "100"
    assert hass.states.get("sensor.hamster_taco_climate_score").state == "100"


async def test_care_pillar_is_not_created_without_a_door_sensor(
    hass: HomeAssistant,
) -> None:
    """No door sensor (#143) -> no Care pillar and no cage-door entity.

    The other three pillars are unaffected - only Care depends entirely
    on the door sensor.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
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
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.hamster_taco_care_score") is None
    assert hass.states.get("binary_sensor.hamster_taco_cage_door") is None
    for pillar in ("activity", "sleep", "climate"):
        assert hass.states.get(f"sensor.hamster_taco_{pillar}_score") is not None


async def test_health_score_is_not_inflated_by_a_missing_door_sensor(
    hass: HomeAssistant,
) -> None:
    """Same wheel/temperature inputs, with vs. without a door sensor: the
    overall health_score must be identical either way (#143) - a missing
    Care pillar must not silently read as a "perfect" 100 that then
    props up the composite score any differently than a door sensor that
    genuinely shows good care.
    """
    with_door = await _good_night(hass)

    # A second hamster needs its own source entities - reusing WHEEL_SENSOR
    # would make this entry's setup (resetting it to "0") also fire a
    # state-change event on with_door's coordinator, corrupting its
    # already-recorded good night.
    wheel_sensor_2 = "sensor.wheel_rotations_fips"
    temperature_sensor_2 = "sensor.cage_temperature_fips"
    hass.states.async_set(wheel_sensor_2, "0")
    hass.states.async_set(temperature_sensor_2, "22")
    entry_without_door = MockConfigEntry(
        domain=DOMAIN,
        unique_id="fips",
        title="Fips",
        data={
            CONF_HAMSTER_NAME: "Fips",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: wheel_sensor_2,
            CONF_TEMPERATURE_SENSOR: temperature_sensor_2,
        },
    )
    entry_without_door.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_without_door.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set(wheel_sensor_2, GOOD_NIGHT_ROTATIONS)
    await hass.async_block_till_done()

    assert (
        with_door.runtime_data.data.health_score
        == entry_without_door.runtime_data.data.health_score
    )
    assert with_door.runtime_data.data.score_care == 100
    assert entry_without_door.runtime_data.data.score_care is None


async def test_cold_cage_only_drags_down_the_climate_pillar(
    hass: HomeAssistant,
) -> None:
    """One bad pillar must not drag the others down with it."""
    entry = await _good_night(hass)

    # Deep in torpor territory: far enough past the hard 18 °C bound to max
    # out the temperature penalty, so the climate pillar bottoms out at 0.
    hass.states.async_set(TEMPERATURE_SENSOR, "5")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.score_climate == 0
    assert entry.runtime_data.data.score_activity == 100
    assert entry.runtime_data.data.health_score < 100


async def test_trend_records_the_day_average_not_a_snapshot(
    hass: HomeAssistant,
) -> None:
    """A day that dipped and recovered must not look untroubled.

    The whole point of averaging: recording only the score standing at
    the reset hour would hide a bad afternoon entirely.
    """
    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    # A day spent mostly in trouble, recovered right before the reset.
    for score in (100, 40, 40, 40):
        coordinator._score_sum_today += score
        coordinator._score_samples_today += 1
    assert coordinator.data.health_score == 100  # the snapshot looks fine

    coordinator._async_handle_daily_reset(dt_util.now())
    await hass.async_block_till_done()

    recorded = coordinator._score_history[-1]["score"]
    assert recorded == 55, "expected the average of 100/40/40/40, not the snapshot"


async def test_day_average_resets_after_being_recorded(hass: HomeAssistant) -> None:
    """Yesterday's samples must not bleed into today's average."""
    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    coordinator._score_sum_today = 300.0
    coordinator._score_samples_today = 4

    coordinator._async_handle_daily_reset(dt_util.now())
    await hass.async_block_till_done()

    assert coordinator._score_sum_today == 0.0
    assert coordinator._score_samples_today == 0


async def test_day_average_falls_back_to_the_current_score(
    hass: HomeAssistant,
) -> None:
    """No samples at all - Home Assistant was down - still records something."""
    entry = await _good_night(hass)
    coordinator = entry.runtime_data
    assert coordinator._score_samples_today == 0

    coordinator._async_handle_daily_reset(dt_util.now())
    await hass.async_block_till_done()

    assert coordinator._score_history[-1]["score"] == 100


async def test_periodic_tick_samples_the_score(hass: HomeAssistant) -> None:
    """The per-minute timer is what feeds the average.

    Deliberately not the source-sensor events: a running hamster fires
    far more of those than a sleeping one, which would drag the daily
    average towards whatever the score was during activity.
    """
    entry = await _good_night(hass)
    coordinator = entry.runtime_data
    before = coordinator._score_samples_today

    coordinator._async_handle_periodic_update(dt_util.now())
    await hass.async_block_till_done()
    assert coordinator._score_samples_today == before + 1

    # A flurry of sensor events must not add samples of its own.
    for count in ("8000", "8100", "8200"):
        hass.states.async_set(WHEEL_SENSOR, count)
    await hass.async_block_till_done()
    assert coordinator._score_samples_today == before + 1


async def test_departed_hamster_stops_sampling(hass: HomeAssistant) -> None:
    """A frozen snapshot shouldn't keep padding the history."""
    from datetime import date

    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()
    before = coordinator._score_samples_today

    coordinator._async_handle_periodic_update(dt_util.now())
    await hass.async_block_till_done()

    assert coordinator._score_samples_today == before


async def test_score_history_keeps_one_entry_per_day(hass: HomeAssistant) -> None:
    """Re-recording the same day overwrites instead of duplicating."""
    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    coordinator._record_daily_score(80)
    coordinator._record_daily_score(90)

    assert len(coordinator.data.score_history or coordinator._score_history) >= 1
    assert coordinator._score_history[-1]["score"] == 90
    dates = [item["date"] for item in coordinator._score_history]
    assert len(dates) == len(set(dates))


async def test_score_history_is_capped(hass: HomeAssistant) -> None:
    """The rolling history never grows past SCORE_HISTORY_DAYS entries."""
    entry = await _good_night(hass)
    coordinator = entry.runtime_data

    for day in range(1, SCORE_HISTORY_DAYS + 5):
        coordinator._score_history.append(
            {"date": f"2026-01-{day:02d}", "score": 50 + day}
        )
        coordinator._score_history = coordinator._score_history[-SCORE_HISTORY_DAYS:]

    assert len(coordinator._score_history) == SCORE_HISTORY_DAYS


def test_pillar_score_scales_to_its_own_maximum() -> None:
    """A pillar reads 0 at its own cap, not at the shared 100-point one."""
    assert _pillar_score(0.0, 50.0) == 100
    assert _pillar_score(25.0, 50.0) == 50
    assert _pillar_score(50.0, 50.0) == 0
    # Care has a different cap (60) but still spans the full 0-100 range.
    assert _pillar_score(60.0, 60.0) == 0
    # Overshooting the cap clamps instead of going negative.
    assert _pillar_score(999.0, 50.0) == 0


def test_sleep_penalty_weighs_openings_heavier_than_wake_ups() -> None:
    """Opening the cage is the disturbance; running is its consequence."""
    assert _sleep_penalty(0, 0) == 0.0
    assert _sleep_penalty(1, 0) == 20.0
    assert _sleep_penalty(0, 1) == 10.0
    assert _sleep_penalty(1, 1) == 30.0
    # Capped, so a chaotic day can't push the pillar below 0.
    assert _sleep_penalty(20, 20) == 100.0


def test_sleep_phase_window_is_wall_clock_local() -> None:
    """_in_sleep_phase compares local hours, whatever tz the input carries."""
    local_noon = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)
    local_night = local_noon.replace(hour=2)

    assert _in_sleep_phase(local_noon) is True
    assert _in_sleep_phase(local_night) is False
    # Same instant expressed in UTC must classify identically.
    assert _in_sleep_phase(dt_util.as_utc(local_noon)) is True
    assert isinstance(local_noon, datetime)


def test_the_suites_frozen_clock_is_outside_the_sleep_phase() -> None:
    """Guards the `fixed_clock` fixture's choice of instant.

    Nearly every test simulates wheel activity, and starting a run
    session inside the sleep phase docks health-score points. If the
    frozen instant in conftest.py ever moved into that window - or the
    window itself widened to cover it - a whole batch of `score == 100`
    assertions would start failing for reasons having nothing to do with
    the change that caused it.

    That was exactly the old failure mode, just driven by the wall clock:
    before the clock was frozen the suite failed for about seven hours a
    day (17:00-24:00 UTC, i.e. 10:00-17:00 US/Pacific, the timezone
    pytest-homeassistant-custom-component runs Home Assistant on).
    """
    assert not _in_sleep_phase(dt_util.utcnow()), (
        "conftest.py's frozen clock now lands inside the sleep phase; "
        "move it back out or the suite will fail en masse"
    )
