# A/B test hypothesis template

**Role.** A reusable structure for writing A/B test hypotheses that are falsifiable, segment-specific, and mechanism-explicit. Used in the "A/B test hypotheses" section of the report. The audit produces up to 5 hypotheses, only those backed by an audit finding, ranked by the strength of that finding and by effort.

A hypothesis that lacks any of the components below is not a hypothesis, it is a guess. Reject it before running the test.

---

## The structure

> **Because** [data observation],
> **we believe** [specific change to the page]
> **will** [direction of the metric movement, on a named primary metric]
> **for** [segment]
> **because** [behavioral mechanism].

Required slots:

1. **Data observation.** What you saw in the audit, analytics, session recordings, or interview corpus that prompted the hypothesis. Not a hunch. A number in this slot comes from the founder's analytics or the audit evidence, with its source.
2. **Specific change.** A single, isolatable change. Not "redesign the hero". "Replace the H1 from X to Y".
3. **Predicted movement.** Direction (increase or decrease) on one named primary metric. The agent never predicts a lift size: no benchmark supports one for a specific page. The only magnitude in the hypothesis is the **minimum detectable effect** (MDE) the founder's traffic can detect, computed below.
4. **Segment.** Which visitors should respond. "All visitors" is rarely correct; mobile cold paid traffic and desktop branded traffic respond differently.

The "because <mechanism>" tail is what separates a hypothesis from a wishful change. If you cannot name the behavioral mechanism, the test is uninformed.

In the worked examples below, values in angle brackets (`<n>%`) are slots for the founder's own analytics. Never fill them with a made-up figure.

---

## Worked example 1: hero copy

> **Because** analytics show `<n>%` of mobile visitors leave before the second viewport, and the 10-second test could not say what the product does from the H1 "We help teams collaborate better",
> **we believe** replacing it with "Run async standups in a few minutes a day"
> **will** increase signup conversion
> **for** mobile cold paid traffic from Google Ads
> **because** the new H1 names a specific outcome and time commitment, reducing the effort needed to understand what the product does before deciding to scroll.

Why this works. Data observation is concrete (scroll-past rate, failed comprehension test). Change is isolated (H1 only). Direction and metric named. Segment narrowed to where the test will run. Mechanism stated (comprehension cost).

---

## Worked example 2: trust signal placement

> **Because** session recordings show visitors hover over the "Companies using us" logo bar (`<n>%` of sessions) but rarely click any logo, and the primary CTA has no trust element next to it,
> **we believe** moving the logo bar from below the value prop to directly above the primary CTA, plus adding one named testimonial pull-quote next to it,
> **will** increase primary-CTA click rate
> **for** desktop visitors who scrolled past the hero
> **because** trust friction is the binding constraint at the CTA, not awareness; positioning trust adjacent to action reduces the gap between intent and click.

---

## Worked example 3: form length

> **Because** the demo-booking form has 7 fields and the analytics funnel shows `<n>%` of visitors who start the form do not finish,
> **we believe** reducing the form to 3 fields (work email, company, calendar slot)
> **will** increase form-completion rate
> **for** all visitors who reach the booking page
> **because** every extra field is extra effort before the reward, and the 4 cut fields (job title, team size, current tool, urgency) can be inferred or asked during the call.

---

## Worked example 4: primary CTA copy

> **Because** the current CTA "Get Started" has a hero click rate of `<n>%` and the copy anti-pattern audit flags it as generic,
> **we believe** replacing the CTA with "Start free trial. No card needed."
> **will** increase hero CTA click rate
> **for** all visitors
> **because** specifying the action plus the risk reversal removes two objections (cost commitment, payment-method commitment) that the visitor would otherwise need to scroll to resolve.

---

## Worked example 5: pricing visibility

> **Because** the pricing page is gated behind a "Contact sales" CTA and analytics show `<n>%` of homepage visitors click "Pricing" in the nav, then bounce within seconds,
> **we believe** showing the self-serve plan cards on the pricing page with a "Talk to sales" link for higher tiers
> **will** increase pricing-page-to-signup rate and decrease pricing-page bounce
> **for** small-team visitors inferred from referral source and on-page signals
> **because** the segment expects self-serve pricing; gating it forces them into a sales motion they will not enter, so they leave rather than convert.

