# scripts/

Bundled tools for the agent. Use this folder only when the work cannot be done by piping `cli-skills` CLIs (`exa`, `firecrawl`, `gsc`, `perplexity`, `instantly`).

Legitimate uses:

- Browser automation (Playwright capture, screenshot stitching)
- CSV / JSON transformations (reshape, dedupe, join)
- Custom scoring formulas applied at scale
- API quota juggling, batched fetch with retry

Not for: things `firecrawl` / `exa` / `gsc` / `perplexity` already do.

## Conventions

- **Python preferred** (matches the broader ecosystem we lift patterns from).
- Forward slashes only. No Windows-specific path handling.
- No magic numbers. Every constant documented inline.
- Handle errors explicitly (return defaults or specific error messages, never silently `pass`).
- Each script ships with `requirements.txt` (or equivalent) and an entry in this README.

## Script inventory

Install once: `pip install -r requirements.txt && python -m playwright install chromium`.

### `extract_brand.py`

- Inputs: `--url <homepage>` `--out <project-context dir>` `[--no-firecrawl]` `[--max-images N]` (default 8)
- Outputs: `brand-candidate.json` (tokens + confidence + `assets` manifest) + `brand-debug/` (homepage.png, header-crop.png, firecrawl.json) + `assets/logo.*` + `assets/site/` (favicon, og-image, asset-NN.*, manifest.json)
- What: two-signal brand extraction (firecrawl DOM/CSS + Playwright screenshot) AND real-asset harvesting. Accent comes from the primary CTA button background (solid, else the most *vivid* stop of a CSS gradient), not a whole-page palette. Downloads the logo (incl. inline SVG serialized to a file), og:image, favicon, and the largest on-page product/hero images (12 MB cap each). Heuristic tokens carry confidence scores. Respects robots.txt.
- Exit codes: `0` ok, `2` robots disallow, `3` Playwright failure.

### `render_brand_preview.py`

- Inputs: `--brand <brand-candidate.json|brand.json>` `--out <png>` `[--logo <img>]`
- Outputs: a single preview-card PNG (color swatches + hex + font names + logo + a contact strip of the harvested assets)
- What: self-contained validation card for the brand checkpoint. Reads the `assets` block from the brand JSON and thumbnails the harvested images so the founder can confirm the agent grabbed real material. Pillow only, no browser, no cross-agent dependency. SVG logos (which Pillow cannot rasterize) are skipped gracefully.
- Exit codes: `0` ok (or Pillow absent -> token table printed), `3` bad json, `4` render error.

### `enrich_context.py`

- Inputs: `--url <homepage>` `--out <project-context dir>` `[--provider auto|firecrawl|exa]`
- Outputs: `brand-debug/enrichment.json` + `brand-debug/enrichment-notes.md`
- What: optional pre-fill for the business Q&A. Pulls homepage + likely about/pricing/product pages. Drafts only, always confirmed by the founder.
- Exit codes: `0` ok, `2` no provider available (skip silently), `3` every fetch failed.

## Cross-platform notes

If a script needs to spawn subprocesses, use `subprocess.run([...])` with a list, not a shell string. Quote paths with spaces. Never assume `bash` is the user's shell.
