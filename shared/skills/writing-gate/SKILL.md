---
name: writing-gate
description: Mechanical gate for every piece of copy an agent writes (emails, posts, slide text, ad lines, page rewrites, report prose). Runs scripts/lint_copy.py with the shared English and French packs plus the project's own pack (founder's banned words, brand casing, calibrated exceptions) and blocks delivery while a BLOCK remains. Catches two-step corrections, hollow intensifiers, staged questions and fake suspense, length announcements, trailing participles, grandiosity, em dashes and objects that act like people. Use on every draft before the claims check and before any human checkpoint. Triggers on "lint the copy", "does this sound like AI", "check the writing", "slop".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
---

# writing-gate

A style rule in prose is followed most of the time; a script is followed every time. This gate turns the stack's writing rules into a command with an exit code, so a draft with a known machine-writing tic cannot reach a deliverable. It checks what the text must not contain. What the text claims stays the job of [`../enforcing-claims-policy/SKILL.md`](../enforcing-claims-policy/SKILL.md), run right after.

Capability: `copy_lint` (see [`../../tools.md`](../../tools.md#copy_lint-machine-writing-gate)). Script: [`scripts/lint_copy.py`](./scripts/lint_copy.py), Python 3.8+, standard library only.

---

## Command

From the repo root (from an agent folder the path is `../../shared/skills/writing-gate/scripts/lint_copy.py`):

```bash
python3 shared/skills/writing-gate/scripts/lint_copy.py \
  --project <your-projects-root>/<project> draft.md
```

- Language is detected per file; force it with `--lang en` or `--lang fr` on short or mixed texts.
- `--project` adds the project pack: `<project>/project-context/voice/rules.json` and `voice.banned_words` from `context.json`, when they exist.
- `--json` prints one object (`status`, and per file `counts` and `findings` with line, column, level, code, match, fix). Keep it next to the deliverable.
- `-` reads stdin, for copy that is not on disk yet.
- `--pack PATH` adds an agent pack in the same format; `--ignore CODE,CODE` skips codes for one run (say why in the report).
- `--with-slopcheck` also runs `slopcheck check` when that command is installed; its BLOCKs fail the gate too. Without it, the flag prints a note and changes nothing.
- `--list` prints the rules that would run.

Exit 0 means no BLOCK, exit 1 means at least one BLOCK, exit 2 means a usage error or a broken pack.

The script skips YAML frontmatter, fenced code, inline code, HTML comments, URLs, markdown blockquotes (verbatim quotes from `market-signal` are never rewritten; `--include-quotes` lints them anyway) and anything between `<!-- writing-gate: off -->` and `<!-- writing-gate: on -->` (use it only for text that quotes bad examples on purpose, like this file).

## Loop

1. Write the draft.
2. Run the gate.
3. Fix every BLOCK **in the copy**: rewrite the sentence with the fact the tic was standing in for. Never edit a pack, a threshold or an ignore list to make a draft pass.
4. Read every WARN: fix it, or keep it when the sentence carries a fact (a short answer that is a number, a passive whose agent is unknown).
5. Re-run until 0 BLOCK. Three passes at most; a BLOCK left after the third pass is listed in the report with the reason and goes to the founder.
6. Run the claims check on the passing draft.

Report one line in Methodology: `Writing gate: 0 BLOCK, 3 WARN kept (packs: en, project)`.

## What the shared packs catch

Packs: [`packs/en.json`](./packs/en.json) and [`packs/fr.json`](./packs/fr.json), format in [`../../schemas/copy-rules.schema.json`](../../schemas/copy-rules.schema.json). Every rule carries `bad` and `good` examples that the tests run.

<!-- writing-gate: off -->
| Family | English codes | French codes | Example caught |
|--------|---------------|--------------|----------------|
| Two-step correction | `not-x-its-y`, `not-just-but`, `no-x-no-y-just-z` | `correction-deux-temps`, `pas-mais`, `pas-seulement-mais`, `ni-ni-juste`, `apposition-pas` | "It's not a tool, it's a habit." |
| Hollow intensifier | `buzzword`, `soft-buzzword`, `hollow-adverb` | `vrai-x`, `intensificateur-creux`, `adverbe-creux` | "a game-changer", "un vrai levier" |
| Staging | `staged-question`, `question-then-answer`, `fake-suspense`, `length-announcement`, `imagine-scene`, `chatbot-ritual`, `staccato` | `question-mise-en-scene`, `question-reponse`, `faux-suspense`, `annonce-longueur`, `imaginez`, `rituel`, `staccato` | "The result? A 3x lift.", "Our method fits in one sentence." |
| Trailing participle | `trailing-participle` | `participe-final` | "..., highlighting the strength of the model." |
| Grandiosity | `grandiosity`, `at-the-heart` | `grandiloquence` | "a new era", "qui change tout" |
| Dash | `em-dash`, `spaced-en-dash`, `spaced-hyphen` | `em-dash`, `spaced-en-dash`, `tiret-espace` | an em dash anywhere |
| Object as agent | `object-as-agent` | `objet-agent` | "The data decides.", "Le chapeau décide du reste." |
| Vague authority | `vague-authority`, `crowd-claim` | `autorite-vague`, `foule-vague` | "Studies show...", "Most founders..." |
<!-- writing-gate: on -->

Levels: BLOCK fails the gate. WARN does not, except when a rule has `escalate_at` and the text repeats it that many times: then every hit of that rule becomes BLOCK, because the repetition is the tic.

## Project pack: `project-context/voice/rules.json`

Optional, written by `project-context` or by the founder, same format as the shared packs:

```json
{
  "language": "any",
  "banned_words": ["synergy", "disrupt"],
  "disable": ["hollow-adverb"],
  "levels": { "crowd-claim": "BLOCK" },
  "rules": [
    {
      "code": "brand-casing",
      "level": "BLOCK",
      "pattern": "\\bAcmeApp\\b",
      "message": "Write the brand as acmeapp, lowercase.",
      "bad": ["Try AcmeApp today."],
      "good": ["Try acmeapp today."]
    }
  ]
}
```

- `banned_words` adds to `voice.banned_words` from `context.json`; both are BLOCK (code `banned-word`), case-insensitive, whole words.
- `disable` and `levels` adjust shared rules for this voice. **Calibration rule:** the founder's own texts (`voice/exemplars/` when present) must pass at 0 BLOCK. When a shared rule blocks a sentence the founder wrote and stands by, disable it or lower it in the project pack, and record why in `memory/decisions.md` (see [`../keeping-project-memory/SKILL.md`](../keeping-project-memory/SKILL.md)).
- A decision from the founder that is a pattern ("never write X", "always lowercase the brand") becomes a rule here, and its decision entry says `Enforced by: writing-gate <code>`.
- Validate the file: `python3 shared/scripts/validate_json.py shared/schemas/copy-rules.schema.json <project>/project-context/voice/rules.json`.

## Changing the shared packs

Add a rule only with at least one `bad` and one `good` example, then run:

```bash
python3 shared/skills/writing-gate/tests/run_tests.py
```

The tests check the packs against the schema, every rule against its examples, the fixtures in `tests/` (`bad_*.md` must fail with the expected families, `good_*.md` must pass at 0 BLOCK), the skipped regions and the project pack. A rule that fires on a `good_*.md` fixture is too broad: narrow the pattern, do not edit the fixture. The shared packs and the repo forbid literal em and en dashes, so rules write them as `\u2014` and `\u2013` and tests generate them.

## Failure modes

- **Python missing** → the gate cannot run: apply the family table above as a manual checklist, and write "Writing gate: manual" in Methodology.
- **A pack fails to load** (exit 2) → fix the JSON (validate it with the schema), never deliver with the gate skipped silently.
- **A legitimate sentence keeps failing** → rewrite it once more; if it is the founder's own wording, apply the calibration rule above.
