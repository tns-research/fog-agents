# scripts/

Collectors and scripts gather, date, verify and score; the model reads threads, judges the fit and writes the touches. Every script runs alone (`--help`), uses the Python 3.9+ standard library only, makes no paid call, and is deterministic on the same files. Commands below run from `agents/first-users-hunter/`.

## Requirements

- Python 3.9+
- No third-party package (`requirements.txt` is intentionally empty)
- Network only for the collectors in live mode and for `cache_page.py`. Both have an offline path: `--fixtures <dir>` replays frozen API answers, `cache_page.py --from-file` stores text fetched by another tool.
- Optional keys, all free: `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` (a Reddit "script" app), `GITHUB_TOKEN` (GitHub discussions only). Without them the source is `skipped` and the run continues.

## The scripts, in workflow order

| Script | Step | Does | Writes (in the run folder unless said) |
|--------|------|------|--------|
| `collect.py signals` | 2 | Runs every enabled collector, validates each record against `assets/signal.schema.json`, merges by `signal_id`, caches the verbatim text of each signal for its URL, records source health | `signals.jsonl`, `cache/`, `source-health.json` |
| `candidates.py` | 3 | Groups signals by person (handles a source publishes together, `identities.json`), keeps eligible signals in their window with an ICP keyword, excludes the founder's handles, `exclude_handles` and the ledger | `candidates.jsonl`, `rejected.jsonl` |
| `collect.py activity` | 4 | Each candidate's own posts in the window: HN, GitHub, Reddit by API, LinkedIn and X from `activity-manual.csv`; handle checks (404, null user) | `activity.jsonl`, `source-health.json` |
| `check_activity.py` | 4 | The gate: own posts only (tagged posts and homonyms ignored), dates from LinkedIn and X ids, weights by kind, window per network, `active` / `not_proven` / `dead_handle` | `activity.json` |
| `score_people.py` | 5 | Score from `assets/criteria.json`, order, top N with a suggested `person_id`, channel map from the people | `shortlist.jsonl`, `channels.json`, `rejected.jsonl` |
| `pipeline.py` | 2 to 5 | The five steps above in one command | the same |
| `cache_page.py` | 6 | Keeps every page read (thread, fit source), same layout and hash as cold-outreach-builder's cache; refuses LinkedIn profile pages | `cache/<hash>.txt`, `index.json` |
| `verify_people.py` | 7 | The gate on `people-<YYYYMMDD>.jsonl`: schema, excerpt in the cached page, signal age, post-id date and owner, activity and score equal to the scripts' results, published email, touch limits, no reused touch | `people-<YYYYMMDD>.verify.json` |
| `export_handoff.py` | 9 | Verifies, then writes the prospect CSV (handoff columns first, then signal columns), one cold-outreach-builder dossier per person with its cached pages, the first touches, the ledger (and purges never-contacted rows after `ledger_purge_days`) | `--out-dir`: `prospects-<date>.csv`, `handoff-<date>/`, `first-touches-<date>.md`, `ledger.csv` |
| `date_from_url.py` | any | Date, time and author of a LinkedIn or X post from its URL | stdout |
| `fuh_lib.py` | | Shared helpers (files, criteria, cache, text folding, post-id dates, owners). Not a command. | |

### Collectors (`collectors/`)

One file per source, one contract (`collectors/common.py`): `collect_signals(cfg, fetch, today, criteria)`, optional `collect_activity(handle, ...)`, records in the shape of `assets/signal.schema.json`. Each runs alone: `python3 scripts/collectors/<name>.py --help | --config CFG | --activity HANDLE | --fixtures DIR | --record DIR | --out FILE`.

