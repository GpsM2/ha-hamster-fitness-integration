# Card preview harness

Renders the four Lovelace cards against a mocked `hass` object, so their
layout and states can be checked without a running Home Assistant.

It loads the **real** files from
`custom_components/hamster_fitness/frontend/` — nothing is duplicated
here, so what you see is what ships.

## Run it

From the repository root:

```bash
python -m http.server 8777
```

Then open <http://localhost:8777/tools/card-preview/index.html>.

Serving from the repo root matters: the page reaches the card files by
relative path, and each card in turn imports
`./hamster-fitness-shared.js?v=…` relative to its own URL.

## What it covers

| Card | States shown |
|---|---|
| Day & Night | night/active, mid-session standstill (0 km/h), day/resting with the light automation paused, a black-furred hamster, plus a 360 px column |
| Health Score | all three badge levels, an active warning, missing trend history, and the demo-data editor preview |
| Chronicle | two configured hamsters (one departed) and two archived ones, including a free-text breed |
| Ranking | the same set, sorted by lifetime distance |

The banner at the top reports whether all four custom elements actually
registered — which is not cosmetic, see below.

## Why the registration check is there

In `v0.3.0-beta.1` **every** card disappeared from Home Assistant's "add
card" dialog, including two that had not changed. The cards are
registered as Lovelace resources with a `?v=` query so browsers re-fetch
them after an update, but `hamster-fitness-shared.js` is not a resource —
the cards import it directly — and it had no cache-busting at all.
Browsers kept their pre-0.3.0 copy, which lacks the exports 0.3.0 added.

A failed ES module import aborts evaluation of the entire file, so
`customElements.define()` never ran. Nothing threw visibly in the UI; the
cards were simply gone.

Two things guard against a repeat: the banner above, and
`tests/test_frontend_resources.py`, which fails if any card imports the
shared module without a version query or with one that disagrees with
`SHARED_MODULE_VERSION` in `const.py`.

**So: whenever you change `hamster-fitness-shared.js`, bump
`SHARED_MODULE_VERSION` and the `?v=` in every card that imports it.**
The test will tell you if you forget.

## Languages

The cards follow Home Assistant's language. `?lang=de` (the default) and
`?lang=en` mock it, so both translations can be checked side by side
without touching anything in Home Assistant — including the locale-driven
number, date and weekday formatting.

## Limitations

- `<ha-card>` is faked with plain CSS here; the real one brings Home
  Assistant's theme variables. Colours and spacing are close, not exact.
- `<ha-form>` does not exist outside Home Assistant, so the card editors
  render empty. Their logic still has to be checked in a real dashboard.
