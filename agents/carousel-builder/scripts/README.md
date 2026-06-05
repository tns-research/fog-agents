# scripts/

Bundled scripts for `carousel-builder`. All scripts are CLI-runnable for debugging without going through the agent.

| Script | Phase | Purpose |
|--------|-------|---------|
| `install_slides2pdf.sh` | 2 | Install the primary engine. Tries prebuilt binary, then `go build`, prints fallback instructions on failure. |
| `render_playwright.py` | 2 | Fallback HTML to PNG renderer. Used when `slides2pdf` is unavailable, or for per-slide repair. |
| `pack_pdf.py` | 2 | Fallback PDF assembly via `img2pdf`. Used after `render_playwright.py` when PDF output is requested. |
| `requirements.txt` | 2 | Python deps: `playwright`, `img2pdf`, `pdf2image`, `Pillow`, optional `pillow-heif` (HEIC user images). |
| `svg_helpers.py` | 4 | 15 brand-aware SVG generators (`bar_chart`, `donut`, `compare`, `quote_mark`, `divider`, `timeline`, `funnel`, `pyramid`, `progress_steps`, `icon_grid`, `callout_arrow`, `checklist`, `comparison_table`, `wave_decoration`, `number_badge`). Each takes `(data, brand, width, height)` and returns an `<svg>` string. CLI for standalone preview. |
| `generate_image.py` | 4 | fal HTTP API client. Single opt-in via `FAL_API_KEY` (or `FAL_KEY`). Models: `fal-ai/nano-banana-pro` (default), `openai/gpt-image-2`, `fal-ai/flux/schnell`, `fal-ai/flux/dev`. Pillow-optimizes to 1500px JPEG. Exit codes: 0 ok, 2 no key, 3 API error, 4 download error. |
| `copy_user_images.py` | 4 | Reads JSON specs (path or URL) from stdin or `--input`, copies/downloads to `<output_dir>/images/slide-NN.jpg`, optimizes to 1500px JPEG. Hard cap 5 per run. HEIC needs `pillow-heif`. |

## Running standalone

### Primary path (slides2pdf)

```bash
bash scripts/install_slides2pdf.sh                          # one-time
slides2pdf convert OUTPUT_DIR/ --width 1080 --height 1350 -o OUTPUT_DIR/carousel.pdf
pdftoppm -png -r 150 -W 1080 -H 1350 OUTPUT_DIR/carousel.pdf OUTPUT_DIR/slide
```

### Fallback path (Playwright)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
playwright install chromium
python scripts/render_playwright.py --html OUTPUT_DIR/index.html --width 1080 --height 1350 --out OUTPUT_DIR/
python scripts/pack_pdf.py --in OUTPUT_DIR/ --out OUTPUT_DIR/carousel.pdf
```

### Per-slide repair (when slides2pdf rendered most slides correctly but one is blank)

```bash
python scripts/render_playwright.py --html OUTPUT_DIR/index.html --width 1080 --height 1350 --out OUTPUT_DIR/ --slide 4
```

### Shared context

Brand and voice context live in `<your-projects-root>/<project>/project-context/`. This agent reads that folder through `resolve-project-context` and does not own brand extraction anymore.

### SVG helpers (Phase 4)

```bash
# preview a single helper as standalone SVG
python scripts/svg_helpers.py bar_chart \
    --data '{"items":[{"label":"A","value":40},{"label":"B","value":80}]}' \
    --brand '{"accent":"#5b8def","accent_secondary":"#2a4a99","text_primary":"#111"}' \
    --width 800 --height 400 > out.svg
```

### fal AI image (Phase 4)

```bash
export FAL_API_KEY="..."         # single opt-in. Without it, exit code 2 + non-fatal message.
python scripts/generate_image.py \
    --prompt "minimalist illustration of a founder at their first 50 users" \
    --out OUTPUT_DIR/images/slide-04.jpg \
    --ratio 4:5 \
    --brand-colors "#0b3d91,#f5a623" \
    --tone founder
# default model: fal-ai/nano-banana-pro. Override: --model openai/gpt-image-2

# dry-run (no API call): print resolved payload
python scripts/generate_image.py --prompt "..." --out /tmp/x.jpg --dry-run
```

### User images (Phase 4)

```bash
echo '[{"slide_index":4,"source":"/path/photo.heic","alt":"team meetup"}]' \
  | python scripts/copy_user_images.py --output-dir OUTPUT_DIR/
# writes OUTPUT_DIR/images/slide-04.jpg (1500px JPEG q=85), prints JSON report
```

## Hard rules

- POSIX paths only.
- No `mcp__*` / `zo-*` references.
- No paths absolute to a specific user (`/home/user/...`).
- All scripts ship with `--help`.
- Cross-platform: macOS, Linux, Windows (WSL or PowerShell).
