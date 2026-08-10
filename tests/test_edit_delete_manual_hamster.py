"""Tests for editing and deleting a purely historical hamster.

Mirrors test_add_historical_hamster.py's approach (see that file's module
docstring for why the WS layer is exercised without a real network
connection): schema validation via `_ws_schema`, handler logic via
`.__wrapped__`.

The one invariant worth testing hard here: a manually-added entry (keyed
"manual_<uuid>") is editable/deletable through these commands, but a real
hamster's departure record (keyed by its config entry_id) must not be -
that record belongs to its coordinator, not to this dialog.
"""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant

from custom_components.hamster_fitness import (
    _ws_remove_historical_hamster,
    _ws_update_historical_hamster,
    archive,
)
from custom_components.hamster_fitness.const import DOMAIN

UPDATE_TYPE = f"{DOMAIN}/update_historical_hamster"
REMOVE_TYPE = f"{DOMAIN}/remove_historical_hamster"


class _FakeConnection:
    """Records what the handler would have sent over the wire."""

    def __init__(self) -> None:
        self.result: dict[str, Any] | None = None
        self.error: tuple[str, str] | None = None

    def send_result(self, msg_id: int, data: dict[str, Any]) -> None:
        self.result = data

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.error = (code, message)


async def _add_manual(hass: HomeAssistant, **overrides: Any) -> str:
    """Add a manual entry directly through the storage layer, return its id."""
    record = {
        "name": "Mochi",
        "breed": "roborovski",
        "breed_other": None,
        "coat_color": "cream_sand",
        "coat_color_hex": "#E8D3A7",
        "acquisition_date": "2018-05-01",
        "departure_date": "2020-09-12",
        "archived_at": "2026-08-09T12:00:00+00:00",
    }
    record.update(overrides)
    await archive.async_add_manual_entry(hass, record)
    (entry,) = await archive.async_load(hass)
    return str(entry["id"])


def _validate_update(msg: dict[str, Any]) -> dict[str, Any]:
    schema: vol.Schema = _ws_update_historical_hamster._ws_schema
    return schema(msg)


def _validate_remove(msg: dict[str, Any]) -> dict[str, Any]:
    schema: vol.Schema = _ws_remove_historical_hamster._ws_schema
    return schema(msg)


async def _call_update(hass: HomeAssistant, msg: dict[str, Any]) -> _FakeConnection:
    validated = _validate_update(msg)
    connection = _FakeConnection()
    await _ws_update_historical_hamster.__wrapped__(hass, connection, validated)
    return connection


async def _call_remove(hass: HomeAssistant, msg: dict[str, Any]) -> _FakeConnection:
    validated = _validate_remove(msg)
    connection = _FakeConnection()
    await _ws_remove_historical_hamster.__wrapped__(hass, connection, validated)
    return connection


def _update_msg(entry_id: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "id": 1,
        "type": UPDATE_TYPE,
        "entry_id": entry_id,
        "name": "Mochi",
        "breed": "roborovski",
        "coat_color": "cream_sand",
        "acquisition_date": "2018-05-01",
        "departure_date": "2020-09-12",
    }
    base.update(overrides)
    return base


# --- archive.py storage layer ---------------------------------------------


async def test_async_load_exposes_the_storage_key_as_id(hass: HomeAssistant) -> None:
    entry_id = await _add_manual(hass)
    assert entry_id.startswith("manual_")


async def test_update_manual_entry_overwrites_in_place(hass: HomeAssistant) -> None:
    entry_id = await _add_manual(hass)

    ok = await archive.async_update_manual_entry(
        hass,
        entry_id,
        {
            "name": "Mochi II",
            "breed": "roborovski",
            "breed_other": None,
            "coat_color": "cream_sand",
            "coat_color_hex": "#E8D3A7",
            "acquisition_date": "2018-05-01",
            "departure_date": "2020-09-12",
            "archived_at": "2026-08-09T12:00:00+00:00",
        },
    )

    assert ok is True
    hamsters = await archive.async_load(hass)
    assert len(hamsters) == 1
    assert hamsters[0]["name"] == "Mochi II"
    assert hamsters[0]["id"] == entry_id


async def test_update_manual_entry_rejects_a_real_hamsters_id(
    hass: HomeAssistant,
) -> None:
    """The prefix check is the actual safety boundary, not just the WS schema."""
    await archive.async_record_departure(
        hass, "real_entry_id", {"name": "Taco", "departure_date": "2025-01-01"}
    )

    ok = await archive.async_update_manual_entry(
        hass, "real_entry_id", {"name": "Hijacked"}
    )

    assert ok is False
    hamsters = await archive.async_load(hass)
    assert hamsters[0]["name"] == "Taco"


