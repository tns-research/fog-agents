# scripts/

Bundled tools for the agent. Use this folder only when the work cannot be done by piping existing CLIs. Every API these scripts can call is optional: providers and fallbacks per capability are in [`../../../shared/tools.md`](../../../shared/tools.md).

Legitimate uses:

- Browser automation (Playwright capture, screenshot stitching)
- CSV / JSON transformations (reshape, dedupe, join)
- Custom scoring formulas applied at scale
- API quota juggling, batched fetch with retry

Not for: things a scrape or search provider already does.

## Conventions

- **Python preferred** (matches the broader ecosystem we lift patterns from).
- Forward slashes only. No Windows-specific path handling.
- No magic numbers. Every constant documented inline.
- Handle errors explicitly (return defaults or specific error messages, never silently `pass`).
- Each script ships with `requirements.txt` (or equivalent) and an entry in this README.

## Script inventory

Install once: `pip install -r requirements.txt && python -m playwright install chromium`.

### `extract_brand.py`

- Inputs: `--url <homepage>` `--out <project-context dir>` `[--max-images N]` (default 6, hero capture included) `[--font-files google|all|none]` (default `google`) `[--no-logo-pipeline]` (debug only); after the founder approved: `--out <project-context dir> --finalize`
- Keys and network: no API key, no paid call. One local Chromium pass (Playwright) plus direct downloads of the page's own assets, stylesheets and fonts. Only `http` and `https` URLs are fetched, redirects included; a host that resolves to a private, loopback or link-local address is refused unless the analyzed site itself sits on one (a local dev server). Respects robots.txt.
- Outputs: `brand-candidate.json` (every token with its confidence and source, the evidence, the `assets` manifest, `warnings`) + `brand-draft.json` (the `brand.json` V2 contract of [`../../../shared/schemas/brand.schema.json`](../../../shared/schemas/brand.schema.json), paths relative to the project-context folder, validated with `shared/scripts/validate_json.py`) + `brand-debug/` (homepage.png, header-crop.png, viewport.png, hero.png, `logo/` from the logo pipeline) + `assets/logos/` (`source.*`, the harvested file, and `{wordmark,mark}-on-{light,dark}.{svg,png}`) + `assets/fonts/` (Google Fonts files by default) + `assets/site/` (favicon, og-image, screenshot.png, hero.jpg, asset-NN.*, manifest.json). `--finalize` validates the approved draft again and writes `brand.json`.
- What: hides cookie and consent banners (their buttons never count as brand colors), scrolls so lazy images load, then measures color roles on the render: `bg` from the screenshot, text roles from the text on the page background checked against the glyph pixels, `surface` and `border` from the cards, `accent` from the primary CTA (solid background, else the most vivid gradient stop, checked against the button pixels), `on_accent` from its label, radius and shadow from the cards. Fonts are the faces `document.fonts` actually loaded (a family declared but never loaded is reported). Harvests the logo (scored: link to the home page, "logo" or the brand name in its label, never inside a button; inline SVG serialized to a file), og:image, favicon, a hero capture and page images (12 MB cap each), drops decorative images (glows, gradients, grain, flat fills) by pixel statistics and records each kept file with license `founder-site` (stock hosts flagged). Then runs `logo_pipeline.py` on the logo.
- Exit codes: `0` ok, `2` robots disallow, `3` Playwright missing or the page never loaded (the message gives the install command; the agent can ask for colors and logo in chat instead), `4` `--finalize` without a `brand-draft.json`, `5` the V2 draft does not match the schema (extraction: the draft stays for diagnosis; `--finalize`: `brand.json` left unchanged). Schema validation is skipped with a note when `shared/` is not next to `agents/`.

### `logo_pipeline.py`

