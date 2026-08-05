"""Cage-light automation for the Hamster Fitness integration.

Turns a configured light on when the cage door opens and (optionally,
after an optional delay) back off when it closes. Only active if
CONF_LIGHT_ENTITY was set during setup - otherwise async_setup() is a
no-op, nothing is ever touched.

Reacts to the coordinator's `door_open` (not the raw door_sensor
directly), the same single source of truth the health-score calculation
and binary_sensor.<hamster>_door already use - keeps one consistent view
of "is the door open" instead of a second, potentially racing listener.
"""

from __future__ import annotations

import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_LIGHT_ENTITY,
    DEFAULT_LIGHT_BRIGHTNESS_PCT,
    DEFAULT_LIGHT_TRANSITION_S,
    DEFAULT_LIGHT_TURN_OFF_DELAY_S,
    DEFAULT_LIGHT_TURN_OFF_ENABLED,
    OPTION_LIGHT_BRIGHTNESS_PCT,
    OPTION_LIGHT_TRANSITION_S,
    OPTION_LIGHT_TURN_OFF_DELAY_S,
    OPTION_LIGHT_TURN_OFF_ENABLED,
)
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator

_LOGGER = logging.getLogger(__name__)

LIGHT_DOMAIN = "light"
SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"


class HamsterFitnessDoorLight:
    """Owns the door-triggered light automation for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HamsterFitnessConfigEntry,
        coordinator: HamsterFitnessCoordinator,
    ) -> None:
        """Initialize the door-light automation (does not yet register anything)."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._light_entity: str | None = entry.data.get(CONF_LIGHT_ENTITY)
        self._previous_door_open: bool | None = None
        self._cancel_delayed_turn_off: CALLBACK_TYPE | None = None

    async def async_setup(self) -> None:
        """Register the coordinator listener, if a light was configured."""
        if not self._light_entity:
            _LOGGER.debug(
                "Hamster Fitness: keine Käfigbeleuchtung konfiguriert, "
                "Licht-Automatik inaktiv"
            )
            return

        self._entry.async_on_unload(
            self._coordinator.async_add_listener(self._async_handle_coordinator_update)
        )
        self._entry.async_on_unload(self._async_cancel_pending_turn_off)

        # Direkt den aktuellen Zustand übernehmen, damit ein beim Start
        # bereits offener Deckel nicht erst auf die nächste Änderung warten
        # muss, um das Licht einzuschalten.
        self._previous_door_open = self._coordinator.data.door_open
        if self._previous_door_open:
            self._hass.async_create_task(self._async_turn_on())

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    @property
    def _brightness_pct(self) -> int:
        return self._entry.options.get(
            OPTION_LIGHT_BRIGHTNESS_PCT, DEFAULT_LIGHT_BRIGHTNESS_PCT
        )

    @property
    def _transition(self) -> float:
        return self._entry.options.get(
            OPTION_LIGHT_TRANSITION_S, DEFAULT_LIGHT_TRANSITION_S
        )

    @property
    def _turn_off_enabled(self) -> bool:
        return self._entry.options.get(
            OPTION_LIGHT_TURN_OFF_ENABLED, DEFAULT_LIGHT_TURN_OFF_ENABLED
        )

    @property
    def _turn_off_delay(self) -> float:
        return self._entry.options.get(
            OPTION_LIGHT_TURN_OFF_DELAY_S, DEFAULT_LIGHT_TURN_OFF_DELAY_S
        )

    # ------------------------------------------------------------------
    # Event-Handling
    # ------------------------------------------------------------------

    @callback
    def _async_handle_coordinator_update(self) -> None:
        """React only to an actual open<->closed transition of the door."""
        door_open = self._coordinator.data.door_open
        if door_open == self._previous_door_open:
            return
        self._previous_door_open = door_open

        self._async_cancel_pending_turn_off()

        if door_open:
            self._hass.async_create_task(self._async_turn_on())
        elif self._turn_off_enabled:
            if self._turn_off_delay > 0:
                self._cancel_delayed_turn_off = async_call_later(
                    self._hass, self._turn_off_delay, self._async_handle_delayed_turn_off
                )
            else:
                self._hass.async_create_task(self._async_turn_off())

    @callback
    def _async_cancel_pending_turn_off(self) -> None:
        """Cancel a scheduled delayed turn-off, e.g. because the door re-opened."""
        if self._cancel_delayed_turn_off is not None:
            self._cancel_delayed_turn_off()
            self._cancel_delayed_turn_off = None

    async def _async_handle_delayed_turn_off(self, _now) -> None:
        """Run the turn-off once OPTION_LIGHT_TURN_OFF_DELAY_S has elapsed."""
        self._cancel_delayed_turn_off = None
        await self._async_turn_off()

    # ------------------------------------------------------------------
    # Versand
    # ------------------------------------------------------------------

    async def _async_turn_on(self) -> None:
        data: dict[str, float | int | str] = {
            "entity_id": self._light_entity,
            "brightness_pct": self._brightness_pct,
        }
        if self._transition > 0:
            data["transition"] = self._transition
        await self._async_call_light_service(SERVICE_TURN_ON, data)

    async def _async_turn_off(self) -> None:
        data: dict[str, float | int | str] = {"entity_id": self._light_entity}
        if self._transition > 0:
            data["transition"] = self._transition
        await self._async_call_light_service(SERVICE_TURN_OFF, data)

    async def _async_call_light_service(
        self, service: str, data: dict[str, float | int | str]
    ) -> None:
        try:
            await self._hass.services.async_call(
                LIGHT_DOMAIN, service, data, blocking=True
            )
        except Exception:  # noqa: BLE001 - ein Licht-Fehler darf HA nicht crashen
            _LOGGER.exception(
                "Hamster Fitness: Käfigbeleuchtung (%s) konnte nicht geschaltet werden",
                self._light_entity,
            )
