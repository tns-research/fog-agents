# Landing Page Audit: <URL>

**Project:** <project-slug>
**Date:** YYYY-MM-DD
**URL audited:** <URL>
**Conversion goal:** <signup | demo | purchase | waitlist | contact>
**Target user:** <who>
**Language:** <en | fr>
**Run by:** landing-page-analyzer

---

## Summary

3 to 5 sentences. Lead with the single biggest blocker to conversion. Name the LEVER total (/100), the strongest dimension, the weakest dimension, and how many "ship this week" fixes are queued. No hedging, no recap of inputs.

### LEVER scorecard

| Dimension | Score (/20) | Verdict |
|-----------|------------:|---------|
| Cost (perceived friction) | X.X | <one line> |
| Trust (credibility) | X.X | <one line> |
| Usability (experience) | X.X | <one line> |
| Comprehension (clarity) | X.X | <one line> |
| Motivation (desire) | X.X | <one line> |
| **TOTAL** | **XX.X / 100** | <one line> |

Computation: per-criterion OK = 2, Partial = 1, Missing = 0, N/A excluded; per-lever `(points / applicable points) * 20`; total = sum of 5 levers. See `assets/lever-checklist-80.md`.

## 10-second comprehension test

| # | Question | Score (1 to 5) | Confidence |
|---|----------|---------------:|-----------|
| 1 | Could a first-time visitor say what this is? | X | low / med / high |
| 2 | Could they say who it's for? | X | low / med / high |
| 3 | Could they name one concrete benefit? | X | low / med / high |

**Verdict:** <pass / partial / fail>
**Why:** <one paragraph: what's clear, what's fuzzy, what's missing>
**Stimulus:** the rendered `desktop.png` (and `mobile.png`), not a mock.

## Findings by LEVER dimension

For each dimension below, list only criteria scored Partial or Missing. OK and N/A go to the tally count.

Severity = 1 (cosmetic) to 5 (kills conversion).
Weight = `impact * frequency * severity` per skill (each on 1 to 5; max weight 125).
Confidence = low / med / high (low when only the markdown is available, high when both screenshots and markdown confirm).

### Cost (perceived friction)

| # | Criterion (ID from rubric) | Status | Severity | Weight | Confidence | Note |
|---|----------------------------|--------|---------:|-------:|-----------|------|
| C5 | Trial end behavior unclear | Partial | 4 | 48 | high | <observation> |
| ... | ... | ... | ... | ... | ... | ... |

### Trust (credibility)

*(repeat the table)*

### Usability (experience)

*(repeat the table)*

### Comprehension (clarity)

*(repeat the table)*

### Motivation (desire)

*(repeat the table)*

## Mobile and visual findings

Mobile checks from `assets/mobile-ux-checklist.md`. Visual checks from `assets/visual-criteria-checklist.md`. Findings that overlap with the LEVER rubric are tagged `(LEVER ref)` and not double-counted in scoring.

| # | Check (ID) | Viewport | Status | Severity | Confidence | Note |
|---|------------|----------|--------|---------:|-----------|------|
| TM1 | Touch targets ≥ 44 px | Mobile | Partial | 3 | high | <observation> |
| PM1 | LCP under 2.5 s | Mobile | Missing | 4 | low | <observation, low conf because no runtime data> |
| V2 | Eye guided to primary CTA | Mobile | Partial | 4 | high | <observation> |

## Trust audit

Per `assets/trust-signals-taxonomy.md`. Strength tier S (strongest) to F (counter-productive).

| Layer | Present? | Strength | Observation |
|-------|----------|----------|-------------|
| Testimonials | yes / partial / no | <S/A/B/C/D/F> | <one line> |
| Customer logo bar | yes / partial / no | <tier> | <one line> |
| Third-party verification (G2, Capterra, Trustpilot) | yes / partial / no | <tier> | <one line> |
| Press and recognition | yes / partial / no | <tier> | <one line> |
| Compliance / security | yes / partial / no | <tier> | <one line> |
| Founder presence | yes / partial / no | <tier> | <one line> |
| Customer counts and scale | yes / partial / no | <tier> | <one line> |
| Footer completeness | yes / partial / no | <tier> | <one line> |

