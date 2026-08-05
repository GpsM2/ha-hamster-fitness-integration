"""Binary sensor platform for the Hamster Fitness integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the Hamster Fitness binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HamsterWarningBinarySensor(coordinator, entry),
            HamsterDoorBinarySensor(coordinator, entry),
        ]
    )


class HamsterWarningBinarySensor(
    CoordinatorEntity[HamsterFitnessCoordinator], BinarySensorEntity
):
    """Turns "on" when the hamster's wellbeing needs attention.

    Triggers when the health score drops below WARNING_SCORE_THRESHOLD,
    the temperature leaves the safe range, and/or the cage/lid hasn't been
    opened for longer than NEGLECT_THRESHOLD_HOURS. All active reasons are
    listed in the `warning_reason` attribute.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "warning"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the warning binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_warning"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return True if the hamster needs attention."""
        return self.coordinator.data.warning_on

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the specific, human-readable reason(s) for the warning."""
        reasons = self.coordinator.data.warning_reasons
        return {"warning_reason": "; ".join(reasons.values()) if reasons else ""}


class HamsterDoorBinarySensor(
    CoordinatorEntity[HamsterFitnessCoordinator], BinarySensorEntity
):
    """Mirrors the configured door/lid sensor's open/closed state.

    A convenience passthrough (same rationale as the humidity/speed
    sensors) so a dashboard only needs this device's own entities, plus
    the exact "since when" via this entity's own `last_changed` - no need
    to separately look up and reference the raw door-contact entity.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "door"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the door binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_door"
        self._attr_device_info = hamster_device_info(entry)

    @property
    def is_on(self) -> bool:
        """Return True if the cage/lid is open."""
        return self.coordinator.data.door_open

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """Expose how many hours the door has been closed, if closed."""
        return {"hours_closed": self.coordinator.data.hours_door_closed}
