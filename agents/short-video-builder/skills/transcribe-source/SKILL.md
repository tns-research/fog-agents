---
name: transcribe-source
description: Produces the word-level transcript a short is cut and captioned from, on the founder's machine. Picks a local engine (faster-whisper, whisper.cpp, openai-whisper) or imports the founder's SRT, VTT or JSON, primes the model with the names it would mangle, writes words.json and a sentence digest, and checks coverage before anything else runs. Use at Step 1 of short-video-builder. Triggers on "transcribe the talk", "use my subtitles", "words.json", "whisper".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*) Bash(ffmpeg:*) Bash(ffprobe:*)
---

# transcribe-source

Everything downstream reads `words.json`: the excerpt choice, the hook check, the karaoke timing, the end-card timing. A transcript with good words and bad timings gives captions that drift; good timings and wrong words give captions that lie. This step gets both as right as the machine allows, then the proofreading step fixes the words.

## 1. Pick the engine

`python3 scripts/transcribe.py <video> --out <run>/words.json` with `--engine auto` walks this order:

| Order | Engine | When | Word timings |
|-------|--------|------|--------------|
| 1 | `import` | the founder gave `--transcript` (SRT, VTT, JSON) | estimated per cue, measured when the VTT has inline word stamps or the JSON has words |
| 2 | `faster-whisper` | `pip install faster-whisper` | measured, with a probability per word (proofread flags the unsure ones) |
| 3 | `whisper-cpp` | a whisper.cpp binary (`whisper-cli`, `whisper-cpp` or `main`) and a ggml model (`--whisper-cpp-model` or `WHISPER_CPP_MODEL`) | measured (one word per segment) |
| 4 | `openai-whisper` | the `whisper` command | measured |

None available: exit 3. Ask the founder, in the Step 0 message if possible, for a transcript file (every captioning tool and YouTube Studio export SRT or VTT), or to install faster-whisper. Never write captions from memory of the video.

## 2. Choose the model size

- `medium` is the default. Smaller models produce plausible but wrong words in ordinary sentences, which then show on screen; they are acceptable for a quick look at what was said, not for captions.
- `large-v3` for a hard recording (room echo, strong accent, many names) or for re-transcribing one ambiguous window during proofreading (see `skills/proofread-transcript/SKILL.md`).
- CPU transcription is slower than real time on modest machines: run it in the background and do Step 0 reading meanwhile.
- `--language` when known: auto-detection on a bilingual talk sometimes picks the wrong one for the first segment.

## 3. Prime the names

`--prompt` takes a short sentence that spells the words the model would mangle: the speaker's name, the company, the product, recurring acronyms, the event. Take them from `context.json` (company, product, people) and the config's `names_to_spell`. Example: `--prompt "Sam Rivera, Lumen Ledger, swanbase, pre-seed, ARR."` Keep it short: a long prompt can leak into the transcript.

## 4. Check the result

- `python3 ../../shared/scripts/validate_json.py assets/words.schema.json <run>/words.json` exits 0.
- The last word ends near the end of speech in the video (a transcript that stops halfway means the engine choked on a silence or the import missed cues).
- `timing` is `word`, or `estimated` and the limitation is noted for the report.
- `python3 scripts/digest.py <run>/words.json` writes `digest.md`: one line per sentence with word indexes and times. Read it end to end at Step 2.

## Failure modes

- **Audio missing or not decodable** → `transcribe.py` exits 2 with ffmpeg's message; ask for another export of the file.
- **Two languages** → transcribe with the main language, note the other passages for proofreading; captions keep what was said.
- **Music or applause stamped as words** → bracketed noise cues (`[Applause]`) are dropped on import; stray words in a music bed are fixed or deleted at proofreading.
