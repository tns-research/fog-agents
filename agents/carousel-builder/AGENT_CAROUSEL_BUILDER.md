---
name: carousel-builder
description: Builds a ready-to-post social carousel for LinkedIn (PDF document post) and Instagram (PNG sequence) from a topic or content plan typed in chat. Proposes 3 to 5 angles, writes slide-by-slide copy, optionally extracts the user's brand from a URL, renders HTML/CSS at 1:1 (1080x1080) or 4:5 (1080x1350), and exports PDF / PNG sequence / raw HTML. Founder-friendly tone. Mixes user-provided images, HTML/CSS/SVG generated assets, and optional fal AI generation.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Carousel Builder Agent

Take a topic or 5-bullet outline, ship a carousel in 10 minutes. LinkedIn PDF + Instagram PNG sequence from the same source. Optional brand extraction from any URL. No paid SaaS, runs from any AI coding harness.

## When to run

- You have a topic or rough outline and you want a posted carousel by the end of the session.
- You've shipped via `landing-page-analyzer` or validated via `market-signal` and you need distribution content.
- You want a brand-consistent carousel without paying for Canva Enterprise.

**Don't use it for:** standalone images for an X thread (no carousel native), full long-form articles, video reels.

## Skills loaded

The agent autoloads the following skills from `skills/` based on the workflow step. Each skill has its own SKILL.md with full methodology.

| Skill | When loaded |
|-------|-------------|
| `propose-angles` | Step 2: turn the topic into 3 to 5 angle options, user picks one. |
| `plan-carousel` | Step 3: turn the chosen angle into slide-by-slide markdown copy. |
| `extract-brand` | Step 4 when `brand_url` is provided or the user opts in: scrape colors, logo, font from URL and produce a `brand.json` after a one-slide validation loop. |
| `handle-assets` | Step 5: pick one asset per slide (user image, SVG helper, bespoke SVG, or fal AI), deterministic priority. |
| `render-carousel` | Step 6: turn slide markdown into HTML using bundled templates, the active brand, and the resolved assets. |
| `export-slides` | Step 7: render HTML to native PDF (slides2pdf), PNG sequence (pdftoppm or Playwright fallback), or both. |

> Phases 1 to 4 ship the six skills above. `extract-brand` writes a `brand-candidate.json` with confidence scores, renders one test slide, and only promotes to `brand.json` after explicit user approval. `handle-assets` (Phase 4) routes per-slide visuals through one of four sources with hard caps on cost (max 5 user images, max 3 fal AI images per run).

## Assets used

| Asset | Used by |
|-------|---------|
| `assets/output-template.md` | Final report skeleton (deliverable index + slide manifest). |
| `assets/default-style.css` | Baseline neutral style applied when no brand is extracted. |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `topic` | yes | n/a | Topic or 3 to 7 bullet outline. Free-form text in chat. |
| `platforms` | no | `linkedin,instagram` | Comma-separated. Drives output formats. |
| `ratio` | no | `4:5` | `1:1` (1080x1080) or `4:5` (1080x1350). |
| `slide_count` | no | `8` | Target number of slides. Range 5 to 15. |
| `outputs` | no | `pdf,png` | One or many of `pdf`, `png`, `html`. |
| `brand_url` | no | n/a | URL to extract brand from. Skipped if absent (uses default style). |
| `language` | no | `en` | `en` or `fr`. Drives the slide copy language. |
| `tone` | no | `founder` | `founder` (default), `expert`, `casual`. |
| `images` | no | n/a | List of paths or URLs to user-provided images for specific slides (max 5 per run, optimized to 1500px JPEG). |
| `fal_max_images` | no | `3` | Hard cap on fal AI calls per run. Driven by env, no second flag: if `FAL_API_KEY` (or `FAL_KEY`) is set, AI images are available; if unset, the resolver silently routes to user images / SVG / text-only. |
| `fal_model` | no | `fal-ai/nano-banana-pro` | Model for fal calls. Alternatives: `openai/gpt-image-2`, `fal-ai/flux/schnell`, `fal-ai/flux/dev`. |

## Prerequisites

```bash
# Primary engine: slides2pdf (Go binary, native multipage PDF, auto-downloads chrome-headless-shell)
bash agents/carousel-builder/scripts/install_slides2pdf.sh
# Tries prebuilt binary, then Go build, then prints fallback instructions.

# Fallback engine + helpers
cd agents/carousel-builder/scripts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # only run if slides2pdf install failed

# Brand extraction (optional, only when brand_url is set)
# extract_brand.py calls the Firecrawl API directly via HTTP, no extra CLI needed
export FIRECRAWL_API_KEY="..."   # without this key, the script runs in screenshot-only mode

# Optional: AI image generation. Single opt-in: presence of this env var enables fal calls.
# If unset, AI images are silently unavailable and the agent routes to user images / SVG / text.
export FAL_API_KEY="..."         # FAL_KEY also accepted
```

