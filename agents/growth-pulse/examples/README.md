# examples/

## swanbase-20261014

Week 2026-W41 of the fictional swanbase site (a Paris accelerator), run on Wednesday 2026-10-14. Every number is invented by `scripts/fixtures/make_fixtures.py`; no real account was read.

| File | What it is |
|------|-----------|
| [`swanbase-20261014/growth-pulse-20261014.md`](swanbase-20261014/growth-pulse-20261014.md) | the report, passes `check_report.py` and the shared writing gate at 0 BLOCK |
| [`swanbase-20261014/pulse.json`](swanbase-20261014/pulse.json) | every number of the week, rebuilt byte for byte by the selftest |
| [`swanbase-20261014/experiments-20261014.json`](swanbase-20261014/experiments-20261014.json) | the three experiments of the next sprint, filled and checked by `check_experiments.py` |
| [`swanbase-20261014/config.json`](swanbase-20261014/config.json) | the project config of the run |

Sources: Umami and Search Console by replayed API responses, LinkedIn and Instagram by CSV export, revenue by payments CSV, Plausible and GA4 not configured. Last run's experiments come from `scripts/fixtures/previous/experiments-20260930.json`.

Rebuild `pulse.json` after a deliberate change to the scripts or the fixtures:

```bash
python3 agents/growth-pulse/scripts/selftest.py --write-example
python3 agents/growth-pulse/scripts/selftest.py
```
