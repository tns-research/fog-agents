# LEVER 80-Criterion Checklist (SaaS landing pages)
# Framework: Cost, Trust, Usability, Comprehension, Motivation

**Role.** This file is the **scoring source** for the audit. Use it to assign OK / Partial / Missing / N/A per criterion (desktop and mobile), compute points, and fill the LEVER score tables and the page total (/100) in the report. For qualitative observations and visual-only criteria, use `visual-criteria-checklist.md` and `mobile-ux-checklist.md` instead.

**Notation.** OK | Partial | Missing | N/A
(OK = 2 pts, Partial = 1 pt, Missing = 0 pts, N/A = excluded from denominator)

**SaaS adaptation.** This rubric replaces e-commerce concepts (collection / product / cart) with SaaS landing-page concepts: hero copy, value proposition, primary CTA, social proof, pricing, signup form, demo booking, trust badges. Keep the 16-per-dimension structure and the 100-point total.

---

## COST: perceived friction (16 criteria)
*Reduce financial, time, and psychological friction to commit*

| # | Criterion | Desktop | Mobile | Note |
|---|-----------|---------|--------|------|
| C1 | Pricing visible on the same page or in the top nav (no "request a quote" stall when product is sub-$5k) | | | |
| C2 | Free tier, free trial, or money-back is named explicitly above the fold or near the primary CTA | | | |
| C3 | "No credit card required" stated when applicable, near the signup CTA | | | |
| C4 | Time-to-value commitment named ("Setup in 5 minutes", "Live in 1 day") | | | |
| C5 | Trial length and what happens after trial end is clear (no auto-charge surprise) | | | |
| C6 | Cancellation policy is one click away or stated near pricing | | | |
| C7 | Plan tiers are easy to compare (table layout, recommended plan highlighted) | | | |
| C8 | Currency and tax treatment match the visitor's locale (or the toggle is obvious) | | | |
| C9 | Annual vs monthly toggle present with the savings shown | | | |
| C10 | Signup form collects only fields needed for the immediate next step (≤ 4 fields preferred) | | | |
| C11 | SSO / Google / GitHub / Microsoft login offered when relevant | | | |
| C12 | "What's NOT included" is clear (avoids upgrade-shock) | | | |
| C13 | Setup or migration support offered (concierge, importer, free onboarding) for higher tiers | | | |
| C14 | Demo booking is short (≤ 4 fields, calendar embed, no qualification gauntlet) | | | |
| C15 | Effort signposted ("Connect your stack in 3 steps", screenshots of empty state) | | | |
| C16 | No hidden cost or surprise upgrade path mid-funnel | | | |

---

## TRUST: credibility (16 criteria)
*Strengthen credibility, legitimacy, and perceived security*

| # | Criterion | Desktop | Mobile | Note |
|---|-----------|---------|--------|------|
| T1 | Professional, coherent design that matches the price point and audience | | | |
| T2 | No typos, broken layout, lorem ipsum, or visible placeholder copy | | | |
| T3 | Customer logos visible above the fold or within the first scroll, and they are recognizable to the target ICP | | | |
| T4 | At least one testimonial with full name, photo, role, company, and a concrete outcome metric | | | |
| T5 | Third-party verification widget present (G2, Capterra, Trustpilot, Product Hunt) when applicable, linked to the live profile | | | |
| T6 | Press mentions or "as seen on" linked to the actual articles, not images of logos only | | | |
| T7 | Founder or team presence on the page (signed letter, Loom video, About link) | | | |
| T8 | Security or compliance badges (SOC 2, ISO 27001, GDPR, HIPAA) shown only if legitimate, with link to a status or trust page | | | |
| T9 | Privacy policy and terms of service linked in the footer, accessible without scrolling traps | | | |
| T10 | Data handling addressed near the signup form when collecting personal or business data | | | |
| T11 | Customer count, AUM, transactions processed, or comparable scale metric named when honest | | | |
| T12 | Awards, integrations with trusted brands, or partnership badges shown with permission | | | |
| T13 | Support reachable from the page (chat, email, docs, status page link) | | | |
| T14 | No suspicious external references that hurt credibility (broken affiliate badges, dead vendor links) | | | |
| T15 | Footer is complete: contact, legal, social, about, blog, status, security | | | |
| T16 | HTTPS active and a security cue is visible at signup (no mixed-content warning) | | | |

---

## USABILITY: experience (16 criteria)
*Smooth navigation, interaction, and progression to conversion*

| # | Criterion | Desktop | Mobile | Note |
|---|-----------|---------|--------|------|
| U1 | Primary CTA is visible above the fold on desktop (1280 wide) and mobile (390 wide) | | | |
| U2 | Primary CTA repeats at logical decision points (after value prop, after social proof, near pricing, in footer) | | | |
| U3 | Primary CTA visually dominant (contrast, size, position) and distinct from secondary CTAs | | | |
| U4 | CTA copy is action-led ("Start free trial", "Book a 15-min demo") not generic ("Submit", "Learn more") | | | |
| U5 | Navigation is minimal on a landing page (≤ 5 items) or removed entirely on a dedicated funnel page | | | |
| U6 | No intrusive elements blocking action (cookie banner is dismissable, exit-intent modal not auto-firing on first scroll, no scroll-jacking) | | | |
| U7 | Touch targets ≥ 44 px with ≥ 8 px spacing on mobile | | | |
| U8 | Form input types are native and correct (`type="email"`, `type="tel"`, `inputmode="numeric"`) | | | |
| U9 | Form errors are inline and human-readable, not generic "Invalid" messages | | | |
| U10 | Page weight reasonable: hero LCP element preloaded, no auto-playing video over 5 MB on first paint | | | |
| U11 | Visual hierarchy guides the eye to the first decision point in under 2 seconds (clear H1, single dominant CTA) | | | |
| U12 | No layout shift during load (CLS < 0.1, see `mobile-ux-checklist.md`) | | | |
| U13 | Anchor links and sticky tab nav work and do not block the CTA | | | |
| U14 | Smooth keyboard navigation (visible focus states, tab order matches reading order) | | | |
| U15 | Calendar embed (Cal, Calendly, Savvycal) loads or has a fallback link to the booking URL | | | |
| U16 | "Back to top" or scroll restoration so the user can re-find the CTA after deep-scrolling | | | |

