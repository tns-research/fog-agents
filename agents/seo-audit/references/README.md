# References

## Providers

Every provider is optional. The full catalog, tiers and fallbacks are in [`../../../shared/tools.md`](../../../shared/tools.md); the founder picks theirs in `project-context/tools.json` or this agent's `config.json`.

| Capability | Default provider | Alternatives | Docs |
|------------|------------------|--------------|------|
| `search_console` | `gsc` CLI (Search Console API) | CSV export from the Search Console UI (no setup) | https://github.com/the20100/cli-skills/tree/main/g-search-console-cli |
| `serp` | Serper | SerpApi, Firecrawl scrape of the Google page, result URLs from host built-in search or pasted (`--organic-file`, degraded) | https://serper.dev, https://serpapi.com/search-api |
| `scrape` | Firecrawl | Jina Reader (keyless), `curl`, host web fetch | https://docs.firecrawl.dev/, https://jina.ai/reader |
| `ai_answers` | Perplexity API (`geo_panel.py run --provider perplexity`) | any answer-engine CLI (`--provider command`), manual capture (`geo_panel.py links`, `template`, `import`) | https://github.com/the20100/cli-skills/tree/main/perplexity-cli |

## APIs

- **Google Search Console API**: https://developers.google.com/webmaster-tools/v1/api_reference_index
- **Search Console performance export (manual CSV)**: https://support.google.com/webmasters/answer/7576553

## SEO references

- **Aleyda Solis**: *SEO audit framework* (technical + content + UX layers).
- **Lily Ray**: Google update analysis (https://twitter.com/lilyraynyc).
- **Marie Haynes**: E-E-A-T patterns and quality signals.
- **Ahrefs blog**: page decay diagnosis playbook.

## Concepts the agent uses

Every threshold below lives in one file, `assets/gsc-bands.json`, read by `scripts/gsc_bands.py`, `scripts/write_briefs.py` and `scripts/seo_state.py`. Skills and the report quote it; nothing else defines a band.

- **Decline** (queries and pages): clicks down at least 20 % vs the prior period, with at least 10 prior clicks; cause position, demand or CTR.
- **Quick win**: positions 4 to 20 with at least 50 impressions; opportunity = impressions x (position - 3).
- **CTR gap**: CTR under 0.75 x the site's own median CTR of its position bucket, never an outside CTR curve.
- **Lost**: in the top 20 in the prior period, out of it now.
- **Cannibalization**: two URLs or more of the site sharing a query's impressions (query x page rows only).
- **Artifact suspect**: deep position, stable rank, impressions falling: a measurement change until proven otherwise.
- **Tracking**: checkpoints at 14, 28 and 56 days after a ship date, N days after vs N days before.
- **Crawl issue codes**: `assets/crawl-rules.json`. **AI crawlers**: `assets/ai-crawlers.json`, each with its operator's documentation.
- **Intent gap**: the SERP top 10 covers a content type, depth or angle the site's page does not.
- **Impact x ease scoring**: each fix is scored 1-5 on each axis, total = product. Ship 5+ first.

## Google documentation behind the checks

- Canonical URLs: https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- robots.txt, as Google reads it (most specific group, longest match): https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt
- Sitemaps (`priority` and `changefreq` ignored): https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- hreflang: https://developers.google.com/search/docs/specialty/international/localized-versions
- FAQ and How-to rich results changes: https://developers.google.com/search/blog/2023/08/howto-faq-changes

## Caveats

- GSC API is not real-time. Data has a 2 to 3 day lag.
- Position averages can mask volatility: always pair with click and impression deltas.
- AI Overviews compress CTR even when positions hold. If clicks dropped but impressions and position are stable, suspect AI Overviews.
- Algorithm volatility: cross-check with https://search.google.com/search-console/index?utm_source=googlestatus or Search Engine Roundtable's update tracker.
