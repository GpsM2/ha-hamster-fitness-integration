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

## 🚧 Planned

_When work on this batch (everything below, added 2026-08-06) actually
starts: bump `manifest.json`'s version to `0.3.0` (explicit user
instruction, overrides the usual patch-only bump rule for this batch),
and put together one coherent plan covering all of it before implementing
- not a grab-bag of unrelated changes._

- Enable branch protection on `main` (block force-push/deletion, ideally
  require PR review) once the repo goes public - GitHub only offers this
  for private repos on paid plans, so it's on hold until then.

### Bugfix: health score drops at the 9 AM reset despite an active night

Reported: right at `DAILY_RESET_HOUR` (9 AM), `daily_distance_km` resets to
~0, which immediately triggers the `too_little_exercise` penalty even if
the hamster ran a lot overnight - the score visibly drops even though
nothing bad actually happened. The health score's distance penalty should
be based on the current/most recently completed *night* (`night_distance_km`,
already tracked separately) instead of - or blended with -
`daily_distance_km`, since that's what actually reflects a hamster's
nocturnal activity. The daytime value is not interesting on its own and
should no longer be shown on the main card. Needs a closer look at how
`_distance_penalty()` in `coordinator.py` picks its input once this is
tackled, and how "the current/most recently completed night" is defined
right after a fresh `NIGHT_WINDOW_START_HOUR` reset.

### Bugfix: Day & Night wheel animation stutters/flickers, doesn't track speed live

The wheel's `@keyframes spinWheel` animation restarts from 0deg on every
`_render()` (every `hass` update rebuilds the card's innerHTML from
scratch), which reads as stutter/flicker instead of one smooth spin. Needs
rework so the rotation continues seamlessly across re-renders (e.g. track
elapsed rotation and set the starting `transform` accordingly, or move the
spin to a persisted DOM node that isn't torn down each render). Separately,
the wheel should react live to the actual current speed - including
coming to a visible stop mid-session if speed drops to 0, even while
`night_active_duration` is still counting (a session can have the hamster
motionless for a bit without timing out, per the 30-minute grace period).

### Card redesign: playful style, data embedded in the scene

Redesign both cards to be more playful/illustrated, moving the data rows
into the scene itself instead of a separate section at the card's foot -
a mockup was provided as the layout/style reference, saved at
`design/mockup-day-night-card.png`. Key cues from the mockup to match:
data readouts overlaid directly on the illustrated scene (not a separate
stats grid), rounded pill-style info chips, larger/friendlier typography,
a small connection-status chip inline in the scene rather than a footer
row.

### Day & Night card: light automation control

Add a button on the card to pause the cage-light automation for 30 minutes
(auto re-enables afterward), plus show the light's current on/off status
when a light entity is connected. Needs a new coordinator-side "pause
until" mechanism for `door_light.py`'s automation (temporarily skip
turn-on/off while paused) and a way for the card to trigger it (a new
service the card calls, most likely) and read the light's live state.

### Weight-reminder push notification

Let the user opt in to a periodic push reminder to weigh the hamster (on
the kitchen scale, entered into `number.<hamster>_weight`), toggleable
independently in the options menu - same pattern as the existing
warnings/daily-summary toggles in `notify.py`.

### Dynamic hamster profile & color customization

- At setup (config flow) and via Reconfigure, let the user pick a hamster
  breed/type (e.g. Golden Hamster, Winter White Dwarf, Roborovski, ...)
  in addition to the existing name/acquisition date/wheel diameter.
- Let the user pick a main coat color from 4 predefined swatches:
  Golden-brown `#D48C46`, Silver-grey `#8A929A`, Cream/sand `#E8D3A7`,
  Black/dark `#333333`.
- The hamster illustration/logo becomes a dynamic SVG whose `fill`
  color(s) (or a CSS custom property) are driven by the selected hex
  value, instead of the fixed color palette the current logos use.

### Lifetime history archive on departure (`history_lifedata.json`)

When a departure date is set (hamster passed away or moved out), archive
that hamster's profile into a durable history file (e.g.
`config/hamster_fitness/history_lifedata.json` via `Store`, matching the
existing per-entry storage pattern) before/alongside freezing its live
snapshot. Should persist: name, breed/type, color hex, acquisition date,
departure date, and aggregated lifetime stats (total distance, top speed,
active days, etc.). This becomes the data source for the new overview card
below.

