---
slug: ugc-text-overlay
name: UGC Text Overlay
funnel_fit: TOFU, MOFU
---

# UGC Text Overlay

## Description

Authentic, lo-fi image (UGC-style) with a bold benefit-first claim overlaid as large text in the first visual zone. Not a polished lifestyle shot with a text overlay, the image itself must feel organic: natural light, slightly imperfect framing, real environment. The text states a specific claim or hook in the first 2 seconds of viewing.

## Performance signal

38% higher ROAS vs. raw UGC without text overlay (DTC Meta data, 2025). The combination of an organic, non-ad-feeling image with a direct bold claim bypasses the "is this an ad?" filter while still delivering a clear message. Either element alone underperforms: a raw UGC image without the text claim drifts; a polished lifestyle shot with an overlay reads as a standard ad.

## Funnel fit

- **TOFU:** Primary fit. The lo-fi aesthetic reads as organic content; the bold text delivers the hook before the scroll. Works for problem-aware hooks ("What nobody tells you about [category]") and curiosity hooks.
- **MOFU:** Valid for early consideration, when the claim is a specific benefit or proof point rather than a product offer. The authentic image format maintains low skepticism while the text educates.
- **BOFU:** Avoid as the primary style. The lo-fi aesthetic reduces conversion trust at a stage when the audience needs reassurance, not discovery energy.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 for stories. Square 1:1 acceptable.
- **Camera position:** Slightly off-level, handheld, not perfectly horizontal. Mimics casual phone photography. Eye level or slightly above; no dramatic angles.
- **Focal length:** 24-28mm equivalent (phone camera wide). Slight environmental context in frame.
- **Lighting:** Natural ambient only, window light, outdoor light, or indoor practical sources. No visible supplemental lighting. Slightly overexposed in highlights is acceptable and reinforces authenticity. No studio softboxes.
- **Color grade:** Minimal or no grading, phone camera color science. Warm, slightly blown-out highlights. No cinematic grade, no film simulation, no lifted blacks. Raw feel.
- **Environment:** Real home, real bathroom, real kitchen, real outdoor context. No studio backdrop. No perfect prop arrangement. Slightly messy or lived-in is fine.
- **Composition logic:** Text is the primary message delivery mechanism. Large, bold, high-contrast text is overlaid in the first visual zone (upper third or center). Image is the credibility signal, it makes the text feel earned, not manufactured. Text is written directly into `image_prompt` as an overlaid element; it is not added in post.
- **Subject:** Real person in a natural moment, not posed for camera, not smiling directly at lens. Mid-action, looking off-frame, or caught in a candid gesture. Natural skin, real hair, no professional styling.
- **Exclusions:** No studio backdrop. No perfect composition. No professional lighting setup. No overly polished product placement.

## image_prompt_snippet

```
Vertical 4:5, handheld lifestyle mid-shot with UGC aesthetic. [SUBJECT DESCRIPTION, specific moment, not a pose, e.g. "a woman, early 30s, standing in her bathroom mid-application of [product], looking off toward the mirror"]. Camera slightly off-level, handheld angle, not perfectly horizontal, mimicking casual phone photography. 28mm equivalent (phone camera wide), f/2.0, shallow depth of field, real environment softly visible in background. Natural [window / indoor practical] light from [DIRECTION], slightly warm, overcast quality, no artificial lighting visible. Warm organic grade, slight overexposure in highlights, phone camera color, no cinematic grading. Large bold text overlaid in the upper third or center of the image: "[CLAIM TEXT]" in high-contrast [COLOR], text appears as part of the image, not added in post. No perfect composition. No smile directed at camera. No professional styling. No studio backdrop. (Style ref: shot on iPhone Pro, social-native, real-home context, candid)
```

## Typography notes

- The text claim is rendered **inside the image** as an overlaid element, it is part of the `image_prompt`, not a separate `typography` layer added in post.
- Describe text in `image_prompt` directly: font weight (bold/extra-bold), color (white, black, or high-contrast brand color), placement zone (upper third, center), approximate size ("large, occupying roughly [X]% of frame width").
- The `headline` field in the JSON still carries the main line of copy, it serves as reference for what the image should render as in-frame text.
- `typography.font_style`: "Sans-serif, extra-bold, high contrast", consistent with the lo-fi text-first aesthetic.

## Constraints

- The image must feel genuinely lo-fi, do not apply this style to polished studio packshots or premium lifestyle compositions.
- Text must be legible, describe it as high-contrast (white on dark area, black on light area, or brand color with sufficient contrast).
- Requires a real-context environment (home, bathroom, kitchen, outdoors), not a neutral grey or white studio background.
- When product is in the scene, it must appear naturally (in hand, on a shelf, on a counter), not hero-placed or studio-lit.

## Example use

TOFU brief (Skeptic Disarm angle): a woman in her bathroom holding the CO₂ mask product, candid phone-camera framing. Bold white text overlaid in the upper third: "Oui, il y a vraiment du CO₂ dans ce masque." No other copy elements. The rawness of the photo makes the direct claim feel honest rather than promotional.
