---
name: learning-from-rejections
description: Keeps what this agent learns in the founder's project memory, following the shared keeping-project-memory skill. Records each batch's posts in memory/posts.jsonl (openings, hook types, angles) so later batches never repeat them, turns a post the founder rejected into a decision of memory/decisions.md with the founder's words, enforces what can be enforced once the founder confirms (banned word in voice/rules.json, refused hook type, refused angle), and appends the run line. Use at the last step of founder-content-writer and whenever the founder rejects a post. Triggers on "I don't like this post", "never write that", "too salesy", "remember this", "don't do that again".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# learning-from-rejections

A post the founder refuses once should never come back in another shape. The shared rules live in [`../../../../shared/skills/keeping-project-memory/SKILL.md`](../../../../shared/skills/keeping-project-memory/SKILL.md); this skill adds one file and one command.

## Record the batch

```bash
python3 scripts/project_memory.py record <run>/posts-spec.json --project <project>
```

Appends one line per post and network to `<project>/project-context/memory/posts.jsonl`, contract [`../../assets/past-post.schema.json`](../../assets/past-post.schema.json). `check_spec.py` compares each opening with this file, with the texts of `content-publisher/queue.json` and with the founder's past posts of the voice pack. A batch's own earlier pass does not count against it. Record once the batch is delivered.

## A rejection becomes a rule

When the founder refuses a post, or rewrites it, ask nothing more than you need and run:

```bash
python3 scripts/project_memory.py reject <ref> --project <project> \
  --reason "the founder's own words, verbatim" \
  --rule "what to do next time, written so another agent can follow it without this conversation" \
  [--ban WORD] [--avoid-hook TYPE] [--avoid-angle-type TYPE] [--keep-angle] [--network x]
```

- `--reason` holds their words, never your summary. `--rule` is facts: "No post built on a feature the founder removed" is a rule, "more engaging" is not.
- The post goes to `rejected` in `posts.jsonl`, with its angle: the checker then refuses the same opening and the same angle (`rejected-opening`, `rejected-angle`). `--keep-angle` when the founder refused the wording and not the idea.
- The decision is written `Status: proposed`, because the rule is your reading of what they said. It shows at the next Step 0 and enforces nothing yet.
- When the founder confirms, `project_memory.py confirm <D-id>` makes it active, and `--confirmed` does both at once when they already stated the rule themselves. Then a banned word lands in `voice/rules.json`, where the writing gate of every agent enforces it, and a refused hook type or angle type is refused by `check_spec.py`.
- Never record as a decision something the founder did not say or confirm. A reviewer's opinion is not a founder decision until the founder agrees.
- A decision that changes follows the shared rule: a new entry with `Replaces: <old id>`, the old one moved under `## Superseded`. Edit those two entries by hand, in the shared format.

A rejection that names a fact ("we never said that", "that number is wrong") is a problem with the source: tell the founder which passage carried it, and let them correct the note or the proof list.

## Close the run

```bash
python3 scripts/project_memory.py log-run --run <run> --project <project> --status ok --critic PASS \
  --provider copy_lint=local --provider critic=subagent --decision D-<YYYYMMDD>-01
python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl
```

`--status`: `ok`, `partial` (no fresh-eyes review, a post left out, the writing gate by hand), `failed` (write the line anyway, with `--notes`), `skipped` (`project_memory.py seen` found the same inputs already done). At the end, show the proposed decisions in one block so the founder can answer "ok", edit or drop.

## Failure modes

- **`decisions.md` or `posts.jsonl` has a broken line** → read what parses, warn once, keep appending.
- **No write access to the project** → print the lines and the entries in the report so the founder can paste them.
