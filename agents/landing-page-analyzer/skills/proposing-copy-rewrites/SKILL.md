---
name: proposing-copy-rewrites
description: Produces two alternative rewrites each for the H1, the primary CTA, and the value-prop section of a landing page. Detects the underlying copy anti-pattern (hedging, jargon, feature-listing, unsupported superlatives, hero about you, no specific number) and writes targeted rewrites in the brand's apparent tone, using verbatim customer language when available. Triggers on "rewrite", "copy alternative", "headline rewrite", "CTA rewrite", "two variants".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read
---

# proposing-copy-rewrites

Methodology for proposing copy rewrites for the three highest-leverage copy locations on a landing page:

1. **H1 (hero headline)**
2. **Primary CTA**
3. **Value-prop section** (the supporting copy that follows the hero, often a 2 to 4 sentence block or a 3-bullet list)

For each location, the skill produces:

- The **anti-pattern flag** detected (which underlying issue is making the current copy underperform).
- **Two alternative rewrites** the founder can pick or A/B test.
- A **mechanic note** explaining why each alternative should perform better.

The skill never produces just one rewrite. Two alternatives force a comparison and surface the trade-off (concise vs specific, benefit-led vs problem-led).

---

## When to invoke

The agent's `AGENT_LANDING_PAGE_ANALYZER.md` workflow points here at Step 6, after the LEVER findings are ranked. The skill consumes the anti-pattern findings from `assets/copy-anti-patterns.md` and produces the "## Top 3 copy rewrites" section of the report.

---

## Inputs

- `current_h1` (string): the current H1 verbatim from the page.
- `current_subhead` (string): the supporting line below the H1.
- `current_cta_copy` (string): the primary CTA button text.
- `current_value_prop` (string or block): the value-prop section copy.
- `goal` (string): conversion goal (signup / demo / purchase / waitlist / contact).
- `target_user` (string): who the page is for (role, vertical, ICP).
- `customer_quotes` (list, optional): verbatim quotes from `market-signal` corpus or interviews. Strongest source of authentic language.
- `competitor_examples` (list, optional): how 2 to 3 competitors phrase their hero. Used to differentiate, not to copy.

---

## Anti-pattern detection

Before rewriting, identify which anti-pattern the current copy exhibits. Reference `assets/copy-anti-patterns.md` for the full list. The most common in hero copy:

| Anti-pattern | Diagnostic | Rewrite direction |
|--------------|-----------|--------------------|
| Hedging | "We believe", "may help", "aim to" | Direct assertion + customer metric |
| Jargon without definition | Acronym or technical term not paired with plain-language follow-up | Strip or follow with plain sentence |
| Feature-listing | List of capabilities with no outcome | Lead with outcome, reveal features below |
| Unsupported superlative | "Industry-leading", "best-in-class", "cutting-edge", "revolutionary" | Strip or replace with sourced specific |
| Hero about you | "We are a passionate team..." | Move company-about copy to About; open with the visitor's situation |
| No specific number | Whole hero with no metric | Surface the strongest customer outcome metric |
| AI-tells | "In today's fast-paced world", "take your X to the next level" | Strip; rewrite from scratch with verbatim customer language |
| Generic CTA | "Submit", "Get Started", "Learn More", "Click Here" | Action verb + outcome + risk reversal |

The flag is reported in the rewrite output so the founder sees the diagnostic, not just the alternatives.

---

## The two-alternative rule

Every rewrite produces **exactly two alternatives**. The two must differ on at least one axis to give the founder a meaningful choice.

### H1 axes

| Axis | Alternative A | Alternative B |
|------|---------------|---------------|
| Concise vs specific | Short, punchy, abstract benefit | Longer, named outcome with number |
| Benefit-led vs problem-led | "Send 5x more outbound" | "Stop spending Mondays on outreach" |
| Outcome vs identity | "Save 6 hours a week on reporting" | "Reporting that actually finishes by Friday" |

### Primary CTA axes

| Axis | Alternative A | Alternative B |
|------|---------------|---------------|
| Concise vs reassurance-heavy | "Start free trial" | "Start free trial. No card needed." |
| Action vs outcome | "Book 15-min demo" | "See it in action (15 min)" |

### Value-prop axes

| Axis | Alternative A | Alternative B |
|------|---------------|---------------|
| Outcome bullets vs narrative | 3 bullets: outcome metric + use case + named customer | One paragraph telling the user's day before / after |
| Generalist vs ICP-specific | Speaks to the broad audience | Names the specific role / vertical / company size |

The two alternatives must not differ on filler (synonym swap). If A and B feel like rewrites of the same idea, redo.

---

## Procedure

### Step 1: Detect anti-pattern

1. Read the current H1, subhead, CTA copy, and value-prop section.
2. Match against the anti-pattern table in `assets/copy-anti-patterns.md`.
3. Flag the dominant anti-pattern. Multiple may apply; pick the one most responsible for the underperformance.

### Step 2: Pull authentic language

4. If `customer_quotes` are available, read them. The strongest hero copy paraphrases (not summarizes) the customer's own words.
5. If only competitor copy is available, extract the language the category uses, then **avoid copying** to differentiate. Same-category sameness is itself an anti-pattern.

