#!/usr/bin/env python3
"""captions.py: deck.json -> captions.md (post texts, alt text per slide, sources).

  python3 scripts/captions.py <deck.json> [--out captions.md] [--qa export/qa.json]

The model writes the post texts in deck.json meta.captions (write-deck skill);
this script assembles them, counts characters against the platform limits,
composes an alt text for every slide that has none (from the blocks: title,
numbers with their labels, chart values, list items, quote and author, photo
and screenshot alt), and lists every source with its URL.

Limits checked: LinkedIn post 3000 characters, Instagram caption 2200
characters and 30 hashtags (5 recommended), alt text 420 characters
(longer text is cut by screen readers in practice).

Exit 0 when within limits and every caption is present, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
import deckspec  # noqa: E402

LIMITS = {"linkedin": 3000, "instagram": 2200, "first_comment": 1250, "alt": 420, "hashtags": 30}


def alt_for(slide: Dict[str, Any], lang: str) -> str:
    if slide.get("alt"):
        return slide["alt"].strip()
    parts: List[str] = []
    for b in slide.get("blocks", []):
        t = b.get("type")
        if t == "title":
            parts.append(b["text"].rstrip(".") + ".")
            if b.get("sub"):
                parts.append(b["sub"])
        elif t == "body":
            parts.append(b["text"].replace("\n\n", " "))
        elif t == "stat":
            parts.append(f"{b['value']} {b['label']}")
            if b.get("context"):
                parts.append(b["context"])
        elif t == "chart":
            parts.append(charts.describe(b, lang))
        elif t == "list":
            items = [i if isinstance(i, str) else i.get("text", "") for i in b.get("items", [])]
            parts.append("; ".join(items) + ".")
        elif t == "quote":
            parts.append(f"« {b['text']} » {b['author']}." if lang.startswith("fr") else f"“{b['text']}” {b['author']}.")
        elif t in ("photo", "screenshot", "visual"):
            parts.append(b.get("alt", ""))
            for a in b.get("annotations", []) or []:
                parts.append(a["label"] + ".")
        elif t == "logo-row":
            parts.append(", ".join(l["name"] for l in b.get("logos", [])) + ".")
        elif t == "cta":
            parts.append(b["text"] + (f" {b['url']}" if b.get("url") else ""))
    return " ".join(p.strip() for p in parts if p and p.strip())


def build(deck: Dict[str, Any], qa: Dict[str, Any] = None) -> (str, List[str]):
    meta = deck.get("meta", {})
    lang = meta.get("language", "en")
    caps = meta.get("captions") or {}
    problems: List[str] = []
    out = [f"# Captions: {meta.get('title') or meta.get('id', 'carousel')}", ""]
    if qa:
        sm = qa.get("summary", {})
        out += [f"QA: {qa.get('status', '?')}, {sm.get('errors', '?')} errors, {sm.get('warnings', '?')} warnings. Do not publish with errors.", ""]

    def section(key: str, title: str) -> None:
        text = (caps.get(key) or "").strip()
        if key == "instagram" and caps.get("hashtags"):
            text = (text + "\n\n" + " ".join(caps["hashtags"])).strip()
        n = len(text)
        lim = LIMITS[key]
        out.append(f"## {title} ({n}/{lim} characters)")
        out.append("")
        if not text:
            problems.append(f"meta.captions.{key} is missing")
            out.append("_Missing: write it in deck.json meta.captions._")
        else:
            if n > lim:
                problems.append(f"{key}: {n} characters, limit {lim}")
            out.append(text)
        out.append("")

    section("linkedin", "LinkedIn post")
    section("first_comment", "LinkedIn first comment (links go here, not in the post)")
    section("instagram", "Instagram caption")
    tags = caps.get("hashtags") or []
    if len(tags) > LIMITS["hashtags"]:
        problems.append(f"{len(tags)} hashtags, Instagram caps at 30")
    out += ["## Alt text per slide", "", "| # | Alt text | Characters |", "|---|---|---|"]
    for i, s in enumerate(deck.get("slides", []), 1):
        a = alt_for(s, lang)
        if len(a) > LIMITS["alt"]:
            problems.append(f"slide {i}: alt text {len(a)} characters, keep under {LIMITS['alt']} (set slide.alt)")
        out.append(f"| {i} | {a.replace('|', '/')} | {len(a)} |")
    out += ["", "## Sources", ""]
    reg = {s["id"]: s for s in deck.get("sources", []) if isinstance(s, dict) and "id" in s}
    seen = set()
    for s in deck.get("slides", []):
        for b in s.get("blocks", []):
            src = deckspec.resolve_source(b.get("source"), reg)
            if src and src.get("label") not in seen:
                seen.add(src.get("label"))
                url = src.get("url") or src.get("proof_ref") or "no URL"
                acc = f", accessed {src['accessed']}" if src.get("accessed") else ""
                out.append(f"- {src['label']}: {url}{acc}")
    if not seen:
        out.append("- None: the deck shows no number or quote.")
    out.append("")
    return "\n".join(out), problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--out", help="Default: captions.md next to deck.json")
    ap.add_argument("--qa", help="qa.json to quote its status at the top")
    args = ap.parse_args()
    deck_path = Path(args.deck).resolve()
    deck = deckspec.load_json(deck_path)
    qa = json.loads(Path(args.qa).read_text(encoding="utf-8")) if args.qa and Path(args.qa).exists() else None
    text, problems = build(deck, qa)
    out = Path(args.out).resolve() if args.out else deck_path.parent / "captions.md"
    out.write_text(text, encoding="utf-8")
    for p in problems:
        print(f"captions: {p}")
    print(f"captions: {out}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
