---
name: example-checklist-audit
description: Applies a structured checklist of heuristics to a target artifact and produces pass/issue/critical findings with severity scores. Use when a workflow step needs to systematically evaluate something (a landing page, a sequence, a SERP, a market) against a known rubric. Triggers on words like "audit", "score", "evaluate", "review against checklist".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write
---

# example-checklist-audit

Reference example for the skills + assets pattern. **This is a stub showing the shape**, not a runnable skill. Replace with real methodology when you fork this template.

A skill is the methodology layer between the agent's workflow and the data it operates on. The skill explains HOW to apply a rubric. The asset is the actual rubric data.

---

## When to invoke

The agent's `AGENT_<NAME>.md` workflow points to this skill at the relevant step. Example wording:

> "Step 4: apply the heuristic audit. Read `skills/example-checklist-audit/SKILL.md`, load `assets/example-checklist.md`, score each heuristic, write findings."

---

## Inputs

- `artifact` (string or URL): what is being audited (page URL, file path, structured data block).
- `context` (object, optional): additional metadata the rubric needs (target user, conversion goal, channel, locale).

---

## Procedure

1. Load the rubric data from `assets/example-checklist.md`. Each row is one heuristic with: id, dimension, criterion, weight, mobile-applicable flag.
2. For each heuristic, evaluate the artifact against the criterion.
3. Score each heuristic: ✅ pass (no issue), ⚠️ issue (problem present, fixable), ❌ critical (blocking issue).
4. Assign severity 1-5 to ⚠️ and ❌ findings (1 = cosmetic, 5 = conversion-blocker).
5. For each non-pass finding, write 1-2 lines: what's wrong, where (selector or section), why it hurts the goal.
6. Sort findings by severity descending, then by dimension.
7. Emit findings + a one-line summary.

---

## Output

Markdown block + sidecar JSON (per cross-cutting convention C1).

```markdown
| # | Dimension | Heuristic | Status | Severity | Note |
|---|-----------|-----------|--------|---------:|------|
| 1 | <dim> | <criterion> | ⚠️ | 4 | <observation> |
| 2 | <dim> | <criterion> | ✅ | n/a |: |
```

```json
[
  {
    "id": 1,
    "dimension": "<dim>",
    "criterion": "<text>",
    "status": "issue",
    "severity": 4,
    "note": "<observation>",
    "selector_or_section": "<where>"
  }
]
```

---

## Failure modes

- **Empty rubric.** Stop and return `[]`. Do not invent heuristics.
- **Artifact unreachable.** Log the URL and skip; do not retry blindly.
- **Ambiguous status (pass or issue, not sure).** Surface the ambiguity in the note instead of silently choosing. Flag with a `?` and severity 1.

---

## Notes

Keep this file under ~500 lines (Anthropic spec). If methodology grows beyond that, split into multiple skills (e.g. one per dimension) or move bulk data into `assets/`.

The actual rubric data lives in `assets/example-checklist.md`. Never inline more than a few illustrative rows in the SKILL.md itself.
