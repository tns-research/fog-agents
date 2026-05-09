# A/B test hypothesis template

**Role.** A reusable structure for writing A/B test hypotheses that are falsifiable, segment-specific, and mechanism-explicit. Used in the "A/B test hypotheses" section of the report. The audit will produce 3 to 5 hypotheses ranked by expected lift and effort.

A hypothesis that lacks any of the four components below is not a hypothesis, it is a guess. Reject it before running the test.

---

## The structure

> **Because** [data observation],
> **we believe** [specific change to the page]
> **will** [predicted metric movement, with direction and magnitude]
> **for** [segment]
> **because** [behavioral mechanism].

Four required slots:

1. **Data observation.** What you saw in the audit, analytics, session recordings, or interview corpus that prompted the hypothesis. Not a hunch.
2. **Specific change.** A single, isolatable change. Not "redesign the hero". "Replace the H1 from X to Y".
3. **Predicted metric movement.** Direction (increase or decrease) and rough magnitude (10%, 25%) with a primary metric named.
4. **Segment.** Which visitors should respond. "All visitors" is rarely correct; mobile cold paid traffic and desktop branded traffic respond differently.

The "because <mechanism>" tail is what separates a hypothesis from a wishful change. If you cannot name the behavioral mechanism, the test is uninformed.

---

## Worked example 1: hero copy

> **Because** the current H1 "We help teams collaborate better" returns a 3.2% scroll-past rate (visitors leave before the second viewport),
> **we believe** replacing it with "Run async standups in 5 minutes a day"
> **will** lift signup conversion by 15 to 25%
> **for** mobile cold paid traffic from Google Ads
> **because** the new H1 names a specific outcome and time commitment, reducing the cognitive cost of figuring out what the product does in the first 5 seconds.

Why this works. Data observation is concrete (scroll-past rate). Change is isolated (H1 only). Movement direction and magnitude named. Segment narrowed to where the test will run. Mechanism stated (cognitive cost reduction in first 5 seconds).

---

## Worked example 2: trust signal placement

> **Because** session recordings show 40% of visitors hover over the "Companies using us" logo bar but only 8% click any logo,
> **we believe** moving the logo bar from below the value prop to directly above the primary CTA, plus adding one named testimonial pull-quote next to it,
> **will** lift primary-CTA click rate by 10 to 18%
> **for** desktop visitors who scrolled past the hero
> **because** trust friction is the binding constraint at the CTA, not awareness; positioning trust adjacent to action reduces the gap between intent and click.

---

## Worked example 3: form length

> **Because** the demo-booking form has 7 fields and 31% of visitors who start the form do not finish (analytics funnel),
> **we believe** reducing the form to 3 fields (work email, company, calendar slot)
> **will** lift form-completion rate by 25 to 40%
> **for** all visitors who reach the booking page
> **because** field count above 4 is the strongest single predictor of mobile form abandonment, and the 4 cut fields (job title, team size, current tool, urgency) can be inferred or asked during the call.

---

## Worked example 4: primary CTA copy

> **Because** the current CTA "Get Started" returns a 2.4% click rate from the hero, and copy anti-pattern audit flags it as generic,
> **we believe** replacing the CTA with "Start free trial. No card needed."
> **will** lift hero CTA click rate by 12 to 22%
> **for** all visitors
> **because** specifying the action plus the risk reversal removes two objections (cost commitment, payment-method commitment) that the visitor would otherwise need to scroll to resolve.

---

## Worked example 5: pricing visibility

> **Because** the pricing page is gated behind a "Contact sales" CTA and 18% of visitors who reach the homepage click "Pricing" in nav, then bounce within 8 seconds,
> **we believe** showing 3 self-serve plan cards on the pricing page (Starter $49, Pro $149, Business $299) with a "Talk to sales" link for higher tiers
> **will** lift pricing-page-to-signup rate by 20 to 35% and reduce pricing-page bounce by 10 to 15%
> **for** small-team visitors (1 to 20 employees) inferred from referral source and on-page signals
> **because** the segment expects self-serve pricing; gating it forces them into a sales motion they will not enter, so they leave rather than convert.

---

## Hypothesis quality checklist

Before adding a hypothesis to the report, verify each row:

| # | Check | Pass? |
|---|-------|-------|
| 1 | Data observation is sourced (audit finding, analytics, recording, quote, interview) | yes / no |
| 2 | The proposed change is a single, isolatable variable | yes / no |
| 3 | Predicted direction and magnitude are stated | yes / no |
| 4 | Primary metric is named | yes / no |
| 5 | Segment is narrower than "all visitors" when traffic is mixed | yes / no |
| 6 | Behavioral mechanism is named, not "because we think it will work" | yes / no |
| 7 | The hypothesis is falsifiable (a clear way it could lose) | yes / no |
| 8 | Minimum sample size estimated from current traffic | yes / no |

A hypothesis that fails 1, 6, or 7 is not testable, drop it. A hypothesis that fails 5 or 8 needs more setup before running.

---

## Output table for the report

Render the 3 to 5 hypotheses in the report as:

| # | Hypothesis (Because / we believe / will / for / because) | Primary metric | Predicted lift | Segment | Min sample | Effort |
|---|-----------------------------------------------------------|----------------|----------------|---------|------------|--------|
| 1 | <full hypothesis> | signup CTR | +15 to 25% | mobile cold paid | 4,000 visitors per arm | low |
| 2 | <full hypothesis> | form completion | +25 to 40% | demo-booking visitors | 600 starts per arm | low |
| 3 | <full hypothesis> | hero CTA CTR | +12 to 22% | all visitors | 6,000 visitors per arm | low |

Sample size is a planning estimate (rule of thumb: ≥ 1,000 events per arm, ≥ 4,000 sessions per arm for a 10% relative lift detection at 80% power). The agent does not run a power calculation; it surfaces the estimate so the user knows whether their traffic supports the test.