async def test_update_manual_entry_rejects_an_unknown_id(hass: HomeAssistant) -> None:
    ok = await archive.async_update_manual_entry(
        hass, "manual_does_not_exist", {"name": "Ghost"}
    )
    assert ok is False


async def test_remove_manual_entry_deletes_it(hass: HomeAssistant) -> None:
    entry_id = await _add_manual(hass)

    ok = await archive.async_remove_manual_entry(hass, entry_id)

    assert ok is True
    assert await archive.async_load(hass) == []


async def test_remove_manual_entry_rejects_a_real_hamsters_id(
    hass: HomeAssistant,
) -> None:
    await archive.async_record_departure(
        hass, "real_entry_id", {"name": "Taco", "departure_date": "2025-01-01"}
    )

    ok = await archive.async_remove_manual_entry(hass, "real_entry_id")

    assert ok is False
    assert len(await archive.async_load(hass)) == 1


# --- The WebSocket commands' schemas ---------------------------------------


def test_update_ws_schema_requires_entry_id() -> None:
    msg = _update_msg("manual_abc")
    del msg["entry_id"]
    with pytest.raises(vol.Invalid):
        _validate_update(msg)


def test_update_ws_schema_rejects_an_unknown_breed() -> None:
    with pytest.raises(vol.Invalid):
        _validate_update(_update_msg("manual_abc", breed="dragon"))


def test_remove_ws_schema_requires_entry_id() -> None:
    with pytest.raises(vol.Invalid):
        _validate_remove({"id": 1, "type": REMOVE_TYPE})


# --- The WebSocket commands' handlers ---------------------------------------


async def test_ws_update_historical_hamster(hass: HomeAssistant) -> None:
    entry_id = await _add_manual(hass)

    connection = await _call_update(hass, _update_msg(entry_id, name="Renamed"))

    assert connection.error is None
    names = [h["name"] for h in connection.result["hamsters"]]
    assert "Renamed" in names


async def test_ws_update_historical_hamster_requires_a_name(
    hass: HomeAssistant,
) -> None:
    entry_id = await _add_manual(hass)

    connection = await _call_update(hass, _update_msg(entry_id, name="   "))

    assert connection.error is not None
    hamsters = await archive.async_load(hass)
    assert hamsters[0]["name"] == "Mochi"


async def test_ws_update_historical_hamster_unknown_id_errors(
    hass: HomeAssistant,
) -> None:
    connection = await _call_update(hass, _update_msg("manual_does_not_exist"))

    assert connection.error is not None
    assert connection.error[0] == "not_found"


async def test_ws_update_historical_hamster_cannot_touch_a_real_entry(
    hass: HomeAssistant,
) -> None:
    """End-to-end proof the WS command can't be used to rewrite a real hamster."""
    await archive.async_record_departure(
        hass, "real_entry_id", {"name": "Taco", "departure_date": "2025-01-01"}
    )

    connection = await _call_update(hass, _update_msg("real_entry_id", name="Hijacked"))

    assert connection.error is not None
    hamsters = await archive.async_load(hass)
    assert hamsters[0]["name"] == "Taco"


async def test_ws_remove_historical_hamster(hass: HomeAssistant) -> None:
    entry_id = await _add_manual(hass)

    connection = await _call_remove(hass, {"id": 1, "type": REMOVE_TYPE, "entry_id": entry_id})

    assert connection.error is None
    assert connection.result["hamsters"] == []


async def test_ws_remove_historical_hamster_unknown_id_errors(
    hass: HomeAssistant,
) -> None:
    connection = await _call_remove(
        hass, {"id": 1, "type": REMOVE_TYPE, "entry_id": "manual_does_not_exist"}
    )

    assert connection.error is not None
    assert connection.error[0] == "not_found"


async def test_ws_remove_historical_hamster_cannot_touch_a_real_entry(
    hass: HomeAssistant,
) -> None:
    await archive.async_record_departure(
        hass, "real_entry_id", {"name": "Taco", "departure_date": "2025-01-01"}
    )

    connection = await _call_remove(
        hass, {"id": 1, "type": REMOVE_TYPE, "entry_id": "real_entry_id"}
    )

    assert connection.error is not None
    assert len(await archive.async_load(hass)) == 1
