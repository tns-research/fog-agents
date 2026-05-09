---
name: extract-brand
description: Extract brand tokens (colors, fonts, logo) from a public URL using firecrawl (DOM/CSS signal) plus a headless screenshot (visual signal). Combines the two with heuristics and confidence scores, writes a brand-candidate.json, renders one test slide, and runs a validation loop with the user until they approve. The validated brand.json is then reused by render-carousel on every future run.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# Skill: extract-brand

Turn a URL like `https://swanbase.co` into a `brand.json` that drives all future carousel renders. Two signal sources, one validation loop.

The extraction is **heuristic, not authoritative**. Every token is emitted with a `confidence` score, the user reviews on a real test slide, edits in chat or directly in the JSON, and only then does the file become canonical.

---

## When to load

- The agent's `Step 4` runs and `brand_url` is present in `config.json`.
- The user types something like *"use my brand from swanbase.co"* / *"extract brand from URL"*.
- A prior `brand.json` is missing or the user explicitly asks to redo extraction.

If `brand_url` is empty AND no prior `brand.json` exists, **skip this skill** and let `render-carousel` fall back to `assets/default-style.css`.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `brand_url` | `config.json` or chat | yes |
| `output_dir` | `<project-root>/<project>/carousel-builder/` | yes |
| `ratio` | `config.json` (passed to test-slide preview) | yes |
| `language` | `config.json` (test-slide copy language) | no, default `en` |

Environment:

| Var | Required | Used by |
|-----|----------|---------|
| `FIRECRAWL_API_KEY` | yes | DOM/CSS scrape |
| (Playwright already installed via Phase 2 fallback path) | yes | screenshot |

If `FIRECRAWL_API_KEY` is missing, the skill degrades to **screenshot-only extraction** and warns the user that confidence will be lower.

---

## Outputs

```
<project-root>/<project>/carousel-builder/
  ├── brand-candidate.json   # ← first pass with confidence scores, written here
  ├── brand-debug/
  │   ├── homepage.png        # full-page screenshot used for color analysis
  │   ├── header-crop.png     # top 200px crop (primary candidate region)
  │   ├── palette.png         # 8-swatch dominant-color extract
  │   └── firecrawl.json      # raw firecrawl response (DOM + computed styles)
  └── brand.json              # ← only written AFTER user approval
```

`brand-candidate.json` schema:

```json
{
  "source_url": "https://swanbase.co",
  "extracted_at": "2026-05-09T16:00:00Z",
  "tokens": {
    "bg":              { "value": "#0d0d10", "confidence": 0.92, "source": "screenshot:dominant" },
    "text_primary":    { "value": "#ffffff", "confidence": 0.88, "source": "css:--text-primary" },
    "accent":          { "value": "#5b8def", "confidence": 0.71, "source": "screenshot:cta-detection" },
    "accent_secondary":{ "value": "#2a4a99", "confidence": 0.45, "source": "fallback:accent-darker" },
    "font_heading":    { "value": "'Instrument Serif', Georgia, serif", "confidence": 0.80, "source": "css:font-family" },
    "font_body":       { "value": "'Inter', sans-serif", "confidence": 0.92, "source": "css:font-family" },
    "logo_url":        { "value": "https://swanbase.co/logo.svg", "confidence": 0.85, "source": "dom:img[alt*=logo]" }
  },
  "warnings": [
    "Body font 'Inter' loaded from Google Fonts. Confirm the carousel target has internet access at render time."
  ]
}
```

`brand.json` (post-approval) drops `confidence` and `source` and may add a local `logo_path` if the user downloaded the logo:

```json
{
  "bg": "#0d0d10",
  "text_primary": "#ffffff",
  "accent": "#5b8def",
  "accent_secondary": "#2a4a99",
  "font_heading": "'Instrument Serif', Georgia, serif",
  "font_body": "'Inter', sans-serif",
  "logo_path": "images/logo.svg"
}
```

---

## Procedure

### Step 1, fetch DOM + screenshot

Run `scripts/extract_brand.py`:

```bash
python agents/carousel-builder/scripts/extract_brand.py \
  --url "$BRAND_URL" \
  --out "$OUTPUT_DIR" \
  [--no-firecrawl]   # if FIRECRAWL_API_KEY missing
```

The script:
1. Fires `firecrawl scrape` with `formats=["html","screenshot@fullPage","links"]` (or skips if key missing).
2. Launches Playwright headless Chrome at 1440x900, `wait_for_load_state("networkidle")`, `document.fonts.ready`, then full-page screenshot.
3. Saves both to `brand-debug/`.

### Step 2, run heuristics

The same script then computes:

