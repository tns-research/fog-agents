---
name: copywriting-en
description: Writes English cold-email and LinkedIn DM copy in a founder-to-founder voice. Imposes Hook / Body / CTA structure with explicit length targets per message type. Bans corporate jargon, AI-tells, and weak openings; favours short sentences, active voice, specific observations. Use during message drafting (Step 7) and during review of a draft sequence. Triggers on words like "write copy", "draft message", "write email", "write DM", "rewrite", "tighten copy".
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

- Step 7 of the agent workflow: write each message body after the sequence shape and Cialdini lever per message are decided.
- During review: rewrite messages that fail the audit rubric in `reviewing-cold-email/SKILL.md`.

---

## Inputs

- `message_purpose` (initial hook | bump | value drop | proof or perspective | direct ask | breakup)
- `allowed_claims`, `claims_policy`, `banned_words` (from `project-context`, see the agent Step 0)
- `cialdini_lever` (assigned by `applying-cialdini-to-cold-email`)
- `icp_context` (role, stage, vertical, geography)
- `tier` of the prospect and its dossier (`dossiers/<id>/prospect.json`) with the facts `verify_dossiers.py` marked `verified`
- `personalization_tokens` (`{{first_name}}`, `{{company}}`, `{{hook}}`, `{{?hook}}`, `{{sender_first_name}}`)

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

The body explains the hook and earns the CTA. One claim per sentence. Concrete facts over adjectives; a number only when it is in the prospect's verified facts or in `positioning.proof` (the lint blocks any other). Active voice. Full sentences: no bullet list and no "Label:" line in a cold message.

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

The limits live in one file, [`../../assets/limits.json`](../../assets/limits.json), and `scripts/lint_outreach.py` applies them: words per message (signature excluded) for message 1 and for follow-ups, characters for a LinkedIn connection note, subject length, links per step. Write under the `warn` value; the `max` value blocks. A project may override them in `<project>/cold-outreach-builder/limits.json`; never stretch them to make a draft pass.

| Message type | Aim |
|--------------|-----|
| Email 1 | the hook, one or two sentences on the offer, one question |
| Follow-ups | one new element each (an artifact, a mechanism, a question), one ask |
| Breakup | two or three sentences, the door left open |
| LinkedIn connection note | the hook in one sentence, no pitch, no link |

## Tone rules

- Look like a colleague, not a marketer. Lowercase first letter in subject when natural.
- Specific over generic. "Saw your post on <topic>" beats "love what you are doing".
- Founder-to-founder when both sender and reader are founders. Drop honorifics.
- No emoji in cold email. One emoji acceptable in LinkedIn DM if it matches the recipient's own posting style.
- One CTA per message. Multiple CTAs split attention and lower reply rate.

---

## Personalization: the hook and the tiers

The research step leaves, per prospect, a verified dossier and a tier ([`../researching-prospects/SKILL.md`](../researching-prospects/SKILL.md)). Writing follows the tier:

- **Tier A**: write every step for this person, around their strongest verified fact. The later steps refer to message 1 or to the same facts; no generic paragraph pasted in. Store them in `messages.json` under `steps`.
- **Tier B**: the shared templates of `cold-outreach-output.json`, with a hook sentence for this person in `messages.json` (`hook`, `hook_fact_id`). The template carries it as `{{hook}}`.
- **Tier C**: nothing is written. The report lists the prospect and the reason.

The hook is one sentence that states a verified fact in plain words, with its date when the date matters ("Tidewell opened its private beta on 29 September"), and leads to the offer in the next sentence. It must appear word for word in message 1 (the lint checks), it must say no more than the fact's `excerpt`, and no two prospects get the same or a near-identical hook.

Static tokens: `{{first_name}}`, `{{company}}`, `{{role}}`. `{{?token}}` marks an optional line: the export drops the whole line when the value is empty. Every body ends with `{{sender_first_name}}` on its own line: never a real first name in a template or an example.

## Anti-pattern check (before shipping)

Run the message through this checklist:

1. Does the first sentence include "hope" or "trust" or "weather"? Cut.
2. Is "Quick question" or "Quick" the subject? Rewrite.
3. Are there more than 2 CTAs? Cut to 1.
4. Is there a paragraph longer than 3 sentences? Split.
5. Is there an adverb that adds no info? Cut.
6. Does the message mention "leverage", "synergy", "best-in-class", "world-class", "cutting-edge"? Rewrite.
7. Is the message body over the length target? Cut 20%.
8. Could the message have been sent to anyone in the ICP? Tie it to the prospect's verified fact.
9. Then run the mechanical gate: `python3 scripts/lint_outreach.py <run>/sequence-export.csv --dossiers <run>/dossiers` until 0 BLOCK.

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

Sidecar JSON includes the same fields per message; per-prospect hooks and tier A steps go to `messages.json` (format in [`../../scripts/README.md`](../../scripts/README.md)).

---

## Failure modes

- **Subject over the limit of `assets/limits.json`** → front-load the words that matter, cut the rest.
- **More than 1 link in body** → drop to 1 (or 0 in Email 1).
- **Personalization is name + company only** → not personalization. Build the hook on a verified fact; with no verified fact the prospect is tier C and gets nothing.
- **Sequence has no breakup** → add one: it gives a silent prospect an easy way to answer.
