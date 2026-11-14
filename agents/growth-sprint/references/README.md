# references/

| File | Read by | What it holds |
|------|---------|---------------|
| [`../assets/agents.json`](../assets/agents.json) | planning-sprint, `scripts/sprint.py`, `scripts/check_step.py` | The registry of the agents a sprint can chain: inputs, outputs with their checks and schemas, spend, publication, human gates |
| [`../../../shared/handoffs.md`](../../../shared/handoffs.md) | planning-sprint | Which agent reads which file: the dependencies of a plan |
| [`../../../shared/schemas/README.md`](../../../shared/schemas/README.md) | contributors | The shared contracts, including the run line every agent appends |

## Design notes

- **Verification on disk, never on the worker's word.** A worker can exit cleanly and write nothing. A step is done when its declared outputs exist, were written after the step started, and validate against the producing agent's own schema. The step result file and the run line can send a step to a person or to failure, never to done.
- **One approval, bound to the plan.** The approval records a person's name and the hash of `sprint.json`; any edit voids it. `approve` runs only at an interactive terminal, shows the plan fingerprint the packet carries, prints a plan code (an HMAC under a local key kept outside the project) and asks the person to type it. The record is sealed with the same key, so an approval written into `state.json` by hand is refused. This stops an agent that follows its workflow and any manual edit; it is not a sandbox.
- **Gates stay where they are.** The sprint approval never answers an agent's own gate (static-ads Gate 1 and Gate 2, the content-publisher approval). It surfaces them in needs_human, and `resolve` re-reads the disk before closing a publication item.
- **Bounded by construction.** A sprint is a finite graph that ends in a report; the breaker stops it on spend above the cap, two failures in a row on a step, or a STOP file. There is no idle loop.
- **Parallel when possible, sequential always possible.** Waves of three at most, never two runs of one agent at once, the shared queue writer alone; the same briefs run in sequence when the harness has no subagents.

## Updating the registry

When an agent changes its outputs or a new agent lands, update its entry in [`../assets/agents.json`](../assets/agents.json): output paths relative to the project folder with `<label>` and `<YYYYMMDD>` tokens, the check and the agent's own schema, `spends`, `publishes`, and its human gates. Then run `python3 agents/growth-sprint/scripts/selftest.py`: it fails when an agent folder is missing from the registry or a schema path does not exist.
