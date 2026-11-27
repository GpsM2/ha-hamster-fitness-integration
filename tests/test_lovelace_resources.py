"""The cards are registered at startup, without waiting for a browser."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.hamster_fitness.const import DOMAIN, JS_MODULES, URL_BASE


async def test_cards_are_registered_without_a_browser(hass: HomeAssistant) -> None:
    """Storage-mode resources load lazily, on first access.

    The registration used to wait for something else - a browser opening a
    dashboard - to load them, polling every 5 seconds. Until then the cards
    were not registered, so the first dashboard load after a restart could
    miss them.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    urls = {r["url"].split("?")[0] for r in hass.data["lovelace"].resources.async_items()}
    assert {f"{URL_BASE}/{m['filename']}" for m in JS_MODULES} <= urls
