"""Push-based coordinator that calculates the hamster's fitness state.

This coordinator never polls (`update_interval=None`). It recalculates
instantly whenever one of the tracked source entities changes state
(see `_async_setup`), and twice more on a fixed daily schedule: at
DAILY_RESET_HOUR (resets the daily-distance baseline) and at
NIGHT_WINDOW_START_HOUR (resets the "night window" baseline used for the
nightly-activity comparison, see `_calculate`).

Once `departure_date` is set (today or in the past - see
`async_set_departure_date`), the hamster counts as "departed"/archived:
`_calculate` stops recomputing anything and simply keeps returning the
frozen final snapshot, even if the underlying source sensors keep firing
events (e.g. because a new hamster has since been assigned to the same
physical wheel/cage).
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import archive
from .const import (
    BREED_OTHER,
    COAT_COLOR_HEX,
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_BREED_OTHER,
    CONF_COAT_COLOR,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_HUMIDITY_SENSOR,
    CONF_SPEED_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DAILY_RESET_HOUR,
    DEFAULT_BREED,
    DEFAULT_COAT_COLOR,
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
    SCORE_HISTORY_DAYS,
    SESSION_END_GAP_MINUTES,
    SLEEP_PHASE_END_HOUR,
    SLEEP_PHASE_START_HOUR,
    STORAGE_VERSION,
    TEMP_BUFFER_C,
    WARNING_SCORE_THRESHOLD,
)
from .runtime_text import format_number, render_message

_LOGGER = logging.getLogger(__name__)

CM_PER_KM: Final = 100_000.0
SESSION_END_GAP: Final = timedelta(minutes=SESSION_END_GAP_MINUTES)

# Interne Formel-Konstanten (kein Options-Flow-Bezug, siehe _*_penalty()).
_DISTANCE_MODERATE_PENALTY_MAX = 25.0
_DISTANCE_CRITICAL_PENALTY_MAX = 25.0
_TEMP_BUFFER_PENALTY_MAX = 15.0
_TEMP_SEVERE_PENALTY_MAX = 35.0
_CARE_BASE_PENALTY = 40.0
_CARE_PENALTY_CAP = 60.0
# Obergrenzen der drei "klassischen" Abzüge - gebraucht, um jeden Abzug in
# einen eigenständigen 0-100-Säulen-Score umzurechnen (siehe _pillar_score()).
_DISTANCE_PENALTY_CAP = _DISTANCE_MODERATE_PENALTY_MAX + _DISTANCE_CRITICAL_PENALTY_MAX
_TEMP_PENALTY_CAP = _TEMP_BUFFER_PENALTY_MAX + _TEMP_SEVERE_PENALTY_MAX

# Schlaf-Abzüge je Störung der Hauptschlafphase (siehe _sleep_penalty()).
_SLEEP_DOOR_PENALTY = 20.0
_SLEEP_ACTIVITY_PENALTY = 10.0
_SLEEP_PENALTY_CAP = 100.0
# Anteil des Schlaf-Abzugs, der in den Gesamt-Health-Score einfließt.
# Bewusst klein gehalten: eine einzelne Käfigöffnung um die Mittagszeit ist
# nicht gut für den Hamster, soll den Gesamtscore aber auch nicht dominieren
# wie eine zu kalte Umgebung oder tagelang zu wenig Bewegung. Bei voll
# ausgereiztem Schlaf-Abzug (100) sind das 15 Punkte.
_SLEEP_SCORE_WEIGHT = 0.15


@dataclass
class HamsterFitnessData:
    """Snapshot of the calculated hamster fitness state."""

    health_score: int = 100
    daily_distance_km: float = 0.0
    previous_day_distance_km: float = 0.0
    # Strecke seit dem letzten Fenster-Start (NIGHT_WINDOW_START_HOUR, z. B.
    # 20 Uhr) - im Gegensatz zu daily_distance_km NICHT erst um
    # DAILY_RESET_HOUR gekappt, sondern deckt die tatsächliche nächtliche
    # Aktivitätsphase ab.
    night_distance_km: float = 0.0
    # Endstand des zuletzt ABGESCHLOSSENEN Nachtfensters (eingefroren beim
    # Reset um NIGHT_WINDOW_START_HOUR). Zusammen mit night_distance_km die
    # Grundlage des Bewegungs-Abzugs, siehe _effective_distance_km() - ohne
    # diesen Wert würde der Health-Score bei jedem Fensterwechsel abstürzen,
    # nur weil der Zähler wieder bei 0 beginnt.
    last_completed_night_km: float = 0.0
    # Strecke seit dem allerersten Einrichten dieses Rad-Sensors, überlebt
    # Geräte-Reboots (siehe _lifetime_offset_count) - wird nur beim Wechsel
    # des Rad-Sensors selbst zurückgesetzt. Grundlage für einen Vergleich
    # zwischen (auch bereits ausgezogenen) Hamstern.
    lifetime_distance_km: float = 0.0
    temperature: float | None = None
    humidity: float | None = None
    current_speed_kmh: float | None = None
    # Höchste seit dem letzten Nachtfenster-Start (NIGHT_WINDOW_START_HOUR)
    # gesehene Geschwindigkeit. Nur in-memory nachgeführt (siehe
    # _async_handle_night_window_reset) - überlebt anders als die
    # Distanz-Baselines KEINEN Neustart von Home Assistant.
    max_speed_tonight_kmh: float | None = None
    # Schnellster je gemessener Wert - anders als max_speed_tonight_kmh
    # persistiert und nie zurückgesetzt. Wandert beim Auszug mit ins
    # Lebenslauf-Archiv (siehe archive.py).
    lifetime_max_speed_kmh: float | None = None
    # Wanduhrzeit seit Beginn der aktuellen, zusammenhängenden Lauf-Session
    # (Pausen < SESSION_END_GAP unterbrechen sie nicht) - 0, wenn gerade
    # keine Session aktiv ist. Siehe _update_activity_session().
    night_active_duration_min: float = 0.0
    # Zeit seit der letzten Aktivität, NUR während keine Session aktiv ist
    # (schließt sich mit night_active_duration_min gegenseitig aus) - 0,
    # solange eine Session läuft oder noch nie Aktivität beobachtet wurde.
    day_rest_duration_min: float = 0.0
    door_open: bool = False
    hours_door_closed: float | None = None
    distance_penalty: float = 0.0
    temperature_penalty: float = 0.0
    care_penalty: float = 0.0
    # Abzug (0-100) für Störungen der Hauptschlafphase, siehe
    # _sleep_penalty(). Fließt nur anteilig (_SLEEP_SCORE_WEIGHT) in
    # health_score ein, ist als score_sleep aber voll sichtbar.
    sleep_penalty: float = 0.0
    # Zähler der laufenden Schlafphase (Reset bei DAILY_RESET_HOUR) - die
    # Rohdaten hinter sleep_penalty, damit die Karte "2 Öffnungen während
    # der Schlafzeit" konkret benennen kann statt nur einen Punktwert.
    sleep_door_openings: int = 0
    sleep_activity_sessions: int = 0
    # Die vier Säulen der Gesundheit, jeweils 0-100 (höher = besser). Jede
    # Säule skaliert ihren eigenen Abzug auf die volle Breite, ist also für
    # sich lesbar - sie summieren sich NICHT zum health_score auf, der die
    # Abzüge nach ihrer jeweiligen Gewichtung von 100 abzieht.
    score_activity: int = 100
    score_sleep: int = 100
    score_climate: int = 100
    score_care: int = 100
    # Rollierende Historie abgeschlossener Tage für das Trend-Diagramm:
    # [{"date": "2026-08-05", "score": 88}, ...], maximal
    # SCORE_HISTORY_DAYS Einträge, ältester zuerst.
    score_history: list[dict[str, Any]] = field(default_factory=list)
    warning_on: bool = False
    # code -> lesbarer Text, z. B.
    # {"too_hot": "Im Käfig ist es ziemlich warm: 30,0 °C."}.
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
        # DataUpdateCoordinator.config_entry is typed ConfigEntry[Any] | None
        # (a coordinator doesn't have to be tied to one) - this integration's
        # coordinator always is, so a precisely-typed alias avoids sprinkling
        # "entry is not None" narrowing everywhere it's used below.
        self._entry: HamsterFitnessConfigEntry = entry
        # Der Config Flow fragt den Durchmesser ab (so werden Hamsterräder
        # verkauft), intern wird für die Distanzberechnung aber der Umfang
        # gebraucht.
        self._wheel_circumference_cm: float = entry.data[CONF_WHEEL_DIAMETER] * math.pi
        self._wheel_sensor: str = entry.data[CONF_WHEEL_SENSOR]
        self._temperature_sensor: str = entry.data[CONF_TEMPERATURE_SENSOR]
        self._door_sensor: str = entry.data[CONF_DOOR_SENSOR]
        # Optional - None, wenn beim Einrichten nicht ausgewählt.
        self._humidity_sensor: str | None = entry.data.get(CONF_HUMIDITY_SENSOR)
        self._speed_sensor: str | None = entry.data.get(CONF_SPEED_SENSOR)

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_baseline"
        )
        self._baseline_count: float = 0.0
        self._baseline_window_start: datetime | None = None
        self._last_known_count: float | None = None
        self._previous_day_distance_km: float = 0.0

        self._night_baseline_count: float = 0.0
        self._night_window_start: datetime | None = None
        self._max_speed_tonight_kmh: float | None = None
        self._lifetime_max_speed_kmh: float | None = None
        self._last_completed_night_km: float = 0.0

        # Störungszähler der laufenden Schlafphase (siehe _sleep_penalty()).
        # Werden bei jedem Tages-Reset geleert und persistiert, damit ein
        # Neustart mitten am Tag die bisherigen Störungen nicht vergisst.
        self._sleep_door_openings: int = 0
        self._sleep_activity_sessions: int = 0
        self._previous_door_open: bool | None = None

        # Abgeschlossene Tages-Scores für das Trend-Diagramm der Karte.
        self._score_history: list[dict[str, Any]] = []
        # Laufende Summe/Anzahl der Score-Stichproben des aktuellen Tages.
        # Abgetastet wird im Minutentakt (siehe
        # _async_handle_periodic_update), nicht bei jedem Sensor-Event -
        # sonst zöge ein laufender Hamster, der viele Events auslöst, den
        # Tagesschnitt zu seinen aktiven Phasen hin.
        self._score_sum_today: float = 0.0
        self._score_samples_today: int = 0

        # Käfiglicht-Automatik: dauerhafter Schalterzustand plus optionale,
        # von selbst auslaufende Pause (siehe door_light.py und die
        # pause_light_automation-Aktion). Beides wird persistiert, damit ein
        # Neustart eine bewusst abgeschaltete Automatik nicht heimlich
        # wieder scharf schaltet.
        self._light_automation_enabled: bool = True
        self._light_pause_until: datetime | None = None
        self._cancel_light_pause: CALLBACK_TYPE | None = None

        # Wann zuletzt ein Gewicht eingetragen wurde - Grundlage der
        # Wiege-Erinnerung (siehe notify.py). Bewusst hier und nicht über
        # den last_changed-Zeitstempel der number-Entity: der wird bei
        # jedem Neustart neu gesetzt, wenn RestoreEntity den alten Wert
        # wiederherstellt, und "vor 2 Minuten gewogen" wäre schlicht falsch.
        self._weight_last_set_at: datetime | None = None

        # Lauf-Session-Tracking für night_active_duration/day_rest_duration -
        # siehe _update_activity_session(). Anders als die Baselines oben
        # zählerskalen-unabhängig (reine Wanduhrzeit), daher beim Wechsel
        # des Rad-Sensors NICHT invalidiert.
        self._session_start_at: datetime | None = None
        self._last_activity_at: datetime | None = None

        # Rotationen, die vor dem aktuellen Zähler-Stand "gebankt" wurden
        # (siehe _calculate()'s Reset-Erkennung) - macht lifetime_distance_km
        # robust gegenüber Geräte-Reboots des Rad-Sensors.
        self._lifetime_offset_count: float = 0.0
        self._departure_date: date | None = None

        self.data = HamsterFitnessData()

    @property
    def departure_date(self) -> date | None:
        """Return the hamster's departure date, if one has been set."""
        return self._departure_date

    # ------------------------------------------------------------------
    # Setup (wird von async_config_entry_first_refresh() aufgerufen)
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """Restore persisted state and register source-entity listeners."""
        entry = self._entry
        # Registered before restoring, since restoring may already re-arm a
        # light pause that outlived a restart.
        entry.async_on_unload(self._cancel_light_pause_timer)

        await self._async_restore_state()
        tracked_entities = [self._wheel_sensor, self._temperature_sensor, self._door_sensor]
        if self._humidity_sensor:
            tracked_entities.append(self._humidity_sensor)
        if self._speed_sensor:
            tracked_entities.append(self._speed_sensor)
        entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                tracked_entities,
                self._async_handle_source_event,
            )
        )
        entry.async_on_unload(
            async_track_time_change(
                self.hass,
                self._async_handle_daily_reset,
                hour=DAILY_RESET_HOUR,
                minute=0,
                second=0,
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
        # _calculate() otherwise only reruns on source-sensor events or the
        # two daily timers above - without this, a running session timing
        # out (or the growing rest duration) would only be noticed whenever
        # some unrelated sensor happens to fire next, not at a predictable
        # cadence. Keeps night_active_duration/day_rest_duration reasonably
        # live for the dashboard.
        entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_handle_periodic_update,
                timedelta(minutes=1),
                # Nothing about a duration counter is worth delaying a Home
                # Assistant shutdown for; without this the timer is still
                # armed while HA is stopping (and shows up as a lingering
                # timer in the test harness).
                cancel_on_shutdown=True,
            )
        )

    async def _async_update_data(self) -> HamsterFitnessData:
        """Compute the initial snapshot for the first refresh."""
        return self._calculate()

    # ------------------------------------------------------------------
    # Persistenz der Tages-Baseline (Radumdrehungen ab DAILY_RESET_HOUR)
    # ------------------------------------------------------------------

    async def _async_restore_state(self) -> None:
        """Load persisted baselines, falling back to "start counting now"."""
        stored: dict[str, Any] = await self._store.async_load() or {}
        if stored:
            self._previous_day_distance_km = stored.get(
                "previous_day_distance_km", 0.0
            )
            self._last_completed_night_km = stored.get("last_completed_night_km", 0.0)
            self._lifetime_max_speed_kmh = stored.get("lifetime_max_speed_kmh")
            self._sleep_door_openings = stored.get("sleep_door_openings", 0)
            self._sleep_activity_sessions = stored.get("sleep_activity_sessions", 0)
            self._score_history = stored.get("score_history", [])
            self._score_sum_today = stored.get("score_sum_today", 0.0)
            self._score_samples_today = stored.get("score_samples_today", 0)
            self._light_automation_enabled = stored.get(
                "light_automation_enabled", True
            )
            pause_raw = stored.get("light_pause_until")
            pause_until = dt_util.parse_datetime(pause_raw) if pause_raw else None
            # Eine Pause, die während eines Neustarts abgelaufen ist, gilt
            # als vorbei; eine noch laufende wird mitsamt ihrem Timer
            # wiederhergestellt, damit sie danach nicht ewig aktiv bleibt.
            if pause_until is not None and pause_until > dt_util.utcnow():
                self._light_pause_until = pause_until
                self._schedule_light_pause_end(pause_until)
            weighed_raw = stored.get("weight_last_set_at")
            self._weight_last_set_at = (
                dt_util.parse_datetime(weighed_raw) if weighed_raw else None
            )

        departure_raw = stored.get("departure_date")
        self._departure_date = date.fromisoformat(departure_raw) if departure_raw else None

        # Reine Wanduhrzeit, nicht an den Rad-Sensor-Zählerstand gekoppelt -
        # anders als die Baselines unten unabhängig von sensor_changed
        # wiederhergestellt. _calculate() erkennt beim nächsten Tick von
        # selbst, ob die Pause seit dem letzten Speichern schon über
        # SESSION_END_GAP lag.
        session_start_raw = stored.get("session_start_at")
        self._session_start_at = (
            dt_util.parse_datetime(session_start_raw) if session_start_raw else None
        )
        last_activity_raw = stored.get("last_activity_at")
        self._last_activity_at = (
            dt_util.parse_datetime(last_activity_raw) if last_activity_raw else None
        )

        if self._is_departed():
            # Bereits archivierter Hamster: den zuletzt eingefrorenen Stand
            # wiederherstellen und NICHT neu baseline - alle Baselines/
            # Zählerstände sind für einen archivierten Hamster irrelevant,
            # da _calculate() ab jetzt ohnehin nur noch self.data
            # unverändert zurückgibt.
            snapshot = stored.get("frozen_snapshot")
            if snapshot:
                self.data = HamsterFitnessData(**snapshot)
            return

        needs_save = False

        # Wenn der Rad-Sensor seit dem letzten Speichern gewechselt wurde
        # (z. B. per Reconfigure), sind die gespeicherten Baselines gegen
        # den Zählerstand eines ANDEREN Sensors gemessen und dürfen nicht
        # weiterverwendet werden - sonst entsteht aus der Differenz zweier
        # unabhängiger Sensor-Skalen eine riesige Phantom-Distanz. Beide
        # Baselines werden dann so behandelt, als gäbe es noch keinen
        # gespeicherten Wert.
        sensor_changed = bool(stored) and stored.get("wheel_sensor") != self._wheel_sensor

        expected_daily_start = _compute_window_start(dt_util.now(), DAILY_RESET_HOUR)
        stored_daily_start = (
            dt_util.parse_datetime(stored["baseline_window_start"])
            if stored.get("baseline_window_start")
            else None
        )
        if not sensor_changed and stored_daily_start == expected_daily_start:
            self._baseline_count = stored.get("baseline_count", 0.0)
            self._baseline_window_start = expected_daily_start
        else:
            # Kein brauchbarer Wert für das laufende Tagesfenster: bei
            # Neustart NICHT bei 0 anfangen, sondern beim aktuellen
            # Zählerstand - sonst "erfindet" ein Neustart mitten im Fenster
            # zusätzliche Strecke.
            self._baseline_count = self._current_wheel_count() or 0.0
            self._baseline_window_start = expected_daily_start
            needs_save = True

        expected_night_start = _compute_window_start(
            dt_util.now(), NIGHT_WINDOW_START_HOUR
        )
        stored_night_start = (
            dt_util.parse_datetime(stored["night_window_start"])
            if stored.get("night_window_start")
            else None
        )
        if not sensor_changed and stored_night_start == expected_night_start:
            self._night_baseline_count = stored.get("night_baseline_count", 0.0)
            self._night_window_start = expected_night_start
        else:
            self._night_baseline_count = self._current_wheel_count() or 0.0
            self._night_window_start = expected_night_start
            needs_save = True

        # Ein Sensor-Wechsel invalidiert auch den Lifetime-Offset - siehe
        # Kommentar oben, dieselbe Skalen-Inkompatibilität gilt hier genauso.
        if sensor_changed or not stored:
            self._lifetime_offset_count = 0.0
        else:
            self._lifetime_offset_count = stored.get("lifetime_offset_count", 0.0)

        if needs_save:
            await self._async_save_state()

    async def _async_save_state(self) -> None:
        await self._store.async_save(
            {
                "wheel_sensor": self._wheel_sensor,
                "baseline_count": self._baseline_count,
                "baseline_window_start": (
                    self._baseline_window_start.isoformat()
                    if self._baseline_window_start
                    else None
                ),
                "previous_day_distance_km": self._previous_day_distance_km,
                "last_completed_night_km": self._last_completed_night_km,
                "lifetime_max_speed_kmh": self._lifetime_max_speed_kmh,
                "sleep_door_openings": self._sleep_door_openings,
                "sleep_activity_sessions": self._sleep_activity_sessions,
                "score_history": self._score_history,
                "score_sum_today": self._score_sum_today,
                "score_samples_today": self._score_samples_today,
                "light_automation_enabled": self._light_automation_enabled,
                "light_pause_until": (
                    self._light_pause_until.isoformat()
                    if self._light_pause_until
                    else None
                ),
                "weight_last_set_at": (
                    self._weight_last_set_at.isoformat()
                    if self._weight_last_set_at
                    else None
                ),
                "night_baseline_count": self._night_baseline_count,
                "night_window_start": (
                    self._night_window_start.isoformat()
                    if self._night_window_start
                    else None
                ),
                "lifetime_offset_count": self._lifetime_offset_count,
                "departure_date": (
                    self._departure_date.isoformat() if self._departure_date else None
                ),
                "session_start_at": (
                    self._session_start_at.isoformat()
                    if self._session_start_at
                    else None
                ),
                "last_activity_at": (
                    self._last_activity_at.isoformat()
                    if self._last_activity_at
                    else None
                ),
                "frozen_snapshot": asdict(self.data),
            }
        )

    @callback
    def _async_handle_daily_reset(self, now: datetime) -> None:
        """Reset the daily distance baseline at DAILY_RESET_HOUR.

        `self.data` still holds the previous window's final snapshot at this
        point (the event fires at DAILY_RESET_HOUR:00:00 before any
        recalculation), so its `daily_distance_km` becomes the new
        "yesterday" reference.

        The same moment closes out the day for the score trend, using
        the day's *average* score rather than whatever it happened to
        read at this instant - a day that dipped badly and recovered
        before 9 AM would otherwise look untroubled. It also lands just
        before the sleep phase begins, which is why the
        sleep-disturbance counters are cleared here too.
        """
        if self.data is not None:
            self._previous_day_distance_km = self.data.daily_distance_km
            self._record_daily_score(self._closing_day_score())
        self._score_sum_today = 0.0
        self._score_samples_today = 0
        self._sleep_door_openings = 0
        self._sleep_activity_sessions = 0
        self._baseline_count = self._current_wheel_count() or 0.0
        self._baseline_window_start = _compute_window_start(
            dt_util.now(), DAILY_RESET_HOUR
        )
        self.hass.async_create_task(self._async_save_state())
        self.async_set_updated_data(self._calculate())

    def _closing_day_score(self) -> int:
        """Average score across the day that is just ending.

        Falls back to the current score if nothing was sampled - Home
        Assistant having been down for the whole window. A snapshot is a
        poorer number than an average, but it beats recording nothing.
        """
        if self._score_samples_today == 0:
            return self.data.health_score
        return round(self._score_sum_today / self._score_samples_today)

    @callback
    def _sample_score(self) -> None:
        """Add the current score to today's running average.

        Skipped for a departed hamster: its snapshot is frozen, so
        sampling would just pad the history with a value that can no
        longer change.
        """
        if self._is_departed():
            return
        self._score_sum_today += self.data.health_score
        self._score_samples_today += 1

    def _record_daily_score(self, score: int) -> None:
        """Append `score` to the rolling SCORE_HISTORY_DAYS-day history.

        Keyed by the date of the day that just ended (i.e. yesterday's
        date if the reset hour is in the morning). Re-recording the same
        date overwrites the existing entry, so a Home Assistant restart
        right around the reset can't produce two entries for one day.
        """
        closing_date = (dt_util.now() - timedelta(hours=DAILY_RESET_HOUR)).date()
        entry = {"date": closing_date.isoformat(), "score": score}
        self._score_history = [
            item for item in self._score_history if item.get("date") != entry["date"]
        ]
        self._score_history.append(entry)
        self._score_history = self._score_history[-SCORE_HISTORY_DAYS:]

    @callback
    def _async_handle_night_window_reset(self, now: datetime) -> None:
        """Reset the night-window baseline at NIGHT_WINDOW_START_HOUR.

        Before the counter starts over, the distance the closing window
        ended on is kept as `last_completed_night_km` - that value keeps
        carrying the health score through the first hours of the new
        night, when `night_distance_km` is necessarily still near zero.
        """
        if self.data is not None:
            self._last_completed_night_km = self.data.night_distance_km
        self._night_baseline_count = self._current_wheel_count() or 0.0
        self._night_window_start = _compute_window_start(
            dt_util.now(), NIGHT_WINDOW_START_HOUR
        )
        self._max_speed_tonight_kmh = None
        self.hass.async_create_task(self._async_save_state())
        self.async_set_updated_data(self._calculate())

    @callback
    def _async_handle_periodic_update(self, now: datetime) -> None:
        """Recompute every minute, mainly to keep session/rest durations live.

        Doubles as the sampling tick for the daily score average: an
        evenly spaced sample every minute, independent of how much the
        source sensors happen to be firing.
        """
        self.async_set_updated_data(self._calculate())
        self._sample_score()

    # ------------------------------------------------------------------
    # Gewicht (siehe number.py und die Wiege-Erinnerung in notify.py)
    # ------------------------------------------------------------------

    @property
    def weight_last_set_at(self) -> datetime | None:
        """Return when a weight was last entered, or None if never."""
        return self._weight_last_set_at

    async def async_record_weight_update(self) -> None:
        """Remember that a weight was just entered."""
        self._weight_last_set_at = dt_util.utcnow()
        await self._async_save_state()
        self.async_update_listeners()

    # ------------------------------------------------------------------
    # Käfiglicht-Automatik (Schalter + Pause, siehe door_light.py)
    # ------------------------------------------------------------------

    @property
    def light_automation_enabled(self) -> bool:
        """Return whether the cage-light automation is switched on at all."""
        return self._light_automation_enabled

    @property
    def light_pause_until(self) -> datetime | None:
        """Return when the current pause ends, or None if not paused."""
        return self._light_pause_until

    @property
    def light_automation_active(self) -> bool:
        """Return whether the automation may act on the door right now.

        The single question door_light.py asks: it is active when the
        switch is on *and* no temporary pause is running.
        """
        if not self._light_automation_enabled:
            return False
        return self._light_pause_until is None

    async def async_set_light_automation_enabled(self, enabled: bool) -> None:
        """Turn the cage-light automation on or off for good."""
        self._light_automation_enabled = enabled
        # Switching the automation off makes a running pause meaningless,
        # and switching it back on shouldn't silently resume one either.
        self._cancel_light_pause_timer()
        self._light_pause_until = None
        await self._async_save_state()
        self.async_update_listeners()

    async def async_pause_light_automation(self, minutes: float) -> None:
        """Skip the door-triggered light switching for `minutes`.

        Calling this again while a pause is running replaces it, so a
        second tap on the card's button extends the break instead of
        stacking timers.
        """
        self._cancel_light_pause_timer()
        pause_until = dt_util.utcnow() + timedelta(minutes=minutes)
        self._light_pause_until = pause_until
        self._schedule_light_pause_end(pause_until)
        await self._async_save_state()
        self.async_update_listeners()

    @callback
    def _schedule_light_pause_end(self, pause_until: datetime) -> None:
        """Arm the timer that lets the pause expire on its own.

        Teardown is handled once in `_async_setup` rather than here -
        registering it per pause would pile up one dead unload callback
        for every pause ever started.
        """
        self._cancel_light_pause = async_track_point_in_utc_time(
            self.hass, self._async_handle_light_pause_end, pause_until
        )

    @callback
    def _cancel_light_pause_timer(self) -> None:
        """Cancel a pending pause-expiry timer, if one is armed."""
        if self._cancel_light_pause is not None:
            self._cancel_light_pause()
            self._cancel_light_pause = None

    async def _async_handle_light_pause_end(self, _now: datetime) -> None:
        """Re-arm the automation once the pause has run its course."""
        self._cancel_light_pause = None
        self._light_pause_until = None
        await self._async_save_state()
        self.async_update_listeners()

    # ------------------------------------------------------------------
    # Archivierung (Auszugs-/Sterbedatum, siehe date.py)
    # ------------------------------------------------------------------

    async def async_set_departure_date(self, value: date) -> None:
        """Record the hamster's departure date.

        If `value` is today or in the past, this immediately freezes the
        current snapshot (clearing any active warning, since a departed
        hamster shouldn't keep alerting) and, from then on, `_calculate`
        ignores further source-sensor events entirely - see
        `_is_departed`. A future date is stored but has no effect yet; the
        freeze only takes place once that date actually arrives (checked
        on the next recalculation, e.g. the next daily reset).
        """
        self._departure_date = value
        if self._is_departed():
            frozen = replace(self.data, warning_on=False, warning_reasons={})
            self.async_set_updated_data(frozen)
            await self._async_archive_departure(value)
        await self._async_save_state()

    async def _async_archive_departure(self, departure: date) -> None:
        """Write this hamster's final record to the lifetime archive.

        Deliberately kept outside the per-entry store: this record has to
        survive the config entry itself being deleted, which is exactly
        when the chronicle card would otherwise lose the hamster (see
        archive.py).
        """
        entry = self._entry
        acquisition_raw = entry.data.get(CONF_ACQUISITION_DATE)
        days_with_you: int | None = None
        if acquisition_raw:
            try:
                days_with_you = (departure - date.fromisoformat(acquisition_raw)).days
            except ValueError:
                _LOGGER.debug(
                    "Hamster Fitness: unlesbares Einzugsdatum %r, "
                    "Aufenthaltsdauer wird nicht archiviert",
                    acquisition_raw,
                )

        await archive.async_record_departure(
            self.hass,
            entry.entry_id,
            {
                "name": entry.data[CONF_HAMSTER_NAME],
                "departure_date": departure.isoformat(),
                "days_with_you": days_with_you,
                "lifetime_distance_km": self.data.lifetime_distance_km,
                "lifetime_max_speed_kmh": self.data.lifetime_max_speed_kmh,
                "final_health_score": self.data.health_score,
                "archived_at": dt_util.utcnow().isoformat(),
                **hamster_profile(entry),
            },
        )

    def _is_departed(self) -> bool:
        """Return True if the hamster's departure date has arrived."""
        return self._departure_date is not None and self._departure_date <= dt_util.now().date()

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

    def _update_activity_session(self, now: datetime, activity_detected: bool) -> None:
        """Track the current run session / rest period.

        Feeds night_active_duration_min/day_rest_duration_min (see
        HamsterFitnessData). A session starts on the first activity pulse
        after none was active, and only ends once SESSION_END_GAP has
        passed without another pulse - short pauses (getting a drink,
        grooming) don't reset it, matching the "Wanduhrzeit seit
        Session-Start" semantics chosen for this. Only persisted at the
        start/end boundary (not on every pulse) to avoid writing to disk
        on every single wheel rotation during an active run.
        """
        if activity_detected:
            self._last_activity_at = now
            if self._session_start_at is None:
                self._session_start_at = now
                if _in_sleep_phase(now):
                    # Der Hamster läuft mitten in seiner Hauptschlafphase -
                    # meist ein Zeichen dafür, dass ihn etwas geweckt hat.
                    self._sleep_activity_sessions += 1
                self.hass.async_create_task(self._async_save_state())
        elif (
            self._session_start_at is not None
            and self._last_activity_at is not None
            and now - self._last_activity_at > SESSION_END_GAP
        ):
            self._session_start_at = None
            self.hass.async_create_task(self._async_save_state())

    @callback
    def _calculate(self) -> HamsterFitnessData:
        """Recompute distance, health score and warning state."""
        if self._is_departed():
            # Archivierter Hamster: eingefrorenen Endstand unverändert
            # zurückgeben, auch wenn die Quell-Sensoren (z. B. nach
            # Zuweisung an einen neuen Hamster) weiter Events feuern.
            return self.data

        now = dt_util.utcnow()
        current_count = self._current_wheel_count()
        if current_count is not None:
            activity_detected = (
                self._last_known_count is not None
                and current_count > self._last_known_count
            )
            if (
                self._last_known_count is not None
                and current_count < self._last_known_count
            ):
                # Quell-Zähler wurde zurückgesetzt (z. B. Geräte-Reboot):
                # der bisherige Stand wird in den Lifetime-Offset gebankt,
                # damit lifetime_distance_km trotzdem weiterwächst, und
                # beide Tages-/Nacht-Baselines beginnen neu bei 0, statt
                # eine negative Strecke zu zählen.
                self._lifetime_offset_count += self._last_known_count
                self._baseline_count = 0.0
                self._night_baseline_count = 0.0
                self.hass.async_create_task(self._async_save_state())
            self._last_known_count = current_count
            self._update_activity_session(now, activity_detected)
            rotations_today = max(0.0, current_count - self._baseline_count)
            distance_km = (
                rotations_today * self._wheel_circumference_cm
            ) / CM_PER_KM
            rotations_tonight = max(0.0, current_count - self._night_baseline_count)
            night_distance_km = (
                rotations_tonight * self._wheel_circumference_cm
            ) / CM_PER_KM
            lifetime_distance_km = (
                (self._lifetime_offset_count + current_count)
                * self._wheel_circumference_cm
            ) / CM_PER_KM
        else:
            distance_km = self.data.daily_distance_km if self.data else 0.0
            night_distance_km = self.data.night_distance_km if self.data else 0.0
            lifetime_distance_km = self.data.lifetime_distance_km if self.data else 0.0

        temp_state = self.hass.states.get(self._temperature_sensor)
        temperature = _as_float(temp_state.state) if temp_state else None

        humidity: float | None = None
        if self._humidity_sensor:
            humidity_state = self.hass.states.get(self._humidity_sensor)
            humidity = _as_float(humidity_state.state) if humidity_state else None

        current_speed_kmh: float | None = None
        if self._speed_sensor:
            speed_state = self.hass.states.get(self._speed_sensor)
            current_speed_kmh = _as_float(speed_state.state) if speed_state else None
            if current_speed_kmh is not None:
                self._max_speed_tonight_kmh = max(
                    current_speed_kmh, self._max_speed_tonight_kmh or 0.0
                )
                if current_speed_kmh > (self._lifetime_max_speed_kmh or 0.0):
                    self._lifetime_max_speed_kmh = current_speed_kmh
                    self.hass.async_create_task(self._async_save_state())

        night_active_duration_min = (
            (now - self._session_start_at).total_seconds() / 60
            if self._session_start_at is not None
            else 0.0
        )
        day_rest_duration_min = (
            (now - self._last_activity_at).total_seconds() / 60
            if self._session_start_at is None and self._last_activity_at is not None
            else 0.0
        )

        door_state = self.hass.states.get(self._door_sensor)
        door_open = bool(door_state and door_state.state == "on")
        if (
            door_open
            and self._previous_door_open is False
            and _in_sleep_phase(now)
        ):
            # Nur die Flanke zählen (geschlossen -> offen), nicht jeden Tick,
            # in dem der Deckel offen steht. Beim allerersten Durchlauf ist
            # _previous_door_open None: ein beim Start bereits offener Deckel
            # wird bewusst nicht als frische Störung gewertet.
            self._sleep_door_openings += 1
            self.hass.async_create_task(self._async_save_state())
        self._previous_door_open = door_open
        hours_door_closed: float | None = None
        if not door_open and door_state and door_state.last_changed:
            hours_door_closed = (
                now - door_state.last_changed
            ).total_seconds() / 3600

        options = self._entry.options
        ideal_temp_min = options.get(OPTION_IDEAL_TEMP_MIN, DEFAULT_IDEAL_TEMP_MIN)
        ideal_temp_max = options.get(OPTION_IDEAL_TEMP_MAX, DEFAULT_IDEAL_TEMP_MAX)
        min_distance_km = options.get(OPTION_MIN_DISTANCE_KM, DEFAULT_MIN_DISTANCE_KM)

        # Bewertet wird die nächtliche Laufleistung, nicht die Tagesstrecke:
        # daily_distance_km fällt um DAILY_RESET_HOUR (9 Uhr) auf 0 zurück
        # und hätte den Score jeden Morgen einbrechen lassen, obwohl der
        # Hamster die Nacht über fleißig gelaufen ist. Der Vergleich mit dem
        # zuletzt abgeschlossenen Nachtfenster verhindert denselben Effekt
        # beim Fensterwechsel um NIGHT_WINDOW_START_HOUR (20 Uhr).
        effective_distance_km = max(night_distance_km, self._last_completed_night_km)

        distance_penalty = _distance_penalty(effective_distance_km, min_distance_km)
        temperature_penalty = (
            _temperature_penalty(temperature, ideal_temp_min, ideal_temp_max)
            if temperature is not None
            else 0.0
        )
        care_penalty = _care_penalty(hours_door_closed)
        sleep_penalty = _sleep_penalty(
            self._sleep_door_openings, self._sleep_activity_sessions
        )

        score = round(
            100
            - distance_penalty
            - temperature_penalty
            - care_penalty
            - sleep_penalty * _SLEEP_SCORE_WEIGHT
        )
        score = max(0, min(100, score))

        reasons: dict[str, str] = {}
        if score < WARNING_SCORE_THRESHOLD:
            reasons["low_score"] = render_message(
                self.hass, "warning.low_score", score=str(score)
            )
        if effective_distance_km < min_distance_km:
            reasons["too_little_exercise"] = render_message(
                self.hass,
                "warning.too_little_exercise",
                distance=format_number(self.hass, effective_distance_km, 2),
            )
        if temperature is not None:
            hard_min = ideal_temp_min - TEMP_BUFFER_C
            hard_max = ideal_temp_max + TEMP_BUFFER_C
            if temperature < hard_min:
                reasons["too_cold"] = render_message(
                    self.hass,
                    "warning.too_cold",
                    temperature=format_number(self.hass, temperature, 1),
                )
            elif temperature > hard_max:
                reasons["too_hot"] = render_message(
                    self.hass,
                    "warning.too_hot",
                    temperature=format_number(self.hass, temperature, 1),
                )
        if hours_door_closed is not None and hours_door_closed > NEGLECT_THRESHOLD_HOURS:
            reasons["neglected"] = render_message(
                self.hass, "warning.neglected", hours=f"{hours_door_closed:.0f}"
            )

        return HamsterFitnessData(
            health_score=score,
            daily_distance_km=round(distance_km, 3),
            previous_day_distance_km=self._previous_day_distance_km,
            night_distance_km=round(night_distance_km, 3),
            last_completed_night_km=round(self._last_completed_night_km, 3),
            lifetime_distance_km=round(lifetime_distance_km, 3),
            temperature=temperature,
            humidity=humidity,
            current_speed_kmh=current_speed_kmh,
            max_speed_tonight_kmh=(
                round(self._max_speed_tonight_kmh, 1)
                if self._max_speed_tonight_kmh is not None
                else None
            ),
            lifetime_max_speed_kmh=(
                round(self._lifetime_max_speed_kmh, 1)
                if self._lifetime_max_speed_kmh is not None
                else None
            ),
            night_active_duration_min=round(night_active_duration_min, 1),
            day_rest_duration_min=round(day_rest_duration_min, 1),
            door_open=door_open,
            hours_door_closed=(
                round(hours_door_closed, 1) if hours_door_closed is not None else None
            ),
            distance_penalty=round(distance_penalty, 1),
            temperature_penalty=round(temperature_penalty, 1),
            care_penalty=round(care_penalty, 1),
            sleep_penalty=round(sleep_penalty, 1),
            sleep_door_openings=self._sleep_door_openings,
            sleep_activity_sessions=self._sleep_activity_sessions,
            score_activity=_pillar_score(distance_penalty, _DISTANCE_PENALTY_CAP),
            score_sleep=_pillar_score(sleep_penalty, _SLEEP_PENALTY_CAP),
            score_climate=_pillar_score(temperature_penalty, _TEMP_PENALTY_CAP),
            score_care=_pillar_score(care_penalty, _CARE_PENALTY_CAP),
            score_history=list(self._score_history),
            warning_on=bool(reasons),
            warning_reasons=reasons,
        )