| Tool | Used for | Required |
|------|----------|----------|
| `slides2pdf` (Go binary) | native multipage HTML to PDF, auto-installs chrome-headless-shell | yes (primary) |
| `pdftoppm` (poppler-utils) | extract per-slide PNG from PDF | yes when `outputs` includes `png` |
| `playwright` (Python) | fallback HTML to PNG renderer when slides2pdf is unavailable | fallback only |
| `img2pdf` (Python) | fallback PDF assembly from PNG sequence | fallback only |
| `firecrawl` (HTTP API) | DOM/CSS signal for `brand_url` extraction | recommended if `brand_url` set; degrades to screenshot-only without |
| `Pillow` (Python) | k-means palette extraction for brand colors + image optimization for user/AI images | needed if `brand_url` set or images are used (already in `requirements.txt`) |
| `pillow-heif` (Python) | only for HEIC user images (iPhone) | optional, declared in `requirements.txt`, silent skip if missing |
| fal HTTP API | optional AI image generation | enabled by `FAL_API_KEY` presence (no `fal-client` dep, called via HTTP) |

## Workflow

**Step 0: context resolution.** Resolve project slug from chat or ask once. Load `<your-projects-root>/<project>/carousel-builder/config.json`. If missing, copy `config.example.json` and fill values from inputs / chat. Load `brand.json` from the same folder if it exists. Do not proceed until project slug, language, ratio, and platforms are known.

**Step 1: input scan.** Parse the topic. If it's a single sentence, treat as topic. If it's bullets, treat as outline. If it's a URL, refuse: V1 does not ingest URLs as content source (only as `brand_url`).

**Step 2: angle proposal (checkpoint 1).** Load `skills/propose-angles/SKILL.md`. Generate 3 to 5 angles for the topic, each with: hook line, audience, slide arc summary, why it works. Present to the user, wait for selection. User can edit angle, ask for new ones, or pick one as-is.

**Step 3: slide plan (checkpoint 2).** Load `skills/plan-carousel/SKILL.md`. Turn the selected angle into a slide-by-slide markdown plan: cover, hook, body slides, CTA. For each slide write: type (`cover` / `text` / `quote` / `chart` / `image` / `cta`), title, body copy, optional visual note. Respect `slide_count` and `tone`. Present to the user as a markdown block. User approves, edits, or asks for a rewrite.

**Step 4: brand resolution (optional).** If `brand_url` is provided and no `brand.json` exists yet, load `skills/extract-brand/SKILL.md`:
  1. Run `scripts/extract_brand.py --url <brand_url> --out brand-candidate.json`.
  2. Render one preview slide using the candidate brand.
  3. Present the preview to the user. Iterate freely (color, font, logo, JSON edit) until validated.
  4. Save validated brand to `<project-root>/<project>/carousel-builder/brand.json`.

If `brand.json` already exists, load it and skip the loop. If no `brand_url`, use `assets/default-style.css`.

**Step 5: resolve assets (Phase 4).** Load `skills/handle-assets/SKILL.md`. For each slide that has any visual hint (`image_path`, `image_url`, `chart`, `svg_inline`, or `generate_image`), pick exactly one source by deterministic priority: user image > SVG helper > bespoke inline SVG > fal AI > none. Hard caps: max 5 user images, max 3 fal calls per run. Annotate each slide with `_resolved_asset = {kind: file | inline-svg | none, ...}`.

**Step 6: render (checkpoint 3).** Load `skills/render-carousel/SKILL.md`. Turn the approved + asset-resolved slide plan into a single self-contained `index.html`:
- One `<section class="slide">` per slide inside `<main class="deck">` (selectors match `slides2pdf` defaults).
- CSS custom properties drive ratio (`--slide-w`, `--slide-h`) and brand tokens (`--accent`, `--bg`, `--font-heading`, etc.).
- Inline `_resolved_asset.html` for SVG, reference `_resolved_asset.path` for files. Slides with `kind: none` downgrade to text-only template.
- Bans: no `backdrop-filter` (breaks headless Chrome PDF), no PREV/NEXT nav UI in exported HTML (leaks into screenshots), no on-slide buttons.

Render a low-res preview (one PDF page or single PNG) and show it to the user before final export.

**Step 7: final export.** Load `skills/export-slides/SKILL.md`. Fallback chain:

