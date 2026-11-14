# market-signal

> What real people say about a market in public, in their words, with proof: a stored corpus, computed counts, quotes checked word for word, and a handoff the copy agents use directly.

**Run before** writing copy or building features, and once a month in watch mode, when you run it or schedule it ([`shared/scheduling.md`](../../shared/scheduling.md)), to watch the market. Don't guess what users feel. Read what they wrote.

## What you get

- A report: escalated pains with computed counts (distinct authors, communities, share by source, trend), the health of every source, verified quotes with permalink and date, hooks, objections, angles by funnel stage, a persona with JTBD forces, recommendations each with the observation that would prove it wrong.
- A JSON sidecar (`schema_version` 2.0) that `cold-outreach-builder`, `static-ads-builder`, `carousel-builder`, `landing-page-analyzer`, `first-users-hunter` and `founder-content-writer` read: schema [`assets/market-signal.schema.json`](assets/market-signal.schema.json), contract [`shared/handoffs.md`](../../shared/handoffs.md).
- The corpus itself (`runs/<date>/corpus.jsonl`), so every quote and count can be checked and the report rebuilt without collecting again.
- In watch mode, `changes.md`: pains new, rising, falling, disappeared, newly escalated since the last run.

How it holds: the model plans, reads every record, labels it and picks quotes by record id and passage; scripts collect, count and verify. A quote that is not word for word in a stored record dated inside the window blocks the build. A regression test keeps it that way: `scripts/fixtures/april-2026/` holds quotes cited the way an unchecked run prints them (texts from 2018 and 2020 in a 90-day window, recapitalised, elided, absent), on fictional articles, and each one must block.

Reference run, swanbase (pre-seed fundraising pains): [`examples/swanbase-preseed-fundraising-20261012/market-signal-20261012.md`](examples/swanbase-preseed-fundraising-20261012/market-signal-20261012.md). Its corpus is fictional: posts, authors, ids and URLs are invented, any resemblance is coincidental.

## Quick start

No API key and no paid call: the collectors use free public APIs (Hacker News Algolia, the Arctic Shift Reddit archive, Stack Exchange, Discourse forums, App Store reviews). Python 3.9+, standard library only.

```bash
cd agents/market-signal
python3 scripts/selftest.py        # offline, about 10 seconds
```

Reddit's own JSON answers 403 to cloud servers, and G2 or Capterra block scripts: the agent goes through Arctic Shift for Reddit and imports review exports you give it. Paid search (Exa, Perplexity) is optional; its output is imported into the same corpus ([`references/README.md`](references/README.md)).

## Run it

In your AI coding harness (Claude Code, Cursor, Codex, Gemini), point at this folder and ask in plain language:

> "Run the market-signal agent at `agents/market-signal/`. Market: freelance invoicing tools for designers. Language: en."

The harness reads [`AGENT_MARKET_SIGNAL.md`](AGENT_MARKET_SIGNAL.md) and runs the workflow: plan, collect, label, analyse, compare (watch mode), build, check.

## Inputs

If you ran [`project-context`](../project-context/) first, `market`, `language` and `geography` are prefilled and the agent only asks for what is missing.

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| `market` | yes | n/a | the market or product category |
| `language` | no | `en` | ISO codes (`fr`, `de,en`) or `both` |
| `geography` | no | `global` | geo focus |
| `recency_days` | no | `90` | every quote must be dated inside the window |
| `depth` | no | `standard` | caps per collector job: `quick` / `standard` / `deep` |
| `sources` | no | from the plan | communities, subreddits, forums, app ids to cover |
| `watch` | no | off | compare with the previous run, collect only what is new |

## Per-project config

```
<your-projects-root>/<project>/market-signal/config.json
```

Created on the first run from [`config.example.json`](config.example.json): window, depth and caps, sources to include or exclude, escalation thresholds, watch mode, sidecar validity. The model applies it: caps go into `plan.json`, thresholds and validity become script flags.

## Tools

| Capability | Default | Free fallback |
|------------|---------|---------------|
| `community_search` | the free collectors in `scripts/` | always available; `exa` optional, imported |
| `reviews` | `scripts/collect_appstore.py` | founder exports of G2 or Capterra, imported |
| `web_search`, `scrape` | host web search and fetch | text imported with its url and date |
| `deep_research` | `perplexity` (optional) | skipped |

Full list of providers: [`shared/tools.md`](../../shared/tools.md).

## Read more

- Workflow: [`AGENT_MARKET_SIGNAL.md`](AGENT_MARKET_SIGNAL.md)
- Scripts and tests: [`scripts/README.md`](scripts/README.md)
- Sources, limits and how to aim them: [`assets/sources.md`](assets/sources.md)
- Report sections: [`assets/output-template.md`](assets/output-template.md)

## License

Apache 2.0.
