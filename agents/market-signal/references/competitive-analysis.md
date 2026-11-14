# Competitive analysis

Reference for surfacing direct and indirect competitors from the corpus, plus the dimensions on which to compare. Used by `coding-the-corpus` (the `competitors` label of each record, `meta_problem` pains) and `extracting-psychographic-profile` (`existing_solutions`, angle `contrast`).

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

Read the records for:

| Pattern | Likely yields |
|---------|---------------|
| "I switched from X to Y because" | direct competitor pair, with switching reason (gold) |
| "I use [tool] for this" | active solution, sentiment-tagged |
| "I tried [tool] but" | abandoned solution, with abandonment reason |
| "Has anyone used [tool]?" | shopping behavior, candidate set |
| "I just use [low-tech approach]" | indirect competitor, status quo |
| "Why does [tool] cost so much?" | competitor pricing pain |

Where each finding goes:

- In `labels.jsonl`, every alternative a record names goes in `competitors`, spelled the same way every time (status quo included: "cold email", "spreadsheet"). `compute_signals.py` counts the records and distinct authors per name; the model never writes a mention count.
- In `analysis.json`, `existing_solutions` lists the alternatives worth reporting:

```json
{"name": "cold email", "type": "status_quo", "sentiment": "negative", "quote_ids": ["q_005", "q_011"]}
```

  `type` is `direct`, `indirect` or `status_quo`, `sentiment` is `positive`, `negative` or `mixed`. The build attaches `mentions` (records and distinct authors) from `stats.json` when the name matches a label.
- What users keep and what they hate, abandonment and pricing reasons stay in the quotes the entry cites, verbatim. A problem the current solution creates becomes a pain of kind `meta_problem` with that solution in `existing_solution`.

The alternative with the most negative quotes and the most "I tried but" stories is the one the angles should contrast with (`contrast` of an angle). Quote what users hate; the copy agents decide how the offer answers it, through their claims gate.

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

These dimensions guide which quotes to pick and which `contrast` an angle uses. Neither the report nor the sidecar holds a score per dimension: a dimension the quotes do not speak to is left out.

---

## What this becomes downstream

The alternatives feed:

- **Positioning** in `extracting-psychographic-profile/SKILL.md`: the frame of reference (the persona's alternatives, in their words) and the `contrast` of each angle.
- **Objections**: "what users hate" and "I tried but" passages become `objections` (force `anxiety` or `habit`) when they are a reason not to act, cited by quote id.
- **Anti-personas**: segments that are loyal to a specific competitor in spite of its weaknesses are usually wrong targets.

---

## Anti-patterns to refuse

- **Listing every tool in the category as a competitor.** The competitor list is what the **target persona** considers, not the analyst's catalog.
- **Treating indirect competitors as out of scope.** The status quo is the first competitor. Skipping it produces positioning that is too inside-baseball for the audience.
- **Using vendor self-description as evidence.** Competitor websites describe themselves favorably. Use verified quotes as the source of truth.
