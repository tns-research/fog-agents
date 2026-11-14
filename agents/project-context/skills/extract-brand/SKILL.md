---
name: extract-brand
description: Extract brand tokens (colors, fonts, logo) AND harvest the site's real assets (logo incl. inline SVG, og:image, favicon, largest product/hero images) from a public URL using a local headless browser (live DOM + screenshot, no key needed). Color roles are measured on the render; the accent is read from the primary CTA button (solid bg or the vivid stop of a gradient), not a whole-page palette. Combines signals with heuristics and confidence scores, downloads assets to disk, audits the logo and builds its light and dark variants, writes a brand-candidate.json and a schema-validated brand-draft.json, renders a brand board with mechanical checks, and runs a validation loop with the user until they approve. The validated brand.json becomes the single shared brand source (tokens + assets) every other agent in the stack reads to build creatives. Use when configuring a project's brand from its URL. Triggers: "extract brand", "use my brand from <url>", "set up my colors/logo", "grab my assets".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# Skill: extract-brand

Turn a URL like `https://swanbase.co` into a `brand.json` that drives every future render across the stack (static ads, carousels, ...). Two signal sources (the live DOM and the rendered pixels), one validation loop.

This skill is the **single owner** of brand extraction in the founders OS. Consumer agents read the resulting `brand.json`; they do not re-extract.

The extraction is **heuristic, not authoritative**. Every token is emitted with a `confidence` score, the user reviews on the brand board, edits in chat or directly in the JSON, and only then does the file become canonical.

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
| (Playwright and Pillow installed via `scripts/requirements.txt`) | yes, for automatic extraction | screenshot + live DOM probe + logo pipeline + brand board (capability `screenshot`, local tier) |

No API key is read: the extraction is one local Chromium pass plus direct downloads of the page's own assets, stylesheets and fonts. Without Playwright, the `screenshot` capability falls to manual: ask the 2-3 inline brand questions (primary color, accent, logo file) instead. Providers: [`../../../../shared/tools.md`](../../../../shared/tools.md).

---

## Outputs

```
<project-root>/<project-slug>/project-context/
  ├── brand-candidate.json   # ← first pass: tokens with confidence and source, evidence, asset manifest, warnings
  ├── brand-debug/
  │   ├── homepage.png        # full-page screenshot used for color analysis (capped at 8000 px)
  │   ├── header-crop.png     # top 200px crop
  │   ├── viewport.png        # above-the-fold shot, promoted to assets/site/screenshot.png
  │   ├── hero.png            # capture of the hero section, promoted to assets/site/hero.jpg
  │   ├── logo/               # logo pipeline: test composites per variant + audit.json
  │   ├── brand-board.html    # the filled board page (render_brand_preview.py)
  │   ├── brand-board.jpg     # the board the founder and the model review
  │   └── board-checks.json   # mechanical checks run on the rendered board
  ├── assets/                 # ← real assets harvested on the FIRST pass (see below)
  │   ├── logos/
  │   │   ├── source.svg|png  # the harvested logo, incl. inline-SVG logos serialized to a file
  │   │   └── {wordmark,mark}-on-{light,dark}.{svg,png}   # variants built by logo_pipeline.py
  │   ├── fonts/              # Google Fonts files for offline rendering (--font-files)
  │   └── site/
  │       ├── favicon.png      # site favicon / apple-touch-icon
  │       ├── og-image.jpg     # the og:image share card (great hero source)
  │       ├── screenshot.png   # above-the-fold UI shot (the "product" for SaaS briefs)
  │       ├── hero.jpg         # capture of the hero section
  │       ├── asset-01.jpg ... # page images kept after the decoration filter, largest first
  │       └── manifest.json    # path/source/dims/alt/role/license for every harvested file, plus the rejected ones
  ├── brand-draft.json        # ← brand.json V2 draft, schema-validated, the file the founder edits
  └── brand.json              # ← only written AFTER user approval (--finalize)
```

**Asset harvesting is not deferred to approval.** The logo, og:image, favicon, the
hero capture and the page images are downloaded during Step 1 so the user
can see them on the brand board and so the creative agents have real source
material to build from. Only the *promotion* of `brand-draft.json` →
`brand.json` waits for approval; the bytes on disk are fetched up front. This is
the point of the agent: it exists to **grab the site's real assets for creatives**,
not just to name a few hex colors.

