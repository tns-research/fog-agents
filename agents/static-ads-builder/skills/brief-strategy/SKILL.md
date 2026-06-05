---
name: brief-strategy
description: Plan funnel-aware static-ad concepts before any copy or image prompt. Distributes the brief pool across TOFU/MOFU/BOFU, assigns one named angle per brief from the angle library, enforces a visual diversity mandate and a surprise test, and grounds every "why it works" in project-context and optional market-signal. Use before brief-json. Triggers: "plan creatives", "ad concepts", "funnel strategy".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read
---

# Skill: brief-strategy

Generate **strategic ad concepts that are likely to perform**, then hand a clean per-brief plan to `brief-json`. Strategy first, copy and image prompts second.

Grounding sources (read-only, in priority order):
- `project-context/context.json`: ICP (who/pains/jobs), offer, positioning, proof, voice. The primary anchor.
- `project-context/brand.json`: the brand palette AND the harvested **assets** (`assets.logo_path`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`). Read this to know what real visual material exists before planning, it changes what concepts are possible.
- Optional `market-signal/` report in the same project: live pains, hooks, objections, quotes. Supporting input only, never overrides core context.
- `assets/ad-library.md`: named angles, photographic vocabulary, headline tests, the visual diversity mandate.

If `context.json` is absent, work from the Step 0 inline answers. Never invent statistics, quotes, or studies; anchor "why it works" in loaded context, and respect `voice.claims_policy`.

**Inventory the assets first.** Before assigning concepts, list what `brand.json.assets` actually contains, this is the founder's real material and it dictates which executions are possible:
- a **physical product** image (`assets.images[]` with a packshot) -> product-hero concepts are on the table;
- a **product UI screenshot** (`assets.screenshot_path`, or a UI image in `assets.images[]`) -> for a SaaS / app / service this IS the product, build device-mockup, feature-callout, and mini-landing concepts around it;
- a **logo** (`assets.logo_path`) -> nearly always available; the default way to brand any creative, especially a typographic or screenshot one;
- a **hero / og:image** (`assets.og_image_path`) -> a recognizable brand backdrop.

Plan to *use* this material. A creative that ignores the founder's real logo and product UI in favor of a generic illustration is a miss, not a style choice.

---

## 2025 context: creative as targeting

Meta's algorithm uses the creative itself as the primary targeting mechanism. The ad reaches the audience that resonates with it. Two implications:

1. **Creative IS the targeting.** A diverse pool (different angles, formats, visual registers) reaches different segments automatically. A pool with one tone targets one audience. Diversity of angle equals diversity of reach.
2. **Ad families, not ad variants.** Do not produce slightly adjusted versions of one ad. Produce genuinely different executions of the same brand/product (a meme-style hook, a testimonial screenshot, an origin-number visual, a typographic card, a product hero). Each finds a different segment.

These principles reinforce the named-angle requirement and the visual diversity mandate below.

---

## When to load

- Workflow Step 3 of `static-ads-builder`, when planning the brief pool (`num_briefs`, distributed by `funnel_stages`).

---

## Funnel stages

| Stage | Goal | Audience state | What the ad must give them |
|-------|------|----------------|----------------------------|
| **TOFU** | Awareness, reach, recall | Cold; may not know brand or category solution | Stop the scroll; one clear idea or feeling; memorable visual; low commitment |
| **MOFU** | Consideration, preference | Aware; comparing or hesitating | Reasons to believe; differentiation; proof; "why us / why this" |
| **BOFU** | Conversion | Ready to act; may have visited site or added to cart | Clear offer, trust, reduced friction, one strong CTA |

---

## What works per stage

### TOFU

- **Single clear idea or emotion.** One takeaway, no long copy, no multiple CTAs.
- **Strong visual or hook.** Pattern interrupt: unexpected angle, specific sensory detail, bold contrast, or a question the audience recognises as their own inner monologue.
- **Broad relevance.** Values, aspiration, shared frustration, not specs.
- **Anti-category move.** Every category has conventions; identify and break one. The contrast earns attention.
- **Angles that work:** Anti-Category (1.1), Specific Ritual (1.2), Wrong Answer (1.3), Origin Number (1.4), Quiet Flex (1.5), Parallel (1.6), Insider (1.7), Quiet Confession (1.8).
- **CTA:** "Learn more" or none. Never "Shop now" at TOFU.
- **Avoid:** long copy, price/offer focus, generic category-standard visuals.

### MOFU

- **Differentiation and proof.** "Why us" vs alternatives: sourcing, process, quality, reviews, credentials.
- **Problem-agitate-solve.** Name the problem, amplify briefly, present the product as the solution.
- **Education and transparency.** How it is made, where it comes from, what makes it better.
- **Comparison.** Before/after, with/without, "most X do Y; we do Z."
- **Product clearly visible.** Hero or in-context shots; the audience is evaluating.
- **Angles that work:** Process Reveal (1.9), False Choice Collapse (1.10), Skeptic Disarm (1.11), Selection Proof (1.12), Expert Voice (1.13), Comparison Without a Competitor (1.14).
- **Avoid:** pure awareness fluff with no reason to believe; hard-sell CTA as if already convinced.

### BOFU

- **Clear offer and one CTA.** What they get, what they do.
- **Trust and reassurance.** Guarantee, delivery, easy cancel, specific social proof.
- **Urgency or scarcity only if true.**
- **Product + offer together.**
- **Angles that work:** Easy First Step (1.15), Social Proof with Specificity (1.16), Cost Reframe (1.17), Guarantee as Headline (1.18), Absence Cost (1.19), Micro-Commitment (1.20).
- **One CTA maximum.** Each BOFU brief does one job.
- **Avoid:** vague brand poetry with no offer; competing CTAs; misleading urgency; percentage-only social proof. Never run TOFU creative at a hot audience.

---

## Concept angle library

Use these named angles from `assets/ad-library.md` Section 1. Record the angle name per brief.

**TOFU:** Anti-Category (1.1) / Specific Ritual (1.2) / Wrong Answer (1.3) / Origin Number (1.4) / Quiet Flex (1.5) / Parallel (1.6) / Insider (1.7) / Quiet Confession (1.8)

**MOFU:** Process Reveal (1.9) / False Choice Collapse (1.10) / Skeptic Disarm (1.11) / Selection Proof (1.12) / Expert Voice (1.13) / Comparison Without a Competitor (1.14)

**BOFU:** Easy First Step (1.15) / Social Proof with Specificity (1.16) / Cost Reframe (1.17) / Guarantee as Headline (1.18) / Absence Cost (1.19) / Micro-Commitment (1.20)

**Do not assign the same angle to more than one brief.** If 5 TOFU briefs are needed, use 5 different angles.

---

## Strategy output (per concept)

For each brief, produce a structured note before writing copy:

1. **Funnel stage:** TOFU | MOFU | BOFU
2. **Named angle:** from the library (e.g. "Anti-Category - 1.1")
3. **Strategic angle in one sentence.**
4. **Why it works:** link to a specific audience state, pain, or motivation from context. Name the mechanism, not "it's engaging".
5. **Hook type:** question / promise / story / comparison / contrast / confession / confession + number / etc.
6. **Visual approach:** explicit camera position + lighting setup + environment (the image prompt inherits these).
7. **Assets in frame:** which real assets the creative uses, from the inventory, as a list of roles (`product` / `screenshot` / `logo` / `hero`) or "none" for a pure typographic / illustrated card. State each one's job (hero packshot / UI in a device mockup / logo lockup top-left / hero backdrop). This list becomes the brief's `reference_assets`. For a SaaS or service with no packshot, prefer `screenshot` and/or `logo` over "none" whenever the concept can carry them.
8. **Visual style:** the assigned style slug (lock or auto-select) or `"free"`.

---

## The surprise test

Before finalising the plan, apply to the batch as a whole:

> *"If someone who has seen 1,000 ads in this category scrolled through all of these, how many would make them pause?"*

If fewer than a third would, the batch is too safe. Push the most category-standard briefs harder: what would the opposite look like, what would a brand with twice the confidence do, what specific sensory detail would make the image feel real rather than generated. Surprise must serve the brand and the funnel stage, not contrarianism for its own sake.

---

## Visual diversity mandate

When assigning visual approach to each concept, apply these constraints across the pool:

- **No angle repeated.** Each named angle appears once.
- **Camera position:** minimum 4 distinct height + angle combinations. No more than 3 briefs share one.
- **Lighting:** minimum 4 distinct source + direction + quality setups. No more than 3 briefs share one.
- **Environment:** minimum 3 types (origin/outdoor, lifestyle/interior, minimal/studio). At least 1 typographic-hero brief (type on flat background, no product) if it serves a concept.
- **Subject distance:** minimum 3 (wide/environmental, medium/lifestyle, close-up/detail).
- **Forbidden clichés (never the primary subject):** steam rising from a cup / hands cupped around a mug with blurred background / beans scattered on a flat surface / marble surface as the only background / identical overhead flat-lay for every hero. (These are the coffee-category examples; translate the principle to the founder's actual category.)

Record the planned camera + lighting per brief to catch repetition before writing prompts.

---

## Distribution of the pool

- **`all`:** split evenly across the three stages (e.g. for 12: 4 TOFU + 4 MOFU + 4 BOFU). Vary angles and visual approach within each stage.
- **One stage:** the whole pool on that stage, using all available angles for it before repeating any (and never repeating).
- **Two stages:** split the pool between them, no third stage. Adjust counts so the total equals `num_briefs`.

A real asset (product, screenshot, or at minimum the logo) should appear in **most** briefs when the goal is performance; keep only 2-3 asset-free for pure typographic / storytelling pattern interrupts. Physical-product brands lean on the packshot; SaaS / app / service brands lean on the UI screenshot and the logo.

---

## Assets-driven concepts (SaaS, app, service, anything with no packshot)

When the founder sells software or a service, there is no bag or bottle to photograph, but there is almost always a **logo** and a **product UI** (the homepage screenshot or an app/dashboard image). Build concepts that put these on the creative instead of defaulting to text-only cards:

- **Product in a device mockup.** The UI screenshot inside a clean laptop or phone frame, floating on a brand-colored background, with the headline beside or below. Attaches `screenshot` (+ `logo`). Styles: `mini-landing-page`, `bold-statement` with a screenshot, or `free`.
- **Feature callout.** The screenshot with 2-3 annotation arrows or labels pointing at key UI elements. Attaches `screenshot` (+ `logo`). Style: `feature-callout-arrows`.
- **Before / after the tool.** Messy manual state vs. the clean dashboard. Attaches `screenshot`. Style: `before-after-asymmetric`.
- **Native social proof.** A testimonial or comment over a faint UI or brand backdrop. Attaches `screenshot` or `hero` (+ `logo`). Styles: `testimonial-screenshot`, `reply-to-comment`, `social-proof-card`.
- **Logo-led typographic card.** When a concept is genuinely text-first (a bold statement, a myth-vs-fact), still attach the `logo` as a small corner signature so the creative is unmistakably the founder's. This is the floor: **a SaaS creative should almost never ship with neither the UI nor the logo on it.**

Rule of thumb for a SaaS batch: at least half the briefs show the real UI screenshot, and nearly all carry the logo. Reserve "none" (no asset) for the 1-2 sharpest typographic pattern interrupts.

---

## Visual style assignment (two modes)

- **Lock mode** (`visual_style` slug set): apply that style's `visual_recipe` (camera, environment, composition, lighting, color grade, exclusions) to every brief. The named angle remains the strategic idea; the style is the visual container, an independent layer. Respect the style's `constraints`.
- **Auto-select mode** (`visual_style` empty): for each brief, pick the best-fit named style from `skills/visual-styles/REGISTRY.md` using three criteria in order: (1) **funnel-stage fit** (the style's `funnel_fit` must include the brief's stage), (2) **angle fit** (does it amplify the strategic angle), (3) **diversity** (no slug more than 2-3 times). When no named style fits, mark the brief `"free"` and build visual direction from `assets/ad-library.md` Section 3.

---

## References

- Named angles, photographic vocabulary, headline tests, diversity mandate: `assets/ad-library.md`
- Visual styles: `skills/visual-styles/REGISTRY.md` and per-style files
- Business grounding: `project-context/context.json`; brand palette + harvested assets: `project-context/brand.json` (`assets.*`); live signals: optional `market-signal/` report
