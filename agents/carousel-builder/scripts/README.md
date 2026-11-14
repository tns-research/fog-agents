# scripts/

The carousel engine. The model writes `deck.json`; these scripts build, size, render, measure and package it. Every script runs alone (`--help`) and is deterministic: the same inputs give the same files.

```bash
pip install -r scripts/requirements.txt
playwright install chromium
```

| Script | Does | Writes |
|--------|------|--------|
| `pipeline.py` | One command: build, render, qa, captions. `--covers` renders the cover board (directions x hooks at feed size). `--video [4:5,9:16,1:1]` adds the MP4 variant when the stills pass. | everything below |
| `build.py` | `deck.json` + direction + `brand.json` → HTML. Validates the schema, claims, dashes, budgets, rhythm; runs the shared writing gate on every text; derives accent roles that keep contrast per surface; copies and downscales images; inlines one-colour SVG logos as `currentColor`. `--list-directions`, `--covers`. | `html/index.html`, `html/build-report.json`, `html/assets/` |
| `deckspec.py` | Loader, stdlib JSON Schema subset validator, spec lint (used by build.py). | n/a |
| `blocks.py` | Markup of every block type (title, body, list, stat, chart, photo, screenshot, quote, logo-row, visual, cta), French and English typography. | n/a |
| `charts.py` | Bar, line and donut charts as SVG: one accent on the highlight, greys elsewhere, direct labels, linear scale, zero baseline. | n/a |
| `fit.js` | Runs in the page after fonts and images load: largest size between each text's min and max that holds in its line budget without overflow; failures reported, never shrunk past the minimum. | `window.__fit` |
| `render.py` | Chromium via Playwright: PDF first (vector, one page per slide), then an exact-size PNG per slide and a 1080 px sRGB JPEG (quality 88). | `export/slide-NN.png`, `.jpg`, `carousel.pdf`, `render.json` |
| `qa.py` | DOM measures per slide: fit failures, overflow, outside slide, safe zone, text size at feed scale, WCAG contrast per text node against what is really under it, empty blocks, missing or low-res images, collisions, dead space, the visual tells of a generated deck; fonts loaded; output files; contact sheet at 25 % through the shared script. | `export/qa.json`, `export/contact-sheet.jpg` |
| `captions.py` | `captions.md`: LinkedIn post, first comment, Instagram caption, alt text per slide (composed from the blocks when `slide.alt` is absent), sources; checks platform limits. | `captions.md` |
| `animate.py` | The video variant: the built HTML, fitted by fit.js, staged on a 4:5, 9:16 or 1:1 canvas by `animate.js`; each paused Web Animation is set frame by frame, Chromium takes a PNG per frame (still frames are reused), ffmpeg encodes H.264 yuv420p 30 fps with faststart; optional `--music` with a fade out. Reading time per slide from its word count, `--max-duration` cap. QA with ffprobe and Pillow (codec, size, fps, frame count, duration, moov before mdat, audio, LinkedIn limits, black or flat first and last frame); `--check FILE.mp4` runs the QA alone. | `export/video-<aspect>.mp4`, `.json`, `-frames.jpg` |
| `animate.js` | Runs in the page after fit.js: canvas staging (scale into the safe box, the slide's ground around it), entrance plan per block type, count-up, reading-time timeline, `window.__animSeek(t)`. | `window.__animSetup`, `window.__animSeek` |
| `preview.py` | Regenerates `directions/<id>/preview.jpg` from the reference deck. | `directions/<id>/preview.jpg` |
| `generate_image.py` | Capability `image_gen`, last resort: `--provider fal`, `openai` or `manual` (writes the prompt for the founder's own tool). `fal` and `openai` need `--confirm-spend` (or `FOG_ALLOW_SPEND=1`), passed only after the founder agreed to the price; without it nothing is sent and the script exits 6 with the estimate. | one image or one prompt file |

## Reference runs

```bash
# The swanbase example, end to end (about 30 s)
python3 scripts/pipeline.py examples/swanbase-seed-deck-20261010/deck.json

# The cover board of the six directions on the same cover
python3 scripts/pipeline.py examples/swanbase-seed-deck-20261010/deck.json --covers --directions all --first-layout

# The stress deck: must exit 1 with explicit errors in examples/stress/export/qa.json, never crash
python3 scripts/pipeline.py examples/stress/deck.json --out /tmp/carousel-stress

# The video variant of the reference deck, 4:5 and 9:16 (about 2 to 3 min each on one CPU)
python3 scripts/animate.py examples/swanbase-seed-deck-20261010/deck.json --out /tmp/carousel-video
python3 scripts/animate.py examples/swanbase-seed-deck-20261010/deck.json --out /tmp/carousel-video --aspect 9:16

# QA of an existing MP4 only
python3 scripts/animate.py --check /tmp/carousel-video/export/video-9x16.mp4 --aspect 9:16
```

## Tests

```bash
# Full regression: video smoke test, stress deck, reference deck (needs ffmpeg for the video part)
python3 scripts/selftest.py

# Video only: the first three slides of the reference deck as a 9:16 MP4 (under a minute on one CPU),
# plus the stress deck refused before rendering
python3 scripts/selftest.py --only video
```

The video part renders at 15 fps to stay fast (production videos use 30 fps) and checks exit 0, QA pass, 1080x1920 at 15 fps, the frame count of the timeline, a non-black first frame, the frames sheet, and that still frames were reused. Every run also checks, offline, that `generate_image.py` refuses a paid call without `--confirm-spend`. Rendering is deterministic: two runs of the same deck give the same MP4, byte for byte.

## Exit codes

`build.py`: 0 clean spec, 1 spec errors (HTML still written), 2 unreadable deck. `animate.py`: 0 video written and QA pass, 1 deck not validated (spec errors or fit failures, nothing rendered unless `--force`) or video QA errors, 2 fatal (unreadable deck, ffmpeg, ffprobe or Playwright missing, music file missing). `qa.py` and `pipeline.py`: 0 pass, 1 errors. `captions.py`: 0 within limits, 1 missing caption or over a limit. `generate_image.py`: 0 image written, 2 key missing, 3 provider error, 4 download or write error, 5 manual prompt written, 6 spend gate closed (no `--confirm-spend`, nothing sent).
