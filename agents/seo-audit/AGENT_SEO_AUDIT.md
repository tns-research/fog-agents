---
name: seo-audit
description: One-shot SEO + AEO audit for a single domain. Pulls Google Search Console data via the gsc CLI (or CSV fallback), computes period-over-period deltas at the query and page level across four opportunity bands (low-hanging at positions 4-15, decay candidates with -20% clicks, CTR underperformers vs position-band benchmark, and queries that fell off top 20). Fetches the live SERP for priority queries via SERPER.dev (free tier) capturing organic top-10 plus AI Overview citations, PAA, and featured snippets. Maps the domain into pillar-and-cluster topology so fixes target topical authority, not isolated queries. Audits AI-Overview / Perplexity / ChatGPT citation presence (~55% of the search surface in 2026, cuts top-organic CTR by ~58%) using an API-first protocol with manual fallback. Audits E-E-A-T (March 2026 core update penalized 55% of weak-EEAT sites). Returns a prioritized fix list with concrete title/meta rewrites, schema gaps, AEO-pattern recommendations, and a 90-day topical-authority roadmap. Outputs a JSON sidecar so re-runs do not re-query APIs.
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# SEO Audit Agent

Single-domain SEO + AEO snapshot. Inputs: a verified GSC property + a list of target queries. Output: a prioritized fix list with concrete title/meta rewrites, intent-gap notes, AI-Overview citation diagnoses, schema fixes, and a 90-day topical-authority roadmap.

Not a recurring pipeline. Run it monthly or when traffic dips.

## When to run

- Organic traffic dipped in the last 30 days. Find what broke.
- Before a content refresh sprint. Pick the right pages to refresh.
- After a Google update (2026 core update, AI Overview rollout). See which queries / pages decayed.
- Before launching new content. Find existing pages that already rank for adjacent intents.
- When the question is "are we cited in AI Overviews / Perplexity for our target queries?"

## Skills loaded

| Skill | When loaded |
|-------|-------------|
| `analyzing-gsc-data` | Steps 2-4: GSC pull, period-over-period deltas, four opportunity bands. |
| `analyzing-serp-competition` | Step 5: live SERP fetch + competitor page crawl per priority query. |
| `mapping-content-clusters` | Step 6: pillar-and-cluster topology + cannibalization detection. |
| `auditing-geo-aeo` | Step 7: AI Overview / Perplexity / ChatGPT citation audit. |

## Assets used

| Asset | Used by |
|-------|---------|
| `assets/aeo-winning-patterns.md` | `auditing-geo-aeo` Step E for fix recommendations |
| `assets/eeat-audit-checklist.md` | `auditing-geo-aeo` Step F + `mapping-content-clusters` pillar credibility |
| `assets/sitemap-probe-checklist.md` | `analyzing-gsc-data` Step F sitemap fallback |
| `assets/schema-gap-checklist.md` | `analyzing-serp-competition` and `auditing-geo-aeo` for schema fixes |
| `assets/output-template.md` | Step 9 report skeleton |
| `references/topical-authority-model.md` | `mapping-content-clusters` framework |

## Scripts used

| Script | Used by |
|--------|---------|
| `scripts/serp_analyzer.py` | `analyzing-serp-competition` Steps A-B (SERP fetch + page crawl loop) |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `domain` | yes | n/a | the GSC-verified property, e.g. `https://acme.com/` |
| `target_queries` | yes | n/a | 3 to 10 strategic queries the site should rank for |
| `period_days` | no | `90` | window for GSC analytics (28, 90, or 180) |
| `country` | no | `all` | restrict GSC to a country code (e.g. `FR`, `US`) |
| `language` | no | `en` | report language |

## Prerequisites

