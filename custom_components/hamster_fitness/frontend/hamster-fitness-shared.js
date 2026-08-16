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

    // Sharing
    "share.button": "Share",
    "share.title": "Share as an image",
    "share.hint":
      "Pick what goes on the picture. It is saved to your device - you share it from there.",
    "share.create": "Create image",
    "share.cancel": "Cancel",
    "share.close": "Close",
    "share.working": "Composing...",
    "share.saved": "Saved.",
    "share.shared": "Shared.",
    "share.failed": "Could not create the image.",
    "share.pickOne": "Pick at least one value.",
    "share.allHamsters": "All hamsters",
    "share.statWeek": "This week",
    "share.statLastNight": "Last night",
    "share.statScore": "Health score",
    "share.statNight": "Tonight",
    "share.statWeight": "Weight",
    "share.statWithYou": "With you",
    "share.statHamsters": "Hamsters",
    "share.statCurrent": "Living with you",
    "share.statLifetime": "Total distance",
    "share.statLeader": "Front runner",
    "share.statClimate": "Climate",
    "share.subtitleFamily": "Hamster Fitness",

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
    "running.tonight": "Tonight",
    "running.collecting":
      "Collecting - {count} of 7 nights recorded so far. A night is added once its window closes in the evening; the dashed bar is the one still running.",
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

    // Teilen
    "share.button": "Teilen",
    "share.title": "Als Bild teilen",
    "share.hint":
      "Wähle aus, was auf das Bild soll. Es wird auf deinem Gerät gespeichert - von dort teilst du es weiter.",
    "share.create": "Bild erstellen",
    "share.cancel": "Abbrechen",
    "share.close": "Schließen",
    "share.working": "Wird erstellt...",
    "share.saved": "Gespeichert.",
    "share.shared": "Geteilt.",
    "share.failed": "Bild konnte nicht erstellt werden.",
    "share.pickOne": "Wähle mindestens einen Wert aus.",
    "share.allHamsters": "Alle Hamster",
    "share.statWeek": "Diese Woche",
    "share.statLastNight": "Letzte Nacht",
    "share.statScore": "Health-Score",
    "share.statNight": "Heute Nacht",
    "share.statWeight": "Gewicht",
    "share.statWithYou": "Bei dir seit",
    "share.statHamsters": "Hamster",
    "share.statCurrent": "Aktuell bei dir",
    "share.statLifetime": "Gesamtstrecke",
    "share.statLeader": "Spitzenreiter",
    "share.statClimate": "Klima",
    "share.subtitleFamily": "Hamster Fitness",

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
    "running.tonight": "Heute",
    "running.collecting":
      "Wird gesammelt - bislang {count} von 7 Nächten. Eine Nacht kommt dazu, sobald ihr Fenster abends schließt; der gestrichelte Balken ist die laufende.",
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

/* ------------------------------------------------------------------ *
 * The sky: what the current conditions look like
 *
 * Colours, thresholds and the weather table live here rather than in the
 * Day & Night card, because the share image draws the same sky and the
 * two must not drift apart. Only the *decision* is shared - which
 * colours, which scene. The geometry stays with each surface: the card's
 * sky is a 300x120 letterbox strip with the sun and moon at fixed
 * coordinates, the share image is a portrait poster, and no single set
 * of coordinates serves both.
 * ------------------------------------------------------------------ */

export const NIGHT_GRADIENT = ["#0B132B", "#1C2541"];
export const DAY_GRADIENT_HORIZON = ["#F4A261", "#E9C46A"];
export const DAY_GRADIENT_MIDDAY = ["#4EA8DE", "#90E0EF"];
export const DAY_ELEVATION_FULL_AT = 30; // degrees - gradient stops shifting past this

// Ambient-light thresholds, only used once an illuminance sensor is
// configured (coordinator.py's ambient_light_lx attribute; None means
// "keep using sun.sun", the card's existing behaviour). At/below
// AMBIENT_NIGHT_LX counts as night; at/above AMBIENT_DAY_LX the gradient
// is fully "day". Deliberately a plain two-stop fade straight to
// DAY_GRADIENT_MIDDAY, not a three-stop one through DAY_GRADIENT_HORIZON
// like the sun-elevation path: lux says how bright the room is, not
// where the sun sits, so there is no honest "just past the horizon" hue
// to interpolate through.
export const AMBIENT_NIGHT_LX = 5;
export const AMBIENT_DAY_LX = 150;
// How bright the lux reading may push the sky once the real sun is below
// the horizon. A lit room at 10pm is still a lit room - but rendering it
// as full midday reads as broken, however accurate the lux value is. This
// caps it at dusk instead: clearly still evening, just not pitch black.
export const AMBIENT_NIGHT_CEILING = 0.3;

