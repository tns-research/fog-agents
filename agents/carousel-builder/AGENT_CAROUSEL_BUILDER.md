---
name: carousel-builder
description: Builds a studio-grade LinkedIn (PDF document) and Instagram (JPEG sequence) carousel from a topic. Researches first and keeps every number sourced, proposes angles, writes a deck.json spec that a deterministic script turns into HTML (the model never edits HTML), shows the cover in several art directions at feed size, then renders, measures (fit, overflow, contrast, safe zone, text size, dead space) and reviews its own slides visually for up to three rounds before a fresh reviewer critiques the deck. Six shipped art directions, the brand applied on top, real data-viz, annotated screenshots and photos never cropped. Exports PNG, Instagram JPEG, vector PDF, captions and alt text, and on request the same deck as a short MP4 (4:5, 9:16 or 1:1) rendered locally.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Carousel Builder Agent

A carousel that a design studio would sign, from a topic typed in chat. The model researches, writes and judges; scripts build, measure and render. One rule holds the whole agent together: **the model writes a spec (`deck.json`), a script produces the deliverable, a loop checks the result.**

## When to run

- You have a topic, a set of notes, a market-signal handoff or URLs, and you want a carousel that teaches something with real material (sourced numbers, screenshots, photos, quotes).
- You want the carousel in your brand without designing it, and to choose its look on a rendered image rather than a description.

**Don't use it for:** a single static ad (`static-ads-builder`), a long article, a filmed or narrated video. The video variant here is the carousel itself, animated (Step 7).

## Skills loaded

| Skill | Step | Output |
|-------|------|--------|
| [`skills/research-topic/SKILL.md`](skills/research-topic/SKILL.md) | 1 | `research.md`: facts with URLs, usable numbers, objects from the subject, available material |
| [`skills/propose-angles/SKILL.md`](skills/propose-angles/SKILL.md) | 2 | 3 to 5 angles built on the research, ranked |
| [`skills/write-deck/SKILL.md`](skills/write-deck/SKILL.md) | 3 | `deck.json` (contract: [`assets/deck.schema.json`](assets/deck.schema.json)), captions included |
| [`skills/art-direct/SKILL.md`](skills/art-direct/SKILL.md) | 4 | cover board: directions x hooks at feed size, **human stop 1** |
| [`skills/build-and-review/SKILL.md`](skills/build-and-review/SKILL.md) | 5 | build, fit, render, `qa.json`, visual review, spec fixes, 3 rounds max, fresh reviewer |
| [`skills/export-deck/SKILL.md`](skills/export-deck/SKILL.md) | 6 | PDF, JPEG, PNG, `captions.md`, report, **human stop 2** |
| [`skills/animate-deck/SKILL.md`](skills/animate-deck/SKILL.md) | 7, optional | `export/video-<aspect>.mp4` from the same slides, `video-<aspect>.json` (timeline, QA), frames sheet; shown at stop 2 |

Shared methodology: [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) (option `brand`), [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md), [`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md), [`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md), [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md), [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md).

## Assets used

| Asset | Used by |
|-------|---------|
| [`assets/deck.schema.json`](assets/deck.schema.json) | write-deck (contract), `scripts/build.py` (validation) |
| [`assets/output-template.md`](assets/output-template.md) | export-deck (run report) |
| [`directions/README.md`](directions/README.md) and `directions/<id>/` | art-direct, build-and-review |
| [`references/design-rules.md`](references/design-rules.md) | write-deck, art-direct, build-and-review |
| [`assets/review-rubric.md`](assets/review-rubric.md) | build-and-review (visual review and fresh reviewer) |
| [`references/platform-specs.md`](references/platform-specs.md) | export-deck |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `topic` | yes | n/a | A sentence, an outline, notes, or URLs to build from. |
| `format` | no | `linkedin` | `linkedin` and `instagram` (1080x1350), `square` (1080x1080). One deck serves both platforms. |
| `video` | no | none | Aspects of the MP4 variant: `4:5` (1080x1350), `9:16` (1080x1920), `1:1` (1080x1080); optional local music file and total duration cap. |
| `language` | no | from `context.json`, else `en` | Slide and caption language. |
| `slide_count` | no | 6 to 10 | 3 to 20. Past 20 the build fails (`too-many-slides`): Instagram publishes 20 images per carousel at most, LinkedIn documents take more. |
| `direction` | no | chosen at stop 1 | Skip the cover board by naming one (`python3 scripts/build.py --list-directions`). |
| `sources` | no | n/a | URLs, files, a `market-signal` sidecar. |
| `media` | no | n/a | Photos, screenshots, logos to use. |

## Tools

Every external capability is optional; providers and tiers: [`../../shared/tools.md`](../../shared/tools.md). Resolve them at Step 0 with [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) and announce the plan in one line.

