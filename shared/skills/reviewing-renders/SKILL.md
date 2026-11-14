---
name: reviewing-renders
description: Visual review loop for anything an agent renders to an image (carousel slides, static ads, brand boards, landing-page captures, video frames). Render, build a numbered contact sheet, read it with the model's vision against a scored checklist (cut or overflowing text, contrast, distorted logo, accents, safe zones, repeated visuals, excess emptiness, stray UI, sizes), fix the source (spec, HTML, CSS, SVG) and never the image, re-render, three rounds at most. Without vision, the sheet and the checklist go to the founder. Use after every render step, before any human checkpoint or delivery. Triggers on "check the slides", "review the render", "does it look right", "contact sheet".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
---

# reviewing-renders

A file size or a page count says nothing about what a reader will see. This skill makes the agent look at its own output the way the reader will, then fix what it sees where the problem was made: in the source.

Capability used: `vision` (see [`../../tools.md`](../../tools.md#vision-read-images)). Script: [`scripts/contact_sheet.py`](./scripts/contact_sheet.py) (needs Pillow: `pip install -r shared/skills/reviewing-renders/scripts/requirements.txt`).

---

## When to run

After every render step of an agent that outputs images, and before showing anything to the founder. A human checkpoint never sees a render that has not been through at least one round.

## Inputs

- The rendered files (one folder per render round).
- The source that produced them: the spec (for example `deck.json`), the HTML/CSS, the SVG, the image prompt.
- The expected format: pixel size per file and file count, from the agent's spec.
- `brand.json` when present (colors, fonts, logo variants), contract in [`../../schemas/brand.schema.json`](../../schemas/brand.schema.json).

---

## The loop

### 1. Render

Run the agent's own render command. Keep each round in its own folder (`renders/r1/`, `renders/r2/`, ...) so rounds can be compared.

### 2. Run the mechanical checks first

Anything a script can measure is measured, not eyeballed: the agent's own QA script when it has one (overflow, fitted title size, WCAG contrast), then the size check below. A failing mechanical check is fixed before the visual read.

### 3. Build the contact sheets

From the repo root (adapt the relative path from the agent folder: `../../shared/skills/reviewing-renders/scripts/contact_sheet.py`):

```bash
python3 shared/skills/reviewing-renders/scripts/contact_sheet.py renders/r1/ \
  -o renders/r1/contact-sheet.png --expect 1080x1350 --title "carousel r1"
python3 shared/skills/reviewing-renders/scripts/contact_sheet.py renders/r1/ \
  -o renders/r1/contact-sheet-feed.png --scale feed
```

- `--expect WxH` flags every file of the wrong size in red and exits 1.
- `--scale feed` draws each tile 375 px wide, the width of one phone feed column in CSS pixels: text that is hard to read on that sheet is hard to read in the feed. Build it for every social format.
- `--scale thumb` (150 px) checks a cover or a thumbnail at grid size.

### 4. Read the sheets

Open the contact sheet with the host's image reading. A sheet downsamples: open a tile's own file at full size whenever a check is borderline, and always for text-heavy tiles. Judge the pixels, never your memory of the HTML.

### 5. Score every tile against the checklist

| # | Check | FAIL when | WARN when |
|---|-------|-----------|-----------|
| R1 | Text cut or overflowing | any glyph touches or crosses the canvas edge or its box, a line is clipped, an ellipsis replaces words | a word breaks across lines with a hyphen it does not need |
| R2 | Safe zones | text or logo closer to the edge than 6 % of the width (65 px on a 1080 px canvas); on 9:16, key text in the top 14 % or bottom 20 % (platform UI covers them) | inside 8 % of the width |
| R3 | Contrast | body text under 4.5:1 or large text (title, number) under 3:1 against its local background, text on a photo without a scrim | within 10 % of a threshold |
| R4 | Legibility at feed scale | on the feed sheet, body text cannot be read; on the source canvas, body text under 28 px or a source line under 20 px on a 1080 px wide canvas | body text between 28 and 32 px |
| R5 | Logo | stretched or squashed (width/height ratio off by more than 2 % from the file), cropped, wrong variant for the background (`logos.on_dark` on dark, `logos.on_light` on light), logo ink under 3:1 against its background | size changes between slides of one set |
| R6 | Accents and characters | a missing glyph (empty box, `?`), accents lost (`Ã©`, `e` instead of `é`), a fallback font inside a word, any visible word that differs from the spec (copy every visible word, product labels included, and compare) | curly and straight quotes mixed |
| R7 | Repeated visual | the same image, illustration or layout on two consecutive tiles without a reason in the spec, two tiles identical | the same layout on more than half the set |
| R8 | Excess emptiness | more than 40 % of the canvas carries no content and no deliberate design element | 25 to 40 % |
| R9 | Stray UI and placeholders | browser chrome, scrollbar, cookie banner, broken image icon, debug outline, `{{...}}`, `TODO`, lorem ipsum | |
| R10 | Size and count | a file of the wrong pixel size (red on the sheet), a missing or extra file against the spec | |
| R11 | Consistency | colors or fonts outside `brand.json`, page numbers out of sequence, margins that jump between tiles | |

Write the result into `render-review.md` next to the renders, one block per round:

```markdown
## Round 1 (renders/r1/, 8 files)

| Tile | Check | Verdict | Where | Fix in the source |
|------|-------|---------|-------|-------------------|
| #03 | R1 | FAIL | title, last line clipped at the right edge | deck.json slide 3: shorten title to 6 words, or let fit.js size it |
| #05 | R5 | FAIL | logo squashed, ratio 3.1 vs 4.27 | _base.html: set height only, width auto |
| all | R4 | PASS | | |

Round verdict: 2 FAIL, 1 WARN.
```

### 6. Fix the source, never the image

Every fix lands in what produced the pixels: the spec, the template HTML/CSS, the SVG, the brand token, the image prompt. Never paint over, crop, retouch or regenerate the output file to hide a problem: the next render would bring it back, and the source would keep lying about the deliverable. When a background came from a paid image model, regenerating it goes through the agent's spending gate.

### 7. Re-render and re-read

Render into the next round folder, rebuild the sheets, re-score every changed tile on all checks and every other tile on the checks that failed before.

### 8. Stop

- **0 FAIL** → done. WARNs are listed in the report and kept only with a reason.
- **3 rounds reached with FAILs left** → stop. Deliver with a "Known render issues" section (tile, check, what was tried) and ask the founder. Never start a fourth round.
- A FAIL that comes back unchanged after a fix → the fix targeted the wrong source. Find the producing line before trying again; it still counts as a round.

Record the number of rounds in the run log (`render_review_rounds`, see [`../keeping-project-memory/SKILL.md`](../keeping-project-memory/SKILL.md)).

---

## Fallback without vision

When the resolved `vision` provider is `manual` (the host model cannot read images):

1. Run steps 1 to 3 as usual. The mechanical checks and `--expect` still run.
2. Hand the founder the contact sheets and the checklist as questions, grouped in one message: "On sheet `contact-sheet-feed.png`, can you read every line? Is any text cut at an edge? Is the logo stretched?" Name the tiles to look at first (text-heavy slides, the cover).
3. Turn each answer into a source fix, one round per answer batch, same 3-round cap.
4. Mark the report "Visual review: founder (no vision on this host)". When nobody can look (unattended run), mark it "Visual review: not done" and list the deliverable as unreviewed.

---

## Failure modes

- **Pillow missing** → `contact_sheet.py` exits 2 with an install hint. Open the files one by one, or hand the folder to the founder.
- **Renderer fails** → no review; report the render error, never review an older round as if it were current.
- **The spec itself is wrong** (a title too long for any layout) → fix the spec text, then re-run the writing gate on the changed copy.
