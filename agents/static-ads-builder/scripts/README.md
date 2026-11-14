# scripts/

The static-ads engine. The model writes `ads.json` (contract: [`../assets/ads.schema.json`](../assets/ads.schema.json)), and in the two extra modes `photo-edits.json` ([`../assets/photo-edits.schema.json`](../assets/photo-edits.schema.json)) or `recipe.json` and `hooks.json` ([`../assets/recipe.schema.json`](../assets/recipe.schema.json), [`../assets/hooks.schema.json`](../assets/hooks.schema.json)); these scripts build, render, measure, proofread, package and read performance. Every script runs alone (`--help`), is deterministic (same inputs, same files) and calls no paid service. Only `render_ads.py` and `photo_edit.py --backend openai` or `--backend fal` can spend money, and only behind the two gates.

```bash
pip install -r scripts/requirements.txt
playwright install chromium
```

## Test (offline, 0 USD)

```bash
python3 scripts/selftest.py            # under a minute: example, proofread, stress, plates, perf, photo edit, winning recipe, 18 styles x 3 formats
python3 scripts/selftest.py --quick    # about 25 s: same without the 18-style render (CI runs this one)
```

It checks, in a temporary folder:

1. the swanbase example (3 ads x 3 formats) builds, renders, passes `qa.json`, its stored blind transcript is `TEXT_OK` on the 9 renders, the Meta package holds 9 import rows, 9 exports and 9 ledger lines, and every render carries the real logo lockup from `brand.json`;
2. a typo transcript (misspelt word, invented word, a misread label on a photo, an unreadable render, a render left out) blocks with the expected verdict on each file;
3. the stress spec raises every error it was built for (schema, dash, unsourced number, style needs, missing plate, text too long) and the expected warnings (its brand copy has no logo file, so `logo-text` too), without crashing;
4. `plates.py` and `render_ads.py` (with `--provider manual` and with no provider, the default) write the plate pack offline, and the missing plate is reported;
5. `perf.py` on the CSV fixtures gives the expected verdict and diagnosis per ad, the account diagnosis `post_click`, the aggregates by angle, and on the insights JSON never adds pixel and omni purchases;
6. photo edit: on a fictional photo the test draws itself (shapes, no real person), `photo_edit.py check` passes; the stub backend renders the three concepts at the size asked, twice to the same bytes, with a media entry valid against `ads.schema.json`; `verify` writes the review packet, passes clean answers, turns a wrong finger count, painted text and a missing answer into `IDENTITY_CHANGED`, `TEXT_ADDED` and `NOT_REVIEWED`, and catches a wrong size; consent blocks a refused person, a person cleared for another scope, an unknown slug, a missing slug and a group with one refusal, lets the operator through, and a blocked render writes nothing; the lint catches a single edit level, a prompt without "no text", a missing invariant and two concepts; the openai backend without `--confirm-spend` sends nothing and exits 4 with the estimate; with no `--backend` the manual pack is written and nothing is rendered;
7. winning recipe: `recipe_variants.py seed` reads the perf winner back from its spec and leaves the judgement fields empty (check-recipe fails), the fixture recipe passes, `build` writes 5 variants (one CTA, four hooks) whose names parse back with their `_t-<variable>`, `build.py` accepts them with 0 error, and `check` refuses two variables, a structure change and a wrong declared variable, `build` a hook with an unsourced number;
8. all 18 styles render in 1:1, 4:5 and 9:16 with 0 QA error, the logo lockup on every render, and no `dead-space-9x16` or `empty-band` on the 9:16 renders (skipped with `--quick`).

Exit 0 when everything holds. Fixtures: [`../tests/fixtures/`](../tests/fixtures/) (fictional brand Acme, fictional ad account).

## Scripts

