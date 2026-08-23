"""The rotation counter field must reject entities that cannot be counters.

Background: on 2026-08-21 a second hamster was set up with the wheel's
*speed* sensor selected as the rotation counter. Nothing complained, and
three days of phantom zeros followed - a speed reading drops to 0 when
the hamster stops, and a counter that drops reads as a device reset, so
the window baseline was discarded every few seconds.

The picker cannot prevent this on its own: there is no device class for
"counts rotations", and `state_class` - the attribute that actually tells
them apart - is not something the entity selector can filter on. So it is
checked after selection. See issue #141.
"""

from __future__ import annotations

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_BREED,
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

ROTATIONS = "sensor.wheel_total_rotations"
SPEED = "sensor.wheel_speed"
DISTANCE = "sensor.wheel_total_distance"
TEMPERATURE = "sensor.cage_temperature"
DOOR = "binary_sensor.cage_door"


def _seed(hass: HomeAssistant) -> None:
    """Recreate the three candidates exactly as the real firmware exposes them."""
    hass.states.async_set(
        ROTATIONS, "218", {ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING}
    )
    hass.states.async_set(
        SPEED,
        "0.0",
        {ATTR_DEVICE_CLASS: "speed", ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT},
    )
    hass.states.async_set(
        DISTANCE,
        "0.143",
        {
            ATTR_DEVICE_CLASS: "distance",
            ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING,
        },
    )
    hass.states.async_set(TEMPERATURE, "22")
    hass.states.async_set(DOOR, "off")


async def _to_sensors_step(hass: HomeAssistant) -> str:
    """Walk the config flow to the source-entity step and return its flow id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HAMSTER_NAME: "Fips",
            CONF_ACQUISITION_DATE: "2026-08-21",
            CONF_BREED: DEFAULT_BREED,
            CONF_COAT_COLOR: DEFAULT_COAT_COLOR,
            CONF_WHEEL_DIAMETER: 21.0,
        },
    )
    assert result["step_id"] == "sensors"
    return result["flow_id"]


async def _submit(hass: HomeAssistant, flow_id: str, wheel: str) -> dict:
    return await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_WHEEL_SENSOR: wheel,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE,
            CONF_DOOR_SENSOR: DOOR,
        },
    )


async def test_speed_sensor_is_rejected(hass: HomeAssistant) -> None:
    """The exact mistake that was made in production."""
    _seed(hass)
    flow_id = await _to_sensors_step(hass)

    result = await _submit(hass, flow_id, SPEED)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_WHEEL_SENSOR: "not_a_counter"}


async def test_distance_sensor_is_rejected(hass: HomeAssistant) -> None:
    """The other plausible mistake: kilometres, not rotations.

    It even carries `total_increasing`, so only the device class gives it
    away. Accepting it would multiply a distance by the wheel
    circumference a second time.
    """
    _seed(hass)
    flow_id = await _to_sensors_step(hass)

    result = await _submit(hass, flow_id, DISTANCE)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_WHEEL_SENSOR: "not_a_counter"}


async def test_rotation_counter_is_accepted(hass: HomeAssistant) -> None:
    """The real counter must still go through."""
    _seed(hass)
    flow_id = await _to_sensors_step(hass)

    result = await _submit(hass, flow_id, ROTATIONS)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_WHEEL_SENSOR] == ROTATIONS


async def test_counter_without_state_class_is_accepted(hass: HomeAssistant) -> None:
    """A hand-written template counter may legitimately set no state_class.

    Rejecting those would be stricter than the problem warrants - the
    check is there to catch entities that are provably something else,
    not to demand a particular authoring style.
    """
    _seed(hass)
    hass.states.async_set("sensor.homemade_counter", "500")
    flow_id = await _to_sensors_step(hass)

    result = await _submit(hass, flow_id, "sensor.homemade_counter")

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_unavailable_entity_is_still_accepted(hass: HomeAssistant) -> None:
    """An entity that is merely offline right now must not block setup.

    Matches the existing behaviour of the numeric check next to it: the
    coordinator re-validates on every update once running.
    """
    _seed(hass)
    hass.states.async_set("sensor.offline_counter", "unavailable")
    flow_id = await _to_sensors_step(hass)

    result = await _submit(hass, flow_id, "sensor.offline_counter")

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_reconfigure_rejects_it_too(hass: HomeAssistant) -> None:
    """The same guard has to hold on the Reconfigure path."""
    _seed(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="fips",
        title="Fips",
        data={
            CONF_HAMSTER_NAME: "Fips",
            CONF_ACQUISITION_DATE: "2026-08-21",
            CONF_WHEEL_DIAMETER: 21.0,
            CONF_WHEEL_SENSOR: ROTATIONS,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE,
            CONF_DOOR_SENSOR: DOOR,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HAMSTER_NAME: "Fips",
            CONF_ACQUISITION_DATE: "2026-08-21",
            CONF_BREED: DEFAULT_BREED,
            CONF_COAT_COLOR: DEFAULT_COAT_COLOR,
            CONF_WHEEL_DIAMETER: 21.0,
        },
    )
    assert result["step_id"] == "reconfigure_sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_WHEEL_SENSOR: SPEED,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE,
            CONF_DOOR_SENSOR: DOOR,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_WHEEL_SENSOR: "not_a_counter"}
