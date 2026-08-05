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
- Bugfix: `[%key:...%]`-Verweise in `strings.json`/`translations/de.json`
  wurden bei Reconfigure als Rohtext angezeigt statt aufgelöst - dieser
  Mechanismus funktioniert nur beim Build von Home Assistant Core
  (hassfest), nicht zur Laufzeit bei Custom Integrations. Alle Verweise
  durch ausgeschriebenen Text ersetzt
- Geräte-/Entity-Namen tragen jetzt ein `hamster_`-Präfix vor dem
  Hamsternamen (z. B. `sensor.hamster_taco_health_score`), damit auf einen
  Blick klar ist, dass eine Entity von dieser Integration stammt
- ESPHome-Firmware: Entity-Namen und Gerätename von Deutsch auf Englisch
  umgestellt, Datei/Gerätename von kryptisch (`esphome-web-d018de`) auf
  sprechend (`hamster-wheel-sensor`) umbenannt
- Eigene, mit der Integration ausgelieferte Lovelace-Karte
  (`hamster-fitness-card`, siehe `custom_components/hamster_fitness/frontend/`) -
  wird bei UI-verwalteten Dashboards automatisch als Ressource registriert,
  nach demselben Muster wie z. B.
  [home-assistant-flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24).
  Kein HACS-Frontend-Paket mehr nötig für eine ansprechende Einzelkarte
- Wheel-Sensor/Geschwindigkeitssensor-Auswahl im Config Flow enger
  eingegrenzt (`device_class: speed` für den Geschwindigkeitssensor, dafür
  in der ESPHome-Firmware ergänzt) - bewusst kein harter Filter auf den
  Umdrehungssensor, da das eine bereits gewählte Entity beim Reconfigure
  unsichtbar machen könnte, falls sie eine andere Einheit als "rot." nutzt
- Karte: visueller Editor (über `ha-form`, wie bei den eingebauten Karten),
  Konfiguration jetzt über einen Entity-Picker (Health-Score-Sensor) statt
  Freitext-Hamstername, zwei Ringe nebeneinander (Health Score + Live-
  Geschwindigkeit im selben Design), Mobile-Optimierung (eigene
  Breakpoint-Anpassung für schmale Karten), anklickbare Werte öffnen den
  Mehr-Info-Dialog der jeweiligen Entity (z. B. Temperaturverlauf), sowie
  eine immer sichtbare Score-Aufschlüsselung (Bewegung/Temperatur/Pflege
  mit Punktabzug), damit auch ohne aktive Warnung klar ist, wie sich der
  Score zusammensetzt
- Käfigbeleuchtung (`door_light.py`, optionales `light_entity`-Feld): geht
  automatisch an, sobald der Deckel-/Käfigsensor öffnet, und (falls
  aktiviert) wieder aus, sobald er schließt. Konfigurierbar im
  Expertenmenü: Helligkeit, optionaler zeitlicher Übergang (Transition),
  automatisches Ausschalten an/aus, optionale Ausschalt-Verzögerung
- Ranking-Karte (`hamster-fitness-ranking-card`, im selben Karten-Bundle):
  findet automatisch alle Hamster in diesem Home Assistant über
  `sensor.hamster_<name>_lifetime_distance` und listet sie sortiert nach
  Lebenszeit-Distanz - keine Konfiguration nötig, bereits ausgezogene
  Hamster bleiben mit eingefrorenem Endstand Teil der Rangliste
- `examples/dashboard_simple.yaml` und `examples/dashboard_taco.yaml`
  entfernt - die eingebauten Karten (`hamster-fitness-card`,
  `hamster-fitness-ranking-card`) ersetzen sie vollständig

## 🚧 Geplant

_Aktuell keine offenen Punkte - neue Wünsche werden hier ergänzt._

## 🔍 Zu prüfen

### Distanzberechnung wirkt hoch im Vergleich zur ESP-eigenen Berechnung

Der wahrscheinlichste Auslöser (Radumfang- statt Raddurchmesser-Feld, siehe
oben) ist durch die Umstellung auf ein gemeinsames Durchmesser-Feld
strukturell behoben. Nach dem Update einmal per Reconfigure den (jetzt als
Durchmesser interpretierten) Wert prüfen/neu eintragen - falls die
Diskrepanz danach weiterhin auftritt, war die Ursache etwas anderes und
müsste anhand konkreter Sensor-Werte neu untersucht werden.