| Capability | Used for | Without it |
|------------|----------|------------|
| `web_search`, `scrape` | Step 1 research beyond what the founder gave | research uses project-context, the handoffs and the URLs or files supplied; the report says so |
| `vision` | Step 5 visual review of the PNGs and the contact sheet | `qa.json` still runs; the contact sheet and the rubric go to the founder at stop 2 ("Visual review: founder") |
| `critic` | Step 5 fresh reviewer | "Fresh-eyes review: not run" in the report; the deck is listed as unreviewed |
| `copy_lint` | every text of `deck.json`, run by `build.py` | the writing-gate checklist applied by hand, "Writing gate: manual" in Methodology |
| `image_gen` | last resort only, for an illustration no real photo, screenshot or SVG can provide | the slide uses a `visual` (SVG drawn from an object of the subject) or a photo the founder drops in `media/`; with the `manual` tier the agent writes the prompt for the founder's tool (`scripts/generate_image.py --provider manual`). The `fal` and `openai` tiers bill per image: the script refuses them without `--confirm-spend` (exit 6, price printed), and the agent adds the flag only after the founder agreed to that price |

Local and free, always needed: Python 3.10+, Pillow, Playwright with Chromium (`pip install -r scripts/requirements.txt && playwright install chromium`). For the video variant only: ffmpeg and ffprobe (no video generation service: the MP4 is rendered from the slides; a HyperFrames CLI, when installed, is an optional route for a richer composition). Network access for Google Fonts; offline, fonts fall back and `qa.json` warns `font-fallback`.

Sub-agents (when the harness has them) parallelise the cover board, the direction trials and the fresh review, by waves of three; without them the same steps run one after the other with the same commands.

## Workflow

**Step 0: context, tools, memory.** Resolve the project slug once. Load `<your-projects-root>/<project>/carousel-builder/config.json` (create it from `config.example.json`). Load the shared context with [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) and its `brand` option: `brand.json` (the `schema_version` "2.0" layout of `shared/schemas/brand.schema.json`; a file without it is mapped on load), `context.json` (`positioning.proof`, `voice.claims_policy`, `voice.banned_words`). Read the project's decisions with [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md): a direction or a phrasing the founder rejected before stays rejected. Resolve tools. If `<project>/market-signal/market-signal-<YYYYMMDD>.json` exists ([`../../shared/handoffs.md`](../../shared/handoffs.md)), load its pains, hooks and verbatim quotes. Ask, in one message, only what is still missing (topic, language).

**Step 1: research before angles.** [`skills/research-topic/SKILL.md`](skills/research-topic/SKILL.md). URLs and documents are accepted as sources. Output `research.md`: each fact with its URL and access date, numbers usable in a chart, objects of the subject usable as visuals, real material available (photos, screenshots, logos), caveats. A number without a source never reaches a slide.

**Step 2: angles.** [`skills/propose-angles/SKILL.md`](skills/propose-angles/SKILL.md). 3 to 5 angles drawn from the research, ranked, with a hook each. No stop here: the founder sees the two best hooks on the cover board at Step 4 and can ask for another angle there.

**Step 3: write the deck.** [`skills/write-deck/SKILL.md`](skills/write-deck/SKILL.md). Write `deck.json` against [`assets/deck.schema.json`](assets/deck.schema.json): `meta` (format, direction, language, brand, two to three cover hooks, captions), `sources`, slides with typed blocks (`title`, `body`, `list`, `stat`, `chart`, `photo`, `screenshot`, `quote`, `logo-row`, `visual`, `cta`). Every stat, chart and quote carries a source. Run `python3 scripts/build.py <deck.json>`: it validates the schema, the claims (a data block without URL or approved proof fails), dashes, budgets, rhythm, and runs the shared writing gate on every text. Fix until 0 error.

**Step 4: art direction, human stop 1 (on image).** [`skills/art-direct/SKILL.md`](skills/art-direct/SKILL.md). Pick three directions that fit the content (or all six), render the board: `python3 scripts/pipeline.py <deck.json> --covers --directions a,b,c --first-layout`. Review it yourself first (the hook must read at 360 px wide), then show `covers/cover-board.jpg` and ask the founder for one direction and one hook. This is the only stop before the final deck.

**Step 5: build, measure, review, fix.** [`skills/build-and-review/SKILL.md`](skills/build-and-review/SKILL.md). `python3 scripts/pipeline.py <deck.json>` builds `html/index.html`, fits every text in the browser (`scripts/fit.js`), renders PNG, JPEG and PDF, writes `export/qa.json` and the contact sheet at 25 % scale. Then read the sheet and every PNG at full size with [`assets/review-rubric.md`](assets/review-rubric.md). Fix in `deck.json` (copy, layout, surface, order) or, when a direction itself is wrong, in its `style.css`; never in the HTML or the image. Three rounds at most. Then the fresh reviewer of [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md) reads `research.md`, `deck.json`, `qa.json` and the contact sheet, scores the rubric, and the deck is revised once.

