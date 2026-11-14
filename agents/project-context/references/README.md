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
| `meta-ads-cli` | Meta Ads reporting | Meta token |
| `gads-cli` | Google Ads reporting | Google Ads OAuth |

Always link to the specific CLI's README inside `cli-skills/` for setup details.

## Approved free-tier APIs (beyond cli-skills)

Only established APIs with generous free tiers are allowed. Add new ones here when the agent needs them.

| API | Purpose | Free tier | Env var |
|-----|---------|-----------|---------|
| SERPER.dev | SERP scrape, AI Overviews data | 2500 queries/mo | `SERPER_API_KEY` |

No paid SaaS in agent workflows or recommendations (no Profound, Scrunch, Frase, Clay, Apollo, Lemlist).

This agent needs no key. Capabilities and their providers (full catalog: [`../../../shared/tools.md`](../../../shared/tools.md)):

| Capability | Default provider | Keyless fallback |
|------------|------------------|------------------|
| `screenshot` | local Playwright (`scripts/extract_brand.py`) | founder gives colors and logo in chat |
| `scrape` | Jina Reader (https://jina.ai/reader, keyless) for the business pages; Firecrawl, Exa or a keyed Jina only with `--confirm-spend` | plain HTTP |
| `web_search` | Exa (optional broad enrichment) | host built-in search, or skipped |

The founder's choices live in `project-context/tools.json` (template: [`../../../shared/tools.example.json`](../../../shared/tools.example.json)).

## API docs

- firecrawl scrape API: https://docs.firecrawl.dev/api-reference/endpoint/scrape
- Jina Reader: https://jina.ai/reader (`https://r.jina.ai/<url>`, works without a key)
- Playwright (Python): https://playwright.dev/python/docs/intro
- Pillow (pixel sampling, logo tests, brand board): https://pillow.readthedocs.io

## Inspiration / prior art

- Brand extraction lives here as the single owner. carousel-builder and static-ads-builder read the resulting `brand.json` instead of re-extracting.
