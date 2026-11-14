# landing-page-analyzer

> Heuristic CRO audit of one landing page (SaaS, e-commerce, local service, lead generation, app listing) using a **LEVER grid** (Cost, Trust, Usability, Comprehension, Motivation): 340 criteria built on the master lever, lever and sub-lever tree of the Levers Framework published by Conversion.com (no affiliation), filtered by page type, with weighted scoring (impact times frequency times severity), confidence ratings, multi-evaluator protocol, and a 10-second comprehension test on the rendered page. Output: friction-ranked fixes plus two-alternative copy rewrites for the H1, primary CTA, and value-prop section.

**Run before** spending on paid traffic, **after** a launch when conversion underperforms, or **before** an A/B test sprint.

## What you get

- LEVER scorecard (5 dimensions, /20 each, /100 total).
- 10-second comprehension test result (3 questions, scored 1 to 5).
- Findings by LEVER dimension with severity, weight, and confidence per finding.
- Mobile and visual findings (touch targets, INP / LCP / CLS, V1 to V10 visual criteria).
- Trust-signal audit by layer (testimonials, logo bar, third-party verification, press, compliance, founder presence, customer counts, footer completeness).
- Copy anti-pattern flags (hedging, jargon, feature-listing, unsupported superlatives, hero about you, no specific number, AI-tells, generic CTAs).
- Top 5 "ship this week" fixes ranked by impact times ease.
- Top 3 copy rewrites with two alternatives each.
- Up to 5 A/B test hypotheses (because / we believe / will / for / because), each with a sample size computed from the founder's baseline and traffic.
- DOM measures of the page on desktop and mobile (overflow, tap targets against WCAG 2.5.8, contrast, CTA position against the fold, observed CLS, images, forms, page weight) with annotated captures (`scripts/probe.py`), and a scripted visit of the conversion path that blocks every final send before it leaves the browser (`scripts/journey.py`).
- Before/after renders of the top fixes injected in the live page, with the measures that prove them (`scripts/fixes.py`).
- An evidence check: every recommendation of the sidecar points at a measure, a capture or a passed fix (`scripts/check_evidence.py`).
- Repo mode (optional, `repo` in config): one unified patch per validated fix against your site's source, plus `all.patch`, each checked with `git apply --check`. A change found in several files or nowhere is listed "to carry over by hand" with the candidates, never guessed. Nothing is written to your repo: you review, apply and merge.

Saved to `<your-projects-root>/<project>/landing-page-analyzer/landing-audit-<YYYYMMDD>.md` plus a sidecar JSON.

## Quick start

No paid API is required. The bundled scripts need Playwright (Chromium):

```bash
pip install -r agents/landing-page-analyzer/scripts/requirements.txt
playwright install chromium
```

Optional: Firecrawl as the `scrape` provider (any other provider of [`../../shared/tools.md`](../../shared/tools.md) plugs in the same way):

```bash
mkdir -p ~/.local/bin
for t in firecrawl; do
  git clone --depth 1 https://github.com/the20100/$t-cli /tmp/$t-cli
  (cd /tmp/$t-cli && go build -o ~/.local/bin/$t .)
  rm -rf /tmp/$t-cli
done
export PATH="$HOME/.local/bin:$PATH"
export FIRECRAWL_API_KEY="..."   # https://www.firecrawl.dev/app/api-keys
```

## Run it

> "Run the landing-page-analyzer agent at `agents/landing-page-analyzer/`. URL: `https://acme.example/pricing`. Goal: demo bookings. Target user: B2B sales ops leads, 50 to 500 employee SaaS."

## Inputs

If you ran [`project-context`](../project-context/) first, `url`, `target_user`, `context` and `language` are prefilled from it. The agent then only asks for `goal` (and anything else still missing).

| Input | Required | Default |
|-------|----------|---------|
| `url` | yes | n/a |
| `goal` | yes | n/a |
| `target_user` | yes | n/a |
| `page_type` | yes | inferred from the page (`saas`, `ecom`, `local`, `lead`, `app`), stated before the run |
| `context` | no | n/a |
| `language` | no | `en` |
| `repo` | no | none (path to the site source code, turns on repo patches) |

## Per-project config

```
<your-projects-root>/<project>/landing-page-analyzer/config.json
```

Config is created from `config.example.json` on first run. The agent prompts for missing required values.

## Repo mode

