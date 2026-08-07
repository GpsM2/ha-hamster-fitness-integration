"""Tests for the lifetime history archive of departed hamsters."""

from __future__ import annotations

from datetime import date

import pytest
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


async def test_undoing_a_departure_retracts_the_archive(
    hass: HomeAssistant,
) -> None:
    """A hamster brought back must not linger in the archived half.

    Otherwise the chronicle would list it twice - once live, once
    archived - the moment the live entry starts reporting again.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()
    assert len(await archive.async_load(hass)) == 1

    await coordinator.async_clear_departure_date()
    await hass.async_block_till_done()

    assert await archive.async_load(hass) == []
    assert coordinator.departure_date is None


async def test_undoing_a_departure_unfreezes_the_hamster(
    hass: HomeAssistant,
) -> None:
    """After the undo, the wheel counts again."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()
    frozen_km = coordinator.data.night_distance_km

    # Frozen means "stops moving", not "drops to zero".
    hass.states.async_set(WHEEL_SENSOR, "6000")
    await hass.async_block_till_done()
    assert coordinator.data.night_distance_km == frozen_km

    await coordinator.async_clear_departure_date()
    await hass.async_block_till_done()
    # Re-baselined on undo, so the counter starts from here again.
    assert coordinator.data.night_distance_km == 0.0

    hass.states.async_set(WHEEL_SENSOR, "7000")
    await hass.async_block_till_done()
    assert coordinator.data.night_distance_km > 0.0


async def test_undoing_a_departure_does_not_invent_distance(
    hass: HomeAssistant,
) -> None:
    """Rotations clocked up while departed must not be booked afterwards.

    While a hamster counts as departed the coordinator ignores the wheel
    entirely - but the counter keeps climbing, quite possibly under a
    different hamster if the sensor was reassigned. Resuming against the
    old baseline would credit all of it to this hamster at once.
    """
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    lifetime_before = coordinator.data.lifetime_distance_km

    await coordinator.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    # A year's worth of somebody else's running.
    hass.states.async_set(WHEEL_SENSOR, "5000000")
    await hass.async_block_till_done()

    await coordinator.async_clear_departure_date()
    await hass.async_block_till_done()

    assert coordinator.data.night_distance_km == 0.0
    assert coordinator.data.daily_distance_km == 0.0
    # Lifetime picks up where it was frozen rather than leaping.
    assert coordinator.data.lifetime_distance_km == pytest.approx(
        lifetime_before, abs=0.01
    )


async def test_undoing_without_a_departure_is_harmless(
    hass: HomeAssistant,
) -> None:
    """Pressing undo on a living hamster changes nothing."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    before = coordinator.data.lifetime_distance_km

    await coordinator.async_clear_departure_date()
    await hass.async_block_till_done()

    assert coordinator.departure_date is None
    assert coordinator.data.lifetime_distance_km == before


async def test_undo_button_is_only_available_when_departed(
    hass: HomeAssistant,
) -> None:
    """The button greys out when there is nothing to undo."""
    entry = await _setup_entry(hass)
    button = "button.hamster_taco_undo_departure"

    assert hass.states.get(button).state == "unavailable"

    await entry.runtime_data.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()
    assert hass.states.get(button).state != "unavailable"

    # And pressing it puts things back.
    await hass.services.async_call(
        "button", "press", {"entity_id": button}, blocking=True
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.departure_date is None
    assert hass.states.get(button).state == "unavailable"


async def test_two_hamsters_are_archived_side_by_side(hass: HomeAssistant) -> None:
    """Several departed hamsters coexist, newest departure first."""
    taco = await _setup_entry(hass, "Taco", "taco")
    nala = await _setup_entry(hass, "Nala", "nala")

    await taco.runtime_data.async_set_departure_date(date(2026, 1, 5))
    await nala.runtime_data.async_set_departure_date(date(2026, 8, 1))
    await hass.async_block_till_done()

    records = await archive.async_load(hass)
    assert [item["name"] for item in records] == ["Nala", "Taco"]
