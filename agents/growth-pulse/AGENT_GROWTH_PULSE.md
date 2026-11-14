---
name: growth-pulse
description: Growth report for an early-stage startup, once a week when the founder runs it or schedules it (shared/scheduling.md). Collects six weeks of daily data from optional, interchangeable sources (Plausible, Umami, GA4, Google Search Console, social networks through the Zernio API, Stripe or a revenue CSV), each with a CSV export fallback and a health status; computes every figure and every change (week against previous week, against the 4-week mean) by script into a schema-validated pulse.json, with noise bands, no percentage on small volumes, Search Console declines by the same definition as seo-audit, and correlations on pre-registered pairs that are never presented as causes. The model writes the report from pulse.json only and a script checks that every number of the report exists there. Ends with three AARRR experiments (hypothesis, metric, threshold, duration, cost) in a JSON handoff that feeds the next sprint, and judges the last run's experiments from the run log.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Growth Pulse Agent

One report per run: what moved last week, what only looks like it moved, what nobody can read yet, and the three experiments of the coming sprint. Nothing starts it but you or a schedule you set up ([`../../shared/scheduling.md`](../../shared/scheduling.md)). One rule holds the agent together: **scripts collect and compute every number (`pulse.json`), the model writes from that file only, a script checks every number of what it wrote.**

## Skills and assets

| Skill | Step | Output |
|-------|------|--------|
| [`skills/collecting-growth-data/SKILL.md`](skills/collecting-growth-data/SKILL.md) | 1 | `<run>/data/<source>.json`, one per source, with a health status |
| [`skills/computing-the-pulse/SKILL.md`](skills/computing-the-pulse/SKILL.md) | 2 | `<run>/pulse.json` ([`assets/pulse.schema.json`](assets/pulse.schema.json)) and `<run>/pulse-tables.md` |
| [`skills/writing-the-pulse-report/SKILL.md`](skills/writing-the-pulse-report/SKILL.md) | 3 | `growth-pulse-<YYYYMMDD>.md`, number check at 0 BLOCK |
| [`skills/designing-aarrr-experiments/SKILL.md`](skills/designing-aarrr-experiments/SKILL.md) | 4 | `experiments-<YYYYMMDD>.json` ([`assets/experiments.schema.json`](assets/experiments.schema.json)), the handoff of the next sprint |

| Asset | Used by |
|-------|---------|
| [`assets/pulse-rules.json`](assets/pulse-rules.json) | every threshold: weeks, volume, noise, correlations, the shared Search Console decline, experiment bounds |
| [`assets/metric-catalog.json`](assets/metric-catalog.json) | metric names, AARRR stages, kinds, directions, derived rates |
| [`assets/source.schema.json`](assets/source.schema.json) | the connectors' output contract |
| [`assets/output-template.md`](assets/output-template.md) | the report |
| [`assets/review-rubric.md`](assets/review-rubric.md) | the fresh reviewer |

Shared methodology: [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md), [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md), [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md), [`../../shared/skills/writing-gate/SKILL.md`](../../shared/skills/writing-gate/SKILL.md), [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md).

## Step 0: context resolution

1. **Project.** Resolve the project slug and `<your-projects-root>`. Ask once if ambiguous.
2. **Project context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md): `url`, `one_liner`, `icp`, `offer` and `voice.language` frame the experiments; `positioning.proof` is not used (the report quotes no proof, only pulse.json).
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md): apply the active decisions (a channel the founder dropped, a metric they do not want). Read the last `growth-pulse` lines of `memory/runs.jsonl`: the latest `experiments-<YYYYMMDD>.json` in their `outputs` is the file whose experiments this run judges. When `inputs_hash` of the last line equals the hash `compute_pulse.py` prints for today's inputs and the report exists, stop with a `skipped` line.
4. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for the capabilities of the Tools table and announce the plan in one block (which source comes by API, which by export, which is missing).
5. **Config.** Load `<your-projects-root>/<project>/growth-pulse/config.json`, or copy [`config.example.json`](config.example.json) there. Read `<project>/seo-audit/config.json` when it exists (its `gsc_bands.decline` override applies here too).
6. **One message of questions**, each with its default: the sources the founder uses and their ids or exports (default: the ones in config; others reported missing), the AARRR stage of each tracked event (default: activation), a focus stage (default: none), the cash budget of the sprint (default: 0). Then run on the answers or the defaults; no later step waits for an answer.

## When to run

