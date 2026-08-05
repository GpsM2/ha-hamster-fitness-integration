"""Constants for the Hamster Fitness integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hamster_fitness"

# --- Config Flow: Stammdaten (Step "user") ---
CONF_HAMSTER_NAME: Final = "hamster_name"
CONF_ACQUISITION_DATE: Final = "acquisition_date"
CONF_WHEEL_CIRCUMFERENCE: Final = "wheel_circumference"

# --- Config Flow: Quell-Entitäten (Step "sensors") ---
CONF_WHEEL_SENSOR: Final = "wheel_sensor"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_DOOR_SENSOR: Final = "door_sensor"
CONF_NOTIFY_SERVICES: Final = "notify_services"

# --- Defaults / Grenzwerte ---
DEFAULT_WHEEL_CIRCUMFERENCE_CM: Final[float] = 28.0  # Ø 9 cm Laufrad
MIN_WHEEL_CIRCUMFERENCE_CM: Final[float] = 1.0
MAX_WHEEL_CIRCUMFERENCE_CM: Final[float] = 100.0

# Zustände, bei denen eine numerische Validierung übersprungen wird
# (Entität ist evtl. nur temporär nicht verfügbar).
SKIP_VALIDATION_STATES: Final[set[str]] = {"unknown", "unavailable"}

# --- Options Flow: Expertenmenü ---
OPTION_IDEAL_TEMP_MIN: Final = "ideal_temp_min"
OPTION_IDEAL_TEMP_MAX: Final = "ideal_temp_max"
OPTION_MIN_DISTANCE_KM: Final = "min_distance_km"
OPTION_WARNINGS_ENABLED: Final = "warnings_enabled"
OPTION_DAILY_SUMMARY_ENABLED: Final = "daily_summary_enabled"
OPTION_NOTIFICATION_TIME: Final = "notification_time"

# --- Options: Defaults ---
DEFAULT_IDEAL_TEMP_MIN: Final[float] = 20.0
DEFAULT_IDEAL_TEMP_MAX: Final[float] = 24.0
DEFAULT_MIN_DISTANCE_KM: Final[float] = 2.0
DEFAULT_WARNINGS_ENABLED: Final = True
DEFAULT_DAILY_SUMMARY_ENABLED: Final = True
DEFAULT_NOTIFICATION_TIME: Final = "08:00:00"

# --- Health-Score-Parameter (fest, nicht über Options konfigurierbar) ---
# Ab dieser Tagesstrecke gibt es keinen Strecken-Punktabzug mehr.
IDEAL_DISTANCE_MIN_KM: Final[float] = 5.0
# Rein informativ (z. B. für UI/Attribute) - oberes Ende der "idealen" Spanne.
IDEAL_DISTANCE_MAX_KM: Final[float] = 10.0
# Pufferbreite zwischen Ideal- und "harter" Temperaturgrenze
# (Default: 20-24 °C ideal, Puffer 2 °C -> harte Grenzen bei 18/26 °C).
TEMP_BUFFER_C: Final[float] = 2.0
# Deckel/Käfig gilt ab dieser Dauer als vernachlässigt.
NEGLECT_THRESHOLD_HOURS: Final[float] = 48.0
# Health-Score-Schwelle, unterhalb derer binary_sensor.<hamster>_warning angeht.
WARNING_SCORE_THRESHOLD: Final[int] = 50

# --- Tages-Reset-Metrik ---
# Der Tages-Distanzzähler (sensor.<hamster>_daily_distance) wird nicht um
# Mitternacht zurückgesetzt, sondern erst zu dieser lokalen Uhrzeit (nicht
# per Options konfigurierbar, siehe Notiz in coordinator.py) - Hamster sind
# nachtaktiv, ein Reset um 00 Uhr würde eine einzelne, zusammenhängende
# Laufphase mitten in der Nacht künstlich auf zwei Kalendertage aufteilen.
# 9 Uhr morgens liegt sicher nach dem typischen Aktivitätsende.
DAILY_RESET_HOUR: Final[int] = 9

# --- Nachtfenster-Metrik ---
# "Nachts gelaufen" wird ab dieser lokalen Uhrzeit gezählt (nicht per
# Options konfigurierbar, siehe Notiz in coordinator.py). Hamster sind
# dämmerungs-/nachtaktiv - 20 Uhr bis zum nächsten Reset um 20 Uhr deckt
# die typische Aktivitätsphase ab.
NIGHT_WINDOW_START_HOUR: Final[int] = 20

# --- Storage ---
STORAGE_VERSION: Final[int] = 1

# --- Benachrichtigungen ---
NOTIFY_DOMAIN: Final = "notify"
NOTIFY_SERVICE_SEND_MESSAGE: Final = "send_message"
# Abklingzeit, bevor derselbe Warngrund erneut gesendet werden darf.
WARNING_NOTIFICATION_COOLDOWN_HOURS: Final[float] = 4.0

# --- Plattformen ---
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DATE,
    Platform.NUMBER,
]

# --- Gewicht ---
MIN_WEIGHT_G: Final[float] = 0.0
MAX_WEIGHT_G: Final[float] = 2000.0