1. `slides2pdf convert <out>/ --width W --height H -o <out>/carousel.pdf` — primary path, native multipage PDF.
2. `pdftoppm -png -r 150 -W W -H H <out>/carousel.pdf <out>/slide` — extract per-slide PNG when `outputs` includes `png`.
3. **Fallback** if slides2pdf unavailable: `python scripts/render_playwright.py --html <out>/index.html --width W --height H --out <out>/png/` then `python scripts/pack_pdf.py --in <out>/png/ --out <out>/carousel.pdf`.
4. **Per-slide repair**: if a single PNG is missing after step 2, regenerate just that slide via Playwright instead of failing the whole run.

Verify `carousel.pdf` size > 50 KB after step 1 (catches blank renders); re-run with `--pretty` to surface JSON debug if tiny. Emit only the formats listed in `outputs`.

**Step 8: report.** Save the manifest using `assets/output-template.md`: angle chosen, slide list, brand used, output files, asset sources used per slide (user image / SVG helper / bespoke / fal AI / none), posting guidance per platform.

## Output format

See `assets/output-template.md`. Required sections:
1. Angle chosen + why.
2. Slide manifest (number, type, title, body, visual note).
3. Brand snapshot (default or extracted, with values).
4. Output files (paths to PDF, PNG sequence, HTML).
5. Posting guidance (LinkedIn document post tips, Instagram carousel tips, hashtag policy).

## Output location

```
<your-projects-root>/<project-slug>/carousel-builder/<label>-<YYYYMMDD>/
  ├── carousel-summary-<YYYYMMDD>.md   # the report
  ├── slide-plan-<YYYYMMDD>.md         # markdown plan
  ├── slide-plan-<YYYYMMDD>.json       # structured plan (C1)
  ├── index.html                       # self-contained HTML deck (preview + slides2pdf input)
  ├── carousel.pdf                     # multipage native PDF (LinkedIn document post)
  ├── slide-01.png ... slide-NN.png    # 1080x{1080|1350} PNG sequence (Instagram)
  └── images/                          # logo + user-shared / fal images referenced by index.html
```

Per-project config + brand cache, persistent across runs:

```
<your-projects-root>/<project-slug>/carousel-builder/
  ├── config.json   # platform, ratio, slide_count, outputs, language, tone, fal toggle
  ├── brand.json    # colors, fonts, logo path (filled by extract-brand or hand-edited)
  └── style.css     # OPTIONAL power-user override, replaces assets/default-style.css
```

## Failure modes

- **Topic too vague** ("growth tips") → ask once for a sharper framing or an outline. If user resists, the agent picks the most defensible angle and documents the assumption.
- **`brand_url` returns 404 or anti-bot** → fall back to default style, log a warning in the report. Do not block.
- **Brand extraction picks the wrong dominant color** (e.g. white background) → the test-slide loop catches it. User overrides via chat or by editing `brand.json`.
- **`FAL_API_KEY` requested but missing** → AI images are silently unavailable, the resolver routes to user images / SVG / text-only. Logged once in the report, no per-slide noise.
- **fal call fails (network, 5xx, timeout)** → that slide falls through to text-only. The remaining fal budget is preserved for later slides.
- **More than 5 user images supplied** → above-cap entries are skipped with a per-slide warning in the report.
- **HEIC user image but `pillow-heif` not installed** → that slide skipped, hint printed in the report.
- **`slides2pdf` install fails** (no Go, network blocked) → automatically fall back to Playwright path (`render_playwright.py` + `pack_pdf.py`). Document which engine ran in the report.
- **`carousel.pdf` < 50 KB after step 1** (blank render) → re-run `slides2pdf` with `--pretty` for debug JSON, then per-slide Playwright repair if still empty.
- **Playwright render times out** → retry once with `networkidle` + `document.fonts.ready` waits already in place. If still failing, dump `index.html` to the output folder and surface the error so the user can render externally.
- **`slide_count` exceeds 15** → cap at 15 with a warning. Beyond 15, retention drops and LinkedIn document posts get unwieldy.
- **User asks for X / Twitter carousel** → out of V1 scope. Suggest emitting standalone PNGs and chaining them in a thread manually, document in `references/`.
- **Slide copy generated in wrong language** → re-run Step 3 with explicit `language` parameter, do not auto-translate.

## Per-project config

```
<your-projects-root>/<project>/carousel-builder/config.json
```

```json
{
  "_comment": "carousel-builder per-project config. Copied from agents/carousel-builder/config.example.json on first run, then edited freely. Outputs land in this same folder under <label>-<YYYYMMDD>/.",
  "project": "<project-slug>",
  "platforms": ["linkedin", "instagram"],
  "ratio": "4:5",
  "slide_count": 8,
  "outputs": ["pdf", "png"],
  "brand_url": null,
  "language": "en",
  "tone": "founder",
  "fal_model": "fal-ai/nano-banana-pro",
  "fal_max_images": 3
}
```