- Inputs: `--logo <svg|png|webp|jpeg>` `--out <project-context dir>` and either `--brand <brand-draft.json|brand.json>` or `--bg <#rrggbb> --text <#rrggbb>`; `[--update]` (write the result into the `--brand` file) `[--json]`
- Outputs: `assets/logos/{wordmark,mark}-on-{light,dark}.{svg,png}` and `brand-debug/logo/` (test composites, `audit.json`). With `--brand --update`: rewrites `logos`, `logo_audit` and `extensions.extract_brand.logo_png` in that brand file.
- What: SVG viewBox audit against the rendered ink (ink cut off by the declared viewBox is found by rendering it widened; the measured ink box replaces the viewBox), mark and wordmark split, an `on_light` and an `on_dark` variant (recolored or knocked out to one brand ink), a pixel test of each variant on its background (pass when 90 % of the ink reads at 3:1 or more, warn from 60 %, fail below), PNG fallbacks at 1024 px. `extract_brand.py` calls it; run it alone when the founder gives a new logo.
- Exit codes: `0` audit pass, `1` audit warn or fail (files written; read `logo_audit.issues`), `2` usage error or unreadable file, `3` Playwright missing (needed for SVG logos; raster logos work without it).

### `render_brand_preview.py`

- Inputs: `--brand <brand-draft.json|brand.json>` (V2; V1 and `brand-candidate.json` files are mapped on load) `[--out <jpg>]` (default `<brand dir>/brand-debug/brand-board.jpg`) `[--max-kb N]` (default 150) `[--engine auto|playwright|pillow]`
- Outputs: `brand-board.html` (the filled [`../assets/brand-board.html`](../assets/brand-board.html) template) and `brand-board.jpg` next to `--out`, plus `board-checks.json` in the same folder.
- What: the brand board the founder and the model review: every color role with its contrast, the display and body families at several sizes (flagged when the browser fell back to another family), each logo variant on its background with its pixel-test result, buttons, a link and a card composed with the tokens, the harvested images with their role and license, and the open issues. Checks: `text` and `text_secondary` against `bg` (4.5:1), `text_muted` (3:1), `on_accent` against `accent` (4.5:1 warn, 3:1 fail), each family really rendered, `logo_audit` status. Without Playwright, a Pillow card (swatches, font names, PNG logos) is written instead and the fonts are not checked.
- Exit codes: `0` board written, no check failed, `1` board written with at least one failed check, `3` brand JSON unreadable, `4` render error (Pillow missing included).

### `enrich_context.py`

