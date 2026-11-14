# examples/

| Example | What it shows | Command |
|---------|---------------|---------|
| [`swanbase-demo-calls-20261012/`](swanbase-demo-calls-20261012/) | A plan for the stack's example brand, its approval packet and the report of a simulated run with every rail exercised (interruption, breaker, spend gate, publication approval, missing input, budget) | `python3 agents/growth-sprint/scripts/selftest.py --keep /tmp/growth-sprint-demo` |

The selftest copies `sprint.json` into a fictional project (`scripts/fixtures/swanbase/`), approves it as a fictional founder and plays every step with fake outputs taken from the other agents' examples. Commands run from the repo root.

## Adding an example

A folder `<brand>-<goal>-<YYYYMMDD>/` with `sprint.json` (it must pass `sprint.py validate` on the fixture project), the `approval.md` that `sprint.py packet` writes for it, and a report. Paths of the run are replaced by `<your-projects-root>`. Examples are in English, on the example brand, with fictional people and no invented benchmark.
