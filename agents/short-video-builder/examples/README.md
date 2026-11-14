# examples/

Inputs of reproducible runs. Videos are never committed: the fixture video is generated in a few seconds, the shorts rebuild with one command.

| Example | What it shows | Command |
|---------|---------------|---------|
| [`synthetic-talk/`](synthetic-talk/) | A fictional founder talk (drawn speaker who walks across the stage, 25 fps, quiet sound) with an imported SRT that holds two mishearings, the `corrections.json` that fixes them, and a two-clip `clips.json` (one with an end card). `preview.jpg` is the contact sheet of the second short: tracking during the walk, lower third, karaoke captions, progress bar, end card. | see below |

```bash
# from agents/short-video-builder/
python3 scripts/fixture.py /tmp/svb-demo --example
python3 scripts/transcribe.py /tmp/svb-demo/talk.mp4 --transcript /tmp/svb-demo/transcript.srt --out /tmp/svb-demo/words.json --language en
python3 scripts/digest.py /tmp/svb-demo/words.json
python3 scripts/proofread.py dump /tmp/svb-demo/words.json --all
python3 scripts/proofread.py apply /tmp/svb-demo/words.json /tmp/svb-demo/corrections.json
python3 scripts/proofread.py sign /tmp/svb-demo/words.json
python3 scripts/pipeline.py /tmp/svb-demo/clips.json
```

`scripts/selftest.py` runs the same chain (with quick encodes) plus the failure cases.

## Adding an example

A folder `<brand>-<topic>-<YYYYMMDD>/` with `clips.json`, the transcript file, `corrections.json` and one `preview.jpg` (a contact sheet, 1200 px wide, under 150 KB). Commit inputs and the preview only. A real talk is used only with the speaker's consent, from a public recording, and its video stays out of git. Examples are in English; the example brand of the stack is swanbase.
