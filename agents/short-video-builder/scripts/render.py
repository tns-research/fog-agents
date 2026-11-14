#!/usr/bin/env python3
"""render.py: one clip of the plan to a 1080x1920 MP4, locally with ffmpeg.

    python3 scripts/render.py RUN/clips.json --clip ID [--quick] [--allow-unproofread]

Usually called through pipeline.py, which renders every clip and runs the QA.
For one clip: clipspec.py resolves the spec, the proofread gate is checked,
track.py computes the crop path, captions.py writes the ASS file, then ffmpeg:

  video  trim (accurate input seek) -> scale the source width by PAN_K ->
         crop x per frame from a sendcmd file (sub-pixel pan: one crop step is
         1/PAN_K source pixel, so a slow glide never stair-steps) -> scale to
         1080x1920 -> progress bar (drawbox width per frame from sendcmd; the
         drawbox width cannot take a time expression) -> captions, lower third
         and end card (libass) -> optional logo, top right.
  fps    the output keeps the source frame rate (common.output_fps). Never a
         fixed -r 30: resampling 50 to 30 drops 2 frames in 5 on an uneven
         cadence and every pan judders, while a static shot looks fine. That
         is the bug this rule exists for.
  audio  48 kHz, high-pass at 80 Hz, light spectral denoise (audio.denoise),
         two-pass EBU R128 loudnorm to audio.target_lufs (default -14 LUFS,
         true peak -1.5 dBTP), 40 ms fade in, 0.5 s fade out. The source sound
         keeps running under the end card: no silent frozen frame.
  file   H.264 yuv420p, AAC 160 kb/s 48 kHz, faststart.

There is no intro card: frame one is the speaker, a few hundredths of a
second before the first word.

Writes RUN/export/<id>.mp4 and RUN/work/<id>/ (track.json, crop.cmd, bar.cmd,
subs.ass, filter.txt, render.json).

Exit codes: 0 rendered; 1 spec errors or transcript not proofread (nothing
rendered); 2 fatal (ffmpeg, OpenCV, unreadable source).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captions as captions_mod  # noqa: E402
import clipspec  # noqa: E402
import proofread  # noqa: E402
import track as track_mod  # noqa: E402
from common import EXIT_CHECK, OUT_H, OUT_W, die, ffmpeg_color, need_binary, write_json  # noqa: E402

PAN_K = 4            # sub-pixel pan grid: source width x4 before the crop
PAN_K_QUICK = 1      # quick previews skip the oversampling
BAR_H = 10           # progress bar height, px at the bottom edge
LOGO_W = 220         # logo width, px
LOGO_MARGIN = 72     # px from the top and right edges (above the 6 % safe margin)
CRF, PRESET = 20, "medium"
CRF_QUICK, PRESET_QUICK = 28, "ultrafast"


def loudnorm_measure(source: str, start: float, dur: float, pre: str, target: Dict[str, Any]) -> Dict[str, str]:
    af = f"{pre}loudnorm=I={target['target_lufs']}:TP={target['true_peak']}:LRA=11:print_format=json"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", source,
                        "-vn", "-af", af, "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if r.returncode != 0 or not m:
        return {}
    data = json.loads(m.group(0))
    if any(str(data.get(k, "")).lower() in ("-inf", "inf", "nan") for k in ("input_i", "input_tp", "input_lra", "input_thresh")):
        return {}
    return data


def audio_chain(source: str, start: float, dur: float, audio: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    pre = "aresample=48000,highpass=f=80,"
    if audio.get("denoise", True):
        pre += "afftdn=nr=10:nf=-25,"
    m = loudnorm_measure(source, start, dur, pre, audio)
    ln = f"loudnorm=I={audio['target_lufs']}:TP={audio['true_peak']}:LRA=11"
    if m:
        ln += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
               f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    fade_out = max(0.0, dur - 0.5)
    chain = f"{pre}{ln},aresample=48000,afade=t=in:d=0.04,afade=t=out:st={fade_out:.3f}:d=0.5"
    return chain, {"two_pass": bool(m), "input_i": m.get("input_i") if m else None}


def write_cmds(work: Path, xs: List[float], fps: Fraction, k: int, speech_end: float, n_frames: int, bar: bool) -> None:
    # A command at time T applies from the first frame whose time is >= T. Half a
    # frame early keeps float rounding from slipping a value to the next frame.
    lines = []
    half = 0.5 / float(fps)
    for i, x in enumerate(xs):
        t = 0.0 if i == 0 else i / float(fps) - half
        lines.append(f"{t:.4f} crop x {int(round(x * k))};")
    (work / "crop.cmd").write_text("\n".join(lines) + "\n", encoding="utf-8")
    blines = []
    if bar:
        for i in range(n_frames):
            t = i / float(fps)
            w = max(1, min(OUT_W, int(round(OUT_W * min(1.0, t / max(speech_end, 0.1))))))
            blines.append(f"{0.0 if i == 0 else t - half:.4f} drawbox w {w};")
    (work / "bar.cmd").write_text("\n".join(blines) + "\n", encoding="utf-8")


def render_clip(plan: Dict[str, Any], clip: Dict[str, Any], run_dir: Path, quick: bool = False,
                unproofread: bool = False) -> Dict[str, Any]:
    need_binary("ffmpeg")
    t0 = time.time()
    work = run_dir / "work" / clip["id"]
    work.mkdir(parents=True, exist_ok=True)
    export = run_dir / "export"
    export.mkdir(parents=True, exist_ok=True)
    fps = Fraction(plan["fps"])
    start, dur = clip["start"], clip["duration"]

    framing = clip.get("framing") or {}
    tr = track_mod.track(Path(plan["source"]), start, start + dur, fps, framing.get("mode", "track"), framing.get("x"))
    write_json(work / "track.json", tr)
    n_frames = tr["frames"]

    ass, cap_info = captions_mod.build(plan, clip)
    (work / "subs.ass").write_text(ass, encoding="utf-8")

    style = plan["style"]
    k = PAN_K_QUICK if quick else PAN_K
    write_cmds(work, tr["xs"], fps, k, clip["speech_end"], n_frames, bool(style.get("progress_bar", True)))
    W, H, cw = tr["src_w"], tr["src_h"], tr["crop_w"]
    x0 = int(round(tr["xs"][0] * k))
    logo = style.get("logo")
    if logo and (not Path(logo).exists() or Path(logo).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp")):
        cap_info["logo_skipped"] = logo
        logo = None
    g = [f"[0:v]scale={W * k}:{H}:flags=bicubic,sendcmd=f=crop.cmd,crop={cw * k}:{H}:{x0}:0,"
         f"scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1,format=yuv420p[v0]"]
    last = "v0"
    if style.get("progress_bar", True):
        g.append(f"[{last}]sendcmd=f=bar.cmd,drawbox=x=0:y={OUT_H - BAR_H}:w=1:h={BAR_H}:color={ffmpeg_color(style['accent'])}:t=fill[v1]")
        last = "v1"
    g.append(f"[{last}]ass=subs.ass[v2]")
    last = "v2"
    if logo:
        g.append(f"[1:v]scale={LOGO_W}:-1,format=rgba[lg]")
        g.append(f"[{last}][lg]overlay=W-w-{LOGO_MARGIN}:{LOGO_MARGIN}:shortest=1[v3]")
        last = "v3"
    g.append(f"[{last}]null[outv]")
    (work / "filter.txt").write_text(";\n".join(g) + "\n", encoding="utf-8")

    af, a_info = audio_chain(plan["source"], start, dur, plan["audio"])
    out = export / f"{clip['id']}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", plan["source"]]
    if logo:
        cmd += ["-loop", "1", "-i", logo]
    cmd += ["-filter_complex_script", "filter.txt", "-map", "[outv]", "-map", "0:a:0", "-af", af,
            "-r", plan["fps"], "-frames:v", str(n_frames),
            "-c:v", "libx264", "-preset", PRESET_QUICK if quick else PRESET, "-crf", str(CRF_QUICK if quick else CRF),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart",
            "-shortest", str(out.resolve())]
    r = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        die(f"ffmpeg failed on clip {clip['id']}: {(r.stderr or '').strip()[-500:]}")
    info = {
        "clip": clip["id"],
        "file": str(out),
        "start": start,
        "duration": dur,
        "frames": n_frames,
        "fps": plan["fps"],
        "fps_note": plan.get("fps_note"),
        "pan_k": k,
        "quick": quick,
        "unproofread": unproofread,
        "captions": cap_info,
        "audio": a_info,
        "track": tr["telemetry"],
        "seconds": round(time.time() - t0, 1),
    }
    write_json(work / "render.json", info)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="clips.json")
    ap.add_argument("--clip", required=True, help="Clip id to render")
    ap.add_argument("--out", help="Run folder (default: the spec's folder)")
    ap.add_argument("--quick", action="store_true", help="Fast preview: ultrafast preset, crf 28, no sub-pixel pan")
    ap.add_argument("--allow-unproofread", action="store_true", help="Render a draft before the proofread signature (QA then fails)")
    args = ap.parse_args()
    spec = Path(args.spec).resolve()
    run_dir = Path(args.out).resolve() if args.out else spec.parent
    plan = clipspec.resolve(spec)
    write_json(run_dir / "work" / "plan.json", plan)
    if plan["status"] != "pass":
        clipspec.print_report(plan)
        return EXIT_CHECK
    ok, why = proofread.gate(Path(plan["transcript"]))
    if not ok and not args.allow_unproofread:
        print(f"render: {why}", file=sys.stderr)
        return EXIT_CHECK
    clip = next((c for c in plan["clips"] if c["id"] == args.clip), None)
    if not clip:
        print(f"render: no clip {args.clip!r} in {spec}", file=sys.stderr)
        return EXIT_CHECK
    info = render_clip(plan, clip, run_dir, args.quick, not ok)
    print(f"render: {info['file']} ({info['duration']:.1f} s, {info['frames']} frames at {info['fps']}, {info['seconds']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