Once a week, when you run it or schedule it ([`../../shared/scheduling.md`](../../shared/scheduling.md)), ideally on Wednesday (Search Console publishes the last days of a week 2 to 3 days late), before the team plans the sprint. Also after a launch or a campaign, to see whether anything moved beyond the noise.

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `sources` | no | from config; a source without key or export is reported missing | Which of Plausible, Umami, GA4, Search Console, social (Zernio or exports), revenue the startup uses, with ids and export files |
| `events` | no | every event counts as activation, listed in Limitations | AARRR stage of each tracked event (`apply_click: activation`, `invite_sent: referral`) |
| `week` | no | the last complete ISO week before the run | Report week, `YYYY-Www` |
| `actions.csv` | no | none | The founder's log of what they shipped (`date,channel,stage,action`), placed next to the metrics as coincidences in time |
| `focus_stage` | no | none, the experiments span at least two stages | Pin the three experiments to one AARRR stage |
| `budget_eur_per_sprint` | no | 0: no cash spend | Cash cap of the three experiments; any spend waits for approval anyway |
| `language` | no | `voice.language` of project-context, else `en` | Report language (headings stay in English) |

## Tools

Every capability is optional and every source has a free export fallback. Providers and tiers: [`../../shared/tools.md`](../../shared/tools.md).

| Capability | Used for | Without it |
|------------|----------|------------|
| `web_analytics` | daily visitors, pageviews and events: Plausible Stats API, Umami API, GA4 Data API (keys in the environment) | the dashboard CSV export the founder drops in `exports/`; with no web source at all, the report says so and acquisition rests on search and social |
| `search_console` | daily clicks, impressions, position, weekly query and page rows (API, or API-shaped JSON from any tool such as the `gsc` CLI) | `Dates.csv` of the UI export: totals only, no query or page declines; with nothing, no Search Console section |
| `social_stats` | impressions, clicks, engagements, reposts, followers, posts per network: Zernio API (`ZERNIO_API_KEY`, `sources.social.zernio.enabled` in config) | CSV exports of each network, the fallback; nothing to set up |
| `revenue_data` | payments, new and returning customers (Stripe API with a restricted read key) | the payments CSV export of Stripe or any invoicing tool |
| `copy_lint` | the report, through the shared writing gate | the gate's family table applied by hand, "Writing gate: manual" in Methodology |
| `critic` | the fresh review of report and experiments | "Fresh-eyes review: not run", report listed as unreviewed |

Nothing is bought by this agent: the APIs above read the founder's own accounts. One exception to watch: Zernio bills X reads at X's rate when an X account is connected, and its docs do not say which analytics reads count; set a spend cap in its dashboard, or leave `x` out of `sources.social.zernio.platforms`.

## Workflow

**Step 1. Collect.** [`skills/collecting-growth-data/SKILL.md`](skills/collecting-growth-data/SKILL.md). One command runs every connector of the config and then Step 2:

```bash
python3 scripts/run_pulse.py --project-dir <your-projects-root>/<project> --today <YYYY-MM-DD>
```

Done when: `<project>/growth-pulse/<YYYYMMDD>/data/` holds one source file per declared source, each with a status (`ok`, `partial`, `stale`, `missing`, `error`).

