# Example: swanbase, pre-seed founders (2026-10-12)

A light, reproducible run of cold-outreach-builder for the stack's example brand. Three fictional prospects, five fictional source pages on `.example` domains, no real person, no network access needed. Output: [`preview.md`](preview.md).

| File | What it is |
|------|-----------|
| `leads.csv` | The lead list, in the first-users-hunter prospect format |
| `cache/` | The pages read for the dossiers, as `cache_page.py` stores them (`<hash>.txt`, `index.json`) |
| `dossiers/<id>/prospect.json` | One dossier per prospect: dated facts with URL and verbatim excerpt |
| `cold-outreach-output.json` | The sidecar: channel and the 4-step template sequence tier B receives |
| `messages.json` | Hooks per prospect, and the 4 steps written for the tier A prospect |
| `preview.md` | Tiers, the rendered messages of the A and B prospects, the C reason, the lint result |

What it shows:

- **p001, tier A.** A company registered on 2026-08-20, a private beta opened on 2026-09-29, a dated note by the founder: every step is written for her around those facts.
- **p002, tier B.** One verified fact, a talk from March 2026, older than the 120-day strong window: the shared template, with a hook line built on the talk.
- **p003, tier C.** Nothing true and dated on public pages: not exported, never sent a generic message.

## Rebuild

From `agents/cold-outreach-builder/`, outputs in `/tmp/cob-example` (the folder holds inputs only):

```bash
EX=examples/swanbase-preseed-founders-20261012
python3 scripts/verify_dossiers.py $EX/dossiers --cache $EX/cache --today 2026-10-12 --out /tmp/cob-example/verify.json
python3 scripts/score_prospects.py $EX/dossiers --verify /tmp/cob-example/verify.json --today 2026-10-12 --out /tmp/cob-example/tiers.json
python3 scripts/build_sequence_export.py --sequence $EX/cold-outreach-output.json --leads $EX/leads.csv \
  --tiers /tmp/cob-example/tiers.json --messages $EX/messages.json --dossiers $EX/dossiers \
  --out /tmp/cob-example/sequence-export.csv
python3 scripts/lint_outreach.py /tmp/cob-example/sequence-export.csv --dossiers $EX/dossiers \
  --verify /tmp/cob-example/verify.json --sequence $EX/cold-outreach-output.json
```

Expected: verify 3 ok, tiers A 1 / B 1 / C 1, export 2 rows (p003 in `sequence-export.csv.skipped.csv`), lint 0 BLOCK. `tests/run_tests.py` runs the same chain.

The signature stays `{{sender_first_name}}`: the sequencer fills it, or `--sender-first-name` renders it from your own config. No equity figure, no reply-rate figure, no invented practice: the offer line is the one in `cold-outreach-output.json`.
