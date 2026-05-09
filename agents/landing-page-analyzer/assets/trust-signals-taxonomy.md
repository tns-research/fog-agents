# Trust signals taxonomy

**Role.** Audit each trust layer on the page. The goal is to score not just the presence of a signal but its strength. A logo bar of 12 unrecognizable companies is weaker than one named testimonial with a metric. A SOC 2 badge with no link is weaker than a status page link. Rank by quality, not count.

This taxonomy feeds the "Trust audit" subsection of the report and informs the Trust dimension scoring in `lever-checklist-80.md`.

---

## 1. Testimonials

### Tiers (strongest to weakest)

| Tier | Pattern | Strength |
|------|---------|----------|
| S | Full name + photo + role + company + outcome metric (with number) | Strongest |
| A | Full name + photo + role + company + qualitative outcome | Strong |
| B | Full name + role + company, no photo | Moderate |
| C | First name only + role | Weak |
| D | Anonymous quote ("Sarah, Marketing Director") | Very weak |
| F | Marketing-written quote with no attribution | Counter-productive |

### What to look for

- Photo. A real headshot beats no photo. A photo from the company's About page beats a stock photo.
- Outcome metric. "Closed 30% more deals" beats "great tool". Numbers anchor.
- Role and company. Match to the visitor's ICP. A testimonial from a 50-person SaaS for an enterprise audience underdelivers.
- Length. 2 to 4 sentences. Long testimonials read as marketing. One-liners read as fake.
- Recency cue. A date or recent role makes the testimonial harder to fake.

### Anti-patterns

- All testimonials are 5 stars and identically structured. Reads as fabricated.
- Testimonials are screenshots of tweets that no longer exist or are not linked.
- The same person quoted in 3 different places on the same page.

---

## 2. Customer logo bar

### Strength order

1. Logo bar of recognizable companies in the visitor's ICP, with permission.
2. Logo bar of recognizable companies outside the ICP, with permission.
3. Logo bar of small or unfamiliar companies.
4. Logo bar of companies that did not authorize the use (counter-productive: legal risk, perception risk).

### What to look for

- Permission. If a logo is shown, the brand should be a real customer. Look for case studies linking the same logos.
- Recognizability. The visitor needs to recognize at least 2 of 5 logos for the bar to function. Count logos but weight by recognizability.
- Density. 5 to 7 logos beats 12. Past 7, the bar reads as cluttered.
- Pairing. A logo bar should anchor the strongest case study or testimonial. Logo + named outcome from that logo is the highest-converting trust pattern.

### Anti-patterns

- Logo bar where every logo is at the same visual weight as the body copy. Indicates undersized logos.
- Animated rotating logo carousel that hides logos under animation. Looks dynamic, performs worse.
- "Trusted by 10,000+ teams" with no logos. Asserted credibility without proof.

---

## 3. Third-party verification

### Widgets

- G2 (B2B SaaS reviews). Embed widget with star rating linked to the live profile. Below 4.5 stars, the widget can hurt; weigh before showing.
- Capterra / GetApp (Gartner Digital Markets). Same logic.
- Trustpilot (broader audience, more consumer / SMB). Strongest in EU.
- Product Hunt (launch and early-stage badges). Showing a 2-year-old PH badge dates the page; remove or refresh.
- App store ratings (mobile, browser extensions). Embed the live count and stars.

### What to look for

- Linked, not screenshot. A G2 image with no link is weaker than an embedded widget that links to the profile.
- Live counts. Static "4.9 stars from 200+ reviews" reads as old. Live widgets refresh.
- Distribution match. A Trustpilot widget on a $50k ACV enterprise page reads as wrong fit; G2 and Capterra fit better.

---

## 4. Press and recognition

### Strength order

1. Press logo bar where each logo links to the actual article.
2. Pull-quote from the article displayed alongside the logo.
3. Press logo bar with no link (purely decorative).
4. "As seen on" with logos that no longer match the article (link rotted).

### What to look for

