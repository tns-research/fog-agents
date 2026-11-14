---
name: analyzing-gsc-data
description: Reads Google Search Console data through the resolved search_console provider (the Search Console API, default gsc CLI, or the CSV exports of the Search Console UI in any interface language, which need no setup) and runs scripts/gsc_bands.py, the single definition of decline, position bands, quick wins (positions 4 to 20 with impressions), CTR gaps against the site's own CTR per position bucket, lost queries and cannibalization (several URLs of the site on one query). Thresholds live in assets/gsc-bands.json; the model reads bands.json and never recomputes a band. Preflight is a real one-row query, never an auth status. Without any Search Console data it hands over to no-traffic mode instead of failing. Triggers on "GSC", "Search Console", "decline", "decay", "CTR", "quick wins", "cannibalization", "impressions".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# analyzing-gsc-data

The data layer of the audit. A band computed by hand on up to 25,000 rows, or a decline defined differently from one run to the next, makes two audits of the same site impossible to compare. One script and one thresholds file decide, and every downstream step (briefs, report, tracking) reads `bands.json`.

## When to invoke

- Step 3 of an audit run.
- Any time a question needs Search Console numbers: which pages decline, which queries are close to page 1, which URLs compete with each other.

## Inputs

- `domain`: the Search Console property.
- `period_days`: 28 (default comparison: last 28 days vs the 28 before), or 90.
- `country`: ISO code, or `all` / empty for no filter (the flag is then left out of every `gsc` call, never passed as `all`).

## Provider

The `search_console` capability resolved at Step 0 ([`../../../../shared/tools.md`](../../../../shared/tools.md)).

| Provider | What it gives | What is missing |
|----------|---------------|-----------------|
| API (default `gsc` CLI) | query x page rows for both periods, daily rows for tracking, URL inspection, sitemaps report | nothing |
| CSV export | queries and pages tables, both periods in one compare export | query x page pairs (no cannibalization), URL inspection (Unverified unless pasted) |
| none | | no-traffic mode: the audit runs on `target_queries`, the crawl and the SERP |

## Step A: preflight with a real query

An auth status can say "authenticated" while the refresh token is revoked (`invalid_grant` on the first real request). Test with one row:

```bash
days_ago() { python3 -c 'import datetime,sys; print(datetime.date.today() - datetime.timedelta(days=int(sys.argv[1])))' "$1"; }
gsc analytics query --site <domain> --start "$(days_ago 4)" --end "$(days_ago 3)" --dimensions query --limit 1 --json
```

