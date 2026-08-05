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
- [`examples/dashboard_taco.yaml`](examples/dashboard_taco.yaml) — ein
  Beispiel-Lovelace-Dashboard im "Samsung Health"-Stil.

## Lizenz

Dieses Projekt steht unter der [PolyForm Noncommercial License 1.0.0](LICENSE).
Kurz zusammengefasst: Jeder darf den Code für **nicht-kommerzielle Zwecke**
(privat, Hobby, Bildung, Forschung) frei nutzen, verändern und weitergeben.
Der Urheber (GpsM2) behält alle Rechte und kann das Projekt unabhängig davon
auch kommerziell nutzen oder lizenzieren.

## 1. Sensor-Hardware bauen (ESPHome)

Benötigt wird ein ESP8266/D1-Mini-Board mit einer optischen Lichtschranke am
GPIO4 (D2), die bei jeder Rad-Umdrehung einmal auslöst.

1. `esphome/esphome-web-d018de.yaml` in dein ESPHome-Setup übernehmen
   (Dateiname/`esphome.name` ggf. anpassen).
2. In `secrets.yaml` die referenzierten Secrets ergänzen:
   `wifi_ssid`, `wifi_password`, `esphome_web_d027a9__encryption_key`,
   `esphome_web_d018de__ota_password`.
3. Flashen (per USB beim Ersteinrichten, danach OTA).
4. Nach dem Ersteinrichten in Home Assistant automatisch über die ESPHome-
   Integration verfügbar. Der reale Raddurchmesser lässt sich über die
   Number-Entity **"Rad Durchmesser"** direkt in Home Assistant einstellen.

Die Firmware legt u. a. folgende Entities an:

| Entity | Bedeutung |
|---|---|
| `sensor.hamsterrad_geschwindigkeit` | Aktuelle Geschwindigkeit (km/h) |
| `sensor.hamsterrad_maximalgeschwindigkeit_heute` | Tages-Maximalgeschwindigkeit |
| `sensor.hamsterrad_strecke_gesamt` | Kumulierte Strecke seit Inbetriebnahme (km) |
| `sensor.hamsterrad_strecke_heute` | Strecke seit dem letzten Reset um 08:00 Uhr (km) |
| `sensor.hamsterrad_umdrehungen_gesamt` | Roher, nie zurückgesetzter Umdrehungszähler |

**Wichtig:** Für die `hamster_fitness`-Integration unten muss
`sensor.hamsterrad_umdrehungen_gesamt` (der rohe Umdrehungszähler) als
"Rad-Umdrehungssensor" ausgewählt werden — nicht einer der bereits fertig in
km umgerechneten Strecken-Sensoren. Die Integration multipliziert den
Sensorwert selbst mit dem konfigurierten Radumfang.

**Achtung, Verwechslungsgefahr:** Das ESPHome-Feld "Rad Durchmesser" erwartet
den **Durchmesser** (rechnet intern × π), das `hamster_fitness`-Feld
"Radumfang" weiter unten dagegen den fertigen **Umfang** direkt. Trag hier
nicht denselben Zahlenwert ein wie dort, sondern: Umfang = Durchmesser × π.
`sensor.hamsterrad_geschwindigkeit` (Echtzeit-Geschwindigkeit) lässt sich
optional ebenfalls in `hamster_fitness` einbinden, siehe Schritt 2 unten.

## 2. Integration installieren

### Über HACS (empfohlen, sobald das Repo als HACS-Repository hinzugefügt ist)

1. HACS → Integrationen → Menü (⋮) → Benutzerdefinierte Repositories.
2. URL dieses Repos eintragen, Kategorie "Integration".
3. "Hamster Fitness" installieren, Home Assistant neu starten.

### Manuell

`custom_components/hamster_fitness/` in das `custom_components`-Verzeichnis
deiner Home-Assistant-Konfiguration kopieren und Home Assistant neu starten.

## 3. Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → "Hamster Fitness".

**Schritt 1 (Basisdaten):** Name des Hamsters, Einzugsdatum, Radumfang (cm).

**Schritt 2 (Quell-Sensoren):**

- Rad-Umdrehungssensor → `sensor.hamsterrad_umdrehungen_gesamt`
- Temperatursensor → dein Temperatursensor am Käfig (`device_class: temperature`)
- Deckel-/Käfigöffnungssensor → dein Tür-/Öffnungskontakt (`device_class: door`
  oder `opening`)
