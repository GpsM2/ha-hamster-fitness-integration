"""Notification logic for the Hamster Fitness integration.

Four independent, options-gated notification flows:

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
- A weigh-in reminder, checked at the same daily time, that only fires
  when the weight is actually overdue - i.e. no new value has been
  entered for `OPTION_WEIGHT_REMINDER_DAYS` days. Whoever weighs their
  hamster regularly never sees it. Gated by
  `OPTION_WEIGHT_REMINDER_ENABLED` (off by default).
- A heat care reminder, also checked at that same daily time, when the
  day's forecast high reaches `OPTION_HEAT_FORECAST_THRESHOLD_C`. Unlike
  the others this one looks *forward*: the point is to act before the
  cage gets hot, not to report that it already is (the climate pillar
  covers that). Gated by `OPTION_HEAT_FORECAST_ENABLED` (off by default)
  and needs `CONF_WEATHER_ENTITY`.

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
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HAMSTER_NAME,
    CONF_NOTIFY_SERVICES,
    CONF_WEATHER_ENTITY,
    DEFAULT_DAILY_SUMMARY_ENABLED,
    DEFAULT_HEAT_FORECAST_ENABLED,
    DEFAULT_HEAT_FORECAST_THRESHOLD_C,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_WARNINGS_ENABLED,
    DEFAULT_WEIGHT_REMINDER_DAYS,
    DEFAULT_WEIGHT_REMINDER_ENABLED,
    DOMAIN,
    HEAT_REMINDER_COOLDOWN_HOURS,
    NOTIFY_DOMAIN,
    NOTIFY_SERVICE_SEND_MESSAGE,
    OPTION_DAILY_SUMMARY_ENABLED,
    OPTION_HEAT_FORECAST_ENABLED,
    OPTION_HEAT_FORECAST_THRESHOLD_C,
    OPTION_NOTIFICATION_TIME,
    OPTION_WARNINGS_ENABLED,
    OPTION_WEIGHT_REMINDER_DAYS,
    OPTION_WEIGHT_REMINDER_ENABLED,
    STORAGE_VERSION,
    WARNING_NOTIFICATION_COOLDOWN_HOURS,
    WEATHER_DOMAIN,
    WEATHER_SERVICE_GET_FORECASTS,
)
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator
from .runtime_text import format_number, render_message

_LOGGER = logging.getLogger(__name__)

WARNING_COOLDOWN = timedelta(hours=WARNING_NOTIFICATION_COOLDOWN_HOURS)


class HamsterFitnessNotifier:
    """Owns every notification flow for one config entry."""

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

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_notifier"
        )
        # Nachtfenster-Distanz beim letzten Versand der Tageszusammenfassung
        # - der Vergleichswert für "mehr/weniger als gestern".
        self._last_night_km: float = 0.0
        # Wann zuletzt ans Wiegen erinnert wurde. Verhindert, dass die
        # Erinnerung ab dem Fälligkeitstag jeden Tag aufs Neue kommt,
        # solange niemand ein Gewicht einträgt.
        self._last_weight_reminder_at: datetime | None = None
        # Wetter-Entity für die Hitze-Erinnerung (optional, siehe
        # CONF_WEATHER_ENTITY) und der Zeitpunkt der letzten solchen
        # Erinnerung - eine Hitzewelle dauert mehrere Tage, die Tipps sind
        # nach dem ersten Morgen bekannt.
        self._weather_entity: str | None = entry.data.get(CONF_WEATHER_ENTITY)
        self._last_heat_reminder_at: datetime | None = None

        self._last_sent: dict[str, datetime] = {}  # warning code -> UTC timestamp
        self._previous_reason_codes: set[str] = set()

    async def async_setup(self) -> None:
        """Register listeners according to the *current* options.

        Called once from async_setup_entry(). Each flow is registered
        independently, gated by its own option - with all of them
        disabled this is a no-op and nothing is ever sent.
        """
        stored = await self._store.async_load()
        if stored:
            self._last_night_km = stored.get("last_night_km", 0.0)
            reminder_raw = stored.get("last_weight_reminder_at")
            self._last_weight_reminder_at = (
                dt_util.parse_datetime(reminder_raw) if reminder_raw else None
            )
            heat_raw = stored.get("last_heat_reminder_at")
            self._last_heat_reminder_at = (
                dt_util.parse_datetime(heat_raw) if heat_raw else None
            )

        # The time-based flows share one timer at the same local time -
        # registering several identical ones would only mean several
        # wake-ups for the same instant.
        if (
            self._daily_summary_enabled
            or self._weight_reminder_enabled
            or self._heat_forecast_enabled
        ):
            summary_time = self._summary_time
            self._entry.async_on_unload(
                async_track_time_change(
                    self._hass,
                    self._async_handle_daily_time,
                    hour=summary_time.hour,
                    minute=summary_time.minute,
                    second=summary_time.second,
                )
            )
        else:
            _LOGGER.debug(
                "Hamster Fitness (%s): Tageszusammenfassung, Wiege- und "
                "Hitze-Erinnerung deaktiviert, kein Listener registriert",
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
    def _weight_reminder_enabled(self) -> bool:
        return bool(
            self._entry.options.get(
                OPTION_WEIGHT_REMINDER_ENABLED, DEFAULT_WEIGHT_REMINDER_ENABLED
            )
        )

    @property
    def _heat_forecast_enabled(self) -> bool:
        """Whether to look ahead at all - needs a weather entity too.

        The option alone isn't enough: without something to ask for a
        forecast there is nothing to check, and gating here keeps every
        later step from having to re-test it.
        """
        if not self._weather_entity:
            return False
        return bool(
            self._entry.options.get(
                OPTION_HEAT_FORECAST_ENABLED, DEFAULT_HEAT_FORECAST_ENABLED
            )
        )

    @property
    def _heat_forecast_threshold(self) -> float:
        return float(
            self._entry.options.get(
                OPTION_HEAT_FORECAST_THRESHOLD_C, DEFAULT_HEAT_FORECAST_THRESHOLD_C
            )
        )

    @property
    def _weight_reminder_interval(self) -> timedelta:
        days = self._entry.options.get(
            OPTION_WEIGHT_REMINDER_DAYS, DEFAULT_WEIGHT_REMINDER_DAYS
        )
        return timedelta(days=days)

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
    def _async_handle_daily_time(self, now: datetime) -> None:
        """Run every time-based flow at the configured local time.

        All stay quiet while the hamster is away (boarding mode): a
        summary repeating a frozen distance, a nudge to weigh a hamster
        that is at the vet, or advice to shade a cage the hamster isn't
        in, is noise the user can do nothing about. Warnings are already
        silent - the coordinator stops producing reasons while paused.
        """
        if self._coordinator.boarding:
            _LOGGER.debug(
                "Hamster Fitness (%s): vorübergehend abwesend, "
                "Tageszusammenfassung, Wiege- und Hitze-Erinnerung "
                "übersprungen",
                self._hamster_name,
            )
            return
        if self._daily_summary_enabled:
            self._async_send_daily_summary()
        if self._weight_reminder_enabled:
            self._async_check_weight_reminder()
        if self._heat_forecast_enabled:
            self._hass.async_create_task(self._async_check_heat_forecast())

    @callback
    def _async_send_daily_summary(self) -> None:
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
    # Wiege-Erinnerung (nur wenn überfällig)
    # ------------------------------------------------------------------

    @callback
    def _async_check_weight_reminder(self) -> None:
        """Remind about weighing, but only if it is actually overdue.

        Two conditions, both required: no weight entered for a full
        interval (never having weighed at all counts as overdue), and no
        reminder sent within the last interval either - otherwise an
        ignored reminder would repeat every single day.
        """
        now = dt_util.utcnow()
        interval = self._weight_reminder_interval
        last_weighed = self._coordinator.weight_last_set_at

        if last_weighed is not None and now - last_weighed < interval:
            return
        if (
            self._last_weight_reminder_at is not None
            and now - self._last_weight_reminder_at < interval
        ):
            return

        if last_weighed is None:
            message = render_message(self._hass, "notify.weight_reminder_never")
        else:
            message = render_message(
                self._hass,
                "notify.weight_reminder",
                days=str((now - last_weighed).days),
            )
        self._hass.async_create_task(self._async_send_weight_reminder(message, now))

    # ------------------------------------------------------------------
    # Hitze-Erinnerung (vorausschauend, nur bei konfigurierter Wetter-Entity)
    # ------------------------------------------------------------------

    async def _async_check_heat_forecast(self) -> None:
        """Warn ahead of a hot day, while there is still time to act.

        Deliberately forward-looking: by the time the cage is actually
        too warm the climate pillar has already docked points and the
        useful moment has passed. Shade, cooling and fresh water all have
        to happen before the heat arrives.

        Silent unless today's forecast high reaches the configured
        threshold, and then at most once per HEAT_REMINDER_COOLDOWN_HOURS
        - a heatwave runs for days, and repeating identical advice every
        morning only teaches the user to swipe it away.
        """
        now = dt_util.utcnow()
        cooldown = timedelta(hours=HEAT_REMINDER_COOLDOWN_HOURS)
        if (
            self._last_heat_reminder_at is not None
            and now - self._last_heat_reminder_at < cooldown
        ):
            return

        high = await self._async_forecast_high()
        if high is None or high < self._heat_forecast_threshold:
            return

        message = render_message(
            self._hass,
            "notify.heat_forecast",
            temperature=format_number(self._hass, high, 0),
        )
        await self._async_send(message)
        self._last_heat_reminder_at = now
        await self._async_save()

    async def _async_forecast_high(self) -> float | None:
        """Today's forecast high from the configured weather entity.

        Uses the `weather.get_forecasts` service rather than the entity's
        old `forecast` state attribute - modern Home Assistant dropped
        that attribute, so the service call is the only supported route.

        Returns None whenever the answer isn't usable (entity gone, the
        integration returned nothing, no temperature in the first daily
        entry). None means "don't know", never "not hot" - the caller
        stays silent either way, which is the safe direction for a
        reminder nobody asked to be woken by.
        """
        assert self._weather_entity is not None  # gated by _heat_forecast_enabled
        try:
            response = await self._hass.services.async_call(
                WEATHER_DOMAIN,
                WEATHER_SERVICE_GET_FORECASTS,
                {"entity_id": self._weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - a broken forecast must not crash HA
            _LOGGER.exception(
                "Hamster Fitness (%s): Wettervorhersage konnte nicht "
                "abgerufen werden",
                self._hamster_name,
            )
            return None

        # The response is only loosely typed (it comes back as plain JSON),
        # and its shape is up to whichever weather integration answered.
        # Each level is checked rather than assumed: a provider returning
        # something unexpected should mean "no forecast", not a traceback
        # in the middle of the morning notification run.
        if not isinstance(response, dict):
            return None
        entity_result = response.get(self._weather_entity)
        if not isinstance(entity_result, dict):
            return None
        forecasts = entity_result.get("forecast")
        if not isinstance(forecasts, list) or not forecasts:
            return None
        today = forecasts[0]
        if not isinstance(today, dict):
            return None

        # "native_temperature" is the daily high in Home Assistant's daily
        # forecasts; "temperature" is the older spelling some integrations
        # still use.
        for key in ("native_temperature", "temperature"):
            value = today.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None

    def _weight_entity_id(self) -> str | None:
        """Resolve this hamster's weight entity, for the reminder's deep link.

        Looked up through the registry by unique_id rather than guessed
        from the hamster's name - entity_ids are generated once from the
        *translated* entity name, so guessing breaks on any non-English
        installation.
        """
        registry = er.async_get(self._hass)
        return registry.async_get_entity_id(
            Platform.NUMBER, DOMAIN, f"{self._entry.entry_id}_weight"
        )

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
        await self._async_save()

    async def _async_send_weight_reminder(self, message: str, now: datetime) -> None:
        """Send the weigh-in reminder and start its cooldown.

        Unlike the other messages this one carries a deep link, so
        tapping the notification opens the weight entity straight away
        instead of dumping the user on their dashboard's front page with
        no hint of what to do next.
        """
        weight_entity = self._weight_entity_id()
        await self._async_send(
            message,
            # clickAction is the Android companion app's key, url is
            # iOS's; sending both means one payload works on either.
            data={
                "clickAction": f"entityId:{weight_entity}",
                "url": f"entityId:{weight_entity}",
            }
            if weight_entity
            else None,
        )
        self._last_weight_reminder_at = now
        await self._async_save()

    async def _async_save(self) -> None:
        """Persist both flows' bookkeeping in one go."""
        await self._store.async_save(
            {
                "last_night_km": self._last_night_km,
                "last_weight_reminder_at": (
                    self._last_weight_reminder_at.isoformat()
                    if self._last_weight_reminder_at
                    else None
                ),
                "last_heat_reminder_at": (
                    self._last_heat_reminder_at.isoformat()
                    if self._last_heat_reminder_at
                    else None
                ),
            }
        )

    async def _async_send(self, message: str, data: dict[str, Any] | None = None) -> None:
        """Send `message` to every notify entity chosen during setup.

        The hamster's name is sent as `title` (rendered as the
        notification heading on targets that support it, e.g. the mobile
        app), so `message` itself never needs to repeat it.

        `data` carries companion-app extras such as a tap target. The
        modern `notify.send_message` entity action accepts only message
        and title, so anything with `data` has to go through the legacy
        per-device service (`notify.mobile_app_<device>`), which the
        mobile app registers alongside its entity. Where no such service
        exists - a notify target that isn't the companion app - the
        message still goes out, just without the extras.
        """
        if not self._targets:
            _LOGGER.warning(
                "Hamster Fitness (%s): keine Notify-Ziele konfiguriert, "
                "Benachrichtigung übersprungen: %s",
                self._hamster_name,
                message,
            )
            return

        plain: list[str] = []
        for target in self._targets:
            legacy_service = target.split(".", 1)[-1]
            if data and self._hass.services.has_service(NOTIFY_DOMAIN, legacy_service):
                await self._async_call_notify(
                    legacy_service,
                    {"title": self._hamster_name, "message": message, "data": data},
                )
            else:
                plain.append(target)

        if plain:
            await self._async_call_notify(
                NOTIFY_SERVICE_SEND_MESSAGE,
                {
                    "entity_id": plain,
                    "title": self._hamster_name,
                    "message": message,
                },
            )

    async def _async_call_notify(self, service: str, payload: dict[str, Any]) -> None:
        """Call one notify service, swallowing failures."""
        try:
            await self._hass.services.async_call(
                NOTIFY_DOMAIN, service, payload, blocking=True
            )
        except Exception:  # noqa: BLE001 - ein Notify-Fehler darf HA nicht crashen
            _LOGGER.exception(
                "Hamster Fitness (%s): Senden der Benachrichtigung fehlgeschlagen",
                self._hamster_name,
            )
