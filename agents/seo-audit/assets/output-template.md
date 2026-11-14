# SEO Audit: <domain>

**Project:** <project-slug>
**Date:** YYYY-MM-DD
**Run folder:** `seo-audit/runs/<YYYYMMDD>/`
**Domain:** <https://acme.example/> (crawled from <start URL>, <N> lines in `crawl.jsonl`)
**Search Console:** <API | CSV export | none (no-traffic mode)>, current <dates> vs prior <dates>, country filter <code or all>
**SERP country:** <code> (<source: config / project-context / default us>)
**Target queries:** <list> (<confirmed by the founder | proposed, not confirmed>)

Every current title, description or H1 below cites its line of `crawl.jsonl` (`check_report.py` blocks the report otherwise). Every band, rate, count and E-E-A-T score comes from a script output named in the section.

---

## Summary

Three sentences: the main blocker found (technical before content), the largest Search Console movement (from `bands.json`), the next action. No figure that is not in a script output of this run.

## Since the last audit

From `since-last-run.md` (`seo_state.py record-run`). First run: "Baseline, nothing to compare."

- Shipped since the previous run: <brief ids, action, verify result, checkpoint outcomes>
- Issues resolved: <codes and counts>; new issues: <codes and counts>
- Pages entering or leaving a band: <list>
- E-E-A-T: site score <before> -> <after>; signals gained and lost per page (from the E-E-A-T table of `since-last-run.md`)

## Technical blockers (fix before any content work)

From `crawl-summary.json` and `crawl.jsonl`, errors first. One row per issue code.

| Issue | Severity | Pages | Example (crawl line) | Fix | Source file (with `repo_path`) |
|-------|----------|------:|----------------------|-----|-------------------------------|
| `canonical-home` | error | 2 | https://acme.example/pricing/ (crawl.jsonl:3) | canonical on itself | `src/layouts/Base.astro:12` (f03, `repo-fix.json`) |

Sitemaps read: <list with status>. robots.txt: <found, groups>. Host and slash variants: <result>.

## Search Console bands

From `bands.json` (thresholds: `assets/gsc-bands.json`). No-traffic mode: "No Search Console data", and the section lists the target queries instead.

| Band | Queries | Pages |
|------|--------:|------:|
| lost | n | n |
| decline | n | n |
| ctr_gap | n | n |
| quick_win | n | n |
| cannibalized queries | n | |
| artifact suspects | n | n |

### Pages in decline or lost (top 15)

| Page | Primary band | Pos prior → now | Clicks prior → now | Cause | Artifact? |
|------|--------------|-----------------|--------------------|-------|-----------|

### Quick wins and CTR gaps (top 15)

| Query | Page | Position | Impressions | CTR vs bucket median | Band |
|-------|------|---------:|------------:|----------------------|------|

### Cannibalization

| Query | URLs (position, share of impressions) | Survivor | Merge or link |
|-------|----------------------------------------|----------|---------------|

## SERP intent gaps

Per priority query, from `serp-analysis.json` (provider and date per query).

### `<query>`

- Dominant intent and format of the top 10: <...>
- AI Overview: <captured, cites ... | Unverified (provider)>; People also ask: <...>
- The site's page: <URL> (crawl.jsonl:<n>), <words> words, JSON-LD <types>; median of the top 3: <words>, <types>
- Gap: <what the page lacks that the top 3 have, located>

## Topic map

Clusters, pillars, under-built clusters (`mapping-content-clusters`). Cannibalization comes from the table above, not from a guess.

## GEO: answer engines

From `geo/ai-access.md` and `geo/geo-score.md`.

**Access.** <AI crawlers blocked on `/` (search or user agents first), Content-Signal lines, pages almost empty without JavaScript (crawl lines)>.

**Panel.** <N> questions in <T> topics, <D> draws per question and surface, captured on <date>.

| Surface | Provider | Answers | Mention rate | Citation rate | Share of voice | Spread between draws |
|---------|----------|--------:|-------------:|--------------:|---------------:|---------------------:|
| perplexity | <api / command / manual> | n | x % | x % | x % | x pts |
| chatgpt | manual | n | x % | n/a | x % | x pts |
| claude | none | 0 | Unverified | Unverified | Unverified | n/a |

Questions where competitors are named and the brand is not: <list>. Most cited domains: <list>.

## E-E-A-T and schema

Paste `eeat.md` as is (`eeat.py`, weights `assets/eeat-weights.json`): the site score line, the site signals, the page scores with their missing signals, the evidence per article. Scores are copied, never edited nor re-rated (`check_report.py --eeat` blocks both).

**E-E-A-T site score:** <copied from eeat.json> (eeat.json)

| URL | Kind | E-E-A-T score | Missing signals |
|-----|------|--------------:|-----------------|
| https://acme.example/blog/x/ (crawl.jsonl:7) | article | <copied> | `author_visible`, `date_modified` |

