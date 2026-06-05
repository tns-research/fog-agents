---
name: render-carousel
description: Assemble a single self-contained index.html from an approved slide plan JSON, the active brand tokens (or default-style.css), and the bundled per-type templates. Inlines CSS and shared SVG defs. The output HTML is the only artifact slides2pdf or Playwright will see.
---

# Skill: render-carousel

Take an approved slide plan + active brand and write `index.html` to the run output folder. One section per slide, selectors `.deck` and `.slide` so `slides2pdf` works with zero configuration.

---

## Hard rules (do not violate)

- **No `backdrop-filter` anywhere.** Breaks `slides2pdf` / headless Chrome PDF rendering.
- **No PREV / NEXT buttons, no `.nav-btns`, `.nav-btn`, `#prev-btn`, `#next-btn`** in the exported HTML. They have leaked into PNG / PDF screenshots in production. Keyboard nav for browser preview is included in `_base.html` and uses arrow keys only.
- **Selectors must be `.deck` and `.slide`** (matches `slides2pdf` defaults, no flag needed).
- **Logo always loaded from a file** (`images/logo.svg`), never reconstructed inline by the agent. If `project-context/brand.json` is missing, omit the logo entirely rather than draw a placeholder.
- **Body copy minimum 22px** so a 1080x1350 portrait slide reads cleanly in a 1:1 mobile feed.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `slide_plan.json` | from `plan-carousel` | yes |
| `brand.json` | from `project-context/brand.json` (shared) or hand-edited in `project-context/`; if absent, use `assets/default-style.css` defaults | no |
| `style.css` (per-project override) | optional, replaces `assets/default-style.css` if present | no |
| `ratio` | from `config.json` (`1:1` or `4:5`) | yes |
| `output_dir` | `<project-root>/<project>/carousel-builder/<label>-<YYYYMMDD>/` | yes |

---

## Outputs

```
<output_dir>/
  ├── index.html       # self-contained deck, fonts URL externalized, CSS + SVG defs inlined
  └── images/
      ├── logo.svg     # copied from the resolved project-context logo_path if set
      └── img-NN.*     # user-provided images referenced by content-image slides
```

The HTML is fed directly to `export-slides` next.

---

## Step-by-step execution

### Step 0 — Resolve assets (Phase 4)

Before any HTML assembly, call `skills/handle-assets/SKILL.md`. It walks the slide plan, picks one of `user_image` / `svg_helper` / `bespoke_svg` / `fal_ai` / `none` per slide, and annotates each slide with `_resolved_asset`. From this point on, the render skill consumes `_resolved_asset` and ignores the raw hints (`image_path`, `chart`, `svg_inline`, `generate_image`).

Per-slide `_resolved_asset` shape:

```json
{ "kind": "file", "path": "images/slide-04.jpg", "alt": "..." }
{ "kind": "inline-svg", "html": "<svg>...</svg>" }
{ "kind": "none", "reason": "..." }
```

Render rules:
- `kind: file` → reference as `<img src="images/slide-NN.jpg" alt="...">` in the matching template.
- `kind: inline-svg` → drop the `<svg>` directly inside the slide's visual slot, no wrapper.
- `kind: none` → render the slide's text-only template variant (e.g. `content-text` instead of `content-image`).

If a slide has `type: content-image` but `_resolved_asset.kind == "none"`, downgrade the type to `content-text` and re-pick the template.

### Step 1 — Resolve ratio

```
1:1 -> --slide-w: 1080px; --slide-h: 1080px
4:5 -> --slide-w: 1080px; --slide-h: 1350px
```

These overwrite the values from `assets/default-style.css` via a small `:root` override block at the top of the inlined CSS.

### Step 2 — Resolve brand tokens

Priority order:

1. `<project-root>/<project>/carousel-builder/style.css` exists → inline it verbatim. Skip token mapping.
2. `<project-root>/<project>/project-context/brand.json` exists → map fields to CSS custom properties (see table below), inline `assets/default-style.css`, then append a `:root` override block with the mapped tokens.
3. Neither → inline `assets/default-style.css` as-is.

`brand.json` -> CSS custom properties:

| brand.json key | CSS variable |
|---|---|
| `bg` | `--bg` |
| `text_primary` | `--text-primary` |
| `text_secondary` | `--text-secondary` |
| `text_muted` | `--text-muted` |
| `accent` | `--accent` |
| `accent_secondary` | `--accent-secondary` |
| `card_bg` | `--card-bg` |
| `card_border` | `--card-border` |
| `card_radius` | `--card-radius` |
| `font_heading` | `--font-heading` |
| `font_body` | `--font-body` |
| `fonts_url` | `<link href="..." rel="stylesheet">` in `<head>` |
| `logo_path` | copy file to `<output_dir>/images/logo.svg`, reference as `images/logo.svg` (resolved against `project-context/`) |
| `logo_text` | optional brand wordmark next to logo (rendered in `_base.html` header) |

### Step 3 — Read templates

Read `_base.html` once, then read only the per-type templates referenced by the slide plan.

```
skills/render-carousel/templates/
  ├── _base.html
  ├── cover.html         # slide 1 hook + logo
  ├── content-text.html
  ├── content-quote.html
  ├── content-list.html
  ├── content-stat.html
  ├── content-image.html
  └── cta.html           # final slide
```

### Step 4 — Assemble `index.html`

