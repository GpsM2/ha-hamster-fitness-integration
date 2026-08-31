"""Tests for the Hamster Fitness config flow."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_ILLUMINANCE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)

BASIC_INPUT = {
    CONF_HAMSTER_NAME: "Taco",
    CONF_ACQUISITION_DATE: "2024-01-01",
    CONF_WHEEL_DIAMETER: 28.0,
}

SENSORS_INPUT = {
    CONF_WHEEL_SENSOR: "sensor.wheel_rotations",
    CONF_TEMPERATURE_SENSOR: "sensor.cage_temperature",
    CONF_DOOR_SENSOR: "binary_sensor.cage_door",
}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A full user flow with valid input creates a config entry."""
    hass.states.async_set("sensor.wheel_rotations", "42")
    hass.states.async_set("sensor.cage_temperature", "22")
    hass.states.async_set("binary_sensor.cage_door", "off")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SENSORS_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Taco"
    assert result["data"][CONF_HAMSTER_NAME] == "Taco"
    assert result["data"][CONF_WHEEL_SENSOR] == "sensor.wheel_rotations"


async def test_user_flow_creates_entry_without_a_door_sensor(
    hass: HomeAssistant,
) -> None:
    """CONF_DOOR_SENSOR is optional (#143) - omitting it still creates an
    entry, and it simply isn't in the stored data."""
    hass.states.async_set("sensor.wheel_rotations", "42")
    hass.states.async_set("sensor.cage_temperature", "22")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    sensors_input = {
        k: v for k, v in SENSORS_INPUT.items() if k != CONF_DOOR_SENSOR
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], sensors_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_DOOR_SENSOR not in result["data"]


async def test_user_flow_stores_an_optional_illuminance_sensor(
    hass: HomeAssistant,
) -> None:
    """Picking an ambient light sensor stores it; the base flow above
    already covers leaving it out entirely, since none of the existing
    fixtures set it."""
    hass.states.async_set("sensor.wheel_rotations", "42")
    hass.states.async_set("sensor.cage_temperature", "22")
    hass.states.async_set("binary_sensor.cage_door", "off")
    hass.states.async_set("sensor.room_illuminance", "5")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**SENSORS_INPUT, CONF_ILLUMINANCE_SENSOR: "sensor.room_illuminance"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ILLUMINANCE_SENSOR] == "sensor.room_illuminance"


async def test_user_flow_rejects_blank_name(hass: HomeAssistant) -> None:
    """A whitespace-only hamster name is rejected with invalid_name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**BASIC_INPUT, CONF_HAMSTER_NAME: "   "}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HAMSTER_NAME: "invalid_name"}


async def test_user_flow_rejects_zero_diameter(hass: HomeAssistant) -> None:
    """A wheel diameter of 0 never makes it past the schema.

    The step's own `invalid_diameter` check is a belt-and-braces fallback
    that can't actually be reached through the UI: the field is a
    NumberSelector with min=MIN_WHEEL_DIAMETER_CM, so voluptuous rejects
    anything smaller first. This test pins down where the rejection
    really happens, rather than asserting an error string the user will
    never see.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**BASIC_INPUT, CONF_WHEEL_DIAMETER: 0}
        )


async def test_sensors_step_rejects_non_numeric_wheel_sensor(
    hass: HomeAssistant,
) -> None:
    """A wheel_sensor whose state isn't a number is rejected with not_numeric."""
    hass.states.async_set("sensor.wheel_rotations", "not-a-number")
    hass.states.async_set("sensor.cage_temperature", "22")
    hass.states.async_set("binary_sensor.cage_door", "off")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SENSORS_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"
    assert result["errors"] == {CONF_WHEEL_SENSOR: "not_numeric"}


async def test_duplicate_name_aborts(hass: HomeAssistant) -> None:
    """Setting up a second hamster with the same name aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={**BASIC_INPUT, **SENSORS_INPUT},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_updates_entry(hass: HomeAssistant) -> None:
    """Reconfigure updates the entry's data without changing its unique_id."""
    hass.states.async_set("sensor.wheel_rotations", "42")
    hass.states.async_set("sensor.cage_temperature", "22")
    hass.states.async_set("binary_sensor.cage_door", "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={**BASIC_INPUT, **SENSORS_INPUT},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**BASIC_INPUT, CONF_WHEEL_DIAMETER: 30.0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SENSORS_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_WHEEL_DIAMETER] == 30.0
    assert entry.unique_id == "taco"


async def test_reconfigure_flow_without_a_door_sensor(hass: HomeAssistant) -> None:
    """Reconfigure also succeeds when the door sensor is left out (#143)."""
    hass.states.async_set("sensor.wheel_rotations", "42")
    hass.states.async_set("sensor.cage_temperature", "22")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={**BASIC_INPUT, **SENSORS_INPUT},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], BASIC_INPUT
    )
    assert result["step_id"] == "reconfigure_sensors"

    sensors_input = {
        k: v for k, v in SENSORS_INPUT.items() if k != CONF_DOOR_SENSOR
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], sensors_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
