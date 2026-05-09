---
name: market-signal
description: Scans Reddit, X, niche forums, Hacker News, IndieHackers, and product reviews (G2, Capterra, App Store) to surface real consumer insights about a target market. Applies pain-validity threshold (5+ mentions across 2+ communities), JTBD Forces of Progress (Push, Pull, Anxiety, Habit), STP segmentation, and a quote-quality rubric. Returns sentiment breakdown, top issues by mention frequency, psychographic profiles with verbatim marketing copy mined from the corpus (never paraphrased), and 15 to 20 quotes with permalinks. Run before writing copy or building anything.
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Market Signal Agent

Scan the open web for what real users say about a market or product category. Output a structured research report with quantitative data, sentiment, and verbatim quotes.

## When to run

- Before writing landing-page or ad copy.
- Before deciding what to build (or what to drop).
- When you need to know **who has this pain, how intense it is, what language they use, and what they already tried**.

## Skills loaded

| Skill | When loaded |
|-------|-------------|
| `scanning-market-signals` | Steps 1 to 3: query plan, exa + firecrawl extraction, quote-quality filter, pain-validity threshold. |
| `extracting-psychographic-profile` | Steps 4 to 5: STP, JTBD Forces of Progress, persona build, verbatim marketing-copy mining. |

## Assets used

| Asset | Used by |
|-------|---------|
| `assets/quote-scoring-rubric.md` | `scanning-market-signals` admit / reject filter |
| `assets/jtbd-forces-of-progress.md` | `extracting-psychographic-profile` Step C |
| `assets/output-template.md` | Step 7 report skeleton |
| `references/marketing-frameworks.md` | STP + Need Analysis + B2B/B2C grid |
| `references/competitive-analysis.md` | Direct vs indirect competitor extraction from corpus |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `market` | yes | n/a | the market or product category, e.g. `"freelance invoicing tools for designers"` |
| `language` | no | `en` | search language: `en`, `fr`, or `both` |
| `geography` | no | `global` | optional geo focus, e.g. `"FR"`, `"US"` |
| `depth` | no | `standard` | `quick` (≤20 sources) / `standard` (40-60) / `deep` (100+) |

## Prerequisites

This agent uses three CLIs from the public `cli-skills` repo. Install once:

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/exa-cli/bin:$HOME/cli-skills/firecrawl-cli/bin:$HOME/cli-skills/perplexity-cli/bin:$PATH"

export EXA_API_KEY="..."
export FIRECRAWL_API_KEY="..."
export PERPLEXITY_API_KEY="..."   # optional, for synthesis fallback
```

| CLI | Used for |
|-----|----------|
| `exa` | semantic search across Reddit, X, forums, HN, blogs |
| `firecrawl` | scrape thread URLs to clean markdown |
| `perplexity` | optional cross-check + citation synthesis |

## Workflow

**Step 1. Query strategy.** Load `skills/scanning-market-signals/SKILL.md`. Build 6 to 12 search queries from `market` across 7 query patterns: pain-language, comparison, wish, switching, niche-platform, review-mining (G2 / Capterra 1-3 star reviews), and FR-specific. Review-mining is the row most agents skip; it surfaces competitor weaknesses that community threads do not.

**Step 2. Collect sources.** For each query:
```bash
exa search "<query>" \
  --num-results 10 \
  --include-domains reddit.com,news.ycombinator.com,indiehackers.com,producthunt.com,x.com,g2.com,capterra.com \
  --type neural \
  --use-autoprompt \
  --start-published-date "$(date -u -d '90 days ago' +%Y-%m-%d)" \
  --json > /tmp/exa-<n>.json
