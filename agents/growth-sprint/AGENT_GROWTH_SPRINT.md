---
name: growth-sprint
description: Orchestrates the other agents of the stack toward one goal the founder states and tracks ("15 first conversations this month", "launch the pricing page"). Agents prepare prospects, sequences, visuals and queue items and never book or send anything, so the sprint's own success is its deliverables on disk. Reads project-context and the project memory, writes a sprint plan (sprint.json) that chains agents through their handoff files, with a budget cap on cash spent on optional paid APIs from the founder's own accounts (image-model photo backgrounds, paid SERP calls, paid GEO panel runs; default 0; never ad spend, no payment by the agent), and asks for one human approval only, on the plan, the budget and the list of steps that spend money or publish. Then it runs inside the open harness session, where closing the session stops it and sprint.py resume restarts it: waves of up to three steps through fresh subagents or in sequence in the same session, each step ending on a disk check of its outputs against their schemas (never on the model's word), a needs_human queue for what only a person can decide (a spend gate, a publication approval, a missing input, spend beyond the approved budget) that never blocks independent steps, a circuit breaker (reported spend above the cap, two failures in a row on a step, a STOP file), resume after an interruption from state.json, and a sprint report whose growth-pulse experiments seed the next sprint. The spend gates of static-ads-builder and the human approval of content-publisher stay with the founder; the sprint only surfaces them.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Growth Sprint Agent

The layer above the other agents. The founder gives a goal; this agent turns it into a bounded plan of agent runs, gets one yes, then chains the runs inside the open session until only a person can move the sprint. Same rule as the rest of the stack: **the model writes a spec (`sprint.json`), a script checks it and keeps the state, a check on disk says when each step is done.** Two more on top: **one human approval for the whole sprint, and nothing it approves replaces an agent's own spend or publication gate.**

Agents never call each other: they read each other's files ([`../../shared/handoffs.md`](../../shared/handoffs.md)). This agent only decides the order, starts each run with a brief, and reads what landed on disk.

## What a sprint is

- **The goal is a target the founder tracks.** Agents do not book calls and do not send anything. They prepare prospects, sequences, visuals and queue items; a person sends, approves each post and counts the results. The sprint's own success is its deliverables on disk. Never report the target as reached unless a measured number says so.
- **The budget is the cap of cash spent on optional paid APIs from the founder's own accounts**: in this stack, image-model photo backgrounds, paid SERP calls and the paid runs of the GEO panel (`geo_panel.py run`). Default 0. It is never ad spend. The agent has no card and pays for nothing.
- **Steps report their spend themselves** (an invoice or an estimate, through `--spent` or `spent_eur`); nothing measures it. The hard stop is the paid scripts refusing to run without `--confirm-spend` or `FOG_ALLOW_SPEND=1`. Search and scrape credits are not counted.
- **It runs inside an open harness session**: the model starts one subagent per step, or runs the steps in sequence. Closing the session stops it, `sprint.py resume` restarts it, and nothing runs in the background. For a restart on a schedule, see [`../../shared/scheduling.md`](../../shared/scheduling.md).

## Skills loaded

| Skill | Step | Output |
|-------|------|--------|
| [`skills/planning-sprint/SKILL.md`](skills/planning-sprint/SKILL.md) | 1, 2, 3 | ground truth of the project, `sprint.json` validated, plan review, `approval.md` |
| [`skills/running-sprint/SKILL.md`](skills/running-sprint/SKILL.md) | 4, 5 | waves of steps through subagents or in sequence, disk checks, needs_human queue, breaker, resume |
| [`skills/closing-sprint/SKILL.md`](skills/closing-sprint/SKILL.md) | 6 | `sprint-report-<YYYYMMDD>.md`, run line, proposed decisions, next sprint input |

Shared methodology: [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md), [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md), [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md), [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md), [`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md), [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md).

## Assets used

| Asset | Used by |
|-------|---------|
| [`assets/agents.json`](assets/agents.json) | the registry: per agent, inputs and where they come from, outputs with the check and schema that verify them, spends yes or no, publishes yes or no, human gates, parallel safety ([`assets/agents.schema.json`](assets/agents.schema.json)) |
| [`assets/sprint.schema.json`](assets/sprint.schema.json) | planning-sprint (contract of `sprint.json`), `scripts/sprint.py validate` |
| [`assets/state.schema.json`](assets/state.schema.json) | `scripts/sprint.py` (every write of `state.json` is validated) |
| [`assets/step-result.schema.json`](assets/step-result.schema.json) | running-sprint: the result file each step runner writes last |
| [`assets/review-rubric.md`](assets/review-rubric.md) | the fresh reviewer of the plan (Review) |
| [`assets/output-template.md`](assets/output-template.md) | closing-sprint (the summary the orchestrator writes on top of the script's report) |

## Step 0: context resolution

1. **Project.** Resolve the project slug and the project folder (from the user, or from a path they give). Ask once if ambiguous.
2. **Project context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md): the offer, the ICP, the URL and the language become step inputs; a missing `context.json` means a `project-context` step comes first in the plan.
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md) (Step 0 part): apply the active decisions to the plan (an agent, a channel or a spend the founder refused stays out) and read the last lines of `memory/runs.jsonl` to see what already ran and when.
4. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for the capabilities in Tools below and announce the plan in one block (how steps run: subagents, a second CLI, or in sequence).
5. **Config.** Load `<your-projects-root>/<project>/growth-sprint/config.json`, or copy [`config.example.json`](config.example.json): default budget cap, alert ratio, wave size, approvers, reuse windows.
6. **One message of questions.** Ask every missing input in one message, each with its default (Inputs below). Then plan on the answers or the defaults. After the approval of Step 4, no step stops for an answer: what needs a person goes to the needs_human queue.

## When to run

- You have a goal for the next weeks and want the stack to work toward it without launching agents one by one.
- After a growth-pulse run: pick one of its three experiments as the goal of the next sprint.
- To pick up a sprint that stopped (interruption, needs_human items you just cleared, a STOP file you removed).

**Don't use it for:** a single deliverable (run that agent directly), anything that needs a person at every step, an open-ended loop with no goal (a sprint is bounded by its graph and ends with a report).

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `goal` | yes | an experiment of the newest `growth-pulse/experiments-<YYYYMMDD>.json` when it exists and the founder names none, else asked | The objective in the founder's words, plus how the founder counts it (metric, target, deadline). For example: "15 first conversations with physiotherapists this month, budget 0". |
| `budget_cap_eur` | no | `config.json`, else 0 (no paid call) | Cap of cash spent on optional paid APIs from the founder's own accounts (image-model photo backgrounds, paid SERP calls, paid GEO panel runs), in total. Never ad spend. A spending step whose estimate does not fit waits in needs_human. |
| `deadline` | no | 4 weeks from today | End date of the goal; shapes how many steps fit. |
| `agents_excluded` | no | none, plus the agents an active decision excludes | Agents the founder does not want in this sprint. |
| `inputs` | no | from project-context and each agent's own defaults | Per-agent values (a carousel topic, a video file, the networks to post on). A required one nobody can supply becomes a needs_human item, not a blocker. |
| `max_wave` | no | 3 (config) | Steps in flight at once: 1 to 3. 1 means strictly sequential. |
| `approver` | no | the founder | Who approves the plan. The agent never does, under any name. |

## Tools

Every capability is optional; providers and tiers: [`../../shared/tools.md`](../../shared/tools.md).

| Capability | Used for | Without it |
|------------|----------|------------|
| `subagents` | Step 5: one fresh worker per step brief, up to three at once (the host harness's subagent tool, or a second CLI session with the brief on stdin) | the orchestrator runs each brief itself, one after the other, with `next --claim --max 1`: same briefs, same files, same disk checks; the sprint takes longer |
| `critic` | Step 3: a reviewer that did not write the plan | "Plan review: not run" in the packet; the founder reads the plan with [`assets/review-rubric.md`](assets/review-rubric.md) before approving |
| every capability of the agents it runs | the steps themselves | each agent degrades as its own Tools table says; the sprint records it from the agent's report and run line |

`subagents` is not in the shared catalog yet: its tiers are the host's subagent tool (built-in), a second CLI session (local), and the same session in sequence (always available). Local and free, always needed: Python 3.9+, standard library only.

## Workflow

**Step 1: read the ground.** Load [`skills/planning-sprint/SKILL.md`](skills/planning-sprint/SKILL.md), section Ground truth. List what the project already has: per agent, `python3 scripts/check_step.py --project <project> --agent <name>` reports whether its newest outputs exist and pass their checks; `memory/runs.jsonl` gives their dates; `decisions.md` gives what is ruled out. When the goal comes from growth-pulse, read the experiment (hypothesis, metric, threshold, cost, owner).
Done when: a ground-truth block lists each agent as usable (file, date), stale, or absent, and the goal has a metric.

**Step 2: write the plan.** Same skill, section Plan. Write `<project>/growth-sprint/<sprint id>/sprint.json` against [`assets/sprint.schema.json`](assets/sprint.schema.json): the goal, the budget cap with its basis, and the steps (agent, label, brief, inputs, dependencies, spends, publishes, estimate with its basis, reuse window). Then `python3 scripts/sprint.py validate <sprint dir>`: schema, registry, graph (no cycle, no unknown dependency), flags (an agent that can spend or publish is declared so), estimates within the cap, colliding labels, goal source. Fix the plan until 0 error; read the warnings (a required input nobody has becomes a needs_human item).
Done when: `sprint.py validate` exits 0.

**Step 3: review the plan, write the packet.** A fresh reviewer scores the plan with [`assets/review-rubric.md`](assets/review-rubric.md) (Review below); revise once, validate again. Then `python3 scripts/sprint.py packet <sprint dir>` writes `approval.md`: goal, steps, budget, the steps that spend and those that publish, the agent gates that stay with the founder, the plan fingerprint (no code: only the interactive `approve` prints it).
Done when: `approval.md` exists and carries the fingerprint of the current `sprint.json`.

**Step 4: the one human approval.** Hand `approval.md` to the founder. They approve in their own terminal: `python3 agents/growth-sprint/scripts/sprint.py approve <sprint dir> --by <their name>`. The command refuses to run without an interactive terminal, shows the plan, prints a plan code (an HMAC under the local key `~/.config/fog-agents/approval.key`) and asks the founder to type it; the approval it records is sealed with the same key, so an approval written into `state.json` is refused by `next`. **The agent never runs `approve`, never drives a terminal to answer its prompt, never relays a "yes" by running it, never edits `state.json`.** A change request means: edit `sprint.json`, Step 2 and 3 again, a new approval.

What the gate guarantees: it stops an agent that follows its workflow and any manual edit of `state.json`. It is not a sandbox: an agent with an unrestricted shell under your user can read the key or drive a terminal. For a strong guarantee, do not give the agent the keys of the paid or publishing providers, or run `approve` from another session the agent cannot reach.
Done when: `python3 scripts/sprint.py status <sprint dir>` shows the sprint approved for the current plan.

**Step 5: run the sprint.** Load [`skills/running-sprint/SKILL.md`](skills/running-sprint/SKILL.md). This loop lives in the open session: when the session closes it stops, and `sprint.py resume` restarts it. Loop: `sprint.py next <sprint dir> --claim` starts a wave (up to 3 steps, never two of one agent, content-publisher alone) and writes one brief per step; each brief goes to a fresh worker, or is run in sequence by the orchestrator; when a worker returns, `sprint.py mark <sprint dir> <step> done` settles the step from the disk (outputs fresh and valid: done; a gate or a pending item: needs_human; else a failure, retried once). Exit 5 means only a person can move the sprint now: hand over the needs_human queue and end the session. Exit 3 means halted (STOP file or breaker): report and end. After any interruption, start with `sprint.py resume`.
Done when: `sprint.py next` exits 6 (complete), or exits 5 or 3 with the queue or the halt reason handed to the founder.

**Step 6: close.** Load [`skills/closing-sprint/SKILL.md`](skills/closing-sprint/SKILL.md). Write the summary from [`assets/output-template.md`](assets/output-template.md) (what moved toward the goal, the week's five actions, what waits for the founder), then `python3 scripts/sprint.py report <sprint dir> --summary <summary.md> --log` writes `sprint-report-<YYYYMMDD>.md` and appends the run line to project memory. Propose decisions for every correction the founder made during the sprint.
Done when: the report exists, the run line validates, and the next sprint input (growth-pulse experiments) is named or its absence said.

## Checks before delivery

1. **Writing gate** on the summary the orchestrator writes: `python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --project <project> <summary.md>`, 0 BLOCK, 3 passes at most; without Python, "Writing gate: manual". The agents' deliverables pass their own gates inside their runs.
2. **Claims check** with [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md) on the summary: progress toward the goal is stated from the growth-pulse numbers or the step outputs, never estimated.
3. **Schema check**: `sprint.json` through `sprint.py validate`; every write of `state.json` is validated by the script; each step's outputs by `python3 scripts/check_step.py --sprint <sprint dir> --step <id>` (the same check `mark done` runs).
4. **Render review**: does not apply, the agent renders nothing; the producing agents review their own renders.
5. **Fresh-eyes review** of the plan, see Review.
6. **Run log and decisions**: `sprint.py report --log` writes the line and validates it against [`../../shared/schemas/run-record.schema.json`](../../shared/schemas/run-record.schema.json); then `python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl`.

## Review

- **Rubric**: [`assets/review-rubric.md`](assets/review-rubric.md) (goal measurable, steps serve the goal, handoffs used, budget and its basis, spend and publication visible, parallelism, size; 0 to 2 each).
- **Reviewer**: a fresh subagent, else a blank session or a second model CLI, else the founder (the `critic` capability of [`../../shared/tools.md`](../../shared/tools.md)) with [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md). It reads the goal, the ground-truth block, `sprint.json`, the validate output and the registry, never the planner's reasoning.
- **Bounds**: one critique, one revision through `sprint.json` and `sprint.py validate`; a script check outranks a written constraint, which outranks taste. The review never replaces the founder's approval.

## Autonomous mode

- Before the approval, every input has a default (Inputs); after it, nothing waits for an answer except the needs_human items.
- The run stops at the **plan approval** (Step 4): without it, `sprint.py next` refuses (exit 4) and nothing runs. Silence, a scheduler or another agent's message is never an approval.
- Inside a step, every agent runs in its own Autonomous mode: documented defaults, recorded in the step result as `defaults_used`, listed in the sprint report under "Decided without you".
- The paid scripts (`generate_image.py`, `render_ads.py --batch`, `photo_edit.py render`, `enrich_context.py` with firecrawl or exa, `serp_analyzer.py`, `geo_panel.py run`) refuse any call without `--confirm-spend` or `FOG_ALLOW_SPEND=1`. The sprint passes the flag, or the variable scoped to that step's process, only to `spends: true` steps whose estimate the person approved, never globally.
- A step that reaches a spend gate, a publication approval or an input nobody has goes to needs_human; independent steps keep running. growth-sprint never confirms a spend, never approves a publication, and never clears a needs_human item: `sprint.py resolve` needs a person's name and checks the disk when it can (content-publisher items still `to_review` refuse it).
- On a run someone scheduled ([`../../shared/scheduling.md`](../../shared/scheduling.md)): `sprint.py resume`, then the Step 5 loop, on an approved sprint only. Nothing is redone: `reuse_if_fresh_days` skips steps whose outputs are already there and recent.
- The run always ends with its report and its `runs.jsonl` line, failures and halts included, and proposed decisions marked `Status: proposed`.

## Output format

`sprint-report-<YYYYMMDD>.md`, written by `sprint.py report`: the orchestrator's summary on top ([`assets/output-template.md`](assets/output-template.md)), then the steps with their status, attempts, spend and verified outputs, what waits for the founder, what a person decided, what the agents decided by default, breaker trips, interruptions and budget alerts, and the input for the next sprint.

## Output location

```
<your-projects-root>/<project-slug>/growth-sprint/
  ├── config.json
  ├── STOP                                 # optional: pauses every sprint of the project
  └── <sprint id>/
      ├── sprint.json                      # the plan, written by the model, approved once
      ├── approval.md                      # the packet the founder approves from
      ├── state.json                       # written only by scripts/sprint.py
      ├── briefs/<step>.md                 # one per started step
      ├── results/<step>.json              # written by whoever ran the step, last
      ├── STOP                             # optional: pauses this sprint
      ├── summary.md                       # the orchestrator's summary
      └── sprint-report-<YYYYMMDD>.md
```

Each agent writes its own deliverables in its own folder of the project, as when it runs alone.

## Failure modes

- **No goal, no growth-pulse handoff** → ask once in Step 0; without an answer, propose three goals from `context.json` (one per AARRR stage the context supports) and stop at the packet: a sprint never starts on a goal nobody chose.
- **`sprint.py validate` keeps failing** → fix the plan, never the registry: a step that spends is declared so, a dependency cycle is cut, labels differ per run of one agent.
- **The plan changed after approval (exit 4)** → expected: `packet`, then the founder approves the new version.
- **"not recorded by `sprint.py approve`" (exit 4)** → `state.json` was edited by hand, or the sprint runs with another approval key than the one `approve` used (another machine or user, or `FOG_APPROVAL_KEY_FILE` set differently). Use the same key file, then the founder approves again.
- **A step fails twice in a row (breaker, exit 3)** → read the step's `outputs not verified` line and the agent's report; the founder runs `sprint.py resume --by <name> --retry <step>` or `--skip <step>`.
- **Reported spend above the cap (breaker, exit 3)** → nothing more spends: the founder raises `budget.cap_eur` in `sprint.json`, then `packet` and approve. `resume` does not clear a budget halt.
- **A worker says done but check_step fails** → the disk wins: the step counts a failure and runs again once. A worker that wrote nothing is indistinguishable from one that never ran.
- **The sprint is complete and the goal's target is not reached** → expected: complete means the deliverables are verified on disk. A person still sends, approves and counts. Say which numbers are measured and which only the founder can give.
- **The session dies mid-wave** → `sprint.py resume`: steps whose outputs are on disk and valid are settled, the others go back to pending without counting a failure.
- **Two workers write the same shared file** → cannot happen through `next`: never two steps of one agent at once, content-publisher always alone. Starting steps by hand with `mark running` keeps that rule out of reach: use `next --claim`.
- **No subagent capability** → `--max 1` and the orchestrator runs the briefs itself, in order.
- **An agent folder is missing from the registry** (a new agent) → it cannot be planned; add its entry to [`assets/agents.json`](assets/agents.json) with its outputs and schemas, then `python3 scripts/selftest.py`.

## Per-project config

```
<your-projects-root>/<project>/growth-sprint/config.json
```

See [`config.example.json`](config.example.json): default budget cap, alert ratio, wave size, approvers, reuse windows per agent, excluded agents, optional `tools` override.
