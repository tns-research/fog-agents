# Copywriting Structures (cold outreach)

7 reusable structures for writing the body of a cold message. For each: the mechanic, when to use it, the dominant Cialdini levers, and a worked example.

Pairs with `applying-cialdini-to-cold-email/SKILL.md` (lever assignment) and `copywriting-en/SKILL.md` (style rules).

**Length targets are shape only too.** The caps that block are those of `limits.json`, applied by `scripts/lint_outreach.py` (signature excluded): an email warns from 80 words in message 1 and 70 in a follow-up, and blocks over 90; a LinkedIn connection note blocks over 45 words or 200 characters, a LinkedIn follow-up over 60 words. When a structure's range below goes past a cap, write it to the cap.

**Worked examples are shape only.** The examples hold no figure: every proof point is a `<slot>` that a real message fills from `positioning.proof` or a sourced fact, or drops. Never invent a count or a result to fill a slot. In a real message, a proof point comes from `positioning.proof` in `project-context` or from a source URL recorded in the report, or the line is written without proof (claims gate: `shared/skills/enforcing-claims-policy/SKILL.md` at the repo root).

---

## 1. AIDA (Attention, Interest, Desire, Action)

**Mechanic.**
1. **Attention.** Hook that stops the scroll (stat, question, surprising fact).
2. **Interest.** Develop the hook, create curiosity or tension.
3. **Desire.** Concrete benefit for the reader.
4. **Action.** One CTA, one option.

**When to use.** Cold inbound, prospect with no shared context. Higher cognitive load than PAS or Resource Share, so use sparingly.

**Cialdini levers.** Authority (Interest), Liking (Desire), Commitment (Action).

**Length target.** 80 to 110 words.

**Worked example (EN, B2B SaaS to ops lead).**
```
Most dashboards a growth-stage team ships answer a question nobody asked twice.

We rebuilt the question, not the dashboard. <Named customer from positioning.proof> <sourced result>. Same data, different surface.

{{first_name}}, if your team is shipping more dashboards than they are using, this might be worth 15 minutes.

Worth a Thursday?
```

---

## 2. BAB (Before, After, Bridge)

**Mechanic.**
1. **Before.** Describe the painful current state, in 1 to 2 lines. Empathy, not judgement.
2. **After.** Concrete vision of the resolved state. Specific numbers, not "things will be better".
3. **Bridge.** One sentence connecting the two via your offer.

**When to use.** Emotional / transformational benefit. Solo founders, stuck-at-MVP teams, anyone who has tried and failed.

**Cialdini levers.** Liking (Before), Unity (Before), Reciprocity optional in Bridge.

**Length target.** 80 to 120 words.

**Worked example (EN, founders with no traction).**
```
Working on customer acquisition alone is exhausting. You have the product, you have the vision, but the first 20 customers have not arrived fast enough.

<Proof from positioning.proof, for example a named founder and what changed for them>. What changed was not the tools: it was a clear weekly cadence.

That is the gap we close. {{first_name}}, want me to walk you through what changed for them? 20 minutes.
```

---

## 3. PAS (Problem, Agitate, Solve)

**Mechanic.**
1. **Problem.** Name the precise problem in one line.
2. **Agitate.** Concrete consequences if unresolved. Factual, not alarmist.
3. **Solve.** Your offer as the natural answer. No pitch tone, just the result + CTA.

**When to use.** Pain is well known and articulated by the ICP. Acquisition stuck, hiring blocked, burn-rate climbing.

**Cialdini levers.** Liking (Problem framing matches their language), Reciprocity (Solve gives a concrete win).

**Length target.** 70 to 110 words.

**Worked example (EN, partnership outreach).**
```
{{platformName}} hosts early-stage founders, and many stall before their first 10 customers.

Without help, those projects quietly close. That is abandoned listings on your platform and frustrated founders.

<Proof from positioning.proof about founders helped past that wall, or drop this sentence>. A {{platformName}} + Founders partnership could change the curve for your community. Worth a 20-minute exchange?
```

---

## 4. PPP (Praise, Picture, Push)