---

## Sample size: the formula, not a rule of thumb

Use the standard sample size for comparing two proportions, two-sided alpha 0.05, power 80%:

```
n per arm = ( z_a * sqrt(2 * p_avg * (1 - p_avg)) + z_b * sqrt(p1 * (1 - p1) + p2 * (1 - p2)) )^2 / (p2 - p1)^2

p1    = baseline conversion rate of the tested metric (from the founder's analytics)
p2    = p1 * (1 + relative lift to detect)
p_avg = (p1 + p2) / 2
z_a   = 1.96   (two-sided alpha 0.05)
z_b   = 0.8416 (power 0.80)
```

`n` counts units of the metric's denominator: sessions for a page conversion rate, form starts for a form-completion rate.

Worked values (computed with the formula above):

| Baseline `p1` | Relative lift to detect | `p2` | Sessions per arm |
|---------------|-------------------------|------|------------------|
| 3% | 10% | 3.3% | about 53,200 |
| 3% | 20% | 3.6% | about 13,900 |
| 5% | 10% | 5.5% | about 31,200 |
| 30% | 10% | 33% | about 3,800 |

The required sample grows fast as the baseline rate drops: a fixed "N sessions per arm" rule only holds for one baseline. Always compute from the founder's own `p1`.

Stdlib one-liner to compute it:

```bash
python3 -c "from statistics import NormalDist as N; from math import sqrt; p1,rel=0.03,0.10; p2=p1*(1+rel); pa=(p1+p2)/2; za,zb=N().inv_cdf(0.975),N().inv_cdf(0.8); print(round((za*sqrt(2*pa*(1-pa))+zb*sqrt(p1*(1-p1)+p2*(1-p2)))**2/(p2-p1)**2))"
```

**Turn it into a decision.** Duration in weeks = `2 * n per arm / weekly units on the tested page`. Work backwards too: from the weekly traffic the founder can give the test, state the smallest relative lift it can detect (the MDE). When the test would need more traffic than the page gets in a period the founder accepts, say so plainly and propose a lighter method instead: a dated before/after comparison, a preference test, or five user interviews. Never present an underpowered A/B test as conclusive.

When the baseline rate or the traffic is unknown, write "Min sample: needs baseline rate and weekly traffic" instead of a number.

---

## Hypothesis quality checklist

Before adding a hypothesis to the report, verify each row:

| # | Check | Pass? |
|---|-------|-------|
| 1 | Data observation is sourced (audit finding, analytics, recording, quote, interview) | yes / no |
| 2 | The proposed change is a single, isolatable variable | yes / no |
| 3 | Predicted direction is stated, with no predicted lift size | yes / no |
| 4 | Primary metric is named | yes / no |
| 5 | Segment is narrower than "all visitors" when traffic is mixed | yes / no |
| 6 | Behavioral mechanism is named, not "because we think it will work" | yes / no |
| 7 | The hypothesis is falsifiable (a clear way it could lose) | yes / no |
| 8 | Sample size computed with the formula above from the founder's baseline, or marked as missing inputs | yes / no |

A hypothesis that fails 1, 6, or 7 is not testable, drop it. A hypothesis that fails 5 or 8 needs more setup before running.

---

## Output table for the report

Render the hypotheses in the report as:

| # | Hypothesis (Because / we believe / will / for / because) | Primary metric | Direction | Segment | Baseline (source) | MDE | Min sample per arm | Effort |
|---|-----------------------------------------------------------|----------------|-----------|---------|-------------------|-----|--------------------|--------|
| 1 | <full hypothesis> | signup conversion | increase | mobile cold paid | `<p1>` (analytics, `<date range>`) | `<relative lift>` | `<n from the formula>` | low |
| 2 | <full hypothesis> | form completion | increase | demo-booking visitors | unknown | n/a | needs baseline rate and weekly traffic | low |

The sample size is a planning estimate for the founder to check against their traffic. It is computed, not guessed: if an input is missing, the cell says which one.
