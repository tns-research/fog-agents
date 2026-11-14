# scripts/

The sprint engine of growth-sprint. The model writes `sprint.json`; these scripts validate it, keep `state.json`, hand out steps and settle each one from the disk. Standard library only (Python 3.9+), every script answers `--help`, none of them runs another program: they can never approve, spend or publish for anyone.

| Script | Does | Writes |
|--------|------|--------|
| `sprint.py` | The state machine: `validate` (schema, registry, graph, spend and publish flags, budget, labels, goal source), `packet` (approval packet with the plan fingerprint), `approve` (interactive terminal only: a person's name, then the plan code it prints typed at the prompt; the record is sealed with an HMAC), `next` (wave of up to 3 runnable steps; `--claim` starts them and writes their briefs; automatic reuse, missing input and budget decisions), `mark` (`done` is settled by the disk check), `resolve` (a person closes a needs_human item, checked on disk when it can be), `status`, `resume` (after an interruption; a person clears a failures breaker), `report` (`--log` appends the run line) | `state.json`, `approval.md`, `briefs/<step>.md`, `sprint-report-<YYYYMMDD>.md`, one line of `project-context/memory/runs.jsonl` |
| `check_step.py` | The disk check of a step or of any agent run: newest output per registry entry, freshness against the step start, file, JSON, JSON Schema, JSONL, CSV columns; gates waiting on disk; result file and run line | stdout (`--json`) |
| `sprint_lib.py` | Registry loading, output checks, gate tests, inputs, run lines, result files, clock, lock file, atomic writes, schema validation through `shared/scripts/validate_json.py` | n/a |
| `selftest.py` | Offline regression test (below) | temporary folder |
| `fixtures/` | A fictional swanbase project (`swanbase/project-context/`) and fake agent outputs for the agents whose repo example cannot be copied as is (`outputs/`) | n/a |

## Quick run on the example

From the repo root, on a copy so the repo stays clean:

```bash
mkdir -p /tmp/gs-demo/swanbase/growth-sprint/demo-calls-20261012
cp -r agents/growth-sprint/scripts/fixtures/swanbase/project-context /tmp/gs-demo/swanbase/
cp agents/growth-sprint/examples/swanbase-demo-calls-20261012/sprint.json /tmp/gs-demo/swanbase/growth-sprint/demo-calls-20261012/
S=agents/growth-sprint/scripts
D=/tmp/gs-demo/swanbase/growth-sprint/demo-calls-20261012
python3 $S/sprint.py validate $D
python3 $S/sprint.py packet $D              # read $D/approval.md
python3 $S/sprint.py approve $D --by <your-name>   # in your own terminal: type the plan code it prints
python3 $S/sprint.py next $D --claim        # first wave and its briefs in $D/briefs/
python3 $S/check_step.py --sprint $D --step s02-signal   # exits 1 until market-signal has written its outputs
python3 $S/sprint.py status $D
```

## Exit codes

`sprint.py`: 0 ok (for `next`: a wave was returned), 1 refused or check failed, 2 usage error or unreadable file, 3 halted (STOP file or circuit breaker), 4 not approved (no approval, plan changed since, approval not recorded by `approve`, approval refused: reserved name, no interactive terminal, `--code` given, wrong code), 5 waiting for a person or for running steps, 6 sprint complete.

`check_step.py`: 0 done, 1 failed (output missing, stale or invalid, or the run reported failed), 2 usage error, 5 a gate or a pending item waits for a person.

## Tests

```bash
python3 agents/growth-sprint/scripts/selftest.py
```

Offline, about 10 seconds, no key, no network, no agent really run. It simulates a full sprint of the example plan on the fictional swanbase project with fake agent outputs (copies of the repo examples of market-signal, first-users-hunter, carousel-builder, static-ads-builder, content-publisher, short-video-builder, plus fixtures): registry coverage of every agent folder and of their schemas; plan validation and ten broken plans; the approval gate (reserved names, no packet, no terminal, `--code` refused, a wrong code typed at a pseudo-terminal, no plan code in the packet, `validate` or `state.json`, an approval written into `state.json` by hand and a sealed one whose cap was raised by hand both refused by `next`, an edited plan voids the approval); waves of three, one agent at a time, content-publisher alone; reuse of a fresh context; a missing input that waits without blocking; an interruption settled by `resume`; a step that claims done with nothing on disk; the failures breaker and its clearing by a person; the STOP file; the static-ads spend gate and the content-publisher approval surfaced and cleared only from the disk; the budget alert, a step that no longer fits, the budget breaker and its clearing by a new approval; the report, the run line against the shared schema, `state.json` against its schema; a growth-pulse experiment that seeds the next sprint; `check_step.py` on stale and broken files; `--help`. The approval key is a throwaway file (`FOG_APPROVAL_KEY_FILE`) in the work folder and approvals are typed through a pseudo-terminal (POSIX only). `--keep DIR` keeps the work folder.
