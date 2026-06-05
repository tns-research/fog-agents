# Visual Styles Registry

Index of named visual styles available to the agent. Each style is a separate file in this directory. When a style is applied, the agent imports the file's `visual_recipe` into the `image_prompt` and `typography` of the brief, overriding or extending the defaults from the 7-element formula.

---

## When to apply a style

- If `visual_style` in the client config is set to a slug from this registry: apply that style to **all 15 briefs** (lock mode) unless the user specifies otherwise.
- If `visual_style` is empty or absent: **auto-select mode**. The agent treats the full registry as the pool. For each brief, assign the best-fitting style using three criteria in order: (1) **funnel-stage fit** (style's `funnel_fit` must include the brief's stage), (2) **angle fit** (does the style amplify the strategic angle?), (3) **diversity** (distribute across multiple slugs; no slug repeated more than 3 times across 15 briefs). For briefs where no named style clearly fits, use **free visual direction** from `assets/ad-library.md` Section 3.
- The agent may also apply a style to a **subset of briefs** when the user explicitly requests it (e.g. "use the hybrid-2d-3d-fusion style for the TOFU briefs only").

### Style categories

The registry contains two categories of visual styles:

1. **Photographic styles** (`ugc-text-overlay`, `before-after-asymmetric`, `ingredient-origin-strip`, `hybrid-2d-3d-fusion`): describe a scene for AI image generation using the 7-element formula (camera, lighting, environment, etc.).
2. **Designed static / Meta Ad template styles** (`three-benefits-card`, `us-vs-them-comparison`, `crossed-out-problems`, `social-proof-card`, `feature-callout-arrows`, `myth-vs-fact`, `reply-to-comment`, `bold-statement`, `mini-landing-page`, `benefit-timeline`, `flowchart-decision`, `meme-static`, `testimonial-screenshot`, `cost-reframe-card`): describe a graphic design layout where text, icons, and layout structure are the primary creative elements. The `image_prompt` for these describes the visual composition including text rendering, layout zones, and graphic elements, not just photography.

Both categories use the same brief JSON schema. The distinction is in the nature of the `image_prompt`: photographic styles describe a scene to photograph; designed statics describe a layout to compose.

---

## Style index

| Slug | Name | Funnel fit | Brief description |
|------|------|------------|-------------------|
| `ugc-text-overlay` | UGC Text Overlay | TOFU, MOFU | Lo-fi authentic image with bold benefit-first text overlaid in the first visual zone |
| `meme-static` | Meme-Style Static | TOFU | Problem-first typographic card; bold text is the primary visual, no product |
| `testimonial-screenshot` | Testimonial Screenshot | MOFU, BOFU | Raw or lightly styled screenshot of a real customer review over a product background |
| `before-after-asymmetric` | Before/After Asymmetric | MOFU, BOFU | Two-panel split; problem state takes 35% of frame, resolution takes 65% |
| `ingredient-origin-strip` | Ingredient/Origin Strip | MOFU | Split composition: raw source or origin on one half, product on the other |
| `cost-reframe-card` | Cost Reframe Card | BOFU | Typography-forward product + math creative; reframes price against an anchor the audience already accepts |
| `hybrid-2d-3d-fusion` | Hybrid 2D/3D Graphic Fusion | TOFU, MOFU | Seamless fusion of flat vector graphic panels and realistic 3D photography; subject and product overlap the graphic boundary; worm's eye view; bold sky backdrop |
| `three-benefits-card` | Three Benefits Card | TOFU, MOFU | Product image + 3 key benefits listed with icons or checkmarks; scannable listicle layout |
| `us-vs-them-comparison` | Us vs. Them Comparison | MOFU | Two-column split: product (checkmarks) vs. generic alternative (X marks); comparative layout |
| `crossed-out-problems` | Crossed-Out Problems | MOFU, BOFU | 3-5 common problems with bold strikethroughs; product as the resolution below the list |
| `social-proof-card` | Social Proof Card | MOFU, BOFU | Customer quote highlighted with marker effect + star rating + product; trust-first format |
| `feature-callout-arrows` | Feature Callout with Arrows | MOFU | Product photo with annotation arrows pointing to key ingredients or features; editorial breakdown |
| `myth-vs-fact` | Myth vs. Fact | TOFU, MOFU | Two-zone split: common myth (muted) vs. corrective fact (bright) with product; belief-shifting |
| `reply-to-comment` | Reply-to-Comment Native | MOFU, BOFU | Native IG/FB comment UI: user question + brand reply that naturally spotlights product; disarms ad filter |
| `bold-statement` | Bold Statement | TOFU | Typography-first: one provocative statement dominates the frame; identity-positioning pattern interrupt |
| `mini-landing-page` | Mini Landing Page | MOFU, BOFU | Dense vertical stack: headline + product + benefits + proof + CTA in one organized frame; high-intent conversion |
| `benefit-timeline` | Benefit Timeline | MOFU, BOFU | Benefits organized along a time axis (Day 1 → Week 1 → Month 1); builds ritual and progressive results |
| `flowchart-decision` | Flowchart Decision Tree | TOFU, MOFU | Yes/no logic tree guiding viewer to the conclusion they need the product; interactive engagement |

---

## How the agent uses a style file

1. Read the style file for the relevant slug from `skills/visual-styles/[slug].md`.
2. Apply the `## Visual recipe` fields to the brief's `image_prompt`: camera position, environment, composition logic, lighting, color grade, exclusions.
3. Apply `## Typography notes` to the brief's `typography` object.
4. Use `## image_prompt_snippet` as the starting skeleton, extend it with brand-specific subject, product placement, and reserve-area instructions from the 7-element formula. Replace all `[PLACEHOLDER]` values.
5. Respect `## Constraints`, do not apply the style in ways explicitly listed as invalid.
6. `## Performance signal` is for the rationale section (human-facing only), not the JSON payload.

---

## Adding a new style

Create a new file `skills/visual-styles/[slug].md` following the schema in any existing style file. Add a row to the index table above. No other files need to change for the style to be available, the agent discovers it from this registry.
