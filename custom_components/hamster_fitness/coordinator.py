"""Push-based coordinator that calculates the hamster's fitness state.

This coordinator never polls (`update_interval=None`). It recalculates
instantly whenever one of the tracked source entities changes state
(see `_async_setup`), and twice more on a fixed daily schedule: at local
midnight (resets the calendar-day baseline) and at NIGHT_WINDOW_START_HOUR
(resets the "night window" baseline used for the nightly-activity
comparison, see `_calculate`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_CIRCUMFERENCE,
    CONF_WHEEL_SENSOR,
    DEFAULT_IDEAL_TEMP_MAX,
    DEFAULT_IDEAL_TEMP_MIN,
    DEFAULT_MIN_DISTANCE_KM,
    DOMAIN,
    IDEAL_DISTANCE_MIN_KM,
    NEGLECT_THRESHOLD_HOURS,
    NIGHT_WINDOW_START_HOUR,
    OPTION_IDEAL_TEMP_MAX,
    OPTION_IDEAL_TEMP_MIN,
    OPTION_MIN_DISTANCE_KM,
    STORAGE_VERSION,
    TEMP_BUFFER_C,
    WARNING_SCORE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

CM_PER_KM: Final = 100_000.0

# Interne Formel-Konstanten (kein Options-Flow-Bezug, siehe _*_penalty()).
_DISTANCE_MODERATE_PENALTY_MAX = 25.0
_DISTANCE_CRITICAL_PENALTY_MAX = 25.0
_TEMP_BUFFER_PENALTY_MAX = 15.0
_TEMP_SEVERE_PENALTY_MAX = 35.0
_CARE_BASE_PENALTY = 40.0
_CARE_PENALTY_CAP = 60.0


@dataclass
class HamsterFitnessData:
    """Snapshot of the calculated hamster fitness state."""

    health_score: int = 100
    daily_distance_km: float = 0.0
    previous_day_distance_km: float = 0.0
    # Strecke seit dem letzten Fenster-Start (NIGHT_WINDOW_START_HOUR, z. B.
    # 20 Uhr) - im Gegensatz zu daily_distance_km NICHT um Mitternacht
    # gekappt, sondern deckt die tatsächliche nächtliche Aktivitätsphase ab.
    night_distance_km: float = 0.0
    temperature: float | None = None
    door_open: bool = False
    hours_door_closed: float | None = None
    distance_penalty: float = 0.0
    temperature_penalty: float = 0.0
    care_penalty: float = 0.0
    warning_on: bool = False
    # code -> lesbarer Text, z. B. {"too_hot": "Zu heiß: 30.0 °C (> 26.0 °C)"}.
    # Der stabile code ermöglicht notify.py ein Cooldown pro Warngrund, ohne
    # durch schwankende Zahlenwerte im Text getäuscht zu werden.
    warning_reasons: dict[str, str] = field(default_factory=dict)


class HamsterFitnessCoordinator(DataUpdateCoordinator[HamsterFitnessData]):
    """Aggregate the source sensors into one hamster-fitness snapshot."""

    def __init__(self, hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=None,  # push-only, siehe _async_handle_source_event
        )
        self._wheel_circumference_cm: float = entry.data[CONF_WHEEL_CIRCUMFERENCE]
        self._wheel_sensor: str = entry.data[CONF_WHEEL_SENSOR]
        self._temperature_sensor: str = entry.data[CONF_TEMPERATURE_SENSOR]
        self._door_sensor: str = entry.data[CONF_DOOR_SENSOR]

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_baseline"
        )
        self._baseline_count: float = 0.0
        self._last_known_count: float | None = None
        self._previous_day_distance_km: float = 0.0

        self._night_baseline_count: float = 0.0
        self._night_window_start: datetime | None = None

        self.data = HamsterFitnessData()

    # ------------------------------------------------------------------
    # Setup (wird von async_config_entry_first_refresh() aufgerufen)
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Restore persisted state and register source-entity listeners."""
        await self._async_restore_state()

        entry = self.config_entry
        entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                [self._wheel_sensor, self._temperature_sensor, self._door_sensor],
                self._async_handle_source_event,
            )
        )
        entry.async_on_unload(
            async_track_time_change(
                self.hass, self._async_handle_midnight, hour=0, minute=0, second=0
            )
        )
        entry.async_on_unload(
            async_track_time_change(
                self.hass,
                self._async_handle_night_window_reset,
                hour=NIGHT_WINDOW_START_HOUR,
                minute=0,
                second=0,
            )
        )

    async def _async_update_data(self) -> HamsterFitnessData:
        """Compute the initial snapshot for the first refresh."""
        return self._calculate()

    # ------------------------------------------------------------------
    # Persistenz der Tages-Baseline (Radumdrehungen um Mitternacht)
    # ------------------------------------------------------------------

    async def _async_restore_state(self) -> None:
        """Load persisted baselines, falling back to "start counting now"."""
        stored = await self._store.async_load()
        today = dt_util.now().date().isoformat()
        if stored:
            self._previous_day_distance_km = stored.get(
                "previous_day_distance_km", 0.0
            )

        needs_save = False

        if stored and stored.get("baseline_date") == today:
            self._baseline_count = stored.get("baseline_count", 0.0)
        else:
            # Kein brauchbarer Wert für heute: bei Neustart NICHT bei 0
            # anfangen, sondern beim aktuellen Zählerstand - sonst
            # "erfindet" ein Neustart mitten am Tag zusätzliche Strecke.
            self._baseline_count = self._current_wheel_count() or 0.0
            needs_save = True

        expected_window_start = _compute_night_window_start(dt_util.now())
        stored_window_start = (
            dt_util.parse_datetime(stored["night_window_start"])
            if stored and stored.get("night_window_start")
            else None
        )
        if stored_window_start == expected_window_start:
            self._night_baseline_count = stored.get("night_baseline_count", 0.0)
            self._night_window_start = expected_window_start
        else:
            self._night_baseline_count = self._current_wheel_count() or 0.0
            self._night_window_start = expected_window_start
            needs_save = True

        if needs_save:
            await self._async_save_state()

    async def _async_save_state(self) -> None:
        await self._store.async_save(
            {
                "baseline_count": self._baseline_count,
                "baseline_date": dt_util.now().date().isoformat(),
                "previous_day_distance_km": self._previous_day_distance_km,
                "night_baseline_count": self._night_baseline_count,
                "night_window_start": (
                    self._night_window_start.isoformat()
                    if self._night_window_start
                    else None
                ),
            }
        )

    @callback
    def _async_handle_midnight(self, now: datetime) -> None:
        """Reset the daily distance baseline at local midnight.

        `self.data` still holds yesterday's final snapshot at this point
        (the event fires at 00:00:00 before any recalculation), so its
        `daily_distance_km` becomes the new "yesterday" reference.
        """
        if self.data is not None:
            self._previous_day_distance_km = self.data.daily_distance_km
        self._baseline_count = self._current_wheel_count() or 0.0
        self.hass.async_create_task(self._async_save_state())
        self.async_set_updated_data(self._calculate())

    @callback
    def _async_handle_night_window_reset(self, now: datetime) -> None:
        """Reset the night-window baseline at NIGHT_WINDOW_START_HOUR."""
        self._night_baseline_count = self._current_wheel_count() or 0.0
        self._night_window_start = _compute_night_window_start(dt_util.now())
        self.hass.async_create_task(self._async_save_state())
        self.async_set_updated_data(self._calculate())

    # ------------------------------------------------------------------
    # Event-Handling
    # ------------------------------------------------------------------

    @callback
    def _async_handle_source_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """React immediately to a source-sensor state change."""
        self.async_set_updated_data(self._calculate())

    # ------------------------------------------------------------------
    # Berechnung
    # ------------------------------------------------------------------

    def _current_wheel_count(self) -> float | None:
        state = self.hass.states.get(self._wheel_sensor)
        return _as_float(state.state) if state else None

    @callback
    def _calculate(self) -> HamsterFitnessData:
        """Recompute distance, health score and warning state."""
        current_count = self._current_wheel_count()
        if current_count is not None:
            if (
                self._last_known_count is not None
                and current_count < self._last_known_count
            ):
                # Quell-Zähler wurde zurückgesetzt (z. B. Geräte-Reboot):
                # beide Baselines neu bei 0 beginnen, statt eine negative
                # Strecke zu zählen.
                self._baseline_count = 0.0
                self._night_baseline_count = 0.0
                self.hass.async_create_task(self._async_save_state())
            self._last_known_count = current_count
            rotations_today = max(0.0, current_count - self._baseline_count)
            distance_km = (
                rotations_today * self._wheel_circumference_cm
            ) / CM_PER_KM
            rotations_tonight = max(0.0, current_count - self._night_baseline_count)
            night_distance_km = (
                rotations_tonight * self._wheel_circumference_cm
            ) / CM_PER_KM
        else:
            distance_km = self.data.daily_distance_km if self.data else 0.0
            night_distance_km = self.data.night_distance_km if self.data else 0.0

        temp_state = self.hass.states.get(self._temperature_sensor)
        temperature = _as_float(temp_state.state) if temp_state else None

        door_state = self.hass.states.get(self._door_sensor)
        door_open = bool(door_state and door_state.state == "on")
        hours_door_closed: float | None = None
        if not door_open and door_state and door_state.last_changed:
            hours_door_closed = (
                dt_util.utcnow() - door_state.last_changed
            ).total_seconds() / 3600

        options = self.config_entry.options
        ideal_temp_min = options.get(OPTION_IDEAL_TEMP_MIN, DEFAULT_IDEAL_TEMP_MIN)
        ideal_temp_max = options.get(OPTION_IDEAL_TEMP_MAX, DEFAULT_IDEAL_TEMP_MAX)
        min_distance_km = options.get(OPTION_MIN_DISTANCE_KM, DEFAULT_MIN_DISTANCE_KM)

        distance_penalty = _distance_penalty(distance_km, min_distance_km)
        temperature_penalty = (
            _temperature_penalty(temperature, ideal_temp_min, ideal_temp_max)
            if temperature is not None
            else 0.0
        )
        care_penalty = _care_penalty(hours_door_closed)

        score = round(100 - distance_penalty - temperature_penalty - care_penalty)
        score = max(0, min(100, score))

        reasons: dict[str, str] = {}
        if score < WARNING_SCORE_THRESHOLD:
            reasons["low_score"] = (
                f"Health-Score bei {score} % (unter {WARNING_SCORE_THRESHOLD} %)"
            )
        if distance_km < min_distance_km:
            reasons["too_little_exercise"] = (
                f"Zu wenig Bewegung: {distance_km:.2f} km "
                f"(< {min_distance_km:.1f} km)"
            )
        if temperature is not None:
            hard_min = ideal_temp_min - TEMP_BUFFER_C
            hard_max = ideal_temp_max + TEMP_BUFFER_C
            if temperature < hard_min:
                reasons["too_cold"] = (
                    f"Zu kalt: {temperature:.1f} °C (< {hard_min:.1f} °C)"
                )
            elif temperature > hard_max:
                reasons["too_hot"] = (
                    f"Zu heiß: {temperature:.1f} °C (> {hard_max:.1f} °C)"
                )
        if hours_door_closed is not None and hours_door_closed > NEGLECT_THRESHOLD_HOURS:
            reasons["neglected"] = (
                f"Käfig seit {hours_door_closed:.0f} Std. nicht geöffnet "
                f"(> {NEGLECT_THRESHOLD_HOURS:.0f} Std.)"
            )

        return HamsterFitnessData(
            health_score=score,
            daily_distance_km=round(distance_km, 3),
            previous_day_distance_km=self._previous_day_distance_km,
            night_distance_km=round(night_distance_km, 3),
            temperature=temperature,
            door_open=door_open,
            hours_door_closed=(
                round(hours_door_closed, 1) if hours_door_closed is not None else None
            ),
            distance_penalty=round(distance_penalty, 1),
            temperature_penalty=round(temperature_penalty, 1),
            care_penalty=round(care_penalty, 1),
            warning_on=bool(reasons),
            warning_reasons=reasons,
        )