`brand-candidate.json` shape (values from a dark example site):

```json
{
  "source_url": "https://swanbase.co",
  "extracted_at": "2026-06-04T16:00:00Z",
  "tokens": {
    "bg":              { "value": "#030619", "confidence": 0.97, "source": "render:dominant+css:body" },
    "text_primary":    { "value": "#ffffff", "confidence": 0.9,  "source": "css+render:headings" },
    "text_secondary":  { "value": "#c0c1c6", "confidence": 0.8,  "source": "css+render:paragraphs" },
    "surface":         { "value": "#101224", "confidence": 0.8,  "source": "render:card pixels" },
    "accent":          { "value": "#a855f7", "confidence": 0.9,  "source": "css:cta-background+css-var" },
    "on_accent":       { "value": "#ffffff", "confidence": 0.85, "source": "css:cta-label" },
    "font_display":    { "value": "Instrument Serif, Georgia, serif", "confidence": 0.85, "source": "render:document.fonts (google_fonts)" },
    "font_body":       { "value": "Inter, system-ui, sans-serif", "confidence": 0.85, "source": "render:document.fonts (google_fonts)" },
    "logo":            { "value": "assets/logos/source.svg", "confidence": 0.85, "source": "asset:svg" }
  },
  "evidence": { "fonts_loaded": ["Instrument Serif", "Inter"], "logo_candidates": [], "css_color_vars": {} },
  "assets": {
    "license": "founder-site",
    "logo":     { "path": "assets/logos/source.svg", "kind": "svg", "source": "inline-svg", "w": 160, "h": 32, "css_filter": "" },
    "favicon":  { "path": "assets/site/favicon.png", "source": "https://swanbase.co/favicon.png", "w": 180, "h": 180 },
    "og_image": { "path": "assets/site/og-image.jpg", "source": "https://swanbase.co/og-image.jpg", "w": 1200, "h": 630 },
    "screenshot": { "path": "assets/site/screenshot.png", "source": "playwright:viewport", "w": 1440, "h": 900 },
    "hero":     { "path": "assets/site/hero.jpg", "source": "https://swanbase.co", "role": "hero", "license": "founder-site" },
    "images": [
      { "path": "assets/site/asset-01.jpg", "source": "https://swanbase.co/team.jpg", "w": 600, "h": 600, "alt": "Team photo", "role": "team", "license": "founder-site" }
    ],
    "rejected": [ { "source": "https://swanbase.co/glow.png", "reason": "<pixel statistics of a decoration>" } ]
  },
  "warnings": [
    "1 cookie or consent element(s) hidden before measuring; their buttons were ignored."
  ]
}
```

Tokens and evidence keys appear only when the page shows them (`text_muted`, `border`, `radius`, `accent_secondary` and others when found).

Every `path` is relative to the `project-context/` dir, so any consumer resolves
`<project-root>/<project-slug>/project-context/<path>`. `project-context/assets/site/manifest.json`
holds the same `assets` block on its own, for agents that only want the images.

`brand-draft.json` and the approved `brand.json` follow the **V2 contract**: [`../../../../shared/schemas/brand.schema.json`](../../../../shared/schemas/brand.schema.json), example in [`../../../../shared/schemas/examples/brand.swanbase.json`](../../../../shared/schemas/examples/brand.swanbase.json). What the script fills:

