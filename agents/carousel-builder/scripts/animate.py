#!/usr/bin/env python3
"""animate.py: the same deck.json as a short MP4 for LinkedIn and Instagram.

  python3 scripts/animate.py <deck.json> [--aspect 4:5|9:16|1:1] [--out DIR]
  python3 scripts/animate.py --check <video.mp4> [--aspect A] [--fps N]

Local and free: build.py writes the HTML, fit.js sizes every text exactly as
for the stills, then scripts/animate.js stages the slides on the video canvas
and schedules sober entrances (title, then body; list items one by one; bars
that grow from the axis; a stat that counts up; a crossfade between slides).
No word is rewritten and no size changes: the video shows the validated slides.

Capture is deterministic. Every motion is a paused Web Animation; for each
frame the script sets currentTime to n / fps, takes a PNG of the page with
Chromium (Playwright) and pipes it to ffmpeg (H.264, yuv420p, BT.709, +faststart).
Frames where nothing moves reuse the previous PNG, so hold time costs nothing.
Same inputs, same file, byte for byte.

Timing: each slide lasts its reading time, `orient + words * 60 / wpm`
(default 200 words a minute, below the 238 wpm average silent reading rate for
non-fiction in Brysbaert 2019, https://doi.org/10.1016/j.jml.2019.104047, since
the reader is also watching), clamped to [--min-slide, --max-slide], and never
less than its entrance plus a short settle. The first slide is complete on
frame 0 (feeds show that frame before playback) and holds --max-first seconds
at most: the hook has to work before the viewer scrolls. --max-duration fits a
total by shortening the holds in proportion, never the entrances.

Canvas: 4:5 (1080x1350), 9:16 (1080x1920) or 1:1 (1080x1080). When the deck's
own ratio differs, the slide is scaled whole into the canvas safe box and
centred on its own ground (never cropped, never recomposed). 9:16 uses the
`reels` safe box by default (top 220, bottom 430, sides 90 px: clear of the
Reels, TikTok and Shorts overlays); `--safe ads` uses Meta's ads margins
(14 % top, 35 % bottom, 6 % sides), `--safe none` the full canvas.

Audio: none by default. --music FILE mixes a local file (looped if shorter)
with a fade out on the last --fade-out seconds.

Writes, in DIR/export (DIR = the deck folder unless --out):
  video-<aspect>.mp4          the video (aspect written 4x5, 9x16, 1x1)
  video-<aspect>.json         timeline per slide, render stats, QA
  video-<aspect>-frames.jpg   contact sheet: mid-entrance and settled frame per slide

QA (also alone with --check): ffprobe codec, pix_fmt, size, fps, frame count,
duration, moov before mdat (faststart), audio as requested, LinkedIn limits
(3 s to 15 min, 30 Mbit/s, 75 KB), first and last frame neither black nor flat.

HyperFrames: when the `hyperframes` CLI is installed, a richer composition can
be authored from the same deck.json with it (see skills/animate-deck/SKILL.md);
this script never needs it.

Exit code: 0 video written and QA pass; 1 deck not validated (build errors or
fit failures; --force renders anyway) or QA errors; 2 fatal input error
(unreadable deck, missing ffmpeg, Playwright or music file, bad option).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

HERE = Path(__file__).resolve().parent
ANIMATE_JS = HERE / "animate.js"
FIT_TIMEOUT_MS = 30000

ASPECTS = {"4:5": (1080, 1350), "9:16": (1080, 1920), "1:1": (1080, 1080)}
# Safe boxes in px on a 1080 wide canvas: (top, bottom, side).
SAFE = {
    "none": (0, 0, 0),
    "reels": (220, 430, 90),
    "ads": (269, 672, 65),
}
LINKEDIN = {"min_s": 3.0, "max_s": 900.0, "max_bps": 30_000_000, "min_bytes": 75_000}
MIN_TEXT_PX = 24  # qa.py minimum on a 1080 px slide


class Fatal(Exception):
    pass


def tag(aspect: str) -> str:
    return aspect.replace(":", "x")


def placement(canvas: Tuple[int, int], slide: Tuple[int, int], safe: Tuple[int, int, int]) -> Dict[str, Any]:
    W, H = canvas
    sw, sh = slide
    top, bottom, side = safe
    bw, bh = W - 2 * side, H - top - bottom
    scale = min(1.0, bw / sw, bh / sh)
    if (sw, sh) == (W, H) and safe == SAFE["none"]:
        scale = 1.0
    scale = round(scale, 4)
    left = round(side + (bw - sw * scale) / 2)
    tp = round(top + (bh - sh * scale) / 2)
    return {"scale": scale, "left": left, "top": tp, "box": {"top": top, "bottom": bottom, "side": side}}


def parse_slides(spec: Optional[str]) -> List[int]:
    if not spec:
        return []
    out: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(dict.fromkeys(out))


def need_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise Fatal(f"{tool} not found: install ffmpeg (apt install ffmpeg, brew install ffmpeg)")
    try:
        import playwright  # noqa: F401
    except ImportError as e:
        raise Fatal("Playwright missing: pip install -r scripts/requirements.txt && playwright install chromium") from e


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------

def ffmpeg_cmd(out: Path, fps: int, crf: int, preset: str, duration: float, music: Optional[Path], volume: float, fade_out: float) -> List[str]:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png", "-i", "-"]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    cmd += ["-map", "0:v"]
    if music:
        fo = max(0.0, min(fade_out, duration))
        cmd += ["-map", "1:a", "-af", f"volume={volume},afade=t=out:st={max(0.0, duration - fo):.3f}:d={fo:.3f}",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    cmd += ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(fps * 2),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
            "-t", f"{duration:.3f}", "-movflags", "+faststart",
            "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", "-map_metadata", "-1",
            str(out)]
    return cmd


def capture(html: Path, out_mp4: Path, canvas: Tuple[int, int], slide_size: Tuple[int, int], place: Dict[str, Any],
            cfg: Dict[str, Any], encode: Dict[str, Any], keep_frames: Optional[Path], force: bool) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright

    W, H = canvas
    res: Dict[str, Any] = {}
    t0 = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": max(W, slide_size[0]), "height": max(H, slide_size[1])}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(html.resolve().as_uri(), wait_until="load")
        page.wait_for_function("document.body.dataset.fitted === '1'", timeout=FIT_TIMEOUT_MS)
        fit = page.evaluate("window.__fit")
        fails = []
        for s in fit.get("slides", []):
            if s.get("overflow"):
                fails.append(f"slide {s['index']:02d} overflows ({', '.join(s.get('overflowAt', []))})")
            for it in s.get("items", []):
                if it.get("status") == "fail":
                    fails.append(f"slide {s['index']:02d} {it.get('kind')}: {it.get('reason')}")
        res["fit_failures"] = fails
        if fails and not force:
            browser.close()
            return res
        page.set_viewport_size({"width": W, "height": H})
        page.add_script_tag(path=str(ANIMATE_JS))
        timeline = page.evaluate("cfg => window.__animSetup(cfg)", dict(cfg, W=W, H=H, scale=place["scale"], left=place["left"], top=place["top"]))
        res["timeline"] = timeline
        n_frames, fps = timeline["frames"], cfg["fps"]
        cdp = ctx.new_cdp_session(page)

        def shot() -> bytes:
            r = cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True,
                                                    "clip": {"x": 0, "y": 0, "width": W, "height": H, "scale": 1},
                                                    "captureBeyondViewport": False})
            return base64.b64decode(r["data"])

        cmd = ffmpeg_cmd(out_mp4, fps, encode["crf"], encode["preset"], n_frames / fps, encode.get("music"), encode["volume"], encode["fade_out"])
        err = tempfile.TemporaryFile()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err)
        if keep_frames:
            keep_frames.mkdir(parents=True, exist_ok=True)
            for old in keep_frames.glob("frame-*.png"):
                old.unlink()
        prev_sig, buf, rendered = None, b"", 0
        try:
            for n in range(n_frames):
                st = page.evaluate("t => window.__animSeek(t)", n / fps)
                if n == 0 or st["moving"] or st["sig"] != prev_sig:
                    buf = shot()
                    rendered += 1
                prev_sig = st["sig"]
                proc.stdin.write(buf)
                if keep_frames:
                    p = keep_frames / f"frame-{n:05d}.png"
                    p.write_bytes(buf)
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except BrokenPipeError:
                pass
            rc = proc.wait()
            browser.close()
        err.seek(0)
        if rc != 0:
            raise Fatal(f"ffmpeg failed ({rc}): {err.read().decode('utf-8', 'replace')[-1500:]}")
        res["rendered_frames"] = rendered
        res["seconds"] = round(time.time() - t0, 1)
    return res


# --------------------------------------------------------------------------
# QA
# --------------------------------------------------------------------------

def probe(path: Path) -> Dict[str, Any]:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Fatal(f"ffprobe cannot read {path}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def atom_order(path: Path) -> List[str]:
    order = []
    with open(path, "rb") as f:
        size_total = os.path.getsize(path)
        pos = 0
        while pos < size_total and len(order) < 64:
            f.seek(pos)
            head = f.read(8)
            if len(head) < 8:
                break
            size, kind = struct.unpack(">I4s", head)
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
            elif size == 0:
                size = size_total - pos
            order.append(kind.decode("latin-1"))
            if size < 8:
                break
            pos += size
    return order


def extract_frames(path: Path, indexes: List[int], tmp: Path) -> Dict[int, Path]:
    """One decode pass, the requested frame numbers as PNG files."""
    idx = sorted(set(i for i in indexes if i >= 0))
    if not idx:
        return {}
    expr = "+".join(f"eq(n\\,{i})" for i in idx)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                    "-vf", f"select='{expr}'", "-vsync", "0", str(tmp / "f-%04d.png")],
                   check=True)
    files = sorted(tmp.glob("f-*.png"))
    return {i: f for i, f in zip(idx, files)}


def frame_stats(png: Path) -> Dict[str, float]:
    from PIL import Image, ImageStat
    im = Image.open(png).convert("L")
    st = ImageStat.Stat(im)
    return {"mean": round(st.mean[0], 1), "std": round(st.stddev[0], 1)}


def check_video(path: Path, expect: Dict[str, Any], tmp: Path) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    def err(code: str, msg: str) -> None:
        errors.append({"code": code, "message": msg})

    def warn(code: str, msg: str) -> None:
        warnings.append({"code": code, "message": msg})

    if not path.exists():
        err("missing-video", f"{path} was not written")
        return {"status": "fail", "errors": errors, "warnings": warnings}
    info = probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    size = int(fmt.get("size", path.stat().st_size))
    duration = float(fmt.get("duration", 0) or 0)
    bitrate = int(fmt.get("bit_rate", 0) or 0)
    p: Dict[str, Any] = {"duration": round(duration, 3), "size_bytes": size, "bit_rate": bitrate}
    if not v:
        err("no-video-stream", "no video stream")
        return {"status": "fail", "errors": errors, "warnings": warnings, "probe": p}
    num, den = (v.get("avg_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    nb = int(v.get("nb_frames", 0) or 0)
    p.update({"codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"), "width": v.get("width"), "height": v.get("height"),
              "fps": round(fps, 3), "frames": nb, "color_space": v.get("color_space"), "audio": a.get("codec_name") if a else None})
    if v.get("codec_name") != "h264":
        err("codec", f"video codec {v.get('codec_name')}, expected h264")
    if v.get("pix_fmt") != "yuv420p":
        err("pix-fmt", f"pixel format {v.get('pix_fmt')}, expected yuv420p (players and platforms)")
    if expect.get("width") and (v.get("width"), v.get("height")) != (expect["width"], expect["height"]):
        err("size", f"{v.get('width')}x{v.get('height')}, expected {expect['width']}x{expect['height']}")
    if expect.get("fps") and abs(fps - expect["fps"]) > 0.01:
        err("fps", f"{fps:.3f} fps, expected {expect['fps']}")
    if expect.get("frames") and abs(nb - expect["frames"]) > 1:
        err("frame-count", f"{nb} frames, expected {expect['frames']}")
    if expect.get("duration") and abs(duration - expect["duration"]) > 2.0 / max(1, expect.get("fps", 30)) + 0.05:
        err("duration", f"{duration:.2f} s, expected {expect['duration']:.2f} s")
    order = atom_order(path)
    p["atoms"] = order[:8]
    if "moov" not in order or ("mdat" in order and order.index("moov") > order.index("mdat")):
        err("faststart", "moov atom after mdat: the video cannot start before it is fully downloaded (+faststart)")
    if "audio" in expect:
        if expect["audio"] and not a:
            err("audio-missing", "--music was given but the file has no audio stream")
        if not expect["audio"] and a:
            warn("audio-unexpected", "audio stream present without --music")
    if duration < LINKEDIN["min_s"]:
        err("too-short", f"{duration:.1f} s: LinkedIn needs 3 s or more")
    if duration > LINKEDIN["max_s"]:
        err("too-long", f"{duration:.0f} s: LinkedIn takes 15 min at most")
    if bitrate > LINKEDIN["max_bps"]:
        err("bitrate", f"{bitrate / 1e6:.1f} Mbit/s, LinkedIn takes 30 Mbit/s at most")
    if size < LINKEDIN["min_bytes"]:
        err("too-small", f"{size} bytes, LinkedIn needs 75 KB or more")
    last = max(0, nb - 1)
    frames = extract_frames(path, [0, last], tmp)
    for label, i in (("first", 0), ("last", last)):
        f = frames.get(i)
        if not f:
            err(f"{label}-frame", f"cannot decode the {label} frame")
            continue
        st = frame_stats(f)
        p[f"{label}_frame"] = st
        if st["mean"] < 12 and st["std"] < 8:
            err(f"{label}-frame-black", f"the {label} frame is black (mean luma {st['mean']})")
        elif st["std"] < 3:
            warn(f"{label}-frame-flat", f"the {label} frame is a flat colour (luma std {st['std']}): nothing to read")
    return {"status": "fail" if errors else "pass", "errors": errors, "warnings": warnings, "probe": p}


def sheet(path: Path, timeline: Dict[str, Any], fps: int, out: Path, tmp: Path, tile_w: int = 216, per_row: int = 6,
          max_tiles: int = 0) -> Optional[str]:
    """Contact sheet: for each slide, mid-entrance frame then settled frame."""
    from PIL import Image, ImageDraw, ImageFont

    picks: List[Tuple[int, str]] = []
    last = timeline["frames"] - 1
    for s in timeline["slides"]:
        cs, en = s["contentStart"], s["entrance"]
        if en > 0.2:
            picks.append((min(last, round((cs + en * 0.45) * fps)), f"{s['index']:02d} in"))
        settled = min(s["end"] - 0.05, cs + en + 0.3) if en > 0 else min(s["end"] - 0.05, cs + 0.5)
        picks.append((min(last, round(settled * fps)), f"{s['index']:02d}"))
    if max_tiles and len(picks) > max_tiles:
        step = (len(picks) - 1) / (max_tiles - 1)
        picks = [picks[round(i * step)] for i in range(max_tiles)]
    sub = tmp / "sheet"
    sub.mkdir(exist_ok=True)
    frames = extract_frames(path, [i for i, _ in picks], sub)
    if not frames:
        return None
    first = Image.open(next(iter(frames.values())))
    th = round(tile_w * first.height / first.width)
    pad, lab = 12, 22
    cols = min(per_row, len(picks))
    rows = (len(picks) + cols - 1) // cols
    W = pad + cols * (tile_w + pad)
    H = pad + rows * (th + lab + pad)
    board = Image.new("RGB", (W, H), (226, 224, 218))
    d = ImageDraw.Draw(board)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 14)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    for k, (i, label) in enumerate(picks):
        f = frames.get(i)
        if not f:
            continue
        x = pad + (k % cols) * (tile_w + pad)
        y = pad + (k // cols) * (th + lab + pad)
        board.paste(Image.open(f).convert("RGB").resize((tile_w, th), Image.LANCZOS), (x, y))
        d.text((x, y + th + 4), f"{label}  {i / fps:.1f} s", fill=(40, 40, 40), font=font)
    board.save(out, quality=80, optimize=True)
    return out.name


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def run(deck_path: Path, out_dir: Path, aspect: Optional[str] = None, direction: Optional[str] = None,
        brand: Optional[str] = None, opts: Optional[Dict[str, Any]] = None) -> int:
    o = dict(DEFAULTS)
    o.update({k: v for k, v in (opts or {}).items() if v is not None})
    need_tools()
    music = Path(o["music"]).resolve() if o.get("music") else None
    if music and not music.is_file():
        raise Fatal(f"music file not found: {music}")
    html_dir = out_dir / "html"
    if o["build"]:
        import build
        rep = build.build_deck(deck_path, html_dir, direction, brand)
        if rep.get("fatal"):
            for e in rep["errors"]:
                print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
            raise Fatal("deck.json does not load")
        if rep["errors"] and not o["force"]:
            for e in rep["errors"]:
                print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
            print(f"animate: {len(rep['errors'])} spec errors: fix deck.json first (the video only shows validated slides), or --force",
                  file=sys.stderr)
            return 1
    rep_file = html_dir / "build-report.json"
    if not (html_dir / "index.html").exists() or not rep_file.exists():
        raise Fatal(f"no built deck in {html_dir}: run without --no-build")
    rep = json.loads(rep_file.read_text(encoding="utf-8"))
    slide_size = (int(rep.get("width", 1080)), int(rep.get("height", 1350)))
    if not aspect:
        aspect = min(ASPECTS, key=lambda k: abs(ASPECTS[k][1] / ASPECTS[k][0] - slide_size[1] / slide_size[0]))
    if aspect not in ASPECTS:
        raise Fatal(f"unknown aspect {aspect}: one of {', '.join(ASPECTS)}")
    canvas = ASPECTS[aspect]
    safe_name = o["safe"]
    if safe_name == "auto":
        safe_name = "reels" if aspect == "9:16" else "none"
    if safe_name not in SAFE:
        raise Fatal(f"unknown safe box {safe_name}: one of auto, {', '.join(SAFE)}")
    place = placement(canvas, slide_size, SAFE[safe_name])
    export = out_dir / "export"
    export.mkdir(parents=True, exist_ok=True)
    mp4 = export / f"video-{tag(aspect)}.mp4"
    cfg = {"fps": o["fps"], "wpm": o["wpm"], "orient": o["orient"], "minSlide": o["min_slide"], "maxSlide": o["max_slide"],
           "transition": o["transition"], "settle": o["settle"], "endHold": o["end_hold"],
           "maxFirst": o["max_first"], "maxDuration": o.get("max_duration") or 0,
           "staticFirst": not o["animate_cover"], "slides": parse_slides(o.get("slides"))}
    encode = {"crf": o["crf"], "preset": o["preset"], "music": music, "volume": o["music_volume"], "fade_out": o["fade_out"]}
    keep = Path(o["keep_frames"]).resolve() if o.get("keep_frames") else None
    print(f"animate: {aspect} {canvas[0]}x{canvas[1]}, slide {slide_size[0]}x{slide_size[1]} at scale {place['scale']} "
          f"(safe box {safe_name}), {o['fps']} fps")
    cap = capture(html_dir / "index.html", mp4, canvas, slide_size, place, cfg, encode, keep, o["force"])
    if cap.get("fit_failures") and "timeline" not in cap:
        for f in cap["fit_failures"]:
            print(f"ERROR fit {f}", file=sys.stderr)
        print("animate: some texts do not fit: fix deck.json first (see export/qa.json), or --force", file=sys.stderr)
        return 1
    tl = cap["timeline"]
    tl["duration"] = round(tl["duration"], 3)
    for s in tl["slides"]:
        for k in ("start", "contentStart", "end"):
            s[k] = round(s[k], 3)
    for s in tl["slides"]:
        print(f"  slide {s['index']:02d} {s['id']:<18} {s['start']:6.2f} s  {s['end'] - s['start']:5.2f} s  "
              f"{s['words']:3d} words  entrance {s['entrance']:.2f} s")
    if o.get("max_duration") and tl["duration"] > o["max_duration"] + 0.05:
        print(f"warn  --max-duration {o['max_duration']} s cannot hold: entrances alone need {tl['floor']} s; "
              "cut slides or raise the cap")
    print(f"capture: {tl['frames']} frames ({tl['duration']:.2f} s), {cap['rendered_frames']} rendered, "
          f"the rest reused, {cap['seconds']} s")
    with tempfile.TemporaryDirectory(prefix="animate-qa-") as td:
        tmp = Path(td)
        expect = {"width": canvas[0], "height": canvas[1], "fps": o["fps"], "frames": tl["frames"],
                  "duration": tl["duration"], "audio": bool(music)}
        qa = check_video(mp4, expect, tmp)
        if place["scale"] < 1:
            px = MIN_TEXT_PX * place["scale"]
            qa["warnings"].append({"code": "scaled-slide", "message": f"slide shown at {place['scale']:.0%}: the smallest text is "
                                   f"{px:.0f} px on the canvas instead of {MIN_TEXT_PX}"})
        sheet_name = sheet(mp4, tl, o["fps"], export / f"video-{tag(aspect)}-frames.jpg", tmp,
                           max_tiles=o.get("sheet_tiles") or 0) if qa["probe"].get("frames") else None
    report = {
        "deck": str(deck_path), "aspect": aspect, "width": canvas[0], "height": canvas[1], "fps": o["fps"],
        "slide": {"width": slide_size[0], "height": slide_size[1]}, "placement": dict(place, safe=safe_name),
        "timing": dict({k: o.get(k) for k in ("wpm", "orient", "min_slide", "max_slide", "max_first", "max_duration",
                                               "transition", "settle", "end_hold")}, squeeze=tl.get("squeeze")),
        "music": str(music) if music else None, "video": mp4.name, "frames_sheet": sheet_name,
        "duration": tl["duration"], "frames": tl["frames"], "rendered_frames": cap["rendered_frames"],
        "seconds": cap["seconds"], "forced_fit_failures": cap.get("fit_failures") or [],
        "slides": tl["slides"], "qa": qa,
    }
    (export / f"video-{tag(aspect)}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for e in qa["errors"]:
        print(f"ERROR video {e['code']}: {e['message']}")
    for w in qa["warnings"]:
        print(f"warn  video {w['code']}: {w['message']}")
    pr = qa.get("probe", {})
    print(f"video qa: {qa['status'].upper()}, {pr.get('width')}x{pr.get('height')} {pr.get('fps')} fps "
          f"{pr.get('duration')} s {pr.get('size_bytes', 0) / 1e6:.1f} MB -> {mp4}")
    if sheet_name:
        print(f"frames sheet: {export / sheet_name}")
    return 0 if qa["status"] == "pass" else 1


DEFAULTS: Dict[str, Any] = {
    "fps": 30, "wpm": 200.0, "orient": 1.0, "min_slide": 3.0, "max_slide": 8.0, "max_first": 5.0,
    "max_duration": None, "transition": 0.5,
    "settle": 1.0, "end_hold": 1.0, "safe": "auto", "animate_cover": False, "slides": None,
    "music": None, "music_volume": 1.0, "fade_out": 2.0, "crf": 18, "preset": "medium", "build": True, "force": False,
    "keep_frames": None, "sheet_tiles": 0,
}

QUICK = {"slides": "1-3", "min_slide": 1.0, "max_slide": 2.0, "max_first": 1.0, "end_hold": 0.3, "settle": 0.4,
         "preset": "veryfast"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", help="deck.json")
    ap.add_argument("--check", metavar="MP4", help="QA an existing video only (no render)")
    ap.add_argument("--out", help="Output folder (default: the deck folder); the video goes to OUT/export")
    ap.add_argument("--aspect", choices=list(ASPECTS), help="Canvas ratio (default: the deck's own, 4:5 for linkedin and instagram)")
    ap.add_argument("--direction")
    ap.add_argument("--brand")
    ap.add_argument("--safe", choices=["auto"] + list(SAFE), help="Safe box (default auto: reels for 9:16, none otherwise)")
    ap.add_argument("--fps", type=int, help="Frames per second (default 30)")
    ap.add_argument("--wpm", type=float, help="Reading speed in words a minute (default 200)")
    ap.add_argument("--min-slide", type=float, help="Shortest slide in seconds (default 3)")
    ap.add_argument("--max-slide", type=float, help="Longest reading time per slide in seconds (default 8)")
    ap.add_argument("--max-first", type=float, help="Longest hold of the first slide in seconds (default 5)")
    ap.add_argument("--max-duration", type=float, help="Fit the video in N seconds by shortening holds (default: no cap)")
    ap.add_argument("--transition", type=float, help="Crossfade between slides in seconds (default 0.5)")
    ap.add_argument("--slides", help="Subset, for example 1-3,5 (default: all)")
    ap.add_argument("--animate-cover", action="store_true", help="Animate the first slide too (frame 0 then shows its ground only)")
    ap.add_argument("--music", help="Local audio file mixed under the video, faded out at the end")
    ap.add_argument("--music-volume", type=float, help="Gain on the music (default 1.0)")
    ap.add_argument("--fade-out", type=float, help="Music fade out in seconds (default 2)")
    ap.add_argument("--crf", type=int, help="x264 quality, lower is better (default 18)")
    ap.add_argument("--preset", choices=["ultrafast", "veryfast", "fast", "medium", "slow"], help="x264 speed preset (default medium)")
    ap.add_argument("--no-build", action="store_true", help="Reuse OUT/html as built (by pipeline.py)")
    ap.add_argument("--force", action="store_true", help="Render even with spec errors or fit failures")
    ap.add_argument("--keep-frames", metavar="DIR", help="Also write every PNG frame to DIR")
    ap.add_argument("--sheet-tiles", type=int, help="Keep N tiles on the frames sheet (default: two per slide)")
    ap.add_argument("--quick", action="store_true", help="Smoke test: slides 1-3, short holds, fast x264 preset")
    args = ap.parse_args()
    try:
        if args.check:
            need_tools()
            p = Path(args.check).resolve()
            expect: Dict[str, Any] = {"fps": args.fps or DEFAULTS["fps"]}
            if args.aspect:
                expect["width"], expect["height"] = ASPECTS[args.aspect]
            with tempfile.TemporaryDirectory(prefix="animate-qa-") as td:
                qa = check_video(p, expect, Path(td))
            print(json.dumps(qa, indent=2, ensure_ascii=False))
            return 0 if qa["status"] == "pass" else 1
        if not args.deck:
            ap.error("deck.json required (or --check FILE)")
        deck_path = Path(args.deck).resolve()
        if not deck_path.is_file():
            raise Fatal(f"no such deck: {deck_path}")
        out_dir = Path(args.out).resolve() if args.out else deck_path.parent
        opts: Dict[str, Any] = dict(QUICK) if args.quick else {}
        for k in ("fps", "wpm", "min_slide", "max_slide", "max_first", "max_duration", "transition", "slides", "music", "music_volume", "fade_out",
                  "crf", "preset", "safe", "keep_frames", "sheet_tiles"):
            val = getattr(args, k)
            if val is not None:
                opts[k] = val
        opts["animate_cover"] = args.animate_cover
        opts["build"] = not args.no_build
        opts["force"] = args.force
        return run(deck_path, out_dir, args.aspect, args.direction, args.brand, opts)
    except Fatal as e:
        print(f"animate: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
