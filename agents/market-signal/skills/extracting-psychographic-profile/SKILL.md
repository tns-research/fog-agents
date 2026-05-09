---
name: extracting-psychographic-profile
description: Turns a corpus of admitted quotes into a structured psychographic profile using STP (Segmentation, Targeting, Positioning) + Need Analysis + JTBD Forces of Progress (Push, Pull, Anxiety, Habit). Builds a target persona with attitudes, frustrations, existing solutions, anti-personas, and ready-to-use marketing copy mined from verbatim quotes (never paraphrased). Use during Steps 4 and 5 of the agent workflow. Triggers on words like "psychographic", "persona", "STP", "JTBD", "anti-persona", "marketing angle".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# extracting-psychographic-profile

Consumes the JSON corpus produced by `scanning-market-signals` and emits a structured psychographic profile.

## When to invoke

Load this skill when the agent enters Step 4 (psychographic profile) or Step 5 (representative quotes) of the workflow. Pairs with `references/marketing-frameworks.md` (STP, Need Analysis), `references/buyer-psychology.md` (Cialdini lenses), and `assets/jtbd-forces-of-progress.md`.

---

## Process

### Step A. Segment the corpus

Group admitted quotes by detectable persona axes, before naming a single target. Useful axes:

- **Role**: founder / operator / IC / consumer
- **Stage of journey**: aware / shopping / using / switching / abandoned
- **Sophistication**: novice / power-user / "former power-user now jaded"
- **Stakes**: hobby / side-project / job-on-the-line / regulated context
- **Geography + language**: which cluster speaks which words

Output: a 3 to 5 row segmentation table with sample quote IDs per row.

### Step B. Pick the primary target (T in STP)

The primary target is the segment where:

- Pain mention count is highest, and
- Existing solutions are weakest (least quoted, or quoted with most negative sentiment), and
- The agent's offer is plausibly fit-for-segment (this is a constraint the user provides).

Document the choice with one line per criterion. Anti-personas come next.

### Step C. Apply JTBD Forces of Progress

For the primary target, classify every escalated pain into one of four forces. See `assets/jtbd-forces-of-progress.md` for the full framework.

| Force | Definition | Example marketing implication |
|-------|------------|-------------------------------|
| **Push** | Pain of the current state | Lead with "stop X", evoke the loss |
| **Pull** | Attractiveness of the new state | Lead with the outcome, paint the future |
| **Anxiety** | Fear of switching, learning curve, sunk cost | Address upfront with "no rip-and-replace", FAQs, money-back |
| **Habit** | Inertia, "we have always done it this way" | Hardest to overcome. Often means the segment is not ready, not that the offer is wrong |

A target with strong Push + Pull but high Anxiety needs a low-friction onboarding promise. A target with high Habit is usually a wrong target choice.

### Step D. Build the persona

Output the persona as a structured profile, not a paragraph. Each field cites quote IDs.

```yaml
persona:
  name: "<descriptive title, not a fake name>"  # e.g. "FR freelance designer with multi-currency clients"
  context: "..."                                  # role, size, vertical, geo
  attitudes:
    - belief: "..."
      evidence_quotes: [q_003, q_011]
  frustrations:
    - pain_id: pain_001
      verbatim_phrasing: "..."        # exact words to copy into headlines
      evidence_quotes: [q_003, q_007]
  existing_solutions:
    - tool: "..."
      sentiment: negative
      what_they_keep: "..."           # the part they would not give up
      what_they_hate: "..."           # the part the new offer can solve
      evidence_quotes: [q_005]
  curiosity_hooks:                    # questions they ask repeatedly, openings for outreach
    - "..."
  anti_personas:                      # NOT-this segments, with reasons
    - segment: "..."
      reason: "..."
      evidence_quotes: [q_022]
  jtbd_forces:
    push: ["..."]
    pull: ["..."]
    anxiety: ["..."]
    habit: ["..."]
```

### Step E. Mine marketing copy from verbatim quotes

Output a `marketing_copy` block where every line is a verbatim quote (or a tight composition of two quotes), never a paraphrase. The headline is the quote.

```yaml
marketing_copy:
  candidate_headlines:
    - text: "I literally can't understand why my invoices are off by 3 cents every single month"
      source_quote_id: q_003
  candidate_subheads:
    - text: "..."
      source_quote_id: q_007
  objection_responses:
    - objection: "It costs too much"
      response_anchored_in_quote: "..."
      source_quote_id: q_011
```

This is the most extractive part of the skill. It is the difference between an analyst's report and an actionable marketing brief.

---

## Anti-patterns to refuse

- **Inventing a name and demographic.** Personas with stock photos and "Sarah, 34, mother of two" are noise. Stick to attitudes and behaviors evidenced by quote IDs.
- **Inventing a quote.** Every line in the marketing-copy block must reference a `source_quote_id`. No reference, no line.
- **Conflating sentiment intensity with pain validity.** A loud single thread is not validation. Check that the pain passed the validity threshold in `scanning-market-signals`.
- **Skipping anti-personas.** Without anti-personas the profile cannot guide channel choice. The "who this is NOT for" section is not optional.

---

## Output

The skill returns the persona YAML block + the marketing copy block. Both feed Step 7 of the agent workflow (write the report) and the `assets/output-template.md` skeleton.