- Luftfeuchtigkeitssensor (optional) → nur nötig, falls vorhanden; ohne
  Auswahl wird einfach keine Feuchtigkeits-Entity angelegt
- Echtzeit-Geschwindigkeitssensor (optional) → z. B.
  `sensor.hamsterrad_geschwindigkeit`; ohne Auswahl werden keine
  Geschwindigkeits-Entities angelegt
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

Jede Benachrichtigung wird mit dem Namen des Hamsters als Titel und dem
eigentlichen Text als Nachricht verschickt (auf Zielen, die das
unterstützen, z. B. die mobile App).

## Angelegte Entities

| Entity | Beschreibung |
|---|---|
| `sensor.<hamster>_health_score` | Gesundheits-Score (0–100 %) |
| `sensor.<hamster>_daily_distance` | Laufstrecke seit dem letzten Reset um 9 Uhr morgens (km) |
| `sensor.<hamster>_night_distance` | Laufstrecke seit dem letzten Nachtfenster-Start (km) |
| `sensor.<hamster>_lifetime_distance` | Laufstrecke seit dem Einrichten des Rad-Sensors, läuft auch nach dem Auszug weiter (km) |
| `sensor.<hamster>_current_speed`¹ | Aktuelle Echtzeit-Geschwindigkeit (km/h) |
| `sensor.<hamster>_max_speed_tonight`¹ | Höchste Geschwindigkeit seit dem letzten Nachtfenster-Start (km/h) |
| `sensor.<hamster>_humidity`² | Luftfeuchtigkeit am Käfig (%) |
| `binary_sensor.<hamster>_warning` | Warnung bei niedrigem Score, Extremtemperatur, vernachlässigtem Käfig oder zu wenig Bewegung |
| `binary_sensor.<hamster>_door` | Käfigtür offen/geschlossen, inkl. Attribut "seit wie vielen Stunden geschlossen" |
| `date.<hamster>_departure_date` | Auszugs-/Sterbedatum - editierbar, standardmäßig leer |
| `number.<hamster>_weight` | Gewicht in Gramm - manuell eintragen, z. B. von der Küchenwaage |

¹ Nur vorhanden, wenn ein Geschwindigkeitssensor konfiguriert wurde.
² Nur vorhanden, wenn ein Luftfeuchtigkeitssensor konfiguriert wurde.

Der Tages-Reset liegt bewusst auf 9 Uhr morgens statt Mitternacht, damit
eine durchgehende nächtliche Laufphase nicht künstlich mitten in der Nacht
auf zwei Kalendertage aufgeteilt wird.

### Auszug/Tod eines Hamsters

Sobald `date.<hamster>_departure_date` auf ein Datum (heute oder in der
Vergangenheit) gesetzt wird, friert die Integration den letzten Stand
(Health Score, Distanzen, ...) endgültig ein - Warnungen werden dabei
gelöscht, es werden ab dann auch keine weiteren Benachrichtigungen mehr
verschickt. Die Quell-Sensoren (Rad/Temperatur/Tür) können danach gefahrlos
einem neuen Hamster zugewiesen werden: Der archivierte Hamster reagiert
nicht mehr darauf, seine `lifetime_distance` bleibt als Vergleichswert
erhalten. Ein neuer Hamster wird einfach als weitere Integrations-Instanz
angelegt (Einstellungen → Geräte & Dienste → Hamster Fitness hinzufügen).

## Beispiel-Dashboards

- [`examples/dashboard_simple.yaml`](examples/dashboard_simple.yaml) —
  nur Standard-Lovelace-Karten (`glance`, `gauge`, `statistics-graph`,
  `entities`), keine HACS-Zusatzkarten nötig. Der einfachste Einstieg.
- [`examples/dashboard_taco.yaml`](examples/dashboard_taco.yaml) — eine
  aufwendigere Ansicht im "Samsung Health"-Stil, benötigt die
  HACS-Frontend-Karten [Mushroom](https://github.com/piitaya/lovelace-mushroom)
  und [ApexCharts Card](https://github.com/RomRider/apexcharts-card).

Entity-IDs in beiden Beispielen gehen von einem Hamster namens "Taco" aus
und müssen an den tatsächlichen Gerätenamen angepasst werden.