def hamster_device_info(entry: HamsterFitnessConfigEntry) -> DeviceInfo:
    """Build the DeviceInfo shared by all entities of this config entry."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data[CONF_HAMSTER_NAME],
        manufacturer="Hamster Fitness",
        model="Aggregator",
    )


def _compute_night_window_start(now_local: datetime) -> datetime:
    """Return the most recent NIGHT_WINDOW_START_HOUR timestamp at/before now.

    Example with NIGHT_WINDOW_START_HOUR=20: at 06:00 this returns
    yesterday 20:00; at 21:00 it returns today 20:00. This is the single
    reset point for the night-window baseline - there is no separate
    "window end", since the next reset (24h later) implicitly closes it.
    """
    candidate = now_local.replace(
        hour=NIGHT_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )
    if now_local < candidate:
        candidate -= timedelta(days=1)
    return candidate


def _as_float(value: str | None) -> float | None:
    """Best-effort float conversion; returns None for unknown/unavailable."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _distance_penalty(distance_km: float, min_distance_km: float) -> float:
    """Penalty points (0-50) for too little daily wheel exercise.

    - >= IDEAL_DISTANCE_MIN_KM (Standard 5 km): kein Abzug.
    - Zwischen min_distance_km und IDEAL_DISTANCE_MIN_KM: linear bis zu 25
      Punkte ("moderate Zone").
    - Unter min_distance_km (Standard 2 km, per Options überschreibbar):
      weitere 0-25 Punkte oben drauf ("massiver Punktabzug").
    """
    if distance_km >= IDEAL_DISTANCE_MIN_KM:
        return 0.0
    if distance_km >= min_distance_km:
        span = max(IDEAL_DISTANCE_MIN_KM - min_distance_km, 0.01)
        return (
            _DISTANCE_MODERATE_PENALTY_MAX
            * (IDEAL_DISTANCE_MIN_KM - distance_km)
            / span
        )
    fraction_below = min(
        1.0, (min_distance_km - distance_km) / max(min_distance_km, 0.01)
    )
    return (
        _DISTANCE_MODERATE_PENALTY_MAX
        + _DISTANCE_CRITICAL_PENALTY_MAX * fraction_below
    )


