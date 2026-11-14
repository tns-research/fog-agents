---
name: writing-the-pulse-report
description: Writes the weekly growth report from pulse.json and pulse-tables.md only, then proves it with scripts/check_report.py (every number exists in pulse.json or the experiments handoff, no percentage on a small volume, no correlation written as a cause, required sections present) and the shared writing gate, looping until 0 BLOCK. Tables are copied as generated; prose says what moved, what stayed inside the noise, and what cannot be read yet. Use at Step 3 of growth-pulse. Triggers on "write the pulse", "weekly report", "growth report", "what moved this week".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# writing-the-pulse-report

The founder reads this report in five minutes on Monday and decides the week from it. It must say what changed, what only looks like it changed, and what nobody can tell yet, with no figure the scripts did not produce.

Template: [`../../assets/output-template.md`](../../assets/output-template.md). Inputs: `<run>/pulse.json`, `<run>/pulse-tables.md`, and for the last section the experiments block of [`../designing-aarrr-experiments/SKILL.md`](../designing-aarrr-experiments/SKILL.md).

## Rules for numbers

1. **Every figure comes from pulse.json or the experiments file.** Copy it at the precision you want (7.14 may be written 7.1); never add, subtract, average or convert one yourself. A figure the report needs and the file lacks goes to the catalog or the rules, then the pulse is recomputed.
2. **Tables are copied from `pulse-tables.md` as they are.** No row edited, none added. You may drop a stage table that has no metric.
3. **Small volume means counts.** When a metric is flagged `small_volume`, write the counts ("13 signups against 11.2 on average", "3 of 529 visitors"), never a percentage, and say why once ("fewer than 30 events").
4. **Flat means flat.** A change with `signal: flat` is inside the noise band: write "within the noise" or "no visible change", even when the percentage looks large. Never call it a dip, a drop or a rise.
5. **Use `trend`, not the sign.** A position going up is worse; refunds going down is better.
6. **Figures go in plain text, never in code spans**, so the check can read them. Code spans are for metric ids, file names and hashes.

## Rules for causes

pulse.json shows what moved together, never why. The report keeps that line:

| Write | Never write |
|-------|-------------|
| "in the same week as", "after", "while", "moved with", "went with" | "because", "drove", "led to", "thanks to", "due to", "resulted in", "boosted", "paid off", "worked" |
| "C5: search clicks and visitors have a correlation of r = 0.51" | "search clicks explain the visits" |
| "the position started to slip in the days after the rewrite; experiment E-... tests it" | "the rewrite cost us 3 positions" |
| "a met threshold goes with the change in time; it does not prove its effect" | "the carousel worked" |

- Any line that cites `r =` or a correlation id says "correlation" on the same line.
- An action from `actions[]` next to a moving metric is a coincidence in time until an experiment tests it: say "in the same week", then point to the experiment.
- Causal wording is allowed in one place: the hypotheses of the next sprint, which are bets, not findings.
- A sentence that negates the cause ("this does not show that ...") is fine.

## Section by section

- **Summary**: 3 to 5 bullets: the notable moves (`notable`), the Search Console decline when there is one, the verdict of last run's experiments, what is too small to read. One figure or two per bullet.
- **Source health**: the table, then one sentence per source that is not `ok`, with what it hides (Plausible missing: web traffic rests on one tool).
- **This week by stage**: one line on how to read the "Read" column, then the stage tables.
- **What moved**: one short paragraph per notable move or decline, in this order: what moved, against what, what did not move with it, what logged action sits in the same days, which experiment tests it. Two to five paragraphs.
- **Search Console**: the definition in one sentence (the seo-audit one), the decline block. Without data, say why (`gsc.note`).
- **Correlations**: the table, then one bullet per correlated pair and per weak pair that matters for the story (a channel that grew while visits did not).
- **Last run's experiments**: the table, then one bullet per experiment: verdict, observed against threshold, what it means for the sprint (scale, iterate, fix the tracking, wait).
- **Next sprint**: the block printed by `check_experiments.py --md`, with the handoff file name and the start date.
- **Methodology**: provider per source, rules applied and overrides, the result of every check, the reviewer.
- **Limitations**: `pulse.json` `limitations`, plus any source caveat the founder should know.

## The loop

1. Write `<project>/growth-pulse/growth-pulse-<YYYYMMDD>.md`.
2. Run the number check:

   ```bash
   python3 scripts/check_report.py <project>/growth-pulse/growth-pulse-<YYYYMMDD>.md \
     --pulse <run>/pulse.json --experiments <project>/growth-pulse/experiments-<YYYYMMDD>.json --json > <run>/report-check.json
   ```

   `unknown-number`: take the figure from pulse.json or delete it. `unknown-percent`: write counts. `number-in-code`: take the figure out of the code span. `causal-claim`: rewrite with the left column above. `unlabeled-correlation`: add the word. `missing-section`, `missing-experiment`: add them. Two WARNs to read: `notable-not-mentioned` (a notable metric is not named) and `decline-not-mentioned` (Search Console declined and the report never says decline).
3. Run the writing gate: `python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --project <project> --json <report> > <run>/writing-gate.json` (from the agent folder).
4. Fix in the copy, never in a threshold or an ignore list. Re-run both until 0 BLOCK, three passes at most; a BLOCK left after the third pass goes to the top of the report with its reason.

Done when: `report-check.json` and `writing-gate.json` both show 0 BLOCK, or the remaining BLOCKs are listed at the top of the report.

## Failure modes

- **A figure the founder gave in chat** ("we signed 2 clients this week") → not in pulse.json, so not in the report body; mention it in Limitations as founder-reported and suggest the export that would carry it.
- **Every source missing** → a two-section report (Source health, Limitations) with the export how-to; no experiments, status `partial`.
- **The check flags a number that is right** (a count the founder can verify) → it is still not in pulse.json: add the metric to the pipeline, never to the allowed list.