| Token | Heuristic | Confidence floor |
|-------|-----------|------------------|
| `bg` | k-means dominant color of the screenshot, filtering near-pure-white and near-pure-black if a slightly tinted color holds >40% of pixels | 0.70 if >50% pixel coverage |
| `text_primary` | DOM: `body { color }` computed style; falls back to maximum-contrast color vs `bg` from screenshot | 0.85 from DOM, 0.55 from screenshot |
| `accent` | screenshot: detect rectangular regions with high saturation and aspect ratio in [2, 6] (CTA buttons), pick most frequent fill | 0.65 |
| `accent_secondary` | DOM `--accent-2` / second most-frequent saturated color; else darken `accent` by 30% | 0.45 |
| `font_heading` | DOM: `h1, h2 { font-family }` first family that's not a generic fallback | 0.75 |
| `font_body` | DOM: `body { font-family }` first non-generic family | 0.85 |
| `logo_url` | DOM: first `<img>` matching `[alt*=logo i]` or `class*="logo"` or `header svg` whose bbox sits in top-left 25% of viewport | 0.70 |

Heuristic edge cases handled in code:
- Logo cannot be a transparent 1x1 pixel (skip).
- If `bg` confidence < 0.5, emit a warning and prompt the user to specify manually.
- If only one accent color is detected, `accent_secondary` is auto-derived (luminance shift).

### Step 3, render one test slide

Pull a hardcoded sample slide plan from `assets/test-slide.json` (a single quote-style slide), inject the candidate brand tokens, and call `render-carousel` + `export-slides` with `outputs=["png"]` only. Output: `<output_dir>/brand-debug/test-slide.png`.

### Step 4, present + validate (chat loop)

Surface to the user:
- The rendered `test-slide.png` (use the harness's image preview if available, else file path).
- A compact table of extracted tokens + confidence.
- Any warnings from `brand-candidate.json`.

Ask the user one of:
1. **Approve as-is** -> rename `brand-candidate.json` to `brand.json`, exit.
2. **Edit a single token in chat** ("change accent to #ff6900") -> patch JSON, re-render test slide, re-validate.
3. **Open and edit the JSON directly** ("I'll edit it myself") -> wait for user to confirm, re-render, re-validate.
4. **Logo is wrong** -> ask for a path or URL, copy/download to `images/logo.svg`, re-render.
5. **Restart from a different URL** -> back to Step 1.

**No iteration cap.** Loop until the user types `approve` / `looks good` / `validate`.

### Step 5, finalize

```bash
mv "$OUTPUT_DIR/brand-candidate.json" "$OUTPUT_DIR/brand.json"
```

Strip `confidence` and `source` fields. Keep the `brand-debug/` folder for traceability (small, useful when re-running).

---

## Hard rules (do not violate)

- **Never auto-approve.** The user must explicitly validate before `brand.json` is written.
- **Logo is always a file**, never inlined SVG generated by the agent. If extraction failed and the user has no logo, omit it.
- **Heuristics must publish their confidence.** A token that ships at 0.0 confidence is a bug.
- **No paid SaaS.** firecrawl is the only external API and it has a free tier.
- **Respect robots.txt + ToS.** The script reads `/robots.txt` first; if `Disallow: /` matches the homepage, abort with a clear message.

---

## Failure modes + fallbacks

| Failure | Fallback |
|---------|----------|
| `FIRECRAWL_API_KEY` missing | Screenshot-only mode. All `source: dom:*` tokens drop to 0 confidence and are filled from screenshot heuristics with a `--no-dom` warning. |
| Site blocks Playwright (Cloudflare 403) | Retry once with a normal user agent and `--ignore-https-errors`. Then surface the error and ask the user for a logo / colors manually. |
| Site returns SPA shell with no rendered text | The script waits for `networkidle` + 2s grace. If still empty, abort with "site rendered no visible text, please share a different URL or skip extraction". |
| All heuristics low confidence (<0.5 across all tokens) | Print a clear "low confidence run, recommend manual entry" message, do NOT render a test slide, and ask the user how to proceed. |
| Webfont loaded from Google Fonts | Add a `warnings[]` entry. Render still works locally but the carousel render machine needs internet. |

---

## Why this design

- **Two signals are stronger than one.** DOM gives ground truth for fonts and logo URLs. Screenshot gives ground truth for *what the user actually sees* (covers CSS-in-JS, inline styles, Tailwind classes).
- **Confidence + validation loop > single-shot extraction.** Brand pages vary wildly. Failure mode is "wrong color shipped to LinkedIn" which is bad. We bias toward asking.
- **Cache the result.** Once `brand.json` exists, every later run skips this whole skill. Edits are a single file change away.