### 4th Lovelace card: "Hamster Chronicle & Overview"

A new card listing every hamster that ever existed in this Home Assistant
- both currently active ones and archived ones from the history file above
 - each with its move-in/move-out dates and an icon/logo in its own coat
color. Which stat columns are shown should be configurable (checkboxes),
similar to the Day & Night card's `show_*` toggles.

### Multi-hamster parallel operation - test & harden

Explicitly test and confirm that running several hamster config entries
side by side stays fully isolated: entity IDs, `Store` storage keys
(already per-`entry_id`, e.g. `hamster_fitness_<entry_id>_baseline` -
worth double-checking this holds for every new storage key added by the
items above too), and dashboard cards (translation_key-based sibling
lookup already handles this, per the entity-registry rework earlier this
project) all need to keep working without cross-talk between hamsters.

### `hamster-fitness-card` (health score) redesign

Overhaul to match the Day & Night card's visual language and add richer,
more actionable detail:

- **Header**: same outer layout/spacing/typography as the Day & Night
  card's header (keep the current header SVG icon). Subtitle changes to a
  dynamic "seit X Monaten bei dir" derived from `acquisition_date`. Add a
  status badge (top right): 🟢 "Voll vital" / 🟡 "Beobachten" / 🔴
  "Tierarzt prüfen", thresholded off the health score.
- **Hero**: keep the central health-score ring (0-100, color-coded), add a
  highlighted "Smart Insight" box below it for the dynamic problem-
  description text (already available via `warning_reason`/the
  `messages` translation category).
- **Interactive 2x2 grid** ("4 pillars of health"), each tile opens a
  modal (`ha-dialog` or a custom shadow-DOM overlay) with detail + a care
  tip:
  - 🏃 Activity & endurance: "Hamsters instinctively hide illness as long
    as possible. A sudden >30% drop in nightly running distance is often
    the very first sign of one - watch the trend, not just one night."
  - 😴 Sleep & rest quality: "Hamsters are crepuscular/nocturnal.
    Disturbing their main sleep phase (10:00-17:00) with light, vibration,
    or cage openings causes chronic stress and weakens the immune system."
  - 🌡️ Climate & environment: "Ideal range is 18-22°C, 40-60% humidity.
    Below 15°C risks life-threatening torpor; above 24°C risks heat
    stroke."
  - 🧹 Care & interaction: measured via the door/lid sensor - tracks how
    regularly the cage is opened for feeding/cleaning. Best is 1-2 short
    openings in the late evening; avoid frequent daytime opening (ties
    into the "too much daytime opening" scoring item above).
  - These four map naturally onto new per-pillar score sensors
    (`sensor.hamster_<name>_score_activity/_sleep/_climate/_care` in the
    request) worth evaluating against the existing single combined
    `distance_penalty`/`temperature_penalty`/`care_penalty` breakdown -
    may become new sensors, or the modal content might just read the
    existing breakdown attributes instead of needing new entities.
- **Trend section**: comparison readouts (e.g. "5.4 km (+0.6 km vs. 7-day
  avg)", "Climate 100% in range") plus a 7-day bar chart of daily scores
  at the bottom of the card. Needs the coordinator to start keeping a
  short rolling history of daily scores somewhere (not currently tracked
  beyond `previous_day_distance_km`).
- Technical notes carried over from the request: plain
  LitElement/HTMLElement web component (no new build tooling), full
  mock-data fallback for the dashboard editor preview, header CSS classes
  kept identical to `hamster-day-night-card.js`'s.
- Consider splitting `README.md` into a short top-level overview plus one
  doc per card, now that there'll be four cards with real depth each.

## 🔍 To investigate

### Distance calculation seemed high compared to the ESP's own numbers

The most likely cause (circumference field instead of a diameter field,
see above) is structurally fixed now that both sides ask for the same
diameter value. After updating, check/re-enter the value once via
Reconfigure (it's now read as a diameter) - if the discrepancy is still
there afterwards, something else was the cause and would need a fresh
look based on actual sensor readings.
