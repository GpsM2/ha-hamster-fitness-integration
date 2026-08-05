"""Date platform for the Hamster Fitness integration (departure date)."""

from __future__ import annotations

from datetime import date as date_type

from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    HamsterFitnessConfigEntry,
    HamsterFitnessCoordinator,
    hamster_device_info,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HamsterFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hamster Fitness departure-date entity from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([HamsterDepartureDateEntity(coordinator, entry)])


class HamsterDepartureDateEntity(
    CoordinatorEntity[HamsterFitnessCoordinator], DateEntity
):
    """The date the hamster passed away or moved out.

    Left unset (the default), the hamster counts as still active. Once
    set to today or a past date, the coordinator freezes health_score/
    daily_distance at their last value and stops reacting to the source
    sensors from then on - see HamsterFitnessCoordinator.async_set_departure_date,
    so a re-assigned wheel/temperature/door sensor can't corrupt a
    departed hamster's historical numbers.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "departure_date"
    _attr_icon = "mdi:calendar-heart"

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the departure-date entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_departure_date"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def native_value(self) -> date_type | None:
        """Return the currently configured departure date, if any."""
        return self.coordinator.departure_date

    async def async_set_value(self, value: date_type) -> None:
        """Set (or update) the departure date."""
        await self.coordinator.async_set_departure_date(value)
