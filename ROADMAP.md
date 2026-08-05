# Roadmap

Diese Datei hält fest, was schon funktioniert und was als Nächstes geplant
ist. Erledigte Punkte bleiben stehen, damit die Historie nachvollziehbar
bleibt.

## ✅ Erledigt

- Health-Score-Berechnung aus Laufstrecke, Temperatur und Käfigpflege, mit
  konfigurierbaren Schwellenwerten
- Config Flow (Basisdaten + Quellsensoren) und Options Flow (Expertenmenü)
- Reconfigure Flow: Basisdaten und Quellsensoren lassen sich nachträglich
  ändern, ohne die Integration neu einzurichten
- Getrennt schaltbare Benachrichtigungen (Warnungen / Tageszusammenfassung)
  mit konfigurierbarer Uhrzeit
- Natürlich formulierte, deutsch formatierte Push-Benachrichtigungen
  (Titel = Hamstername, Inhalt = eigentliche Mitteilung)
- Tages-Reset um 9 Uhr morgens statt Mitternacht, damit eine durchgehende
  nächtliche Laufphase nicht künstlich zerschnitten wird
- Bugfix: Die Distanz-Baseline wird beim Wechsel des Rad-Sensors (z. B. per
  Reconfigure) korrekt neu gesetzt, statt eine Phantom-Distanz aus zwei
  unterschiedlichen Sensor-Skalen zu berechnen
- ESPHome-Firmware: roher, nie zurückgesetzter Umdrehungszähler
  (`sensor_pulses_total`) als eigene HA-Entity exponiert
- Deutsche Übersetzung korrekt unter `translations/de.json` eingebunden
- `LICENSE` (PolyForm Noncommercial 1.0.0), `README.md`, `hacs.json`,
  GitHub-Repository
- Bugfix: Distanzberechnung lief nach wenigen echten Umdrehungen auf 9,42 km
  auf, weil beim Sensor-Wechsel per Reconfigure die alte Baseline gegen den
  neuen Sensor weitergerechnet wurde
- Einfaches Beispiel-Dashboard (`examples/dashboard_simple.yaml`) nur mit
  Standard-Lovelace-Karten, keine HACS-Zusatzkarten nötig
- Auszugsdatum (`date.<hamster>_departure_date`) pro Hamster: sobald
  gesetzt, friert die Integration den letzten Stand ein und reagiert nicht
  mehr auf die (ggf. neu zugewiesenen) Quell-Sensoren
- `sensor.<hamster>_lifetime_distance`: Strecke seit dem Einrichten des
  Rad-Sensors, überlebt Geräte-Reboots und bleibt nach dem Auszug als
  Vergleichswert erhalten
- Gewichts-Tracking (`number.<hamster>_weight`, Gramm, manuell einzutragen)
- Beschreibung des Radumfang-Felds klargestellt (Umfang, nicht Durchmesser),
  um Verwechslungen mit ESPHome-seitigen Durchmesser-Feldern zu vermeiden
- Integrations-Icon entworfen, freigestellt und zugeschnitten
  (`brands/hamster_fitness/`) - Quelle: GpsM2
- Alle relevanten Daten laufen jetzt über die Integration selbst, keine
  separate ESP-Entity nötig für ein vollständiges Dashboard:
  - `binary_sensor.<hamster>_door` (Käfigtür-Status, spiegelt den
    konfigurierten Tür-/Deckelsensor, inkl. "seit wie vielen Stunden
    geschlossen" als Attribut)
  - `sensor.<hamster>_humidity` (optional, falls ein Feuchtigkeitssensor
    ausgewählt wurde)
  - `sensor.<hamster>_night_distance` (Strecke seit dem Nachtfenster-Start)
  - `sensor.<hamster>_current_speed` und `sensor.<hamster>_max_speed_tonight`
    (optional, falls ein Echtzeit-Geschwindigkeitssensor ausgewählt wurde)
  - Beispiel-Dashboard (`examples/dashboard_simple.yaml`) inkl.
    Echtzeit-Geschwindigkeits-Gauge entsprechend erweitert

## 🚧 Geplant

### Icon bei home-assistant/brands einreichen

Das fertige Icon liegt bereit (`brands/hamster_fitness/`), muss aber noch
per Pull Request bei [home-assistant/brands](https://github.com/home-assistant/brands)
eingereicht werden, damit es tatsächlich in der Home-Assistant-Oberfläche
erscheint (HA lädt Integrations-Icons zentral von dort, nicht aus diesem
Repo) - wartet noch auf grünes Licht.

### Fertige Lovelace-Karte/-Strategy

Eine eigene, mit der Integration ausgelieferte Lovelace-Karte oder
-Strategy, die pro Hamster automatisch eine passende Ansicht generiert -
als Alternative zu den beiden manuell einzurichtenden Beispiel-Dashboards.
Deutlich größerer Aufwand (eigenes Frontend-Paket, Registrierung als
Lovelace-Resource) - nur sinnvoll, wenn das Projekt über den privaten
Gebrauch hinauswächst.

### Ranking-Card für mehrere Hamster

Die Rohdaten dafür stehen bereits (`sensor.<hamster>_lifetime_distance`
je Hamster, auch nach dem Auszug eingefroren erhalten), eine fertige
Vergleichs-/Ranking-Karte über mehrere Hamster-Geräte hinweg (z. B. "wer
ist insgesamt am meisten gelaufen?") gibt es aber noch nicht. Aktuell
lässt sich das manuell per `entities`-Karte mit den `lifetime_distance`-
Sensoren aller Hamster nachbauen.

## 🔍 Zu prüfen

### Distanzberechnung wirkt hoch im Vergleich zur ESP-eigenen Berechnung

Wahrscheinlichste Ursache: `wheel_circumference` in `hamster_fitness`
erwartet den **Umfang**, das ESPHome-Feld "Rad Durchmesser" dagegen den
**Durchmesser** (wird dort intern × π gerechnet) - beide Felder hatten
zufällig denselben Default-Wert (28.0), was die Verwechslung begünstigt
(die Feldbeschreibung wurde inzwischen klargestellt, siehe oben). Noch
nicht abschließend anhand echter Werte verifiziert.
