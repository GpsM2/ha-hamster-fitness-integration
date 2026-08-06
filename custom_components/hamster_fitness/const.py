"""Constants for the Hamster Fitness integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hamster_fitness"

# --- Config Flow: Stammdaten (Step "user") ---
CONF_HAMSTER_NAME: Final = "hamster_name"
CONF_ACQUISITION_DATE: Final = "acquisition_date"
CONF_WHEEL_DIAMETER: Final = "wheel_diameter"
CONF_BREED: Final = "breed"
# Freitext, nur ausgewertet wenn CONF_BREED == BREED_OTHER - für Mischlinge
# und Rassen, die nicht in der Liste stehen.
CONF_BREED_OTHER: Final = "breed_other"
CONF_COAT_COLOR: Final = "coat_color"

# --- Hamster-Profil: Rassen ---
# Symbolische Schlüssel statt Klartext, damit die Anzeige über
# strings.json/translations/*.json übersetzbar bleibt (Selector-Optionen
# unter "selector.breed.options.<key>").
BREED_GOLDEN: Final = "golden"
BREED_WINTER_WHITE: Final = "winter_white"
BREED_CAMPBELL: Final = "campbell"
BREED_ROBOROVSKI: Final = "roborovski"
BREED_CHINESE: Final = "chinese"
BREED_TEDDY: Final = "teddy"
BREED_OTHER: Final = "other"
BREEDS: Final[list[str]] = [
    BREED_GOLDEN,
    BREED_TEDDY,
    BREED_WINTER_WHITE,
    BREED_CAMPBELL,
    BREED_ROBOROVSKI,
    BREED_CHINESE,
    BREED_OTHER,
]
DEFAULT_BREED: Final = BREED_GOLDEN

# --- Hamster-Profil: Fellfarben ---
# Ebenfalls symbolische Schlüssel (übersetzbar), der Hex-Wert wird erst
# beim Rendern der Karten-Illustration aufgelöst - so lässt sich ein
# Farbton nachjustieren, ohne gespeicherte Config-Entries anzufassen.
COAT_COLOR_GOLDEN_BROWN: Final = "golden_brown"
COAT_COLOR_SILVER_GREY: Final = "silver_grey"
COAT_COLOR_CREAM_SAND: Final = "cream_sand"
COAT_COLOR_BLACK: Final = "black"
COAT_COLOR_HEX: Final[dict[str, str]] = {
    COAT_COLOR_GOLDEN_BROWN: "#D48C46",
    COAT_COLOR_SILVER_GREY: "#8A929A",
    COAT_COLOR_CREAM_SAND: "#E8D3A7",
    COAT_COLOR_BLACK: "#333333",
}
COAT_COLORS: Final[list[str]] = list(COAT_COLOR_HEX)
DEFAULT_COAT_COLOR: Final = COAT_COLOR_GOLDEN_BROWN

# --- Config Flow: Quell-Entitäten (Step "sensors") ---
CONF_WHEEL_SENSOR: Final = "wheel_sensor"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_DOOR_SENSOR: Final = "door_sensor"
# Optional - ohne diese beiden werden die entsprechenden Entities
# (Feuchtigkeit / aktuelle & maximale Geschwindigkeit) einfach nicht
# angelegt, siehe sensor.py.
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_SPEED_SENSOR: Final = "speed_sensor"
# Optional - ohne diese Entity bleibt die Käfigbeleuchtungs-Automatik
# einfach inaktiv, siehe door_light.py.
CONF_LIGHT_ENTITY: Final = "light_entity"
# Optional - eine number-Entity (typischerweise auf einem ESPHome-Gerät),
# an die CONF_WHEEL_DIAMETER bei jedem Setup/Reconfigure automatisch
# übertragen wird, siehe __init__.py's _async_sync_wheel_diameter(). Ohne
# diese Auswahl bleiben beide Werte komplett unabhängig voneinander -
# genauso, wie es vor Einführung dieses Felds für alle Hamster der Fall war.
CONF_WHEEL_DIAMETER_SYNC_ENTITY: Final = "wheel_diameter_sync_entity"
CONF_NOTIFY_SERVICES: Final = "notify_services"

# --- Defaults / Grenzwerte ---
# Hamsterräder werden im Handel immer über den Durchmesser angegeben, nicht
# den Umfang - daher fragt auch der Config Flow direkt danach (der Umfang
# wird intern via _wheel_circumference_cm = diameter * pi hergeleitet, siehe
# coordinator.py). Grenzen/Default sind bewusst identisch zum "Hamster Wheel
# Diameter"-Feld der ESPHome-Firmware (esphome/hamster-wheel-sensor.yaml),
# damit hier derselbe Zahlenwert eingetragen werden kann.
DEFAULT_WHEEL_DIAMETER_CM: Final[float] = 28.0
MIN_WHEEL_DIAMETER_CM: Final[float] = 10.0
MAX_WHEEL_DIAMETER_CM: Final[float] = 50.0

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
OPTION_WEIGHT_REMINDER_ENABLED: Final = "weight_reminder_enabled"
OPTION_WEIGHT_REMINDER_DAYS: Final = "weight_reminder_days"
# Nur wirksam, wenn CONF_LIGHT_ENTITY gesetzt ist, siehe door_light.py.
OPTION_LIGHT_BRIGHTNESS_PCT: Final = "light_brightness_pct"
OPTION_LIGHT_TRANSITION_S: Final = "light_transition_s"
OPTION_LIGHT_TURN_OFF_ENABLED: Final = "light_turn_off_enabled"
OPTION_LIGHT_TURN_OFF_DELAY_S: Final = "light_turn_off_delay_s"

# --- Options: Defaults ---
DEFAULT_IDEAL_TEMP_MIN: Final[float] = 20.0
DEFAULT_IDEAL_TEMP_MAX: Final[float] = 24.0
DEFAULT_MIN_DISTANCE_KM: Final[float] = 2.0
DEFAULT_WARNINGS_ENABLED: Final = True
DEFAULT_DAILY_SUMMARY_ENABLED: Final = True
DEFAULT_NOTIFICATION_TIME: Final = "08:00:00"
DEFAULT_WEIGHT_REMINDER_ENABLED: Final = False
DEFAULT_WEIGHT_REMINDER_DAYS: Final[int] = 7
MIN_WEIGHT_REMINDER_DAYS: Final[int] = 1
MAX_WEIGHT_REMINDER_DAYS: Final[int] = 90
DEFAULT_LIGHT_BRIGHTNESS_PCT: Final[int] = 100
DEFAULT_LIGHT_TRANSITION_S: Final[float] = 0.0
DEFAULT_LIGHT_TURN_OFF_ENABLED: Final = True
DEFAULT_LIGHT_TURN_OFF_DELAY_S: Final[float] = 0.0

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

# --- Aktivitäts-/Ruhe-Sensoren (night_active_duration / day_rest_duration) ---
# Wie lange eine Laufpause andauern darf, bevor eine Lauf-Session als
# beendet gilt (siehe coordinator.py's _calculate()). Kürzere Pausen
# (z. B. Trinken, Putzen) unterbrechen die Session nicht.
SESSION_END_GAP_MINUTES: Final[int] = 30

# --- Schlafphasen-Metrik (score_sleep) ---
# Hauptschlafphase eines dämmerungs-/nachtaktiven Hamsters. Störungen in
# diesem Fenster (Deckel öffnen, dadurch geweckt werden und ins Rad
# steigen) gelten als Stressfaktor und senken den Schlaf-Score, siehe
# coordinator.py's _sleep_penalty(). Die Grenzen liegen bewusst innerhalb
# des Tagesfensters (DAILY_RESET_HOUR = 9 Uhr), damit die Zähler genau
# einmal pro Tag - kurz vor Beginn der Schlafphase - zurückgesetzt werden.
SLEEP_PHASE_START_HOUR: Final[int] = 10
SLEEP_PHASE_END_HOUR: Final[int] = 17

# --- Score-Historie (Trend-Diagramm der Health-Score-Karte) ---
# Wie viele abgeschlossene Tage an Health-Scores rollierend vorgehalten
# werden (siehe coordinator.py's _record_daily_score()).
SCORE_HISTORY_DAYS: Final[int] = 7

# --- Licht-Automatik: Schalter & Pause ---
# Der Schalter switch.<hamster>_light_automation bildet den dauerhaften
# Wunsch ab ("Automatik grundsätzlich an/aus"). Die Pause ist davon
# unabhängig und temporär: sie überspringt das automatische Schalten für
# eine begrenzte Zeit und läuft danach von selbst wieder aus - gedacht für
# "ich mache jetzt den Käfig sauber und will nicht, dass das Licht bei
# jedem Deckelheben an- und ausgeht". Siehe door_light.py.
SERVICE_PAUSE_LIGHT_AUTOMATION: Final = "pause_light_automation"
ATTR_DURATION_MINUTES: Final = "duration_minutes"
DEFAULT_LIGHT_PAUSE_MINUTES: Final[int] = 30
MAX_LIGHT_PAUSE_MINUTES: Final[int] = 1440

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
    Platform.SWITCH,
]

# --- Gewicht ---
MIN_WEIGHT_G: Final[float] = 0.0
MAX_WEIGHT_G: Final[float] = 2000.0

# --- Frontend (bundled hamster-fitness-card, siehe frontend/__init__.py) ---
URL_BASE: Final = f"/{DOMAIN}-frontend"
# Cache-Busting für hamster-fitness-shared.js. Das Modul ist KEINE eigene
# Lovelace-Ressource, sondern wird von den Karten per relativer URL
# importiert - es bekommt also nicht automatisch das ?v=... der Karten
# unten. Ohne eigene Version lädt der Browser weiter seine alte Kopie,
# und sobald dort ein neu hinzugekommener Export fehlt, bricht der Import
# ab: dann registriert sich KEINE der Karten mehr, auch die unveränderten
# nicht (in 0.3.0-beta.1 genau so passiert).
#
# Bei jeder Änderung an hamster-fitness-shared.js hochzählen UND denselben
# Wert in den ?v=-Importen aller Kartendateien nachziehen. tests/
# test_frontend_resources.py prüft das ab, damit es nicht vergessen wird.
SHARED_MODULE_VERSION: Final = "2"
# "version" steuert das Cache-Busting (?v=...) der Lovelace-Resource - bei
# jeder inhaltlichen Änderung an der .js-Datei hochzählen, sonst laden
# Browser ggf. die alte, gecachte Version weiter aus.
JS_MODULES: Final[list[dict[str, str]]] = [
    {
        "name": "Hamster Fitness Card",
        "filename": "hamster-fitness-card.js",
        "version": "8",
    },
    {
        "name": "Hamster Day & Night Card",
        "filename": "hamster-day-night-card.js",
        "version": "3",
    },
    {
        "name": "Hamster Chronicle Card",
        "filename": "hamster-chronicle-card.js",
        "version": "2",
    },
]
