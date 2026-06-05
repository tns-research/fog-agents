---
name: static-ads-builder
description: Turns a founder's project context into a batch of Meta static-ad creatives, end to end. Plans funnel-aware concepts, writes image-generation-ready JSON briefs, then renders the selected ones on fal.ai. Two hard human gates protect every dollar of spend, brief selection and model+budget confirmation. Reads project-context when present, runs standalone otherwise.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# static-ads-builder

One agent for the whole static-ad pipeline: **strategy -> briefs -> images**. It fuses the two halves a founder used to run separately (concept/brief writing, then image rendering) into a single flow with a clean spend wall in the middle.

It produces, in the founder's project:

- **static-ads-briefs-YYYYMMDD.md** + **.json**, a pool of funnel-aware creative briefs (each a valid image-generation payload).
- **static-ads-YYYYMMDD.md** + the rendered **images/**, only for the briefs the founder explicitly selected and paid for.

Two rules sit above everything else in this agent:

1. **No fal spend without two human gates.** Gate 1 selects which briefs to render. Gate 2 confirms model, resolution, and budget. Neither can be skipped, and they cannot be collapsed into one "yes". A founder must know how many images, at what resolution, for how much, before a single request is sent.
2. **Shared context is an accelerator, never a hard gate.** If `project-context/` exists, the agent reads brand and business context from it and skips re-asking. If it is absent, the agent runs a short inline Q&A and still completes.

---

## Step 0: context resolution

1. Resolve the **project slug** (from the user, or infer from a URL domain). If ambiguous, ask once. Resolve the projects root (ask if unknown, never hard-code one).
2. Compute the agent folder: `<project-root>/<project-slug>/static-ads-builder/`. Create it if missing.
3. **Load shared context (accelerator).** Load `skills/resolve-project-context/SKILL.md`. If `<project-root>/<project-slug>/project-context/` exists, read `brand.json` (colors, fonts, logo) and `context.json` (product, ICP, offer, positioning, proof, `voice`). Inherit `voice.banned_words` and `voice.claims_policy` for all copy. If it is absent, ask 3-4 inline questions (what it is, who for, product name, primary color) and continue.
4. **Config.** If `static-ads-builder/config.json` does not exist, copy `config.example.json` into it. Read it. Resolve missing blocking values by asking once and writing back: `copy_language` (fr/en), `funnel_stages`. Resolve non-blocking values with defaults: `product`, `visual_style` (empty = auto-select), `web_enrichment` (default `off`), `num_briefs` (default 12, max 15), `default_model`, `default_resolution`.
5. Do not proceed past Step 0 until slug, folder, `copy_language`, and `funnel_stages` are resolved.

---

## When to run

Run it whenever a founder wants a fresh batch of static ad creatives for Meta. Ideally after `project-context` is configured (so brand and business context are reused), but it runs standalone if not. Re-run it for a new campaign, a new product, or a new funnel focus.

---

## Inputs needed

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `project_slug` | yes | inferred from URL/context | Names the agent folder. |
| `copy_language` | yes | ask once | `fr` / `en`. Language of on-ad copy. Image prompts are always English. |
| `funnel_stages` | yes | ask once | `all` / `tofu` / `mofu` / `bofu` / two-stage pairs. Distributes the briefs. |
| `product` | optional | from `context.json` or ask | Exact product name for the reference image. Empty = generic. |
| `visual_style` | optional | `""` (auto-select) | Slug from `skills/visual-styles/REGISTRY.md` to lock one style, or empty to auto-assign per brief. |
| `web_enrichment` | optional | `off` | `off` / `exa` / `firecrawl` / `auto`. Non-blocking angle discovery. |
| `num_briefs` | optional | `12` | Size of the brief pool (max 15). Gate 1 then selects a subset to render. |

Environment (all optional, the agent degrades without them):

- `FAL_API_KEY` (or `FAL_KEY`), required only at render time. Without it, the agent still writes briefs and stops cleanly before Gate 2.
- `FIRECRAWL_API_KEY`, reference-image scraping and optional web enrichment.
- `EXA_API_KEY`, optional web enrichment.

---

## Workflow

1. **Resolve context.** Finish Step 0. Load brand + business context via `skills/resolve-project-context/SKILL.md`. Resolve `copy_language`, `funnel_stages`, `product`, `visual_style`, `web_enrichment`, `num_briefs`.
2. **Optional web enrichment (non-blocking).** If `web_enrichment != off`, run `exa`/`firecrawl` for angle and hook discovery. On any failure, continue from local context and note the fallback. Never block.
3. **Plan concepts.** Load `skills/brief-strategy/SKILL.md`. Distribute `num_briefs` across the chosen funnel stages, assign a unique named angle per brief, and apply the visual diversity mandate and surprise test. Assign each brief a visual style (lock or auto-select) from `skills/visual-styles/`.
4. **Write briefs.** Load `skills/brief-json/SKILL.md`. For each concept, emit one valid JSON payload (`image_prompt`, `headline`, `subheadline`, `typography`, and `reference_assets` only when one of the founder's real assets - product, screenshot, logo, or hero - is on the creative). Apply `voice.claims_policy` and `voice.banned_words`. Write `static-ads-briefs-YYYYMMDD.md` (human, with rationale) and `static-ads-briefs-YYYYMMDD.json` (machine). Validate the JSON with `scripts/validate_briefs.py`; fix any error before continuing.
5. **Gate 1 - brief selection (BLOCKING).** Present the pool with one-line summaries (number, funnel stage, angle, which assets it uses). Ask which to render. Default suggestion is **10**; the founder may pick any subset from **5 to 15**. Record the selected indices. No selection, no render. Do not proceed on a vague "looks good", get an explicit set.
6. **Resolve reference assets.** Load `skills/resolve-reference-assets/SKILL.md`. For each **selected** brief, resolve every role in `reference_assets` to a local file (logo/screenshot/hero from `brand.json` assets; product from user path -> project-context asset -> firecrawl scrape -> ask) and write the ordered `_ref_paths` list into the brief. Dedupe shared assets (logo, screenshot) across briefs. A brief that declared assets but resolved **none** is flagged `SKIPPED_REF_MISSING` and excluded from the spend estimate; if some-but-not-all resolved, it renders with what resolved.
7. **Gate 2 - model + resolution + budget (BLOCKING).** Load `skills/render-fal/SKILL.md`. Run `scripts/render_ads.py --estimate` for the menu and cost. Present: the model menu (`fal-ai/nano-banana-2` default, `openai/gpt-image-2`, `fal-ai/nano-banana-pro` fallback), the resolution choice (1K / 2K / 4K, **the main cost lever**), the count of renderable briefs, and the **total estimated spend**. The founder confirms model + resolution + spend in one explicit answer. No confirmation, no render.
8. **Render.** Run `scripts/render_ads.py --batch` over the confirmed selection with the confirmed model and resolution. Image-to-image when a reference exists, text-to-image otherwise. **One attempt per brief, no auto-retry.** Download each result locally.
9. **Package output.** Load `skills/package-output/SKILL.md`. Write `static-ads-YYYYMMDD.md` with per-brief records (brief, mode, model, resolution, local path, source URL, error) and the run state: `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED`. Report actual spend.

---

## Output format

Briefs follow `skills/brief-json/SKILL.md` (one JSON block per brief, rationale in markdown). The run report follows `assets/output-template.md`. The folder produced in the founder's project:

```
<project-root>/<project-slug>/static-ads-builder/
├── config.json
├── static-ads-briefs-YYYYMMDD.md     # brief pool, human-readable + rationale
├── static-ads-briefs-YYYYMMDD.json   # brief pool, machine-readable (render input)
├── static-ads-YYYYMMDD.md            # render run report (selected briefs only)
├── refs/                             # resolved reference assets (logo, screenshot, product, hero)
│   ├── logo-<slug>.png               # shared assets, deduped and reused across briefs
│   ├── screenshot-<slug>.png
│   └── NN-<product-slug>-ref.jpg     # per-brief physical product packshot
└── images/
    └── YYYYMMDD/
        └── NN-<brief-slug>.jpg       # one file per rendered brief
```

---

## Output location

```
<your-projects-root>/<project-slug>/static-ads-builder/
```

A sibling of `project-context/` and the other per-agent folders, inside the founder's project, never inside the fog-agents repo.

---

## Failure modes

- **No `project-context/` folder** -> run the short inline brand + business Q&A (Step 0.3); still produce briefs and renders.
- **`FAL_API_KEY` missing** -> write briefs, run Gate 1, then stop cleanly before Gate 2 with a one-line message ("set FAL_API_KEY to render"). Never error mid-batch.
- **Founder selects 0 briefs at Gate 1** -> stop after writing briefs; nothing is rendered. The brief file is the deliverable.
- **Reference image unresolved for a selected product brief** -> mark `SKIPPED_REF_MISSING`, exclude from the spend estimate, keep the rest.
- **A render fails mid-batch** -> log the exact error for that brief, continue with the rest, end as `PARTIAL_SUCCESS`. No auto-retry.
- **`web_enrichment` tool/key missing** -> treat as `off`; local context carries the run. Never block.
- **Product named but not found in `context.json`** -> ask the founder to confirm the exact name or proceed generic; never invent a catalog entry.
- **`voice.claims_policy` present** -> drop any metric or claim with no traceable source rather than inventing one.
