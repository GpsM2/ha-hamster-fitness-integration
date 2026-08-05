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
- `hamster_fitness` fragt jetzt wie im Handel üblich den **Raddurchmesser**
  statt des Radumfangs ab (intern weiterhin über Umfang = Durchmesser × π
  in die Distanzberechnung eingerechnet) - Grenzen/Default sind bewusst
  identisch zum ESPHome-Feld "Rad Durchmesser", damit hier wie dort derselbe
  Wert eingetragen werden kann. Löst die weiter unten vermutete
  Verwechslungsgefahr strukturell, nicht nur per Beschreibungstext
- Integrations-Icon entworfen, freigestellt, zugeschnitten und **aktiv**
  (`custom_components/hamster_fitness/brand/`, Quelle: GpsM2) - dank der
  neuen [Brands-Proxy-API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
  (ab HA 2026.3) liegt das Icon direkt in der Integration selbst, keine
  externe PR bei `home-assistant/brands` mehr nötig. Dafür `manifest.json`
  jetzt mit `"homeassistant": "2026.3.0"` als Mindestversion.
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

Der wahrscheinlichste Auslöser (Radumfang- statt Raddurchmesser-Feld, siehe
oben) ist durch die Umstellung auf ein gemeinsames Durchmesser-Feld
strukturell behoben. Nach dem Update einmal per Reconfigure den (jetzt als
Durchmesser interpretierten) Wert prüfen/neu eintragen - falls die
Diskrepanz danach weiterhin auftritt, war die Ursache etwas anderes und
müsste anhand konkreter Sensor-Werte neu untersucht werden.
