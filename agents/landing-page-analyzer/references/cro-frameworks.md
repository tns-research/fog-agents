# CRO frameworks: LEVER, CXL, LIFT, NN/g

**Role.** Cross-walk between the four most-used CRO heuristic frameworks. Helps the agent and the reader see how a finding under one framework maps to another. The audit is run with **LEVER** as the primary framework (the 340-criterion grid in `assets/lever-grid.md`); the other frameworks are referenced for triangulation and to make the report intelligible to founders trained in any of them.

---

## LEVER (this stack)

The Lever Framework comes from the CRO agency Conversion.com ([introduction](https://conversion.com/blog/lever-framework/), [white paper](https://conversion.com/ebook-whitepaper/levers-framework/)). It is a three-level tree, not an acronym: 5 **master levers**, split into **levers**, split into **sub-levers**. Conversion.com uses it to tag experiments and find which levers win on a given site; this stack uses the same tree to organize its audit grid. Every row of `assets/lever-grid.md` belongs to exactly one sub-lever.

| Master lever | Question it answers | Levers (sub-levers) |
|--------------|---------------------|---------------------|
| **Cost** | What will this cost me in money, time and effort? | Financial cost (known cost, anticipated cost, relative value); Soft cost (time cost, effort cost) |
| **Trust** | Is this legitimate, are the claims true, is my data safe? | Legitimacy (UI quality, brand recognition); Credibility (authority, social proof, customer service); Security (payment security, personal information requests) |
| **Usability** | Can I get from arrival to conversion without friction? | User flow (location, direction); Effort (experienced, anticipated); Choice (findability, structure); Attention (distraction, engagement); Persistence (progress presentation, positive feedback) |
| **Comprehension** | Do I understand the category, the product and the transaction? | Education (educational content); Product understanding (product information, product depiction); Transactional understanding (savings understanding, payment structure) |
| **Motivation** | What is in it for me, and why now? | Value statement (value proposition, benefits); Motivational depiction (imagery, video); Preview access (full trials, limited free content); Obligation (reciprocity, altruism); Sociability (community, exclusivity); Urgency (availability, price change); Product range (new product, variety); Delivery (speed, ease); Gamification (immersion, progression, competition) |

LEVER is the most balanced of the four for landing pages because Cost and Motivation get their own master lever; CXL collapses Cost into Friction.

---

## CXL Institute (Peep Laja and the CXL conversion research curriculum)

5 dimensions:

| CXL dim | What it covers |
|---------|----------------|
| Clarity | Headline and subhead, message hierarchy, scan-readability |
| Relevancy | Match between traffic source intent and page content |
| Value | Perceived benefit minus perceived cost |
| Friction | Anything that increases the cost or reduces the conversion probability |
| Distraction | Elements competing with the primary conversion path |

CXL is more academic and emphasizes Relevancy (audit the traffic source plus message match) more than the others. It's the best framework when running paid media because it forces a separate scoring of "did the ad promise match the page".

### Cross-walk (LEVER to CXL)

| LEVER | Maps to CXL |
|-------|-------------|
| Comprehension | Clarity (1:1) |
| Motivation | Value, partly Relevancy |
| Trust | Trust is implicit in CXL, often filed under Friction (lack of trust = friction) |
| Usability | Friction, Distraction |
| Cost | Friction (CXL collapses friction broadly) |

---

## LIFT (WiderFunnel)

6 factors, two of which are negative:

| LIFT factor | Direction | What it covers |
|-------------|-----------|----------------|
| Value Proposition | + | The core promise of the page |
| Relevance | + | Match with visitor expectations |
| Clarity | + | Visual and message clarity |
| Distraction | - | Elements that compete with conversion |
| Anxiety | - | Doubt, risk perception, missing trust |
| Urgency | + | Reasons to act now |

LIFT is the most actionable for in-page edits because it explicitly separates the two negative factors (Distraction, Anxiety) so they can be addressed separately. CXL collapses both into "Friction".

### Cross-walk (LEVER to LIFT)

| LEVER | Maps to LIFT |
|-------|--------------|
| Comprehension | Clarity, Value Proposition |
| Motivation | Value Proposition, Urgency |
| Trust | Anxiety (inverted; high trust = low anxiety) |
| Usability | Distraction, Clarity |
| Cost | Anxiety, Distraction |

---

## NN/g (Nielsen Norman Group) usability heuristics

10 heuristics (1994, refreshed 2020). General UX, not CRO-specific. Most relevant to the Usability dimension of the LEVER rubric.

1. Visibility of system status
2. Match between system and the real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Help users recognize, diagnose, and recover from errors
10. Help and documentation

### Cross-walk (NN/g to LEVER)

| NN/g heuristic | Most relevant LEVER dim |
|-----------------|--------------------------|
| 1. Visibility of system status (loading, validation, success states) | Usability |
| 2. Match real-world language (no jargon) | Comprehension |
| 3. User control and freedom (no scroll-jacking, escape modal) | Usability |
| 4. Consistency and standards (CTAs look like CTAs) | Usability |
| 5. Error prevention (form validation, autocomplete) | Usability |
| 6. Recognition rather than recall (visible CTA, repeated nav) | Usability |
| 7. Flexibility (keyboard, accessibility) | Usability |
| 8. Aesthetic minimalism | Usability, Comprehension |
| 9. Error recovery (helpful messages) | Usability |
| 10. Help and docs (FAQ, support link) | Trust, Comprehension |

For a landing page, NN/g is most useful as a sanity check on Usability. It is less useful for the Motivation, Trust, and Cost dimensions because it does not address persuasion or credibility.

---

## Combined cross-walk table

When a finding could be classified under more than one framework, score it once under LEVER (the primary) and reference the equivalent in the other frameworks for the reader.

| LEVER | CXL | LIFT | NN/g |
|-------|-----|------|------|
| Comprehension | Clarity | Clarity, Value Proposition | 2, 8 |
| Motivation | Value, Relevancy | Value Proposition, Urgency | (low coverage) |
| Trust | Friction (anxiety component) | Anxiety (inverted) | 10 |
| Usability | Friction, Distraction | Distraction, Clarity | 1, 3, 4, 5, 6, 7, 9 |
| Cost | Friction | Anxiety, Distraction | (low coverage) |

---

## When to consult each framework

- **LEVER**: every audit. The default.
- **CXL**: when paid traffic is involved and the page is a destination for an ad. Adds the Relevancy axis explicitly.
- **LIFT**: when the page has a known low conversion rate and the goal is to identify which negative factor (Distraction or Anxiety) is binding.
- **NN/g**: for the Usability dimension only, when a deeper UX-heuristic pass is warranted (often for product UX more than landing pages).

---

## References

- LEVER: Conversion.com, Lever Framework, https://conversion.com/blog/lever-framework/. This stack's grid: `assets/lever-grid.md`.
- CXL: https://cxl.com (conversion research curriculum, Peep Laja).
- LIFT: https://www.widerfunnel.com (Chris Goward, "You Should Test That!").
- NN/g 10 usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/

These are pointers for further reading. The audit itself uses only the LEVER rubric for scoring; cross-walks are reference material for the report's reader.
