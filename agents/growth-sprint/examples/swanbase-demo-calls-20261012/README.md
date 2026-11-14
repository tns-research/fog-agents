# swanbase-demo-calls-20261012

A fictional sprint for the stack's example brand (swanbase, an accelerator in Paris). Goal: 20 demo calls booked with first-time founders this month, 40 EUR cap for image plates. The agents prepare the prospects, sequences, visuals and queue items; a person sends, and the fictional founder counts the calls. The 40 EUR caps image-model calls on that founder's own account and is never ad spend.

| File | What it is |
|------|-----------|
| [`sprint.json`](sprint.json) | The plan: 11 steps over 10 agents, two static-ads batches that may spend, one content-publisher step that publishes, a short-video step whose video nobody gave yet |
| [`approval.md`](approval.md) | The packet the founder approves from, written by `sprint.py packet` |
| [`sprint-report-20261012.md`](sprint-report-20261012.md) | The report of the run simulated by `scripts/selftest.py`: an interruption, a step that claimed done with nothing on disk (breaker, cleared by the founder), the static-ads spend gate, the posts approved by the founder in their own terminal, a missing video supplied, the budget alert, a batch that no longer fit, a raised cap approved twice |

Every agent output of the simulated run is a copy of that agent's own repo example or a fixture: nothing here comes from a real campaign, and the people and figures are fictional. Rebuild the run and keep its files:

```bash
python3 agents/growth-sprint/scripts/selftest.py --keep /tmp/growth-sprint-demo
```
