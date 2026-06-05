# scripts/

Bundled tools for the agent. Use this folder only when the work cannot be done by piping `cli-skills` CLIs (`exa`, `firecrawl`, `gsc`, `perplexity`, `instantly`).

Legitimate uses:

- Browser automation (Playwright capture, screenshot stitching)
- CSV / JSON transformations (reshape, dedupe, join)
- Custom scoring formulas applied at scale
- API quota juggling, batched fetch with retry

Not for: things `firecrawl` / `exa` / `gsc` / `perplexity` already do.

## Conventions

- **Python preferred** (matches the broader ecosystem we lift patterns from).
- Forward slashes only. No Windows-specific path handling.
- No magic numbers. Every constant documented inline.
- Handle errors explicitly (return defaults or specific error messages, never silently `pass`).
- Each script ships with `requirements.txt` (or equivalent) and an entry in this README.

## Script inventory

Standard library only, no install step: `python --version` >= 3.9 is enough. `requirements.txt` documents that there is no third-party dependency.

### `render_ads.py`

The render engine **and** the budget gate, in one file. The pricing table inside it is the single source of truth for cost.

- **Estimate (Gate 2, no API call, no key):**
  `python scripts/render_ads.py --estimate --count <N> --model <id> --resolution <1K|2K|4K> [--quality medium|high]`
  Prints per-image price and total for the founder to confirm before any spend.
- **Batch render (after Gate 2):**
  `python scripts/render_ads.py --batch <briefs.json> --select "1,2,4,7-10" --out <images/YYYYMMDD> --model <id> --resolution <res> [--refs-dir <refs>] [--ratio 4:5|1:1]`
  Image-to-image when a brief has resolved reference assets (its `_ref_paths` list, or a `NN-` file in `--refs-dir` as fallback), attaching all of them; text-to-image otherwise. The script SHELLS the `fal` CLI (it owns endpoint routing, submit, polling, result extraction); each local reference is first uploaded to fal storage so the model receives a short URL, never a data URI on the command line.
- **Models:** `fal-ai/nano-banana-2` (default), `openai/gpt-image-2` (`--quality`), `fal-ai/nano-banana-pro` (fallback).
- **One attempt per brief, no auto-retry.** Prints a JSON run summary on stdout (`run_state`, per-brief records, actual spend).
- **Exit codes:** `0` ok, `2` no `FAL_API_KEY`/`FAL_KEY` (batch), `3` bad input or the `fal` CLI is not on PATH.

### `validate_briefs.py`

Structural guard run before Gate 2, so a malformed brief never wastes a render.

- Inputs: `python scripts/validate_briefs.py <briefs.json>`
- Checks: valid JSON array, required fields, no conditional language in `image_prompt`, `reference_assets` shape/role/instruction + attach consistency, logo-redraw guard, duplicate angle (`_concept`) detection.
- Exit codes: `0` valid (warnings on stderr), `3` invalid (errors on stderr; fix before rendering).

## Cross-platform notes

If a script needs to spawn subprocesses, use `subprocess.run([...])` with a list, not a shell string. Quote paths with spaces. Never assume `bash` is the user's shell.
