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

This agent uses `firecrawl` (brand DOM/CSS + business page scrape) and optionally `exa` (broad business enrichment). Both degrade cleanly when their key is missing.

## API docs

- firecrawl scrape API: https://docs.firecrawl.dev/api-reference/endpoint/scrape
- Playwright (Python): https://playwright.dev/python/docs/intro
- Pillow (palette / preview render): https://pillow.readthedocs.io

## Inspiration / prior art

- Brand extraction methodology originated in `agents/carousel-builder/skills/extract-brand` and now lives here as the single owner. carousel-builder and static-ads-builder read the resulting `brand.json` instead of re-extracting.
- The shared-context design is documented in `eng/PLAN_PROJECT_CONTEXT_2026-06-04.md` and its consumer `eng/PLAN_STATIC_ADS_BUILDER_2026-06-04.md`.
