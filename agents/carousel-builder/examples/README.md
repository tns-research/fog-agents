# examples/

Reproducible runs of `carousel-builder`. Every example holds its `deck.json`: rebuild it with one command and compare.

| Example | What it shows | Command |
|---------|---------------|---------|
| [`swanbase-seed-deck-20261010/`](swanbase-seed-deck-20261010/) | The reference run for the stack's example brand (swanbase): research with URLs, deck spec, captions, contact sheet in `preview.jpg` | `python3 scripts/pipeline.py examples/swanbase-seed-deck-20261010/deck.json` |
| [`swanbase-seed-deck-20261010/video-frames.jpg`](swanbase-seed-deck-20261010/video-frames.jpg) | Six frames of the 9:16 video of the same deck (mid-entrance and settled states); the MP4 is not committed | `python3 scripts/animate.py examples/swanbase-seed-deck-20261010/deck.json --out /tmp/carousel-video --aspect 9:16 --sheet-tiles 6` |
| [`blocks-tour/`](blocks-tour/) | The blocks a direction must style beyond the reference deck: line chart, donut, SVG visual, on official INSEE data (English) | `python3 scripts/pipeline.py examples/blocks-tour/deck.json --out /tmp/blocks-tour` |
| [`stress/`](stress/) | A deck built to fail: title too long for any cover, empty body, missing photo, chart highlight that is not a label, unsourced stat, dash in the copy, unknown layout and block type, a word wider than the slide, 21 slides (over the 20-slide cap). Every failure must show as an explicit error, never a crash | `python3 scripts/selftest.py` |

Commands run from `agents/carousel-builder/`. `selftest.py` runs the stress deck and the reference deck and checks the expected findings, then a short 9:16 video of the reference deck and the spend gate of `generate_image.py`; it is the test to run after any engine or direction change.

## Adding an example

A folder `<brand>-<topic>-<YYYYMMDD>/` with `research.md`, `deck.json`, `media/` (each image under 150 KB, sized for its slot), a `project-context/brand.json` (or a `meta.brand` path to one), `captions.md` and one `preview.jpg` (the contact sheet, 1200 px wide, under 150 KB). Commit inputs and the preview only: the PNG, JPEG, PDF and MP4 exports rebuild in one command, so they stay out of git. Examples are in English. The example brand of the stack is swanbase; use real, sourced data and real material with consent, never invented figures. Output folders are named `html/` and `export/` because `build/` and `out/` are ignored by git.
