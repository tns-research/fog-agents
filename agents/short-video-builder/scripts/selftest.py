#!/usr/bin/env python3
"""selftest.py: offline regression test of the short-video engine (about a minute on one CPU).

    python3 scripts/selftest.py [--keep DIR]

No transcription model, no GPU, no network. It builds a synthetic 25 fps talk
with scripts/fixture.py and the inputs of examples/synthetic-talk/, then checks:

 1. Transcript importers: SRT, WebVTT (cue-level and inline word timestamps),
    Whisper JSON with segments, whisper.cpp JSON; words.json matches
    assets/words.schema.json.
 2. Spec checks: the example fails with hook-mismatch before proofreading (its
    hook quotes the corrected brand name); a broken spec raises intro-card,
    schema, duplicate-id, span-order, out-of-source, too-short, cta-empty and a
    copy BLOCK, without crashing.
 3. Proofread gate: sign refuses before every page is printed; the pipeline
    renders nothing before the signature; apply fixes "raisin hand" and
    "swan base"; a transcript edited after signing is refused again.
 4. Render (quick encode): both clips pass QA at 1080x1920, 25 fps like the
    source, -14 LUFS within 1 LU, first caption within 0.3 s, the face inside
    the crop, the end card only on the clip that asks for it, corrected words
    in the captions, review frames, caption strip and contact sheets written.
 5. Judder guard: the same short re-encoded at 30 fps fails QA with fps-mismatch.

Exit 0 when everything holds, 1 otherwise. Outputs go to a temporary folder
(or --keep DIR); the repo is never written.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
sys.path.insert(0, str(HERE))
import transcribe  # noqa: E402
from common import SHARED  # noqa: E402

sys.path.insert(0, str(SHARED / "scripts"))
from validate_json import validate  # noqa: E402

FAILS = []


def ok(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)
        print(f"FAIL {msg}")


def run(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True)
    if "Traceback" in r.stderr or "Traceback" in r.stdout:
        print(r.stdout[-1500:], r.stderr[-2500:])
        FAILS.append(f"crash in {Path(args[0]).name}")
    return r


def s(name: str) -> Path:
    return HERE / name


def test_importers() -> None:
    vtt_inline = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n"
                  "We<00:00:01.400><c> open</c><00:00:01.900><c> with</c><00:00:02.300><c> a story.</c>\n")
    w, timing = transcribe.parse_vtt(vtt_inline)
    ok([x["word"] for x in w] == ["We", "open", "with", "a", "story."] and timing == "word", f"vtt inline: {w} {timing}")
    ok(abs(w[1]["start"] - 1.4) < 0.01, "vtt inline: 'open' should start at 1.4 s")
    vtt = "WEBVTT\n\nNOTE test\n\n1\n00:01.000 --> 00:02.500 align:start\n<i>Start with</i> the problem.\n"
    w, timing = transcribe.parse_vtt(vtt)
    ok(len(w) == 4 and timing == "estimated" and w[0]["start"] == 1.0 and abs(w[-1]["end"] - 2.5) < 0.01, f"vtt cues: {w}")
    seg = {"language": "fr", "segments": [{"start": 0, "end": 2, "text": "x", "words": [
        {"word": " Levez", "start": 0.1, "end": 0.4, "probability": 0.91}, {"word": " la", "start": 0.4, "end": 0.5, "probability": 0.4}]}]}
    w, timing, meta = transcribe.parse_json_transcript(seg)
    ok(len(w) == 2 and w[1]["prob"] == 0.4 and timing == "word" and meta.get("language") == "fr", f"whisper json: {w}")
    cpp = {"result": {"language": "en"}, "transcription": [
        {"offsets": {"from": 0, "to": 320}, "text": " Start"}, {"offsets": {"from": 320, "to": 500}, "text": " here."},
        {"offsets": {"from": 500, "to": 900}, "text": " [BLANK_AUDIO]"}]}
    w, timing, meta = transcribe.parse_json_transcript(cpp)
    ok([x["word"] for x in w] == ["Start", "here."] and timing == "word" and abs(w[1]["start"] - 0.32) < 0.01, f"whisper.cpp json: {w}")
    print("importers: srt, vtt (cues and inline), whisper json, whisper.cpp json checked")


def bad_spec(run_dir: Path) -> None:
    spec = json.loads((run_dir / "clips.json").read_text(encoding="utf-8"))
    good = spec["clips"][0]
    spec["intro_card"] = {"text": "THE PROMISE"}
    spec["clips"] = [
        dict(good),
        dict(good, title="A game-changing pitch " + chr(0x2014) + " in one move"),           # duplicate id + copy BLOCK
        dict(good, id="backwards", start=9.0, end=4.0),
        dict(good, id="past-the-end", start=20.0, end=40.0),
        dict(good, id="too-short", start=0.4, end=3.1),
        dict(good, id="empty-card", cta={"enabled": True, "lines": [], "url": ""}),
    ]
    p = run_dir / "bad-clips.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    r = run(s("clipspec.py"), p, "--plan", run_dir / "work" / "bad-plan.json")
    ok(r.returncode == 1, f"bad spec must exit 1 (got {r.returncode})")
    ok("intro-card" in r.stdout and "schema" in r.stdout, "bad spec: intro-card and schema errors expected first")
    del spec["intro_card"]
    p.write_text(json.dumps(spec), encoding="utf-8")
    r = run(s("clipspec.py"), p, "--plan", run_dir / "work" / "bad-plan.json")
    plan = json.loads((run_dir / "work" / "bad-plan.json").read_text(encoding="utf-8"))
    codes = {(e.get("clip"), e["code"]) for e in plan["errors"]}
    for want in [("investors-fund-problems", "duplicate-id"), ("backwards", "span-order"), ("past-the-end", "out-of-source"),
                 ("too-short", "too-short"), ("empty-card", "cta-empty"), ("investors-fund-problems", "copy:em-dash"),
                 ("investors-fund-problems", "copy:buzzword")]:
        ok(want in codes, f"bad spec: expected {want}, got {sorted(codes)}")
    print(f"bad spec: {len(plan['errors'])} errors, {sorted(c for _, c in codes)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="Keep outputs in this folder")
    args = ap.parse_args()
    t0 = time.time()
    base = Path(args.keep).resolve() if args.keep else Path(tempfile.mkdtemp(prefix="svb-selftest-"))
    R = base / "run"

    test_importers()
    r = run(s("fixture.py"), R, "--example")
    ok(r.returncode == 0 and (R / "talk.mp4").exists(), f"fixture: {r.stderr.strip()[-300:]}")
    if FAILS:
        return 1
    r = run(s("transcribe.py"), R / "talk.mp4", "--transcript", R / "transcript.srt", "--out", R / "words.json", "--language", "en")
    ok(r.returncode == 0, f"transcribe import: {r.stderr.strip()}")
    words = json.loads((R / "words.json").read_text(encoding="utf-8"))
    schema = json.loads((AGENT / "assets" / "words.schema.json").read_text(encoding="utf-8"))
    ok(not validate(words, schema), f"words.json schema: {validate(words, schema)[:3]}")
    r = run(s("transcribe.py"), R / "talk.mp4", "--engine", "import", "--out", R / "x.json")
    ok(r.returncode == 2, "transcribe --engine import without --transcript must exit 2")
    r = run(s("digest.py"), R / "words.json")
    ok(r.returncode == 0 and "raisin hand" in (R / "digest.md").read_text(encoding="utf-8"), "digest")

    # spec before proofreading: the hook quotes "swanbase", the raw transcript says "swan base"
    r = run(s("clipspec.py"), R / "clips.json")
    ok(r.returncode == 1 and "hook-mismatch" in r.stdout and "demo-comes-last" in r.stdout, "raw transcript must give hook-mismatch on demo-comes-last")
    bad_spec(R)

    # proofread gate
    r = run(s("proofread.py"), "sign", R / "words.json")
    ok(r.returncode == 1, "sign must refuse before the transcript was printed")
    r = run(s("proofread.py"), "dump", R / "words.json", "--all")
    ok(r.returncode == 0 and "all 70 words printed" in r.stdout, "dump --all")
    r = run(s("proofread.py"), "apply", R / "words.json", R / "corrections.json")
    ok(r.returncode == 0 and "2 span(s)" in r.stdout, f"apply: {r.stdout} {r.stderr}")
    r = run(s("proofread.py"), "apply", R / "words.json", R / "corrections.json")
    ok(r.returncode == 0 and "70 words" in r.stdout, "apply must be idempotent (re-applied from words.raw.json)")
    r = run(s("pipeline.py"), R / "clips.json", "--quick")
    ok(r.returncode == 1 and "not proofread" in r.stdout and not (R / "export").exists(), "pipeline must render nothing before the signature")
    r = run(s("proofread.py"), "sign", R / "words.json")
    ok(r.returncode == 0, f"sign: {r.stderr}")
    ok(run(s("proofread.py"), "status", R / "words.json").returncode == 0, "status after sign")

    # render
    r = run(s("pipeline.py"), R / "clips.json", "--quick")
    print("\n".join(line for line in r.stdout.splitlines() if line.startswith(("clip ", "pipeline")) and not line.startswith("clip    ")))
    ok(r.returncode == 0, f"pipeline must pass (exit {r.returncode}): {r.stdout[-800:]} {r.stderr[-800:]}")
    qa = json.loads((R / "export" / "qa.json").read_text(encoding="utf-8"))
    ok(qa["fps"] == "25/1", f"output fps {qa['fps']}, source is 25/1")
    for c in qa["clips"]:
        entry = json.loads((R / "export" / f"{c['id']}.json").read_text(encoding="utf-8"))
        q, rend = entry["qa"], entry["render"]
        ok(q["status"] == "pass", f"{c['id']}: qa {q['errors']}")
        ok(q["probe"]["fps"] == "25/1" and (q["probe"]["width"], q["probe"]["height"]) == (1080, 1920), f"{c['id']}: probe {q['probe']}")
        ok(abs((q["loudness"]["integrated"] or 0) + 14) <= 1.0, f"{c['id']}: loudness {q['loudness']}")
        ok(rend["captions"]["first_caption"] is not None and rend["captions"]["first_caption"] <= 0.3, f"{c['id']}: first caption {rend['captions']['first_caption']}")
        ok(rend["captions"]["overlaps"] == 0 and rend["captions"]["micro_gaps"] == 0, f"{c['id']}: caption tiling")
        ok((rend["track"]["face_inside_ratio"] or 0) >= 0.9 and (rend["track"]["face_ratio"] or 0) >= 0.3, f"{c['id']}: tracking {rend['track']}")
        ok(rend["track"]["max_step_px"] <= 8.0, f"{c['id']}: pan step {rend['track']['max_step_px']} px/frame")
        ok(q["first_frame"]["std"] > 6, f"{c['id']}: first frame flat {q['first_frame']}")
        rv = entry["review"]
        ok(len(rv["frames"]) == 7 and rv["captions_strip"] and all(v["exit"] == 0 for v in rv["sheets"].values()), f"{c['id']}: review files {rv}")
    subs1 = (R / "work" / "investors-fund-problems" / "subs.ass").read_text(encoding="utf-8")
    subs2 = (R / "work" / "demo-comes-last" / "subs.ass").read_text(encoding="utf-8")
    ok("RAISIN" not in subs1 and "RAISE" in subs1, "corrected words must reach the captions (raise your hand)")
    ok("SWANBASE" in subs2 and "Dialogue: 5," in subs2 and "Dialogue: 5," not in subs1, "end card only on demo-comes-last, brand spelled right")
    ok((R / "review" / "first-frames.png").exists() and (R / "posts.md").exists(), "first-frames board and posts.md")

    # judder guard: a 30 fps re-encode of a 25 fps short must fail
    dec = R / "decimated-30fps.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(R / "export" / "investors-fund-problems.mp4"), "-r", "30",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "copy", str(dec)], capture_output=True)
    r = run(s("qa.py"), "--check", dec, "--source", R / "talk.mp4")
    ok(r.returncode == 1 and "fps-mismatch" in r.stdout, "a 30 fps re-encode must fail with fps-mismatch")

    # a transcript edited after the signature is refused
    words = json.loads((R / "words.json").read_text(encoding="utf-8"))
    words["words"][3]["word"] = "the."
    (R / "words.json").write_text(json.dumps(words), encoding="utf-8")
    ok(run(s("proofread.py"), "status", R / "words.json").returncode == 1, "status must fail once words.json changed")
    r = run(s("pipeline.py"), R / "clips.json", "--quick", "--only", "investors-fund-problems")
    ok(r.returncode == 1, "pipeline must refuse a transcript changed after the signature")

    secs = time.time() - t0
    print(f"selftest: {'PASS' if not FAILS else 'FAIL'} in {secs:.0f} s, {len(FAILS)} failure(s) (outputs in {base})")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
