# References

## CLIs / binaries

| Tool | Used for | Repo |
|------|----------|------|
| `gsc` | Search Console queries, sitemaps, URL inspection | https://github.com/the20100/cli-skills/tree/main/g-search-console-cli |
| `firecrawl` | live SERP scrape + competitor pages | https://github.com/the20100/cli-skills/tree/main/firecrawl |

## APIs

- **Google Search Console API**: https://developers.google.com/webmaster-tools/v1/api_reference_index
- **Firecrawl**: https://docs.firecrawl.dev/

## SEO references

- **Aleyda Solis**: *SEO audit framework* (technical + content + UX layers).
- **Lily Ray**: Google update analysis (https://twitter.com/lilyraynyc).
- **Marie Haynes**: E-E-A-T patterns and quality signals.
- **Ahrefs blog**: page decay diagnosis playbook.

## Concepts the agent uses

- **Query decay**: a query loses ≥ 5 positions or ≥ 50% clicks vs prior period → flagged.
- **Page decay**: a page loses ≥ 30% of its total clicks in 30 days vs prior 30 → flagged.
- **Intent gap**: SERP top 10 covers a content type / depth / angle the user's page doesn't.
- **Impact × ease scoring**: each fix is scored 1-5 on each axis, total = product. Ship 5+ first.

## Caveats

- GSC API is not real-time. Data has a 2 to 3 day lag.
- Position averages can mask volatility: always pair with click and impression deltas.
- AI Overviews compress CTR even when positions hold. If clicks dropped but impressions and position are stable, suspect AI Overviews.
- Algorithm volatility: cross-check with https://search.google.com/search-console/index?utm_source=googlestatus or Search Engine Roundtable's update tracker.
