---
name: analyzing-gsc-data
description: Pulls Google Search Console data via the gsc CLI, computes period-over-period deltas at the query and page level, and identifies four opportunity bands (low-hanging at positions 4-15 with high impressions, decay candidates with -20% clicks vs prior period, CTR underperformers vs position-band benchmark, and queries that disappeared from top 20). Outputs a JSON sidecar plus a Markdown summary so re-runs do not require re-querying GSC. Falls back to CSV ingestion when the CLI is unavailable. Triggers on words like "GSC", "Search Console", "decay", "CTR", "position bands", "lost queries", "impressions".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# analyzing-gsc-data

The data layer of the SEO audit. Everything downstream (intent gaps, fix list, GEO/AEO audit) consumes the JSON sidecar this skill produces.

The script that pairs with this skill is `scripts/serp_analyzer.py` (which the agent runs after GSC analysis to enrich top opportunities with live SERP data).

---

## When to invoke

- Step 2-4 of the agent workflow: pull and analyze GSC data.
- Re-runs of an existing audit when only the markdown report needs regeneration (the JSON sidecar makes this cheap).
- Cross-audit comparisons: diff two GSC JSON sidecars to track recovery between sprints.

---

## Inputs

- `domain`: GSC-verified property URL.
- `period_days`: 28, 90, or 180.
- `country`: ISO country code or `all`.
- Comparison anchor: `last_30_vs_prior_30` (default), `last_90_vs_prior_90`, or `last_28_vs_year_ago_28` (Christmas / annual).

---

## Step A: Preflight

```bash
gsc sites list
```

Confirm the domain is in the list. If not, halt and ask the user to verify ownership in GSC. Do not attempt to query an unverified property.

```bash
gsc auth status
```

If auth is missing or expired, run `gsc auth setup` interactively. Note: the OAuth code Google returns is valid ~10 minutes, do not delay.

---

## Step B: Bulk pull (the period anchor)

```bash
gsc analytics query --site <domain> \
  --start-date $(date -u -d '90 days ago' +%Y-%m-%d) \
  --end-date $(date -u +%Y-%m-%d) \
  --dimensions query,page \
  --row-limit 25000 \
  --country <country|all> \
  --output json > /tmp/gsc-period.json
```

This is the source of truth for queries × pages × clicks × impressions × CTR × position. 25000 rows is the GSC max per query, sufficient for ~99% of founder-stage sites.

---

## Step C: Period-over-period diff

Two pulls, then a diff:

```bash
# Last 30
gsc analytics query --site <domain> \
  --start-date $(date -u -d '30 days ago' +%Y-%m-%d) \
  --end-date $(date -u +%Y-%m-%d) \
  --dimensions query --row-limit 5000 \
  --output json > /tmp/gsc-last30.json

# Prior 30
gsc analytics query --site <domain> \
  --start-date $(date -u -d '60 days ago' +%Y-%m-%d) \
  --end-date $(date -u -d '31 days ago' +%Y-%m-%d) \
  --dimensions query --row-limit 5000 \
  --output json > /tmp/gsc-prior30.json
```

Compute, per query: `clicks_delta`, `impressions_delta`, `position_delta`, `ctr_delta`. Same diff at the page level.

---

## Step D: Four opportunity bands

The output of this skill is a categorized opportunity list. Every query/page goes into exactly one band:

### Band 1: Low-hanging fruit (position 4-15, high impressions)

```
filter: avg_position between 4 and 15 AND impressions >= 100 AND clicks > 0
sort: impressions DESC
```

These queries are visible to Google but underclicked. A title/meta rewrite or content depth update can lift them into the top 3 with a modest effort. Highest-ROI band for content-refresh sprints.

### Band 2: Decay candidates

```
filter: clicks_last_30 < clicks_prior_30 * 0.8 (≥20% drop)
       AND clicks_prior_30 >= 10
sort: absolute_click_loss DESC
```

The 20% threshold filters noise. The minimum prior-clicks gate removes low-volume jitter. Pages that cross this threshold sustained for 8-12 weeks are confirmed-decay candidates worth a refresh. Earlier alerts: clicks -30% over 2 weeks, position -2 on high-value queries, CTR -25% with stable position.

### Band 3: CTR underperformers vs position-band benchmark

For each query, compare its CTR to the expected CTR for its position band:

