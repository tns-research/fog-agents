---
name: scanning-market-signals
description: Plans and runs the collection of market-signal. Writes plan.json (window, caps, hypotheses from project-context used as queries only, one job per source, query and language, with a reason), runs the free collectors in parallel through scripts/collect.py (Hacker News Algolia, Reddit through Arctic Shift, Stack Exchange, Discourse, App Store reviews, plus exports and optional paid search through import_records.py), reads the health of every job (ok, empty, error, quota), runs a second wave on the gaps, and keeps sources-rejected.md. Everything ends in one stored corpus.jsonl; nothing outside it can be quoted. Use at Steps 1 and 2. Triggers on "scan", "collect", "find what users say", "mine Reddit", "review mining".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# scanning-market-signals

Turns a market into a stored corpus of public records, each with its id, source, url, `author_hash`, date and public text. The model chooses where to look; the collectors fetch, page, cap, date-filter and report their health. Sources, limits and aiming: [`../../assets/sources.md`](../../assets/sources.md).

## Inputs

- `market`, `language`, `geography`, `recency_days`, `depth` (Step 0 of the agent).
- From project-context, as query material only: `icp.pains[]`, `icp.who`, `positioning.against` (alternatives to mine reviews of).
- `<project>/market-signal/sources-rejected.md` and, in watch mode, the previous run's `plan.json`.

## Step A. Write plan.json

Write `<project>/market-signal/runs/<YYYYMMDD>/plan.json` against [`../../assets/plan.schema.json`](../../assets/plan.schema.json). Example: [`../../examples/swanbase-preseed-fundraising-20261012/runs/20261012/plan.json`](../../examples/swanbase-preseed-fundraising-20261012/runs/20261012/plan.json).

- `window`: `since` = `until` minus `recency_days`. Every quote must be dated inside it.
- `caps`: from `depth` (`quick` 10 records per job and 2 pages, `standard` 25 and 3, `deep` 50 and 5). A capped job keeps the newest records: volumes become lower bounds and trends unknown. Raise the cap of the jobs whose volume matters.
- `hypotheses`: the founder's beliefs about the pain, from `icp.pains[]`. They decide what to search, and the report never presents them as results.
- `jobs`: one per source and query, with `why`. Cover the families below; skip a family only with a reason in `why` of a neighbouring job or in Limitations.

| Family | Typical jobs |
|--------|--------------|
| Pain language | Reddit comments with the problem's words in two or three subreddits where the persona asks for help; Hacker News exact phrases |
| Switching and comparison | the names of the alternatives (`positioning.against`, tools the persona uses) with "switched", "alternative", "instead of" |
| Wish and hesitation | "I wish", "is there a tool", "I tried but", "what stopped me" (the Anxiety and Habit forces) |
| Review mining | App Store reviews of the alternatives; G2 or Capterra exports from the founder; low ratings are where competitors fail |
| Niche communities | Discourse forums and Stack Exchange sites of the persona's trade |
| Each language | the same families with native wording, in the communities of that language |

Query words are artefacts: a phrase the collection searched for never counts as language from the market (`compute_signals.py` drops it from the language bank).

## Step B. Collect

```bash
python3 scripts/collect.py --plan <run>/plan.json --out <run>
```

Run from `agents/market-signal/`. Each job runs as its own process; sources run in parallel lanes, the jobs of one source in turn so no provider gets concurrent requests. `--sequential` runs everything one after the other with the same result; `--only <ids>` re-runs some jobs and merges with the rest of the run. Optional providers (`exa search ... --json --text`) and founder exports: save the file in the run folder and add an `import` job (`{"source": "import", "args": {"input": "g2-export.csv", "format": "csv", "source": "g2"}}`). Watch mode adds `--seen <project>/market-signal/state/seen.json --since-last-run` (the first watch run, with no state file yet, uses `--seen` alone).

Outputs: `corpus.jsonl` (records, schema [`../../assets/record.schema.json`](../../assets/record.schema.json)), `health.json`, `manifest.json`, and one file per job under `corpus/` and `health/`.

## Step C. Read the health, second wave

Open `health.json` before reading any record.

- `empty`: change the words or the community once. Still empty: write the source in `sources-rejected.md` (date, job, reason) so the next run does not try it again.
- `error`: read `errors[0]`. A closed site, a wrong host or a private forum goes to `sources-rejected.md`. A 5xx is retried once later.
- `quota`: retry later with a smaller cap; never loop on it.
- `capped: true`: fine for language; note it when the founder needs volumes.

When a family returned nothing usable (no review, no switching story, no community outside one subreddit), run a second wave on that gap with new jobs in the same run folder (`--only`). In watch mode the second wave keeps the same `--seen` flags: the records already in the run's `corpus.jsonl` stay, and `--since-last-run` keeps the run's window. Stop after two waves; what is still missing goes to Limitations.

## Rules

- Nothing is quoted from outside `corpus.jsonl`: not a search snippet, not a page read in the browser, not memory. Text read elsewhere goes in through `import_records.py` with its url and date first.
- Never edit `corpus.jsonl` by hand. A wrong record is excluded by labelling it `relevant: false`.
- No handle is stored: the collectors pseudonymise every handle (`user-<6 hex>`, also where a text of the same answer names it) and replace emails, phone numbers, profile links and @mentions with placeholders before a record or a recorded fixture is written (`mslib.scrub`). Records carry `author_hash` only.
- No paid call without the founder's go (`shared/tools.md` tiers); the free collectors are enough for a full run.

## Output

`runs/<YYYYMMDD>/corpus.jsonl`, `health.json`, `manifest.json`, an updated `sources-rejected.md`. Next: [`../coding-the-corpus/SKILL.md`](../coding-the-corpus/SKILL.md).
