/**
 * Shared helpers for the Hamster Fitness card family
 * (hamster-fitness-card.js, hamster-day-night-card.js,
 * hamster-chronicle-card.js). Split out so the entity/device lookup logic
 * - fixed once already for non-English Home Assistant installs (see
 * siblingEntityId() below) - exists in exactly one place instead of being
 * duplicated across card files.
 *
 * IMPORTANT: this module is NOT a Lovelace resource. The cards import it
 * by relative URL with an explicit `?v=` (see SHARED_MODULE_VERSION in
 * const.py). Any change here means bumping that version *and* the query
 * in every importer - otherwise browsers keep an older copy, the import
 * fails, and every card silently stops registering. That is not
 * hypothetical; it happened in 0.3.0-beta.1.
 * tests/test_frontend_resources.py enforces it.
 */

export const HAMSTER_PREFIX = /^hamster_/;

export const DEFAULT_FUR = "#D48C46";

/**
 * Card text, in the two languages this integration ships.
 *
 * These deliberately do NOT come from strings.json. Home Assistant only
 * loads a fixed set of translation categories into the frontend (entity
 * names, config flow, services, ...), and card labels fit none of them;
 * `hass.localize` therefore cannot reach a custom category. Python-side
 * runtime text solves the same problem the other way round, through
 * runtime_text.py - see its module docstring.
 *
 * English is the source and the fallback: an unknown language, or a key
 * missing from a translation, falls back to the English string.
 */