### Step 3: Choose the rewrite axes

6. Pick the two axes from the table above (one per alternative).
7. Sketch the alternatives. Use plain language. Avoid the full banned-superlatives list in `assets/copy-anti-patterns.md`.
8. Verify each alternative addresses the anti-pattern. If A and B both still hedge, both fail.

### Step 4: Verify against rules

For each alternative, run the checklist:

| # | Check | Pass? |
|---|-------|-------|
| 1 | Specific outcome named (number when honest, scenario when not) | yes / no |
| 2 | No banned superlative ("world-class", "cutting-edge", "revolutionary", etc.) | yes / no |
| 3 | No hedging ("we believe", "may", "aim to") | yes / no |
| 4 | Plain language; no jargon unexplained | yes / no |
| 5 | Visitor-centric, not company-centric | yes / no |
| 6 | One sentence (H1, CTA) or one short paragraph (value prop) | yes / no |
| 7 | Verbatim or near-verbatim customer language when source available | yes / no |
| 8 | Differentiated from competitors (not the category cliché) | yes / no |

A rewrite that fails 1, 3, or 5 must be redone. Failures on 2, 4, 6, 7, 8 should be discussed in the mechanic note.

### Step 5: Write the mechanic note

For each alternative, one sentence explaining why it should perform better than the current copy. The note grounds the rewrite in a behavioral mechanism, not in style.

> Example: "Alternative A names a specific outcome (5x outbound) which gives the visitor a measurable benefit to remember; the current copy uses an abstract benefit (better outreach) that has no anchor."

---

## Output

```markdown
## Top 3 copy rewrites

### 1. H1 (current)

> We help modern sales teams collaborate better.

**Issue:** Hedging ("we help") plus a non-specific outcome ("collaborate better"). No number. Audience ("modern sales teams") is too broad.
**Anti-pattern flag:** hedging, no-specific-number, audience-too-broad.

**Alternative A** (concise, outcome-led):
> Close 30% more deals without hiring another rep.

*Mechanic.* Names a specific outcome (30%) and an alternative cost (hiring), giving the visitor two anchors instead of an abstract benefit.

**Alternative B** (specific, problem-led):
> Stop losing deals because your reps work in 6 different tools.

*Mechanic.* Names the visitor's specific pain (tool sprawl) instead of a generic benefit; pulls authentic language from the corpus ("losing deals", "6 tools").

### 2. Primary CTA (current)

> Get Started

**Issue:** Generic CTA copy. No action specificity, no risk reversal.
**Anti-pattern flag:** generic-cta.

**Alternative A:**
> Start free trial. No card needed.
*Mechanic.* Removes the most common signup objection (card required) at the moment of click.

**Alternative B:**
> Book 15-min demo
*Mechanic.* Names the action (book) plus the time commitment (15 min). Lower psychological cost than an unbounded "demo".

### 3. Value-prop section (current)

> Our platform offers real-time dashboards, custom reports, SSO, SOC 2, and integration with all your favorite tools to help you work smarter.

**Issue:** Feature-listing without outcome. Banned filler ("favorite tools", "work smarter"). No named customer or number.
**Anti-pattern flag:** feature-listing, ai-tells, no-specific-number.

**Alternative A** (3 outcome bullets):
> - Cut Monday-morning reporting from 4 hours to 15 minutes.
> - See revenue at risk this quarter without waiting for the QBR.
> - Used by 12 Series A SaaS leaders to give their RevOps team time back.

*Mechanic.* Three outcome statements, each with a number or a named ICP, replacing 5 unranked features.

**Alternative B** (narrative):
> Mondays used to start with 4 hours of reporting. Sales leaders running on this stack now ship the same report in 15 minutes, with one click. Their RevOps team has Mondays back.

*Mechanic.* Day-before / day-after structure makes the change tangible. The visitor projects themselves into the after-state.
```

---

## Failure modes

- **No customer quotes available.** Note in the rewrite mechanic that the alternative is hypothesis-driven; recommend a 5-respondent customer-language interview as a follow-up.
- **The current copy is so generic the rewrites would be invented from scratch.** That IS the finding: the page does not currently communicate anything specific. Both alternatives become "create a specific value proposition" examples; the founder must pick one to validate.
- **Brand tone is unclear from the rest of the site.** Default to "founder-direct, no jargon, no superlatives" and note the assumption in the rewrite output.
- **Foreign-language original.** Rewrite in the same language. If the agent is running in English and the page is French, ask the user whether to keep the report in English (with French rewrites) or switch the report to French.

---

## Notes

- Two alternatives is the rule, not three. Three alternatives push the founder into choice paralysis. Two forces a real comparison.
- Use verbatim customer language when available (cross-cutting C5). "Closing the loop" beats a paraphrase. The rewrite IS the customer's words, not the agent's interpretation of them.
- Preserve apparent brand tone where possible. If the brand reads as playful, the rewrites should not be corporate. If the brand reads as enterprise-formal, the rewrites should not be casual.
- The skill produces the rewrite, the agent's report inserts it into the `## Top 3 copy rewrites` section per `assets/output-template.md`.
