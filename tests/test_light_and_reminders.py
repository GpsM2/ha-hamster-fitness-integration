"""Tests for the cage-light automation switch/pause and the weigh-in reminder."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.hamster_fitness.const import (
    ATTR_DURATION_MINUTES,
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_LIGHT_ENTITY,
    CONF_NOTIFY_SERVICES,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    OPTION_WARNINGS_ENABLED,
    OPTION_WEIGHT_REMINDER_DAYS,
    OPTION_WEIGHT_REMINDER_ENABLED,
    SERVICE_PAUSE_LIGHT_AUTOMATION,
)
from custom_components.hamster_fitness.notify import HamsterFitnessNotifier

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
CAGE_LIGHT = "light.cage"
NOTIFY_TARGET = "notify.mobile_app_phone"

SWITCH_ENTITY = "switch.hamster_taco_light_automation"

# The wheel sits at 0 rotations in these tests, which legitimately trips the
# "too little exercise" warning - and that would land in the same
# notify.send_message list the reminder assertions look at. Warnings are
# covered by their own tests, so they're off here to keep the signal clean.
REMINDER_OPTIONS = {
    OPTION_WARNINGS_ENABLED: False,
    OPTION_WEIGHT_REMINDER_ENABLED: True,
    OPTION_WEIGHT_REMINDER_DAYS: 7,
}


async def _setup_entry(
    hass: HomeAssistant, *, with_light: bool = True, options: dict | None = None
) -> MockConfigEntry:
    """Set up a Taco entry, optionally with a cage light configured."""
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")
    hass.states.async_set(CAGE_LIGHT, "off")

    data = {
        CONF_HAMSTER_NAME: "Taco",
        CONF_ACQUISITION_DATE: "2024-01-01",
        CONF_WHEEL_DIAMETER: 28.0,
        CONF_WHEEL_SENSOR: WHEEL_SENSOR,
        CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
        CONF_DOOR_SENSOR: DOOR_SENSOR,
        CONF_NOTIFY_SERVICES: [NOTIFY_TARGET],
    }
    if with_light:
        data[CONF_LIGHT_ENTITY] = CAGE_LIGHT

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data=data,
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _open_the_cage(hass: HomeAssistant) -> None:
    """Trigger a closed -> open transition of the cage door."""
    hass.states.async_set(DOOR_SENSOR, "on")
    await hass.async_block_till_done()


async def test_no_switch_without_a_configured_light(hass: HomeAssistant) -> None:
    """Without a cage light there is no automation, so no switch either."""
    await _setup_entry(hass, with_light=False)
    assert hass.states.get(SWITCH_ENTITY) is None


async def test_switch_exists_and_defaults_to_on(hass: HomeAssistant) -> None:
    """A configured light gets a switch, on by default (previous behaviour)."""
    await _setup_entry(hass)

    state = hass.states.get(SWITCH_ENTITY)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["pause_active"] is False
    assert state.attributes["light_entity"] == CAGE_LIGHT


async def test_automation_turns_the_light_on_while_enabled(
    hass: HomeAssistant,
) -> None:
    """Baseline: opening the cage still switches the light on."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    await _setup_entry(hass)

    await _open_the_cage(hass)

    assert len(turn_on) == 1
    assert turn_on[0].data["entity_id"] == CAGE_LIGHT


