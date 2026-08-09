"""Tests for the forward-looking heat care reminder.

Unlike the climate pillar, which reports a cage that is *already* too
warm, this one fires the morning of a hot day - while shade, cooling and
fresh water can still be arranged.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hamster_fitness.const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_NOTIFY_SERVICES,
    CONF_TEMPERATURE_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_SENSOR,
    DOMAIN,
    HEAT_REMINDER_COOLDOWN_HOURS,
    OPTION_HEAT_FORECAST_ENABLED,
    OPTION_HEAT_FORECAST_THRESHOLD_C,
    OPTION_WARNINGS_ENABLED,
    WEATHER_DOMAIN,
    WEATHER_SERVICE_GET_FORECASTS,
)
from custom_components.hamster_fitness.notify import HamsterFitnessNotifier

WHEEL_SENSOR = "sensor.wheel_rotations"
TEMPERATURE_SENSOR = "sensor.cage_temperature"
DOOR_SENSOR = "binary_sensor.cage_door"
WEATHER_ENTITY = "weather.home"
NOTIFY_TARGET = "notify.mobile_app_phone"

# The wheel sits at 0 rotations here, which legitimately trips the "too
# little exercise" warning - and that would land in the same
# notify.send_message list these assertions look at.
HEAT_OPTIONS = {
    OPTION_WARNINGS_ENABLED: False,
    OPTION_HEAT_FORECAST_ENABLED: True,
    OPTION_HEAT_FORECAST_THRESHOLD_C: 28.0,
}


async def _setup_entry(
    hass: HomeAssistant, *, with_weather: bool = True, options: dict | None = None
) -> MockConfigEntry:
    hass.states.async_set(WHEEL_SENSOR, "0")
    hass.states.async_set(TEMPERATURE_SENSOR, "22")
    hass.states.async_set(DOOR_SENSOR, "off")
    if with_weather:
        hass.states.async_set(WEATHER_ENTITY, "sunny")

    data = {
        CONF_HAMSTER_NAME: "Taco",
        CONF_ACQUISITION_DATE: "2024-01-01",
        CONF_WHEEL_DIAMETER: 28.0,
        CONF_WHEEL_SENSOR: WHEEL_SENSOR,
        CONF_TEMPERATURE_SENSOR: TEMPERATURE_SENSOR,
        CONF_DOOR_SENSOR: DOOR_SENSOR,
        CONF_NOTIFY_SERVICES: [NOTIFY_TARGET],
    }
    if with_weather:
        data[CONF_WEATHER_ENTITY] = WEATHER_ENTITY

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="taco",
        title="Taco",
        data=data,
        options=options if options is not None else HEAT_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _mock_forecast(hass: HomeAssistant, response: Any) -> list:
    """Stand in for weather.get_forecasts, returning `response`."""
    return async_mock_service(
        hass,
        WEATHER_DOMAIN,
        WEATHER_SERVICE_GET_FORECASTS,
        response=response,
        supports_response="only",
    )


def _daily(temperature: Any, key: str = "native_temperature") -> dict:
    return {WEATHER_ENTITY: {"forecast": [{key: temperature, "condition": "sunny"}]}}


async def _run_check(hass: HomeAssistant, entry: MockConfigEntry) -> list:
    """Fire the daily check and return whatever notifications went out."""
    sent = async_mock_service(hass, "notify", "send_message")
    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    await notifier.async_setup()
    await notifier._async_check_heat_forecast()
    await hass.async_block_till_done()
    return sent


async def test_reminder_sent_when_forecast_reaches_the_threshold(
    hass: HomeAssistant,
) -> None:
    _mock_forecast(hass, _daily(31))
    entry = await _setup_entry(hass)

    sent = await _run_check(hass, entry)

    assert len(sent) == 1
    assert "31" in sent[0].data["message"]


async def test_no_reminder_below_the_threshold(hass: HomeAssistant) -> None:
    _mock_forecast(hass, _daily(24))
    entry = await _setup_entry(hass)

    assert await _run_check(hass, entry) == []


async def test_threshold_is_inclusive(hass: HomeAssistant) -> None:
    """Exactly at the configured number counts as reaching it."""
    _mock_forecast(hass, _daily(28))
    entry = await _setup_entry(hass)

    assert len(await _run_check(hass, entry)) == 1


async def test_older_temperature_key_is_understood(hass: HomeAssistant) -> None:
    """Some integrations still use `temperature` rather than the native one."""
    _mock_forecast(hass, _daily(31, key="temperature"))
    entry = await _setup_entry(hass)

    assert len(await _run_check(hass, entry)) == 1


async def test_no_weather_entity_means_the_flow_is_off(hass: HomeAssistant) -> None:
    """The option alone isn't enough - there has to be something to ask."""
    _mock_forecast(hass, _daily(35))
    entry = await _setup_entry(hass, with_weather=False)

    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    assert notifier._heat_forecast_enabled is False


