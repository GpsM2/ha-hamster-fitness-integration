# Hamster Fitness

Eine Home-Assistant-Integration, die aus einem Laufrad-Umdrehungssensor, einem
Temperatursensor und einem Käfig-/Deckelkontakt einen "Health Score" für einen
Hamster berechnet, inklusive Warnungen und einer täglichen
Zusammenfassungs-Benachrichtigung.

Dieses Repository enthält beide Teile des Projekts:

- [`custom_components/hamster_fitness/`](custom_components/hamster_fitness) —
  die Home-Assistant-Integration.
- [`esphome/`](esphome) — die ESPHome-Firmware-Konfiguration für den
  optischen Laufrad-Sensor (D1 Mini + Reflex-Lichtschranke).

## Lizenz

Dieses Projekt steht unter der [PolyForm Noncommercial License 1.0.0](LICENSE).
Kurz zusammengefasst: Jeder darf den Code für **nicht-kommerzielle Zwecke**
(privat, Hobby, Bildung, Forschung) frei nutzen, verändern und weitergeben.
Der Urheber (GpsM2) behält alle Rechte und kann das Projekt unabhängig davon
auch kommerziell nutzen oder lizenzieren.

## 1. Sensor-Hardware bauen (ESPHome)

Benötigt wird ein ESP8266/D1-Mini-Board mit einer optischen Lichtschranke am
GPIO4 (D2), die bei jeder Rad-Umdrehung einmal auslöst.

1. `esphome/hamster-wheel-sensor.yaml` in dein ESPHome-Setup übernehmen
   (Dateiname/`esphome.name` ggf. anpassen).
2. In `secrets.yaml` die referenzierten Secrets ergänzen:
   `wifi_ssid`, `wifi_password`, `esphome_web_d027a9__encryption_key`,
   `esphome_web_d018de__ota_password` (die Secret-Namen selbst stammen noch
   vom ursprünglichen Auto-Namen des Geräts - das ist rein kosmetisch ohne
   Funktionsunterschied, wurde bewusst nicht mit umbenannt).
3. Flashen (per USB beim Ersteinrichten, danach OTA).
4. Nach dem Ersteinrichten in Home Assistant automatisch über die ESPHome-
   Integration verfügbar. Der reale Raddurchmesser lässt sich über die
   Number-Entity **"Hamster Wheel Diameter"** direkt in Home Assistant
   einstellen.

Die Firmware legt u. a. folgende Entities an:

| Entity | Bedeutung |
|---|---|
| `sensor.hamster_wheel_speed` | Aktuelle Geschwindigkeit (km/h) |
| `sensor.hamster_wheel_max_speed_today` | Tages-Maximalgeschwindigkeit |
| `sensor.hamster_wheel_total_distance` | Kumulierte Strecke seit Inbetriebnahme (km) |
| `sensor.hamster_wheel_distance_today` | Strecke seit dem letzten Reset um 08:00 Uhr (km) |
| `sensor.hamster_wheel_total_rotations` | Roher, nie zurückgesetzter Umdrehungszähler |

**Wichtig:** Für die `hamster_fitness`-Integration unten muss
`sensor.hamster_wheel_total_rotations` (der rohe Umdrehungszähler) als
"Rad-Umdrehungssensor" ausgewählt werden — nicht einer der bereits fertig in
km umgerechneten Strecken-Sensoren. Die Integration multipliziert den
Sensorwert selbst mit dem konfigurierten Raddurchmesser (siehe Abschnitt 3
"Einrichtung" unten).

Sowohl das ESPHome-Feld "Hamster Wheel Diameter" als auch das
`hamster_fitness`-Feld "Raddurchmesser" erwarten denselben Wert - einfach
überall denselben Durchmesser eintragen, wie er üblicherweise auf der
Verpackung des Laufrads steht. `sensor.hamster_wheel_speed`
(Echtzeit-Geschwindigkeit) lässt sich optional ebenfalls in
`hamster_fitness` einbinden, siehe Abschnitt 3.

## 2. Integration installieren

Benötigt **Home Assistant 2026.3 oder neuer** (wegen der
[Brands-Proxy-API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/),
über die das Integrations-Icon direkt aus
`custom_components/hamster_fitness/brand/` geladen wird).

### Über HACS (empfohlen, sobald das Repo als HACS-Repository hinzugefügt ist)

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories.
2. URL dieses Repos eintragen, Kategorie "Integration".
3. "Hamster Fitness" installieren, Home Assistant neu starten.

### Manuell

`custom_components/hamster_fitness/` in das `custom_components`-Verzeichnis
deiner Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

### Nach einem Update

