"""Tests for the options flow, especially its two collapsed sections.

The cage-light fields and the notification fields are each grouped into
a collapsed `section` so neither dominates the form. Home Assistant hands
a section's values back *nested*, but everything that reads options at
runtime - door_light.py, notify.py, the coordinator - expects them flat,
and entries saved before either grouping existed are flat too.
`_flatten_options()` bridges that, and these tests pin it down: a silent
regression there would leave the cage light or the reminders silently
using defaults.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hamster_fitness.config_flow import _flatten_options
from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_LIGHT_ENTITY,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    LIGHT_SECTION,
    NOTIFICATION_SECTION,
    OPTION_IDEAL_TEMP_MAX,
    OPTION_IDEAL_TEMP_MIN,
    OPTION_LIGHT_BRIGHTNESS_PCT,
    OPTION_LIGHT_TRANSITION_S,
    OPTION_LIGHT_TURN_OFF_DELAY_S,
    OPTION_LIGHT_TURN_OFF_ENABLED,
    OPTION_MIN_DISTANCE_KM,
    OPTION_NOTIFICATION_TIME,
    OPTION_WARNINGS_ENABLED,
    OPTION_WEIGHT_REMINDER_DAYS,
    OPTION_WEIGHT_REMINDER_ENABLED,
)

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
CAGE_LIGHT = "light.cage"


def _submission(**overrides: object) -> dict:
    """A complete options-form submission, shaped as HA delivers it."""
    payload = {
        OPTION_IDEAL_TEMP_MIN: 20.0,
        OPTION_IDEAL_TEMP_MAX: 24.0,
        OPTION_MIN_DISTANCE_KM: 2.0,
        NOTIFICATION_SECTION: {
            OPTION_WARNINGS_ENABLED: True,
            "daily_summary_enabled": True,
            OPTION_NOTIFICATION_TIME: "08:00:00",
            OPTION_WEIGHT_REMINDER_ENABLED: False,
            OPTION_WEIGHT_REMINDER_DAYS: 7,
        },
        LIGHT_SECTION: {
            OPTION_LIGHT_BRIGHTNESS_PCT: 60,
            OPTION_LIGHT_TRANSITION_S: 1.5,
            OPTION_LIGHT_TURN_OFF_ENABLED: False,
            OPTION_LIGHT_TURN_OFF_DELAY_S: 30,
        },
    }
    payload.update(overrides)
    return payload


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")
    hass.states.async_set(CAGE_LIGHT, "off")

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
            CONF_LIGHT_ENTITY: CAGE_LIGHT,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def test_flatten_lifts_both_sections_up() -> None:
    """Section values end up alongside the rest, not nested under them."""
    flattened = _flatten_options(_submission())

    assert LIGHT_SECTION not in flattened
    assert NOTIFICATION_SECTION not in flattened
    assert flattened[OPTION_LIGHT_BRIGHTNESS_PCT] == 60
    assert flattened[OPTION_LIGHT_TRANSITION_S] == 1.5
    assert flattened[OPTION_LIGHT_TURN_OFF_ENABLED] is False
    assert flattened[OPTION_LIGHT_TURN_OFF_DELAY_S] == 30
    assert flattened[OPTION_WARNINGS_ENABLED] is True
    assert flattened[OPTION_WEIGHT_REMINDER_DAYS] == 7
    # ...and the ungrouped fields are untouched.
    assert flattened[OPTION_IDEAL_TEMP_MIN] == 20.0


def test_flatten_tolerates_a_missing_section() -> None:
    """A payload missing a section must not raise.

    Belt and braces: an older Home Assistant, or a future step that drops
    a section, should degrade to "keep the other options" rather than a
    KeyError in the middle of saving.
    """
    payload = _submission()
    del payload[LIGHT_SECTION]
    del payload[NOTIFICATION_SECTION]

    flattened = _flatten_options(payload)
    assert OPTION_LIGHT_BRIGHTNESS_PCT not in flattened
    assert OPTION_WARNINGS_ENABLED not in flattened
    assert flattened[OPTION_IDEAL_TEMP_MIN] == 20.0


async def test_options_flow_saves_sections_flat(hass: HomeAssistant) -> None:
    """End to end: what lands in entry.options is flat, so readers find it."""
    entry = await _setup_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _submission()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert LIGHT_SECTION not in entry.options
    assert NOTIFICATION_SECTION not in entry.options
    assert entry.options[OPTION_LIGHT_BRIGHTNESS_PCT] == 60
    assert entry.options[OPTION_LIGHT_TURN_OFF_ENABLED] is False
    assert entry.options[OPTION_WARNINGS_ENABLED] is True
    assert entry.options[OPTION_WEIGHT_REMINDER_ENABLED] is False


async def test_options_flow_still_validates_the_temperature_range(
    hass: HomeAssistant,
) -> None:
    """Validation reads the flattened values, not the raw nested payload."""
    entry = await _setup_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _submission(**{OPTION_IDEAL_TEMP_MIN: 26.0, OPTION_IDEAL_TEMP_MAX: 22.0}),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_temp_range"}
