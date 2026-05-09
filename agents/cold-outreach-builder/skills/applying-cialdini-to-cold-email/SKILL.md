---
name: applying-cialdini-to-cold-email
description: Maps Cialdini's 7 principles of influence (Reciprocity, Commitment, Social Proof, Authority, Liking, Scarcity, Unity) to concrete cold-email and LinkedIn DM tactics. For each principle, names the lever, the legitimate way to deploy it, and the failure mode that destroys reply rate. Use during sequence design (which lever to assign per message) and during sequence review (audit that the sequence is not stacking the same lever twice). Triggers on words like "Cialdini", "persuasion", "reciprocity", "social proof", "lever", "principle".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# applying-cialdini-to-cold-email

The methodology layer. Use this when picking which lever a message should pull, and when auditing whether a written message is actually deploying the lever it claims.

The asset that pairs with this skill is `assets/cialdini-channel-matrix.md` (the lookup table) and `assets/banned-patterns.md` (the failure-mode catalogue).

---

## When to invoke

- Step 3 (sequence design) of the agent workflow: assign one Cialdini lever per message before drafting bodies.
- Step 4 (drafting): when a message body is written, verify the lever is actually present, not just claimed.
- During `reviewing-cold-email` skill: audit whether the sequence over-relies on a single lever.

---

## Inputs

- `message_purpose`: initial hook | bump | value drop | social proof | direct ask | breakup
- `icp_context`: role + stage + vertical (informs which levers land)
- `goal`: book call | try free | give feedback | partnership

---

## The 7 principles, applied

### 1. Reciprocity

**Mechanism.** Giving first creates a social obligation to respond.

**Legitimate cold-email tactic.**
- Lead with a specific insight or mini-audit, not "free demo".
- Resource-share message: name the artifact, name its concrete value, attach or offer to send.
- Email 1 should never ask for time; it should give value.

**Failure mode.** "Free guide" with a marketing landing page behind it. The prospect immediately reads it as a lead-magnet flow, not a gift. Reciprocity breaks the moment the gift requires a form.

**Best for.** Initial hook, value drop.

---

### 2. Commitment and consistency

**Mechanism.** A small yes predisposes the prospect to a bigger yes.

**Legitimate cold-email tactic.**
- Email 1 CTA = micro-yes (a question, a pointer to a resource), not "book a 30-min call".
- Follow-up references the implicit prior commitment: "you mentioned acquisition was the bottleneck" only if true.
- Sequence escalates: question → resource → conversation → call.

**Failure mode.** Faking a prior commitment ("as we discussed last week"). Detected immediately and burns trust permanently.

**Best for.** Bump, direct ask.

---

### 3. Social proof

**Mechanism.** People follow the visible behaviour of similar peers.

**Legitimate cold-email tactic.**
- Name one comparable customer (same vertical, same stage), with one concrete outcome metric.
- Numbers beat adjectives: "0 to 50 clients in 3 months" beats "great results".
- One named peer beats a logo wall in a cold email; logo walls work on landing pages.

**Failure mode.** Generic "trusted by 1000+ companies" or unnamed testimonial. Reads as marketing, not peer signal.

**Best for.** Social proof message (#4 in the sequence), bump.

---

### 4. Authority

**Mechanism.** People defer to credible experts.

**Legitimate cold-email tactic.**
- One credibility sentence with proof, woven into the hook or body, not a bio.
- Reference a publication, talk, dataset, or named outcome they can verify.
- Authority is shown by the specificity of what you reference about THEIR world, not by titles.

**Failure mode.** A bio paragraph ("As CEO of Acme, serial entrepreneur, growth expert..."). Authority claimed = authority lost.

**Best for.** Initial hook (one sentence only), value drop.

---

### 5. Liking

**Mechanism.** People say yes to people they like.

**Legitimate cold-email tactic.**
- Shared struggle: show you have been where they are. One specific moment, not "as a founder myself".
- Sincere observation tied to a real artifact (a post, a hire, a launch).
- Founder-to-founder tone, not vendor-to-prospect.

**Failure mode.** Generic flattery ("I admire your work"). Detected as template. Use one specific observation or none.

**Best for.** Initial hook, breakup.

---

### 6. Scarcity

**Mechanism.** What is limited feels more valuable.

**Legitimate cold-email tactic.**
- Honest scarcity only: a real cohort cap, an event with real seat limit, a beta with real headcount.
- Frame in terms of what they would miss, not pressure.
- Acceptable: "we take 10 founders per cohort and 7 are in". Not acceptable: "this offer expires in 24h" when it does not.

**Failure mode.** Manufactured urgency (countdown timers, "last chance"). Founders detect this immediately. Permanent credibility loss.

**Best for.** Direct ask, only when scarcity is real.

---

### 7. Unity

**Mechanism.** People say yes to those who belong to their identity group.

**Legitimate cold-email tactic.**
- Write as a peer addressing a peer. The shared category does not need to be named.
- "Working solo on acquisition is hard" activates unity if both sender and recipient are solo founders.
- Reference shared experiences (cohort, event, community, role) when real.

**Failure mode.** Forced "us" language ("we founders all know..."). Reads as flattery if the sender is not actually one of them.

**Best for.** Initial hook (when sender and ICP share a real identity), breakup.

---

## Per-message assignment heuristic

| Message | Default lever | Alternative |
|---------|---------------|-------------|
| 1. Initial hook | Reciprocity OR Liking | Authority (one-sentence credibility) |
| 2. Bump | Commitment | Social proof |
| 3. Value drop | Reciprocity | Authority |
| 4. Social proof | Social proof | Unity |
| 5. Direct ask | Commitment | Scarcity (only if real) |
| 6. Breakup | Liking OR Unity | Reciprocity |

A 6-message sequence should touch at least 4 distinct levers. Stacking the same lever in 3 consecutive messages signals templated outreach.

---

## Audit rubric (use during review)

For each written message, answer:

1. Which Cialdini lever does the message claim to pull?
2. Is the lever actually present in the body, or only labelled?
3. Does the lever match the message purpose (per the table above)?
4. Across the sequence, are at least 4 distinct levers represented?
5. Are any failure modes triggered (manufactured urgency, claimed authority, generic social proof)?

If the answer to 2, 3, or 4 is no, rewrite the offending message before shipping.

---

## Output

Annotate each message in the sequence draft with:

```
**Cialdini lever:** <principle>
**How it lands:** <one sentence: the specific phrase or move that activates the lever>
**Risk:** <one sentence: the failure mode this message is closest to, and the guardrail>
```

This block goes in the sequence draft and the final report. The sidecar JSON includes `cialdini_lever` per message (machine-readable for downstream auditing).

---

## Failure modes

- **No lever specified.** The message is generic. Pick one before shipping.
- **Wrong lever for purpose** (e.g. authority on a breakup). Rewrite or swap message order.
- **Same lever 3 messages in a row.** Sequence is monotonic. Add variety.

---

## Notes

The `assets/cialdini-channel-matrix.md` table is the lookup. This SKILL.md is the methodology for using it. Never inline the full matrix here, the asset is the source of truth.