Home Assistant cacht Übersetzungen (`strings.json`/`translations/*.json`)
und die Frontend-Ressourcen pro Sitzung. Nach dem Kopieren einer neuen
Version reicht ein einfaches "Integration neu laden" oft nicht - **einmal
Home Assistant komplett neu starten** (Einstellungen → System → Neu
starten), und im Browser bei Bedarf per <kbd>Strg</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>
neu laden. Zeigt der Config Flow sonst rohe Feldnamen wie `wheel_diameter`
statt einer übersetzten Beschriftung an, ist das fast immer die Ursache.

## 3. Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → "Hamster Fitness".

**Schritt 1 (Basisdaten):** Name des Hamsters, Einzugsdatum, Raddurchmesser (cm) -
wie auf der Verpackung des Laufrads angegeben.

**Schritt 2 (Quell-Sensoren):**

- Rad-Umdrehungssensor → `sensor.hamster_wheel_total_rotations`
- Temperatursensor → dein Temperatursensor am Käfig (`device_class: temperature`)
- Deckel-/Käfigöffnungssensor → dein Tür-/Öffnungskontakt (`device_class: door`
  oder `opening`)
- Luftfeuchtigkeitssensor (optional) → nur nötig, falls vorhanden; ohne
  Auswahl wird einfach keine Feuchtigkeits-Entity angelegt
- Echtzeit-Geschwindigkeitssensor (optional) → z. B.
  `sensor.hamster_wheel_speed`; ohne Auswahl werden keine
  Geschwindigkeits-Entities angelegt
