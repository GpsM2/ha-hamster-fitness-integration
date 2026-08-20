"""What happens to the distances while the wheel sensor can't be read.

All three cases here were found against live production data on
2026-08-20, after a firmware re-flash took the wheel sensor offline for
two and a half hours. The integration reported a lifetime distance of
0 km and a daily distance equal to the *entire* counter - see issue #137.
"""

from __future__ import annotations

import math

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
DIAMETER = 28.0


def _km(rotations: float) -> float:
    """The distance the integration should derive from `rotations`."""
    return round(rotations * (DIAMETER * math.pi) / 100_000, 3)


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: DIAMETER,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_baseline_waits_instead_of_assuming_zero(hass: HomeAssistant) -> None:
    """A counter unreadable at setup must not make today's baseline 0.

    This is the bug that inflated the history: the baseline fell back to
    0, so once the device came back the *whole* counter was booked as
    distance run in the current window. On the live instance that showed
    up as a daily distance of 5.337 km, matching the counter exactly.

    The baseline now stays open and adopts the first real reading, so
    only what happens *after* the gap is counted.
    """
    hass.states.async_set(WHEEL_SENSOR, "unavailable")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    await _setup_entry(hass)

    # Device returns, carrying a counter that has been running for months.
    hass.states.async_set(WHEEL_SENSOR, "5858")
    await hass.async_block_till_done()

    daily = hass.states.get("sensor.hamster_taco_daily_distance")
    assert daily is not None
    assert float(daily.state) == 0.0, (
        "the counter's whole value was booked as distance run today"
    )

    # And counting resumes normally from there.
    hass.states.async_set(WHEEL_SENSOR, "5958")
    await hass.async_block_till_done()

    daily = hass.states.get("sensor.hamster_taco_daily_distance")
    assert float(daily.state) == _km(100)


async def test_lifetime_holds_its_value_while_sensor_is_away(
    hass: HomeAssistant,
) -> None:
    """Lifetime distance must not read 0 just because the device dropped off.

    It is a `total_increasing` sensor, so a dip to zero is read by Home
    Assistant's statistics engine as a counter reset - the damage
    outlives the outage.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = await _setup_entry(hass)

    hass.states.async_set(WHEEL_SENSOR, "1000")
    await hass.async_block_till_done()

    before = entry.runtime_data.data.lifetime_distance_km
    assert before == _km(1000)

    hass.states.async_set(WHEEL_SENSOR, "unavailable")
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == before

    lifetime = hass.states.get("sensor.hamster_taco_lifetime_distance")
    assert lifetime is not None
    assert float(lifetime.state) == before


async def test_lifetime_survives_a_reload_with_the_sensor_away(
    hass: HomeAssistant,
) -> None:
    """The value must come back after a reload, not restart from zero.

    This is the case that actually bit: the device was offline *and* the
    entry re-set-up, so the in-memory fallback was a fresh snapshot whose
    distances are all 0.0. The fallback now comes from the persisted
    state instead.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = await _setup_entry(hass)

    hass.states.async_set(WHEEL_SENSOR, "1000")
    await hass.async_block_till_done()
    before = entry.runtime_data.data.lifetime_distance_km
    assert before == _km(1000)

    hass.states.async_set(WHEEL_SENSOR, "unavailable")
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.data.lifetime_distance_km == before
