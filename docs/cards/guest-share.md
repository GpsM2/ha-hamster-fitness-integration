# Hamster Fitness: Guest Access

Turns a read-only link and QR code for one hamster on or off — for a
boarding sitter, or anyone else you'd like to check in on a hamster
without giving them a Home Assistant account.

`type: custom:hamster-guest-share-card`

## Why it exists

Every other card in this integration assumes you're logged into Home
Assistant. That's the right default, but it leaves no way to answer the
concrete case this card is for: a hamster is boarding while its owners
are away, and the sitter would like a quick way to check in without
setting up an account of their own.

## What it shows

- A **switch** — on turns sharing on and creates a link, off deletes it
  immediately. Off-then-on is the only "rotate" story: there's no
  separate button to invalidate a link and replace it, since turning it
  off already does exactly that.
- While on: the **link**, a **QR code** generated on the spot (scan it
  straight from a phone, no typing), and a **copy button** for pasting it
  somewhere else — a chat message, an email.
- While off: a short note that turning it on will create a new link.

## What the other end sees

The link opens a small, self-contained page — not the real dashboard.
It shows the hamster's name, its illustrated wheel or sleep scene in its
actual fur colour, the health score, tonight's distance and current
speed, and whether it's currently running or resting. Nothing on it is
clickable in a way that changes anything: there is no path from that
page to any service call, on purpose.

It also isn't a copy of `hamster-day-night-card` or
`hamster-fitness-card` — those cards call back into Home Assistant for
things like the light toggle or history lookups, none of which make
sense (or should be reachable) from an anonymous link. The guest page is
its own small, independent piece of markup instead.

## Where the link points

`https://<your Home Assistant URL>/hamster_fitness/guest/<token>` — the
token is 256 bits of randomness, generated fresh every time the switch
turns on, and is the *only* thing that protects it: reaching it doesn't
depend on being on your home network or behind any particular proxy
setup, which matters specifically because a boarding sitter usually
isn't on your network at all.

If Home Assistant has no reachable URL configured at all (Settings →
System → Network), there's nothing to build a link from, and the card
says so instead of showing a broken one.

## Options

| Option | Default | What it does |
|---|---|---|
| `entity` | — | **Required.** The hamster's `_health_score` sensor |
| `title` | device name | Overrides the displayed name |

```yaml
type: custom:hamster-guest-share-card
entity: sensor.hamster_taco_health_score
```

## Notes

- The switch is the actual state — `switch.<hamster>_guest_access` can be
  turned on or off from an automation exactly like from this card, and
  the two always agree.
- Copying the link needs a secure context (HTTPS, or `localhost`); on a
  plain-HTTP setup the button selects the link's text instead so it can
  still be copied by hand.
- The guest page follows the visitor's device theme (light/dark), not
  your personal Home Assistant theme — it's served outside any Home
  Assistant session, so your theme customisations aren't reachable
  there.
- It also follows the visitor's own browser language (English or
  German), including number and time formatting — deliberately theirs
  and not your instance's, since the whole point is that they aren't
  logged into it. A sitter whose phone is set to English sees
  "Running for 2 h 18 min" and "6.1 km".
- A momentary hiccup (your instance restarting, a phone losing signal)
  doesn't break the link. The last reading stays on screen but is greyed
  out and the footer says "No connection", so nobody mistakes a stale
  number for a current one; it clears itself as soon as the data starts
  flowing again. Only a genuinely revoked link replaces the page with
  "this link is no longer valid".
- That also covers the case where something between the viewer and Home
  Assistant — a reverse proxy, a CDN — answers with a cached copy while
  the instance itself is down. Each response carries the moment Home
  Assistant produced it, so the page can tell a fresh answer from an old
  one being handed back, rather than trusting that a reply arrived at
  all.
