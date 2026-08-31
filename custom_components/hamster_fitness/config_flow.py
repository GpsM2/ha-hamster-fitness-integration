"""Config flow for the Hamster Fitness integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorStateClass,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import ATTR_DEVICE_CLASS, Platform
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)
from homeassistant.util import slugify

from .const import (
    BREED_OTHER,
    BREEDS,
    COAT_COLORS,
    CONF_ACQUISITION_DATE,
    CONF_BREED,
    CONF_BREED_OTHER,
    CONF_COAT_COLOR,
    CONF_DOOR_SENSOR,
    CONF_HAMSTER_NAME,
    CONF_HUMIDITY_SENSOR,
    CONF_ILLUMINANCE_SENSOR,
    CONF_LIGHT_ENTITY,
    CONF_MOON_ENTITY,
    CONF_NOTIFY_SERVICES,
    CONF_SPEED_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_WHEEL_DIAMETER,
    CONF_WHEEL_DIAMETER_SYNC_ENTITY,
    CONF_WHEEL_SENSOR,
    DEFAULT_BREED,
    DEFAULT_COAT_COLOR,
    DEFAULT_DAILY_SUMMARY_ENABLED,
    DEFAULT_HEAT_FORECAST_ENABLED,
    DEFAULT_HEAT_FORECAST_THRESHOLD_C,
    DEFAULT_IDEAL_TEMP_MAX,
    DEFAULT_IDEAL_TEMP_MIN,
    DEFAULT_LIGHT_BRIGHTNESS_PCT,
    DEFAULT_LIGHT_TRANSITION_S,
    DEFAULT_LIGHT_TURN_OFF_DELAY_S,
    DEFAULT_LIGHT_TURN_OFF_ENABLED,
    DEFAULT_MIN_DISTANCE_KM,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_WARNINGS_ENABLED,
    DEFAULT_WEIGHT_REMINDER_DAYS,
    DEFAULT_WEIGHT_REMINDER_ENABLED,
    DEFAULT_WHEEL_DIAMETER_CM,
    DOMAIN,
    IDEAL_DISTANCE_MIN_KM,
    LIGHT_SECTION,
    MAX_HEAT_FORECAST_THRESHOLD_C,
    MAX_LIFETIME_DISTANCE_KM,
    MAX_WEIGHT_REMINDER_DAYS,
    MAX_WHEEL_DIAMETER_CM,
    MIN_HEAT_FORECAST_THRESHOLD_C,
    MIN_WEIGHT_REMINDER_DAYS,
    MIN_WHEEL_DIAMETER_CM,
    NOTIFICATION_SECTION,
    OPTION_DAILY_SUMMARY_ENABLED,
    OPTION_HEAT_FORECAST_ENABLED,
    OPTION_HEAT_FORECAST_THRESHOLD_C,
    OPTION_IDEAL_TEMP_MAX,
    OPTION_IDEAL_TEMP_MIN,
    OPTION_LIFETIME_DISTANCE_KM,
    OPTION_LIGHT_BRIGHTNESS_PCT,
    OPTION_LIGHT_TRANSITION_S,
    OPTION_LIGHT_TURN_OFF_DELAY_S,
    OPTION_LIGHT_TURN_OFF_ENABLED,
    OPTION_MIN_DISTANCE_KM,
    OPTION_NOTIFICATION_TIME,
    OPTION_WARNINGS_ENABLED,
    OPTION_WEIGHT_REMINDER_DAYS,
    OPTION_WEIGHT_REMINDER_ENABLED,
    SKIP_VALIDATION_STATES,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HAMSTER_NAME): TextSelector(),
        vol.Required(CONF_ACQUISITION_DATE): DateSelector(),
        # Rasse und Fellfarbe sind rein beschreibend: sie landen als
        # Attribute am Health-Score-Sensor und färben dort die
        # Karten-Illustration ein (siehe hamster_profile() in
        # coordinator.py). In die Score-Berechnung fließen sie nicht ein.
        vol.Required(CONF_BREED, default=DEFAULT_BREED): SelectSelector(
            SelectSelectorConfig(
                options=BREEDS,
                translation_key="breed",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_BREED_OTHER): TextSelector(),
        vol.Required(CONF_COAT_COLOR, default=DEFAULT_COAT_COLOR): SelectSelector(
            SelectSelectorConfig(
                options=COAT_COLORS,
                translation_key="coat_color",
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
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


def _validate_basics(user_input: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Validate the shared user/reconfigure step, returning (name, errors)."""
    name = str(user_input[CONF_HAMSTER_NAME]).strip()
    errors: dict[str, str] = {}

    if not name:
        errors[CONF_HAMSTER_NAME] = "invalid_name"
    if user_input[CONF_WHEEL_DIAMETER] <= 0:
        errors[CONF_WHEEL_DIAMETER] = "invalid_diameter"
    # "Sonstige" ohne Angabe wäre eine Rasse, die nichts aussagt.
    if user_input.get(CONF_BREED) == BREED_OTHER and not str(
        user_input.get(CONF_BREED_OTHER, "")
    ).strip():
        errors[CONF_BREED_OTHER] = "breed_required"

    return name, errors


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
            # Optional: ohne diese Entity gibt es keinen Pflege-Pillar und
            # keine binary_sensor.<name>_cage_door-Entity (siehe sensor.py,
            # binary_sensor.py) - der Schlaf-Pillar zählt dann nur noch
            # Aktivitätssitzungen, nicht mehr Türöffnungen (coordinator.py).
            vol.Optional(CONF_DOOR_SENSOR): EntitySelector(
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
            # Optional: ohne diese Entity bleibt die Day-&-Night-Karte bei
            # sun.sun für Tag/Nacht (siehe coordinator.py). Ein echter
            # Helligkeitssensor im Zimmer trifft es besser als der
            # Sonnenstand, sobald Vorhänge, Keller o. Ä. im Spiel sind.
            vol.Optional(CONF_ILLUMINANCE_SENSOR): EntitySelector(
                EntitySelectorConfig(
                    domain=Platform.SENSOR,
                    device_class="illuminance",
                    multiple=False,
                )
            ),
            # Optional: Grundlage für die Hitze-Erinnerung (notify.py) und
            # später das Wetter-Overlay der Day-&-Night-Karte. Ohne diese
            # Entity bleibt beides inaktiv.
            vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
                EntitySelectorConfig(domain=Platform.WEATHER, multiple=False)
            ),
            # Optional: Mondphase für die Day-&-Night-Karte, typischerweise
            # sensor.moon aus der eingebauten "Moon"-Integration. Es gibt
            # dafür keine eigene device_class, auf die sich filtern ließe
            # (dieselbe Lage wie beim Umdrehungszähler ganz oben), daher nur
            # nach Domain - "moon" eintippen grenzt die Liste ein. Ohne
            # Auswahl bleibt es bei der festen Sichel.
            vol.Optional(CONF_MOON_ENTITY): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR, multiple=False)
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
            name, errors = _validate_basics(user_input)

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
            elif not self._looks_like_a_counter(user_input[CONF_WHEEL_SENSOR]):
                errors[CONF_WHEEL_SENSOR] = "not_a_counter"
            if not self._entity_exists(user_input[CONF_TEMPERATURE_SENSOR]):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if user_input.get(CONF_DOOR_SENSOR) and not self._entity_exists(
                user_input[CONF_DOOR_SENSOR]
            ):
                errors[CONF_DOOR_SENSOR] = "entity_not_found"

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

    @callback
    def _looks_like_a_counter(self, entity_id: str) -> bool:
        """Return True unless the entity is plainly not a rotation counter.

        There is no `device_class` for "counts rotations", which is why the
        picker can only filter on the domain - and the attribute that would
        actually tell them apart, `state_class`, is not something the entity
        selector can filter on (EntitySelectorConfig takes integration,
        domain, device_class and supported_features, nothing else). So this
        has to be checked after the fact.

        Two rules, both drawn from what the real entities look like. The
        bundled firmware's counter carries no device class and
        `state_class: total_increasing`; the two entities most likely to be
        picked by mistake sit on the other side of exactly one of those:

        - the speed sensor is `device_class: speed`, `state_class:
          measurement` - picked by accident on 2026-08-21, which produced
          three days of phantom zeros, because a speed reading falls back
          to 0 whenever the hamster stops and a counter that falls reads as
          a device reset;
        - the device's own distance sensor is `device_class: distance`,
          which looks plausible but reports kilometres that would then be
          multiplied by the wheel circumference a second time.

        A missing `state_class` is accepted: a hand-written template counter
        may legitimately set none, and rejecting those would be stricter
        than the problem warrants.
        """
        state = self.hass.states.get(entity_id)
        if state is None or state.state in SKIP_VALIDATION_STATES:
            return True
        if state.attributes.get(ATTR_DEVICE_CLASS) is not None:
            return False
        return state.attributes.get(ATTR_STATE_CLASS) != SensorStateClass.MEASUREMENT

    @callback
    def _entity_exists(self, entity_id: str) -> bool:
        """Return True if the entity is currently known to Home Assistant.

        A required source entity should exist by the time the entry is
        created - the EntitySelector already limits picks to existing
        entities, but this catches the rare case of an entity
        disappearing between rendering the form and submitting it. Unlike
        _is_numeric_state, this doesn't care about the *value* of the
        state (unknown/unavailable are fine, same as elsewhere) - only
        that Home Assistant knows about the entity at all.
        """
        return self.hass.states.get(entity_id) is not None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration: basic data about the hamster."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            name, errors = _validate_basics(user_input)

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
            elif not self._looks_like_a_counter(user_input[CONF_WHEEL_SENSOR]):
                errors[CONF_WHEEL_SENSOR] = "not_a_counter"
            if not self._entity_exists(user_input[CONF_TEMPERATURE_SENSOR]):
                errors[CONF_TEMPERATURE_SENSOR] = "entity_not_found"
            if user_input.get(CONF_DOOR_SENSOR) and not self._entity_exists(
                user_input[CONF_DOOR_SENSOR]
            ):
                errors[CONF_DOOR_SENSOR] = "entity_not_found"

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
                OPTION_LIFETIME_DISTANCE_KM,
                default=current.get(OPTION_LIFETIME_DISTANCE_KM, 0.0),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=MAX_LIFETIME_DISTANCE_KM,
                    step=0.001,
                    unit_of_measurement="km",
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
            # Sieben Felder rund um Benachrichtigungen, als eingeklappte
            # Section gruppiert wie die Käfigbeleuchtung unten - anders als
            # dort ist hier nichts an eine optionale Sensor-Auswahl
            # gebunden, es geht nur darum, das Formular nicht mit
            # Benachrichtigungs-Feldern zu überladen.
            vol.Required(NOTIFICATION_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            OPTION_WARNINGS_ENABLED,
                            default=current.get(
                                OPTION_WARNINGS_ENABLED, DEFAULT_WARNINGS_ENABLED
                            ),
                        ): BooleanSelector(),
                        vol.Required(
                            OPTION_DAILY_SUMMARY_ENABLED,
                            default=current.get(
                                OPTION_DAILY_SUMMARY_ENABLED,
                                DEFAULT_DAILY_SUMMARY_ENABLED,
                            ),
                        ): BooleanSelector(),
                        vol.Required(
                            OPTION_NOTIFICATION_TIME,
                            default=current.get(
                                OPTION_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME
                            ),
                        ): TimeSelector(),
                        # Teilt sich die Uhrzeit oben mit der
                        # Tageszusammenfassung - erinnert aber nur, wenn
                        # tatsächlich zu lange nicht gewogen wurde, siehe
                        # notify.py.
                        vol.Required(
                            OPTION_WEIGHT_REMINDER_ENABLED,
                            default=current.get(
                                OPTION_WEIGHT_REMINDER_ENABLED,
                                DEFAULT_WEIGHT_REMINDER_ENABLED,
                            ),
                        ): BooleanSelector(),
                        vol.Required(
                            OPTION_WEIGHT_REMINDER_DAYS,
                            default=current.get(
                                OPTION_WEIGHT_REMINDER_DAYS,
                                DEFAULT_WEIGHT_REMINDER_DAYS,
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_WEIGHT_REMINDER_DAYS,
                                max=MAX_WEIGHT_REMINDER_DAYS,
                                step=1,
                                unit_of_measurement="d",
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                        # Greift nur, wenn CONF_WEATHER_ENTITY gesetzt ist
                        # (siehe notify.py). Der Schwellwert meint die
                        # vorhergesagte Außen-Tageshöchsttemperatur, nicht
                        # die Käfigtemperatur.
                        vol.Required(
                            OPTION_HEAT_FORECAST_ENABLED,
                            default=current.get(
                                OPTION_HEAT_FORECAST_ENABLED,
                                DEFAULT_HEAT_FORECAST_ENABLED,
                            ),
                        ): BooleanSelector(),
                        vol.Required(
                            OPTION_HEAT_FORECAST_THRESHOLD_C,
                            default=current.get(
                                OPTION_HEAT_FORECAST_THRESHOLD_C,
                                DEFAULT_HEAT_FORECAST_THRESHOLD_C,
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_HEAT_FORECAST_THRESHOLD_C,
                                max=MAX_HEAT_FORECAST_THRESHOLD_C,
                                step=0.5,
                                unit_of_measurement="°C",
                                mode=NumberSelectorMode.BOX,
                            )
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            # Vier Felder, die nur greifen, wenn CONF_LIGHT_ENTITY gesetzt
            # ist (siehe door_light.py) - als eingeklappte Section, damit
            # sie das Formular nicht dominieren. Home Assistant liefert
            # ihre Werte dadurch verschachtelt zurück, siehe
            # _flatten_options() unten.
            vol.Required(LIGHT_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            OPTION_LIGHT_BRIGHTNESS_PCT,
                            default=current.get(
                                OPTION_LIGHT_BRIGHTNESS_PCT,
                                DEFAULT_LIGHT_BRIGHTNESS_PCT,
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
                                OPTION_LIGHT_TRANSITION_S,
                                DEFAULT_LIGHT_TRANSITION_S,
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
                                OPTION_LIGHT_TURN_OFF_ENABLED,
                                DEFAULT_LIGHT_TURN_OFF_ENABLED,
                            ),
                        ): BooleanSelector(),
                        vol.Required(
                            OPTION_LIGHT_TURN_OFF_DELAY_S,
                            default=current.get(
                                OPTION_LIGHT_TURN_OFF_DELAY_S,
                                DEFAULT_LIGHT_TURN_OFF_DELAY_S,
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
                ),
                {"collapsed": True},
            ),
        }
    )


_OPTION_SECTIONS = (LIGHT_SECTION, NOTIFICATION_SECTION)


def _flatten_options(user_input: dict[str, Any]) -> dict[str, Any]:
    """Merge every section's values back up into a flat options dict.

    A `section` in the schema means Home Assistant hands the values back
    nested under its own key. Everything that reads options at runtime
    (door_light.py, notify.py, the coordinator) expects them flat, and
    entries saved before this grouping existed are flat too - so the nest
    is undone here rather than teaching every reader about it.
    """
    flattened = {k: v for k, v in user_input.items() if k not in _OPTION_SECTIONS}
    for section_key in _OPTION_SECTIONS:
        flattened.update(user_input.get(section_key, {}))
    return flattened


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
            options = _flatten_options(user_input)
            if options[OPTION_IDEAL_TEMP_MIN] >= options[OPTION_IDEAL_TEMP_MAX]:
                errors["base"] = "invalid_temp_range"
            else:
                return self.async_create_entry(data=options)

        # Die Gesamtstrecke wird mit dem TATSÄCHLICHEN Stand vorbelegt, nicht
        # mit dem zuletzt eingetippten. Sonst zeigt das Feld eine alte
        # Korrektur an, und wer das Formular nur wegen einer anderen
        # Einstellung öffnet und speichert, würde die seither gelaufene
        # Strecke stillschweigend zurücksetzen.
        current = dict(self.config_entry.options)
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None and coordinator.data is not None:
            current[OPTION_LIFETIME_DISTANCE_KM] = coordinator.data.lifetime_distance_km

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
            errors=errors,
        )
