---
name: export-slides
description: Convert the assembled index.html into the final deliverables — multipage carousel.pdf (LinkedIn document post) and slide-NN.png sequence (Instagram). Primary path uses slides2pdf for native multipage PDF; pdftoppm extracts PNGs from that PDF. If slides2pdf is unavailable, falls back to Playwright + img2pdf and produces the same files. Verifies output non-empty, repairs single blank slides instead of failing the whole run.
---

# Skill: export-slides

Final step of the carousel pipeline. Takes the `index.html` that `render-carousel` wrote and produces `carousel.pdf` and `slide-NN.png` in the same directory.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `<output_dir>/index.html` | from `render-carousel` | yes |
| `ratio` | from `config.json`, drives `--width` / `--height` | yes |
| `outputs` | from `config.json`: any combination of `pdf`, `png`, `html` | yes |

Ratio mapping:

| `ratio` | width | height |
|---|---|---|
| `1:1` | 1080 | 1080 |
| `4:5` | 1080 | 1350 |

---

## Outputs

```
<output_dir>/
  ├── index.html       # already written by render-carousel
  ├── carousel.pdf     # multipage native PDF (when 'pdf' in outputs)
  ├── slide-01.png     # 1080x{1080|1350} PNG sequence (when 'png' in outputs)
  ├── slide-02.png
  └── ...
```

If `outputs == ["html"]` only, no PDF / PNG step runs.

---

## Pipeline

```
                  ┌────────────────────────────┐
                  │ index.html (one deck file) │
                  └────────────┬───────────────┘
                               │
         ┌─────────────────────┴─────────────────────┐
         │ Engine selection: slides2pdf available?   │
         └────────┬─────────────────────────┬────────┘
              yes │                         │ no
                  ▼                         ▼
   slides2pdf convert ...      python render_playwright.py
   carousel.pdf (native)       slide-01.png ... slide-NN.png
                  │                         │
                  ▼                         ▼
   pdftoppm -png ...           python pack_pdf.py
   slide-01.png ... NN          carousel.pdf (img2pdf)
                  │                         │
                  └─────────────┬───────────┘
                                ▼
                    Sanity-check + per-slide repair
```

Both branches end up with the same filenames, so downstream `report` step is unchanged.

---

## Step-by-step execution

### Step 1 — Engine detection

```bash
if command -v slides2pdf >/dev/null 2>&1; then
  ENGINE="slides2pdf"
else
  ENGINE="playwright"
fi
```

If `slides2pdf` is missing and the user has not installed it yet, attempt one-shot install:

```bash
bash agents/carousel-builder/scripts/install_slides2pdf.sh
```

If that exits non-zero, set `ENGINE="playwright"` and surface a one-line note in the final report (which engine ran, why).

### Step 2a — Primary path: slides2pdf

```bash
W=1080
H=1350   # or 1080 for 1:1
OUT="<output_dir>"

slides2pdf convert "$OUT/" --width "$W" --height "$H" -o "$OUT/carousel.pdf" --pretty
```

`--pretty` emits debug JSON. Capture it. If file size of `carousel.pdf` is `< 50 KB`:

1. Re-run once with `--pretty` to surface JSON debug.
2. If still small, fall through to Step 2b for the whole deck (do not blindly trust the PDF).

Then extract per-slide PNGs (only if `outputs` includes `png`):

```bash
pdftoppm -png -r 150 -W "$W" -H "$H" "$OUT/carousel.pdf" "$OUT/slide"

# normalize zero-padded names: pdftoppm writes slide-1.png, we want slide-01.png
cd "$OUT"
for f in slide-*.png; do
  num=$(echo "$f" | sed -E 's/slide-([0-9]+)\.png/\1/')
  padded=$(printf "%02d" "$num")
  if [ "$f" != "slide-${padded}.png" ]; then mv "$f" "slide-${padded}.png"; fi
done
```

### Step 2b — Fallback path: Playwright

When `slides2pdf` cannot run (no Go, network blocked, install failed, or step 2a produced a tiny PDF):

```bash
cd agents/carousel-builder/scripts
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -q -r requirements.txt
playwright install chromium

python scripts/render_playwright.py --html "$OUT/index.html" --width "$W" --height "$H" --out "$OUT"
python scripts/pack_pdf.py --in "$OUT" --out "$OUT/carousel.pdf"     # only if 'pdf' in outputs
```

### Step 3 — Sanity check + per-slide repair

After whichever branch ran:

```bash
expected="$(jq '.meta.total_slides' < <output_dir>/slide-plan.json)"
actual="$(ls -1 <output_dir>/slide-*.png 2>/dev/null | wc -l)"
```

- If `actual < expected`: identify missing slide indexes, regenerate just those:
  ```bash
  python scripts/render_playwright.py --html "$OUT/index.html" --width "$W" --height "$H" --out "$OUT" --slide N
  ```
  Then if PDF exists, re-pack only on the Playwright branch (slides2pdf PDF is left intact since the missing PNG was an extraction artifact, not a render artifact).

- If `carousel.pdf` is missing and `pdf in outputs`: surface the error to the user along with the path to `index.html`, suggest opening it in a browser as a workaround.

### Step 4 — Drop unwanted formats

If `outputs` does not include:

| Format dropped | Action |
|---|---|
| `pdf` | delete `carousel.pdf` |
| `png` | delete `slide-*.png` |
| `html` | leave `index.html`, since it's needed for the run; user can ignore |

---

## Selector compatibility

`slides2pdf` defaults match our HTML:

| `slides2pdf` flag | Default | Our HTML |
|---|---|---|
| `--deck-selector` | `.deck` | `<main class="deck" id="deck">` |
| `--slide-selector` | `.slide` | `<section class="slide">` |

No custom selectors needed.

---

## Error handling

| Situation | Action |
|---|---|
| Both `slides2pdf` and Go missing, Playwright succeeds | Report "engine: playwright (fallback)" in summary |
| Playwright not installed when fallback hits | Run `pip install -r scripts/requirements.txt && playwright install chromium`, retry once |
| `pdftoppm` not installed (poppler-utils) | `apt-get install -y poppler-utils 2>/dev/null` first; if that fails, fall through to Playwright path for PNGs only |
| Single slide PNG missing after extraction | Per-slide Playwright repair, do not fail whole run |
| `carousel.pdf` < 50 KB after slides2pdf | Re-run with `--pretty`; if still tiny, switch to Playwright for the whole deck |
| `font` not loaded in PDF | `slides2pdf` already waits for network idle; if still flaky, Playwright path explicitly awaits `document.fonts.ready` |
| User passes `outputs=["html"]` only | Skip steps 2/3 entirely |

---

## Why this design

1. **`slides2pdf` first** because native multipage PDF beats screenshot-stitched PDF (vector text, smaller file, sharper on retina). Battle-tested in `agent-social-slides`.
2. **`pdftoppm` second** because it's cheap and reuses the rendered PDF (no double-render).
3. **Playwright + `img2pdf` only as fallback** so the heavy ~450 MB chromium download is only paid by users without Go.
4. **Per-slide repair** keeps slow, expensive runs from being wasted by a single transient blank screenshot.

---

## Tools used

- `Bash` / `run_bash_command`: run `slides2pdf`, `pdftoppm`, install scripts, the Python fallback
- `Read` / `read_file`: spot-check `carousel.pdf` size, list PNGs
