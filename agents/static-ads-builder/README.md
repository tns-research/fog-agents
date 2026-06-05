# static-ads-builder

**One agent, the whole static-ad pipeline: strategy -> briefs -> images.** It plans funnel-aware Meta ad concepts, writes them as render-ready JSON, and generates the ones you choose on fal.ai, with two human gates in the middle so you never spend a cent by accident.

## What it produces

In your project:

```
<your-projects-root>/<project-slug>/static-ads-builder/
├── static-ads-briefs-YYYYMMDD.md     # the brief pool, with rationale
├── static-ads-briefs-YYYYMMDD.json   # the same, machine-readable (render input)
├── static-ads-YYYYMMDD.md            # render run report (selected briefs only)
├── refs/                             # resolved reference assets (logo, screenshot, product, hero)
└── images/YYYYMMDD/                  # the rendered creatives, one per brief
```

## The two gates (why this agent is safe to run)

No fal spend happens without two explicit confirmations, and they cannot be merged into one "yes":

1. **Gate 1, brief selection.** You see the whole pool and pick which to render. Default suggestion is 10; you can choose any subset from 5 to 15.
2. **Gate 2, model + resolution + budget.** You confirm the model, the resolution, and the total spend. The agent shows you "N images on <model> at <resolution> = about $X" before a single request is sent. Resolution is the main cost lever.

Models (newest first): `fal-ai/nano-banana-2` (default, best price/quality), `openai/gpt-image-2`, `fal-ai/nano-banana-pro` (higher-fidelity fallback).

## When to run it

- After `project-context` is set, so brand and business context are reused automatically.
- For a fresh campaign, a new product, or a new funnel focus.
- It also runs standalone: with no `project-context/`, it asks 3-4 quick questions and still completes.

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| project slug | yes | inferred | names the agent folder |
| `copy_language` | yes | ask once | `fr`/`en`, on-ad copy language (prompts are always English) |
| `funnel_stages` | yes | ask once | `all`/`tofu`/`mofu`/`bofu`/pairs, distributes the pool |
| `product` | optional | from context.json | exact product name for the reference image |
| `visual_style` | optional | auto-select | lock one style slug, or empty to auto-assign per brief |
| `web_enrichment` | optional | `off` | `off`/`exa`/`firecrawl`/`auto`, non-blocking angle discovery |
| `num_briefs` | optional | `12` | size of the brief pool (max 15) |

## Prerequisites

```bash
# Install once, reuse across all agents in this stack
git clone https://github.com/the20100/cli-skills.git ~/cli-skills

# Add the CLIs this agent can use to your PATH
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$PATH"
export PATH="$HOME/cli-skills/exa-cli/bin:$PATH"

# Keys
export FAL_API_KEY="..."         # required only at render time (Gate 2 onward)
export FIRECRAWL_API_KEY="..."   # reference-image scraping + optional enrichment
export EXA_API_KEY="..."         # optional angle enrichment
```

The render and validation scripts use the Python standard library only, no install step:

```bash
python --version   # 3.9+ is enough; no pip install needed
```

## Run it

### Claude Code

```
Run the static-ads-builder agent at agents/static-ads-builder/AGENT_STATIC_ADS_BUILDER.md.
Project: acme   copy_language: fr   funnel_stages: all
```

### Cursor / Codex CLI / Gemini CLI

Open `agents/static-ads-builder/AGENT_STATIC_ADS_BUILDER.md` as the system prompt for a fresh session, then:

```
Follow this workflow. Project: acme  copy_language: fr  funnel_stages: all
```

## How it works

1. **Resolve context.** Reads `project-context/brand.json` + `context.json` if present (colors, fonts, product, ICP, offer, positioning, voice). Inherits `voice.banned_words` and `voice.claims_policy`.
2. **Plan + write briefs.** Funnel-aware concepts (one named angle each), visual diversity mandate, surprise test, then one valid JSON payload per brief. Validated by `scripts/validate_briefs.py` before any spend.
3. **Gate 1.** You select which briefs to render.
4. **Resolve references.** For each selected brief, resolves every asset it asked for - logo, product UI screenshot, hero, or a physical product packshot - to a local file (logo/screenshot/hero from your `brand.json` assets; product from your path -> project-context asset -> firecrawl -> ask). Shared assets like the logo are fetched once and reused. A SaaS with no packshot still ships creatives built from its real logo and UI.
5. **Gate 2.** You confirm model, resolution, and budget (`scripts/render_ads.py --estimate`).
6. **Render.** `scripts/render_ads.py --batch`, image-to-image (attaching every resolved asset) when a brief uses real material, text-to-image otherwise. One attempt per brief, no auto-retry.
7. **Report.** A run report with per-brief status, the actual spend, and the briefs you did not render (so the pool stays reusable).

## Notes

- This agent **reads** `brand.json` from `project-context`; it does not extract brand itself. Run `project-context` first for a configured brand.
- It is the fusion of two earlier agents (creative-brief writing + fal image rendering) into a single flow with the spend gates added.
- Without `FAL_API_KEY`, it still writes the brief pool and stops cleanly before Gate 2.

## License

Apache 2.0 (matches the rest of the stack).