```
Then for the 20 to 40 most relevant URLs, fetch full content (including comment trees):
```bash
firecrawl scrape <url> --format markdown --only-main-content > /tmp/source-<n>.md
```

**Step 3. Quantitative extraction.** Apply the quote-quality filter from `assets/quote-scoring-rubric.md` and the pain-validity threshold (5+ mentions across 2+ communities). Across admitted quotes only, compute:
- Total sources analyzed and quotes admitted vs rejected (transparency).
- Sentiment split (positive / negative / neutral) from text + engagement signals.
- Top 5 escalated pains (each with `mention_count`, `distinct_communities`, evidence quote IDs).
- Top 3 existing solutions cited (direct + indirect competitors per `references/competitive-analysis.md`).
- Top 3 unmet needs (Pull-force quotes per JTBD framework).
- Weak-signals appendix (pains under threshold, kept for transparency, not as findings).

**Step 4. Psychographic profile.** Load `skills/extracting-psychographic-profile/SKILL.md`. Apply STP segmentation, pick the primary persona, run Need Analysis per pain, classify each pain into JTBD Forces of Progress (Push, Pull, Anxiety, Habit) using `assets/jtbd-forces-of-progress.md`. Output the persona as a structured YAML block, not a paragraph; every field cites `quote_id` references.

**Step 5. Verbatim marketing-copy mining.** From the persona's force quotes, extract candidate headlines, subheads, and objection-response copy. Every line cites its `source_quote_id`. No paraphrase, no invention. This is the most extractive step in the agent.

**Step 6. Synthesis check (optional).** Cross-validate top findings with:
```bash
perplexity ask "What are the top 3 frustrations of <target audience> regarding <market>? Cite sources."
```
Use as a sanity check, not as a primary source.

**Step 7. Write the report.** Use the skeleton in `assets/output-template.md`. Save to:
```
<your-projects-root>/<project>/market-signal/market-signal-<YYYYMMDD>.md
```

## Output format

See `assets/output-template.md` for the full skeleton. Required sections:
1. Summary (3 to 4 sentences, lead with the single sharpest insight).
2. Quantitative data (sources, admit/reject counts, sentiment %, top escalated pains with `mention_count` and `distinct_communities`, direct + indirect competitors).
3. Psychographic profile (persona YAML block, JTBD force balance, anti-personas).
4. 15 to 20 verbatim quotes with permalinks and quote-score metadata.
5. Marketing-copy mining (candidate headlines / subheads / objection responses, each with `source_quote_id`).
6. 3 actionable recommendations.

A JSON sidecar `market-signal-output.json` is produced alongside the Markdown report (cross-cutting convention C1) so downstream agents can re-run analysis without re-querying APIs.

## Output location

```
<your-projects-root>/<project-slug>/market-signal/market-signal-<YYYYMMDD>.md
```

Example: `~/work/acme/market-signal/market-signal-20260427.md`.

## Failure modes

- **Exa returns nothing on a query** → broaden terms, drop site filters, retry once. If still empty, document the gap in the report.
- **Firecrawl fails on a URL** (Cloudflare, paywall) → fall back to Exa's `text` field for that result. Do not block the run.
- **All API keys missing** → fall back to Perplexity-only mode and note the limitation in the report header.
- **Language mismatch** (user asks `fr`, Exa returns mostly `en`) → broaden domain list, add French-language queries explicitly (`"... reddit français"`, `"... avis"`, `"... j'utilise"`).
- **Pain-validity threshold not met for any pain** → flag clearly in the report. Do not pad the top-findings list with single-thread complaints. The signal is insufficient; recommend deeper or different scan.
- **Persona has zero Anxiety quotes after corpus mining** → re-run with switching-language queries ("I tried but...", "I gave up because...", "what stopped me..."). Anxiety quotes are usually present and were missed by the query plan.

## Per-project config

```
<your-projects-root>/<project>/market-signal/config.json
```

Example:
```json
{
  "project": "acme-saas",
  "market": "freelance invoicing tools for designers",
  "language": "en",
  "geography": "global",
  "depth": "standard"
}
```

If missing, the agent copies `config.example.json` and asks for missing values in chat.
