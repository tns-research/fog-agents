---
name: project-context
description: The entry door of the founders OS. Turns a URL plus a short Q&A into a shared context folder (brand identity + business context) written into the founder's project, then reused by every other agent in the stack. Configure once, read everywhere.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# project-context

This is the **entry door** of the Founders Growth Agent Stack. A founder configures their brand and business context **once** here, and every other agent (market-signal, static-ads-builder, carousel-builder, ...) reads the same shared folder instead of re-asking the same questions.

It produces two stable artifacts in the founder's project:

- **brand.json**, the visual identity (colors, fonts, logo) **plus a manifest of real assets harvested from the site** (logo, og:image, favicon, largest product/hero images), so the creative agents build from the founder's own material, not lookalikes.
- **context.json** + **context.md**, the business context (what it is, ICP, offer, positioning, proof, voice).

Golden rule for the whole stack: **shared context is an accelerator, never a hard gate.** Every other agent still runs standalone if this folder is absent. This agent's only job is to make that folder good, so the rest of the stack gets faster and more consistent.

---

## Step 0: context resolution

1. Resolve the **project slug** (from the user, or infer from the URL domain, e.g. `acme.com` -> `acme`). If ambiguous, ask once.
2. Compute the shared folder path: `<your-projects-root>/<project-slug>/project-context/`. Ask the user for their projects root if not already known; never hard-code one.
3. If `project-context/` already exists with a `context.json` and/or `brand.json`, this is an **update run**: load both, show the user what is on file, and ask whether to (a) edit specific fields, (b) re-extract brand from URL, or (c) rebuild context from scratch. Do not silently overwrite.
4. If it does not exist, this is a **fresh run**: copy `config.example.json` into the folder as `config.json`, fill missing values from chat (URL, language, web_enrichment), then proceed.
5. Do not proceed past Step 0 until the slug and folder path are resolved.

---

## When to run

Run this **first**, before any other agent in the stack, the very first time a founder sets up a project. Re-run it whenever the brand changes (rebrand, new logo) or the business pivots (new ICP, new offer). One run configures the whole OS.

---

## Inputs needed

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `project_slug` | yes | inferred from URL | Names the shared folder. |
| `url` | optional, recommended | none | Triggers brand extraction and business enrichment. Without it, everything comes from the Q&A. |
| `web_enrichment` | optional | `auto` | `off` / `exa` / `firecrawl` / `auto`. Pre-fills the business Q&A from product/about/pricing pages. Degrades cleanly with no key. |
| `language` | optional | `en` | Language of `context.md` and the `voice.language` field. |

Environment (all optional, the agent degrades without them):

- `FIRECRAWL_API_KEY`, DOM/CSS brand signal + business page scrape.
- `EXA_API_KEY`, broad business enrichment.

---

## Workflow

1. **Resolve project + create folder.** Finish Step 0. Create `<project-root>/<project-slug>/project-context/` and `project-context/assets/`.
2. **Extract brand + harvest assets (if `url` present).** Load `skills/extract-brand/SKILL.md`. Run `scripts/extract_brand.py`: it reads the accent from the primary CTA button (solid bg or the vivid stop of a gradient) and **downloads the real assets** (logo incl. inline SVG, og:image, favicon, largest product/hero images) to `assets/` up front. Render a self-contained preview card (color swatches + harvested-asset contact strip), then run the **brand checkpoint** validation loop. Writes `brand.json` (tokens + assets manifest) only after approval. If no URL, ask 2-3 inline brand questions (primary color, accent, logo path) or skip.
3. **Build business context.** Load `skills/build-context/SKILL.md`. Optionally pre-fill from `scripts/enrich_context.py` (web_enrichment), then run the structured Q&A (one_liner, ICP, offer, positioning, proof, voice). Fill `assets/context-template.md`.
4. **Context checkpoint.** Present the filled `context.md` for review. The user corrects in chat or edits the file directly. Loop until approved. Validate the JSON against `assets/context-schema.json`.
5. **Write artifacts.** Write `context.json` (machine) + `context.md` (human) + `brand.json` into `project-context/`. Confirm the logo file path resolves.
6. **Hand off.** Tell the user the folder is ready and which agents will now read it automatically. Remind them they can edit any file by hand at any time.

---

## Output format

See `assets/context-template.md` for the `context.md` skeleton and `assets/context-schema.json` for the `context.json` contract. The folder produced in the founder's project:

```
<project-root>/<project-slug>/project-context/
├── context.json          # machine-readable business context
├── context.md            # human-readable business context (same info, prose)
├── brand.json            # colors, fonts, logo_path + assets manifest
├── assets/
│   ├── logo.svg|png       # downloaded logo (incl. serialized inline SVG)
│   └── site/              # harvested creative source material
│       ├── og-image.jpg   # og:image share card
│       ├── favicon.png
│       ├── asset-01.jpg … # largest on-page product/hero images
│       └── manifest.json  # path/source/dims/alt for every harvested file
└── brand-debug/          # homepage.png, header-crop.png, brand-preview.png, firecrawl.json
```

---

## Output location

```
<your-projects-root>/<project-slug>/project-context/
```

This is a **sibling** of the per-agent deliverable folders (`market-signal/`, `carousel-builder/`, ...), not a child of any agent folder. It lives in the founder's project, never in the fog-agents repo. It is a data convention: other agents point at this **data** folder in the user's project, exactly as they already write into `<project-root>/<project-slug>/<agent>/`.

---

## Failure modes

- **No URL provided** -> skip brand extraction's heavy path; ask 2-3 inline brand questions and build context from the Q&A alone. Still produces a valid folder.
- **`FIRECRAWL_API_KEY` missing** -> brand extraction runs screenshot-only (lower confidence, warned); enrichment falls back to Q&A only.
- **No web-enrichment key at all** -> `web_enrichment` is treated as `off`; the Q&A carries the full load. Never error.
- **Brand extraction low confidence across all tokens** -> do not auto-write; tell the user, ask them to enter colors/logo manually.
- **User wants to skip brand entirely** -> write `context.json`/`context.md` only; consumers fall back to their inline brand path.
- **Folder already exists** -> treat as an update run (Step 0.3); never overwrite without asking.
- **Robots.txt disallows the homepage** -> `extract_brand.py` aborts with a clear message; ask the user for colors/logo manually.
