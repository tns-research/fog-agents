#!/usr/bin/env python3
"""proofread.py: the full-transcript proofreading gate, before any render.

A transcription model mishears ordinary words, not only names ("raise your hand"
heard as "raisin hand", a brand split in two, a figure off by a zero). On screen,
a wrong caption disqualifies the short as surely as a mangled company name. So
the whole transcript is read, fixed and signed before the first render, and the
renderer refuses a transcript that changed after the signature.

    python3 scripts/proofread.py dump   RUN/words.json [--page N | --all] [--page-size 400]
    python3 scripts/proofread.py apply  RUN/words.json RUN/corrections.json
    python3 scripts/proofread.py sign   RUN/words.json [--reviewer model|founder] [--note TEXT]
    python3 scripts/proofread.py status RUN/words.json

dump    prints the transcript page by page: word indexes, times, and a "check
        first" list per page (numbers, capitalised words that may be names or
        acronyms, words the model was unsure of). Every page printed is recorded
        in proofread-progress.json; sign refuses until every word was printed.
apply   applies corrections.json to the pristine transcript (words.raw.json,
        snapshotted on the first apply), so re-running never applies twice.
        Each correction is either
          {"find": "raisin hand", "replace": "raise your hand", "occurrence": "all", "why": "..."}
        or {"i": 41, "j": 42, "text": "raise your hand", "why": "..."}
        (inclusive word indexes of the raw transcript). The span's time window is
        shared between the new words by character length, so the karaoke
        highlight stays in sync when the word count changes; an empty text
        deletes the span. Trailing punctuation of the span is kept when the
        replacement has none. A find that matches nothing, or two corrections
        that overlap, fail the whole file and nothing is written.
sign    writes proofread.json with the hash of the corrected words.json.
status  exit 0 when the signature matches the current words.json.

Exit codes: 0 done; 1 gate not satisfied (pages not read, signature missing or
stale, a correction that does not apply); 2 unreadable file.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EXIT_CHECK, PUNCT, die, ends_sentence, fmt_time, load_json, load_words,  # noqa: E402
                    norm_token, sha256_file, tokens_of, write_json)

LOW_PROB = 0.5   # faster-whisper word probability under which a word is listed to check
NUMBER_WORDS = {
    # en
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "fifteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "millions", "billion", "billions", "percent",
    # fr
    "deux", "trois", "quatre", "cinq", "sept", "huit", "neuf", "dix", "onze", "douze", "quinze", "vingt",
    "trente", "quarante", "cinquante", "soixante", "cent", "cents", "mille", "milliard", "milliards", "pourcent",
}


def paths(words_path: Path) -> Dict[str, Path]:
    d = words_path.parent
    return {"raw": words_path.with_name(words_path.stem + ".raw.json"),
            "progress": d / "proofread-progress.json",
            "signature": d / "proofread.json"}


def transcript_id(words_path: Path) -> str:
    raw = paths(words_path)["raw"]
    return sha256_file(raw if raw.exists() else words_path)


# ---------------------------------------------------------------- dump

def flags_for(words: List[Dict[str, Any]], i: int) -> List[str]:
    w = words[i]
    tok = w["word"].strip()
    core = tok.strip(PUNCT)
    out = []
    if re.search(r"\d", core) or norm_token(core) in NUMBER_WORDS:
        out.append("number")
    prev_ends = i == 0 or ends_sentence(words[i - 1]["word"])
    if core[:1].isupper() and not prev_ends and core.lower() not in ("i", "i'm", "i've", "i'll", "i'd"):
        out.append("name?")
    elif len(core) >= 2 and core.isupper():
        out.append("acronym?")
    if isinstance(w.get("prob"), (int, float)) and w["prob"] < LOW_PROB:
        out.append(f"unsure {w['prob']:.2f}")
    return out


def cmd_dump(args) -> int:
    path = Path(args.words)
    doc = load_words(path)
    words = doc["words"]
    n = len(words)
    size = max(50, args.page_size)
    pages = (n + size - 1) // size
    if args.all:
        wanted = list(range(1, pages + 1))
    else:
        p = args.page or 1
        if p < 1 or p > pages:
            die(f"page {p} out of range 1..{pages}", EXIT_CHECK)
        wanted = [p]
    p_paths = paths(path)
    tid = transcript_id(path)
    prog = load_json(p_paths["progress"]) if p_paths["progress"].exists() else {}
    if prog.get("transcript_id") != tid:
        prog = {"transcript_id": tid, "words": n, "ranges": []}
    for p in wanted:
        a, b = (p - 1) * size, min(n, p * size) - 1
        print(f"## Page {p}/{pages}: words {a}-{b}, {fmt_time(words[a]['start'])}-{fmt_time(words[b]['end'])}")
        for row in range(a, b + 1, 10):
            chunk = range(row, min(row + 10, b + 1))
            print(f"[{row:05d} {fmt_time(words[row]['start'])}] " + " ".join(words[k]["word"] for k in chunk))
        checks = [(k, flags_for(words, k)) for k in range(a, b + 1)]
        checks = [(k, f) for k, f in checks if f]
        print("\nCheck first on this page (then read every line above):")
        if not checks:
            print("  (nothing flagged)")
        for k, f in checks:
            ctx = " ".join(x["word"] for x in words[max(0, k - 3):k + 4])
            print(f"  [{k}] {words[k]['word']!r:20} {', '.join(f):18} ... {ctx} ...")
        print()
        prog["ranges"].append([a, b])
    write_json(p_paths["progress"], prog)
    left = uncovered(prog["ranges"], n)
    if left:
        print(f"progress: {n - len(left)}/{n} words printed; next: --page {(left[0] // size) + 1}")
    else:
        print(f"progress: all {n} words printed. Write corrections.json, run apply, then sign.")
    return 0


def uncovered(ranges: List[List[int]], n: int) -> List[int]:
    seen = [False] * n
    for a, b in ranges:
        for k in range(max(0, a), min(n - 1, b) + 1):
            seen[k] = True
    return [k for k, s in enumerate(seen) if not s]


# ---------------------------------------------------------------- apply

def redistribute(t0: float, t1: float, toks: List[str]) -> List[Dict[str, Any]]:
    span = max(t1 - t0, 0.01)
    weights = [max(len(t), 1) + 1 for t in toks]
    total = float(sum(weights))
    out, acc = [], 0.0
    for t, wt in zip(toks, weights):
        s = t0 + span * acc / total
        acc += wt
        out.append({"word": t, "start": round(s, 3), "end": round(t0 + span * acc / total, 3), "fixed": True})
    return out


def find_spans(words: List[Dict[str, Any]], find: str) -> List[Tuple[int, int]]:
    target = tokens_of(find)
    if not target:
        return []
    toks = [norm_token(w["word"]) for w in words]
    out = []
    for i in range(len(toks) - len(target) + 1):
        if toks[i:i + len(target)] == target:
            out.append((i, i + len(target) - 1))
    return out


def resolve_corrections(words: List[Dict[str, Any]], corrs: List[Dict[str, Any]]) -> Tuple[List[Tuple[int, int, str]], List[str]]:
    spans: List[Tuple[int, int, str]] = []
    errors: List[str] = []
    for k, c in enumerate(corrs):
        if not isinstance(c, dict):
            errors.append(f"correction {k}: not an object")
            continue
        if "find" in c:
            hits = find_spans(words, str(c["find"]))
            if not hits:
                errors.append(f"correction {k}: find {c['find']!r} matches nothing in the raw transcript")
                continue
            occ = c.get("occurrence", "all")
            if occ != "all":
                if not isinstance(occ, int) or occ < 1 or occ > len(hits):
                    errors.append(f"correction {k}: occurrence {occ!r} out of 1..{len(hits)}")
                    continue
                hits = [hits[occ - 1]]
            for i, j in hits:
                spans.append((i, j, str(c.get("replace", ""))))
        elif "i" in c and "j" in c:
            i, j = c["i"], c["j"]
            if not (isinstance(i, int) and isinstance(j, int) and 0 <= i <= j < len(words)):
                errors.append(f"correction {k}: i/j out of range 0..{len(words) - 1}")
                continue
            spans.append((i, j, str(c.get("text", ""))))
        else:
            errors.append(f"correction {k}: needs find/replace or i/j/text")
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if b[0] <= a[1]:
            errors.append(f"corrections overlap on words {b[0]}-{a[1]}")
    return spans, errors


def cmd_apply(args) -> int:
    path = Path(args.words)
    p_paths = paths(path)
    if not p_paths["raw"].exists():
        shutil.copyfile(path, p_paths["raw"])
    raw = load_words(p_paths["raw"])
    words = [dict(w) for w in raw["words"]]
    corrs = load_json(Path(args.corrections))
    if isinstance(corrs, dict):
        corrs = corrs.get("corrections", [])
    spans, errors = resolve_corrections(words, corrs)
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        print("apply: nothing written", file=sys.stderr)
        return EXIT_CHECK
    for i, j, text in reversed(spans):
        toks = text.split()
        tail = words[j]["word"].strip()
        trail = tail[len(tail.rstrip(PUNCT)):]
        if toks and trail and toks[-1] == toks[-1].rstrip(PUNCT):
            toks[-1] += trail
        words[i:j + 1] = redistribute(words[i]["start"], words[j]["end"], toks) if toks else []
    doc = dict(raw)
    doc["words"] = words
    doc["corrections_applied"] = len(spans)
    write_json(path, doc)
    sig = p_paths["signature"]
    if sig.exists():
        sig.unlink()  # the transcript changed: the signature no longer holds
    print(f"apply: {len(spans)} span(s) corrected from {len(corrs)} correction(s), {len(words)} words -> {path}")
    return 0


# ---------------------------------------------------------------- sign / status

def gate(words_path: Path) -> Tuple[bool, str]:
    """(ok, reason) for the renderer: signed, and words.json unchanged since."""
    sig = paths(words_path)["signature"]
    if not sig.exists():
        return False, "transcript not proofread: run proofread.py dump (every page), apply, sign"
    data = load_json(sig)
    if data.get("words_sha256") != sha256_file(words_path):
        return False, "words.json changed after the proofread signature: read the changes and sign again"
    return True, f"proofread by {data.get('reviewer')} on {data.get('signed_at')}, {data.get('corrections_applied', 0)} correction(s)"


def cmd_sign(args) -> int:
    path = Path(args.words)
    doc = load_words(path)
    p_paths = paths(path)
    raw_n = len(load_words(p_paths["raw"])["words"]) if p_paths["raw"].exists() else len(doc["words"])
    prog = load_json(p_paths["progress"]) if p_paths["progress"].exists() else {}
    if prog.get("transcript_id") != transcript_id(path):
        print("sign: no reading recorded for this transcript: run proofread.py dump --all (or every --page)", file=sys.stderr)
        return EXIT_CHECK
    left = uncovered(prog.get("ranges", []), raw_n)
    if left:
        print(f"sign: {len(left)} word(s) never printed (first: {left[0]}); dump the remaining pages first", file=sys.stderr)
        return EXIT_CHECK
    data = {
        "words_sha256": sha256_file(path),
        "transcript_id": prog["transcript_id"],
        "words": len(doc["words"]),
        "corrections_applied": doc.get("corrections_applied", 0),
        "reviewer": args.reviewer,
        "note": args.note,
        "signed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_json(p_paths["signature"], data)
    print(f"sign: transcript signed ({data['words']} words, {data['corrections_applied']} correction(s)) -> {p_paths['signature']}")
    return 0


def cmd_status(args) -> int:
    ok, why = gate(Path(args.words))
    print(("ok: " if ok else "not ok: ") + why)
    return 0 if ok else EXIT_CHECK


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump", help="Print the transcript page by page with a check-first list")
    d.add_argument("words")
    d.add_argument("--page", type=int)
    d.add_argument("--all", action="store_true")
    d.add_argument("--page-size", type=int, default=400)
    a = sub.add_parser("apply", help="Apply corrections.json to the raw transcript")
    a.add_argument("words")
    a.add_argument("corrections")
    s = sub.add_parser("sign", help="Sign the proofread transcript")
    s.add_argument("words")
    s.add_argument("--reviewer", default="model", help="Who read it: model, founder, or a name")
    s.add_argument("--note", default="")
    st = sub.add_parser("status", help="Exit 0 when the signature matches words.json")
    st.add_argument("words")
    args = ap.parse_args()
    return {"dump": cmd_dump, "apply": cmd_apply, "sign": cmd_sign, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
