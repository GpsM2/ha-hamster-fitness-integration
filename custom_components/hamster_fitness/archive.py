"""Lifetime history archive for departed hamsters.

Every other piece of storage in this integration is scoped to one config
entry (`hamster_fitness_<entry_id>_baseline` and friends) and disappears
with it. This one deliberately is not: the whole point of the archive is
to outlive the entry, so a hamster that has passed away or moved out
still shows up in the chronicle years later - even once its config entry,
device and entities are long gone.

Written once, when a departure date takes effect (see
`HamsterFitnessCoordinator.async_set_departure_date`). Re-archiving the
same entry overwrites its record rather than adding a second one, so
correcting a mistyped departure date stays harmless.

Read back by the chronicle card through the `hamster_fitness/history`
WebSocket command registered in `__init__.py` - a card can only see
entity states otherwise, and archived hamsters no longer have any.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

# Landet unter config/.storage/ - dieselbe Mechanik wie bei den
# entry-bezogenen Stores, nur ohne entry_id im Schlüssel, damit sich alle
# Hamster dieselbe Datei teilen.
STORAGE_KEY = f"{DOMAIN}_history_lifedata"

DATA_ARCHIVE_STORE = f"{DOMAIN}_archive_store"


def _store(hass: HomeAssistant) -> Store[dict[str, Any]]:
    """Return the shared archive store, creating it once per Home Assistant.

    Cached in `hass.data`: two Store instances pointing at the same file
    would each keep their own delayed-write buffer and could overwrite
    one another when two hamsters depart around the same time.
    """
    store: Store[dict[str, Any]] | None = hass.data.get(DATA_ARCHIVE_STORE)
    if store is None:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        hass.data[DATA_ARCHIVE_STORE] = store
    return store


async def async_load(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return every archived hamster, most recently departed first.

    Each record carries its storage key as `id` - the chronicle card needs
    it to tell a manually-added entry (editable/deletable through the
    card) apart from a real hamster's departure record (managed by its
    coordinator instead), and to target the right record when it does.
    """
    stored = await _store(hass).async_load() or {}
    hamsters: list[dict[str, Any]] = [
        {**record, "id": key} for key, record in stored.get("hamsters", {}).items()
    ]
    hamsters.sort(key=lambda item: item.get("departure_date") or "", reverse=True)
    return hamsters


async def async_remove_departure(hass: HomeAssistant, entry_id: str) -> None:
    """Retract one hamster's archive record.

    The counterpart to `async_record_departure`, for undoing a departure
    that was set by mistake. A hamster that is back among the living has
    no business in the chronicle's archived half - and leaving the record
    behind would make it appear twice once the live entry reappears.
    """
    store = _store(hass)
    stored = await store.async_load() or {}
    hamsters: dict[str, Any] = stored.get("hamsters", {})
    if hamsters.pop(entry_id, None) is None:
        return
    await store.async_save({"hamsters": hamsters})
    _LOGGER.debug(
        "Hamster Fitness: Archiv-Eintrag für %s zurückgenommen", entry_id
    )


async def async_record_departure(
    hass: HomeAssistant, entry_id: str, record: dict[str, Any]
) -> None:
    """Add (or refresh) one hamster's final record in the archive.

    Takes a plain dict rather than the coordinator's dataclass on
    purpose - it keeps this module free of any import back into
    coordinator.py, which imports this one.
    """
    store = _store(hass)
    stored = await store.async_load() or {}
    hamsters: dict[str, Any] = stored.get("hamsters", {})
    hamsters[entry_id] = record
    await store.async_save({"hamsters": hamsters})
    _LOGGER.debug(
        "Hamster Fitness: %s ins Lebenslauf-Archiv übernommen", record.get("name")
    )


async def async_add_manual_entry(hass: HomeAssistant, record: dict[str, Any]) -> None:
    """Add a purely historical hamster that never had a config entry.

    Same store, same record shape as `async_record_departure` - the
    chronicle card can't tell the two apart, which is the point: a
    hamster from before this integration existed belongs in the same
    list as one it tracked itself. Keyed by a random id rather than an
    entry_id, since there is no config entry behind it to key on.
    """
    key = f"manual_{uuid.uuid4().hex}"
    store = _store(hass)
    stored = await store.async_load() or {}
    hamsters: dict[str, Any] = stored.get("hamsters", {})
    hamsters[key] = record
    await store.async_save({"hamsters": hamsters})
    _LOGGER.debug(
        "Hamster Fitness: %s manuell ins Lebenslauf-Archiv eingetragen",
        record.get("name"),
    )


def _is_manual_entry_id(entry_id: str) -> bool:
    """Whether `entry_id` names a manually-added entry, not a real hamster's.

    Both `async_update_manual_entry` and `async_remove_manual_entry` check
    this before touching the store - the chronicle card only ever offers
    editing/deleting for entries it created itself, but the WebSocket
    commands behind that UI are the actual safety boundary: a real
    hamster's departure record must stay under its coordinator's control.
    """
    return entry_id.startswith("manual_")


async def async_update_manual_entry(
    hass: HomeAssistant, entry_id: str, record: dict[str, Any]
) -> bool:
    """Overwrite a manually-added entry in place. Returns whether it existed."""
    if not _is_manual_entry_id(entry_id):
        return False
    store = _store(hass)
    stored = await store.async_load() or {}
    hamsters: dict[str, Any] = stored.get("hamsters", {})
    if entry_id not in hamsters:
        return False
    hamsters[entry_id] = record
    await store.async_save({"hamsters": hamsters})
    _LOGGER.debug(
        "Hamster Fitness: manueller Archiv-Eintrag %s aktualisiert", entry_id
    )
    return True


async def async_remove_manual_entry(hass: HomeAssistant, entry_id: str) -> bool:
    """Delete a manually-added entry. Returns whether it existed."""
    if not _is_manual_entry_id(entry_id):
        return False
    store = _store(hass)
    stored = await store.async_load() or {}
    hamsters: dict[str, Any] = stored.get("hamsters", {})
    if hamsters.pop(entry_id, None) is None:
        return False
    await store.async_save({"hamsters": hamsters})
    _LOGGER.debug("Hamster Fitness: manueller Archiv-Eintrag %s gelöscht", entry_id)
    return True