**Step 2. Compute.** [`skills/computing-the-pulse/SKILL.md`](skills/computing-the-pulse/SKILL.md). `compute_pulse.py` (run by `run_pulse.py`, with last run's experiments file, the action log and the seo-audit override when present) writes `pulse.json` and `pulse-tables.md`. Read `sources`, `notable`, `stage_summary`, `gsc`, `correlations`, `experiments_followup`, `limitations`. Never compute a figure.

Done when: `<run>/pulse.json` exists and validates (the script refuses to write an invalid one).

**Step 3. Write the report.** [`skills/writing-the-pulse-report/SKILL.md`](skills/writing-the-pulse-report/SKILL.md), template [`assets/output-template.md`](assets/output-template.md): tables copied from `pulse-tables.md`, prose from `pulse.json` only, counts on small volumes, "within the noise" for flat moves, correlations and coincidences in time never written as causes.

Done when: `growth-pulse-<YYYYMMDD>.md` exists with every section of the template (its "Next sprint" block is filled at Step 4).

**Step 4. Three experiments.** [`skills/designing-aarrr-experiments/SKILL.md`](skills/designing-aarrr-experiments/SKILL.md). Write `experiments-<YYYYMMDD>.json`: three AARRR experiments drawn from the evidence of pulse.json, last run's verdicts first. Then:

```bash
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-<YYYYMMDD>.json --pulse <run>/pulse.json --config <project>/growth-pulse/config.json --fill
python3 scripts/check_experiments.py <project>/growth-pulse/experiments-<YYYYMMDD>.json --pulse <run>/pulse.json --md
```

Paste the `--md` block into the report's "Next sprint" section.

Done when: `check_experiments.py` exits 0 and the file holds exactly three experiments.

**Step 5. Checks, review, memory.** The gates below, in order, then the run line.

Done when: every gate has a result in Methodology and the run line validates.

## Checks before delivery

From the agent folder (from the repo root, drop `../../` and prefix `agents/growth-pulse/`):

1. **Number check** on the report: `python3 scripts/check_report.py <report> --pulse <run>/pulse.json --experiments <handoff> --json > <run>/report-check.json`. 0 BLOCK.
2. **Writing gate**: `python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --project <project> --json <report> > <run>/writing-gate.json`. 0 BLOCK, 3 passes at most with the number check.
3. **Claims check**: the number check is this agent's claims check (every figure traces to pulse.json); the report quotes no customer, proof or testimonial. A sentence that would need one is removed (see [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md)).
4. **Schema check** of every contract file: `pulse.json` is validated by `compute_pulse.py` before it is written; the handoff by `check_experiments.py`; on demand: `python3 ../../shared/scripts/validate_json.py assets/experiments.schema.json <handoff>`.
5. **Render review**: does not apply (no image).
6. **Fresh-eyes review**, see Review.
7. **Run log and decisions** with [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md): append the line, with `inputs_hash` from `pulse.json` and the handoff path in `outputs` (the next run's Step 0 finds it there), then `python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl`.

## Review

- **Rubric**: [`assets/review-rubric.md`](assets/review-rubric.md) (numbers, noise and volume, causes, source health, continuity, experiments, reader value, voice), 13/16 and no 0 to pass.
- **Reviewer**: a fresh subagent, else a blank session or a second model CLI, else the founder (`critic` capability). The packet holds the brief, `pulse.json`, the report, the handoff and the check outputs, never the producer's notes. A second pass by the producing session never counts.
- **Bounds**: one critique, one revision; the number check and the experiments check outrank any opinion.

## Autonomous mode

- Every input has a default (Inputs table); the defaults used are listed in Methodology.
- A missing key or export degrades the run (source `missing`, Limitations), never stops it. With no source at all, the report is Source health plus the export how-to, and the run is `partial`.
- Nothing spends or publishes: the report and the handoff are files. An experiment with cash carries `spend_requires_approval: true`; nobody spends before the founder approves.
- The run ends with its `runs.jsonl` line, failures included, and decisions proposed as `Status: proposed`.

## Output format

The report follows [`assets/output-template.md`](assets/output-template.md): Summary, Source health, This week by stage, What moved, Search Console, Correlations, Last run's experiments, Next sprint, Methodology, Limitations. Reference run: [`examples/swanbase-20261014/`](examples/swanbase-20261014/).

## Output location

```
<your-projects-root>/<project>/growth-pulse/
  ├── config.json
  ├── actions.csv                        # optional, the founder's log of what shipped
  ├── exports/                           # CSV exports the founder drops (any name, listed in config)
  ├── <YYYYMMDD>/
  │   ├── data/<source>.json             # one per source, with health
  │   ├── pulse.json                     # every number of the week
  │   ├── pulse-tables.md
  │   ├── report-check.json
  │   └── writing-gate.json
  ├── growth-pulse-<YYYYMMDD>.md         # the report
  └── experiments-<YYYYMMDD>.json        # the handoff of the next sprint
```

## Failure modes

- **No key and no export for a source** → status `missing` with the export how-to in its message; the report names what it hides. Never a stop.
- **API error (401, 429, timeout)** → status `error`; retry once, then the CSV fallback of the message.
- **Zernio answers 402 or 403** → the account has no analytics access: status `error`, `run_pulse.py` reads the CSV exports when the config lists some and writes the reason in the notes. Nothing is bought. Only the follower call refused: the source stays usable without `followers_gained`.
- **Search Console run on a Monday** → the report week is `stale` for Search Console: its metrics are not compared and no decline is computed. Rerun on Wednesday or accept it in Limitations.
- **A metric under 30 events** → counts only, no percentage; the experiments use count targets.
- **A big move inside the noise band** → reported as flat, whatever its percentage.
- **The founder wants to know why a metric moved** → the report gives coincidences in time and correlations, then an experiment that tests the cause. It never asserts one.
- **`check_report.py` blocks after three passes** → the remaining BLOCKs go to the top of the report and the run is `partial`.
- **Last run's experiments file missing or malformed** → follow-up section says so; `compute_pulse.py` exits 2 on a malformed file: run without it and record why.
- **An event that is not tracked yet** → the experiment uses `new:<metric id>` and starts with the tracking; next run reports it `not_measurable` until it records.

## Per-project config

```
<your-projects-root>/<project>/growth-pulse/config.json
```

See [`config.example.json`](config.example.json): sources (ids, export files, enabled, and `social.zernio` for the API with the exports as fallback), events and their AARRR stage, focus stage, sprint cash budget, `pulse_rules` and `gsc_bands.decline` overrides, optional `tools` object.
