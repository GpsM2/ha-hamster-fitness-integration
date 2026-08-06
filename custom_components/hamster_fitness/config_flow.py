"""Config flow for the Hamster Fitness integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TimeSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_ACQUISITION_DATE,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_HUMIDITY_SENSOR,
    CONF_LIGHT_ENTITY,
    CONF_NOTIFY_SERVICES,
    CONF_SPEED_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_DIAMETER_SYNC_ENTITY,
    CONF_WHEEL_SENSOR,
    DEFAULT_DAILY_SUMMARY_ENABLED,
    DEFAULT_IDEAL_TEMP_MAX,
    DEFAULT_IDEAL_TEMP_MIN,
    DEFAULT_LIGHT_BRIGHTNESS_PCT,
    DEFAULT_LIGHT_TRANSITION_S,
    DEFAULT_LIGHT_TURN_OFF_DELAY_S,
    DEFAULT_LIGHT_TURN_OFF_ENABLED,
    DEFAULT_MIN_DISTANCE_KM,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_WARNINGS_ENABLED,
    DEFAULT_WHEEL_DIAMETER_CM,
    DOMAIN,
    IDEAL_DISTANCE_MIN_KM,
    MAX_WHEEL_DIAMETER_CM,
    MIN_WHEEL_DIAMETER_CM,
    OPTION_DAILY_SUMMARY_ENABLED,
    OPTION_IDEAL_TEMP_MAX,
    OPTION_IDEAL_TEMP_MIN,
    OPTION_LIGHT_BRIGHTNESS_PCT,
    OPTION_LIGHT_TRANSITION_S,
    OPTION_LIGHT_TURN_OFF_DELAY_S,
    OPTION_LIGHT_TURN_OFF_ENABLED,
    OPTION_MIN_DISTANCE_KM,
    OPTION_NOTIFICATION_TIME,
    OPTION_WARNINGS_ENABLED,
    SKIP_VALIDATION_STATES,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HAMSTER_NAME): TextSelector(),
        vol.Required(CONF_ACQUISITION_DATE): DateSelector(),
        vol.Required(
            CONF_WHEEL_DIAMETER, default=DEFAULT_WHEEL_DIAMETER_CM
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_WHEEL_DIAMETER_CM,
                max=MAX_WHEEL_DIAMETER_CM,
                step=0.1,
                unit_of_measurement="cm",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
)


def _sensors_schema() -> vol.Schema:
    """Build the schema for the source-entity selection step."""
    return vol.Schema(
        {
            # Es gibt keinen passenden device_class-Wert für "Umdrehungszähler",
            # daher wird hier nur auf die Domain gefiltert (bewusst KEIN
            # unit_of_measurement-Filter: das Auswahlfeld würde dann jeden
            # Umdrehungszähler mit einer anderen Einheit als "rot." komplett
            # ausblenden - inklusive einer bereits gewählten Entity beim
            # Reconfigure, falls sich die Einheit zwischenzeitlich geändert
            # hat). Die eigentliche "ist eine Zahl"-Prüfung übernimmt
            # _is_numeric_state() zur Laufzeit. Bei der mitgelieferten
            # ESPHome-Firmware "Hamster Wheel Total Rotations" eintippen, um
            # die Liste per Freitextsuche einzugrenzen.
            vol.Required(CONF_WHEEL_SENSOR): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR, multiple=False)
            ),
            # Optional: eine number-Entity (z. B. "Hamster Wheel Diameter"
            # auf dem ESPHome-Gerät), an die der oben eingegebene
            # CONF_WHEEL_DIAMETER automatisch übertragen wird - sonst
            # bleiben beide Werte unabhängig voneinander und müssen manuell
            # synchron gehalten werden. Siehe __init__.py.
            vol.Optional(CONF_WHEEL_DIAMETER_SYNC_ENTITY): EntitySelector(
                EntitySelectorConfig(domain=Platform.NUMBER, multiple=False)
            ),
            vol.Required(CONF_TEMPERATURE_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.SENSOR,
                    device_class="temperature",
                    multiple=False,
                )
            ),
            vol.Required(CONF_DOOR_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.BINARY_SENSOR,
                    device_class=["door", "opening"],
                    multiple=False,
                )
            ),
            # Optional: ohne diese beiden bleiben die Feuchtigkeits- bzw.
            # Geschwindigkeits-Entities einfach weg (siehe sensor.py).
            vol.Optional(CONF_HUMIDITY_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.SENSOR,
                    device_class="humidity",
                    multiple=False,
                )
            ),
            # device_class "speed" ist ein normierter HA-Wert (im Gegensatz zum
            # Umdrehungszähler oben) - die mitgelieferte ESPHome-Firmware setzt
            # ihn auf sensor_speed, engt die Auswahl also sinnvoll ein.
            vol.Optional(CONF_SPEED_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.SENSOR,
                    device_class="speed",
                    multiple=False,
                )
            ),
            # Optional: ohne diese Entity bleibt die Käfigbeleuchtungs-
            # Automatik einfach inaktiv (siehe door_light.py). Helligkeit/
            # Übergang/Ausschalt-Verhalten stehen im Expertenmenü.
            vol.Optional(CONF_LIGHT_ENTITY): EntitySelector(
                EntitySelectorConfig(domain=Platform.LIGHT, multiple=False)
            ),
            # Moderne HA-Versionen exponieren notify.* zunehmend als Entitäten
            # (Domain "notify") statt als reine Services. Damit bleibt die
            # Auswahl UI-basiert und zukunftssicher.
            vol.Optional(CONF_NOTIFY_SERVICES, default=list): EntitySelector(
                EntitySelectorConfig(domain=Platform.NOTIFY, multiple=True)
            ),
        }
    )


class HamsterFitnessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hamster Fitness."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first step: basic data about the hamster."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = str(user_input[CONF_HAMSTER_NAME]).strip()
            diameter = user_input[CONF_WHEEL_DIAMETER]

            if not name:
                errors[CONF_HAMSTER_NAME] = "invalid_name"
            if diameter <= 0:
                errors[CONF_WHEEL_DIAMETER] = "invalid_diameter"

            if not errors:
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_configured()

                self._data.update(user_input)
                self._data[CONF_HAMSTER_NAME] = name
                return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second step: selection of source entities."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not self._is_numeric_state(user_input[CONF_WHEEL_SENSOR]):
                errors[CONF_WHEEL_SENSOR] = "not_numeric"

            if not errors:
                self._data.update(user_input)
                return self.async_create_entry(
                    title=self._data[CONF_HAMSTER_NAME],
                    data=self._data,
                )

        return self.async_show_form(
            step_id="sensors",
            data_schema=_sensors_schema(),
            errors=errors,
        )

    @callback
    def _is_numeric_state(self, entity_id: str) -> bool:
        """Return True if the entity's current state is numeric.

        Entities that are (temporarily) unknown/unavailable at config-flow
        time are accepted; the runtime coordinator re-validates on every
        update once the integration is set up.
        """
        state = self.hass.states.get(entity_id)
        if state is None or state.state in SKIP_VALIDATION_STATES:
            return True
        try:
            float(state.state)
        except (TypeError, ValueError):
            return False
        return True

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration: basic data about the hamster."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            name = str(user_input[CONF_HAMSTER_NAME]).strip()
            diameter = user_input[CONF_WHEEL_DIAMETER]

            if not name:
                errors[CONF_HAMSTER_NAME] = "invalid_name"
            if diameter <= 0:
                errors[CONF_WHEEL_DIAMETER] = "invalid_diameter"

            if not errors:
                # unique_id bleibt bewusst unangetastet: er wurde beim
                # Ersteinrichten aus dem damaligen Namen abgeleitet, aber ein
                # Reconfigure soll ein Umbenennen erlauben, ohne dass die
                # Geräte-Identität wechselt. Anders als beim Standardmuster für
                # discovery-basierte unique_ids (IP/Seriennummer) gibt es hier
                # daher kein async_set_unique_id()/_abort_if_unique_id_mismatch().
                self._data = dict(reconfigure_entry.data)
                self._data.update(user_input)
                self._data[CONF_HAMSTER_NAME] = name
                return await self.async_step_reconfigure_sensors()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_reconfigure_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration: selection of source entities."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            if not self._is_numeric_state(user_input[CONF_WHEEL_SENSOR]):
                errors[CONF_WHEEL_SENSOR] = "not_numeric"

            if not errors:
                self._data.update(user_input)
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=self._data[CONF_HAMSTER_NAME],
                    data=self._data,
                )

        return self.async_show_form(
            step_id="reconfigure_sensors",
            data_schema=self.add_suggested_values_to_schema(
                _sensors_schema(), user_input or reconfigure_entry.data
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HamsterFitnessOptionsFlow:
        """Get the options ('Expertenmenü') flow for this handler."""
        return HamsterFitnessOptionsFlow()


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the schema for the options ('Expertenmenü') step."""
    return vol.Schema(
        {
            vol.Required(
                OPTION_IDEAL_TEMP_MIN,
                default=current.get(OPTION_IDEAL_TEMP_MIN, DEFAULT_IDEAL_TEMP_MIN),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=40,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPTION_IDEAL_TEMP_MAX,
                default=current.get(OPTION_IDEAL_TEMP_MAX, DEFAULT_IDEAL_TEMP_MAX),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=40,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPTION_MIN_DISTANCE_KM,
                default=current.get(OPTION_MIN_DISTANCE_KM, DEFAULT_MIN_DISTANCE_KM),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=IDEAL_DISTANCE_MIN_KM,
                    step=0.1,
                    unit_of_measurement="km",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPTION_WARNINGS_ENABLED,
                default=current.get(OPTION_WARNINGS_ENABLED, DEFAULT_WARNINGS_ENABLED),
            ): BooleanSelector(),
            vol.Required(
                OPTION_DAILY_SUMMARY_ENABLED,
                default=current.get(
                    OPTION_DAILY_SUMMARY_ENABLED, DEFAULT_DAILY_SUMMARY_ENABLED
                ),
            ): BooleanSelector(),
            vol.Required(
                OPTION_NOTIFICATION_TIME,
                default=current.get(
                    OPTION_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
                ),
            ): TimeSelector(),
            # Ab hier nur wirksam, wenn CONF_LIGHT_ENTITY konfiguriert ist -
            # siehe door_light.py. Werden trotzdem immer angezeigt, wie die
            # übrigen Options auch unabhängig von den Quell-Sensoren.
            vol.Required(
                OPTION_LIGHT_BRIGHTNESS_PCT,
                default=current.get(
                    OPTION_LIGHT_BRIGHTNESS_PCT, DEFAULT_LIGHT_BRIGHTNESS_PCT
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=100,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPTION_LIGHT_TRANSITION_S,
                default=current.get(
                    OPTION_LIGHT_TRANSITION_S, DEFAULT_LIGHT_TRANSITION_S
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=60,
                    step=0.5,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPTION_LIGHT_TURN_OFF_ENABLED,
                default=current.get(
                    OPTION_LIGHT_TURN_OFF_ENABLED, DEFAULT_LIGHT_TURN_OFF_ENABLED
                ),
            ): BooleanSelector(),
            vol.Required(
                OPTION_LIGHT_TURN_OFF_DELAY_S,
                default=current.get(
                    OPTION_LIGHT_TURN_OFF_DELAY_S, DEFAULT_LIGHT_TURN_OFF_DELAY_S
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=3600,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class HamsterFitnessOptionsFlow(OptionsFlowWithReload):
    """Handle the options ('Expertenmenü') for Hamster Fitness.

    Subclassing OptionsFlowWithReload means the config entry is reloaded
    automatically whenever the options change, so the coordinator picks up
    new thresholds immediately instead of waiting for the next incidental
    sensor event. self.config_entry is provided by the base class.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[OPTION_IDEAL_TEMP_MIN] >= user_input[OPTION_IDEAL_TEMP_MAX]:
                errors["base"] = "invalid_temp_range"
            else:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(dict(self.config_entry.options)),
            errors=errors,
        )
