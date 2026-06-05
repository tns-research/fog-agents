---
slug: hybrid-2d-3d-fusion
name: Hybrid 2D/3D Graphic Fusion
funnel_fit: TOFU, MOFU
---

# Hybrid 2D/3D Graphic Fusion

## Description

Seamless fusion of flat 2D vector graphic panels and realistic 3D photography in a single frame. The subject (person) and their primary product prop physically overlap the boundary between the graphic design layer and the photographic layer, breaking the visual "wall" between the two. Geometric shapes from the graphic side bleed into the photographic area (e.g. into the sky). Text layers have 3D depth, they sit partially behind the subject or product, as if embedded in the scene's space.

## Performance signal

High scroll-stop rate in cold-audience prospecting: the 2D/3D overlap creates a visual paradox the brain cannot process as a known format, it pauses to resolve it. Strongest in categories where bold visual identity is a primary brand signal (tech, automotive, fashion, lifestyle). Less tested in performance-first DTC skincare/wellness but high novelty value in those categories. Best used sparingly, 1-2 briefs per batch of 15 to preserve its pattern-interrupt value.

## Funnel fit

- **TOFU:** Primary fit. The visual novelty earns scroll-stop and brand recall on cold audiences. The worm's eye + sky backdrop creates an aspirational, confident register. Keep copy to one idea, no offer, no price at this stage.
- **MOFU:** Valid when a product-feature or differentiation claim is the headline. The product prop in the overlap zone (physically crossing the 2D/3D boundary) puts the product center of attention without a plain studio packshot.
- **BOFU:** Avoid. The graphic complexity competes with the CTA clarity that BOFU requires. The format does not lend itself to friction-reduction messaging.

## Visual recipe

- **Format + crop:** Vertical 4:5 (feed). 9:16 acceptable for stories/reels. Square 1:1 loses the verticality the worm's eye + sky composition relies on, avoid.
- **Camera position:** Extreme low angle, worm's eye view (camera at or below subject knee level, angled sharply upward). The subject and product loom large against the sky. No eye-level, slightly elevated, or overhead compositions, the worm's eye is structural to this style.
- **Focal length:** 16-24mm wide equivalent. The wide angle exaggerates the low-angle perspective (enlarges lower body relative to head) and expands the sky area.
- **Lighting:** Bright, high-key. Main light simulates overhead sun or large overcast sky softbox. Subject and product evenly lit so they integrate cleanly with the graphic panels. No moody, low-key, or dark setups, the sky backdrop requires luminosity to read clearly against the graphic layer.
- **Color grade:** Crisp, saturated, clean digital, no film grain, no lifted blacks. Brand primary color is the unifying hue across graphic panels, subject's outfit accents, and product. Sky is clear, deeply saturated blue throughout.
- **Environment:** Massive clear blue sky as the photographic backdrop. Horizon line low or entirely out of frame. The graphic design panels occupy the lower portion or one side of the frame, bleeding into the sky area.
- **Composition logic:**
  - **Graphic layer:** Flat 2D vector-style geometric panels with bold shapes and brand-color fills. Occupies a defined zone (lower third, lower quarter, or left column).
  - **Photo layer:** The subject (person) and product prop, photographed at worm's eye, against blue sky.
  - **Overlap zone:** The subject's feet/legs and the product prop physically extend into and over the graphic panel, breaking its boundary. Geometric shapes from the graphic side extend into the photographic sky area (e.g. a triangle or diagonal bleeds upward into the blue).
  - **Text depth:** Headline and subheadline text have 3D spatial depth, they appear to sit partially behind the subject's body or product, as if the subject is standing in front of the type layer.
- **Subject:** A person reflecting the brand's audience. Standing or in motion, worm's eye view. Lower body prominent in frame, feet and legs cross into the graphic panel zone. Look direction: upward, forward, or confident, not looking down at camera. Natural, diverse. Outfit must incorporate brand primary color as accent or dominant element.
- **Exclusions:** No overhead or eye-level camera. No dark or moody background. No neutral grey stock-photo backdrop. No cramped composition, the sky must breathe. No product floating without a person (the overlap mechanic requires a subject).

