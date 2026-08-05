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

## 🚧 Geplant

### Integrations-Icon

Ein erster Entwurf wurde verworfen und muss neu gestaltet werden. Für die
Anzeige in der Home-Assistant-Oberfläche muss das fertige Icon zusätzlich
per Pull Request bei [home-assistant/brands](https://github.com/home-assistant/brands)
eingereicht werden (HA lädt Integrations-Icons zentral von dort, nicht aus
diesem Repo).

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
