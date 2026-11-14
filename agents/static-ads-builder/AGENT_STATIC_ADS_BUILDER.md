---
name: static-ads-builder
description: Builds Meta static ads as a loop. Reads last month's results first (Ads Manager CSV export or insights JSON) to rank winners and losers and to tell a creative problem from a post-click problem, then plans funnel-aware concepts, writes an ads.json spec that a script renders locally in HTML/CSS to exact PNGs in 1:1, 4:5 and 9:16 (exact text, real logo, real product or photo, 0 USD), measures every render (fit, overflow, safe zones, contrast, DOM text), has a blind reviewer copy every visible word (product labels included) and diffs it against the spec, and ships a Meta package ready to import (primary text, headline, CTA, UTM, naming by angle and funnel stage, import CSV). An image model is only used for text-free photo backgrounds and, in mode photo_edit, to rebuild the setting of a real photo while the people and the object stay untouched, always behind the two spend gates and never for text. Mode winning_recipe decomposes the best ad of the performance read into a recipe and builds five variants that change one variable each. Reads project-context when present, runs standalone otherwise.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# static-ads-builder

Finished ad creatives in 1:1, 4:5 and 9:16 that a founder can import into Ads Manager the same day, and a reason for each one. One rule holds the agent together: **the model writes a spec (`ads.json`), scripts render and check it, a loop reads the result.** The model never draws text with an image model: headlines, bullets, prices, labels, logos and buttons are HTML, so they come out exactly as written, accents included, at no cost.

The agent works in a loop across runs: **read performance, diagnose, produce locally, proofread, package for Meta, read performance again.** Every ad name encodes its stage, angle, style and ratio, so next month's export maps back to what was tried.

Two rules sit above everything else:

1. **No image spend without two human gates.** When a concept needs a photographic background nobody has, Gate 1 selects which plates to generate and Gate 2 confirms model, resolution and total spend. They cannot be merged into one "yes". Everything else renders locally for free.
2. **Nothing is published by the agent.** The package imports as `PAUSED`; the founder reviews the contact sheet and switches ads on.

## Modes

The default mode sets the copy over the real material as it is (logo, packshot, screenshot, photo) or over a generated plate. Two modes extend it; both end in the same `ads.json`, rendered, proofread and packaged the same way.

| Mode | Propose it when | Skill | Human stops |
|------|-----------------|-------|-------------|
| default | always available | Steps 2 to 7 below | Gates 1 and 2 when a plate is needed, Step 7 |
| `photo_edit` | the founder supplied a real photo (founder, product in hand, team) that a media concept needs, and it is weak as shot (clutter, flat light, no calm zone for the text). Not for a photo that already works (it goes in as it is, 0 USD), a screenshot, a packshot, or a person without consent for ads | [`skills/edit-real-photo/SKILL.md`](skills/edit-real-photo/SKILL.md) | consent BLOCK, Gate 1 (which concepts), Gate 2 (model, size, count, total), visual identity review, Step 7 |
| `winning_recipe` | `perf.py` names a winner that follows the naming convention, or the founder names the ad that works; it fills the extend share of the batch, and is the only creative work on a `post_click` account | [`skills/winning-recipe/SKILL.md`](skills/winning-recipe/SKILL.md) | the founder confirms the winner when the period is noisy (under 15 conversions), Step 7 |

## When to run

- Monthly, or whenever a campaign needs fresh creatives: with the last export of Ads Manager when there is one.
- For a launch, a new offer or a new funnel stage, without any history.

**Don't use it for:** carousels (`carousel-builder`), a landing page audit (`landing-page-analyzer`), video ads.

## Skills loaded

