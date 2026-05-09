# References

## CLIs (from cli-skills)

Public toolbelt: https://github.com/the20100/cli-skills

| CLI | Used for | Docs |
|-----|----------|------|
| `exa` | semantic search across Reddit, X, forums, HN | https://github.com/the20100/cli-skills/tree/main/exa |
| `firecrawl` | URL → clean markdown for thread analysis | https://github.com/the20100/cli-skills/tree/main/firecrawl |
| `perplexity` | optional cross-validation with citations | https://github.com/the20100/cli-skills/tree/main/perplexity |

## APIs

- **Exa**: https://docs.exa.ai/: neural search engine, semantic queries.
- **Firecrawl**: https://docs.firecrawl.dev/: scrape any URL to markdown.
- **Perplexity**: https://docs.perplexity.ai/: research with sources.

## Inspiration

- **Eric Ries**: *The Lean Startup* (2011): customer development > guessing.
- **Rob Fitzpatrick**: *The Mom Test* (2013): how to extract real signal from real users.
- **Reddit search operators**: site:reddit.com inurl:comments [keyword] still works wonders alongside Exa.

## Tips

- Combine `exa` (broad sweep) + `firecrawl` (deep dive on top 10 URLs). Quality jumps.
- For French markets, Reddit is sparse. Compensate with French forums (`forum-auto.fr`, `commentcamarche.net`), Substack comments, and Lu.ma event Q&As.
- Run `perplexity` last as a sanity check, not first as a primary source. It synthesizes well but can hallucinate citations.