def _temperature_penalty(temp: float, ideal_min: float, ideal_max: float) -> float:
    """Penalty points (0-50) for a cage temperature outside the ideal range.

    ideal_min/ideal_max sind per Options überschreibbar (Standard 20/24 °C).
    Die "harten" Grenzen ergeben sich als ideal +/- TEMP_BUFFER_C (Standard
    2 °C -> 18/26 °C), sodass sie sich bei einer Options-Änderung konsistent
    mitverschieben.
    """
    if ideal_min <= temp <= ideal_max:
        return 0.0
    hard_min = ideal_min - TEMP_BUFFER_C
    hard_max = ideal_max + TEMP_BUFFER_C
    if temp < ideal_min:
        if temp >= hard_min:
            span = max(ideal_min - hard_min, 0.01)
            return _TEMP_BUFFER_PENALTY_MAX * (ideal_min - temp) / span
        return _TEMP_BUFFER_PENALTY_MAX + min(
            _TEMP_SEVERE_PENALTY_MAX, (hard_min - temp) * 5
        )
    if temp <= hard_max:
        span = max(hard_max - ideal_max, 0.01)
        return _TEMP_BUFFER_PENALTY_MAX * (temp - ideal_max) / span
    return _TEMP_BUFFER_PENALTY_MAX + min(
        _TEMP_SEVERE_PENALTY_MAX, (temp - hard_max) * 5
    )


def _care_penalty(hours_door_closed: float | None) -> float:
    """Penalty points (0-60) for cage neglect (Deckel > 48 h nicht offen)."""
    if hours_door_closed is None or hours_door_closed <= NEGLECT_THRESHOLD_HOURS:
        return 0.0
    overdue = hours_door_closed - NEGLECT_THRESHOLD_HOURS
    return min(_CARE_PENALTY_CAP, _CARE_BASE_PENALTY + overdue / 6)


type HamsterFitnessConfigEntry = ConfigEntry[HamsterFitnessCoordinator]