async def test_disabled_by_default(hass: HomeAssistant) -> None:
    """Nobody gets woken by a reminder they never switched on."""
    _mock_forecast(hass, _daily(35))
    entry = await _setup_entry(hass, options={OPTION_WARNINGS_ENABLED: False})

    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    assert notifier._heat_forecast_enabled is False


async def test_cooldown_suppresses_the_next_day(hass: HomeAssistant) -> None:
    """A heatwave runs for days; the advice doesn't change after the first."""
    _mock_forecast(hass, _daily(33))
    entry = await _setup_entry(hass)

    sent = async_mock_service(hass, "notify", "send_message")
    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    await notifier.async_setup()

    await notifier._async_check_heat_forecast()
    await hass.async_block_till_done()
    assert len(sent) == 1

    # Next morning, still hot - inside the cooldown, so still quiet.
    await notifier._async_check_heat_forecast()
    await hass.async_block_till_done()
    assert len(sent) == 1

    # Once the cooldown has expired it may speak up again.
    notifier._last_heat_reminder_at = dt_util.utcnow() - timedelta(
        hours=HEAT_REMINDER_COOLDOWN_HOURS + 1
    )
    await notifier._async_check_heat_forecast()
    await hass.async_block_till_done()
    assert len(sent) == 2


async def test_stays_quiet_while_the_hamster_is_boarding(
    hass: HomeAssistant,
) -> None:
    """Advice about a cage the hamster isn't in is noise."""
    _mock_forecast(hass, _daily(35))
    entry = await _setup_entry(hass)
    await entry.runtime_data.async_set_boarding(True)

    sent = async_mock_service(hass, "notify", "send_message")
    notifier = HamsterFitnessNotifier(hass, entry, entry.runtime_data)
    await notifier.async_setup()
    notifier._async_handle_daily_time(dt_util.utcnow())
    await hass.async_block_till_done()

    assert sent == []


# --- Malformed forecasts --------------------------------------------------
#
# The response shape is up to whichever weather integration answered, and
# it comes back as plain JSON. None must mean "don't know" and keep the
# reminder silent - never a traceback in the middle of the morning run.


async def test_empty_forecast_list_is_silent(hass: HomeAssistant) -> None:
    _mock_forecast(hass, {WEATHER_ENTITY: {"forecast": []}})
    entry = await _setup_entry(hass)

    assert await _run_check(hass, entry) == []


async def test_forecast_without_a_temperature_is_silent(
    hass: HomeAssistant,
) -> None:
    _mock_forecast(hass, {WEATHER_ENTITY: {"forecast": [{"condition": "sunny"}]}})
    entry = await _setup_entry(hass)

    assert await _run_check(hass, entry) == []


async def test_unexpected_response_shape_is_silent(hass: HomeAssistant) -> None:
    """A provider answering with something else entirely must not crash."""
    _mock_forecast(hass, {WEATHER_ENTITY: "unexpectedly a string"})
    entry = await _setup_entry(hass)

    assert await _run_check(hass, entry) == []


async def test_non_numeric_temperature_is_silent(hass: HomeAssistant) -> None:
    _mock_forecast(hass, _daily("warm-ish"))
    entry = await _setup_entry(hass)

    assert await _run_check(hass, entry) == []
