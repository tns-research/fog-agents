---
name: planning-sprint
description: Turns a founder's goal into a growth-sprint plan. Reads what the project already has (outputs of each agent checked on disk, their dates, the founder's decisions), shapes the goal into a metric, picks and orders the stack agents through their handoff files, sets labels, inputs, reuse windows and a budget cap whose every figure has a basis, then validates sprint.json with scripts/sprint.py, has the plan reviewed by a fresh reviewer and writes the approval packet. Use at Steps 1 to 3 of growth-sprint, and when a growth-pulse experiment becomes the next goal. Triggers on "plan a sprint", "15 conversations this month", "launch the page", "next sprint", "use the growth-pulse experiments".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# planning-sprint

A plan the founder can approve in one read, and that the scripts can run without asking again. The model chooses; [`../../scripts/sprint.py`](../../scripts/sprint.py) refuses what does not hold.

## 1. Ground truth

Before choosing anything, list what exists. For each agent of [`../../assets/agents.json`](../../assets/agents.json):

```bash
python3 agents/growth-sprint/scripts/check_step.py --project <project> --agent <name> [--label <label>]
```

Exit 0: its newest outputs exist and pass their checks (no freshness test in this mode). Read the file dates in the names and the agent's last line in `project-context/memory/runs.jsonl`. Write one block:

```
Ground truth (2026-10-12):
- project-context: usable, context.json 2026-09-30
- market-signal: usable, market-signal-20260928.json (14 days)
- first-users-hunter: absent
- growth-pulse: usable, experiments-20261007.json (3 experiments)
Decisions applied: D-20261002-01 (no street address in public copy)
```

Then the decisions of `memory/decisions.md` that shape the plan: an agent, a channel or a spend the founder refused stays out, and the plan lists their ids in `decisions_applied`.

## 2. The goal

`goal.text` keeps the founder's words. `goal.metric` says what is counted ("first conversations held", "visits to /pricing"), `target` and `deadline` when the founder gave them. Never invent a target: no number from the founder or from growth-pulse means `"target": null`.

The target is what the founder tracks, not what the sprint delivers. Agents do not book calls or send anything: they prepare prospects, sequences, visuals and queue items, and a person sends and counts. Write each step's `brief` as a deliverable on disk, and say in one line of the handoff which numbers the founder will have to count.

Seeded by growth-pulse: `goal.source` is `growth-pulse/experiments-<YYYYMMDD>.json#<experiment id>`; copy its title as `text`, its metric label as `metric`, its threshold as `target`. Its `owner` names the agent that runs the change; its `cost.cash_eur` must fit in the cap (`validate` warns otherwise). An experiment with `spend_requires_approval: true` is approved through this sprint's packet, not before.

## 3. Choosing and ordering steps

Agents never call each other: a step depends on another when it reads its file ([`../../../../shared/handoffs.md`](../../../../shared/handoffs.md), `reads` in the registry). Typical chains:

| Goal shape | Steps (dependencies in brackets) |
|------------|----------------------------------|
| Conversations or demo calls | market-signal, first-users-hunter, then cold-outreach-builder [both]; carousel-builder [market-signal], content-publisher [carousel] |
| Launch or fix a page | market-signal, landing-page-analyzer [market-signal]; seo-audit for an existing site |
| Organic reach | market-signal, carousel-builder, short-video-builder and founder-content-writer [market-signal, or none], content-publisher [the deliverables] |
| Paid test | market-signal, landing-page-analyzer, static-ads-builder [market-signal] |
| Read the result | growth-pulse last, after what it should measure has shipped |

Rules:

- `project-context` first only when `context.json` is absent or stale; otherwise a step with `reuse_if_fresh_days` (it is skipped automatically when recent).
- Reuse windows from `config.json` (`reuse_if_fresh_days`): a recent market-signal or first-users run is reused, not redone.
- Every step serves the goal in one sentence (`brief`). A step nobody can tie to the goal goes.
- 4 to 12 steps. More means two sprints.
- One label per run of a labelled agent (`<label>` in its output paths), different labels for two runs of one agent, or their outputs collide (`validate` refuses).
- `content-publisher` after the deliverables it posts, with them in `inputs.deliverables`. Its publication approval stays with the founder.
- `inputs` hold what the agent cannot take from project-context: a carousel topic, a video file, the networks. A required input with no value becomes a needs_human item at run time; `validate` warns.

## 4. Spend, publication and budget

- The budget is the cap of cash spent on optional paid APIs from the founder's own accounts: in this stack, image-model photo backgrounds, paid SERP calls and the paid runs of the seo-audit GEO panel. Default 0. Never ad spend: an ad budget is not a figure of this plan, and the agent has no card. Search and scrape credits are not counted.
- `spends: true` and `publishes: true` follow the registry: an agent that can spend or publish is declared so even when this run should not (the founder sees it in the packet). `validate` refuses the opposite.
- `estimate_eur` is a ceiling per step, 0 for local work. Its `estimate_basis` names where the figure comes from: the agent's own quote (static-ads-builder `render_ads.py --estimate`), the founder's provider price, or the founder's ceiling. Never a guessed market price.
- `budget.cap_eur` is the founder's figure, else the sum of the estimates, which is 0 when nothing is planned to spend; `budget.basis` says which. Default `alert_ratio` 0.8. With a cap of 0, a step that can spend keeps `spends: true` with `estimate_eur` 0: it runs without paid calls, and one it would need goes to needs_human.
- The sprint approval allows a spending step to run up to its agent's gates; it never answers them. Static-ads Gate 1 and Gate 2, the seo-audit paid-call question and the content-publisher approval stay with the founder, and the packet says so.

## 5. Validate, review, packet

```bash
python3 agents/growth-sprint/scripts/sprint.py validate <sprint dir>
```

Exit 1 lists every error (schema, unknown agent, cycle, unknown dependency, hidden spend or publication, missing basis, over the cap, colliding labels, unknown experiment). Fix the plan, never the registry. Warnings stay in the packet.

Then the fresh-eyes review ([`../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md)) with [`../../assets/review-rubric.md`](../../assets/review-rubric.md): the reviewer gets the goal, the ground-truth block, `sprint.json`, the validate output and the registry. One revision, validate again, then:

```bash
python3 agents/growth-sprint/scripts/sprint.py packet <sprint dir>
```

Hand `approval.md` to the founder with one line: the goal, the number of steps, the cap, the steps that spend or publish, and the approve command printed at the end of the packet. Then stop: the founder approves in their own terminal. `approve` refuses to run without an interactive terminal, prints the plan code only there and asks the founder to type it; the agent never runs it, never drives a terminal to answer it and never writes an approval into `state.json` (the record is sealed with a local key, so `next` would refuse it). This stops an agent that follows its workflow and any manual edit of `state.json`; it is not a sandbox: for a strong guarantee, keep the paid and publishing providers' keys out of the agent's environment, or run `approve` from another session.
