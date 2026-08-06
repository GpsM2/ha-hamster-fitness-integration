"""Sensor platform for the Hamster Fitness integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HUMIDITY_SENSOR,
    CONF_SPEED_SENSOR,
    IDEAL_DISTANCE_MAX_KM,
    IDEAL_DISTANCE_MIN_KM,
    NEGLECT_THRESHOLD_HOURS,
    SLEEP_PHASE_END_HOUR,
    SLEEP_PHASE_START_HOUR,
)
from .coordinator import (
    HamsterFitnessConfigEntry,
    HamsterFitnessCoordinator,
    hamster_device_info,
    hamster_profile,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HamsterFitnessConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hamster Fitness sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[HamsterFitnessSensorBase] = [
        HamsterHealthScoreSensor(coordinator, entry),
        HamsterDailyDistanceSensor(coordinator, entry),
        HamsterNightDistanceSensor(coordinator, entry),
        HamsterLifetimeDistanceSensor(coordinator, entry),
        HamsterNightActiveDurationSensor(coordinator, entry),
        HamsterDayRestDurationSensor(coordinator, entry),
        HamsterActivityScoreSensor(coordinator, entry),
        HamsterSleepScoreSensor(coordinator, entry),
        HamsterClimateScoreSensor(coordinator, entry),
        HamsterCareScoreSensor(coordinator, entry),
    ]
    # Nur anlegen, wenn beim Einrichten ein entsprechender Quell-Sensor
    # ausgewählt wurde - siehe CONF_HUMIDITY_SENSOR/CONF_SPEED_SENSOR in
    # const.py.
    if entry.data.get(CONF_HUMIDITY_SENSOR):
        entities.append(HamsterHumiditySensor(coordinator, entry))
    if entry.data.get(CONF_SPEED_SENSOR):
        entities.append(HamsterCurrentSpeedSensor(coordinator, entry))
        entities.append(HamsterMaxSpeedTonightSensor(coordinator, entry))
    async_add_entities(entities)


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

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the health-score sensor."""
        super().__init__(coordinator, entry, "health_score")
        # Static config, so reading it once is enough - a Reconfigure
        # reloads the whole entry and rebuilds this entity anyway.
        self._profile = hamster_profile(entry)

    @property
    def native_value(self) -> int:
        """Return the current health score (0-100)."""
        return self.coordinator.data.health_score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the score breakdown and the hamster's profile.

        `score_history` backs the health-score card's 7-day trend chart
        and the profile fields (coat colour, acquisition date) let the
        cards tint the illustration and work out "with you for X months",
        all without a second entity to look up.
        """
        data = self.coordinator.data
        return {
            **self._profile,
            "night_distance_km": data.night_distance_km,
            "last_completed_night_km": data.last_completed_night_km,
            "daily_distance_km": data.daily_distance_km,
            "temperature": data.temperature,
            "hours_door_closed": data.hours_door_closed,
            "distance_penalty": data.distance_penalty,
            "temperature_penalty": data.temperature_penalty,
            "care_penalty": data.care_penalty,
            "sleep_penalty": data.sleep_penalty,
            "score_history": data.score_history,
        }


class HamsterDailyDistanceSensor(HamsterFitnessSensorBase):
    """Distance run on the wheel since the last DAILY_RESET_HOUR.

    Uses TOTAL_INCREASING, since this value only grows during the window
    and resets to 0 once a day (at DAILY_RESET_HOUR, not midnight - see
    coordinator.py) - the same pattern used by daily energy/water
    counters, which also makes it compatible with long-term statistics.
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

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


class HamsterNightDistanceSensor(HamsterFitnessSensorBase):
    """Distance run on the wheel since the last NIGHT_WINDOW_START_HOUR.

    Covers the actual nightly activity phase (default: since 20:00),
    independent of the DAILY_RESET_HOUR-based daily_distance sensor - see
    coordinator.py for why the two windows differ.
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the night-distance sensor."""
        super().__init__(coordinator, entry, "night_distance")

    @property
    def native_value(self) -> float:
        """Return tonight's distance in km."""
        return self.coordinator.data.night_distance_km


class HamsterNightActiveDurationSensor(HamsterFitnessSensorBase):
    """How long the current continuous running session has lasted.

    A session starts on the first wheel movement after none was active,
    and keeps running through short pauses (drinking, grooming) - only a
    gap of SESSION_END_GAP_MINUTES (see coordinator.py) ends it, at which
    point this drops back to 0. Tracked across restarts (unlike
    max_speed_tonight) since a nightly Home Assistant update shouldn't
    silently reset an in-progress session.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the night-active-duration sensor."""
        super().__init__(coordinator, entry, "night_active_duration")

    @property
    def native_value(self) -> float:
        """Return the current session's elapsed time in minutes (0 if resting)."""
        return self.coordinator.data.night_active_duration_min


class HamsterDayRestDurationSensor(HamsterFitnessSensorBase):
    """How long the hamster has been continuously inactive since its last run.

    Mutually exclusive with night_active_duration: this is 0 while a run
    session is active, and starts counting the moment one ends.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the day-rest-duration sensor."""
        super().__init__(coordinator, entry, "day_rest_duration")

    @property
    def native_value(self) -> float:
        """Return the current rest period's elapsed time in minutes (0 if active)."""
        return self.coordinator.data.day_rest_duration_min


class HamsterPillarScoreBase(HamsterFitnessSensorBase):
    """Base class for the four "pillars of health" sub-scores.

    Each pillar rates one aspect on its own 0-100 scale (100 = nothing
    wrong), scaled against that aspect's own maximum penalty - see
    `_pillar_score()` in coordinator.py. They deliberately do NOT add up
    to `health_score`, which weighs the same penalties against each other
    on a shared 100-point budget; the pillars exist so a single weak area
    is readable at a glance (and usable in automations/history) instead of
    being averaged away.
    """

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT


