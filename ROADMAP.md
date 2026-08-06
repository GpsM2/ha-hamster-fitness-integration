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

## 🚧 Planned

_Nothing open right now - new ideas get added here._

## 🔍 To investigate

### Distance calculation seemed high compared to the ESP's own numbers

The most likely cause (circumference field instead of a diameter field,
see above) is structurally fixed now that both sides ask for the same
diameter value. After updating, check/re-enter the value once via
Reconfigure (it's now read as a diameter) - if the discrepancy is still
there afterwards, something else was the cause and would need a fresh
look based on actual sensor readings.
