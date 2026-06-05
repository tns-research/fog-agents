---
name: handle-assets
description: Resolve the visual asset for every slide in an approved plan, picking deterministically between user-supplied images, the SVG helper library, bespoke inline SVG, and (opt-in) fal AI image generation. Returns a per-slide asset descriptor that render-carousel inlines into the final HTML. Phase 4 of carousel-builder.
---

# Skill: handle-assets

Per slide, return exactly one of: a **file** path under `images/`, an **inline SVG** string, or **none** (slide stays text-only). The `render-carousel` skill calls this skill once before assembling `index.html`.

This skill is the single source of truth for visual asset resolution. It does not render templates, it does not modify the slide plan beyond annotating each slide with its resolved asset.

---

## Hard rules

- **One asset per slide.** Never combine user image + AI image + SVG on the same slide.
- **Deterministic priority.** Same plan + same env + same brand always resolves the same way.
- **fal AI is single opt-in.** Presence of `FAL_API_KEY` (or `FAL_KEY`) in env is the only gate. No second config flag. If unset, AI images are silently unavailable, the resolver routes around them.
- **Hard caps.** Max 5 user images per run, max 3 fal images per run (`fal_max_images` overrides). Above the cap, the slide falls through to the next priority.
- **Brand colors via CSS variables.** All SVG (helpers and bespoke) must use brand tokens (`var(--accent)`, `var(--accent-secondary)`, etc.), never hardcoded hex.
- **No network by default.** Only fal calls and remote-URL user images touch the network. Everything else is local.

---

## Inputs

| Input | Source | Required |
|-------|--------|----------|
| `slide_plan.json` | from `plan-carousel`, optionally enriched with `image_path`, `image_url`, `chart`, or `generate_image` blocks per slide | yes |
| `brand.json` | from `project-context/brand.json` (shared) or hand-edited in `project-context/`; absent means default-style.css colors | no |
| `output_dir` | run output dir, e.g. `<project-root>/<project>/carousel-builder/<label>-<YYYYMMDD>/` | yes |
| `config.json.fal_max_images` | per-project cap on fal images per run, default `3` | no |
| `config.json.fal_model` | per-project default fal model, default `fal-ai/nano-banana-pro` | no |
| `config.json.tone` | drives prompt suffix (`founder` / `expert` / `casual`) | no |

---

## Per-slide visual hints (added by plan-carousel or by hand)

The `plan-carousel` skill already produces a structured slide plan. Phase 4 extends each slide with optional fields:

```json
{
  "type": "content-image",
  "title": "Your first 50 users",
  "image_path": "/Users/me/photos/users.jpg",   // optional, local path
  "image_url": "https://...",                    // optional, remote URL
  "chart": {                                      // optional, SVG helper input
    "kind": "bar_chart",
    "data": {"items": [{"label": "Q1", "value": 12}, ...]}
  },
  "svg_inline": "<svg>...</svg>",                 // optional, bespoke author-time SVG
  "generate_image": {                             // optional, fal AI request
    "prompt": "minimalist illustration of...",
    "alt": "..."
  }
}
```

A slide may have multiple hints set. The resolver picks one; all others are ignored for that slide (and noted in the report).

---

## Priority order (per slide, highest first)

1. **`image_path` / `image_url`** (user image) — always wins if present and the image is reachable.
2. **`chart`** (SVG helper) — wins over `svg_inline` when both are present (the helper is more constrained, less slop-prone).
3. **`svg_inline`** (bespoke SVG written by the agent) — wins over `generate_image` (vector beats raster for editorial visuals).
4. **`generate_image`** (fal AI) — only when env key is present AND remaining fal budget > 0.
5. **None** — slide stays text-only. The render-carousel skill renders the matching template without an `IMAGE_*` substitution.

If a higher-priority source fails (file not found, helper unknown, fal call errors), the resolver falls through to the next source rather than failing the whole run.

---

## Step-by-step execution

### Step 1 — Pre-pass: collect user images

Build a list of slide indices that have `image_path` or `image_url` set. Cap at 5. Above the cap, mark the slide as `over-cap` and fall through to the next source.

If non-empty, call:

```bash
python scripts/copy_user_images.py --output-dir <output_dir> < specs.json
```

`specs.json` is built from the plan: `[{"slide_index": N, "source": "...", "alt": "..."}, ...]`.

The script writes `<output_dir>/images/slide-NN.jpg` for each successful copy and prints a JSON report. Merge `ok: true` entries back into the slide spec under `_resolved_asset`.

### Step 2 — Pre-pass: count fal budget

```python
fal_budget = config.get("fal_max_images", 3) if FAL_API_KEY in env else 0
```

If `fal_budget == 0`, skip Step 4 entirely.

