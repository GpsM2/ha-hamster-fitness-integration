"""Localized, dynamically-composed runtime text (warnings, notifications).

Config-flow/entity/options text is translated automatically by Home
Assistant's frontend from strings.json/translations/*.json. The text
handled here is different: it's built dynamically in Python with
interpolated values (temperatures, distances, ...) and handed off as-is
to a notify service or an entity attribute - Home Assistant's frontend
never sees it, so its translation layer can't localize it for us.

This module resolves these messages through the very same
strings.json/translations/*.json files anyway, under a custom "messages"
category, using the same lookup mechanism Home Assistant Core itself uses
for translated exception messages (see
homeassistant.helpers.translation.async_get_exception_message). That way
the source of truth for these texts stays in one place and follows
hass.config.language automatically, exactly like everywhere else in this
integration - defaulting to English, with the German translation applied
automatically whenever Home Assistant's language is set to German.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation

from .const import DOMAIN

MESSAGES_CATEGORY = "messages"


async def async_warm_up(hass: HomeAssistant) -> None:
    """Load this integration's "messages" translations into the cache.

    Must run once (from async_setup_entry(), before the coordinator's
    first refresh can construct a warning) - async_get_cached_translations()
    only reads what's already cached, it doesn't load anything itself.
    """
    await translation.async_get_translations(
        hass, hass.config.language, MESSAGES_CATEGORY, integrations=[DOMAIN]
    )


def render_message(hass: HomeAssistant, key: str, **placeholders: str) -> str:
    """Return the translated, placeholder-filled runtime message for `key`.

    `key` is a dotted path under the "messages" section of
    strings.json/translations/*.json, e.g. "warning.too_hot" or
    "notify.daily_summary". Falls back to `key` itself if translations
    haven't been loaded (see async_warm_up()) or the key doesn't exist.
    """
    localize_key = f"component.{DOMAIN}.{MESSAGES_CATEGORY}.{key}"
    translations = translation.async_get_cached_translations(
        hass, hass.config.language, MESSAGES_CATEGORY, DOMAIN
    )
    message = translations.get(localize_key, key)
    if placeholders:
        message = message.format(**placeholders)
    return message


def format_number(hass: HomeAssistant, value: float, decimals: int) -> str:
    """Format a number the way the active language usually writes it.

    Only English vs. German is distinguished (decimal point vs. comma) -
    this integration only ships those two languages, see translations/.
    """
    formatted = f"{value:.{decimals}f}"
    if hass.config.language == "de":
        formatted = formatted.replace(".", ",")
    return formatted