## image_prompt_snippet

```
Vertical 4:5, wide environmental composite. Two visual layers fused seamlessly in a single frame: a flat 2D vector graphic panel occupying the lower [quarter / third] of the frame with bold geometric shapes in [BRAND PRIMARY COLOR], and a realistic photograph of [SUBJECT DESCRIPTION] shot from an extreme low angle (worm's eye view, camera at ground level angled sharply upward) against a massive, clear, deeply saturated blue sky. [SUBJECT] stands with feet and lower legs physically overlapping and extending over the graphic panel boundary, breaking the 2D/3D wall. Use the attached product reference image ([BRAND], [PRODUCT NAME]) as the single source for the product: exact shape, label, logo, brand colors. Place the product in [SUBJECT]'s hand or at their side, also crossing over the graphic panel edge into the photographic area. Geometric shapes from the graphic panel bleed upward into the sky photographic area ([SHAPE TYPE: e.g. sharp diagonal triangles / grid lines / soft organic arcs]). Headline and subheadline text rendered with 3D depth, sitting partially behind the subject's torso or product, as if the subject stands in front of the type layer. Camera: extreme worm's eye, 16-24mm wide equivalent, f/8. Lighting: bright high-key overhead (sun simulation), evenly lit, no harsh shadows on subject face. Color grade: crisp, saturated, clean digital, no grain. [BRAND PRIMARY COLOR] as unifying accent across graphic panels, [SUBJECT]'s outfit, and product. No grey neutral backdrop. No eye-level camera. No moody or dark lighting. Reserve upper quarter as a clear zone for headline if not embedded in 3D depth layer. (Style ref: high-end commercial fusion of flat vector art and realistic photography, Nike Air Max campaign, bold graphic identity)
```

## Typography notes

- **3D depth on text:** Headline and subheadline appear to have spatial depth, sitting between the graphic layer and the subject, partially occluded by the subject's body or product. This must be described in `image_prompt` (not just in `typography`) since it is a scene-composition instruction.
- **CTA button (optional):** If a CTA is included, describe it in `image_prompt` as: "minimalist pill-shaped CTA button with the text '[CTA TEXT]' in [BRAND COLOR], placed in the lower graphic panel zone."
- **Font style:** Bold, modern, geometric sans-serif. High contrast against both the graphic panel and the sky backdrop.
- **Placement:** Headline upper half (sky area) or embedded in the 3D depth layer between subject and background. Subheadline immediately below headline, same zone.
- **Color:** White or light on dark graphic panel zone; dark brand color on the bright sky zone, whichever creates legibility in each specific zone.

## Constraints

- The worm's eye camera is **mandatory**: do not apply this style to any brief where another camera position is specified.
- Requires a **human subject** in the scene, the overlap mechanic does not function without a person whose body crosses the 2D/3D boundary.
- Apply to a **maximum of 2-3 briefs per batch of 15**: pattern-interrupt value is diluted when overused.
- Not suitable for **product-only packshot** briefs (no person). Use a standard studio hero style for those.
- The graphic panel geometry should match brand tone (infer from `project-context/context.json` voice/positioning): sharp diagonals and speed-lines for dynamic/active brands; grid and minimal rectangles for tech/precision brands; soft organic arcs for wellness/beauty brands.

## Example use

TOFU brief for a French skincare brand (Anti-Category angle): a woman in her 30s photographed from worm's eye against a deep blue sky, holding the CO₂ mask product, her feet crossing into a bold geometric graphic panel in dark navy at the bottom of the frame. The headline sits partially behind her shoulder in large white geometric sans-serif with 3D depth. The panel's triangular shapes bleed one third of the way into the sky above.
