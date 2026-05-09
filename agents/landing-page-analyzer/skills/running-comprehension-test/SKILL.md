---
name: running-comprehension-test
description: Runs the 10-second comprehension test on a landing page using the rendered screenshot as stimulus, never a mock. Scores three questions (what does this do, who is it for, what should I do) on a 1 to 5 rubric, assigns confidence, and produces a verdict (pass / partial / fail) plus a short narrative. Triggers on "10-second test", "5-second test", "first impression", "comprehension test", "clarity test".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read
---

# running-comprehension-test

Methodology for the 10-second comprehension test on a landing page. The test simulates a first-time visitor who lands on the page, reads only the first viewport, and is then asked three questions:

1. **What does this product do?**
2. **Who is it for?**
3. **What should I do next?**

A page that fails any of the three is a Comprehension fail in the LEVER scorecard, regardless of how strong the rest of the page is. Visitors who do not understand the offer in 10 seconds bounce.

This skill produces the `## 10-second comprehension test` block in the report.

---

## When to invoke

The agent's `AGENT_LANDING_PAGE_ANALYZER.md` workflow points here at Step 3, before the LEVER rubric. Running the test first anchors the rest of the audit: a page that fails the comprehension test will have low Comprehension scores in the rubric, but this gives a sharper, more communicable headline finding.

---

## Inputs

- `desktop.png` (file path): the rendered desktop screenshot from `scripts/capture-page.py`. **Required.** Stimulus must be the actual rendered page, never a mock.
- `mobile.png` (file path, optional): the rendered mobile screenshot. If present, run the test twice (once per viewport).
- `markdown` (string, optional): the full page content. Used only when a question score is borderline; the test is primarily visual.
- `target_user` (string): who the page is for. Used to evaluate question 2.

---

## The three questions and the rubric

### Q1: What does this product do?

The visitor reads the H1, supporting subhead, and any visible hero copy. Then says, in one sentence, what the product does.

| Score | Definition |
|------:|------------|
| 5 | The visitor's sentence matches the founder's intended description, plain language, no jargon |
| 4 | The sentence is mostly correct, missing one nuance |
| 3 | The sentence captures category but not specific function ("some kind of CRM thing") |
| 2 | The sentence is wrong but in the right space ("I think this is a marketing tool") |
| 1 | The visitor cannot say anything meaningful ("I don't know what this is") |

How to score in practice. Read the H1 plus first paragraph plus any visible body text. Try to articulate what the product does without reading any further. Score against the rubric.

### Q2: Who is it for?

The visitor identifies the target audience.

| Score | Definition |
|------:|------------|
| 5 | The visitor names the role / vertical / company size matching the founder's ICP |
| 4 | The visitor names a broad audience that includes the ICP ("for sales teams") |
| 3 | The visitor identifies a vague segment ("for businesses") |
| 2 | The visitor cannot identify a specific audience |
| 1 | The visitor reads it as for "anyone" or as ambiguous |

How to score. Look at the hero. Is there an explicit role, vertical, or pain mentioned? "For Series A SaaS founders" scores 5. "For modern teams" scores 2.

### Q3: What should I do next?

The visitor identifies the primary action the page wants them to take.

| Score | Definition |
|------:|------------|
| 5 | The visitor names the exact action ("start a free trial", "book a demo") and the action is one tap away |
| 4 | The visitor names the right action but it is not clearly the primary (multiple equal-weight CTAs) |
| 3 | The visitor names a possible action but is unsure ("maybe sign up?") |
| 2 | The visitor cannot identify a clear next step |
| 1 | The visitor sees no CTA or sees CTAs that contradict each other |

How to score. Identify all CTAs visible in the first viewport. Is there one clearly dominant primary CTA? What does its copy say? Is the action low-cost (free, no card) or high-cost (15-min call)?

---

## Procedure

### Step 1: Set up the stimulus

1. Open `desktop.png`. Crop or zoom to the first viewport (1280 x 900 default).
2. If `mobile.png` is present, also crop to the first mobile viewport (390 x 844 default).
3. **Do not** read the markdown yet. The test is a visual first-impression check.

### Step 2: Score Q1

