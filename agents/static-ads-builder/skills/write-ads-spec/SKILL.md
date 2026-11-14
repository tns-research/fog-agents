---
name: write-ads-spec
description: Writes the batch as one ads.json, the only thing the model authors. Per ad - stage, named angle, one of the 18 styles, formats (1:1, 4:5, 9:16), surface, structured copy (headline, subhead, bullets, columns, comment, callouts, CTA), a sourced proof, claims for every number, real media with the words printed on them, the Meta ad text (primary text, headline, description, CTA, destination, ad set) and the winner it extends. Validated and linted by scripts/build.py (schema, numbers without source, dashes, style needs, copy gate). Use at Step 3 of static-ads-builder, after the concept plan. Triggers on "write the ads", "ads.json", "ad copy", "spec the batch".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# write-ads-spec

The spec is the deliverable's source of truth: every word on every render, every row of the import CSV and every name in next month's export come from it. The HTML is built from it and never edited.

Contract: [`../../assets/ads.schema.json`](../../assets/ads.schema.json). Example: [`../../examples/swanbase-mini-batch-20261012/ads.json`](../../examples/swanbase-mini-batch-20261012/ads.json). Path of the file: `<project>/static-ads-builder/<label>-YYYYMMDD/ads.json`, with the media it uses in `media/` next to it.

## Shape

```json
{
  "schema_version": "1.0",
  "meta": { "project": "acme", "brand": "../../project-context/brand.json", "language": "en", "date": "2026-10-12",
            "campaign": "spring-jam", "utm": { "source": "facebook", "medium": "paid_social", "campaign": "spring-jam" },
            "input": "../ads-performance-20261004.json" },
  "sources": [ { "id": "survey", "label": "Acme survey, 2026", "url": "https://example.com/survey", "accessed": "2026-10-12" } ],
  "ads": [ { "id": "fruit-first", "n": 1, "stage": "tofu", "angle": "anti-category", "style": "bold-statement",
             "formats": ["4:5", "9:16"], "surface": "brand",
             "copy": { "headline": "Jam should taste like *the fruit*.", "subhead": "...", "cta": "See how" },
             "proof": { "text": "...", "source": "survey" },
             "claims": [ { "text": "...", "source": "positioning.proof[0]" } ],
             "media": [ { "role": "product", "src": "media/jar.png", "visible_text": ["ACME", "FIG", "&", "VANILLA", "JAM"] } ],
             "meta_ad": { "primary_text": "...", "headline": "...", "description": "...", "cta": "LEARN_MORE",
                          "destination_url": "https://example.com/jam", "ad_set": "tofu-broad" },
             "extends": { "ad_name": "acme_01_tofu_anti-category_bold-statement_4x5", "why": "CPA 16.36 EUR on 11 purchases" } } ]
}
```

## Rules

**Copy.**
- Language = `copy_language`. French keeps every accent, capitals included. No `voice.banned_words`. `*word*` marks the one phrase the style sets in the accent colour; use it once per headline at most.
- One idea per headline. Write the copy for the style's slots: `bullets` for lists and timelines (with `label` for time steps or branches), `columns` for us-vs-them, myth-vs-fact, before-after and cost-reframe, `comment` for reply-to-comment, `callouts` for feature-callout-arrows. What a style needs is enforced by `build.py`.
- The CTA on the creative is short (one to four words). The Meta button type goes in `meta_ad.cta` (`LEARN_MORE` at TOFU, never `SHOP_NOW` there).
- Meta's feed guide recommends 50 to 150 characters of primary text and a 27-character headline ([`../../references/README.md`](../../references/README.md)); `package_meta.py` warns past them.

**Claims.** Every number in the copy or the Meta text must appear inside a `claims[]` text (or the `proof` text) whose `source` is a `sources[].id` with a URL, or `positioning.proof[N]` from `context.json`. `build.py` refuses any other number (`unsourced-number`). Reviews, ratings, quotes and comments are shown only when real: `proof.source` points at where they were published. A market-signal quote is language, never a testimonial (claims policy: [`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)). Urgency and end dates only when true: set `meta_ad.end_date` for anything dated.

**Media.** Real material first: the logo comes from `brand.json` automatically; a packshot (`product`, transparent PNG preferred), a UI capture (`screenshot`) or a founder photo (`photo`) goes in `media` with `src` relative to `ads.json`. Real media are shown whole (`fit: contain`). `visible_text` lists every word printed on the object, copied from the real thing (label, packaging, sign, shirt, UI): the proofread expects exactly those words on the render, so a distorted label cannot pass. Use `[]` when the media shows no word. A `plate` is a text-free photographic background made by an image model behind the spend gates: give it a `prompt` (scene only, English, no text, no logo, no product) and the path `plates/<NN>-<id>.jpg`.

**Formats.** List every format the concept should run in; the layout adapts per format (9:16 keeps text inside the Meta Reels safe band: 14 % top, 35 % bottom, 6 % sides). A dense style (mini-landing-page, us-vs-them) reads best in 4:5.

**Meta and tracking.** `meta_ad.ad_set` is a slug (`tofu-broad`, `bofu-site-visitors`): the package groups the exports by it and puts it in `utm_term`. The ad name is built by the scripts: `<project>_<NN>_<stage>_<angle>_<style>_<ratio>`. Keep `angle` to the slugs of [`../../assets/ad-library.md`](../../assets/ad-library.md) section 1 so performance aggregates across runs.

**Extends.** An ad that prolongs a winner of the performance read names it in `extends` with the metric, and changes the execution (style, format, hook), not the angle.

## Build until clean

```bash
python3 scripts/build.py <run>/ads.json
```

Exit 0 is required before rendering. Each error has a JSON path: fix the spec, rebuild. Warnings (a media without `visible_text`, a cropped real photo, a CTA type outside the common list, no `meta_ad`) are fixed or kept with a reason in the report.

## Failure modes

- **A number the angle needs has no source** → drop the number or the angle. Never an illustrative value.
- **No real media** → pure type styles (bold-statement, meme-static, myth-vs-fact, flowchart-decision) or a plate through the gates.
- **The founder supplies a photo with a third-party brand on it** → declare the words in `visible_text` and flag it in the report for the founder's decision before spend.