- Käfigbeleuchtung (optional) → ein Leuchtmittel, das automatisch mit dem
  Deckel angeht/ausgeht, siehe [Käfigbeleuchtung](#käfigbeleuchtung) unten;
  ohne Auswahl bleibt die Licht-Automatik einfach inaktiv
- Benachrichtigungsziele (optional) → `notify.*`-Entitäten für Warnungen und
  Tageszusammenfassung

Alle Werte lassen sich später über **Reconfigure** (Zahnrad-Menü des Geräts)
erneut anpassen, ohne die Integration neu einrichten zu müssen.

### Erweiterte Einstellungen (Konfigurieren-Button)

- Ideal-Temperaturbereich (min/max)
- Mindest-Tagesstrecke, ab der der Health Score stark abfällt
- Warnungen an/aus (Temperatur, vernachlässigter Käfig, niedriger Score,
  zu wenig Bewegung)
- Tageszusammenfassung an/aus
- Uhrzeit der täglichen Zusammenfassung
- Helligkeit, Übergangszeit, automatisches Ausschalten und Ausschalt-
  Verzögerung der Käfigbeleuchtung (nur wirksam, wenn eine ausgewählt wurde)

Jede Benachrichtigung wird mit dem Namen des Hamsters als Titel und dem
eigentlichen Text als Nachricht verschickt (auf Zielen, die das
unterstützen, z. B. die mobile App).

### Käfigbeleuchtung

Wurde im Schritt "Quell-Sensoren" ein Leuchtmittel ausgewählt, geht es
automatisch an, sobald der Deckel-/Käfigsensor öffnet (mit der im
Expertenmenü eingestellten Helligkeit und optionalem Überblend-Übergang),
und - falls "Käfigbeleuchtung automatisch ausschalten" aktiviert ist -
wieder aus, sobald der Deckel schließt (optional erst nach einer
einstellbaren Verzögerung, z. B. damit noch kurz Licht bleibt, während du
den Deckel schließt). Reagiert auf denselben Türstatus wie
`binary_sensor.hamster_<name>_door`.

## Angelegte Entities

Jede Entity-ID trägt zur Einordnung ein `hamster_`-Präfix vor dem
Hamsternamen (z. B. `sensor.hamster_taco_health_score` für einen Hamster
namens "Taco") - so ist auf einen Blick klar, dass die Entity von dieser
Integration stammt.

| Entity | Beschreibung |
|---|---|
| `sensor.hamster_<name>_health_score` | Gesundheits-Score (0–100 %) |
| `sensor.hamster_<name>_daily_distance` | Laufstrecke seit dem letzten Reset um 9 Uhr morgens (km) |
| `sensor.hamster_<name>_night_distance` | Laufstrecke seit dem letzten Nachtfenster-Start (km) |
| `sensor.hamster_<name>_lifetime_distance` | Laufstrecke seit dem Einrichten des Rad-Sensors, läuft auch nach dem Auszug weiter (km) |
| `sensor.hamster_<name>_current_speed`¹ | Aktuelle Echtzeit-Geschwindigkeit (km/h) |
| `sensor.hamster_<name>_max_speed_tonight`¹ | Höchste Geschwindigkeit seit dem letzten Nachtfenster-Start (km/h) |
| `sensor.hamster_<name>_humidity`² | Luftfeuchtigkeit am Käfig (%) |
| `binary_sensor.hamster_<name>_warning` | Warnung bei niedrigem Score, Extremtemperatur, vernachlässigtem Käfig oder zu wenig Bewegung |
| `binary_sensor.hamster_<name>_door` | Käfigtür offen/geschlossen, inkl. Attribut "seit wie vielen Stunden geschlossen" |
| `date.hamster_<name>_departure_date` | Auszugs-/Sterbedatum - editierbar, standardmäßig leer |
| `number.hamster_<name>_weight` | Gewicht in Gramm - manuell eintragen, z. B. von der Küchenwaage |

¹ Nur vorhanden, wenn ein Geschwindigkeitssensor konfiguriert wurde.
² Nur vorhanden, wenn ein Luftfeuchtigkeitssensor konfiguriert wurde.

Alle Entity-IDs sind unabhängig von der in Home Assistant eingestellten
Sprache immer englisch (`health_score`, nicht `gesundheits_score`) - nur
die angezeigten Namen in der Oberfläche folgen der Sprachsprache.

Der Tages-Reset liegt bewusst auf 9 Uhr morgens statt Mitternacht, damit
eine durchgehende nächtliche Laufphase nicht künstlich mitten in der Nacht
auf zwei Kalendertage aufgeteilt wird.

### Auszug/Tod eines Hamsters

Sobald `date.hamster_<name>_departure_date` auf ein Datum (heute oder in der
Vergangenheit) gesetzt wird, friert die Integration den letzten Stand
(Health Score, Distanzen, ...) endgültig ein - Warnungen werden dabei
gelöscht, es werden ab dann auch keine weiteren Benachrichtigungen mehr
verschickt. Die Quell-Sensoren (Rad/Temperatur/Tür) können danach gefahrlos
einem neuen Hamster zugewiesen werden: Der archivierte Hamster reagiert
nicht mehr darauf, seine `lifetime_distance` bleibt als Vergleichswert
erhalten. Ein neuer Hamster wird einfach als weitere Integrations-Instanz
angelegt (Einstellungen → Geräte & Dienste → Hamster Fitness hinzufügen).

## Eingebaute Karte

Die Integration bringt ihre eigene Lovelace-Karte mit
(`custom_components/hamster_fitness/frontend/hamster-fitness-card.js`) -
kein HACS-Frontend-Paket nötig, genau wie z. B. bei
[home-assistant-flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24).
Sie zeigt Health-Score und Live-Geschwindigkeit als zwei Ringe im selben
Design nebeneinander, darunter eine Aufschlüsselung, wie sich der Score
zusammensetzt (Bewegung/Temperatur/Pflege), sowie Distanzen, Klima,
Gewicht und Käfigtür-Status. Alle Werte sind antippbar und öffnen den
Mehr-Info-Dialog der jeweiligen Entity (z. B. für den Temperaturverlauf).
Für Mobile-Dashboards gibt es einen eigenen, schmaleren Kartenzuschnitt.

Bei UI-verwalteten Dashboards (Standard-Modus "storage") wird die
Ressource automatisch registriert - direkt nach der Installation im
Dashboard-Editor "Karte hinzufügen" suchen: **"Hamster Fitness Card"**.
Über den visuellen Editor (Zahnrad-Symbol beim Bearbeiten der Karte) lässt
sich der Hamster bequem per Entity-Auswahl einstellen, kein manuelles
YAML nötig. Wer YAML bevorzugt:

```yaml
type: custom:hamster-fitness-card
entity: sensor.hamster_taco_health_score   # der Health-Score-Sensor des Hamsters
title: Taco                                 # optional
max_speed: 5                                # optional, km/h - Skala des Geschwindigkeits-Rings
```

Nutzt du ein YAML-verwaltetes Dashboard (Modus "yaml"), muss die Ressource
einmalig manuell ergänzt werden: Einstellungen → Dashboards → Menü (⋮) →
Ressourcen → Ressource hinzufügen → URL
`/hamster_fitness-frontend/hamster-fitness-card.js`, Typ "JavaScript-Modul".

### Ranking-Karte

Im selben Karten-Bundle enthalten: **"Hamster Fitness Ranking Card"**
(`type: custom:hamster-fitness-ranking-card`) vergleicht automatisch alle
Hamster in diesem Home Assistant nach Lebenszeit-Distanz - keine
Konfiguration nötig, sie findet jede `sensor.hamster_<name>_lifetime_distance`
selbst. Bereits ausgezogene Hamster bleiben mit ihrem eingefrorenen Endstand
Teil der Rangliste (🪦-Symbol). Optional ein Titel:

```yaml
type: custom:hamster-fitness-ranking-card
title: Hamster-Ranking   # optional
```
