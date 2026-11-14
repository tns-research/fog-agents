# JTBD Forces of Progress

The Jobs-To-Be-Done framework for understanding why people switch (or fail to switch) products. Every pain in `market-signal` is classified into one of four forces. This file is the reference; records and pains are classified in `coding-the-corpus/SKILL.md` (`forces` of each label, `force` of each pain), the persona's forces are filled in `extracting-psychographic-profile/SKILL.md`.

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

**Marketing implication:** Habit is the hardest force to fight. It often means **this segment is not ready**. The agent flags it as a segment out of market. No acquisition budget goes to Habit-dominant segments. Move to a segment where the Push + Pull + Anxiety triad is the active dynamic.

---

## Force balance per persona

The balance is read from counts, never estimated. `stats.json` holds `forces` (force labels across counted voices) and each pain's `forces`; the persona in `analysis.json` lists the quote ids that show each force. The report prints both. Read them this way:

| Reading | Means | Copy implication |
|---------|-------|------------------|
| Push and Pull both voiced, Anxiety voiced | ready to move, afraid of the switch | answer Anxiety upfront, lead with a concrete Pull |
| Push voiced, Pull absent | pain without a picture of better | paint the outcome; this is TOFU material |
| Habit dominant, Push weak | not ready | flag it; usually the wrong segment, not the wrong offer |
| A force with no quote | absent in this corpus | the report says "absent"; a second wave may find it, never fill it |

When a force is voiced by many distinct authors, the copy must work it explicitly. When a force has no quote, the corresponding section stays out of the copy rather than being written from assumption.

---

## How to classify a quote

In `labels.jsonl`, a record carries every force it shows (`forces`). In the persona, each force lists 2 to 3 quote ids of different authors that show it best, for the escalated pains first; a quote illustrates its dominant force.

| Quote-to-force tells | Force |
|----------------------|-------|
| Past tense + frustration + concrete cost | Push |
| Future tense + outcome + aspirational verb | Pull |
| Conditional + risk + "but" | Anxiety |
| Resignation + present perfect ("I have always") | Habit |

---

## Anti-patterns

- **Defaulting every pain to Push.** Forces a single-note "everything sucks" tone in marketing.
- **Skipping Anxiety classification.** Anxiety is what kills conversion. A profile with no Anxiety quote calls for a second wave on "I tried but...", "what stopped me" and "I gave up" threads; if the corpus still has none, the force stays absent, never filled.
- **Acting on Habit-dominant segments.** They are not ready. Flag and pick another segment.

---

## Source

Bob Moesta and Chris Spiek (Re-Wired Group): _Demand-Side Sales 101_ (2020) and the original Forces of Progress diagram. Adapted with quote-evidence requirement specific to this agent.
