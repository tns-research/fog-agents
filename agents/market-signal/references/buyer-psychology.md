# Buyer psychology lenses (Cialdini)

Reference for `extracting-psychographic-profile`, Steps A to D. It helps read the verified quotes for **what persuades this buyer**, so the persona and the mined copy say which kind of evidence the segment trusts.

Source framework: Robert Cialdini, *Influence: The Psychology of Persuasion* (1984; new and expanded edition 2021) for the first six principles, and *Pre-Suasion* (2016), which added Unity as the seventh.

These lenses classify what people wrote. `market-signal` only extracts: it never invents a quote or a claim.

---

## The seven lenses, applied to a corpus

| Principle | What it means | Signals to look for in quotes | What to note in the persona |
|-----------|---------------|-------------------------------|-----------------------------|
| **Reciprocity** | People feel obliged to return a favor. | Praise for vendors who gave something first: a free template, a generous free tier, a helpful founder reply. Resentment at gated "free" resources. | Whether a useful free artifact is a credible first touch for this segment. |
| **Commitment and consistency** | People act in line with what they already said or did. | "We've always used X", sunk-cost language, public stances ("I'll never pay for Y"), long-held workflows. | Overlaps with the JTBD Habit force. Record the prior commitment the switch has to respect. |
| **Social proof** | People follow what similar people do. | "Everyone in r/<sub> recommends...", "what do other <role>s use?", asking for peer recommendations before buying. | Which peers the segment copies (same role, same size, same community), and where they ask. |
| **Authority** | People defer to credible experts. | Citing a known practitioner, a standard, a regulator, an accountant, a certification; distrust of self-proclaimed experts. | Which authorities the segment names, and which they dismiss. |
| **Liking** | People say yes to people they like and relate to. | Warmth toward founder-led brands, "the founder answered me personally", irritation at faceless support. | Whether a founder-to-founder voice is an asset for this segment. |
| **Scarcity** | Things seem more valuable when they are rare or about to go away. | Fear of losing a grandfathered price, a sunset feature, a closing deadline (tax dates, renewals). | Real deadlines in the buyer's calendar. Never invent one. |
| **Unity** | People favor those who share an identity with them. | "As a solo founder...", "for us freelancers...", in-group vocabulary, community identity markers. | The shared identity the segment claims, in its own words. |

---

## How to use it in the profile

No field of `analysis.json` or of the sidecar stores a lens: a lens guides choices, the quotes carry the proof.

1. While picking quotes (Step A), note which principle is clearly visible in a quote, if any; most quotes carry none.
2. In the persona `context` (Step B), name in words the kinds of evidence the segment trusts when the same lens shows up across several authors, with no number; the quotes that show it go in the persona's force lists or behind its hooks.
3. For hooks and angles (Steps C and D), prefer headline quotes that carry the segment's dominant lens. The line stays verbatim; the lens only guides which quote to pick, and an angle's `why` may name it.
4. A lens the corpus does not show is not claimed. Absence is a finding too.

## Guardrails

- A lens is an interpretation. Wherever one is named, a quote id sits next to it so a reader can check.
- Do not stack lenses on one quote to make it look richer; one clear lens or none.
- Downstream agents (`cold-outreach-builder`, `static-ads-builder`, `carousel-builder`, `landing-page-analyzer`) read the persona through the handoff sidecar. They apply these principles only with proof the founder actually holds (claims gate in `shared/skills/enforcing-claims-policy/SKILL.md` at the repo root).
