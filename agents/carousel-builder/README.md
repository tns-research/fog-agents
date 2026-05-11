# carousel-builder

Build a ready-to-post social carousel (LinkedIn PDF + Instagram PNG sequence) from a topic typed in chat. HTML/CSS rendered to native PDF by `slides2pdf` (Playwright fallback). Optional brand extraction from any URL. Optional AI image generation via fal. No paid SaaS, no Canva account required, runs from any AI coding harness (Claude Code, Cursor, Codex CLI, Gemini CLI).

## What it does

1. You type a topic or short outline in chat.
2. The agent proposes 3 to 5 angles. You pick one.
3. The agent writes a slide-by-slide markdown plan. You approve or edit.
4. (Optional) The agent extracts your brand from a URL, shows a test slide, iterates with you until validated.
5. The agent renders HTML slides at 1:1 (1080x1080) or 4:5 (1080x1350).
6. You get PDF (LinkedIn document post), PNG sequence (Instagram), and optional raw HTML.

10 minutes, 8 slides, posted.

## Status

V1, shipped. Phase 6 (Canva Connect, X threads, more styles) is the next iteration but not required for end-to-end use today.

| Phase | Status | What ships |
|-------|--------|------------|
| Phase 1 | ✅ | scaffold + `AGENT_CAROUSEL_BUILDER.md` + skills `propose-angles`, `plan-carousel` |
| Phase 2 | ✅ this commit | rendering core: `render-carousel` + 7 templates + `_base.html`, `export-slides` skill, `default-style.css`, scripts `install_slides2pdf.sh` / `render_playwright.py` / `pack_pdf.py` + `requirements.txt` |
| Phase 3 | ✅ | skill `extract-brand` + `scripts/extract_brand.py` (firecrawl DOM + Playwright screenshot + Pillow palette heuristics, confidence-scored, validation loop) + `assets/test-slide.json` |
| Phase 4 | ✅ | skill `handle-assets` + `scripts/svg_helpers.py` (15 helpers) + `scripts/generate_image.py` (fal HTTP, single opt-in via `FAL_API_KEY`, models nano-banana-pro / gpt-image-2) + `scripts/copy_user_images.py` (1500px JPEG opt) + `references/svg-patterns.md` |
| Phase 5 | ✅ | `examples/swanbase-explainer-20260509/` (full 8-slide gallery, brand snapshot, engine notes) + `examples/svg-creative-gallery.md` (17 patterns) + integration into top-level `README.md` and `AGENTS.md` |
| Phase 6 | later | optional Canva Connect REST integration, X thread output, more shipped styles |

End-to-end pipeline (topic → PDF + PNG) runs today with optional brand extraction from any URL. The default neutral style is used when no brand is provided.

## Prerequisites

```bash
# Primary engine (recommended): slides2pdf — native multipage PDF, auto-downloads chrome-headless-shell
bash agents/carousel-builder/scripts/install_slides2pdf.sh
# Tries prebuilt binary, then go build, then prints fallback instructions.

# Fallback engine: Playwright + img2pdf — only used when slides2pdf can't install
cd agents/carousel-builder/scripts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Brand extraction (optional, used when brand_url is set)
# extract_brand.py calls the Firecrawl API directly (no extra CLI needed)
export FIRECRAWL_API_KEY="..."   # without this key, runs in screenshot-only mode

# Optional: AI image generation. Single opt-in: this env var is the only gate.
# Default model fal-ai/nano-banana-pro at $0.15/image, hard cap 3 per run = $0.45 max.
# Without the key, the agent silently uses user images / SVG / text-only — no errors, no degraded slides.
export FAL_API_KEY="..."   # FAL_KEY also accepted
```

Disk footprint: `slides2pdf` + chrome-headless-shell ≈ 150 MB. Playwright chromium ≈ 450 MB (only needed if slides2pdf unavailable). Both produce the same `carousel.pdf` and `slide-NN.png` filenames, so downstream is unaffected.

## Usage

From your AI coding harness (Claude Code, Cursor, Codex CLI, Gemini CLI), open the repo and prompt:

```
Run carousel-builder for project acme on the topic
"why your first 50 users matter more than product-market fit"
```

The agent will:
1. Resolve project context (creates `<your-projects-root>/acme/carousel-builder/config.json` if missing).
2. Propose 3-5 angles. You pick one.
3. Write the slide plan. You approve or edit.
4. Ask if you want brand extraction (only if `brand_url` not yet set).
5. Render and export.

## Per-project config

Outputs live outside the agent folder, in your project root:

```
<your-projects-root>/<project>/carousel-builder/
  ├── config.json                   # platforms, ratio, slide_count, language, tone, outputs, fal toggle
  ├── brand.json                    # extracted brand cache (validated, optional)
  ├── brand-debug/                  # screenshot, header crop, firecrawl response (kept for traceability)
  ├── style.css                     # OPTIONAL power-user override, replaces default-style.css
  └── <label>-<YYYYMMDD>/
      ├── carousel-summary-<YYYYMMDD>.md
      ├── slide-plan-<YYYYMMDD>.md
      ├── slide-plan-<YYYYMMDD>.json
      ├── index.html                # self-contained deck
      ├── carousel.pdf              # multipage native PDF
      ├── slide-01.png ... slide-NN.png
      └── images/                   # logo + per-slide images
```

