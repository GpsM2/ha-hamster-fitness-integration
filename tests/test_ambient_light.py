"""Tests for the Day & Night card's ambient-light source.

CONF_ILLUMINANCE_SENSOR (added in #27) feeds
HamsterFitnessCoordinator._read_ambient_light(), which the Day & Night
card reads instead of sun.sun once configured. The one behaviour worth
pinning down: the cage light itself must not be allowed to convince the
sensor - and the card - that it's suddenly daytime.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
CAGE_LIGHT = "light.cage"
ILLUMINANCE_SENSOR = "sensor.room_illuminance"

HEALTH_SCORE = "sensor.hamster_taco_health_score"


async def _setup_entry(
    hass: HomeAssistant, *, with_illuminance: bool = True, with_light: bool = True
) -> MockConfigEntry:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")
    if with_light:
        hass.states.async_set(CAGE_LIGHT, "off")

    data = {
        CONF_HAMSTER_NAME: "Taco",
        CONF_ACQUISITION_DATE: "2024-01-01",
        CONF_WHEEL_DIAMETER: 28.0,
        CONF_WHEEL_SENSOR: WHEEL_SENSOR,
        CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
        CONF_DOOR_SENSOR: DOOR_SENSOR,
    }
    if with_illuminance:
        data[CONF_ILLUMINANCE_SENSOR] = ILLUMINANCE_SENSOR
    if with_light:
        data[CONF_LIGHT_ENTITY] = CAGE_LIGHT

    entry = MockConfigEntry(domain=DOMAIN, unique_id="taco", title="Taco", data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _ambient_lx(entry: MockConfigEntry) -> float | None:
    return entry.runtime_data.data.ambient_light_lx


async def test_no_illuminance_sensor_means_no_value(hass: HomeAssistant) -> None:
    """Not configuring one at all is the card's cue to keep using sun.sun."""
    entry = await _setup_entry(hass, with_illuminance=False)
    assert _ambient_lx(entry) is None


async def test_reads_the_live_value_while_the_light_is_off(
    hass: HomeAssistant,
) -> None:
    entry = await _setup_entry(hass)

    hass.states.async_set(ILLUMINANCE_SENSOR, "5")
    await hass.async_block_till_done()
    assert _ambient_lx(entry) == 5.0

    hass.states.async_set(ILLUMINANCE_SENSOR, "120")
    await hass.async_block_till_done()
    assert _ambient_lx(entry) == 120.0


async def test_light_turning_on_freezes_the_reading(hass: HomeAssistant) -> None:
    """The whole point: the light must not fake a daytime reading at 2am."""
    entry = await _setup_entry(hass)

    hass.states.async_set(ILLUMINANCE_SENSOR, "3")
    await hass.async_block_till_done()
    assert _ambient_lx(entry) == 3.0

    hass.states.async_set(CAGE_LIGHT, "on")
    await hass.async_block_till_done()
    # The light being on is itself what would spike the reading in
    # reality; simulated here as the sensor jumping the way it actually
    # would next to a lit lamp.
    hass.states.async_set(ILLUMINANCE_SENSOR, "300")
    await hass.async_block_till_done()

    assert _ambient_lx(entry) == 3.0, "the pre-light reading must be held"


async def test_reading_resumes_once_the_light_turns_off(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)

    # The "off" reading has to actually be processed (awaited) before the
    # light turns on - otherwise both state writes land before any
    # recalculation runs, and the very first one already sees the light
    # as on, capturing nothing.
    hass.states.async_set(ILLUMINANCE_SENSOR, "3")
    await hass.async_block_till_done()
    hass.states.async_set(CAGE_LIGHT, "on")
    await hass.async_block_till_done()
    hass.states.async_set(ILLUMINANCE_SENSOR, "300")
    await hass.async_block_till_done()
    assert _ambient_lx(entry) == 3.0

    hass.states.async_set(CAGE_LIGHT, "off")
    await hass.async_block_till_done()
    hass.states.async_set(ILLUMINANCE_SENSOR, "4")
    await hass.async_block_till_done()

    assert _ambient_lx(entry) == 4.0


async def test_no_configured_light_means_nothing_to_hold_against(
    hass: HomeAssistant,
) -> None:
    """An illuminance sensor without a cage light just always reads live."""
    entry = await _setup_entry(hass, with_light=False)

    hass.states.async_set(ILLUMINANCE_SENSOR, "7")
    await hass.async_block_till_done()
    assert _ambient_lx(entry) == 7.0


async def test_unavailable_before_any_good_reading_is_none(
    hass: HomeAssistant,
) -> None:
    """Nothing to hold onto yet if the sensor has never reported a number."""
    entry = await _setup_entry(hass)
    hass.states.async_set(ILLUMINANCE_SENSOR, "unavailable")
    await hass.async_block_till_done()

    assert _ambient_lx(entry) is None


async def test_health_score_sensor_exposes_ambient_light(
    hass: HomeAssistant,
) -> None:
    await _setup_entry(hass)
    hass.states.async_set(ILLUMINANCE_SENSOR, "42")
    await hass.async_block_till_done()

    state = hass.states.get(HEALTH_SCORE)
    assert state.attributes["ambient_light_lx"] == 42.0
