# Example: swanbase, pre-seed founders (2026-10-12)

A light, reproducible run of first-users-hunter for the stack's example brand (swanbase, a Paris accelerator for first-time founders). **Every person is fictional.** The API answers are frozen in [`../../tests/fixtures/api/`](../../tests/fixtures/api/): the field shapes of the real APIs as recorded on 2026-10-12, with fictional authors, ids and texts. No network is needed. Output: [`preview.md`](preview.md).

| File | What it is | Written by |
|------|-----------|------------|
| `config.json` | ICP keywords and the queries of each source | the model, Step 1 |
| `run/manual-signals.csv`, `run/texts/` | LinkedIn and X posts found by web search, with their text | the model, Step 2 |
| `run/activity-manual.csv` | own LinkedIn and X posts of the candidates (dates come from the ids) | the model, Step 4 |
| `run/identities.json` | one merge (an HN profile that links a LinkedIn profile), with its evidence | the model, Step 3 |
| `people-20261012.jsonl` | the deliverable: four people, fit and touches | the model, Step 6 |
| `preview.md` | the report, shortened | the model, Step 9 |

Everything else (signals, cache, candidates, activity, shortlist, CSV, dossiers) is rebuilt by the scripts.

## What it shows

- **Kept, 4 people**: two Ask HN requests for help, a LinkedIn post asking for a program in Paris before the round, and a Luma host of a founders breakfast. Each has a dated signal, a verbatim excerpt found in the cached page, and at least 2 weighted own posts in the window.
- **Dropped at drafting, 1**: a GitHub issue asking for a waitlist tool. Real signal, active person, but no overlap with an accelerator: dropped rather than forced.
- **Rejected by the scripts, 7**: a LinkedIn ask from June (stale), a list row with no signal of its own (seed), a deleted GitHub account (`dead_handle`), an HN commenter with one post, an X account with one post and two replies (`not_proven`), a company director from the registry with no public handle (`not_proven`), and an X row whose date contradicted its post id (refused by the manual collector).

## Rebuild

From `agents/first-users-hunter/`, outputs in `/tmp/fuh-example` (this folder holds inputs only):

```bash
EX=examples/swanbase-preseed-founders-20261012
rm -rf /tmp/fuh-example && mkdir -p /tmp/fuh-example && cp -R $EX/run/. /tmp/fuh-example/
python3 scripts/pipeline.py --config $EX/config.json --run-dir /tmp/fuh-example --fixtures tests/fixtures/api --today 2026-10-12
python3 scripts/verify_people.py $EX/people-20261012.jsonl --run-dir /tmp/fuh-example --today 2026-10-12 --out /tmp/fuh-example/verify.json
python3 scripts/export_handoff.py $EX/people-20261012.jsonl --run-dir /tmp/fuh-example --out-dir /tmp/fuh-example/out --today 2026-10-12
python3 ../../shared/skills/writing-gate/scripts/lint_copy.py /tmp/fuh-example/out/first-touches-20261012.md
```

Expected: 5 shortlisted, verify 4 ok, export 4 rows and 4 dossiers, writing gate 0 BLOCK. Then cold-outreach-builder reads the handoff with its own scripts:

```bash
cd ../cold-outreach-builder
python3 scripts/verify_dossiers.py /tmp/fuh-example/out/handoff-20261012/dossiers --cache /tmp/fuh-example/out/handoff-20261012/cache --today 2026-10-12 --out /tmp/fuh-example/cob-verify.json
```

Expected: 4 dossiers ok, 4 facts verified. `tests/run_tests.py` runs the same chain.
