---
name: export-deck
description: Packages a reviewed carousel for publishing - vector PDF for a LinkedIn document post, 1080 px sRGB JPEGs for Instagram, exact PNGs, captions.md (LinkedIn post, first comment, Instagram caption, alt text per slide, sources), the contact sheet and the run report - checks every file against the platform limits, logs the run, and hands it to the founder as the second and last human stop. Never publishes. Use at Step 6 of carousel-builder. Triggers on "export", "deliver the carousel", "final files".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# export-deck

The files already exist after build-and-review. This step checks they are the right files, writes what goes around them, and stops.

## Checks

`export/qa.json` (written by `scripts/qa.py`) holds an `outputs` block: PNG and JPEG count equal to the slide count, exact dimensions, sRGB profile on JPEGs, PDF page count and page ratio, PDF weight. Platform limits are in [`../../references/platform-specs.md`](../../references/platform-specs.md). Any error there blocks delivery.

`captions.md` (written by `scripts/captions.py`): LinkedIn post under 3000 characters with the thesis in the first 125, links in the first comment, Instagram caption under 2200 characters with 3 to 5 hashtags, alt text per slide under 420 characters, every source with its URL. A missing caption is an error: write it in `deck.json` `meta.captions` and re-run.

## Deliver

Write `carousel-report-<YYYYMMDD>.md` from [`../../assets/output-template.md`](../../assets/output-template.md), then show the founder, in one message:

- the contact sheet (`export/contact-sheet.jpg`) and the cover (`export/slide-01.png`);
- the paths of `export/carousel.pdf`, `export/slide-NN.jpg`, `captions.md`;
- when a video was asked for, `export/video-<aspect>.mp4`, its duration and its frames sheet (from [`../animate-deck/SKILL.md`](../animate-deck/SKILL.md));
- QA status, review rounds, the critic's verdict, open warnings;
- what to check before posting (names, sources, the first comment link).

This is stop 2. The founder approves, asks for changes (back to build-and-review with the change written in `deck.json`) or rejects (record why with keeping-project-memory). The agent never posts and never schedules.

## Log

Append the run line with [`../../../../shared/skills/keeping-project-memory/SKILL.md`](../../../../shared/skills/keeping-project-memory/SKILL.md): agent `carousel-builder`, label, status, outputs, providers per capability, checks (`copy_lint`, `qa`), critic verdict, review rounds, human verdict. Propose a decision for each correction the founder made during the run.

## Failure modes

- **PDF over 15 MB** → photos are too heavy: they are downscaled at build past 2400 px; replace an oversized PNG photo by a JPEG in `media/`.
- **Platform rejects the JPEG** (rare: wrong colour profile or size) → re-run `python3 scripts/render.py <run>/html`; never re-encode by hand.
- **The founder edits text in Canva or elsewhere** → the next run starts from `deck.json`, so ask for the change to be made there.
