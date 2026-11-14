# growth-sprint

One goal, one approval, then the steps run one after the other in your open harness session. You say what you are aiming for this month ("15 first conversations with physiotherapists", "launch the pricing page"); growth-sprint reads your project context and memory, writes a plan that chains the other agents through the files they already exchange, and asks you once. After that it runs the steps, checks every result on disk, and only comes back to you for what a person must decide.

## Four things to know first

**The goal is a target you track.** Agents do not book calls and do not send anything. They prepare prospects, sequences, visuals and queue items; a person sends, approves each post and counts the results. The sprint's own success is its deliverables on disk, each one checked. Whether the 15 conversations happened is yours to count, or the next growth-pulse run's where your analytics can see it.

**The budget is a cap on cash spent on optional paid APIs from your own accounts.** In this stack that means image-model photo backgrounds, paid SERP calls and the paid runs of the GEO panel (`geo_panel.py run`). The default is 0: everything runs on local scripts and free tiers. It is never ad spend. The agent has no card and pays for nothing: a paid call uses your key and lands on your provider's invoice.

**Nothing measures the spend.** Each step reports what it spent, from an invoice or an estimate, and the sprint adds up those reports: an alert at 80 % of the cap, a halt above it. The hard stop is in the paid scripts themselves, which refuse to run without `--confirm-spend` or `FOG_ALLOW_SPEND=1`. Search and scrape credits are not counted.

**It runs inside an open session.** The model in your harness starts one subagent per step, or runs the steps itself in sequence. Close the session and the sprint stops. `sprint.py resume` restarts it, in a new session, where it left off. Nothing runs in the background. To restart it on a schedule, see [`shared/scheduling.md`](../../shared/scheduling.md).

## How it works

1. **Ground truth**: what the project already has, per agent (`scripts/check_step.py --project <project> --agent <name>`), and the decisions you made before.
2. **Plan** (`sprint.json`): the goal and how you count it, a budget cap with its basis, 4 to 12 steps (agent, label, brief, inputs, dependencies, spends, publishes, estimate). `scripts/sprint.py validate` refuses a hidden spend or publication, a cycle, an estimate over the cap, two runs of one agent writing the same folder.
3. **One approval**: `approval.md` lists the steps, the budget, what spends, what publishes, and the agent gates that stay yours. You run `sprint.py approve` yourself, in your own terminal: it shows the plan, prints a plan code and asks you to type it. Any edit of the plan voids it.
4. **Run**, in your open session: waves of up to three steps, each with a brief that a subagent (or the same session, in sequence) follows. A step is done when its outputs are on disk, newer than the step, and valid against the producing agent's schema. Never on the worker's word.
5. **needs_human**: spend gates, posts to approve, a missing input, a step that no longer fits the budget. They wait for you; the steps that do not depend on them keep going.
6. **Report**: what ran, what waits for you, what the agents decided by default, the spend the steps reported, and the growth-pulse experiments that seed the next sprint.

```
pending --next--> running --mark done + disk check--> done
                     |        \--> needs_human --resolve (a person)--> pending | done | skipped
                     \--> failure: pending (retry once), then failed + breaker
```

## Safety rails

| Rail | Enforced by |
|------|-------------|
| Nothing runs before a person approves this exact plan | `next`, `mark` and `resolve` exit 4 without a sealed approval whose hash matches `sprint.json` |
| The approval comes from a person at a terminal | `approve` refuses without an interactive terminal (stdin and stdout TTYs) and refuses `--code`; the plan code is an HMAC under a local key and only the interactive `approve` prints it (not the packet, not `validate`, not `state.json`) |
| An approval cannot be written into `state.json` | the approval record is sealed with an HMAC under the same key; a hand-written or hand-edited approval (a raised cap, another plan hash) is refused by `next` |
| Approvals and resolutions carry a person's name | agent and tool names refused |
| Done means on disk | `mark done` runs the same check as `check_step.py`; a worker that wrote nothing counts a failure |
| Agent gates stay with you | static-ads Gate 1 and Gate 2, the seo-audit paid-call question, content-publisher approval: surfaced in needs_human; `resolve` refuses while queue items are still `to_review` |
| Paid calls | the paid scripts refuse to run without `--confirm-spend` or `FOG_ALLOW_SPEND=1`; the sprint passes either one only to a step you approved to spend |
| Budget | counts what steps report (`--spent`, or `spent_eur` in the result file): alert at 80 % of the cap; a spending step that no longer fits waits; reported spend above the cap halts until you approve a higher cap |
| Breaker | two failures in a row on a step, spent above the cap, or a `STOP` file |
| Interruptions | `resume` settles running steps from the disk; an interruption is not a failure |
| No side effects | the scripts run no other program: they cannot approve, spend or post for anyone |

