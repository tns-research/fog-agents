# Visual Styles Registry

The 18 named styles of the agent. **Every style is an HTML/CSS layout** rendered locally by `scripts/build.py` (`templates/styles.css`, one block per slug) in 1:1, 4:5 and 9:16: the text, the logo, the product and the screenshot are placed exactly, at no cost. An image model is only used for a text-free photographic plate behind the spend gates (`ugc-text-overlay`, `ingredient-origin-strip`, `hybrid-2d-3d-fusion` and `before-after-asymmetric` use a real photo or a plate as media).

Rendered examples of all 18 styles in the three formats: `python3 scripts/pipeline.py tests/fixtures/all-styles/ads.json --out /tmp/all-styles` (from the agent folder).

**Examples in the style files are shape only.** The product figures in them stand for facts that brand would hold in its own `positioning.proof`. In a real ad, every figure comes from `positioning.proof` or a source URL (claims gate: `shared/skills/enforcing-claims-policy/SKILL.md` at the repo root, enforced by `build.py`); a comparison against competitors states only what a source shows.

---

## When to apply a style

- `visual_style` set in the config: that layout for every concept of the batch (lock mode), unless the founder says otherwise.
- `visual_style` empty: per concept, the best fit on (1) funnel-stage fit, (2) angle fit, (3) diversity (no slug more than twice in a batch of six). Every concept gets one of the slugs below.

## What each layout needs in `ads.json`

| Slug | Copy slots used | Media |
|------|-----------------|-------|
| `bold-statement`, `meme-static` | headline, subhead, cta, proof | none |
| `three-benefits-card`, `crossed-out-problems` | headline, 2 to 5 `bullets`, subhead (crossed-out: the resolution), cta | optional product or screenshot (three-benefits) |
| `mini-landing-page` | headline, subhead, 2 to 4 `bullets`, proof, cta (required) | optional product or screenshot |
| `benefit-timeline` | headline, 2 to 5 `bullets` with a `label` (time step) | none |
| `flowchart-decision` | headline (the question), 2 to 3 `bullets` with a `label` (branch) | none |
| `us-vs-them-comparison` | headline, `columns` them/us, mirrored rows (2 to 5) | none |
| `myth-vs-fact` | headline, `columns` them = myth, us = fact | none |
| `before-after-asymmetric` | headline, `columns` them = before, us = after | optional product or screenshot in the after panel |
| `cost-reframe-card` | headline, `columns` with the figure as first item, subhead | none |
| `social-proof-card` | headline, `proof` (real quote, rating optional), cta | none |
| `testimonial-screenshot` | headline, `proof` with `attribution` (a real review) | none |
| `reply-to-comment` | headline, `comment` (a real comment with its source, the brand reply) | none |
| `feature-callout-arrows` | headline, 2 to 4 `callouts` with x/y anchors on the media | screenshot or product (required) |
| `ugc-text-overlay` | headline and subhead as caption boxes, cta | photo or plate (required), shown whole |
| `ingredient-origin-strip` | headline, subhead | origin photo, then product (second media) |
| `hybrid-2d-3d-fusion` | headline, subhead | product cut-out (transparent PNG) over flat panels |

The `## Visual recipe` and `## image_prompt_snippet` sections of each style file describe the composition the layout implements and, for photo styles, the scene of a plate. Any text they mention is set by the HTML, never asked of an image model.

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

1. Read `skills/visual-styles/<slug>.md` for the intent, the funnel fit and the constraints of the style.
2. Fill the copy slots of the table above in `ads.json`; respect `## Constraints` (number of lines, mirror rows, no named competitor).
3. For a plate, take the scene from `## Visual recipe` and write a text-free prompt (no words, no logo, no product).
4. `## Performance signal` is for the report's rationale only.

---

## Adding a new style

Create `skills/visual-styles/<slug>.md` like the others, add a row to the index above, add the slug to the `style` enum of `assets/ads.schema.json`, a layout function in `scripts/build.py` (`STYLE_FN`) and its CSS block in `templates/styles.css`, then a concept using it in `tests/fixtures/all-styles/ads.json` and run `scripts/selftest.py`.
