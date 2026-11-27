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

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

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

        if self.lovelace is not None and self.lovelace.resource_mode == "storage":
            # Storage-mode resources load lazily, on first access. Waiting
            # for a browser to trigger that registered our resource only
            # after the first dashboard load following a restart, so the
            # cards could be missing until a reload. async_get_info() loads
            # the list if nothing has yet.
            await self.lovelace.resources.async_get_info()
            await self._async_register_modules()
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

    async def _async_register_modules(self) -> None:
        """Create or version-bump this integration's Lovelace resource(s)."""
        assert self.lovelace is not None
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
