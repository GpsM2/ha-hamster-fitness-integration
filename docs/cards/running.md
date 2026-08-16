# Hamster Fitness: Running

One bar per night for the last week, so a run can be read against the
nights around it rather than on its own.

`type: custom:hamster-running-card`

## What it shows

The Day & Night card answers "what is happening right now"; this one
answers "is that normal". Seven bars, one per completed night, with:

- **A goal line** at the minimum nightly distance from the integration's
  own settings. It is deliberately the *same* number the health score
  grades against, so the chart and the score can never disagree about
  what counts as enough.
- **An average line** across the seven nights on show.
- **Average speed** as a line over the bars, on by default. Distance says
  how much the hamster ran; speed says how hard. A short but fast night
  looks quite different from a short, listless one.
- **Runs per night** as a small number inside each bar: how many
  separate sessions that night's distance was made of. The total time
  alone hides the pattern — ninety minutes in one go and six bursts of
  fifteen add up the same, but they are not the same night. Nights
  recorded before this existed simply show no number.
- **Personal bests**: the longest single night and the fastest speed ever
  measured, each with the date it happened. Neither is capped to the
  seven-night window — a record set months ago still stands.

### Climate overlays

Two more lines can be switched on with the buttons under the chart:
**Temperature** and **Humidity**, both averaged across each night rather
than sampled at one moment. They are there to answer questions the
numbers alone can't: whether a quiet week lines up with a warm spell, for
instance.

The average covers the hours the hamster was awake, not the whole
twenty-four. The bars themselves span a window that runs from evening to
evening, which is right for distance — a hamster runs at night, so the
daytime adds nothing to the total. Climate is the other way round: the
hours it sleeps through are the warmest of the day, and letting them in
would produce a number describing neither the night nor the day.

Each line is scaled against its own range rather than the kilometre axis
— humidity forced onto a distance scale would be a flat line along the
bottom. The shape is the point; the exact values live in the readings
themselves.

A night with only one reading of a given kind gets a dot rather than a
line, since a line needs two points. That is worth knowing in the first
few days: the toggles do work, there is simply not yet enough recorded
to join anything up.

The toggles are card-local and not part of the dashboard config: they are
a way of looking at the data, not a property of the hamster.

## Which night is which

A night runs from the evening into the next morning, and is filed under
the date it **started**. Friday night's run appears under Friday, even
though most of it happened on Saturday.

## Tonight's bar

The last bar is the night currently running, drawn dashed and hollow and
labelled **Tonight**. It updates live as the hamster runs, rather than
waiting for the window to close in the evening.

It is deliberately not solid: three hours into a night is not the same
thing as a short night, and a filled bar beside seven finished ones
would invite exactly that reading.

Only closed nights become part of the history, count towards personal
bests, or survive a restart. Until seven of them exist the card says how
many it has, so "still collecting" is distinguishable from "broken".

## Options

| Option | Default | What it does |
|---|---|---|
| `entity` | — | Required. The hamster's health score sensor, same as the other per-hamster cards |
| `title` | the device name | Heading in the banner |

```yaml
type: custom:hamster-running-card
entity: sensor.hamster_taco_health_score
```

## Notes

- Everything comes from attributes on the health-score sensor, so there
  is no second entity to pick and nothing to configure beyond the card
  itself.
- The history is kept by the integration, not read from Home Assistant's
  recorder — so purging or excluding recorder data does not empty this
  chart, and it survives a restart.
- A night with no humidity sensor configured simply has no humidity
  point; the other lines are unaffected.
