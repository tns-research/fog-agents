---
name: extract-brand
description: Extract brand tokens (colors, fonts, logo) AND harvest the site's real assets (logo incl. inline SVG, og:image, favicon, largest product/hero images) from a public URL using firecrawl (DOM/CSS signal) plus a headless screenshot (visual signal). The accent is read from the primary CTA button (solid bg or the vivid stop of a gradient), not a whole-page palette. Combines signals with heuristics and confidence scores, downloads assets to disk, writes a brand-candidate.json, renders a self-contained brand preview card with an asset contact strip, and runs a validation loop with the user until they approve. The validated brand.json becomes the single shared brand source (tokens + assets) every other agent in the stack reads to build creatives. Use when configuring a project's brand from its URL. Triggers: "extract brand", "use my brand from <url>", "set up my colors/logo", "grab my assets".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# Skill: extract-brand

Turn a URL like `https://swanbase.co` into a `brand.json` that drives every future render across the stack (static ads, carousels, ...). Two signal sources, one validation loop.

This skill is the **single owner** of brand extraction in the founders OS. Consumer agents read the resulting `brand.json`; they do not re-extract.

The extraction is **heuristic, not authoritative**. Every token is emitted with a `confidence` score, the user reviews on a preview card, edits in chat or directly in the JSON, and only then does the file become canonical.

---

## When to load

- The `project-context` agent's Workflow Step 2 runs and a `url` is present.
- The user types something like *"use my brand from swanbase.co"* / *"extract brand from URL"*.
- A prior `brand.json` is missing or the user explicitly asks to redo extraction.

If no `url` is provided AND no prior `brand.json` exists, **skip this skill**. The agent asks 2-3 inline brand questions (primary color, accent, logo path) instead, or omits brand entirely.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `brand_url` | `config.json` or chat | yes |
| `output_dir` | `<project-root>/<project-slug>/project-context/` | yes |
| `language` | `config.json` (preview-card copy language) | no, default `en` |

Environment:

| Var | Required | Used by |
|-----|----------|---------|
| `FIRECRAWL_API_KEY` | recommended | DOM/CSS scrape |
| (Playwright installed via `scripts/requirements.txt`) | yes | screenshot + preview card |

If `FIRECRAWL_API_KEY` is missing, the skill degrades to **screenshot-only extraction** and warns the user that confidence will be lower.

---

## Outputs

```
<project-root>/<project-slug>/project-context/
  ├── brand-candidate.json   # ← first pass with confidence scores + asset manifest
  ├── brand-debug/
  │   ├── homepage.png        # full-page screenshot used for color analysis
  │   ├── header-crop.png     # top 200px crop (primary candidate region)
  │   ├── viewport.png        # above-the-fold shot, promoted to assets/site/screenshot.png
  │   ├── firecrawl.json      # raw firecrawl response (DOM + computed styles)
  │   └── brand-preview.png   # the validation preview card
  ├── assets/                 # ← real assets harvested on the FIRST pass (see below)
  │   ├── logo.svg|png         # logo, incl. inline-SVG logos serialized to a file
  │   └── site/
  │       ├── favicon.png      # site favicon / apple-touch-icon
  │       ├── og-image.jpg     # the og:image share card (great hero source)
  │       ├── screenshot.png   # above-the-fold UI shot (the "product" for SaaS briefs)
  │       ├── asset-01.jpg ... # largest on-page product/hero images, ranked by area
  │       └── manifest.json    # path/source/dims/alt for every harvested file
  └── brand.json              # ← only written AFTER user approval
```

**Asset harvesting is not deferred to approval.** The logo, og:image, favicon, and
the largest on-page product/hero images are downloaded during Step 1 so the user
can see them on the preview card and so the creative agents have real source
material to build from. Only the *promotion* of `brand-candidate.json` →
`brand.json` waits for approval; the bytes on disk are fetched up front. This is
the point of the agent: it exists to **grab the site's real assets for creatives**,
not just to name a few hex colors.

`brand-candidate.json` schema:

