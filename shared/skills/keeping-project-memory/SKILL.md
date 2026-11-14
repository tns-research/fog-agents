---
name: keeping-project-memory
description: Gives every agent a memory of the project that survives the session. Reads <project>/project-context/memory/decisions.md at Step 0 (each correction the founder made, as a rule with its reason and how to apply it) and appends one line per run to memory/runs.jsonl (agent, inputs hash, outputs, providers, checks, verdicts, status), failures included. At the last step, proposes the new decisions the founder's corrections imply. Use at Step 0 and at the final step of every agent. Triggers on "remember this", "don't do that again", "we already decided", "last run".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
---

# keeping-project-memory

A correction the founder makes once should never have to be made twice, by any agent. This skill keeps two plain files in the founder's project: the decisions (what was corrected and why) and the run log (what ran, with what, and how it went).

```
<your-projects-root>/<project>/project-context/memory/
├── decisions.md   # one entry per founder correction, read at every Step 0
└── runs.jsonl     # one JSON line per run, appended at every final step
```

Both are optional for readers: a missing folder means no memory yet, never an error. Agents create the folder the first time they have something to write.

---

## Step 0: read

Right after loading the project context ([`../loading-project-context/SKILL.md`](../loading-project-context/SKILL.md)):

1. Read `memory/decisions.md` if it exists. Keep every **active** entry whose scope covers this agent or this channel. Entries with `Status: proposed` are advisory: follow them, and mention them in the Step 0 block so the founder can confirm or drop them.
2. Apply them as hard rules for the run. A decision outranks the agent's defaults and the voice description; a value the founder gives in this conversation outranks a decision (then propose updating it at the last step).
3. When two active decisions conflict, or a decision conflicts with the brief, say so in the Step 0 block and follow the newer one. Do not pick silently.
4. Read the last lines of `memory/runs.jsonl` for this agent when the run depends on a previous one (a delta run, a scheduled re-run). When `inputs_hash` equals the hash of today's resolved inputs and the outputs exist, the work is already done: report it and stop, with a `skipped` line.
5. Print one line: `Memory: 6 decisions apply (2 proposed), last run 2026-09-28 ok.`

## Decision entry format

`decisions.md` starts with a one-line-per-entry index, then the entries:

```markdown
# Decisions

- D-20261010-01: Address the audience formally in French copy (all copy agents)
- D-20261002-01: Never present a market-signal quote as a customer quote (all)

## Active

### D-20261010-01: Address the audience formally in French copy
- Rule: French copy for an audience (posts, pages, newsletters) uses "vous"; "tu" only in one-to-one messages.
- Why: the founder rejected a LinkedIn draft on 2026-10-10: "our readers are investors and founders, not friends".
- How to apply: before the writing gate, check the address form of every French deliverable against its channel.
- Scope: all copy agents, French
- Date: 2026-10-10
- Source: carousel-builder, run "pricing-explainer"
- Status: active
- Enforced by: none
- Replaces: none

## Superseded

### D-20260914-02: Use "tu" on LinkedIn
- (same fields)
- Status: superseded by D-20261010-01 on 2026-10-10
```

Rules for writing entries:

- **One entry per correction**, written as a rule a different agent can follow without the conversation: what to do, why (with the founder's own words and the date), how to apply it, where it applies.
- **Replace, never erase.** When a decision changes, write the new entry with `Replaces: <old id>`, move the old entry under `## Superseded` with `Status: superseded by <new id> on <date>`, and update the index. The history of why a rule changed is part of the memory.
- **Facts, not adjectives.** "Sentences under 20 words in posts" is a rule; "punchy tone" is not.
- **Mechanizable decisions get enforced.** A banned word or pattern also goes into `voice/rules.json` (see [`../writing-gate/SKILL.md`](../writing-gate/SKILL.md)); the entry says `Enforced by: writing-gate <code>`.
- **No secrets, no personal data** beyond what the founder already put in `project-context`.
- Ids: `D-<YYYYMMDD>-<NN>`, numbered per day.

## Last step: log the run and propose decisions

### 1. Append the run line (always, failures included)

`founder-content-writer` also keeps `memory/posts.jsonl`, the openings it already used, so a new batch does not repeat them.

One JSON object per line, UTF-8, appended to `memory/runs.jsonl`. Contract: [`../../schemas/run-record.schema.json`](../../schemas/run-record.schema.json).

```json
{"ts": "2026-10-10T16:42:00+02:00", "agent": "carousel-builder", "label": "pricing-explainer", "status": "ok", "inputs_hash": "3f9a1c0b7d2e", "outputs": ["carousel-builder/pricing-explainer-20261010/carousel.pdf"], "providers": {"web_search": "builtin", "vision": "builtin"}, "checks": {"copy_lint": "pass", "brand_schema": "pass"}, "critic_verdict": "PASS", "render_review_rounds": 2, "human_verdict": "none", "decisions_added": ["D-20261010-01"]}
```

- `inputs_hash`: sha256 of the resolved inputs (brief, config, the handoff files read), hex, 12 characters are enough.
- `status`: `ok`, `partial` (delivered with skipped capabilities or open issues listed in the report), `failed`, or `skipped` (idempotence guard).
- A run that fails still writes its line, with `status: failed` and a `notes` field. A run that writes nothing is indistinguishable from a run that never happened.
- Check the file after writing: `python3 shared/scripts/validate_json.py --jsonl shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl`.

Writing the line takes no tool beyond appending text. Where the shell is available:

```bash
printf '%s\n' '<the JSON object on one line>' >> <project>/project-context/memory/runs.jsonl
```

### 2. Propose decisions

Scan the run for corrections: a draft the founder rejected or rewrote, an angle refused, a word struck, a fact corrected, a reviewer FAIL that traces to a missing rule. For each, draft an entry in the format above and show the drafts in one block at the end of the run:

```
Proposed decisions (reply "ok", edit, or drop):
- D-20261010-02: Never mention a competitor by name in ads (static-ads-builder, all channels)
  Why: "we don't name them, ever" (2026-10-10)
```

- On "ok" (or an edit), write them with `Status: active` and record their ids in the run line's `decisions_added`.
- With no answer (unattended run), write them with `Status: proposed`. The next Step 0 shows them for confirmation.
- Never record as a decision something the founder did not say or confirm. A reviewer's opinion is not a founder decision until the founder agrees.

---

## Failure modes

- **`decisions.md` unreadable or malformed** → read what parses, warn once, never stop the run.
- **`runs.jsonl` has a broken line** → skip that line when reading, keep appending; report the line number once.
- **No write access to the project** → print the run line and the proposed entries in the report so the founder can paste them.