- Rows or an empty list: the API works.
- Property not found or not verified: never query it; switch to the CSV path or no-traffic mode and tell the founder in the report how to verify the property (https://search.google.com/search-console).
- `invalid_grant`, expired or missing credentials: do not run an interactive login inside the audit. Switch to the CSV exports the Step 0 message asked for (or no-traffic mode), and put the re-authorization procedure in the report: the founder runs the OAuth flow of their client once, outside the run (for the `gsc` CLI: `gsc auth setup` in their own terminal; the authorization code Google returns expires within minutes, so it is exchanged right away), then the next run uses the API.

Done when the provider for this run is fixed (API, CSV or none) and written in Methodology.

## Step B: get the exports

**API.** Two pulls with query x page rows (the API maximum is 25,000 rows per request; say so when a pull hits it):

```bash
DIMS=query,page; case "<country>" in ""|all|ALL|All) ;; *) DIMS=query,page,country ;; esac
gsc analytics query --site <domain> --start "$(days_ago 31)" --end "$(days_ago 3)" --dimensions $DIMS --limit 25000 --json > <project>/seo-audit/data/gsc-current.json
gsc analytics query --site <domain> --start "$(days_ago 59)" --end "$(days_ago 32)" --dimensions $DIMS --limit 25000 --json > <project>/seo-audit/data/gsc-prior.json
```

The last three days are left out: Search Console data arrives late. The `gsc` CLI has no country flag: with a country, the pulls add the `country` dimension and `gsc_bands.py --dimensions $DIMS --country <country>` keeps that country only (ISO alpha-2 or alpha-3). The CLI JSON carries no dimension names, so `--dimensions` repeats the order of the pull.

**CSV.** The Step 0 message asked the founder for one compare export: Search Console > Performance > Search results > Date > Compare > "Last 28 days" vs "Previous period" > Export > Download CSV. The zip holds `Queries.csv` and `Pages.csv` with both periods side by side; drop them in `<project>/seo-audit/data/`. Headers in English, French, German, Spanish or Italian, comma or semicolon separators and decimal commas are all read. The UI caps each table at 1000 rows: the script says so when a file reaches it.

Done when the exports are in `data/` or the run is in no-traffic mode.

## Step C: compute the bands

```bash
python3 scripts/gsc_bands.py --current <project>/seo-audit/data/gsc-current.json --prior <project>/seo-audit/data/gsc-prior.json \
  --dimensions $DIMS --country <country> --site <domain> --config <project>/seo-audit/config.json --out-dir <project>/seo-audit/runs/<YYYYMMDD>/
# CSV compare export: both periods are in the files
python3 scripts/gsc_bands.py --current <project>/seo-audit/data/Queries.csv <project>/seo-audit/data/Pages.csv --out-dir <run>/
```

The definitions, all in `assets/gsc-bands.json` (a project overrides a key with `gsc_bands` in its `config.json`; `--show-thresholds` prints what applies):

| Band | Definition |
|------|------------|
| decline | clicks down 20 % or more vs the prior period, with at least 10 prior clicks; cause `position` (2 places or more lost), `demand` (impressions down 20 % at a stable position) or `ctr` |
| lost | in the top 20 in the prior period (20 impressions or more), absent or below 20 now |
| ctr_gap | CTR under 0.75 x the site's own median CTR of its position bucket (buckets with 5 queries or more, 100 impressions or more); never an outside CTR curve |
| quick_win | positions 4 to 20 with 50 impressions or more; opportunity = impressions x (position - 3) |
| cannibalization | two URLs or more of the site on one query, each with 10 impressions or more and 10 % of the query's impressions; trailing-slash pairs flagged |
| artifact suspect (flag, not a band) | position 50 or deeper, stable within 2 places, impressions down 30 % or more: check for a measurement change before calling it a decline |

A row can sit in several bands; `primary_band` follows the priority order of the file (lost, decline, ctr_gap, quick_win).

Done when `bands.json` and `bands.md` exist in the run folder.

## Step D: read, do not recompute

- Report the counts table and the top rows of `bands.md`; copy `limitations` from `bands.json` into the report.
- A decline always comes with its impressions and position deltas: a fall in demand is not a ranking loss.
- Queries with fewer than 10 impressions are anonymized by Google and absent from every export.
- `top_query_by_page` and `cannibalization` feed the briefs (`writing-seo-briefs`).

## Step E: URL inspection and sitemaps (API only)

For the pages the briefs target and for every error page of the crawl (or every sitemap URL when the sitemap holds fewer than 100):

```bash
gsc inspect <page-url> --site <domain> --json
gsc sitemaps list <domain> --json
```

Compare Google's chosen canonical with the canonical of the crawl line: a page whose Google canonical is another URL is not ranking itself, whatever the content. With the CSV path, indexing status is Unverified unless the founder pasted the URL Inspection result; the crawl's own canonical, robots and sitemap checks still apply.

## Failure modes

- **No Search Console access at all** → no-traffic mode: `bands.json` is not written, the report says "No Search Console data", the audit prioritizes `target_queries` with the crawl and the SERP. Never invent traffic numbers.
- **Only one period** → quick wins and CTR gaps only; the script lists decline, lost and artifact as not computed.
- **Property younger than the comparison window** → compare 14 days with the 14 before (`--start` and `--end` accordingly) and say so.
- **All bands empty** (new site) → report the crawl findings and the target queries; re-run in 28 days.

## Anti-patterns to refuse

- Computing a band in the conversation from raw rows.
- Treating a 10 % drop as a decline, or a demand drop as a ranking problem.
- Benchmarking CTR against a published curve: the site's own median per bucket is the only reference.
- Using `gsc auth status` as the preflight.