```bash
python3 agents/landing-page-analyzer/scripts/repo_patch.py --repo ../acme-site --fixes <run folder>/fixes
```

Reads the fixes that passed the before/after, finds each change in the source (rendered text in `.html`, `.md`, `.mdx`, `.astro`, `.jsx`, `.tsx`, `.vue`, `.svelte`, `.njk`, `.liquid`, then in JSON and YAML content and i18n files; elements by id, classes or href; CSS rules by exact selector and media query in `.css`, `.scss`, `.less` and `<style>` blocks) and writes `repo-patches/<id>.patch`, `repo-patches/all.patch`, `repo-patches.json` and `repo-patches.md` next to `fixes/`. Statuses: `ready`, `ready-needs-import` (CSS with no exact rule goes to a new `lpa-fixes.css` that you import after your main stylesheet), `manual` (candidates and reason, no patch). `--exclude <path>` skips a dead copy of a component. Tailwind utility classes are not rewritten: their CSS goes to `lpa-fixes.css`. Patches drop the `!important` the before/after render injects; check the result in your dev server before merging.

## Tools

Each capability is resolved at Step 0 from the project `tools.json` or the chat ([`../../shared/tools.md`](../../shared/tools.md)); a missing one turns its grid rows Unverified.

| Capability | Default | Purpose |
|------------|---------|---------|
| `screenshot` | `scripts/capture-page.py` (local Playwright) | desktop and mobile PNG screenshots, first screen and whole page, cookie-banner dismissal |
| `scrape` | host web fetch, or `curl` for HTML (Firecrawl, Jina Reader and others optional) | page text and HTML |
| `page_speed` | `scripts/pagespeed.py` (PageSpeed Insights, else local Lighthouse) | Core Web Vitals |

## Folder layout

```
landing-page-analyzer/
├── AGENT_LANDING_PAGE_ANALYZER.md     ← agent spec, Step 0 plus a 10-step workflow
├── README.md                           ← this file
├── config.example.json                 ← per-project config template
├── skills/
│   ├── auditing-lever-heuristics/SKILL.md     ← core methodology
│   ├── running-comprehension-test/SKILL.md    ← 10-second test
│   └── proposing-copy-rewrites/SKILL.md       ← two-alternative rewrites
├── assets/
│   ├── lever-grid.md                   ← 340-criterion LEVER grid (rubric data)
│   ├── visual-criteria-checklist.md    ← V1 to V10 visual-only
│   ├── mobile-ux-checklist.md          ← touch + INP/LCP/CLS + forms
│   ├── trust-signals-taxonomy.md       ← layer-by-layer trust audit
│   ├── copy-anti-patterns.md           ← hedging, jargon, etc.
│   ├── ab-hypothesis-template.md       ← because / we believe / will / for / because
│   └── output-template.md              ← the deliverable structure
├── references/
│   ├── README.md                       ← CLIs, frameworks, performance
│   └── cro-frameworks.md               ← LEVER + CXL + LIFT + NN/g cross-walk
├── examples/
│   └── northdock-apply-fixture/         ← offline fixture: site/, repo/, journey.json, fixes.json, audit.example.json
└── scripts/
    ├── capture-page.py                 ← Playwright single-page capture
    ├── pagespeed.py                    ← Core Web Vitals (PageSpeed Insights, else local Lighthouse)
    ├── probe.py, probe.js              ← DOM measures (overflow, targets, contrast, CLS, forms)
    ├── lpa_common.py                   ← helpers shared by probe.py, journey.py and fixes.py
    ├── journey.py                      ← scripted visit, writes blocked before they leave
    ├── fixes.py                        ← before/after render of each fix on the live page
    ├── repo_patch.py                   ← repo mode: one patch per validated fix, git apply --check
    ├── check_evidence.py               ← every recommendation and announced patch resolves
    ├── selftest.py                     ← offline test on examples/northdock-apply-fixture/ (site/ and repo/)
    ├── requirements.txt                ← playwright>=1.65.0
    └── README.md                       ← script usage
```

## Read more

- Full agent spec: [`AGENT_LANDING_PAGE_ANALYZER.md`](./AGENT_LANDING_PAGE_ANALYZER.md)
- 340-criterion LEVER grid: [`assets/lever-grid.md`](./assets/lever-grid.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- CRO framework cross-walk: [`references/cro-frameworks.md`](./references/cro-frameworks.md)

## License

Apache 2.0.
