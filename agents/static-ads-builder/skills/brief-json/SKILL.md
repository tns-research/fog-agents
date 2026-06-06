---
name: brief-json
description: Structure each planned ad concept as a valid image-generation JSON payload. Only the fields the renderer needs, image_prompt, headline, subheadline, typography, and reference_assets (an ordered list of the founder's real assets - product, screenshot, logo, hero - on the creative). Enforces the 7-element image-prompt formula, logo fidelity, the French/English copy rules, voice.banned_words and voice.claims_policy. Use after brief-strategy, before rendering. Triggers: "write the briefs", "creative JSON", "ad prompts".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# Skill: brief-json

Turn each concept from `brief-strategy` into one JSON payload that is the **exact input the renderer sends to fal**. The JSON holds only what the image generator uses; everything human (concept name, rationale) lives in the surrounding markdown.

Inherit from `project-context/context.json` (via `resolve-project-context`): the product name, the brand palette, `voice.banned_words` (hard blacklist), and `voice.claims_policy` (default: "no invented stats, every metric must trace to a URL or be omitted"). A claim with no traceable source is dropped, not invented.

Also inherit the **harvested visual assets** from `project-context/brand.json` (`assets.logo_path`, `assets.screenshot_path`, `assets.og_image_path`, `assets.images[]`). These are the founder's real material: their logo, a screenshot of their product/UI, the hero/share image, and the largest on-page images. A brief that wants any of them on the creative declares it in `reference_assets` (below); `resolve-reference-assets` turns each declared role into a local file the renderer attaches. This is the path that lets a SaaS or service with no physical packshot still ship creatives built from its real logo and product interface, not generic stand-ins.

---

## When to load

- Workflow Step 4 of `static-ads-builder`, once the per-brief strategy plan exists.

---

## JSON schema (renderer payload only)

When no real asset (product, logo, screenshot, hero) appears on the creative, omit `reference_assets` entirely, the brief is pure text-to-image.

```json
{
  "image_prompt": "string",
  "headline": "string",
  "subheadline": "string",
  "typography": {
    "font_style": "string",
    "color": "string",
    "headline_placement": "string",
    "subheadline_placement": "string"
  }
}
```

When one or more of the founder's real assets **is** on the creative, add `reference_assets`, an ordered list of the assets to attach to the generation:

```json
  "reference_assets": [
    { "role": "screenshot", "instruction": "string" },
    { "role": "logo", "instruction": "string" }
  ]
```

### Asset roles

| `role` | What it is | Resolved from | Typical use |
|--------|-----------|---------------|-------------|
| `product` | A physical product packshot | `assets.images[]` or a firecrawl scrape | E-commerce hero / in-context shot |
| `screenshot` | The product UI / app / dashboard | `assets.screenshot_path` (homepage screenshot) or a UI image in `assets.images[]` | The "product" for a SaaS / app / service: shown in a device or browser mockup, or as a feature callout |
| `logo` | The brand logo | `assets.logo_path` | Brand signature in a corner, a centered lockup, or a watermark. The default way to brand a creative when there is no packshot |
| `hero` | The og:image / brand hero image | `assets.og_image_path` | Atmospheric backdrop or a recognizable brand visual |

A single brief may attach several roles (e.g. `screenshot` + `logo` for a UI ad with the brand mark in the corner). Order matters only as a readability hint; the renderer attaches them all.

### Field rules

| Field | Type | Required | Rules |
|-------|------|----------|--------|
| `image_prompt` | string | Yes | **English only.** 7-element formula (below). Rich and specific, never a one-liner. When assets are attached, the prompt names each one and its placement, e.g. "Use the attached product UI screenshot (Brand) as the screen content inside a floating browser mockup, centered. Use the attached logo exactly as provided, do not redraw it, top-left, small. Reserve the lower third for headline and subheadline." No conditional language. When no asset is attached, describe only the scene. |
| `headline` | string | Yes | On-creative main line, language = `copy_language`. One clear, complete idea. French: correct and idiomatic, **with every accent and diacritic kept intact** (é è ê ë à â ä î ï ô ö ù û ü ç, uppercase too: É È À Ç). Never strip accents to plain ASCII, the copy renders on the creative exactly as written. Passes the 5 quality tests in `assets/ad-library.md` Section 8. No `voice.banned_words`. |
| `subheadline` | string | Yes | Secondary line. `""` when the creative has one line. Same language; a second idea, not a repeat of the headline. |
| `typography` | object | Yes | See typography rules below. |
| `reference_assets` | array | Only when a real asset is on the creative | Ordered list of `{ "role", "instruction" }`. `role` is one of `product` / `screenshot` / `logo` / `hero`. `instruction` states exactly what the asset is, where it goes, and (for logo/product) "use it exactly as provided, do not redraw it". No conditionals. Omit the whole key when no asset is shown (never `"N/A"`, never an empty array). |

---

## Image prompt - the 7-element formula

Every `image_prompt` includes all 7 elements, in order:

```
[1. Format + crop] [2. Subject + action] [3. Camera position] [4. Focal length equivalent] [5. Lighting (source + direction + quality)] [6. Color grade] [7. Exclusions]. [Product instruction if applicable.] [Reserve area for text.]
```

**Physics-first principle.** Do not prompt for objects, prompt for physics. "Soft light, warm tones" is an adjective. "Soft diffuse window light from camera-left 45 degrees" is a physical description that accesses the generator's training on professional photography.

**Element definitions**

1. **Format + crop:** aspect ratio + how the subject fills the frame ("Vertical 4:5, close-up" / "Square 1:1, wide overhead").
2. **Subject + action:** be specific. Not "a coffee bag" but "a single kraft paper coffee bag standing upright, label facing camera".
3. **Camera position:** height (low angle / eye level / elevated 30-45 / true overhead / Dutch tilt) + angle (frontal / 3-4 front / profile / 45 front-above).
4. **Focal length equivalent:** one of 16mm / 24mm / 35mm / 50mm / 85mm / 100mm macro / 200mm telephoto.
5. **Lighting:** source + direction + quality, all three. Never only "soft light".
6. **Color grade:** "Warm matte grade, lifted blacks, slight film grain" / "Neutral clean digital, high contrast" / "Cool desaturated, clinical".
7. **Exclusions:** at least one thing explicitly NOT in frame ("No steam." / "No human hands." / "No marble surface.").

**Failure modes to avoid (look AI-generated):** over-perfect skin/surfaces (add "natural skin texture", "visible material grain"); centered symmetric composition (specify asymmetry, rule of thirds); "warm light" with no source; stock-photo poses (describe the moment, not the pose); 5+ style refs (max 2); no exclusion clause; open mouths / complex hands (use profile, looking-away, closed-mouth); "photorealistic, ultra-detailed" (replace with lens + light + film stock specifics).

---

## Image prompt rules

1. **No conditionals.** Never "if reference available", "can be generic or branded", "optional". Either the creative shows a real asset and you reference the attached image(s), or it describes only the scene.
2. **Asset in scene:** `image_prompt` and each `reference_assets[].instruction` name the attached image and what it is. For `product`, the exact product name (e.g. "Loutsa - Abonnement Colombie Bio 500g"). For `screenshot`, "the attached product UI screenshot (Brand)". For `logo`, "the attached logo, used exactly as provided, do not redraw or restyle it". Always define placement and the reserved text area.
3. **No asset in scene:** omit `reference_assets`; describe only what is visible (a typographic card, an illustrated scene, etc.).
4. **Logo fidelity:** generative models distort logos if asked to "draw" one. When a `logo` asset is attached, the prompt must say "reproduce the attached logo exactly, do not redraw, do not change its colors or proportions" and give it a small, clean zone (a corner or a centered lockup on flat background). Never ask the model to invent a logo.
5. **No two briefs share the same camera position + lighting setup** (visual diversity mandate, `assets/ad-library.md` Section 9).

---

## Headline and subheadline rules

- **Headline:** one clear, complete idea. A native speaker understands it in one read. No telegraphic fragments, no dot-separated noun lists ("Bio. Artisanal. Bon." is forbidden, it is a spec sheet, not an idea).
- **Subheadline:** same rules. `""` when only one line. Adds a second layer, never repeats the headline.
- **French (`copy_language: fr`) process, mandatory:** think the headline natively in French as a complete sentence with subject, verb, and point of view. Read it aloud; if it sounds like a translated English tagline or a fragment list, rewrite from scratch. Only then write the English image prompt to match. The French copy drives the creative, not the other way around. See `assets/ad-library.md` Section 4.
- **Accents are mandatory in French.** Every French string in the brief (`headline`, `subheadline`, and any French value in `typography`) keeps its full diacritics: write "torréfié", "différence", "protège", "goûtés", "pilotés", "déjà", "français", not "torrefie", "difference", "protege", "goutes", "pilotes", "deja", "francais". The JSON is UTF-8 and these characters are valid and expected; a stripped accent ships straight onto the creative as a typo. Capitals keep their accents too (É, À, Ç). The complete French character set lives in `assets/ad-library.md` Section 4. Only `copy_language: en` copy is accent-free by nature.
- **Length:** French headline 6-15 words (the idea dictates length; a 12-word sentence that means something beats a 4-word fragment that means nothing). English headline 4-10 words. Subheadline: same ballpark or `""`.
- **Quality gates:** every headline passes all 5 tests in `assets/ad-library.md` Section 8 (Competitor, 5-Word, Surprising Word, Emotion, Native Speaker).
- **Voice:** no `voice.banned_words`. No claim violating `voice.claims_policy`, drop unverifiable metrics rather than invent them.

---

## Typography field rules

| Subfield | What to specify |
|----------|----------------|
| `font_style` | Weight + style + distinctive trait. "Sans-serif, medium weight, wide tracking" / "Serif italic, light, editorial". Default to the brand fonts from `brand.json` when present. |
| `color` | Hex for text + hex/description for background. "#F5EDE4 text on #2C1810 background". Default to `brand.json` tokens when present. |
| `headline_placement` | Specific zone: "Upper third, left-aligned" / "Lower third, centered". |
| `subheadline_placement` | Same specificity, or `""` when the subheadline is empty. |

Do not repeat identical typography across all briefs. Font may stay consistent if the brand mandates it, but placement and weight vary to serve each composition.

---

## Examples

### Example A - product-free, low angle, hard light, typography-hero

```json
{
  "image_prompt": "Vertical 4:5, mid-shot showing only the lower half of a copper industrial coffee roaster drum, warm dark background. Camera at low angle, 45 degrees below eye level, 3-4 front. 50mm equivalent, medium depth of field. Hard side light from camera-right, single bare source at 45 degrees, strong cast shadow across the drum and floor. Warm high-contrast grade, deep blacks, copper highlights. No human hands. No coffee cup. No text on roaster. Reserve lower quarter for headline and subheadline overlay. (Style ref: industrial craft editorial)",
  "headline": "On torréfie ici. Vous sentez la différence.",
  "subheadline": "",
  "typography": {
    "font_style": "Sans-serif, light weight, wide tracking",
    "color": "#F5EDE4 sur fond sombre",
    "headline_placement": "Tiers inférieur, centré sur zone sombre",
    "subheadline_placement": ""
  }
}
```

### Example B - product hero, elevated overhead, studio soft

```json
{
  "image_prompt": "Vertical 4:5, close-up flat lay. Use the attached product reference image (Loutsa - Abonnement Colombie Bio 500g) as the single source for the coffee bag: exact shape, label, logo, brand colors. Place the bag upright at slight angle, lower-center frame, on a matte dark-grey surface. Small handful of unroasted green beans to the left, out of focus. Camera directly overhead, 100mm macro equivalent. Studio softbox overhead, centered, soft diffuse, no shadows. Neutral-cool grade, clean digital, no grain. No ceramic cup. No steam. No scattered roasted beans. Reserve upper third for headline and subheadline.",
  "headline": "200 lots goûtés. 12 retenus.",
  "subheadline": "Le vôtre en fait partie.",
  "typography": {
    "font_style": "Serif, light weight, tight tracking",
    "color": "#F5EDE4 sur #1A1A1A",
    "headline_placement": "Tiers supérieur, left-aligned",
    "subheadline_placement": "Sous le headline, même alignement"
  },
  "reference_assets": [
    {
      "role": "product",
      "instruction": "Use the attached product reference image (Loutsa - Abonnement Colombie Bio 500g) as the single source for the coffee bag: exact shape, label, logo, brand colors. Place upright at slight angle, lower-center of frame. Keep upper third completely free for headline and subheadline."
    }
  ]
}
```

### Example C - SaaS, no physical product: UI screenshot in a device + logo lockup

```json
{
  "image_prompt": "Vertical 4:5, clean studio composition on a soft #f5f6f8 background. Use the attached product UI screenshot (Acme Reviews) as the exact screen content inside a single floating laptop mockup, centered, tilted 8 degrees, soft drop shadow beneath. Use the attached logo exactly as provided, do not redraw or recolor it, placed top-left, small. Camera eye level, frontal, 50mm equivalent, medium depth of field. Soft even studio light from above, gentle gradient, no harsh shadows. Neutral clean digital grade, high contrast on the screen. No human hands. No extra UI windows. No invented interface, the screen shows only the attached screenshot. Reserve the lower third for headline and subheadline.",
  "headline": "Vos avis Google, pilotés en un seul endroit.",
  "subheadline": "Acme Reviews centralise, répond, et fait grimper la note.",
  "typography": {
    "font_style": "Sans-serif, semibold, tight tracking",
    "color": "#09090b text on #f5f6f8 background, accent #f97316",
    "headline_placement": "Tiers inférieur, centré",
    "subheadline_placement": "Sous le headline, centré"
  },
  "reference_assets": [
    {
      "role": "screenshot",
      "instruction": "Use the attached product UI screenshot (Acme Reviews) as the exact screen content inside the laptop mockup. Do not invent or alter the interface; show it as captured. Centered, tilted 8 degrees."
    },
    {
      "role": "logo",
      "instruction": "Use the attached logo exactly as provided, do not redraw, recolor, or restyle it. Place it top-left, small, with clear margin."
    }
  ]
}
```

---

## Output format in markdown

1. **Heading:** `## Brief N: [Concept name] (TOFU | MOFU | BOFU)` - concept name for humans only, not in the JSON.
2. **One fenced ` ```json ` block** with the payload. No title, no brief_id, no rationale inside the JSON.
3. **After the block: Rationale:** in markdown (funnel role, named angle, assigned visual style slug or "free", which assets it uses and why, why it works).
4. When no real asset is shown, the JSON has no `reference_assets` key.
5. Valid JSON: no trailing commas, no comments, correct escaping.

Also write a machine-readable sidecar `static-ads-briefs-YYYYMMDD.json`: a single array of the payload objects, in brief order, each augmented with two non-rendered keys the pipeline needs downstream: `"_brief_n"` (integer) and `"_concept"` (string). The renderer ignores keys prefixed `_`.

---

## Validation checklist

- [ ] JSON has only `image_prompt`, `headline`, `subheadline`, `typography`, and optionally `reference_assets`. No `title`/`brief_id`/`rationale` inside the JSON.
- [ ] Image prompt uses all 7 formula elements. English only. Rich, not a one-liner.
- [ ] No two briefs share the same camera position + lighting setup.
- [ ] Asset shown: `image_prompt` and each `reference_assets[].instruction` name the attached image, its role, and its placement. Logo/product say "use exactly as provided, do not redraw". No conditionals.
- [ ] No asset shown: no `reference_assets` key (never an empty array).
- [ ] Headline passes all 5 quality tests; no `voice.banned_words`; no claim breaking `voice.claims_policy`.
- [ ] Headline and subheadline are clear, complete ideas in `copy_language`. Subheadline `""` when one line.
- [ ] French copy keeps all accents/diacritics (é è ê à â î ô û ç, capitals included). No accent-stripped ASCII French.
- [ ] Typography placement varies across briefs.
- [ ] Both files written: `static-ads-briefs-YYYYMMDD.md` and `.json`. The `.json` validates with `scripts/validate_briefs.py`.

---

## References

- Output template: `assets/output-template.md`
- Ad library (angles, photographic vocabulary, headline tests, what's dying): `assets/ad-library.md`
- Visual styles: `skills/visual-styles/`
