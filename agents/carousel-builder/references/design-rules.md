# Design rules

What a studio-grade carousel does, and what gives a generated deck away. The mechanical part is enforced by `scripts/build.py` and `scripts/qa.py`; the rest is judged in the visual review ([`../assets/review-rubric.md`](../assets/review-rubric.md)).

## Reading conditions

- A LinkedIn document page shows at about 360 to 400 px wide on a phone, an Instagram carousel at 375 to 430 px: a 1080 px slide is read at roughly a third of its size. Text under 24 px on the slide is under 8 px on the phone. Minimums enforced by qa.py: 24 px for any text, 20 px for sources, folios and chart ticks. Directions keep body text at 30 px or more.
- The cover is also seen in a grid or a feed thumbnail: hierarchy must read at 25 % (the contact sheet scale) in one second.
- Instagram's profile grid shows a 3:4 crop of 4:5 posts: keep the cover's key element away from the outer 45 px left and right.

## Composition

- One idea per slide. One title, one chart, one number in the lead role.
- Fill the frame on purpose: content anchored to the top, the bottom or both, type grown into the space by fit.js. The failure this system exists to fix is the slide centred vertically with 40 to 50 % of its height empty (qa.py `dead-space`).
- Alternate calm slides (one number, one quote, one photo, big type, air) and dense slides (chart, list, screenshot). About half and half; never three dense slides in a row. An inverse surface slide or two gives the series a pulse.
- Series consistency: same margins, same title position, same footer, a few type sizes (the direction's `steps`), not one size per slide.
- Covers give the start of the answer: the number, the reversal, the name. The sub-line gives half the mechanism.

## Type

- Measured, not fixed: each text has a min and max per direction; fit.js picks the largest size that holds in the line budget without overflow; a text that cannot hold at its minimum is an error to fix in the copy.
- Titles balanced (`text-wrap: balance`), body text `pretty`, hyphenated words and number-unit pairs never split, French punctuation on narrow no-break spaces. Line length for body around 45 to 70 characters.
- Two families at most per direction plus a mono or label face; a type scale with clear steps (ratio 1.25 or more between levels).

## Colour

- One accent per slide, on the one thing that changes or matters (the highlighted bar, the accent words of the title, the list numerals). Everything else in ink and greys.
- Contrast measured on what is really under each text: 4.5:1 for normal text, 3:1 from 40 px, 7:1 for text on a highlight. Highlights under dark ink are light (yellow, lavender, a light tint of the accent); never a mid-tone violet under black text (4.6:1).
- The brand accent is mapped to roles that keep contrast on each surface (`--accent-mark`, `--accent-text`, `--accent-fill`, `--accent-solid`); a direction never hardcodes a brand colour.

## Data-viz

- A chart exists only with real data and a source line (the build fails otherwise).
- One accent for the value that carries the message, all other marks grey; direct labels on the marks, no legend box; the unit in the chart title; linear scales, zero included for bars; ranked bars sorted, time series in time order; no 3D, no dual axis, no pie with more than 4 parts (prefer bars).
- A chart note states the scope when the reader could misread it ("average over decks that include the section").

## Real material

- Real photos, real screenshots, real logos before anything generated. Photos are never cropped by default (`contain` on a mat); a crop needs the owner's consent (`crop_ok`).
- Screenshots are annotated with numbered boxes and a legend in real text, not with arrows drawn over text.
- A `visual` redraws an object of the subject (the form, the document, the ranking, the page); at most one generic diagram (timeline, 2x2, cycle) per deck.
- People: no identifiable face without consent; a named person needs their real photo or none.

## Motion (video variant)

- Motion only decides when a block appears; it never changes a word, a size or a position the stills validated. One vocabulary: a short rise (opacity and a 24 px lift), a fade, bars growing from the zero axis, a line drawn along its length, a number counting up in its own format, a crossfade between slides.
- Reading order is the entrance order: title, then sub-line and body, list items one by one, chart frame before its marks, quote before attribution.
- Time follows the words: each slide holds its reading time, the motion is over within the first two or three seconds and the rest is reading.
- The first frame is the complete cover. The last slide stays on screen at the end.
- Forbidden in motion: glow, pulse, bounce, shake, parallax, zoom or pan on a photo, letter-by-letter typing, per-word animation, motion on a number the slide does not show.

## The tells of a generated deck (forbidden)

Mechanically flagged by qa.py: blurred `box-shadow` or `text-shadow` (glow), `backdrop-filter` (glassmorphism), `filter: blur` outside a photo mat, gradient text, gradients between two opaque colours, side-stripe cards, radius over 28 px.

Judged in review: navy or black background with violet glow, radial halos in the corners, identical card grids, pill eyebrow chips and a repeated uppercase kicker on every slide, a `01 / 08` counter on every slide, an emoji per title, stock icons in circles, a giant white logo with a drop shadow, decorative SVG unrelated to the subject (hexagons, abstract waves), centred everything.

## Copy (checked by the shared writing gate)

Active voice, full sentences, the project's banned words honoured, no em or en dash, no "not X but Y" constructions, no staged questions, no teaser of the next carousel, no outside analogy the reader has to decode on a 4:5 slide, no invented practice of the brand.
