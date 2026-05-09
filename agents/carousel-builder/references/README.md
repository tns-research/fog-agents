# references/

External docs and prior art consulted while building `carousel-builder`. Not dependencies — pointers for contributors who want context.

## CLI references
- `cli-skills` repo: https://github.com/the20100/cli-skills (firecrawl, exa, gsc, perplexity, instantly).
- `firecrawl` is the only CLI dependency in V1, and only for the optional `extract-brand` skill.

## Playwright (Python)
- Docs: https://playwright.dev/python/
- Webfont gotcha: must `await page.wait_for_load_state("networkidle")` AND `await page.evaluate("document.fonts.ready")` before screenshot. Already burned us in `agent-cro-heuristic`, well-known.
- Lock to `chromium` only. Firefox / WebKit add ~400 MB without benefit.

## img2pdf
- Docs: https://gitlab.mister-muffin.de/josch/img2pdf
- Lossless PNG to PDF assembly, preserves DPI. ~1 MB install, no system deps.

## fal AI
- Docs: https://fal.ai/docs
- Optional. Single opt-in: presence of `FAL_API_KEY` (or `FAL_KEY`) env var. No second config flag.
- Default model: `fal-ai/nano-banana-pro` ($0.15 fixed). Alternative: `openai/gpt-image-2` (~$0.053).
- Hard cap per run: `fal_max_images` (default 3). Max bill: ~$0.45 with defaults.
- Falls back gracefully to user images / SVG / text-only if key missing or call fails.

## SVG patterns
- See `references/svg-patterns.md` for the bespoke inline-SVG patterns the agent has used in real runs. Promote any reusable pattern to `scripts/svg_helpers.py`.

## Anthropic Agent Skills (spec for SKILL.md frontmatter)
- Spec: https://agentskills.io/specification
- All `SKILL.md` files in this agent comply with the spec (frontmatter fields, naming rules, ≤500 lines body).

## Prior art / inspirations
- `portable-agents/agent-social-slides/` (Zo-first prior art, copied structure liberally).
- Anthropic skills `frontend-design` (anti-AI-slop HTML aesthetic).
- Anthropic skills `pdf` (assembly post-render).
- `FranciscoMoretti/carousel-generator` (visual reference for slide layouts).

## Manual Canva handoff (V1 alternative to integration)
- Canva Connect API REST: https://www.canva.dev/docs/connect/
- Canva MCP: https://www.canva.dev/docs/mcp/ (intentionally not used in V1; see `eng/PLAN_CAROUSEL_AGENT_2026-05-08.md` for rationale).

## Platform specs (LinkedIn, Instagram)
- LinkedIn document post sizes: 1:1 or 4:5, max 300 pages, 100 MB.
- Instagram carousel: max 20 images (raised from 10 in 2024), 1080x1080 or 1080x1350.
- X has no native carousel format in 2026 — out of V1 scope.
