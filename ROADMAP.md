# Roadmap

This file tracks what already works and what's planned next. Finished
items stay listed so the history stays traceable.

## ✅ Done

- Health-score calculation from running distance, temperature, and cage
  care, with configurable thresholds
- Config flow (basic info + source sensors) and options flow (advanced
  settings)
- Reconfigure flow: basic info and source sensors can be changed later
  without setting up the integration from scratch
- Independently toggleable notifications (warnings / daily summary) with
  a configurable time
- Naturally worded, German-formatted push notifications (title = hamster
  name, body = the actual message)
- Daily reset moved to 9 AM instead of midnight, so one continuous night
  of running isn't artificially split in two
- Bugfix: the distance baseline is now reset correctly when the wheel
  sensor is swapped (e.g. via Reconfigure), instead of computing a
  phantom distance from two unrelated sensor scales
- ESPHome firmware: raw, never-reset rotation counter
  (`sensor_pulses_total`) exposed as its own HA entity
- German translation correctly wired up under `translations/de.json`
- `LICENSE` (PolyForm Noncommercial 1.0.0), `README.md`, `hacs.json`,
  GitHub repository
- Bugfix: distance calculation jumped to 9.42 km after only a few real
  rotations, because swapping the wheel sensor via Reconfigure kept
  computing against the old baseline
- Simple example dashboard (`examples/dashboard_simple.yaml`) using only
  stock Lovelace cards, no HACS cards required
- Departure date (`date.<hamster>_departure_date`) per hamster: once set,
  the integration freezes the last snapshot and stops reacting to the
  (possibly reassigned) source sensors
- `sensor.<hamster>_lifetime_distance`: distance since the wheel sensor
  was first set up, survives device reboots, and stays available as a
  comparison value after a hamster departs
- Weight tracking (`number.<hamster>_weight`, grams, entered by hand)
- `hamster_fitness` now asks for the **wheel diameter**, like wheels are
  actually sold, instead of the circumference (still converted internally
  via circumference = diameter × π for the distance math) - limits and
  default deliberately match the ESPHome "Wheel Diameter" field, so the
  same number works in both places. Fixes the mix-up risk noted further
  below structurally, not just through better wording
