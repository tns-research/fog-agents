# scripts/

The checks of founder-content-writer. The model writes `posts-spec.json`; these scripts check it against the raw material and build what content-publisher takes. Standard library only (Python 3.9+), no network, no key, every script answers `--help`.

| Script | Does | Writes |
|--------|------|--------|
| `ingest.py` | Copies raw material into the batch, verbatim, with its sha256. Refuses audio, a third-party page without URL, and a market-signal file its own validator rejects. Flags text addressed to an AI and personal data. | `<run>/sources/`, `sources/manifest.json` |
| `check_spec.py` | Every mechanical check: passages word for word, claims and numbers against `positioning.proof`, names, quotes, time markers, content-publisher's limits and link rules, the writing gate, duplicate openings (batch, memory, queue, past posts), hook and angle variety, the voice pack, the address form, active decisions. | stdout, `--out check.json` |
| `build_batch.py` | Runs the check, compiles `posts.json`, runs content-publisher's own `variants.py lint` on it, writes the founder's report and the critique packet. A failing spec leaves no `posts.json`. | `posts.json`, `lint.json`, `check.json`, `founder-content-<YYYYMMDD>.md`, `review/critique-prompt.md`, `review/critique-packet.md` |
| `project_memory.py` | `record` past posts, `reject` a post into a decision, `confirm` a decision, `log-run`, `seen`. | `memory/posts.jsonl`, `memory/decisions.md`, `memory/runs.jsonl`, `voice/rules.json` on a confirmed ban |
| `fcw_lib.py` | Word-for-word matching, number comparison, project file readers, the compile step. | n/a |
| `selftest.py` | Offline regression test (below). | temporary folder |

## Dependencies on the rest of the stack

Read at run time, never copied:

- `agents/content-publisher/scripts/variants.py` and `common.py`: limits, X count, link rules, the post spec. Without them `check_spec.py` exits 2: a limit is never guessed.
- `shared/skills/writing-gate/scripts/lint_copy.py`, through content-publisher. Without it the report says "Writing gate: manual" and the batch ends `partial`.
- `shared/scripts/validate_json.py`: schemas.
- `shared/scripts/proof.py`: reads `positioning.proof` and says which items are usable for posts. `check_spec.py` imports it.
- `agents/market-signal/scripts/validate_sidecar.py`, when a sidecar is ingested. `agents/project-context/assets/voice-schema.json`, when a voice pack exists.

If you copy this agent alone, copy `shared/` and `agents/content-publisher/` next to it.

## Quick run on the example

From the repo root:

```bash
E=agents/founder-content-writer/examples/brindlefen-workshop-notes-20261026
S=agents/founder-content-writer/scripts
P=/tmp/fcw-demo; R=$P/founder-content-writer/workshop-notes-20261026
rm -rf $P; mkdir -p $P/project-context $R
cp $E/context.json $P/project-context/; cp $E/posts-spec.json $E/brief.md $R/
python3 $S/ingest.py add --run $R --id voice-note --kind voice_note $E/raw/voice-note.md
python3 $S/ingest.py add --run $R --id call-notes --kind notes $E/raw/call-notes.md
python3 $S/ingest.py market-signal --run $R --id market-signal $E/raw/market-signal-20261020.json
python3 $S/check_spec.py $R/posts-spec.json --project $P
python3 $S/build_batch.py $R/posts-spec.json --project $P
python3 agents/content-publisher/scripts/variants.py lint $R/posts.json --project $P
```

## Tests

```bash
python3 agents/founder-content-writer/scripts/selftest.py
```

Offline, about 15 seconds, no key, no network, fictional founder and brand. It proves the reference batch goes from raw material to `posts.json` and that content-publisher takes it as is (its own `variants.py lint`, its own schema, its own `pubqueue.py add`, every item `to_review`); every failure of the stress spec with its code; the source refusals; the French address form and its overrides; the voice pack and the Limitations line without one; memory (past openings, the queue, rejection to proposed decision, confirmation, enforcement, run line, idempotence); the thread switch; growth-sprint's `check_step.py` on the batch; and the hard rules (no network import, nothing runs an approval or a publication, no em or en dash). `--keep DIR` keeps the work folder.

Not tested: a fresh reviewer's judgment, and any real founder's material. The rubric and the packet are checked for shape, not for what a model or a person answers.

## Exit codes

All CLIs: 0 ok, 1 a check failed or a command was refused on the content (`project_memory.py seen`: not done yet), 2 usage error, unreadable or invalid file.
