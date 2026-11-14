---
name: extracting-psychographic-profile
description: Completes the market-signal analysis spec (analysis.json) on top of the labelled corpus. Picks quotes by record id and exact passage (never retyped), builds the persona with STP and JTBD Forces of Progress as lists of quote ids, anti-personas, hooks (verbatim or flagged analyst lines), objections in the buyer's words, angles ready for the copy agents (pain, force, awareness stage, funnel stage, headline quote, support quotes, contrast, formats), alternatives named, rejected pains and recommendations each with the observation that would prove it wrong. verify_quotes.py checks every quote against the corpus and the window; build_handoff.py turns the spec into the sidecar and the report. Use at Step 4. Triggers on "persona", "JTBD", "STP", "hooks", "angles", "objections", "marketing copy from quotes".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# extracting-psychographic-profile

The model writes judgement as references; scripts attach the text, the counts and the proof. Inputs: `corpus.jsonl`, `labels.jsonl`, `stats.json`, the `pains` already in `analysis.json`, project-context (`offer.core`, `icp.who` constrain the target), [`../../references/marketing-frameworks.md`](../../references/marketing-frameworks.md), [`../../references/buyer-psychology.md`](../../references/buyer-psychology.md), [`../../assets/jtbd-forces-of-progress.md`](../../assets/jtbd-forces-of-progress.md), [`../../assets/quote-scoring-rubric.md`](../../assets/quote-scoring-rubric.md).

Schema of everything below: [`../../assets/analysis.schema.json`](../../assets/analysis.schema.json). Worked example: [`../../examples/swanbase-preseed-fundraising-20261012/runs/20261012/analysis.json`](../../examples/swanbase-preseed-fundraising-20261012/runs/20261012/analysis.json).

## Step A. Quotes by reference

Each quote is `{quote_id, record_id, passage, pain_id, persona_id, usable_as}`.

- `passage` is copied from the record's text: contiguous, same case, same punctuation, same typos. Whitespace and curly versus straight quote marks are the only tolerated differences.
- No ellipsis, no `[...]`, no added capital letter: a long post becomes several quotes.
- Pick with [`../../assets/quote-scoring-rubric.md`](../../assets/quote-scoring-rubric.md): voices (`user`, `practitioner`) first, specific over generic, one quote per idea, several authors per escalated pain rather than several quotes of one author.
- `usable_as`: `headline` (short, says the pain alone), `support`, `hook`, `objection`, `outreach_opener`, `quote_slide`.

Check, and loop until it passes (three rounds at most, then drop the quote):

```bash
python3 scripts/verify_quotes.py --corpus <run>/corpus.jsonl --quotes <run>/analysis.json
```

BLOCK codes and what to do: `not-found` or `case-changed` (copy the passage again from the record), `elided` (split it), `out-of-window` or `no-date` (another record), `record-not-in-corpus` or `no-record` (the line has no source: drop it).

## Step B. Segment and target (STP)

Read the labelled voices by role, journey stage, sophistication, stakes and language. Pick the primary target where escalated pains are strongest, alternatives are weakest, and the offer plausibly fits. Write it as a persona:

- `name`: a descriptive title ("First-time founder raising a first round without investor connections"), never a made-up person, no invented age or demographics.
- `context`: role, stage, where they talk, in plain words, no number.
- `pain_ids`, `hook_ids`.
- `jtbd_forces`: `push`, `pull`, `anxiety`, `habit` as lists of quote ids. A force with no quote stays an empty list: the report prints "absent in this corpus", which is a finding (strong Habit with weak Push usually means the wrong segment).
- `anti_personas`: who this is not for, with the quote that shows it.

## Step C. Hooks and objections

- Hook: `{hook_id, text, verbatim, pain_id, quote_ids}`. `verbatim: true` when the text is a contiguous part of one of its quotes (checked). A question the analyst writes from several quotes is allowed with `verbatim: false`: consumers treat it as their own copy and pass it through their claims gate.
- Objection: `{objection_id, text, force, pain_id, quote_ids}`, the text a contiguous part of a cited quote (checked), force `anxiety` or `habit`.

## Step D. Angles for the copy agents

One angle per message worth testing: `{angle_id, pain_id, force, awareness_stage, funnel_stage, headline_quote_id, support_quote_ids, contrast, formats, why}`.

| Funnel stage | Awareness | Typical angle |
|--------------|-----------|---------------|
| `tofu` | `unaware`, `problem_aware` | the pain in the persona's words, no product |
| `mofu` | `problem_aware`, `solution_aware` | how people solve it today and where that breaks (contrast) |
| `bofu` | `solution_aware`, `product_aware` | the condition that makes a solution work, objections answered |

`formats`: `carousel`, `static_ad`, `cold_outreach`, `landing_page`. Lead with escalated pains; an angle on a weak pain is allowed and the sidecar marks it (`pain_escalated: false`).

## Step E. The rest of the spec

- `summary`: three or four sentences, the sharpest finding first, no number (the report prints the computed ones next to it).
- `existing_solutions`: alternatives named, `direct`, `indirect` or `status_quo`, with quote ids; counts come from the labels.
- `rejected_pains`: what was looked for or looked similar and was not kept, with the reason.
- `recommendations`: action, `falsified_if` (the observation that would prove it wrong), quote ids; a number only with `source_urls`. No claim about the founder's product beyond `positioning.proof` ([`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md)).
- `limitations`: what the corpus cannot show, no number.

## Anti-patterns to refuse

- Retyping a quote, smoothing it, fixing its typo, translating it in place.
- A persona line, hook or headline with no quote id behind it.
- A percentage or a count in the prose: `build_handoff.py` refuses it.
- Presenting a quote as a testimonial of the founder's product, or attaching it to a company or a face.

## Output

The complete `analysis.json`. Next: `python3 scripts/build_handoff.py --run <run>` (Step 6 of the agent), after `diff_runs.py` in watch mode.
