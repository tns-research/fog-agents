# scripts/

The short-video engine. The model writes `clips.json` and `corrections.json`; these scripts transcribe, check, render, measure and lay out the review. Every script runs alone (`--help`), reads and writes files only, and calls no network service.

```bash
pip install -r scripts/requirements.txt      # opencv-python-headless, numpy, Pillow
# plus ffmpeg and ffprobe with libass on the PATH (apt install ffmpeg, brew install ffmpeg)
# optional local transcription: pip install faster-whisper (or whisper.cpp, or openai-whisper)
```

| Script | Does | Writes |
|--------|------|--------|
| `transcribe.py` | Word-level transcript: faster-whisper, whisper.cpp or openai-whisper on the machine, or import of an SRT, VTT (cue or inline word stamps) or JSON transcript. `--prompt` primes names. | `words.json` |
| `digest.py` | Sentence timeline with word indexes, times and pause markers, for choosing clips. | `digest.md` |
| `proofread.py` | `dump` (pages with a check-first list: numbers, names, unsure words; records what was read), `apply` (span corrections from the raw snapshot, timing redistributed), `sign` (hash of the corrected transcript), `status`. | `words.raw.json`, `proofread-progress.json`, `proofread.json` |
| `clipspec.py` | Schema (`assets/clips.schema.json` through `shared/scripts/validate_json.py`), intro-card ban, spans snapped to words and checked against the source, lengths, verbatim hook, sentence edges, overlaps, copy through the shared writing gate; brand.json mapped into the style. | `work/plan.json` |
| `track.py` | Crop path: Haar face (then profile, then motion) every 0.4 s, dead zone, 1.6 s smoothing, first-face seed; one x per output frame; telemetry. | `work/<id>/track.json` |
| `captions.py` | ASS file: karaoke groups (colour-only highlight, contiguous tiling, merged elisions), lower third, end card. | `work/<id>/subs.ass` |
| `render.py` | One clip: track, captions, per-frame `crop.cmd` and `bar.cmd`, ffmpeg filter graph (sub-pixel pan, progress bar, libass, optional logo), two-pass loudnorm, source frame rate. | `export/<id>.mp4`, `work/<id>/` |
| `qa.py` | Measures an MP4: size, codec, fps against the source, duration, frames, audio rate, loudness and true peak (ebur128), faststart, first frame, first caption, caption tiling, tracking telemetry, face on frame one. Builds review frames, the caption strip and contact sheets (shared `contact_sheet.py`). `--check FILE --source SRC` alone. | `review/<id>/` |
| `pipeline.py` | All of the above for every clip, behind the spec check and the proofread gate. `--quick` previews, `--only` some clips. | `export/qa.json`, `review/first-frames.png`, `posts.md` |
| `fixture.py` | A synthetic 25 fps talk (drawn speaker on a known path, quiet sound) and, with `--example`, the example inputs. | `talk.mp4` |
| `selftest.py` | The regression test below. | temporary folder |
| `common.py` | Probing, output frame rate, time parsing, hashing, exit codes (module). | n/a |

## Tests

```bash
# from the repo root: offline, no transcription model, no GPU, about a minute on one CPU
python3 agents/short-video-builder/scripts/selftest.py
```

It generates the fixture, imports the SRT, checks the importers (SRT, VTT cues and inline stamps, Whisper JSON, whisper.cpp JSON) and the `words.json` schema, the spec failures (hook mismatch before proofreading, intro card, schema, duplicate id, span order, out of source, too short, empty end card, copy BLOCKs), the proofread gate (`sign` refuses before every page is printed, `apply` is idempotent, no signature means nothing rendered, a transcript changed after signing is refused), renders both example clips with quick encodes and checks 1080x1920, 25 fps like the source, -14 LUFS within 1 LU, first caption within 0.3 s, caption tiling, face inside the crop, pan speed, the end card only where asked, the corrected words in the captions, the review files; then that a 30 fps re-encode fails with `fps-mismatch`. Exit 0 when all hold.

## Exit codes

All scripts: 0 done and every check passed; 1 a check failed (spec errors, QA errors, proofread gate not satisfied, a correction that does not apply); 2 fatal (unreadable input, ffmpeg, ffprobe, OpenCV or Pillow missing, ffmpeg failure); 3, `transcribe.py` only, no local transcription engine and no `--transcript` (capability unavailable: ask the founder for a transcript file).

## Notes

- Paths in `clips.json` are relative to the spec file. Run folders use `work/` and `export/`, never `build/` (ignored by git in this repo).
- No fixed frame rate anywhere: the output rate always comes from `common.output_fps()` on the source.
- Fonts: the caption font must be installed (`fc-list : family`); otherwise DejaVu Sans is used and QA warns `font-fallback`.
