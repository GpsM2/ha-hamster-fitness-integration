"""Number platform for the Hamster Fitness integration (weight tracking)."""

from __future__ import annotations

import contextlib

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MAX_WEIGHT_G, MIN_WEIGHT_G
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
    """Set up the Hamster Fitness weight entity from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([HamsterWeightNumber(coordinator, entry)])


class HamsterWeightNumber(
    CoordinatorEntity[HamsterFitnessCoordinator], RestoreEntity, NumberEntity
):
    """User-editable body weight of the hamster, in grams.

    There is no sensor that reports this automatically - the value is
    entered manually (e.g. from a kitchen scale) and simply persisted
    across restarts via RestoreEntity, the same pattern the built-in
    `input_number` helper relies on.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "weight"
    _attr_device_class = NumberDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_native_min_value = MIN_WEIGHT_G
    _attr_native_max_value = MAX_WEIGHT_G
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the weight entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_weight"
        self._attr_device_info = hamster_device_info(entry)
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known weight after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in ("unknown", "unavailable"):
            return
        with contextlib.suppress(ValueError):
            self._attr_native_value = float(last_state.state)

    async def async_set_native_value(self, value: float) -> None:
        """Update the weight when changed via the UI."""
        self._attr_native_value = value
        self.async_write_ha_state()
