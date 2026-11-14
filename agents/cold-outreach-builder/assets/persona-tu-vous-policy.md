# Tu / Vous Policy (FR cold outreach)

Decision rules for `copywriting-fr/SKILL.md` on whether to address the prospect with `tu` or `vous`. The choice signals positioning as much as the words themselves.

---

## Default: vouvoiement

In B2B French cold outreach, **vouvoiement is the default** unless an explicit signal supports tutoiement. Vouvoiement is the safe choice; the cost of getting it wrong is small. Tutoiement when wrong reads as presumptuous and burns the message.

---

## Decision flow

The register follows what the person writes in public, as recorded in the dossier (`register` and `register_source_url` of `prospect.json`, see `skills/researching-prospects/SKILL.md`). Age and seniority are not observable and never decide it.

```
Does the dossier show the recipient using "tu" with peers
in public writing (posts, threads, newsletter, community)?
  yes → tutoyer allowed
  no  → continue

Is the sender introducing peer-to-peer
(co-founder talking to co-founder, same cohort)?
  yes → tutoyer
  no  → vouvoyer (default)
```

---

## Tutoiement signals (use with caution)

These signals support tutoyer, but never alone:

- Recipient writes in tu in fr-startup communities, Indie Hackers or tech threads (with the URL in the dossier).
- Recipient runs a B2C / D2C brand with a tu-tone marketing voice.
- Recipient is a recently launched solo founder posting in tu on LinkedIn.
- Sender and recipient share a known cohort (Y Combinator, The Family, École 42, a known accelerator) where tu is the norm.

Even with these signals, vouvoiement is acceptable. The cost of vouvoyer-when-tu-was-fine is near zero.

---

## Hard vouvoiement zones

Always vouvoyer regardless of other signals:

- Recipient is a VC, investor, or holds a leadership title (CEO, COO, CFO) at a 50+ company.
- Industry is institutional: banking, insurance, public sector, healthcare, legal.
- Email is corporate (`@bnpparibas.fr`, `@gouvernement.fr`, `@hopital-X.fr`, etc.).
- First contact and no other signal: default to vous.

---

## Phrasing equivalences

Adjust openings and CTAs to match the chosen register.

| Concept | Vouvoiement | Tutoiement |
|---------|-------------|------------|
| Opening | "Bonjour {{first_name}}," | "Salut {{first_name}}," |
| Direct address | "Vous avez écrit..." | "Tu as écrit..." |
| Question | "Cela vous parle ?" | "Ça te parle ?" |
| CTA | "Disponible jeudi 15h ?" | "Tu es dispo jeudi 15h ?" |
| Sign-off | "Bien à vous" | "À très vite" |

Never mix. A message starting with "Bonjour {{first_name}}" then ending with "À très vite" reads as automated.

---

## Non-binary edge cases

For prospects with French-non-native names or unclear cultural cues, default to vouvoyer. The cost of formality is lower than the cost of presumed informality.

For prospects whose first name uses an alternative spelling indicating non-binary or international identity, the policy does not change: register is about formality, not gender.

---

## Cadence and switch rules

- **Never switch register mid-sequence.** If Email 1 uses vous, Emails 2 to 6 use vous. Switching is read as the sender losing track.
- **If the prospect replies in tu**, the sender may switch to tu in the reply. Within the cold sequence (no reply yet), do not switch.
- **If the sender doubts**, vouvoyer. The default is robust.

---

## Examples

### Hard vouvoiement (VC outreach)
```
Bonjour {{first_name}},

Je vous écris à propos des récents investissements de {{fundName}} dans le segment SaaS B2B early-stage. La thèse {{sector}} {{stage}} est rare, et votre portfolio le démontre.

[...]

Je reste disponible pour un échange de 20 minutes jeudi.

Bien à vous,
{{sender_first_name}}
```

### Tutoiement (founder peer, post-MVP, active on LinkedIn in tu)
```
Salut {{first_name}},

J'ai vu ton post sur le passage de 5 à 20 clients. C'est l'étape sur laquelle on accompagne des fondateurs.

[...]

Si ça t'intéresse, je peux t'envoyer notre checklist en 12 points. Pas de call, juste le doc.

À très vite,
{{sender_first_name}}
```

---

## When in doubt

Default to vous. The penalty for vouvoyer-when-tu-was-fine is near-zero. The penalty for tutoyer-when-vous-was-required is the message read as familiar, immature, or pushy.

The agent's review-mode report flags any FR message where tu is used without a documented signal supporting it.
