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

    @property
    def native_value(self) -> float | None:
        """Return the weight the coordinator holds."""
        return self.coordinator.weight_g

    async def async_added_to_hass(self) -> None:
        """Hand a pre-0.4.0 weight over to the coordinator, once.

        The value used to live only in Home Assistant's restore-state
        store, because nothing but this entity needed it. Now the health
        score does, so the coordinator owns it - and entries set up
        before that change still have their weight sitting in the old
        place. This moves it across on first load; afterwards
        `async_adopt_restored_weight` is a no-op.
        """
        await super().async_added_to_hass()
        if self.coordinator.weight_g is not None:
            return
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in ("unknown", "unavailable"):
            return
        with contextlib.suppress(ValueError):
            await self.coordinator.async_adopt_restored_weight(float(last_state.state))

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Expose when this weight was last entered.

        Deliberately not the entity's own `last_changed`: RestoreEntity
        re-publishes the stored value on every restart, which would reset
        that timestamp and make a weeks-old weight look fresh. The
        coordinator keeps the real one (and the weigh-in reminder in
        notify.py goes by it).
        """
        last_set = self.coordinator.weight_last_set_at
        return {"last_weighed_at": last_set.isoformat() if last_set else None}

    async def async_set_native_value(self, value: float) -> None:
        """Update the weight when changed via the UI."""
        await self.coordinator.async_record_weight_update(value)
