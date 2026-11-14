# references/

Pointers for the engine choices of short-video-builder, and where to read more.

| Topic | Source | Used by |
|-------|--------|---------|
| faster-whisper (CTranslate2 Whisper, word timestamps, VAD filter) | https://github.com/SYSTRAN/faster-whisper | `scripts/transcribe.py` |
| whisper.cpp (C/C++ Whisper, ggml models, `-ml 1 -sow -oj` for one word per segment in JSON) | https://github.com/ggml-org/whisper.cpp | `scripts/transcribe.py` |
| openai-whisper (`whisper` command, `--word_timestamps True`) | https://github.com/openai/whisper | `scripts/transcribe.py` |
| WebVTT format, inline cue timestamps | https://www.w3.org/TR/webvtt1/ | `scripts/transcribe.py` |
| OpenCV Haar cascades (face and profile detectors shipped with opencv-python-headless) | https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html | `scripts/track.py`, `scripts/qa.py` |
| ffmpeg filters: crop, sendcmd, drawbox, ass, loudnorm, ebur128 | https://ffmpeg.org/ffmpeg-filters.html | `scripts/render.py`, `scripts/qa.py` |
| loudnorm two-pass (measured values, linear mode) | https://ffmpeg.org/ffmpeg-filters.html#loudnorm | `scripts/render.py` |
| EBU R128 loudness recommendation | https://tech.ebu.ch/publications/r128 | `scripts/render.py` (method), `scripts/qa.py` (measure) |
| A streaming platform's loudness normalisation level (-14 LUFS integrated) | https://support.spotify.com/us/artists/article/loudness-normalization/ | default `audio.target_lufs` (configurable) |
| ASS subtitle format as read by libass (styles, `\1c`, `\fad`, `\p1` drawings) | https://github.com/libass/libass and https://aegisub.org/docs/latest/ass_tags/ | `scripts/captions.py` |
| Safe zones and visual checklist for 9:16 frames | [`../../../shared/skills/reviewing-renders/SKILL.md`](../../../shared/skills/reviewing-renders/SKILL.md) (check R2: top 14 %, bottom 20 %) | `scripts/captions.py` placement, render review |

## Engine notes

- **Frame rate.** `scripts/common.py` `output_fps()` keeps the source rate as a rational (`25/1`, `30000/1001`), halves it exactly above 60 fps, and snaps variable-frame-rate phone files to the nearest standard rate of their average. Any other conversion drops or repeats frames on an uneven cadence, which only shows when the crop pans: the reason the judder looks random from one talk to the next. `scripts/qa.py --check FILE --source SRC` catches it on any file.
- **Crop path.** `crop` takes an integer x; the path is a float. render.py scales the source width by `PAN_K` (4) before the crop and writes x on that finer grid in `crop.cmd`, one command per output frame, half a frame early so rounding never shifts a value to the next frame. The drawbox width of the progress bar is driven the same way (`bar.cmd`): drawbox does not re-evaluate a time expression for its width.
- **Captions.** The ASS Dialogue line has exactly nine fields; an extra comma before the text prints a comma in front of every caption. The active word is coloured with an inline `\1c&HBBGGRR&` (ASS colours are byte-reversed against `#RRGGBB`).
- **End card.** A full-frame ASS drawing with a fade-in, on top of the moving source; the audio keeps running and fades over the last half second.
- **Fixture.** `scripts/fixture.py` draws a speaker the Haar detector finds and moves it along a known path at 25 fps, with a quiet two-tone sound; tests use it instead of footage of a real person.

## Prior art

The dead-zone camera, the per-frame crop commands, the caption rules and the source-fps rule come from work on real event pitches; the clip-choice method (objective shaping, digest of timestamped sentences, word-boundary snapping, overlap check between ideas) comes from a shortform pipeline that cuts one long video into several shorts.