```bash
# CLIs
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/perplexity-cli/bin:$PATH"

# gsc binary (one-time install, see g-search-console-cli SKILL.md)
git clone https://github.com/the20100/gsc-cli /tmp/gsc-cli && cd /tmp/gsc-cli && go build -o gsc . && mv gsc /usr/local/bin/ && cd - && rm -rf /tmp/gsc-cli

# Auth
gsc auth setup   # one-time OAuth flow

# Python deps for serp_analyzer.py
pip install -r agents/seo-audit/scripts/requirements.txt

export FIRECRAWL_API_KEY="..."
export SERPER_API_KEY="..."        # free tier 2500 queries/month
export PERPLEXITY_API_KEY="..."    # for AEO citation audit
```

| CLI / API | Used for |
|-----------|----------|
| `gsc` | Search Console queries, pages, sitemap status, URL inspection |
| `firecrawl` | scrape competitor pages and SERPs (fallback) |
| `serper.dev` | SERP API with AI Overview field; primary SERP source |
| `perplexity` | AEO citation audit (which sources Perplexity cites for target queries) |

## Workflow

**Step 1. Confirm property + auth.** Load `skills/analyzing-gsc-data/SKILL.md`. Run preflight (Step A in the skill): `gsc sites list` and `gsc auth status`. If the domain is not verified, halt and ask the user to verify in GSC first.

**Step 2. Pull period analytics.** Apply `analyzing-gsc-data` Step B: bulk pull 90-day analytics with query × page dimensions to `/tmp/gsc-period.json`.

**Step 3. Period-over-period diff.** Apply `analyzing-gsc-data` Step C: pull last-30 vs prior-30, compute deltas at the query and page level.

**Step 4. Four opportunity bands.** Apply `analyzing-gsc-data` Step D: classify every query/page into one of: low-hanging (positions 4-15 with high impressions), decay candidates (-20% clicks vs prior, ≥10 prior clicks), CTR underperformers (≥25% below position-band benchmark), or lost queries (fell off top 20). Sort, take top 5-10 priorities.

**Step 5. Live SERP analysis on priority queries.** Load `skills/analyzing-serp-competition/SKILL.md`. For the union of `target_queries` and top GSC priorities, run `scripts/serp_analyzer.py`:
```bash
python agents/seo-audit/scripts/serp_analyzer.py \
  --queries "<q1>" "<q2>" ... \
  --country <country> --language <language> \
  --out /tmp/serp-analysis.json
```
Per query: capture top-10 organic, AI Overview citations, PAA, featured snippet, dominant content type. Crawl each top-10 URL for on-page signals (title, meta, H1-H3, word count, schema, author signal).

**Step 6. Topology + cannibalization.** Load `skills/mapping-content-clusters/SKILL.md`. Group ranking queries into 3-8 topic clusters. Identify pillar-and-cluster gaps, cannibalization pairs, under-built clusters relative to SERP volume. See `references/topical-authority-model.md` for the framework.

**Step 7. GEO/AEO citation audit.** Load `skills/auditing-geo-aeo/SKILL.md`. For each priority query, audit citation presence in:
- Google AI Overview (from SERPER.dev `aiOverview` field).
- Perplexity (`perplexity ask "<q>" --json`).
- ChatGPT (manual fallback only when API-first fails).
Compute citation gap diagnoses. Map fixes to `assets/aeo-winning-patterns.md` patterns. Foundation check via `assets/eeat-audit-checklist.md`.

**Step 8. URL inspection + sitemap probe.**
```bash
gsc urls inspect --site <domain> --url <page-url>     # top 5 priority pages
gsc sitemaps list --site <domain>
```
Fallback to `assets/sitemap-probe-checklist.md` standard locations + robots.txt directive when GSC sitemap report is empty.

**Step 9. Schema gap audit.** For each priority page, apply `assets/schema-gap-checklist.md`. Flag missing high-ROI types (BreadcrumbList, Article+author, FAQPage, HowTo, Organization), miscoded markup, duplicates.

