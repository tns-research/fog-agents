#!/usr/bin/env python3
"""track.py: the 9:16 crop path that follows the speaker, one x per output frame.

    python3 scripts/track.py SOURCE --start 12.4 --end 41.0 --fps 25/1 --out RUN/work/<id>/track.json
                             [--mode track|fixed] [--x 0.5] [--sample 0.4]

How it moves (validated on real talks: calm and in frame beats tight tracking):

1. Detect. Every --sample seconds, OpenCV's Haar frontal face detector (shipped
   with opencv-python-headless, no model download) on a 960 px wide grey frame;
   then the profile detector, both ways; then a motion fallback (the largest
   moving area against the previous sample, the speaker in a static shot); else
   the sample is a miss. Several faces: the biggest, central and coherent with
   the previous pick wins, or the one nearest --x when given.
2. Fill misses by interpolation; no detection at all keeps the crop centred
   (or at --x).
3. Dead zone. The crop holds perfectly still while the face stays within
   DEADZONE_FRAC of the crop width around its centre, and moves only when the
   face crosses that edge, just enough to put it back on the edge. Long static
   holds and rare glides, never a nervous chase of every detection jitter.
4. Smooth. The path is sampled once per output frame (the renderer gives every
   frame its own x) and averaged over SMOOTH_SEC: the dead zone's steps become
   slow eases, holds stay exactly flat.
5. Seed. The first SEED_SEC are anchored on the first detection, so frame one is
   already composed on the speaker.

The x values are floats in source pixels; render.py places them on a finer grid
(sub-pixel pan) so a slow glide never stair-steps. Frame rate: the source rate
given by --fps, never another one (see render.py).

Writes track.json: crop width, one x per output frame, every sample with its
detector, and telemetry (max and mean step in output pixels per frame, share of
samples with a face, share of samples whose face stays inside the crop).

Exit codes: 0 written; 2 unreadable source, OpenCV missing, source narrower
than 9:16.
"""

from __future__ import annotations

import argparse
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_H, die, write_json  # noqa: E402

SAMPLE_DT = 0.4        # s between detections
DET_W = 960            # px width the detector works at
DEADZONE_FRAC = 0.30   # the face roams +-30 % of the crop width before the crop moves
SMOOTH_SEC = 1.6       # moving-average window: steps become eases, holds stay flat
SEED_SEC = 0.8         # first seconds anchored on the first detection
MOTION_MIN_AREA = 0.004  # share of the frame a moving area needs to count as the speaker
INSIDE_MARGIN = 0.10   # a face counts as inside the crop with 10 % of the crop width to spare


def _imports():
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        return cv2, np
    except ImportError:
        die("OpenCV and numpy are needed: pip install opencv-python-headless numpy")


def detect(cv2, np, frame, prev_gray, prev_cx: Optional[float], prefer_x: Optional[float], cascades) -> Tuple[Optional[float], str, Any, Optional[Tuple[float, float, float, float]]]:
    h, w = frame.shape[:2]
    scale = w / float(DET_W) if w > DET_W else 1.0
    small = cv2.resize(frame, (int(w / scale), int(h / scale))) if scale != 1.0 else frame
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    eq = cv2.equalizeHist(gray)
    sw = gray.shape[1]
    found = []
    method = "none"
    frontal, profile = cascades
    faces = frontal.detectMultiScale(eq, scaleFactor=1.15, minNeighbors=6, minSize=(34, 34))
    if len(faces):
        found, method = list(faces), "face"
    elif profile is not None:
        faces = profile.detectMultiScale(eq, scaleFactor=1.15, minNeighbors=6, minSize=(34, 34))
        flipped = profile.detectMultiScale(cv2.flip(eq, 1), scaleFactor=1.15, minNeighbors=6, minSize=(34, 34))
        found = list(faces) + [(sw - x - fw, y, fw, fh) for (x, y, fw, fh) in flipped]
        method = "profile" if found else "none"
    if found:
        best, best_score, box = None, -1e18, None
        for (x, y, fw, fh) in found:
            cx = (x + fw / 2.0) * scale
            cy = (y + fh / 2.0) * scale
            area = (fw * scale) * (fh * scale)
            if prefer_x is not None:
                score = -abs(cx - prefer_x)
            else:
                ref = prev_cx if prev_cx is not None else w / 2.0
                # big faces, near the upper-middle third, coherent with the previous pick
                score = area - 4.0 * abs(cx - ref) - 0.0008 * abs(cy - h * 0.42) * area
            if score > best_score:
                best_score, best = score, cx
                box = (x * scale, y * scale, fw * scale, fh * scale)
        return best, method, gray, box
    if prev_gray is not None and prev_gray.shape == gray.shape:
        diff = cv2.absdiff(cv2.GaussianBlur(gray, (9, 9), 0), cv2.GaussianBlur(prev_gray, (9, 9), 0))
        _, th = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
        th = cv2.dilate(th, None, iterations=3)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > MOTION_MIN_AREA * gray.size:
                x, y, fw, fh = cv2.boundingRect(c)
                return (x + fw / 2.0) * scale, "motion", gray, None
    return None, "none", gray, None


