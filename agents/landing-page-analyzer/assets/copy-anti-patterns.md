# Copy anti-patterns

**Role.** Audit the page's copy for the patterns that consistently underperform. Each anti-pattern is paired with a "fix direction" so the agent can suggest a rewrite trajectory in the report. The actual two-alternative rewrites for the H1, primary CTA, and value-prop section are produced via `skills/proposing-copy-rewrites/SKILL.md`, which references this file.

These anti-patterns are scored as flags (present / not present) and listed in a "Copy anti-pattern flags" subsection of the report.

---

## 1. Hedging

### What it looks like
> "We believe we can help you grow."
> "Our platform may help reduce churn."
> "We aim to make sales easier."

### Why it underperforms
The visitor reads hedging as the company hedging its claims. If the company is unsure, why should the visitor commit?

### Fix direction
Replace with a direct assertion backed by the strongest customer outcome on the page.

> Before: "We believe we can help you grow."
> After: "Teams using us close 30% more deals in 90 days."

---

## 2. Jargon without definition

### What it looks like
> "Real-time AI-driven workflow orchestration for revenue ops."

### Why it underperforms
If a first-time visitor cannot decode the H1 in 5 seconds, they leave. Jargon without a plain-language counterpart in the next paragraph forces a translation step the visitor will not perform.

### Fix direction
Either remove the jargon or follow it with a plain-language sentence in the next paragraph. Keep the jargon if the audience expects it (developer tools to engineers); drop it for cross-functional buyers.

> Before: "AI-driven workflow orchestration."
> After: "Automate the steps your sales team copy-pastes between Salesforce and Slack."

---

## 3. Feature-listing without outcome

### What it looks like
> "Real-time dashboards. Custom reports. SSO. SOC 2."

### Why it underperforms
Features answer "what does it have" but not "what does it do for me". The visitor's next-action threshold is determined by the second answer, not the first.

### Fix direction
Pair every feature with the outcome it produces. Or lead with the outcome and reveal the features below.

> Before: "Real-time dashboards."
> After: "See revenue at risk this quarter without waiting for the Monday meeting."

---

## 4. Unsupported superlatives

### What it looks like
> "The world's leading platform for X."
> "Industry-leading."
> "Best-in-class."
> "Cutting-edge."
> "Revolutionary."

### Why it underperforms
Self-asserted superlatives carry no information. They signal absence of proof. A reader trained on marketing copy will skim past or disengage.

### Fix direction
Replace with a specific, sourced claim, or remove. If the page genuinely is the category leader, cite the source (G2 grid Q3 2026, Forrester wave, etc.).

> Before: "Industry-leading email deliverability."
> After: "98.4% inbox placement on the last 10M emails sent (Litmus, March 2026)."

---

## 5. Hero copy about you, not the visitor

### What it looks like
> "We are a passionate team building the next generation of project management."
> "Our mission is to empower teams everywhere."

### Why it underperforms
The visitor's first question is "what does this do for me", not "who are you". A hero that answers the wrong question burns the most attention-rich part of the page.

### Fix direction
Move the company-about copy to the About page. Open the hero with the visitor's situation or the product's outcome.

> Before: "We are a passionate team rethinking sales tools."
> After: "Run a sales team without spending Mondays in spreadsheets."

---

## 6. No specific number anywhere

### What it looks like
A page where the entire above-the-fold and the next 2 sections contain no metric: no "30% more", no "5 minutes", no "10,000 users", no "$2.3B".

### Why it underperforms
Numbers anchor. They give the reader something concrete to remember. Pages that score well on this criterion typically have at least one number in the hero, one in the social-proof block, and one in the value-prop section.

### Fix direction
Audit the strongest customer outcome on the page. Surface its number to the hero. Repeat numbers in social proof and the value-prop section.

> Before: "Save time on outreach."
> After: "Send 5x more outbound without hiring an SDR."

---

## 7. Banned superlatives list

When auditing, flag any of these unless paired with a specific source on the same screen:

- "world-class"
- "cutting-edge"
- "revolutionary"
- "next-generation"
- "game-changing"
- "industry-leading"
- "best-in-class"
- "state-of-the-art"
- "groundbreaking"
- "disruptive"
- "innovative" (when used about the product itself)
- "scalable" (when used as a virtue without a specific scale)

These are noise words. The page that uses three or more of them in the hero almost always underperforms a page that uses zero.

---

## 8. AI-tells in copy

Patterns from generative output that read as low-effort:

- "In today's fast-paced world..."
- "Whether you're a small team or a large enterprise..."
- "Take your X to the next level."
- "Empower your team with..."
- "Streamline your workflow."
- "Unlock the full potential of..."
- "Seamlessly integrate..."

If three or more of these appear on the page, flag as Critical. The page reads as auto-generated and will be rejected by sophisticated buyers.

---

## 9. Generic CTAs

### What it looks like
- "Submit"
- "Get Started"
- "Learn More"
- "Click Here"
- "Sign Up"

### Why it underperforms
Generic CTAs do not reduce uncertainty about what happens next. "Get Started" with what? Is a card required? How long does this take?

### Fix direction
Action verb plus specific outcome plus optional risk reversal.

> Before: "Get Started"
> After: "Start free trial. No card needed."

> Before: "Learn More"
> After: "Watch the 90-second demo"

> Before: "Submit"
> After: "Send my report"

---

## 10. Multiple CTAs of equal weight

### What it looks like
Three buttons in the hero: "Sign up", "Book demo", "Watch video", all visually identical.

### Why it underperforms
The visitor is forced to make a choice rather than commit to a path. Decision paralysis lowers commitment rate.

### Fix direction
Identify the primary conversion goal. That goal gets the visually dominant CTA. Other actions become secondary (ghost button, text link).

---

## 11. Long blocks of text without scannable structure

### What it looks like
A 6-paragraph wall of body copy under a single H2.

### Why it underperforms
Visitors scan, they do not read. They read 20 to 28% of the words on the page. Long unbroken paragraphs are skipped entirely.

### Fix direction
Break into shorter blocks: H3 + 2 to 3 sentences + supporting bullet. Use bolding for the load-bearing claim. Use bullet lists for parallel features.

---

## 12. Missing or weak risk reversal

### What it looks like
A signup CTA with no mention of what happens if the user does not love it. No "free trial", no "money-back", no "cancel anytime".

### Why it underperforms
Visitors weigh perceived risk. A 14-day free trial with no card converts better than a free tier with hidden upgrade pressure. Risk reversal lowers the activation energy.

### Fix direction
Add the strongest honest risk reversal near the primary CTA. "No card needed" beats "free to try". "30-day money back" beats "cancel anytime".

---

## How to use in the report

In the report, render flagged anti-patterns as:

| # | Anti-pattern | Where on page | Severity (1 to 5) | Fix direction |
|---|--------------|----------------|------------------:|---------------|
| 1 | Hedging in hero | H1 + subhead | 5 | Replace with direct assertion + customer metric |
| 2 | Generic CTA copy | Primary CTA above fold | 4 | Action verb + outcome + risk reversal |
| 3 | Three banned superlatives | Hero, value prop, footer | 3 | Strip or replace with specific claim |

The full rewrites for the H1, primary CTA, and value prop are produced via the dedicated `skills/proposing-copy-rewrites/SKILL.md`, which uses this file as the diagnostic input.
