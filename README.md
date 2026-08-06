# Hamster Fitness

[![Version](https://img.shields.io/badge/version-0.2.6-blue.svg)](custom_components/hamster_fitness/manifest.json)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-lightgrey.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/R8O124JOD1)

Hamster Fitness is a free add-on for Home Assistant. It watches your
hamster's running wheel, cage temperature, and cage door, and turns that
data into one simple health score. It can also send you alerts, show
nice cards on your dashboard, and turn on a light when you open the cage.

This repository has two parts:

- **The Home Assistant integration** (`custom_components/hamster_fitness/`)
  — the main add-on.
- **The sensor firmware** (`esphome/`) — code for a small, cheap sensor
  that counts wheel turns. You only need this if you don't already have a
  way to track wheel rotations.

## License

This project uses the [PolyForm Noncommercial License 1.0.0](LICENSE).
In short: anyone can use, change, and share the code for free, but only
for **non-commercial** purposes (personal use, hobby projects, schools,
research). The author (GpsM2) keeps full rights and may also use or
license the project commercially.

## Features

- **Health score** (0–100%) based on how much your hamster ran, the cage
  temperature, and how long since you last opened the cage.
- **Distance tracking**: today, last night, and lifetime total.
- **Speed tracking**: current speed and the fastest speed last night
  (needs a speed sensor).
- **Temperature and humidity** readings near the cage.
- **Cage door status**, including how many hours it's been closed.
- **Weight tracking**: type in your hamster's weight by hand (for
  example, after weighing it on a kitchen scale).
- **Warnings**: get notified if the temperature is off, the cage hasn't
  been opened in a while, your hamster isn't running much, or the score
  drops too low.
- **Daily summary**: a short message each day about how far your hamster
  ran the night before.
- **Cage light automation**: turn a light on when the cage opens, and
  off again when it closes (brightness, fade time, and delay are all
  adjustable).
- **Hamster history**: when a hamster moves out (or passes away), mark a
  departure date. Its data is saved and frozen, so you can still see how
  far it ran in its lifetime — even after you set up a new hamster.
- **Two dashboard cards built in** — no extra downloads needed:
  - A card that shows one hamster's health score, speed, distances, and
    status.
  - A ranking card that automatically lists and compares every hamster
    you've set up, sorted by lifetime distance.
- **Keeps the wheel diameter in sync**: if your sensor device (like the
  ESPHome one in this repo) has its own wheel diameter setting, this
  integration can update it automatically whenever you change the
  diameter here — no need to enter the same number twice.

## What you need

- A recent version of Home Assistant (2026.3 or newer).
- A sensor that counts your hamster wheel's rotations. The easiest way is
  to build the small ESP8266 sensor in this repo (see below) — it costs
  only a few euros in parts. If you already have a rotation counter from
  somewhere else, you can use that instead.
- Optional, but nice to have: a temperature sensor, a humidity sensor, a
  door/lid sensor for the cage, a light, and a speed sensor. Everything
  optional will simply be skipped if you don't have it.

## Installation

### Step 1: Build the wheel sensor

Skip this step if you already have a working rotation sensor.

1. Get a cheap ESP8266 board (like a "D1 Mini") and an optical sensor
   (a small light sensor that notices when something passes by it).
2. Open `esphome/hamster-wheel-sensor.yaml` in ESPHome and flash it to
   your board.
3. In your ESPHome `secrets.yaml` file, add these four entries:
   `wifi_ssid`, `wifi_password`, `esphome_web_d027a9__encryption_key`,
   `esphome_web_d018de__ota_password`.
4. Attach the sensor to the wheel so it "sees" one mark or magnet once
   per full turn.
5. Once it's flashed, Home Assistant should find it automatically
   through the ESPHome integration.

### Step 2: Install the Home Assistant integration

**Option A — with HACS** (once this repo is public and added to HACS):

1. Open HACS, go to Integrations, click the three-dot menu, and choose
   "Custom repositories."
2. Add this repo's URL, category "Integration."
3. Find "Hamster Fitness" in HACS and install it.
4. Restart Home Assistant.

**Option B — manually:**

1. Copy the `custom_components/hamster_fitness/` folder into your Home
   Assistant `custom_components` folder.
2. Restart Home Assistant.

### Step 3: Set up your hamster

1. Go to **Settings → Devices & Services → Add Integration**, and search
   for "Hamster Fitness."
2. Enter your hamster's name, the date it moved in, and its wheel
   diameter (check the packaging of the wheel — use the same number here
   as in the ESPHome sensor, if you built one).
3. Choose the sensors that feed the integration:
   - **Wheel rotation sensor** (required) — pick
     `sensor.hamster_wheel_total_rotations` if you used the sensor from
     this repo.
   - **Wheel diameter sync target** (optional) — pick the ESPHome
     device's "Hamster Wheel Diameter" entity here, and the wheel
     diameter you entered in step 2 gets sent to it automatically. No
     need to type the same number into two places and keep them in sync
     by hand.
   - **Temperature sensor** (required).
   - **Cage/lid sensor** (required).
   - Humidity sensor, speed sensor, cage light, and notification targets
     (all optional).
4. Done! You can change any of these choices later without starting
   over — just click the gear icon on the device and choose
   "Reconfigure."

There's also an **options menu** (the "Configure" button) for
fine-tuning: ideal temperature range, minimum daily distance, whether to
send warnings and daily summaries (and when), and the cage light's
brightness, fade time, and turn-off delay.

### Step 4: Add the dashboard card

1. Open a dashboard, click **Edit**, then **Add card**.
2. Search for "Hamster Fitness Card."
3. Pick your hamster's health score sensor and save. That's it — no YAML
   needed.

Want to compare several hamsters? Add the **"Hamster Fitness Ranking
Card"** the same way. It finds every hamster on its own.

### If something looks wrong after an update

Home Assistant keeps translations and dashboard files cached. After
copying in a new version, a simple "reload" is often not enough.
**Restart Home Assistant completely** (Settings → System → Restart), and
refresh your browser with <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>. If
a setup screen shows a raw name like `wheel_diameter` instead of a normal
label, this is almost always the fix.

## Entities

Every entity name starts with `hamster_` and your hamster's name, so you
can always tell where it came from — for example,
`sensor.hamster_taco_health_score` for a hamster named "Taco."

| Entity | What it shows |
|---|---|
| `sensor.hamster_<name>_health_score` | Health score (0–100%) |
| `sensor.hamster_<name>_daily_distance` | Distance run today |
| `sensor.hamster_<name>_night_distance` | Distance run tonight |
| `sensor.hamster_<name>_lifetime_distance` | Total distance ever run |
| `sensor.hamster_<name>_current_speed`¹ | Current wheel speed |
| `sensor.hamster_<name>_max_speed_tonight`¹ | Fastest speed tonight |
| `sensor.hamster_<name>_humidity`² | Cage humidity |
| `binary_sensor.hamster_<name>_warning` | On when something needs attention |
| `binary_sensor.hamster_<name>_door` | Cage door open or closed |
| `date.hamster_<name>_departure_date` | Set this when the hamster moves out |
| `number.hamster_<name>_weight` | Type in the hamster's weight (grams) |

¹ Only shows up if you picked a speed sensor.
² Only shows up if you picked a humidity sensor.

## Support this project

Hamster Fitness is free and always will be. If it's useful to you and you
want to say thanks, you can [buy me a coffee on Ko-fi](https://ko-fi.com/R8O124JOD1).
Not required — just appreciated.
