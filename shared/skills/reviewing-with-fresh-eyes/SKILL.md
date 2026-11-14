---
name: reviewing-with-fresh-eyes
description: Bounded critique of a finished deliverable by a reviewer who did not produce it. The reviewer gets the brief verbatim, the agent's rules and rubric, the mechanical check results and the deliverable, never the producer's reasoning. It returns a PASS/FAIL verdict per written constraint, a 0-2 score per rubric criterion, and located problems with a proposed fix, without rewriting. The producer revises once. Runs on a fresh subagent when the harness has one, otherwise in a blank session or a second model CLI, otherwise as a guided human review. Use as the last step before delivery of any agent report, copy set or creative. Triggers on "review this", "second opinion", "critique", "fresh eyes".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
---

# reviewing-with-fresh-eyes

The session that wrote a deliverable is the worst judge of it: it remembers what it meant, so it reads what it meant. A reviewer with the same rules and none of the memory reads what is on the page. This skill sets up that reviewer, bounds what it may do, and caps the exchange at one critique and one revision.

Capability used: `critic` (see [`../../tools.md`](../../tools.md#critic-a-reviewer-that-did-not-produce-the-work)).

---

## When to run

Once per deliverable, after the mechanical gates passed (writing gate at 0 BLOCK, schema validation, render review), and before the founder sees it. Mechanical gates run first because a critic should spend its attention on what no script can check.

## 1. Build the critique packet

Write one file, `review/critique-packet.md` in the run's output folder, holding in this order:

1. **The brief, verbatim**: the founder's request for this run and the resolved inputs (Step 0 block).
2. **The rules, resolved and inlined**: the agent's constraints from its `AGENT_<NAME>.md` (Output, Failure modes, any hard rule), the claims policy, the project's `memory/decisions.md` entries that apply, `voice` rules. Inline the text; a rule the reviewer cannot read is a rule it cannot check.
3. **The rubric**: `agents/<name>/assets/review-rubric.md` of the running agent, or the default rubric below.
4. **The mechanical results**: writing gate JSON, schema validation output, `render-review.md`, claims ledger.
5. **The deliverable**: the full files, or for images the contact sheet plus the spec.

Never include the producer's reasoning, drafts, plan notes or chat. Context parity means the same rules, not the same thoughts.

## 2. Pick the reviewer

Take the first available, top down. Say which one ran in the report.

| Order | Reviewer | How |
|-------|----------|-----|
| 1 | Fresh subagent of the harness | Start a subagent whose only input is the packet and the reviewer prompt below. It must not inherit the producing conversation. |
| 2 | Blank session or second model | A new session of the same tool started from the packet, or a model CLI that reads the prompt on stdin: `claude -p < prompt.md`, `codex exec - < prompt.md`, `gemini -p "$(cat prompt.md)"` (stdin when the prompt is large). Read-only: the reviewer writes its critique to stdout, the agent saves it. |
| 3 | Guided human review | The founder (or a teammate) gets the packet's deliverable and the rubric as a short form: one question per constraint, one 0-2 score per criterion, "point at anything wrong". |

A second pass by the producing session is not a fresh-eyes review. When none of the three is available (unattended run, no subagent, no CLI), write "Fresh-eyes review: not run" in the report and list the deliverable as unreviewed.

## 3. Reviewer prompt

Save as `review/critique-prompt.md`, then append the packet:

<!-- writing-gate: off -->
```text
You review a deliverable you did not write. You hold the brief, the rules, the
rubric, the mechanical check results and the deliverable. Judge only against
them. Do not rewrite the deliverable and do not add scope.

Return exactly four sections:

1. Constraints. One line per written constraint in the brief and the rules:
   PASS or FAIL, then a one-line reason with the location (file, section,
   slide, line). Quote the offending words for every FAIL.
2. Rubric. One line per criterion: score 0, 1 or 2, then the evidence that
   justifies it (a short quote or a location).
3. Problems. A numbered list of located problems not covered above, each with
   a proposed fix in one sentence. Fixes describe the change; they do not
   rewrite the passage.
4. Verdict. PASS when no constraint FAILs, no criterion scores 0 and the
   rubric total reaches the threshold; otherwise FAIL, with the 3 changes
   that matter most.
```
<!-- writing-gate: on -->

## 4. Default rubric

Use the agent's own `agents/<name>/assets/review-rubric.md` when it exists (same format: criteria scored 0 to 2, a threshold, a floor). Otherwise:

| # | Criterion | 0 | 1 | 2 |
|---|-----------|---|---|---|
| 1 | Brief fit | misses the ask or answers another question | answers it with gaps | answers exactly what was asked |
| 2 | Evidence | a claim without source, an invented fact | sources present but thin | every claim traced (claims ledger, URLs) |
| 3 | Reader value | the reader cannot act on it | one clear next action | each section leads to a decision or an action |
| 4 | Voice and form | reads generated, breaks voice rules | minor tics | in the founder's voice, no tic |
| 5 | Craft | layout or structure broken | usable | finished, nothing to clean up |

Threshold 8/10, floor 1 on every criterion (any 0 fails).

## 5. Settle and revise once

For each FAIL and each problem, the producer decides on the highest rung available:

1. **Hard check**: a script, a validator, a count. A failing check gets fixed; opinion does not override it.
2. **Written constraint**: a FAIL against a rule in the packet gets fixed.
3. **Reasoned taste**: a taste-only point may be declined, with the reason written down.

Then the producer revises **once**. No second critique. The exception: when the revision touches something a hard check covers, re-run that check (not the critic) until it passes, within the agent's own round cap.

## 6. Record it

Save the critique as `review/critique.md`. End the report with a role log:

```text
fresh-eyes: reviewer=<subagent | blank session | <model> CLI | founder | not run>
verdict: <PASS | FAIL> (constraints <n> PASS / <n> FAIL, rubric <n>/10)
settled by: <hard check | written constraint | reasoned taste> per point
changed: <one line on what the revision changed, or "nothing, deliverable held">
```

Copy the verdict into the run log (`critic_verdict`, see [`../keeping-project-memory/SKILL.md`](../keeping-project-memory/SKILL.md)). When the critique exposed a rule the founder should own (a recurring mistake), propose it as a decision in that same step.

---

## Failure modes

- **The reviewer rewrites the deliverable** → keep only its verdicts and located problems; discard the rewrite.
- **The reviewer invents a constraint** that is not in the packet → reasoned-taste rung at most; it never blocks.
- **Reviewer output unusable** (empty, off-format, a CLI that exited 0 without output) → check the saved file on disk, not the exit message; retry once with the next reviewer in the table, then mark "not run".
- **Critique and founder disagree later** → the founder wins; record the decision.
