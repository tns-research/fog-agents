#!/usr/bin/env python3
"""selftest.py: regression test of the carousel engine.

  python3 scripts/selftest.py [--keep DIR] [--only stills|video]

1. Runs the stress deck (examples/stress/deck.json) through the pipeline and
   checks that every failure it was built to trigger appears in qa.json with
   the expected code on the expected slide, and that nothing crashed.
2. Runs the reference deck (examples/swanbase-seed-deck-20261010) and checks
   that it passes with 0 errors and produces the expected files.
3. Video (scripts/animate.py --quick --fps 15, under a minute on one CPU): the
   first three slides of the reference deck as a 9:16 MP4; checks exit 0, QA
   pass, 1080x1920 at 15 fps, the frame count of the timeline, a non-black first frame; and that
   the stress deck is refused (exit 1) before anything is rendered.
4. Spend gate (offline, no key used): scripts/generate_image.py with a fake
   fal key and no --confirm-spend sends nothing and exits 6.

Exit 0 when all hold, 1 otherwise. Outputs go to a temporary folder (or
--keep DIR) so the repo is not touched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
PIPE = AGENT / "scripts" / "pipeline.py"
ANIMATE = AGENT / "scripts" / "animate.py"
GENERATE_IMAGE = AGENT / "scripts" / "generate_image.py"

# (slide index, level, code) the stress deck must produce.
EXPECTED = [
    (1, "errors", "text-too-long"),
    (2, "errors", "build:schema"),
    (2, "errors", "empty-block"),
    (3, "errors", "build:missing-asset"),
    (3, "errors", "missing-asset"),
    (4, "errors", "build:chart-highlight"),
    (4, "errors", "build:unsourced"),
    (5, "errors", "build:unsourced"),
    (5, "errors", "build:schema"),
    (6, "errors", "build:dash"),
    (6, "errors", "build:accent-not-found"),
    (7, "warnings", "build:unknown-layout"),
    (8, "warnings", "build:over-budget"),
    (9, "warnings", "build:over-budget"),
    (10, "errors", "build:unknown-block"),
    (14, "errors", "text-too-long"),
]


def run(deck: Path, out: Path) -> dict:
    r = subprocess.run([sys.executable, str(PIPE), str(deck), "--out", str(out)], capture_output=True, text=True)
    if "Traceback" in r.stderr or "Traceback" in r.stdout:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit("selftest: the pipeline crashed")
    return json.loads((out / "export" / "qa.json").read_text(encoding="utf-8"))


def video(base: Path) -> bool:
    ok = True
    out = base / "video"
    deck = AGENT / "examples" / "swanbase-seed-deck-20261010" / "deck.json"
    # 15 fps halves the capture for the smoke test; production videos use the 30 fps default.
    r = subprocess.run([sys.executable, str(ANIMATE), str(deck), "--out", str(out), "--quick", "--aspect", "9:16", "--fps", "15"],
                       capture_output=True, text=True)
    if "Traceback" in r.stderr or r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:])
        print(f"FAIL video: animate.py exited {r.returncode}")
        return False
    rep = json.loads((out / "export" / "video-9x16.json").read_text(encoding="utf-8"))
    p = rep["qa"]["probe"]
    checks = [
        (rep["qa"]["status"] == "pass", f"qa {rep['qa']['status']}: {rep['qa']['errors']}"),
        ((p.get("width"), p.get("height")) == (1080, 1920), f"size {p.get('width')}x{p.get('height')}"),
        (abs(p.get("fps", 0) - 15) < 0.01, f"fps {p.get('fps')}"),
        (abs(p.get("frames", 0) - rep["frames"]) <= 1, f"frames {p.get('frames')} vs timeline {rep['frames']}"),
        (len(rep["slides"]) == 3, f"{len(rep['slides'])} slides, expected 3"),
        (p.get("first_frame", {}).get("mean", 0) > 40, f"first frame {p.get('first_frame')}"),
        ((out / "export" / "video-9x16-frames.jpg").exists(), "no frames sheet"),
        (rep["rendered_frames"] < rep["frames"], "no still frame was reused"),
    ]
    for good, msg in checks:
        if not good:
            ok = False
            print(f"FAIL video: {msg}")
    r = subprocess.run([sys.executable, str(ANIMATE), str(AGENT / "examples" / "stress" / "deck.json"),
                        "--out", str(base / "video-stress"), "--quick"], capture_output=True, text=True)
    if r.returncode != 1 or (base / "video-stress" / "export" / "video-4x5.mp4").exists():
        ok = False
        print(f"FAIL video: the stress deck must be refused with exit 1 and no MP4 (exit {r.returncode})")
    print(f"video: {'ok' if ok else 'FAIL'}, {rep['duration']} s, {rep['frames']} frames, {rep['rendered_frames']} rendered, "
          f"{rep['seconds']} s capture; stress deck refused")
    return ok


def spend_gate(base: Path) -> bool:
    """generate_image.py must refuse a paid call without --confirm-spend, before any request."""
    env = {k: v for k, v in os.environ.items() if k != "FOG_ALLOW_SPEND"}
    env["FAL_KEY"] = "selftest-not-a-key"
    out = base / "gate" / "slide-01.jpg"
    r = subprocess.run([sys.executable, str(GENERATE_IMAGE), "--prompt", "selftest", "--out", str(out)],
                       capture_output=True, text=True, env=env, timeout=60)
    ok = r.returncode == 6 and "--confirm-spend" in r.stderr and "submitted" not in r.stderr and not out.exists()
    print(f"spend gate: {'ok' if ok else 'FAIL'} (generate_image exit {r.returncode} without --confirm-spend)")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="Keep outputs in this folder")
    ap.add_argument("--only", choices=["stills", "video"], help="Run one part only")
    args = ap.parse_args()
    base = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="carousel-selftest-"))
    ok = spend_gate(base)
    if args.only != "stills":
        ok = video(base) and ok
    if args.only == "video":
        print(f"selftest: {'PASS' if ok else 'FAIL'} (outputs in {base})")
        return 0 if ok else 1

    qa = run(AGENT / "examples" / "stress" / "deck.json", base / "stress")
    for idx, level, code in EXPECTED:
        s = qa["slides"][idx - 1]
        if not any(e["code"] == code for e in s[level]):
            ok = False
            print(f"FAIL stress slide {idx}: expected {level[:-1]} {code}, got {[e['code'] for e in s[level]]}")
    if not any(e["code"] == "build:too-many-slides" for e in qa["global"]["errors"]):
        ok = False
        print("FAIL stress: expected global error build:too-many-slides")
    if qa["status"] != "fail":
        ok = False
        print("FAIL stress: qa status should be fail")
    print(f"stress: {qa['summary']['errors']} errors, {qa['summary']['warnings']} warnings, {len(EXPECTED)} expected findings checked")

    qa = run(AGENT / "examples" / "swanbase-seed-deck-20261010" / "deck.json", base / "swanbase")
    if qa["status"] != "pass":
        ok = False
        print(f"FAIL swanbase: {qa['summary']}")
    files = ["export/carousel.pdf", "export/contact-sheet.jpg", "captions.md"] + [f"export/slide-{i:02d}.jpg" for i in range(1, qa["summary"]["slides"] + 1)]
    for f in files:
        if not (base / "swanbase" / f).exists():
            ok = False
            print(f"FAIL swanbase: missing {f}")
    print(f"swanbase: {qa['status']}, {qa['summary']['errors']} errors, {qa['summary']['warnings']} warnings")
    print(f"selftest: {'PASS' if ok else 'FAIL'} (outputs in {base})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