| V2 key | From |
|--------|------|
| `schema_version`, `name`, `source_url`, `as_of`, `mode` | `"2.0"`; `og:site_name`, else the page title's first segment, else the domain; the URL; today; `dark` when white text contrasts more than black on `colors.bg` |
| `colors.bg`, `text`, `accent` | the `bg`, `text_primary`, `accent` tokens |
| `colors.surface`, `border`, `text_secondary`, `text_muted`, `on_accent` | the card pixels and border, the paragraph and small-print text on the page background (checked against the glyph pixels), the primary CTA's label |
| `colors.accent_secondary` | the secondary token, only when it comes from a CTA (gradient stop or second button) and stands out from `bg` |
| `radius` | the cards' corner radius, else the CTA's (a pill radius is left out) |
| `fonts.display`, `fonts.body` | the h1 and body families that `document.fonts` really loaded (a declared family that never loaded is skipped and reported), split into `family` + `fallback`, computed `weights`, `source` (`system`, `google_fonts`, `self_hosted`, else `other`), local `files` (Google Fonts by default, `--font-files`); `fonts_url` is the page's Google Fonts stylesheet |
| `logos.on_light`, `logos.on_dark` | `wordmark` and `mark` per variant from `scripts/logo_pipeline.py`: the harvested file keeps its colors under the background it reads on, the other variant is recolored (or knocked out) to one brand ink; `ink`, `width`, `height` from the file. Inline SVG logos are serialized with the colors the page paints (computed fill and stroke, `currentColor` resolved), so the file looks like the site |
| `logo_audit` | per variant: viewBox audit against the rendered ink (`viewbox_clips_ink`) and a pixel test on the variant's background (pass when 90 % of the ink reads at 3:1 or more, warn from 60 %, fail below); the harvested file is also tested on `colors.bg` (the classic dark ink on a dark site) |
| `assets` | `og_image_path`, `favicon_path`, `screenshot_path`, `images[]` (the hero capture first, then the kept page images with their `role`: `hero`, `product`, `team`, `illustration`, `other`) |
| `warnings`, `extensions.extract_brand` | the extraction caveats; the confidence per token, the image license note, the PNG fallbacks of the logos (`logo_png`) |

