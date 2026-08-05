"""Registers the bundled hamster-fitness-card as a Lovelace resource.

Mirrors the pattern used by other custom integrations that ship their own
card (e.g. AlexandrErohin/home-assistant-flightradar24): serve the JS file
from this folder as a static path, then - if the dashboard is in "storage"
mode (UI-managed) - auto-register it as a Lovelace resource so the user
never has to add it by hand. In "yaml" mode dashboards are user-managed
files, so we can't safely inject a resource there; the user adds it
manually instead (see README.md).
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from ..const import JS_MODULES, URL_BASE

_LOGGER = getLogger(__name__)


class JSModuleRegistration:
    """Registers this integration's frontend resources."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize with the current Lovelace data, if already loaded."""
        self.hass = hass
        self.lovelace = self.hass.data.get("lovelace")

    async def async_register(self) -> None:
        """Register the static path and, if possible, the Lovelace resource."""
        await self._async_register_path()

        mode = getattr(self.lovelace, "mode", None) or getattr(
            self.lovelace, "resource_mode", "yaml"
        )
        if mode == "storage":
            await self._async_wait_for_lovelace_resources()
        else:
            _LOGGER.info(
                "Hamster Fitness: Dashboard läuft im YAML-Modus - die Karte "
                "%s muss manuell als Lovelace-Ressource hinzugefügt werden, "
                "siehe README.md.",
                JS_MODULES[0]["filename"],
            )

    async def _async_register_path(self) -> None:
        """Serve this folder's JS file(s) under URL_BASE."""
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(Path(__file__).parent), False)]
            )
            _LOGGER.debug("Pfad registriert: %s -> %s", URL_BASE, Path(__file__).parent)
        except RuntimeError:
            # Bereits registriert (z. B. Config-Entry-Reload) - kein Fehler.
            _LOGGER.debug("Pfad bereits registriert: %s", URL_BASE)

    async def _async_wait_for_lovelace_resources(self) -> None:
        """Retry every 5s until Lovelace's own resource list has loaded."""

        async def _check_loaded(_now: Any) -> None:
            if self.lovelace is None:
                self.lovelace = self.hass.data.get("lovelace")
            if self.lovelace and getattr(self.lovelace.resources, "loaded", False):
                await self._async_register_modules()
            else:
                async_call_later(self.hass, 5, _check_loaded)

        await _check_loaded(None)

    async def _async_register_modules(self) -> None:
        """Create or version-bump this integration's Lovelace resource(s)."""
        existing = [
            resource
            for resource in self.lovelace.resources.async_items()
            if resource["url"].startswith(URL_BASE)
        ]

        for module in JS_MODULES:
            url = f"{URL_BASE}/{module['filename']}"
            match = next(
                (r for r in existing if self._url_path(r["url"]) == url), None
            )

            if match is None:
                _LOGGER.info(
                    "Hamster Fitness: Registriere Karte %s (v%s)",
                    module["name"],
                    module["version"],
                )
                await self.lovelace.resources.async_create_item(
                    {"res_type": "module", "url": f"{url}?v={module['version']}"}
                )
            elif self._url_version(match["url"]) != module["version"]:
                _LOGGER.info(
                    "Hamster Fitness: Aktualisiere Karte %s auf v%s",
                    module["name"],
                    module["version"],
                )
                await self.lovelace.resources.async_update_item(
                    match["id"],
                    {"res_type": "module", "url": f"{url}?v={module['version']}"},
                )

    @staticmethod
    def _url_path(url: str) -> str:
        return url.split("?")[0]

    @staticmethod
    def _url_version(url: str) -> str:
        parts = url.split("?")
        if len(parts) > 1 and parts[1].startswith("v="):
            return parts[1].removeprefix("v=")
        return "0"
