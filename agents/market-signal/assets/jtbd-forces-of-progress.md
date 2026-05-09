# JTBD Forces of Progress

The Jobs-To-Be-Done framework for understanding why people switch (or fail to switch) products. Every escalated pain in `market-signal` is classified into one of four forces. This file is the reference; the classification happens in `extracting-psychographic-profile/SKILL.md`.

Switching happens when **(Push + Pull) > (Anxiety + Habit)**. Marketing copy works the four forces explicitly.

---

## The four forces

### 1. Push of the current situation

The pain of staying with the current state. What is broken, frustrating, expensive, slow about how the user does the job today.

**How it shows up in quotes:**
- "I waste 3 hours every week on [task]"
- "The current tool keeps doing X, and I have to manually fix it"
- "I can't believe this is still broken in 2026"
- Time costs, money costs, embarrassment, missed opportunities, errors

**Marketing implication:** lead with the loss. Use the verbatim pain language. The headline is the user's complaint.

**Verbatim example for headline:** "Stop spending Monday mornings reconciling invoices in three currencies."

---

### 2. Pull of the new solution

The attractiveness of the new state. What life looks like once the job is done well.

**How it shows up in quotes:**
- "I wish there was a tool that..."
- "What I want is..."
- "If only I could..."
- Vision statements, future-tense, aspirational verbs

**Marketing implication:** paint the after-state. Make it concrete (numbers, outcomes), not vague ("revolutionary", "next-gen").

**Verbatim example:** "Send 12 invoices in 8 minutes, three currencies, no manual reconciliation."

---

### 3. Anxiety about the new solution

The fear of switching. Learning curve, integration risk, sunk cost in the old tool, fear of looking foolish, fear that the new thing breaks at scale.

**How it shows up in quotes:**
- "I tried [tool] but I gave up because..."
- "It looks great but I don't have time to migrate"
- "What happens if [edge case]?"
- "I already paid for [old tool] for the year"
- Words: "complicated", "migration", "learning curve", "another tool"

**Marketing implication:** address upfront. FAQ section, money-back guarantees, "import from X in 90 seconds", short demos that show the migration step.

**Verbatim example:** "Imports your existing invoices and clients from QuickBooks and FreshBooks in one click. Migrate in under 5 minutes."

---

### 4. Habit of the present

Inertia. "We have always done it this way." Not a fear, not a frustration, just the default groove.

**How it shows up in quotes:**
- "Yeah it sucks but I'm used to it"
- "I'd switch if I had time"
- "Honestly I haven't looked at alternatives in years"
- Resignation, indifference, mild grumbling without action signal

**Marketing implication:** Habit is the hardest force to fight. It often means **this segment is not ready**. The agent should flag it: "this is not a good target segment, the audience is not in market". Do not spend acquisition spend on Habit-dominant segments. Move to a segment where the Push + Pull + Anxiety triad is the active dynamic.

---

## Force balance per persona

For the primary target persona, output a force-balance scorecard:

```yaml
force_balance:
  push: high            # mention count >= 5, intensity >= 4
  pull: medium          # vision quotes present but vague
  anxiety: high         # multiple "I tried but gave up" quotes
  habit: medium         # some resignation, but switching language present
  switch_likelihood: medium-high
  marketing_priority: address Anxiety upfront, lead with concrete Pull
```

When a force is **high**, the marketing copy must work it explicitly. When **low**, the corresponding section can be light or absent.

---

## How to classify a quote

For each escalated pain (mention_count >= 5 across 2+ communities), find 2 to 3 quotes that best illustrate each of the four forces. A quote can map to multiple forces; pick the dominant one.

| Quote-to-force tells | Force |
|----------------------|-------|
| Past tense + frustration + concrete cost | Push |
| Future tense + outcome + aspirational verb | Pull |
| Conditional + risk + "but" | Anxiety |
| Resignation + present perfect ("I have always") | Habit |

---

## Anti-patterns

- **Defaulting every pain to Push.** Forces a single-note "everything sucks" tone in marketing.
- **Skipping Anxiety classification.** Anxiety is what kills conversion. If your psychographic profile has no Anxiety quotes, you mined the corpus wrong: dig deeper into "I tried but..." threads.
- **Acting on Habit-dominant segments.** They are not ready. Flag and pick another segment.

---

## Source

Bob Moesta and Chris Spiek (Re-Wired Group): _Demand-Side Sales 101_ (2020) and the original Forces of Progress diagram. Adapted with quote-evidence requirement specific to this agent.
