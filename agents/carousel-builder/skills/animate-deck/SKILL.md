---
name: animate-deck
description: Turns a validated deck.json into a short MP4 for LinkedIn and Instagram (4:5 1080x1350 by default, 9:16 1080x1920 or 1:1 1080x1080), locally and for free - the same build.py, fit.js and slides as the stills, sober entrances block by block (title then body, list items one by one, bars that grow, a stat that counts up), a reading time per slide computed from its word count, a crossfade between slides, deterministic capture through Playwright and ffmpeg (H.264, yuv420p, 30 fps, faststart), optional local music with a fade out, then QA on the file and a frames sheet the model reviews. Use after build-and-review passes, when the founder wants a video variant. Triggers on "video", "animate the carousel", "reel", "MP4 version".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "2.0"
allowed-tools: Read Write Bash(python3:*)
---

# animate-deck

The video is the carousel, moving. Same spec, same engine, same validated slides: the motion only decides when each block appears. The model never writes a frame, a keyframe or a word for the video; it picks options, reads the frames sheet and fixes `deck.json` when something reads badly.

## When

After [`../build-and-review/SKILL.md`](../build-and-review/SKILL.md) passes (`export/qa.json` with 0 error) and the founder asked for a video, or `config.json` has `video.aspects`. The script refuses a deck with spec errors or fit failures (exit 1): a video never shows a slide the stills would not ship.

## Commands

```bash
# Default: the deck's own ratio (4:5), into <run>/export/video-4x5.mp4
python3 scripts/animate.py <run>/deck.json

# Reels, TikTok, Shorts
python3 scripts/animate.py <run>/deck.json --aspect 9:16

# Inside the pipeline, right after the stills (only when their QA passes)
python3 scripts/pipeline.py <run>/deck.json --video 4:5,9:16

# A local music file, faded out on the last 2 s; a total cap for a faster cut
python3 scripts/animate.py <run>/deck.json --aspect 9:16 --music media/track.mp3 --max-duration 45
```

`python3 scripts/animate.py --help` lists every option. The run writes `export/video-<aspect>.mp4`, `export/video-<aspect>.json` (timeline per slide, render stats, QA) and `export/video-<aspect>-frames.jpg` (mid-entrance and settled frame per slide).

## What moves, and what never does

| Block | Motion |
|-------|--------|
| title | title rises in (opacity and a 24 px lift), then the sub-line |
| body | paragraph by paragraph |
| list | item by item |
| stat | the number counts up to its value in its own format (a year or a value with two numbers only fades), then label and context |
| chart | frame and labels fade, bars grow from the zero axis one after the other with their values, lines draw along their length, donut segments sweep |
| quote | quote, then attribution |
| photo, visual | fade, never a crop, a zoom or a pan |
| screenshot | fade, then the annotation pins one by one |
| logo row, CTA | item by item |
| slide to slide | 0.5 s crossfade; header, footer and sources arrive with the slide |

Never: glow, pulse, bounce, parallax, Ken Burns, text typed letter by letter, per-word animation, a counter that runs on a number the slide does not show. The motion vocabulary follows [`../../references/design-rules.md`](../../references/design-rules.md).

## Timing

- Each slide holds its reading time: `1 s + words / 200 wpm`, clamped to 3 s and 8 s, never shorter than its entrance plus 1 s. Chart labels count one word each (they are glanced, not read). The 200 wpm default sits under the 238 wpm average silent reading rate for non-fiction (Brysbaert 2019, https://doi.org/10.1016/j.jml.2019.104047) because the viewer also watches the motion.
- The first slide is complete on frame 0: that frame is what feeds show before playback. It holds 5 s at most; the hook has to work before the scroll.
- The last slide holds 1 s more so the call to action is not cut by the loop.
- `--max-duration N` fits a total by shortening holds in proportion; entrances are never shortened. When even the entrances do not fit, the run says so: cut slides with `--slides` or in a dedicated `deck.json`.

## 9:16 and 1:1

A 4:5 slide on a 9:16 canvas is scaled whole into the safe box and centred on its own ground (the slide's background colour and texture continue around it). Default `--safe reels` keeps 220 px at the top, 430 px at the bottom and 90 px on each side clear of the Reels, TikTok and Shorts overlays; the slide shows at 83 % (smallest text 20 px on the canvas). `--safe ads` applies Meta's ads margins (14 % top, 35 % bottom, 6 % sides) for a paid placement; the slide then shows at 73 % and the run warns about text size. A 4:5 slide on 1:1 shows at 80 % with side bands.

Why not recompose for 9:16: a recomposed slide is a new layout that fit.js and qa.py have not validated, and the founder approved the 4:5 slides. Scaling keeps the approved slides exactly. For a native 1:1 video, write the deck with `meta.format: "square"` and run the stills QA on it first.

## Review loop (2 rounds at most)

1. Read the terminal summary and `export/video-<aspect>.json`: `qa.status` must be `pass`. QA errors (codec, size, fps, frame count, duration, faststart, black first or last frame, audio, LinkedIn limits) are fixed by re-running with the right options, never by re-encoding by hand.
2. With `vision`, read `export/video-<aspect>-frames.jpg`, then the full-size frames that look wrong (`--keep-frames DIR` writes every PNG). Check: the first tile is the complete cover; no text appears half covered by another block mid-entrance; counts read as numbers in the slide's format; bars grow from the axis; the 9:16 slide sits clear of the bottom band. Without `vision`, the founder reviews the sheet.
3. A slide that feels rushed or slow is a copy problem first (too many words for one slide: split it in `deck.json`), a `--wpm`, `--min-slide`, `--max-slide` choice second.

## Deliver

Add to the stop 2 message of [`../export-deck/SKILL.md`](../export-deck/SKILL.md): the path of each MP4, its duration and size, the frames sheet, and the posting notes:

- LinkedIn: upload the MP4 as a native video (3 s to 15 min, 30 Mbit/s at most: https://www.linkedin.com/help/linkedin/answer/a548372); the post text and the first comment from `captions.md` stay the same; set a thumbnail from the cover if the platform proposes another frame.
- Instagram: 4:5 as a feed video, 9:16 as a Reel; caption from `captions.md`.
- Music: only a file the founder owns or licensed for this use; the agent never downloads a track.

The agent never publishes.

## HyperFrames (optional)

When the harness has the `hyperframes` CLI and its skills, a richer composition (kinetic type, designed transitions, a voice-over) can be authored from the same `deck.json` with them, as a separate deliverable the founder chose. The default path above needs only Playwright and ffmpeg and stays the reference: same slides, same QA.

## Failure modes

- **Exit 1 before rendering** → spec errors or texts that do not fit: back to build-and-review. `--force` exists for debugging only; never deliver a forced video.
- **`ffmpeg` or `ffprobe` missing (exit 2)** → `apt install ffmpeg` or `brew install ffmpeg`.
- **Fonts fall back** → same cause and same fix as the stills (`font-fallback` in `qa.json`).
- **Video too long for the platform or the founder** → `--max-duration`, or fewer slides; never shorten the entrances by hand.
- **Music shorter than the video** → it loops; longer → it is cut and faded out.