/**
 * Every weather state Home Assistant defines, mapped to what the scene
 * should show. Covered individually rather than lumped into a few
 * buckets, and an unknown state means "no overlay" rather than a guess -
 * so a state a future Home Assistant adds degrades to a clear sky.
 */
export const WEATHER_SCENES = {
  "clear-night": { clouds: 0, dim: 0 },
  sunny: { clouds: 0, dim: 0 },
  partlycloudy: { clouds: 2, dim: 0.05 },
  cloudy: { clouds: 4, dim: 0.16 },
  fog: { clouds: 0, dim: 0.3, fog: true },
  windy: { clouds: 2, dim: 0.05, wind: true },
  "windy-variant": { clouds: 3, dim: 0.1, wind: true },
  rainy: { clouds: 4, dim: 0.24, drops: 26, dropKind: "rain" },
  pouring: { clouds: 5, dim: 0.34, drops: 54, dropKind: "rain" },
  snowy: { clouds: 4, dim: 0.2, drops: 30, dropKind: "snow" },
  "snowy-rainy": { clouds: 4, dim: 0.26, drops: 34, dropKind: "sleet" },
  hail: { clouds: 5, dim: 0.28, drops: 30, dropKind: "hail" },
  lightning: { clouds: 4, dim: 0.3, lightning: true },
  "lightning-rainy": {
    clouds: 5,
    dim: 0.36,
    drops: 46,
    dropKind: "rain",
    lightning: true,
  },
  // "Exceptional" means severe weather of an unspecified kind, so it
  // gets the most dramatic treatment rather than a guess at which.
  exceptional: { clouds: 5, dim: 0.4, lightning: true, wind: true },
};

/**
 * Home Assistant's eight moon-phase states (the built-in Moon
 * integration), as an illuminated fraction plus which limb is lit.
 *
 * `lit` is the fraction of the disc that is bright; `waxing` says whether
 * that bright part is on the right (growing towards full) or the left
 * (shrinking towards new). Both are what moonPath() needs to draw the
 * terminator - the curved edge between light and shadow.
 *
 * Orientation is the northern-hemisphere one, matching the fixed crescent
 * the Day & Night card has always drawn. Below the equator the moon
 * appears mirrored; Home Assistant's sensor doesn't report that, and
 * guessing it from the configured latitude is a separate question from
 * reading the phase.
 */
export const MOON_PHASES = {
  new_moon: { lit: 0, waxing: true },
  waxing_crescent: { lit: 0.25, waxing: true },
  first_quarter: { lit: 0.5, waxing: true },
  waxing_gibbous: { lit: 0.75, waxing: true },
  full_moon: { lit: 1, waxing: true },
  waning_gibbous: { lit: 0.75, waxing: false },
  last_quarter: { lit: 0.5, waxing: false },
  waning_crescent: { lit: 0.25, waxing: false },
};

/**
 * The configured moon entity's phase, or null to draw the default.
 *
 * Same treatment as the weather entity: no entity configured, an
 * unavailable one, or a state this doesn't recognise all mean "draw the
 * default" rather than an error in the sky.
 */
export function moonPhase(hass, healthScoreState) {
  const entityId =
    healthScoreState &&
    healthScoreState.attributes &&
    healthScoreState.attributes.moon_entity;
  if (!entityId) return null;
  const state = hass && hass.states && hass.states[entityId];
  if (!state) return null;
  return MOON_PHASES[state.state] ? state.state : null;
}

/**
 * The lit part of the moon as an SVG path, around any centre and radius.
 *
 * Two arcs: the outer limb (a half circle, on whichever side is lit),
 * then the terminator back to the start. The terminator is an ellipse
 * flattened by how full the moon is - at exactly half it collapses to a
 * straight line, which is what makes a quarter moon a clean half disc.
 *
 * Geometry is a parameter rather than a constant because two surfaces
 * draw this moon at very different sizes: the card's letterbox sky and
 * the share image's portrait poster.
 */
export function moonPath(cx, cy, r, lit, waxing) {
  const top = `${cx} ${cy - r}`;
  const bottom = `${cx} ${cy + r}`;
  // Sweep 1 from top to bottom traces the right half, 0 the left.
  const outerSweep = waxing ? 1 : 0;
  // Below half the terminator curves towards the lit limb (a thin
  // crescent); above half it bulges the other way (a fat gibbous).
  const innerSweep = lit < 0.5 ? (waxing ? 0 : 1) : waxing ? 1 : 0;
  const rx = (r * Math.abs(1 - 2 * lit)).toFixed(2);
  return (
    `M ${top}` +
    ` A ${r} ${r} 0 1 ${outerSweep} ${bottom}` +
    ` A ${rx} ${r} 0 1 ${innerSweep} ${top} Z`
  );
}

