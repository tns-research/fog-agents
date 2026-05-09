---
name: copywriting-en
description: Writes English cold-email and LinkedIn DM copy in a founder-to-founder voice. Imposes Hook / Body / CTA structure with explicit length targets per message type. Bans corporate jargon, AI-tells, and weak openings; favours short sentences, active voice, specific observations. Use during message drafting (Step 4) and during review of a draft sequence. Triggers on words like "write copy", "draft message", "write email", "write DM", "rewrite", "tighten copy".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# copywriting-en

Methodology for writing English cold outreach copy. Pairs with `assets/banned-patterns.md`, `assets/copywriting-structures.md`, and `assets/subject-line-patterns.md`.

---

## When to invoke

- Step 4 of the agent workflow: write each message body after the sequence shape and Cialdini lever per message are decided.
- During review: rewrite messages that fail the audit rubric in `reviewing-cold-email/SKILL.md`.

---

## Inputs

- `message_purpose` (initial hook | bump | value drop | social proof | direct ask | breakup)
- `cialdini_lever` (assigned by `applying-cialdini-to-cold-email`)
- `icp_context` (role, stage, vertical, geography)
- `personalization_tokens` (`{{first_name}}`, `{{specific_observation}}`, `{{personal_hook}}`, etc.)

---

## Hook / Body / CTA structure

Every cold email and LinkedIn DM has three parts.

### Hook (1 to 2 sentences, ≤30 words)

The first sentence earns the second. If a busy reader stops after the hook, they should know whether to keep reading.

Strong hook patterns:
- Specific observation about the reader: "saw your post on <specific topic>".
- Hard data point that contradicts a belief in their world.
- Direct value offer: "<artifact>, attached, no catch".
- Shared struggle: "<one specific moment>, not 'as a founder myself'".

Weak hooks (rewrite):
- "I hope this email finds you well."
- "I came across your impressive work."
- "Quick question."
- "We help <ICP> with <generic outcome>."

### Body (1 to 4 sentences)

The body explains the hook and earns the CTA. One claim per sentence. Prefer concrete numbers over adjectives. Active voice.

Cut every word that does not serve the message. After drafting, reread and remove:
- Adverbs that add no information ("really", "actually", "very").
- Hedging ("we believe", "we think we can", "potentially").
- Brand jargon ("synergize", "leverage", "best-in-class").
- Filler transitions ("furthermore", "in addition").

### CTA (1 sentence, 1 option)

One ask. No multi-CTA. Low pressure: a question is stronger than a calendar link in Email 1.

Strong CTAs (by message purpose):
- Initial hook: "want me to send it?" or "worth 10 minutes next Thursday?"
- Bump: "still relevant?"
- Value drop: "want the full version?"
- Direct ask: "open to a 15-minute call next week?"
- Breakup: "should I close the loop, or keep this in your inbox?"

Weak CTAs:
- Multiple links.
- "Looking forward to hearing from you" (no ask).
- Long calendar URL inline.

---

## Length targets

| Message type | Body length | Subject |
|--------------|-------------|---------|
| Email 1 (initial hook) | 50 to 80 words | 33 to 50 chars |
| Email 2 (bump) | 30 to 50 words | reuse subject 1 (Re:) |
| Email 3 (value drop) | 60 to 90 words | new subject, 33 to 50 chars |
| Email 4 (social proof) | 40 to 60 words | reuse or new |
| Email 5 (direct ask) | 30 to 50 words | new subject |
| Email 6 (breakup) | 30 to 40 words | "closing the loop" |
| LinkedIn DM | 40 to 60 words | n/a |
| LinkedIn connection note | ≤200 chars, no pitch | n/a |

Going over the target is not an error in itself, but if the body exceeds the target, the message has not been cut hard enough.

---

## Tone rules

- Look like a colleague, not a marketer. Lowercase first letter in subject when natural.
- Specific over generic. "Saw your post on <topic>" beats "love what you are doing".
- Founder-to-founder when both sender and reader are founders. Drop honorifics.
- No emoji in cold email. One emoji acceptable in LinkedIn DM if it matches the recipient's own posting style.
- One CTA per message. Multiple CTAs split attention and lower reply rate.

---

## Personalization tokens

Tokens replace static content with per-prospect values. The two non-trivial tokens:

- `{{specific_observation}}`: one sentence about something concrete the prospect did or said publicly (post, hire, launch, raise, talk). Generated per prospect by the personalization step.
- `{{personal_hook}}`: one sentence tying the observation to the offer. Also per prospect.

Static tokens: `{{first_name}}`, `{{company}}`, `{{role}}`, `{{vertical}}`.

A message body that contains only static tokens is not personalized; it is mail-merge. Always include at least one of `{{specific_observation}}` or `{{personal_hook}}` in Email 1.

---

## Anti-pattern check (before shipping)

Run the message through this checklist:

1. Does the first sentence include "hope" or "trust" or "weather"? Cut.
2. Is "Quick question" or "Quick" the subject? Rewrite.
3. Are there more than 2 CTAs? Cut to 1.
4. Is there a paragraph longer than 3 sentences? Split.
5. Is there an adverb that adds no info? Cut.
6. Does the message mention "leverage", "synergy", "best-in-class", "world-class", "cutting-edge"? Rewrite.
7. Is the message body over the length target? Cut 20%.
8. Could the message have been sent to anyone in the ICP? Add personalization.

The full anti-pattern list is in `assets/banned-patterns.md`.

---

## Output

For each message, produce:

```markdown
### Message N: <purpose> (Day D)

**Subject:** `<subject line>`
**Body:**
> <body, with token placeholders>

**CTA:** <text>
**Cialdini lever:** <principle>
**Personalization tokens:** `{{token1}}`, `{{token2}}`
**Word count:** N
**Why this works for this ICP:** <one line>
```

Sidecar JSON includes the same fields per message.

---

## Failure modes

- **Subject longer than 50 chars** → Android Gmail truncates at 33. Front-load or rewrite.
- **More than 1 link in body** → drop to 1 (or 0 in Email 1).
- **Personalization is name + company only** → not personalization. Add a `{{specific_observation}}`.
- **Sequence has no breakup** → add Email 6. The breakup is consistently the highest-reply message.
