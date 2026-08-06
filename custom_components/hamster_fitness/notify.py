"""Notification logic for the Hamster Fitness integration.

Two independent, options-gated notification flows:

- A daily summary sent at the user-configured local time
  (`OPTION_NOTIFICATION_TIME`), comparing the current night-window
  distance (since NIGHT_WINDOW_START_HOUR, see coordinator.py) against
  the value recorded the last time this same notification fired - i.e.
  an apples-to-apples "same point in the night, one day apart"
  comparison, not a partial-day-vs-full-day one. Gated by
  `OPTION_DAILY_SUMMARY_ENABLED`.
- Immediate warnings whenever a NEW warning reason appears on the
  coordinator's data (the same condition that drives
  binary_sensor.<hamster>_warning), each with its own per-reason
  cooldown to avoid spam. Gated by `OPTION_WARNINGS_ENABLED`.

Every message is sent with the hamster's name as the notification title
(`title`) and the actual text as `message`, so both flows can be toggled
independently. Because config_flow.py's options flow uses
OptionsFlowWithReload, the whole config entry (and therefore this
notifier) is recreated from scratch whenever the options change - so a
changed notification_time or a toggled option always results in the old
listeners being torn down (via entry.async_on_unload) and fresh ones
being registered. No manual "cancel old listener" bookkeeping is
required.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HAMSTER_NAME,
    CONF_NOTIFY_SERVICES,
    DEFAULT_DAILY_SUMMARY_ENABLED,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_WARNINGS_ENABLED,
    DOMAIN,
    NOTIFY_DOMAIN,
    NOTIFY_SERVICE_SEND_MESSAGE,
    OPTION_DAILY_SUMMARY_ENABLED,
    OPTION_NOTIFICATION_TIME,
    OPTION_WARNINGS_ENABLED,
    STORAGE_VERSION,
    WARNING_NOTIFICATION_COOLDOWN_HOURS,
)
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator
from .runtime_text import format_number, render_message

_LOGGER = logging.getLogger(__name__)

WARNING_COOLDOWN = timedelta(hours=WARNING_NOTIFICATION_COOLDOWN_HOURS)


class HamsterFitnessNotifier:
    """Owns both notification flows for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HamsterFitnessConfigEntry,
        coordinator: HamsterFitnessCoordinator,
    ) -> None:
        """Initialize the notifier (does not yet register any listener)."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._hamster_name: str = entry.data[CONF_HAMSTER_NAME]
        self._targets: list[str] = entry.data.get(CONF_NOTIFY_SERVICES, [])

        self._store: Store[dict[str, float]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_notifier"
        )
        # Nachtfenster-Distanz beim letzten Versand der Tageszusammenfassung
        # - der Vergleichswert für "mehr/weniger als gestern".
        self._last_night_km: float = 0.0

        self._last_sent: dict[str, datetime] = {}  # warning code -> UTC timestamp
        self._previous_reason_codes: set[str] = set()

    async def async_setup(self) -> None:
        """Register listeners according to the *current* options.

        Called once from async_setup_entry(). Each flow is registered
        independently, gated by its own option - if both are disabled,
        this is a no-op and nothing is ever sent.
        """
        stored = await self._store.async_load()
        if stored:
            self._last_night_km = stored.get("last_night_km", 0.0)

        if self._daily_summary_enabled:
            summary_time = self._summary_time
            self._entry.async_on_unload(
                async_track_time_change(
                    self._hass,
                    self._async_handle_summary_time,
                    hour=summary_time.hour,
                    minute=summary_time.minute,
                    second=summary_time.second,
                )
            )
        else:
            _LOGGER.debug(
                "Hamster Fitness (%s): Tageszusammenfassung deaktiviert, "
                "kein Listener registriert",
                self._hamster_name,
            )

        if self._warnings_enabled:
            self._entry.async_on_unload(
                self._coordinator.async_add_listener(
                    self._async_handle_coordinator_update
                )
            )
            # Direkt einmal mit dem aktuellen Snapshot abgleichen, damit ein
            # bereits beim Start aktiver Warngrund nicht erst auf die
            # nächste Sensor-Änderung warten muss, um gemeldet zu werden.
            self._async_handle_coordinator_update()
        else:
            _LOGGER.debug(
                "Hamster Fitness (%s): Warnungen deaktiviert, "
                "kein Listener registriert",
                self._hamster_name,
            )

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    @property
    def _warnings_enabled(self) -> bool:
        return bool(
            self._entry.options.get(OPTION_WARNINGS_ENABLED, DEFAULT_WARNINGS_ENABLED)
        )

    @property
    def _daily_summary_enabled(self) -> bool:
        return bool(
            self._entry.options.get(
                OPTION_DAILY_SUMMARY_ENABLED, DEFAULT_DAILY_SUMMARY_ENABLED
            )
        )

    @property
    def _summary_time(self) -> time:
        raw = self._entry.options.get(
            OPTION_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
        )
        parsed = dt_util.parse_time(raw) or dt_util.parse_time(
            DEFAULT_NOTIFICATION_TIME
        )
        assert parsed is not None  # DEFAULT_NOTIFICATION_TIME always parses
        return parsed

    # ------------------------------------------------------------------
    # Tägliche Zusammenfassung
    # ------------------------------------------------------------------

    @callback
    def _async_handle_summary_time(self, now: datetime) -> None:
        """Send the daily summary at the configured local time.

        Compares the night-window distance so far (since
        NIGHT_WINDOW_START_HOUR, e.g. 20:00) against the value this same
        method recorded the last time it fired - i.e. both numbers cover
        the same relative point in the night, so "mehr/weniger als
        gestern" is a fair comparison even though the current window
        technically isn't "closed" yet at notification time.
        """
        tonight_km = self._coordinator.data.night_distance_km
        delta_m = round((tonight_km - self._last_night_km) * 1000)

        if delta_m > 0:
            comparison = render_message(
                self._hass, "notify.more_than_yesterday", delta=str(delta_m)
            )
        elif delta_m < 0:
            comparison = render_message(
                self._hass, "notify.less_than_yesterday", delta=str(abs(delta_m))
            )
        else:
            comparison = render_message(self._hass, "notify.same_as_yesterday")

        message = render_message(
            self._hass,
            "notify.daily_summary",
            distance=format_number(self._hass, tonight_km, 2),
            comparison=comparison,
        )
        self._hass.async_create_task(self._async_send_summary(message, tonight_km))

    # ------------------------------------------------------------------
    # Kritische Warnungen (sofort, mit Cooldown pro Warngrund)
    # ------------------------------------------------------------------

    @callback
    def _async_handle_coordinator_update(self) -> None:
        """Notify immediately for every newly-appeared warning reason."""
        reasons = self._coordinator.data.warning_reasons  # dict[code, text]
        current_codes = set(reasons)
        new_codes = current_codes - self._previous_reason_codes
        self._previous_reason_codes = current_codes

        if not new_codes:
            return

        now = dt_util.utcnow()
        for code in new_codes:
            last_sent = self._last_sent.get(code)
            if last_sent is not None and now - last_sent < WARNING_COOLDOWN:
                _LOGGER.debug(
                    "Hamster Fitness (%s): Warnung '%s' unterdrückt (Cooldown aktiv)",
                    self._hamster_name,
                    code,
                )
                continue
            self._last_sent[code] = now
            self._hass.async_create_task(self._async_send(reasons[code]))

    # ------------------------------------------------------------------
    # Versand
    # ------------------------------------------------------------------

    async def _async_send_summary(self, message: str, tonight_km: float) -> None:
        """Send the daily summary, then roll `tonight_km` forward as the
        new comparison baseline for tomorrow's summary."""
        await self._async_send(message)
        self._last_night_km = tonight_km
        await self._store.async_save({"last_night_km": self._last_night_km})

    async def _async_send(self, message: str) -> None:
        """Send `message` to every notify entity chosen during setup.

        The hamster's name is sent as `title` (rendered as the
        notification heading on targets that support it, e.g. the mobile
        app), so `message` itself never needs to repeat it.
        """
        if not self._targets:
            _LOGGER.warning(
                "Hamster Fitness (%s): keine Notify-Ziele konfiguriert, "
                "Benachrichtigung übersprungen: %s",
                self._hamster_name,
                message,
            )
            return
        try:
            await self._hass.services.async_call(
                NOTIFY_DOMAIN,
                NOTIFY_SERVICE_SEND_MESSAGE,
                {
                    "entity_id": self._targets,
                    "title": self._hamster_name,
                    "message": message,
                },
                blocking=True,
            )
        except Exception:  # noqa: BLE001 - ein Notify-Fehler darf HA nicht crashen
            _LOGGER.exception(
                "Hamster Fitness (%s): Senden der Benachrichtigung fehlgeschlagen",
                self._hamster_name,
            )
