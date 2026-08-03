"""Sensor platform for the Hamster Fitness integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import IDEAL_DISTANCE_MAX_KM, IDEAL_DISTANCE_MIN_KM
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
    """Set up Hamster Fitness sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HamsterHealthScoreSensor(coordinator, entry),
            HamsterDailyDistanceSensor(coordinator, entry),
        ]
    )


class HamsterFitnessSensorBase(
    CoordinatorEntity[HamsterFitnessCoordinator], SensorEntity
):
    """Base class sharing device info for all Hamster Fitness sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HamsterFitnessCoordinator,
        entry: HamsterFitnessConfigEntry,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = hamster_device_info(entry)


class HamsterHealthScoreSensor(HamsterFitnessSensorBase):
    """Overall wellbeing score of the hamster (0-100 %)."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heart-pulse"

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the health-score sensor."""
        super().__init__(coordinator, entry, "health_score")

    @property
    def native_value(self) -> int:
        """Return the current health score (0-100)."""
        return self.coordinator.data.health_score

    @property
    def extra_state_attributes(self) -> dict[str, float | str | None]:
        """Expose the score breakdown for transparency/debugging."""
        data = self.coordinator.data
        return {
            "daily_distance_km": data.daily_distance_km,
            "temperature": data.temperature,
            "hours_door_closed": data.hours_door_closed,
            "distance_penalty": data.distance_penalty,
            "temperature_penalty": data.temperature_penalty,
            "care_penalty": data.care_penalty,
        }


class HamsterDailyDistanceSensor(HamsterFitnessSensorBase):
    """Distance run on the wheel since local midnight.

    Uses TOTAL_INCREASING, since this value only grows during the day and
    resets to 0 at midnight - the same pattern used by daily energy/water
    counters, which also makes it compatible with long-term statistics.
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:run-fast"

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the daily-distance sensor."""
        super().__init__(coordinator, entry, "daily_distance")

    @property
    def native_value(self) -> float:
        """Return today's distance in km."""
        return self.coordinator.data.daily_distance_km

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        """Expose yesterday's distance and the ideal daily-distance range."""
        return {
            "previous_day_distance_km": self.coordinator.data.previous_day_distance_km,
            "ideal_distance_min_km": IDEAL_DISTANCE_MIN_KM,
            "ideal_distance_max_km": IDEAL_DISTANCE_MAX_KM,
        }
