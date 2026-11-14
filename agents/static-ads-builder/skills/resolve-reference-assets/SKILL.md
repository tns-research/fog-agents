---
name: resolve-reference-assets
description: Gathers the founder's real material for each concept before ads.json is written - the logo (read from brand.json by the renderer), a product packshot, a product UI screenshot, founder photos - copies each file into the run's media/ folder, and records every word printed on it (visible_text) so the proofread can catch a distorted label. Asset bank first - nothing is generated while a real file can do the job. Resolution order per role - founder path, project-context asset, a scrape of the brand site (product only, any scrape provider), then ask. Use at Step 3 of static-ads-builder. Triggers: "find the product image", "use my logo and screenshot", "use this photo".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "3.0"
allowed-tools: Read Write Bash(curl:*) Bash(python3:*)
---

# resolve-reference-assets

Real material beats any illustration: the actual packshot, the actual interface, the founder's own photos. The renderer places these files in HTML exactly as they are (shown whole, never redrawn), so no model can distort a label or a logo. This skill finds the files and writes down what is printed on them.

## Asset bank first

Before planning a plate (a generated background), list what exists, in this order: `brand.json` (`logos`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`), the founder's folders they point to, files they attach in chat. A plate is planned only when no real file serves the concept, and it then goes through the spend gates of [`../render-ads/SKILL.md`](../render-ads/SKILL.md).

## Roles

| `media.role` | What | Resolved from |
|--------------|------|---------------|
| logo (no media entry) | brand logo | `brand.json` `logos.on_dark` / `logos.on_light`, picked by `build.py` per surface; a variant that failed `logo_audit` is skipped; without any file, `logo_text` is typeset |
| `product` | packshot, transparent PNG preferred | founder path, then a packshot in `assets.images[]`, then a scrape of the product page (`og:image`, main product image), then ask |
| `screenshot` | the product UI | founder path, then `assets.screenshot_path`, then a UI image in `assets.images[]`, then ask (or capture it with the `screenshot` capability) |
| `photo` | a real photo: team, place, customer, product in use | founder path or attachment, then `assets.images[]` (never a `role: texture` image), then ask |
| `plate` | text-free generated background | only after the bank is empty for that concept; see render-ads |

`brand.json` paths resolve against the folder of `brand.json` (`<project>/project-context/`), then its parent, as described by the loader ([`../../../../shared/skills/loading-project-context/SKILL.md`](../../../../shared/skills/loading-project-context/SKILL.md#option-brand-brand-tokens-and-assets)).

## Procedure

1. For each concept of the plan, pick the files by role. Copy each into `<run>/media/` (download with `curl -L <url> -o <run>/media/<role>-<slug>.<ext>` when it is a URL). One copy per file, reused by every concept that needs it.
2. Check each file: it opens, its long side is at least 800 px for a media shown large (`qa.py` warns `low-res-image` when it is upscaled), a packshot has a clean or transparent background (keep the original background when no local cut-out tool is available; never ask an image model to cut it out).
3. **Write `visible_text`.** Open the file at full size and copy every word printed on the object: brand and product name on a label, flavour, weight, claims on a pack, words on a sign, a shirt or a screen. Copy them from the real object or the founder's product sheet, accents and capitals as printed. `[]` when there is none. These words are expected on the render: if the file itself is wrong (an old label, a mock-up with a typo), replace the file.
4. A third-party brand visible on a photo (a logo on clothing, a shop sign) is declared in `visible_text` and flagged in the report for the founder's decision before spend.
5. Write the media entries into `ads.json` with `src` relative to it (`media/<file>`), `alt`, `fit: contain` (shown whole; `cover` only for plates), `visible_text`.

## Failure modes

- **No `brand.json`** → ask the founder for the logo file and the product image in the Step 0 message; text-only styles still work.
- **Only an SVG logo with a clipped viewBox** → `build.py` inlines the SVG; if letters are cut on the render, flag it and use the other variant or `logo_text`.
- **Scrape not available** → ask for a URL or a file; never block concepts that need no media.
- **A product image found only on a marketplace or a competitor page** → do not use it; ask the founder.
