---
name: running-sprint
description: Runs an approved growth-sprint inside the open harness session, without asking the founder again until only a person can move it; closing the session stops it and sprint.py resume restarts it. Starts waves of up to three steps with sprint.py next --claim, hands each step brief to a fresh worker (the host's subagent tool, a second CLI session) or runs the briefs in sequence in the same session, settles every step from the disk with sprint.py mark done (outputs fresh and valid against their schemas, never the worker's word), routes spend gates, publication approvals and missing inputs to the needs_human queue while independent steps continue, honours the STOP file and the circuit breaker, and resumes after an interruption from state.json. Use at Steps 4 and 5 of growth-sprint, and whenever someone restarts a sprint, by hand or on a schedule they set up. Triggers on "run the sprint", "continue the sprint", "resume", "what is blocked".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# running-sprint

The orchestrator decides nothing the scripts can decide. It starts steps, passes briefs, and asks the disk how each one ended.

All of this happens in the open session: the model starts one subagent per step or runs them in sequence. When the session closes, the sprint stops. Nothing runs in the background; `sprint.py resume` restarts it in the next session ([`../../../../shared/scheduling.md`](../../../../shared/scheduling.md) for a restart on a schedule).

All commands run from the repo root; `<dir>` is `<project>/growth-sprint/<sprint id>`.

## The loop

```bash
python3 agents/growth-sprint/scripts/sprint.py resume <dir>          # always first: settles what an interruption left running
python3 agents/growth-sprint/scripts/sprint.py next <dir> --claim    # starts a wave, writes briefs/<step>.md
# run each brief (below), then for each step of the wave:
python3 agents/growth-sprint/scripts/sprint.py mark <dir> <step> done
# repeat next --claim until it exits 5, 3 or 6
```

| `next` exit | Meaning | What the orchestrator does |
|-------------|---------|----------------------------|
| 0 | a wave started (`STARTED <step> <agent> brief <path>`) | run the briefs |
| 4 | no approval for this version of `sprint.json`, or an approval in `state.json` whose seal does not verify (written by hand) | stop, hand `approval.md` to the founder; never edit `state.json` |
| 3 | halted: STOP file or circuit breaker | stop, report the reason (`sprint.py status`) |
| 5 | only a person (needs_human) or running steps can move the sprint | finish running steps; then stop and hand over the queue |
| 6 | every step done or skipped | go to closing-sprint |

`next` also takes the automatic decisions before it picks a wave: a step whose outputs are recent enough is skipped (`reuse_if_fresh_days`), a step missing a required input and a spending step whose estimate no longer fits the budget left go to needs_human. The rest keeps going.

A wave holds at most 3 steps (`--max`, or `max_wave` in the plan), never two steps of the same agent, and content-publisher always alone (it writes the shared `queue.json`).

## Running a brief

Each `briefs/<step>.md` is self-contained: the agent's workflow file, the project folder, the label, the inputs, the rules, the expected outputs and the done check. Three ways to run it, same contract:

1. **Fresh worker** (capability `subagents`, built-in): one per brief, started with the brief only, up to three at once. Wait for all of them.
2. **Second CLI session** (local): the brief on stdin of a blank session of any model CLI, one process per brief.
3. **In sequence** (always available): `next --claim --max 1`, then the orchestrator follows the brief itself, then `mark`, then the next one.

A step that would ask the founder a question is not a reason to keep it out of a worker: the brief tells the agent to run in its Autonomous mode, use its defaults and list any gate as a pending item. The worker's last act is the result file `results/<step>.json` ([`../../assets/step-result.schema.json`](../../assets/step-result.schema.json)): status, cash spent, pending items, defaults used.

## Settling a step: the disk decides

```bash
python3 agents/growth-sprint/scripts/sprint.py mark <dir> <step> done [--spent <EUR>]
```

`mark done` runs the same verification as `python3 agents/growth-sprint/scripts/check_step.py --sprint <dir> --step <step>`:

- every required output of the registry exists, was modified after the step first started, and passes its check (JSON Schema, JSONL, CSV columns, non-empty file);
- no human gate waits on disk (content-publisher items still `to_review`);
- the result file (if any, written after this attempt started) lists no pending item and does not say failed; the agent's run line does not say failed.

| Verdict | Exit | State |
|---------|------|-------|
| done | 0 | `done`, outputs recorded, defaults recorded |
| needs_human | 5 | `needs_human`, one item per gate or pending entry, with how to clear it |
| failed | 1 | back to `pending` for one retry; the second failure in a row sets `failed` and trips the breaker (exit 3) |

A worker that says "done" with nothing on disk is a failure. The result file can only send a step to a person or record a spend: it never makes a step done.

`--spent` (or `spent_eur` in the result file) adds to the sprint's spend. That figure is what the step reports, from an invoice or an estimate; nothing measures it, and search and scrape credits are not counted. At 80 % of the approved cap the state records an alert; above the cap the breaker trips and nothing more starts. The hard stop on a paid call is the paid script itself, which refuses to run without `--confirm-spend` or `FOG_ALLOW_SPEND=1`.

## needs_human: what only a person clears

| Kind | Comes from | Cleared by |
|------|-----------|-----------|
| `spend` | an agent spend gate: static-ads-builder Gate 1 and Gate 2, a seo-audit paid call | the founder answers in a session of that agent, then `resolve` (the step reruns) |
| `publish` | content-publisher items `to_review` | the founder runs `pubqueue.py approve` (or `reject`) in their own terminal; `resolve` refuses while any item is still `to_review`; the step reruns to schedule |
| `input` | a required input missing from the plan and the project | `resolve <H-id> --by <name> --set <input>=<value>` |
| `budget` | a spending step whose estimate does not fit what is left | a new plan with a higher cap, approved; then `resolve`; or `--then skip` |
| `other` | a run ended partial without its outputs | the founder reads the agent report and decides |

```bash
python3 agents/growth-sprint/scripts/sprint.py status <dir>                          # the queue, with the how of each item
python3 agents/growth-sprint/scripts/sprint.py resolve <dir> H-03 --by <person> [--then rerun|done|skip]
```

`resolve` needs a person's name (agent and tool names are refused). The orchestrator never runs it on the founder's behalf, never runs `pubqueue.py approve`, never answers an agent's spend gate. It lists the open items, with their `how`, at the end of its turn.

## Breaker, STOP, interruption

- **STOP file** (`<dir>/STOP` or `<project>/growth-sprint/STOP`): `next` and `mark running` refuse while it exists; steps already running may still be settled. Removing it resumes.
- **Two failures in a row on a step**: `failed`, sprint halted. The founder runs `sprint.py resume <dir> --by <name> --retry <step>` or `--skip <step>`.
- **Reported spend above the approved cap**: halted. The founder raises `budget.cap_eur` in `sprint.json`; `packet`; approve. `resume` alone never clears it.
- **Interruption** (session closed, machine rebooted): `sprint.py resume <dir>` settles every `running` step from the disk: valid outputs make it done (or needs_human), nothing valid puts it back to `pending` without counting a failure.
- **Plan edited after approval**: every command that moves a step exits 4 until the founder approves the new version in their own terminal.

## End of a session

Before handing back: `sprint.py status <dir>`, then tell the founder in a few lines what finished, what runs next, and each open needs_human item with its command. When `next` exits 6, load [`../closing-sprint/SKILL.md`](../closing-sprint/SKILL.md).
