---
name: auditing-lever-heuristics
description: Applies the LEVER 80-criterion rubric (Cost, Trust, Usability, Comprehension, Motivation) to a landing page using OK / Partial / Missing / N/A coverage scoring plus a weighted findings layer (impact times frequency times severity) and a per-finding confidence rating. Uses a multi-evaluator protocol when two evaluators disagree. Produces the LEVER scorecard and the prioritized findings list. Triggers on words like "audit", "score", "evaluate", "review against checklist", "LEVER", "heuristic audit".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# auditing-lever-heuristics

Core methodology for auditing a single landing page against the LEVER 80-criterion rubric. Two scoring layers run in parallel:

1. **Coverage scoring.** Per-criterion OK / Partial / Missing / N/A on `assets/lever-checklist-80.md`. Produces the per-lever score (/20) and the page total (/100).
2. **Weighted findings layer.** For each Partial or Missing finding, compute `weight = impact * frequency * severity` (each on 1 to 5; max 125). Used to prioritize fixes.

Each finding also carries a **confidence rating** (low / med / high). The audit can run with markdown only (low confidence on visual criteria), with one viewport (med), or with desktop and mobile screenshots plus markdown (high).

When two evaluators disagree on a borderline call (Partial vs Missing), apply the multi-evaluator protocol below.

---

## When to invoke

The agent's `AGENT_LANDING_PAGE_ANALYZER.md` workflow points here at Step 4 ("Apply the LEVER rubric"). The skill is the bridge between the workflow and the data.

---

## Inputs

- `markdown` (string): the page content from `firecrawl scrape`.
- `screenshots` (file paths): `desktop.png` and optionally `mobile.png` from the bundled capture script.
- `goal` (string): the conversion goal (signup / demo / purchase / waitlist / contact). Drives whether some criteria are N/A.
- `target_user` (string): who the page is for. Drives ICP-specific judgments.
- `language` (string): the report language. The rubric is English; report output follows this.

---

## Procedure

### Step 1: Coverage scoring (per-criterion, OK / Partial / Missing / N/A)

1. Open `assets/lever-checklist-80.md`. The file has 5 dimension tables, 16 criteria each, with Desktop and Mobile columns.
2. For each row, read the criterion text. Decide:
   - **OK** (2 pts): the page clearly satisfies the criterion.
   - **Partial** (1 pt): the page partially satisfies (present but weak, or only on one viewport).
   - **Missing** (0 pts): the page does not satisfy.
   - **N/A** (excluded from denominator): the criterion does not apply to this page (e.g. enterprise pricing on a self-serve page; SSO on a consumer landing page).
3. Score Desktop and Mobile independently. A criterion can be OK on desktop and Missing on mobile (e.g. CTA above fold).
4. Record a one-line note in the Note cell, verbatim from the page when possible.
5. Compute the per-lever score: `(points obtained / applicable points) * 20`. Applicable points = (number of criteria not marked N/A) * 2, multiplied by 2 again because each criterion is scored twice (desktop and mobile). For mobile-irrelevant criteria, score Desktop only and use that as the applicable score.

   Simplified formula: per-lever score = `(sum of points) / (count of OK + Partial + Missing) / 2 * 20`.

6. Sum the 5 lever scores. The total is out of 100.

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

1. Both evaluators score the **first 5 criteria** independently without comparing.
2. Compare. Where scores differ, discuss the criterion text and the page evidence to align.
3. Update shared notes if the criterion definition is ambiguous.

### Independent scoring

4. Both evaluators score all 80 criteria independently. No discussion during scoring.

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
| C5 | Trial end behavior unclear | Partial | 4 | 48 | high | Page says "free trial" but not what happens at day 14 |
| C9 | Annual / monthly toggle missing | Missing | 3 | 27 | high | Only monthly shown; competitors show annual savings |
```

```json
{
  "id": "C5",
  "dimension": "Cost",
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

- Keep this file under 500 lines (Anthropic Agent Skills spec). Extra detail goes into `assets/lever-checklist-80.md` (the rubric data) or `references/cro-frameworks.md` (the multi-framework cross-walk).
- The rubric data is in `assets/lever-checklist-80.md`. Never inline the 80 criteria in this file.
- The agent's `AGENT_LANDING_PAGE_ANALYZER.md` Step 4 is the entry point.
