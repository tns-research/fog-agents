---
name: designing-sequences
description: Designs multi-message cold outreach sequences using a widening-gap cadence. Picks the number of messages (4 to 7), the day of each send, the message purpose per touch, and the Cialdini lever per touch. Outputs the sequence skeleton before any body is written. Use during Step 7 of the agent workflow, before drafting any message body. Triggers on words like "sequence", "cadence", "follow-up", "design touches", "touch plan".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# designing-sequences

Methodology for picking the shape of a cold outreach sequence: how many messages, what each one does, when each one fires.

---

## When to invoke

- Step 7 of the agent workflow: before any body is written.
- During review: validate that an existing sequence has the right shape before rewriting individual messages.

---

## Inputs

- `channel` (email | linkedin)
- `goal` (book call | try free | give feedback | partnership | relationship)
- `seniority` (founder | vp | manager | mixed)
- `relationship_signal` (none | cold-with-trigger | warm-intro)
- the tiers of `tiers.json` (from `scripts/score_prospects.py`)

## Shape per tier

- **Tier A** (a strong, fresh, verified fact): the steps are written for the person. A short sequence often fits better: 3 or 4 touches whose follow-ups refer to the facts or to message 1. The step count of the export is the template's; a tier A step replaces the template step with the same number.
- **Tier B** (fit, an older or weaker verified fact): the shared template, 4 to 6 touches, the hook in message 1.
- **Tier C**: no sequence.
- **`goal: relationship`** (partners, sponsors, investors): three touches with no ask at all (engage on a post, give something useful, connect), then the founder writes in person.

---

## The widening-gap cadence

The cadence between sends widens as the sequence progresses. Two reasons: replying late should not feel late, and a regular interval (every 2 days, every 3 days) screams automation.

Default cadence for a 6-message email sequence:

| Message | Day | Gap from previous |
|---------|-----|-------------------|
| 1. Initial hook | 0 | n/a |
| 2. Bump | +3 | 3 days |
| 3. Value drop | +7 | 4 days |
| 4. Proof or perspective | +12 | 5 days |
| 5. Direct ask | +18 | 6 days |
| 6. Breakup | +26 | 8 days |

Total span: 26 days. Adjust ±20 percent based on goal urgency. Do not compress to a regular cadence.

For a 4-message sequence (ICP with low tolerance for follow-ups, e.g. C-level at large enterprise):

| Message | Day |
|---------|-----|
| 1. Initial hook | 0 |
| 2. Value drop | +5 |
| 3. Direct ask | +12 |
| 4. Breakup | +21 |

For a LinkedIn sequence (3 to 4 messages, see also `sequencing-linkedin-dm/SKILL.md`):

| Message | Day | Notes |
|---------|-----|-------|
| 1. Connection request | 0 | ≤200 chars, no pitch |
| 2. First DM after accept | +1 to +3 | 2 sentences, no link |
| 3. Follow-up | +7 | value drop or specific question |
| 4. Soft ask | +14 | frame as conversation, not call |

---

## Message purposes (the canonical list)

Pick from these. Do not invent new ones for a given sequence.

| Purpose | What it does | Default Cialdini lever |
|---------|--------------|------------------------|
| Initial hook | Earns attention, opens loop | Reciprocity or Liking |
| Bump | Surfaces previous message, adds nothing new | Commitment |
| Value drop | Delivers a useful artifact | Reciprocity |
| Proof or perspective | Uses one allowed claim from `project-context` (`positioning.proof`) or a sourced URL; with none, a proof-free angle: mechanism, founder observation from the user, or a self-diagnosis question | Social proof (allowed claim), else Authority, Unity or Commitment |
| Direct ask | Asks for the conversion (call, trial, intro) | Commitment |
| Breakup | Closes the loop gracefully | Liking or Unity |

A 6-message sequence uses each purpose once. A 4-message sequence drops Bump and Proof or perspective. A 5-message sequence drops Bump.

The Proof or perspective touch never requires a named customer or a number. When the founder has no allowed claim, it runs its proof-free branch (see Step 7 of `AGENT_COLD_OUTREACH_BUILDER.md`). An invented customer, metric or quote is a hard failure.

---

## Cialdini lever assignment

See `applying-cialdini-to-cold-email/SKILL.md` for the full mapping.

The constraint at sequence-design time: a 6-message sequence should touch at least 4 distinct levers. Stacking the same lever in 3 consecutive messages signals templated outreach.

The most underused lever is **Unity** in cold email. If sender and recipient share a real category (founders, ex-employees of company X, alumni of cohort Y), put Unity in either Email 1 or Email 6.

---

## Send-time variation

A perfectly regular cadence (Tuesday 10:00, Tuesday 10:00, Tuesday 10:00) signals a tool. Vary the day-of-week and time-of-day across the sequence:

- Email 1: Tue or Wed, 10:00 to 11:00 in the recipient's timezone.
- Email 2: Mon or Thu, 14:00 to 15:00.
- Email 3: Wed, 09:00 to 10:00.
- Email 4: Tue, 16:00 to 17:00.
- Email 5: Thu, 10:00 to 11:00.
- Email 6: Fri, 11:00 to 12:00 (breakups land well on Fridays).

Avoid Mondays before 09:00 and Fridays after 16:00. Avoid Sundays entirely unless the ICP is publicly known to read on Sundays (e.g. solo founders, certain creator categories).

---

## Stop conditions

The sequence stops on:

- Any human reply, positive, negative or off topic: the sequence stops for that person.
- An out-of-office auto-reply: the sequence pauses until the return date given in the reply (or a week), then resumes at the next step. It is not a reply.
- Bounce (hard bounce removes the prospect; soft bounce retries once).
- Unsubscribe link clicked.
- Manual stop by the user.

Sequence-stop logic belongs to whatever sending tool the founder imports the CSV into; the message body never handles it. The agent's deliverable describes the stop conditions in the import-instructions doc, and the project state (`scripts/outreach_state.py`, fed by `scripts/ingest_replies.py`, see [`../triaging-replies/SKILL.md`](../triaging-replies/SKILL.md)) records them so the next run never recontacts a person who replied, bounced or asked to stop.

---

## Output (sequence skeleton)

```markdown
| # | Day | Purpose | Cialdini lever | Word target |
|---|----:|---------|----------------|------------:|
| 1 | 0 | initial hook | reciprocity | 60 |
| 2 | 3 | bump | commitment | 35 |
| 3 | 7 | value drop | reciprocity | 70 |
| 4 | 12 | proof or perspective | social proof (allowed claim) or authority / unity / commitment (proof-free) | 50 |
| 5 | 18 | direct ask | commitment | 40 |
| 6 | 26 | breakup | liking | 35 |
```

This skeleton is finalized before any body is drafted. Bodies are then written, still in Step 7, by the `copywriting-en` or `copywriting-fr` skill.

---

## Failure modes

- **Regular cadence (every N days, same day of week)** → widen gaps, vary days.
- **No breakup** → add Email 6. The breakup gives a silent prospect an easy, low-cost way to answer.
- **Same Cialdini lever 3 messages in a row** → swap message order or change lever.
- **Sequence longer than 7 emails** → shorten. Past that point each extra email mostly adds unsubscribes and complaints.
- **Bump in position 3+** → the bump only works as Email 2.

---

## Notes

The cadence numbers are this stack's defaults, not figures from a cited study. Adjust them for your ICP with your own reply data (replies per step, with the sample size); do not adjust by feel.