The approval key is `~/.config/fog-agents/approval.key` (random, mode 600, created on first use, outside every project folder; `FOG_APPROVAL_KEY_FILE` sets another path; content-publisher uses the same file). `approve` and the commands that run the sprint must see the same key. What the gate guarantees: it stops an agent that follows its workflow and any manual edit of `state.json`. It is not a sandbox: an agent with an unrestricted shell under your user can read the key or drive a terminal. For a strong guarantee, do not give the agent the keys of the paid or publishing providers, or run `approve` from another session the agent cannot reach.

## Agents it can chain

The registry [`assets/agents.json`](assets/agents.json) lists every agent of the stack with its inputs, its outputs and their checks, and whether it can spend or publish:

| Agent | Spends | Publishes | Human gate surfaced |
|-------|--------|-----------|---------------------|
| project-context, market-signal, first-users-hunter, landing-page-analyzer, cold-outreach-builder, founder-content-writer, short-video-builder, growth-pulse | no | no | none (inputs only) |
| carousel-builder | possible (image model, last resort) | no | none |
| seo-audit | possible (paid SERP calls, paid GEO panel runs) | no | spend |
| static-ads-builder | possible (photo plates) | no | Gate 1 and Gate 2 |
| content-publisher | no | yes | publication approval |

## Quick start

```bash
# Offline test of the whole engine (about 10 s, no key, no network)
python3 agents/growth-sprint/scripts/selftest.py
```

Then, from your AI coding harness:

```
Run growth-sprint for project acme. Goal: 15 first conversations with physiotherapists this month, which I count myself. Budget: 0.
```

With that prompt you approve one plan and keep the session open while it runs. A typical plan ends with a list of people who showed a dated need, an outreach sequence to send from your own tool, carousels waiting for your approval, and a report. You send the messages and count the conversations. No step may make a paid call: one that would need it waits in needs_human.

The agent follows [`AGENT_GROWTH_SPRINT.md`](AGENT_GROWTH_SPRINT.md). CLI reference: [`scripts/README.md`](scripts/README.md).

## Outputs

```
<your-projects-root>/<project>/growth-sprint/<sprint id>/
  sprint.json  approval.md  state.json  briefs/<step>.md  results/<step>.json  summary.md  sprint-report-<YYYYMMDD>.md
```

Each agent writes its own deliverables in its own folder, exactly as when it runs alone.

## Tools

Optional: `subagents` (parallel workers; without them the same briefs run in sequence) and `critic` (plan review). See the Tools table of [`AGENT_GROWTH_SPRINT.md`](AGENT_GROWTH_SPRINT.md#tools).

## Examples

- [`examples/swanbase-demo-calls-20261012/`](examples/swanbase-demo-calls-20261012/): a fictional sprint for the stack's example brand: the plan, its approval packet, and the report of a simulated run (interruption, breaker, spend gate, publication approval, budget raise). Its 40 EUR cap exists to exercise the budget rails: it pays for image-model backgrounds on the fictional founder's own account, not for ads, and the demo calls in its goal are a target that founder counts.

## Limits

- Spend is what steps report, from an invoice or an estimate; nothing measures it. API credits drawn by an agent's optional providers (search, scrape) are not counted.
- The sprint cannot tell whether the goal's target was reached: a person sends and counts. It completes when its deliverables are verified on disk.
- The approval binds the agent and the repo's scripts, not someone who has your shell.
- Nothing runs in the background and a sprint does not schedule itself: closing the session stops it, and `sprint.py resume`, then `next`, restarts it, by hand or on a schedule you set up ([`shared/scheduling.md`](../../shared/scheduling.md)).
