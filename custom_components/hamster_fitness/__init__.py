"""The Hamster Fitness integration."""

from __future__ import annotations

import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import PLATFORMS
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator
from .door_light import HamsterFitnessDoorLight
from .frontend import JSModuleRegistration
from .notify import HamsterFitnessNotifier

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hamster Fitness integration (domain-level, once).

    Registers the bundled hamster-fitness-card, independently of how many
    hamster config entries exist. Deferred until Home Assistant has fully
    started, since the Lovelace resource list isn't guaranteed to be ready
    any earlier (same reasoning/pattern used by other integrations that
    ship their own card, e.g. home-assistant-flightradar24).
    """

    async def _register_frontend(_event=None) -> None:
        await JSModuleRegistration(hass).async_register()

    if hass.state is CoreState.running:
        await _register_frontend()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register_frontend)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> bool:
    """Set up Hamster Fitness from a config entry."""
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
