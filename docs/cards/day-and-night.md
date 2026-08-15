# Hamster Fitness: Day & Night

The illustrated live view: one big scene showing what your hamster is
doing right now, with the readings sitting inside the picture.

`type: custom:hamster-day-night-card`

## What it shows

**The scene** switches on the hamster's *actual* activity, not the clock:

- **Running** — the hamster in its wheel, which turns at the real
  measured speed. Faster running spins it faster; if the speed drops to
  zero while the session is still counting, the wheel visibly parks and
  picks up again from the same position when the hamster starts moving.
  A running session survives pauses under 30 minutes, so a quick drink
  doesn't end it.
- **Resting** — the hamster curled up in its nest with drifting Zs, the
  wheel standing still in the background.

**The sky** is driven separately from the scene: a starry night with the
moon, or a daytime gradient. The two layers are deliberately independent
— a hamster dozing at 2 AM is drawn sleeping under a night sky, not
sprinting just because it is dark.

By default the sky follows `sun.sun`, shifting with the sun's elevation.
**The sun itself moves with it**, sitting high around solar noon and
sinking towards the horizon in the morning and evening — so in midwinter
at northern latitudes it honestly stays low all day, because it does.

If you picked an **ambient light sensor** during setup, the card uses its
actual reading instead — closer to reality for a cage behind curtains,
in a basement, or under a cover, where the sun's position outside says
nothing about the light where the hamster actually lives. The cage
light itself can't fool it: while the light is on, the card holds the
brightness reading from just before it switched on, rather than reading
the lit room as broad daylight. No illuminance sensor configured? The
card falls back to `sun.sun` exactly as before — nothing to set up.

Once the real sun has set, it outranks that sensor: a brightly lit room
at 10 PM dims the sky to dusk rather than full daylight, and the moon
stays in the sky instead of the sun. While the sun is up, the sensor
still decides on its own — that is the whole point of having one, so a
covered cage reads as night even at noon.

**The moon** shows its real phase if you picked a **moon phase sensor**
during setup — typically `sensor.moon` from Home Assistant's built-in
Moon integration, which works the phase out locally, with no internet
connection or extra hardware. All eight phases are drawn: a sliver for a
crescent, a clean half disc at the quarters, a full circle at full moon,
and just a faint earthshine disc at new moon. The lit side is drawn as
seen from the northern hemisphere. Without that sensor the card keeps
its fixed decorative crescent — nothing to set up, nothing breaks.

**The weather** drifts over the scene when a weather entity was picked
during setup: clouds, rain, snow, sleet, hail, fog, wind and lightning,
with the sky dimming to match. All fifteen Home Assistant weather states
are drawn individually rather than lumped together — `pouring` really
does look wetter than `rainy`, and `hail` isn't snow. Clear states draw
nothing, which is also what happens with no weather entity configured,
or for a state a future Home Assistant version might add.

**The hamster** is drawn in the coat colour from its profile, so two
hamsters on one dashboard are told apart at a glance.

**The chips** in the scene hold the live readings: how long it has been
running or resting, current speed, distance this night, temperature and
humidity, and the cage light. Every chip is tappable and opens that
reading's own history.

**The "this night" chip** adds the night's average speed alongside the
distance once at least a minute of running has piled up — distance over
the time actually spent running, not over wall-clock hours, so a hamster
that slept through most of the night reads as well-rested, not slow. It
covers every session since the night began, not just the one currently
running.

**The resting chip** carries a **lid open** badge whenever the cage is
open while the hamster rests — the moment most likely to interrupt a
nap, and exactly what the sleep pillar of the health score scores.

**The light chip** shows whether the cage light is on, off, or its
automation is paused. Tapping the chip itself **switches the light**
directly — the label still opens the automation's own history, and a
**30 Min. Pause** button sits alongside for cleaning the cage, so the
light doesn't flick on and off with every lift of the lid. The
automation re-arms itself afterwards. The chip only appears if you
picked a cage light during setup.

## Options

| Option | Default | What it does |
|---|---|---|
| `entity` | — | **Required.** The hamster's `_health_score` sensor |
| `title` | device name | Overrides the displayed name |
| `show_speed` | `true` | Current speed chip |
| `show_distance` | `true` | Distance-this-night chip |
| `show_active_duration` | `true` | "Läuft seit" chip (while active) |
| `show_rest_duration` | `true` | "Ruht seit" chip (while resting) |
| `show_climate` | `true` | Temperature/humidity chip |
| `show_light` | `true` | Cage light chip with the pause button |

```yaml
type: custom:hamster-day-night-card
entity: sensor.hamster_taco_health_score
show_climate: false
```

## Notes

- On narrow cards (a phone, or a sidebar column) the chips wrap below the
  scene instead of squeezing in beside it.
- The wheel's rotation is driven through the Web Animations API rather
  than a CSS animation, because rewriting a CSS animation's duration
  restarts it — with a constantly-updating speed sensor that made the
  wheel stutter. Speed changes now retime the running animation instead
  of restarting it.
- With `prefers-reduced-motion` set, the animations are skipped. The
  lightning flash is removed outright rather than paused — a full-card
  white strobe is exactly what that setting exists to avoid, and a frozen
  one would just sit there as a bright pane.
- The card's text follows `hass.language` (English and German).
