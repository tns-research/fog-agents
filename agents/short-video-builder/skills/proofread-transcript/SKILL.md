---
name: proofread-transcript
description: Hard gate before any short is rendered - the whole transcript is read page by page (not only the names), every mishearing is fixed as a span correction that keeps karaoke timing, ambiguous words get evidence instead of a guess, and the result is signed so the renderer refuses any transcript changed afterwards. Use at Step 3 of short-video-builder, and again whenever words.json changes. Triggers on "proofread the captions", "fix the transcript", "the caption says the wrong word", "corrections.json".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*) Bash(ffmpeg:*)
---

# proofread-transcript

A recogniser does not only mangle brand names. It turns ordinary phrases into other plausible words ("raise your hand" heard as "raisin hand"), drops a zero from a figure, splits a product name in two, hears a common word instead of an acronym. Checking only the names lets those through, and a nonsense caption on screen costs the short as much as a misspelt company. So the whole transcript is read, every time.

Script: `scripts/proofread.py` (dump, apply, sign, status).

## 1. Read every page

```bash
python3 scripts/proofread.py dump <run>/words.json --page 1     # then --page 2, 3 ... or --all for a short talk
```

Each page prints the words with their indexes and times, ten per line, then a **check first** list: numbers, capitalised words that may be names or acronyms, and words the engine was unsure of (faster-whisper probability under 0.5). Start with that list, then read every line of the page as sentences: does each sentence make sense, is it what a person would say there? The script records which words were printed; `sign` refuses while a word was never shown.

What to look for:

| Kind | Examples of what goes wrong |
|------|------------------------------|
| Names | company, product, people, places, the event; split ("swan base"), merged, phonetic spelling |
| Numbers | magnitude (10 vs 100, million vs billion), units, percentages, years, money symbols |
| Acronyms and jargon | ARR, MRR, SaaS, KYC, ERP, technical terms heard as common words |
| Homophones and near-sounds | a common phrase replaced by a similar-sounding one that is grammatical but absurd |
| Elisions and contractions | French `l'`, `c'est`, `qu'`; English `don't`, `we're` split or lost |
| Fillers and false starts | "um", repeated words: delete them only inside clips, and only when the speaker's meaning stays intact |
| Noise | applause or music transcribed as words |

Never rewrite what the speaker said into better prose: corrections restore what was said, nothing else.

## 2. Write corrections.json

A list; each item is either a phrase replacement or an index span:

```json
[
  {"find": "raisin hand", "replace": "raise your hand", "why": "mishearing, the speaker asks the room"},
  {"find": "swan base", "replace": "swanbase", "why": "brand name is one word (context.json)"},
  {"i": 412, "j": 413, "text": "", "why": "false start 'we we' inside clip demo-comes-last"}
]
```

- `find` matches the raw transcript word sequence, ignoring case and outer punctuation; every occurrence by default, or `"occurrence": n`.
- `i`/`j` are inclusive word indexes of the raw transcript (the dump's indexes before any apply).
- An empty `replace`/`text` deletes the span. Trailing punctuation of the span is kept when the replacement has none, so sentence edges survive.
- The span's time window is shared between the new words by length: the karaoke highlight stays in sync even when the word count changes.

```bash
python3 scripts/proofread.py apply <run>/words.json <run>/corrections.json
```

`apply` always starts from `words.raw.json` (snapshotted on the first apply), so it can be run again after editing corrections. A `find` that matches nothing or two overlapping corrections fail the whole file and nothing is written.

## 3. Ambiguous spans: evidence, not guesses

When the transcript has a non-word or a name you cannot confirm:

1. Look for it in the founder's material: `context.json`, the talk's slides, the event page, the speaker's site.
2. Re-transcribe only that window with a larger model and a prompt of domain terms:
   `ffmpeg -ss <t0> -to <t1> -i <video> -ar 16000 -ac 1 window.wav`, then `python3 scripts/transcribe.py window.wav --model large-v3 --prompt "<terms>" --out window.json` and read it.
3. Still unclear: do not put a guess on screen. Cut the span out of the clip (move `start` or `end`), or drop that clip, and list the question in the report for the founder.

## 4. Sign

```bash
python3 scripts/proofread.py sign <run>/words.json --reviewer model     # or founder, or a name
python3 scripts/proofread.py status <run>/words.json                    # exit 0 = the renderer will accept it
```

The signature holds the hash of the corrected `words.json`. Any later change (a new correction, a re-transcription) voids it: dump the changed pages, apply, sign again. `pipeline.py` and `render.py` refuse to render without a valid signature; `--allow-unproofread` exists for drafts only and its shorts fail QA with `not-proofread`, so they cannot ship by mistake.

## 5. After the render

Read the caption strips (`review/<id>/captions-strip.jpg`) at Step 5: a word that looks right in the dump can still be split badly into caption groups, or an estimated timing can drift. A caption fix goes back here (corrections, sign, re-render), never into the video.

## Failure modes

- **Long talk** → page by page is the only way; the dump marks progress so a session can stop and resume (`--page` of the first unread page is printed at the end of each dump).
- **The founder corrects a caption after delivery** → add the correction, sign, re-render that clip, and record the term in `names_to_spell` (and as a project decision) so the next run primes it.