| Script | Does | Writes |
|--------|------|--------|
| `pipeline.py` | One command: build, render, qa, proofread packet; `--transcript` diffs a transcript, `--package` writes the Meta package, `--width 1440` renders at Meta's recommended feed size. | everything below |
| `build.py` | `ads.json` + `brand.json` to HTML: schema, lint (numbers need a sourced claim, dashes, style needs, media, Meta fields), shared writing gate; colour roles per surface derived to hold contrast; media copied, shown whole; logo: mark + wordmark lockup of the `brand.json` variant whose ink holds on the real paper, one-colour SVG inlined in `currentColor`, measured size and clear space (name in text only when the brand has no logo file); 9:16 recomposed (media styles: the photo runs from the text zone into the bottom band on a stage panel; other styles: the footer panel runs to the bottom edge). | `html/index.html`, `html/expected.json`, `html/build-report.json`, `html/assets/` |
| `adspec.py` | Loader, stdlib JSON Schema subset validator, lint, ad names, visible text, word tokens and word diff (used by the others). | n/a |
| `fit.js` | In the page, after fonts and images: largest size per text between its min and max that holds its line budget without overflow; failures reported, never shrunk past the minimum; media resized to their own ratio; callout lines. | `window.__fit` |
| `render.py` | Chromium via Playwright: one exact PNG and JPEG (quality 90, 4:4:4, sRGB) per ad and format, and the DOM text of each. | `renders/<name>.png`, `.jpg`, `render.json` |
| `qa.py` | DOM measures: fit failures, overflow, canvas and safe zone (Meta Reels zones on 9:16), text size, WCAG contrast per text node, DOM words vs `ads.json`, missing or low-res media, dead space (9:16: in the text zone, and the reserved bottom band left bare), logo size, contrast and clear space, the tells of generated design; output sizes; contact sheet. | `renders/qa.json`, `renders/contact-sheet.jpg` |
| `proofread.py` | `packet`: blind brief for the reviewer and a transcript template. `check`: word diff of the transcript against copy + media `visible_text` + logo; verdict per render. | `proofread/packet.md`, `proofread/proofread.json` |
| `package_meta.py` | Import CSV (ads `PAUSED`), exports per ad set, ad copy with lengths, UTM links, creative ledger. | `meta/` |
| `perf.py` | Ads Manager CSV or insights JSON to winners, losers, inconclusive, insufficient data; creative vs post-click diagnosis; account diagnosis against a previous period; aggregates by angle, style, stage, ratio; next batch input. | `ads-performance-YYYYMMDD.json`, markdown summary |
| `plates.py` | `prepare`: text-free plate briefs from `ads.json` for `render_ads.py`, with the gate commands. `status`: plates present or missing. | `plates/plate-briefs-<ratio>.json` |
| `render_ads.py` | Capability `image_gen` for plates: `--estimate` (Gate 2, no key, no call), `--batch` with `--provider manual` (the default: pack for the founder's tool, 0 USD), `fal` or `openai`. A fal or openai batch needs `--confirm-spend` (or `FOG_ALLOW_SPEND=1`), passed only after the founder's yes at Gate 2. With fal, local reference images are uploaded to fal storage under a public URL. One attempt per plate, no retry. | `plates/NN-<id>.jpg`, `plates/_manual/` |
| `photo_edit.py` | Mode `photo_edit`. `check`: schema, lint (invariants in never_changes and in the prompt's keep line, labelled prompt fields, "no text", two edit levels, photo present), consent of every person for `ads` through `shared/scripts/registry.py` (local reader of `people.json` as fallback). `estimate`: Gate 2 figures. `render --backend manual` (the CLI default: prompt pack in `_manual/`, nothing sent, exits 5 until the files are dropped, then collects them), `higgsfield` (the manual pack plus `_manual/higgsfield-plan.json`, the MCP calls the agent makes), `fal` (photo uploaded under a public URL, `FAL_KEY` and the `fal` CLI, a photo with people also needs `--accept-public-url`) or `openai` (`POST /v1/images/edits`, `OPENAI_API_KEY`), or `stub` for tests only (local Pillow placeholder, 0 USD); `fal` and `openai` are refused without `--confirm-spend` or `FOG_ALLOW_SPEND=1`, one attempt. `verify`: size of every result, review packet, reviewer verdicts with `--review`. | `media/edited/<photo>--<concept>.png`, `photo-edit-run.json`, `photo-edit-verify.json`, `review/photo-edit-packet.md` |
| `recipe_variants.py` | Mode `winning_recipe`. `seed`: recipe from the perf winner and its spec, measured fields filled. `check-recipe`: schema and recipe against the control. `build`: recipe + hooks to `ads.json` variants, one variable each, named `_t-<variable>`. `check`: one variable per variant, structure kept, plus the ads.json schema and lint. | `recipe.json`, `ads.json` |
| `selftest.py` | The offline regression test above. | a temporary folder |

## Reference runs

```bash
# The swanbase example, end to end, with its blind transcript and the Meta package
python3 scripts/pipeline.py examples/swanbase-mini-batch-20261012/ads.json --out /tmp/swanbase-ads \
  --transcript examples/swanbase-mini-batch-20261012/transcript.json --package

# Every style in every format
python3 scripts/pipeline.py tests/fixtures/all-styles/ads.json --out /tmp/all-styles

# Performance loop on the fixture export, with the previous period
python3 scripts/perf.py tests/fixtures/perf/meta-export-20261004.csv \
  --previous tests/fixtures/perf/meta-export-20260920.csv --target-cpa 20 --out /tmp/perf.json
```

## Exit codes

`build.py`: 0 clean spec, 1 spec errors (HTML still written), 2 unreadable spec. `render.py`: 0, 1 a section failed, 2 no HTML. `qa.py`, `pipeline.py`: 0 pass, 1 errors (pipeline: 2 unreadable spec). `proofread.py check`: 0 all `TEXT_OK`, 1 any BLOCK, 3 bad input. `package_meta.py`: 0 written, 1 an ad without render or `meta_ad`, 3 bad input. `perf.py`: 0, 3 unreadable input. `plates.py status`: 0, 1 a plate missing. `photo_edit.py`: 0, 1 spec errors, consent BLOCK or verify BLOCK, 2 provider key or `fal` CLI missing (nothing sent), 3 bad input, 4 spend gate or public-URL gate closed (nothing sent, estimate printed), 5 manual or higgsfield pack written, files still to drop. `recipe_variants.py`: 0, 1 errors (build: `ads.json` still written), 3 bad input. `render_ads.py`: 0, 2 key missing (nothing sent), 3 bad input or `fal` CLI missing, 4 spend gate closed (no `--confirm-spend`, nothing sent, estimate printed).
