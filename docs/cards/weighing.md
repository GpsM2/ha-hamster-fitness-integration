# Hamster Fitness: Weighing

An input for your hamster's weight that's worth looking at — the hamster
sits on an old-fashioned two-pan balance, counterweights stack up on the
other pan as the number rises, and the hamster itself gets visibly
rounder.

`type: custom:hamster-weight-card`

## Why it exists

Weight is the one thing this integration can't measure by itself: you put
the hamster on a kitchen scale and type the number in. Until now that
meant a bare number box behind a more-info dialog, with nothing to make
the figure mean anything.

"97 g" tells you very little on its own. Watching the beam tip tells you
a lot at a glance.

## What it shows

- The **balance**, tipping with the entered weight, counterweights
  stacking on the opposite pan, and the hamster's body swelling as the
  number climbs. It's drawn in the hamster's own coat colour.
- The **current weight**, tappable to open the entity's history.
- **−5 / −1 / +1 / +5 gram buttons** (the step is configurable), writing
  straight to `number.<hamster>_weight`.
- **When it was last weighed** — "Weighed 2 days ago" — so an overdue
  weigh-in is obvious without opening anything.

Nothing recorded yet? The scale rests level with both pans bare, rather
than pretending to a half-load.

Values are clamped to the number entity's own minimum and maximum, so the
buttons can never write something the entity would reject.

## Options

| Option | Default | What it does |
|---|---|---|
| `entity` | — | **Required.** The hamster's `_health_score` sensor |
| `title` | device name | Overrides the displayed name |
| `scale_min` | `20` | Grams at the low end of the drawn scale |
| `scale_max` | `200` | Grams at the high end |
| `step` | `1` | Grams per button tap (the ±5 buttons use five of these) |

`scale_min`/`scale_max` only drive the illustration, never validation.
The defaults span a dwarf hamster up to a large Syrian; narrow them
around your own hamster's usual range for a more expressive tilt — a
Roborovski at 20–30 g will barely move the default scale.

```yaml
type: custom:hamster-weight-card
entity: sensor.hamster_taco_health_score
scale_min: 20
scale_max: 45
```

## The weigh-in reminder

If you enabled the reminder in the integration options, tapping that
notification now opens the weight entity directly instead of dropping
you on your dashboard's front page.

One caveat: Home Assistant's modern `notify.send_message` action carries
only a title and a message, with no room for a tap target. The deep link
therefore goes out through the companion app's own legacy notify service,
which does accept one. If your notification target isn't the companion
app, the reminder still arrives — just without the link.

## Notes

- The card's text follows `hass.language` (English and German), as do
  number and date formatting.
- With `prefers-reduced-motion` set, the balance snaps rather than
  animating.