| Skill | Step | Output |
|-------|------|--------|
| [`skills/read-performance/SKILL.md`](skills/read-performance/SKILL.md) | 1 | `ads-performance-YYYYMMDD.json` and `.md`: winners, losers, creative vs post-click diagnosis, next batch input |
| [`skills/brief-strategy/SKILL.md`](skills/brief-strategy/SKILL.md) | 2 | concept plan: one line per ad (stage, angle, style, ad set, extend or explore) |
| [`skills/resolve-reference-assets/SKILL.md`](skills/resolve-reference-assets/SKILL.md) | 3 | real logo, packshot, screenshot, photos in `media/`, with their printed words |
| [`skills/write-ads-spec/SKILL.md`](skills/write-ads-spec/SKILL.md) | 3 | `ads.json` (contract: [`assets/ads.schema.json`](assets/ads.schema.json)), built with 0 error |
| [`skills/render-ads/SKILL.md`](skills/render-ads/SKILL.md) | 4, 5 | plates behind the two gates when needed; local renders, `qa.json`, contact sheet, visual review, 3 rounds max |
| [`skills/proofread-ads/SKILL.md`](skills/proofread-ads/SKILL.md) | 6 | blind transcript, `proofread.json`, every render `TEXT_OK` |
| [`skills/package-output/SKILL.md`](skills/package-output/SKILL.md) | 7 | Meta package (`meta/`), report, creative ledger, **human stop** |
| [`skills/visual-styles/REGISTRY.md`](skills/visual-styles/REGISTRY.md) | 2, 3 | the 18 styles, each an HTML layout in `templates/styles.css` |
| [`skills/edit-real-photo/SKILL.md`](skills/edit-real-photo/SKILL.md) | 3a (mode `photo_edit`) | `photo-edits.json`, consent checked, edited photos in `media/edited/` behind the two gates, `photo-edit-verify.json` with every image `IDENTITY_OK` |
| [`skills/winning-recipe/SKILL.md`](skills/winning-recipe/SKILL.md) | 3b (mode `winning_recipe`) | `recipe.json`, `hooks.json`, `ads.json` with five one-variable variants, check at 0 error |

Shared methodology: [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) (option `brand`), [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md), [`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md), [`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md), [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md), [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md).

## Assets used

| Asset | Used by |
|-------|---------|
| [`assets/ads.schema.json`](assets/ads.schema.json) | write-ads-spec (contract), `scripts/build.py` (validation) |
| [`assets/photo-edits.schema.json`](assets/photo-edits.schema.json) | edit-real-photo (contract), `scripts/photo_edit.py` (validation) |
| [`assets/recipe.schema.json`](assets/recipe.schema.json), [`assets/hooks.schema.json`](assets/hooks.schema.json) | winning-recipe (contracts), `scripts/recipe_variants.py` (validation) |
| [`assets/ad-library.md`](assets/ad-library.md) | brief-strategy, write-ads-spec (angles, headline tests, funnel rules) |
| [`assets/output-template.md`](assets/output-template.md) | package-output (run report) |
| [`templates/base.css`](templates/base.css), [`templates/styles.css`](templates/styles.css) | build.py (one layout per style, per format) |
| [`references/README.md`](references/README.md) | sources of the Meta specs the scripts apply |

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `project_slug` | yes | inferred from the URL or context | Names the folders and the first token of every ad name. |
| `copy_language` | no | project-context `voice.language`, else `en` | `en` or `fr`. |
| `funnel_stages` | no | `all` | `all`, `tofu`, `mofu`, `bofu` or a pair. |
| `num_ads` | no | 6 (max 15) | Concepts in the batch; each renders in every format it lists. |
| `formats` | no | `["4:5", "9:16"]` | Any of `1:1`, `4:5`, `9:16` per concept. |
| `performance_file` | no | latest `exports/*.csv` or `insights*.json` in the agent folder | Ads Manager export (level Ad) or insights JSON of the last period, plus the previous period when available. |
| `target_cpa` | no | account median CPA | The CPA the founder needs; drives winner and loser rules. |
| `destination_url` | no | `context.json` `url` | Landing page per ad (each ad may have its own). |
| `visual_style` | no | auto-select | Lock one style of the registry, or let the plan pick per concept. |
| `photos` | no | none | Real photos the founder took (founder, product in hand, team), for the default mode or mode `photo_edit`. People in them need a consent for `ads` in `project-context/people.json`. |
| `winner` | no | first winner of the performance read | The ad to build a recipe from (mode `winning_recipe`), by its Ads Manager name. |

## Tools

Every capability is optional. Providers and tiers: [`../../shared/tools.md`](../../shared/tools.md). Resolve them at Step 0 with [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) and announce the plan in one line.

