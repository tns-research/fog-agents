# Sprint approval: demo-calls-20261012

- Project: `swanbase`
- Goal: 20 demo calls booked with first-time founders this month
- Measured by: demo calls booked, target 20, by 2026-11-12
- Goal source: `founder`
- Plan fingerprint: `d3dcb41d6deb` (start of the sha256 of sprint.json; any edit changes it and voids the approval)

## Steps

| Step | Agent | After | Spends | Publishes | Estimate (EUR) | Basis |
|------|-------|-------|--------|-----------|----------------|-------|
| `s01-context` | project-context | start | no | no | 0.00 | no spend |
| `s02-signal` | market-signal | s01-context | no | no | 0.00 | no spend |
| `s03-people` | first-users-hunter | s01-context | no | no | 0.00 | no spend |
| `s04-landing` | landing-page-analyzer | s01-context | no | no | 0.00 | no spend |
| `s05-carousel` | carousel-builder | s02-signal | yes | no | 0.00 | local render, no image model planned |
| `s06-ads` | static-ads-builder | s02-signal | yes | no | 12.00 | founder's ceiling for photo plates in this batch, confirmed again at the agent's Gate 2 |
| `s07-outreach` | cold-outreach-builder | s02-signal, s03-people | no | no | 0.00 | no spend |
| `s08-publish` | content-publisher | s05-carousel | no | yes | 0.00 | no spend |
| `s09-shorts` | short-video-builder | s01-context | no | no | 0.00 | no spend |
| `s10-retarget` | static-ads-builder | s06-ads | yes | no | 20.00 | founder's ceiling for two photo plates, confirmed again at the agent's Gate 2 |
| `s11-pulse` | growth-pulse | s07-outreach, s08-publish | no | no | 0.00 | no spend |

## Budget

- Cap: 40.00 EUR (founder's ceiling for image plates this month). Step estimates total 32.00 EUR.
- Alert at 80% of the cap. Spent above the cap stops the sprint (circuit breaker) until you approve a new plan.
- A spending step whose estimate no longer fits in what is left waits for you in needs_human; the other steps go on.

## What this approval lets the sprint do without asking you again

- Run every step above in order, in parallel where the graph allows, and retry a failed step once.
- Steps that may spend, each up to its estimate: `s05-carousel` (0.00 EUR), `s06-ads` (12.00 EUR), `s10-retarget` (20.00 EUR).
- Steps that prepare a publication: `s08-publish`.

## What stays with you (never cleared by the sprint)

- `s06-ads` static-ads-builder, spend gate `plates-gate-1-and-2`: Open a static-ads-builder session on this run: answer Gate 1 (which plates) and Gate 2 (model, resolution, total) yourself, or drop your own files with --provider manual. Then resolve the needs_human item.
- `s08-publish` content-publisher, publish gate `publish-approval`: Read the review packet, then approve each item yourself in your own terminal: python3 agents/content-publisher/scripts/pubqueue.py approve <id> --queue <project>/content-publisher/queue.json --by <your-name> (or reject it). Then resolve the needs_human item; the sprint re-runs content-publisher to schedule what you approved.
- `s10-retarget` static-ads-builder, spend gate `plates-gate-1-and-2`: Open a static-ads-builder session on this run: answer Gate 1 (which plates) and Gate 2 (model, resolution, total) yourself, or drop your own files with --provider manual. Then resolve the needs_human item.
- Any input nobody can supply, any spend beyond the cap, any step failing twice in a row.
- These land in the needs_human queue (`sprint.py status`); the steps that do not depend on them keep running.

## Warnings

- s09-shorts: required input(s) video not given and not in the project: the step will wait in needs_human

## Approve

Read the plan, then run this yourself, in your own terminal (the sprint never runs it for you). It shows the plan fingerprint, the cap and the steps that spend or publish, prints a plan code and asks you to type it:

```bash
python3 agents/growth-sprint/scripts/sprint.py approve <your-projects-root>/swanbase/growth-sprint/demo-calls-20261012 --by <your-name>
```

To change the plan, edit sprint.json, run `sprint.py packet` again and approve the new version.
