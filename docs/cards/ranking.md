# Hamster Fitness: Ranking

A leaderboard of every hamster you have set up, sorted by lifetime
distance.

`type: custom:hamster-fitness-ranking-card`

## What it shows

One row per hamster, medals for the top three, and the total distance
each has ever run. Departed hamsters keep their frozen final distance and
stay in the ranking, marked with 🪦.

Nothing to configure: the card finds hamsters through the entity registry
(every `lifetime_distance` sensor belonging to this integration), so it
picks up new hamsters by itself and works on a Home Assistant running in
any language.

## Options

| Option | Default | What it does |
|---|---|---|
| `title` | `Hamster-Ranking` | Heading above the list |

```yaml
type: custom:hamster-fitness-ranking-card
title: Wer läuft am meisten?
```

## Related

For a fuller picture — including hamsters whose integration entry has
since been deleted, with breeds, coat colours and dates — see the
[Chronicle card](chronicle.md).
