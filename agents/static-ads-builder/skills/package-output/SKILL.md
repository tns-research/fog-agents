---
name: package-output
description: Assemble the render run report for static-ads-builder. Writes static-ads-YYYYMMDD.md with one record per rendered brief (mode, model, resolution, local path, source URL, error), the run state (SUCCESS/PARTIAL_SUCCESS/FAILED), and the actual spend. Use as the final step after rendering. Triggers: "write the report", "summarize the run", "what did we render".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# Skill: package-output

Close the run with a single human-readable report that a founder can scan in ten seconds and an honest record of what was generated, skipped, and spent.

---

## When to load

- Workflow Step 9 of `static-ads-builder`, after `render-fal` returns the per-brief records.

---

## What to write

File: `<project-root>/<project-slug>/static-ads-builder/static-ads-YYYYMMDD.md`, following `assets/output-template.md`.

Header (metadata block):
- Project, date, copy_language, funnel_stages.
- Brief pool size and the **selected** count.
- Model, resolution, run state.
- **Estimated spend** (from Gate 2) and **actual spend** (renderable briefs * per-image price). Note any gap (e.g. skipped briefs).

`## Summary`: one or two sentences, the run state first, then the headline number (e.g. "9 of 10 rendered, 1 skipped for a missing reference, about $0.72 on nano-banana-2 at 1K").

`## Rendered briefs`: a table, one row per selected brief:

| # | Concept | Stage | Mode | Model | Res | Status | File | Source |
|---|---------|-------|------|-------|-----|--------|------|--------|
| 1 | ... | TOFU | text-to-image | nano-banana-2 | 1K | OK | images/YYYYMMDD/01-...jpg | - |
| 3 | ... | MOFU | image-to-image | nano-banana-2 | 1K | OK | images/YYYYMMDD/03-...jpg | refs/03-...-ref.jpg |
| 7 | ... | BOFU | image-to-image | nano-banana-2 | 1K | SKIPPED_REF_MISSING | - | - |

`## Spend`: estimated vs actual, per-image price, model + resolution. Be exact.

`## Not rendered`: briefs from the pool the founder did not select (just numbers + concept names), so they can render them later without regenerating.

`## Limitations`: failures with their exact error, references that could not be resolved, anything degraded (no web enrichment, no project-context). Honest.

End with the standard generation footer.

---

## Rules

- The deliverable folder is the founder's, never the repo. Paths in the report are relative to the `static-ads-builder/` folder for readability.
- Do not claim success for a brief whose file is missing or empty. If `render-fal` flagged it, it stays flagged here.
- Keep the unselected briefs listed so the pool stays reusable, the founder paid (in time) to generate them; do not bury them.
- Report `voice.claims_policy` enforcement if any claim was dropped during brief writing (one line, so the founder knows why a metric they expected is absent).

---

## References

- Report skeleton: `assets/output-template.md`
