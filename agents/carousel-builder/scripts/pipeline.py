#!/usr/bin/env python3
"""pipeline.py: one command from deck.json to a reviewed, exportable carousel.

Deck mode (build -> render -> qa -> captions):
  python3 scripts/pipeline.py <deck.json> [--direction ID] [--brand brand.json] [--out DIR]
  -> DIR/html/index.html, DIR/export/slide-NN.png|.jpg, carousel.pdf,
     contact-sheet.jpg, qa.json, and DIR/captions.md   (DIR = deck folder)

Cover mode (art-direction stop):
  python3 scripts/pipeline.py <deck.json> --covers [--directions a,b,c|all] [--first-layout]
  -> DIR/covers/<direction>/html + png, and DIR/covers/cover-board.jpg:
     one tile per variant at feed size (360 px wide, the width a phone shows),
     rows = hooks (meta.covers.hooks), columns = direction x cover layout.

Video variant (after the deck mode, only when its QA passes):
  python3 scripts/pipeline.py <deck.json> --video [4:5,9:16,1:1]
  -> DIR/export/video-<aspect>.mp4 per aspect, through scripts/animate.py on
     the HTML just built (same slides). Default aspect: the deck's own (4:5).

Exit code: 0 when QA passes, 1 when the deck has errors (files are still
written so the reviewer sees them), 2 on a fatal input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import animate  # noqa: E402
import build  # noqa: E402
import captions  # noqa: E402
import deckspec  # noqa: E402
import qa  # noqa: E402
import render  # noqa: E402

TILE_W = 360


def run_deck(deck_path: Path, out_dir: Path, direction: str = None, brand: str = None, pdf: bool = True) -> int:
    html_dir, export = out_dir / "html", out_dir / "export"
    rep = build.build_deck(deck_path, html_dir, direction, brand)
    if rep.get("fatal"):
        for e in rep["errors"]:
            print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
        return 2
    print(f"1/4 build: {len(rep['slides'])} slides, {rep['direction']}, {len(rep['errors'])} spec errors, {len(rep['warnings'])} warnings")
    r = render.render(html_dir, export, 1.0, pdf=pdf)
    print(f"2/4 render: {len(r['png'])} PNG, {len(r['jpg'])} JPEG, pdf={r['pdf']} ({r['seconds']} s)")
    res = qa.run(html_dir, export, export / "qa.json")
    qa.print_summary(res)
    print("3/4 qa: " + str(export / "qa.json") + (f", sheet {export / res['contact_sheet']}" if res.get("contact_sheet") else ""))
    deck = deckspec.load_json(deck_path)
    text, problems = captions.build(deck, res)
    cap = out_dir / "captions.md"
    cap.write_text(text, encoding="utf-8")
    for p in problems:
        print(f"captions: {p}")
    print(f"4/4 captions: {cap}")
    return 0 if res["status"] == "pass" and not problems else 1


def board(variants: List[Dict[str, Any]], covers_dir: Path, out: Path, w: int, h: int) -> None:
    from PIL import Image, ImageDraw, ImageFont

    def font(size: int):
        for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()

    hooks = list(dict.fromkeys(v["hook"] for v in variants))
    cols = list(dict.fromkeys((v["direction"], v["layout"]) for v in variants))
    th = round(TILE_W * h / w)
    pad, head, side = 24, 64, 56
    W = side + len(cols) * (TILE_W + pad) + pad
    H = head + len(hooks) * (th + pad) + pad + 30
    sheet = Image.new("RGB", (W, H), (226, 224, 218))
    d = ImageDraw.Draw(sheet)
    f1, f2 = font(20), font(16)
    for ci, (did, lay) in enumerate(cols):
        x = side + ci * (TILE_W + pad)
        d.text((x, 14), did, fill=(20, 20, 20), font=f1)
        d.text((x, 40), lay, fill=(90, 90, 90), font=f2)
    for ri, hk in enumerate(hooks):
        y = head + ri * (th + pad)
        d.text((14, y + th // 2 - 10), hk, fill=(20, 20, 20), font=f1)
        for ci, (did, lay) in enumerate(cols):
            v = next((v for v in variants if v["hook"] == hk and v["direction"] == did and v["layout"] == lay), None)
            if not v or not v.get("png"):
                continue
            x = side + ci * (TILE_W + pad)
            im = Image.open(v["png"]).convert("RGB").resize((TILE_W, th), Image.LANCZOS)
            sheet.paste(im, (x, y))
            if v.get("errors"):
                d.rectangle([x, y, x + TILE_W - 1, y + th - 1], outline=(220, 38, 38), width=5)
                d.text((x + 8, y + th - 26), f"{v['errors']} QA errors", fill=(220, 38, 38), font=f2)
    d.text((side, H - 30), "Tiles at feed size (360 px wide). Pick one direction and one hook.", fill=(90, 90, 90), font=f2)
    sheet.save(out, quality=88, optimize=True)


def run_covers(deck_path: Path, out_dir: Path, directions: List[str], brand: str = None, first_layout: bool = False) -> int:
    deck = deckspec.load_json(deck_path)
    if first_layout:
        deck.setdefault("meta", {}).setdefault("covers", {})
    covers_root = out_dir / "covers"
    manifest = build.build_covers(deck_path, out_dir, directions, brand)
    variants = manifest["variants"]
    if first_layout:
        keep = {}
        for v in variants:
            keep.setdefault((v["direction"], v["hook"]), v)
        variants = list(keep.values())
    w = h = None
    for did in dict.fromkeys(v["direction"] for v in variants):
        html_dir = covers_root / did / "html"
        r = render.render(html_dir, covers_root / did / "png", 1.0, pdf=False, jpg=False, prefix="cover")
        w, h = r["width"], r["height"]
        res = qa.run(html_dir, None, covers_root / did / "qa.json", sheet=False)
        ids = [s["id"] for s in res["slides"]]
        for v in variants:
            if v["direction"] == did and v["id"] in ids:
                k = ids.index(v["id"])
                v["png"] = str(covers_root / did / "png" / f"cover-{k + 1:02d}.png")
                v["errors"] = len(res["slides"][k]["errors"])
                v["warnings"] = len(res["slides"][k]["warnings"])
        print(f"covers: {did} rendered, {sum(len(s['errors']) for s in res['slides'])} QA errors")
    out = covers_root / "cover-board.jpg"
    board(variants, covers_root, out, w or 1080, h or 1350)
    (covers_root / "manifest.json").write_text(json.dumps({"deck": str(deck_path), "variants": variants}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"cover board: {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("--out", help="Output folder (default: the deck folder)")
    ap.add_argument("--direction")
    ap.add_argument("--brand")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--covers", action="store_true")
    ap.add_argument("--directions", help="Comma list or 'all' (cover mode)")
    ap.add_argument("--first-layout", action="store_true", help="Cover mode: one layout per direction (the choice board)")
    ap.add_argument("--video", nargs="?", const="auto", metavar="ASPECTS",
                    help="Also render the MP4 variant: comma list of 4:5, 9:16, 1:1 (default: the deck's ratio)")
    ap.add_argument("--music", help="Video: local audio file mixed under the video")
    ap.add_argument("--max-duration", type=float, help="Video: fit in N seconds by shortening holds")
    args = ap.parse_args()
    deck_path = Path(args.deck).resolve()
    out_dir = Path(args.out).resolve() if args.out else deck_path.parent
    if args.covers:
        if args.directions == "all":
            dirs = build.list_directions()
        elif args.directions:
            dirs = [d.strip() for d in args.directions.split(",")]
        else:
            dirs = None
        return run_covers(deck_path, out_dir, dirs, args.brand, args.first_layout)
    rc = run_deck(deck_path, out_dir, args.direction, args.brand, not args.no_pdf)
    if not args.video:
        return rc
    if rc != 0:
        print("video: skipped, the stills have QA errors (the video only shows validated slides)")
        return rc
    aspects = [None] if args.video == "auto" else [a.strip() for a in args.video.split(",") if a.strip()]
    for a in aspects:
        if a is not None and a not in animate.ASPECTS:
            print(f"video: unknown aspect {a}, one of {', '.join(animate.ASPECTS)}", file=sys.stderr)
            return 2
    for a in aspects:
        try:
            r = animate.run(deck_path, out_dir, a, args.direction, args.brand,
                            {"build": False, "music": args.music, "max_duration": args.max_duration})
        except animate.Fatal as e:
            print(f"video: {e}", file=sys.stderr)
            return 2
        rc = max(rc, r)
    return rc


if __name__ == "__main__":
    sys.exit(main())
