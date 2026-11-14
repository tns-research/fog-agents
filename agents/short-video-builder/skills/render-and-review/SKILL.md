---
name: render-and-review
description: Renders every clip of clips.json into a 1080x1920 short with ffmpeg (dead-zone face tracking with sub-pixel pan, word-by-word karaoke captions, progress bar, lower third, optional end card over the continuing source, two-pass loudnorm, source frame rate kept, no intro card), measures each file (size, codec, fps against the source, duration, loudness, first frame, first caption, caption tiling, face inside the crop) and reviews the contact sheets and caption strips like an editor, fixing the spec and never the MP4, three rounds at most, before a fresh reviewer critiques the set once. Use at Step 5 of short-video-builder. Triggers on "render the shorts", "check the clips", "the camera judders", "captions flicker".
license: Apache-2.0
compatibility: Claude Code, Cursor, Codex CLI, Gemini CLI
metadata:
  version: "1.0"
allowed-tools: Read Write Bash(python3:*) Bash(ffmpeg:*) Bash(ffprobe:*)
---

# render-and-review

## 1. Render and measure

```bash
python3 scripts/pipeline.py <run>/clips.json --project <project>          # final quality
python3 scripts/pipeline.py <run>/clips.json --quick --only <id>           # fast preview of one clip
```

It refuses to start on spec errors or an unsigned transcript (exit 1, nothing rendered). Per clip it writes `export/<id>.mp4`, `export/<id>.json` (render facts and QA) and `review/<id>/`; then `export/qa.json`, `review/first-frames.png` and `posts.md`. Final quality can take longer than the clip itself on a small CPU; `--quick` previews are several times faster and never ship (crf 28, no sub-pixel pan).

What the render does, and why each choice is fixed:

| Stage | Choice | Why |
|-------|--------|-----|
| Trim | accurate input seek on the snapped span | the clip opens a breath before the hook, never on half a word |
| Reframe | Haar face detection every 0.4 s, profile and motion fallbacks; a dead zone of 30 % of the crop width; 1.6 s moving average; first 0.8 s anchored on the first face | long still holds and rare slow glides read as a calm camera; chasing every detection reads as nervous |
| Sub-pixel pan | crop x on a grid 4 times finer than the source pixel (source width scaled by 4 before the crop) | a slow glide at whole-pixel steps stair-steps after the upscale |
| Frame rate | the source rate, halved exactly only above 60 fps, VFR snapped to the nearest standard rate | resampling (50 to 30) drops frames unevenly: every pan judders |
| Captions | 3 words and 18 characters per group at most; active word by colour only; events tiled end to start; elisions merged; above the bottom 20 % | scaling the active word makes the line jump; a gap of one frame blinks |
| Lower third | name and role for the first seconds, under the captions, above the safe line | who speaks, without covering the face |
| Progress bar | 10 px at the bottom edge, accent colour, full at the last word | shows the viewer how much is left |
| End card | optional, dissolves in after the last word over the continuing picture and sound | a silent frozen card is dead air |
| Intro card | none, and no option for one | a card before the speaker is where viewers scroll away |
| Audio | 48 kHz, high-pass 80 Hz, light denoise, two-pass loudnorm to -14 LUFS and -1.5 dBTP by default, short fades | even level across clips and platforms, no click at the cut |

## 2. Read the QA first

`export/qa.json` lists every finding per clip. Errors block delivery:

| Code | Meaning | Fix in |
|------|---------|--------|
| `fps-mismatch` | output rate differs from the source | never re-time a file: render again with `pipeline.py` |
| `late-start` | first caption more than 1 s in | `start` in `clips.json` (snap is automatic; a long silence before the hook means the span is wrong) |
| `first-frame` | black or flat first frame | look for an edit or fade at the source in point; move `start` |
| `face-outside-crop` | detections outside the crop | `framing` in the clip |
| `caption-overlap` | two caption events at once | report it: a timing bug in `words.json` (overlapping words after an import) |
| `loudness`, `audio` | level off target, missing or wrong rate | source audio; `audio` block of the spec |
| `size`, `codec`, `duration` | file not what the plan says | report it: an engine bug, not a spec problem |
| `not-proofread` | drafted with `--allow-unproofread` | proofread, sign, render again |

Warnings to read and either fix or keep with a reason: `fast-pan`, `low-face-detection`, `face-near-edge`, `no-face-first-frame`, `upscaled-source`, `timing-estimated`, `font-fallback`, `caption-gap`, `true-peak`, `faststart`, `logo-skipped`.

## 3. Look

Follow [`../../../../shared/skills/reviewing-renders/SKILL.md`](../../../../shared/skills/reviewing-renders/SKILL.md) (its checklist R1 to R11 applies frame by frame) with these files:

1. `review/first-frames.png`: the first frame of every short at feed size. Each one must show the speaker, composed, with the first caption or a breath before it. This is the scroll stop.
2. `review/<id>/sheet.png` and `sheet-feed.png`: first frame, five evenly spaced frames, last frame. Face in frame and not cut by the edge; captions readable at feed size and never over the eyes or mouth for long; lower third readable then gone; end card text whole, brand colours right.
3. `review/<id>/captions-strip.jpg`: the caption band at 10 fps over the first words. The line stays put, only the colour moves; no split word, no blink, no double line; every word matches the proofread transcript.
4. When something looks off, open `review/<id>/frames/frame-NN.jpg` at full size, or extract the exact moment: `ffmpeg -ss <t> -i export/<id>.mp4 -frames:v 1 /tmp/check.jpg`.

Score with [`../../assets/review-rubric.md`](../../assets/review-rubric.md) and write `render-review.md` (one block per round: clip, check, verdict, where, fix in the source).

## 4. Fix the source, never the file

Every fix lands in `clips.json` (span, hook, framing, style, end card), `corrections.json` (then `apply` and `sign`), or the config. Re-run `pipeline.py --only <id>` for the clips that changed. Never trim, re-encode, crop or overlay an exported MP4 by hand: the next render would undo it, and a re-encode is exactly how a frame-rate change sneaks in. Three rounds at most; with FAILs left after the third, deliver with a "Known issues" section at the top of the report.

## 5. Fresh reviewer

Then [`../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md`](../../../../shared/skills/reviewing-with-fresh-eyes/SKILL.md) with the packet: the brief, `digest.md`, `clips.json`, `export/qa.json`, `render-review.md`, `review/first-frames.png`, each clip's sheet and caption strip, the rubric. It may say an excerpt does not stand alone, a hook is weak, or a better moment exists in the digest; one revision, then deliver.

## Without vision

QA still gates. The founder gets `review/first-frames.png`, the sheets and caption strips with the rubric as questions ("Does each short open on the speaker? Is any caption word wrong? Is the face cut at any point?"), and the report says "Visual review: founder".
