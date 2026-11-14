# references/

Reference material the workflow reads, plus pointers for contributors.

| File | Read by | What it holds |
|------|---------|---------------|
| [`design-rules.md`](design-rules.md) | write-deck, art-direct, build-and-review, animate-deck | Reading conditions, composition, type, colour, data-viz, real material, motion for the video variant, the tells of a generated deck |
| [`platform-specs.md`](platform-specs.md) | export-deck, animate-deck | LinkedIn document and Instagram carousel limits, video limits and safe zones, what render.py produces |

The review rubric lives in [`../assets/review-rubric.md`](../assets/review-rubric.md), where the shared fresh-eyes skill looks for an agent's rubric.

## Engine notes

- Playwright (Python), Chromium only: https://playwright.dev/python/. render.py and qa.py wait for `document.fonts.ready`, window load and fit.js (`body[data-fitted="1"]`) before measuring or capturing.
- PNGs come from element screenshots at the slide's exact size; the PDF from Chromium's print with `@page` set to the slide size, printed before any screenshot (a scrolled page prints blank pages in Chromium).
- Video (`scripts/animate.py`): the page is staged by `scripts/animate.js` after fit.js; every motion is a paused Web Animation whose `currentTime` is set per frame (https://developer.mozilla.org/en-US/docs/Web/API/Animation/currentTime), Chromium's `Page.captureScreenshot` returns each PNG, ffmpeg (https://ffmpeg.org/ffmpeg.html) reads them from a pipe. Unchanged frames are reused, so the capture cost follows the motion, not the duration.
- Contact sheets: [`../../../shared/skills/reviewing-renders/SKILL.md`](../../../shared/skills/reviewing-renders/SKILL.md).

## AI images (capability `image_gen`, last resort)

Optional, through the tool plan ([`../../../shared/tools.md`](../../../shared/tools.md)): `scripts/generate_image.py --provider fal|openai|manual` (`fal` and `openai` bill per image and run only with `--confirm-spend`, after the founder's yes). Real photos, screenshots and SVG drawn from the subject come first; a generated image is never a person, a customer, a product the company does not make, or a chart. The `manual` tier writes the prompt for the founder's own tool and the founder drops the file in `media/`.

## Prior art

- `frontend-design` skill (Anthropic): anti-slop HTML aesthetics.
- Riso, poster and editorial conventions: Swiss International Style (Müller-Brockmann, "Grid Systems in Graphic Design"), risograph printing (spot inks, misregistration, halftone).
- Data-viz: one accent, direct labels, linear scales, source line (common practice of newsroom graphics desks).
