# Example checklist (rubric data)

This is the data file the `example-checklist-audit` skill operates on. It's a flat list of heuristics that the skill walks through one at a time.

Replace this file's content when you fork the template. Keep the table structure.

---

| # | Dimension | Criterion | Weight (1-5) | Mobile-applicable | Notes |
|---|-----------|-----------|-------------:|-------------------|-------|
| 1 | Comprehension | Above-fold copy answers "what is this and who is it for" in plain language | 5 | yes | Test by reading H1 + first paragraph in 10 seconds |
| 2 | Comprehension | No jargon without definition in the first viewport | 4 | yes |: |
| 3 | Trust | Recognizable customer logos or testimonials with name + role | 4 | yes | Anonymous testimonials count for less |
| 4 | Trust | Verifiable third-party signal (G2, Trustpilot, press mention) | 3 | yes |: |
| 5 | Usability | Primary CTA visible without scrolling on 375px wide viewport | 5 | yes | Critical for mobile conversion |
| 6 | Usability | Tap targets ≥ 44px × 44px with ≥ 8px spacing | 4 | yes |: |
| 7 | Motivation | One specific outcome metric in the hero (e.g. "save 6 hours/week") | 5 | yes | Beats abstract value props |
| 8 | Cost | Pricing visible or "free to start" on the same page | 3 | yes | Hidden pricing increases friction |

---

**Format notes**:

- Each heuristic has a stable `#` ID. Do not renumber when adding rows; append.
- `Weight` is the importance multiplier when computing the dimension score.
- `Mobile-applicable` flags whether the heuristic should be evaluated on the mobile viewport too.
- `Notes` field is for human context, ignored by the scoring rubric.

For deeper rubrics (50+ heuristics), keep the same column shape and split by dimension into separate files (e.g. `comprehension-heuristics.md`, `trust-heuristics.md`).