### Step 3 — Per-slide resolution loop

For each slide in `slide_plan.slides`:

```
if slide already has _resolved_asset (from Step 1):
    continue

if slide.chart:
    try:
        from scripts.svg_helpers import HELPERS
        helper = HELPERS[slide.chart.kind]
        svg = helper(slide.chart.data, brand_tokens, width, height)
        slide._resolved_asset = {"kind": "inline-svg", "html": svg, "source": "svg_helper"}
        continue
    except KeyError:
        warn(f"unknown helper {slide.chart.kind}, falling through")
    except Exception as e:
        warn(f"helper {slide.chart.kind} failed: {e}, falling through")

if slide.svg_inline:
    slide._resolved_asset = {"kind": "inline-svg", "html": slide.svg_inline,
                             "source": "bespoke"}
    continue

if slide.generate_image and fal_budget > 0:
    out_path = f"{output_dir}/images/slide-{slide.index:02d}.jpg"
    cmd = [
        "python", "scripts/generate_image.py",
        "--prompt", slide.generate_image.prompt,
        "--out", out_path,
        "--ratio", config.ratio,
        "--model", config.get("fal_model", "fal-ai/nano-banana-pro"),
        "--brand-colors", ",".join(brand_tokens.colors_for_prompt()),
        "--tone", config.get("tone", "founder"),
    ]
    rc = subprocess.run(cmd, capture_output=True).returncode
    if rc == 0:
        slide._resolved_asset = {"kind": "file", "path": f"images/slide-{slide.index:02d}.jpg",
                                 "alt": slide.generate_image.alt, "source": "fal_ai"}
        fal_budget -= 1
        continue
    elif rc == 2:
        warn("fal key absent; not retrying for the rest of the run")
        fal_budget = 0
    else:
        warn(f"fal call failed (rc={rc}); falling through to text-only")

# Fallback
slide._resolved_asset = {"kind": "none", "reason": "no asset hint or all sources failed"}
```

### Step 4 — Return enriched plan

Hand the slide plan back to `render-carousel` with `_resolved_asset` annotated on each slide. The render skill knows how to inline `kind: inline-svg` into the slide HTML and reference `kind: file` paths from `<img src>`.

---

## SVG helper library

Implemented in `scripts/svg_helpers.py`. Each helper has signature `(data: dict, brand: dict, width: int, height: int) -> str` and returns a complete `<svg>...</svg>`.

| Helper | Data shape | Notes |
|---|---|---|
| `bar_chart` | `{"items": [{"label","value"},...]}` | horizontal bars, alternates accent / accent_secondary |
| `donut` | `{"value": 0..100, "label": "of users"}` | single-value progress donut |
| `compare` | `{"left": {"title","items":[]}, "right": {"title","items":[]}}` | left/right vs. layout |
| `quote_mark` | `{"size": "lg"}` | decorative quotation mark, accent fill |
| `divider` | `{"style": "line"\|"dots"\|"gradient"}` | section divider |
| `timeline` | `{"events": [{"date","label"},...]}` | horizontal events |
| `funnel` | `{"stages": [{"label","value"},...]}` | top-down narrowing |
| `pyramid` | `{"levels": [{"label"},...]}` | hierarchy 3 to 5 levels |
| `progress_steps` | `{"steps": [{"label"},...], "current": N}` | numbered bullets, accent on current |
| `icon_grid` | `{"icons": [{"name","label"},...], "cols": 2\|3}` | 10 built-in icons |
| `callout_arrow` | `{"target": "value", "label": "..."}` | arrow + label |
| `checklist` | `{"items": ["..."]}` | brand-colored ✓ list |
| `comparison_table` | `{"header":[], "rows":[[]]}` | small table, max 4 cols × 5 rows |
| `wave_decoration` | `{"variant": "top"\|"bottom"}` | background flourish |
| `number_badge` | `{"number": "42%", "label": "..."}` | big number with halo |

CLI for debugging:

```bash
python scripts/svg_helpers.py bar_chart \
    --data '{"items":[{"label":"A","value":40},{"label":"B","value":80}]}' \
    --brand '{"accent":"#5b8def","accent_secondary":"#2a4a99","text_primary":"#111"}' \
    --width 800 --height 400 > out.svg
```

---

## Bespoke inline SVG (when no helper fits)

Helpers cover ~80% of common carousel visuals. For the rest, **author SVG inline** in the slide spec under `svg_inline`. Pattern:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" role="img" aria-hidden="true">
  <rect x="40" y="40" width="720" height="320" fill="var(--card-bg)" stroke="var(--card-border)"/>
  <text x="400" y="200" text-anchor="middle" fill="var(--accent)"
        font-family="var(--font-heading)" font-size="48">42%</text>
