# scripts/

Bundled tools for the agent. Use this folder only when the work cannot be done by piping the providers of [`shared/tools.md`](../../../shared/tools.md) (for example the `cli-skills` CLIs `exa`, `firecrawl`, `gsc`, `perplexity`, or the host's built-in search and fetch).

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
- **API calls are optional.** A script that calls an API reads the key from the environment (never a flag, never a file in the repo), offers `--provider` (or a fallback provider, `manual` when the capability is core to the agent), and exits with a one-line message and a documented exit code when no provider is usable. Never a stack trace for a missing key. Test `--help` and a no-key run before shipping.

## Script inventory

(Add one section per bundled script when this is forked.)

### `<script-name>.py`

- Inputs: `<args>`
- Outputs: `<files>`
- Install: `pip install -r requirements.txt && playwright install chromium` (if Playwright)
- Usage: `python scripts/<script-name>.py --url https://...`
- Capability and providers (if it calls an API): `<capability>`, `--provider <default|alternative|manual>`, key env var per provider
- Exit codes: `0` ok, `2` no usable provider (nothing sent), `3` bad input

## Cross-platform notes

If a script needs to spawn subprocesses, use `subprocess.run([...])` with a list, not a shell string. Quote paths with spaces. Never assume `bash` is the user's shell.
