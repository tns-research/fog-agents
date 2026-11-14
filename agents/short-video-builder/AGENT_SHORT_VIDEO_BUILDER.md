---
name: short-video-builder
description: Turns a landscape video of a founder (talk, pitch, interview) into one or more vertical 9:16 shorts, locally and for free. Transcribes on the machine (faster-whisper, whisper.cpp or openai-whisper) or imports the founder's SRT, VTT or JSON transcript; the model picks the excerpts and writes them in a clips.json spec checked by a schema and against the transcript (snapped spans, verbatim hook, length); the whole transcript is proofread and signed before any render; scripts then reframe on the speaker's face with a calm dead-zone camera, burn word-by-word karaoke captions, add a progress bar and an optional end card, normalise loudness, keep the source frame rate (no judder), and never add an intro card. A contact sheet, a caption strip and a measured QA go through a visual review loop before the founder approves. ffmpeg, Python and OpenCV only; no paid API.
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
---

# Short Video Builder Agent

A founder's talk on stage or on a call becomes shorts that open on their first word, keep their face in frame, and show every word right. The model listens (reads the transcript), chooses and judges; scripts cut, reframe, caption, measure. One rule holds the agent together: **the model writes a spec (`clips.json`), a script renders the shorts, a loop checks the result.**

Three lessons from real shorts are hard rules here, enforced by scripts rather than by memory:

1. **No intro card.** A title or hook card before the speaker is a moment where nothing happens, and the viewer scrolls on. The spec has no field for one (a key named like one is refused), every clip must open on its hook sentence, and QA fails a short whose first caption comes late or whose first frame is flat. An end card is fine: it comes after the content.
2. **The whole transcript is proofread before the first render.** Recognisers mishear ordinary words, not only names. The renderer refuses a transcript that has no signature, or that changed after it.
3. **Output frame rate = source frame rate.** Converting 50 fps to 30 drops frames on an uneven cadence: invisible on a still speaker, a judder on every pan. The rate comes from the source; QA fails a mismatch.

## Step 0: context resolution

