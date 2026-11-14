# LEVER Grid: 340 criteria for landing page audits

**Role.** This file is the **scoring source** of the audit. It holds every criterion, its place in the LEVER tree, the page types it applies to, the evidence needed to judge it, its weight, and its source. `skills/auditing-lever-heuristics/SKILL.md` explains how to walk it. Never inline these rows elsewhere.

**Structure.** The grid follows the three-level tree of the Levers Framework published by Conversion.com [LVR]: 5 **Master levers** (Cost, Trust, Usability, Comprehension, Motivation), 22 **Levers**, 48 **Sub-levers**. Each sub-lever holds the concrete, checkable criteria. Criterion wording comes from the sources listed at the bottom; rows tagged `PRAC` come from shared practitioner practice and have no single primary source.

## How to read a row

| Column | Values |
|--------|--------|
| **ID** | Stable. `C` Cost, `T` Trust, `U` Usability, `K` Comprehension, `M` Motivation. Never renumber; append new rows at the end of their sub-lever with the next free number. |
| **Scope** | Page types the row applies to. `all`, or one or more of `saas`, `ecom` (product or shop page), `local` (local service business), `lead` (lead generation, lead magnet, quote request), `app` (app store or marketplace listing). A row outside the audited `page_type` is N/A and leaves the denominator. |
| **Ev.** | Evidence needed. `S` screenshots, `M` page markdown, `H` HTML source or head, `P` PageSpeed Insights data, `X` interaction or external check (clicking, submitting, visiting a third-party profile). |
| **W** | Weight. `3` critical (a miss alone can sink the conversion), `2` important, `1` hygiene. |
| **Src** | Source key, see [Sources](#sources). |

**Notation per criterion:** OK (2 pts) | Partial (1) | Missing (0) | N/A (excluded) | Unverified (excluded, listed in Limitations). Rows with `S` evidence are judged on desktop and mobile separately; the criterion score is the mean of the two.

---

## COST (57 criteria)

*How the visitor perceives what they must give: money, time, effort, flexibility [LVR].*

### Financial cost > Known cost

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| C001 | Price or starting price is visible on the page or one click away in the main navigation | all | S M | 3 | LVR, BAY-CA |
| C002 | The price sits next to the offer it prices, not only in a footer, FAQ or PDF | all | S | 2 | LVR |
| C003 | Currency matches the target market | all | M | 1 | PRAC |
| C004 | Tax treatment is explicit (tax included for consumers, excluded and labelled for businesses) | all | M | 2 | PRAC |
| C005 | A "from" price says what the entry level includes | all | M | 2 | LVR |
| C006 | The billing unit is explicit (per month, per seat, per usage unit) | saas | M | 3 | LVR |
| C007 | Plans are compared in a table with aligned feature rows | saas | S | 2 | PRAC |
| C008 | One plan is marked as recommended for the main segment | saas | S | 1 | PRAC |
| C009 | The annual or monthly toggle shows the saving in currency or percent | saas | S | 1 | LVR |
| C010 | A "contact us" tier does not replace public prices on a self-serve product | saas | M | 2 | PRAC |
| C011 | Shipping cost or the free-shipping threshold is visible on the product page, before the cart | ecom | S M | 3 | BAY-CA, BAY-SHIP |
| C012 | Delivery cost for the visitor's country can be found without creating an account | ecom | M X | 2 | BAY-CA |
| C013 | The displayed price updates when a variant with a different price is selected | ecom | X | 2 | BAY-PDP |
| C014 | A struck-through reference price is the lowest price of the previous 30 days (EU rule) | ecom | M | 2 | OMNI |
| C015 | A price range or typical job price is given for the service | local | M | 2 | PRAC |
| C016 | Travel or call-out fees are stated | local | M | 1 | PRAC |
| C017 | The free nature of the offer is explicit (free guide, free estimate, free call) | lead | S M | 2 | PRAC |
| C018 | The price on the listing matches the pricing page, free plan or trial stated | app | M X | 2 | PRAC |

### Financial cost > Anticipated cost

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| C019 | No hidden cost: setup fees, add-ons and overage are disclosed near the price | all | M | 3 | LVR, BAY-CA |
| C020 | What happens at the end of the trial is stated (automatic charge or not) | saas | M | 3 | LVR |
| C021 | Cancellation terms are stated near the price | all | M | 2 | LVR |
| C022 | Refund or money-back conditions are stated with their duration | all | M | 2 | LVR |
| C023 | Return window and return cost are stated on the product page | ecom | M | 3 | BAY-PDP, BAY-CA |
| C024 | Contract length or commitment is stated | all | M | 2 | LVR |
| C025 | Renewal and price-change terms are stated | saas | M | 1 | PRAC |
| C026 | Accepted payment methods are shown before checkout | all | S M | 2 | BAY-CA |
| C027 | Instalment or pay-later options are shown where offered | ecom | S M | 1 | PRAC |
| C028 | "No credit card required" is stated near the CTA when true | saas | S M | 2 | PRAC |
| C029 | Limits of the free plan are explicit | saas | M | 2 | LVR |
| C030 | What the offer does not include is stated | all | M | 1 | PRAC |
| C031 | Pre-order, backorder or out-of-stock delays are stated with a date | ecom | M | 1 | BAY-PDP |
| C032 | Duties and customs are addressed for cross-border buyers | ecom | M | 1 | BAY-CA |

### Financial cost > Relative value

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| C033 | The price is anchored against an alternative (cost of the problem, competitor, doing it yourself, hiring) | all | M | 2 | LVR |
| C034 | A per-unit framing (per day, per user, per order) is used where it lowers the perceived cost | all | M | 1 | LVR |
| C035 | Any ROI or savings claim cites its basis | all | M | 2 | LVR |
| C036 | Bundle or volume discounts are visible | ecom | S M | 1 | PRAC |
| C037 | The free-shipping threshold is shown with the remaining amount | ecom | S | 1 | BAY-SHIP |
| C038 | The jump between tiers is justified by visible extra value | saas | M | 1 | LVR |
| C039 | The guarantee is proportionate to the price and risk | all | M | 1 | PRAC |
| C040 | A promo-code field does not dominate the purchase step | ecom | S | 1 | BAY-CO |

### Soft cost > Time cost

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| C041 | Time to first value is stated ("live in 10 minutes") | saas app | M | 2 | LVR |
| C042 | Delivery lead time is stated as a date or date range | ecom | M | 3 | BAY-PDP |
| C043 | Response time to a quote or contact request is stated | local lead | M | 2 | PRAC |
| C044 | Next available appointment or slot is visible | local | S M | 2 | PRAC |
| C045 | Signup or checkout length is announced (steps or minutes) | all | M | 1 | LVR |
| C046 | Demo length is stated | saas | M | 1 | PRAC |
| C047 | Onboarding duration and effort are stated | saas | M | 1 | LVR |

### Soft cost > Effort cost

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| C048 | The form asks only for the fields needed for the next step | all | S M | 3 | BAY-FF, NNG-FORM |
| C049 | Optional fields are removed or clearly marked | all | S | 1 | NNG-FORM |
| C050 | Social login or SSO is offered for signup | saas | S | 1 | PRAC |
| C051 | Guest checkout is available | ecom | X | 3 | BAY-CO |
| C052 | Integrations or import options that reduce setup are listed | saas | M | 2 | LVR |
| C053 | Migration help is offered | saas | M | 1 | PRAC |
| C054 | Phone number is not mandatory unless needed, and the reason is given when it is | all | S | 2 | BAY-CO |
| C055 | Booking is self-serve (calendar embed) | local lead | S X | 2 | PRAC |
| C056 | No account is needed to see the price | all | X | 2 | BAY-CA |
| C057 | Documents or prerequisites the customer must prepare are listed | local | M | 1 | PRAC |

---

## TRUST (70 criteria)

*Is this legitimate, are the claims believable, is my data safe [LVR].*

### Legitimacy > UI quality

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T001 | Visual system is consistent (type families, spacing, colors) | all | S | 2 | NNG-T |
| T002 | No typo or grammar error in visible copy | all | M | 3 | NNG-T |
| T003 | No broken layout, overlapping element or cut-off text | all | S | 3 | NNG-T |
| T004 | No placeholder, lorem ipsum or default template content | all | S M | 3 | NNG-T |
| T005 | Images are sharp, not stretched or pixelated | all | S | 2 | NNG-T |
| T006 | No broken image or dead link on visible CTAs and navigation | all | X | 3 | NNG-T |
| T007 | Design quality matches the price point and audience | all | S | 2 | LVR |
| T008 | No visibly stale content (old year, expired promo, dead event) | all | M | 1 | NNG-T |
| T009 | Stock photos are not presented as team or customers | all | S | 2 | NNG-T |
| T010 | No mixed-content warning or visible script error | all | H | 1 | PRAC |
| T011 | Favicon and a descriptive page title are set | all | H | 1 | PRAC |
| T012 | Branding matches the ad, email or listing that sent the visitor | all | S X | 2 | UNB |

### Legitimacy > Brand recognition

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T013 | Logo is visible in the header | all | S | 2 | NNG-H |
| T014 | Legal company name and address are published (legal notice) | all | M | 2 | NNG-T |
| T015 | An About page is reachable | all | M | 1 | NNG-T |
| T016 | Founders or team appear with real names and photos | all | S M | 2 | NNG-T |
| T017 | The domain matches the brand, no unexpected redirect | all | X | 2 | PRAC |
| T018 | Linked social profiles exist and are active | all | X | 1 | PRAC |
| T019 | Physical address or map is shown | local | S M | 3 | PRAC |
| T020 | Google Business Profile rating is shown or linked | local | S M | 2 | PRAC |
| T021 | Registration details (company number, years in business) are stated when true | local | M | 1 | PRAC |
| T022 | Contact email uses the company domain | all | M | 1 | PRAC |

### Credibility > Authority

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T023 | Press mentions link to the actual articles | all | M | 1 | NNG-T |
| T024 | Certifications or labels link to a verifiable record | all | M X | 2 | LVR |
| T025 | Credentials of the expert or author are stated | all | M | 1 | LVR |
| T026 | Partner or integration logos are used with a real integration behind them | saas app | M | 1 | PRAC |
| T027 | Awards are verifiable | all | M X | 1 | LVR |
| T028 | Data and statistics cite their source | all | M | 2 | NNG-T |
| T029 | Expertise content (guides, blog) is linked | all | M | 1 | LVR |
| T030 | Mandatory professional insurance is stated (for example ten-year building warranty in France) | local | M | 2 | PRAC |

### Credibility > Social proof

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T031 | Social proof is visible within the first two screens | all | S | 3 | LVR, NNG-SP |
| T032 | Customer logos are recognizable to the target segment | saas lead | S | 2 | NNG-SP |
| T033 | Testimonials carry full name, photo, and role and company or city | all | S M | 3 | NNG-SP |
| T034 | Testimonials describe a specific outcome | all | M | 2 | NNG-SP |
| T035 | Testimonials come from the target segment | all | M | 2 | NNG-SP |
| T036 | A third-party rating widget links to the live profile (Trustpilot, Google, G2, stores) | all | S X | 2 | NNG-SP |
| T037 | Review count is shown with the average rating | all | S | 2 | BAY-PDP |
| T038 | Rating distribution is shown, mixed reviews included | ecom | S | 1 | BAY-PDP |
| T039 | Reviews can be sorted or filtered | ecom | X | 1 | BAY-PDP |
| T040 | Customer photos or user content appear | ecom | S | 1 | BAY-PDP |
| T041 | A case study with measured results is linked | saas lead | M | 2 | PRAC |
| T042 | Scale figures (customers, orders) are precise and dated | all | M | 1 | PRAC |
| T043 | Social proof sits next to decision points and CTAs | all | S | 2 | NNG-SP |
| T044 | At least one video testimonial | all | S | 1 | PRAC |
| T045 | Before and after photos of real jobs | local | S | 2 | PRAC |
| T046 | Store rating and install or review count are visible | app | S | 3 | PRAC |
| T047 | No proof looks fabricated (round numbers without source, anonymous quotes) | all | M | 2 | NNG-T |
| T048 | Reviews are recent (dated within the last 12 months) | all | M | 1 | PRAC |

### Credibility > Customer service and support

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T049 | A contact method is visible (phone, email or chat) | all | S M | 2 | NNG-T |
| T050 | Phone number is tap-to-call on mobile | local | H | 3 | PRAC |
| T051 | Opening hours are shown | local | M | 2 | PRAC |
| T052 | Chat widget does not cover content or CTA on mobile | all | S | 2 | NNG-POP |
| T053 | Support response time is stated | all | M | 1 | PRAC |
| T054 | Help center or documentation is linked | saas app | M | 1 | PRAC |
| T055 | Status page is linked | saas | M | 1 | PRAC |
| T056 | Support has a human name or face | all | S | 1 | PRAC |
| T057 | Warranty and after-sales terms are stated | ecom | M | 2 | BAY-PDP |
| T058 | Service area is stated | local | M | 3 | PRAC |

### Security > Payment security

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T059 | HTTPS with a valid certificate on every page of the path | all | X | 3 | LVR |
| T060 | Payment method logos appear near price or CTA | ecom | S | 2 | BAY-CO |
| T061 | Secure payment is mentioned at the purchase step | ecom | S | 1 | BAY-CO |
| T062 | The payment provider is a recognized one | all | X | 1 | LVR |
| T063 | No generic "100% secure" seal without an issuer | all | S | 1 | NNG-T |

### Security > Personal information requests

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| T064 | Privacy policy is linked next to the form | all | S M | 2 | LVR |
| T065 | Each sensitive field says why it is requested | all | S | 2 | BAY-CO |
| T066 | An anti-spam promise sits next to the email field | all | S | 1 | PRAC |
| T067 | Cookie banner offers refusal as easily as acceptance and does not block reading | all | S | 2 | CNIL |
| T068 | Marketing consent boxes are not pre-checked | all | S H | 2 | CNIL |
| T069 | Compliance and data location are stated for business buyers (GDPR, SOC 2, EU hosting) | saas | M | 1 | PRAC |
| T070 | Legal pages are linked (terms of sale, terms of use, legal notice) | all | M | 2 | PRAC |

---

## USABILITY (92 criteria)

*How easily the visitor moves from arrival to conversion without the thought of leaving [LVR].*

### User flow > Location

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U001 | The first screen confirms the visitor landed where the link promised (brand, topic, offer) | all | S X | 3 | UNB, NNG-H |
| U002 | Browser title describes the page | all | H | 1 | NNG-H |
| U003 | Breadcrumbs or active navigation state on deep pages | ecom | S | 1 | NNG-H |
| U004 | Anchor links land on their section, not hidden under a sticky header | all | X | 1 | PRAC |
| U005 | Logo links to the home page | all | H | 1 | NNG-H |
| U006 | Language or country switch is visible on multilingual sites | all | S | 1 | PRAC |

### User flow > Direction

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U007 | One primary CTA serves the page goal | all | S | 3 | UNB |
| U008 | Primary CTA is visible in the first desktop screen (1280 wide) | all | S | 3 | NNG-FOLD |
| U009 | Primary CTA is visible in the first mobile screen (390 wide) | all | S | 3 | NNG-FOLD |
| U010 | CTA is repeated at each decision point (after value, after proof, after pricing, at the end) | all | S | 2 | PRAC |
| U011 | Long pages keep a sticky CTA on mobile | all | S | 1 | PRAC |
| U012 | CTA label states the action and its benefit | all | M | 2 | NNG-UXW |
| U013 | CTA looks clickable (button shape, contrast, size) | all | S | 3 | NNG-H |
| U014 | Secondary CTAs are visually subordinate | all | S | 2 | NNG-VH |
| U015 | The step after the click is described ("pick a time", "get the PDF by email") | all | M | 2 | NNG-H |
| U016 | Text links are distinguishable from body text | all | S | 1 | NNG-H |
| U017 | Visual cues lead the eye to the CTA | all | S | 1 | PRAC |
| U018 | Navigation is reduced on paid-traffic landing pages | all | S | 2 | UNB |
| U019 | Footer and navigation exits do not compete with the CTA | all | S | 1 | PRAC |
| U020 | Add to cart is visible without scrolling on a mobile product page | ecom | S | 3 | BAY-PDP |
| U021 | Tap-to-call is the primary mobile CTA when the phone converts best | local | S | 2 | PRAC |
| U022 | Store badges link straight to the listing | app | X | 2 | PRAC |

### Effort > Experienced effort

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U023 | Largest Contentful Paint at or under 2.5 s on mobile | all | P | 3 | CWV-LCP |
| U024 | Interaction to Next Paint at or under 200 ms | all | P | 2 | CWV-INP |
| U025 | Cumulative Layout Shift at or under 0.1 | all | P | 2 | CWV-CLS |
| U026 | Hero image is compressed, sized to its slot and in a modern format | all | H P | 1 | CWV-LCP |
| U027 | Web fonts do not leave text invisible while loading | all | P | 1 | CWV |
| U028 | No heavy autoplay video on mobile | all | H S | 1 | CWV |
| U029 | Every field has a visible label, not a placeholder alone | all | S | 3 | NNG-PH |
| U030 | Fields are validated inline once completed | all | X | 2 | BAY-VAL |
| U031 | Error messages are specific and sit next to the field | all | X | 2 | NNG-ERR |
| U032 | Mobile keyboard matches the field type (email, tel, numeric) | all | H | 2 | BAY-KB |
| U033 | Fields carry autocomplete attributes | all | H | 1 | WCAG |
| U034 | Entered data survives an error | all | X | 2 | NNG-ERR |
| U035 | Form is laid out in a single column | all | S | 1 | NNG-FORM |
| U036 | Tap targets are at least 24 by 24 CSS px with spacing (44 pt recommended) | all | S H | 2 | WCAG-TS, HIG |
| U037 | Body text is at least 16 px on mobile | all | S H | 2 | PRAC |
| U038 | Text contrast is at least 4.5:1 (3:1 for large text) | all | S H | 2 | WCAG-CT |
| U039 | No horizontal scroll at 390 px wide | all | S | 3 | WCAG-RF |
| U040 | Viewport meta is set and zoom is not disabled | all | H | 2 | WCAG-RF |
| U041 | Keyboard focus is visible | all | X | 1 | WCAG-FV |
| U042 | Meaningful images carry alt text | all | H | 1 | WCAG-NT |
| U043 | Buttons and links have an accessible name | all | H | 1 | WCAG |
| U044 | No popup in the first seconds, easy to close, no full-screen mobile interstitial | all | S | 2 | NNG-POP, GOOG-INT |
| U045 | Cookie banner does not cover the mobile CTA | all | S | 2 | GOOG-INT |
| U046 | Desktop line length stays near 50 to 75 characters | all | S | 1 | PRAC |
| U047 | Paragraphs are short (four lines or fewer) | all | S M | 1 | NNG-READ |
| U048 | Video has controls and captions and does not autoplay with sound | all | S H | 1 | NNG-VID |

### Effort > Anticipated effort

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U049 | Number of steps is announced before starting | all | M | 1 | LVR |
| U050 | The form looks short at first glance (light first step if multi-step) | all | S | 2 | LVR |
| U051 | Effort needed after signup is described | saas | M | 1 | LVR |
| U052 | Checkout steps are visible | ecom | X | 1 | BAY-CO |
| U053 | A calendar shows open slots instead of "we will contact you" | local lead | S X | 1 | PRAC |

### Choice > Findability

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U054 | Price, delivery and contact are found within two scrolls or one navigation click | all | S | 2 | NNG-H |
| U055 | Search is available on catalog pages | ecom | S | 1 | NNG-H |
| U056 | FAQ is easy to reach | all | S M | 1 | PRAC |
| U057 | Plan or product selector leads quickly to the right option | saas ecom | S | 2 | LVR |
| U058 | Variant selectors show available and unavailable states | ecom | S | 2 | BAY-PDP |
| U059 | A size or fit guide is linked next to the size selector | ecom | S | 2 | BAY-PDP |
| U060 | Each service has its own link or section | local | M | 2 | PRAC |
| U061 | Mobile menu is labelled and reachable | all | S | 1 | NNG-H |

### Choice > Structure

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U062 | Visual hierarchy is clear (H1 dominant, then subheads) | all | S | 2 | NNG-VH |
| U063 | Sections follow a logical order (problem, solution, proof, offer, CTA) | all | M | 2 | PRAC |
| U064 | Each section has a scannable subhead | all | S M | 2 | NNG-READ |
| U065 | Feature lists use bullets | all | S | 1 | NNG-READ |
| U066 | Similar sections share the same design pattern | all | S | 1 | NNG-H |
| U067 | White space groups related items | all | S | 1 | NNG-VH |
| U068 | Pricing columns are aligned for comparison | saas | S | 1 | PRAC |
| U069 | Product gallery has several images and zoom | ecom | S X | 2 | BAY-PDP |
| U070 | Mobile layout keeps key content, only reordered | all | S | 2 | NNG-H |
| U071 | Accordions do not hide critical facts (price, delivery, returns) | all | S | 2 | NNG-PD |
| U072 | Footer is organized by topic | all | S | 1 | PRAC |

### Attention > Distraction

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U073 | Key messages do not sit in an auto-rotating carousel | all | S H | 2 | NNG-AUTO |
| U074 | No competing animation near the CTA | all | S | 1 | PRAC |
| U075 | Outbound links are few | all | M | 1 | UNB |
| U076 | Promo banners do not push the hero below the first screen | all | S | 2 | NNG-FOLD |
| U077 | Chat or notification popups do not interrupt reading | all | S | 1 | NNG-POP |
| U078 | Important content does not look like an ad | all | S | 2 | NNG-BB |
| U079 | At most one or two distinct offers in the first screen | all | S | 2 | PRAC |
| U080 | Embedded social feeds do not pull attention from the offer | all | S | 1 | PRAC |
| U081 | Cross-sell does not appear before the primary action | ecom | S | 1 | PRAC |

### Attention > Engagement

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U082 | The hero gives a reason to keep scrolling | all | S | 1 | LVR |
| U083 | No false bottom (a block ending exactly at the fold that looks like the end) | all | S | 2 | NNG-FOLD |
| U084 | An interactive element (calculator, configurator, demo) exists where relevant | all | S | 1 | LVR |
| U085 | Page length matches the price and complexity of the offer | all | S | 2 | PRAC |

### Persistence > Progress presentation

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U086 | Multi-step forms show a progress indicator | all | S X | 2 | NNG-PROG |
| U087 | Checkout shows progress | ecom | X | 1 | BAY-CO |
| U088 | Onboarding steps are previewed | saas | M | 1 | LVR |

### Persistence > Positive feedback

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| U089 | Buttons show a loading or done state after the click | all | X | 2 | NNG-H |
| U090 | Confirmation says what happens next and when | all | X | 2 | NNG-H |
| U091 | Add to cart gives visible confirmation | ecom | X | 2 | BAY-PDP |
| U092 | Promised follow-up (email, call) states its timing | all | M | 1 | LVR |

---

## COMPREHENSION (56 criteria)

*Does the visitor understand the category, the product and the transaction well enough to buy [LVR].*

### Education > Educational content

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| K001 | The problem or category is explained for a visitor new to it | all | M | 2 | LVR |
| K002 | A "how it works" section has three to five steps | all | S M | 2 | LVR |
| K003 | Jargon is defined inline | all | M | 1 | NNG-PLAIN |
| K004 | Comparison with alternatives (do it yourself, competitors, status quo) | all | M | 2 | LVR |
| K005 | Use cases are shown per segment | all | M | 2 | LVR |
| K006 | FAQ answers the top objections (price, integration, security, support, commitment) | all | M | 2 | LVR |
| K007 | Resources for not-yet-ready visitors are linked (guide, webinar, blog) | all | M | 1 | LVR |
| K008 | The page says who the offer is not for | all | M | 1 | PRAC |
| K009 | The service process is explained (visit, quote, job, follow-up) | local | M | 2 | PRAC |
| K010 | Lead magnet content is previewed (table of contents, page count) | lead | S M | 2 | PRAC |

### Product understanding > Product information

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| K011 | H1 says what the product is or does in plain language | all | M | 3 | LVR, NNG-PLAIN |
| K012 | Five-second test: a newcomer can say what it is, for whom, and the next step | all | S | 3 | LVR |
| K013 | Target user is named in the first screen | all | S M | 2 | LVR |
| K014 | Subheadline adds how or for whom | all | M | 2 | PRAC |
| K015 | No unexplained jargon or acronym in the hero | all | M | 2 | NNG-PLAIN |
| K016 | The page carries one core message | all | M | 2 | PRAC |
| K017 | Key features are listed, each with its benefit | all | M | 2 | LVR |
| K018 | Specifications or technical details are available | ecom saas | M | 2 | BAY-PDP |
| K019 | Integrations and compatibility are listed | saas app | M | 2 | LVR |
| K020 | Materials, dimensions and weight are given | ecom | M | 3 | BAY-PDP |
| K021 | Size or fit information is precise | ecom | M | 2 | BAY-PDP |
| K022 | Stock or availability status is shown | ecom | S M | 2 | BAY-PDP |
| K023 | The list of services and their scope is explicit | local | M | 3 | PRAC |
| K024 | What a quote includes is explicit | local | M | 1 | PRAC |
| K025 | Subheads make sense read alone (scan test) | all | M | 2 | NNG-READ |
| K026 | Copy uses the customers' vocabulary | all | M | 2 | LVR |
| K027 | Numbers are specific with explicit units | all | M | 1 | NNG-READ |
| K028 | Claims are specific, no vague superlatives | all | M | 2 | NNG-READ |
| K029 | Short sentences, plain language | all | M | 1 | NNG-PLAIN |
| K030 | The copy is fully in the market's language (no untranslated fragments) | all | M | 2 | PRAC |
| K031 | Care, maintenance or usage instructions are available | ecom | M | 1 | BAY-PDP |
| K032 | Requirements are stated (OS, devices, permissions) | app | M | 2 | PRAC |
| K033 | The differentiator is stated explicitly | all | M | 2 | LVR |

### Product understanding > Product depiction

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| K034 | The real product appears in the first screen (photo or screenshot, not an abstract illustration) | all | S | 3 | LVR |
| K035 | The product is shown in use or in context | all | S | 2 | LVR, BAY-PDP |
| K036 | Several angles or views are shown | ecom | S | 2 | BAY-PDP |
| K037 | One image gives a sense of scale | ecom | S | 1 | BAY-PDP |
| K038 | A short demo video or GIF exists | all | S | 1 | LVR |
| K039 | Interface screenshots are readable, not tiny | saas app | S | 2 | LVR |
| K040 | Screenshots match the current product | saas app | S X | 1 | PRAC |
| K041 | Images follow the selected variant | ecom | X | 1 | BAY-PDP |
| K042 | Photos of the team and real jobs, not stock | local | S | 2 | NNG-T |
| K043 | Images that need context carry a caption | all | S | 1 | PRAC |
| K044 | An interactive demo or sandbox is available | saas | M X | 1 | LVR |

### Transactional understanding > Savings understanding

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| K045 | A discount shows both the amount and the percentage | all | S | 1 | LVR |
| K046 | Annual savings are computed for the visitor | saas | S | 1 | LVR |
| K047 | Promotion conditions and end date are explicit | all | M | 2 | LVR, OMNI |
| K048 | The difference between free trial and free plan is clear | saas | M | 1 | LVR |
| K049 | Bundle or discount rules are clear | ecom | M | 1 | LVR |

### Transactional understanding > Payment structure

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| K050 | Billing frequency is clear | all | M | 2 | LVR |
| K051 | What each price includes is explicit | all | M | 3 | LVR |
| K052 | A worked example shows per-seat or usage billing | saas | M | 2 | LVR |
| K053 | Deposit and payment schedule are stated | local | M | 1 | PRAC |
| K054 | A typical total or sample quote is given | local | M | 2 | PRAC |
| K055 | When the charge happens is stated (now, at shipping, after trial) | all | M | 1 | LVR |
| K056 | Terms of sale are linked next to the purchase action | all | S M | 1 | PRAC |

---

## MOTIVATION (65 criteria)

*What is in it for the visitor, and why act now [LVR].*

### Value statement > Value proposition

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M001 | The headline states the main benefit or outcome | all | M | 3 | LVR |
| M002 | The value proposition targets the ICP's top pain (market-signal data when available) | all | M | 3 | LVR |
| M003 | The value proposition is distinct from alternatives | all | M | 2 | LVR |
| M004 | The value proposition is specific (numbers, time, scope) | all | M | 2 | LVR |
| M005 | The value proposition is believable, no hype | all | M | 2 | NNG-T |
| M006 | The value proposition reuses customer wording | all | M | 1 | LVR |
| M007 | The pain is named explicitly | all | M | 2 | LVR |
| M008 | The cost of doing nothing is stated | all | M | 1 | PRAC |
| M009 | The page keeps the promise of the ad, email or search result that sent the visitor | all | M X | 3 | UNB |
| M010 | The final CTA section restates the value | all | M | 1 | PRAC |

### Value statement > Benefits

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M011 | Features are translated into benefits | all | M | 2 | LVR |
| M012 | Benefits are ordered by importance to the ICP | all | M | 1 | LVR |
| M013 | Benefits cover functional and emotional gains | all | M | 1 | LVR |
| M014 | The outcome is shown (before and after, results screen) | all | S | 2 | LVR |
| M015 | Benefits are adapted per segment or use case | all | M | 1 | LVR |
| M016 | Benefit lists stay scannable (seven items or fewer per block) | all | S | 1 | NNG-READ |
| M017 | Risk reversal (guarantee, free cancellation) sits next to the CTA | all | S | 2 | LVR |
| M018 | Main objections are answered with a benefit | all | M | 1 | LVR |

### Motivational depiction > Motivational imagery

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M019 | The hero visual supports the value proposition, not decoration | all | S | 2 | LVR |
| M020 | People shown resemble the ICP | all | S | 1 | LVR |
| M021 | The desired outcome is pictured | all | S | 1 | LVR |
| M022 | Imagery looks authentic | all | S | 1 | NNG-T |
| M023 | Product photography is professional (light, background, consistency) | ecom | S | 2 | BAY-PDP |

### Motivational depiction > Motivational video

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M024 | Video states the value in its opening seconds | all | X | 1 | NNG-VID |
| M025 | Video thumbnail is compelling with a clear play control | all | S | 1 | NNG-VID |
| M026 | A founder or customer speaks on video | all | S | 1 | LVR |

### Preview access > Full trials

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M027 | A free trial, demo or sample is offered where the model allows | all | M | 2 | LVR |
| M028 | Trial is full-featured, or its limits are clear | saas | M | 1 | LVR |
| M029 | A free consultation or estimate is offered | local | M | 2 | LVR |
| M030 | Try before you buy is offered (home try-on, free returns) | ecom | M | 1 | LVR |

### Preview access > Limited free content

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M031 | A free plan exists or is clearly absent | saas | M | 1 | LVR |
| M032 | A free tool, calculator or resource is offered | all | M | 1 | LVR |
| M033 | A sample of the gated content is visible | lead | S | 2 | LVR |

### Obligation > Reciprocity

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M034 | Value is given before the ask (tips, free resource) | all | M | 1 | LVR |
| M035 | Something personalized is offered (audit, estimate, plan) | all | M | 1 | LVR |

### Obligation > Altruism

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M036 | Mission or impact is stated when genuine and specific | all | M | 1 | LVR |
| M037 | Ethical or environmental claims link to a verifiable label | ecom | M X | 1 | LVR |

### Sociability > Community

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M038 | Community size and access are shown | all | M | 1 | LVR |
| M039 | Belonging is framed honestly ("join the founders who...") with a real figure | all | M | 1 | LVR |
| M040 | Events or user groups are shown | saas | M | 1 | LVR |

### Sociability > Exclusivity

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M041 | Exclusive or invite-only access is real and explained | all | M | 1 | LVR |
| M042 | Limited editions are real and quantified | ecom | M | 1 | LVR |

### Urgency > Availability

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M043 | Low stock is shown when true | ecom | S | 1 | LVR |
| M044 | Limited slots or capacity are shown when true | local lead | S | 1 | LVR |
| M045 | No fake urgency (resetting countdowns, permanent "only 2 left") | all | X | 3 | NNG-DP |

### Urgency > Price change

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M046 | A promotion shows a real end date | all | M | 1 | LVR, OMNI |
| M047 | Early-bird or launch pricing terms are clear | all | M | 1 | LVR |
| M048 | Price lock for early customers is stated when offered | saas | M | 1 | LVR |

### Product range > New product

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M049 | Changelog or recent releases show momentum | saas | M | 1 | LVR |
| M050 | New arrivals are highlighted | ecom | S | 1 | LVR |

### Product range > Variety

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M051 | The range of options is visible without overload | all | S | 1 | LVR |
| M052 | A guide helps choose ("best for", quiz, recommender) | all | S | 2 | LVR |
| M053 | Related products appear after the main decision | ecom | S | 1 | LVR |

### Delivery > Delivery speed

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M054 | Fast delivery is promised with a date | ecom | S M | 2 | LVR, BAY-PDP |
| M055 | An express option exists | ecom | M | 1 | LVR |
| M056 | Access is immediate after signup | saas | M | 2 | LVR |
| M057 | Emergency or fast intervention is stated when offered | local | M | 2 | LVR |

### Delivery > Delivery ease

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M058 | Pickup points or click and collect are offered | ecom | M | 1 | LVR |
| M059 | Order tracking is promised | ecom | M | 1 | LVR |
| M060 | Done-for-you onboarding is offered | saas | M | 1 | LVR |
| M061 | On-site or remote service mode is stated | local | M | 1 | LVR |

### Gamification > Immersion

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M062 | An interactive quiz, configurator or simulator engages the visitor | all | S X | 1 | LVR |

### Gamification > Progression

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M063 | Loyalty or reward progression is shown | ecom | M | 1 | LVR |
| M064 | An onboarding checklist is previewed | saas | S | 1 | LVR |

### Gamification > Competition

| ID | Criterion | Scope | Ev. | W | Src |
|----|-----------|-------|-----|---|-----|
| M065 | Leaderboards or challenges are shown where they fit the product | app | S | 1 | LVR |

---

## Scoring

**Per criterion.** OK 2, Partial 1, Missing 0. N/A and Unverified leave the denominator. `S` rows: mean of desktop and mobile.

**Per master lever (out of 20).**

```
score = 20 × Σ(weight × points) / Σ(weight × 2)     over applicable, verified rows
```

**Total (out of 100).** Sum of the 5 master lever scores.

**Coverage line (mandatory in the report).** For each master lever: applicable rows, verified rows, unverified rows. A lever score built on fewer than 60 % verified rows is flagged "low confidence".

| Master lever | Rows | Critical (W3) |
|--------------|-----:|--------------:|
| Cost | 57 | 9 |
| Trust | 70 | 11 |
| Usability | 92 | 9 |
| Comprehension | 56 | 6 |
| Motivation | 65 | 4 |
| **Total** | **340** | **39** |

Applicable rows depend on `page_type`: the 214 rows scoped `all` plus the rows of the audited type.

| `page_type` | Applicable rows |
|-------------|----------------:|
| `saas` | 256 |
| `ecom` | 265 |
| `local` | 241 |
| `lead` | 223 |
| `app` | 225 |

Report the applicable count, never "340 criteria checked" when fewer applied.

**Any W3 row scored Missing** goes to the top of the findings, whatever its lever score.

---

## Sources

| Key | Source |
|-----|--------|
| LVR | Conversion.com, *Why do users convert? Introducing our Lever Framework* (E. Beggs, 2022): https://conversion.com/blog/lever-framework/ (master levers, levers, sub-levers) |
| NNG-H | Nielsen Norman Group, 10 Usability Heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/ |
| NNG-T | NN/g, Trustworthiness in Web Design: https://www.nngroup.com/articles/trustworthy-design/ |
| NNG-SP | NN/g, Social Proof in the User Experience: https://www.nngroup.com/articles/social-proof-ux/ |
| NNG-READ | NN/g, How Users Read on the Web: https://www.nngroup.com/articles/how-users-read-on-the-web/ |
| NNG-FOLD | NN/g, The Fold Manifesto: https://www.nngroup.com/articles/page-fold-manifesto/ |
| NNG-BB | NN/g, Banner Blindness: https://www.nngroup.com/articles/banner-blindness-old-and-new-findings/ |
| NNG-VH | NN/g, Visual Hierarchy: https://www.nngroup.com/articles/visual-hierarchy-ux-definition/ |
| NNG-FORM | NN/g, Website Forms Usability: https://www.nngroup.com/articles/web-form-design/ |
| NNG-PH | NN/g, Placeholders in Form Fields: https://www.nngroup.com/articles/form-design-placeholders/ |
| NNG-ERR | NN/g, Error-Message Guidelines for Forms: https://www.nngroup.com/articles/errors-forms-design-guidelines/ |
| NNG-PROG | NN/g, Progress Indicators: https://www.nngroup.com/articles/progress-indicators/ |
| NNG-PD | NN/g, Progressive Disclosure: https://www.nngroup.com/articles/progressive-disclosure/ |
| NNG-AUTO | NN/g, Auto-Forwarding Carousels: https://www.nngroup.com/articles/auto-forwarding/ |
| NNG-POP | NN/g, Popups: https://www.nngroup.com/articles/popups/ |
| NNG-VID | NN/g, Video Usability: https://www.nngroup.com/articles/video-usability/ |
| NNG-UXW | NN/g, UX Writing Study Guide: https://www.nngroup.com/articles/ux-writing-study-guide/ |
| NNG-PLAIN | NN/g, Plain Language Is for Everyone: https://www.nngroup.com/articles/plain-language-experts/ |
| NNG-DP | NN/g, Deceptive Patterns in UX: https://www.nngroup.com/articles/deceptive-patterns/ |
| BAY-PDP | Baymard Institute, Product Page UX research: https://baymard.com/research/product-page |
| BAY-CO | Baymard, Checkout Usability research: https://baymard.com/research/checkout-usability |
| BAY-FF | Baymard, Checkout form fields: https://baymard.com/blog/checkout-flow-average-form-fields |
| BAY-CA | Baymard, Cart abandonment reasons: https://baymard.com/blog/cart-abandonment |
| BAY-SHIP | Baymard, Free shipping thresholds: https://baymard.com/blog/free-shipping-thresholds |
| BAY-VAL | Baymard, Inline form validation: https://baymard.com/blog/inline-form-validation |
| BAY-KB | Baymard, Mobile touch keyboards: https://baymard.com/blog/mobile-touch-keyboards |
| WCAG | W3C, WCAG 2.2: https://www.w3.org/TR/WCAG22/ |
| WCAG-TS | WCAG 2.2, 2.5.8 Target Size (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html |
| WCAG-CT | WCAG 2.2, 1.4.3 Contrast (Minimum): https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html |
| WCAG-RF | WCAG 2.2, 1.4.10 Reflow: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html |
| WCAG-FV | WCAG 2.2, 2.4.7 Focus Visible: https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html |
| WCAG-NT | WCAG 2.2, 1.1.1 Non-text Content: https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html |
| HIG | Apple Human Interface Guidelines, Accessibility: https://developer.apple.com/design/human-interface-guidelines/accessibility |
| CWV | web.dev, Web Vitals: https://web.dev/articles/vitals |
| CWV-LCP | web.dev, LCP: https://web.dev/articles/lcp |
| CWV-INP | web.dev, INP: https://web.dev/articles/inp |
| CWV-CLS | web.dev, CLS: https://web.dev/articles/cls |
| GOOG-INT | Google Search Central, Avoid intrusive interstitials: https://developers.google.com/search/docs/appearance/avoid-intrusive-interstitials |
| UNB | Unbounce, Conversion Benchmark Report: https://unbounce.com/conversion-benchmark-report/ |
| OMNI | EU Directive 2019/2161 (Omnibus), price reduction announcements: https://eur-lex.europa.eu/eli/dir/2019/2161/oj |
| CNIL | CNIL, cookies and trackers rules: https://www.cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies |
| PRAC | Shared CRO practitioner practice, no single primary source. Treat as a strong default, never as a proven effect. |
