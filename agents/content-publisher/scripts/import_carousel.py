#!/usr/bin/env python3
"""import_carousel.py: turn a carousel-builder run into a post spec draft.

Reads <run>/captions.md (sections "LinkedIn post", "LinkedIn first comment",
"Instagram caption", optional "X post", "Threads post", "Bluesky post", and
the "Alt text per slide" table) and the exports (<run>/export/carousel.pdf,
<run>/export/slide-NN.jpg, or .png when no JPEG exists). Writes one post entry:

  - LinkedIn: the post text, the first comment, the PDF as a document;
  - Instagram: the caption and every slide image with its alt text;
  - X: the text when captions.md has an "X post" section, else nothing: the
    lint then reports missing-variant and the model writes it (one tweet);
  - link: the first https URL of the first comment.

The output is a draft: run variants.py lint on it before pubqueue.py add.

Usage:
  python3 import_carousel.py RUN_DIR --ref REF --out posts.json [--networks linkedin,instagram,x]
                             [--source-path carousel-builder/<label>] [--append]

Exit codes: 0 spec written, 2 run folder unreadable or without captions.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
URL_RE = re.compile(r"https://[^\s<>()]+")
SECTIONS = {
    "linkedin post": ("linkedin", "text"),
    "linkedin first comment": ("linkedin", "first_comment"),
    "instagram caption": ("instagram", "text"),
    "x post": ("x", "text"),
    "threads post": ("threads", "text"),
    "bluesky post": ("bluesky", "text"),
}


def parse_captions(text: str) -> Dict[str, Any]:
    title_m = re.search(r"^#\s+(?:Captions:\s*)?(.+?)\s*$", text, re.M)
    out: Dict[str, Any] = {"title": title_m.group(1) if title_m else "", "variants": {}, "alt": {}}
    marks = list(SECTION_RE.finditer(text))
    for k, m in enumerate(marks):
        body = text[m.end(): marks[k + 1].start() if k + 1 < len(marks) else len(text)].strip()
        head = re.sub(r"\s*\(.*$", "", m.group(1)).strip().lower()  # "LinkedIn post (820/3000 characters)"
        if head in SECTIONS:
            net, field = SECTIONS[head]
            out["variants"].setdefault(net, {})[field] = body
        elif head.startswith("alt text"):
            for row in body.splitlines():
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                if len(cells) >= 2 and cells[0].isdigit():
                    out["alt"][int(cells[0])] = cells[1]
    return out


def build(run: Path, ref: str, out_dir: Path, networks: List[str], source_path: str) -> Dict[str, Any]:
    cap_file = run / "captions.md"
    if not cap_file.is_file():
        raise common.UsageError(f"{cap_file} not found: run carousel-builder's export step first")
    cap = parse_captions(cap_file.read_text(encoding="utf-8"))
    export = run / "export"
    slides = sorted(export.glob("slide-*.jpg")) or sorted(export.glob("slide-*.png"))
    pdf = export / "carousel.pdf"

    def rel(p: Path) -> str:
        return Path(os.path.relpath(p.resolve(), out_dir.resolve())).as_posix()

    media: List[Dict[str, Any]] = []
    if pdf.is_file():
        media.append({"path": rel(pdf), "type": "document", "title": cap["title"] or ref})
    slide_idx = []
    for k, s in enumerate(slides, start=1):
        m = re.search(r"slide-(\d+)", s.name)
        n = int(m.group(1)) if m else k
        slide_idx.append(len(media))
        media.append({"path": rel(s), "type": "image", "alt": cap["alt"].get(n, "")})
    variants: Dict[str, Any] = {}
    for net in networks:
        v = dict(cap["variants"].get(net) or {})
        if not v.get("text"):
            continue
        if net == "linkedin" and pdf.is_file():
            v["media"] = [0]
        elif net == "instagram":
            v["media"] = slide_idx
        elif net in ("x", "threads", "bluesky"):
            v["media"] = slide_idx[:1]  # the cover only
        variants[net] = v
    first_comment = (cap["variants"].get("linkedin") or {}).get("first_comment", "")
    links = URL_RE.findall(first_comment)
    post: Dict[str, Any] = {
        "ref": ref, "kind": "carousel", "language": "en",
        "source": {"agent": "carousel-builder", "path": source_path or run.name},
        "link": links[0].rstrip(".,;:") if links else None,
        "media": media, "networks": networks, "variants": variants,
    }
    return post


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="carousel-builder run folder (holds captions.md and export/)")
    ap.add_argument("--ref", required=True, help="post ref, lowercase and hyphens")
    ap.add_argument("--out", required=True, help="post spec to write")
    ap.add_argument("--networks", default="linkedin,instagram,x")
    ap.add_argument("--language", default="en")
    ap.add_argument("--source-path", default="", help="run path relative to the project folder, for the record")
    ap.add_argument("--append", action="store_true", help="add the post to an existing spec instead of replacing it")
    a = ap.parse_args(argv)
    try:
        nets = [n.strip() for n in a.networks.split(",") if n.strip()]
        bad = [n for n in nets if n not in common.NETWORKS]
        if bad:
            raise common.UsageError(f"unknown network(s): {', '.join(bad)}")
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        post = build(Path(a.run), a.ref, out.parent, nets, a.source_path)
        post["language"] = a.language
        spec = common.read_json(out) if a.append and out.exists() else {"schema_version": "1.0", "posts": []}
        spec["posts"] = [p for p in spec["posts"] if p.get("ref") != a.ref] + [post]
        common.write_json_atomic(out, spec)
        missing = [n for n in nets if n not in post["variants"]]
        print(f"wrote {out}: {len(post['media'])} media, variants {', '.join(post['variants']) or 'none'}"
              + (f"; to write: {', '.join(missing)}" if missing else ""))
        return 0
    except common.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
