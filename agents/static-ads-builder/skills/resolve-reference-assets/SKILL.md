---
name: resolve-reference-assets
description: Resolve the local reference images each selected brief asked for, so the renderer can attach them (image-to-image / compose). Handles every asset role, a physical product packshot, the product UI screenshot, the brand logo, and the hero/og image, not just a single packshot. Resolution order per role, user-provided path, then a project-context asset, then a firecrawl scrape (product only), then ask. Writes an ordered _ref_paths list per brief. Use after Gate 1, before Gate 2. Triggers: "find the reference images", "attach the logo and screenshot", "resolve assets".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(firecrawl:*) Bash(curl:*)
---

# Skill: resolve-reference-assets

For each **selected** brief, resolve every asset it declared in `reference_assets` to a local file, and write the ordered list of absolute paths into the brief as `_ref_paths`. The renderer attaches all of them to the generation (image-to-image / compose). Briefs with no `reference_assets` need nothing from this skill and render text-to-image.

This is the bridge that makes the founder's **real material**, their logo, their product UI, their hero image, actually reach the creative. The previous version resolved only a single physical packshot and explicitly threw the logo away; this one resolves whatever role the brief asked for.

This runs **after Gate 1** (so only the selected briefs cost effort) and **before Gate 2** (so the spend estimate only counts briefs whose references resolved).

---

## When to load

- Workflow Step 6 of `static-ads-builder`, once the founder has selected briefs to render.

---

## The asset roles

Each entry in a brief's `reference_assets` has a `role`. Resolve each to one local file:

| `role` | What it is | Where it comes from |
|--------|-----------|---------------------|
| `product` | A physical product packshot | user path -> `brand.json.assets.images[]` (a packshot) -> firecrawl product scrape -> ask |
| `screenshot` | The product UI / app / dashboard (the "product" for SaaS) | user path -> `brand.json.assets.screenshot_path` -> a UI-looking image in `assets.images[]` -> homepage screenshot in `project-context/brand-debug/homepage.png` -> ask |
| `logo` | The brand logo | `brand.json.assets.logo_path` -> user path -> ask. **Never rejected.** |
| `hero` | The og:image / brand hero | `brand.json.assets.og_image_path` -> user path -> ask |

`brand.json.assets.*` paths are project-root-relative; resolve them against `<project-root>/<project-slug>/`. Verify each file exists and is non-empty before using it.

---

## Procedure

1. **Read the assets manifest once.** Load `<project-root>/<project-slug>/project-context/brand.json` and note `assets.logo_path`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`. If `brand.json` is absent, every role falls back to "ask the founder for a path/URL".
2. **Walk the selected briefs.** For each brief and each `reference_assets[].role`, resolve a local file using that role's order above.
3. **Dedupe across briefs.** A logo or screenshot is downloaded/copied **once** and the same local path is reused everywhere. Resolve a distinct `product` per distinct product.
4. **Write `_ref_paths`.** Set `_ref_paths` on the brief to the ordered list of resolved absolute paths (same order as `reference_assets`). Drop any role that could not resolve, and note it. `_ref_paths` is a pipeline-only key; the renderer strips `_`-prefixed keys from the fal payload.
5. **Decide renderability.** If a brief declared `reference_assets` but **none** resolved, mark it `SKIPPED_REF_MISSING` and exclude it from the spend estimate. If some-but-not-all resolved, keep it (render with what resolved) and note the missing role.

---

## Resolving each role

### `logo`

Use `brand.json.assets.logo_path` directly (copy into the agent's `refs/` so the run is self-contained). If it is an SVG, rasterize to PNG first (the generator needs a raster): `python` + `cairosvg`/`rsvg-convert`, or fall back to the favicon/og image if no rasterizer is available. If no logo exists anywhere, drop the role and note it; never invent a logo.

### `screenshot`

First choice `brand.json.assets.screenshot_path` (the clean homepage screenshot promoted by `extract-brand`). If absent, look for a UI-looking image in `assets.images[]` (wide aspect, alt text mentioning app/dashboard/screen). If still nothing, fall back to `project-context/brand-debug/homepage.png`. As a last resort, ask the founder for a screenshot path or offer to capture one. Copy the chosen file into `refs/`.

### `hero`

Use `brand.json.assets.og_image_path`. If absent, ask or drop.

### `product` (physical packshot)

1. **User-provided.** A local path -> verify and use. A public URL -> download (below).
2. **project-context asset.** A packshot in `assets.images[]` (not the logo). Use a matching product asset if present.
3. **Scrape the brand site (firecrawl).** Only if `FIRECRAWL_API_KEY` is set.

   ```bash
   firecrawl map <website_url> --search "product" --limit 30 --json
   firecrawl scrape <product_page_url> \
     --schema '{"type":"object","properties":{"product_name":{"type":"string"},"main_image_url":{"type":"string"},"image_candidates":{"type":"array","items":{"type":"string"}}}}' \
     --format markdown,links --json
   ```

   Scoring: product-slug match in the URL; packshot / main / featured cues; absolute `https://`; prefer `og:image` / `twitter:image`; avoid logo / nav / banner / icon assets.
