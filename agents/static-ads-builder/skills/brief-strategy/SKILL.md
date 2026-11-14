---
name: brief-strategy
description: Plan funnel-aware static-ad concepts before any copy. Starts from the performance read (winners to extend, losers to retire, extend and explore shares), distributes the batch across TOFU/MOFU/BOFU, assigns one named angle and one of the 18 styles per concept, applies a surprise test, and grounds every "why it works" in project-context and optional market-signal. Outputs one line per concept for write-ads-spec. Use at Step 2 of static-ads-builder. Triggers: "plan creatives", "ad concepts", "funnel strategy", "what should we make next".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read
---

# Skill: brief-strategy

Generate **strategic ad concepts that are likely to perform**, then hand a one-line-per-concept plan to [`../write-ads-spec/SKILL.md`](../write-ads-spec/SKILL.md). Strategy first, copy second.

## Start from the performance read

When `ads-performance-YYYYMMDD.json` exists ([`../read-performance/SKILL.md`](../read-performance/SKILL.md)), its `next_batch` block sets the frame:

- `fix_post_click_first: true` → the batch is the extensions of the winners only, and the report leads with the post-click actions. More reach does not fix a page that stopped converting.
- `extend` → about `extend_share` of the batch prolongs the winners: same angle and stage, a new execution (another style, another format, a sharper hook). Each such concept names the winner and its metric (`extends` in ads.json).
- `retire` → those angle and style pairs are not proposed again this run.
- `creative_fixes` → a loser with a good post-click rate keeps its angle with a new hook and style.
- the rest explores angles absent from `angles_tested`.

Without a performance read, the whole batch explores.