4. Read only what is visible in the first viewport: H1, subhead, hero copy, any callouts.
5. Articulate in one sentence what the product does. Write it down.
6. Compare to the founder's intended description (from `goal` and `target_user` inputs).
7. Score 1 to 5 per the rubric.
8. Note one specific phrase from the page that helped or hurt the score.

### Step 3: Score Q2

9. Without scrolling, identify any reference to a specific audience.
10. Score 1 to 5 per the rubric.
11. Note the phrase that named the audience, or the absence of it.

### Step 4: Score Q3

12. Identify all CTAs in the first viewport. Note their copy and visual weight.
13. Determine the primary CTA (most visually dominant).
14. Read the CTA copy. Is it action-led ("Start free trial", "Book 15-min demo") or generic ("Submit", "Get Started", "Learn More")?
15. Score 1 to 5 per the rubric.

### Step 5: Verdict

| Total (out of 15) | Verdict |
|------------------:|---------|
| 13 to 15 | **Pass.** The page communicates clearly. Comprehension is not the binding constraint. |
| 9 to 12 | **Partial.** One question scored 3 or below. Fix the weakest first. |
| 5 to 8 | **Fail.** Two or more questions scored 3 or below. Comprehension is the binding constraint. |
| 3 to 4 | **Critical fail.** All three questions scored low. The page communicates almost nothing in the first viewport. |

### Step 6: Confidence

Assign confidence per question:

- **High**: the screenshot clearly shows the answer (or its absence).
- **Med**: the screenshot is partially obscured (cookie banner, lazy-loaded images), and the markdown supplements.
- **Low**: only markdown is available (no screenshot). Note this in the report.

### Step 7: Run the mobile pass (if `mobile.png` is present)

Repeat steps 2 to 6 on the mobile viewport. Report mobile and desktop scores separately. The mobile score is often lower because the first viewport is shorter and contains less copy.

---

## Output

```markdown
## 10-second comprehension test

| # | Question | Desktop (1-5) | Mobile (1-5) | Confidence |
|---|----------|--------------:|-------------:|-----------|
| 1 | What does this product do? | 4 | 3 | high |
| 2 | Who is it for? | 3 | 2 | high |
| 3 | What should I do next? | 5 | 4 | high |
| Total | | 12 / 15 | 9 / 15 | |

**Verdict (desktop):** Partial.
**Verdict (mobile):** Partial, leaning Fail.
**Why:** The H1 names the category but not the specific outcome. The audience is implied ("modern teams") but not named. The primary CTA is clear on desktop but competes with two secondary CTAs on mobile.
**Stimulus:** `screenshots-<YYYYMMDD>/desktop.png`, `screenshots-<YYYYMMDD>/mobile.png`. Not a mock.
```

---

## Failure modes

- **No screenshot available.** Run from markdown only; mark confidence as `low`. The test loses most of its value because the first-impression heuristic is visual. Document in the report's Limitations.
- **Hero is a video that did not capture.** The screenshot shows the poster frame. Score on the poster; note that a moving video may communicate more or less than the still.
- **Cookie banner blocks the first viewport.** Re-run the capture script (cookie dismissal should handle it). If the banner persists, ask the user for a manual screenshot.
- **The page is multi-language and the rendered language differs from the audit language.** Flag explicitly. Run the test in the rendered language.

---

## Variants

This skill implements the 10-second test by default. Two related variants:

- **5-second test (Wiebe / Peep Laja)**: shorter exposure. Use when the page is dense or when the first impression matters disproportionately (paid traffic landing pages). Same three questions, harder rubric (Q1 score 5 only if the visitor nails it in 5 seconds).
- **First-impression test (NN/g)**: open-ended ("what is your reaction?"). Useful for redesign discussions but harder to score, so out of default scope.

The agent runs the 10-second test by default. The user can request the 5-second variant explicitly.

---

## Notes

- The test is a heuristic with one human evaluator (the agent). It is not a substitute for usertesting.com or Wynter, which run real visitors. When the audit needs validation, recommend a 5-respondent test on the live page in the report's Recommendations.
- Keep the test inputs lean: H1, subhead, hero copy, primary CTA. If the agent finds itself reading paragraph 4 to score Q1, the test has already failed, and the audit should reflect that.
