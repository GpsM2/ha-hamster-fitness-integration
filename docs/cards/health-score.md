# Hamster Fitness: Health Score

The main card for one hamster: how it is doing, why, and what to look at
if the number is low.

`type: custom:hamster-fitness-card`

## What it shows

**Header** — the hamster's name, how long it has been with you (from the
acquisition date), and a status badge:

| Badge | Score |
|---|---|
| 🟢 Voll vital | 75–100 |
| 🟡 Beobachten | 50–74 |
| 🔴 Tierarzt prüfen | below 50 |

The banner takes its colour from the badge, so a glance across the
dashboard is enough.

**Rings** — the health score, and (optionally) the live wheel speed.

**Smart Insight** — one sentence in plain language. When a warning is
active this is the warning itself ("Im Käfig ist es ziemlich kalt: 12,5
°C."); otherwise it either confirms things are fine or, for a middling
score with no acute warning, points you at the pillars below.

**The four pillars** — a 2×2 grid, each tile tappable:

| Pillar | Measured from |
|---|---|
| 🏃 Aktivität | distance run in the relevant night |
| 😴 Schlaf | cage openings and wake-up runs between 10:00 and 17:00 |
| 🌡️ Klima | cage temperature against your ideal range |
| 🧹 Pflege | how long the lid has stayed shut |

Tapping a tile opens a detail dialog with the concrete numbers behind
that score and a short husbandry note explaining why it matters. Escape
or the × closes it.

**7-day trend** — a bar chart of the daily scores the integration
records each morning at 9 AM (right after the hamster's active phase
ends), with today compared against that average. Before the first full
day has passed it says so rather than drawing an empty chart.

## Options

All of them are in the card editor, no YAML needed.

| Option | Default | What it does |
|---|---|---|
| `entity` | — | **Required.** The hamster's `_health_score` sensor |
| `title` | device name | Overrides the displayed name |
| `max_speed` | `5` | Scale of the speed ring, in km/h |
| `show_speed` | `true` | Second ring next to the score |
| `show_pillars` | `true` | The 2×2 grid |
| `show_trend` | `true` | The 7-day bar chart |

```yaml
type: custom:hamster-fitness-card
entity: sensor.hamster_taco_health_score
max_speed: 8
show_trend: false
```

## Notes

- While the dashboard editor has no entity picked yet, the card draws
  itself from demo data so you can see the layout.
- Sibling entities are found through the entity registry, not by guessing
  entity IDs, so the card works on a Home Assistant running in any
  language.
