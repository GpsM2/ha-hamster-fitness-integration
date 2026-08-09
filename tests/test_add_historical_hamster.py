"""Tests for adding a purely historical hamster with no config entry.

Covers both layers: the storage helper directly (archive.py), and the
`hamster_fitness/add_historical_hamster` WebSocket command the chronicle
card's "add a past hamster" dialog calls.

The WS layer is exercised without a real network connection. A real one
(pytest-homeassistant-custom-component's `hass_ws_client`) turned out to
be unusable in CI: aiohttp's DefaultResolver is AsyncResolver (backed by
aiodns) whenever aiodns is importable, and ThreadedResolver otherwise:
- AsyncResolver requires a SelectorEventLoop, which Windows has not
  defaulted to since Python 3.8 - every real aiohttp connection crashed
  locally before reaching any of this integration's own code.
- ThreadedResolver keeps a worker thread alive past the connection,
  which pytest-homeassistant-custom-component's strict thread-leak
  check does not tolerate - the very first CI run of this file failed
  there instead, on a completely clean Ubuntu runner.

Testing the command directly sidesteps both: run the message through its
real voluptuous schema (`_ws_schema`, same validation a real WS message
gets) to prove the schema itself rejects bad input, then call the
handler's own coroutine directly (`.__wrapped__`, bypassing only the
background-task scheduling `@websocket_api.async_response` adds for the
live server's benefit) to prove its business logic. No socket, no
thread, no event-loop requirement - and arguably a more precise test,
since a schema rejection and a handler-level rejection are genuinely
different things that a full round-trip WS test would have blurred
together into one "success: false".
"""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant

from custom_components.hamster_fitness import _ws_add_historical_hamster, archive
from custom_components.hamster_fitness.const import DOMAIN

COMMAND_TYPE = f"{DOMAIN}/add_historical_hamster"


class _FakeConnection:
    """Records what the handler would have sent over the wire."""

    def __init__(self) -> None:
        self.result: dict[str, Any] | None = None
        self.error: tuple[str, str] | None = None

    def send_result(self, msg_id: int, data: dict[str, Any]) -> None:
        self.result = data

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.error = (code, message)


def _validate(msg: dict[str, Any]) -> dict[str, Any]:
    """Run `msg` through the command's real schema, like the WS router would."""
    schema: vol.Schema = _ws_add_historical_hamster._ws_schema
    return schema(msg)


async def _call(hass: HomeAssistant, msg: dict[str, Any]) -> _FakeConnection:
    """Validate `msg`, then run the handler inline, and return what it sent."""
    validated = _validate(msg)
    connection = _FakeConnection()
    await _ws_add_historical_hamster.__wrapped__(hass, connection, validated)
    return connection


def _msg(**overrides: Any) -> dict[str, Any]:
    # "id" is the WS protocol's own message-id envelope field, normally
    # added by the connection layer before a handler's schema ever runs -
    # BASE_COMMAND_MESSAGE_SCHEMA (which every command schema extends)
    # requires it too, so a realistic message needs one even here.
    base = {
        "id": 1,
        "type": COMMAND_TYPE,
        "name": "Pepper",
        "breed": "chinese",
        "coat_color": "black",
        "acquisition_date": "2019-02-11",
        "departure_date": "2021-05-30",
    }
    base.update(overrides)
    return base


# --- archive.async_add_manual_entry -------------------------------------


async def test_manual_entry_appears_in_the_archive(hass: HomeAssistant) -> None:
    """The storage layer alone: a manual record shows up on load."""
    await archive.async_add_manual_entry(
        hass,
        {
            "name": "Mochi",
            "breed": "roborovski",
            "breed_other": None,
            "coat_color": "cream_sand",
            "coat_color_hex": "#E8D3A7",
            "acquisition_date": "2018-05-01",
            "departure_date": "2020-09-12",
            "archived_at": "2026-08-09T12:00:00+00:00",
        },
    )

    hamsters = await archive.async_load(hass)
    assert len(hamsters) == 1
    assert hamsters[0]["name"] == "Mochi"


