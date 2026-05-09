# Banned Patterns (cold outreach)

Catalogue of phrasings and patterns that kill reply rate, trigger spam filters, or burn the sender's credibility. Used by `copywriting-en/SKILL.md`, `copywriting-fr/SKILL.md`, and `reviewing-cold-email/SKILL.md`.

If any pattern below appears in a draft, rewrite before shipping.

---

## A. AI-tells (English)

These phrases signal "this email was generated, not written":

- "I hope this email finds you well."
- "I hope this finds you well."
- "I trust this email finds you well."
- "I came across your impressive work."
- "I came across your profile and was impressed."
- "I wanted to reach out regarding..."
- "I am reaching out because..."
- "I noticed that you are..."
- "Your work in <field> is truly inspiring."
- "I am writing to introduce myself."

**Why banned.** All of these are over-represented in LLM training data and read as machine-generated. Replies drop sharply when any of these appear in the first sentence.

**Fix.** Replace with a specific observation tied to a verifiable artifact (post, hire, raise, talk).

---

## B. AI-tells (French, mostly translations)

- "J'espère que ce message vous trouve bien."
- "Je me permets de vous contacter."
- "J'espère que vous allez bien."
- "Je vous écris suite à votre activité sur LinkedIn."
- "Permettez-moi de me présenter."
- "C'est avec plaisir que je vous adresse..."
- "Je reste à votre entière disposition."
- "Dans l'attente de votre retour, ..."

**Why banned.** Word-for-word translations of EN AI-tells, plus French corporate clichés. Pas pour [X] is a separate ban (see Section H).

**Fix.** Direct opening tied to a real artifact. Vouvoiement does not require formal AI-tell openings.

---

## C. Jargon and amplifiers (EN)

Banned words anywhere in cold copy:

- "synergy", "synergize", "synergistic"
- "leverage" (as a verb)
- "best-in-class", "world-class", "cutting-edge", "state-of-the-art"
- "revolutionary", "revolutionize", "disruptive", "disrupt"
- "game-changer", "game-changing", "next-level"
- "scalable" (as adjective in claim copy)
- "unlock potential", "unleash potential"
- "10x", "100x" without specific metric named
- "thought leader", "thought leadership"
- "ecosystem", "platform" (when actually a SaaS tool)
- "holistic", "360°", "end-to-end"

**Why banned.** All flagged as jargon by buyers in B2B reply-rate studies. Functions as a marketer-tone signal.

**Fix.** Use the underlying concrete verb or noun. "Leverage your data" → "use your data". "Best-in-class" → drop, or replace with the specific outcome.

---

## D. Jargon and amplifiers (FR)

- "booster", "exploser", "révolutionner", "disruptif"
- "synergie", "synergiser"
- "next-level", "game-changer" (anglicismes)
- "performer" (in the sense of doing well)
- "challenger" (as a verb)
- "scaler", "leverager"
- "impactant"
- "solutionner"
- "implémenter" → use "mettre en place" or "déployer"

**Why banned.** Same logic as EN, plus calques EN-to-FR that read as untranslated marketing.

---

## E. Hedging language

- "we believe we can help..."
- "we think we might be able to..."
- "potentially could..."
- "perhaps it would be worth..."
- "if you'd be open to..."
- "no pressure but..."

**Why banned.** Hedging signals lack of confidence. Replies drop when the sender hedges in the hook.

**Fix.** State the offer directly. If the offer is uncertain, say "this might not be a fit, here is what we do". Direct uncertainty beats hedged confidence.

---

## F. Multi-CTA

- Two or more links in one body.
- "or" between two asks ("happy to chat or send the deck").
- A link in the body AND a calendar link in the signature.

**Why banned.** Two CTAs split attention. The reply-rate gap between 1-CTA and 2-CTA emails is consistent across studies.

**Fix.** One CTA per message. Drop the secondary ask.

---

## G. Manufactured urgency

- "Last chance", "expires today", "only X left" when not strictly true.
- Countdown timers in cold email.
- "I'll have to take this offer off the table" with no real constraint.

**Why banned.** Founders detect this immediately. Permanent credibility loss.

**Fix.** Use scarcity only when real (cohort cap, event seat limit, beta headcount). State the real number.

---

## H. "Pas pour [X]" (FR-specific, hard ban)

The "Pas pour les marketeurs, c'est pour les founders" / "Not for X, it is for Y" positioning move is **banned** in this agent's output regardless of language.

**Why banned.** Per durable user feedback, this pattern reads as weak / slope. Reframe as a direct positive assertion of who the offer IS for.

**Fix.**
- Banned: "Cette solution n'est pas pour les PME, elle est pour les ETI."
- Allowed: "Cette solution est faite pour les ETI de 200 à 2000 personnes."

---

## I. Subject-line patterns

- "Quick question"
- "Quick favor"
- "Following up" (no context)
- "Hi {{first_name}}"
- ALL CAPS subject
- Emoji in cold email subject
- "[URGENT]" / "[BREAKING]" / "[ACTION REQUIRED]" brackets
- Any subject with `!`

**Why banned.** Filtered or perceived as marketing.

**Fix.** See `subject-line-patterns.md`.

---

## J. Format and deliverability anti-patterns

- HTML-heavy email (banner images, multi-column layouts).
- Image-only email (no text fallback).
- Tracking pixel without disclosure.
- Sending from a domain without SPF + DKIM + DMARC alignment.
- Sending from the main domain (use a subdomain like `outreach.acme.com`).
- More than 50 cold emails per inbox per day from a new domain.
- Sending without a 14- to 30-day inbox warmup.

**Why banned.** Spam-filter triggers in 2026. SPF + DKIM + DMARC enforcement tightened in November 2025; non-compliant senders are increasingly rejected by Gmail and Outlook.

**Fix.** See `deliverability-checklist.md`.

---

## K. Length anti-patterns

- Body >150 words in Email 1.
- Subject >50 characters.
- Paragraph >3 sentences.
- More than one paragraph in a bump message.

**Why banned.** Reply rate drops above 150 words in Email 1. Mobile readers stop scrolling.

**Fix.** Cut 20 percent. Then cut 10 percent more.

---

## L. Personalization anti-patterns

- Personalization that resolves to "your company" or "your work".
- Token referencing a field that does not exist in the prospect CSV.
- Same `{{specific_observation}}` value across multiple prospects.
- A token that, if missing, breaks the sentence (e.g. "I saw your post on " + nothing).

**Why banned.** Empty or generic tokens read worse than no personalization at all.

**Fix.** Pre-fill all tokens before sending. Drop the prospect from the batch if a critical token cannot be filled.

---

## Summary checklist

Before shipping any message, verify:

- [ ] No AI-tells in the first sentence (EN list A, FR list B).
- [ ] No banned jargon (EN list C, FR list D).
- [ ] No hedging (list E).
- [ ] One CTA per message (list F).
- [ ] No manufactured urgency (list G).
- [ ] No "Pas pour [X]" pattern (list H).
- [ ] Subject not in banned list (list I).
- [ ] Plain-text or minimal HTML, SPF/DKIM/DMARC aligned (list J).
- [ ] Body under length target (list K).
- [ ] All personalization tokens pre-filled and concrete (list L).

A message failing any item is not ready.