```json
{
  "source_url": "https://swanbase.co",
  "extracted_at": "2026-06-04T16:00:00Z",
  "tokens": {
    "bg":              { "value": "#030619", "confidence": 0.92, "source": "screenshot:dominant" },
    "text_primary":    { "value": "#ffffff", "confidence": 0.88, "source": "css:body.color" },
    "accent":          { "value": "#f5a623", "confidence": 0.71, "source": "screenshot:cta-detection" },
    "accent_secondary":{ "value": "#7c3aed", "confidence": 0.45, "source": "fallback:accent-darker" },
    "font_heading":    { "value": "'Instrument Serif', Georgia, serif", "confidence": 0.80, "source": "css:h1.font-family" },
    "font_body":       { "value": "'Inter', sans-serif", "confidence": 0.92, "source": "css:body.font-family" },
    "logo_url":        { "value": "https://swanbase.co/logo.svg", "confidence": 0.85, "source": "dom:img-or-svg-near-top" }
  },
  "assets": {
    "logo":     { "path": "assets/logo.svg", "kind": "img", "source": "https://swanbase.co/assets/brand/swanbase_logo_icn.svg", "w": null, "h": null },
    "favicon":  { "path": "assets/site/favicon.png", "source": "https://swanbase.co/icon_light.png", "w": null, "h": null },
    "og_image": { "path": "assets/site/og-image.jpg", "source": "https://media.swanbase.co/...og.jpg", "w": 1200, "h": 630 },
    "screenshot": { "path": "assets/site/screenshot.png", "source": "playwright:viewport", "w": 1440, "h": 900 },
    "images": [
      { "path": "assets/site/asset-01.jpg", "source": "https://media.swanbase.co/...swan.jpg", "w": 599, "h": 597, "alt": "Curious Swan" }
    ]
  },
  "warnings": [
    "Body font 'Inter' loaded from Google Fonts. Render machine needs internet to load it."
  ]
}
```

Every `path` is relative to the `project-context/` dir, so any consumer resolves
`<project-root>/<project-slug>/project-context/<path>`. `assets/site/manifest.json`
holds the same `assets` block on its own, for agents that only want the images.

`brand.json` (post-approval) drops `confidence`/`source`, adds a local `logo_path` if the user kept a logo:

```json
{
  "bg": "#030619",
  "text_primary": "#ffffff",
  "accent": "#a855f7",
  "accent_secondary": "#4a276e",
  "font_heading": "'Instrument Serif', Georgia, serif",
  "font_body": "'Inter', sans-serif",
  "logo_path": "project-context/assets/logo.svg",
  "assets": {
    "logo_path": "project-context/assets/logo.svg",
    "og_image_path": "project-context/assets/site/og-image.jpg",
    "favicon_path": "project-context/assets/site/favicon.png",
    "screenshot_path": "project-context/assets/site/screenshot.png",
    "images": [
      "project-context/assets/site/asset-01.jpg",
      "project-context/assets/site/asset-04.png"
    ]
  }
}
```

`logo_path` and every entry in `assets` are written relative to the **project
root** (not the project-context dir) so any consumer agent resolves them the same
way. The creative agents (`static-ads-builder`, `carousel-builder`) read
`assets.images` for real product/hero source material, `assets.screenshot_path` for
the product UI shot (the "product" for a SaaS with no physical packshot), and
`assets.logo_path` for the lockup; they never re-scrape the site.

---

## Procedure

### Step 1, fetch DOM + screenshot

Run `scripts/extract_brand.py`:

```bash
python agents/project-context/scripts/extract_brand.py \
  --url "$BRAND_URL" \
  --out "$OUTPUT_DIR" \
  [--no-firecrawl]   # if FIRECRAWL_API_KEY missing
```

The script:
1. Checks `/robots.txt`; aborts if the homepage is `Disallow: /`.
2. Fires `firecrawl scrape` (`formats=["html","links"]`) or skips if key missing.
3. Launches Playwright headless Chrome at 1440x900, waits for `networkidle` + `document.fonts.ready`, then full-page + header-crop screenshots.
4. Probes the live DOM: computed body/h1 fonts, `theme-color`, og:image, icons, the
   logo (img `src` **or** inline-SVG `outerHTML` serialized to a file), every styled
   CTA/button (solid bg **and** CSS-gradient stops, with area + vertical position),
   and a raster-image inventory ranked by rendered area.
5. Derives the accent from the **primary CTA's color** (solid bg, else the most
   *vivid* gradient stop), not from the whole-page palette where a small button
   drowns under whitespace.
6. **Harvests real assets to disk**: downloads the logo, og:image, favicon, and the
   largest on-page product/hero images into `assets/` + `assets/site/`, writes a
   `manifest.json`, and caps each file at 12 MB.
7. Writes `brand-candidate.json` (tokens + confidence + `assets` block) + `brand-debug/`.

### Step 2, render the preview card

Render a **self-contained** brand preview (no dependency on any other agent):

```bash
python agents/project-context/scripts/render_brand_preview.py \
  --brand "$OUTPUT_DIR/brand-candidate.json" \
  --out "$OUTPUT_DIR/brand-debug/brand-preview.png" \
  [--logo "$OUTPUT_DIR/assets/logo.svg"]
```

It composes a single card showing: the four color swatches with hex labels, the
heading/body font names, the logo if available, **and a contact strip of the
harvested assets** (og:image + the largest product/hero images) so the user can
confirm at a glance that the agent grabbed their real material. Asset paths are
read from the `assets` block in the brand JSON and resolved relative to it. This is
what the user judges, not a real deliverable.

### Step 3, present + validate (chat loop)

