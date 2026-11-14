# scripts/

The model researches and writes; these scripts check, score, assemble and remember. Every script runs alone (`--help`), uses the Python 3.9+ standard library only, makes no paid call, and is deterministic: the same files give the same result. Commands below run from `agents/cold-outreach-builder/`.

## Requirements

- Python 3.9+
- No third-party package (`requirements.txt` is intentionally empty)
- Network only for `cache_page.py` (fetching a page) and `check_sender.py` (DNS). Both have an offline path: `--from-file` and `--records`.

## The scripts, in workflow order

| Script | Step | Does | Writes |
|--------|------|------|--------|
| `outreach_state.py` | 0, 10, 11 | Memory between runs: `init`, `check` (leads already contacted, suppressed, or touched under the recontact delay), `register` (an exported sequence, with planned step dates), `mark-sent`, `suppress`, `answered`, `due` (next actions), `summary` (counts per sequence, tier or angle, never a winner), `show` | `state/state.json` |
| `run_dossiers.py` | 4 | `prepare` normalizes the lead list, drops leads the state excludes, writes one research brief per prospect; `status` tells done, invalid, pending and the next wave of three; `run` optionally starts a model CLI per brief (`--agent-cmd` or `FOG_AGENT_CMD`), three at a time, and checks the file each produced | `leads.csv`, `excluded-already-contacted.csv`, `dossiers/<id>/brief.md`, `dossiers/queue.json` |
| `cache_page.py` | 4 | Keeps every page read: fetches with urllib, or stores text another provider fetched (`--from-file`). Refuses LinkedIn profile and company pages. | `cache/<hash>.txt`, `.html`, `index.json` |
| `verify_dossiers.py` | 5 | Schema of each `prospect.json`, then per fact: page cached, excerpt present in the page, date not in the future, LinkedIn or X post date read from the post id, post owner, age against the freshness window (stale facts never score) | `dossiers/verify.json` |
| `score_prospects.py` | 6 | Applies the criteria grid to verified facts only: score and tier A, B or C with the reason | `tiers.json`, `tiers.csv` |
| `build_sequence_export.py` | 8 | Templates for tier B, written steps for tier A (`messages.json`), hooks, `{{?token}}` optional lines, skips tier C, the state's exclusions, rows without contact or with an unfilled token | `sequence-export.csv`, `.skipped.csv` |
| `lint_outreach.py` | 9 | The gate on the export: shared writing gate engine and packs, outreach packs, plus duplicates of address and hook between prospects, unfilled variables, length, links, subject, sourced fact in message 1, numbers, signature. Exit 1 while a BLOCK remains. | stdout, `--out lint.json` |
| `check_sender.py` | 2 | SPF, DKIM (selectors given), DMARC, MX by DNS only (dig, else DNS over HTTPS, else `--records`), sending plan from inbox age. Never an SMTP probe. | stdout, `--out sender-check.json` |
| `ingest_replies.py` | 11 | Reads exported replies (CSV, `.eml`, `.mbox`), removes quoted history, classifies positive, negative, out of office, off topic, bounce with the triggering sentence, updates the state; ambiguous replies wait for an override that quotes the reply | `replies-<date>.md`, the state |
| `outreach_lib.py` | | Shared helpers (paths, cache hash, HTML to text, post-id dates, contact keys). Not a command. | |

## Single sources

| File | Read by | Holds |
|------|---------|-------|
| `assets/prospect.schema.json` | `verify_dossiers.py`, `run_dossiers.py` | The dossier contract |
| `assets/criteria.example.json` | `verify_dossiers.py` (freshness), `score_prospects.py` | Points, freshness windows, tier thresholds, exclusions |
| `assets/limits.json` | `lint_outreach.py`, `build_sequence_export.py`, `outreach_state.py` | Words, characters, links, subject, hook similarity, number patterns, signature token, recontact delay |
| `assets/patterns/outreach.en.json`, `assets/patterns/outreach.fr.json` | `lint_outreach.py` | Outreach rules in the writing-gate pack format |
| `assets/reply-rules.json` | `ingest_replies.py` | Reply cues per class, auto-reply headers, return-date patterns |

