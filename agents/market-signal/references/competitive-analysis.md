# Competitive analysis

Reference for surfacing direct and indirect competitors from the corpus, plus the dimensions on which to compare.

---

## Direct vs indirect competitors

### Direct

Same job, similar shape. Same primary buyer, same use case, same category. If the prospect would put your offer and theirs in a side-by-side spreadsheet, they are direct.

### Indirect

Same job, different shape. Different category, different buying motion, but solves the same underlying need.

Examples:

| Job | Direct | Indirect |
|-----|--------|----------|
| "I need to manage my freelance invoices" | FreshBooks, QuickBooks, Wave | Excel + email, hiring an accountant, a notebook |
| "I need to write social copy" | Jasper, Copy.ai | Hiring a copywriter, AI chat with a custom prompt, writing it themselves |
| "I need to validate a startup idea" | Mom Test workshop, accelerator, validation SaaS | Talking to 5 friends, lurking on Reddit, building a landing page |

Indirect competitors are usually the **status quo**. They are what the prospect is doing today before they consider any direct alternative. Indirect is what your offer must beat first; direct is what it must beat second.

---

## How to extract competitors from the corpus

Mine the admitted quotes for:

| Pattern | Likely yields |
|---------|---------------|
| "I switched from X to Y because" | direct competitor pair, with switching reason (gold) |
| "I use [tool] for this" | active solution, sentiment-tagged |
| "I tried [tool] but" | abandoned solution, with abandonment reason |
| "Has anyone used [tool]?" | shopping behavior, candidate set |
| "I just use [low-tech approach]" | indirect competitor, status quo |
| "Why does [tool] cost so much?" | competitor pricing pain |

Build a competitor table:

```yaml
competitors:
  - name: "..."
    type: direct | indirect
    mention_count: 12
    sentiment_breakdown:
      positive: 3
      neutral: 4
      negative: 5
    what_users_keep: "..."     # the parts users like
    what_users_hate: "..."     # the parts they complain about
    abandonment_reasons: ["...", "..."]
    pricing_signal: "...$/mo per user"
    evidence_quotes: [q_005, q_011, q_023]
```

A competitor that scores high on `what_users_hate` and high on `abandonment_reasons` is the one your positioning should target. Quote what users hate, then describe how you avoid it (in their words, not yours).

---

## Comparison dimensions

Map each competitor on the dimensions that matter for the primary persona. Pick 4 to 7 dimensions, not all. Common dimensions:

| Dimension | Detail |
|-----------|--------|
| Price | Free tier? Per-seat? Usage-based? Annual contract? |
| Setup time | Self-serve / sales-led, time to first value |
| Integrations | Native vs Zapier vs none, key integrations for the persona |
| Support quality | Self-serve docs / chat / dedicated CSM |
| Workflow fit | Specifically for the persona's job-to-be-done |
| Brand affinity | Insider, mainstream, premium, indie, enterprise |
| Switching cost | Migration effort, contract lock-in, data export quality |
| Reliability | Outage history, performance complaints |

Output a competitor matrix scored 1 to 5 per dimension, with quote evidence.

---

## What this becomes downstream

The competitor table feeds:

- **Positioning** in `extracting-psychographic-profile/SKILL.md`: frame of reference, point of difference.
- **Marketing copy mining**: "what users hate" quotes become objection-response copy, "what users keep" quotes become reassurance copy ("we still do X").
- **Anti-personas**: segments that are loyal to a specific competitor in spite of its weaknesses are usually wrong targets.

---

## Anti-patterns to refuse

- **Listing every tool in the category as a competitor.** The competitor list is what the **target persona** considers, not the analyst's catalog.
- **Treating indirect competitors as out of scope.** The status quo is the first competitor. Skipping it produces positioning that is too inside-baseball for the audience.
- **Using vendor self-description as evidence.** Competitor websites describe themselves favorably. Use admitted quotes as the source of truth.