**Mechanic.**
1. **Praise.** Specific compliment grounded in a real public achievement (raise, launch, post, talk). Never generic.
2. **Picture.** Project the next level possible from that achievement.
3. **Push.** Light invitation, not pressure.

**When to use.** Research has been done, public artifact visible. Ideal for VCs, public-facing founders, recently funded teams.

**Cialdini levers.** Liking (Praise), Authority (Picture references your track), Commitment (Push).

**Length target.** 90 to 130 words.

**Worked example (EN, VC relationship-building).**
```
Saw {{fundName}}'s recent investments in {{sector}} {{stage}} startups. The deal flow on that segment is hard to access, and your portfolio shows you have a real angle on it.

We work with founders at exactly that stage, and a few of them are starting to look for an investor with your specific {{sector}} expertise.

Not a pitch. Curious whether early access to those deals would be useful for {{fundName}}.
```

---

## 5. Resource Share

**Mechanic.** Give value first (resource, guide, intro) before asking for anything. The email does not sell; it offers.

**When to use.** Founders past MVP with first customers, audiences who have already seen many cold pitches. Often the highest-conversion structure when the resource is genuinely useful.

**Cialdini levers.** Reciprocity only.

**Length target.** 50 to 90 words.

**Worked example (EN, post-MVP founders).**
```
{{first_name}}, finding the first 10 customers tends to stall at the same few steps.

We wrote them down: a short checklist, free, a few minutes to read.

Want me to send it?
```

---

## 6. Challenge Status Quo

**Mechanic.** Question a belief or default the ICP holds. Pattern interrupt. Disruption gets attention better than a standard pitch.

**When to use.** Market leaders, early adopters, opinionated audiences with established views in their domain.

**Cialdini levers.** Authority (you have data they do not), Curiosity (technically not Cialdini, but adjacent).

**Length target.** 90 to 130 words.

**Worked example (EN, founder-acquisition opinion).**
```
Most founders we talk to look for a co-founder before their first 10 customers.

<Sourced finding, with its source in the report: for example what the founders in positioning.proof did first>. Customers came before the co-founder, not after.

That changes the priority order.

{{first_name}}, if you are in "find customers first" mode, want to compare notes? 15 minutes.
```

---

## 7. Sujan 4-Step (ultra-short)

**Mechanic.**
1. Who I am (1 line).
2. Why I am writing (1 line).
3. What I offer (1 line).
4. CTA (1 line).

**When to use.** Cold follow-ups (>2 weeks no reply), very busy prospects, when other emails have not landed. Ultra-short = low friction.

**Cialdini levers.** Commitment (refers to prior touch), Liking (terse, respects time).

**Length target.** 40 to 70 words.

**Worked example (EN, follow-up).**
```
I am {{sender_first_name}}, co-founder at <Company>.

I wrote 3 weeks ago about the first-10-customers gap.

We help founders close that gap; if it is still your bottleneck, I am around.

Interested or should I close the loop?
```

---

## Summary table

| Structure | Length | Best context | Cialdini levers |
|-----------|-------:|--------------|-----------------|
| AIDA | 80 to 110 words | Cold inbound, no context | Authority, Liking, Commitment |
| BAB | 80 to 120 words | Solo founders, MVP stuck | Liking, Unity |
| PAS | 70 to 110 words | Known pain, partnership | Liking, Reciprocity |
| PPP | 90 to 130 words | Public achievement, VCs | Liking, Authority, Commitment |
| Resource Share | 50 to 90 words | Post-MVP, busy audiences | Reciprocity only |
| Challenge Status Quo | 90 to 130 words | Opinionated, market leaders | Authority |
| Sujan 4-Step | 40 to 70 words | Cold follow-up, very busy | Commitment, Liking |

---

## Notes

The structures are not mutually exclusive. A 6-message sequence often combines: Resource Share (Email 1) + Sujan 4-Step (Email 2 bump) + AIDA or PAS (Email 3 value drop).

Avoid using the same structure for 3+ messages in a row. Variety reads as human; repetition reads as template.
