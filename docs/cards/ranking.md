# Hamster Fitness: Ranking

A leaderboard of every hamster you have set up, sorted by lifetime
distance.

`type: custom:hamster-fitness-ranking-card`

## What it shows

One row per hamster with medals for the top three, each drawn in that
hamster's own coat colour, and two figures:

| Column | What it means |
|---|---|
| **Total** | Lifetime distance ever run |
| **Per day** | That distance divided by the days the hamster has been with you |

The per-day figure is what makes the ranking fair. Sorted by total alone,
the leaderboard just rewards whoever lived longest — a hamster who moved
in years ago will out-run a newcomer no matter how lazy it is. Per day
puts them on equal footing.

Days are counted from the acquisition date to the departure date, or to
today for a hamster that's still here. A hamster with no acquisition date
recorded shows `–` rather than a made-up number.

Departed hamsters keep their frozen final distance and stay in the
ranking, marked with 🪦 and slightly dimmed.

Nothing to configure: the card finds hamsters through the entity registry
(every `lifetime_distance` sensor belonging to this integration), so it
picks up new hamsters by itself and works on a Home Assistant running in
any language.

## Options

| Option | Default | What it does |
|---|---|---|
| `title` | `Hamster ranking` | Shown in the banner header |

```yaml
type: custom:hamster-fitness-ranking-card
title: Wer läuft am meisten?
```

## Notes

- The card's text follows `hass.language` (English and German), as does
  number formatting.
- On narrow cards the two figures wrap onto their own line below the name.
- Coat colour and acquisition date are read from the hamster's
  health-score sensor attributes, where the profile lives (see
  `hamster_profile()` in `coordinator.py`).

## Related

For a fuller picture — including hamsters whose integration entry has
since been deleted, with breeds and move-in/move-out dates — see the
[Chronicle card](chronicle.md).
