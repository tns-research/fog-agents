---
name: rendering-article-visuals
description: Turns a finished article draft into its visuals in the brand of the company running the agent. The model writes visuals-spec.json (one cover and three to five body visuals, every visible word taken from the article), scripts/article_visuals.py builds them from HTML, CSS and inline SVG templates driven by project-context/brand.json, renders PNG with a local Chromium (optionally standalone SVG), measures overflow, text size and WCAG contrast, and writes visuals.json for assembly. The model then reads the PNG through the shared render review before anything ships. No image model, no API, no remote asset. Use at the visuals step of the write mode. Triggers on "article visuals", "cover image", "og image", "comparison table image", "infographic for the article".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# rendering-article-visuals

A visual earns its place when it says something faster than the paragraph next to it: a comparison the reader would otherwise rebuild in their head, an order of steps, a list to tick, a figure with its source. This skill decides which visuals an article gets, writes their spec from the article itself, renders them in the company's brand and checks them twice: by script, then by eye.

Capabilities: `image_gen`, Local tier (HTML, CSS and SVG rendered by Playwright and Chromium, see [Failure modes](#failure-modes)) and `vision` for the review ([`../../../../shared/tools.md`](../../../../shared/tools.md#vision-read-images)).

---

## When to run

After the article draft is final (H2 wording fixed, sources in place), before assembly. A changed H2 after rendering means re-running this skill: `after_h2` must match the H2 exactly.

## Inputs

- The article draft and its facts ledger (the only source of figures).
- `<project>/project-context/brand.json` (contract: [`../../../../shared/schemas/brand.schema.json`](../../../../shared/schemas/brand.schema.json)). Missing: ask the founder to run project-context first. A visual without the brand looks like stock material; do not invent colours.
- `positioning.proof` in `<project>/project-context/context.json` when a figure comes from the company itself.

---

## Step 1: choose the visuals

One cover, always. Then three to five body visuals for a long article (1,500 words and more), two or three for a short one, none for a section that is a single argument. Never two visuals of the same kind in a row, never two under the same H2, never a visual that only repeats a sentence.

| The section holds | Kind | Holds |
|-------------------|------|-------|
| two to four options judged on the same criteria | `comparison` | 2 to 4 columns, 2 to 8 rows; a cell is text or `yes`, `no`, `partial` (drawn as icons), optionally `partial: note` |
| an ordered procedure | `steps` | 3 to 7 steps, title and one sentence each; 3 or 4 short steps lay out on one line |
| things to check before acting | `checklist` | 4 to 10 items, state `check` (default), `warn` or `cross`; two columns from 6 short items |
| one to three figures that carry the argument | `stat` | value (10 characters at most), label, source per figure |
| dated events or phases | `timeline` | 3 to 8 events, date, title, optional sentence |
| a choice that depends on one or two questions | `decision` | a yes or no question, then an outcome or a second question with two outcomes (two levels at most) |

A section that fits none of them gets no visual. Charts of a series, photos, screenshots and diagrams with arrows are out of scope here.

## Step 2: write the spec

`<article dir>/visuals-spec.json`, schema [`../../assets/visuals-spec.schema.json`](../../assets/visuals-spec.schema.json):

```json
{
  "schema_version": "1.0",
  "lang": "fr",
  "cover": { "kind": "cover", "kicker": "Guide pratique", "title": "<the H1 or a shorter form of it>", "alt": "..." },
  "body": [
    { "id": "v1", "kind": "comparison", "title": "...", "after_h2": "<exact H2 text>", "alt": "...",
      "source": "<where the cells come from, optional>",
      "data": { "corner": "Critère", "columns": ["A", "B", "C"], "highlight": 1,
                "rows": [ { "label": "Export", "cells": ["yes", "partial: Pro plan", "no"] } ] } }
  ]
}
```

Data keys per kind: `comparison` columns, rows, corner, highlight; `steps` steps, layout (auto, vertical, horizontal); `checklist` items, layout (auto, one-column, two-columns); `stat` stats (value, label, source, source_url); `timeline` events (date, title, text); `decision` question, yes, no, yes_label, no_label.

Rules:

- **Every word comes from the article.** The spec shortens, it never adds a claim, an option or a step the text does not hold. The script typesets what you write and nothing else.
- **Figures.** Every number in a `stat` visual, and every number in any other kind, comes from a source cited in the article or from `positioning.proof`, with the same value and unit. The `source` field names it as the article does. A figure you cannot trace is cut from the visual and from the article ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)).
- **Titles** state what the reader learns ("What each option covers"), not the H2 again. 90 characters at most, two lines at 44 px.
- **Alt text** describes what the image shows and its key content, so a reader who cannot see it loses nothing: the options and criteria of a table, the steps in order, the figures with their meaning. Not "image of", not the file name, not the title alone. 250 characters at most.
- **Short cells.** A table cell over six words, a step text over two lines: cut. The renderer blocks a word wider than its box and a title that does not fit at its minimum size.
- **Brand name, product names and quotes** keep their exact spelling.