## Copy anti-pattern flags

Per `assets/copy-anti-patterns.md`. Only patterns flagged as present.

| # | Anti-pattern | Where on page | Severity | Fix direction |
|---|--------------|---------------|---------:|---------------|
| 1 | Hedging in hero | H1 + subhead | 5 | Replace with direct assertion + customer metric |
| 2 | Generic CTA copy | Primary CTA above fold | 4 | Action verb + outcome + risk reversal |

## Top 5 fixes: ship this week

Ranked by `impact * ease`. Both on 1 to 5.

| # | Fix | Where | Impact | Ease | Score | Owner | ETA |
|---|-----|-------|-------:|-----:|------:|-------|-----|
| 1 | <fix> | <H1 / hero / CTA / form> | 5 | 5 | 25 | dev / copy | 30 min |
| 2 | <fix> | <section> | 5 | 4 | 20 | copy | 1 h |
| 3 | <fix> | <section> | 4 | 5 | 20 | dev | 30 min |
| 4 | <fix> | <section> | 4 | 4 | 16 | copy + dev | 2 h |
| 5 | <fix> | <section> | 5 | 3 | 15 | design | 1 day |

## Top 3 copy rewrites

Produced via `skills/proposing-copy-rewrites/SKILL.md`. Each issue gets two alternatives the founder can pick or A/B test. Tone follows the brand's apparent voice on the rest of the site.

### 1. H1 (current)

> <current H1>

**Issue:** <why it underperforms, ref to anti-pattern>
**Anti-pattern flag:** <hedging / jargon / feature-listing / superlative / about-you / no-number>

**Alternative A** (concise, benefit-led):
> <rewrite>

**Alternative B** (specific, problem-led):
> <rewrite>

### 2. Primary CTA (current)

> <current CTA>

**Issue:** <why>

**Alternative A:**
> <rewrite>

**Alternative B:**
> <rewrite>

### 3. Value prop section (current)

> <current copy>

**Issue:** <why>

**Alternative A:**
> <rewrite>

**Alternative B:**
> <rewrite>

## A/B test hypotheses

Per `assets/ab-hypothesis-template.md`. Each hypothesis fills the four required slots (data observation, specific change, predicted movement, segment, mechanism).

| # | Hypothesis (Because / we believe / will / for / because) | Primary metric | Predicted lift | Segment | Min sample | Effort |
|---|-----------------------------------------------------------|----------------|----------------|---------|------------|--------|
| 1 | <full hypothesis> | signup CTR | +15 to 25% | mobile cold paid | 4,000 / arm | low |
| 2 | <full hypothesis> | form completion | +25 to 40% | demo-booking | 600 / arm | low |
| 3 | <full hypothesis> | hero CTA CTR | +12 to 22% | all visitors | 6,000 / arm | low |

## Recommendations

3 to 5 actions ranked by impact. Each: action, rationale, first concrete step. Pulled from the Top 5 above plus any cross-cutting theme that spans dimensions (e.g. "the page lacks any specific number, fix in 4 places").

## Methodology

- LEVER framework (Cost, Trust, Usability, Comprehension, Motivation) applied via the 80-criterion rubric in `assets/lever-checklist-80.md`. Per-criterion OK / Partial / Missing / N/A scoring with 2 / 1 / 0 / excluded points. Per-lever score out of 20, total out of 100.
- Weighted scoring per finding: `impact * frequency * severity`, each on 1 to 5. See `skills/auditing-lever-heuristics/SKILL.md`.
- Confidence rating per finding: `low` (markdown only, no screenshot evidence), `med` (one viewport confirms), `high` (both desktop and mobile screenshots plus markdown confirm).
- Multi-evaluator protocol when two evaluators disagree on Partial vs Missing: see `skills/auditing-lever-heuristics/SKILL.md` (calibration round, independent scoring, consolidation).
- Page captured at desktop (1280 x 900) and mobile (390 x 844). Cookie banners auto-dismissed by the capture script.
- 10-second comprehension test on the rendered page (`desktop.png`), not on a mock.
- Visual criteria from `assets/visual-criteria-checklist.md` (V1 to V10).
- Mobile UX criteria from `assets/mobile-ux-checklist.md` (touch targets, INP / CLS / LCP, lazy-load discipline).
- Trust audit from `assets/trust-signals-taxonomy.md`.
- Copy anti-patterns from `assets/copy-anti-patterns.md`.
- A/B hypotheses from `assets/ab-hypothesis-template.md`.
- Findings ranked by `impact * ease`, both 1 to 5.

