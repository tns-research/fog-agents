---
name: build-and-review
description: Builds the full carousel from deck.json, measures it in the browser and reviews it like an art director until it is clean - build.py, fit.js (measured type), render.py (exact PNG, JPEG, vector PDF), qa.py (overflow, safe zone, text size at feed scale, WCAG contrast per text node, collisions, dead space, visual tells) and a contact sheet at 25 % - then the model reads every PNG, fixes the spec, and loops three rounds at most before a fresh reviewer critiques the deck once. Use at Step 5 of carousel-builder. Triggers on "build the carousel", "render", "check the slides".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# build-and-review

Measures first, eyes second, a stranger third. Scripts catch what can be counted; the model catches what must be seen; a reviewer who did not write the deck catches what the author can no longer see.

## Commands

```bash
python3 scripts/pipeline.py <run>/deck.json
```

It runs, in order:

| Step | Script | Writes |
|------|--------|--------|
| build | `scripts/build.py` | `html/index.html` (one section per slide, fonts, CSS, fit.js inline), `html/build-report.json` |
| fit | `scripts/fit.js` (in the page) | each text sized between the direction's min and max, `window.__fit` |
| render | `scripts/render.py` | `export/slide-NN.png` (exact size), `export/slide-NN.jpg`, `export/carousel.pdf`, `export/render.json` |
| measure | `scripts/qa.py` | `export/qa.json`, `export/contact-sheet.jpg` (25 % scale, shared contact sheet) |
| captions | `scripts/captions.py` | `captions.md` |

Each script also runs alone (`--help`). Open `html/index.html` in a browser to see the whole deck.

## The loop (3 rounds at most)

1. **Mechanical.** Read `export/qa.json`. Every error is fixed before looking further:
   - `text-too-long`, `overflow`: shorten the copy, split the slide, or move a block to another slide. Never lower a direction minimum.
   - `contrast`: change the slide `surface`; if the direction's accent role is wrong for the brand, report it.
   - `outside-safe-zone`, `collision`: a layout problem of the direction (report it with the slide) or a block that does not belong on that slide.
   - `missing-asset`, `empty-block`, `build:*` (schema, claims, writing gate): fix the spec or the file.
   - `outside-slide`, `text-too-small`, and the tells (`blurred-shadow`, `backdrop-filter`, `blur-filter`, `gradient-text`): fix the spec, or the direction when it causes them on every deck.
   Warnings (`dead-space`, `text-on-image`, `low-res-image`, `font-fallback`, `gradient`, `side-stripe`, `big-radius`) are each fixed or justified in the report. The full list: `python3 scripts/qa.py --help`.
2. **Visual** ([`../../../../shared/skills/reviewing-renders/SKILL.md`](../../../../shared/skills/reviewing-renders/SKILL.md) with [`../../assets/review-rubric.md`](../../assets/review-rubric.md)). Open `export/contact-sheet.jpg`, then every `export/slide-NN.png` at full size. Judge as an art director: the hierarchy reads in one second at 25 %, one idea per slide, calm and dense slides alternate, the series is consistent (margins, title position, footer), nothing is cut, no dead band, the photo is whole, the logo small and posed, the accent used once, the chart says its point without the caption. Score the rubric; anything under 2 is a fix.
3. **Fix the source, never the output**: `deck.json` first (copy, block choice, layout, surface, order, an annotation box), the direction's `style.css` or `direction.json` only when the fault is the direction's and would hit every deck. Never edit `html/index.html` or an image.
4. Rebuild and repeat. Stop when `qa.json` has 0 errors and the rubric has no score under 2, or after round 3 (deliver with the remaining issues at the top of the report).

## Fresh reviewer (once)

Follow [`../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md). Packet: the founder's brief verbatim, `research.md`, `deck.json`, `export/qa.json`, `export/contact-sheet.jpg`, the rubric. The reviewer returns PASS or FAIL per written constraint (sources, claims, budgets, language), a 0 to 2 score per rubric criterion and located problems with a proposed fix, without rewriting. Revise once, re-run the pipeline, record the verdict in the report.

## Without vision, without sub-agents

- No `vision`: steps 1 and 3 still run; the contact sheet and the rubric go to the founder at stop 2, the report says "Visual review: founder".
- No sub-agent: the fresh review runs in a blank session or another model CLI with the same packet; failing that, the founder answers the rubric. Never count a second pass by the same session as the fresh review.

## Failure modes

- **Fonts did not load** (`font-fallback`) → measurements and renders used fallback faces: fix network or names before trusting the fit.
- **Playwright or Chromium missing** → `pip install -r scripts/requirements.txt && playwright install chromium`; nothing renders without it.
- **The same error survives two rounds** → the slide is wrong, not the wording: change its block type or merge it with the next one.
