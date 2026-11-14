#!/usr/bin/env python3
"""qa.py: measure a rendered short, and build the frames the reviewer reads.

    python3 scripts/qa.py --check RUN/export/<id>.mp4 --fps 25/1 [--duration 14.2] [--lufs -14]
    python3 scripts/qa.py --check FILE.mp4 --source talk.mp4     # expected fps taken from the source

Called by pipeline.py on every clip with what the render knows (frames,
captions, crop path). With --check it measures any MP4 against the expected
frame rate, which is the regression test for the judder bug: a short whose
frame rate differs from its source has dropped or repeated frames.

Errors (status fail): size (not 1080x1920), codec (not H.264 yuv420p), fps-mismatch,
duration, audio (missing or not 48 kHz), loudness (more than 2 LU off target),
first-frame (black or flat: a card or a fade, not the speaker), late-start (first
caption more than FIRST_CAPTION_MAX s in: the short does not open on speech),
caption-overlap, face-outside-crop (under 70 % of detections inside the crop),
not-proofread.

Warnings: loudness within 1 to 2 LU, true-peak, frame-count, faststart,
caption-gap, font-fallback, fast-pan, low-face-detection, face-near-edge,
no-face-first-frame, upscaled-source, logo-skipped.

Review files (pipeline.py): review/<id>/frames/frame-NN.jpg (first frame, evenly
spaced frames, last frame), review/<id>/captions-strip.jpg (the caption band at
10 fps over the first words, to read flicker, jumps and split words),
review/<id>/sheet.png and sheet-feed.png (shared contact sheet, 1080x1920
expected), review/first-frames.png (every clip's first frame: the scroll stop).

Exit codes (--check): 0 pass, 1 errors, 2 unreadable file or ffmpeg missing.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import struct
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXIT_CHECK, OUT_H, OUT_W, SHARED, need_binary, output_fps, probe  # noqa: E402

CONTACT_SHEET = SHARED / "skills" / "reviewing-renders" / "scripts" / "contact_sheet.py"
FIRST_CAPTION_MAX = 1.0    # s: past this the short does not open on speech
LOUD_WARN, LOUD_ERR = 1.0, 2.0  # LU away from the target
FAST_PAN = 8.0             # output px per frame: a glide faster than this reads as a jerk
FACE_INSIDE_WARN, FACE_INSIDE_ERR = 0.9, 0.7
FACE_RATIO_WARN = 0.5
UPSCALE_WARN = 2.0         # crop enlarged more than 2x: the image gets soft (720p source)
REVIEW_FRAMES = 6          # evenly spaced frames plus the last one


def loudness(path: Path) -> Dict[str, Optional[float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    summary = r.stderr.split("Summary:")[-1]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    p = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summary, re.S)

    def num(m):
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None
    return {"integrated": num(i), "true_peak": num(p)}


def frame_stats(path: Path, t: float = 0.0) -> Dict[str, float]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=270:480,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    data = r.stdout
    if not data:
        return {"mean": 0.0, "std": 0.0}
    vals = list(data[:: 7])
    return {"mean": round(statistics.fmean(vals), 1), "std": round(statistics.pstdev(vals), 1)}


def faststart(path: Path) -> Optional[bool]:
    try:
        with open(path, "rb") as f:
            order = []
            while len(order) < 8:
                head = f.read(8)
                if len(head) < 8:
                    break
                size, kind = struct.unpack(">I4s", head)
                kind = kind.decode("latin-1")
                if size == 1:
                    size = struct.unpack(">Q", f.read(8))[0]
                    f.seek(size - 16, 1)
                elif size == 0:
                    order.append(kind)
                    break
                else:
                    f.seek(size - 8, 1)
                order.append(kind)
            if "moov" in order and "mdat" in order:
                return order.index("moov") < order.index("mdat")
    except OSError:
        return None
    return None


def face_in_first_frame(path: Path) -> Optional[bool]:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    cap = cv2.VideoCapture(str(path))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    gray = cv2.equalizeHist(cv2.cvtColor(cv2.resize(frame, (540, 960)), cv2.COLOR_BGR2GRAY))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return len(casc.detectMultiScale(gray, 1.15, 5, minSize=(40, 40))) > 0


def check(path: Path, expect: Dict[str, Any]) -> Dict[str, Any]:
    """expect: fps (rational str), duration, frames, target_lufs, true_peak, captions, track, unproofread, logo_skipped."""
    need_binary("ffmpeg")
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    def err(code, msg):
        errors.append({"code": code, "message": msg})

    def warn(code, msg):
        warnings.append({"code": code, "message": msg})

    if not path.exists():
        err("missing", f"{path} not found")
        return {"file": str(path), "status": "fail", "errors": errors, "warnings": warnings}
    p = probe(path)
    if (p.get("width"), p.get("height")) != (OUT_W, OUT_H):
        err("size", f"{p.get('width')}x{p.get('height')}, expected {OUT_W}x{OUT_H}")
    if p.get("codec") != "h264" or p.get("pix_fmt") != "yuv420p":
        err("codec", f"{p.get('codec')} {p.get('pix_fmt')}, expected h264 yuv420p")
    want = Fraction(expect["fps"]) if expect.get("fps") else None
    got = Fraction(p.get("r_frame_rate") or "0/1") if p.get("r_frame_rate") else Fraction(0)
    if want and abs(float(got) - float(want)) > 0.01:
        err("fps-mismatch", f"{float(got):.3f} fps, source rate is {float(want):.3f}: frames were dropped or repeated, pans will judder. "
            "Render at the source rate (never -r 30 on a 25 or 50 fps source).")
    if expect.get("duration"):
        tol = 2.0 / float(want or 25) + 0.08
        if abs(p["duration"] - expect["duration"]) > tol:
            err("duration", f"{p['duration']:.2f} s, expected {expect['duration']:.2f} s")
    if expect.get("frames") and p.get("nb_frames") and abs(p["nb_frames"] - expect["frames"]) > 1:
        warn("frame-count", f"{p['nb_frames']} frames, the crop path has {expect['frames']}")
    if not p.get("has_audio"):
        err("audio", "no audio stream")
    elif p.get("sample_rate") != 48000:
        err("audio", f"audio at {p.get('sample_rate')} Hz, expected 48000")
    fs = faststart(path)
    if fs is False:
        warn("faststart", "moov atom after mdat: the file starts playing only once fully downloaded")

    loud = loudness(path) if p.get("has_audio") else {"integrated": None, "true_peak": None}
    target = expect.get("target_lufs", -14.0)
    if loud["integrated"] is None:
        warn("loudness", "integrated loudness not measurable (silent audio?)")
    else:
        off = abs(loud["integrated"] - target)
        if off > LOUD_ERR:
            err("loudness", f"{loud['integrated']:.1f} LUFS, target {target:.1f}")
        elif off > LOUD_WARN:
            warn("loudness", f"{loud['integrated']:.1f} LUFS, target {target:.1f}")
    if loud["true_peak"] is not None and loud["true_peak"] > expect.get("true_peak", -1.5) + 0.5:
        warn("true-peak", f"true peak {loud['true_peak']:.1f} dBFS")

    first = frame_stats(path, 0.0)
    if first["mean"] < 16 or first["std"] < 6:
        err("first-frame", f"first frame is black or flat (mean {first['mean']}, std {first['std']}): a short opens on the speaker, not on a card or a fade")

    cap = expect.get("captions") or {}
    if cap:
        fc = cap.get("first_caption")
        if fc is None:
            err("late-start", "no caption at all")
        elif fc > FIRST_CAPTION_MAX:
            err("late-start", f"first caption at {fc:.2f} s: the short must open on speech")
        if cap.get("overlaps"):
            err("caption-overlap", f"{cap['overlaps']} caption events overlap (double text on screen)")
        if cap.get("micro_gaps"):
            warn("caption-gap", f"{cap['micro_gaps']} gaps under 20 ms between captions (one-frame blink)")
        if cap.get("font_fallback"):
            warn("font-fallback", f"font {cap.get('font_requested')!r} not installed, {cap.get('font')} used")
    tr = expect.get("track") or {}
    face_first = None
    if tr:
        if tr.get("max_step_px", 0) > FAST_PAN:
            warn("fast-pan", f"crop moves up to {tr['max_step_px']} px per frame")
        fr = tr.get("face_ratio")
        if fr is not None and fr < FACE_RATIO_WARN:
            warn("low-face-detection", f"a face found in {fr:.0%} of samples ({tr.get('methods')}): check the framing on the sheet, or set framing in clips.json")
        fi = tr.get("face_inside_ratio")
        if fi is not None and fi < FACE_INSIDE_ERR:
            err("face-outside-crop", f"only {fi:.0%} of detected faces inside the crop")
        elif fi is not None and fi < FACE_INSIDE_WARN:
            warn("face-near-edge", f"{fi:.0%} of detected faces inside the crop margins")
        if tr.get("upscale", 0) > UPSCALE_WARN:
            warn("upscaled-source", f"the crop is enlarged {tr['upscale']}x: a 1080p or larger source gives a sharper short")
        if fr and fr >= FACE_RATIO_WARN:
            face_first = face_in_first_frame(path)
            if face_first is False:
                warn("no-face-first-frame", "no face detected on frame one: check that the short opens on the speaker")
    if expect.get("unproofread"):
        err("not-proofread", "rendered before the transcript was proofread and signed: draft only")
    if expect.get("logo_skipped"):
        warn("logo-skipped", f"logo {expect['logo_skipped']} not used (missing or not PNG/JPEG/WebP)")

    return {
        "file": str(path),
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "probe": {"width": p.get("width"), "height": p.get("height"), "fps": p.get("r_frame_rate"),
                  "duration": round(p["duration"], 3), "frames": p.get("nb_frames"), "sample_rate": p.get("sample_rate"),
                  "faststart": fs},
        "loudness": loud,
        "first_frame": first,
        "face_first_frame": face_first,
    }


def review_assets(path: Path, review: Path, duration: float, first_caption: float, title: str) -> Dict[str, Any]:
    frames = review / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    times = [0.0] + [duration * k / REVIEW_FRAMES for k in range(1, REVIEW_FRAMES)] + [max(0.0, duration - 0.15)]
    for n, t in enumerate(times, start=1):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-q:v", "3",
                        str(frames / f"frame-{n:02d}.jpg")], capture_output=True)
    strip = review / "captions-strip.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, first_caption):.3f}", "-t", "2.4", "-i", str(path),
                    "-vf", "fps=10,crop=1080:480:0:1060,scale=360:160,tile=4x6", "-frames:v", "1", "-q:v", "3", str(strip)],
                   capture_output=True)
    sheets = {}
    if CONTACT_SHEET.exists():
        for name, extra in (("sheet.png", []), ("sheet-feed.png", ["--scale", "feed"])):
            r = subprocess.run([sys.executable, str(CONTACT_SHEET), str(frames), "-o", str(review / name),
                                "--expect", f"{OUT_W}x{OUT_H}", "--title", title, "--cols", "7"] + extra,
                               capture_output=True, text=True)
            sheets[name] = {"exit": r.returncode, "path": str(review / name)}
    return {"frames": sorted(str(f) for f in frames.glob("*.jpg")), "captions_strip": str(strip) if strip.exists() else None,
            "sheets": sheets}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", required=True, help="MP4 to measure")
    ap.add_argument("--fps", help="Expected frame rate (rational, for example 25/1)")
    ap.add_argument("--source", help="Source video: the expected frame rate is derived from it")
    ap.add_argument("--duration", type=float)
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    fps = args.fps
    if not fps and args.source:
        fps = output_fps(probe(Path(args.source)))[0]
    res = check(Path(args.check), {"fps": fps, "duration": args.duration, "target_lufs": args.lufs})
    if args.json:
        print(json.dumps(res, indent=1))
    else:
        for e in res["errors"]:
            print(f"ERROR   {e['code']:20} {e['message']}")
        for w in res["warnings"]:
            print(f"warning {w['code']:20} {w['message']}")
        print(f"qa: {res['status']} ({res['probe'] if 'probe' in res else ''})")
    return 0 if res["status"] == "pass" else EXIT_CHECK


if __name__ == "__main__":
    sys.exit(main())