async def test_switching_the_automation_off_stops_it(hass: HomeAssistant) -> None:
    """With the switch off, the door no longer controls the light."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    await _setup_entry(hass)

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )
    assert hass.states.get(SWITCH_ENTITY).state == "off"

    await _open_the_cage(hass)
    assert turn_on == []


async def test_pause_service_suspends_the_automation(hass: HomeAssistant) -> None:
    """Pausing keeps the switch on but stops it acting on the door."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAUSE_LIGHT_AUTOMATION,
        {"entity_id": SWITCH_ENTITY, ATTR_DURATION_MINUTES: 30},
        blocking=True,
    )

    state = hass.states.get(SWITCH_ENTITY)
    # Still "on": a pause is a short break, not a change of intent.
    assert state.state == "on"
    assert state.attributes["pause_active"] is True
    assert state.attributes["paused_until"] is not None

    await _open_the_cage(hass)
    assert turn_on == []

    # Let the pause run out through its own timer, rather than poking the
    # callback - that also proves the timer was armed in the first place.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done()

    assert entry.runtime_data.light_pause_until is None
    assert hass.states.get(SWITCH_ENTITY).attributes["pause_active"] is False
    # And it does not retroactively act on the door change it slept through.
    assert turn_on == []


async def test_pause_defaults_to_thirty_minutes(hass: HomeAssistant) -> None:
    """Omitting the duration gives the 30 minutes the card's button uses."""
    entry = await _setup_entry(hass)

    before = dt_util.utcnow()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAUSE_LIGHT_AUTOMATION,
        {"entity_id": SWITCH_ENTITY},
        blocking=True,
    )

    paused_until = entry.runtime_data.light_pause_until
    assert paused_until is not None
    assert timedelta(minutes=29) < paused_until - before < timedelta(minutes=31)


async def test_turning_the_switch_off_clears_a_running_pause(
    hass: HomeAssistant,
) -> None:
    """A pause is meaningless once the automation is off for good."""
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PAUSE_LIGHT_AUTOMATION,
        {"entity_id": SWITCH_ENTITY},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": SWITCH_ENTITY}, blocking=True
    )

    assert entry.runtime_data.light_pause_until is None


async def test_weight_updates_are_timestamped(hass: HomeAssistant) -> None:
    """Entering a weight records when it happened, for the reminder."""
    entry = await _setup_entry(hass)
    assert entry.runtime_data.weight_last_set_at is None

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.hamster_taco_weight", "value": 45},
        blocking=True,
    )

    assert entry.runtime_data.weight_last_set_at is not None
    weight = hass.states.get("number.hamster_taco_weight")
    assert weight.state == "45.0"
    assert weight.attributes["last_weighed_at"] is not None


async def test_weight_reminder_stays_quiet_when_recently_weighed(
    hass: HomeAssistant,
) -> None:
    """Weighing regularly means never seeing this reminder."""
    sent = async_mock_service(hass, "notify", "send_message")
    entry = await _setup_entry(hass, options=REMINDER_OPTIONS)
    coordinator = entry.runtime_data
    await coordinator.async_record_weight_update(45.0)

    notifier = HamsterFitnessNotifier(hass, entry, coordinator)
    notifier._async_check_weight_reminder()
    await hass.async_block_till_done()

    assert sent == []


async def test_weight_reminder_fires_once_overdue(hass: HomeAssistant) -> None:
    """Past the interval the reminder goes out - but only once per interval."""
    sent = async_mock_service(hass, "notify", "send_message")
    entry = await _setup_entry(hass, options=REMINDER_OPTIONS)
    coordinator = entry.runtime_data
    coordinator._weight_last_set_at = dt_util.utcnow() - timedelta(days=9)

    notifier = HamsterFitnessNotifier(hass, entry, coordinator)
    notifier._async_check_weight_reminder()
    await hass.async_block_till_done()

    assert len(sent) == 1
    assert sent[0].data["title"] == "Taco"
    assert "9" in sent[0].data["message"]

    # Still overdue tomorrow, but the reminder must not repeat daily.
    notifier._async_check_weight_reminder()
    await hass.async_block_till_done()
    assert len(sent) == 1


async def test_weight_reminder_nudges_when_never_weighed(
    hass: HomeAssistant,
) -> None:
    """Never having weighed at all counts as overdue."""
    sent = async_mock_service(hass, "notify", "send_message")
    entry = await _setup_entry(hass, options=REMINDER_OPTIONS)

    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    notifier._async_check_weight_reminder()
    await hass.async_block_till_done()

    assert len(sent) == 1
