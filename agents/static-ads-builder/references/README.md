# References

External docs and links the agent depends on.

## cli-skills (the toolbelt)

Public, MIT-licensed.
Repo: https://github.com/the20100/cli-skills

Available CLIs (as of 2026-04):

| CLI | Purpose | Env vars |
|-----|---------|----------|
| `exa` | Semantic web search (Reddit, X, forums, blogs) | `EXA_API_KEY` |
| `firecrawl` | URL → clean markdown, SERP scrape | `FIRECRAWL_API_KEY` |
| `perplexity` | Research with citations | `PERPLEXITY_API_KEY` |
| `g-search-console-cli` | Google Search Console queries | OAuth (see CLI README) |
| `g-indexing-cli` | Google Indexing API | OAuth |
| `instantly` | Cold email sequences (Instantly.ai) | `INSTANTLY_API_KEY` |
| `meta-ads-cli` | Meta Ads reporting | Meta token |
| `gads-cli` | Google Ads reporting | Google Ads OAuth |

Always link to the specific CLI's README inside `cli-skills/` for setup details.

## Approved free-tier APIs (beyond cli-skills)

Only established APIs with generous free tiers are allowed. Add new ones here when the agent needs them.

| API | Purpose | Free tier | Env var |
|-----|---------|-----------|---------|
| SERPER.dev | SERP scrape, AI Overviews data | 2500 queries/mo | `SERPER_API_KEY` |

No paid SaaS in agent workflows or recommendations (no Profound, Scrunch, Frase, Clay, Apollo, Lemlist).

This agent uses `firecrawl` (product reference-image scraping) and optionally `exa`/`firecrawl` (angle enrichment). Both degrade cleanly when their key is missing.

## Image generation: fal.ai

The render step calls the fal.ai HTTP **queue** API directly (no fal CLI, no `fal-client` dependency), wrapped in `scripts/render_ads.py`. The local product reference is sent inline as a base64 data URI, so there is no upload step.

- fal queue API (submit / status / result): https://docs.fal.ai/model-endpoints/queue
- Models the menu exposes (verify pricing and input schema against the live model page before trusting the bundled table):
  - `fal-ai/nano-banana-2` (default)
  - `openai/gpt-image-2` (`quality`: medium | high)
  - `fal-ai/nano-banana-pro` (higher-fidelity fallback)
- `FAL_API_KEY` (or `FAL_KEY`) auth, required only at render time.

The pricing table that drives Gate 2 lives in `scripts/render_ads.py` (`PRICING`). It is the single source of truth for cost; update it there when fal prices change.

## Approved free-tier APIs used here

| API | Purpose | Free tier | Env var |
|-----|---------|-----------|---------|
| firecrawl | Product reference-image scrape | per cli-skills | `FIRECRAWL_API_KEY` |

## Inspiration / prior art

- Brief generation and the funnel-aware angle library originate in the private `agent-creative-briefs` agent; image rendering originates in `agent-image-generation`. static-ads-builder fuses both into one flow and adds the two spend gates.
- Brand tokens are produced by `project-context` (`extract-brand`); this agent only reads `brand.json`.
