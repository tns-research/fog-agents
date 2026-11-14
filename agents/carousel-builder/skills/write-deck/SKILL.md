---
name: write-deck
description: Writes deck.json, the single source of a carousel, against assets/deck.schema.json - slides as typed blocks (title, body, list, stat, chart, photo, screenshot, quote, logo-row, visual, cta), every number with its source, cover hooks and post captions - then runs build.py until the spec has no error. The model never writes HTML. Use at Step 3 of carousel-builder. Triggers on "write the slides", "slide plan", "deck spec".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# write-deck

`deck.json` is the only file the model writes for the visual part. `scripts/build.py` turns it into HTML, `scripts/fit.js` sizes the type, `scripts/qa.py` measures the result. Every later fix goes back into this file.

## Inputs

- The chosen angle and its arc, `research.md`, `context.json` (voice, proof), `brand.json`.
- The contract: [`../../assets/deck.schema.json`](../../assets/deck.schema.json). Worked example: [`../../examples/swanbase-seed-deck-20261010/deck.json`](../../examples/swanbase-seed-deck-20261010/deck.json).
- Design rules: [`../../references/design-rules.md`](../../references/design-rules.md).

## Shape of the file

```json
{
  "meta": {
    "id": "acme-onboarding", "format": "linkedin", "direction": "editorial-paper", "language": "en",
    "brand": "../project-context/brand.json", "handle": "acme.example",
    "covers": { "hooks": [ { "id": "a", "title": "...", "accent": "...", "sub": "..." }, { "id": "b", "title": "..." } ] },
    "captions": { "linkedin": "...", "first_comment": "...", "instagram": "...", "hashtags": ["#..."] }
  },
  "sources": [ { "id": "study", "label": "Org, report, 2026", "url": "https://...", "accessed": "2026-10-10" } ],
  "slides": [
    { "role": "cover", "blocks": [ { "type": "title", "text": "...", "accent": "...", "sub": "...", "source": "study" }, { "type": "photo", "src": "media/x.jpg", "alt": "..." } ] },
    { "role": "content", "blocks": [ { "type": "stat", "value": "58 %", "label": "...", "source": "study" } ] },
    { "role": "content", "blocks": [ { "type": "title", "text": "..." }, { "type": "chart", "kind": "bar", "title": "...", "unit": "seconds", "highlight": "...", "data": [ ... ], "source": "study" } ] },
    { "role": "cta", "blocks": [ { "type": "cta", "text": "...", "url": "acme.example/guide" } ] }
  ]
}
```

## Writing rules

- **One idea per slide.** One title per slide, one chart per slide. If a slide needs two ideas, it is two slides.
- **Cover.** The hook from propose-angles: 6 to 12 words, the start of the answer, the sub-line gives half the mechanism. `accent` marks one group (a number, a name). Put the real photo or the object of the subject on the cover when there is one.
- **Slide 2 sets the stakes**: the setup and the surprising outcome, so the reader swipes for the why.
- **Rhythm.** Alternate calm slides (one `stat`, one `quote`, one `photo`) with dense ones (`chart`, `list`, `screenshot`, a `body` of 40 to 55 words). Three dense slides in a row is a warning. Use `"surface": "inverse"` on one or two calm slides for contrast in the series.
- **Budgets.** Titles up to 14 words, body up to 55 words in two short paragraphs, lists up to 5 items (`numbered` only for a real sequence), stat values as printed ("58 %", "3 min 44").
- **Data.** A `chart` has a title, a `unit`, one `highlight` (the value that carries the message), a `note` when the reader needs the scope, and a `source`. Bars sort by value (columns keep their order for time series). Line charts are linear and start at zero unless the note says why not. Donuts only for 2 to 4 parts of a whole.
- **Real material first.** `photo` (always `fit: contain` unless the owner accepted a crop with `crop_ok`), `screenshot` with up to 4 `annotations` (fractions of the image: `[x, y, w, h]`), `logo-row` for partners or sources you have the right to show. A `visual` is an SVG drawn from an object of the subject (classes `c-ink`, `c-accent`, `c-fill`, `s-ink` take the direction's colours). At most one generic diagram per deck.
- **Claims.** Every `stat`, `chart` and `quote` has a `source` that resolves to a URL or a `positioning.proof` entry (`proof_ref`). A number in a `title`, `body` or `list` needs a source on the slide. Rules: [`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md).
- **Voice.** Active voice, full sentences, the project's banned words honoured, no em or en dash, no teaser for "the next carousel", no rhetorical question except the CTA question. The shared writing gate runs inside `build.py`.
- **Captions** in `meta.captions`: the LinkedIn post (the thesis in the first 125 characters, the step further, one question), the first comment (links and full source titles), the Instagram caption (shorter, "link in bio" when needed), 3 to 5 hashtags. Alt text: `slide.alt` for slides whose meaning is visual (cover with photo, screenshot, visual); `captions.py` composes the others.
- **Language** of slides and captions = `meta.language`; French gets its typography (narrow spaces before `:;!?`, guillemets) from `build.py`.

## Check

```bash
python3 scripts/build.py <run>/deck.json
```

Exit 0 means: schema valid, every data block sourced, no dash, writing gate passed. Warnings (budgets, rhythm, unsourced digits in text) are read and either fixed or justified in the slide `notes`. Do not move on with an error.

## Failure modes

- **`schema` errors** → each line gives the JSON path; fix the field. Unknown field names are errors on purpose (a typo would silently vanish).
- **`unsourced`** → add the source id or remove the number.
- **`copy:<rule>` BLOCK** → rewrite the sentence; the message gives the fix. Never disable a rule to pass.
- **`accent-not-found`** → `accent` must be an exact substring of `text`.
