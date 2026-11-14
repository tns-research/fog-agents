---
name: collecting-growth-data
description: Collects six weeks of daily growth data from interchangeable, optional sources (Plausible, Umami, GA4, Google Search Console, social networks through the Zernio API or CSV exports, Stripe or a revenue CSV) into one source file per source with a health status, through scripts/connect_*.py or scripts/run_pulse.py. Every source has a CSV export fallback the founder drops in a folder; a source with neither key nor export is reported missing and the run goes on. Use at Step 1 of growth-pulse. Triggers on "weekly numbers", "connect analytics", "export CSV", "Plausible", "Umami", "GA4", "Search Console", "Stripe", "Zernio", "LinkedIn analytics".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# collecting-growth-data

The pulse is only as good as what reached it. This step gets the numbers out of the founder's tools without asking them to change tools, and records, per source, what came in and what did not. It never computes a change: that is [`../computing-the-pulse/SKILL.md`](../computing-the-pulse/SKILL.md).

## The contract

Every connector writes `<run>/data/<source>.json` in the shape of [`../../assets/source.schema.json`](../../assets/source.schema.json), whatever the provider:

- `daily`: one row per day, summable values only (visitors, clicks, events, payments, amounts). Search position travels as `position_weighted` (position x impressions) so a week can be averaged by impressions later.
- `breakdowns`: weekly Search Console rows per query and per page, when the provider has them.
- `status`: `ok` (every day of the window), `partial` (days missing inside it), `stale` (days missing at the end only: an export made too early, or the Search Console lag), `missing` (no key, no export), `error` (the provider failed; the message says which fallback to use).
- `notes`: what was read and what was left out (another currency, failed payments, post-level attribution).

The window is the six ISO weeks (Monday to Sunday) ending with the last complete week before the run date. A source file never holds a customer id, an email or a key.

## Providers per source

`--provider auto` takes the CSV when one is given, else the API when its key is in the environment, else writes a `missing` file. Keys are read from the environment only, never from a flag or a file, never printed.

| Source | API (optional) | CSV fallback the founder exports | Script |
|--------|----------------|----------------------------------|--------|
| Umami | `UMAMI_API_KEY` (Cloud) or `UMAMI_BASE_URL` with `UMAMI_USERNAME`/`UMAMI_PASSWORD` or `UMAMI_API_TOKEN` (self-hosted); website id | `date,visitors,pageviews` and `date,event,count` | `scripts/connect_umami.py` |
| Plausible | `PLAUSIBLE_API_KEY` (Stats API v2), `PLAUSIBLE_BASE_URL` when self-hosted; site id (or `PLAUSIBLE_SITE_ID`) | Export > CSV, `visitors.csv`; goals as `date,event,count` | `scripts/connect_plausible.py` |
| GA4 | `GA4_ACCESS_TOKEN` (OAuth token, analytics.readonly), property id, key events | report Share > Download CSV (traffic by Date; events by Date and Event name) | `scripts/connect_ga4.py` |
| Search Console | `GSC_ACCESS_TOKEN` (OAuth token, webmasters.readonly), property | Performance > Export, `Dates.csv` (totals only); or API-shaped JSON from another tool such as the `gsc` CLI | `scripts/connect_gsc.py` |
| Social | Zernio: `ZERNIO_API_KEY` and `sources.social.zernio.enabled: true` (optional `profile_id`, `platforms`) | LinkedIn page analytics (daily), Meta Business Suite content export (one row per post), X analytics, or `date,network,impressions,engagements,clicks,reposts,followers_gained,posts`; any tool that writes the same columns works | `scripts/connect_zernio.py`, `scripts/connect_social.py` |
| Revenue | `STRIPE_API_KEY` or `STRIPE_SECRET_KEY` (a restricted read key; reading costs nothing) | Stripe Payments export, or any `date,amount,currency,customer` file | `scripts/connect_revenue.py` |

None of these calls buys anything: they read the founder's own accounts. Zernio's X reads are the one thing to watch (see `scripts/connect_zernio.py --help` and its docstring). Tests replay recorded responses (`--fixtures`) or a local server, never the network.

Social is the one source with two connectors. `run_pulse.py` decides: Zernio when it is enabled and its key is set; the CSV exports when it is not enabled, when the key is not set, or when the API call ends without data (the reason goes in the notes of `data/social.json`). Daily metrics use Zernio's `attribution=received`, so engagement sits on the day it arrived; a post-level CSV export puts a post's lifetime figures on its publish day. Do not compare across a switch of provider without saying so.

## Procedure

1. **Read the config.** `<project>/growth-pulse/config.json`, `sources` object: the ids, the export files (relative to `<project>/growth-pulse/`), `enabled: false` for a source the founder does not use. Export files live in `<project>/growth-pulse/exports/`.
2. **Run every connector in one command:**

   ```bash
   python3 scripts/run_pulse.py --project-dir <your-projects-root>/<project> --today <YYYY-MM-DD>
   ```

   It runs the connectors of the config, then the computation. A connector alone, for a retry: `python3 scripts/connect_gsc.py --today <date> --csv <project>/growth-pulse/exports/Dates.csv --out <run>/data/gsc.json`.
3. **Read the health lines** it prints. For each source not `ok`, decide:
   - `missing` with a source the founder uses: ask once, in the Step 0 message of the next run (or now when someone is there), for the export named in the message. Never stop the run for it.
   - `stale` on Search Console: the last days are not published yet (2 to 3 days of lag). Run on Wednesday or later, or accept that Search Console metrics of the week are not compared.
   - `error`: the message names the HTTP status. Retry once; then use the CSV fallback. Zernio 402 or 403: the account has no analytics access; say so in Limitations and use the exports, nothing is bought.
4. **Check the files exist** for every source of the config (a `missing` file counts: it carries the health).

Done when: `<run>/data/` holds one source file per declared source, each with a status, and the health lines are noted for the report.

## Export how-to, for the founder

Give these steps, word for word, when a source is missing:

- **Umami**: no daily CSV in the interface; copy the daily table of the dashboard into `date,visitors,pageviews`, or set the API key.
- **Plausible**: dashboard, Export (download icon), unzip, keep `visitors.csv`.
- **GA4**: Reports, the table by Date, Share this report, Download File, CSV. Same for Events with Date and Event name as dimensions.
- **Search Console**: Performance, set the date range to the last 6 complete weeks, Export, Download CSV, keep `Dates.csv`.
- **LinkedIn page**: Analytics, Content (or Visitors / Followers), Export, pick the 6-week range.
- **Instagram or Facebook**: Meta Business Suite, Insights, Content, Export data.
- **Stripe**: Payments, Export, all columns, a range starting well before the 6 weeks (new and returning customers need history).

## Failure modes

- **`followers_gained` is negative** (Zernio) → a net daily change: the account lost more followers than it gained. Report it as it is.
- **A CSV with unexpected headers** → exit 2 with the columns it expected; rename the columns, never edit the numbers.
- **Slash dates read the wrong way round** → pass `--date-format %d/%m/%Y`.
- **Several currencies in the payments** → the main one is kept (`--currency`), the others are counted in the notes and left out.
- **A post-level export** (one row per post) → lifetime figures land on the publish day; the days between are real zeros. Say so in the report when a post published late in a week carries reach from the next one.
