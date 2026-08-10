"""The Hamster Fitness integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import archive, runtime_text
from .const import (
    BREED_OTHER,
    BREEDS,
    COAT_COLOR_HEX,
    COAT_COLORS,
    CONF_HAMSTER_NAME,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_DIAMETER_SYNC_ENTITY,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator
from .door_light import HamsterFitnessDoorLight
from .frontend import JSModuleRegistration
from .notify import HamsterFitnessNotifier
from .update_check import async_setup_update_check

_LOGGER = logging.getLogger(__name__)

NUMBER_DOMAIN = "number"
NUMBER_SERVICE_SET_VALUE = "set_value"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hamster Fitness integration (domain-level, once).

    Registers the bundled hamster-fitness-card, independently of how many
    hamster config entries exist. Deferred until Home Assistant has fully
    started, since the Lovelace resource list isn't guaranteed to be ready
    any earlier (same reasoning/pattern used by other integrations that
    ship their own card, e.g. home-assistant-flightradar24).
    """

    async def _register_frontend(_event: Event | None = None) -> None:
        await JSModuleRegistration(hass).async_register()

    if hass.state is CoreState.running:
        await _register_frontend()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register_frontend)

    websocket_api.async_register_command(hass, _ws_history)
    websocket_api.async_register_command(hass, _ws_add_historical_hamster)
    websocket_api.async_register_command(hass, _ws_update_historical_hamster)
    websocket_api.async_register_command(hass, _ws_remove_historical_hamster)

    # Raises a Repairs entry when HACS has written a new version to disk
    # but Home Assistant is still running the old one. Domain-wide, like
    # the commands above - the version belongs to the integration, not to
    # any one hamster.
    await async_setup_update_check(hass)

    return True


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/history"})
@websocket_api.async_response
async def _ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the lifetime archive of departed hamsters.

    The chronicle card can find currently configured hamsters through the
    entity registry, the same way the ranking card does - but a hamster
    whose config entry was deleted has no entities left to find. This is
    the only way to get at those, so the card asks for them here.

    Registered domain-wide (in async_setup, not per entry), since the
    archive is shared by all hamsters and has to answer even when no
    config entry exists at all any more.
    """
    connection.send_result(msg["id"], {"hamsters": await archive.async_load(hass)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/add_historical_hamster",
        vol.Required("name"): str,
        vol.Required("breed"): vol.In(BREEDS),
        vol.Optional("breed_other", default=""): str,
        vol.Required("coat_color"): vol.In(COAT_COLORS),
        vol.Required("acquisition_date"): cv.date,
        vol.Required("departure_date"): cv.date,
    }
)
@websocket_api.async_response
async def _ws_add_historical_hamster(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Add a hamster from before this integration existed.

    For a hamster with no sensors, no device and therefore no health
    score to speak of - see the chronicle card's "add a past hamster"
    dialog. The record carries no distance/speed/score fields at all
    (rather than zeroes, which would read as "a hamster that never
    moved"); the chronicle card already renders a missing value as
    "–", the same way it does for the two other optional stat columns.
    """
    name = msg["name"].strip()
    if not name:
        connection.send_error(msg["id"], "invalid_format", "Name is required")
        return
    breed_other = msg["breed_other"].strip()
    if msg["breed"] == BREED_OTHER and not breed_other:
        connection.send_error(
            msg["id"], "invalid_format", "Breed description is required for 'Other'"
        )
        return

    await archive.async_add_manual_entry(
        hass,
        {
            "name": name,
            "breed": msg["breed"],
            "breed_other": breed_other if msg["breed"] == BREED_OTHER else None,
            "coat_color": msg["coat_color"],
            "coat_color_hex": COAT_COLOR_HEX.get(msg["coat_color"]),
            "acquisition_date": msg["acquisition_date"].isoformat(),
            "departure_date": msg["departure_date"].isoformat(),
            "archived_at": dt_util.utcnow().isoformat(),
        },
    )
    connection.send_result(msg["id"], {"hamsters": await archive.async_load(hass)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/update_historical_hamster",
        vol.Required("entry_id"): str,
        vol.Required("name"): str,
        vol.Required("breed"): vol.In(BREEDS),
        vol.Optional("breed_other", default=""): str,
        vol.Required("coat_color"): vol.In(COAT_COLORS),
        vol.Required("acquisition_date"): cv.date,
        vol.Required("departure_date"): cv.date,
    }
)
@websocket_api.async_response
async def _ws_update_historical_hamster(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Edit a hamster previously added through the "add a past hamster" dialog.

    Same fields and validation as adding one - `archive.async_update_manual_entry`
    is the actual safety boundary, rejecting anything that isn't a manually-added
    entry's own id, so this can't be used to rewrite a real hamster's departure
    record.
    """
    name = msg["name"].strip()
    if not name:
        connection.send_error(msg["id"], "invalid_format", "Name is required")
        return
    breed_other = msg["breed_other"].strip()
    if msg["breed"] == BREED_OTHER and not breed_other:
        connection.send_error(
            msg["id"], "invalid_format", "Breed description is required for 'Other'"
        )
        return

    updated = await archive.async_update_manual_entry(
        hass,
        msg["entry_id"],
        {
            "name": name,
            "breed": msg["breed"],
            "breed_other": breed_other if msg["breed"] == BREED_OTHER else None,
            "coat_color": msg["coat_color"],
            "coat_color_hex": COAT_COLOR_HEX.get(msg["coat_color"]),
            "acquisition_date": msg["acquisition_date"].isoformat(),
            "departure_date": msg["departure_date"].isoformat(),
            "archived_at": dt_util.utcnow().isoformat(),
        },
    )
    if not updated:
        connection.send_error(msg["id"], "not_found", "No such manual entry")
        return
    connection.send_result(msg["id"], {"hamsters": await archive.async_load(hass)})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/remove_historical_hamster",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def _ws_remove_historical_hamster(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a hamster added through the "add a past hamster" dialog."""
    removed = await archive.async_remove_manual_entry(hass, msg["entry_id"])
    if not removed:
        connection.send_error(msg["id"], "not_found", "No such manual entry")
        return
    connection.send_result(msg["id"], {"hamsters": await archive.async_load(hass)})


async def async_setup_entry(hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> bool:
    """Set up Hamster Fitness from a config entry."""
    # Warms the cache for warning/notification text (see runtime_text.py) -
    # must happen before the coordinator's first refresh, which can
    # already construct a warning message on the very first calculation.
    await runtime_text.async_warm_up(hass)

    coordinator = HamsterFitnessCoordinator(hass, entry)

    # Registers the source-entity listeners (_async_setup) and computes the
    # first snapshot. Raises ConfigEntryNotReady automatically on failure.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Registers the daily-summary timer and the warning listener, each
    # gated by its own option (OPTION_DAILY_SUMMARY_ENABLED /
    # OPTION_WARNINGS_ENABLED, see notify.py). Both are torn down
    # automatically on unload/reload via entry.async_on_unload().
    await HamsterFitnessNotifier(hass, entry, coordinator).async_setup()

    # Turns CONF_LIGHT_ENTITY on/off with the cage door, if configured -
    # a no-op otherwise, see door_light.py.
    await HamsterFitnessDoorLight(hass, entry, coordinator).async_setup()

    # Pushes CONF_WHEEL_DIAMETER to CONF_WHEEL_DIAMETER_SYNC_ENTITY, if
    # configured - a no-op otherwise, see _async_sync_wheel_diameter().
    await _async_sync_wheel_diameter(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_sync_wheel_diameter(
    hass: HomeAssistant, entry: HamsterFitnessConfigEntry
) -> None:
    """Push CONF_WHEEL_DIAMETER to CONF_WHEEL_DIAMETER_SYNC_ENTITY, if set.

    A one-way, one-shot push - runs once per entry setup, which also
    covers every Reconfigure (that fully reloads the entry). The typical
    target is the "Hamster Wheel Diameter" number entity on an ESPHome
    device (see esphome/hamster-wheel-sensor.yaml), which would otherwise
    have to be kept in sync with this value by hand. The sync entity
    might not be available yet right after a Home Assistant restart (its
    own integration may still be connecting) - that's logged, not raised,
    since it shouldn't block this entry from setting up.
    """
    sync_entity = entry.data.get(CONF_WHEEL_DIAMETER_SYNC_ENTITY)
    if not sync_entity:
        return
    try:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NUMBER_SERVICE_SET_VALUE,
            {"entity_id": sync_entity, "value": entry.data[CONF_WHEEL_DIAMETER]},
            blocking=True,
        )
    except Exception:  # noqa: BLE001 - ein Sync-Fehler darf HA nicht crashen
        _LOGGER.exception(
            "Hamster Fitness (%s): Raddurchmesser konnte nicht an %s "
            "übertragen werden",
            entry.data[CONF_HAMSTER_NAME],
            sync_entity,
        )
