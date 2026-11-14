#!/usr/bin/env python3
"""digest.py: the timeline the model reads to choose clips.

    python3 scripts/digest.py RUN/words.json [--out RUN/digest.md] [--gap 0.6] [--json]

Groups words.json into sentences (sentence punctuation, a pause of --gap seconds
or more, or 40 words at most) and writes one line per sentence:

    [12-31] 0:04.20-0:09.80 (5.6 s) The sentence as transcribed.
        ~ 1.4 s pause

The bracket holds the word indexes (for proofread.py), then the times to copy
into clips.json. A pause line marks a clean cut point. The header gives the
duration, the engine and whether word timings are measured or estimated.

Exit codes: 0 digest written, 2 unreadable words.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ends_sentence, fmt_time, load_words  # noqa: E402

MAX_SENTENCE_WORDS = 40


def sentences(words: List[Dict[str, Any]], gap: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    cur: List[int] = []
    for i, w in enumerate(words):
        if cur:
            prev = words[cur[-1]]
            if ends_sentence(prev["word"]) or w["start"] - prev["end"] >= gap or len(cur) >= MAX_SENTENCE_WORDS:
                out.append(_sentence(words, cur))
                cur = []
        cur.append(i)
    if cur:
        out.append(_sentence(words, cur))
    return out


def _sentence(words: List[Dict[str, Any]], idx: List[int]) -> Dict[str, Any]:
    text = " ".join(words[i]["word"] for i in idx)
    text = text.replace(" '", "'").replace(" ’", "’")
    return {"i": idx[0], "j": idx[-1], "start": words[idx[0]]["start"], "end": words[idx[-1]]["end"], "text": text}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", help="words.json from transcribe.py")
    ap.add_argument("--out", help="Output markdown (default: digest.md next to words.json)")
    ap.add_argument("--gap", type=float, default=0.6, help="Pause in seconds that closes a sentence and marks a cut point")
    ap.add_argument("--json", action="store_true", help="Print the sentences as JSON on stdout instead")
    args = ap.parse_args()

    path = Path(args.words)
    doc = load_words(path)
    words = doc["words"]
    sents = sentences(words, args.gap)
    if args.json:
        print(json.dumps(sents, ensure_ascii=False, indent=1))
        return 0
    lines = [
        f"# Transcript digest: {doc.get('source') or path.name}",
        "",
        f"Duration {fmt_time(doc.get('duration') or words[-1]['end'])}, {len(words)} words, {len(sents)} sentences, "
        f"engine {doc.get('engine')}, timing {doc.get('timing', 'word')}, language {doc.get('language') or 'unknown'}.",
        "",
        "Each line: [first-last word index] start-end (length) text. `~ pause` lines are clean cut points.",
        "Copy start and end times into clips.json; the hook is the first sentence of the clip, verbatim.",
        "",
    ]
    prev_end = None
    for s in sents:
        if prev_end is not None and s["start"] - prev_end >= args.gap:
            lines.append(f"    ~ {s['start'] - prev_end:.1f} s pause")
        lines.append(f"[{s['i']}-{s['j']}] {fmt_time(s['start'])}-{fmt_time(s['end'])} ({s['end'] - s['start']:.1f} s) {s['text']}")
        prev_end = s["end"]
    out = Path(args.out) if args.out else path.with_name("digest.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"digest: {len(sents)} sentences -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
