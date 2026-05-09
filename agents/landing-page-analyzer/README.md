# landing-page-analyzer

> Heuristic CRO audit of one SaaS landing page using the **LEVER framework** (Cost, Trust, Usability, Comprehension, Motivation). 80-criterion rubric with weighted scoring (impact times frequency times severity), confidence ratings, multi-evaluator protocol, and a 10-second comprehension test on the rendered page. Output: friction-ranked fixes plus two-alternative copy rewrites for the H1, primary CTA, and value-prop section.

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
- 3 to 5 A/B test hypotheses (because / we believe / will / for / because).

Saved to `<your-projects-root>/<project>/landing-page-analyzer/landing-audit-<YYYYMMDD>.md` plus a sidecar JSON.

## Quick start

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$PATH"
export FIRECRAWL_API_KEY="..."   # https://www.firecrawl.dev/app/api-keys

# Bundled capture script (Playwright)
pip install -r agents/landing-page-analyzer/scripts/requirements.txt
playwright install chromium
```

## Run it

> "Run the landing-page-analyzer agent at `agents/landing-page-analyzer/`. URL: `https://acme.com/pricing`. Goal: demo bookings. Target user: B2B sales ops leads, 50 to 500 employee SaaS."

## Inputs

| Input | Required | Default |
|-------|----------|---------|
| `url` | yes | n/a |
| `goal` | yes | n/a |
| `target_user` | yes | n/a |
| `context` | no | n/a |
| `language` | no | `en` |

## Per-project config

```
<your-projects-root>/<project>/landing-page-analyzer/config.json
```

Config is created from `config.example.json` on first run. The agent prompts for missing required values.

## Required tools

| Tool | Purpose |
|------|---------|
| `firecrawl` | scrape page markdown (desktop) |
| `scripts/capture-page.py` | desktop and mobile PNG screenshots, cookie-banner dismissal |

## Folder layout

```
landing-page-analyzer/
├── AGENT_LANDING_PAGE_ANALYZER.md     ← agent spec, 7-step workflow
├── README.md                           ← this file
├── config.example.json                 ← per-project config template
├── skills/
│   ├── auditing-lever-heuristics/SKILL.md     ← core methodology
│   ├── running-comprehension-test/SKILL.md    ← 10-second test
│   └── proposing-copy-rewrites/SKILL.md       ← two-alternative rewrites
├── assets/
│   ├── lever-checklist-80.md           ← 80-criterion rubric (rubric data)
│   ├── visual-criteria-checklist.md    ← V1 to V10 visual-only
│   ├── mobile-ux-checklist.md          ← touch + INP/LCP/CLS + forms
│   ├── trust-signals-taxonomy.md       ← layer-by-layer trust audit
│   ├── copy-anti-patterns.md           ← hedging, jargon, etc.
│   ├── ab-hypothesis-template.md       ← because / we believe / will / for / because
│   └── output-template.md              ← the deliverable structure
├── references/
│   ├── README.md                       ← CLIs, frameworks, performance
│   └── cro-frameworks.md               ← LEVER + CXL + LIFT + NN/g cross-walk
└── scripts/
    ├── capture-page.py                 ← Playwright single-page capture
    ├── requirements.txt                ← playwright>=1.40
    └── README.md                       ← script usage
```

## Read more

- Full agent spec: [`AGENT_LANDING_PAGE_ANALYZER.md`](./AGENT_LANDING_PAGE_ANALYZER.md)
- 80-criterion rubric: [`assets/lever-checklist-80.md`](./assets/lever-checklist-80.md)
- Output skeleton: [`assets/output-template.md`](./assets/output-template.md)
- CRO framework cross-walk: [`references/cro-frameworks.md`](./references/cro-frameworks.md)

## License

Apache 2.0.
