# Hamster Fitness: Track Weight

An input for your hamster's weight that's worth looking at — the hamster
sits in the pan of an old household kitchen scale, and the numbered drum
below turns to bring the reading up to the marker.

`type: custom:hamster-weight-card`

## Why it exists

Weight is the one thing this integration can't measure by itself: you put
the hamster on a kitchen scale and type the number in. Until now that
meant a bare number box behind a more-info dialog, with nothing to make
the figure mean anything.

"97 g" tells you very little on its own — it's a healthy Syrian, a
dangerously fat Roborovski, or nothing at all, depending on the animal.
Seeing where the marker lands between the healthy and the worrying bands
tells you a lot at a glance.

## What it shows

- The **dial**, its drum turning so the current weight sits under the
  fixed red marker, with coloured bands for the underweight, healthy and
  overweight ranges. The numbers are printed on the drum and turn with
  it, the way they do on the real thing.
- The **current weight** in the middle of the dial, coloured by verdict,
  and a plain-language verdict below it — *Underweight*, *Healthy
  weight*, *Overweight*.
- **−5 / −1 / +1 / +5 gram buttons** (the step is configurable), writing
  straight to `number.<hamster>_weight`, plus a **✎ button** to type a
  number instead when the steps would take too long.
- With **nothing recorded yet**, the buttons are replaced by an input
  field outright — climbing from zero to a Syrian hamster's ~100 g one
  tap at a time is no way to enter a first value. Enter saves, Escape
  backs out.
- **When it was last weighed** — "Weighed 2 days ago" — so an overdue
  weigh-in is obvious without opening anything.

Nothing recorded yet? The pan is empty and the dial reads `–`, rather
than pretending to a value.

## The scale comes from the breed

A Roborovski and a Syrian differ by a factor of five, so one fixed scale
would be useless for one of them. The dial's range and its coloured bands
are taken from the breed you chose when setting the hamster up:

| Breed | Underweight below | Healthy | Overweight above | Dial reads to |
|---|---|---|---|---|
| Syrian / Golden, Teddy | 85 g | 100–160 g | 170 g | 250 g |
| Winter White, Campbell | 30 g | 35–50 g | 55 g | 80 g |
| Chinese | 25 g | 30–45 g | 50 g | 70 g |
| Roborovski | 15 g | 18–28 g | 32 g | 50 g |

Picked **Other**? There's no reference range to judge against, so the
dial shows a plain 0–250 g scale with no bands, the verdict reads *No
reference range for this breed* — and the weight is left out of the
health score entirely. Guessing would be worse than saying nothing.

Change the breed in the integration options and the dial follows.

## Weight and the health score

Once a weight is recorded, how far it sits outside the healthy range
costs health-score points — up to 20 of them, ramping up as the deviation
grows rather than falling off a cliff at the threshold. Being off-weight
also raises the warning binary sensor, with an `underweight` or
`overweight` reason.

**Never weighed means no deduction.** The value is hand-entered, and
docking points for not having got round to it would punish you rather
than tell you anything about the hamster. The same goes for an unknown
breed.

The most you can enter is **250 g** — comfortably above the heaviest
Syrian on record, and low enough that a slipped decimal point is rejected
rather than quietly wrecking the score.

## Options

| Option | Default | What it does |
|---|---|---|
| `entity` | — | **Required.** The hamster's `_health_score` sensor |
| `title` | device name | Overrides the displayed name |
| `step` | `1` | Grams per button tap (the ±5 buttons use five of these) |

```yaml
type: custom:hamster-weight-card
entity: sensor.hamster_taco_health_score
```

There is no `scale_min`/`scale_max` any more: the dial is driven by the
breed, so there's nothing left to tune by hand.

## The weigh-in reminder

If you enabled the reminder in the integration options, tapping that
notification opens the weight entity directly instead of dropping you on
your dashboard's front page.

One caveat: Home Assistant's modern `notify.send_message` action carries
only a title and a message, with no room for a tap target. The deep link
therefore goes out through the companion app's own legacy notify service,
which does accept one. If your notification target isn't the companion
app, the reminder still arrives — just without the link.

## Notes

- The card's text follows `hass.language` (English and German), as do
  number and date formatting.
- With `prefers-reduced-motion` set, the drum snaps rather than
  animating.
