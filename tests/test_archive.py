"""Tests for the lifetime history archive of departed hamsters."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness import archive
from custom_components.hamster_fitness.const import (
    BREED_ROBOROVSKI,
    COAT_COLOR_HEX,
    COAT_COLOR_SILVER_GREY,
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_COAT_COLOR,
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


async def _setup_entry(
    hass: HomeAssistant, name: str = "Taco", unique_id: str = "taco"
) -> MockConfigEntry:
    """Set up one hamster that has been running for a while."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title=name,
        data={
            CONF_HAMSTER_NAME: name,
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_BREED: BREED_ROBOROVSKI,
            CONF_COAT_COLOR: COAT_COLOR_SILVER_GREY,
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(WHEEL_SENSOR, "5000")
    await hass.async_block_till_done()
    return entry


async def test_nothing_archived_before_a_departure(hass: HomeAssistant) -> None:
    """A living hamster has no place in the history archive."""
    await _setup_entry(hass)
    assert await archive.async_load(hass) == []


async def test_departure_writes_a_full_record(hass: HomeAssistant) -> None:
    """Setting a departure date archives the hamster's whole profile."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    lifetime_km = coordinator.data.lifetime_distance_km
    assert lifetime_km > 0

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    (record,) = await archive.async_load(hass)
    assert record["name"] == "Taco"
    assert record["departure_date"] == "2026-08-01"
    assert record["acquisition_date"] == "2024-01-01"
    assert record["breed"] == BREED_ROBOROVSKI
    assert record["coat_color_hex"] == COAT_COLOR_HEX[COAT_COLOR_SILVER_GREY]
    assert record["lifetime_distance_km"] == lifetime_km
    # 2024-01-01 -> 2026-08-01
    assert record["days_with_you"] == 943


async def test_correcting_a_departure_date_does_not_duplicate(
    hass: HomeAssistant,
) -> None:
    """Re-archiving the same hamster overwrites instead of adding a twin."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await coordinator.async_set_departure_date(date(2026, 7, 15))
    await hass.async_block_till_done()

    records = await archive.async_load(hass)
    assert len(records) == 1
    assert records[0]["departure_date"] == "2026-07-15"


async def test_archive_outlives_the_config_entry(hass: HomeAssistant) -> None:
    """The whole point: removing the entry must not erase the hamster.

    Every other store this integration writes is keyed by entry_id and
    goes away with it - this one is shared on purpose.
    """
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    (record,) = await archive.async_load(hass)
    assert record["name"] == "Taco"


async def test_two_hamsters_are_archived_side_by_side(hass: HomeAssistant) -> None:
    """Several departed hamsters coexist, newest departure first."""
    taco = await _setup_entry(hass, "Taco", "taco")
    nala = await _setup_entry(hass, "Nala", "nala")

    await taco.runtime_data.async_set_departure_date(date(2026, 1, 5))
    await nala.runtime_data.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    records = await archive.async_load(hass)
    assert [item["name"] for item in records] == ["Nala", "Taco"]