**Step 6: export, human stop 2.** [`skills/export-deck/SKILL.md`](skills/export-deck/SKILL.md). Deliver `export/carousel.pdf` (LinkedIn), `export/slide-NN.jpg` (Instagram), PNGs, `captions.md` (LinkedIn post, first comment, Instagram caption, alt text per slide, sources), the contact sheet and the report from [`assets/output-template.md`](assets/output-template.md). When a video was asked for, Step 7 runs before this stop and its files join the same message. Log the run with keeping-project-memory. The founder approves and publishes; the agent never posts.

**Step 7 (optional): video variant.** [`skills/animate-deck/SKILL.md`](skills/animate-deck/SKILL.md). Only once the stills pass QA: `python3 scripts/animate.py <deck.json> --aspect 4:5` (or `9:16`, `1:1`; or `pipeline.py <deck.json> --video 4:5,9:16`). Same HTML, same fitted slides, sober entrances block by block, reading time per slide from its word count, crossfades, deterministic capture (Playwright drives the clock, ffmpeg encodes H.264 yuv420p 30 fps faststart), optional local music with a fade out. Read the QA in `export/video-<aspect>.json` and the frames sheet, fix in `deck.json` when a slide reads badly, two rounds at most. A 9:16 video shows the 4:5 slide whole inside the Reels safe box, never recomposed.

## Output format

The report follows [`assets/output-template.md`](assets/output-template.md): angle and why, direction and hook chosen, slide manifest, sources, QA result and review rounds, critic verdict, files, posting notes, methodology (provider per capability), limitations.

## Output location

```
<your-projects-root>/<project-slug>/carousel-builder/<label>-<YYYYMMDD>/
  ├── research.md
  ├── deck.json                  # the source of truth
  ├── media/                     # photos, screenshots, SVG files used by the deck
  ├── covers/cover-board.jpg     # stop 1
  ├── html/index.html            # built by build.py, never edited
  ├── export/
  │   ├── slide-01.png ...       # exact 1080x1350 (or 1080x1080)
  │   ├── slide-01.jpg ...       # Instagram, quality 88, sRGB
  │   ├── carousel.pdf           # LinkedIn document, vector
  │   ├── contact-sheet.jpg      # 25 % scale
  │   ├── qa.json
  │   ├── video-4x5.mp4          # optional, Step 7 (also video-9x16.mp4, video-1x1.mp4)
  │   ├── video-4x5.json         # timeline per slide and video QA
  │   └── video-4x5-frames.jpg   # frames sheet for the review
  ├── captions.md
  └── carousel-report-<YYYYMMDD>.md
```

## Failure modes

- **Topic too vague** → research still runs on the closest defensible framing; the angles say which assumption they make.
- **No source for a number the angle needs** → drop the number or the angle. Never an "illustrative" value. A deck can have no number at all.
- **`deck.json` fails the schema or the claims check** → `build.py` lists each error with its JSON path; fix the spec, rebuild.
- **`text-too-long` in `qa.json`** → the copy is too long for the layout at the direction's minimum size: shorten it, split the slide, or change the layout. Never lower the minimum to make it fit.
- **`contrast` error** → change the slide `surface`, or the brand accent role is wrong for that direction: report it; never hand-pick a colour in the HTML.
- **`missing-asset`** → the file path in `deck.json` is wrong or the founder has not dropped the file yet; the slide shows a labelled placeholder until then.
- **`font-fallback` warning** → no network for Google Fonts or a misspelt family; ship only after the fonts load or after the founder accepts the fallback.
- **No `vision` capability** → the founder reviews the contact sheet against the rubric at stop 2; the report says "Visual review: founder".
- **No sub-agents** → covers and the fresh review run sequentially; a second session or model CLI plays the critic (see the shared skill).
- **Three review rounds without a clean QA** → stop, deliver with the remaining errors listed at the top of the report, never present it as ready.
- **Video exits 1 before rendering** → the stills have spec errors or texts that do not fit: the video never shows a slide the stills would not ship; fix `deck.json` first.
- **Video too long** → `--max-duration` shortens the holds, never the entrances; a dense slide is better split in `deck.json`.
- **Founder rejects a direction or a phrasing** → record it with keeping-project-memory so the next run does not propose it again.

## Per-project config

```
<your-projects-root>/<project>/carousel-builder/config.json
```

See [`config.example.json`](config.example.json): format, language, slide range, handle, preferred and excluded directions, a locked direction for a series, brand fonts, video aspects, duration cap and music, optional `tools` override.
