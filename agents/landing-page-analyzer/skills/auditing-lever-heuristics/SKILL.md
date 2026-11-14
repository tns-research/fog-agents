---
name: auditing-lever-heuristics
description: Applies the 340-criterion LEVER grid (Cost, Trust, Usability, Comprehension, Motivation, organized by the Conversion.com master lever, lever and sub-lever tree) to a landing page, filtered by page type, using weighted OK / Partial / Missing / N/A coverage scoring plus a weighted findings layer (impact times frequency times severity) and a per-finding confidence rating. Uses a multi-evaluator protocol when two evaluators disagree. Produces the LEVER scorecard and the prioritized findings list. Triggers on words like "audit", "score", "evaluate", "review against checklist", "LEVER", "heuristic audit".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write
---

# auditing-lever-heuristics

Core methodology for auditing a single landing page against the 340-criterion LEVER grid. Two scoring layers run in parallel:

1. **Coverage scoring.** Per-criterion OK / Partial / Missing / N/A on `assets/lever-grid.md`, weighted by the row weight (3, 2, 1). Produces the per-lever score (/20) and the page total (/100).
2. **Weighted findings layer.** For each Partial or Missing finding, compute `weight = impact * frequency * severity` (each on 1 to 5; max 125). Used to prioritize fixes.

Each finding also carries a **confidence rating** (low / med / high). The audit can run with markdown only (low confidence on visual criteria), with one viewport (med), or with desktop and mobile screenshots plus markdown (high).

When two evaluators disagree on a borderline call (Partial vs Missing), apply the multi-evaluator protocol below.

---

## When to invoke

The agent's `AGENT_LANDING_PAGE_ANALYZER.md` workflow points here at Step 4 ("Apply the LEVER rubric"). The skill is the bridge between the workflow and the data.

---

## Inputs

- `markdown` (string): the page content from the `scrape` provider resolved at Step 0 (`page.md`), plus the raw HTML (`page.html`) for the `H` rows.
- `screenshots` (file paths): `desktop.png` and optionally `mobile.png` from the bundled capture script, plus the `desktop-full-NN.png` and `mobile-full-NN.png` slices of the whole page.
- `page_type` (string): `saas`, `ecom`, `local`, `lead` or `app`. Selects the applicable rows of the grid.
- `psi` (file path, optional): `psi-summary.json` written by `scripts/pagespeed.py` for the mobile run. Needed for the `P` evidence rows.
- `goal` (string): the conversion goal (signup / demo / purchase / waitlist / contact). Drives whether some criteria are N/A.
- `target_user` (string): who the page is for. Drives ICP-specific judgments.
- `language` (string): the report language. The rubric is English; report output follows this.

---

## Procedure

### Step 1: Coverage scoring (per-criterion, OK / Partial / Missing / N/A)

1. Open `assets/lever-grid.md`. Keep only the rows whose Scope is `all` or contains the audited `page_type` (between 223 and 265 rows depending on the type). Every other row is N/A.
2. **Walk the grid in five passes, one per master lever** (Cost, Trust, Usability, Comprehension, Motivation). Finish a pass, write its results to the sidecar JSON, then start the next. Never score the whole grid in one go: attention drops and late rows get rubber-stamped.
3. For each applicable row, check the evidence named in the `Ev.` column and decide:
   - **OK** (2 pts): the page clearly satisfies the criterion.
   - **Partial** (1 pt): present but weak, or only on one viewport.
   - **Missing** (0 pts): the page does not satisfy it.
   - **N/A** (excluded): the row does not apply to this page despite its scope (for example SSO on a consumer page). Justify in the note.
   - **Unverified** (excluded, listed in Limitations): the evidence is not available (no PageSpeed data for a `P` row, no interaction possible for an `X` row, the section lies outside the captured screenshots). Never guess an `X` or `P` row.
4. `S` rows are scored on desktop and mobile separately; the row score is the mean of the two.
5. Record a note of at most 12 words for every non-OK row, verbatim from the page when possible.
6. Per master lever: `score = 20 * sum(weight * points) / sum(weight * 2)` over applicable, verified rows. The total is the sum of the five, out of 100.
7. Report the coverage line per lever (applicable, verified, unverified). A lever with fewer than 60 % verified rows is flagged low confidence.
8. Any `W3` row scored Missing is a critical finding and goes to the top of the findings list, whatever the lever score.

### Step 2: Weighted findings layer (prioritization)

For each criterion scored Partial or Missing, produce a finding with three weights:

- **Impact** (1 to 5): how much fixing this criterion would lift conversion. 5 = directly unblocks the conversion path. 1 = cosmetic.
- **Frequency** (1 to 5): how often a typical visitor encounters this issue. 5 = every visitor sees it (e.g. hero copy). 1 = rare path (e.g. footer item).
- **Severity** (1 to 5): how badly the issue blocks the action. 5 = causes bounce. 1 = mild friction.

Compute `weight = impact * frequency * severity` (max 125). Sort findings by weight descending.

Heuristics for assigning weights:

| Where on page | Frequency hint | Why |
|---------------|----------------|-----|
| Hero (above the fold) | 5 | Every visitor sees it |
| First scroll | 4 | Most visitors see it |
| Mid page | 3 | Engaged visitors see it |
| Footer | 2 | Some visitors see it |
| Pricing page (linked) | 3 to 4 | Buy-intent visitors only |