/**
 * The moon body for a phase, or null for "no phase to draw".
 *
 * Only the bright part is ever drawn. Painting a shadow over a full disc
 * would need it to match the sky behind it, which changes with the
 * gradient, the weather overlay and the cage light.
 */
export function moonBody(cx, cy, r, phase, fill = "#F4E285") {
  if (phase === null || !MOON_PHASES[phase]) return null;
  const { lit, waxing } = MOON_PHASES[phase];
  if (lit >= 1) {
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" opacity="0.95"/>`;
  }
  // New moon: earthshine only. Drawing nothing at all would read as a
  // rendering failure rather than as the sky actually looking like that.
  if (lit <= 0) {
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${fill}" opacity="0.13"/>`;
  }
  return `<path d="${moonPath(cx, cy, r, lit, waxing)}" fill="${fill}" opacity="0.95"/>`;
}

function hexToRgb(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function lerpColor(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const rgb = a.map((channel, i) => Math.round(channel + (b[i] - channel) * t));
  return `rgb(${rgb.join(", ")})`;
}

/** True/false from sun.sun, or null when there is no sun entity. */
export function sunBelowHorizon(hass) {
  const sun = hass && hass.states && hass.states["sun.sun"];
  if (!sun) return null;
  return sun.state === "below_horizon";
}

/** sun.sun's elevation in degrees, or null if unavailable. */
export function sunElevation(hass) {
  const sun = hass && hass.states && hass.states["sun.sun"];
  const elevation = Number(sun && sun.attributes && sun.attributes.elevation);
  return Number.isFinite(elevation) ? elevation : null;
}

/**
 * The two gradient colours for the sky right now, plus whether it counts
 * as night and which weather scene applies.
 *
 * `ambientLx` wins where an illuminance sensor exists, because it
 * describes the room the hamster is actually in rather than the sky
 * outside - except that it may not claim daylight once the real sun has
 * set (AMBIENT_NIGHT_CEILING). With no sensor this falls back to the
 * sun's elevation.
 */
export function skyState(hass, healthScoreState) {
  const attrs = (healthScoreState && healthScoreState.attributes) || {};
  const rawLx = attrs.ambient_light_lx;
  const ambientLx =
    rawLx === null || rawLx === undefined ? null : Number(rawLx);
  const below = sunBelowHorizon(hass);

  const weatherId = attrs.weather_entity;
  const weather = weatherId && hass.states ? hass.states[weatherId] : null;
  const scene = (weather && WEATHER_SCENES[weather.state]) || null;

  if (ambientLx !== null && Number.isFinite(ambientLx)) {
    let t = Math.min(
      1,
      Math.max(0, (ambientLx - AMBIENT_NIGHT_LX) / (AMBIENT_DAY_LX - AMBIENT_NIGHT_LX))
    );
    if (below) t = Math.min(t, AMBIENT_NIGHT_CEILING);
    return {
      from: lerpColor(NIGHT_GRADIENT[0], DAY_GRADIENT_MIDDAY[0], t),
      to: lerpColor(NIGHT_GRADIENT[1], DAY_GRADIENT_MIDDAY[1], t),
      night: ambientLx <= AMBIENT_NIGHT_LX || below === true,
      scene,
    };
  }

  if (below !== false) {
    return {
      from: NIGHT_GRADIENT[0],
      to: NIGHT_GRADIENT[1],
      night: true,
      scene,
    };
  }

  const elevation = sunElevation(hass);
  const t =
    elevation === null ? 1 : Math.min(1, Math.max(0, elevation / DAY_ELEVATION_FULL_AT));
  return {
    from: lerpColor(DAY_GRADIENT_HORIZON[0], DAY_GRADIENT_MIDDAY[0], t),
    to: lerpColor(DAY_GRADIENT_HORIZON[1], DAY_GRADIENT_MIDDAY[1], t),
    night: false,
    scene,
  };
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
 * Entity ids of every hamster's health-score sensor, sorted.
 *
 * Matched on the entity registry rather than on the entity_id, for the
 * same reason siblingEntityId() does: translation_key is the fixed
 * English key from sensor.py, while the entity_id slug follows whatever
 * language was active when the entity was first created.
 */
export function healthScoreEntityIds(hass) {
  const entities = (hass && hass.entities) || {};
  const ids = [];
  for (const [id, entry] of Object.entries(entities)) {
    if (
      entry &&
      entry.platform === "hamster_fitness" &&
      entry.translation_key === "health_score"
    ) {
      ids.push(id);
    }
  }
  return ids.sort();
}

/**
 * Entity selector for the four cards that are configured with a single
 * hamster's health-score sensor (Health Score, Day & Night, Weight,
 * Running).
 *
 * A declarative filter can only narrow by domain/device_class/
 * integration, so "every hamster_fitness sensor" was as close as the
 * picker could get - leaving the user to pick the right one out of
 * lifetime_distance, activity_score, climate_score and friends, when
 * only health_score is ever accepted. include_entities takes an explicit
 * allowlist instead, so we resolve the exact entities ourselves.
 *
 * Falls back to the old integration filter when the registry yields
 * nothing: an empty include_entities list renders an empty picker, which
 * would be a worse failure than an over-broad one.
 */
export function healthScoreEntitySelector(hass) {
  const ids = healthScoreEntityIds(hass);
  if (!ids.length) {
    return { entity: { filter: { integration: "hamster_fitness", domain: "sensor" } } };
  }
  return { entity: { include_entities: ids } };
}

/** True when `entityId` was created by this integration. */
export function isHamsterFitnessEntity(hass, entityId) {
  const entry = hass && hass.entities && hass.entities[entityId];
  return Boolean(entry && entry.platform === "hamster_fitness");
}

/**
 * The health-score entity of whichever hamster `entityId` belongs to,
 * or null if that isn't one of ours.
 *
 * Used by the card picker's entity suggestions (see getEntitySuggestion
 * on the window.customCards entries). The picked entity does not have to
 * BE the health-score sensor: any of a hamster's sensors identifies the
 * hamster just as well, and the four per-hamster cards all want the
 * health-score one. Someone who clicks "Taco weight" while building a
 * dashboard means Taco, the same as someone who clicks "Taco health
 * score" - so both get offered the same cards, wired to the entity the
 * cards actually accept.
 */
export function healthScoreEntityFor(hass, entityId) {
  if (!isHamsterFitnessEntity(hass, entityId)) return null;
  if (hass.entities[entityId].translation_key === "health_score") return entityId;
  return siblingEntityId(hass, entityId, "health_score");
}

/**
 * Wraps a card editor's schema factory so it only re-runs when the
 * health-score entity list actually changed.
 *
 * A card editor's `set hass` fires on every state change anywhere in
 * Home Assistant, and healthScoreEntityIds() walks the entire entity
 * registry - thousands of entries on a big instance. Without this the
 * editor would repeat that scan several times a second for as long as
 * the dialog stays open, to arrive at the same answer every time.
 */
export function memoizedEditorSchema(build) {
  let key = null;
  let cached = null;
  return (hass) => {
    const next = healthScoreEntityIds(hass).join(",");
    if (cached === null || next !== key) {
      key = next;
      cached = build(hass);
    }
    return cached;
  };
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

/* ------------------------------------------------------------------ *
 * Sharing
 *
 * One engine, six entry points. Every card renders its banner through
 * renderCardHeader(), so the button goes in there once and the dialog,
 * the composition, the rasterizing and the saving all live here - a card
 * contributes only a payload saying what it is about and which numbers
 * it can offer.
 *
 * The image is drawn as SVG and rasterized through a canvas, rather than
 * screenshotting the live card: capturing CSS-styled HTML needs a
 * third-party library, while an SVG rasterizes natively and these cards
 * are SVG-heavy anyway. It is composed for the format - a portrait
 * poster - not a copy of the card layout.
 * ------------------------------------------------------------------ */

// 4:5 portrait, the shape most social apps show without cropping.
const SHARE_W = 1080;
const SHARE_H = 1350;

// Only fonts a rasterizer can be expected to resolve on its own. Text
// inside an <img>-loaded SVG cannot reach the page's stylesheets or any
// webfont loaded there, so a custom family would silently fall back to
// something else and the image would not match the card.
const SHARE_FONT =
  "'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif";

/** A safe, dated file name for a shared image. */
export function shareFilename(name, kind) {
  const slug =
    String(name || "hamster")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "hamster";
  return `hamster-${slug}-${kind}-${new Date().toISOString().slice(0, 10)}`;
}

/** Escapes text bound for SVG/XML markup. */
export function escapeXml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** The small share glyph. Deliberately quiet - three dots and two arms. */
const SHARE_ICON_SVG = `
<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
  <path d="M18 8a3 3 0 1 0-2.83-4H15a3 3 0 0 0 .13.87L8.7 8.5a3 3 0 1 0 0 7l6.43 3.63A3 3 0 1 0 18 16a3 3 0 0 0-2.06.82L9.87 13.4a3 3 0 0 0 0-2.8l6.07-3.42A3 3 0 0 0 18 8Z"
        fill="currentColor"/>
</svg>
`;

/**
 * Renders one card's banner.
 *
 * `share` is optional: pass a payload (see openShareDialog) and the
 * header grows a share button in its corner. Cards that pass nothing
 * look exactly as before.
 */
export function renderCardHeader({ logoSvg, title, subtitle, badgeHtml = "", share }) {
  const shareButton = share
    ? `<button class="hf-share" type="button" data-hf-share
               title="${escapeXml(share.buttonLabel || "Share")}"
               aria-label="${escapeXml(share.buttonLabel || "Share")}">
         ${SHARE_ICON_SVG}
       </button>`
    : "";
  return `
    <div class="hf-header">
      <span class="hf-logo">${logoSvg}</span>
      <div class="hf-header-text">
        <span class="hf-title">${title}</span>
        <span class="hf-subtitle">${subtitle}</span>
      </div>
      ${badgeHtml}
      ${shareButton}
    </div>
  `;
}

/**
 * Wires the header's share button on a card root.
 *
 * `payloadFor()` is called at click time, not now, so the image always
 * carries the values on screen at that moment rather than whatever was
 * current when the card last rendered its header.
 */
export function bindShareButton(root, payloadFor) {
  if (!root || root._hfShareBound) return;
  root._hfShareBound = true;
  // The dialog is absolutely positioned against this element, so it has
  // to be a containing block - otherwise the overlay escapes to the
  // nearest positioned ancestor and covers the whole dashboard. Same
  // trap as the chronicle's add-past dialog (#70). Only set where the
  // card has not already positioned its own root.
  if (getComputedStyle(root).position === "static") {
    root.style.position = "relative";
  }
  root.addEventListener("click", (ev) => {
    const button = ev.target.closest("[data-hf-share]");
    if (!button || !root.contains(button)) return;
    ev.stopPropagation();
    const payload = payloadFor();
    if (payload) openShareDialog(root, payload);
  });
}

/** Deterministic pseudo-random, so one image renders the same twice. */
function _seeded(seed) {
  let value = seed >>> 0 || 1;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

/** The weather overlay, drawn for a portrait canvas. */
function _shareWeather(scene, night, rand) {
  if (!scene) return "";
  const parts = [];

  for (let i = 0; i < (scene.clouds || 0); i++) {
    const cx = 90 + rand() * (SHARE_W - 180);
    const cy = 90 + rand() * 260;
    const r = 46 + rand() * 40;
    const opacity = (night ? 0.16 : 0.3) + rand() * 0.12;
    parts.push(
      `<g opacity="${opacity.toFixed(2)}" fill="#ffffff">
         <ellipse cx="${cx.toFixed(0)}" cy="${cy.toFixed(0)}" rx="${(r * 1.7).toFixed(0)}" ry="${r.toFixed(0)}"/>
         <ellipse cx="${(cx - r).toFixed(0)}" cy="${(cy + r * 0.28).toFixed(0)}" rx="${r.toFixed(0)}" ry="${(r * 0.7).toFixed(0)}"/>
         <ellipse cx="${(cx + r).toFixed(0)}" cy="${(cy + r * 0.22).toFixed(0)}" rx="${(r * 1.1).toFixed(0)}" ry="${(r * 0.72).toFixed(0)}"/>
       </g>`
    );
  }

  const dropFill = { rain: "#BFE3F5", sleet: "#D8ECF7", hail: "#FFFFFF", snow: "#FFFFFF" };
  for (let i = 0; i < (scene.drops || 0); i++) {
    const x = rand() * SHARE_W;
    const y = 120 + rand() * (SHARE_H * 0.62);
    const fill = dropFill[scene.dropKind] || "#BFE3F5";
    if (scene.dropKind === "snow" || scene.dropKind === "hail") {
      parts.push(
        `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${(3 + rand() * 3).toFixed(1)}" fill="${fill}" opacity="0.75"/>`
      );
    } else {
      parts.push(
        `<rect x="${x.toFixed(0)}" y="${y.toFixed(0)}" width="2.5" height="${(14 + rand() * 12).toFixed(0)}" rx="1.2" fill="${fill}" opacity="0.6"/>`
      );
    }
  }

  if (scene.fog) {
    for (let i = 0; i < 5; i++) {
      const y = 160 + i * 150;
      parts.push(
        `<rect x="0" y="${y}" width="${SHARE_W}" height="70" fill="#ffffff" opacity="0.13"/>`
      );
    }
  }

  if (scene.lightning) {
    parts.push(
      `<path d="M628 150 L586 330 L648 330 L596 520 L712 300 L650 300 L700 150 Z"
             fill="#FFE79A" opacity="0.85"/>`
    );
  }

  if (scene.dim) {
    parts.push(
      `<rect x="0" y="0" width="${SHARE_W}" height="${SHARE_H}" fill="#000000" opacity="${scene.dim}"/>`
    );
  }
  return parts.join("");
}

// Where the moon sits on the poster, and how big.
const SHARE_MOON_CX = 872;
const SHARE_MOON_CY = 208;
const SHARE_MOON_R = 74;

/**
 * Stars and the moon for a night sky, or a sun disc for a day one.
 *
 * `phase` is one of Home Assistant's moon states, or null when no moon
 * sensor is configured (or it reports something unrecognised) - in which
 * case the poster falls back to the same fixed crescent the Day & Night
 * card has always drawn.
 */
function _shareCelestial(night, rand, phase) {
  if (!night) {
    return `
      <g>
        <circle cx="880" cy="210" r="150" fill="#FFD166" opacity="0.18"/>
        <circle cx="880" cy="210" r="96" fill="#FFD166" opacity="0.28"/>
        <circle cx="880" cy="210" r="62" fill="#FFE08A"/>
      </g>`;
  }
  const stars = [];
  for (let i = 0; i < 60; i++) {
    const x = rand() * SHARE_W;
    const y = rand() * (SHARE_H * 0.55);
    const r = 1.2 + rand() * 2.4;
    stars.push(
      `<circle cx="${x.toFixed(0)}" cy="${y.toFixed(0)}" r="${r.toFixed(1)}" fill="#ffffff" opacity="${(0.35 + rand() * 0.55).toFixed(2)}"/>`
    );
  }
  const moon =
    moonBody(SHARE_MOON_CX, SHARE_MOON_CY, SHARE_MOON_R, phase, "#F3F0E4") ||
    // The fixed crescent, scaled from the card's own fallback path: one
    // subpath for the disc and a smaller one wound the other way, so the
    // bite is a genuine hole. Painting a dark disc over the top instead
    // would read as a full moon in shadow - the sky has to show through.
    `<path d="M ${SHARE_MOON_CX} ${SHARE_MOON_CY - SHARE_MOON_R}` +
      ` a ${SHARE_MOON_R} ${SHARE_MOON_R} 0 1 0 2.6 0` +
      ` a ${(SHARE_MOON_R * 13) / 17} ${(SHARE_MOON_R * 13) / 17} 0 1 1 -2.6 0 Z"` +
      ` fill="#F3F0E4" opacity="0.95"/>`;
  return `<g>${stars.join("")}</g>${moon}`;
}

/**
 * Composes the share image.
 *
 * Returns SVG source; rasterizing is a separate step, so the composition
 * can be inspected and tested on its own.
 */
export function buildShareSvg({ title, subtitle, stats, footer, fur, sky, moon = null }) {
  const rand = _seeded(
    [...String(title || "hamster")].reduce((a, c) => a + c.charCodeAt(0), 7)
  );
  const night = !!(sky && sky.night);
  const from = (sky && sky.from) || NIGHT_GRADIENT[0];
  const to = (sky && sky.to) || NIGHT_GRADIENT[1];

  // Two columns once there are more than three, so a long selection does
  // not run off the bottom of a fixed-height canvas.
  const twoCol = stats.length > 3;
  const cellW = twoCol ? 430 : 880;
  const startY = 700;
  const rowH = twoCol ? 168 : 150;

  const cells = stats
    .map((stat, i) => {
      const col = twoCol ? i % 2 : 0;
      const row = twoCol ? Math.floor(i / 2) : i;
      const x = 100 + col * (cellW + 20);
      const y = startY + row * rowH;
      return `
        <g>
          <rect x="${x}" y="${y}" width="${cellW}" height="${rowH - 18}" rx="26"
                fill="#ffffff" opacity="0.12"/>
          <text x="${x + 34}" y="${y + 52}" class="s-label">${escapeXml(stat.label)}</text>
          <text x="${x + 34}" y="${y + 112}" class="s-value">${escapeXml(stat.value)}</text>
        </g>`;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${SHARE_W}" height="${SHARE_H}"
     viewBox="0 0 ${SHARE_W} ${SHARE_H}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${from}"/>
      <stop offset="100%" stop-color="${to}"/>
    </linearGradient>
    <linearGradient id="veil" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#000000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.55"/>
    </linearGradient>
  </defs>
  <style>
    text { font-family: ${SHARE_FONT}; fill: #ffffff; }
    .s-title { font-size: 92px; font-weight: 900; letter-spacing: 2px; }
    .s-sub { font-size: 34px; font-weight: 600; letter-spacing: 7px; opacity: 0.85; }
    .s-label { font-size: 27px; font-weight: 700; letter-spacing: 3px; opacity: 0.8; }
    .s-value { font-size: 62px; font-weight: 800; }
    .s-foot { font-size: 28px; font-weight: 600; opacity: 0.75; }
  </style>

  <rect width="${SHARE_W}" height="${SHARE_H}" fill="url(#sky)"/>
  ${_shareCelestial(night, rand, moon)}
  ${_shareWeather(sky && sky.scene, night, rand)}
  <rect width="${SHARE_W}" height="${SHARE_H}" fill="url(#veil)"/>

  <g transform="translate(100, 470)">
    <rect x="0" y="-52" width="14" height="120" rx="7" fill="${fur || "#D48C46"}"/>
    <text x="42" y="10" class="s-title">${escapeXml(String(title).toUpperCase())}</text>
    <text x="46" y="62" class="s-sub">${escapeXml(String(subtitle).toUpperCase())}</text>
  </g>

  ${cells}

  <text x="100" y="${SHARE_H - 70}" class="s-foot">${escapeXml(footer)}</text>
</svg>`;
}

/**
 * SVG source to a PNG blob.
 *
 * The SVG travels through a blob URL rather than a base64 data URL on
 * purpose: btoa() throws on anything outside Latin-1, and these strings
 * routinely carry German text. A blob URL is same-origin, so it does not
 * taint the canvas and toBlob() stays available.
 */
export function rasterizeSvg(svg, scale = 1) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(
      new Blob([svg], { type: "image/svg+xml;charset=utf-8" })
    );
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = SHARE_W * scale;
      canvas.height = SHARE_H * scale;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))),
        "image/png"
      );
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("SVG failed to load"));
    };
    image.src = url;
  });
}

/**
 * Hands the finished image to the user.
 *
 * Saving is the primary path, not navigator.share(): that needs a secure
 * context, and Home Assistant is commonly reached over plain http on the
 * local network - and the Android companion app is a WebView, which does
 * not implement it at all. Where it genuinely exists it is the nicer
 * route, so it is tried first and falls back rather than relied upon.
 */
export async function deliverShareImage(blob, filename) {
  const file = new File([blob], filename, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file] });
      return "shared";
    } catch (err) {
      // Someone who dismisses the sheet has not asked for a download.
      if (err && err.name === "AbortError") return "cancelled";
    }
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return "downloaded";
}

/**
 * The share dialog.
 *
 * A plain absolutely-positioned overlay rather than <ha-dialog>, matching
 * the chronicle's add-past dialog and the health-score pillar modal: those
 * keep working inside the dashboard editor preview, where an ha-dialog
 * does not. The card root needs `position: relative` for the overlay to
 * size itself against the card - the same containing-block point that
 * bit the chronicle dialog.
 *
 * `payload` is:
 *   hass      the hass object, for translations and the sky
 *   entity    the health-score entity, or null for all-hamster cards
 *   title     headline on the image (a name, or the integration's own)
 *   subtitle  the small line beneath it
 *   fur       accent colour
 *   stats     [{ key, label, value, default }] - what may go on the image
 *   filename  base name for the saved file
 */
export function openShareDialog(root, payload) {
  root.querySelectorAll("[data-hf-share-overlay]").forEach((el) => el.remove());

  const hass = payload.hass;
  const chosen = new Set(
    payload.stats.filter((s) => s.default !== false).map((s) => s.key)
  );

  const overlay = document.createElement("div");
  overlay.className = "hf-share-overlay";
  overlay.setAttribute("data-hf-share-overlay", "");
  overlay.innerHTML = `
    <div class="hf-share-sheet" role="dialog" aria-modal="true"
         aria-label="${escapeXml(t(hass, "share.title"))}">
      <div class="hf-share-head">
        <span class="hf-share-heading">${escapeXml(t(hass, "share.title"))}</span>
        <button class="hf-share-x" type="button" data-act="close"
                aria-label="${escapeXml(t(hass, "share.close"))}">&times;</button>
      </div>
      <p class="hf-share-hint">${escapeXml(t(hass, "share.hint"))}</p>
      <div class="hf-share-list">
        ${payload.stats
          .map(
            (stat) => `
          <label class="hf-share-row">
            <input type="checkbox" data-stat="${escapeXml(stat.key)}"
                   ${chosen.has(stat.key) ? "checked" : ""}/>
            <span class="hf-share-row-label">${escapeXml(stat.label)}</span>
            <span class="hf-share-row-value">${escapeXml(stat.value)}</span>
          </label>`
          )
          .join("")}
      </div>
      <div class="hf-share-status" hidden></div>
      <div class="hf-share-actions">
        <button class="hf-share-btn" type="button" data-act="close">
          ${escapeXml(t(hass, "share.cancel"))}
        </button>
        <button class="hf-share-btn hf-share-btn-primary" type="button" data-act="go">
          ${escapeXml(t(hass, "share.create"))}
        </button>
      </div>
    </div>
  `;
  root.appendChild(overlay);

  const status = overlay.querySelector(".hf-share-status");
  const close = () => overlay.remove();

  overlay.addEventListener("click", async (ev) => {
    if (ev.target === overlay || ev.target.closest('[data-act="close"]')) {
      close();
      return;
    }
    const box = ev.target.closest("input[data-stat]");
    if (box) {
      if (box.checked) chosen.add(box.dataset.stat);
      else chosen.delete(box.dataset.stat);
      return;
    }
    if (!ev.target.closest('[data-act="go"]')) return;

    const stats = payload.stats.filter((s) => chosen.has(s.key));
    if (!stats.length) {
      status.hidden = false;
      status.textContent = t(hass, "share.pickOne");
      return;
    }

    status.hidden = false;
    status.textContent = t(hass, "share.working");
    try {
      const scoreState = payload.entity ? hass.states[payload.entity] : null;
      const svg = buildShareSvg({
        title: payload.title,
        subtitle: payload.subtitle,
        stats,
        footer: payload.footer || fmtDate(hass, new Date().toISOString()),
        fur: payload.fur,
        sky: skyState(hass, scoreState),
        moon: moonPhase(hass, scoreState),
      });
      const blob = await rasterizeSvg(svg);
      const how = await deliverShareImage(blob, `${payload.filename}.png`);
      if (how === "cancelled") {
        status.hidden = true;
        return;
      }
      status.textContent = t(hass, how === "shared" ? "share.shared" : "share.saved");
      setTimeout(close, 1400);
    } catch (err) {
      status.textContent = t(hass, "share.failed");
      // eslint-disable-next-line no-console
      console.error("[hamster-fitness] share failed", err);
    }
  });
}

export const SHARE_STYLES = `
  .hf-share {
    margin-left: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
    cursor: pointer;
    opacity: 0.75;
    transition: opacity 0.15s ease, background-color 0.15s ease;
  }
  /* No margin-left:auto here - the badge already claims it. Without a
     badge the button would otherwise sit against the subtitle, so the
     header text block is what pushes it over. */
  .hf-header-text {
    margin-right: auto;
  }
  .hf-share:hover,
  .hf-share:focus-visible {
    opacity: 1;
    background: rgba(255, 255, 255, 0.3);
  }
  .hf-share:focus-visible {
    outline: 2px solid #ffffff;
    outline-offset: 2px;
  }

  .hf-share-overlay {
    position: absolute;
    inset: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    background: rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(2px);
  }
  .hf-share-sheet {
    width: 100%;
    max-width: 340px;
    max-height: 100%;
    overflow: auto;
    padding: 14px 16px 16px;
    border-radius: 16px;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }
  .hf-share-head {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .hf-share-heading {
    font-size: 1em;
    font-weight: 800;
  }
  .hf-share-x {
    margin-left: auto;
    border: none;
    background: transparent;
    color: var(--secondary-text-color);
    font-size: 1.4em;
    line-height: 1;
    cursor: pointer;
  }
  .hf-share-hint {
    margin: 6px 0 10px;
    font-size: 0.78em;
    line-height: 1.4;
    color: var(--secondary-text-color);
  }
  .hf-share-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .hf-share-row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 7px 8px;
    border-radius: 10px;
    cursor: pointer;
    font-size: 0.84em;
  }
  .hf-share-row:hover {
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.12));
  }
  .hf-share-row-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .hf-share-row-value {
    margin-left: auto;
    font-weight: 700;
    color: var(--secondary-text-color);
    flex-shrink: 0;
  }
  .hf-share-status {
    margin-top: 10px;
    font-size: 0.78em;
    color: var(--secondary-text-color);
  }
  .hf-share-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
  }
  .hf-share-btn {
    padding: 8px 14px;
    border-radius: 999px;
    border: 1px solid var(--divider-color, #e0e0e0);
    background: transparent;
    color: var(--primary-text-color);
    font-family: inherit;
    font-size: 0.82em;
    font-weight: 700;
    cursor: pointer;
  }
  .hf-share-btn-primary {
    border-color: transparent;
    background: var(--primary-color, #03a9f4);
    color: #ffffff;
  }
`;
