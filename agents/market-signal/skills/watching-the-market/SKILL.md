---
name: watching-the-market
description: Runs market-signal as a recurring watch. Collects only what is new since the last run (state/seen.json, --since-last-run), labels it with the previous codebook (aliases for renamed pains), builds the sidecar of the new window, and compares it with the previous run through scripts/diff_runs.py, which writes changes.json and changes.md (pains new, rising, falling, disappeared, newly escalated, in distinct authors per 30 days; collectors whose health changed; alternatives named for the first time). Started by any scheduler. Use at Step 5 or when the founder asks what changed. Triggers on "watch", "monitor", "what changed", "weekly signal", "since last time".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# watching-the-market

A watch run is a normal run on a new window, plus a comparison. The founder reads `changes.md`; the full report stays one command away.

## Schedule

Nothing starts it by itself: a person or a schedule you set up ([`../../../../shared/scheduling.md`](../../../../shared/scheduling.md)) starts the agent with `watch: true` in `config.json`. The cadence follows the market's volume: weekly for a busy category, monthly for a niche. A run that finds `runs.jsonl` with the same inputs and outputs present stops with a `skipped` line (keeping-project-memory).

## Step A. Collect what is new

Copy the previous `plan.json` into the new run folder (change jobs only on purpose, and say why in `why`), then:

```bash
python3 scripts/collect.py --plan <run>/plan.json --out <run> \
    --seen <project>/market-signal/state/seen.json --since-last-run
```

`--since-last-run` starts the window where the last run ended; `--seen` drops records already collected (`already_seen` in `health.json`) and adds the new ids. The first watch run has no state file yet: `--since-last-run` refuses to start without one (exit 2), so that run uses `--seen` alone, collects the configured window and creates the file.

A second wave in the same run folder (`--only <ids>`) runs without `--seen`: the first pass already wrote its ids to `seen.json`, so with `--seen` every record would count as seen and the merged corpus would come out empty.

## Step B. Label with the same codebook

Reuse the previous `pains` ids. A pain that changed name lists its old id in `aliases`, so its history follows. A new pain gets a new id. Then `compute_signals.py` as usual ([`../coding-the-corpus/SKILL.md`](../coding-the-corpus/SKILL.md)).

## Step C. Compare

```bash
python3 scripts/diff_runs.py --previous <project>/market-signal/runs/<previous> --current <run>
```

| Status | Rule (distinct authors scaled to 30 days) |
|--------|-------------------------------------------|
| `new` | absent before, present now |
| `disappeared` | present before, no voice now |
| `rising` | at least 1.5 times the previous rate and 2 more per 30 days (`--rise-ratio`, `--min-delta`, from `config.json` `watch`) |
| `falling` | the other way round |
| `stable` | anything else |

Plus `newly_escalated` and `no_longer_escalated`, collectors whose health changed, alternatives named for the first time or no longer named, new phrases of the language bank.

Read it with two cautions, both printed in `changes.md`:

- a pain marked `lower bound` came partly from a collector that hit its cap: its direction is a hint, not a measure (raise the caps when the founder needs the trend);
- a collector that failed or came back empty in one run lowers that run's counts: a "rise" next to a source back from `quota` may be the source, not the market.

## Step D. Deliver

`build_handoff.py` picks up `changes.json` and adds a "Changes since the last run" section to the report and a `changes` block to the sidecar. Send the founder `changes.md` first, then the report link. A newly escalated pain, a disappeared escalated pain, or a new direct alternative is worth a proposed decision (keeping-project-memory).

## Output

`runs/<YYYYMMDD>/changes.json`, `changes.md`, the updated `state/seen.json`, and the usual sidecar and report of the window.
