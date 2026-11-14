# examples/

Reproducible runs of `market-signal`. Commands run from `agents/market-signal/` and need no network and no key.

| Example | What it shows | Command |
|---------|---------------|---------|
| [`swanbase-preseed-fundraising-20261012/`](swanbase-preseed-fundraising-20261012/) | The reference run for the stack's example brand (swanbase): pains of first-time founders raising a pre-seed round, on a fictional corpus dated 2026-10-12 and shaped like the answers of Reddit (Arctic Shift), Hacker News, Stack Exchange, a Discourse forum and the App Store feed, in a 91-day window. Read the report first: [`market-signal-20261012.md`](swanbase-preseed-fundraising-20261012/market-signal-20261012.md). | `python3 scripts/build_handoff.py --run examples/swanbase-preseed-fundraising-20261012/runs/20261012` |
| [`swanbase-preseed-fundraising-20261012/runs/20260713/`](swanbase-preseed-fundraising-20261012/runs/20260713/) | The previous watch run (same plan, window 2026-04-15 to 2026-07-13), kept for `diff_runs.py` | `python3 scripts/diff_runs.py --previous examples/swanbase-preseed-fundraising-20261012/runs/20260713 --current examples/swanbase-preseed-fundraising-20261012/runs/20261012` |

What is in the reference run folder, and who wrote it:

| File | Written by |
|------|-----------|
| `runs/20261012/plan.json` | the model, Step 1 |
| `runs/20261012/fixtures/` | `collect.py --record` (the API answers, frozen; `collect.py --fixtures` replays them) |
| `runs/20261012/corpus.jsonl`, `health.json`, `manifest.json` | `collect.py` |
| `runs/20261012/labels.jsonl` | the model, one label per record after reading all of them |
| `runs/20261012/analysis.json` | the model: pains, quotes by record id and passage, hooks, objections, angles, persona, recommendations |
| `runs/20261012/stats.json`, `quotes-check.json` | `build_handoff.py` (through `compute_signals.py` and `verify_quotes.py`) |
| `runs/20261012/changes.json`, `changes.md` | `diff_runs.py` |
| `market-signal-20261012.json`, `market-signal-20261012.md` | `build_handoff.py` |

**Fictional data.** Every post, comment, review, article, author, id, permalink and URL in this example (the recorded API answers under `fixtures/`, both corpora, the labels and the analysis) is invented, written to show what the agent produces on a realistic market; any resemblance to real people, posts, products or companies is coincidental. Only the platforms and the shape of their API answers are real: the collectors build Reddit, Hacker News and App Store permalinks from ids, so those links keep the platform domain with ids that do not exist (`fictive..` Reddit ids, Hacker News ids above 90000000); every other link uses a reserved `.example` domain (the Discourse forum of a fictional no-code builder at `forum.example`, Stack Exchange links at `qa.example`). The fictional App Store app (Tablesplit) has a fake id.

The data follows the rules a real run applies: every handle is a pseudonym (`user-<6 hex>` in the fixtures; `author_hash` is computed on that pseudonym in both runs, so distinct-author counts and the diff hold), there is no email, phone number, profile link or @mention, and each text is a short excerpt (about 400 characters at most), `[...]` marking the cuts. Records carry only `author_hash`. Several collectors hit their cap on purpose to keep the example light, so most volumes read `lower_bound` and most trends `unknown`: that is the honest reading of a capped collection, not a bug. The recorded search answers of capped jobs keep only the items the collector reads before its cap. The App Store feed answered no review that day (health `empty`); the Arctic Shift query of r/ycombinator was throttled in the previous run (health `quota`).

## Adding an example

A folder `<brand>-<topic>-<YYYYMMDD>/` laid out like a project's `market-signal/` folder: `runs/<YYYYMMDD>/` with `plan.json`, the recorded `fixtures/`, `corpus.jsonl`, `health.json`, `labels.jsonl`, `analysis.json`, and the outputs `build_handoff.py` writes. Keep it light (caps of about ten records per job, no fixture file over 60 KB). Examples are in English, on the stack's example brand (swanbase), with fictional posts, authors, ids and URLs marked as such (never a real person's text), pseudonymised handles, short excerpts and no contact detail (`selftest.py` fails on an email, a profile link or a raw handle in a fixture or a corpus). Run `python3 scripts/selftest.py` after any change: it rebuilds the reference sidecar and report byte for byte.