- Integration icon designed, cut out, and **live**
  (`custom_components/hamster_fitness/brand/`, source: GpsM2) - thanks to
  the new [Brands Proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
  (HA 2026.3+), the icon ships inside the integration itself, no external
  PR to `home-assistant/brands` needed. `manifest.json` now requires
  `"homeassistant": "2026.3.0"` as a minimum version for this
- All relevant data now flows through the integration itself, no separate
  ESPHome entity needed for a complete dashboard:
  - `binary_sensor.<hamster>_door` (cage door status, mirrors the
    configured door/lid sensor, includes "hours closed" as an attribute)
  - `sensor.<hamster>_humidity` (optional, if a humidity sensor was
    selected)
  - `sensor.<hamster>_night_distance` (distance since the night window
    started)
  - `sensor.<hamster>_current_speed` and `sensor.<hamster>_max_speed_tonight`
    (optional, if a real-time speed sensor was selected)
  - Example dashboard (`examples/dashboard_simple.yaml`) extended with a
    real-time speed gauge accordingly
- Bugfix: `[%key:...%]` references in `strings.json`/`translations/de.json`
  showed up as raw text instead of being resolved during Reconfigure -
  that mechanism only runs at Home Assistant Core build time (hassfest),
  never at runtime for custom integrations. Replaced every reference with
  the literal text
- Device/entity names now carry a `hamster_` prefix before the hamster's
  name (e.g. `sensor.hamster_taco_health_score`), so it's obvious at a
  glance that an entity belongs to this integration
- ESPHome firmware: entity names and device name switched from German to
  English, file/device name renamed from the cryptic
  `esphome-web-d018de` to the descriptive `hamster-wheel-sensor`
- Own Lovelace card shipped with the integration
  (`hamster-fitness-card`, see `custom_components/hamster_fitness/frontend/`) -
  auto-registers as a resource on UI-managed dashboards, following the
  same pattern as e.g.
  [home-assistant-flightradar24](https://github.com/AlexandrErohin/home-assistant-flightradar24).
  No HACS frontend package needed for a good-looking single card anymore
- Wheel-sensor/speed-sensor picker in the config flow narrowed down
  (`device_class: speed` for the speed sensor, added to the ESPHome
  firmware to match) - deliberately no hard filter on the rotation
  sensor, since that could hide an already-selected entity during
  Reconfigure if it uses a unit other than "rot."
- Card: visual editor (via `ha-form`, matching the built-in cards),
  configuration now uses an entity picker (health-score sensor) instead
  of a free-text hamster name, two rings side by side (health score +
  live speed in the same style), mobile optimization (its own breakpoint
  for narrow cards), clickable values that open the relevant entity's
  more-info dialog (e.g. temperature history), and an always-visible
  score breakdown (movement/temperature/care point deductions) so it's
  clear how the score adds up even without an active warning
- Cage light automation (`door_light.py`, optional `light_entity` field):
  turns on automatically when the door/lid sensor opens, and (if enabled)
  back off when it closes. Configurable in the options menu: brightness,
  optional fade time (transition), automatic turn-off on/off, optional
  turn-off delay
- Ranking card (`hamster-fitness-ranking-card`, same card bundle): auto-
  discovers every hamster in this Home Assistant via
  `sensor.hamster_<name>_lifetime_distance` and lists them sorted by
  lifetime distance - no configuration needed, departed hamsters stay in
  the ranking with their frozen final distance
- Removed `examples/dashboard_simple.yaml` and `examples/dashboard_taco.yaml` -
  the built-in cards (`hamster-fitness-card`, `hamster-fitness-ranking-card`)
  replace them completely
- Bugfix: both cards required an entity_id starting with `hamster_`, so
  hamsters set up before that naming prefix existed (entity_ids don't
  change on their own when the code's naming convention changes) weren't
  recognized - the ranking card reported "no hamsters found" for them.
  Both cards now only require the entity_id to *end* in the right suffix
  (e.g. `_lifetime_distance`); a leading `hamster_` is optional and only
  affects the displayed name, not whether the entity is found
- README.md and ROADMAP.md rewritten in English, README simplified into a
  clear feature overview plus a step-by-step install guide
- Wheel diameter sync: optional `wheel_diameter_sync_entity` field (a
  `number` entity, typically the ESPHome device's own "Hamster Wheel
  Diameter"). Whenever the diameter is set here - now or later via
  Reconfigure - it's pushed to that entity automatically via
  `number.set_value`, so the two values don't have to be kept in sync by
  hand. Previously they were completely independent, with no way to link
  them
- Bugfix: both cards guessed sibling entity_ids (daily_distance,
  night_distance, current_speed, etc.) by swapping the `_health_score`/
  `_lifetime_distance` suffix of an entity_id string. This silently broke
  on any non-English Home Assistant install: entity_id is generated once,
  from the *translated* name active when the entity was first created
  (e.g. `sensor.hamster_taco_tagesdistanz` on a German instance), not from
  the English name in the code - so the guessed id never matched, leaving
  distances/speed blank ("-") and the ranking card unable to find hamsters
  at all. Both cards now look entities up through the entity/device
  registry instead (same device_id, matched by `translation_key`, a fixed
  English string set in Python that never changes), with the old suffix-
  swap kept only as a fallback. Card titles/ranking names now also prefer
  the device's own name over parsing it out of the entity_id, for the same
  reason
- `diagnostics.py` added: lets you download a config entry's diagnostics
  (Settings → Devices & Services → Hamster Fitness → device → Download
  diagnostics) for bug reports, without having to copy state by hand.
  Notification targets are redacted since they can be identifying; the
  rest (sensor references, entity registry entries) isn't sensitive - the
  first step of an ongoing pass to bring the integration closer to Home
  Assistant's Quality Scale standards for a possible future Core
  submission
- Config flow now also checks that `temperature_sensor`/`door_sensor`
  actually exist in Home Assistant before creating or updating the entry
  (new `entity_not_found` error), the same defensive spirit as the
  existing wheel-sensor numeric check - covers the rare case of an entity
  disappearing between rendering the form and submitting it
- Bugfix + feature: dynamic runtime text (warning reasons, daily-summary
  push notifications) was hardcoded German, unlike every other user-facing
  string in this integration. Moved it into a new `messages` section in
  `strings.json`/`translations/*.json` (new `runtime_text.py`), resolved
  through the same mechanism Home Assistant Core uses for translated
  exception messages - defaults to English, applies German automatically
  based on `hass.config.language`, and formats numbers with a decimal
  point or comma to match. While verifying this against the real
  `homeassistant` package, found and fixed a related latent bug: this
  integration never shipped a `translations/en.json`, so - contrary to
  the assumption earlier in this project - config flow/entity/options
  text was **not** actually falling back to `strings.json` for English
  users at runtime (only hassfest-built Core integrations get that
  fallback for free); it would have shown blank/raw text for anyone
  running Home Assistant in English. `translations/en.json` now mirrors
  `strings.json` and needs to be kept in sync by hand going forward (see
  CLAUDE.md)
- Third dashboard card, `hamster-day-night-card` ("Hamster
  Fitness: Day & Night"): the hamster runs animated in its wheel (speed-
  coupled spin) at night/while active, or sleeps in a nest during the
  day/while resting - driven by two new sensors,
  `sensor.<hamster>_night_active_duration` and
  `sensor.<hamster>_day_rest_duration` (mutually exclusive continuous
  running/resting time, tolerates pauses under 30 minutes without ending
  a session, survives Home Assistant restarts). Background is a sun-
  position-driven gradient (`sun.sun`, independent of the activity state,
  so a hamster napping at 2am correctly shows as sleeping rather than
  spinning just because it's dark). All three cards were renamed to a
  shared "Hamster Fitness: X" naming scheme in the card picker for
  consistency (cosmetic only, `custom:type` ids unchanged). Shared entity/
  device lookup helpers extracted into `hamster-fitness-shared.js` so the
  logic isn't duplicated across card files.
- Split the project into two repos. This one
  (`ha-hamster-fitness-integration`, renamed from `ha-hamster-fitness`) now
  contains only the Home Assistant integration, Lovelace cards, and
  software tests, relicensed to the permissive
  [Apache License 2.0](LICENSE) (was PolyForm Noncommercial). `esphome/`
  moved out to the new
  [hamster-fitness-hardware](https://github.com/GpsM2/hamster-fitness-hardware)
  repo (private, CC BY-NC 4.0), which will also hold future CAD/3D-print
  and PCB files. Both repos got a `transfer-issue.yml` workflow that
  auto-moves mislabeled issues to the other repo (needs a `CROSS_REPO_PAT`
  secret in each repo - the default `GITHUB_TOKEN` can't write across
  repos, so this doesn't work automatically yet).

- **0.3.0 — the roadmap batch of 2026-08-06.** One release covering all of
  the items previously listed under "Planned":
  - *Bugfix:* the health score dropped every morning at 9 AM even after a
    great night, because the distance penalty read `daily_distance_km`,
    which resets at `DAILY_RESET_HOUR`. It now uses the nightly distance -
    and specifically the higher of the running night and the last
    completed one (new persisted `last_completed_night_km`), so the same
    cliff doesn't simply reappear at `NIGHT_WINDOW_START_HOUR`. The
    daytime value is no longer shown on the health-score card; the sensor
    itself stays for history and automations.
  - *Bugfix:* the Day & Night wheel stuttered. Two separate causes:
    `_render()` rebuilt the whole card on every `hass` update (restarting
    the CSS animation), and rewriting `animation-duration` on a running
    CSS animation resets it to 0deg - which the constantly-updating speed
    sensor triggered over and over. The DOM is now patched in place and
    the rotation runs through the Web Animations API, where a speed change
    only adjusts `playbackRate`. The wheel also parks when the speed hits
    0 mid-session and resumes from the same position.
  - **Four pillars of health** as their own sensors
    (`sensor.<hamster>_activity_score` / `_sleep_score` / `_climate_score` /
    `_care_score`), each scaled against its own maximum penalty so 0-100
    means the same thing on every pillar. Sleep is a brand-new metric:
    cage openings and wake-up runs during the 10:00-17:00 main sleep
    phase, weighted into the overall score at 15%.
  - **Cage-light automation made visible and controllable**: a
    `switch.<hamster>_light_automation` entity plus a
    `hamster_fitness.pause_light_automation` action (30 minutes by
    default, re-arms itself). Registered as an *entity* service so
    targeting stays correct with several hamsters. Both the switch state
    and a running pause survive a restart.
  - **Weigh-in reminder**, opt-in, that only fires when weighing is
    actually overdue - and then waits a full interval instead of nagging
    daily. Goes by a timestamp the coordinator keeps, not the number
    entity's `last_changed`, which RestoreEntity resets on every restart.
  - **Hamster profile**: breed (translated list plus free text for
    "Other") and one of four coat colours, stored as symbolic keys so the
    list stays translatable and colours can be re-tuned later. Surfaced as
    attributes on the health-score sensor, which is what lets the cards
    tint the illustration per hamster.
  - **Lifetime archive** (`hamster_fitness_history_lifedata` in
    `.storage`): written when a departure date takes effect, and
    deliberately NOT keyed by entry_id - it has to outlive the config
    entry being deleted. Exposed to the frontend through a new
    `hamster_fitness/history` WebSocket command, since archived hamsters
    have no entities left to read.
  - **Card redesign** following the provided mockup
    (`design/mockup-day-night-card.png`): one illustrated scene with the
    readings as pill chips inside it, sun/moon corner, bigger typography,
    inline status chip. The header is now shared verbatim between the
    Day & Night and health-score cards (extracted into
    `hamster-fitness-shared.js`) so the two cannot drift apart.
  - **Health-score card rebuilt**: banner header with a dynamic "seit X
    Monaten bei dir" subtitle and a status badge (Voll vital / Beobachten
    / Tierarzt prüfen), score ring, a plain-language Smart Insight, the
    four pillars as a tappable 2x2 grid opening detail dialogs with the
    real numbers and a husbandry tip each, and a 7-day trend chart fed by
    a rolling score history the coordinator now keeps. Renders from demo
    data in the dashboard editor instead of erroring.
  - **Fourth card, "Hamster Fitness: Chronik"**: every hamster that ever
    lived here, live ones from the entity registry and deleted ones from
    the archive, each in its own coat colour with breed, dates and
    configurable stat columns.
  - **Multi-hamster operation tested**, not just assumed: entity ids,
    per-entry storage keys, per-hamster profiles, light pauses and
    departure freezing all covered by `tests/test_multi_hamster.py`.
  - **The test suite runs on Windows for the first time.** Two blockers,
    both worked around narrowly and only on `win32`: asyncio's self-pipe
    needs a socket (re-enabled for loopback only), and the HTTP server's
    accept task lingers past teardown. Config entries are now unloaded
    after every test - which immediately surfaced three real problems: a
    timer missing `cancel_on_shutdown`, a test asserting an entity id that
    never existed (`binary_sensor.<name>_door` is `_cage_door`), and a
    test asserting an error branch the NumberSelector makes unreachable.
  - **README split** into a short overview plus one page per card under
    `docs/cards/`.

## 🚧 Planned

- Enable branch protection on `main` (block force-push/deletion, ideally
  require PR review) once the repo goes public - GitHub only offers this
  for private repos on paid plans, so it's on hold until then.
- Card localisation. Python-side text (config flow, entity names, warning
  and notification messages) follows Home Assistant's language, but the
  four Lovelace cards still carry hardcoded German labels. Worth moving
  them through the same `strings.json` mechanism, or at least an
  English/German switch, before the repo goes public.
- The 7-day trend records the score standing at `DAILY_RESET_HOUR`, i.e.
  one snapshot per day rather than a daily average. Fine as a trend, but
  a day that dipped and recovered looks unremarkable - worth revisiting
  if the chart turns out to be misleading in practice.

## 🔍 To investigate

### Distance calculation seemed high compared to the ESP's own numbers

The most likely cause (circumference field instead of a diameter field,
see above) is structurally fixed now that both sides ask for the same
diameter value. After updating, check/re-enter the value once via
Reconfigure (it's now read as a diameter) - if the discrepancy is still
there afterwards, something else was the cause and would need a fresh
look based on actual sensor readings.