`config.json` is created on first run from `agents/carousel-builder/config.example.json`. Edit it freely.

## Three layers of customization (most users only touch the first)

| Layer | File | When to edit |
|---|---|---|
| 1. Brand tokens | `brand.json` | The default 95% case. Colors, fonts, logo path. Auto-extracted by `extract-brand` (firecrawl + screenshot heuristics, confidence-scored), validated via a one-slide preview, then reused on every run. |
| 2. Per-project full CSS | `style.css` | When `brand.json` tokens aren't enough. Drop a complete CSS file; it replaces `assets/default-style.css` for that project only. Other projects unaffected. |
| 3. Default style | `agents/carousel-builder/assets/default-style.css` | Only when contributing back to the agent. Affects every project with no `brand.json` / `style.css`. |

## Brand extraction

Optional. If you provide a `brand_url`, the agent runs `scripts/extract_brand.py` (firecrawl + heuristic color/font detection), produces a candidate `brand.json`, and renders one preview slide. Iterate freely in chat ("change primary to navy", "use logo from /logo.svg", "edit JSON directly") until you approve. The validated `brand.json` is reused on every future run.

If you don't provide a `brand_url`, the agent uses `assets/default-style.css` (neutral baseline).

## Manual Canva handoff

Canva MCP / Connect is **not** integrated in V1. Reasoning: branded auto-fill is Canva Enterprise only (~$30/user/month), and `mcp__*` tools break the agent's portability across harnesses.

If you want to retouch in Canva: export the PDF, upload it manually to Canva ("Create design > Upload"). The carousel becomes editable. This is a one-click workflow, no integration needed.

## Output formats

You pick one or many at runtime via the `outputs` parameter:

| Output | Best for | Notes |
|--------|----------|-------|
| `pdf` | LinkedIn document post | Native multipage PDF. 1:1 (1080x1080) or 4:5 (1080x1350). |
| `png` | Instagram, Twitter image standalone | One PNG per slide. Same dimensions as PDF pages. |
| `html` | Preview, copy-paste, custom styling | Raw self-contained `index.html`, tweakable. |

Default: `pdf,png`.

## Robustness (what the agent does when something breaks)

- **`slides2pdf` install fails** → automatically falls back to Playwright + `img2pdf`. Same output filenames, run continues.
- **`carousel.pdf` < 50 KB** (suspect blank render) → re-runs `slides2pdf --pretty` for debug; if still tiny, switches the whole deck to Playwright.
- **A single slide PNG is missing** after `pdftoppm` extraction → regenerates just that slide via Playwright (`--slide N`) instead of failing the whole run.
- **Webfont not loaded** → `slides2pdf` waits for network idle natively; the Playwright path explicitly awaits `document.fonts.ready` before screenshots.
- **`pdftoppm` not installed** (no poppler-utils) → tries `apt-get install -y poppler-utils`; if blocked, falls through to Playwright PNG path.
- **The final report records which engine ran** so you can see at a glance whether the primary path or the fallback was used.

## Image strategy

The `handle-assets` skill picks one source per slide using a deterministic priority:

1. **User-provided image** (local path or URL): always wins if present and reachable. Optimized to 1500px JPEG. Hard cap: 5 per run.
2. **SVG helper** (15 shipped: bar chart, donut, compare, timeline, funnel, pyramid, progress steps, icon grid, callout arrow, checklist, comparison table, wave, number badge, quote mark, divider): brand-colored vector, instant, $0.
3. **Bespoke inline SVG** (the agent writes SVG directly when no helper fits): same brand-token rules, escape hatch for one-off layouts. Patterns documented in `references/svg-patterns.md`.
4. **fal AI** (opt-in via `FAL_API_KEY` env var only): generates a photo or illustration. Default `fal-ai/nano-banana-pro`, alt `openai/gpt-image-2`. Hard cap `fal_max_images: 3` per run = $0.45 max with defaults. Failure on a slide silently falls through to text-only, never breaks the run.
5. **None**: slide stays text-only.

## Limitations (V1)

- No URL ingestion as content source (URLs only as `brand_url`).
- No X / Twitter native carousel (X has no carousel format).
- No video reels or animated slides.
- One default style shipped (neutral). Brand customization happens via extraction or direct `brand.json` edit.
- Slide count capped at 15 (LinkedIn document post drop-off).

## Portability

Runs identically on:
- Claude Code (`/agents/carousel-builder/AGENT_CAROUSEL_BUILDER.md`)
- Cursor (open the spec, prompt: "Run this agent")
- Codex CLI
- Gemini CLI

No `mcp__*`, no `zo-*`, no vendor-specific tooling. POSIX paths, forward slashes only, shell + cli-skills CLIs.

## License

Apache-2.0.
