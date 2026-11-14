---
name: copywriting-fr
description: Writes French cold-email and LinkedIn DM copy for B2B audiences. Defaults to vouvoiement; switches to tutoiement only on explicit cultural cue (founder-to-founder peer in early-stage tech, casual community, prior tu used by the prospect). Bans corporate calques, AI-tells translated from English, and the "Pas pour [X]" pattern. Use when the agent's `language: fr` flag is set or when the ICP is FR-speaking. Triggers on words like "écrire en français", "vouvoiement", "tutoiement", "FR copy".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# copywriting-fr

Methodology for writing French cold outreach copy. Pairs with `references/fr-copywriting-rules.md` (the rule reference) and `assets/persona-tu-vous-policy.md` (the tu/vous decision flow).

The structural prose of this SKILL is in English. The output (the message bodies) is in French.

---

## When to invoke

- Step 7 of the agent workflow when `language: fr`.
- Mixed-language ICPs: write FR for FR-speaking prospects, EN for the rest, the language is set per prospect in `messages.json`, and the templates of `cold-outreach-output.json` come in both languages.

---

## Inputs

- Same as `copywriting-en`.
- Plus `seniority` (founder | vp | manager | mixed): informs the tone; vous stays the default whatever the seniority.
- Plus `relationship_signal` (none | mutual | tu_already_used): if the prospect already used tu in a public post or to the sender, tu is allowed.

---

## Tu vs vous: decision flow

Default: **vouvoiement** in B2B. Always start with vous unless one of the conditions in `assets/persona-tu-vous-policy.md` is met.

Quick decision. The register comes from what the person writes in public, recorded in the dossier (`register` and `register_source_url` of `prospect.json`), never from an assumed age or seniority:

1. Does the dossier show the prospect addressing peers with "tu" in public writing (post, thread, newsletter, talk page)? → tu allowed.
2. Are sender and prospect both early-stage founders in the same community or cohort, and does the dossier show tu in that community? → tu allowed.
3. Is the prospect a manager-level or above in a corporate environment? → vous (always).
4. Is the prospect a VC, banker, lawyer, public-sector? → vous (always).
5. Otherwise → vous.

Switching from vous to tu inside a sequence is acceptable only after the prospect replies in tu. Never auto-switch after one accepted connection request.

---

## Banned phrasings (hard rules)

These phrases are banned in every FR cold message:

- **"Pas pour [X]"** as a positioning move ("Cette solution n'est pas pour les PME, elle est pour les..."). Always rewrite as a direct positive assertion of who it IS for.
- **"J'espère que ce message vous trouve bien"** and variants. This is an English AI-tell translated word-for-word.
- **"Je me permets de vous contacter"** when followed by a pitch. The phrase signals sales-speak and adds zero value.
- **Corporate calques**: "synergiser", "solutionner", "performer" (in the sense of doing well), "challenger" (as a verb), "scaler", "leverager".
- **"Booster"**, "exploser", "révolutionner", "disruptif", "next-level", "game-changer". (Same as `assets/banned-patterns.md` for EN, in their FR forms.)

---

## Hook / Body / CTA rules in FR

The structure is identical to `copywriting-en`. The differences are tonal.

### Hook

Strong FR patterns:
- "J'ai vu votre post sur <topic>." (vous) / "J'ai vu ton post sur <topic>." (tu)
- Direct observation, sans fioritures.
- A dated fact of their dossier in plain words: "Vous avez ouvert la bêta privée de <produit> le 29 septembre." A number appears only when it is in the fact's excerpt.

Weak FR hooks (rewrite):
- "Bonjour, j'espère que vous allez bien."
- "Permettez-moi de me présenter."
- "Suite à votre activité sur LinkedIn..."

### Body

Same cut-every-word discipline as EN. Active voice in FR is harder because passive feels natural; rewrite passive to active wherever possible.

FR-specific cuts:
- "Permettre de <verbe>" → use the verb directly. "Ce produit permet de gagner du temps" → "Ce produit fait gagner du temps".
- "Adresser un problème" → "traiter un problème" or "résoudre un problème".
- "Délivrer de la valeur" → "apporter de la valeur" or "créer de la valeur".
- "Implémenter" → "mettre en place" or "déployer".
- "Basé sur" → "fondé sur" (in formal contexts).

### CTA

Strong FR CTAs:
- vous: "Vous voulez que je vous l'envoie ?"
- vous: "15 minutes la semaine prochaine, vous êtes ouvert ?"
- tu: "Je te l'envoie ?"
- tu: "On en parle 15 min la semaine pro ?"

Weak FR CTAs:
- "N'hésitez pas à me recontacter." (no ask)
- "Dans l'attente de votre retour." (passive, generic)
- "Je reste à votre entière disposition." (corporate filler)

---

## Length targets

Same single source as `copywriting-en`: [`../../assets/limits.json`](../../assets/limits.json), applied by `scripts/lint_outreach.py` (words, characters of a LinkedIn connection note, subject, links). French usually takes more words than English for the same content: cut harder, never raise the limit.

Subject lines keep their accents ("votre bêta", "équipe"): sending tools encode headers in UTF-8, and a French reader reads "deja" or "equipe" as a typo.

## Hook, tiers and signature

Same rules as the "Personalization: the hook and the tiers" section of [`../copywriting-en/SKILL.md`](../copywriting-en/SKILL.md): tier A written for the person, tier B template plus a hook built on a verified fact, tier C nothing. The hook appears word for word in message 1. Every body ends with `{{sender_first_name}}` on its own line. Greeting by language: "Bonjour {{first_name}}," in French (never "Hey"), "Hi {{first_name}}," in English.

## Punctuation

- Espace insécable avant `:`, `;`, `!`, `?`. Most modern email clients handle the regular space; if your sending stack does not, use the regular space and accept the typographic compromise.
- Guillemets « » for quotes in formal copy. Straight quotes acceptable in informal tu copy.
- **No em-dash**. Replace with comma, period, or parenthesis.

---

## Output

Same structure as `copywriting-en`. The fields are in English, the message body is in FR.

```markdown
### Message N: <purpose> (Jour D)

**Subject:** `<sujet>`
**Body:**
> <corps en FR avec tokens>

**CTA:** <CTA en FR>
**Cialdini lever:** <principe>
**Personalization tokens:** `{{token1}}`, `{{token2}}`
**Word count:** N
**Tu/vous:** vous | tu
**Why this works for this ICP:** <one line in EN>
```

---

## Failure modes

- **Mixed tu/vous within one message** → pick one and apply consistently.
- **English calque slipped through** → grep the body for "permettez", "implémenter", "scaler", "synergie", "challenger" and rewrite.
- **"Pas pour [X]" pattern** → forbidden. Rewrite as positive assertion of who the offer IS for.
- **Subject contains "Question rapide"** → cliché, rewrite.

---

## Notes

The 10 mandatory FR copy rules (kill the text, nobody cares, no BS words, kill adverbs, active voice, short sentences, scannable, personalize, keep personality, benefits over features) live in `references/fr-copywriting-rules.md`. Read that file before drafting.
