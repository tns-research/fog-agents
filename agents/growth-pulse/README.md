# growth-pulse

A growth report for an early-stage startup, from the tools it already uses, once a week when you run it or schedule it ([`shared/scheduling.md`](../../shared/scheduling.md)). Nothing runs by itself. Scripts collect six weeks of daily data and compute every figure into `pulse.json`; the model writes the report from that file only, and a script refuses any number that is not in it. The report says what moved, what stayed inside the noise, what is too small to read, and ends with three AARRR experiments for the next sprint, which the next run judges.

## How it works

1. **Collect** (`run_pulse.py`): one connector per source, each optional and interchangeable, each with a CSV export fallback, each writing a health status (`ok`, `partial`, `stale`, `missing`, `error`).

   | Source | API (key in the environment) | Export fallback |
   |--------|------------------------------|-----------------|
   | Plausible | Stats API v2 | dashboard CSV export |
   | Umami | Cloud API key or self-hosted login | daily CSV |
   | GA4 | Data API (OAuth token) | report CSV download |
   | Search Console | Search Analytics API, or JSON from the `gsc` CLI | Performance export, `Dates.csv` |
   | Social | Zernio, when it publishes for you (`connect_zernio.py`, `ZERNIO_API_KEY`, enabled in config) | LinkedIn, Instagram, Facebook, X exports (`connect_social.py`) |
   | Revenue | Stripe, restricted read key | Stripe Payments export or any payments CSV |

2. **Compute** (`compute_pulse.py`): weekly values, the report week against the previous week and against the 4-week mean, with a noise band. No percentage on fewer than 30 events (counts instead), rate changes in points, Search Console declines with the same definition as `seo-audit`, correlations on pairs fixed in advance with the day-of-week pattern removed and `causal: false` on every one, and the verdict of the last run's experiments.
3. **Write** the report from `pulse.json` and the generated tables; `check_report.py` blocks an invented number, a percentage on a small volume, a correlation written as a cause, a missing section.
4. **Plan** three AARRR experiments (hypothesis, one metric, success threshold, duration, cost, owner, evidence) in `experiments-<date>.json`; `check_experiments.py --fill` writes the baselines and tells whether each threshold can be read against the noise in its duration.
5. **Remember**: the run line in `project-context/memory/runs.jsonl` points to the handoff, so the next run judges each experiment: met, not met, running or not measurable.

Nothing bought, no image, no publication: the optional APIs read accounts you already have. Python 3.9+ standard library only.

## Quick start

```bash
# Replay the reference example (fictional swanbase data, six weeks) and run every test
python3 agents/growth-pulse/scripts/selftest.py

# Your project: copy the config, list your sources and exports, then
python3 agents/growth-pulse/scripts/run_pulse.py --project-dir <your-projects-root>/<project> --today 2026-10-14
```

Then, from your AI coding harness:

```
Run growth-pulse for project acme
```

The agent follows [`AGENT_GROWTH_PULSE.md`](AGENT_GROWTH_PULSE.md).

## Outputs

```
<your-projects-root>/<project>/growth-pulse/
  <YYYYMMDD>/data/<source>.json  <YYYYMMDD>/pulse.json  <YYYYMMDD>/pulse-tables.md
  growth-pulse-<YYYYMMDD>.md     experiments-<YYYYMMDD>.json
```

`experiments-<YYYYMMDD>.json` is the handoff of the next sprint ([`assets/experiments.schema.json`](assets/experiments.schema.json)): the founder or an orchestrator runs each change, the next growth-pulse run judges it.

## Tools

All optional: see the Tools table of [`AGENT_GROWTH_PULSE.md`](AGENT_GROWTH_PULSE.md#tools). Without any API key, every source works from its export; without a reviewer, the report is marked unreviewed.

Social numbers come from the Zernio API when `sources.social.zernio.enabled` is true in your config and `ZERNIO_API_KEY` is set. The CSV exports are the fallback: `run_pulse.py` reads them when Zernio is not enabled, when the key is not set or when the call ends without data, and writes the reason in the notes of `data/social.json`. Create a read-only Zernio key ([scoped keys](https://docs.zernio.com/multi-tenant#scoped-api-keys)): the default key can also publish.

## Example

[`examples/swanbase-20261014/`](examples/swanbase-20261014/): week 2026-W41 of the fictional swanbase site. LinkedIn reach more than doubled while site visits stayed inside the noise, Search Console declined after a page title rewrite, last week's carousel experiment met its threshold, and three experiments follow. Every number is invented.

## Limits

- Daily unique visitors are summed per week: a person visiting on two days counts twice.
- Correlations on six weeks of one site show what moved together, never what caused what. Causes are left to the experiments.
- Search Console data arrives 2 to 3 days late: run on Wednesday for a complete week.
- An unattended run cannot download a CSV for you: schedule it only for sources that have an API key ([`shared/scheduling.md`](../../shared/scheduling.md)).
- Zernio: HTTP 402 or 403 means the account has no analytics access; the source then reports `error` and the CSV exports take over (only `followers_gained` is left out when just the follower call is refused). `followers_gained` is a net daily change and can be negative. LinkedIn personal accounts only report posts published through Zernio. Zernio bills X reads at X's rate when an X account is connected and its docs do not say which analytics reads count: set a spend cap in its dashboard, or leave `x` out of `platforms`.
- The UI export of Search Console has no query or page by date: query and page declines need the API or an API-shaped JSON.

## License

Apache-2.0.
