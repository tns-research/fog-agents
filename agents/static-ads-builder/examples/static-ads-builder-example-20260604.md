# Example run: static-ads-builder (synthetic)

Anonymized, synthetic-but-realistic run for the fictional product **Acme Invoices** (the same brand used in the `project-context` example). Shows the brief pool, the two gates, and the run report that a real run writes into `<project-root>/acme/static-ads-builder/`.

Input given to the agent:

```
Project: acme   copy_language: fr   funnel_stages: all
```

`project-context/` already exists, so brand and business context are reused (no re-asking). The agent reports: *"Loaded brand.json + context.json from project-context."*

---

## 1. Brief pool (excerpt from static-ads-briefs-20260604.md)

The agent planned 12 briefs (4 TOFU / 4 MOFU / 4 BOFU), one named angle each, with the visual diversity mandate applied. Two excerpts:

```markdown
## Brief 2: Origin Number (TOFU)
```
```json
{
  "image_prompt": "Vertical 4:5, extreme close-up of a single paper invoice on a designer's desk, one line highlighted in CTA orange. Camera 45 degrees above, 3-4 front. 100mm macro equivalent, shallow depth. Soft diffuse window light from camera-left 45 degrees, slight rim from a desk lamp camera-right. Neutral clean digital grade, high contrast. No laptop in frame. No hands. Reserve upper third for headline.",
  "headline": "1 200 designers attendent moins pour etre payes.",
  "subheadline": "",
  "typography": {
    "font_style": "Instrument Serif, light, editorial",
    "color": "#ffffff sur #0b1020",
    "headline_placement": "Tiers superieur, gauche",
    "subheadline_placement": ""
  }
}
```
```markdown
Rationale: TOFU, Origin Number (1.4). Anchors the waitlist proof point from context.json (positioning.proof) without a hard CTA. Style: free visual direction. Camera/light pair unique in the pool.
```

```markdown
## Brief 6: Process Reveal (MOFU)
```
```json
{
  "image_prompt": "Use the attached product UI screenshot (Acme Invoices - app dashboard) as the exact screen content, do not invent or alter the interface. Vertical 4:5 mid-shot, the dashboard shown on a tablet held at a slight angle on a concrete desk. Use the attached logo exactly as provided, do not redraw or recolor it, top-left corner, small. Camera eye level, 3-4 front, 35mm equivalent. Soft overhead softbox, medium quality, gentle falloff. Cool-neutral clean grade. No hands gripping the tablet edge. Reserve right column for headline and subheadline.",
  "headline": "L'argent reste en main jusqu'a la livraison.",
  "subheadline": "L'escrow protege les deux cotes.",
  "typography": {
    "font_style": "Inter, medium weight",
    "color": "#ffffff sur #0b1020",
    "headline_placement": "Colonne droite, haut",
    "subheadline_placement": "Sous le headline"
  },
  "reference_assets": [
    {
      "role": "screenshot",
      "instruction": "Use the attached product UI screenshot (Acme Invoices - app dashboard) as the exact screen content on the tablet: do not invent or alter the interface. Tablet at slight angle on concrete desk. Keep right column free for text."
    },
    {
      "role": "logo",
      "instruction": "Use the attached logo exactly as provided, do not redraw, recolor, or restyle it. Top-left corner, small, with clear margin."
    }
  ]
}
```
```markdown
Rationale: MOFU, Process Reveal (1.9). Differentiator from offer.differentiators ("escrow"). Style: feature-callout-arrows (auto-selected, MOFU fit).
```

`scripts/validate_briefs.py static-ads-briefs-20260604.json` -> `12 brief(s) OK (0 warning(s))`.

Note: a "paie 2x plus vite" line the founder mentioned verbally was **dropped** from every headline, because `voice.claims_policy` requires a source and none was on file. The "1 200 designers" line stayed (it traces to `context.json` positioning.proof).

---