Only roles the page shows are written; readers derive the missing ones with the fallbacks in [`../../../../shared/schemas/README.md`](../../../../shared/schemas/README.md#fallbacks-for-missing-roles). Every path is relative to the `project-context/` folder (`assets/logos/wordmark-on-dark.svg`, never `project-context/assets/logos/wordmark-on-dark.svg`), so any consumer resolves `<project-root>/<project-slug>/project-context/<path>`. The creative agents (`static-ads-builder`, `carousel-builder`) read `assets.images` for real product/hero source material, `assets.screenshot_path` for the product UI shot (the "product" for a SaaS with no physical packshot), and the `logos` variant matching their background; they never re-scrape the site.

---

## Procedure

### Step 1, fetch DOM + screenshot

Run `scripts/extract_brand.py`:

```bash
python3 agents/project-context/scripts/extract_brand.py \
  --url "$BRAND_URL" \
  --out "$OUTPUT_DIR" \
  [--max-images 6] [--font-files google|all|none]
```

The script:
1. Checks `/robots.txt`; aborts if the homepage is disallowed (exit 2). Only `http` and `https` URLs are fetched, and a host on a private, loopback or link-local address is refused unless the analyzed site sits on one.
2. Launches headless Chromium at 1440x900 with a desktop user agent, loads the page (`load`, then `domcontentloaded`, 30 s each; exit 3 when both fail), allows a 5 s `networkidle` grace, hides cookie and consent banners, scrolls to the bottom so lazy images load, waits for `document.fonts.ready`, then takes the full-page, header-crop, viewport and hero screenshots.
3. Probes the live DOM: every visible text node, card and button with its computed style and box, the loaded font faces and the `@font-face` rules of the stylesheets, `theme-color`, og:image, icons, the logo candidates (img `src` **or** inline-SVG `outerHTML`, scored: link to the home page, "logo" or the brand name in its label, never inside a button), every styled CTA (solid bg **and** CSS-gradient stops), and an image inventory ranked by rendered area.
4. Measures the color roles on the render: `bg` from the screenshot, text roles checked against the glyph pixels, `surface` and `border` from the cards, the accent from the **primary CTA's color** (solid bg, else the most *vivid* gradient stop, checked against the button pixels), not from the whole-page palette where a small button drowns under whitespace.
5. **Harvests real assets to disk**: the logo to `assets/logos/source.*`, og:image, favicon, the viewport and hero captures, and page images into `assets/site/` (12 MB cap each, `--max-images` counting the hero capture); drops decorative images (glows, gradients, grain textures, flat fills) by pixel statistics; records each kept file with its role and license `founder-site` (stock hosts flagged) in `manifest.json`; copies Google Fonts files to `assets/fonts/`.
6. Runs `scripts/logo_pipeline.py` on the logo: viewBox audit, mark and wordmark, `on_light` and `on_dark` variants tested in pixels, PNG fallbacks, `logo_audit`.
7. Writes `brand-candidate.json` (tokens + confidence + evidence + `assets` block + warnings).
8. Builds `brand-draft.json` in the V2 contract and validates it with `shared/scripts/validate_json.py` against `shared/schemas/brand.schema.json` (exit 5 when it does not match; the draft stays on disk for diagnosis).

### Step 2, render the brand board

Render a **self-contained** brand board (no dependency on any other agent):

```bash
python3 agents/project-context/scripts/render_brand_preview.py \
  --brand "$OUTPUT_DIR/brand-draft.json"
```

It fills [`../../assets/brand-board.html`](../../assets/brand-board.html) with the draft, renders it in Chromium and writes `brand-debug/brand-board.html`, `brand-debug/brand-board.jpg` (under 150 KB by default, `--max-kb`) and `brand-debug/board-checks.json`. The board shows every color role with its contrast, the display and body families at several sizes (flagged when the browser fell back to another family), each logo variant on its background with its pixel-test result, buttons, a link and a card composed with the tokens, **the harvested images with their role and license**, and the open issues, so the user can confirm at a glance that the agent grabbed their real material. Exit 1 means a mechanical check failed (contrast of `text`, `text_secondary`, `text_muted` or `on_accent`, a font that did not render, `logo_audit`): the board is still written and the failure goes into the checkpoint. This is what the user judges, not a real deliverable.

### Step 3, present + validate (chat loop)

Surface to the user:
- The rendered `brand-board.jpg` (use the harness's image preview if available, else the file path) and any failed check of `board-checks.json`.
- A compact table of extracted tokens + confidence.
- Any warnings from `brand-draft.json` and every `logo_audit` issue.

Ask the user one of:
1. **Approve as-is** -> finalize (Step 4).
2. **Edit a single token in chat** ("change accent to #ff6900") -> patch `brand-draft.json` (`colors.accent`), re-render the board, re-validate.
3. **Open and edit the JSON directly** ("I'll edit it myself", in `brand-draft.json`) -> wait for confirm, re-render, re-validate.
4. **Logo is wrong** -> ask for the file (SVG first) or its URL, then run `python3 agents/project-context/scripts/logo_pipeline.py --logo <file> --out "$OUTPUT_DIR" --brand "$OUTPUT_DIR/brand-draft.json" --update` (variants, pixel test and `logo_audit` written into the draft), re-render.
5. **Restart from a different URL** -> back to Step 1.

**No iteration cap.** Loop until the user types `approve` / `looks good` / `validate`. This checkpoint is shown together with the context checkpoint in one message (see the agent's Workflow), never as a separate round of questions. Without an answer (unattended run), stop at the draft: `brand-draft.json` stays on disk, `brand.json` is not written, and the report lists the draft as awaiting approval.

### Step 4, finalize

1. The logo, og:image, favicon, and product/hero images are already on disk under
   `assets/` from Step 1. A logo replaced during validation went through
   `logo_pipeline.py --update` (Step 3), which rewrote `logos` and `logo_audit`. If no
   usable logo exists, leave `logos` out and keep `logo_text`.
2. Promote the approved draft:

   ```bash
   python agents/project-context/scripts/extract_brand.py --out "$OUTPUT_DIR" --finalize
   ```

   It dates the file (`as_of`), validates it against the V2 schema and writes
   `brand.json`. Exit 5 means the edited draft no longer matches the schema:
   `brand.json` is left unchanged and the validator names the field to fix.
3. Keep `brand-debug/` and `assets/site/` for traceability and as creative source
   material (small, useful on re-runs).

---

## Hard rules (do not violate)

- **Never auto-approve.** The user must explicitly validate before `brand.json` is written (`--finalize`). An unattended run stops at `brand-draft.json`.
- **V2 only.** The script writes the V2 contract; a V1 `brand.json` found on an update run is replaced by a validated V2 file after approval, never patched in V1 shape.
- **Logo is always a file.** The site's own inline-SVG logo IS serialized to a file (that is real brand material). What is forbidden is the agent *inventing* a logo. If extraction failed and the user has no logo, omit it.
- **Harvest real assets, never synthesize them.** Product/hero images come from the site, downloaded as-is. The agent does not generate stand-in imagery here.
- **Respect download limits.** Each asset is capped (12 MB) and the harvest count is bounded (`--max-images`, default 6, hero capture included). Skip anything that is not an image.
- **Heuristics must publish their confidence.** A token shipped at 0.0 confidence is a bug.
- **No paid SaaS required.** The extraction runs locally and calls no API.
- **Respect robots.txt + ToS.** The script reads `/robots.txt` first; if `Disallow: /` matches the homepage, it aborts with a clear message.
- **No cross-agent dependency.** The board is rendered by this agent's own script; never reach into another agent's render skill.

---

## Failure modes + fallbacks

| Failure | Fallback |
|---------|----------|
| Playwright not installed | Script exits 3 with the install command. Offer the install, or ask 2-3 inline brand questions (primary color, accent, logo file) and write `brand.json` from the answers. |
| Site blocks Playwright (Cloudflare 403) | The script already sends a desktop browser user agent and ignores HTTPS errors; a blocked page gives a challenge screenshot and low-confidence tokens. The agent sees it on the board and puts the logo and color questions in the checkpoint message. |
| Page never settles (analytics, chat widgets) | The script loads on `load`, then `domcontentloaded` (30 s each), and gives `networkidle` a 5 s grace that never fails the run; exit 3 only when both loads time out. |
| All heuristics low confidence (<0.5 across all tokens) | The agent (not the script) checks `extensions.extract_brand.confidence`: it says "low confidence run, recommend manual entry" in the checkpoint message and asks for colors and logo there. |
| Webfont (Google Fonts, self-hosted or unknown) | Google Fonts files are copied to `assets/fonts/` (`--font-files google`, the default). A self-hosted font is not copied (license unknown) unless `--font-files all` after the founder confirms the license; a `warnings[]` entry names every family that needs the site's stylesheet or local files to render elsewhere. A family declared but never loaded is skipped and reported. |
| Logo ink unreadable on the brand background, or a viewBox that cuts the ink | `logo_audit` is `warn` or `fail` with an issue line; the checkpoint asks for the other variant (or the founder accepts `logo_text`). |
| Draft does not match the V2 schema | Exit 5 with the validator's line per field. A script bug: report it, never hand-edit around it. |
| Pillow not installed | Install it from `scripts/requirements.txt`: the pixel sampling of `extract_brand.py` and the board of `render_brand_preview.py` need it (`render_brand_preview.py` exits 4 without it). Without Playwright but with Pillow, `render_brand_preview.py` writes a Pillow card (swatches, font names, PNG logos) and does not check the fonts. |
| Fewer than 3 usable images on the page | The script adds a `warnings[]` entry (hero capture included in the count): ask the founder for product or team photos, or run on a richer page. The creative agents fall back to the og:image, logo, and homepage screenshot. |
| Logo is inline SVG | Serialized to `assets/logos/source.svg` with the computed fill and stroke of each shape and `currentColor` resolved, so the file renders like the site. `logo_pipeline.py` writes PNG fallbacks of every variant for raster-only consumers. |
| Asset host blocks hotlinking (403) | The file is skipped and the rest is kept (a page image that fails to download is listed under `rejected` in `manifest.json`). One asset never fails the whole run. |

---

## Why this design

- **Two signals are stronger than one.** DOM gives ground truth for fonts and logo URLs. Screenshot gives ground truth for *what the user actually sees* (covers CSS-in-JS, inline styles, Tailwind classes).
- **Accent comes from the CTA, not the palette.** The brand accent is whatever color the site puts on its primary button. Reading the CTA background (solid or the vivid stop of a gradient) beats a whole-page palette where a small button drowns under whitespace. This is what fixes sites where the true accent is the CTA color (often the lit stop of a gradient), not a leftover theme-color in the markup. A button that barely stands out from the page (a ghost button) is never the accent.
- **Grab the real assets, do not redraw them.** Founders want creatives built from *their* logo and *their* product shots, not lookalikes. Harvesting the logo, og:image, and largest on-page images up front is the whole point of this agent; the colors are necessary but not sufficient.
- **Confidence + validation loop > single-shot extraction.** Brand pages vary wildly. The failure mode is "wrong color shipped to an ad", which is expensive. Bias toward asking.
- **Extract once, read everywhere.** Once `brand.json` exists in `project-context/`, every other agent reuses its tokens *and* its harvested assets. Edits are one file change away.