Validate before rendering:

```bash
python3 ../../shared/scripts/validate_json.py assets/visuals-spec.schema.json <article dir>/visuals-spec.json
```

## Step 3: render and read the checks

From `agents/seo-audit/`:

```bash
python3 scripts/article_visuals.py --spec <article dir>/visuals-spec.json \
  --brand <project>/project-context/brand.json --out-dir <article dir>/visuals [--format png|svg|both] [--scale 2]
```

- `png` (default) suits every site. `both` adds a standalone SVG for cover, stat, steps, checklist and comparison when the site takes SVG; `svg` makes the SVG the main file for those kinds (timeline and decision stay PNG). The SVG wraps text with an estimate of the font width: the PNG is the reference, so read the SVG once too.
- Exit 0: written, no BLOCK. Exit 1: a BLOCK, or the renderer is missing. Exit 2: the spec is invalid (each error printed), nothing built.
- `visuals-qa.json` lists every check. BLOCK: a text that does not fit, a word wider than its box, text under 20 px (18 px for sources), text outside the canvas, contrast under 3:1 (brand roles or measured on the page), cover not 1200x630, a body visual over 2000 px tall, a flat band in the PNG. WARN: contrast between 3:1 and the AA threshold, a brand font that did not load (the fallback was used), empty space, PNG weight.
- A BLOCK is fixed in the spec (shorter text, fewer rows, a visual split in two). A contrast BLOCK on a brand role is fixed in `brand.json` by project-context, with the founder: never by editing the HTML, never by a local colour override.

## Step 4: look at every PNG

Mechanical checks do not see an awkward line break, a table that reads in the wrong order or a figure that says the opposite of the text. Run the review loop of [`../../../../shared/skills/reviewing-renders/SKILL.md`](../../../../shared/skills/reviewing-renders/SKILL.md), three rounds at most:

```bash
python3 ../../shared/skills/reviewing-renders/scripts/contact_sheet.py <article dir>/visuals \
  -o <article dir>/review/visuals-r1.png --title "visuals r1"
python3 ../../shared/skills/reviewing-renders/scripts/contact_sheet.py <article dir>/visuals \
  -o <article dir>/review/visuals-r1-column.png --scale 720
```

Keep the sheets out of `visuals/` (the next sheet would include them). `--scale 720` is the width of an article column: text unreadable there is unreadable on the page. Open the cover and every text-heavy visual at full size too. Beyond the checklist of that skill, check for each visual:

- every visible word against the spec and the article, accents and French spacing included;
- the reading order (rows, steps, branches) is the article's;
- the highlighted column or the `yes` icons do not favour an option the article does not favour;
- the logo is the brand's, not stretched, the right variant for the background.

Write the verdicts in `<article dir>/review/render-review.md`, fix the spec, re-render into the same folder, re-read.

## Step 5: hand off

`<article dir>/visuals/visuals.json` (schema [`../../assets/visuals-manifest.schema.json`](../../assets/visuals-manifest.schema.json)) is what assembly reads: per visual `path` (relative to the article folder), `alt`, `after_h2`, `width` and `height` in CSS pixels for the `img` attributes. The cover is also the `og:image`. Re-check a folder at any time with `python3 scripts/article_visuals.py qa --out-dir <article dir>/visuals`.

---

## Failure modes

- **Playwright or Chromium missing**: the script writes the HTML pages in `visuals/_src/` and exits 1 with the install line (`pip install playwright && python3 -m playwright install chromium`). Ask the founder to install it, or ship the article without body visuals and say so in the report. `--format svg --no-render` still produces the SVG kinds, with a manifest when every visual has one.
- **Pillow missing**: INFO `pillow-missing`, the flat band check of the PNG is skipped (`pip install pillow`).
- **Brand font without `fonts.*.files`**: a Google Fonts family (`source: google_fonts` or named in a fonts.googleapis.com `fonts_url`) is downloaded into `visuals/_src/fonts-cache/` (INFO `font-fetched`, brand.json untouched); tell the founder to run `shared/scripts/fetch_fonts.py` on brand.json to keep the files. A self-hosted family, or `--no-font-fetch`: WARN `font-fallback`, the fallback stack is used.
- **No logo file usable** (missing, failed audit, wrong variant for the background): the brand name is typeset in the display font. Say so in the review.
- **The same BLOCK after three rounds**: deliver without that visual and list it under "Known render issues".
