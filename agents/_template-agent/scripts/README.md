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

(Add one section per bundled script when this is forked.)

### `<script-name>.py`

- Inputs: `<args>`
- Outputs: `<files>`
- Install: `pip install -r requirements.txt && playwright install chromium` (if Playwright)
- Usage: `python scripts/<script-name>.py --url https://...`

## Cross-platform notes

If a script needs to spawn subprocesses, use `subprocess.run([...])` with a list, not a shell string. Quote paths with spaces. Never assume `bash` is the user's shell.
