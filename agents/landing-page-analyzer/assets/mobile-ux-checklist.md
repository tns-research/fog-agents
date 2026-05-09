# Mobile UX checklist (2026 standards)

**Role.** Targeted checks for the mobile viewport (390 x 844 by default), feeding the "Mobile and visual findings" section of the report. Mobile is where most paid traffic lands and where the average SaaS landing page leaks the most. The ceiling on mobile is roughly 1.5 to 2.5% conversion for cold paid traffic, so every friction point matters.

These checks complement the LEVER 80-criterion rubric. They are scored OK / Partial / Missing with a one-line observation each.

---

## Touch and tap

### TM1: Touch targets ≥ 44 x 44 px with ≥ 8 px spacing
Apple HIG and Material Design baseline. Buttons, links, form controls, icon buttons, accordion headers, FAQ rows. Two adjacent CTAs without spacing fail this even if each is 44 px wide.

### TM2: No accidental double-tap zone
Stacked links that look like a single block (e.g. logo + tagline both clickable) are an anti-pattern. Use one tap target per intent.

### TM3: Forms use native input types
`type="email"` triggers the email keyboard. `type="tel"` triggers the numeric pad. `inputmode="numeric"` for verification codes. `autocomplete="email"` and `autocomplete="given-name"` reduce typing.

### TM4: No `hover`-only interactions
On mobile, hover does not exist. Tooltips, "hover to reveal", or hover-only navigation do not work. Use tap-to-reveal (`<details>`, accordion) or show by default.

---

## Performance and Page Experience 2.0

Page Experience 2.0 (Google, since March 2024) replaced FID with INP and continues weighting LCP and CLS. INP measures real interaction latency, not just first input.

### PM1: LCP under 2.5 s on a moderate mobile connection
Largest Contentful Paint is usually the hero image, hero video poster, or H1. To stay under 2.5 s on 4G:
- Preload the hero image with `<link rel="preload" as="image">`.
- Do NOT lazy-load the LCP element. `loading="lazy"` on the hero image is a common 1-second regression.
- Inline critical CSS for the hero.
- Avoid client-side font swaps that delay text rendering.

### PM2: INP under 200 ms (75th percentile)
Interaction to Next Paint replaced First Input Delay. Long tasks on the main thread are the biggest cause: heavy analytics scripts, third-party chat widgets initializing on load, large hydration bundles. Defer non-critical scripts. Break up tasks with `requestIdleCallback`.

### PM3: CLS under 0.1
Cumulative Layout Shift. Reserve dimensions for images and embeds (`width` and `height` attributes, `aspect-ratio` CSS). Avoid injecting banners, sticky headers, or cookie banners that push content. Pre-allocate space for fonts (use `font-display: optional` or `swap` with metric overrides).

### PM4: Lazy-load below the fold, not above
Use `loading="lazy"` on images that are not in the first viewport. The LCP element must be eager. Same for `<iframe>` embeds.

### PM5: No render-blocking third-party scripts on first paint
Tag managers, analytics, chat widgets, video players. Defer or inject after `load`. Use `<script async>` or `<script defer>` rather than blocking `<script>` in `<head>`.

---

## Layout and viewport

### LM1: No horizontal scroll on a 390-wide viewport
Common offenders: `overflow-x: visible` on a parent, fixed-width pricing tables, large screenshots not constrained to `max-width: 100%`.

### LM2: Sticky elements do not block content
Sticky header, sticky CTA bar, cookie banner, chat widget. Combined they can occupy 30% of the viewport on mobile. Keep at most one sticky element on screen.

### LM3: Modal and popup discipline
No exit-intent popup that fires on first scroll. No newsletter modal blocking the hero. Cookie banner uses standard close patterns and keeps the dismiss button reachable.

### LM4: Above-the-fold answers "what is this and what do I do next"
On a 390 x 844 viewport, before any scroll, the visitor sees: H1, supporting line, primary CTA, and one trust cue (logo bar, rating, or testimonial). If the trust cue is missing, score Partial.

### LM5: First scroll reveals the value prop
Within one swipe (roughly 600 px on mobile), the visitor sees the value proposition expanded with one concrete outcome and visual proof.

---

## Forms

### FM1: Field count minimal
Signup form ≤ 4 fields (email, password optional, name optional, company optional). Demo booking form ≤ 4 fields. Every extra field above 4 reduces completion roughly 8 to 12% on mobile.

### FM2: Single-column layout
Multi-column forms break on narrow viewports. Stack vertically.

### FM3: Inline validation, human-readable
Errors appear under the field, not in a generic banner. Messages say what to fix ("Email needs an @"), not "Invalid input".

### FM4: Submit button is full-width on mobile
Easier to tap. Visible without scrolling once the form is filled.

### FM5: Autofocus only when the form is the page
A landing page should not steal focus and pop the keyboard on load. Autofocus belongs on dedicated signup pages, not on hero forms.

---

## Mobile conversion notes

- Average SaaS mobile conversion (cold paid traffic): 1.5 to 2.5%. Above 4% is excellent. Below 1% suggests a critical friction point, often LCP > 4 s, hidden CTA, or form too long.
- Mobile typically converts 20 to 40% lower than desktop on the same page. If the gap is larger, the mobile experience has a specific defect, not just a viewport issue.
- The two highest-leverage mobile fixes are (1) shorten the form, (2) make the primary CTA visible without scrolling.

---

## Scoring template

| ID | Criterion | Score | Observation |
|----|-----------|-------|-------------|
| TM1 | Touch targets ≥ 44 px with spacing | OK / Partial / Missing | |
| TM2 | No accidental double-tap zones | OK / Partial / Missing | |
| TM3 | Native input types and autocomplete | OK / Partial / Missing | |
| TM4 | No hover-only interactions | OK / Partial / Missing | |
| PM1 | LCP under 2.5 s | OK / Partial / Missing | |
| PM2 | INP under 200 ms | OK / Partial / Missing | |
| PM3 | CLS under 0.1 | OK / Partial / Missing | |
| PM4 | Lazy-load only below the fold | OK / Partial / Missing | |
| PM5 | No render-blocking third-party scripts | OK / Partial / Missing | |
| LM1 | No horizontal scroll on 390 px | OK / Partial / Missing | |
| LM2 | Sticky elements do not block content | OK / Partial / Missing | |
| LM3 | Modal and popup discipline | OK / Partial / Missing | |
| LM4 | Above-fold answers "what + next" | OK / Partial / Missing | |
| LM5 | First scroll reveals value prop | OK / Partial / Missing | |
| FM1 | Field count ≤ 4 | OK / Partial / Missing | |
| FM2 | Single-column form layout | OK / Partial / Missing | |
| FM3 | Inline, human-readable validation | OK / Partial / Missing | |
| FM4 | Submit button full-width on mobile | OK / Partial / Missing | |
| FM5 | No autofocus on landing pages | OK / Partial / Missing | |

Mobile checks that overlap with the 80-criterion LEVER rubric (e.g. TM1 overlaps with U7) are reported once, in the LEVER table, with a `(mobile)` tag. Mobile-only items (PM1 to PM5, FM5) live in this section alone.
