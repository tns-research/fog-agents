---
name: coding-the-corpus
description: Reads every record of the market-signal corpus and labels it, so scripts can count. Writes the pain codebook (pains in analysis.json, each with a force and an awareness stage), then one line of labels.jsonl per record (relevant, speaker, pains, sentiment, JTBD forces, awareness stage, alternatives named), then runs scripts/compute_signals.py, which computes mentions, distinct authors, communities, shares by source, trend and escalation. The model never writes a count. Use at Step 3. Triggers on "label the corpus", "cluster the pains", "code the threads", "count mentions".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash
---

# coding-the-corpus

Open coding over the whole corpus, not seven fixed patterns. The corpus of a standard run (a few hundred records) fits in context: read all of it before naming pains, then label every record. Scripts turn the labels into numbers.

## Step A. Read, then write the codebook

Read every record of `<run>/corpus.jsonl` (text, context, community, date). Then write the `pains` list of `<run>/analysis.json` (schema [`../../assets/analysis.schema.json`](../../assets/analysis.schema.json)):

- `pain_id`: `pain_<snake_case>`, stable across runs (watch mode reuses the previous codebook; a renamed pain lists its old id in `aliases`).
- `summary`: the pain in plain words, no number.
- `kind`: `pain`, `desire`, or `meta_problem` (a problem created by the solution people use now; name it in `existing_solution`). See [`../../references/competitive-analysis.md`](../../references/competitive-analysis.md).
- `force` (Push, Pull, Anxiety, Habit, see [`../../assets/jtbd-forces-of-progress.md`](../../assets/jtbd-forces-of-progress.md)) and `awareness_stage` (`unaware`, `problem_aware`, `solution_aware`, `product_aware`, `most_aware`).

Split two pains when people would act differently on them; merge two when the same people say both in the same breath. A pain the founder believed in (`hypotheses`) and the corpus does not show is not written; it goes to `rejected_pains` with the reason if it was in the plan. Same words in another market (warm intros for hiring in a fundraising scan) go to `rejected_pains` too.

## Step B. One label per record

`<run>/labels.jsonl`, one line per record read, relevant or not, against [`../../assets/labels.schema.json`](../../assets/labels.schema.json):

| Field | Rule |
|-------|------|
| `relevant` | `true` only when the record speaks to the market scanned. Off-topic, hiring threads, other markets: `false` with a short `note`. |
| `speaker` | `user`: first person about their own situation. `practitioner`: first-hand advice from someone who did it (founder, investor, operator). `vendor`: promotes their own product or service. `press`: reports someone else's words. `other`. Only `user` and `practitioner` count as voices. |
| `pains` | pain ids the record expresses, not merely mentions. |
| `sentiment` | of the record towards the situation: `negative`, `neutral`, `positive`, `mixed`. |
| `forces` | JTBD forces the record shows. |
| `awareness` | where the speaker stands. |
| `competitors` | alternatives named, including the status quo ("cold email", "spreadsheet", "friends and family round"), spelled the same way every time. |

The same author posting twice, a crosspost, an aggregator quoting someone: label each record; `compute_signals.py` counts distinct authors, so repetition does not inflate a pain. Labelling may be split in batches across sub-agents with this codebook; the orchestrator reads the disagreements before counting. Without sub-agents, one pass.

## Step C. Count

```bash
python3 scripts/compute_signals.py --corpus <run>/corpus.jsonl --labels <run>/labels.jsonl \
    --analysis <run>/analysis.json --out <run>/stats.json
```

Per pain: voices, distinct authors, distinct communities, voices by source and their share, first and last seen, months, trend between the two halves of the window, resonance against the median score of the same community, escalation (5 distinct authors across 2 communities by default, `--min-authors`, `--min-communities`, from `config.json` `escalation`). A pain fed by a capped collector reads trend `unknown` and volume `lower_bound`. Corpus: records and shares by source and community, speakers, sentiment counts and shares, forces, alternatives named, language bank (2 to 6 word phrases in 3 records by 3 authors at least, `--phrase-records`, `--phrase-authors`, query words excluded). `build_handoff.py` recomputes `stats.json` at Step 6 with its own threshold flags, `--speakers` included (default `user,practitioner`); an unknown speaker is an error, never replaced.

## Step D. Saturation

Look at `stats.json`:

- an escalated pain carried by one source family or one community type: a second wave elsewhere (Step 2 of the agent) before trusting it;
- a force with no voice, often Anxiety: hesitation and switching queries;
- a pain just under the threshold: more records from the communities that hold it.

Label the new records with the same codebook and count again. Stop when a wave opens no new pain and moves no pain across the threshold. Two waves at most.

## Rules

- The model never writes a count, a share, a trend or "most people": the report prints `stats.json`.
- Sentiment is the model's reading of each record; the report says so and prints counts, never an estimate.
- A record can be relevant with no pain (it names an alternative, or asks a novice question).

## Output

`analysis.json` with its `pains` (the rest comes at Step 4), `labels.jsonl`, `stats.json`. Next: [`../extracting-psychographic-profile/SKILL.md`](../extracting-psychographic-profile/SKILL.md).