---

## COMPREHENSION: clarity (16 criteria)
*Make the offer and next steps immediately clear*

| # | Criterion | Desktop | Mobile | Note |
|---|-----------|---------|--------|------|
| CO1 | H1 names the product or category in plain language a first-time visitor can parse | | | |
| CO2 | The hero answers "what does this do for me" within the first viewport | | | |
| CO3 | Above-fold copy mentions the target user (role, vertical, or pain) | | | |
| CO4 | One specific outcome metric in the hero ("save 6 hours per week", "30% lift in reply rate") rather than abstract value | | | |
| CO5 | No unexplained jargon or acronyms in the first viewport | | | |
| CO6 | The page has a single primary message, not 3 competing ones | | | |
| CO7 | Subheads are scan-readable: a visitor can grasp the page by reading only the H2s | | | |
| CO8 | A 3 to 5 step "how it works" section is present and visually clear | | | |
| CO9 | Visual proof of the product (screenshot, GIF, embedded demo) above or within the first scroll, not a stock illustration | | | |
| CO10 | At least one named use case or scenario shown ("teams using us for X") | | | |
| CO11 | Pricing breakdown is readable: what you get per tier, no per-seat math hidden in tooltips | | | |
| CO12 | Differentiator vs alternatives stated ("works with X" or "unlike Y, we...") when the category is crowded | | | |
| CO13 | FAQ section addresses the top 3 to 5 objections (security, integration, pricing, support, sunset risk) | | | |
| CO14 | Glossary or inline definitions for any technical term that survived the edit | | | |
| CO15 | Roadmap or "what's coming" linked when relevant for early-stage SaaS | | | |
| CO16 | Final CTA section repeats the offer in plain language ("Start your 14-day trial. No card. Cancel anytime.") | | | |

---

## MOTIVATION: desire (16 criteria)
*Increase desire, intent, and willingness to act now*

| # | Criterion | Desktop | Mobile | Note |
|---|-----------|---------|--------|------|
| M1 | Concrete outcome stated, not generic capability ("close 10 deals/month" beats "boost sales") | | | |
| M2 | The problem the page solves is named explicitly somewhere in the first half | | | |
| M3 | Specific use cases or scenarios are shown (not just abstract claims) | | | |
| M4 | Visual proof of result: dashboard with numbers, before/after, customer screen recording | | | |
| M5 | Emotional resonance: the page acknowledges the user's pain or aspiration in their own language (verbatim quotes from the corpus) | | | |
| M6 | Curiosity hook: there is a reason to keep scrolling beyond the hero | | | |
| M7 | "Why now" or differentiation vs alternatives is named | | | |
| M8 | Social proof is highlighted (best testimonials with named outcome, hero quote) | | | |
| M9 | Comparable customer named for the visitor's segment (if visitor is "Series A SaaS", show one) | | | |
| M10 | Honest urgency when justified (cohort closes Friday, pricing increases Q3) and never fake | | | |
| M11 | Risk reversal restated near the final CTA (free trial, money-back, cancel anytime) | | | |
| M12 | Peer endorsement: founder-LinkedIn pull-quote, podcast clip, X post embedded | | | |
| M13 | "Why we built this" or founder story present (humanizes the product) | | | |
| M14 | Final-CTA section motivates with one specific outcome, not generic "Get started today" | | | |
| M15 | "Continue exploring" path (docs, blog, changelog) for the not-yet-ready visitor | | | |
| M16 | Page closes with a one-sentence hook that names the cost of doing nothing | | | |

---

## Scoring

| Lever | Criteria | Max points | Score |
|-------|----------|-----------:|------:|
| Cost | 16 | 20 | /20 |
| Trust | 16 | 20 | /20 |
| Usability | 16 | 20 | /20 |
| Comprehension | 16 | 20 | /20 |
| Motivation | 16 | 20 | /20 |
| **TOTAL** | **80** | **100** | **/100** |

**Per criterion:** OK = 2 pts, Partial = 1 pt, Missing = 0 pts, N/A = excluded from denominator.
**Per lever:** `(points obtained / applicable points) * 20`.
**Total:** sum of the 5 levers, out of 100.

**Weighted scoring layer.** The point system above gives a coverage score (how much of the rubric the page satisfies). The findings table in the report adds a weight per finding using `impact * frequency * severity`, each on 1 to 5. See `skills/auditing-lever-heuristics/SKILL.md` for the formula and the confidence-rating protocol.

---

## Format notes

- Each criterion has a stable ID (`C1`, `T7`, `U16`, ...). Do not renumber when iterating; append.
- The Desktop and Mobile cells are independent. A page can pass C1 on desktop and miss it on mobile.
- The Note cell records the observation that justifies the score. Keep it short (≤ 12 words) and verbatim where possible.
- Criteria that genuinely do not apply (e.g. enterprise-only pricing on a self-serve page) are scored N/A and excluded from the denominator.