4. **Ask.** If nothing resolves, ask for a direct URL or local path. Still nothing -> drop the role.

---

## Download / copy

```bash
mkdir -p "<project-root>/<project-slug>/static-ads-builder/refs"
# from a URL:
curl -L "<selected_url>" -o "<refs>/<role>-<slug>.<ext>"
# from a local project-context asset:
cp "<project-root>/<project-slug>/project-context/<asset_path>" "<refs>/<role>-<slug>.<ext>"
```

Filename: `<role>-<slug>.<ext>` for shared assets (`logo-acme.png`, `screenshot-acme.png`), or `NN-<product-slug>-ref.<ext>` for a per-brief product. Verify every file is non-empty.

---

## Wire the paths back into the briefs JSON

For each selected brief, write the resolved absolute paths into its object in `static-ads-briefs-YYYYMMDD.json` as `"_ref_paths"` (a JSON array, in `reference_assets` order). This is how `render_ads.py` knows which references to attach, deterministically, even after dedupe. A brief that resolved nothing keeps `_ref_paths` unset and is `SKIPPED_REF_MISSING`. (For backward compatibility the renderer also reads a single legacy `_ref_path` and falls back to a `NN-` filename in `--refs-dir`, but `_ref_paths` is the reliable channel.)

---

## Confirm before Gate 2

Show a compact table per selected brief: brief number, the roles it asked for, the resolved local path + source for each (user / project-context / firecrawl / homepage-screenshot), and any role that was dropped. The founder eyeballs it before any spend is confirmed. Make it obvious when a logo or screenshot is being reused across several briefs (dedupe).

---

## Failure modes

- **No `brand.json` / no assets** -> every role falls back to asking the founder; never block non-asset (text-only) briefs.
- **`FIRECRAWL_API_KEY` missing** -> skip the product scrape (step 3), ask the founder for a product URL/path instead.
- **Logo is SVG and no rasterizer available** -> fall back to favicon or og:image as the brand mark, or drop the logo role with a note.
- **Scrape or download fails** -> ask for a manual URL or local path; never block other briefs.
- **A brief declared assets but none resolved** -> `SKIPPED_REF_MISSING`; excluded from the spend estimate and not rendered.
- **Some roles resolved, others did not** -> render with what resolved; note the dropped role in the confirm table.

---

## References

- Asset manifest schema: `project-context` `skills/extract-brand/SKILL.md` (the `assets` block in `brand.json`).
- firecrawl CLI: `references/README.md` (cli-skills).
- Renderer multi-image attach: `scripts/render_ads.py` (`_ref_paths` -> `image_urls`).
