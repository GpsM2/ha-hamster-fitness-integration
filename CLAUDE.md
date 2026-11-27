# Hamster Fitness – Projektregeln für Claude

Diese Datei enthält verbindliche Arbeitsanweisungen für Claude in diesem
Repository. Sie ergänzt README.md (Nutzer-Doku, Englisch), richtet sich
aber ausschließlich an den Entwicklungsprozess. Geplante Arbeit wird über
GitHub Issues getrackt (Milestones bündeln zusammengehörige Batches),
nicht mehr über eine ROADMAP.md-Datei im Repo.

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

## Neue Lovelace-Karte? Vier Dinge gehören zusammen

Kommt eine Karte dazu (oder wird eine umbenannt/entfernt), müssen diese
vier Stellen gemeinsam angefasst werden – sonst laufen Issues zu dieser
Karte unbeschriftet ins Leere und die Doku wird still falsch:

1. Eintrag in `JS_MODULES` (`const.py`) inkl. eigener Cache-Busting-Version.
2. GitHub-Label `card: <name>` anlegen
   (`gh label create "card: <name>" --color ... --description ...`).
3. Passende Regex-Regel in `.github/issue-labeler.yml` ergänzen – auf
   Custom-Element-Name, Dateiname und die umgangssprachliche Bezeichnung,
   zweisprachig (EN/DE). Der Auto-Labeler taggt Issues darüber automatisch
   der richtigen Karte zu.
4. Eigene Seite unter `docs/cards/` plus Zeile in der README-Tabelle.

## Standards (Home Assistant Quality Scale)

- Python 3.14+ (Mindestversion Home Assistant 2026.11, steht in
  `hacs.json`), vollständig `asyncio`-basiert – keine blockierenden
  I/O-Aufrufe (kein `requests`, kein synchrones Networking-/Datei-I/O) im
  Event-Loop. Unvermeidbare blockierende Aufrufe laufen über
  `hass.async_add_executor_job`.
- Einrichtung ausschließlich über den UI-Config-Flow (`config_flow.py`)
  inkl. Options-Flow – keine YAML-Konfiguration für den Nutzer.
- Strikte Type Hints im gesamten Code (`from __future__ import
  annotations`, vollständige Signaturen inkl. Rückgabetypen).
- Vordefinierte `DeviceClass`/`StateClass`/`UnitOf...`-Konstanten aus
  Home Assistant verwenden, keine Freitext-Einheiten.
- UI-Texte (Config-Flow, Optionen, Entity-Namen) über
  `translations/en.json` (Quelle) und `translations/de.json` pflegen –
  keine hartcodierten UI-Strings in `.py`-Dateien. Gilt auch für
  dynamisch zusammengesetzte Laufzeittexte (Warnmeldungen,
  Push-Benachrichtigungen) – siehe `runtime_text.py`, Schlüssel unter der
  `exceptions`-Sektion (die einzige Kategorie, die hassfest für frei
  formulierte Laufzeittexte mit Platzhaltern zulässt). Ein `strings.json` gibt es bewusst nicht: Custom
  Integrations liefern fertige Dateien in `translations/`, eine zweite,
  händisch synchron zu haltende Kopie war in 0.2.6 schon einmal die
  Ursache eines echten Bugs.
- Tests unter `tests/` (pytest, idealerweise
  `pytest-homeassistant-custom-component`), mindestens für
  `config_flow.py` und die Sensor-Plattform.
- Code sollte `ruff` und `mypy` sauber durchlaufen, bevor er gemergt wird.

## Tests