- Inputs: `--url <homepage>` `--out <project-context dir>` `[--provider auto|firecrawl|jina|http|exa]` `[--confirm-spend]`
- Spend gate: Firecrawl and Exa use paid credits and a `JINA_API_KEY` draws on a token balance, so they run only with `--confirm-spend` (or `FOG_ALLOW_SPEND=1` for a scripted run), passed after the founder agreed. Without it, `auto` skips Firecrawl and calls Jina keyless, and a pinned `--provider firecrawl` or `exa` sends nothing and exits 4 with the estimate (up to 7 Firecrawl scrapes at 1 credit each, or one Exa search).
- Only `http` and `https` URLs are opened, redirects included (`file://`, `ftp://` refused).
- Providers: `auto` (default) = `firecrawl` if `FIRECRAWL_API_KEY` is set and spend is confirmed, else `jina` (Jina Reader, keyless; `JINA_API_KEY` raises the rate), else `http` (plain fetch with a browser user agent, no JavaScript rendering). A page that fails with one provider is retried with the next. `exa` runs a site-scoped `exa search` and is used only when asked for (needs the `exa` CLI and `EXA_API_KEY`).
- Outputs: `brand-debug/enrichment.json` (with the provider used per page) + `brand-debug/enrichment-notes.md`
- What: optional pre-fill for the business Q&A. Pulls homepage + likely about/pricing/product pages. Drafts only, always confirmed by the founder.
- Exit codes: `0` ok, `2` the requested provider is unusable (missing key or CLI: rerun with `--provider auto`) or `--url` is not http(s), `3` every fetch failed (fall back to the manual Q&A), `4` spend gate closed (nothing sent: rerun with `--provider auto`, or with `--confirm-spend` after the founder's yes).

### `ingest_docs.py`

- Inputs: `extract --out <project-context dir> FILE...` (deck `.pdf`, notes `.md` / `.txt`) `[--extractor auto|pdftotext|pypdf]`; `check --out <dir> <doc-candidates.json> [--json]`; `apply --out <dir> <doc-candidates.json> --approve ID,... [--approve-fields PATH,...] [--context FILE]`
- Keys and network: none. PDF text comes from poppler's `pdftotext` when installed, else `pypdf` when importable (neither is required: exit 3 with the install line).
- Outputs: `docs/<file>` (copy) + `docs/<file>.pages.json` (sha256, extractor, text per page); `apply` writes the approved candidates to `brand-debug/context-draft.json` (or `--context`).
- What: reads the founder's deck and notes so the Q&A asks fewer questions. `check` refuses a proof candidate whose claim, numbers included, is not word for word on the page its `source` cites (`docs/deck.pdf#p7`), a field whose excerpt is not on its page, a missing page or document, a document changed since extract; it also says whether `shared/scripts/proof.py` would let a copy use each candidate today. `apply` writes only the ids the founder approved and nothing when one of them fails.
- Exit codes: `0` ok, `1` a candidate refused (`check`, `apply`), `2` usage error, unreadable or unsupported file, `3` no PDF text extractor.

### `build_voice.py`

- Inputs: `--out <project-context dir>` then the founder's own texts (`.md` / `.txt` files, folders or public URLs) `[--lang auto|en|fr]` `[--brand-name NAME]` `[--channel post|about|email|newsletter|site|talk|other]` `[--ban WORD]` (repeatable) `[--update-context]`; without inputs it rebuilds from `voice/exemplars/`; `--check` re-runs the calibration only.
- Outputs: `voice/exemplars/` (the texts, verbatim), `voice/voice.json` (the voice pack, [`../assets/voice-schema.json`](../assets/voice-schema.json)) and `voice/rules.json` (the writing-gate project pack, `shared/schemas/copy-rules.schema.json`). `--update-context` writes `voice.pack_path`, `voice.address` and `voice.language` into `context.json`.
- What: measures sentence and paragraph length, grammatical person, form of address (you; tu or vous in French), punctuation and emoji per 1000 words, contractions, brand casing and frequent words, and writes rules as measured facts with their evidence and verbatim example sentences. Calibration: every exemplar goes through the shared writing gate with the generated pack and must pass at 0 BLOCK; a generated rule that blocks the founder's text is dropped, a shared rule that blocks it is lowered to WARN for this project, and each change is recorded with the founder's sentence. A banned word found in the founder's own text is a conflict: nothing is changed, exit 1.
- Exit codes: `0` pack written, `1` conflict (a banned word in the founder's texts; `--check`: a BLOCK remains), `2` usage error, unreadable input or a written file fails its schema, `3` under 80 words of founder text, `4` the shared writing gate was not found next to `agents/`.

### `brand_common.py`

Color math and small helpers shared by `extract_brand.py`, `logo_pipeline.py` and `render_brand_preview.py`. Not a command.

### `selftest.py`

- Inputs: `[--only brand|logo|board|voice|fetch|proof|registry|docs]` `[--keep DIR]`
- What: offline tests, no network and no key. A local HTTP server serves `tests/fixtures/site/` (images drawn by `tests/make_fixture_images.py`) with the traps the scripts must handle (a cookie banner with a large "Accept all" button, a menu icon before the logo, a black logo shown white through a CSS filter on a dark page, a gradient CTA, a webfont declared but never loaded, decorative textures and a tracking pixel). Also covers `tests/fixtures/logo-clipped.svg`, the voice texts of `tests/fixtures/voice/`, the fetch guard, `shared/scripts/proof.py` and `shared/scripts/registry.py` on the fixtures, and `ingest_docs.py` on a deck drawn by `tests/make_fixture_pdf.py`.
- Exit codes: `0` every check passes, `1` a check failed, `2` Playwright or Pillow missing (the voice, fetch, proof, registry and docs parts run without them).

Proof items and registries are read by two shared scripts, not by this folder: `../../../shared/scripts/proof.py` (`check <context.json> --scope <use>`) and `../../../shared/scripts/registry.py` (`check <project-context>`).

## Cross-platform notes

If a script needs to spawn subprocesses, use `subprocess.run([...])` with a list, not a shell string. Quote paths with spaces. Never assume `bash` is the user's shell.
