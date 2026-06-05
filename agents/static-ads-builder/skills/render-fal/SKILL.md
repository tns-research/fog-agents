---
name: render-fal
description: Render selected ad briefs on fal.ai through the fal CLI, behind two mandatory human gates. Gate 1 selects which briefs to render, Gate 2 confirms model, resolution, and total spend before a single request is sent. Drives scripts/render_ads.py for the estimate and the batch. One attempt per brief, no auto-retry. Use after briefs exist. Triggers: "render the ads", "generate the images", "spend on fal".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.1"
allowed-tools: Read Bash(python:*) Bash(fal:*) Bash(curl:*)
---

# Skill: render-fal

Render only what the founder explicitly chose and explicitly paid for. This skill owns the **two spend gates** and the call to `scripts/render_ads.py`.

`render_ads.py` shells the **`fal` CLI**, which owns the fal-specific work: routing references to the model's `/edit` endpoint, queue submit, polling, and result extraction. The script keeps only the founder-facing guardrails (pricing, the two gates, the batch loop, reference upload, naming, the run report). Requires the `fal` binary on PATH (install from `skills-cli/fal-cli`) and `FAL_KEY` (or `FAL_API_KEY`) in the environment. References are uploaded to fal storage first, so the model receives short URLs, never giant data URIs on the command line.

**The two gates are non-negotiable and cannot be merged into one answer.**

---

## When to load

- Workflow Steps 5, 7, and 8 of `static-ads-builder` (Gate 1, Gate 2, render).

---

## Gate 1 - brief selection (BLOCKING)

After the brief pool is written, present a compact list, one line per brief:

```
1  TOFU   Anti-Category 1.1       product: no
2  TOFU   Origin Number 1.4       product: yes
3  MOFU   Process Reveal 1.9      product: yes
...
```

Ask: **"Which briefs do you want to render? Default is 10. You can pick any subset from 5 to 15."**

Rules:
- Record explicit indices (e.g. "1, 2, 4, 7-10"). Do not proceed on "looks good" or "all of them" without confirming the resulting count.
- If the founder names a count rather than indices, suggest the strongest N from the pool and confirm.
- Enforce the range: **5 to 15** renderable briefs. If they ask for fewer than 5, confirm they understand it is a small batch; if more than 15, cap and explain.
- If they select 0, stop, the brief file is the deliverable. No render.

---

## Between the gates - resolve references

Run `resolve-reference-assets` for the selected product briefs. Any brief whose reference cannot be resolved is `SKIPPED_REF_MISSING` and is **excluded from the spend estimate** and the render.

---

## Gate 2 - model + resolution + budget (BLOCKING)

The founder must understand, before any spend: **which model, what resolution, how many images, for how much.** Resolution is the main cost lever, say so explicitly.

1. Get the menu and live estimate from the script (no API call):

```bash
python scripts/render_ads.py --estimate --count <N_renderable> --model <model> --resolution <1K|2K|4K>
```

2. Present the menu and the numbers:

**Model menu**

| Model | id | Notes |
|-------|----|-------|
| Nano Banana 2 (**default**) | `fal-ai/nano-banana-2` | Newest Google image model. Best price/quality. Default. |
| GPT Image 2 | `openai/gpt-image-2` | OpenAI. `medium` or `high` quality tier. Strong instruction following. |
| Nano Banana Pro (fallback) | `fal-ai/nano-banana-pro` | Higher-fidelity fallback. More expensive at 4K. |

**Resolution (the main cost lever)**

| Resolution | Use it for | Cost impact |
|------------|-----------|-------------|
| **1K** | Most feed ads, fast iteration, the default | Cheapest |
| **2K** | Crisper detail, larger placements | Middle |
| **4K** | Print, hero assets, heavy crops | Most expensive, can be 2-3x of 1K |

3. State the bottom line in one sentence: *"`<N>` images on `<model>` at `<resolution>` = about `$<total>` (`$<per_image>`/image)."* Pull these exact numbers from the script output.

4. Get an **explicit** confirmation of all three: model + resolution + spend. A bare "ok" to the briefs (Gate 1) does NOT carry over. If the founder wants to change model or resolution, re-run the estimate and re-present. No confirmation, no render.

---

## Render (after Gate 2)

```bash
python scripts/render_ads.py \
  --batch "<project-root>/<project-slug>/static-ads-builder/static-ads-briefs-YYYYMMDD.json" \
  --select "1,2,4,7,8,9,10" \
  --out "<project-root>/<project-slug>/static-ads-builder/images/YYYYMMDD" \
  --model fal-ai/nano-banana-2 \
  --resolution 1K \
  --refs-dir "<project-root>/<project-slug>/static-ads-builder/refs"
```

- `--select` is the confirmed Gate 1 indices (minus any `SKIPPED_REF_MISSING`).
- The script renders **image-to-image** when a brief has resolved reference assets (its `_ref_paths`, set by `resolve-reference-assets`; a matching `NN-` file in `--refs-dir` is the fallback). It uploads each reference to fal storage and attaches all of them on the model's `/edit` endpoint (nano-banana via `fal edit --image <url>`, gpt-image-2 via `fal run <endpoint>/edit`). **text-to-image** otherwise.
- **One attempt per brief. No auto-retry.** A failed brief is logged and skipped; the batch continues.
- Each result is downloaded to `images/YYYYMMDD/NN-<brief-slug>.jpg` and verified non-empty.

---

## Run state

Classify at the end:
- `SUCCESS`: every selected, renderable brief produced an image.
- `PARTIAL_SUCCESS`: at least one success and at least one failure/skip.
- `FAILED`: no images produced.

Hand the per-brief records (brief, mode, model, resolution, local path, source URL, error) and the actual spend to `package-output`.

---

## Failure modes

- **`fal` CLI missing on PATH** -> `render_ads.py` exits 3 before any request. Install it from `skills-cli/fal-cli`; the briefs are already saved.
- **`FAL_KEY` (or `FAL_API_KEY`) missing** -> `render_ads.py` exits 2 before any request. Tell the founder to set it; the briefs are already saved. Never error mid-batch.
- **A single render fails** (CLI non-zero exit, timeout, bad payload) -> log the exact error, mark the brief failed, continue. No retry.
- **Reference upload fails** for an image-to-image brief -> mark the brief failed, continue.
- **Reference file missing** for an image-to-image brief -> mark `SKIPPED_REF_MISSING`, continue.
- **Founder changes their mind at Gate 2** -> re-estimate, re-present; do not render on stale numbers.

---

## References

- Script + pricing table: `scripts/render_ads.py`, `scripts/README.md`
- fal CLI reference: `skills-cli/fal-cli/SKILL.md`