Die Tests brauchen Python 3.14 (die aktuelle
`pytest-homeassistant-custom-component` verlangt es). Auf dem
Windows-Rechner ist nur 3.12 installiert, die lokale `.venv` taugt
deshalb nicht mehr – gelaufen wird in Docker (kopiert nur, was die
Tests brauchen; ein Kopieren des ganzen OneDrive-Ordners dauert Minuten),
die CI macht dasselbe auf Ubuntu. Neue Testbibliothek: Volume
`hf-venv-314` löschen, dann baut der Befehl es neu:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$(cygpath -w "$PWD"):/src:ro" -v hf-venv-314:/venv python:3.14-slim bash -c "mkdir /w && cd /src && cp -r custom_components tests pyproject.toml requirements_test.txt .github /w/ && cd /w && ([ -x /venv/bin/pytest ] || (python -m venv /venv && /venv/bin/pip install -q -r requirements_test.txt)) && /venv/bin/ruff check custom_components tests && /venv/bin/mypy custom_components/hamster_fitness && /venv/bin/pytest tests/ -q -p no:cacheprovider"
```

Die Testbibliothek hinkt Home Assistant um etwa eine Version hinterher
(Stand 0.11.4: Tests gegen 2026.10.4, Mindestversion 2026.11). Was erst
ab der Mindestversion existiert, ist deshalb mit einem `ponytail:`-
Kommentar markiert und fällt weg, sobald die Bibliothek nachzieht.

`tests/conftest.py` enthält zwei eng begrenzte Windows-Ausnahmen
(Loopback-Socketpair für asyncio, überlebender Accept-Task); beide
greifen nur bei `sys.platform == "win32"`.

Ein autouse-Fixture entlädt nach jedem Test alle Config-Entries. Das ist
kein Kosmetikschritt - ohne das bleiben die per `entry.async_on_unload()`
registrierten Timer scharf und verdecken echte Fehler.

## Workflow

- Code-Änderungen nicht direkt auf `main` committen. Für jede
  nichttriviale Änderung einen neuen Branch erstellen
  (`git checkout -b <kurzer-branch-name>`) und einen Pull Request öffnen.
- Commit-Messages beschreiben das "Warum", nicht nur das "Was".
- `manifest.json`'s `version` nur bei tatsächlichen Code-Änderungen
  hochzählen (Patch-Version, z. B. 0.2.3 → 0.2.4) – nicht bei reinen
  README-/Doku-Änderungen.
- Größere Refactorings (z. B. Architektur-Umbauten) vorher als Plan
  vorstellen und explizit bestätigen lassen, bevor der Code angefasst
  wird.

## Umgang mit externen Pull Requests (STRIKT EINHALTEN)

Bevor an einer Issue gearbeitet wird, muss geprüft werden, ob dazu
bereits ein Pull Request von einem Contributor vorliegt (`gh pr list`,
auch auf Verweise zur Issue-Nummer in Titel/Body prüfen). Das gilt vor
jedem Arbeitsbeginn an einer Issue, nicht nur einmalig zu Sessionbeginn.

Trifft ein Pull Request von einem Contributor ein – zu einer bereits
gelösten Issue, oder inhaltlich nicht zu den Zielen des Projekts
passend –, wird er nicht stillschweigend ignoriert oder übernommen,
sondern beantwortet:

- Klarstellen, dass die Antwort von Claude Code stammt.
- Höflich ablehnen.
- Einen kurzen, fachlichen Grund für die Ablehnung nennen.

Ist der Pull Request inhaltlich gut, wird er dem Nutzer vorgeschlagen –
nicht eigenständig gemergt. Pull Requests von Dritten (nicht von Claude
selbst erstellt) benötigen vor dem Merge immer die ausdrückliche
Freigabe des Nutzers, ohne Ausnahme.

## Release-Regel (STRIKT EINHALTEN)

Sobald ein Befehl zur Erstellung eines Releases oder Git-Tags erteilt
wird, MUSS Claude den Nutzer zuerst explizit fragen:

> „Soll dieses Release als Beta-Version (Pre-release z. B. v1.0.0-beta.1)
> für HACS-Tester oder als finale Standard-Release (z. B. v1.0.0)
> veröffentlicht werden?“

Kein Release/Tag wird erstellt, bevor diese Frage gestellt und eindeutig
beantwortet wurde – unabhängig davon, wie der ursprüngliche Befehl
formuliert war.
