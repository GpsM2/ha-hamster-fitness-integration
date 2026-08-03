"""The Hamster Fitness integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import HamsterFitnessConfigEntry, HamsterFitnessCoordinator
from .notify import HamsterFitnessNotifier

_LOGGER = logging.getLogger(__name__)


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HamsterFitnessConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
