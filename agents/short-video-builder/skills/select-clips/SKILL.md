---
name: select-clips
description: Chooses the excerpts of a long talk that work as standalone vertical shorts for a stated objective (reach, leads, authority) and writes them as clips.json - span on sentence boundaries, the spoken hook copied verbatim, the reason, title and post copy, brand style and an optional end card - never an intro card. Reads the whole digest, spreads picks over the talk, and lets clipspec.py check spans, hooks and lengths against the transcript. Use at Step 2 of short-video-builder. Triggers on "find the best moments", "which clips", "cut shorts from this talk", "clips.json".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*)
---

# select-clips

A short is watched by a stranger, on mute half the time, who decides in the first seconds whether to stay. The excerpt must make sense with no context, start on a sentence that earns attention, and end on a sentence that closes the thought. The model chooses; `clipspec.py` checks what can be checked.

## 1. Read everything

Read `digest.md` from the first line to the last before choosing. The best moment of a talk is often in the Q&A or the closing minutes; a choice made on the first third misses it. Note candidates as you read: line indexes, times, why.

## 2. What makes an excerpt

A candidate passes when all of these hold:

- **Standalone.** A viewer who saw nothing else follows it. No "as I said", no "this", no unexplained name or number from earlier. If the setup is two sentences earlier, start there.
- **Opens on its hook.** The first spoken sentence is the strongest available opening: a claim against common belief, a concrete stake, a question the viewer has, a number that surprises (said by the speaker), the start of a story. Not a greeting, not "so", not a slide reference.
- **One idea.** One point, one story or one method. Two ideas make two shorts.
- **Closes.** It ends on a sentence that lands: the conclusion, the punchline, the rule. Not mid-list, not on "and".
- **Length.** Within `duration_limits` (default 15 to 60 s). Shorter is better when the idea is complete; never pad.

Objective shaping:

| Objective | Prefer | End with |
|-----------|--------|----------|
| `reach` | reversals, strong opinions, stories with a turn, front-loaded payoff | the line people will quote |
| `leads` | problem, insight, how the founder solves it (implied), credibility beats said by the speaker | an end card with one action and the URL |
| `authority` | teaching moments, a method in steps, a sharp point of view, lessons from the founder's own numbers | the rule, stated plainly |

Spread the picks across the talk (beginning, middle, end) and never cut two shorts of the same moment (`clipspec.py` warns at 50 % overlap). Pick `clips_count` excerpts; when the talk has fewer good ones, ship fewer and say why.

## 3. Write clips.json

Contract: [`../../assets/clips.schema.json`](../../assets/clips.schema.json). Example: [`../../examples/synthetic-talk/clips.json`](../../examples/synthetic-talk/clips.json).

- `source`, `transcript`: paths relative to the spec.
- Per clip: `id` (kebab-case, becomes the file name), `start` and `end` copied from the digest lines (seconds or `M:SS.s`; `clipspec.py` snaps them to word edges, adds a short breath before the first word and after the last, and never cuts a word or an elision in half), `hook` (the first sentence as it appears in the proofread transcript, word for word), `reason` (what a stranger gets from it, for this objective), `title` and optional `post` (copy for the platform).
- `style`: `brand_json` to the project's `brand.json` (accent for the active word and the progress bar, text colour, end-card ground, body font), or explicit values. The font must be installed on the machine.
- `speaker`: name and role for the lower third, or omit it.
- `cta`: optional end card (one to three short lines and a URL). It dissolves in after the last word while the source keeps playing under it; enable it per clip or for all. Leads objective: usually on; reach: usually off.
- `framing` per clip only when needed: two people on screen (`"x"` = which one to follow), or a speaker the face detector misses (`"mode": "fixed"`).

There is no intro, title or hook card in this spec, and none may be added: the first frame is the speaker, a breath before the hook. A title belongs in the post, and the hook belongs in what the speaker says.

## 4. Copy rules for titles and posts

- Same language as the talk unless the founder asked otherwise.
- The writing gate runs on them in `clipspec.py`; fix every BLOCK.
- A number or a name in the copy comes from what the speaker said in the clip (quote it as theirs) or from `positioning.proof`; nothing else (`../../../../shared/skills/enforcing-claims-policy/SKILL.md`).
- The title says what the viewer learns, not that it is "a must-watch".

## 5. Check

`python3 scripts/clipspec.py <run>/clips.json` runs at Step 4, once the transcript is proofread (hooks are compared with the corrected words). Typical fixes:

| Code | Fix |
|------|-----|
| `hook-mismatch` | move `start` to the hook sentence, or copy the hook from the corrected transcript |
| `starts-mid-sentence` / `ends-mid-sentence` | widen to the sentence edge (or keep it, with the reason in the report) |
| `too-short` / `too-long` | take the setup sentence, or cut the aside; never pad |
| `slow-hook` | start one sentence later on a shorter opening, if it still stands alone |
| `overlap` | drop one of the two, or move one to another moment |
