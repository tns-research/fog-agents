---
name: closing-sprint
description: Closes a growth-sprint. Writes the orchestrator's summary (progress toward the goal from measured numbers only, the five actions of the week, what waits for the founder), generates sprint-report-<YYYYMMDD>.md with scripts/sprint.py report, appends the run line to project memory, proposes decisions from the founder's corrections, and names the growth-pulse experiments that can seed the next sprint. Use at Step 6 of growth-sprint, when the sprint completes or halts. Triggers on "sprint report", "close the sprint", "what did the sprint do", "next sprint".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# closing-sprint

The script writes the facts; the orchestrator writes a short summary on top. A halted sprint gets a report too.

## 1. The summary

Write `<dir>/summary.md` from [`../../assets/output-template.md`](../../assets/output-template.md):

- **Toward the goal.** Only measured numbers: the growth-pulse report of the sprint, or counts read from the step outputs (people listed, posts queued, ads packaged). No estimate of the effect, no "should bring". A complete sprint means its deliverables are verified on disk, not that the target was reached: agents send nothing, so name what the founder has to send and count.
- **This week's five actions** for the founder, in order, each with its file or command: approve the queued posts, import the ads PAUSED, send the sequence, answer a spend gate.
- **Waiting for you**: the open needs_human items, one line each.
- **Decided without you**: the defaults the agents took that change what the founder sees (a direction, an angle, a slot).

Run the writing gate on it:

```bash
python3 shared/skills/writing-gate/scripts/lint_copy.py --project <project> <dir>/summary.md
```

0 BLOCK, three passes at most. Claims follow [`../../../../shared/skills/enforcing-claims-policy/SKILL.md`](../../../../shared/skills/enforcing-claims-policy/SKILL.md).

## 2. The report and the run line

```bash
python3 agents/growth-sprint/scripts/sprint.py report <dir> --summary <dir>/summary.md --log
```

Writes `sprint-report-<YYYYMMDD>.md` (summary, steps with status, attempts, spend and verified outputs, needs_human open and resolved, defaults, breaker and interruptions, next sprint input) and appends one line to `project-context/memory/runs.jsonl`: `ok` when complete with nothing waiting, `partial` when items wait or the sprint did not finish, `failed` when the failures breaker halted it. The line is validated against [`../../../../shared/schemas/run-record.schema.json`](../../../../shared/schemas/run-record.schema.json) before it is written.

## 3. Decisions

Follow the last step of [`../../../../shared/skills/keeping-project-memory/SKILL.md`](../../../../shared/skills/keeping-project-memory/SKILL.md). Typical corrections in a sprint: a step the founder skipped ("never run seo-audit in a launch sprint"), a budget raised or refused, a post rejected, an input supplied that should become a default. Drafts go in the report; without an answer they are written `Status: proposed`.

## 4. The next sprint

When the sprint produced `growth-pulse/experiments-<YYYYMMDD>.json`, the report names it. The next sprint's goal is one of its experiments: `goal.source` = `growth-pulse/experiments-<YYYYMMDD>.json#<experiment id>` ([`../planning-sprint/SKILL.md`](../planning-sprint/SKILL.md), section 2). Without growth-pulse in the sprint, say so and suggest it as the last step of the next one.
