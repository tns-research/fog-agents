# scripts/

The market-signal engine. The model plans the collection, reads every record and writes two files (`labels.jsonl`, `analysis.json`); these scripts collect, count, verify and build the deliverables. Python 3.9+ standard library only (`requirements.txt` lists nothing to install). Every script answers `--help`, and the same inputs give the same files.

| Script | Does | Writes |
|--------|------|--------|
| `collect.py` | Runs the jobs of `plan.json` (contract: `assets/plan.schema.json`), one process per job, sources in parallel lanes (one lane per source so no provider gets concurrent requests), `--sequential` as fallback. `--only <ids>` re-runs some jobs and merges them with the job files already in the run folder. Merges and deduplicates by `record_id`. Watch mode: `--seen state/seen.json` drops records already seen and records the new ids; `--since-last-run` starts the window at the end of the last run in that file (it needs one). A re-run with `--seen` in the same run folder (second wave, `--only`) keeps the stored `corpus.jsonl` and, with `--since-last-run`, that run's window. `--fixtures` replays frozen responses, `--record` saves live ones, scrubbed like every live answer. | `corpus/<job>.jsonl`, `health/<job>.json`, `corpus.jsonl`, `health.json`, `manifest.json` |
| `collect_hn.py` | Hacker News through Algolia: stories and comments in the window, exact phrases, optional comments of the best threads. Comments of the job-seeker threads ("Who wants to be hired", "Seeking freelancer") are never stored. | records `hn:<id>` |
| `collect_reddit.py` | Reddit comments or posts through the Arctic Shift archive (reddit.com answers 403 to cloud IPs). | records `reddit:t1_<id>`, `reddit:t3_<id>` |
| `collect_stackexchange.py` | Questions, and optionally answers, of one Stack Exchange site (300 requests a day without a key). | records `se:<site>:q<id>` |
| `collect_discourse.py` | Posts of a public Discourse forum through `/search.json`, full text per post. | records `discourse:<host>:<id>` |
| `collect_appstore.py` | App Store reviews of one app through the iTunes RSS JSON feed (no date filter, stops past the window). | records `appstore:<app>:<review>` |
| `import_records.py` | Files to records: CSV or JSONL exports (G2, Capterra, Reddit threads saved with the founder's OAuth, interviews with consent) and the JSON of an optional provider (`exa search --json`). Rows without url or date are dropped. | records `<source>:<hash>` |
| `compute_signals.py` | Every number (thresholds `--min-authors`, `--min-communities`, counted speakers `--speakers`, language bank `--phrase-records`, `--phrase-authors`): per pain voices, distinct authors, communities, share by source, months, trend between window halves, resonance against the community median, escalation; corpus shares, sentiment counts, forces, alternatives named, language bank. Trend `unknown` and volume `lower_bound` when a capped collector fed the pain. | `stats.json` |
| `verify_quotes.py` | Finds each cited passage in its record (whitespace, curly quotes and Unicode composition tolerated, nothing else) and returns the exact text, url and date; BLOCK on an absent, recapitalised or elided passage, a date outside the window, a missing record, url or date, a removed text, a stated url or date that differs from the record; WARN on a short or mid-word passage. | the `--out` report (`quotes-check.json` when `build_handoff.py` runs it) |
| `diff_runs.py` | Watch mode: pains new, rising, falling, disappeared, newly escalated or no longer escalated (authors per 30 days, `--rise-ratio`, `--min-delta`), collectors whose health changed, alternatives named for the first time or no longer named, new phrases of the language bank. | `changes.json`, `changes.md` |
| `build_handoff.py` | Schema checks, `compute_signals` (voices: `--speakers`, default `user,practitioner`; an unknown speaker exits 2), `verify_quotes`, spec checks (references, verbatim hooks and objections, no bare number in the analyst's prose), then the sidecar v2, checked by `validate_sidecar`, and the report. Flags: `--out-dir`, `--min-authors`, `--min-communities`, `--speakers`, `--phrase-records`, `--phrase-authors`, `--valid-days`, `--no-report`. On any problem it refuses and writes neither the sidecar nor the report. | `stats.json`, `quotes-check.json` (in the run), `market-signal-<YYYYMMDD>.json`, `market-signal-<YYYYMMDD>.md` |
| `validate_sidecar.py` | The sidecar against `assets/market-signal.schema.json`, its id references, verbatim hooks and objections, its window, angle lengths and escalation flags, its prose, and the corpus it points to (hash, every quote found again; `--corpus` to give another path). `--stats` also compares every pain count with `stats.json`. Consumers without the corpus use `--no-corpus`. | n/a |
| `mslib.py` | Shared helpers: record format, HTTP with fixture and record modes, health, text normalisation, schema loading, privacy (`scrub`: every answer gets its handles pseudonymised and its emails, phone numbers, profile links and @mentions replaced before a collector reads it or a fixture stores it; records keep `author_hash`, never a handle). | n/a |
| `selftest.py` | Offline regression of everything above (next section). | n/a |

## Run layout

```
<your-projects-root>/<project>/market-signal/
├── state/seen.json                 # watch mode: record ids already collected, end of the last window
├── sources-rejected.md             # sources dropped, with the date and the reason
├── runs/<YYYYMMDD>/
│   ├── plan.json                   # model, Step 1
│   ├── corpus/<job>.jsonl  health/<job>.json      # collect.py, one file per job
│   ├── corpus.jsonl  health.json  manifest.json   # collect.py, merged
│   ├── labels.jsonl                # model, Step 3
│   ├── analysis.json               # model, Step 4
│   ├── stats.json  quotes-check.json              # build_handoff.py
│   └── changes.json  changes.md    # diff_runs.py, watch mode
├── market-signal-<YYYYMMDD>.json   # handoff sidecar v2
└── market-signal-<YYYYMMDD>.md     # report
```

## Reference run

The swanbase example (`examples/swanbase-preseed-fundraising-20261012/`, a fictional corpus: posts, authors, ids and URLs are invented), offline, from the agent folder:

```bash
E=examples/swanbase-preseed-fundraising-20261012
# Collection replayed from the recorded responses (live: drop --fixtures, add --record to refresh them)
python3 scripts/collect.py --plan $E/runs/20261012/plan.json --out /tmp/ms-run --fixtures $E/runs/20261012/fixtures
# What changed since the previous run, then the sidecar and the report
python3 scripts/diff_runs.py --previous $E/runs/20260713 --current $E/runs/20261012
python3 scripts/build_handoff.py --run $E/runs/20261012
python3 scripts/validate_sidecar.py $E/market-signal-20261012.json --stats $E/runs/20261012/stats.json
# The regression citations against their records: exit 1, every defective quote blocks, the one cited by record id and passage passes
python3 scripts/verify_quotes.py --corpus scripts/fixtures/april-2026/corpus.jsonl --quotes scripts/fixtures/april-2026/citations.json
```

## Tests

```bash
# From agents/market-signal/, offline, about 10 seconds: 53 checks
python3 scripts/selftest.py
# One group only
python3 scripts/selftest.py --only april,sidecar
```

Groups: `help`, `collectors` (ok, error, quota and import cases on recorded responses), `collect` (parallel and sequential replay byte-identical to the committed corpus, watch mode, re-run in the same run folder), `april` (quotes cited the way an unchecked run prints them, on fictional articles: each defect blocks with its code, the citation by record id and passage passes), `verify`, `signals` (equal to the committed `stats.json`, one author counted once, capped jobs, HN job-seeker threads never collected), `diff`, `handoff` (byte-identical rebuild, refusal, `--speakers` respected or rejected), `sidecar` (six mutations that must fail), `privacy` (no email, profile link or raw handle in the example fixtures and corpora; `scrub` on a synthetic answer). Fixtures: [`fixtures/README.md`](fixtures/README.md).

## Exit codes

Collectors: 0 the job ran (health `ok` or `empty`), 1 `error` or `quota` (partial records kept), 2 usage. `import_records.py`: 0 the import ran (health `ok` or `empty`), 1 unreadable file, 2 usage. `collect.py`: 0 corpus not empty, 1 empty corpus (see `health.json`), 2 usage error or invalid plan (also `--since-last-run` without a `--seen` file from a previous run). `verify_quotes.py`: 0 no BLOCK, 1 at least one BLOCK, 2 unreadable input. `compute_signals.py`: 0 written, 1 labels name an unknown record or pain, 2 unreadable input or unknown `--speakers` value. `build_handoff.py`: 0 delivered, 1 refused (reasons printed), 2 unreadable input or unknown `--speakers` value. `validate_sidecar.py`: 0 valid, 1 invalid, 2 unreadable. `diff_runs.py`: 0 written, 2 unreadable. `selftest.py`: 0 all pass, 1 otherwise.