Surface to the user:
- The rendered `brand-preview.png` (use the harness's image preview if available, else the file path).
- A compact table of extracted tokens + confidence.
- Any warnings from `brand-candidate.json`.

Ask the user one of:
1. **Approve as-is** -> finalize (Step 4).
2. **Edit a single token in chat** ("change accent to #ff6900") -> patch JSON, re-render preview, re-validate.
3. **Open and edit the JSON directly** ("I'll edit it myself") -> wait for confirm, re-render, re-validate.
4. **Logo is wrong** -> ask for a path or URL, download/copy to `assets/logo.png`, re-render.
5. **Restart from a different URL** -> back to Step 1.

**No iteration cap.** Loop until the user types `approve` / `looks good` / `validate`.

### Step 4, finalize

1. The logo, og:image, favicon, and product/hero images are already on disk under
   `assets/` from Step 1. If the user replaced the logo during validation, swap that
   one file. If no usable logo exists, omit `logo_path`.
2. Strip `confidence` and `source` from the tokens, set `logo_path`
   (project-root-relative), and carry the harvested `assets` forward as
   project-root-relative paths (`assets.logo_path`, `assets.og_image_path`,
   `assets.favicon_path`, `assets.screenshot_path`, `assets.images[]`). Write the
   final `brand.json`.
3. Keep `brand-debug/` and `assets/site/` for traceability and as creative source
   material (small, useful on re-runs).

---

## Hard rules (do not violate)

- **Never auto-approve.** The user must explicitly validate before `brand.json` is written.
- **Logo is always a file.** The site's own inline-SVG logo IS serialized to a file (that is real brand material). What is forbidden is the agent *inventing* a logo. If extraction failed and the user has no logo, omit it.
- **Harvest real assets, never synthesize them.** Product/hero images come from the site, downloaded as-is. The agent does not generate stand-in imagery here.
- **Respect download limits.** Each asset is capped (12 MB) and the harvest count is bounded (`--max-images`, default 8). Skip anything that is not an image.
- **Heuristics must publish their confidence.** A token shipped at 0.0 confidence is a bug.
- **No paid SaaS.** firecrawl is the only external API and it has a free tier.
- **Respect robots.txt + ToS.** The script reads `/robots.txt` first; if `Disallow: /` matches the homepage, it aborts with a clear message.
- **No cross-agent dependency.** The preview is rendered by this agent's own script; never reach into another agent's render skill.

---

## Failure modes + fallbacks

| Failure | Fallback |
|---------|----------|
| `FIRECRAWL_API_KEY` missing | Screenshot-only mode. DOM-source tokens drop to lower confidence, filled from screenshot heuristics, with a warning. |
| Site blocks Playwright (Cloudflare 403) | Script retries once with a normal user agent + `--ignore-https-errors`, then surfaces the error and asks for a logo/colors manually. |
| SPA shell with no rendered text | Script waits for `networkidle` + 2s grace; if still empty, aborts with "site rendered no visible text, share a different URL or skip extraction". |
| All heuristics low confidence (<0.5 across all tokens) | Print "low confidence run, recommend manual entry", do NOT render a preview, ask the user how to proceed. |
| Webfont from Google Fonts | Add a `warnings[]` entry. Render works locally but a render machine needs internet. |
| Pillow not installed | `render_brand_preview.py` falls back to printing the token table only; the user validates from `brand-debug/homepage.png` + the table. |
| No on-page image large enough to harvest | `images[]` is empty; add a `warnings[]` entry. The creative agents fall back to the og:image, logo, and homepage screenshot. |
| Logo is inline SVG | Serialize the `outerHTML` to `assets/logo.svg`; record `kind: "img"`. Raster-only consumers fall back to the favicon or a rasterized og:image. |
| Asset host blocks hotlinking (403) | Skip that file, keep the rest, note it in `warnings[]`. Never fail the whole run for one asset. |

---

## Why this design

- **Two signals are stronger than one.** DOM gives ground truth for fonts and logo URLs. Screenshot gives ground truth for *what the user actually sees* (covers CSS-in-JS, inline styles, Tailwind classes).
- **Accent comes from the CTA, not the palette.** The brand accent is whatever color the site puts on its primary button. Reading the CTA background (solid or the vivid stop of a gradient) beats a whole-page palette where a small button drowns under whitespace. This is what fixed swanbase (vivid purple, not a decorative maroon) and other SaaS sites where the true accent was the CTA color, not a leftover theme-color in the markup.
- **Grab the real assets, do not redraw them.** Founders want creatives built from *their* logo and *their* product shots, not lookalikes. Harvesting the logo, og:image, and largest on-page images up front is the whole point of this agent; the colors are necessary but not sufficient.
- **Confidence + validation loop > single-shot extraction.** Brand pages vary wildly. The failure mode is "wrong color shipped to an ad", which is expensive. Bias toward asking.
- **Extract once, read everywhere.** Once `brand.json` exists in `project-context/`, every other agent reuses its tokens *and* its harvested assets. Edits are one file change away.
