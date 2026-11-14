# Shorts: <talk title or label>

**Project:** <project-slug> · **Date:** <YYYY-MM-DD> · **Language:** <fr | en | ...> · **Objective:** <reach | leads | authority>
**Source:** <file name>, <duration>, <width>x<height> at <fps> · **Shorts:** <N>
**Status:** <ready for approval | delivered with open issues | partial (reason)>

<If anything is open, list it here first: QA errors left, warnings kept, review items not fixed, words that could not be confirmed and were cut.>

---

## 1. Shorts

| id | File | Length | Source span | Hook (spoken) | Why this excerpt | QA |
|----|------|--------|-------------|---------------|------------------|----|
| <id> | `export/<id>.mp4` | <s> | <M:SS-M:SS> | <verbatim first sentence> | <one line> | <pass, warnings kept> |

First frames: `review/first-frames.png`.

## 2. Transcript and proofreading

- **Engine:** <faster-whisper medium | whisper.cpp <model> | openai-whisper <model> | import (srt/vtt/json)>, timing <measured | estimated per cue>
- **Proofread:** <N> corrections over <N> words, signed by <model | founder>. Main fixes: <"swan base" to "swanbase", ...>
- **Unconfirmed words:** <none | what, where, and what was done (span cut, clip dropped, question below)>

## 3. Quality

- **export/qa.json:** <pass/fail>, <errors>, <warnings kept with the reason>
- **Frame rate:** source <fps>, every short <fps> (no resampling)
- **Loudness:** <LUFS per short>, target <target>
- **Visual review:** <rounds>, rubric <scores>/16, by <model | founder | not done>
- **Fresh reviewer:** <PASS/FAIL>, <scores>, <main points and the revision> (or "not run")
- **Writing gate:** <pass, BLOCKs fixed> · **Claims:** <every figure in the copy said by the speaker in the clip, or from positioning.proof>

## 4. Files

| File | Use |
|------|-----|
| `export/<id>.mp4` | upload as a vertical video (Reels, TikTok, Shorts, LinkedIn) |
| `posts.md` | title and post copy per short |
| `clips.json` | the source: every change goes here, then `pipeline.py` |
| `words.json`, `corrections.json`, `proofread.json` | the signed transcript |
| `review/` | first frames, sheets, caption strips |

## 5. Posting notes

<Per platform: which short first and why, the caption from posts.md, the link placement (end card, first comment or bio), cover frame choice. The agent does not publish: the founder approves and posts.>

## Methodology

- Providers: transcription <engine>, vision <builtin | founder | none>, critic <subagent | CLI | founder | none>, copy_lint <writing gate | manual>
- Defaults used: <objective, clips_count, duration, style, end card...>
- Checks: writing gate <result>, claims <result>, schemas <result>, render review <rounds>, fresh eyes <verdict>, run log <written>

## Limitations

<Skipped capabilities and what they left unverified; estimated timings; a soft 720p source; anything the founder must look at before posting.>
