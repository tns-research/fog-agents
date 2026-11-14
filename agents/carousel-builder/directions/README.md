# Directions

A direction is an art direction stored as data: the same `deck.json` renders in any of them, and the brand (accent colours, logo, optionally fonts) sits on top without changing the structure. `scripts/build.py` inlines `_base.css`, then the direction's `style.css`, then the theme variables it computes from `direction.json` and `brand.json`.

| Direction | Look | Best for |
|-----------|------|----------|
| `editorial-paper` | Warm paper, editorial serif, hairline rules | explainers, opinion, research summaries |
| `riso-print` | Two or three spot inks on paper, halftone, misregistration | culture, events, playful education |
| `swiss-grid` | Strict grid, grotesque, oversized numerals | data, frameworks, step-by-step |
| `photo-poster` | Full photo shown whole, solid type band | events, people, places, product in use |
| `data-notebook` | Graph paper, chart as the hero, marginal notes | numbers-first carousels, benchmarks |
| `terminal` | Controlled dark ground, monospace, one phosphor accent | developer tools, technical how-tos |

List them with `python3 scripts/build.py --list-directions`. The art-direct step renders the same cover in each (`python3 scripts/pipeline.py <deck.json> --covers --directions all --first-layout`).

## Files of a direction

```
directions/<id>/
  direction.json   rules and tokens (below)
  style.css        the look; every selector scoped under .d-<id>
  preview.jpg      generated vignette (cover, chart, a calm stat, list of the reference deck, by scripts/preview.py), never hand-made
```

## direction.json

| Key | What it holds |
|-----|---------------|
| `id`, `name`, `summary`, `best_for`, `avoid_for`, `mood` | Identity. `mood` is `light` or `dark`; it picks the brand logo variant (`logos.on_light` or `logos.on_dark`). |
| `rules` | Plain-language rules the model and the reviewer read: `grid`, `type`, `density`, `accent`, `photo`, `texture`. |
| `palette` | `paper`, `ink`, `muted`, `rule`, `chart_base`, `chart_base_2`, `chart_base_3`, `mat`, default `accent` and `accent_2` (used when the project has no brand), and an `inverse` palette for `surface: "inverse"` slides. |
| `fonts` | Roles (`display`, `text`, `label`, `mono`...), each `{family, google, fallback}` or `{family, files: [{path, weight, style}]}`. Each role becomes `--font-<role>`. |
| `brand` | `fonts`: whether brand fonts replace `display` and `text` by default (deck `meta.use_brand_fonts` overrides). `inverse_from_brand`: a dark brand background becomes the inverse surface. `accent_pick`: `first` (default, the brand accent) or `max-contrast` (the brand colour that stands out most on the direction's paper, for dark directions). |
| `chrome` | Roles that get the logo (`logo`), the handle (`handle`), and whether content slides carry a folio (`folio`). |
| `safe_margin` | Pixels from the edge no text may cross (qa.py `outside-safe-zone`). |
| `type_scale` | Fit ranges per text role: `{min, max, lines, steps?}`. Keys: `cover_title`, `cover_sub`, `title`, `sub`, `body`, `list`, `stat_value`, `stat_label`, `stat_context`, `chart_title`, `quote`, `cta`, `cta_sub`. A key can be specialised per layout (`title@text`) or for slides carrying media (`cover_title_media`). |
| `budgets` | Word budgets build.py warns about (`title_words`, `cover_title_words`, `body_words`, `list_items`). |
| `chart_box` | `[w, h]` the chart SVG is drawn for, per layout (`default`, `chart`). |
| `cover_layouts` | Ordered list of cover layouts; the first is the default, `--covers` renders them all. |
| `layouts` | Every layout the direction styles, with a one-line description. A direction must style all of: `cover-a`, `cover-b`, `text`, `list`, `stat`, `chart`, `quote`, `media`, `logos`, `visual`, `cta`. |
| `min_text` | Optional `{text, meta}` minimum px for qa.py (default 24 and 20). |

## The markup a direction styles

Fixed by `scripts/blocks.py` and `scripts/build.py`. The slide:

```html
<section class="slide role-<cover|content|cta> layout-<name> surface-<default|inverse|accent> tone-<calm|dense> has-<blocktype>...">
  <div class="s-deco"></div>                       <!-- decoration layer, empty: draw with ::before/::after -->
  <div class="s-frame">                            <!-- padding = --pad-top --pad-x --pad-bottom -->
    <header class="s-head"><div class="logo">...</div></header>      <!-- chrome.logo roles only -->
    <div class="s-main"> blocks </div>
    <footer class="s-foot"><p class="src">Source : ...</p><p class="handle">...</p><p class="folio">...</p></footer>
  </div>
</section>
```

Blocks and their classes: see the docstring of `scripts/blocks.py`. Charts are SVG with classes (`.c-bar.is-hl`, `.c-line.is-hl`, `.c-seg.is-hl`, `.c-label`, `.c-value`, `.c-axis`, `.c-tick`, `.c-grid`), so a direction recolours them in CSS. Use `:has()` and the `has-<type>` classes to adapt a layout to its content (a cover with or without a photo).

## Variables

Set per surface by build.py; a direction reads them and never hardcodes a brand colour:

`--paper --ink --muted --rule --chart-base --chart-base-2 --chart-base-3 --mat`, the accent roles `--accent-mark` (graphics, 3:1 on paper), `--accent-text` (accent words, 4.5:1), `--accent-fill` (highlight under ink, 7:1), `--on-accent-fill`, `--accent-solid` and `--on-accent-solid` (accent surface), `--font-<role>`, and `--W`, `--H`. The structure variables a direction sets: `--pad-top --pad-x --pad-bottom --gap --logo-h --font-chart`.

## Rules every direction follows

- Scope every selector under `.d-<id>`; never restyle `_base.css` globally.
- No blurred `box-shadow` or `text-shadow` (glow), no `backdrop-filter`, no `filter: blur` outside the photo mat, no gradient text, no gradient between two opaque colours, no side-stripe cards, radius 28 px at most. qa.py fails or flags each of these.
- One accent on a slide at most, applied through the accent variables. Highlights under ink text use `--accent-fill`.
- Photos are never cropped by default (`fit-contain`); the zone around them is a mat (paper, ink or a blurred copy of the photo), chosen by the direction.
- Text never closer to the edge than `safe_margin`; sources stay at 20 px or more, everything else at 24 px or more, body text at 30 px or more.
- 40 to 50 % empty surface is the failure this system exists to prevent: layouts anchor content to the frame (top, bottom, both) and let fit.js grow the type into the space.
- Texture (grain, halftone) is drawn in CSS so the PDF keeps it, and stays under 10 % opacity behind text.

## Adding a direction

Copy the closest direction folder, rename every `.d-<old>` selector, change the tokens, then iterate on real renders until qa.py passes on `examples/swanbase-seed-deck-20261010/deck.json`, `examples/blocks-tour/deck.json` and `examples/stress/deck.json` reports only the stress errors it is built to trigger:

```bash
python3 scripts/pipeline.py examples/swanbase-seed-deck-20261010/deck.json --direction <id> --out /tmp/<id>
python3 scripts/pipeline.py examples/blocks-tour/deck.json --direction <id> --out /tmp/<id>-tour
python3 scripts/pipeline.py examples/stress/deck.json --direction <id> --out /tmp/<id>-stress
python3 scripts/preview.py <id>      # regenerates directions/<id>/preview.jpg
```

Read every PNG at full size and the contact sheet at 25 % before calling it done.
