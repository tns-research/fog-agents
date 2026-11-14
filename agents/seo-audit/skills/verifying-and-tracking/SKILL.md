---
name: verifying-and-tracking
description: Closes the loop after a change goes live. scripts/verify_served.py fetches the published page and checks the served HTML against the brief's expect.json (status 200 at the same URL, indexable, allowed by robots.txt, title, canonical on itself, og:url, hreflang, listed in a sitemap of the same host, JSON-LD parsed with the expected types, no production jargon, merged URLs 301 to the page). scripts/seo_state.py records the shipping date, the verification, and the Search Console follow-up of every modified page at 14, 28 and 56 days, tagged by refresh action, and diffs each run with the previous one. Use after a publication (verify mode), on a schedule (track mode), and at the start of every audit. Triggers on "verify", "is it live", "did it work", "track", "follow-up", "since last audit".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# verifying-and-tracking

Code that is correct can still serve a wrong page: a canonical built from an environment variable that fell back to another domain, a JSON-LD block stripped by a Markdown sanitizer at build time, a sitemap still pointing at the old host. None of these raises an error; only the HTTP response shows them. And a refresh that is never measured teaches nothing. This skill checks the served page, then follows it in Search Console.

All state lives in `<project>/seo-audit/state.json` (`seo_state.py`). Thresholds and checkpoints: the `tracking` object of `assets/gsc-bands.json`.

## Step A: after publication (verify mode)

The founder or the writer publishes; the agent never does. Then:

```bash
python3 scripts/seo_state.py ship --state <project>/seo-audit/state.json --id <brief id> --date <publication date>
python3 scripts/verify_served.py --expect <project>/seo-audit/briefs/<id>/expect.json --out <project>/seo-audit/briefs/<id>/verify-<YYYYMMDD>.json
python3 scripts/seo_state.py verified --state <project>/seo-audit/state.json --id <brief id> --report <that verify json>
```

- A failing check names the tag and what was served. Fix the source (template, environment variable, build step), redeploy, verify again. A brief is `verified` only when every check passes; a failed verification stays in the state with the failing checks.
- Before deployment, the same check runs on a local build: `--fetch-base http://127.0.0.1:<port>` keeps the production URLs in every comparison.
- `--check-links` also fetches every internal link of the page.

Done when the brief is `verified` in the state, or the failing checks are in the report with the file to fix.

## Step B: since the last audit (every audit run)

```bash
python3 scripts/seo_state.py init --state <project>/seo-audit/state.json --project <slug> --domain <domain>   # first run only
python3 scripts/seo_state.py record-run --state <project>/seo-audit/state.json --run-dir <project>/seo-audit/runs/<YYYYMMDD>
```

`since-last-run.md` lists the pages added or gone, every title, description, canonical, og:url, status, indexability, H1 and JSON-LD change with its crawl line, issues new and resolved, pages entering or leaving a band, the E-E-A-T signals each page gained or lost and the site score before and after (when both runs hold an `eeat.json`: run `scripts/eeat.py` before `record-run`), and the briefs shipped since the previous run with their verification and checkpoints. The report's "Since the last audit" section is written from it. Done when the file exists.

## Step C: follow-up at 14, 28 and 56 days (track mode)

```bash
python3 scripts/seo_state.py due --state <project>/seo-audit/state.json --today <YYYY-MM-DD>
```

`due` lists briefs to write, shipped changes not verified, and checkpoints due (checkpoint N is due N + 3 days after shipping, Search Console data arriving late), each with its exact windows: the N days before the ship date and the N days after it.

Data, by `search_console` tier:

- API: one pull of daily rows covering every window `due` printed, then one command records all of them:

  ```bash
  gsc analytics query --site <domain> --start <earliest before date> --end <latest after date> --dimensions date,page --limit 25000 --json > <project>/seo-audit/data/gsc-date-page-<YYYYMMDD>.json
  python3 scripts/seo_state.py track --state <project>/seo-audit/state.json --gsc <project>/seo-audit/data/gsc-date-page-<YYYYMMDD>.json --today <YYYY-MM-DD>
  ```

- CSV: the founder exports the Pages table twice per checkpoint (the two date ranges `due` printed, filtered on the page), then:

  ```bash
  python3 scripts/seo_state.py track --state <state> --id <brief id> --checkpoint 28 --before <before.csv> --after <after.csv>
  ```

- none: checkpoints stay `scheduled`; the report says the follow-up is not measured.

Each checkpoint records clicks, impressions, CTR and position before and after, the outcome (`up`, `flat`, `down`, from the thresholds file) and the tag `refresh:<action>`. When the 56-day checkpoint is recorded the brief is `closed`.

```bash
python3 scripts/seo_state.py summary --state <project>/seo-audit/state.json
```

counts outcomes per action and checkpoint. Done when `due` lists no checkpoint the available data covers.

## Reading outcomes

- An outcome is a correlation on a small sample: a core update, a seasonal query or a competitor's move can explain it. Report it with the sample ("refine: 3 up, 1 flat at 28 days") and never name a winning action from fewer than a handful of pages.
- Position stable and impressions down on a deep position: check for a measurement change before calling it a decline (`artifact_suspect` in `bands.json`).
- A `down` at 14 days after an expand or a retarget is common while Google re-evaluates the page; read the 28 and 56-day checkpoints before reverting anything.

## Anti-patterns to refuse

- Calling a change done because the commit merged or the CMS says "published".
- Checking the source repository instead of the served response.
- Requesting re-indexing as the last step: it is a request, not a verification.
- Comparing a checkpoint with a different window length before and after.