const STRINGS = {
  en: {
    // Shared
    "common.online": "Online",
    "common.offline": "Offline",
    "common.unavailable": "Unavailable",
    "common.notFound":
      'Entity "{entity}" not found. Check the card configuration.',
    "common.optionalTitle": "Title (optional)",
    "common.entityPicker": "The hamster's health score sensor",
    "common.needEntity":
      "{card}: 'entity' is missing - please pick a hamster's health score sensor (ends in _health_score).",
    "common.wrongEntity":
      "{card}: 'entity' must be a hamster's health score sensor (the entity ID ends in _health_score).",

    // Day & Night card
    "dayNight.subtitle": "Day &amp; Night",
    "dayNight.runningFor": "Running for",
    "dayNight.restingFor": "Resting for",
    "dayNight.speed": "Speed",
    "dayNight.thisNight": "This night",
    "dayNight.climate": "Climate",
    "dayNight.cageLight": "Cage light",
    "dayNight.lightOn": "Light on",
    "dayNight.lightOff": "Light off",
    "dayNight.automationOff": "Automation off",
    "dayNight.pausedUntil": "Paused until {time}",
    "dayNight.pauseButton": "Pause 30 min",
    "dayNight.lidOpen": "Lid open",
    "dayNight.pickerName": "Hamster Fitness: Day & Night",
    "dayNight.pickerDescription":
      "The hamster animated in its wheel while active, or asleep in its nest while resting - under a sky that follows the sun, with the readings inside the scene.",
    "dayNight.showSpeed": "Show speed",
    "dayNight.showDistance": "Show night distance",
    "dayNight.showActive": "Show running time",
    "dayNight.showRest": "Show resting time",
    "dayNight.showClimate": "Show temperature/humidity",
    "dayNight.showLight": "Show cage light (with pause button)",

    // Health score card
    "health.badgeVital": "Fully fit",
    "health.badgeWatch": "Keep an eye on it",
    "health.badgeVet": "See a vet",
    "health.badgeUnknown": "Unknown",
    "health.fallbackSubtitle": "Health Score",
    "health.departed": "moved out",
    "health.withYouDays": "with you for {count} day",
    "health.withYouDays_plural": "with you for {count} days",
    "health.withYouMonths": "with you for {count} month",
    "health.withYouMonths_plural": "with you for {count} months",
    "health.withYouYears": "with you for {count} years",
    "health.ringScore": "Health Score",
    "health.ringSpeed": "Speed",
    "health.previewNote": "Preview with sample data",
    "health.insightGoodTonight":
      "All good - {distance} run so far tonight.",
    "health.insightGood":
      "All good - last full night of running: {distance}.",
    "health.insightGoodPlain": "All good - nothing out of the ordinary.",
    "health.insightMiddling":
      "Nothing acutely wrong, but the score is below its usual level - the four pillars below show where it comes from.",
    "health.insightMock": "All good - ran 6.1 km last night.",
    "health.trend": "7-day trend",
    "health.trendAvg": "avg {value}",
    "health.trendUp": "+{delta} vs. average",
    "health.trendDown": "{delta} vs. average",
    "health.trendSame": "same as average",
    "health.trendEmpty":
      "No completed days yet - the first value appears tomorrow at 9 AM.",
    "health.tipLabel": "Worth knowing",
    "health.openHistory": "Open history",
    "health.close": "Close",
    "health.detailsFor": "{pillar} - show details",
    "health.pickerName": "Hamster Fitness: Health Score",
    "health.pickerDescription":
      "Health score as a ring, a plain-language insight, the four pillars of health to tap through, and a 7-day trend.",
    "health.maxSpeed": "Scale of the speed ring (km/h)",
    "health.showSpeed": "Show speed ring",
    "health.showPillars": "Show the four pillars",
    "health.showTrend": "Show 7-day trend",

    // Pillars
    "pillar.activity": "Activity",
    "pillar.activityLong": "Activity & stamina",
    "pillar.activityTip":
      "Hamsters instinctively hide illness for as long as they can. A sudden drop of more than 30% in nightly running distance is often the very first sign - watch the trend, not a single night.",
    "pillar.activityNight": "This night",
    "pillar.activityLast": "Last full night",
    "pillar.activityIdeal": "Ideal",
    "pillar.sleep": "Sleep",
    "pillar.sleepLong": "Sleep & rest quality",
    "pillar.sleepTip":
      "Hamsters are crepuscular and nocturnal. Disturbing their main sleep phase (10:00-17:00) with light, vibration or cage openings causes chronic stress and weakens the immune system.",
    "pillar.sleepOpenings": "Cage opened (sleeping hours)",
    "pillar.sleepWakeups": "Woke up and ran",
    "pillar.sleepPhase": "Sleep phase",
    "pillar.sleepPhaseValue": "{from}–{to}",
    "pillar.climate": "Climate",
    "pillar.climateLong": "Climate & environment",
    "pillar.climateTip":
      "Ideal is 18-22 °C at 40-60% humidity. Below 15 °C there is a risk of life-threatening torpor, above 24 °C of heat stroke.",
    "pillar.climateTemperature": "Temperature",
    "pillar.climateHumidity": "Humidity",
    "pillar.care": "Care",
    "pillar.careLong": "Care & interaction",
    "pillar.careTip":
      "Measured via the lid/door sensor: how regularly the cage is opened for feeding and cleaning. One or two short openings in the late evening are best; frequent opening during the day is better avoided.",
    "pillar.careClosedFor": "Lid shut for",
    "pillar.careLidNow": "Lid right now",
    "pillar.careLidOpen": "open",
    "pillar.careLidClosed": "closed",
    "pillar.careNeglectFrom": "Counts as neglected from",

    // Weighing card
    "weight.subtitle": "Track Weight",
    "weight.pickerName": "Hamster Fitness: Track Weight",
    "weight.pickerDescription":
      "Enter your hamster's weight on an illustrated balance scale - counterweights stack up and the hamster gets rounder as the number rises.",
    "weight.weighedToday": "Weighed today",
    "weight.weighedDaysAgo": "Weighed {count} day ago",
    "weight.weighedDaysAgo_plural": "Weighed {count} days ago",
    "weight.neverWeighed": "No weight recorded yet - type the first one below.",
    "weight.enterWeight": "Enter weight",
    "weight.save": "Save",
    "weight.cancel": "Cancel",
    "weight.typeIt": "Type a weight",
    "weight.step": "Grams per tap",
    "weight.status.underweight": "Underweight",
    "weight.status.normal": "Healthy weight",
    "weight.status.overweight": "Overweight",
    "weight.noBreedRange": "No reference range for this breed",

    // Ranking card
    "ranking.title": "Hamster ranking",
    "ranking.subtitle": "By distance run",
    "ranking.total": "Total",
    "ranking.perDay": "Per day",
    "ranking.count": "{count} hamster",
    "ranking.count_plural": "{count} hamsters",
    "ranking.empty":
      "No Hamster Fitness hamsters found (no sensor.hamster_<name>_lifetime_distance in this Home Assistant).",
    "ranking.pickerName": "Hamster Fitness: Ranking",
    "ranking.pickerDescription":
      "Compares every hamster in this Home Assistant by lifetime distance - found automatically, no configuration needed.",

    // Running card
    "running.title": "Running",
    "running.subtitle": "Last 7 nights",
    "running.weekTotal": "{value} this week",
    "running.empty":
      "No completed nights recorded yet. The first bar appears after tonight's window closes.",
    "running.distance": "Distance",
    "running.avgSpeed": "Average speed",
    "running.goal": "Goal",
    "running.average": "Average",
    "running.temperature": "Temperature",
    "running.humidity": "Humidity",
    "running.sessions": "Runs per night (in the bar)",
    "running.records": "Personal bests",
    "running.bestNight": "Longest night",
    "running.fastest": "Fastest ever",
    "running.noRecord": "Not set yet",
    "running.pickerName": "Hamster Fitness: Running",
    "running.pickerDescription":
      "One bar per night for the last week, with average speed, your distance goal and personal bests - plus optional climate overlays.",

    // Chronicle card
    "chronicle.title": "Hamster chronicle",
    "chronicle.subtitle": "Overview",
    "chronicle.count": "{count} hamster",
    "chronicle.count_plural": "{count} hamsters",
    "chronicle.since": "since {date}",
    "chronicle.unknownPeriod": "Period unknown",
    "chronicle.movedOut": "moved out",
    "chronicle.archived": "Archive",
    "chronicle.empty":
      "No hamsters yet. As soon as one is set up it appears here - and stays in the chronicle after it moves out.",
    "chronicle.archiveFailed":
      "The lifetime archive could not be loaded - only currently configured hamsters are shown.",
    "chronicle.columns": "Stats to show",
    "chronicle.colDistance": "Lifetime distance",
    "chronicle.colTopSpeed": "Top speed",
    "chronicle.colDays": "Days with you",
    "chronicle.colScore": "Health Score",
    "chronicle.pickerName": "Hamster Fitness: Chronicle",
    "chronicle.pickerDescription":
      "Every hamster in this Home Assistant at a glance - current and long departed, with their dates and the stats you choose.",
    "chronicle.addPast": "Add past hamster",
    "chronicle.addPastTitle": "Add a past hamster",
    "chronicle.addPastDescription":
      "For a hamster from before this integration existed - no sensors, no health score, just the record.",
    "chronicle.editPast": "Edit",
    "chronicle.editPastTitle": "Edit hamster",
    "chronicle.editPastDescription": "Update this hamster's record.",
    "chronicle.fieldName": "Name",
    "chronicle.fieldBreed": "Breed",
    "chronicle.fieldBreedOther": "Breed (if \"Other\")",
    "chronicle.fieldCoatColor": "Coat colour",
    "chronicle.fieldAcquisitionDate": "Move-in date",
    "chronicle.fieldDepartureDate": "Move-out date",
    "chronicle.save": "Save",
    "chronicle.cancel": "Cancel",
    "chronicle.delete": "Delete",
    "chronicle.deleteConfirmBody":
      "This removes this entry from the chronicle for good. This can't be undone.",
    "chronicle.deleteConfirmYes": "Yes, delete",
    "chronicle.nameRequired": "Enter a name.",
    "chronicle.breedOtherRequired": "Describe the breed.",
    "chronicle.datesRequired": "Enter both the move-in and move-out date.",
    "chronicle.addPastFailed": "Could not save - please try again.",
    "chronicle.deleteFailed": "Could not delete - please try again.",

    "coatColor.golden_brown": "Golden brown",
    "coatColor.silver_grey": "Silver grey",
    "coatColor.cream_sand": "Cream / sand",
    "coatColor.black": "Black / dark",

    // Breeds (mirrors const.py's BREEDS)
    "breed.golden": "Syrian / golden hamster",
    "breed.teddy": "Teddy bear hamster",
    "breed.winter_white": "Winter white dwarf hamster",
    "breed.campbell": "Campbell's dwarf hamster",
    "breed.roborovski": "Roborovski dwarf hamster",
    "breed.chinese": "Chinese hamster",
    "breed.other": "Other",
  },

  de: {
    "common.online": "Online",
    "common.offline": "Offline",
    "common.unavailable": "Nicht verfügbar",
    "common.notFound":
      'Entity "{entity}" nicht gefunden. Prüfe die Karten-Konfiguration.',
    "common.optionalTitle": "Titel (optional)",
    "common.entityPicker": "Health-Score-Sensor des Hamsters",
    "common.needEntity":
      "{card}: 'entity' fehlt - bitte den Health-Score-Sensor eines Hamsters auswählen (endet auf _health_score).",
    "common.wrongEntity":
      "{card}: 'entity' muss der Health-Score-Sensor eines Hamsters sein (Entity-ID endet auf _health_score).",

    "dayNight.runningFor": "Läuft seit",
    "dayNight.restingFor": "Ruht seit",
    "dayNight.speed": "Geschwindigkeit",
    "dayNight.thisNight": "Diese Nacht",
    "dayNight.climate": "Klima",
    "dayNight.cageLight": "Käfiglicht",
    "dayNight.lightOn": "Licht an",
    "dayNight.lightOff": "Licht aus",
    "dayNight.automationOff": "Automatik aus",
    "dayNight.pausedUntil": "Pause bis {time}",
    "dayNight.pauseButton": "30 Min. Pause",
    "dayNight.lidOpen": "Deckel offen",
    "dayNight.pickerDescription":
      "Zeigt den Hamster animiert im Laufrad (aktiv) oder schlafend im Nest (ruhend), mit sonnenstand-abhängigem Himmel und den Messwerten direkt in der Szene.",
    "dayNight.showSpeed": "Geschwindigkeit anzeigen",
    "dayNight.showDistance": "Nachtdistanz anzeigen",
    "dayNight.showActive": "Lauf-Dauer anzeigen",
    "dayNight.showRest": "Ruhezeit anzeigen",
    "dayNight.showClimate": "Temperatur/Luftfeuchtigkeit anzeigen",
    "dayNight.showLight": "Käfiglicht anzeigen (mit Pause-Button)",

    "health.badgeVital": "Voll vital",
    "health.badgeWatch": "Beobachten",
    "health.badgeVet": "Tierarzt prüfen",
    "health.badgeUnknown": "Unbekannt",
    "health.departed": "ausgezogen",
    "health.withYouDays": "seit {count} Tag bei dir",
    "health.withYouDays_plural": "seit {count} Tagen bei dir",
    "health.withYouMonths": "seit {count} Monat bei dir",
    "health.withYouMonths_plural": "seit {count} Monaten bei dir",
    "health.withYouYears": "seit {count} Jahren bei dir",
    "health.ringSpeed": "Geschwindigkeit",
    "health.previewNote": "Vorschau mit Beispieldaten",
    "health.insightGoodTonight":
      "Alles im grünen Bereich - heute Nacht bisher {distance} gelaufen.",
    "health.insightGood":
      "Alles im grünen Bereich - letzte volle Nacht: {distance}.",
    "health.insightGoodPlain":
      "Alles im grünen Bereich - keine Auffälligkeiten.",
    "health.insightMiddling":
      "Nichts akut Auffälliges, aber der Score liegt unter dem üblichen Niveau - die vier Säulen unten zeigen, woran es hängt.",
    "health.insightMock":
      "Alles im grünen Bereich - gestern Nacht 6,1 km gelaufen.",
    "health.trend": "7-Tage-Trend",
    "health.trendAvg": "Ø {value}",
    "health.trendUp": "+{delta} ggü. Schnitt",
    "health.trendDown": "{delta} ggü. Schnitt",
    "health.trendSame": "wie im Schnitt",
    "health.trendEmpty":
      "Noch keine abgeschlossenen Tage - der erste Wert erscheint morgen früh um 9 Uhr.",
    "health.tipLabel": "Gut zu wissen",
    "health.openHistory": "Verlauf öffnen",
    "health.close": "Schließen",
    "health.detailsFor": "{pillar} - Details anzeigen",
    "health.pickerDescription":
      "Health Score als Ring, verständlicher Hinweistext, die vier Säulen der Gesundheit zum Antippen und ein 7-Tage-Trend.",
    "health.maxSpeed": "Skala des Geschwindigkeits-Rings (km/h)",
    "health.showSpeed": "Geschwindigkeits-Ring anzeigen",
    "health.showPillars": "Die vier Säulen anzeigen",
    "health.showTrend": "7-Tage-Trend anzeigen",

    "pillar.activity": "Aktivität",
    "pillar.activityLong": "Aktivität & Ausdauer",
    "pillar.activityTip":
      "Hamster verbergen Krankheit instinktiv so lange wie möglich. Ein plötzlicher Einbruch der nächtlichen Laufstrecke um mehr als 30 % ist oft das allererste Anzeichen - achte auf den Trend, nicht auf eine einzelne Nacht.",
    "pillar.activityNight": "Diese Nacht",
    "pillar.activityLast": "Letzte volle Nacht",
    "pillar.activityIdeal": "Ideal",
    "pillar.sleep": "Schlaf",
    "pillar.sleepLong": "Schlaf & Ruhequalität",
    "pillar.sleepTip":
      "Hamster sind dämmerungs- und nachtaktiv. Wird ihre Hauptschlafphase (10:00-17:00 Uhr) durch Licht, Erschütterungen oder Käfigöffnungen gestört, entsteht chronischer Stress und das Immunsystem leidet.",
    "pillar.sleepOpenings": "Käfig geöffnet (Schlafzeit)",
    "pillar.sleepWakeups": "Aufgewacht und gelaufen",
    "pillar.sleepPhase": "Schlafphase",
    "pillar.sleepPhaseValue": "{from}–{to} Uhr",
    "pillar.climate": "Klima",
    "pillar.climateLong": "Klima & Umgebung",
    "pillar.climateTip":
      "Ideal sind 18-22 °C bei 40-60 % Luftfeuchtigkeit. Unter 15 °C droht lebensgefährliche Kältestarre, über 24 °C Hitzschlag.",
    "pillar.climateTemperature": "Temperatur",
    "pillar.climateHumidity": "Luftfeuchtigkeit",
    "pillar.care": "Pflege",
    "pillar.careLong": "Pflege & Interaktion",
    "pillar.careTip":
      "Gemessen über den Deckel-/Türsensor: wie regelmäßig der Käfig zum Füttern und Reinigen geöffnet wird. Am besten 1-2 kurze Öffnungen am späten Abend; häufiges Öffnen tagsüber besser vermeiden.",
    "pillar.careClosedFor": "Deckel zu seit",
    "pillar.careLidNow": "Deckel gerade",
    "pillar.careLidOpen": "offen",
    "pillar.careLidClosed": "geschlossen",
    "pillar.careNeglectFrom": "Als vernachlässigt ab",

    "weight.subtitle": "Gewicht erfassen",
    "weight.weighedToday": "Heute gewogen",
    "weight.weighedDaysAgo": "Vor {count} Tag gewogen",
    "weight.weighedDaysAgo_plural": "Vor {count} Tagen gewogen",
    "weight.neverWeighed": "Noch kein Gewicht erfasst - den ersten Wert unten eintippen.",
    "weight.enterWeight": "Gewicht eingeben",
    "weight.save": "Speichern",
    "weight.cancel": "Abbrechen",
    "weight.typeIt": "Wert eintippen",
    "weight.pickerName": "Hamster Fitness: Gewicht erfassen",
    "weight.pickerDescription":
      "Gewicht des Hamsters auf einer illustrierten Balkenwaage eintragen - mit steigendem Wert stapeln sich die Gegengewichte und der Hamster wird runder.",
    "weight.step": "Gramm pro Tastendruck",
    "weight.status.underweight": "Untergewicht",
    "weight.status.normal": "Normalgewicht",
    "weight.status.overweight": "Übergewicht",
    "weight.noBreedRange": "Kein Referenzbereich für diese Rasse",

    "ranking.title": "Hamster-Ranking",
    "ranking.subtitle": "Nach gelaufener Strecke",
    "ranking.total": "Gesamt",
    "ranking.perDay": "Pro Tag",
    "ranking.count": "{count} Hamster",
    "ranking.count_plural": "{count} Hamster",
    "ranking.empty":
      "Keine Hamster-Fitness-Hamster gefunden (kein sensor.hamster_<name>_lifetime_distance in diesem Home Assistant).",
    "ranking.pickerDescription":
      "Vergleicht alle Hamster in diesem Home Assistant nach Lebenszeit-Distanz - erkennt sie automatisch, keine Konfiguration nötig.",

    "running.title": "Laufleistung",
    "running.subtitle": "Letzte 7 Nächte",
    "running.weekTotal": "{value} diese Woche",
    "running.empty":
      "Noch keine abgeschlossene Nacht aufgezeichnet. Der erste Balken erscheint, sobald das heutige Nachtfenster endet.",
    "running.distance": "Strecke",
    "running.avgSpeed": "Ø-Geschwindigkeit",
    "running.goal": "Ziel",
    "running.average": "Durchschnitt",
    "running.temperature": "Temperatur",
    "running.humidity": "Luftfeuchtigkeit",
    "running.sessions": "Läufe pro Nacht (im Balken)",
    "running.records": "Bestleistungen",
    "running.bestNight": "Längste Nacht",
    "running.fastest": "Schnellster Wert",
    "running.noRecord": "Noch keine",
    "running.pickerName": "Hamster Fitness: Laufleistung",
    "running.pickerDescription":
      "Ein Balken pro Nacht der letzten Woche, mit Ø-Geschwindigkeit, deinem Streckenziel und Bestleistungen - dazu optionale Klima-Überlagerungen.",

    "chronicle.title": "Hamster-Chronik",
    "chronicle.subtitle": "Gesamtübersicht",
    "chronicle.count": "{count} Hamster",
    "chronicle.count_plural": "{count} Hamster",
    "chronicle.since": "seit {date}",
    "chronicle.unknownPeriod": "Zeitraum unbekannt",
    "chronicle.movedOut": "ausgezogen",
    "chronicle.archived": "Archiv",
    "chronicle.empty":
      "Noch keine Hamster gefunden. Sobald ein Hamster eingerichtet ist, taucht er hier auf - und bleibt auch nach dem Auszug in der Chronik.",
    "chronicle.archiveFailed":
      "Das Lebenslauf-Archiv konnte nicht geladen werden - es werden nur aktuell eingerichtete Hamster angezeigt.",
    "chronicle.columns": "Angezeigte Kennzahlen",
    "chronicle.colDistance": "Gesamtdistanz",
    "chronicle.colTopSpeed": "Topspeed",
    "chronicle.colDays": "Tage bei dir",
    "chronicle.colScore": "Health Score",
    "chronicle.pickerName": "Hamster Fitness: Chronik",
    "chronicle.pickerDescription":
      "Alle Hamster dieses Home Assistant auf einen Blick - aktuelle und längst ausgezogene, mit Zeitraum und wählbaren Kennzahlen.",
    "chronicle.addPast": "Vergangenen Hamster nachtragen",
    "chronicle.addPastTitle": "Vergangenen Hamster nachtragen",
    "chronicle.addPastDescription":
      "Für einen Hamster von vor dieser Integration - ohne Sensoren, ohne Health Score, nur der Eintrag.",
    "chronicle.editPast": "Bearbeiten",
    "chronicle.editPastTitle": "Hamster bearbeiten",
    "chronicle.editPastDescription": "Diesen Eintrag aktualisieren.",
    "chronicle.fieldName": "Name",
    "chronicle.fieldBreed": "Rasse",
    "chronicle.fieldBreedOther": "Rasse (bei „Sonstige“)",
    "chronicle.fieldCoatColor": "Fellfarbe",
    "chronicle.fieldAcquisitionDate": "Einzugsdatum",
    "chronicle.fieldDepartureDate": "Auszugsdatum",
    "chronicle.save": "Speichern",
    "chronicle.cancel": "Abbrechen",
    "chronicle.delete": "Löschen",
    "chronicle.deleteConfirmBody":
      "Dadurch wird dieser Eintrag endgültig aus der Chronik entfernt. Das lässt sich nicht rückgängig machen.",
    "chronicle.deleteConfirmYes": "Ja, löschen",
    "chronicle.nameRequired": "Bitte einen Namen eingeben.",
    "chronicle.breedOtherRequired": "Bitte die Rasse beschreiben.",
    "chronicle.datesRequired": "Bitte Einzugs- und Auszugsdatum eingeben.",
    "chronicle.addPastFailed": "Konnte nicht gespeichert werden - bitte erneut versuchen.",
    "chronicle.deleteFailed": "Konnte nicht gelöscht werden - bitte erneut versuchen.",

    "coatColor.golden_brown": "Goldbraun",
    "coatColor.silver_grey": "Silbergrau",
    "coatColor.cream_sand": "Creme / Sand",
    "coatColor.black": "Schwarz / Dunkel",

    "breed.golden": "Goldhamster (Syrer)",
    "breed.teddy": "Teddyhamster",
    "breed.winter_white": "Dsungarischer Zwerghamster",
    "breed.campbell": "Campbell-Zwerghamster",
    "breed.roborovski": "Roborowski-Zwerghamster",
    "breed.chinese": "Chinesischer Zwerghamster",
    "breed.other": "Sonstige",
  },
};

