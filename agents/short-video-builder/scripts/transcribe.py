#!/usr/bin/env python3
"""transcribe.py: word-level transcript of a talk, written as words.json.

    python3 scripts/transcribe.py SOURCE --out RUN/words.json [--engine auto] [--model medium]
                                  [--language fr] [--prompt "Proper Nouns, Product"]
    python3 scripts/transcribe.py SOURCE --out RUN/words.json --transcript talk.srt

Engines, all local and free (capability `transcription`):

  faster-whisper   Python package faster-whisper; word timestamps, voice activity
                   filter, per-word probability (used by proofread.py to flag doubts).
  whisper-cpp      whisper.cpp binary (whisper-cli, whisper-cpp or main) and a ggml
                   model file: --whisper-cpp-model PATH or WHISPER_CPP_MODEL.
  openai-whisper   the `whisper` command of the openai-whisper package.
  import           a transcript the founder already has: SRT, WebVTT or JSON
                   (this stack's words.json, a list of words, Whisper JSON with
                   segments, whisper.cpp JSON). Cue-level files get word timings
                   estimated by character length ("timing": "estimated"); WebVTT
                   files with inline word timestamps keep them.

--engine auto takes --transcript when given, else the first engine installed in
the order above. --prompt primes the model with names it would mangle (speaker,
company, product): read them from project-context first.

Exit codes: 0 words.json written; 2 fatal (unreadable source or transcript,
engine crash); 3 no engine installed and no --transcript (capability
unavailable: ask the founder for a transcript, or install faster-whisper).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXIT_FATAL, EXIT_UNAVAILABLE, die, probe, write_json  # noqa: E402

WHISPER_CPP_BINARIES = ("whisper-cli", "whisper-cpp", "main")
NOISE_RE = re.compile(r"^\[.*\]$|^\(.*\)$")  # [BLANK_AUDIO], (music), [Applause]


# ---------------------------------------------------------------- helpers

def spread(text: str, t0: float, t1: float) -> List[Dict[str, Any]]:
    """Cue-level text -> words, the cue window shared by character length."""
    toks = [t for t in text.split() if t]
    if not toks:
        return []
    span = max(t1 - t0, 0.01)
    weights = [max(len(t), 1) + 1 for t in toks]  # +1: the space, so short words keep some time
    total = float(sum(weights))
    out, acc = [], 0.0
    for tok, wt in zip(toks, weights):
        s = t0 + span * acc / total
        acc += wt
        e = t0 + span * acc / total
        out.append({"word": tok, "start": round(s, 3), "end": round(e, 3)})
    return out


def clean_cue_text(text: str) -> str:
    text = re.sub(r"\{\\[^}]*\}", "", text)          # SRT/ASS override tags {\an8}
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)      # <i>, <b>, <c.color>
    text = html.unescape(text)
    return " ".join(text.split())


def ts_seconds(s: str) -> float:
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


# ---------------------------------------------------------------- importers

SRT_TIME = re.compile(r"(\d+:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{1,3})")
VTT_TIME = re.compile(r"((?:\d+:)?\d{2}:\d{2}\.\d{1,3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}\.\d{1,3})")
VTT_INLINE = re.compile(r"<((?:\d+:)?\d{2}:\d{2}\.\d{1,3})>")


def parse_srt(text: str) -> Tuple[List[Dict[str, Any]], str]:
    words: List[Dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.strip().split("\n")
        for k, line in enumerate(lines):
            m = SRT_TIME.search(line)
            if m:
                body = clean_cue_text(" ".join(lines[k + 1:]))
                if body and not NOISE_RE.match(body):
                    words += spread(body, ts_seconds(m.group(1)), ts_seconds(m.group(2)))
                break
    return words, "estimated"


def parse_vtt(text: str) -> Tuple[List[Dict[str, Any]], str]:
    words: List[Dict[str, Any]] = []
    timing = "estimated"
    seen_inline = False
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.strip().split("\n")
        if lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        for k, line in enumerate(lines):
            m = VTT_TIME.search(line)
            if not m:
                continue
            t0, t1 = ts_seconds(m.group(1)), ts_seconds(m.group(2))
            raw = " ".join(lines[k + 1:])
            if VTT_INLINE.search(raw):
                # <00:00:01.200><c> word</c>: each tag opens the next word.
                seen_inline = True
                pieces = VTT_INLINE.split(raw)
                cur_t = t0
                stamped: List[Tuple[float, str]] = []
                head = clean_cue_text(pieces[0])
                if head:
                    stamped.append((t0, head))
                for i in range(1, len(pieces), 2):
                    cur_t = ts_seconds(pieces[i])
                    body = clean_cue_text(pieces[i + 1] if i + 1 < len(pieces) else "")
                    if body:
                        stamped.append((cur_t, body))
                for j, (ts, body) in enumerate(stamped):
                    nxt = stamped[j + 1][0] if j + 1 < len(stamped) else t1
                    words += spread(body, ts, max(nxt, ts + 0.05))
            else:
                body = clean_cue_text(raw)
                if body and not NOISE_RE.match(body):
                    if words and body == " ".join(w["word"] for w in words[-len(body.split()):]):
                        break  # rolling captions repeat the previous line
                    words += spread(body, t0, t1)
            break
    if seen_inline:
        timing = "word"
    return words, timing


def parse_json_transcript(data: Any) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    """Accepts the shapes listed in the module docstring. Returns (words, timing, meta)."""
    meta: Dict[str, Any] = {}
    if isinstance(data, dict) and isinstance(data.get("words"), list):
        meta = {k: data.get(k) for k in ("language", "engine", "model") if data.get(k)}
        return [dict(w) for w in data["words"]], data.get("timing", "word"), meta
    if isinstance(data, list) and data and isinstance(data[0], dict) and "word" in data[0]:
        return [dict(w) for w in data], "word", meta
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        words: List[Dict[str, Any]] = []
        timing = "word"
        for seg in data["segments"]:
            if seg.get("words"):
                for w in seg["words"]:
                    item = {"word": str(w.get("word", w.get("text", ""))).strip(),
                            "start": float(w["start"]), "end": float(w["end"])}
                    if w.get("probability") is not None:
                        item["prob"] = round(float(w["probability"]), 3)
                    if item["word"]:
                        words.append(item)
            else:
                timing = "estimated"
                words += spread(str(seg.get("text", "")).strip(), float(seg["start"]), float(seg["end"]))
        if data.get("language"):
            meta["language"] = data["language"]
        return words, timing, meta
    if isinstance(data, dict) and isinstance(data.get("transcription"), list):
        words = []
        single = True
        for seg in data["transcription"]:
            text = str(seg.get("text", "")).strip()
            off = seg.get("offsets") or {}
            if not text or NOISE_RE.match(text):
                continue
            t0, t1 = float(off.get("from", 0)) / 1000.0, float(off.get("to", 0)) / 1000.0
            if len(text.split()) > 1:
                single = False
            words += spread(text, t0, t1)
        lang = (data.get("result") or {}).get("language")
        if lang:
            meta["language"] = lang
        return words, "word" if single else "estimated", meta
    die("unrecognised JSON transcript: expected words.json, a list of {word,start,end}, "
        "Whisper JSON with segments, or whisper.cpp JSON with transcription")
    return [], "", meta


def import_transcript(path: Path) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        die(f"cannot read transcript {path}: {e}")
    ext = path.suffix.lower()
    if ext == ".json":
        try:
            return parse_json_transcript(json.loads(text))
        except json.JSONDecodeError as e:
            die(f"{path} is not valid JSON: {e.msg}")
    if ext == ".vtt" or text.lstrip().startswith("WEBVTT"):
        w, t = parse_vtt(text)
        return w, t, {"format": "vtt"}
    if ext == ".srt" or SRT_TIME.search(text):
        w, t = parse_srt(text)
        return w, t, {"format": "srt"}
    die(f"{path}: unknown transcript format (use .srt, .vtt or .json)")
    return [], "", {}


# ---------------------------------------------------------------- engines

def extract_audio(source: Path, tmp: Path) -> Path:
    wav = tmp / "audio16k.wav"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"ffmpeg could not extract audio from {source}: {r.stderr.strip()[:200]}")
    return wav


def has_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def whisper_cpp_binary() -> Optional[str]:
    for name in WHISPER_CPP_BINARIES:
        p = shutil.which(name)
        if p and name != "main":
            return p
        if p and name == "main" and os.environ.get("WHISPER_CPP_MODEL"):
            return p  # a bare `main` is only trusted when a ggml model is configured
    return None


def run_faster_whisper(wav: Path, model: str, language: Optional[str], prompt: Optional[str]):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segments, info = m.transcribe(str(wav), language=language, word_timestamps=True, initial_prompt=prompt,
                                  vad_filter=True, vad_parameters=dict(min_silence_duration_ms=400))
    words = []
    for seg in segments:
        for w in seg.words or []:
            t = w.word.strip()
            if t:
                words.append({"word": t, "start": round(w.start, 3), "end": round(w.end, 3),
                              "prob": round(float(w.probability), 3)})
        print(f"[{seg.start:7.1f}] {seg.text.strip()}", file=sys.stderr)
    return words, "word", {"language": info.language}


def run_whisper_cpp(binary: str, wav: Path, model_path: str, language: Optional[str], prompt: Optional[str], tmp: Path):
    if not model_path or not Path(model_path).exists():
        die("whisper.cpp needs a ggml model: --whisper-cpp-model PATH or WHISPER_CPP_MODEL", EXIT_UNAVAILABLE)
    base = tmp / "wcpp"
    cmd = [binary, "-m", model_path, "-f", str(wav), "-oj", "-of", str(base), "-ml", "1", "-sow"]
    if language:
        cmd += ["-l", language]
    if prompt:
        cmd += ["--prompt", prompt]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not (base.with_suffix(".json")).exists():
        die(f"whisper.cpp failed: {(r.stderr or '').strip()[-300:]}")
    return parse_json_transcript(json.loads(base.with_suffix(".json").read_text(encoding="utf-8")))


def run_openai_whisper(wav: Path, model: str, language: Optional[str], prompt: Optional[str], tmp: Path):
    cmd = ["whisper", str(wav), "--model", model, "--word_timestamps", "True", "--output_format", "json",
           "--output_dir", str(tmp), "--fp16", "False"]
    if language:
        cmd += ["--language", language]
    if prompt:
        cmd += ["--initial_prompt", prompt]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = tmp / (wav.stem + ".json")
    if r.returncode != 0 or not out.exists():
        die(f"openai-whisper failed: {(r.stderr or '').strip()[-300:]}")
    return parse_json_transcript(json.loads(out.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- main

def tidy(words: List[Dict[str, Any]], duration: Optional[float]) -> List[Dict[str, Any]]:
    """Sorted, non-overlapping, inside the source."""
    out = []
    for w in sorted(words, key=lambda x: (float(x["start"]), float(x["end"]))):
        s, e = float(w["start"]), float(w["end"])
        if duration:
            s, e = min(s, duration), min(e, duration)
        if out and s < out[-1]["end"]:
            s = out[-1]["end"]
        if e <= s:
            e = s + 0.02
        item = {"word": str(w["word"]).strip(), "start": round(s, 3), "end": round(e, 3)}
        if "prob" in w:
            item["prob"] = w["prob"]
        if item["word"]:
            out.append(item)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="The landscape video (or its audio). Needed for duration; may be omitted with --transcript.", nargs="?")
    ap.add_argument("--out", required=True, help="Path of the words.json to write")
    ap.add_argument("--engine", default="auto", choices=["auto", "faster-whisper", "whisper-cpp", "openai-whisper", "import"])
    ap.add_argument("--transcript", help="SRT, VTT or JSON transcript to import instead of transcribing")
    ap.add_argument("--model", default="medium", help="Whisper model size for faster-whisper and openai-whisper (default medium)")
    ap.add_argument("--whisper-cpp-model", default=os.environ.get("WHISPER_CPP_MODEL", ""), help="ggml model file for whisper.cpp")
    ap.add_argument("--language", help="Language code (fr, en...). Auto-detected when absent.")
    ap.add_argument("--prompt", help="Initial prompt: speaker, company and product names spelled right")
    args = ap.parse_args()

    source = Path(args.source).resolve() if args.source else None
    info = probe(source) if source else {}
    if source and not info.get("has_audio") and not args.transcript:
        die(f"{source} has no audio stream to transcribe")
    duration = info.get("duration") or None

    engine = args.engine
    if engine == "auto":
        if args.transcript:
            engine = "import"
        elif has_faster_whisper():
            engine = "faster-whisper"
        elif whisper_cpp_binary() and args.whisper_cpp_model:
            engine = "whisper-cpp"
        elif shutil.which("whisper"):
            engine = "openai-whisper"
        else:
            die("no local transcription engine (faster-whisper, whisper.cpp, openai-whisper) and no --transcript. "
                "Install one (pip install faster-whisper) or ask the founder for an SRT/VTT/JSON transcript.",
                EXIT_UNAVAILABLE)
    if engine == "import" and not args.transcript:
        die("--engine import needs --transcript FILE", EXIT_FATAL)
    if engine != "import" and not source:
        die("a SOURCE video is needed to transcribe", EXIT_FATAL)

    meta: Dict[str, Any] = {}
    model = None
    if engine == "import":
        words, timing, meta = import_transcript(Path(args.transcript))
        engine_label = f"import:{meta.get('format') or Path(args.transcript).suffix.lstrip('.').lower() or 'json'}"
    else:
        if not shutil.which("ffmpeg"):
            die("ffmpeg not found on PATH")
        with tempfile.TemporaryDirectory(prefix="svb-asr-") as td:
            tmp = Path(td)
            wav = extract_audio(source, tmp)
            if engine == "faster-whisper":
                if not has_faster_whisper():
                    die("faster-whisper is not installed (pip install faster-whisper)", EXIT_UNAVAILABLE)
                words, timing, meta = run_faster_whisper(wav, args.model, args.language, args.prompt)
                model = args.model
            elif engine == "whisper-cpp":
                binary = whisper_cpp_binary()
                if not binary:
                    die("whisper.cpp binary not found (whisper-cli)", EXIT_UNAVAILABLE)
                words, timing, meta = run_whisper_cpp(binary, wav, args.whisper_cpp_model, args.language, args.prompt, tmp)
                model = Path(args.whisper_cpp_model).name
            else:
                if not shutil.which("whisper"):
                    die("the openai-whisper `whisper` command is not installed", EXIT_UNAVAILABLE)
                words, timing, meta = run_openai_whisper(wav, args.model, args.language, args.prompt, tmp)
                model = args.model
        engine_label = engine

    words = tidy(words, duration)
    if not words:
        die("the transcript holds no words")
    out = Path(args.out)
    doc = {
        "version": 1,
        "source": source.name if source else None,
        "duration": round(duration, 3) if duration else round(words[-1]["end"], 3),
        "language": args.language or meta.get("language"),
        "engine": engine_label,
        "model": model,
        "timing": timing,
        "prompt": args.prompt,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "words": words,
    }
    write_json(out, doc)
    note = " (word timings estimated from cues: karaoke sync is approximate)" if timing == "estimated" else ""
    print(f"transcribe: {len(words)} words, {engine_label}, timing {timing}{note} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
