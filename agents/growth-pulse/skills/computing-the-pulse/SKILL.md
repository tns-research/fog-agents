---
name: computing-the-pulse
description: Turns the source files into pulse.json with scripts/compute_pulse.py, the only place where growth-pulse computes a number. Weekly values per metric, the report week against the previous week and against the 4-week mean, a percentage only on enough events, a noise band and a signal per change, Search Console declines with seo-audit's definition, weekday-adjusted correlations on pre-registered pairs (never causes), and the verdict of last run's experiments. The model reads pulse.json and never recomputes a figure. Use at Step 2 of growth-pulse. Triggers on "compute the pulse", "week over week", "noise", "small volume", "correlation", "did last week's experiment work".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Bash(python3:*)
---

# computing-the-pulse

A model that does arithmetic in prose gets one figure in twenty wrong, and nobody can tell which. Here a script computes every figure once, writes it with its rule, and the model only reads. Thresholds: [`../../assets/pulse-rules.json`](../../assets/pulse-rules.json). Metric definitions: [`../../assets/metric-catalog.json`](../../assets/metric-catalog.json). Contract: [`../../assets/pulse.schema.json`](../../assets/pulse.schema.json).

## Command

`run_pulse.py` calls it at the end of Step 1. Alone:

```bash
python3 scripts/compute_pulse.py --sources <run>/data/*.json \
  --config <project>/growth-pulse/config.json --seo-config <project>/seo-audit/config.json \
  --actions <project>/growth-pulse/actions.csv \
  --previous-experiments <project>/growth-pulse/experiments-<YYYYMMDD>.json \
  --today <YYYY-MM-DD> --out-dir <run>/
python3 scripts/compute_pulse.py --show-rules --config <project>/growth-pulse/config.json
```

Writes `<run>/pulse.json` (validated against its schema before it is written) and `<run>/pulse-tables.md` (the tables of the report, ready to copy). Exit 0 written, 1 written but no source had data, 2 unreadable input.

Done when: `pulse.json` exists and the command exited 0 (or 1, with every source reported missing in the report).

## What the rules decide

| Question | Rule (pulse-rules.json) | What it means for the report |
|----------|------------------------|------------------------------|
| Which week? | `weeks`: the last complete ISO week before the run, against the previous week and the mean of the 4 weeks before it; a week with a missing day is incomplete and never compared | "this week" always means Monday to Sunday |
| Percentage or not? | `volume.min_events_for_pct` (30): a count change on a base under 30 has no `pct`; a rate under 30 events is `null` with its `counts`; a revenue change with fewer than 30 payments is `small_volume` | write the count ("13 of 529"), never a percentage |
| Real move or noise? | `noise`: the larger of a Poisson band and the observed spread of the 4 reference weeks, times `z` (2); rates use the two-proportion standard error, positions a 1-position flat band | `signal` flat = "within noise", whatever the percentage says |
| Better or worse? | `trend` reads the signal with the metric's direction (refunds and positions are better down) | use `trend`, not the sign |
| Search decline? | `gsc_decline`, a mirror of the decline object of seo-audit's `gsc-bands.json`: clicks down 20 % or more on at least 10 prior clicks; cause position, demand, ctr or gone | say "decline" only when `gsc.totals.decline` is true; quote the cause as named |
| What moved together? | `correlation`: Pearson r on daily values with the day-of-week mean removed, only on the pairs listed in advance, lag 0 and 1 day, `correlated` at abs(r) >= 0.5 on at least 28 days | every correlation is `causal: false`; see the wording rules of the report skill |
| Did last run's experiments hold? | `experiments_followup`: the mean (or total) of the metric over the complete weeks inside each experiment, against its threshold | `met`, `not_met`, `running`, `not_measurable`; a `met` is not a proof |

Two overrides, both optional: `pulse_rules` in the growth-pulse config (any key), and the `gsc_bands.decline` override of `<project>/seo-audit/config.json`, read so one project override serves both agents. Overrides are listed in the report's Methodology.

## Reading pulse.json

Read in this order; each field is final.

1. `sources`: status per source; a non-ok source goes into Source health and Limitations.
2. `notable`: metrics whose trend is the same against last week and against the 4-week mean, largest first. These lead "What moved".
3. `stage_summary`: per AARRR stage, how many metrics are better, worse, flat or too small. The stage with the most `worse` is the first candidate for an experiment.
4. `metrics[]`: `current`, `previous`, `baseline`, `vs_previous`, `vs_baseline` (`abs`, `pct`, `pp`, `noise_band`, `signal`, `trend`, `small_volume`), `flags` (`small_volume`, `incomplete_week`, `unmapped_event`, `daily_visitors_summed`), `counts` for rates.
5. `gsc`: `totals`, declining `queries` and `pages` with their cause; `note` when not computed.
6. `correlations[]` with ids C1, C2...; `actions[]` logged by the founder (`in_report_week`).
7. `experiments_followup[]` and `previous_experiments`.
8. `limitations[]`: copied into the report.

Never derive a new figure from these (a sum of two metrics, a ratio, a share): if the report needs it, add it to the catalog or the rules and recompute.

## Failure modes

- **A metric is missing from the catalog** → it is left out and listed in `limitations`; add a `match` entry to `metric-catalog.json`, never compute it by hand.
- **An event has no stage** in `config.events` → counted as activation, flagged `unmapped_event`, listed in Limitations; propose the mapping to the founder.
- **No previous experiments file** → `experiments_followup` is empty; say "first run, nothing to follow up".
- **Previous experiments file fails its schema** → exit 2 with the errors; fix the file (it was written by a previous run, so its producer changed) or run without it and say so.
