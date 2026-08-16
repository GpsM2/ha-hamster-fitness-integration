# Sharing a picture

Every card has a small share icon in the corner of its header. It turns
the hamster's numbers into one portrait image you can save and post,
instead of screenshotting a dashboard and cropping it.

## What happens

Pressing the icon opens a short dialog listing the values that card can
offer, with a sensible selection already ticked. Untick what you don't
want, press **Create image**, and it lands in your downloads.

The picture is built fresh at that moment, so it always carries what was
on the card when you pressed the button.

## What each card offers

| Card | Scope | Offered by default |
|---|---|---|
| Health Score | one hamster | score, tonight's distance |
| Day & Night | one hamster | tonight's distance, current speed, score |
| Track Weight | one hamster | weight |
| Running | one hamster | this week, longest night, fastest ever |
| Chronicle | every hamster | how many, how many still with you |
| Ranking | every hamster | front runner, how many, total distance |

The four per-hamster cards name the hamster. Chronicle and Ranking are
about the household, so they are not tied to a single name — a hamster
that has moved out still counts.

Anything not ticked by default is still there to switch on: lifetime
distance, weight, climate, and so on.

## The background

The sky is the same one the Day & Night card paints, generated fresh
rather than picked from a set of stock images. It follows the real
conditions: the sun's elevation, your illuminance sensor if you have
one, and your weather entity — so a picture made during a rainy night
actually looks like one.

Nothing is bundled for this. There are no background images in the
repository, which is why installing and updating the integration stays
small.

## Saving versus sharing

The image is **saved to your device**, and you share it from your gallery
or files app. That is deliberate rather than a limitation:

- The browser's native share sheet (`navigator.share`) needs a secure
  context. Home Assistant is very often reached over plain `http://` on
  the local network, where the API simply does not exist.
- The Android companion app is a WebView, and Android's WebView does not
  implement it at all. iOS does.

So where the native share sheet genuinely works, you get it — and
everywhere else you get a download, which works. You are never left with
a button that does nothing.

## Notes

- Only real values are shared. The Health Score card's demo preview, the
  one shown before you have picked a hamster, offers nothing to share —
  an image of invented numbers is not something to post.
- Text on the image uses ordinary system fonts. A custom font would have
  to be embedded in the file, and would otherwise silently fall back to
  something else once the image is rendered.
