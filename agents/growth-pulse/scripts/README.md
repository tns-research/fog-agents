# scripts/

The collection, computation and checks of growth-pulse. Python 3.9+ standard library only (`requirements.txt` lists nothing to install). Every script answers `--help`, is deterministic (same inputs, same files) and never prints a key.

| Script | Does | Writes |
|--------|------|--------|
| `run_pulse.py` | One command: every connector declared in `<project>/growth-pulse/config.json`, then `compute_pulse.py` with the action log, the seo-audit override and last run's experiments when present | `<project>/growth-pulse/<YYYYMMDD>/` |
| `connect_umami.py` | Umami Cloud or self-hosted API, or daily and events CSV | `data/umami.json` |
| `connect_plausible.py` | Plausible Stats API v2, or the dashboard export and a goals CSV | `data/plausible.json` |
| `connect_ga4.py` | GA4 Data API, or the report CSV downloads | `data/ga4.json` |
| `connect_gsc.py` | Search Console API (totals, weekly query and page rows), API-shaped JSON from any tool, or `Dates.csv` | `data/gsc.json` |
| `connect_zernio.py` | Social metrics per network from the Zernio API (daily metrics, follower stats), read-only | `data/social.json` |
| `connect_social.py` | The fallback for social: LinkedIn, Instagram, Facebook, X exports, daily or one row per post, or a normalized CSV | `data/social.json` |
| `connect_revenue.py` | Stripe charges, or a payments export; new and returning customers counted, no customer id written | `data/revenue.json` |
| `compute_pulse.py` | Weekly values, comparisons, noise bands, small-volume rule, Search Console declines, correlations on pre-registered pairs, follow-up of last run's experiments, health, limitations; validates its output | `pulse.json`, `pulse-tables.md` |
| `check_report.py` | Every number of the report exists in `pulse.json` or the handoff; no percentage on a small volume; no causal wording; required sections | stdout or `--json` |
| `check_experiments.py` | `--fill` writes baselines, noise readouts, follow-up and budget from `pulse.json`; then checks count, metrics, baselines, durations, spend gate, budget, evidence, numbers; `--md` prints the report block | the handoff (with `--fill`), stdout |
| `gp_lib.py` | Shared helpers: ISO weeks, CSV and number parsing, the source-file contract, HTTP with fixture replay, the connector runner | n/a |
| `selftest.py` | Offline regression test (below) | n/a |
| `fixtures/make_fixtures.py` | Writes the fictional swanbase fixtures (seeded); `--check` verifies them | `fixtures/` |

## Connectors

Common flags: `--today`, `--week`, `--weeks` (default 6), `--since`/`--until`, `--provider auto|api|csv`, `--csv FILE...`, `--fixtures DIR` (replay recorded responses, no network), `--out FILE`, and `--date-format` (strptime format of the CSV date column) on every connector that reads a CSV. API keys come from the environment only:

| Connector | Environment | Ids |
|-----------|-------------|-----|
| Umami | `UMAMI_API_KEY` (Cloud) or `UMAMI_BASE_URL` + `UMAMI_USERNAME`/`UMAMI_PASSWORD` or `UMAMI_API_TOKEN` | `--website-id` or `UMAMI_WEBSITE_ID`, `--timezone` of the daily buckets (default UTC) |
| Plausible | `PLAUSIBLE_API_KEY`, optional `PLAUSIBLE_BASE_URL` | `--site-id` or `PLAUSIBLE_SITE_ID` |
| GA4 | `GA4_ACCESS_TOKEN` | `--property-id`, `--events` |
| Search Console | `GSC_ACCESS_TOKEN` | `--site-url`, `--dimensions` (key order of JSON rows without a dimensions field) |
| Social (Zernio) | `ZERNIO_API_KEY`, optional `ZERNIO_BASE_URL` | `--profile-id`, `--platforms` |
| Revenue | `STRIPE_API_KEY` (or `STRIPE_SECRET_KEY`) | `--currency`, `--history-days` (default 365, to tell returning customers), `--max-pages` (default 50) |

Source `social` has two connectors and `run_pulse.py` picks: `connect_zernio.py` when `sources.social.zernio.enabled` is true and the key is set, `connect_social.py` (CSV exports) when it is not enabled, when the key is not set, or when the API call exits 1; the reason goes in the notes of `data/social.json`. `connect_zernio.py` takes no `--csv`. Field mapping, limits and documentation links: its docstring.

Exit codes of every connector: 0 data written (`ok`, `partial` or `stale`), 1 health file written without data (`missing` or `error`, the message names the export to use), 2 usage error or unreadable input (nothing written).

## Typical run

```bash
python3 scripts/run_pulse.py --project-dir <project> --today 2026-10-14
# the model writes growth-pulse-20261014.md and experiments-20261014.json, then:
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-20261014.json --pulse <project>/growth-pulse/20261014/pulse.json --config <project>/growth-pulse/config.json --fill
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-20261014.json --pulse <project>/growth-pulse/20261014/pulse.json --md
python3 scripts/check_report.py <project>/growth-pulse/growth-pulse-20261014.md --pulse <project>/growth-pulse/20261014/pulse.json --experiments <project>/growth-pulse/experiments-20261014.json
```

## Tests

```bash
python3 agents/growth-pulse/scripts/selftest.py
python3 agents/growth-pulse/scripts/selftest.py --only connectors,report
```

Offline, no key (the test removes analytics keys from its own environment; the only socket is a local server on 127.0.0.1), under 15 seconds. It checks that API replay and CSV export give identical source files for every source, the missing, error and stale paths, the Zernio connector on recorded answers and `run_pulse.py` against a local HTTP server (GET only, bearer header, CSV fallback), that the example rebuilds `examples/swanbase-20261014/pulse.json` byte for byte, that no percentage is computed under the volume threshold, that the Search Console decline equals seo-audit's definition, the follow-up verdicts, `check_report.py` and `check_experiments.py` on the example and on mutations that must fail, `run_pulse.py` on a project with CSV exports only, the shared writing gate on the example report and the shared run-record schema.

## Exit codes

`compute_pulse.py`, `run_pulse.py`: 0 written, 1 written but no source had data, 2 usage or unreadable input. `check_report.py`, `check_experiments.py`: 0 no BLOCK, 1 at least one BLOCK, 2 unreadable input. `selftest.py`: 0 all pass, 1 otherwise.
