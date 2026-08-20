"""The integration is the authority for the wheel diameter.

Background: re-flashing the wheel sensor resets its diameter number
entity to the firmware default, and the device is unavailable while it
happens. The old one-shot push at setup therefore landed on nothing and
never tried again - the configured 29 cm silently stayed 28 cm on the
live instance from 2026-08-19 onwards. See issue #138.

Note on the mocking: `number.set_value` has to be mocked *after* the
config entry is set up. Setting the entry up brings up the `number`
platform for the weight entity, which registers the real service and
would replace a mock installed earlier.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_DIAMETER_SYNC_ENTITY,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
SYNC_ENTITY = "number.wheel_diameter_on_device"
DIAMETER = 29.0


async def _setup(hass: HomeAssistant, *, with_sync: bool = True) -> MockConfigEntry:
    data = {
        CONF_HAMSTER_NAME: "Taco",
        CONF_ACQUISITION_DATE: "2024-01-01",
        CONF_WHEEL_DIAMETER: DIAMETER,
        CONF_WHEEL_SENSOR: WHEEL_SENSOR,
        CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
        CONF_DOOR_SENSOR: DOOR_SENSOR,
    }
    if with_sync:
        data[CONF_WHEEL_DIAMETER_SYNC_ENTITY] = SYNC_ENTITY

    entry = MockConfigEntry(domain=DOMAIN, unique_id="taco", title="Taco", data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _seed(hass: HomeAssistant) -> None:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")


async def test_pushes_once_the_target_shows_up(hass: HomeAssistant) -> None:
    """Unavailable at setup must not mean "give up until the next restart".

    This is the re-flash case: the device is offline exactly when the
    setup-time push happens, and comes back carrying the firmware
    default.
    """
    _seed(hass)
    hass.states.async_set(SYNC_ENTITY, "unavailable")

    await _setup(hass)
    calls: list[ServiceCall] = async_mock_service(hass, "number", "set_value")

    hass.states.async_set(SYNC_ENTITY, "28.0")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["value"] == DIAMETER
    assert calls[0].data["entity_id"] == SYNC_ENTITY


async def test_reasserts_when_the_device_drifts(hass: HomeAssistant) -> None:
    """A value changed on the device gets set back.

    That is what makes a re-flash self-healing, and it is deliberate: the
    integration owns the number so it only has to be typed in one place.
    """
    _seed(hass)
    hass.states.async_set(SYNC_ENTITY, str(DIAMETER))

    await _setup(hass)
    calls: list[ServiceCall] = async_mock_service(hass, "number", "set_value")

    hass.states.async_set(SYNC_ENTITY, "28.0")
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["value"] == DIAMETER


async def test_does_not_push_when_already_correct(hass: HomeAssistant) -> None:
    """No pointless service calls while the device already agrees."""
    _seed(hass)
    hass.states.async_set(SYNC_ENTITY, str(DIAMETER))

    await _setup(hass)
    calls: list[ServiceCall] = async_mock_service(hass, "number", "set_value")

    # A state write that leaves the value alone.
    hass.states.async_set(SYNC_ENTITY, "29.0", {"unrelated": "attribute"})
    await hass.async_block_till_done()

    # And one that makes it unreadable - nothing to compare against, so
    # nothing to do until a real value returns.
    hass.states.async_set(SYNC_ENTITY, "unavailable")
    await hass.async_block_till_done()

    assert calls == []


async def test_no_sync_entity_configured_is_a_no_op(hass: HomeAssistant) -> None:
    """The whole feature is optional and must stay silent when unused."""
    _seed(hass)
    hass.states.async_set(SYNC_ENTITY, "28.0")

    await _setup(hass, with_sync=False)
    calls: list[ServiceCall] = async_mock_service(hass, "number", "set_value")

    hass.states.async_set(SYNC_ENTITY, "27.0")
    await hass.async_block_till_done()

    assert calls == []