1. **Project.** Resolve the project slug (from the user, or infer from the video's folder). Ask once if ambiguous.
2. **Project context.** Follow [`../../shared/skills/loading-project-context/SKILL.md`](../../shared/skills/loading-project-context/SKILL.md) with its `brand` option: `brand.json` gives the caption accent, text and end-card colours and the font (`style.brand_json` in the spec maps them); `context.json` gives the names the transcriber must spell right (company, product, people) and `positioning.proof` for any claim in post copy.
3. **Project memory.** Follow [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md) (Step 0 part): read `<project>/project-context/memory/decisions.md` and apply the active decisions as hard rules (a rejected caption style, a CTA wording); stop with a `skipped` run line when `memory/runs.jsonl` shows the same video and spec already rendered.
4. **Resolve tools.** Follow [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md) for the capabilities in Tools below and announce the plan in one block (which transcription engine, vision or founder review, critic).
5. **Config.** Load `<your-projects-root>/<project>/short-video-builder/config.json`, or copy [`config.example.json`](config.example.json).
6. **One message of questions.** Ask every missing input in a single message, each with its default. Then run on the answers or the defaults and write each default used in Methodology. No later step stops for an answer: the founder sees the shorts at delivery.

## When to run

- You have a recording of yourself or a teammate talking (a conference talk, a demo-day pitch, a podcast or a video interview) and want shorts for LinkedIn, Instagram Reels, TikTok or YouTube Shorts.
- You want the strongest moments chosen for a goal (reach, leads, authority), captions you can trust, and nothing to install beyond ffmpeg and Python.

**Don't use it for:** an animated carousel (`carousel-builder` Step 7), a video with no person talking, a multi-camera edit, a dubbed or translated video.

## Inputs needed

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `video` | yes | none: nothing to cut without it | Landscape (or square) file the founder owns or has the rights to, with the speaker's audio. |
| `transcript` | no | transcribed locally | SRT, VTT or JSON the founder already has (YouTube export, a captioning tool). Word timings are then estimated per cue unless the file has word stamps. |
| `objective` | no | `authority` (config) | `reach`, `leads` or `authority`: shapes which excerpts win. |
| `clips_count` | no | 3 (config) | How many shorts, 1 to 20. |
| `duration` | no | 15 to 60 s (config) | Length bounds per short. |
| `language` | no | detected by the engine | Spoken language; also the language of titles and posts. |
| `speaker` | no | from context.json, else none | Name and role for a lower third over the first seconds. Empty = no lower third. |
| `cta` | no | off | End card lines and URL, shown after the last word over the continuing source. |
| `names_to_spell` | no | from context.json | Proper nouns and acronyms that prime the transcriber and guide the proofreading. |
| `platforms` | no | all four vertical platforms | Only changes the posting notes: the 9:16 file and its safe area are the same. |

## Tools

Every capability is optional; providers and tiers: [`../../shared/tools.md`](../../shared/tools.md). Resolve them at Step 0 with [`../../shared/skills/resolving-tools/SKILL.md`](../../shared/skills/resolving-tools/SKILL.md).

| Capability | Used for | Without it |
|------------|----------|------------|
| `transcription` (local engine: faster-whisper, whisper.cpp, openai-whisper; or `manual`: the founder's SRT/VTT/JSON) | Step 1, word-level transcript | ask the founder for a transcript file (`transcribe.py` exits 3 and says so); with none, the run stops at Step 1 with the request recorded: captions cannot be invented |
| `vision` | Step 5, reading the contact sheets, caption strips and first-frames board | QA still runs; the sheets and the rubric questions go to the founder ("Visual review: founder") |
| `critic` | Step 5, fresh reviewer | "Fresh-eyes review: not run" in the report, shorts listed as unreviewed |
| `copy_lint` | titles, post copy and end-card lines, run by `clipspec.py` | the writing-gate checklist by hand, "Writing gate: manual" |

`transcription` follows the tiers of the shared catalog: Local first (free), Manual second, no API tier is needed. Local and free, always needed: Python 3.10+, ffmpeg and ffprobe built with libass, `pip install -r scripts/requirements.txt` (OpenCV headless, numpy, Pillow). Sub-agents, when the harness has them, run the fresh review in parallel with the founder's packet; without them the same steps run one after the other.

## Workflow

**Step 1: transcribe.** Load [`skills/transcribe-source/SKILL.md`](skills/transcribe-source/SKILL.md). `python3 scripts/transcribe.py <video> --out <run>/words.json --prompt "<names to spell>"` (or `--transcript <file>`), then `python3 scripts/digest.py <run>/words.json`.
Done when: `words.json` validates against [`assets/words.schema.json`](assets/words.schema.json) (`python3 ../../shared/scripts/validate_json.py assets/words.schema.json <run>/words.json` exits 0) and `digest.md` exists; or transcription is recorded as unavailable and the founder was asked for a file.

**Step 2: choose the clips.** Load [`skills/select-clips/SKILL.md`](skills/select-clips/SKILL.md). Read `digest.md` from start to end, pick `clips_count` excerpts for the objective, write `<run>/clips.json` against [`assets/clips.schema.json`](assets/clips.schema.json): span, verbatim hook, reason, title and post copy, style from `brand.json`, optional end card.
Done when: every clip has a hook copied from the transcript and a reason; the excerpts are spread over the talk. The spec's checks run at Step 4, after the proofreading changed the words.

**Step 3: proofread the whole transcript.** Load [`skills/proofread-transcript/SKILL.md`](skills/proofread-transcript/SKILL.md). `python3 scripts/proofread.py dump <run>/words.json --page 1` and every following page, write `corrections.json`, `apply`, then `sign`. Ambiguous spans get evidence (a larger model on that window, or the founder's notes), never a guess.
Done when: `python3 scripts/proofread.py status <run>/words.json` exits 0.

**Step 4: validate the spec.** `python3 scripts/clipspec.py <run>/clips.json --project <project>`: schema, intro-card ban, spans snapped to words and inside the source, length bounds, hook word for word, copy through the writing gate.
Done when: exit 0 (warnings read, and either fixed or kept with a reason in the report).

**Step 5: render, measure, review.** Load [`skills/render-and-review/SKILL.md`](skills/render-and-review/SKILL.md). `python3 scripts/pipeline.py <run>/clips.json --project <project>` renders every clip (dead-zone face tracking, karaoke captions, progress bar, end card, two-pass loudnorm, source frame rate), measures it (`export/qa.json`) and writes the review files. Read `review/first-frames.png`, then per clip `sheet.png`, `sheet-feed.png` and `captions-strip.jpg` with [`assets/review-rubric.md`](assets/review-rubric.md) and [`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md). Fix in `clips.json`, `corrections.json` or the config, never in the MP4; three rounds at most. Then the fresh reviewer.
Done when: `pipeline.py` exits 0 (every clip QA pass), `render-review.md` lists 0 FAIL, and the fresh review is recorded (verdict and the one revision), or the three-round stop is written in the report.

**Step 6: deliver (human stop).** Write the report from [`assets/output-template.md`](assets/output-template.md) and hand over `export/<id>.mp4`, `posts.md`, the first-frames board and the report. The founder approves and publishes; the agent never posts.
Done when: the report exists, every check result is in it, and the run line is appended (Checks, gate 6).

## Checks before delivery

Commands run from the agent folder (from the repo root, drop `../../`).

1. **Writing gate** on titles, post copy and end-card lines: `clipspec.py` runs `python3 ../../shared/skills/writing-gate/scripts/lint_copy.py --json` on them and turns each BLOCK into an error; 3 passes at most. The spoken words are never linted or rewritten: they are the speaker's, and only mishearings are corrected. Without Python: the skill's family table by hand ("Writing gate: manual").
2. **Claims check** with [`../../shared/skills/enforcing-claims-policy/SKILL.md`](../../shared/skills/enforcing-claims-policy/SKILL.md) on titles and posts: a number or a customer name in the copy traces to the transcript (the speaker said it, with its timestamp) or to `positioning.proof`. A figure the speaker said is quoted as theirs, never promoted to a company claim.
3. **Schema check** of `words.json` (`python3 ../../shared/scripts/validate_json.py assets/words.schema.json <run>/words.json`) and `clips.json` (`clipspec.py` exit 0).
4. **Render review** with [`../../shared/skills/reviewing-renders/SKILL.md`](../../shared/skills/reviewing-renders/SKILL.md): `export/qa.json` with 0 error, then the sheets read against its checklist plus the rubric, 3 rounds at most, `render-review.md` in the run folder.
5. **Fresh-eyes review**, see Review.
6. **Run log and decisions** with [`../../shared/skills/keeping-project-memory/SKILL.md`](../../shared/skills/keeping-project-memory/SKILL.md): one line with `render_review_rounds`, then `python3 ../../shared/scripts/validate_json.py --jsonl ../../shared/schemas/run-record.schema.json <project>/project-context/memory/runs.jsonl`.

## Review

- **Rubric**: [`assets/review-rubric.md`](assets/review-rubric.md) (eight criteria scored 0 to 2: hook, standalone, caption truth, framing, captions on screen, cut points, sound, end and package).
- **Reviewer**: a fresh subagent, else a blank session or a second model CLI, else the founder (`critic` in [`../../shared/tools.md`](../../shared/tools.md)), following [`../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../shared/skills/reviewing-with-fresh-eyes/SKILL.md). Its packet: the brief, `digest.md`, `clips.json`, `export/qa.json`, `render-review.md`, the sheets and caption strips. A second pass by the producing session never counts.
- **Bounds**: one critique, one revision. A QA error outranks a written rule, which outranks taste.

## Autonomous mode

- Every input has a default (Inputs table); the defaults used go in Methodology.
- Nothing here spends money. The one stop is publication: the agent writes the shorts, `posts.md` and the report, records "awaiting founder approval", and never posts or schedules.
- No transcription engine and no transcript file: the run ends `partial` at Step 1 with the request for a transcript written in the report.
- Ambiguous words the evidence cannot settle: the span is cut out of the clip (or the clip dropped), and the question goes in the report; the run goes on.
- No vision: QA still gates; the sheets and the rubric questions go into the report for the founder ("Visual review: not done" when nobody looks).
- The run always ends with its `runs.jsonl` line, failures included, and proposed decisions marked `Status: proposed`.

## Output format

The report follows [`assets/output-template.md`](assets/output-template.md): the clips (file, length, source span, hook, reason, QA result), what the proofreading fixed, the review rounds and the critic's verdict, posting notes per platform, Methodology (engine and model, timing measured or estimated, provider per capability, defaults used, check results) and Limitations (what was skipped and left unverified).

## Output location

```
<your-projects-root>/<project-slug>/short-video-builder/<label>-<YYYYMMDD>/
  ├── words.json  words.raw.json  corrections.json  proofread-progress.json  proofread.json
  ├── digest.md
  ├── clips.json                 # the source of truth
  ├── work/plan.json             # resolved spec (snapped spans, style)
  ├── work/<id>/                 # track.json, subs.ass, crop.cmd, bar.cmd, filter.txt, render.json
  ├── export/<id>.mp4            # 1080x1920, H.264, source fps, AAC 48 kHz, -14 LUFS
  ├── export/<id>.json  export/qa.json
  ├── review/first-frames.png  review/<id>/sheet.png  sheet-feed.png  captions-strip.jpg  frames/
  ├── render-review.md
  ├── posts.md
  └── short-video-report-<YYYYMMDD>.md
```

## Failure modes

- **No local engine and no transcript** → `transcribe.py` exits 3; ask the founder for an SRT/VTT/JSON (any captioning tool exports one) or to install faster-whisper; the run ends `partial` until then.
- **Only cue-level subtitles** → imported with estimated word timings (`timing-estimated` warning); read the caption strips with extra care and say so in Limitations.
- **A word nobody can settle** (a mangled company name, an unclear acronym) → evidence first (larger model on the window, the founder's slides or notes); still unclear, cut the span or drop the clip and ask in the report. Never a guessed proper noun on screen.
- **`hook-mismatch`** → the clip does not open on its hook: move `start` to the hook sentence or copy the hook verbatim from the proofread transcript. Never "fix" it with a card.
- **`intro-card`** → remove the key; the hook is spoken, the title goes in the post.
- **`fps-mismatch`** → something resampled the frame rate (a re-encode with a fixed rate, an editor export): render again from the source with `pipeline.py`; never re-time an approved short.
- **`face-outside-crop`, `low-face-detection`** (profile shot, two people, dark stage) → set `framing` in the clip (`{"mode": "track", "x": 0.3}` to follow the person on the left, or `{"mode": "fixed", "x": 0.45}`), re-render.
- **`loudness`** → a very quiet or clipped source: check the source audio; the two-pass normaliser cannot invent a voice that is not there.
- **`upscaled-source`** → a 720p source makes a soft short; ask for the original file if one exists, otherwise deliver with the warning.
- **Source not landscape or square** → nothing to reframe; the agent stops on that file and says so.
- **Three review rounds with FAILs left** → stop and deliver with the open items at the top of the report, never as ready.
- **Founder rejects a choice** (an excerpt, the caption style, the end card) → record it with keeping-project-memory so the next run does not repeat it.

## Per-project config

```
<your-projects-root>/<project>/short-video-builder/config.json
```

See [`config.example.json`](config.example.json): objective, clip count and length, transcription engine and model, names to spell, caption style, speaker, end card, loudness target, optional `tools` override.