async def test_manual_entries_get_distinct_keys(hass: HomeAssistant) -> None:
    """Two hamsters of the same name must not overwrite one another.

    Live departures are keyed by entry_id, which is naturally unique.
    Manual entries have no entry_id to key on, so this is what stops a
    second "Mochi" from clobbering the first.
    """
    for _ in range(2):
        await archive.async_add_manual_entry(
            hass,
            {
                "name": "Mochi",
                "breed": "roborovski",
                "breed_other": None,
                "coat_color": "cream_sand",
                "coat_color_hex": "#E8D3A7",
                "acquisition_date": "2018-05-01",
                "departure_date": "2020-09-12",
                "archived_at": "2026-08-09T12:00:00+00:00",
            },
        )

    hamsters = await archive.async_load(hass)
    assert len(hamsters) == 2


# --- The WebSocket command's schema --------------------------------------


def test_ws_schema_rejects_an_unknown_breed() -> None:
    """A breed outside the known list is a client bug, not free text."""
    with pytest.raises(vol.Invalid):
        _validate(_msg(breed="dragon"))


def test_ws_schema_rejects_an_unknown_coat_color() -> None:
    with pytest.raises(vol.Invalid):
        _validate(_msg(coat_color="rainbow"))


def test_ws_schema_rejects_an_unparsable_date() -> None:
    with pytest.raises(vol.Invalid):
        _validate(_msg(acquisition_date="not a date"))


def test_ws_schema_converts_dates() -> None:
    """cv.date turns the wire's ISO strings into real date objects."""
    from datetime import date

    validated = _validate(_msg())
    assert validated["acquisition_date"] == date(2019, 2, 11)
    assert validated["departure_date"] == date(2021, 5, 30)


# --- The WebSocket command's handler --------------------------------------


async def test_ws_add_historical_hamster(hass: HomeAssistant) -> None:
    """A complete, valid submission is stored and echoed back."""
    connection = await _call(hass, _msg())

    assert connection.error is None
    names = [h["name"] for h in connection.result["hamsters"]]
    assert "Pepper" in names


async def test_ws_add_historical_hamster_has_no_activity_data(
    hass: HomeAssistant,
) -> None:
    """No distance/speed/score - never tracked, so nothing to report.

    Zeros would misrepresent a hamster that simply was never measured as
    one that never moved. The chronicle card already renders a missing
    stat as "-", so omitting the fields is enough.
    """
    connection = await _call(hass, _msg())

    record = next(h for h in connection.result["hamsters"] if h["name"] == "Pepper")
    assert "lifetime_distance_km" not in record
    assert "lifetime_max_speed_kmh" not in record
    assert "final_health_score" not in record


async def test_ws_add_historical_hamster_requires_a_name(hass: HomeAssistant) -> None:
    """A blank (or whitespace-only) name is rejected, not silently stored.

    The schema only demands a string, not a non-blank one - this is the
    handler's own check, not vol.In or similar.
    """
    connection = await _call(hass, _msg(name="   "))

    assert connection.error is not None
    assert connection.result is None
    assert await archive.async_load(hass) == []


async def test_ws_add_historical_hamster_other_breed_needs_a_description(
    hass: HomeAssistant,
) -> None:
    """Breed "other" with nothing to say what it actually is gets rejected."""
    connection = await _call(hass, _msg(breed="other"))

    assert connection.error is not None
    assert await archive.async_load(hass) == []


async def test_ws_add_historical_hamster_other_breed_with_description(
    hass: HomeAssistant,
) -> None:
    """The same submission succeeds once breed_other is filled in."""
    connection = await _call(
        hass, _msg(breed="other", breed_other="Mischling")
    )

    assert connection.error is None
    record = next(h for h in connection.result["hamsters"] if h["name"] == "Pepper")
    assert record["breed_other"] == "Mischling"