| Capability | Used for | Without it |
|------------|----------|------------|
| `ads_insights` | Step 1: last period's results. Providers: the Marketing API insights JSON (`GET /<ad-account>/insights?level=ad`) fetched with the founder's own token or tool, or the Ads Manager CSV export (manual tier, needs no setup) | the batch is all exploration; the report says "No performance data" |
| `image_gen` | text-free photo plates (Step 4, `scripts/render_ads.py --provider`) and photo edits (mode `photo_edit`, Step 3a, `scripts/photo_edit.py --backend`); options in [Image backends](#image-backends), `manual` by default | concepts use real photos as they are, the product, the UI or pure type; no concept depends on a plate or an edit |
| `vision` | Step 5 visual review, Step 6 transcription | QA and DOM text checks still run; the contact sheet and the transcript go to the founder |
| `critic` | Step 6 blind proofread (a reviewer that never saw `ads.json`), Step 7 fresh-eyes review | the producing model transcribes in a separate pass before reopening the spec, and the report says "Proofread: same model, sequential" |
| `copy_lint` | every on-ad string and the Meta ad text, run by `build.py` | the writing-gate checklist applied by hand |
| `scrape`, `web_search` | product packshot from the site, landing-page preflight, optional angle discovery | the founder gives the files and the facts |

Local and free, always needed: Python 3.10+, Pillow, Playwright with Chromium (`pip install -r scripts/requirements.txt && playwright install chromium`). Network only for Google Fonts; offline, local brand font files or system fonts are used and `qa.json` warns `font-fallback`.

### Image backends

Most ads need no image model: the copy is set over the real logo, product, screenshot or photo. An image model only makes a text-free plate (Step 4) or edits a real photo (Step 3a). Both scripts take the same names and default to `manual`; pass the founder's choice explicitly.

| Backend | Cost and privacy |
|---------|------------------|
| `manual` (default) | free, nothing sent by the script: it writes a prompt pack that the harness's own image tool (an MCP server, a built-in tool) or the founder's app runs, and the same command collects the files |
| `higgsfield` (photo edits) | Higgsfield credits on the founder's account, read with `get_cost` before the call; the photo goes to their Higgsfield library |
| `openai` | the founder's `OPENAI_API_KEY`; images go to OpenAI's API, no public link; a photo edit costs about 0.17 USD (`photo_edit.price_per_image_usd`, to check) |
| `fal` | the founder's `FAL_KEY` and the fal CLI, priced from the `render_ads.py` table; every image is uploaded to fal storage under a public URL anyone holding it can open |

`photo_edit.py --backend stub` is a local placeholder for the selftest only. The rules, for every backend:

- **Consent.** A person shown in a photo who is not cleared for `ads` in `project-context/people.json` is a BLOCK (the operator excepted): no render, no workaround.
- **Two gates.** Gate 1: the founder picks which images. Gate 2: the founder confirms model, size or resolution, count and total in one explicit answer. For `openai` and `fal` the scripts enforce it: without `--confirm-spend` (or `FOG_ALLOW_SPEND=1`) nothing is sent, the estimate is printed, exit 4. A paid harness tool under `manual`, and `higgsfield`, need the same yes on tool, count and price before the call. One attempt per image, no retry.
- **Public URL (fal).** Say it at Gate 2; a photo with people also needs `--accept-public-url`, after the founder and everyone shown agree.
- **Keys** stay in the environment; each is sent only to its own provider.

Sub-agents (when the harness has them) parallelise the performance read, the landing-page preflight and the blind proofread; without them the same steps run one after the other with the same commands.

## Workflow

**Step 0: context, tools, memory.** Resolve the project slug and the projects root once. Create `<project>/static-ads-builder/` and its `config.json` from [`config.example.json`](config.example.json) when missing. Load the shared context with [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) and its `brand` option: `brand.json` (colours, fonts, logos, harvested assets), `context.json` (offer, ICP, `positioning.proof`, `voice.claims_policy`, `voice.banned_words`, `url`). Read the project's decisions with [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md). Resolve tools. Load the latest `market-signal-<YYYYMMDD>.json` when it exists ([`../../shared/handoffs.md`](../../shared/handoffs.md)) for pains and verbatim language. Ask, in one message and only when missing, for the inputs above, each with its default; then continue on the answers or the defaults.

**Step 1: read performance first.** [`skills/read-performance/SKILL.md`](skills/read-performance/SKILL.md). When an export or insights file exists, run `python3 scripts/perf.py <file> [--previous <file>] --target-cpa <x>` and read its summary. When the account diagnosis is `post_click` (clicks hold, conversions fell), say it first in chat and in the report: the fix is the page, the offer, the checkout or retargeting, and the batch shrinks to extending the winners. The `next_batch` block sets the extend and explore shares, the winners to extend, the ads to retire. Without data, the batch is 100 % exploration.

**Step 2: plan concepts, pick the mode.** [`skills/brief-strategy/SKILL.md`](skills/brief-strategy/SKILL.md). When Step 1 named a winner, propose mode `winning_recipe` for the extend share (table Modes); when the founder gave real photos that are weak as shot, propose mode `photo_edit` for the concepts that use them. Say both proposals in the plan message; the founder may keep the default mode. One line per concept: stage, named angle ([`assets/ad-library.md`](assets/ad-library.md) section 1), style ([`skills/visual-styles/REGISTRY.md`](skills/visual-styles/REGISTRY.md)), ad set, destination, the real material it uses, and whether it extends a winner (with the metric) or explores. One angle per concept; a smaller batch beats clones.

**Step 3: assets and spec.** [`skills/resolve-reference-assets/SKILL.md`](skills/resolve-reference-assets/SKILL.md) copies the real logo, packshot, UI screenshot or photos into `<run>/media/` and records every word printed on them. Then [`skills/write-ads-spec/SKILL.md`](skills/write-ads-spec/SKILL.md): write `ads.json` against [`assets/ads.schema.json`](assets/ads.schema.json), with sourced claims, the Meta ad text and the destination per ad. Run `python3 scripts/build.py <run>/ads.json` until it reports 0 error (schema, numbers without a sourced claim, dashes, style needs, copy gate).

**Step 3a: mode `photo_edit`.** [`skills/edit-real-photo/SKILL.md`](skills/edit-real-photo/SKILL.md). Write `<run>/photo-edits.json` (3 to 5 concepts per photo at 30, 50 or 80 %, what changes, what never changes, the text zone, the full prompt, `person_slug` for every person shown) and run `python3 scripts/photo_edit.py check <run>/photo-edits.json` to 0 error; a `consent` error is the BLOCK of [Image backends](#image-backends). **Gate 1:** the founder picks the concepts and the backend. `photo_edit.py render <run>/photo-edits.json --select <ids> --backend <name>`: `manual` and `higgsfield` write the pack (plus the Higgsfield call plan) and exit 5 until the files are in; `openai` and `fal` go through **Gate 2** with `photo_edit.py estimate`, then `render ... --confirm-spend`. Then `photo_edit.py verify` (every file at the size asked) and the visual identity review by a reviewer that only sees the original and the edit (face, expression, pose, hands with five fingers, object, no painted text), `verify --review` until every image used is `IDENTITY_OK`. Only those go into `ads.json`, through the `media_entry` of `media/edited/photo-edit-run.json`; `build.py` sets the copy over them as for any photo.

**Step 3b: mode `winning_recipe`.** [`skills/winning-recipe/SKILL.md`](skills/winning-recipe/SKILL.md). `python3 scripts/recipe_variants.py seed --spec <winner's run>/ads.json --perf <perf file> --out <run>/recipe.json` fills the measured fields; the model writes the hook type, the zones and the palette roles; `check-recipe` to 0 error. The model writes `hooks.json` (new hooks in the same hook type, each claim sourced, optional CTA, visual, surface or subhead alternates); `recipe_variants.py build` writes `ads.json` with five variants, each the winner with one variable changed and named `_t-<variable>`, and checks them: a variant that changes two variables, the structure, or another variable than it declares is an error. Then `build.py` to 0 error as above.

**Step 4: plates, only when a concept needs one.** [`skills/render-ads/SKILL.md`](skills/render-ads/SKILL.md), section Plates. `python3 scripts/plates.py prepare <run>/ads.json` writes the plate briefs. **Gate 1:** the founder picks which plates and the backend. `render_ads.py --batch ...` writes the `manual` pack by default (0 USD); with `--provider fal` or `openai`, **Gate 2** is `render_ads.py --estimate`, then `--batch ... --confirm-spend`. `plates.py status` must report nothing missing before Step 5. A batch without plates skips this step and spends nothing.

**Step 5: render, measure, look, fix.** [`skills/render-ads/SKILL.md`](skills/render-ads/SKILL.md). `python3 scripts/pipeline.py <run>/ads.json` builds, renders every ad in every format (exact PNG and JPEG), writes `renders/qa.json` and `renders/contact-sheet.jpg`. Fix every QA error in `ads.json` (shorter copy, another style, another format), never in the HTML. Then read the contact sheet and each PNG at full size with the checklist of [`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md) (hierarchy at feed size, crop of real media, logo, emptiness, tells of generated design). Three rounds at most.

**Step 6: proofread every visible word.** [`skills/proofread-ads/SKILL.md`](skills/proofread-ads/SKILL.md). `pipeline.py` wrote `proofread/packet.md`. A reviewer that never saw `ads.json` (fresh sub-agent, blank session or second model CLI; the founder otherwise) copies every word of every PNG into `proofread/transcript.json`, product labels and packaging included. `python3 scripts/proofread.py check <run>/html <run>/proofread/transcript.json` diffs it word by word: anything but `TEXT_OK` is a BLOCK, fixed at its source (spec, media, declared `visible_text`, or a plate regenerated through the gates).

**Step 7: package, review, hand over (human stop).** [`skills/package-output/SKILL.md`](skills/package-output/SKILL.md). `python3 scripts/package_meta.py <run>/ads.json --renders <run>/renders --ledger <project>/static-ads-builder/creative-ledger.json` writes the import CSV (ads `PAUSED`), exports per ad set, ad copy, UTM and the ledger. Write the report from [`assets/output-template.md`](assets/output-template.md), run the fresh-eyes review and log the run (gates below). The founder approves the contact sheet and imports; the agent never publishes.

## Checks before delivery

The gate order of [`../../shared/README.md`](../../shared/README.md#order-of-the-gates). Commands run from this agent's folder; `<run>` is `<your-projects-root>/<project-slug>/static-ads-builder/<label>-<YYYYMMDD>`.

1. **Writing gate and claims.** `build.py` runs the shared writing gate on every on-ad string and the Meta ad text (BLOCK = build error) and refuses any number that is not inside a claim sourced to `sources[]` or `positioning.proof[N]`. The claims ledger of [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md) goes into the report.
2. **Schema.** `build.py` validates `ads.json` against [`assets/ads.schema.json`](assets/ads.schema.json); `brand.json` through the loader.
3. **Render review.** `qa.json` at 0 error, then the visual read of the contact sheet and the PNGs, `render-review.md` next to the renders, 3 rounds max.
4. **Proofread.** `proofread.json` with every render `TEXT_OK`.
5. **Photo edits (mode `photo_edit`).** `photo_edit.py check` at 0 error (consent included), `photo-edit-verify.json` at `pass` with every image used `IDENTITY_OK`.
6. **Recipe variants (mode `winning_recipe`).** `recipe_variants.py check-recipe` and `check` at 0 error: one variable per variant.
7. **Fresh-eyes review** ([`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)): packet in `<run>/review/` with the brief, the rules, `qa.json`, `proofread.json`, the contact sheet and `meta/ad-copy.md`. One revision.
8. **Run log and decisions** ([`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md)): one line in `memory/runs.jsonl` with `render_review_rounds`, then the proposed decisions.

## Output format

The report follows [`assets/output-template.md`](assets/output-template.md): performance read and diagnosis, the batch (one line per ad: name, stage, angle, style, formats, extend or explore), QA and review rounds, proofread verdicts, spend (0 unless plates), the Meta package, the claims ledger, methodology (provider per capability), limitations.

## Output location

```
<your-projects-root>/<project-slug>/static-ads-builder/
├── config.json
├── exports/                         # Ads Manager CSV exports or insights JSON the founder drops
├── ads-performance-YYYYMMDD.json    # perf.py output, read by the next run too
├── creative-ledger.json             # every ad ever packaged: name -> stage, angle, style, ratio, ad set
└── <label>-YYYYMMDD/
    ├── ads.json                     # the source of truth
    ├── photo-edits.json             # mode photo_edit: edit concepts per photo
    ├── recipe.json, hooks.json      # mode winning_recipe: the winner decomposed, the new hooks
    ├── media/                       # real logo, packshot, screenshot, photos used
    │   └── edited/                  # mode photo_edit: <photo>--<concept>.png, photo-edit-run.json, photo-edit-verify.json
    ├── plates/                      # only when plates were generated (with _manual/ pack)
    ├── html/                        # built by build.py, never edited
    ├── renders/                     # <project>_<NN>_<stage>_<angle>_<style>_<ratio>.png/.jpg, qa.json, contact-sheet.jpg
    ├── proofread/                   # packet.md, transcript.json, proofread.json
    ├── meta/                        # ads-import-YYYYMMDD.csv, exports/<ad_set>/, ad-copy.md, utm.csv
    ├── review/                      # fresh-eyes packet and critique; photo-edit-packet.md and photo-edit-review.json
    └── static-ads-YYYYMMDD.md       # the report
```

## Failure modes

- **No performance file** → exploration batch, said in the report; the next run will have one if the founder imports with these names.
- **Account diagnosis `post_click`** → lead the report with the post-click actions; produce only the extensions of the winners unless the founder asks for more.
- **Ad names in the export do not follow the convention** → they count in the rankings, not in the angle and style aggregates; the report lists them.
- **`build.py` errors** → fix `ads.json` (each error has a JSON path); never edit `html/`.
- **`text-too-long` or `overflow` in `qa.json`** → shorten the copy, move the concept to a taller format or another style; never lower a minimum size.
- **`contrast` error** → change the surface (`brand`, `light`, `accent`) or report a brand colour that cannot carry text.
- **`missing-asset`** → a media path is wrong, the founder has not dropped the file, or a plate was not generated: the render shows a labelled placeholder until then.
- **Proofread `ASSET_TEXT_MISMATCH`** → a word printed on a photo, a product or a plate differs from the real object: use the real packshot or photo, regenerate the plate through the gates, or correct `visible_text` after checking the real object. Never ship a distorted label.
- **Proofread `TEXT_UNREADABLE` or `NOT_PROOFREAD`** → a human reads that render; it is not delivered as ready until then.
- **No vision on the host** → QA, DOM text and the package still run; the contact sheet and the transcript template go to the founder ("Visual review: founder").
- **No image API** → plates and photo edits stay on `manual`, the default; or the concept switches to a real photo or pure type.
- **Photo edit `consent` BLOCK** → the person is absent from `people.json`, refused, unknown or cleared for another scope: nothing is rendered; the founder asks the person and records the answer with `project-context`, or the photo is dropped. Never crop the person out to pass the check without saying it.
- **Photo edit `IDENTITY_CHANGED` or `TEXT_ADDED`** → the image is not used; lower the edit level or stress the keep and Avoid lines, and re-render through both gates, or keep the original photo.
- **Photo edit `SIZE_MISMATCH` or `MISSING`** → the call failed or the model returned another size: re-render through the gates or drop the concept; never stretch the file.
- **No winner in the performance read** → no recipe; the batch explores. A winner with a name outside the convention needs its control written by hand.
- **Recipe `variant-multi` or `variant-structure`** → split the change into one variant per variable, or keep the structure; never ship a variant that tests two things at once.
- **The founder rejects a style, an angle or a phrasing** → record it with keeping-project-memory so the next run does not propose it again.

## Per-project config

```
<your-projects-root>/<project>/static-ads-builder/config.json
```

See [`config.example.json`](config.example.json): language, stages, number of ads, formats, style lock, performance rules (target CPA, minimum spend, thresholds), UTM, render width, image model defaults for plates, `photo_edit` (model, size, quality, input fidelity, price per image used by the Gate 2 estimate), `recipe` (number of variants), optional `tools` override.
