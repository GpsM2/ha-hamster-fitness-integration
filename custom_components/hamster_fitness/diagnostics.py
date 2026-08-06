"""Diagnostics support for the Hamster Fitness integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_NOTIFY_SERVICES

# Not secrets, but potentially identifying (e.g. a mobile_app notify target
# usually encodes a device/person name) - redacted the same way HA Core's
# own diagnostics.py examples redact anything beyond plain sensor/device
# references.
TO_REDACT = {CONF_NOTIFY_SERVICES}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    registry = er.async_get(hass)
    entities = registry.entities.get_entries_for_config_entry_id(entry.entry_id)

    return {
        "config_entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": entry.options,
        },
        "entities": [entity.extended_dict for entity in entities],
    }
