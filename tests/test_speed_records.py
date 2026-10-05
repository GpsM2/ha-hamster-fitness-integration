"""Speed records count what was sustained, not what was glimpsed (#168).

Against a production instance, running sat tightly between 2 and 4 km/h
(median 2.87, 99th percentile 3.82) while the nightly maximum was 11-13
km/h every single night: isolated glitch pulses, capped only by the
firmware's 250 ms cooldown. A record now needs the speed held over
SUSTAINED_SPEED_READINGS consecutive readings.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_HAMSTER_NAME,
    CONF_SPEED_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    SPEED_TRUST_VERSION,
    STORAGE_VERSION,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
SPEED_SENSOR = "sensor.wheel_speed"
ENTRY_ID = "tacoentry"
STORE_KEY = f"{DOMAIN}_{ENTRY_ID}_baseline"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(SPEED_SENSOR, "0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 29.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_SPEED_SENSOR: SPEED_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _speeds(hass: HomeAssistant, *values: str) -> None:
    for value in values:
        hass.states.async_set(SPEED_SENSOR, value)
        await hass.async_block_till_done()


async def test_a_single_glitch_does_not_set_a_record(hass: HomeAssistant) -> None:
    """The production pattern: steady running with one spike in between."""
    entry = await _setup(hass)

    await _speeds(hass, "3.0", "12.7", "3.1")

    data = entry.runtime_data.data
    assert data.max_speed_tonight_kmh == 3.0
    assert data.lifetime_max_speed_kmh == 3.0


async def test_a_sustained_sprint_counts(hass: HomeAssistant) -> None:
    """A real burst lasts several turns - its lowest reading is the record."""
    entry = await _setup(hass)

    await _speeds(hass, "5.0", "5.4", "5.2")

    data = entry.runtime_data.data
    assert data.max_speed_tonight_kmh == 5.0
    assert data.lifetime_max_speed_kmh == 5.0
    assert data.lifetime_max_speed_date is not None


async def test_a_stop_breaks_the_run(hass: HomeAssistant) -> None:
    """Readings either side of a stop are not one sustained run."""
    entry = await _setup(hass)

    await _speeds(hass, "6.0", "6.1", "0", "6.2")

    assert entry.runtime_data.data.max_speed_tonight_kmh is None


async def test_rereading_one_value_does_not_make_it_sustained(
    hass: HomeAssistant,
) -> None:
    """_calculate() re-reads the speed sensor on every tracked event.

    A glitch that is still the speed sensor's current state when the
    temperature updates three times is still one reading, not three.
    """
    entry = await _setup(hass)

    await _speeds(hass, "12.7")
    for temperature in ("22.1", "22.2", "22.3"):
        hass.states.async_set(TEMPERATURE_SENSOR, temperature)
        await hass.async_block_till_done()

    assert entry.runtime_data.data.max_speed_tonight_kmh is None


async def test_upgrade_discards_records_set_by_glitches(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """Old records could never be beaten under the new rule - drop them once."""
    hass_storage[STORE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            "lifetime_max_speed_kmh": 13.1,
            "lifetime_max_speed_date": "2026-09-29",
            "max_speed_tonight_kmh": 12.7,
            "night_history": [
                {"date": "2026-10-03", "distance_km": 8.15, "max_speed_kmh": 11.0}
            ],
        },
    }
    entry = await _setup(hass)

    data = entry.runtime_data.data
    assert data.lifetime_max_speed_kmh is None
    assert data.lifetime_max_speed_date is None
    assert data.max_speed_tonight_kmh is None
    # Only the speed goes - the night itself is real.
    assert data.night_history == [
        {"date": "2026-10-03", "distance_km": 8.15, "max_speed_kmh": None}
    ]

    # Once, not on every start: a record set under the new rule stays.
    await _speeds(hass, "5.0", "5.4", "5.2")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.lifetime_max_speed_kmh == 5.0


async def test_records_from_the_current_rule_are_kept(
    hass: HomeAssistant, hass_storage: dict
) -> None:
    """Storage already written under SPEED_TRUST_VERSION is left alone."""
    hass_storage[STORE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {
            "wheel_sensor": WHEEL_SENSOR,
            "speed_trust_version": SPEED_TRUST_VERSION,
            "lifetime_max_speed_kmh": 5.5,
            "lifetime_max_speed_date": "2026-10-04",
        },
    }
    entry = await _setup(hass)

    assert entry.runtime_data.data.lifetime_max_speed_kmh == 5.5
