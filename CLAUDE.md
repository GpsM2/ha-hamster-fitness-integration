# Hamster Fitness – Projektregeln für Claude

Diese Datei enthält verbindliche Arbeitsanweisungen für Claude in diesem
Repository. Sie ergänzt README.md (Nutzer-Doku, Englisch) und ROADMAP.md
(Verlauf, Englisch), richtet sich aber ausschließlich an den
Entwicklungsprozess.

## Projektziel

Hamster Fitness ist eine Home-Assistant-Custom-Integration
(`custom_components/hamster_fitness/`). Mittelfristiges Ziel: Code-Qualität
auf einem Niveau, das eine spätere Aufnahme in Home Assistant Core
(Gold/Platinum Quality Scale) realistisch macht – auch wenn das Projekt
aktuell privat/eigenständig bleibt und nicht jede Regel sofort erzwungen
wird.

## Scope dieses Repos (STRIKT EINHALTEN)

Dieses Repository (`ha-hamster-fitness-integration`) verwaltet
**ausschließlich**:

- Python-Code der Home-Assistant-Integration
  (`custom_components/hamster_fitness/`),
- die Lovelace-Karten (`custom_components/hamster_fitness/frontend/`),
- sowie die zugehörigen Software-Tests (`tests/`).

Hardware-Inhalte (ESPHome-Firmware, CAD/3D-Druck-Dateien, Platinen/KiCad,
Bauanleitungen) gehören **nicht** hierher, sondern ins separate Repo
[hamster-fitness-hardware](https://github.com/GpsM2/hamster-fitness-hardware).
Falls eine Anfrage Hardware-Dateien in diesem Repo anlegen oder ändern
würde, bitte nachfragen statt sie hier einzufügen – vermutlich gehört sie
ins Hardware-Repo.

## Standards (Home Assistant Quality Scale)

- Python 3.12+, vollständig `asyncio`-basiert – keine blockierenden
  I/O-Aufrufe (kein `requests`, kein synchrones Networking-/Datei-I/O) im
  Event-Loop. Unvermeidbare blockierende Aufrufe laufen über
  `hass.async_add_executor_job`.
- Einrichtung ausschließlich über den UI-Config-Flow (`config_flow.py`)
  inkl. Options-Flow – keine YAML-Konfiguration für den Nutzer.
- Strikte Type Hints im gesamten Code (`from __future__ import
  annotations`, vollständige Signaturen inkl. Rückgabetypen).
- Vordefinierte `DeviceClass`/`StateClass`/`UnitOf...`-Konstanten aus
  Home Assistant verwenden, keine Freitext-Einheiten.
- UI-Texte (Config-Flow, Optionen, Entity-Namen) über `strings.json`
  (englische Quelle) und `translations/*.json` pflegen – keine
  hartcodierten UI-Strings in `.py`-Dateien. Gilt auch für dynamisch
  zusammengesetzte Laufzeittexte (Warnmeldungen, Push-Benachrichtigungen) –
  siehe `runtime_text.py`, Schlüssel unter der `messages`-Sektion.
- **Wichtig:** Anders als bei echten Home-Assistant-Core-Integrationen wird
  `translations/en.json` bei dieser (Custom-)Integration NICHT automatisch
  aus `strings.json` generiert (das übernimmt nur hassfest beim Core-Build).
  `strings.json` und `translations/en.json` müssen deshalb händisch
  identisch gehalten werden – bei jeder Änderung an einem der beiden Werte
  auch den anderen aktualisieren, sonst fehlt englischsprachigen Nutzern
  der Text komplett (siehe ROADMAP für den Bugfix-Hintergrund).
- Tests unter `tests/` (pytest, idealerweise
  `pytest-homeassistant-custom-component`), mindestens für
  `config_flow.py` und die Sensor-Plattform.
- Code sollte `ruff` und `mypy` sauber durchlaufen, bevor er gemergt wird.

## Workflow

- Code-Änderungen nicht direkt auf `main` committen. Für jede
  nichttriviale Änderung einen neuen Branch erstellen
  (`git checkout -b <kurzer-branch-name>`) und einen Pull Request öffnen.
- Commit-Messages beschreiben das "Warum", nicht nur das "Was".
- `manifest.json`'s `version` nur bei tatsächlichen Code-Änderungen
  hochzählen (Patch-Version, z. B. 0.2.3 → 0.2.4) – nicht bei reinen
  README-/ROADMAP-Änderungen.
- Größere Refactorings (z. B. Architektur-Umbauten) vorher als Plan
  vorstellen und explizit bestätigen lassen, bevor der Code angefasst
  wird.

## Release-Regel (STRIKT EINHALTEN)

Sobald ein Befehl zur Erstellung eines Releases oder Git-Tags erteilt
wird, MUSS Claude den Nutzer zuerst explizit fragen:

> „Soll dieses Release als Beta-Version (Pre-release z. B. v1.0.0-beta.1)
> für HACS-Tester oder als finale Standard-Release (z. B. v1.0.0)
> veröffentlicht werden?“

Kein Release/Tag wird erstellt, bevor diese Frage gestellt und eindeutig
beantwortet wurde – unabhängig davon, wie der ursprüngliche Befehl
formuliert war.