**Step 10. Build the prioritized fix list.** Combine outputs from all skills into 10 to 15 actionable fixes, ranked by **(impact × ease)**:
- Title / meta rewrites for the worst-decay pages and CTR underperformers (use exact pain language from SERPs).
- Internal link injections from healthy pages to decayed pages.
- Sections to add for intent gaps (per `analyzing-serp-competition`).
- AEO patterns to add to ranks-but-uncited pages (answer blocks, FAQPage schema, expert quotes).
- Pages to merge or 301 (cannibalization fixes).
- Schema additions/corrections.
- Pillar pages to build, clusters to expand.

**Step 11. 90-day topical-authority roadmap.** From the topic map and fix list, produce a sprint plan: cannibalization fixes (sprint 1), missing pillar (sprint 2), cluster expansion (sprint 3). See `references/topical-authority-model.md`.

**Step 12. Write the report.** Use `assets/output-template.md`. Save to:
```
<your-projects-root>/<project>/seo-audit/seo-audit-<YYYYMMDD>.md
```
A JSON sidecar `seo-audit-<YYYYMMDD>.json` is produced alongside (cross-cutting C1) so re-runs of the report do not require re-querying GSC, SERPER, or firecrawl.

## Output format

See `assets/output-template.md`. Required sections:
1. Executive summary (3 sentences + traffic delta + AI-Overview presence rate).
2. Lost / decaying queries (top 20 with deltas, classified into the four bands).
3. Decaying pages (top 15 with deltas, with URL inspection results).
4. SERP intent gaps (per priority query, with dominant format and SERP feature map).
5. Topic map (clusters, pillars, cannibalization pairs, under-built clusters).
6. AEO citation audit (per query: classic rank vs AI surface citation presence + gap diagnosis).
7. E-E-A-T audit (per priority page).
8. Schema gap audit.
9. Prioritized fix list (10 to 15 items, ranked by impact × ease).
10. Title / meta rewrites (concrete copy for the top 5 pages).
11. Technical sanity check (sitemap, indexing, canonicals).
12. 90-day topical-authority roadmap.

## Output location

```
<your-projects-root>/<project-slug>/seo-audit/seo-audit-<YYYYMMDD>.md
```

## Failure modes

- **GSC property not verified** → ask user to verify in https://search.google.com/search-console first; halt.
- **No auth set up for `gsc`** → run `gsc auth setup` interactively, then retry.
- **GSC OAuth code expired** → the one-time OAuth code Google returns is valid for ~10 minutes. If the agent fails at Step 2 with a 400 from `gsc auth`, regenerate the OAuth URL with `gsc auth setup` and ask the user for a fresh code instead of bailing.
- **GSC CLI unavailable entirely** → fall back to CSV import (user exports GSC reports manually). Place files at `<project>/seo-audit/data/gsc-period.csv` + `gsc-prior.csv`.
- **SERPER.dev quota exceeded** → switch `analyzing-serp-competition` to firecrawl SERP fallback. Note in the report that AI-Overview field is unreliable in fallback mode.
- **Firecrawl blocked on a Google SERP** → infer SERP intent by crawling each top-10 URL individually.
- **Period too short** (< 28 days of data) → reduce comparison window to 14 days vs prior 14, note in the report.
- **target_queries already in SERP top 3** → flip the analysis: focus on stable rankings → which adjacent queries are next?
- **Sitemap not at /sitemap.xml** → run the full probe sequence in `assets/sitemap-probe-checklist.md` (standard locations + robots.txt directive + CMS defaults) before flagging "no sitemap".
- **All AI surfaces fail to cite anyone for a query** → AI Overview suppressed for that query type. Classic SEO still applies; AEO not a priority.
- **Perplexity CLI unavailable / no API key** → flag in report header. Run AEO with whatever surfaces remain. Do not skip the audit entirely.

## Per-project config

```
<your-projects-root>/<project>/seo-audit/config.json
```

```json
{
  "project": "<project-slug>",
  "domain": "https://acme.com/",
  "target_queries": ["query 1", "query 2", "query 3"],
  "period_days": 90,
  "country": "all",
  "language": "en"
}
```

If missing, the agent copies `config.example.json` and asks for missing values in chat.