</svg>
```

Rules:
- Use `var(--accent)`, `var(--accent-secondary)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--card-bg)`, `var(--card-border)`. Never hardcode hex (`#0b3d91`).
- `viewBox` mandatory. Skip `width`/`height` attrs so CSS can scale to slide width.
- No `<foreignObject>` (breaks PDF), no `<script>`, no `<style>`.
- One `<svg>` per slide. Keep total markup under ~80 lines.
- If the pattern is reusable, **promote it to a helper in `svg_helpers.py`** and document in `references/svg-patterns.md`.

---

## fal AI integration

Single opt-in: env var `FAL_API_KEY` or `FAL_KEY` set. Per-project config controls model and budget:

```json
{
  "fal_model": "fal-ai/nano-banana-pro",
  "fal_max_images": 3
}
```

Models supported by `scripts/generate_image.py`:

| Model | Cost | Notes |
|---|---|---|
| `fal-ai/nano-banana-pro` (default) | $0.15 fixed | Google Gemini 3 Pro Image. Strong text rendering, brand-consistent visuals. |
| `openai/gpt-image-2` | ~$0.053 medium | OpenAI gpt-image-2, 1024x1024 or 1024x1536. |
| `fal-ai/flux/schnell` | ~$0.003 | Cheap, fast, lower quality. |
| `fal-ai/flux/dev` | ~$0.025 | Higher quality flux variant. |

The skill always:
1. Builds a brand-aware prompt suffix (colors + tone + `no text overlay, no watermark`).
2. Submits to the fal queue, polls until done.
3. Downloads result, runs through Pillow (max 1500px long edge, JPEG q=85).
4. Writes to `<output_dir>/images/slide-NN.jpg`.

Failure (network, API error, timeout) is **non-fatal**: warn, fall through to text-only.

Cost guard: at most `fal_max_images` calls per run. Default `3` × default model `$0.15` = **$0.45 max per run**.

---

## User image source

Two paths accepted: local filesystem (absolute or relative to project root) and HTTPS URLs.

The script `scripts/copy_user_images.py`:
- Resolves and downloads if needed.
- Optimizes via Pillow: max 1500px long edge, JPEG q=85, EXIF stripped.
- Converts HEIC if `pillow-heif` is installed (falls back to error message otherwise).
- Hard cap: 5 images per run (above the cap → skip with warning).

Output path pattern: `<output_dir>/images/slide-NN.jpg`. The render skill references it as `<img src="images/slide-NN.jpg">`.

---

## Outputs

The skill returns the slide plan with each slide annotated:

```json
{
  "_resolved_asset": {
    "kind": "file" | "inline-svg" | "none",
    "path": "images/slide-04.jpg",   // when kind == "file"
    "html": "<svg>...</svg>",         // when kind == "inline-svg"
    "alt": "...",                     // when kind == "file"
    "source": "user_image" | "svg_helper" | "bespoke" | "fal_ai",
    "reason": "..."                    // when kind == "none"
  }
}
```

It also writes a small audit log to `<output_dir>/asset-resolution-<YYYYMMDD>.json` so the final report can show which sources were used.

---

## Tools used

- `Read` / `read_file`: load `slide_plan.json`, `project-context/brand.json`, `config.json`.
- `Bash` / `run_bash_command`: invoke `copy_user_images.py`, `generate_image.py`, `svg_helpers.py`.
- `Write` / `create_or_rewrite_file`: write the audit log; the slide plan stays in memory and is passed to render-carousel.

---

## Error handling

| Situation | Action |
|---|---|
| User image path missing | Log warning, fall through to next source |
| Remote URL 404 | Log warning, fall through |
| HEIC file but `pillow-heif` not installed | Log warning with install hint, fall through |
| Helper name unknown | Log warning, fall through |
| Bespoke `svg_inline` malformed | Skip, fall through, do not crash |
| `FAL_API_KEY` set but invalid | First call returns rc=3, log warning, set fal_budget=0 to skip remaining |
| fal queue timeout (>120s) | Log warning, fall through |
| All sources fail for a slide | Mark `kind: none`, render-carousel renders text-only template |

The skill never raises. Worst case: every slide is `kind: none`, run continues, report flags it.

---

## Why this design

- **Single resolver = one place to debug.** Render-carousel does not need to know about fal or user images.
- **Priority order is opinionated.** User > vector > AI is the right call for editorial carousels: predictable, brand-consistent, anti-slop.
- **Single fal opt-in.** No accidental spend: if the env var is unset, no AI calls happen, no warnings, no degraded output.
- **Helpers + bespoke SVG = best of both.** 15 helpers cover common cases; bespoke SVG is the escape hatch when content needs something the library cannot express.
- **Hard caps mean predictable cost** ($0.45 max per run with defaults).
