---
name: render-ads
description: Renders ads.json locally, for free, to exact PNG and JPEG files in 1:1, 4:5 and 9:16 through scripts/pipeline.py (HTML/CSS in Chromium, text fitted in the browser, Meta safe zones, contrast and DOM text measured in qa.json, contact sheet), then reviews the renders visually and fixes the spec, three rounds at most. When a concept needs a text-free photographic background, it owns the two spend gates of scripts/render_ads.py (Gate 1 which plates, Gate 2 model + resolution + total spend), or the zero-cost manual pack. Use at Steps 4 and 5 of static-ads-builder. Triggers on "render the ads", "build the creatives", "generate a background", "spend on fal".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*) Bash(fal:*)
---

# render-ads

Local rendering is the default and costs nothing. An image model is called only for a plate: a photographic background that contains no word, no logo and no product, because the HTML sets all of those exactly.

## Plates (only when a concept has a media of role `plate`)

```bash
python3 scripts/plates.py prepare <run>/ads.json
```

It writes `<run>/plates/plate-briefs-<ratio>.json` (the tallest format of each ad; plates render with `fit: cover`, so smaller formats crop a picture made for the ad, never a real photo) and prints the commands below. Each prompt ends with a fixed exclusion: no text, no letters, no logo, no product.

**Gate 1, which plates (blocking).** Show one line per plate: ad, scene, ratio, and the real-media alternative that would avoid it. The founder names the plates to generate. No answer, no plate.

**Gate 2, model + resolution + spend (blocking).** With an API provider:

```bash
python3 scripts/render_ads.py --estimate --provider <fal|openai> --count <N> --model <model> --resolution <1K|2K|4K>
```

Show the bottom line, read from the script output: "N plates on <model> at <resolution> = about $<total> ($<per image>/image)". Resolution is the main cost lever; the bundled price table is checked against the provider's page before quoting it. The founder confirms model, resolution and spend in one explicit answer; the Gate 1 answer never carries over. Then:

```bash
python3 scripts/render_ads.py --batch <run>/plates/plate-briefs-<ratio>.json --select "<n,...>" --out <run>/plates \
  --ratio <ratio> --provider <fal|openai> --model <model> --resolution <res> --confirm-spend
```

Add `--confirm-spend` only after the founder's explicit yes at Gate 2, never on your own initiative: without it (or `FOG_ALLOW_SPEND=1` set by an orchestrator that already holds that yes) the script sends nothing, prints the estimate for the selection and exits 4. With fal, each local reference image of a brief is uploaded to fal storage under a public URL: say so at Gate 2 when a plate attaches the founder's files. One attempt per plate, no retry; a new attempt is new spend and goes through Gate 2 again. Without an API (or by choice): `--provider manual` writes `<run>/plates/_manual/MANUAL-RENDER.md` and one prompt file per plate, 0 USD; the founder generates in their own tool and drops `NN-<anything>.jpg` in `<run>/plates/`. Then:

```bash
python3 scripts/plates.py status <run>/ads.json
```

Exit 0 is required before Step 5 (set `media.src` to a dropped file when its name differs).

## Render, measure

```bash
python3 scripts/pipeline.py <run>/ads.json [--width 1440]
```

- `html/`: built by `build.py`, never edited.
- `renders/<project>_<NN>_<stage>_<angle>_<style>_<ratio>.png` and `.jpg`: exact 1080x1080, 1080x1350, 1080x1920 (or 1440 wide with `--width 1440`, the size Meta's feed guide recommends).
- `renders/qa.json`: per render, errors (`text-too-long`, `overflow`, `outside-canvas`, `outside-safe-zone`, `text-too-small`, `contrast`, `dom-text-mismatch`, `missing-asset`, `logo-too-small`, `logo-contrast`, `logo-clear-space`, the tells of generated design) and warnings (`text-on-image`, `low-res-image`, `dead-space`, `dead-space-9x16`, `empty-band`, `build:logo-text`, `font-fallback`). The full list with thresholds: `python3 scripts/qa.py --help`.
- `renders/contact-sheet.jpg`: all renders at 360 px per tile.

Fix every error in `ads.json`: shorter copy, fewer bullets, another surface, another style, a taller format. Never lower a minimum size, never edit `html/`, never touch a PNG.

## Look, fix, three rounds

Read `contact-sheet.jpg`, then every PNG at full size, with the checklist of [`../../../../shared/skills/reviewing-renders/SKILL.md`](../../../../shared/skills/reviewing-renders/SKILL.md). What the scripts do not judge, the review does:

- the hook reads first at feed size (360 px wide), the CTA last;
- a real photo or product is shown whole and is the right one for the claim; a third-party brand on a photo is flagged;
- 9:16 keeps every word inside the band (the scripts check it) and fills the frame: large type in the text zone, the CTA just above Meta's bottom band, the photo or the footer panel running through that band (`dead-space-9x16` and `empty-band` flag a 4:5 composition letterboxed in a tall frame);
- the logo is the brand's real mark and wordmark, legible at feed size; `build:logo-text` means `brand.json` has no logo file, so ask `project-context` for one before spend;
- the three formats of one concept feel like one ad, not three;
- no tell of generated design: glow, glass, gradient text, identical cards, a giant logo;
- the batch varies: no two concepts with the same style and the same hook shape.

Write `renders/render-review.md` (tile, check, verdict, fix in the source), fix `ads.json`, rerun `pipeline.py`. Three rounds at most; a FAIL left after the third goes to the report under "Known render issues". Without vision, the contact sheet and the checklist questions go to the founder in one message.

## Failure modes

- **Playwright or Chromium missing** → `pip install -r scripts/requirements.txt && playwright install chromium`; without them, stop at the spec and say so: an unrendered ad is not delivered.
- **`font-fallback`** → no network for Google Fonts or a misspelt family: ship only after the font loads, or after the founder accepts the fallback.
- **A provider key is missing at Gate 2** → `render_ads.py` exits 2 before any request; offer the other provider or `--provider manual`.
- **`render_ads.py --batch` exits 4 (spend gate closed)** → nothing was sent; show the printed estimate at Gate 2 and re-run with `--confirm-spend` only after the founder's yes.
- **A plate render fails** → logged, no retry; the ad keeps its labelled placeholder until a plate exists.