/**
 * The active language, as a bare code ("de" from "de-DE").
 *
 * `hass` is not always there: `setConfig()` runs before it is assigned,
 * and the card picker entries are built at module load. The browser's own
 * language is the sensible stand-in for those - better than defaulting a
 * German user to English on the one screen where something went wrong.
 */
export function languageOf(hass) {
  const raw =
    (hass && (hass.language || (hass.locale && hass.locale.language))) ||
    (typeof navigator !== "undefined" && navigator.language) ||
    "en";
  return String(raw).toLowerCase().split("-")[0];
}

/** Full locale tag for Intl formatting ("de-DE" stays "de-DE"). */
export function localeOf(hass) {
  return (
    (hass && (hass.language || (hass.locale && hass.locale.language))) ||
    (typeof navigator !== "undefined" && navigator.language) ||
    "en"
  );
}

/**
 * Translated card text. `count` triggers plural selection via the
 * `<key>_plural` variant; every placeholder is `{name}`.
 */
export function t(hass, key, vars = {}) {
  const lang = languageOf(hass);
  const table = STRINGS[lang] || {};
  let lookup = key;
  if (vars.count !== undefined && vars.count !== 1) {
    const plural = `${key}_plural`;
    if (table[plural] || STRINGS.en[plural]) lookup = plural;
  }
  let text = table[lookup];
  if (text === undefined) text = STRINGS.en[lookup];
  if (text === undefined) text = STRINGS.en[key];
  if (text === undefined) return key;
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    vars[name] === undefined ? match : String(vars[name])
  );
}

