"""Tests for adding a purely historical hamster with no config entry.

Covers both layers: the storage helper directly (archive.py), and the
`hamster_fitness/add_historical_hamster` WebSocket command the chronicle
card's "add a past hamster" dialog calls.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hamster_fitness import archive
from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"


async def _setup_any_entry(hass: HomeAssistant) -> None:
    """Get the domain (and its WebSocket commands) registered.

    The command is registered domain-wide in `async_setup`, which a bare
    `hass` fixture never triggers on its own - it needs at least one
    config entry to be set up first.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_BREED: "golden",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


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


# --- The WebSocket command -----------------------------------------------


async def test_ws_add_historical_hamster(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """A complete, valid submission is stored and echoed back."""
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "Pepper",
            "breed": "chinese",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    assert response["success"], response
    names = [h["name"] for h in response["result"]["hamsters"]]
    assert "Pepper" in names


async def test_ws_add_historical_hamster_has_no_activity_data(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """No distance/speed/score - never tracked, so nothing to report.

    Zeros would misrepresent a hamster that simply was never measured as
    one that never moved. The chronicle card already renders a missing
    stat as "-", so omitting the fields is enough.
    """
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "Pepper",
            "breed": "chinese",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    record = next(
        h for h in response["result"]["hamsters"] if h["name"] == "Pepper"
    )
    assert "lifetime_distance_km" not in record
    assert "lifetime_max_speed_kmh" not in record
    assert "final_health_score" not in record


async def test_ws_add_historical_hamster_requires_a_name(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """A blank (or whitespace-only) name is rejected, not silently stored."""
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "   ",
            "breed": "chinese",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert await archive.async_load(hass) == []


async def test_ws_add_historical_hamster_other_breed_needs_a_description(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Breed "other" with nothing to say what it actually is gets rejected."""
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "Pepper",
            "breed": "other",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert await archive.async_load(hass) == []


async def test_ws_add_historical_hamster_other_breed_with_description(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """The same submission succeeds once breed_other is filled in."""
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "Pepper",
            "breed": "other",
            "breed_other": "Mischling",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    assert response["success"], response
    record = next(
        h for h in response["result"]["hamsters"] if h["name"] == "Pepper"
    )
    assert record["breed_other"] == "Mischling"


async def test_ws_add_historical_hamster_rejects_unknown_breed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """A breed outside the known list is a client bug, not free text."""
    await _setup_any_entry(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/add_historical_hamster",
            "name": "Pepper",
            "breed": "dragon",
            "coat_color": "black",
            "acquisition_date": "2019-02-11",
            "departure_date": "2021-05-30",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