def track(source: Path, start: float, end: float, fps: Fraction, mode: str = "track",
          x_frac: Optional[float] = None, sample_dt: float = SAMPLE_DT) -> Dict[str, Any]:
    cv2, np = _imports()
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        die(f"OpenCV cannot open {source}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or float(fps)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cw = int(round(H * 9 / 16 / 2.0)) * 2   # even crop width, full source height
    if cw > W:
        die(f"source {W}x{H} is narrower than 9:16: nothing to reframe")
    max_x = float(W - cw)
    dur = end - start
    n_out = max(1, int(round(dur * float(fps))))
    out_t = np.arange(n_out) / float(fps)
    px_scale = OUT_H / float(H)   # output px per source px

    samples: List[Dict[str, Any]] = []
    prefer = x_frac * W if x_frac is not None else None
    if mode == "fixed":
        cx = (x_frac if x_frac is not None else 0.5) * W
        xs = np.full(n_out, float(np.clip(cx - cw / 2.0, 0, max_x)))
    else:
        frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        prof_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
        profile = cv2.CascadeClassifier(prof_path) if Path(prof_path).exists() else None
        if frontal.empty():
            die("OpenCV's Haar face cascade is missing from this install")
        # Sequential decode from the start frame: seeking per sample is slower on most codecs.
        first = int(round(start * src_fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, first)
        targets = [start + k * sample_dt for k in range(int(dur / sample_dt) + 1)]
        frame_i, ti = first, 0
        prev_gray, prev_cx = None, prefer
        while ti < len(targets):
            ok = cap.grab()
            if not ok:
                break
            t = frame_i / src_fps
            frame_i += 1
            if t + 0.5 / src_fps < targets[ti]:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            cx, method, prev_gray, box = detect(cv2, np, frame, prev_gray, prev_cx, prefer, (frontal, profile))
            if cx is not None and method in ("face", "profile"):
                prev_cx = cx
            samples.append({"t": round(targets[ti] - start, 3), "cx": None if cx is None else round(cx, 1),
                            "method": method, "box": [round(v, 1) for v in box] if box else None})
            ti += 1
        ts = np.array([s["t"] for s in samples]) if samples else np.array([0.0])
        raw = np.array([s["cx"] if s["cx"] is not None else np.nan for s in samples]) if samples else np.array([np.nan])
        good = ~np.isnan(raw)
        idx = np.arange(len(raw))
        if good.sum() == 0:
            raw[:] = prefer if prefer is not None else W / 2.0
            first_good = 0
        else:
            raw = np.interp(idx, idx[good], raw[good])
            first_good = int(np.argmax(good))
        dead = DEADZONE_FRAC * cw
        C = float(raw[first_good])
        centers = np.empty_like(raw)
        for i, fcx in enumerate(raw):
            if fcx > C + dead:
                C = fcx - dead
            elif fcx < C - dead:
                C = fcx + dead
            centers[i] = C
        crop_x = np.clip(centers - cw / 2.0, 0, max_x)
        xs = np.interp(out_t, ts, crop_x)
        win = max(3, int(round(SMOOTH_SEC * float(fps))))
        if win % 2 == 0:
            win += 1
        pad = win // 2
        xs = np.convolve(np.pad(xs, pad, mode="edge"), np.ones(win) / win, mode="valid")
        seed = float(crop_x[first_good])
        m = out_t < SEED_SEC
        ramp = np.clip(out_t[m] / SEED_SEC, 0.0, 1.0)
        xs[m] = (1.0 - ramp) * seed + ramp * xs[m]
        xs = np.clip(xs, 0.0, max_x)
    cap.release()

    steps = np.abs(np.diff(xs)) * px_scale if len(xs) > 1 else np.array([0.0])
    detected = [s for s in samples if s["method"] in ("face", "profile")]
    inside = 0
    for s in detected:
        k = min(n_out - 1, int(round(s["t"] * float(fps))))
        lo, hi = xs[k] + INSIDE_MARGIN * cw, xs[k] + cw - INSIDE_MARGIN * cw
        inside += 1 if lo <= s["cx"] <= hi else 0
    methods: Dict[str, int] = {}
    for s in samples:
        methods[s["method"]] = methods.get(s["method"], 0) + 1
    return {
        "source": str(source),
        "start": start,
        "end": end,
        "fps": f"{fps.numerator}/{fps.denominator}",
        "frames": n_out,
        "src_w": W,
        "src_h": H,
        "crop_w": cw,
        "mode": mode,
        "xs": [round(float(v), 2) for v in xs],
        "samples": samples,
        "telemetry": {
            "samples": len(samples),
            "methods": methods,
            "face_ratio": round(len(detected) / len(samples), 3) if samples else None,
            "face_inside_ratio": round(inside / len(detected), 3) if detected else None,
            "max_step_px": round(float(steps.max()), 2),
            "mean_step_px": round(float(steps.mean()), 3),
            "moving_frames": int((steps > 0.05).sum()),
            "x_range": [round(float(xs.min()), 1), round(float(xs.max()), 1)],
            "upscale": round(OUT_H / float(H), 2),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--fps", required=True, help="Output frame rate as a rational (25/1, 30000/1001): the source rate")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["track", "fixed"], default="track")
    ap.add_argument("--x", type=float, help="Fraction of the source width: crop centre (fixed) or person to follow (track)")
    ap.add_argument("--sample", type=float, default=SAMPLE_DT)
    args = ap.parse_args()
    if args.end <= args.start:
        die("--end must be after --start")
    data = track(Path(args.source), args.start, args.end, Fraction(args.fps), args.mode, args.x, args.sample)
    write_json(Path(args.out), data)
    t = data["telemetry"]
    print(f"track: {data['frames']} frames, crop {data['crop_w']}x{data['src_h']}, methods {t['methods']}, "
          f"face {t['face_ratio']}, inside {t['face_inside_ratio']}, max step {t['max_step_px']} px/frame -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