Then, per priority article, the comment (`assets/eeat-audit-checklist.md`, "What stays a comment"): what the missing signals mean for this page, the located fix, the Experience markers read on the page, quoted. No rating.

Schema: per priority page, from `crawl.jsonl` (JSON-LD types parsed from the served HTML, invalid blocks) and `assets/schema-gap-checklist.md`. A type is recommended only when the visible content matches it; FAQPage and HowTo no longer produce rich results for most sites (see the checklist), they are kept only as faithful structure.

## Internal linking

Paste `links/links.md` (`links.py audit`), trimmed: the pages that need links (new pages, orphans, quick wins under 3 body inlinks), the links to add with their sentence and the reason, the linking defects, the links that go through a redirect. Every suggestion read in its sentence; the dropped ones listed in Methodology with the reason. Body links only: menu, footer and template links are counted apart.

## Source fixes (repo mode)

Only with `repo_path`. Paste `repo-fix/repo-fix.md` (`repo_fix.py`) and `links/links-patch.md` (`links.py patch`): the patches with their `git apply --check` result, the fixes with their source line, the items to locate by hand with their candidates. Every placeholder filled and `repo_fix.py check` at 0 BLOCK before the section is delivered; the founder applies the patches, the agent never does. Without `repo_path`: "Repo mode not run: fixes described on the served HTML."

## Prioritized fix list

Ranked by impact x ease (1 to 5 each). Technical blockers first.

| # | Fix | Page(s) (crawl line) | Type | Impact | Ease | Score | Brief |
|---|-----|----------------------|------|-------:|-----:|------:|-------|
| 1 | <fix> | <URL> (crawl.jsonl:n) | technical | 5 | 5 | 25 | n/a |
| 2 | <fix> | <URL> (crawl.jsonl:n) | refine | 4 | 5 | 20 | `briefs/<id>/brief.md` |

## Title and description rewrites (top 5)

### 1. <URL>

**Current title:** `<title exactly as in the crawl>` (crawl.jsonl:<n>)
**Proposed title:** `<proposed>`
**Current meta description:** `<description exactly as in the crawl, or (missing)>` (crawl.jsonl:<n>)
**Proposed meta description:** `<proposed>`
**Why:** <query and wording seen in the SERP, intent>

## Briefs open

From `briefs/index-<YYYYMMDD>.md` and `state.json`.

| Brief | URL | Action | Priority | Status |
|-------|-----|--------|---------:|--------|

## Verifications and tracking

From `seo_state.py due` and `summary`.

| Brief | Shipped | Verify | 14 days | 28 days | 56 days |
|-------|---------|--------|---------|---------|---------|

Outcomes are correlations on small samples, never proof that the change caused them.

## 90-day roadmap

Sprint 1: technical blockers and merges. Sprint 2: refines and updates from the briefs. Sprint 3: expansions, missing pillar, new articles (`assets/article-brief-template.md`). Re-run in <date> (the 28-day checkpoints of sprint 1 are due then).

## Claims ledger

Every proof, customer name, metric or testimonial used in the proposed copy above, with its source (claims gate: `shared/skills/enforcing-claims-policy/SKILL.md` at the repo root). Write "No claims used." when the copy holds none.

| Claim (as written) | Used in | Source (`positioning.proof[i]`, URL, or facts ledger ID) |
|--------------------|---------|----------------------------------------------------------|

**Dropped:** <claims removed for lack of a source, or "none">

## Methodology

- Crawl: `crawl.py`, <N> lines, cap <max_pages>, robots.txt obeyed, <delay> s between requests.
- E-E-A-T: `eeat.py`, weights version <n> (<eeat overrides from config, or none>), reference date <YYYY-MM-DD>.
- Repo mode: <`repo_fix.py` on <repo>, <n> patches, <n> to locate by hand | not run>.
- Search Console: <API with dates / CSV files / none>; bands by `gsc_bands.py` with `assets/gsc-bands.json` (<overrides from config, or none>).
- Providers used per capability (tool plan of Step 0):

  | Capability | Provider used | Notes |
  |------------|---------------|-------|
  | `search_console` | <gsc API / CSV export / none> | |
  | `serp` | <serper / serpapi / dataforseo / builtin / pasted / none> | |
  | `scrape` | <firecrawl / jina / http / builtin> | competitor pages only; the site itself is always read by `crawl.py` |
  | `ai_answers` | <perplexity API / command `<cli>` / manual / none> per surface | |
- Checks: report gate <0 BLOCK, E-E-A-T scores match eeat.json>, repo fix check <0 BLOCK | not run>, writing gate <result>, claims check <result>, fresh-eyes review <verdict or not run>.
- Defaults used without an answer: <list>.

## Limitations

- Skipped or degraded capabilities and what they left Unverified.
- `bands.json` limitations, copied as is.
- SERP and answer engines read at one point in time, from one country, signed out.

---

*Generated by `seo-audit` on YYYY-MM-DD. Founders Growth Agent Stack.*