1. Start from `_base.html`.
2. Substitute global tokens: `LANG`, `TITLE`, `FONTS_URL`, inlined `CSS`, brand `LOGO_HTML`.
3. For each slide, render the matching template with per-slide substitutions (table below).
4. Inject the assembled slide HTML into the `<main class="deck">` block.
5. Write to `<output_dir>/index.html`.

### Step 5 — Copy assets

```
mkdir -p <output_dir>/images
cp <project-root>/<project>/<logo_path> <output_dir>/images/logo.svg     # if present
cp <user-provided image> <output_dir>/images/img-NN.<ext>  # for each content-image slide with a local path
```

For remote URLs in `image_url`, leave the `src` attribute as the URL (no copy).

### Step 6 — Sanity-check

After writing, verify:

- `index.html` contains exactly `slide_plan.meta.total_slides` `<section class="slide">` elements.
- No `<button class="nav-btn">`, `<div class="nav-btns">`, `id="prev-btn"`, or `id="next-btn"` survived.
- `images/logo.svg` exists if `project-context/brand.json.logo_path` was set.

If any check fails, fix before handing off to `export-slides`.

---

## Per-slide substitutions

### `cover` (always slide 1)

| Placeholder | Source | Required |
|---|---|---|
| `COVER_KICKER` | `slide.kicker` | no |
| `COVER_TITLE` | `slide.title` (use `<br>` for line breaks) | yes |
| `COVER_SUBTITLE` | `slide.subtitle` | no |
| `COVER_HOOK_HERO` | `slide.hook_hero` | no |
| `SWIPE_INDICATOR` | always `Swipe →` (cover only) | yes |

### `content-text`

| Placeholder | Source | Required |
|---|---|---|
| `TEXT_KICKER` | `slide.kicker` | no |
| `TEXT_TITLE` | `slide.title` | yes |
| `TEXT_BODY` | `slide.body` (markdown -> HTML, see below) | yes |
| `TEXT_TAKEAWAY` | `slide.takeaway` | no |

### `content-quote`

| Placeholder | Source | Required |
|---|---|---|
| `QUOTE_TEXT` | `slide.quote` | yes |
| `QUOTE_ATTRIBUTION` | `slide.attribution` (`— Name`) | no |

### `content-list`

| Placeholder | Source | Required |
|---|---|---|
| `LIST_TITLE` | `slide.title` | yes |
| `LIST_ITEMS` | `slide.items[]`, each `{lead, sub}` | yes |

Each item renders as:

```html
<li><span class="num">01</span><div><p class="lead">Lead</p><p class="sub">Sub</p></div></li>
```

### `content-stat`

| Placeholder | Source | Required |
|---|---|---|
| `STAT_NUMBER` | `slide.number` | yes |
| `STAT_LABEL` | `slide.label` | yes |
| `STAT_SOURCE` | `slide.source` | no |

### `content-image`

| Placeholder | Source | Required |
|---|---|---|
| `IMAGE_TITLE` | `slide.title` | yes |
| `IMAGE_SRC` | `slide.image_url` -> `images/img-NN.ext` (local) or URL (remote) | yes |
| `IMAGE_ALT` | `slide.image_alt` (fallback to `slide.title`) | yes |
| `IMAGE_CAPTION` | `slide.caption` | no |

Resolution:
- Local path -> copy to `images/`, reference as `images/img-NN.ext`.
- URL -> use directly.
- If copy fails -> render a `<div class="image-placeholder">` with the alt text.

### `cta` (always last slide)

| Placeholder | Source | Required |
|---|---|---|
| `CTA_TITLE` | `slide.title` | yes |
| `CTA_TEXT` | `slide.cta_text` | no |
| `CTA_LINK` | `slide.cta_url` (default `"#"`) | no |
| `CTA_SECONDARY` | `slide.cta_secondary` | no |
| `CTA_HANDLE` | `slide.author_handle` or `meta.author_handle` | no |

Optional fields render their HTML element only when present; otherwise omit the element entirely (do not leave empty tags).

---

## Markdown to HTML conversion (for `content-text.body`)

Keep it lightweight. Slide copy is short.

| Markdown | HTML |
|---|---|
| `**bold**` | `<strong>bold</strong>` |
| `*italic*` | `<em>italic</em>` |
| `\n` | `<br>` |
| `**emphasis word**` matching `slide.emphasis` | `<strong class="accent">word</strong>` |

No nested markdown, no headings inside body copy.

---

## Tools used

- `Read` / `read_file`: load templates, default-style.css, project-context/brand.json
- `Write` / `create_or_rewrite_file`: write index.html
- `Bash` / `run_bash_command`: copy logo + images into `images/`

---

## Error handling

| Situation | Action |
|---|---|
| Slide type not in templates | Fall back to `content-text` template |
| `project-context/brand.json` malformed | Warn, ignore, use default-style.css |
| Logo path does not exist | Render header without logo, log warning |
| Local image path missing | Render `image-placeholder` div, log warning |
| `slide_plan.json` references unknown field | Skip the field, do not crash the whole render |
| Output dir already populated | Overwrite `index.html`, merge `images/` (do not delete user assets) |

---

## Why this design

- **One self-contained `index.html`** = `slides2pdf` reads it as a single deck and produces a multipage PDF. No per-slide HTML files needed.
- **CSS variables for ratio + brand** = same templates handle 1:1 and 4:5, neutral and branded, without forking.
- **Templates inlined into a single deck** mirrors `agent-social-slides` exactly so the muscle memory carries over.
- **Per-project `style.css` override** = power users never get blocked by the default tokens.
