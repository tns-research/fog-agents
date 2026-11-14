# Sprint report: demo-calls-20261012

- Goal: 20 demo calls booked with first-time founders this month (measured by demo calls booked, target 20)
- Status: complete
- Approved by: Alex Martin on 2026-10-12T11:21:42+00:00
- Budget: 64.00 EUR spent of 70.00 EUR approved

## Summary

**Toward the goal.** Demo calls booked: not measured yet, growth-pulse found no booking metric (`growth-pulse/experiments-20261012.json`, experiment E-20261012-1 instruments it first). What shipped for the goal: a prospect list and a three-step sequence (`cold-outreach-builder/outreach-20261012/`), one carousel queued on LinkedIn and X and approved, two ad batches packaged PAUSED, three shorts.

**This week, in order:**
1. Import the outreach sequence into your sequencer and send it (`cold-outreach-builder/outreach-20261012/sequence-export.csv`).
2. Check the two scheduled posts in the dry-run outbox and post them at their slots (`content-publisher/outbox/`).
3. Import the two ad batches, still PAUSED, and start the TOFU batch (`static-ads-builder/demo-tofu-20261012/`).
4. Post the three shorts after watching them (`short-video-builder/pitch-talk-20261012/posts.md`).
5. Add a booking event to your analytics so the next growth-pulse can count demo calls.

**Waiting for you:** nothing.

**Decided without you:** the carousel uses the editorial-paper direction, ranked first on the cover board.

**Not done and why:** nothing; the landing audit needed a third attempt after two runs without a valid report.

## Steps

| Step | Agent | Status | Attempts | Spent (EUR) | Verified outputs |
|------|-------|--------|----------|-------------|------------------|
| `s01-context` | project-context | skipped | 0 | 0.00 | none |
| `s02-signal` | market-signal | done | 1 | 0.00 | `market-signal/market-signal-20261012.json`<br>`market-signal/market-signal-20261012.md` |
| `s03-people` | first-users-hunter | done | 2 | 0.00 | `first-users-hunter/people-20261012.jsonl`<br>`first-users-hunter/prospects-20261012.csv`<br>`first-users-hunter/first-users-20261012.md` |
| `s04-landing` | landing-page-analyzer | done | 3 | 0.00 | `landing-page-analyzer/landing-audit-20261012.json`<br>`landing-page-analyzer/landing-audit-20261012.md` |
| `s05-carousel` | carousel-builder | done | 1 | 0.00 | `carousel-builder/demo-objections-20261012/deck.json`<br>`carousel-builder/demo-objections-20261012/export/carousel.pdf`<br>`carousel-builder/demo-objections-20261012/export/qa.json`<br>`carousel-builder/demo-objections-20261012/captions.md` |
| `s06-ads` | static-ads-builder | done | 2 | 34.00 | `static-ads-builder/demo-tofu-20261012/ads.json`<br>`static-ads-builder/demo-tofu-20261012/renders/contact-sheet.jpg`<br>`static-ads-builder/demo-tofu-20261012/static-ads-20261012.md` |
| `s07-outreach` | cold-outreach-builder | done | 1 | 0.00 | `cold-outreach-builder/outreach-20261012/cold-outreach-output.json`<br>`cold-outreach-builder/outreach-20261012/sequence-export.csv`<br>`cold-outreach-builder/outreach-20261012/outreach-summary-20261012.md` |
| `s08-publish` | content-publisher | done | 2 | 0.00 | `content-publisher/demo-week-20261012/posts.json`<br>`content-publisher/queue.json`<br>`content-publisher/demo-week-20261012/review-20261012.md` |
| `s09-shorts` | short-video-builder | done | 1 | 0.00 | `short-video-builder/pitch-talk-20261012/clips.json`<br>`short-video-builder/pitch-talk-20261012/export/qa.json`<br>`short-video-builder/pitch-talk-20261012/posts.md` |
| `s10-retarget` | static-ads-builder | done | 1 | 30.00 | `static-ads-builder/demo-bofu-20261012/ads.json`<br>`static-ads-builder/demo-bofu-20261012/renders/contact-sheet.jpg`<br>`static-ads-builder/demo-bofu-20261012/static-ads-20261012.md` |
| `s11-pulse` | growth-pulse | done | 1 | 0.00 | `growth-pulse/experiments-20261012.json`<br>`growth-pulse/growth-pulse-20261012.md` |

## Waiting for you

- Nothing.

## Decided by a person during the sprint

- `H-01` (input, `s09-shorts`): required input(s) video: not in the plan nor in the project. Cleared by Alex Martin on 2026-10-12T11:21:40+00:00, then rerun
- `H-02` (spend, `s06-ads`): Gate 1: two concepts need a photo plate. Cleared by Alex Martin on 2026-10-12T11:21:40+00:00, then rerun (Gate 1 and 2 answered in the agent session)
- `H-03` (publish, `s08-publish`): 2 item(s) of content-publisher/queue.json still to_review. Cleared by Alex Martin on 2026-10-12T11:21:40+00:00, then rerun
- `H-04` (budget, `s10-retarget`): estimate 20.00 EUR, budget left 6.00 EUR. Cleared by Alex Martin on 2026-10-12T11:21:42+00:00, then rerun

## Decided without you (agent defaults)

- `s05-carousel`: direction: editorial-paper, best ranked at the cover board

## Breaker, interruptions, budget alerts

- 2026-10-12T11:21:38+00:00 interrupted `s03-people`
- 2026-10-12T11:21:38+00:00 halt `s04-landing`: s04-landing failed 2 times in a row: outputs not verified: report-json missing
- 2026-10-12T11:21:39+00:00 halt_cleared `s04-landing`
- 2026-10-12T11:21:41+00:00 budget_alert: spent 34.00 EUR, 85% of the cap 40.00 EUR
- 2026-10-12T11:21:41+00:00 plan_changed: d3dcb41d -> ed254db1
- 2026-10-12T11:21:42+00:00 halt `s10-retarget`: spent 64.00 EUR above the approved cap 60.00 EUR
- 2026-10-12T11:21:42+00:00 plan_changed: ed254db1 -> 8262323e
- 2026-10-12T11:21:42+00:00 halt_cleared: new cap approved

## Input for the next sprint

- `growth-pulse/experiments-20261012.json`: pick one experiment as the next goal (`goal.source`: `growth-pulse/experiments-20261012.json#<experiment id>`).
