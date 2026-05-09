---
name: reviewing-cold-email
description: Reviews an existing cold-outreach sequence (email or LinkedIn) against a structured rubric. Audits Cialdini lever coverage, deliverability checklist, anti-pattern presence, sequence pacing, personalization quality, and CTA discipline. Produces a findings list with severity per finding and a rewritten version of any failing message. Use when the user supplies an existing sequence to fix, or as a self-check after the agent drafts a new sequence. Triggers on words like "review", "audit", "improve", "tighten", "fix this sequence".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# reviewing-cold-email

Review-mode methodology. The sequence already exists; the job is to find what is wrong and propose a rewrite.

This skill pairs with:
- `assets/banned-patterns.md` (anti-pattern catalogue).
- `assets/cialdini-channel-matrix.md` (lever lookup).
- `assets/deliverability-checklist.md` (technical pre-send checklist).

---

## When to invoke

- User supplies an existing sequence and asks for a review.
- Self-check after the agent drafts a new sequence in Step 4: run the rubric before finalizing.

---

## Inputs

- The existing sequence (text of each message, plus subject lines, plus cadence days).
- `icp_context` (role, stage, vertical, geography).
- `goal`, `channel`, `language`, `seniority` (same as the agent inputs).

---

## The 6-section rubric

### Section 1: Sequence shape

For each message, check:
- Purpose declared (initial hook | bump | value drop | social proof | direct ask | breakup).
- Day of send specified.
- Cadence is widening, not regular. If the gaps are 3-3-3-3, flag.
- The sequence ends on a breakup. If not, flag.
- Sequence length is between 4 and 7. Outside this band, flag.

### Section 2: Cialdini coverage

For each message, check:
- The Cialdini lever is named.
- The lever is actually present in the body (not just labelled).
- The lever matches the message purpose (use the table in `applying-cialdini-to-cold-email/SKILL.md`).

Across the sequence, check:
- At least 4 distinct levers represented in a 6-message sequence.
- No single lever stacked in 3 consecutive messages.

### Section 3: Anti-patterns

For each message body, search for:
- AI-tells: "I hope this email finds you well", "I came across your impressive work", "I trust this finds you well", "Quick question".
- Banned jargon: "synergy", "leverage", "best-in-class", "world-class", "cutting-edge", "revolutionary", "disruptive", "game-changer", "next-level".
- Hedging: "we believe we can", "we think we might", "potentially", "could possibly".
- Multi-CTA: more than one ask per message.
- Calques and FR-specific bans (if `language: fr`): "Pas pour [X]", "permettez-moi", "implémenter", "synergiser", "challenger" (verb), "scaler".
- Manufactured urgency: "expires today" when it does not, "last chance" when it is not.

For each subject line, check:
- ≤50 characters (front-loaded in first 33).
- No ALL CAPS.
- No emoji (cold email).
- Not "Quick question" or any of the cliché openers.

### Section 4: Personalization quality

For each message, check:
- Tokens present beyond name+company.
- At least one of `{{specific_observation}}` or `{{personal_hook}}` in Email 1.
- Personalization is concrete, not generic ("your work" is not personalization).
- Tokens map to fields available in the prospect CSV (no token referencing a field that does not exist).

### Section 5: Deliverability

Run through `assets/deliverability-checklist.md`:
- SPF, DKIM, DMARC aligned for the sending domain.
- Subdomain in use (e.g. `outreach.acme.com`), not main domain.
- One link maximum in body, no tracking pixel.
- Unsubscribe link if jurisdiction requires (RFC 8058 one-click for bulk).
- Inbox warmed for ≥30 days if new.
- Daily cap ≤30 to 50 emails per inbox per day.

### Section 6: CTA discipline

For each message, check:
- One CTA per message. No multi-link, no "or".
- CTA matches the message purpose (a calendar link in Email 1 is too aggressive; a question is fine).
- CTA is specific ("worth 10 minutes Thursday?" beats "let me know your thoughts").
- Breakup CTA is graceful ("should I close the loop?"), not desperate.

---

## Severity scale

For each finding:

- **Critical** (kills the sequence): missing breakup, no SPF/DKIM/DMARC, AI-tell in Email 1 hook, multi-CTA in direct ask, manufactured urgency, "Pas pour [X]" in FR copy.
- **Major** (significant reply-rate hit): regular cadence, single Cialdini lever stacked, banned jargon in body, generic personalization, subject >50 chars.
- **Minor** (polish): hedging adverbs, weak transitions, small calques (FR), suboptimal day-of-week.

A sequence with any Critical finding should not be sent until fixed. Major findings are non-blocking but the user is told reply rate will suffer.

---

## Rewrite mandate

For every Critical or Major finding on a specific message, the review output includes a rewritten version of that message. The rewrite preserves the message purpose and Cialdini lever (or proposes a swap if the lever is wrong) but fixes the finding.

The rewritten message follows the rules in `copywriting-en/SKILL.md` or `copywriting-fr/SKILL.md`.

---

## Output

A markdown report with this structure:

```markdown
# Sequence review: <project> / <icp>

## Summary
<2-3 sentences: severity counts (N critical, N major, N minor), top finding, recommended next move>

## Findings

### Critical
- [Message 1] AI-tell in hook ("I hope this email finds you well"). Replace with specific observation. (See rewrite below.)
- ...

### Major
- ...

### Minor
- ...

## Rewrites

### Message 1 (rewritten)
**Subject:** ...
**Body:**
> ...

### ...

## Deliverability check
- [x] SPF aligned
- [ ] DKIM missing
- ...
```

Sidecar JSON includes the same findings as a structured array (per cross-cutting C1).

---

## Failure modes

- **Sequence not provided** → ask the user for the message bodies, subjects, and cadence.
- **Sequence is one message** → scope mismatch. Ask whether the user wants a sequence design (use `designing-sequences/SKILL.md` instead) or just a single-message review.
- **Domain deliverability cannot be checked from inside the agent** → ask the user to run `dig TXT <domain>` and paste output, or skip Section 5 with a documented limitation.
