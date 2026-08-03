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

## 🚧 Geplant

### Integrations-Icon

Ein erster Entwurf wurde verworfen und muss neu gestaltet werden. Für die
Anzeige in der Home-Assistant-Oberfläche muss das fertige Icon zusätzlich
per Pull Request bei [home-assistant/brands](https://github.com/home-assistant/brands)
eingereicht werden (HA lädt Integrations-Icons zentral von dort, nicht aus
diesem Repo).

### Einfachere Dashboard-Cards

Das aktuelle Beispiel-Dashboard (`examples/dashboard_taco.yaml`) braucht
zwei zusätzliche HACS-Frontend-Karten (Mushroom, ApexCharts) - das ist eine
Einstiegshürde für weniger technische Nutzer.

Konzept:

- **Kurzfristig:** ein zweites Beispiel-Dashboard nur mit
  Standard-Lovelace-Karten (`entities`, `gauge`, `statistics-graph`,
  `glance`), ohne jede HACS-Abhängigkeit - funktioniert sofort nach der
  Installation, ohne dass zusätzliche Frontend-Karten eingerichtet werden
  müssen.
- **Mittelfristig:** eine eigene, mit der Integration ausgelieferte
  Lovelace-Karte oder -Strategy, die pro Hamster automatisch eine passende
  Ansicht generiert. Deutlich größerer Aufwand (eigenes Frontend-Paket,
  Registrierung als Lovelace-Resource) - nur sinnvoll, wenn das Projekt
  über den privaten Gebrauch hinauswächst.

### Lebenszyklus mehrerer Hamster

Hamster ziehen alle 2-3 Jahre ein und aus. Geplant:

- Auszugsdatum ("Sterbedatum") pro Hamster-Gerät, analog zum bereits
  vorhandenen Einzugsdatum
- Automatische Archivierung ausgezogener Hamster (kein aktiver
  Health-Score/keine Warnungen mehr, Historie bleibt erhalten)
- Vergleich/Ranking zwischen Hamstern, auch über den eigenen Auszug hinaus
  (z. B. Lifetime-Distanz-Ranking: "wer ist am meisten gelaufen?")

Mehrere Hamster gleichzeitig sind technisch schon heute möglich (jede
Integrations-Instanz ist ein eigenes Gerät mit eigenen Entities) - offen ist
nur die Lebenszyklus- und Vergleichs-Ebene obendrauf.

### Gewichts-Tracking

Editierbare Gewichts-Entity (Gramm) pro Hamster, um den Gewichtsverlauf über
die Zeit zu beobachten.
