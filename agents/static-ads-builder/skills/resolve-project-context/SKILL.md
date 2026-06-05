---
name: resolve-project-context
description: Load shared brand and business context for a project from the project-context folder, falling back to a short inline Q&A when it is absent. Reads brand.json (colors, fonts, logo) and context.json (product, ICP, offer, positioning, proof, voice) and exposes voice.banned_words and voice.claims_policy to every downstream copy step. Use at Step 0 of static-ads-builder. Triggers: "load my context", "use my brand", "what we sell".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read
---

# Skill: resolve-project-context

Make the rest of the run faster and more on-brand by reading the shared context once. This skill never writes; it only reads and reports what was found.

**Golden rule:** shared context is an accelerator, never a hard gate. A missing `project-context/` folder must never stop the run; it only means a slightly longer Step 0.

---

## When to load

- Step 0 of `static-ads-builder`, always, on every run.

---

## Procedure

1. **Locate the folder.** Look for `<project-root>/<project-slug>/project-context/`.
2. **If it exists, read both artifacts (defensively, never assume a field is present):**
   - `brand.json`: `bg`, `text_primary`, `accent`, `accent_secondary`, `font_heading`, `font_body`, `logo_path`, and the `assets` block (`assets.logo_path`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`) - the founder's real harvested material the creative is built from. Resolve every asset path against the **project root**, the same way `brand.json` writes them.
   - `context.json`: `one_liner`, `what_it_is`, `category`, `icp` (who/pains/jobs), `offer` (core/price_model/differentiators), `positioning` (against/promise/proof), `voice` (tone/language/`banned_words`/`claims_policy`).
3. **Carry forward into the run:**
   - Brand tokens -> default typography colors and the brand palette referenced in image prompts and the `typography` object.
   - `context.json.offer` + `positioning.proof` -> grounding for headlines and rationale. Every claim must trace to `proof` or be dropped (see policy below).
   - `voice.banned_words` -> a hard blacklist for all copy.
   - `voice.claims_policy` -> the anti-fabrication rule for all copy (default: "no invented stats, every metric must trace to a URL or be omitted").
   - `product` (if set in config or named in `offer`) -> the product name used in the `product` role of `reference_assets`.
   - `assets` -> the pool of real reference material (`logo`, `screenshot`, `og_image`, on-page `images`) that briefs declare via `reference_assets` and `resolve-reference-assets` turns into attached files. A SaaS or service with no physical packshot still has its logo and product screenshot here.
4. **If it does NOT exist, run a short inline Q&A (4 questions max), then continue:**
   - What is it (one line)? Who is it for? Exact product name (or "generic")? Primary brand color (hex, optional)?
   - Treat the answers as the minimal context. Default `voice.claims_policy` to "no invented stats, every metric must trace to a URL or be omitted" even with no folder.
5. **Report** in one line what was loaded ("Loaded brand.json + context.json from project-context" / "No project-context found, using inline answers") so the founder knows which path was taken.

---

## What this skill does NOT do

- It does not extract or re-derive brand colors from a URL. That is `project-context`'s `extract-brand` skill. If the founder wants a fresh brand pull, point them at `project-context`.
- It does not write any file.

---

## Failure modes

- **`brand.json` present but malformed** -> ignore it, fall back to the inline color question, warn once.
- **`context.json` present but missing `voice`** -> apply the default `claims_policy` and an empty `banned_words` list.
- **Neither file present** -> inline Q&A path (step 4). Never error.
