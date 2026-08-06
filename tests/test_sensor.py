"""Tests for the Hamster Fitness sensor platform (via the coordinator)."""

from __future__ import annotations

import math

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
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


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and set up a minimal Taco config entry for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data={
            CONF_HAMSTER_NAME: "Taco",
            CONF_ACQUISITION_DATE: "2024-01-01",
            CONF_WHEEL_DIAMETER: 28.0,
            CONF_WHEEL_SENSOR: WHEEL_SENSOR,
            CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
            CONF_DOOR_SENSOR: DOOR_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_daily_distance_uses_diameter_not_circumference(
    hass: HomeAssistant,
) -> None:
    """100 rotations on a 28 cm *diameter* wheel is ~0.088 km, not ~0.028 km.

    Regression test for the diameter/circumference mix-up this integration
    used to have (see ROADMAP.md): CONF_WHEEL_DIAMETER must be converted
    via circumference = diameter * pi before being used for distance math.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    await _setup_entry(hass)

    hass.states.async_set(WHEEL_SENSOR, "100")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.hamster_taco_daily_distance")
    assert state is not None

    expected_km = round(100 * (28.0 * math.pi) / 100_000, 3)
    assert expected_km == 0.088  # sanity check against the old, wrong 0.028
    assert float(state.state) == expected_km


async def test_low_distance_triggers_warning(hass: HomeAssistant) -> None:
    """A day far below the minimum distance sets the warning binary sensor."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    entry = await _setup_entry(hass)

    hass.states.async_set(WHEEL_SENSOR, "100")
    await hass.async_block_till_done()

    warning = hass.states.get("binary_sensor.hamster_taco_warning")
    assert warning is not None
    assert warning.state == "on"
    # Checked against the coordinator's stable reason codes, not the
    # human-readable (currently German) attribute text.
    assert "too_little_exercise" in entry.runtime_data.data.warning_reasons

    health_score = hass.states.get("sensor.hamster_taco_health_score")
    assert health_score is not None
    assert 0 <= int(health_score.state) < 100


async def test_door_sensor_mirrors_source(hass: HomeAssistant) -> None:
    """binary_sensor.<hamster>_cage_door mirrors the configured door sensor.

    Note the entity_id: Home Assistant derives it from the *name* ("Cage
    door"), not from the translation_key ("door") the Python code uses.
    """
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")

    await _setup_entry(hass)

    assert hass.states.get("binary_sensor.hamster_taco_cage_door").state == "off"

    hass.states.async_set(DOOR_SENSOR, "on")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.hamster_taco_cage_door").state == "on"
