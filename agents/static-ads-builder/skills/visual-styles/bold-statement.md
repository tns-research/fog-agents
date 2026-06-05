---
slug: bold-statement
name: Bold Statement
funnel_fit: TOFU
---

# Bold Statement

## Description

A typography-first static where a single provocative, belief-shifting statement dominates the entire frame. The text IS the visual, no product, no image, or only a minimal product element at the bottom. The statement earns the scroll-stop by making the viewer think "wait, what?" or "finally, someone said it." The format works through identity alignment: the viewer either agrees (and feels seen) or disagrees (and engages). Either way, they stop scrolling.

## Performance signal

"Pattern-breaking" hooks are identified as one of the 12 highest-performing hook types across hundreds of Meta accounts (Curtis Howland, $100M+ spend). MS Paint / ugly-format statics that lead with bold text consistently outperform polished branded content: "Relevance wins, pretty doesn't" (Backlinko, Dirty Dog Farm). The format is the static equivalent of a "hot take", it earns attention through conviction, not aesthetics. Sunday Bedding's "Hot People Sleep Here" demonstrates how a bold statement with personality outperforms product-first approaches.

## Funnel fit

- **TOFU:** Primary and ideal fit. Cold audiences need a reason to stop scrolling. A bold, provocative statement creates cognitive engagement before any product awareness is needed. The statement IS the ad, it positions the brand's worldview.
- **MOFU:** Light use. Can work when the statement directly challenges a misconception the warm audience holds. But at MOFU, benefit-driven formats typically outperform pure attitude.
- **BOFU:** Avoid entirely. Attitude doesn't convert. BOFU needs offers and friction reduction.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 for Stories. Square 1:1 works for maximum text size.
- **Camera position:** N/A, this is a pure typography format. If product appears, it's minimal and secondary.
- **Focal length:** N/A.
- **Lighting:** N/A for typography. If product appears at bottom, flat, neutral.
- **Color grade:** High-contrast. Bold text on clean background. Two-color compositions work best.
- **Environment:** Solid-color background, brand color, black, white, or cream. Zero environmental context. The emptiness forces the eye onto the text.
- **Composition logic:**
  - **The statement occupies 60-80% of the frame.** Large, bold, impossible to miss. Left-aligned or centered.
  - **Background is a single solid color.** No gradients, no textures, no imagery. The text is the only visual element (besides optional product).
  - **Product (optional):** Small, bottom 15-20% of frame. Standing upright, clean. It anchors the statement to a brand, without it, the statement is just a poster.
  - **Brand logo (optional):** Small, corner placement. Identifies the brand without competing with the statement.
  - The statement should be 5-15 words. Long enough to carry a real idea. Short enough to be read in 1 second at mobile scale.
- **Subject:** No human subject. Typography-only (with optional small product).
- **Exclusions:** No imagery competing with the text. No decorative elements. No multiple messages, one statement only. No hedging language ("maybe", "we think", "some people say"). The statement must be confident and definitive.

## image_prompt_snippet

```
Vertical 4:5, bold typography statement composition. Solid [BACKGROUND COLOR: black / white / brand primary / cream] background. Single bold statement in large [TEXT COLOR: high contrast to background] geometric sans-serif, extra-bold weight, occupying 65-75% of frame area: "[STATEMENT, 5-15 words, provocative, belief-shifting, confident]". Text [ALIGNMENT: left-aligned / centered], vertically centered in frame with breathing room. [OPTIONAL: small product, use the attached product reference image ([BRAND], [PRODUCT NAME]), placed bottom-center, occupying ~15% of frame, standing upright, label visible. OPTIONAL: small brand logo in lower-right corner.] No imagery. No gradients. No decorative elements. No second message. The text IS the visual. (Style ref: Sunday Bedding "Hot People Sleep Here", Dirty Dog Farm MS Paint, conviction over aesthetics, identity-first, pattern interrupt)
```

## Typography notes

- **The statement IS the creative.** Extra-bold or black weight, geometric sans-serif. Size: as large as possible while maintaining 5-15 word readability. At mobile thumbnail scale, the first 3-4 words must be legible.
- **High contrast is mandatory.** White on black, black on white, or dark brand color on light background. No low-contrast combinations.
- **Alignment:** Left-aligned reads more conversational and modern. Centered reads more declarative and poster-like. Choose based on brand voice.
- **No headline/subheadline split** in the traditional sense. The statement IS the headline. If a subheadline exists, it's tiny, a brand tagline or product name at the bottom, not a second message.
- **The `headline` field** in the brief JSON contains the statement. The `subheadline` field is either `""` or the brand/product name.

## Constraints

- **One statement only.** No second message, no supporting text, no explanation. The power is in the singularity, one idea, absolute conviction.
- **5-15 words.** Shorter risks feeling empty; longer loses instant readability.
- **The statement must express a point of view.** It should be something the brand believes that not everyone agrees with. "Notre gel est bon" is not a bold statement. "Votre peau n'a pas besoin de 12 produits, elle a besoin du bon" IS.
- **No hedging.** No "peut-être", "nous pensons", "certains disent". The format demands confidence.
- **TOFU only as primary.** The format is a brand-positioning tool, not a conversion tool.
- **Apply sparingly**: 1-2 per batch. Pattern-interrupt value is diluted when overused.

## Example use

TOFU brief for NaturAloé Gel Originel: Solid cream background. Large bold dark-green text, left-aligned: "Votre peau n'a pas besoin d'un gel à 94 ingrédients. Elle a besoin d'un gel à 94 % d'aloé vera." Product small at bottom-center. No other elements.