- Linked. Click each logo. If it does not lead to the article, downgrade the signal.
- Recency. "Featured in TechCrunch in 2018" is weaker than "Featured in The Information last month".
- Relevance. A Forbes feature is impressive; a Forbes Council Contributor post is paid placement (downgrade).

### Anti-patterns

- "As seen on" logos with no link. Often visitors assume bought placement.
- Logos of awards from pay-to-play directories.

---

## 5. Compliance and security badges

### Legitimate signals

- SOC 2 Type II report (link to a trust portal or status page that lists the report).
- ISO 27001.
- GDPR data processing agreement linked from the privacy page.
- HIPAA BAA available for healthcare-relevant SaaS.
- PCI DSS (for payment-handling products).
- A trust page (often `<domain>/trust` or `<domain>/security`) linked from the footer.

### What to verify

- The badge links somewhere. A static SOC 2 image is unverifiable.
- The certification is current. SOC 2 Type II reports are dated; an expired one is worse than none.
- The audit firm is named. "SOC 2 audited by Deloitte" beats an unnamed image.

### Anti-patterns

- Made-up "Bank-grade encryption" or "Military-grade security" without specification.
- Compliance badges shown for compliance the company has not achieved (legal exposure).
- HIPAA badge on a non-healthcare product (false signal of safety theater).

---

## 6. Founder and team presence

### Patterns (strongest to weakest)

1. Founder Loom or short video on the landing page (face + voice + 60 to 120 seconds explaining what and why).
2. Signed letter from the founder, with photo and signature, addressing the visitor's pain.
3. About page link with team photos.
4. LinkedIn link to the founder.
5. No founder presence at all.

### What to look for

- Specifically named pain. The founder should reference the visitor's situation, not their own bio.
- Recency. A "Hello, I'm <founder>" with a photo from 5 years ago hurts.
- Reachability. The founder's email or LinkedIn DM linked from the about page is a strong signal for early-stage SaaS targeting other founders.

---

## 7. Customer counts and scale

### Acceptable forms

- "Used by 12,000 teams in 80 countries". Specific.
- "$2.3B processed". Specific.
- "Trusted by 50+ Series B startups". Specific to ICP.

### Watch out

- "Thousands of users". Vague, low credibility.
- "Industry leader" with no source. Self-claimed.
- "#1 in the category". Where? When? By whom? Always cite (G2 grid, Forrester wave, etc.).

---

## 8. Footer trust completeness

The footer is a trust signal in itself. A complete footer signals a real company.

| Item | Required for trust |
|------|-------------------|
| Contact email or contact page | Yes |
| Postal address (or registered company info) | Yes for B2B EU compliance |
| Privacy policy | Yes |
| Terms of service | Yes |
| Cookie policy | Yes for EU traffic |
| About / team link | Yes for high-trust segments |
| Status page link | Yes for B2B SaaS |
| Blog or changelog link | Recommended |
| Social links to company accounts | Recommended |
| Security or trust page | Recommended |

Missing privacy policy, ToS, or contact info is a critical Trust failure regardless of how strong the testimonials are.

---

## How to score in the report

In the report, render this taxonomy as a "Trust audit" subsection:

| Layer | Present? | Strength tier (S/A/B/C/D/F) | Observation |
|-------|----------|------------------------------|-------------|
| Testimonials | yes / partial / no | <tier> | <one line> |
| Logo bar | yes / partial / no | <tier> | <one line> |
| Third-party verification | yes / partial / no | <tier> | <one line> |
| Press and recognition | yes / partial / no | <tier> | <one line> |
| Compliance / security | yes / partial / no | <tier> | <one line> |
| Founder presence | yes / partial / no | <tier> | <one line> |
| Customer counts | yes / partial / no | <tier> | <one line> |
| Footer completeness | yes / partial / no | <tier> | <one line> |

The Trust dimension /20 score in the LEVER rubric is computed independently from the 16-criterion table; this taxonomy is the qualitative supplement.
