# References

## In this folder

- `competitive-analysis.md`: direct and indirect alternatives, the status quo as the first competitor, meta-problems (the problem the current solution creates).
- `marketing-frameworks.md`: STP, Need Analysis, B2B and B2C grid.
- `buyer-psychology.md`: Cialdini's seven principles as lenses for reading quotes.

## Free sources the collectors use

No key, all called by `scripts/collect_*.py` (details and limits in [`../assets/sources.md`](../assets/sources.md)):

- **Hacker News Algolia API**: https://hn.algolia.com/api
- **Arctic Shift** (Reddit archive, open source): https://github.com/ArthurHeitmann/arctic_shift
- **Stack Exchange API v2.3**: https://api.stackexchange.com/docs
- **Discourse search API**: https://docs.discourse.org/#tag/Search
- **iTunes customer reviews RSS**: https://itunes.apple.com/us/rss/customerreviews/id=<app id>/sortby=mostrecent/json (find an app id with https://itunes.apple.com/search?term=<name>&entity=software)

## Optional paid providers

Never called by the scripts. Their output goes into the corpus through `scripts/import_records.py`; alternatives per capability are in [`shared/tools.md`](../../../shared/tools.md). CLIs from the public toolbelt https://github.com/the20100/cli-skills:

| CLI | Used for | Docs |
|-----|----------|------|
| `exa` | semantic search beyond the free sources; save `exa search ... --json --text` and import it with `--format exa-json` | https://github.com/the20100/cli-skills/tree/main/exa-cli |
| `firecrawl` | page to markdown when a source has no API; import the passage with its url and date | https://github.com/the20100/cli-skills/tree/main/firecrawl-cli |
| `perplexity` | optional cross-check of the escalated pains, never a source of quotes | https://github.com/the20100/cli-skills/tree/main/perplexity-cli |

APIs: Exa https://docs.exa.ai/, Firecrawl https://docs.firecrawl.dev/, Perplexity https://docs.perplexity.ai/.

## Inspiration

- **Eric Ries**, *The Lean Startup* (2011): customer development over guessing.
- **Rob Fitzpatrick**, *The Mom Test* (2013): how to extract real signal from real users.
- **Bob Moesta and Chris Spiek**, *Demand-Side Sales 101* (2020): the Forces of Progress used in `assets/jtbd-forces-of-progress.md`.