| Collector | Source | Key | Activity check |
|-----------|--------|-----|----------------|
| `hn.py` | HN Algolia `search_by_date`, user API | none | yes |
| `github.py` | search/issues, users/<u>/events/public, GraphQL discussions | none (discussions: `GITHUB_TOKEN`) | yes |
| `reddit.py` | official OAuth (`client_credentials`) | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | yes |
| `luma.py` | public city and event pages (`__NEXT_DATA__`) | none | no (hosts' published LinkedIn and X handles are linked) |
| `notion.py` | public Notion database (`loadPageChunk`, `queryCollection`) | none | no (seeds) |
| `folk.py` | shared folk view (GraphQL `sharedViewContactList`) | none | no (seeds) |
| `registry_fr.py` | `recherche-entreprises.api.gouv.fr/search` | none | no (seeds; birth dates never read) |
| `manual.py` | `manual-signals.csv`, `activity-manual.csv` in the run folder | none | LinkedIn, X, closed groups |

`--record <dir>` saves every live answer in the fixture format (Authorization headers are never written), so a new source gets a frozen fixture from one live call.

## Single sources

| File | Read by | Holds |
|------|---------|-------|
| `assets/criteria.json` | every script | signal types and max ages, classifier patterns, activity gate, score points, touch limits |
| `assets/signal.schema.json` | `collect.py` | collector contract |
| `assets/person.schema.json` | `verify_people.py` | people file contract |
| `assets/handoff/cold-outreach-prospect.schema.json` | `export_handoff.py` | copy of cold-outreach-builder's dossier schema 1.0 (the tests fail if it drifts) |

A project `criteria.json` with the same shape is merged over `assets/criteria.json` with `--criteria`; `config.json` `recency_days` and `activity` override the windows and the gate.

## Tests (offline)

```bash
python3 agents/first-users-hunter/tests/run_tests.py        # from the repo root; -v lists every check
```

No network, no key, outputs in a temporary folder. It runs:

- `--help` of every script and collector;
- dates and owners from LinkedIn and X ids (fixed values and round trips), `date_from_url.py`, published-email checks;
- every collector on `tests/fixtures/api/` (the shape of the real APIs as recorded on 2026-10-12, fictional people and content), plus the skip paths without a key (Reddit, GitHub discussions) and a missing fixture;
- the pipeline end to end on `examples/swanbase-preseed-founders-20261012/`: signals, merges, stale and seed-only rejections, the activity gate (tagged post ignored, dead handle, not proven), scores and order, source health, determinism of a re-run;
- `verify_people.py` on the example people file, then tampered copies: excerpt, post-id date, activity, inactive person, score, link in touch 1, X length, connection-note length, dash, placeholder, reused touch, `package@version` email, post owner, missing touch, stale later;
- `export_handoff.py`: CSV columns, dossiers valid against the copied schema with their cached pages, ledger and its purge, ledger exclusions on a re-run, export refused on errors;
- the shared writing gate on the first touches (0 BLOCK);
- when `agents/cold-outreach-builder/` sits next to this agent: the schema copy is in sync, its `verify_dossiers.py` passes on the handoff, its `run_dossiers.py prepare` and `status` see every dossier done;
- no paid API, SMTP or dead source in the scripts.

Expected last line: `164 passed, 0 failed`. Also run, from the repo root, `python3 scripts/validate_stack.py`.

## Exit codes

`verify_people.py`: 0 no error, 1 at least one error, 2 usage error. `export_handoff.py`: 0 exported, 1 verification errors (nothing written), 2 usage error. `pipeline.py`: 0 shortlist written, 1 a step failed. `collect.py`, `candidates.py`, `check_activity.py`, `score_people.py`: 0 done (a failed source is recorded in health, not an exit code), 2 usage error. Collectors alone: 0 ok or skipped, 1 the source failed, 2 usage error. `date_from_url.py`: 1 when a URL has no post id. `cache_page.py`: 1 when a URL failed.

## Cross-platform notes

Forward slashes only. Works the same on macOS, Linux and Windows (use `python` instead of `python3` if that is how Python is installed). Open CSV files as UTF-8 in a spreadsheet so accents survive.