## 2. Gate 1, brief selection (blocking)

```
The pool has 12 briefs:
 1  TOFU   Anti-Category 1.1        product: no
 2  TOFU   Origin Number 1.4        product: no
 3  TOFU   Quiet Confession 1.8     product: no
 4  TOFU   Specific Ritual 1.2      product: yes
 5  MOFU   Skeptic Disarm 1.11      product: yes
 6  MOFU   Process Reveal 1.9       product: yes
 7  MOFU   Comparison 1.14          product: yes
 8  MOFU   Selection Proof 1.12     product: no
 9  BOFU   Easy First Step 1.15     product: yes
10  BOFU   Social Proof 1.16        product: yes
11  BOFU   Cost Reframe 1.17        product: yes
12  BOFU   Guarantee 1.18           product: yes

Which do you want to render? Default is 10; pick any subset from 5 to 15.
```

Founder: *"1, 2, 4, 5, 6, 7, 9, 10, 11"* -> 9 briefs selected.

---

## 3. Reference resolution (between the gates)

Selected briefs with `reference_assets`: 4, 5, 6, 7, 9, 10, 11. Briefs 4, 5, 6, 7, 9, 10 use the same app dashboard `screenshot` and the brand `logo`, so the agent resolved each shared asset **once** (`refs/screenshot-acme.png`, `refs/logo-acme.png` from `brand.json` assets) and reused the paths everywhere, writing the ordered `_ref_paths` list into each brief. Brief 11's only declared asset was a separate pricing-card image the scrape could not find, so **nothing** resolved for it -> flagged `SKIPPED_REF_MISSING`, excluded from the estimate. (A brief that resolves *some* of its roles renders with what resolved; only a brief that resolves none is skipped.) Renderable: 8 briefs.

---

## 4. Gate 2, model + resolution + budget (blocking)

```
python scripts/render_ads.py --estimate --count 8 --model fal-ai/nano-banana-2 --resolution 1K
-> 8 image(s) on fal-ai/nano-banana-2 at 1K = about $0.64 ($0.08/image)

Model:      Nano Banana 2 (default)  |  GPT Image 2  |  Nano Banana Pro (fallback)
Resolution: 1K (default, cheapest)   |  2K  |  4K (up to 2-3x of 1K)  <- main cost lever
Renderable: 8 briefs  (brief 11 skipped, reference missing)

Bottom line: 8 images on nano-banana-2 at 1K = about $0.64 ($0.08/image). Confirm model + resolution + spend?
```

Founder: *"nano banana 2, 1K, go."* -> confirmed.

---

## 5. Render

```bash
python scripts/render_ads.py --batch static-ads-briefs-20260604.json \
  --select "1,2,4,5,6,7,9,10" --out images/20260604 \
  --model fal-ai/nano-banana-2 --resolution 1K --refs-dir refs
```

One attempt per brief, no retry. Brief 7 returned an HTTP 500 from fal and was logged + skipped. Result: 7 rendered, 1 skipped reference (11, not in the render set), 1 failed (7).

---

## 6. Run report (static-ads-20260604.md, excerpt)

```markdown
**Run state:** PARTIAL_SUCCESS
**Brief pool:** 12 generated, 9 selected
**Model:** fal-ai/nano-banana-2   **Resolution:** 1K
**Spend:** estimated $0.64 (Gate 2) / actual $0.56

## Summary
PARTIAL_SUCCESS, 7 of 8 renderable briefs generated, brief 7 failed (fal HTTP 500),
brief 11 skipped for a missing reference. About $0.56 on nano-banana-2 at 1K.

## Not rendered
- Brief 3: Quiet Confession 1.8
- Brief 8: Selection Proof 1.12
- Brief 12: Guarantee 1.18
```

Downstream, the founder can render the leftover pool (3, 8, 12) later with another Gate-2 confirmation, no regeneration needed, the briefs JSON is reused as-is.