/** Number in the active locale, so decimals aren't hardcoded to a comma. */
export function fmtNumber(hass, value, decimals, unit) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return "–";
  }
  const text = Number(value).toLocaleString(localeOf(hass), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return unit ? `${text} ${unit}` : text;
}

/** "1h 15m" / "45m" - compact enough to fit in a chip in any language. */
export function fmtDuration(hass, minutes) {
  if (minutes === undefined || minutes === null || Number.isNaN(Number(minutes))) {
    return "–";
  }
  const total = Math.max(0, Math.round(Number(minutes)));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return hours > 0 ? `${hours}h ${rest}m` : `${rest}m`;
}

export function fmtTime(hass, isoString) {
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return "–";
  return parsed.toLocaleTimeString(localeOf(hass), {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDate(hass, isoString) {
  if (!isoString) return null;
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString(localeOf(hass), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Two-letter weekday for the trend chart's axis. */
export function fmtWeekday(hass, isoString) {
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return "?";
  return parsed
    .toLocaleDateString(localeOf(hass), { weekday: "short" })
    .slice(0, 2);
}

/**
 * The card header, shared verbatim by the Day & Night and health-score
 * cards so the two genuinely match instead of drifting apart. Both render
 * it on a coloured banner, hence the light-on-dark styling.
 */
export function renderCardHeader({ logoSvg, title, subtitle, badgeHtml = "" }) {
  return `
    <div class="hf-header">
      <span class="hf-logo">${logoSvg}</span>
      <div class="hf-header-text">
        <span class="hf-title">${title}</span>
        <span class="hf-subtitle">${subtitle}</span>
      </div>
      ${badgeHtml}
    </div>
  `;
}

export const HEADER_STYLES = `
  .hf-header {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 2;
  }
  .hf-logo {
    display: flex;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
  }
  .hf-header-text {
    display: flex;
    flex-direction: column;
    line-height: 1.1;
    min-width: 0;
  }
  .hf-title {
    font-size: 1.55em;
    font-weight: 900;
    letter-spacing: 0.06em;
    color: #ffffff;
    text-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hf-subtitle {
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.82);
  }
  .hf-badge {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 11px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(4px);
    font-size: 0.72em;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #ffffff;
    flex-shrink: 0;
  }
  .hf-badge-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  @media (max-width: 460px) {
    .hf-title {
      font-size: 1.3em;
    }
  }
`;

/**
 * Whole days between two ISO dates, counting to today when `toIso` is
 * empty. Used for "days with you" - the chronicle shows it as a column,
 * the ranking divides lifetime distance by it.
 */
export function daysBetween(fromIso, toIso) {
  if (!fromIso) return null;
  const from = new Date(fromIso);
  const to = toIso ? new Date(toIso) : new Date();
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return null;
  return Math.max(0, Math.floor((to.getTime() - from.getTime()) / 86400000));
}

/** Lightens (amount > 0) or darkens (amount < 0) a hex colour. */
export function shade(hex, amount) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((channel) => {
    const target = amount > 0 ? 255 : 0;
    return Math.round(channel + (target - channel) * Math.abs(amount));
  });
  return `rgb(${rgb.join(", ")})`;
}

export function isValidHex(value) {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

/** Resolves the hamster's coat colour from the health-score attributes. */
export function coatColor(healthScoreState) {
  const hex = healthScoreState && healthScoreState.attributes.coat_color_hex;
  return isValidHex(hex) ? hex : DEFAULT_FUR;
}

/** Applies the coat colour as CSS custom properties on `el`. */
export function applyFur(el, fur) {
  el.style.setProperty("--hf-fur", fur);
  el.style.setProperty("--hf-fur-light", shade(fur, 0.18));
  el.style.setProperty("--hf-fur-dark", shade(fur, -0.4));
  el.style.setProperty("--hf-belly", shade(fur, 0.62));
}

/**
 * Finds a sibling entity on the same device by its translation_key.
 * translation_key is a fixed English string set in the integration's
 * Python code (e.g. "daily_distance") and never changes - unlike
 * entity_id, which Home Assistant generates once from the *translated*
 * name active when the entity was first created, so it can end up in
 * German, French, etc. instead of English. Returns null if the entity/
 * device registry data isn't available yet or there's no match.
 */
export function siblingEntityId(hass, entityId, translationKey) {
  const entities = hass && hass.entities;
  const self = entities && entities[entityId];
  const deviceId = self && self.device_id;
  if (!deviceId) return null;
  for (const [id, entry] of Object.entries(entities)) {
    if (entry.device_id === deviceId && entry.translation_key === translationKey) {
      return id;
    }
  }
  return null;
}

/**
 * Resolves the display title from the device's own name, which is set
 * once from the hamster's actual name and never translated (see
 * hamster_device_info() in coordinator.py) - unlike the entity_id slug,
 * which may be in any language.
 */
export function deviceDisplayName(hass, entityId) {
  const entities = hass && hass.entities;
  const devices = hass && hass.devices;
  const self = entities && entities[entityId];
  const device = self && devices && devices[self.device_id];
  const name = device && (device.name_by_user || device.name);
  return name ? name.replace(/^Hamster\s+/, "") : null;
}
