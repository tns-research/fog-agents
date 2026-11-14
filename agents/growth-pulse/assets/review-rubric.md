# Review rubric

Used by the fresh reviewer of [`../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md) on the report and the experiments handoff, after `check_report.py`, `check_experiments.py` and the writing gate passed. The packet holds the brief, `pulse.json`, the report, the handoff and the check outputs. Score each criterion 0, 1 or 2 and locate everything under 2.

| # | Criterion | 2 | 1 | 0 |
|---|-----------|---|---|---|
| 1 | Numbers | every figure traces to pulse.json or the handoff, at the stated precision | a figure is right but out of context (wrong week, wrong comparison) | a figure is wrong or invented |
| 2 | Noise and volume | flat moves are called flat, small volumes are counts, the reader knows what cannot be read | one flat move described as a rise or a drop | percentages on small volumes, noise read as news |
| 3 | Causes | moves are tied to actions in time only; every correlation is called a correlation | one sentence leans causal | a correlation or a coincidence presented as a cause |
| 4 | Source health | every missing or stale source is named with what it hides | named without the consequence | a missing source goes unmentioned |
| 5 | Continuity | each experiment of last run has its verdict and its consequence for the sprint | verdicts listed without consequence | last run's experiments ignored |
| 6 | Experiments | three falsifiable bets, one metric each, readable in their duration, tied to evidence, at least two stages | one experiment vague or unreadable in its duration | experiments that no metric can judge |
| 7 | Reader value | the founder knows in five minutes what to keep, stop and start | the actions are there but buried | a data dump with no decision |
| 8 | Voice and form | plain, specific, passes the writing gate, no filler | minor tics | reads generated |

Total out of 16. Under 13, or any 0, is a FAIL.
