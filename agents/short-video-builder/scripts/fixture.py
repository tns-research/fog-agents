#!/usr/bin/env python3
"""fixture.py: a synthetic landscape talk for tests and demos, made locally.

    python3 scripts/fixture.py OUT_DIR [--seconds 27] [--fps 25] [--example]

Writes OUT_DIR/talk.mp4: 1280x720 at 25 fps (deliberately not 30, so a render
that forces 30 fps fails the QA), a drawn speaker (face and shoulders, found by
OpenCV's face detector) who holds on the left, walks right, holds, then comes
back to the centre, with a slight sway that must not move the crop; a quiet
two-tone voice-like sound around -30 LUFS that the loudness pass must raise.
Nothing is downloaded and no person is filmed.

--example also copies examples/synthetic-talk/ (clips.json, transcript.srt,
corrections.json) into OUT_DIR, ready for:

    python3 scripts/transcribe.py OUT_DIR/talk.mp4 --transcript OUT_DIR/transcript.srt --out OUT_DIR/words.json
    python3 scripts/proofread.py dump OUT_DIR/words.json --all
    python3 scripts/proofread.py apply OUT_DIR/words.json OUT_DIR/corrections.json
    python3 scripts/proofread.py sign OUT_DIR/words.json
    python3 scripts/pipeline.py OUT_DIR/clips.json

The speaker path (centre x, source pixels) is in SPEAKER_PATH; tests read it.

Exit codes: 0 written; 2 ffmpeg or Pillow missing, or ffmpeg failed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import AGENT, die, need_binary  # noqa: E402

W, H = 1280, 720
DRAW_W, DRAW_H = 300, 820   # the speaker is drawn at this size, then scaled by SPK_SCALE
SPK_SCALE = 0.7              # face about 126 px wide on a 1280 px frame, a usual stage framing
SPK_W, SPK_H = int(DRAW_W * SPK_SCALE), int(DRAW_H * SPK_SCALE)
# (time s, centre x px): holds, walks right at about 60 px/s, holds, comes back to the centre.
SPEAKER_PATH = [(0.0, 380), (5.0, 380), (13.0, 860), (17.0, 860), (21.0, 640), (999.0, 640)]
SWAY_PX = 8   # head sway amplitude, well inside the tracker's dead zone


def draw_assets(out: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        die("Pillow is needed: pip install Pillow")
    bg = Image.new("RGB", (W, H), (34, 38, 52))
    d = ImageDraw.Draw(bg)
    for y in range(H):  # vertical gradient, a lit stage
        c = int(34 + 30 * (1 - y / H))
        d.line([(0, y), (W, y)], fill=(c, c + 4, c + 18))
    d.rectangle([0, int(H * 0.78), W, H], fill=(52, 44, 40))           # floor
    d.rectangle([60, 30, 330, 140], fill=(64, 72, 98))                   # screen on the wall, above head height
    d.rectangle([980, 90, 1200, 300], fill=(70, 60, 80))                 # banner
    bg.filter(ImageFilter.GaussianBlur(1)).save(out / "stage.png")

    spk = Image.new("RGBA", (DRAW_W, DRAW_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(spk)
    d.rounded_rectangle([10, 300, DRAW_W - 10, DRAW_H + 60], radius=70, fill=(30, 52, 92, 255))  # shoulders
    d.rectangle([118, 250, 182, 320], fill=(200, 156, 128, 255))                                  # neck
    fx, fy, fw, fh = 60, 40, 180, 234                                                             # face box
    d.ellipse([fx, fy, fx + fw, fy + fh], fill=(214, 170, 140, 255))
    d.chord([fx, fy - 26, fx + fw, fy + 92], 180, 360, fill=(50, 35, 25, 255))                  # hair
    ey, r = fy + int(fh * 0.40), int(fw * 0.075)
    for ex in (fx + int(fw * 0.30), fx + int(fw * 0.70)):
        d.rounded_rectangle([ex - int(r * 1.9), ey - int(r * 2.4), ex + int(r * 1.9), ey - int(r * 1.6)], radius=4, fill=(60, 40, 30, 255))
        d.ellipse([ex - int(r * 1.6), ey - r, ex + int(r * 1.6), ey + r], fill=(245, 245, 245, 255))
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(40, 30, 25, 255))
    cx = fx + fw // 2
    d.polygon([(cx, ey + r), (cx - int(r * 1.2), fy + int(fh * 0.62)), (cx + int(r * 1.2), fy + int(fh * 0.62))], fill=(190, 140, 115, 255))
    d.ellipse([cx - int(fw * 0.17), fy + int(fh * 0.71), cx + int(fw * 0.17), fy + int(fh * 0.79)], fill=(120, 50, 50, 255))
    spk = spk.resize((SPK_W, SPK_H), Image.LANCZOS)
    spk.filter(ImageFilter.GaussianBlur(1.0)).save(out / "speaker.png")


def x_expr() -> str:
    """ffmpeg overlay x(t): piecewise-linear centre from SPEAKER_PATH, plus sway, minus half the width."""
    expr = str(SPEAKER_PATH[-1][1])
    for (t0, x0), (t1, x1) in reversed(list(zip(SPEAKER_PATH, SPEAKER_PATH[1:]))):
        seg = f"{x0}+({x1}-{x0})*(t-{t0})/({t1}-{t0})" if x1 != x0 else f"{x0}"
        expr = f"if(lt(t,{t1}),{seg},{expr})"
    return f"({expr})+{SWAY_PX}*sin(2*PI*0.5*t)-{SPK_W // 2}"


def make(out: Path, seconds: float, fps: int) -> Path:
    need_binary("ffmpeg")
    out.mkdir(parents=True, exist_ok=True)
    draw_assets(out)
    video = out / "talk.mp4"
    voice = "0.05*sin(2*PI*180*t)*(0.55+0.45*sin(2*PI*3.3*t))+0.02*sin(2*PI*360*t)*(0.5+0.5*sin(2*PI*2.1*t))"
    fc = (f"[0:v]loop=loop=-1:size=1:start=0,fps={fps},trim=duration={seconds}[bg];"
          f"[1:v]loop=loop=-1:size=1:start=0,fps={fps},trim=duration={seconds},format=rgba[sp];"
          f"[bg][sp]overlay=x='{x_expr()}':y={H - SPK_H}:eval=frame:shortest=1,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(out / "stage.png"), "-i", str(out / "speaker.png"),
           "-f", "lavfi", "-i", f"aevalsrc='{voice}':s=48000:d={seconds}",
           "-filter_complex", fc, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-t", str(seconds),
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-g", str(fps * 2),
           "-c:a", "aac", "-b:a", "96k", str(video)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"ffmpeg failed: {r.stderr.strip()[-400:]}")
    for f in ("stage.png", "speaker.png"):
        (out / f).unlink()
    return video


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="Output folder")
    ap.add_argument("--seconds", type=float, default=27.0)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--example", action="store_true", help="Also copy examples/synthetic-talk/ inputs into OUT")
    args = ap.parse_args()
    out = Path(args.out)
    video = make(out, args.seconds, args.fps)
    if args.example:
        src = AGENT / "examples" / "synthetic-talk"
        for f in ("clips.json", "transcript.srt", "corrections.json"):
            shutil.copyfile(src / f, out / f)
    print(f"fixture: {video} ({args.seconds:g} s, {W}x{H}, {args.fps} fps)" + (", example inputs copied" if args.example else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
