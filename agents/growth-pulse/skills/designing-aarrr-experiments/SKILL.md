---
name: designing-aarrr-experiments
description: Turns the week's pulse.json into exactly three AARRR experiments for the next sprint (acquisition, activation, retention, referral, revenue), each with a falsifiable hypothesis, one metric of pulse.json, a success threshold, a duration, a cost and an owner, written as the experiments handoff JSON that growth-sprint or the founder runs next. scripts/check_experiments.py --fill writes the baselines, the noise readout and last run's verdicts, then refuses an unknown metric, a typed baseline, an unreadable duration, an unapproved spend or an invented number. Use at Step 4 of growth-pulse. Triggers on "growth experiments", "AARRR", "pirate metrics", "next sprint", "what should we test", "ICE".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# designing-aarrr-experiments

The report says what happened; this step decides what to try next, small enough to run in a sprint and precise enough that the next run's pulse can say whether it held. Three experiments, no more: a founder runs three changes in a week, not ten. Contract: [`../../assets/experiments.schema.json`](../../assets/experiments.schema.json).

## AARRR, for an early-stage startup

| Stage | The question | Metrics of pulse.json that answer it |
|-------|-------------|--------------------------------------|
| Acquisition | Do the right people reach us? | visitors, search clicks, impressions and position, social impressions, link clicks, new followers |
| Activation | Do they take the first step that shows interest? | the events mapped to activation in `config.events` (signup, apply, demo request) and their visitor rates |
| Retention | Do they come back, use it again, pay again? | returning payments, events mapped to retention |
| Referral | Do they bring others? | reposts and shares, invite events |
| Revenue | Do they pay? | payments, new paying customers, gross and net revenue |

Awareness counts as acquisition here. One metric per experiment, the one that would move first if the hypothesis is right: a leading metric of the stage, not revenue for an acquisition test.

## Choosing the three

Read, in this order: `experiments_followup` (what last run started), `gsc` (a decline with a cause), `notable`, `stage_summary` (the stage with the most `worse`), the weak correlations of a channel that grew alone, `actions` of the report week.

1. **Continue before you add.** A `running` experiment stays as it is: do not propose a second one on the same metric. A `not_measurable` one comes back as "instrument, then rerun" (metric `new:<id>`). A `met` one is scaled or followed by the next step of the funnel, never declared proven. A `not_met` one is dropped or changed on one variable.
2. **Go where the funnel leaks.** A channel whose reach grew while the next stage did not move (impressions up, visitors flat) is a better target than the stage that is already improving.
3. **Spread the bets** over at least two stages (`experiments.min_distinct_stages`), unless `config.focus_stage` pins one.
4. **Prefer free and fast.** Zero cash by default; a test that costs money states it and waits for approval.

## Writing one experiment

| Field | Rule |
|-------|------|
| `id` | `E-<YYYYMMDD>-<n>`, the run date |
| `title` | the change in under 90 characters |
| `stage` | one AARRR stage |
| `hypothesis` | "We believe that <change> will <move metric> because <reason drawn from pulse.json>." The reason cites what the data shows, never an outside benchmark or a figure absent from pulse.json |
| `change` | what is done, where, by whom, concrete enough to start Monday |
| `channel` | where the change happens (`search`, `linkedin`, `email`, ...) |
| `metric` | `id` of a pulse.json metric, or `new:<id>` when it must be tracked first (the change then starts with the tracking), with a readable `label` |
| `baseline.basis` | `4-week mean` (default) or `report week`; the value is written by the script |
| `success_threshold` | comparator, value, `per` week (mean of the complete weeks inside the test) or `total`, unit. Ask for a change the noise band can show (see readout) |
| `duration_days` | 7 to 28; at least 14 for Search Console (late data, slow ranking) |
| `start_date` | the Monday after the run, never earlier than the file date |
| `cost` | `cash_eur`, `hours`; `spend_requires_approval: true` whenever cash is above 0 |
| `owner` | `founder` or the stack agent that runs it (`carousel-builder`, `landing-page-analyzer`, `cold-outreach-builder`, `seo-audit`, `static-ads-builder`, `first-users-hunter`) |
| `evidence` | references into pulse.json: `metrics/<id>`, `correlations/<C id>`, `gsc/totals`, `gsc/pages/<url>`, `gsc/queries/<query>`, `sources/<source>`, `followup/<id>`, `actions/<date>` |
| `ice` | impact, confidence, ease, 1 to 10 each, as a ranking aid only |
| `kill_criterion` | optional: when to stop before the end |
| `status` | `proposed` when written; the founder or growth-sprint moves it on (see the handoff) |

Numbers in the title, hypothesis, change and kill criterion must be in pulse.json or in the experiment's own fields. "Raise signups by 40 %" is refused; set the threshold instead.

## Fill and check

```bash
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-<YYYYMMDD>.json \
  --pulse <run>/pulse.json --config <project>/growth-pulse/config.json --fill
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-<YYYYMMDD>.json --pulse <run>/pulse.json --md
```

`--fill` writes `baseline.value`, `readout` (is the threshold outside the noise band for that duration, with the band per week), `followup` (last run's verdicts), `budget` and the pulse reference. Then the checks run. Fix every BLOCK in the experiment, never in the rules. Read every WARN:

- `undetectable`: lengthen the test, pick a bigger change, or a metric with more volume; keep it only with the reason in the report.
- `no-lift`: the threshold asks for nothing better than the baseline.
- `stage-mismatch`: the metric belongs to another stage; pick the stage's own metric or change the stage.
- `new-metric`: the tracking comes first, and the report says so.
- `stages`: fewer than `experiments.min_distinct_stages` stages; spread the bets unless `config.focus_stage` pins one.

`--md` prints the block the report quotes in "Next sprint".

Done when: `check_experiments.py` exits 0 on the filled file, and the file holds exactly three experiments.

## The handoff

`<project>/growth-pulse/experiments-<YYYYMMDD>.json` is the input of the next sprint: the founder (or growth-sprint) runs each change from `start_date`, sets `status` to `approved`, `running`, `done` or `dropped`, and the next growth-pulse run reads the file back to judge each experiment from its metric. Every experiment is a hypothesis to test, never a finding. Nothing that spends money starts before the founder approves it.

## Failure modes

- **Every metric is too small to read** (a very young product) → use count targets over the whole test (`per: total`, "at least 5 demo requests in 14 days"), say that the readout is a count, not a lift.
- **No data at all** → no experiments; the first experiment is to connect a source, written in the report, not in the handoff.
- **The founder already decided the next tests** → write them in this format anyway, so the next run can judge them, and keep the evidence honest (`sources/<source>` when nothing in pulse.json supports them).