| Position | Expected CTR (organic, no AI Overview) | Expected CTR (with AI Overview present) |
|----------|-----------------------------------------|------------------------------------------|
| 1 | 32% | ~14% |
| 2 | 18% | ~9% |
| 3 | 12% | ~6% |
| 4-5 | 7-9% | ~4-5% |
| 6-10 | 3-5% | ~2-3% |
| 11-20 | 1-2% | ~0.7-1.2% |

A CTR ≥25% below the band benchmark indicates a title/meta problem (or AI Overview cannibalization). Flag for rewrite.

### Band 4: Lost queries

```
filter: query in prior_period top 20 AND query NOT in last period top 20
sort: prior_clicks DESC
```

Queries that fell off the visible board entirely. Often the highest-stakes recovery work.

---

## Step E: URL inspection on top 5 priorities

For the top 5 ranked priorities (mix of all four bands), run URL inspection:

```bash
gsc urls inspect --site <domain> --url <page-url>
```

Capture: indexing status, canonical URL, mobile usability, last crawl date, crawl errors. A "Discovered, currently not indexed" status on a Band-2 page is itself the diagnosis.

---

## Step F: Sitemap probe

```bash
gsc sitemaps list --site <domain>
gsc sitemaps get --site <domain> --sitemap <sitemap-url>
```

Check: errors, last-submitted date, indexed/submitted ratio. Flag any sitemap with errors or last-submitted >30 days.

If `gsc sitemaps list` returns empty, probe the standard locations directly:

```bash
firecrawl scrape "<domain>/sitemap.xml" --format markdown --only-main-content
firecrawl scrape "<domain>/sitemap-index.xml" --format markdown --only-main-content
firecrawl scrape "<domain>/robots.txt" --format markdown --only-main-content
```

Parse `Sitemap:` directive from `robots.txt`. See `assets/sitemap-probe-checklist.md` for the full probe protocol.

---

## Output: dual JSON + Markdown

This skill always produces two files (cross-cutting C1):

```
<project>/seo-audit/seo-audit-<YYYYMMDD>.json
<project>/seo-audit/seo-audit-<YYYYMMDD>.md
```

The JSON sidecar schema:

```yaml
audit:
  domain: https://...
  period: { start: ..., end: ..., country: ... }
  totals:
    clicks: { last: 1234, prior: 1567, delta_pct: -21.3 }
    impressions: { last: ..., prior: ..., delta_pct: ... }
    avg_position: { last: 18.4, prior: 15.7, delta: -2.7 }
  bands:
    low_hanging: [...]    # one row per query
    decay: [...]
    ctr_underperformers: [...]
    lost_queries: [...]
  url_inspection: [...]
  sitemap: { found: true, errors: [...], last_submitted: ... }
```

The Markdown report reads the JSON and renders human-readable sections. Re-running just the report does not require a fresh GSC pull.

---

## Failure modes

- **GSC CLI unavailable** → fall back to CSV import. The user can export GSC reports manually (Performance → Queries → Export → CSV). Place files at `<project>/seo-audit/data/gsc-period.csv` and `gsc-prior.csv`. Same JSON-sidecar schema is produced.
- **OAuth code expired** → regenerate via `gsc auth setup` interactively, retry. Do not bail.
- **Property has <28 days of data** → reduce comparison to last_14 vs prior_14 and note the reduced confidence in the report.
- **All bands empty** (rare, but possible for a brand-new site) → produce the report anyway with an "Insufficient data" header, recommend re-running in 30 days.

---

## Anti-patterns to refuse

- **Reporting raw clicks delta without impressions context.** A 50% clicks drop can be a -20 visibility shift or a -50 ranking collapse. Include impressions and position deltas.
- **Treating any 10% drop as decay.** Noise threshold is ≥20% over the comparison window with at least 10 prior-period clicks.
- **Ignoring the AI Overview impact on CTR benchmarks.** If the SERP for a query has an AI Overview, expected CTR is roughly halved. The benchmark must adjust accordingly.
- **Skipping the JSON sidecar.** Every consumer of this skill (intent-gap analysis, fix-list ranking) reads the JSON, not the Markdown.

---

## Source

Adapted from the search-console-analysis methodology in agent-seo-content-pipeline. Position-band CTR benchmarks calibrated against 2025-2026 industry benchmarks (Advanced Web Ranking, Backlinko studies) with explicit AI-Overview adjustment.
