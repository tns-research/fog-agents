"""common.py: helpers shared by the short-video-builder scripts.

Probing (ffprobe), output frame rate, time parsing, hashing, JSON I/O, word
normalisation and the exit codes every script documents:

    0  done, every check passed
    1  a check failed (spec errors, QA errors, a gate not satisfied)
    2  fatal (unreadable input, ffmpeg or a Python module missing)
    3  capability unavailable (no local transcription engine and no transcript)

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

EXIT_OK = 0
EXIT_CHECK = 1
EXIT_FATAL = 2
EXIT_UNAVAILABLE = 3

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent.parent
SHARED = REPO / "shared"

# Output canvas of every short: 9:16 at 1080 wide.
OUT_W = 1080
OUT_H = 1920

# Frame rates a variable-frame-rate source is snapped to (NTSC and PAL families).
STANDARD_RATES = ["24000/1001", "24/1", "25/1", "30000/1001", "30/1", "50/1", "60000/1001", "60/1"]

# Above this rate the output is halved cleanly (120 -> 60, 100 -> 50): social
# players do not show more, and an exact halving never drops frames unevenly.
MAX_OUT_FPS = 60.5

SENTENCE_END = (".", "?", "!", "…")
PUNCT = ".,!?;:\"()[]{}«»“”…-"


def die(msg: str, code: int = EXIT_FATAL) -> None:
    prog = Path(sys.argv[0]).name
    print(f"{prog}: {msg}", file=sys.stderr)
    sys.exit(code)


def need_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"{name} not found on PATH. Install ffmpeg (apt install ffmpeg, brew install ffmpeg).")
    return path


def run(cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if check and r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-6:]
        die(f"command failed ({cmd[0]} exit {r.returncode}): " + " | ".join(tail))
    return r


def load_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"file not found: {path}")
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: line {e.lineno}: {e.msg}")


def write_json(path: Path, data: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- time

TIME_RE = re.compile(r"^\d+(?::\d{1,2}){0,2}(?:\.\d+)?$")


def parse_time(v: Any) -> float:
    """Seconds from 12.5, "12.5", "1:02.5" or "1:01:02". Raises ValueError."""
    if isinstance(v, bool):
        raise ValueError(f"not a time: {v!r}")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not TIME_RE.match(s):
        raise ValueError(f"not a time: {v!r} (use seconds or M:SS.s)")
    total = 0.0
    for part in s.split(":"):
        total = total * 60 + float(part)
    return total


def fmt_time(s: float) -> str:
    s = max(0.0, s)
    m = int(s // 60)
    return f"{m}:{s - 60 * m:05.2f}"


# ---------------------------------------------------------------- probing

def _frac(s: Optional[str]) -> Fraction:
    try:
        f = Fraction(str(s))
        return f if f > 0 else Fraction(0)
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def probe(path: Path) -> Dict[str, Any]:
    """Video and audio facts of a media file (ffprobe)."""
    need_binary("ffprobe")
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], check=False)
    if r.returncode != 0:
        die(f"ffprobe cannot read {path}: {(r.stderr or '').strip()[:200]}")
    data = json.loads(r.stdout or "{}")
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    out: Dict[str, Any] = {
        "path": str(path),
        "duration": float(fmt.get("duration") or 0.0),
        "has_video": v is not None,
        "has_audio": a is not None,
    }
    if v:
        out.update({
            "width": int(v.get("width") or 0),
            "height": int(v.get("height") or 0),
            "codec": v.get("codec_name"),
            "pix_fmt": v.get("pix_fmt"),
            "r_frame_rate": v.get("r_frame_rate"),
            "avg_frame_rate": v.get("avg_frame_rate"),
            "fps": float(_frac(v.get("r_frame_rate"))),
            "avg_fps": float(_frac(v.get("avg_frame_rate"))),
            "nb_frames": int(v["nb_frames"]) if str(v.get("nb_frames", "")).isdigit() else None,
        })
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = rot or int((v.get("tags") or {}).get("rotate", 0) or 0)
        if abs(rot) in (90, 270):
            out["width"], out["height"] = out["height"], out["width"]
        out["rotation"] = rot
    if a:
        out.update({
            "audio_codec": a.get("codec_name"),
            "sample_rate": int(a.get("sample_rate") or 0),
            "channels": int(a.get("channels") or 0),
        })
    return out


def output_fps(info: Dict[str, Any]) -> Tuple[str, float, str]:
    """Frame rate of the short, as (ffmpeg rational, float, note).

    The output keeps the source frame rate. Resampling to another rate (the
    classic 50 -> 30) drops or repeats frames on an uneven cadence, which reads
    as judder the moment the crop pans. Only two adjustments are allowed: an
    exact halving above 60 fps, and snapping a variable-frame-rate phone file to
    the nearest standard rate of its average.
    """
    r = _frac(info.get("r_frame_rate"))
    a = _frac(info.get("avg_frame_rate"))
    if r == 0 and a == 0:
        return "30/1", 30.0, "no frame rate in the source, 30 used"
    if r == 0:
        r = a
    constant = a == 0 or abs(float(r - a)) / float(r) < 0.05
    if constant:
        note = "source rate kept"
        while float(r) > MAX_OUT_FPS:
            r = r / 2
            note = "source rate halved exactly (above 60 fps)"
        return f"{r.numerator}/{r.denominator}", float(r), note
    best = min(STANDARD_RATES, key=lambda s: abs(float(Fraction(s)) - float(a)))
    f = Fraction(best)
    while float(f) > MAX_OUT_FPS:
        f = f / 2
    return f"{f.numerator}/{f.denominator}", float(f), f"variable frame rate source (average {float(a):.3f}), snapped to {best}"


# ---------------------------------------------------------------- words

def norm_token(w: str) -> str:
    """Lowercase core of a word for matching: outer punctuation off, inner apostrophes kept."""
    w = w.strip().replace("’", "'").strip(PUNCT).lower()
    return w


def tokens_of(text: str) -> List[str]:
    return [t for t in (norm_token(x) for x in text.split()) if t]


def is_elision_tail(word: str) -> bool:
    """Whisper splits French elisions in two tokens ("l" + "'IA"): the second one starts with an apostrophe."""
    return word.strip()[:1] in ("'", "’")


def ends_sentence(word: str) -> bool:
    return word.strip().rstrip("\"”»)").endswith(SENTENCE_END)


def load_words(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if isinstance(data, list):
        data = {"words": data}
    words = data.get("words")
    if not isinstance(words, list) or not words:
        die(f"{path}: no words (expected the words.json written by transcribe.py)")
    for i, w in enumerate(words):
        if not isinstance(w, dict) or not isinstance(w.get("word"), str) \
                or not isinstance(w.get("start"), (int, float)) or not isinstance(w.get("end"), (int, float)):
            die(f"{path}: word {i} needs word, start and end")
    return data


def rel_or_abs(base: Path, p: str) -> Path:
    q = Path(os.path.expanduser(p))
    return q if q.is_absolute() else (base / q).resolve()


def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ass_color(h: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR (byte-reversed, alpha 00 = opaque)."""
    r, g, b = hex_to_rgb(h)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ffmpeg_color(h: str) -> str:
    r, g, b = hex_to_rgb(h)
    return f"0x{r:02X}{g:02X}{b:02X}"
