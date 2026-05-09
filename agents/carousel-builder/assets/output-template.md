# Carousel: <angle title>

**Project:** <project-slug>
**Date:** <YYYY-MM-DD>
**Platforms:** <linkedin, instagram>
**Ratio:** <1:1 | 4:5>
**Slides:** <N>
**Language:** <en | fr>
**Tone:** <founder | expert | casual>

---

## 1. Angle chosen

**Title:** <angle title>
**Hook:** <≤12-word scroll-stop>
**Audience:** <who>
**Position / Lens / Pull:** <position> · <lens> · <emotional pull>
**Why this angle:** <one line on the rationale>

Other angles considered:
1. <angle 2 title> — <one line>
2. <angle 3 title> — <one line>
3. <angle 4 title> — <one line>

---

## 2. Slide manifest

| # | Type | Title | Body (excerpt) | Visual |
|---|------|-------|----------------|--------|
| 1 | cover | <hook> | <subline> | <visual> |
| 2 | text | <title> | <≤30 words excerpt> | <visual> |
| ... |
| N | cta | <action> | <CTA body> | <visual> |

Full slide-by-slide copy: see `slide-plan-<YYYYMMDD>.md` (markdown) and `slide-plan-<YYYYMMDD>.json` (structured).

---

## 3. Brand snapshot

| Property | Value |
|----------|-------|
| Source | <default | extracted from <brand_url>> |
| Primary color | <#hex> |
| Secondary color | <#hex> |
| Accent color | <#hex> |
| Background | <#hex> |
| Text color | <#hex> |
| Font family | <name> |
| Logo | <path or "none"> |

Brand cache: `<your-projects-root>/<project>/carousel-builder/brand.json`. Edit and re-run to apply changes.

---

## 4. Output files

| Format | Path |
|--------|------|
| PDF | `<label>-<YYYYMMDD>/pdf/carousel-<YYYYMMDD>.pdf` |
| PNG sequence | `<label>-<YYYYMMDD>/png/slide-01.png` ... `slide-<NN>.png` |
| HTML bundle | `<label>-<YYYYMMDD>/html/index.html` + per-slide HTMLs |

---

## 5. Posting guidance

### LinkedIn (document post)
- Upload the **PDF** as a document post.
- Caption: 150-300 chars, hook in first line, no link in caption (drop links in first comment).
- Best ratio: 4:5. 1:1 also works.
- Optimal slide count: 8-12.
- Hashtags: 3-5 relevant, end of caption.

### Instagram (multi-image carousel)
- Upload the **PNG sequence** (max 20 images).
- Caption: 125 chars before "more", hook + value teaser.
- Best ratio: 4:5 (1080x1350).
- Optimal slide count: 7-10.
- Hashtags: 5-15 relevant, mix of broad + niche.

### Hashtag policy
The agent does NOT generate hashtags by default. They date the post and can hurt reach if generic. If the user asks, propose 3-5 niche hashtags from the topic vocabulary, not from a generic list.

---

## 6. Run notes

- <any flags from the run, e.g. "fal_images requested but FAL_API_KEY missing, fell back to SVG">
- <"slide 5 split into 5a + 5b due to body length">
- <"brand extraction returned white as primary; user overrode to navy">