| Criterion type | Severity hint |
|----------------|---------------|
| Missing primary CTA | 5 |
| Missing risk reversal where required | 4 |
| Missing trust signal | 3 to 4 |
| Generic CTA copy | 3 |
| Typography readability | 2 |
| Footer item missing | 1 to 2 |

Record the weight, the impact, and the confidence in the report findings table.

### Step 3: Confidence rating per finding

Assign one of three:

- **High**: both desktop and mobile screenshots plus the markdown confirm the finding.
- **Med**: one viewport screenshot plus markdown confirm. Or the markdown alone confirms a non-visual criterion (e.g. "no privacy policy linked in footer").
- **Low**: only the markdown is available (Playwright unavailable), and the criterion is visual; OR the criterion requires runtime data (LCP, INP, CLS) and no Lighthouse run was done.

Confidence is reported separately from severity. A high-severity finding with low confidence should be re-checked manually before shipping a fix.

### Step 4: Quick-fix vs Real-fix split

For each finding, tag the fix type:

- **Quick fix (≤ 1 hour)**: copy edit, button text, image swap, alt text, footer link.
- **Real fix (≥ 1 day)**: layout change, new component, new section, performance refactor.

The Top 5 "ship this week" list pulls from Quick fixes first, sorted by impact * ease.

---

## Multi-evaluator protocol

When two evaluators (human or model) score the same criterion differently:

### Calibration round (once per session)

1. Both evaluators score the **first 10 applicable rows of each master lever** independently without comparing.
2. Compare. Where scores differ, discuss the criterion text and the page evidence to align.
3. Update shared notes if the criterion definition is ambiguous.

### Independent scoring

4. Both evaluators score every applicable row independently. No discussion during scoring.

### Consolidation

5. For criteria with matching scores: accept.
6. For criteria with one-step difference (OK vs Partial, Partial vs Missing): keep the more conservative score. In the note, mention that the score is a consolidation.
7. For criteria with two-step difference (OK vs Missing): re-evaluate together. The disagreement signals an evidence gap, not a judgment gap.
8. For criteria where one evaluator says N/A and the other gives a score: the N/A evaluator must justify with the page context. If justified, use N/A. Else use the score.

The audit can run single-evaluator. The multi-evaluator protocol kicks in only when the user requests a calibrated audit (typically when the audit will inform a major redesign decision or external A/B test plan).

---

## Validation plan

Findings should be validated against external evidence when available:

- **Heat-map or session recordings** (if user has Hotjar Free, FullStory, or similar): confirm visitors actually behave as the heuristic predicted. Heat-map data is qualitative validation, not statistical.
- **Analytics funnel**: the funnel data should show the predicted drop-off where the audit predicted friction. If not, downgrade severity.
- **Customer interview corpus**: if the audit flags missing trust signals, check the corpus for trust-related objections. If buyers consistently raise the flagged objection, upgrade severity.

The agent does not perform validation; it surfaces what should be validated. Validation is documented as a follow-up in the report's Recommendations section.

---

## Output

Markdown findings tables (one per LEVER dimension) plus a sidecar JSON. See `assets/output-template.md` for the exact structure.

```markdown
### Cost (perceived friction)

| # | Criterion (ID) | Status | Severity | Weight | Confidence | Note |
|---|----------------|--------|---------:|-------:|-----------|------|
| C020 | Trial end behavior unclear | Partial | 4 | 48 | high | Page says "free trial" but not what happens at day 14 |
| C009 | Annual / monthly toggle missing | Missing | 3 | 27 | high | Only monthly shown |
```

```json
{
  "id": "C020",
  "dimension": "Cost",
  "lever": "Financial cost",
  "sub_lever": "Anticipated cost",
  "row_weight": 3,
  "criterion": "Trial end behavior unclear",
  "status": "Partial",
  "severity": 4,
  "impact": 4,
  "frequency": 3,
  "weight": 48,
  "confidence": "high",
  "viewport": "both",
  "note": "Page says free trial but not what happens at day 14",
  "fix_type": "quick"
}
```

---

## Failure modes

- **Empty rubric file.** Stop and ask the user. Do not invent criteria.
- **Page unreachable.** Log the URL, capture what is available, document as a Limitation. Do not retry blindly.
- **Ambiguous status (OK vs Partial).** Score Partial with a `?` flag and a note. Better to surface the ambiguity than to silently round.
- **No screenshots available.** Run text-only audit. Mark all visual-criteria findings at low confidence. Document in Limitations.
- **Goal mismatch (page goal differs from `goal` input).** Flag explicitly. Audit against the user's stated goal, then add a note that the page seems optimized for a different one.

---

## Notes

- Keep this file under 500 lines (Anthropic Agent Skills spec). Extra detail goes into `assets/lever-grid.md` (the grid data) or `references/cro-frameworks.md` (the multi-framework cross-walk).
- The grid data is in `assets/lever-grid.md`. Never inline its rows in this file.
- The agent's `AGENT_LANDING_PAGE_ANALYZER.md` Step 4 is the entry point.
