# Quote scoring rubric

Filter for admitting a quote into the corpus. Used by `scanning-market-signals/SKILL.md` Step D.

A quote is **admitted** only if it scores 3+ on at least 4 of the 5 dimensions. Below that, the quote is rejected (or kept as weak signal in the appendix, never as a top finding).

---

## Five dimensions

### 1. Recency (1 to 5)

| Score | Criterion |
|-------|-----------|
| 5 | Posted within the last 30 days |
| 4 | Posted in the last 90 days |
| 3 | Posted in the last 12 months |
| 2 | Posted in the last 24 months |
| 1 | Older than 24 months |

Default `recency_days` window is 90 for community content (Reddit, X, IndieHackers) and 365 for blog / forum content. Older content can pass if the pain is structural (e.g. tax-rule complaints from 2022 are still valid today).

### 2. Specificity (1 to 5)

| Score | Criterion |
|-------|-----------|
| 5 | Names a tool, dollar amount, exact time spent, exact workflow step, or specific edge case |
| 4 | Names two of: tool, time, workflow, edge case |
| 3 | Names one of those |
| 2 | Vague but with a domain hint |
| 1 | Generic ("it sucks", "could be better") |

Specificity is the dimension that separates an actionable quote ("It takes me 45 min every Monday to reconcile invoices in 3 currencies") from filler ("Invoicing is annoying").

### 3. Source trust (1 to 5)

| Score | Criterion |
|-------|-----------|
| 5 | Account age >2 years, karma / reputation positive, post history shows domain expertise, no promotional pattern |
| 4 | Account age 1-2 years, karma positive |
| 3 | Account age 6 months to 1 year, karma positive |
| 2 | Account age <6 months but post history is neutral |
| 1 | Brand-new throwaway, promotional pattern, suspicious karma |

Promotional accounts are rejected entirely regardless of score. Look for patterns: account name matches a brand, post history is 80%+ links to one domain, all comments end with the same CTA.

### 4. Emotional intensity (1 to 5)

| Score | Criterion |
|-------|-----------|
| 5 | Strong verb + exclamation + specific emotion. "I literally cannot believe this is still broken in 2026!" |
| 4 | Strong emotion expressed clearly. "This is driving me insane every single week" |
| 3 | Mild emotion. "It's frustrating but workable" |
| 2 | Neutral, descriptive |
| 1 | Detached, no emotion |

High-intensity quotes are the ones that become headlines. Low-intensity quotes are the ones that become subheads or body copy.

### 5. Community resonance (1 to 5)

| Score | Criterion |
|-------|-----------|
| 5 | Top 1% post by upvotes / replies in its subreddit, or thread received awards |
| 4 | Above-median by upvotes / replies, comment received many "this" replies |
| 3 | Average traction |
| 2 | Below-median |
| 1 | Zero traction (no upvotes, no replies) |

A high-intensity quote with zero community resonance is one person's anecdote, not signal. A medium-intensity quote with high resonance is a pain the community recognizes, which is what the agent is mining for.

---

## Admit / reject decision

```
Total = sum(scores)  # max 25
Admit if Total >= 16 (mean of 3.2 across 5 dimensions)
AND if no single dimension is at 1.
```

Quotes that score 16+ but have a 1 on a single dimension can be admitted as **weak signal** in the report appendix, but never as headline material.

---

## Quote metadata template

Every admitted quote carries metadata:

```yaml
quote_id: q_001
text_verbatim: "..."
language: en
permalink: https://reddit.com/r/freelance/comments/.../
date: 2026-04-12
upvotes: 142
author_age_months: 38
scores:
  recency: 5
  specificity: 5
  trust: 4
  intensity: 5
  resonance: 4
total: 23
admit: true
notes: "..."
```

This metadata is preserved in the corpus JSON and is what enables verbatim-preservation downstream (`extracting-psychographic-profile/SKILL.md`).

---

## Anti-patterns to refuse

- **Padding the corpus with low-scoring quotes** to hit a target count. The agent's value is the filter, not the volume.
- **Auto-admitting any quote from a high-traffic thread.** Community resonance is one of five dimensions, not a free pass.
- **Translating before scoring.** Score the quote in the original language. Translate only at output time, and keep the original alongside.
