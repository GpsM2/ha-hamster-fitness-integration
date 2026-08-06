# Hamster Fitness: Chronik

Every hamster that ever lived in this Home Assistant, in one list — the
ones currently set up and the ones long gone.

`type: custom:hamster-chronicle-card`

## What it shows

One row per hamster: a small hamster mark in that animal's own coat
colour, its name, breed, and the period it was with you, plus the stat
columns you choose. Current hamsters come first, then departed ones,
newest move-in first.

Two tags mark the past:

- **ausgezogen** — a departure date is set, but the hamster is still
  configured in Home Assistant. Its row is still clickable and opens the
  usual more-info dialog.
- **Archiv** — the config entry is gone; this row comes purely from the
  lifetime archive.

### Where the archived ones come from

When you set a departure date, the integration writes that hamster's
final record — name, breed, coat colour, both dates, days together,
lifetime distance, top speed and final score — into a permanent archive
file. Unlike everything else this integration stores, that file is *not*
tied to the config entry, so deleting the entry (or the whole
integration) does not erase the hamster. The card reads it over the
`hamster_fitness/history` WebSocket command.

If a hamster appears both live and in the archive, the live entry wins,
since its numbers still update.

## Options

| Option | Default | What it does |
|---|---|---|
| `title` | `Hamster-Chronik` | Heading in the banner |
| `columns` | `distance`, `days` | Which stats each row shows |

Available columns: `distance` (lifetime distance), `top_speed`, `days`
(days with you), `score` (health score — the final one for archived
hamsters).

```yaml
type: custom:hamster-chronicle-card
title: Unsere Hamster
columns:
  - distance
  - top_speed
  - days
```

## Notes

- If the archive cannot be read (for example an older integration
  version), the card shows the currently configured hamsters and says so
  instead of failing.
- On narrow cards the stats wrap onto their own line below the name.
