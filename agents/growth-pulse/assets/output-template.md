# Report template

The weekly report, written by the model from `pulse.json` and `pulse-tables.md` with [`../skills/writing-the-pulse-report/SKILL.md`](../skills/writing-the-pulse-report/SKILL.md), checked by `scripts/check_report.py` (every heading below is required) and the shared writing gate. Reference instance: [`../examples/swanbase-20261014/growth-pulse-20261014.md`](../examples/swanbase-20261014/growth-pulse-20261014.md).

Path: `<your-projects-root>/<project>/growth-pulse/growth-pulse-<YYYYMMDD>.md`, in the language of `config.language` (headings stay in English so the check finds them).

```markdown
# Growth pulse: <project>, week <YYYY-Www>

Week <YYYY-Www> (<start> to <end>), compared with <previous week> and with the mean of the 4 weeks before it. Generated on <date> from `pulse.json` (inputs hash `<inputs_hash>`).

## Summary

- <3 to 5 bullets: notable moves, Search Console decline, last run's verdicts, what is too small to read>

## Source health

<table "Source health" of pulse-tables.md>

<one sentence per source that is not ok, and what it hides>

## This week by stage

<one line on how to read the Read column>

#### Acquisition
<table>
#### Activation
<table>
#### Retention
<table>
#### Referral
<table>
#### Revenue
<table>

## What moved

<2 to 5 short paragraphs: what moved, against what, what did not move with it, the logged action in the same days, the experiment that tests it. No causal wording.>

## Search Console

<the shared decline definition in one sentence, then the block "Search Console declines", or why it was not computed>

## Correlations

<one line on the method, the table, then one bullet per pair worth reading; every line citing r = says correlation>

## Last run's experiments

<the table, then one bullet per experiment: verdict, observed against threshold, what it means for the sprint; "First run, nothing to follow up." when empty>

## Next sprint: three experiments

Handoff: `experiments-<YYYYMMDD>.json`, for the sprint starting <date>. <cash total, hours total, approval needed or not>

<block printed by check_experiments.py --md>

## Methodology

- Sources: <provider per source>
- Numbers: compute_pulse.py with pulse-rules.json <overrides, or "shipped rules">
- Checks: report numbers <n> BLOCK, experiments <n> BLOCK and <n> WARN, writing gate <n> BLOCK, schemas <pass/fail>
- Fresh-eyes review: <reviewer and verdict, or "not run">
- Defaults used without an answer: <list, or none>

## Limitations

- <limitations of pulse.json, one per line>
- <source caveats>
```
