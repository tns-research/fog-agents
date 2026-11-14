---
name: read-performance
description: Reads the last period of Meta ads results before any creative is planned. Takes an Ads Manager export (CSV, level Ad) or a Marketing API insights JSON, runs scripts/perf.py, and turns it into decisions - winners to extend, losers to retire, inconclusive ads to leave running, and a diagnosis that separates a creative problem (CTR, hook rate) from a post-click problem (conversion rate, landing page views). With a previous period it diagnoses the account (post-click drop, creative fatigue, auction pressure) and writes the next batch input (extend and explore shares). Use at Step 1 of static-ads-builder, and whenever the founder asks "which ads work", "why did sales drop", "what should we make next". Triggers on "ads performance", "winners", "CPA", "CTR", "Meta export".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# read-performance

A batch of new creatives is the answer to one problem only: people do not click. When they click and do not buy, new creatives burn the budget faster. This skill reads the numbers first and says which problem the account has.

## 1. Get the data

Capability `ads_insights`, first available:

| Tier | Source | How |
|------|--------|-----|
| API | Marketing API insights | the founder's own token or reporting tool exports `GET /<ad-account>/insights?level=ad&fields=ad_name,adset_name,campaign_name,spend,impressions,inline_link_clicks,actions&time_range=...` as JSON; the agent never stores the token |
| Manual | Ads Manager export | Ads Manager > Reports, breakdown by Ad, columns including Amount spent, Impressions, Link clicks, Landing page views, the conversion (Purchases, Leads or Registrations completed), 3-second video plays for video; Export table data > CSV. The founder drops it in `<project>/static-ads-builder/exports/` |
| none | | exploration batch, "No performance data" in the report |

Ask for the previous period too (same columns, same length): the account diagnosis needs two periods. Ask for the target CPA once; without it the account median CPA is the target and the report says so.

## 2. Run the script

```bash
python3 scripts/perf.py <project>/static-ads-builder/exports/<file> \
  --previous <project>/static-ads-builder/exports/<previous file> \
  --target-cpa <cpa> --config <project>/static-ads-builder/config.json \
  --out <project>/static-ads-builder/ads-performance-YYYYMMDD.json \
  --md <project>/static-ads-builder/ads-performance-YYYYMMDD.md
```

The rules are explicit, documented in the script's `--help` and overridable in `config.json` `perf`: minimum spend before judging, winner (3+ conversions at or under the target CPA), loser (no conversion after 2 target CPAs, or CPA at 1.5 times the target after 3 target CPAs), diagnosis against the account's own medians. They are decision rules, not market benchmarks: never compare the account to an "industry CTR" without a source URL.

Conversions come from one column or one action type, never a sum of pixel and omni counts of the same event. Check which one the script read (`conversion` in the output) and that it is the event the founder optimises for; force it with `--conversion` otherwise.

## 3. Read it, then decide

- **Account `post_click`** (CTR holds, conversion rate falls): lead the report with it. The work is the landing page against the ads' promises, the page load (landing page views per link click), the checkout or form, and retargeting the clickers. Produce only the extensions of the winners; more top-of-funnel creatives would not fix it. Offer `landing-page-analyzer` on the destination URL.
- **Account `creative`** (CTR falls): creative fatigue. The batch extends the winners in new executions and explores new angles.
- **Account `audience`** (CPM rises, CTR and conversion stable): auction pressure; say it, the creative is not the lever.
- **Ad `creative`**: the hook or the visual does not stop the scroll; rework the first line and the style, keep the angle only if it converts elsewhere.
- **Ad `post_click`**: the ad promises something the page does not deliver, or the page loses people before it loads.
- **Under 15 conversions in the period**: every ranking is a hint. Say it once, do not dress noise as a finding.

The `next_batch` block gives the plan to `brief-strategy`: `extend` (winners with their stage, angle, style and ratio parsed from the name, and the metric that made them win), `retire`, `creative_fixes`, `angles_tested`, `extend_share` and `explore_share`.

## 4. Report

In the run report, section "Performance read": the period, the conversion read, the target CPA and where it came from, the account diagnosis with its numbers, the table of ads (verdict and diagnosis), the next batch plan, and the notes (noise, names outside the convention). Ad names that follow `<project>_<NN>_<stage>_<angle>_<style>_<ratio>` (written by `scripts/package_meta.py`) feed the aggregates by angle and style; old names count in the rankings only.

## Failure modes

- **Export at the campaign or ad set level** (no `Ad name` column) → `perf.py` exits 3; ask for the Ad breakdown.
- **Columns in another language** → ask for an English export (Ads Manager language setting) or map the columns by hand in a copy of the file.
- **No conversion column** → the script reads `Results`; check its `Result indicator` is the right event before trusting a CPA.
- **One period only** → the account diagnosis comes from the count of ads per problem, and the report says the trend is unknown.
