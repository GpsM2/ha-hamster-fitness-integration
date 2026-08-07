"""Button platform for the Hamster Fitness integration.

Exists for one job: undoing a departure. Setting
`date.<hamster>_departure_date` freezes the hamster's final snapshot and
writes a permanent archive record, and Home Assistant's date entity
offers neither a confirmation prompt nor a way to clear the value again -
so a mistyped date would archive a living hamster with no way back.

The button sits right next to that date on the device page, which is
where someone will look after realising the mistake, and reports itself
unavailable whenever there is no departure to undo.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up the Hamster Fitness buttons from a config entry."""
    async_add_entities([HamsterUndoDepartureButton(entry.runtime_data, entry)])


class HamsterUndoDepartureButton(
    CoordinatorEntity[HamsterFitnessCoordinator], ButtonEntity
):
    """Clears the departure date and brings the hamster back."""

    _attr_has_entity_name = True
    _attr_translation_key = "undo_departure"

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the undo-departure button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_undo_departure"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def available(self) -> bool:
        """Only offer the button when there is a departure to undo."""
        return super().available and self.coordinator.departure_date is not None

    async def async_press(self) -> None:
        """Undo the departure."""
        await self.coordinator.async_clear_departure_date()
