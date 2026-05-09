---
name: scanning-market-signals
description: Mines Reddit, X, niche forums, Hacker News, and product reviews (G2, Capterra, App Store) for verbatim consumer signal about a target market. Builds the query plan, runs the search via `exa` and `firecrawl`, applies a pain-validity threshold (signal must appear 5+ times across 2+ communities to escalate), and tags each finding with quote-quality metadata (recency, specificity, emotional intensity, source trust). Use during Steps 1 to 3 of the agent workflow. Triggers on words like "scan", "research", "mine signal", "what do users say", "find quotes".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash
---

# scanning-market-signals

Turns a market description into a structured corpus of verbatim user signal. Uses `exa` for discovery, `firecrawl` for full-thread extraction, and a quote-quality rubric for filtering noise.

## When to invoke

Load this skill when the agent enters Step 1 (query strategy) of the workflow, or whenever the user says "scan the market", "find quotes about X", "what are users saying about Y". Pairs with `extracting-psychographic-profile` for downstream analysis and with `assets/quote-scoring-rubric.md` for filtering.

---

## Inputs

- `market` (string): the product category or audience to scan, e.g. "freelance invoicing tools for designers"
- `language` (`en` | `fr` | `both`)
- `geography` (string, optional)
- `recency_days` (integer, default 90 for community content, 365 for blog/forum content)

---

## Process

### Step A. Build query bank

For each market, generate 6 to 12 queries across these query patterns:

| Pattern | Template | Example |
|---------|----------|---------|
| Pain-language | `"[problem] frustrating reddit"`, `"[category] sucks site:reddit.com"` | `"freelance invoicing painful reddit"` |
| Comparison | `"[tool A] vs [tool B] honest review"` | `"freshbooks vs wave honest review"` |
| Wish | `"I wish there was a tool for [problem]"` | `"I wish there was a tool for invoicing in francs"` |
| Switching | `"why I switched from [tool] to"`, `"alternatives to [tool] reddit"` | `"alternatives to quickbooks reddit"` |
| Niche platform | `"[topic] hackernews"`, `"[topic] indiehackers"`, `"[topic] producthunt"` | `"freelance invoicing indiehackers"` |
| Review-mining | `"[tool] 1-star review"`, `"[tool] G2 review"`, `"[tool] Capterra"` | `"freshbooks 1-star review G2"` |
| FR-specific | `"[problem] reddit français"`, `"[category] avis"`, `"j'utilise [tool]"` | `"facture freelance reddit français"` |

The review-mining row is the one most agents skip. G2 / Capterra 1 to 3 star reviews surface competitor weaknesses that community threads do not.

### Step B. Discovery via `exa`

Run each query with domain hints:

```bash
exa search "<query>" \
  --num-results 10 \
  --include-domains reddit.com,news.ycombinator.com,indiehackers.com,producthunt.com,x.com,g2.com,capterra.com \
  --type neural \
  --use-autoprompt \
  --start-published-date "$(date -u -d '90 days ago' +%Y-%m-%d)" \
  --json > /tmp/exa-<query-slug>.json
```

For FR scans, swap `reddit.com` for `reddit.com/r/france,reddit.com/r/quebec,forum-FR-niche`. Indie Hackers FR community uses the main domain with FR keywords.

### Step C. Full-thread extraction via `firecrawl`

For the 20 to 40 most relevant URLs, fetch the full thread with comments:

```bash
firecrawl scrape <url> --format markdown --only-main-content > /tmp/source-<n>.md
```

Top-level posts are not enough. The signal is in the comments (community resonance, dissenting takes, "I switched to X because Y"). Fetch the comment tree.

### Step D. Apply quote-quality filter

Use `assets/quote-scoring-rubric.md`. A quote is admissible only if it passes:

1. **Recency**: posted in the configured `recency_days` window. Older content discounted but not excluded if the pain is structural (e.g. "billing taxonomy" complaints from 2022 may still hold).
2. **Specificity**: names a tool, workflow, dollar amount, time spent, or specific frustration. "It is annoying" fails. "It takes me 45 min every Monday to reconcile invoices in three currencies" passes.
3. **Source trust**: account age >6 months, karma positive, not a brand-new throwaway promoting something. Promotional posts excluded.
4. **Emotional intensity**: contains a strong verb, exclamation, or specific emotion. "I literally cannot believe this is still broken in 2026" beats "could be improved".
5. **Community resonance**: post upvotes / replies / awards above subreddit median, or post in a thread that received traction.

### Step E. Apply pain-validity threshold

A pain only escalates to the report when it appears **5+ times per month across 2+ distinct communities**. A single thread complaint is anecdote, not signal. Track:

```
pain_id | mention_count | distinct_communities | first_seen | last_seen | escalate?
```

Pain escalates if `mention_count >= 5` AND `distinct_communities >= 2`. Below threshold, list as "weak signal" in the report appendix, not as a top finding.

### Step F. Tag every finding

Per-finding metadata, attached at extraction time:

```yaml
quote_id: q_001
text_verbatim: "..."  # exact wording, original language
language: en | fr
permalink: https://reddit.com/r/...
date: 2026-04-12
upvotes: 142
author_age_months: 38
sentiment: negative | neutral | positive
intensity: 1-5
specificity_score: 1-5
community: r/freelance
pain_id: pain_001
```

The `pain_id` clusters quotes that are about the same underlying issue. This is what feeds the quantitative extraction in Step 3 of the agent workflow.

---

## Anti-patterns to refuse

- **Search-volume-only research.** Combine community mining with review mining. If the agent only hits Reddit and X, it is missing 30 to 40% of the signal that lives in G2 / Capterra / App Store 1 to 3 star reviews.
- **Paraphrasing during extraction.** Quotes are copied verbatim. The verbatim preservation rule exists because "billing friction" is what the analyst writes, while "I literally cannot understand why my invoices are off by 3 cents every single month" is what the customer says. The second one is the headline.
- **Translating during extraction.** When `language: both`, keep each quote in its original language. Tag with `[translated]` only if a downstream consumer truly needs the EN version, and keep the original alongside.
- **Loose quote (no permalink, no date).** Every admissible quote has a permalink and a date. Quotes without source provenance are not admissible.

---

## Output

Returns a JSON corpus consumable by `extracting-psychographic-profile`:

```json
{
  "queries_run": [...],
  "sources_fetched": 38,
  "quotes_admitted": 23,
  "quotes_rejected": 47,
  "pains": [
    {
      "pain_id": "pain_001",
      "summary": "...",
      "mention_count": 12,
      "distinct_communities": 4,
      "escalate": true,
      "quote_ids": ["q_003", "q_007", "q_011", ...]
    }
  ],
  "quotes": [...],
  "weak_signals": [...]
}
```

This JSON is the input to `extracting-psychographic-profile`. Do not skip the structured form. The agent's downstream report can be regenerated from this JSON without re-running APIs.