## Limitations

- Single-page audit only. Multi-step flows (signup, onboarding, activation, billing) are out of scope.
- No runtime performance data (Lighthouse, WebPageTest) unless the user supplies it. Mobile PM1 to PM5 (LCP, INP, CLS, lazy-load, third-party scripts) are scored at low confidence from visual and markdown evidence alone.
- A/B hypothesis sample sizes are estimates assuming current traffic.
- Auth-gated content cannot be captured automatically. The user must provide screenshots if the page is behind login.
- Cookie-banner dismissal in the capture script handles common patterns; non-standard banners may persist.

## Sources

- Page capture: `screenshots-<YYYYMMDD>/desktop.png`, `screenshots-<YYYYMMDD>/mobile.png` (saved alongside this report)
- Page markdown: `firecrawl scrape <URL> --format=markdown --only-main-content`
- LEVER 80-criterion rubric: `agents/landing-page-analyzer/assets/lever-checklist-80.md`
- Visual criteria: `agents/landing-page-analyzer/assets/visual-criteria-checklist.md`
- Mobile UX criteria: `agents/landing-page-analyzer/assets/mobile-ux-checklist.md`
- Trust signal taxonomy: `agents/landing-page-analyzer/assets/trust-signals-taxonomy.md`
- Copy anti-patterns: `agents/landing-page-analyzer/assets/copy-anti-patterns.md`
- A/B hypothesis template: `agents/landing-page-analyzer/assets/ab-hypothesis-template.md`
- Multi-framework cross-walk (LEVER, CXL, LIFT, NN/g): `agents/landing-page-analyzer/references/cro-frameworks.md`

## Sidecar JSON

A machine-readable sidecar `landing-audit-<YYYYMMDD>.json` is written next to this report (cross-cutting C1). Schema:

```json
{
  "url": "<URL>",
  "date": "YYYY-MM-DD",
  "goal": "signup | demo | purchase | waitlist | contact",
  "target_user": "<who>",
  "lever_scores": { "cost": 0.0, "trust": 0.0, "usability": 0.0, "comprehension": 0.0, "motivation": 0.0, "total": 0.0 },
  "comprehension_test": { "what_is_it": 0, "who_for": 0, "benefit": 0, "verdict": "pass | partial | fail" },
  "findings": [
    {
      "id": "C5",
      "dimension": "Cost",
      "criterion": "Trial end behavior unclear",
      "status": "Partial",
      "severity": 4,
      "impact": 4,
      "frequency": 4,
      "weight": 48,
      "confidence": "high",
      "viewport": "desktop | mobile | both",
      "note": "<short observation>"
    }
  ],
  "trust_audit": [ { "layer": "testimonials", "present": true, "tier": "B", "note": "..." } ],
  "copy_anti_patterns": [ { "pattern": "hedging", "where": "hero", "severity": 5 } ],
  "top_fixes": [ { "rank": 1, "fix": "...", "where": "...", "impact": 5, "ease": 5, "score": 25, "owner": "copy", "eta": "30 min" } ],
  "ab_hypotheses": [ { "rank": 1, "hypothesis": "...", "metric": "signup CTR", "predicted_lift": "+15 to 25%", "segment": "mobile cold paid", "min_sample_per_arm": 4000, "effort": "low" } ]
}
```

---

*Generated by `landing-page-analyzer` on YYYY-MM-DD. Founders Growth Agent Stack. LEVER framework, 80-criterion rubric.*
