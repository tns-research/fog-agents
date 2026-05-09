---
name: landing-page-analyzer
description: CRO heuristic audit of a single SaaS landing page using the LEVER framework (Cost, Trust, Usability, Comprehension, Motivation). Captures desktop and mobile screenshots, applies an 80-criterion rubric with weighted scoring and confidence ratings, runs a 10-second comprehension test, proposes copy rewrites, and ranks fixes by impact times ease. Use before paying for traffic, after a launch, or when conversion rate stalls.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
---

# Landing Page Analyzer Agent

Heuristic CRO audit of one landing page. Inputs: a URL plus business context. Output: a friction-ranked report with concrete fixes for copy, hierarchy, CTAs, trust signals, and mobile UX. Scoring is weighted, every finding carries a confidence rating, and the top 3 copy issues each get two rewrites.

## Step 0: context resolution

1. Resolve the project slug. If the user did not supply one, ask now.
2. Look for `<your-projects-root>/<project>/landing-page-analyzer/config.json`. Read it.
3. If the file does not exist, copy `agents/landing-page-analyzer/config.example.json` to that path and ask the user for any missing required values (`url`, `goal`, `target_user`).
4. Do not proceed until `url`, `goal`, `target_user` are resolved. `language` defaults to `en`.

## When to run

- Before paying for paid traffic. Do not pour into a leaky bucket.
- After a launch when conversion is below expectation.
- Before A/B tests. Identify which hypotheses to test, in what order.
- When refactoring a high-traffic page.

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `url` | yes | n/a | the landing page URL |
| `goal` | yes | n/a | primary conversion goal (signup / demo / purchase / waitlist / contact) |
| `target_user` | yes | n/a | who the page is for |
| `context` | no | n/a | optional pricing, value prop, competitor URLs |
| `language` | no | `en` | report language |

## Prerequisites

```bash
git clone https://github.com/the20100/cli-skills.git ~/cli-skills
export PATH="$HOME/cli-skills/firecrawl-cli/bin:$PATH"
export FIRECRAWL_API_KEY="..."

# Bundled capture script (Playwright)
pip install -r agents/landing-page-analyzer/scripts/requirements.txt
playwright install chromium
```

| Tool | Used for |
|------|----------|
| `firecrawl` | scrape page markdown (desktop) |
| `scripts/capture-page.py` | desktop and mobile PNG screenshots, cookie-banner dismissal |

## Workflow

1. **Capture page.** Run `scripts/capture-page.py <out_dir> <url>` to produce `desktop.png` and `mobile.png`. In parallel, scrape markdown via `firecrawl scrape <url> --format markdown --only-main-content > <out_dir>/page.md`. If Playwright is unavailable, fall back to text-only audit and document the limitation.
2. **Extract structure.** From the markdown identify H1 and H2 hierarchy, every CTA (text, position, type), every trust signal (logos, testimonials, ratings, badges), form fields if present, pricing display, and footer.
3. **Run the 10-second comprehension test.** Read `skills/running-comprehension-test/SKILL.md`. Use the actual rendered `desktop.png` (and `mobile.png`) as stimulus, never a mock. Score the 3 questions and write the verdict.
4. **Apply the LEVER rubric.** Read `skills/auditing-lever-heuristics/SKILL.md`. Walk every row of `assets/lever-checklist-80.md` (16 criteria across 5 dimensions, desktop + mobile, OK/Partial/Missing/N/A). Compute weighted scores (impact times frequency times severity) and assign a confidence rating (low/med/high) per finding.
5. **Mobile and visual passes.** Walk `assets/visual-criteria-checklist.md` (V1 to V10 visual-only) against `mobile.png` and `desktop.png`. Walk `assets/mobile-ux-checklist.md` for touch targets, INP / CLS, lazy-load discipline, viewport mistakes. Cross-check trust signals against `assets/trust-signals-taxonomy.md` and copy against `assets/copy-anti-patterns.md`.
6. **Rank fixes and propose rewrites.** Sort all `Issue` and `Critical` findings by `impact times ease` (both 1 to 5). Tag the top 5 as "ship this week". Read `skills/proposing-copy-rewrites/SKILL.md` to write two alternatives each for the H1, the primary CTA, and the value-prop section. Draft 3 to 5 A/B hypotheses using `assets/ab-hypothesis-template.md`.
7. **Write the report.** Use `assets/output-template.md`. Save the markdown plus a sidecar JSON to the output location below (cross-cutting C1).

## Output format

See `assets/output-template.md`. Required sections: executive summary plus LEVER scorecard (/100), 10-second test, findings by LEVER dimension with confidence ratings, mobile-and-visual findings, trust-signal audit, copy anti-pattern flags, top 5 "ship this week" fixes, top 3 copy rewrites with two alternatives each, A/B hypotheses, methodology, limitations, sources.

## Output location

```
<your-projects-root>/<project-slug>/landing-page-analyzer/landing-audit-<YYYYMMDD>.md
<your-projects-root>/<project-slug>/landing-page-analyzer/landing-audit-<YYYYMMDD>.json
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/desktop.png
<your-projects-root>/<project-slug>/landing-page-analyzer/screenshots-<YYYYMMDD>/mobile.png
```

The screenshots live alongside the report so the markdown can reference them by relative path.

## Failure modes

- **Page renders only with JavaScript and Firecrawl returns empty** → use `firecrawl scrape <url> --wait-for 3000`, or rely on the capture script (Playwright already waits for `domcontentloaded` plus `networkidle`).
- **Playwright not installed** → run text-only audit on the markdown, score visual criteria with `confidence: low`, document in Limitations.
- **Auth-gated page** → ask the user for screenshots plus visible copy as text. Skip mobile pass if no mobile screenshot supplied.
- **No clear CTA on the page** → that IS the finding. Score low on Usability and Motivation, recommend adding one.
- **Goal mismatch (page goal differs from `goal` input)** → flag explicitly. Audit against the user's stated goal, then note the page seems optimized for a different one.
- **Cookie banner blocks capture** → the script auto-dismisses common banners. If a non-standard banner persists, ask the user for a manual screenshot.

## Per-project config

```
<your-projects-root>/<project>/landing-page-analyzer/config.json
```

```json
{
  "project": "<project-slug>",
  "url": "https://acme.com/pricing",
  "goal": "demo",
  "target_user": "<who the page is for>",
  "context": "<optional: pricing, value prop, competitor URLs>",
  "language": "en"
}
```
