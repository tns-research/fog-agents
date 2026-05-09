---
name: sequencing-linkedin-dm
description: Designs LinkedIn DM and InMail sequences that match LinkedIn's social norms in 2026. Ranks tactics: Comment-then-DM > thoughtful DM (no template) > Voice note DM > InMail. Bans pitching in the connection note. Pitch only after 1-2 value interactions. Use when `channel: linkedin`. Triggers on words like "linkedin", "DM", "InMail", "connection request", "comment-then-DM".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# sequencing-linkedin-dm

LinkedIn-specific outreach methodology. Different from email because:
- Connection requests are gated and quota-limited.
- The platform penalizes account-level patterns (high-volume DMs, identical text across recipients).
- The DM box is checked far less often than an email inbox; cadence must be slower.

This skill covers DMs and InMails. Organic LinkedIn-post writing is **not** in scope for this agent.

---

## When to invoke

- Step 3 of the agent workflow when `channel: linkedin`.
- During review: validate that an existing LinkedIn sequence respects the tactics ranking and the platform caps.

---

## Tactics ranking (highest reply rate first)

### 1. Comment-then-DM (highest signal)

The sender comments thoughtfully on a recent post by the prospect, then DMs 24 to 72 hours later referencing the comment.

Mechanic:
1. Find a post by the prospect from the last 14 days.
2. Comment with one specific, value-adding sentence (not "great post"). Add a counter-example, a number, or a question that opens a thread.
3. Wait 24 to 72 hours.
4. Send the connection request with a note that references the comment / the post.
5. After accept, send a DM that continues the conversation, not a pitch.

Best for: founders, creators, public-facing roles. Reply rate band: 25 to 40 percent in well-targeted LinkedIn outreach.

### 2. Thoughtful DM, no template

A DM written specifically for this one prospect, referencing one specific public artifact (post, hire, talk, raise). No copy-paste body.

Mechanic:
1. Send a connection request with a note referencing the artifact.
2. After accept, DM 1 to 3 days later with a 40 to 60 word message: hook + body + soft ask.
3. Follow up at +7 with a value drop or a specific question.
4. Soft ask at +14.

Best for: most B2B ICPs. Reply rate band: 10 to 20 percent.

### 3. Voice note DM

A 30 to 60 second voice note. Replaces the "first DM after accept" in the standard sequence.

Mechanic: same as 2, but the first message is voice. Voice notes have higher open rates because they are a novelty in many ICPs.

Best for: mid-senior B2B, sales-savvy audiences. Lower reply rate than text but higher per-recipient engagement when it lands.

Avoid for: enterprise C-level (perceived as informal), legal / banking / public sector.

### 4. InMail (last resort)

Use only when the prospect is not connected and a connection request is unlikely to be accepted. InMail looks transactional by default.

Mechanic:
- One InMail. No follow-up via InMail (LinkedIn's anti-spam logic flags repeat InMails).
- Subject line is critical (InMail has a subject; DMs do not).
- Lead with a specific observation, not credentials.

Best for: connecting to executives at companies where you have no warm path. Reply rate band: 3 to 8 percent.

---

## Sequence shape

Default 4-touch LinkedIn sequence (after the optional Comment-then-DM warmup):

| # | Day | Action | Length | Notes |
|---|----:|--------|-------:|-------|
| 1 | 0 | Connection request with note | ≤200 chars | Reference the post or artifact. NEVER pitch. |
| 2 | +1 to +3 | First DM after accept | 40 to 60 words | 2 sentences. No link. |
| 3 | +7 | Value drop or specific question | 40 to 60 words | One question or one artifact reference. |
| 4 | +14 | Soft ask | 30 to 50 words | Frame as conversation, not call. |

If the prospect has not accepted the connection by Day 7, do not send any DM. Either let the request sit (sometimes accepted weeks later) or send one InMail at Day 14 with a different angle.

---

## Connection note rules (≤200 chars)

The connection note is the most over-templated message on LinkedIn. To stand out:

- Open with the specific reference: "saw your post on <topic>".
- One sentence on why connecting matters to the recipient (not the sender).
- No CTA. No link. No pitch.
- Sign with first name only.

Banned patterns:
- "I'd love to connect with like-minded professionals" → generic, deleted.
- "Let me know if I can help with anything" → no specific value.
- "Saw you in [Group] and wanted to network" → low signal.
- Pitching in the note → blocked, account flagged.

---

## Daily caps and platform discipline

LinkedIn enforces account-level limits. Exceeding them flags the account.

| Action | Limit (Sales Nav unlocks higher) |
|--------|----------------------------------|
| Connection requests | 100 / week |
| DMs to 1st-degree connections | 50 / day |
| InMails | 30 to 50 / month (depends on plan) |
| Comments on prospect posts | 30 / day, mixed across networks |

Do not use third-party automation that violates LinkedIn ToS. The platform detects browser-extension automation patterns and account-level pacing patterns. Bans are permanent.

---

## Tu / vous policy on LinkedIn

LinkedIn is a public, semi-formal context. Default to vouvoiement in FR unless one of the conditions in `assets/persona-tu-vous-policy.md` is met. The "fr-tech-twitter" relaxation (where everyone uses tu) does NOT automatically apply to LinkedIn.

---

## Output

Same sequence-skeleton output as `designing-sequences/SKILL.md`, with one extra column:

```markdown
| # | Day | Action | Cialdini lever | Char/word target | LinkedIn-specific notes |
|---|----:|--------|----------------|------------------|-------------------------|
| 1 | 0 | connection request | liking | ≤200 chars | reference post |
| 2 | +1-3 | first DM | reciprocity | 40-60 words | no link |
| 3 | +7 | value drop | reciprocity | 40-60 words | attach artifact |
| 4 | +14 | soft ask | commitment | 30-50 words | conversation framing |
```

---

## Failure modes

- **Pitch in connection note** → blocked. Rewrite to one specific reference, no ask.
- **DM blasted to 50+ identical recipients** → account flagged. Personalize per-recipient.
- **Voice note for C-level enterprise** → mismatch. Use text DM.
- **Multiple InMails to the same prospect** → flagged as spam. One InMail max.
- **Daily cap exceeded** → account warning, then restriction. Pace below cap.

---

## Notes

LinkedIn changes its anti-spam thresholds quietly. The cap numbers above are valid as of Q1 2026. If the agent detects a 429 or "we've noticed unusual activity" warning, halt all sends from that account and notify the user.