class HamsterActivityScoreSensor(HamsterPillarScoreBase):
    """Pillar 1: how much the hamster ran during the relevant night."""

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the activity-score sensor."""
        super().__init__(coordinator, entry, "score_activity")

    @property
    def native_value(self) -> int:
        """Return the activity pillar score (0-100)."""
        return self.coordinator.data.score_activity

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the distance figures this pillar is derived from."""
        data = self.coordinator.data
        return {
            "night_distance_km": data.night_distance_km,
            "last_completed_night_km": data.last_completed_night_km,
            "ideal_distance_min_km": IDEAL_DISTANCE_MIN_KM,
            "ideal_distance_max_km": IDEAL_DISTANCE_MAX_KM,
        }


class HamsterSleepScoreSensor(HamsterPillarScoreBase):
    """Pillar 2: how undisturbed the main sleep phase stayed.

    Counts cage openings and run sessions started between
    SLEEP_PHASE_START_HOUR and SLEEP_PHASE_END_HOUR - see
    `_sleep_penalty()` in coordinator.py. Resets daily at
    DAILY_RESET_HOUR.
    """

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the sleep-score sensor."""
        super().__init__(coordinator, entry, "score_sleep")

    @property
    def native_value(self) -> int:
        """Return the sleep pillar score (0-100)."""
        return self.coordinator.data.score_sleep

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw disturbance counts behind this pillar."""
        data = self.coordinator.data
        return {
            "sleep_door_openings": data.sleep_door_openings,
            "sleep_activity_sessions": data.sleep_activity_sessions,
            "sleep_phase_start_hour": SLEEP_PHASE_START_HOUR,
            "sleep_phase_end_hour": SLEEP_PHASE_END_HOUR,
        }


class HamsterClimateScoreSensor(HamsterPillarScoreBase):
    """Pillar 3: how close the cage climate stays to the ideal range."""

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the climate-score sensor."""
        super().__init__(coordinator, entry, "score_climate")

    @property
    def native_value(self) -> int:
        """Return the climate pillar score (0-100)."""
        return self.coordinator.data.score_climate

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the current climate readings behind this pillar."""
        data = self.coordinator.data
        return {"temperature": data.temperature, "humidity": data.humidity}


class HamsterCareScoreSensor(HamsterPillarScoreBase):
    """Pillar 4: how regularly the cage is opened for feeding/cleaning."""

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the care-score sensor."""
        super().__init__(coordinator, entry, "score_care")

    @property
    def native_value(self) -> int:
        """Return the care pillar score (0-100)."""
        return self.coordinator.data.score_care

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the door figures behind this pillar."""
        data = self.coordinator.data
        return {
            "hours_door_closed": data.hours_door_closed,
            "door_open": data.door_open,
            "neglect_threshold_hours": NEGLECT_THRESHOLD_HOURS,
        }


class HamsterHumiditySensor(HamsterFitnessSensorBase):
    """Cage humidity, mirrored from the configured humidity sensor.

    Only created if CONF_HUMIDITY_SENSOR was set during setup - purely a
    convenience passthrough so a dashboard only needs this device's own
    entities instead of also referencing the raw source sensor.
    """

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the humidity sensor."""
        super().__init__(coordinator, entry, "humidity")

    @property
    def native_value(self) -> float | None:
        """Return the current cage humidity (%)."""
        return self.coordinator.data.humidity


class HamsterCurrentSpeedSensor(HamsterFitnessSensorBase):
    """Real-time wheel speed, mirrored from the configured speed sensor.

    Only created if CONF_SPEED_SENSOR was set during setup - same
    passthrough rationale as HamsterHumiditySensor. Suited for a gauge
    card.
    """

    _attr_device_class = SensorDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the current-speed sensor."""
        super().__init__(coordinator, entry, "current_speed")

    @property
    def native_value(self) -> float | None:
        """Return the current wheel speed (km/h)."""
        return self.coordinator.data.current_speed_kmh


class HamsterMaxSpeedTonightSensor(HamsterFitnessSensorBase):
    """Highest wheel speed seen since the last NIGHT_WINDOW_START_HOUR.

    Only created if CONF_SPEED_SENSOR was set during setup. Tracked
    in-memory only (see coordinator.py) - a Home Assistant restart resets
    this to unknown for the remainder of that night.
    """

    _attr_device_class = SensorDeviceClass.SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the max-speed-tonight sensor."""
        super().__init__(coordinator, entry, "max_speed_tonight")

    @property
    def native_value(self) -> float | None:
        """Return tonight's top wheel speed (km/h)."""
        return self.coordinator.data.max_speed_tonight_kmh


class HamsterLifetimeDistanceSensor(HamsterFitnessSensorBase):
    """Cumulative distance run since the wheel sensor was first configured.

    Unlike daily_distance, this never resets on a schedule - only a
    counter reboot (banked into the offset, see coordinator.py) or
    swapping the configured wheel sensor resets it. Comparing this sensor
    across multiple hamsters (including ones with a departure_date set,
    since their snapshot stays frozen) is the basis for a simple
    lifetime-distance ranking.
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: HamsterFitnessCoordinator, entry: HamsterFitnessConfigEntry
    ) -> None:
        """Initialize the lifetime-distance sensor."""
        super().__init__(coordinator, entry, "lifetime_distance")

    @property
    def native_value(self) -> float:
        """Return the lifetime distance in km."""
        return self.coordinator.data.lifetime_distance_km