Grounding sources (read-only, in priority order):
- `project-context/context.json`: ICP (who/pains/jobs), offer, positioning, proof, voice. The primary anchor.
- `project-context/brand.json`: the brand palette AND the harvested **assets** (`logos.on_dark` / `logos.on_light`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`; a `brand.json` without `schema_version` "2.0" carries `assets.logo_path` instead). Read this to know what real visual material exists before planning, it changes what concepts are possible.
- Optional `market-signal/market-signal-<YYYYMMDD>.json` sidecar in the same project (latest date wins; schema in `shared/handoffs.md` at the repo root): personas, escalated pains, objections, verbatim quotes with permalinks, candidate headlines. Supporting input only, never overrides core context. Use the quotes as customers' real words for angles and headlines (verbatim, same language); never as testimonials, reviews or social proof for the product. Say in the report whether the sidecar was used.
- `assets/ad-library.md`: named angles, photographic vocabulary, headline tests, the visual diversity mandate.

If `context.json` is absent, work from the Step 0 inline answers. Never invent statistics, quotes, or studies; anchor "why it works" in loaded context, and respect `voice.claims_policy`.

**Inventory the assets first.** Before assigning concepts, list what `brand.json.assets` actually contains, this is the founder's real material and it dictates which executions are possible:
- a **physical product** image (`assets.images[]` with a packshot) -> product-hero concepts are on the table;
- a **product UI screenshot** (`assets.screenshot_path`, or a UI image in `assets.images[]`) -> for a SaaS / app / service this IS the product, build UI, feature-callout and mini-landing concepts around it;
- a **logo** (`logos.*`, or `assets.logo_path` in a file without `schema_version` "2.0") -> nearly always available; the default way to brand any creative, especially a typographic or screenshot one;
- a **hero / og:image** (`assets.og_image_path`) -> a recognizable brand photo (role `photo`).

Plan to *use* this material. A creative that ignores the founder's real logo and product UI in favor of a generic illustration is a miss, not a style choice.

---

## 2025 context: creative as targeting

Meta's algorithm uses the creative itself as the primary targeting mechanism. The ad reaches the audience that resonates with it. Two implications:

1. **Creative IS the targeting.** A diverse pool (different angles, formats, visual registers) reaches different segments automatically. A pool with one tone targets one audience. Diversity of angle equals diversity of reach.
2. **Ad families, not ad variants.** Do not produce slightly adjusted versions of one ad. Produce different executions of the same brand/product (a meme-style hook, a testimonial screenshot, an origin-number visual, a typographic card, a product hero). Each finds a different segment.

These principles reinforce the named-angle requirement and the visual diversity mandate below.

---

## When to load

- Workflow Step 2 of `static-ads-builder`, when planning the batch (`num_ads`, distributed by `funnel_stages`).

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
- **One CTA maximum.** Each BOFU concept does one job.
- **Avoid:** vague brand poetry with no offer; competing CTAs; misleading urgency; percentage-only social proof. Never run TOFU creative at a hot audience.

---

## Concept angle library

Use these named angles from `assets/ad-library.md` Section 1. Record the angle name per concept.

**TOFU:** Anti-Category (1.1) / Specific Ritual (1.2) / Wrong Answer (1.3) / Origin Number (1.4) / Quiet Flex (1.5) / Parallel (1.6) / Insider (1.7) / Quiet Confession (1.8)

**MOFU:** Process Reveal (1.9) / False Choice Collapse (1.10) / Skeptic Disarm (1.11) / Selection Proof (1.12) / Expert Voice (1.13) / Comparison Without a Competitor (1.14)

**BOFU:** Easy First Step (1.15) / Social Proof with Specificity (1.16) / Cost Reframe (1.17) / Guarantee as Headline (1.18) / Absence Cost (1.19) / Micro-Commitment (1.20)

**Do not assign the same angle to more than one concept.** If 5 TOFU concepts are needed, use 5 different angles.

---

## Strategy output: one line per concept

Write the plan as a table, one row per concept, before any copy:

| # | Stage | Angle | Style | Formats | Ad set | Material | Extends or explores | Why it works |
|---|-------|-------|-------|---------|--------|----------|---------------------|--------------|
| 1 | TOFU | anti-category (1.1) | bold-statement | 4:5, 9:16 | tofu-broad | logo only | explores | one mechanism tied to a pain or a job of `context.json` |

- **Angle:** from the library, as a slug (`anti-category`, `process-reveal`); it becomes part of the ad name, so perf aggregates by it.
- **Style:** a slug of [`../visual-styles/REGISTRY.md`](../visual-styles/REGISTRY.md), chosen for the stage and the angle; every style is an HTML layout, so typographic styles cost nothing.
- **Material:** the real assets the concept shows (`product`, `screenshot`, `photo`, logo) from the inventory, or `plate` when only a text-free generated background would do (it will go through the spend gates). For a SaaS or service with no packshot, prefer the UI screenshot and the logo.
- **Extends or explores:** "extends <ad name> (<metric>)" or "explores". Never a clone of a winner with a word changed.
- **Why it works:** the mechanism, not "it is engaging".

The table goes in the report. No stop for approval here: the founder judges the rendered contact sheet at the end, which is cheaper than judging descriptions.

---

## The surprise test

Before finalising the plan, apply to the batch as a whole:

> *"If someone who has seen 1,000 ads in this category scrolled through all of these, how many would make them pause?"*

If fewer than a third would, the batch is too safe. Push the most category-standard concepts harder: what would the opposite look like, what would a brand with twice the confidence do, what specific sensory detail would make the image feel real rather than generated. Surprise must serve the brand and the funnel stage, not contrarianism for its own sake.

---

## Diversity across the batch

- **No angle repeated** within a batch, and no angle and style pair the performance read retired.
- **Styles:** no style more than twice in a batch of six; at least one pure-type concept when it serves an angle.
- **Plates and photos:** when several concepts use a photographic background, vary camera height, light and distance between them, and avoid the category's cliché shot (translate the principle to the founder's category).

---

## Distribution of the pool

- **`all`:** split evenly across the three stages (for 6: 2 TOFU + 2 MOFU + 2 BOFU). Vary angles and visual approach within each stage.
- **One stage:** the whole pool on that stage, using all available angles for it before repeating any (and never repeating).
- **Two stages:** split the pool between them, no third stage. Adjust counts so the total equals `num_ads`.

A real asset (product, screenshot, or at minimum the logo) should appear in **most** concepts when the goal is performance; keep only 2-3 asset-free for pure typographic / storytelling pattern interrupts. Physical-product brands lean on the packshot; SaaS / app / service brands lean on the UI screenshot and the logo.

---

## Assets-driven concepts (SaaS, app, service, anything with no packshot)

When the founder sells software or a service, there is no bag or bottle to photograph, but there is almost always a **logo** and a **product UI** (the homepage screenshot or an app/dashboard image). Build concepts that put these on the creative instead of defaulting to text-only cards:

- **Product UI in frame.** The real UI screenshot shown whole on a brand surface, with the headline above. Media `screenshot`. Styles: `mini-landing-page`, `three-benefits-card`.
- **Feature callout.** The screenshot with 2-3 annotation arrows or labels pointing at key UI elements. Media `screenshot`. Style: `feature-callout-arrows`.
- **Before / after the tool.** Messy manual state vs. the clean dashboard. Media `screenshot`. Style: `before-after-asymmetric`.
- **Native social proof.** A real testimonial or comment, with its source. Styles: `testimonial-screenshot`, `reply-to-comment`, `social-proof-card`.
- **Logo-led typographic card.** When a concept is text-first (a bold statement, a myth-vs-fact), the logo stays as the small corner signature (the default of every layout) so the creative is unmistakably the founder's. This is the floor: **a SaaS creative should almost never ship with neither the UI nor the logo on it.**

Rule of thumb for a SaaS batch: at least half the concepts show the real UI screenshot, and nearly all carry the logo. Reserve "none" (no asset) for the 1-2 sharpest typographic pattern interrupts.

---

## Visual style assignment (two modes)

- **Lock mode** (`visual_style` slug set): every concept uses that layout. The named angle remains the strategic idea; the style is the container.
- **Auto-select mode** (`visual_style` empty): for each concept, pick the best-fit style from `skills/visual-styles/REGISTRY.md` using three criteria in order: (1) **funnel-stage fit** (the style's `funnel_fit` includes the concept's stage), (2) **angle fit** (it amplifies the angle), (3) **diversity** (see above). Every concept gets one of the 18 slugs: they are the layouts `build.py` renders.

---

## References

- Named angles, photographic vocabulary, headline tests, diversity mandate: `assets/ad-library.md`
- Visual styles: `skills/visual-styles/REGISTRY.md` and per-style files
- Business grounding: `project-context/context.json`; brand palette + harvested assets: `project-context/brand.json` (`assets.*`); live signals: optional `market-signal/market-signal-<YYYYMMDD>.json` sidecar
