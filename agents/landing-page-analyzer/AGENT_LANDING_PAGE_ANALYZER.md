---
name: landing-page-analyzer
description: CRO heuristic audit of a single landing page (SaaS, e-commerce, local service, lead generation or app listing) using a LEVER grid (Cost, Trust, Usability, Comprehension, Motivation) built on the Levers Framework published by Conversion.com, no affiliation. Captures desktop and mobile screenshots of the whole page, measures Core Web Vitals, applies a 340-criterion grid filtered by page type with weighted scoring and confidence ratings, runs a 10-second comprehension test, proposes copy rewrites, and ranks fixes by impact times ease. Use before paying for traffic, after a launch, or when conversion rate stalls.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "3.0"
---

# Landing Page Analyzer Agent

Heuristic CRO audit of one landing page. Inputs: a URL plus business context. Output: a friction-ranked report with concrete fixes for copy, hierarchy, CTAs, trust signals, and mobile UX. Scoring is weighted, every finding carries a confidence rating, and the top 3 copy issues each get two rewrites.

## Step 0: context resolution

1. Resolve the project slug. If the user did not supply one, ask now.
2. **Load shared context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md). If `<your-projects-root>/<project>/project-context/context.json` exists, prefill:

   | Input | From `context.json` |
   |-------|---------------------|
   | `url` | `url` (the user may point at a deeper page instead, such as `/pricing`) |
   | `target_user` | `icp.who` |
   | `context` | `offer.core`, `offer.price_model`, `offer.differentiators[]`, `positioning.against`, `positioning.promise` |
   | `language` | `voice.language` |
   | `goal` | not in project-context: asked in the Step 0 message unless `config.json` has it; without an answer, the action of the page's primary CTA (signup, demo, purchase, waitlist, contact), stated in the report |
   | `page_type` | not in project-context; infer from the page (pricing plans: `saas`, add to cart: `ecom`, address and service area: `local`, gated resource or quote form: `lead`, store listing: `app`) and state the inference in the Step 0 block, where the founder may correct it |

   Keep `allowed_claims`, `claims_policy`, `banned_words` and `tone` for the copy rewrites (Step 6).
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md) (Step 0 part): read `<your-projects-root>/<project>/project-context/memory/decisions.md` when it exists and apply every active decision whose scope covers this agent as a hard rule (a decision outranks this file's defaults; a value given in this chat outranks a decision). List proposed decisions and conflicts in the Step 0 block. When `memory/runs.jsonl` holds a line for this agent with the same `inputs_hash` and its outputs exist, report it and stop with a `skipped` line. A missing memory folder is not an error.
4. Look for `<your-projects-root>/<project>/landing-page-analyzer/config.json`. Read it. If the file does not exist, copy `agents/landing-page-analyzer/config.example.json` to that path. Values the user gives in chat win, then `config.json`, then project-context, then defaults.
5. **Optional handoff.** If `<your-projects-root>/<project>/market-signal/market-signal-<YYYYMMDD>.json` exists (latest date wins, contract in [`../../shared/handoffs.md`](../../shared/handoffs.md)), load its verbatim quotes, pains, objections and `marketing_copy` as `customer_quotes` for Step 6 and say so in one line. If it does not exist, continue as usual. A handoff file older than 90 days is still used: give its date in the Step 0 block and in Limitations, and do not ask about it (this agent does not wait on the 90-day question of `shared/handoffs.md`).
6. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for `screenshot`, `scrape` and `page_speed`, and announce the tool plan in one block.
7. **One message of questions.** Ask every input still missing in a single message, together with any other Step 0 question (including the optional `repo`: "Do you have the site's source code on this machine? Give its path and the validated fixes come back as patches"), each with the default used without an answer (Inputs table). Then run on the answers or the defaults, and write each default used in the report's Methodology. `target_user` defaults to project-context `icp.who`, else to the audience the page addresses, stated as an inference; `language` defaults to `en`. Only `url` has no default: without it and without project-context, the run cannot start. No later step stops for an answer, except a step that spends money or publishes.

## When to run

- Before paying for paid traffic. Do not pour into a leaky bucket.
- After a launch when conversion is below expectation.
- Before A/B tests. Identify which hypotheses to test, in what order.
- When refactoring a high-traffic page.

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `url` | yes | project-context `url`, else ask | the landing page URL |
| `goal` | yes | asked at Step 0; without an answer, the action of the page's primary CTA | primary conversion goal (signup / demo / purchase / waitlist / contact) |
| `target_user` | yes | project-context `icp.who`, else the audience the page addresses (inferred, stated in the report) | who the page is for |
| `page_type` | yes | inferred from the page, stated in the Step 0 block | `saas`, `ecom`, `local`, `lead` or `app`. Selects the applicable rows of the LEVER grid |
| `context` | no | project-context `offer` + `positioning` | optional pricing, value prop, competitor URLs |
| `language` | no | project-context `voice.language`, else `en` | report language |
| `repo` | no | `config.json` `repo`, else none (no repo mode) | local path to the site's source code; turns on Step 8, which writes patches against it and never writes to it |

## Tools

No paid API is required. Each capability below has free fallbacks; the founder picks providers in `tools.json` or in chat, and [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) resolves them at Step 0. Providers per capability: [`../../shared/tools.md`](../../shared/tools.md).

| Capability | Used for | Default | Without it |
|------------|----------|---------|------------|
| `screenshot` | first-screen and full-page images, desktop and mobile (`S` rows, comprehension test) | `scripts/capture-page.py` (local Playwright, free) | founder drops screenshots in the output folder; otherwise `S` rows are Unverified |
| `scrape` | page text (`M` rows) and HTML (`H` rows) | host web fetch, or `curl` for HTML | founder pastes the page text; `H` rows Unverified |
| `page_speed` | Core Web Vitals (rows U023 to U028) | `scripts/pagespeed.py` (PageSpeed Insights, no key needed at low volume, else local Lighthouse) | founder pastes LCP, INP, CLS from pagespeed.web.dev; otherwise Unverified |

Optional setup for the local tools:

```bash
pip install -r agents/landing-page-analyzer/scripts/requirements.txt
playwright install chromium
```

Firecrawl (`firecrawl scrape <url> --format markdown`), Jina Reader or any other `scrape` provider from [`../../shared/tools.md`](../../shared/tools.md) plugs in the same way.

## Workflow

1. **Collect evidence** with the providers resolved at Step 0, in parallel:
   - `screenshot`: by default `scripts/capture-page.py <out_dir> <url>`, which saves `desktop.png` and `mobile.png` (first screen only) plus `desktop-full-NN.png` and `mobile-full-NN.png` (the whole page in slices). Founder screenshots dropped in `<out_dir>` are used as is.
   - `scrape`: page text to `<out_dir>/page.md` and raw HTML to `<out_dir>/page.html` (for example `firecrawl scrape <url> --format markdown --only-main-content`, `curl https://r.jina.ai/<url>`, the host web fetch, and `curl -sL <url>` for the HTML).
   - `page_speed`: by default `scripts/pagespeed.py <out_dir> <url>` (PageSpeed Insights, then local Lighthouse if it fails) for `psi-summary.json`.

   Whatever is missing turns its rows Unverified: no screenshots, `S` rows; no HTML, `H` rows; no speed data, U023 to U028.

   **Review the captures before scoring anything on them** ([`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md)). Build the sheet, then read it with the checks that apply to a capture: R9 (cookie banner, consent wall, loader, chat widget or blank area hiding the page), R10 (`desktop.png` 1280x900 and `mobile.png` 390x844 by default, slices present), R1 (a slice cut mid-section with nothing after it):

   ```bash
   python3 ../../shared/skills/reviewing-renders/scripts/contact_sheet.py <out_dir> -o <out_dir>/contact-sheet.png --title "captures"
   ```

   A failing capture is fixed at the source (the capture script's wait or banner handling, a re-run with another `screenshot` provider), never by editing the image; 3 rounds at most. A capture still failing after that keeps its `S` rows Unverified and is named in Limitations.
2. **Extract structure.** From the markdown identify H1 and H2 hierarchy, every CTA (text, position, type), every trust signal (logos, testimonials, ratings, badges), form fields if present, pricing display, and footer.
3. **Run the 10-second comprehension test.** Read `skills/running-comprehension-test/SKILL.md`. Use the actual rendered `desktop.png` (and `mobile.png`) as stimulus, never a mock. Score the 3 questions and write the verdict.
4. **Apply the LEVER grid.** Read `skills/auditing-lever-heuristics/SKILL.md`. Filter `assets/lever-grid.md` by `page_type` (223 to 265 applicable rows out of 340), then walk it in five passes, one per master lever, scoring each row OK / Partial / Missing / N/A / Unverified with the evidence its `Ev.` column names. Compute the weighted lever scores, then the findings weight (impact times frequency times severity) and a confidence rating per finding.
5. **Mobile and visual passes.** Walk `assets/visual-criteria-checklist.md` (V1 to V10 visual-only) against `mobile.png` and `desktop.png`. Walk `assets/mobile-ux-checklist.md` for touch targets, INP / CLS, lazy-load discipline, viewport mistakes. Cross-check trust signals against `assets/trust-signals-taxonomy.md` and copy against `assets/copy-anti-patterns.md`.
6. **Rank fixes and propose rewrites.** Sort all `Issue` and `Critical` findings by `impact times ease` (both 1 to 5). Tag the top 5 as "ship this week". Read `skills/proposing-copy-rewrites/SKILL.md` to write two alternatives each for the H1, the primary CTA, and the value-prop section. When the market-signal sidecar was loaded, pass its quotes as `customer_quotes` so at least one alternative per location reuses real wording (cite the `quote_id` and permalink in the mechanic note). Run every alternative through [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md): a metric, customer name, logo or testimonial in a rewrite comes from `positioning.proof`, from the page itself, or from a source URL, otherwise the rewrite goes proof-free. Draft 3 to 5 A/B hypotheses using `assets/ab-hypothesis-template.md`.
7. **Test the fixes before and after.** When Playwright is installed, write the top fixes that change the page (CSS, text, attributes, inserted markup) as `fixes.json` (shape in the docstring of `scripts/fixes.py`) and render them on the live page: `python3 scripts/fixes.py fixes.json --out <run_dir>`, where `<run_dir>` is `screenshots-<YYYYMMDD>/`. Each fix loads once as is and once with the change injected, per viewport, and its `expect` lines are checked on the after measures. A fix that fails stays a recommendation without a `fix:` reference. Measures for the report come from `scripts/probe.py` and the form journey from `scripts/journey.py`, written to the same `<run_dir>`.
8. **Repo patches (repo mode).** Run it when `repo` is set and at least one fix passed Step 7. Propose it in the delivery message when it is not set and the founder edits the site in code (a git checkout of a static site, Astro, Next, Nuxt, SvelteKit, Eleventy, Jekyll, Hugo, a Shopify theme pulled locally); skip it for sites edited only in a hosted builder, where `fixes/<id>/patch.css` and `patch.js` stay the hand-off.

   ```bash
   python3 scripts/repo_patch.py --repo <repo> --fixes <run_dir>/fixes
   ```

   For every passed fix the script finds each change in the source: the text the element showed before the fix in the markup files, then as a value of the JSON and YAML content and i18n files; the element by id, classes or href for attribute and markup changes; the CSS rule with the same selector and media query. Found in exactly one place: a unified patch, `repo-patches/<id>.patch`, plus `repo-patches/all.patch` for every ready fix at once, each checked with `git apply --check` on a temporary copy. Found in several places or nowhere: no patch is guessed, the fix is `manual` with its candidates and the reason. CSS with no exact rule goes to a new `lpa-fixes.css` and the fix is `ready-needs-import` (the founder imports the file after the main stylesheet). The repo is only read: no write, no branch, no commit, no push, no pull request. Copy `repo-patches/repo-patches.md` into the report and the per-fix entries of `repo-patches/repo-patches.json` into the sidecar `repo_patches` (with `repo`), statuses unchanged. The founder reviews, applies and merges each patch.
9. **Write the report.** Use `assets/output-template.md`. Save the markdown plus a sidecar JSON to the output location below (cross-cutting C1).
10. **Checks, then the run log.** Run [Checks before delivery](#checks-before-delivery) in order, record each result in the report's Methodology, then append the run line and propose decisions.

## Checks before delivery

The gate order of [`../../shared/README.md`](../../shared/README.md#order-of-the-gates), each gate on the output of the previous one. Commands run from this agent's folder (`agents/landing-page-analyzer/`; from the repo root, drop the leading `../../`). `<project>` stands for `<your-projects-root>/<project-slug>`.

1. **Writing gate** ([`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md)) on the copy rewrites (Step 6) and the report prose:

   ```bash
   python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --project <project> --json <project>/landing-page-analyzer/landing-audit-<YYYYMMDD>.md > <project>/landing-page-analyzer/writing-gate-<YYYYMMDD>.json
   ```

   Text quoted from the audited page is evidence, not copy: keep it in blockquotes or code spans so the gate skips it. Fix every BLOCK in the copy, 3 passes at most; a BLOCK left after the third pass goes to the report with its reason. Without Python: the skill's family table as a manual checklist, "Writing gate: manual" in Methodology.
2. **Claims check** ([`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md)) on every rewrite, already applied at Step 6: re-run it on any rewrite the writing gate changed.
3. **Schema check** of the sidecar. No JSON Schema ships for it yet: it must parse.

   ```bash
   python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" <project>/landing-page-analyzer/landing-audit-<YYYYMMDD>.json
   ```

4. **Evidence check** of the sidecar against the run folder: every recommendation points at a measure, a capture or a passed fix, and in repo mode every patch announced `ready` or `ready-needs-import` exists and still passes `git apply --check` on the founder's repo, with the status `repo_patch.py` recorded. Fix the sidecar, never the check; re-run `repo_patch.py` when the repo moved since Step 8.

   ```bash
   python3 scripts/check_evidence.py <project>/landing-page-analyzer/landing-audit-<YYYYMMDD>.json --root <project>/landing-page-analyzer/screenshots-<YYYYMMDD> [--repo <repo>]
   ```

5. **Render review** of the captures, run at Step 1 before any visual criterion is scored (see there); record its rounds and verdict here. When the report embeds before/after renders of a fix, they go through the same review before delivery.
6. **Fresh-eyes review** ([`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)) with the default rubric, packet in `<project>/landing-page-analyzer/review/`. One revision. Without a reviewer: "Fresh-eyes review: not run", deliverable listed as unreviewed.
7. **Run log and decisions** ([`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md), last step): append one line to `<project>/project-context/memory/runs.jsonl` (failures included), validate it, then show the proposed decisions in one block:

   ```bash
   python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl
   ```

## Output format

See `assets/output-template.md`. Required sections: executive summary plus LEVER scorecard (/100), 10-second test, findings by LEVER dimension with confidence ratings, mobile-and-visual findings, trust-signal audit, copy anti-pattern flags, top 5 "ship this week" fixes, top 3 copy rewrites with two alternatives each, A/B hypotheses, methodology, limitations, sources.

## Output location

```
<your-projects-root>/<project-slug>/landing-page-analyzer/landing-audit-<YYYYMMDD>.md
<your-projects-root>/<project-slug>/landing-page-analyzer/landing-audit-<YYYYMMDD>.json
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/desktop.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/desktop-full-NN.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/mobile.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/mobile-full-NN.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/psi-summary.json
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/probe.json
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/probe-<viewport>.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/journey/journey-log.json
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/fixes/fixes.md
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/fixes/<id>/compare-<viewport>.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/repo-patches/<id>.patch
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/repo-patches/all.patch
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/repo-patches/repo-patches.json
```

`probe.json`, `journey/` and `fixes/` exist when Step 7 ran, `repo-patches/` in repo mode only. Never write them inside the founder's repo: `repo_patch.py` refuses an output folder inside `--repo`.

The screenshots live alongside the report so the markdown can reference them by relative path.

## Failure modes

- **Page renders only with JavaScript and Firecrawl returns empty** → use `firecrawl scrape <url> --wait-for 3000`, or rely on the capture script (Playwright already waits for `domcontentloaded` plus `networkidle`).
- **Playwright not installed** → run text-only audit on the markdown, score visual criteria with `confidence: low`, document in Limitations.
- **Auth-gated page** → audit what is reachable, mark the rest Unverified, and give the drop-back in the report: the founder drops screenshots in the output folder and pastes the visible copy, then re-runs. Skip the mobile pass if no mobile screenshot is supplied. When the page is known to be gated at Step 0, ask for the files in the Step 0 message.
- **No clear CTA on the page** → that IS the finding. Score low on Usability and Motivation, recommend adding one.
- **Goal mismatch (page goal differs from `goal` input)** → flag explicitly. Audit against the user's stated goal, then note the page seems optimized for a different one.
- **Repo mode: every change of a fix found in several places** (an old copy of a component, the same string in two locale files) → the fix is `manual` with the candidates listed in the report. When the founder later names the dead copy, re-run Step 8 with `--exclude <path of the dead copy>`. Never pick a candidate yourself.
- **Repo mode: text not found** → the text is built from variables, a CMS or an API. The fix is `manual`; the report names the files holding parts of the text when there are any.
- **Repo mode: a ready patch no longer applies at the evidence check** → the founder's code moved after Step 8. Re-run Step 8; never edit a patch by hand.
- **Cookie banner blocks capture** → the script auto-dismisses common banners. If a non-standard banner persists (the capture review catches it under R9), mark the hidden rows Unverified and name the banner in Limitations, with the same drop-back for a manual screenshot.

## Per-project config

```
<your-projects-root>/<project>/landing-page-analyzer/config.json
```

```json
{
  "project": "<project-slug>",
  "url": "https://acme.example/pricing",
  "goal": "demo",
  "page_type": "saas",
  "target_user": "<who the page is for>",
  "context": "<optional: pricing, value prop, competitor URLs>",
  "language": "en",
  "repo": "<optional: path to the site source code, turns on repo patches>"
}
```