def hamster_device_info(entry: HamsterFitnessConfigEntry) -> DeviceInfo:
    """Build the DeviceInfo shared by all entities of this config entry.

    The "Hamster " prefix on the device name is deliberate: since entities
    use has_entity_name (see sensor.py etc.), Home Assistant derives their
    entity_id from <device name>_<entity name> - without the prefix, a
    hamster named e.g. "Speed" could collide/read confusingly next to
    unrelated devices. With it, entity_ids consistently look like
    sensor.hamster_<name>_<description> (e.g. sensor.hamster_taco_health_score),
    making it obvious at a glance which integration they belong to.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Hamster {entry.data[CONF_HAMSTER_NAME]}",
        manufacturer="Hamster Fitness",
        model="Aggregator",
    )


def hamster_profile(entry: HamsterFitnessConfigEntry) -> dict[str, str | None]:
    """Return the static, user-entered profile of this hamster.

    Purely descriptive - none of it feeds the health score. It is surfaced
    as attributes on the health-score sensor because that is the one
    entity every dashboard card already resolves, and the cards need it:
    the coat colour tints the illustrated hamster, the acquisition date
    drives the "with you for X months" subtitle.

    Every field is read defensively: entries created before 0.3.0 simply
    do not have these keys, and a Reconfigure is the only thing that adds
    them.
    """
    breed = entry.data.get(CONF_BREED, DEFAULT_BREED)
    breed_other = str(entry.data.get(CONF_BREED_OTHER, "")).strip()
    color = entry.data.get(CONF_COAT_COLOR, DEFAULT_COAT_COLOR)
    return {
        "breed": breed,
        # Only meaningful for BREED_OTHER; None keeps the attribute quiet
        # rather than showing a stale value from a since-changed breed.
        "breed_other": breed_other if breed == BREED_OTHER and breed_other else None,
        "coat_color": color,
        "coat_color_hex": COAT_COLOR_HEX.get(
            color, COAT_COLOR_HEX[DEFAULT_COAT_COLOR]
        ),
        "acquisition_date": entry.data.get(CONF_ACQUISITION_DATE),
    }


def _compute_window_start(now_local: datetime, hour: int) -> datetime:
    """Return the most recent daily reset timestamp (at `hour`) at/before now.

    Example with hour=20: at 06:00 this returns yesterday 20:00; at 21:00 it
    returns today 20:00. Shared by the daily-distance baseline
    (DAILY_RESET_HOUR) and the night-window baseline
    (NIGHT_WINDOW_START_HOUR) - each reset point is the single start of its
    own window, there is no separate "window end" since the next reset 24h
    later implicitly closes it.
    """
    candidate = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now_local < candidate:
        candidate -= timedelta(days=1)
    return candidate


def _in_sleep_phase(moment: datetime) -> bool:
    """Return True if `moment` falls into the hamster's main sleep phase.

    Accepts UTC or local timestamps; the hour comparison always happens in
    the user's local timezone, since SLEEP_PHASE_START_HOUR/END_HOUR
    describe a wall-clock window.
    """
    hour = dt_util.as_local(moment).hour
    return SLEEP_PHASE_START_HOUR <= hour < SLEEP_PHASE_END_HOUR


def _pillar_score(penalty: float, penalty_cap: float) -> int:
    """Scale one penalty onto its own 0-100 scale (100 = nothing wrong).

    Each of the four health pillars is meant to be readable on its own,
    so a penalty is measured against *its own* maximum rather than
    against the shared 100-point score - a fully blown temperature
    penalty (50 of a possible 50) reads as a climate score of 0, not 50.
    """
    ratio = min(1.0, max(0.0, penalty / penalty_cap)) if penalty_cap > 0 else 0.0
    return round(100 - ratio * 100)


def _sleep_penalty(door_openings: int, activity_sessions: int) -> float:
    """Penalty points (0-100) for disturbances of the main sleep phase.

    Hamsters are crepuscular/nocturnal: being woken between
    SLEEP_PHASE_START_HOUR and SLEEP_PHASE_END_HOUR is a chronic stress
    factor. Two observable signals feed this, both counted per day and
    cleared at DAILY_RESET_HOUR:

    - the cage/lid being opened during the sleep phase (the disturbance
      itself, weighted heavier), and
    - the hamster starting a fresh run session during it (usually the
      *consequence* of having been woken up).
    """
    return min(
        _SLEEP_PENALTY_CAP,
        door_openings * _SLEEP_DOOR_PENALTY
        + activity_sessions * _SLEEP_ACTIVITY_PENALTY,
    )


def _as_float(value: str | None) -> float | None:
    """Best-effort float conversion; returns None for unknown/unavailable."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _distance_penalty(distance_km: float, min_distance_km: float) -> float:
    """Penalty points (0-50) for too little nightly wheel exercise.

    `distance_km` is the effective night distance (see
    `_effective_distance_km` in `_calculate`), not the daily counter.

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