Each one can be overridden per project with a file of the same shape in `<your-projects-root>/<project>/cold-outreach-builder/` (`--criteria`, `--limits`, `--rules`): keys are merged over the shipped file.

## File formats

`messages.json` (written by the agent at Step 7, read by the export):

```json
{
  "p001": {
    "hook": "One sentence on a verified fact, exactly as it appears in message 1.",
    "hook_fact_id": "f2",
    "angle": "launch",
    "steps": [ { "n": 1, "subject": "...", "body": "Hi Maya,\n\n...\n\n{{sender_first_name}}" } ]
  },
  "p002": { "hook": "...", "hook_fact_id": "f1", "angle": "talk" }
}
```

`steps` is for tier A only; a step listed there replaces the template step with the same `n`. `"hold": "<reason>"` keeps a prospect out of the export (a row that still blocks after three lint passes). Tier B rows take the templates of `cold-outreach-output.json` with `{{hook}}` filled.

`sequence-export.csv` columns: `prospect_id`, `tier`, `email`, `first_name`, `last_name`, `company`, `role`, `linkedin_url`, `hook`, `hook_fact_id`, `hook_source_url`, `hook_date`, `angle`, `specific_observation`, `personal_hook`, `source_url`, `subject_variant`, then `step_N_subject`, `step_N_body`, `step_N_delay_days` per step, then any extra lead column. RFC 4180, UTF-8. An empty `step_N_subject` means "reply in the same thread". `{{sender_first_name}}` is the only token allowed to remain (the sequencer fills it) unless `--sender-first-name` renders it.

## Tests (offline)

```bash
python3 agents/cold-outreach-builder/tests/run_tests.py        # from the repo root; -v lists every check
```

No network, no API key, outputs in a temporary folder. It runs:

- the outreach packs against `shared/schemas/copy-rules.schema.json` and their `bad` / `good` examples;
- `tests/fixtures/regression-20260428/`: an anonymized LinkedIn sequence of a real run, which must exit 1 with at least 5 BLOCK (its six dashes, unsourced numbers, unfilled `{{link}}`, no sourced fact, an over-long connection note, the pitch disclaimer, the invented scarcity);
- `tests/fixtures/structural/`: duplicate address, identical and near-identical hooks, placeholders, links, shortener, subject, signature, length, bullets, numbers, missing hook;
- the example `examples/swanbase-preseed-founders-20261012/` end to end (verify, score A/B/C, export, lint at 0 BLOCK), then tampered copies that must block;
- `tests/fixtures/dossiers/`: excerpt not in the page, page not cached, LinkedIn post date and owner read from the URL, future date, stale fact, email not on its page, schema error;
- the export template syntax (`{{?token}}`, unresolved token, delays);
- state and replies with `tests/fixtures/replies/`: classification of CSV and `.eml` replies, bounce mapped to its recipient, out-of-office return date, idempotent re-run, overrides accepted only with a quote from the reply, `due`, `check`, refused re-registration, export skipping contacted people;
- `run_dossiers.py` with `tests/fake_agent.py` standing in for a model CLI: waves, a failed task, resume;
- `check_sender.py` on `tests/fixtures/dns/` (pass, every check failing, no selector) and the absence of any SMTP code;
- `cache_page.py`: hash, LinkedIn profile refused, HTML stored as text.

Expected last line: `153 passed, 0 failed`. Also run, from the repo root, `python3 scripts/validate_stack.py` and `python3 shared/skills/writing-gate/tests/run_tests.py`.

## Exit codes

`lint_outreach.py`, `verify_dossiers.py`, `check_sender.py`: 0 pass, 1 at least one BLOCK, error or failed check, 2 usage error or unreadable input (DNS unreachable for `check_sender.py`). `run_dossiers.py status|run`: 1 while a dossier is pending or invalid. `ingest_replies.py`: 1 when an override was rejected. `outreach_state.py register`: 1 when a contact was refused. `build_sequence_export.py`: 1 on bad input only (skipped rows are not an error).

## Cross-platform notes

Forward slashes only. Works the same on macOS, Linux and Windows (use `python` instead of `python3` if that is how Python is installed). Open CSV files as UTF-8 in a spreadsheet so accents survive.
