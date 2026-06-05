---
slug: testimonial-screenshot
name: Testimonial Screenshot
funnel_fit: MOFU, BOFU
---

# Testimonial Screenshot

## Description

A raw or lightly styled screenshot of a real customer review, Trustpilot, Google, DMs, email, or the brand's own platform, overlaid on a product photo background. The rawness of the format is the trust signal: the screenshot feel is the mechanic. Designed or polished versions of the same content underperform because the audience has learned to distrust "designed testimonial graphics."

## Performance signal

Outperforms designed review graphics in MOFU and BOFU by a significant margin (Meta DTC 2025 data). The raw screenshot format reads as evidence, not marketing. Audiences have strong pattern-recognition for designed graphics, they know the brand curated and styled it. A screenshot looks like something the brand grabbed from their reviews dashboard without touching it. That unpolished quality is what makes it believable.

## Funnel fit

- **TOFU:** Avoid as a primary format. Cold audiences have no context for the review, they don't know the brand or the product yet, so the testimonial doesn't land. Use only if the review text opens with a strong problem-hook that works without brand context.
- **MOFU:** Primary fit. The audience is comparing options, a specific, detailed customer review provides the third-party proof they're looking for.
- **BOFU:** Strong fit. For an audience who has already considered the product, a specific review removes the last trust objection. Pair with an offer for maximum BOFU impact.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 for stories.
- **Camera position:** Agent selects based on product background, typically eye level, 3/4 front or slightly elevated for the product hero underneath the overlay.
- **Focal length:** Agent selects, 85mm or 50mm for product background (product should be softly present but not competing with the text overlay).
- **Lighting:** Agent selects for the product background layer. Typically soft and clean so the overlay text remains legible. Avoid high-contrast or very dark backgrounds unless overlay panel has sufficient contrast.
- **Color grade:** Neutral to warm, the overlay panel provides most of the visual weight; the background image should not fight it.
- **Environment:** Product background: the brand's product on a surface or in a context relevant to the brief. The overlay panel sits above it.
- **Composition logic:**
  - **Background layer:** Product photo, softly lit, placed lower or to one side, slightly reduced in visual weight to not compete with the text overlay.
  - **Overlay panel:** A semi-transparent white or very light panel, positioned center or upper-center, containing: (1) 5-star rating (★★★★★), (2) 2-4 sentences of customer review text naming a specific result and time period, (3) customer first name or handle below the review text, (4) optional: platform logo (Trustpilot star, Google "G") in one corner.
  - The overlay mimics a real screenshot, no brand colors, no brand fonts on the overlay itself. The panel should look like it was screenshotted from a review platform.
- **Subject:** Optional, a person can appear in the product background, but the review overlay is the primary visual element.
- **Exclusions:** No designed, fully branded "review card" aesthetic. No brand colors on the overlay panel. No multiple reviews in one frame. No fake or generic reviews ("Great product!", too short, too generic to build trust).

## image_prompt_snippet

```
Vertical 4:5, product photo background with raw screenshot UI overlay. Use the attached product reference image ([BRAND], [PRODUCT NAME]) as the single source for the product: exact shape, label, logo, brand colors. Place product [POSITION: e.g. lower-center frame / lower-left], slightly softened in visual weight to serve as a background layer. Camera [POSITION], [FOCAL LENGTH] equivalent, [DEPTH OF FIELD]. [LIGHTING: agent selects, clean and legible]. [COLOR GRADE: neutral to warm, not competing with overlay]. Over the product background: a semi-transparent white panel overlaid center or upper-center of frame, mimicking a raw review screenshot, containing a 5-star rating (★★★★★), the following customer review text rendered clearly and legibly: "[SPECIFIC REVIEW TEXT, result + time period, e.g. 'J'utilise ce masque depuis 3 semaines, ma peau est visiblement plus lumineuse. Je ne m'attendais pas à un résultat aussi rapide.']", and the customer name "[FIRST NAME or HANDLE]" below. Optional: small [Trustpilot / Google] platform icon in corner of the panel. No brand colors or brand fonts on the overlay panel, it must read as a raw screenshot, not a designed graphic. No multiple reviews. (Style ref: raw screenshot, unpolished, the rawness is the trust signal)
```

## Typography notes

- **Overlay text:** Rendered as plain platform-style typography, dark grey or black on white/light panel, no brand font. Review text in regular weight, customer name in light or italic. Mimics the actual visual language of Trustpilot, Google Reviews, or a DM screenshot.
- **Star rating:** Rendered as ★★★★★ in the platform's gold/yellow, it's a recognized trust symbol.
- **Headline field:** The `headline` in the JSON should echo the most compelling line from the review text (in copy_language), it serves as the ad's copy frame even if the visual renders the full review inside the overlay.
- **Subheadline:** Can be `""`, the review text inside the overlay is the copy payload.

## Constraints

- The review text must be **specific**: it must name a result, a time period, a before-state, or a concrete observation. Generic reviews ("Super produit !") do not work, they read as made-up.
- The overlay panel must feel **raw and undesigned**: no brand colors, no brand logo on the panel, no decorative elements. The moment it looks designed, the trust signal disappears.
- Do not stack multiple reviews in a single frame. One review, fully rendered and readable.
- If the brand has **no external reviews** (e.g. no Trustpilot profile), the `image_prompt` can reference a DM-style screenshot format or a brand-owned review format, but the rawness must be preserved.

## Example use

BOFU brief (Social Proof with Specificity angle) for a skincare brand: the CO₂ mask product placed lower-left, soft background. White overlay panel center-frame with ★★★★★, the review "J'ai essayé 4 masques différents cette année. Celui-là, je le rachète chaque mois depuis juillet.", and "Sophie M." below. Headline echoes the key claim in the brief's copy.
