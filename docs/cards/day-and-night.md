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
If you picked an **ambient light sensor** during setup, the card uses its
actual reading instead — closer to reality for a cage behind curtains,
in a basement, or under a cover, where the sun's position outside says
nothing about the light where the hamster actually lives. The cage
light itself can't fool it: while the light is on, the card holds the
brightness reading from just before it switched on, rather than reading
the lit room as broad daylight. No illuminance sensor configured? The
card falls back to `sun.sun` exactly as before — nothing to set up.

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
- With `prefers-reduced-motion` set, the animations are skipped.
- The card's text follows `hass.language` (English and German).
