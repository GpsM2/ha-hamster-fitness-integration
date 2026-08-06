"""Tests for the hamster profile (breed and coat colour)."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    BREED_OTHER,
    BREED_ROBOROVSKI,
    COAT_COLOR_HEX,
    COAT_COLOR_SILVER_GREY,
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_BREED_OTHER,
    CONF_COAT_COLOR,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DEFAULT_BREED,
    DEFAULT_COAT_COLOR,
    DOMAIN,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"

BASIC_INPUT = {
    CONF_HAMSTER_NAME: "Taco",
    CONF_ACQUISITION_DATE: "2024-01-01",
    CONF_BREED: BREED_ROBOROVSKI,
    CONF_COAT_COLOR: COAT_COLOR_SILVER_GREY,
    CONF_WHEEL_DIAMETER: 28.0,
}

SENSORS_INPUT = {
    CONF_WHEEL_SENSOR: WHEEL_SENSOR,
    CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
    CONF_DOOR_SENSOR: DOOR_SENSOR,
}

HEALTH_SCORE = "sensor.hamster_taco_health_score"


def _seed_states(hass: HomeAssistant) -> None:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")


async def test_profile_is_stored_and_exposed(hass: HomeAssistant) -> None:
    """Breed and coat colour survive the flow and reach the cards."""
    _seed_states(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SENSORS_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BREED] == BREED_ROBOROVSKI

    await hass.async_block_till_done()

    attrs = hass.states.get(HEALTH_SCORE).attributes
    assert attrs["breed"] == BREED_ROBOROVSKI
    assert attrs["breed_other"] is None
    assert attrs["coat_color"] == COAT_COLOR_SILVER_GREY
    assert attrs["coat_color_hex"] == COAT_COLOR_HEX[COAT_COLOR_SILVER_GREY]
    assert attrs["acquisition_date"] == "2024-01-01"


async def test_other_breed_requires_a_name(hass: HomeAssistant) -> None:
    """Picking "Other" without filling in the free-text field is rejected."""
    _seed_states(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**BASIC_INPUT, CONF_BREED: BREED_OTHER, CONF_BREED_OTHER: "   "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BREED_OTHER: "breed_required"}


async def test_other_breed_is_carried_through(hass: HomeAssistant) -> None:
    """A named "Other" breed shows up on the health-score sensor."""
    _seed_states(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**BASIC_INPUT, CONF_BREED: BREED_OTHER, CONF_BREED_OTHER: "Mischling"},
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], SENSORS_INPUT)
    await hass.async_block_till_done()

    attrs = hass.states.get(HEALTH_SCORE).attributes
    assert attrs["breed"] == BREED_OTHER
    assert attrs["breed_other"] == "Mischling"


async def test_entries_from_before_the_profile_existed_still_work(
    hass: HomeAssistant,
) -> None:
    """Pre-0.3.0 entries have no breed/colour keys and must not break.

    Nothing migrates them - a Reconfigure is what adds the fields - so
    every read has to fall back to the defaults.
    """
    _seed_states(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            **SENSORS_INPUT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    attrs = hass.states.get(HEALTH_SCORE).attributes
    assert attrs["breed"] == DEFAULT_BREED
    assert attrs["coat_color"] == DEFAULT_COAT_COLOR
    assert attrs["coat_color_hex"] == COAT_COLOR_HEX[DEFAULT_COAT_COLOR]
