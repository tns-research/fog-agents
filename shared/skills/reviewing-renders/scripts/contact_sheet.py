#!/usr/bin/env python3
"""
contact_sheet.py

Assemble rendered images (PNG, JPG, WEBP) into one numbered contact sheet, so a
reviewer (a vision model or the founder) checks a whole carousel, ad set or
capture series in one look. Each tile carries its number, file name and pixel
size; a size that differs from --expect (or from the majority when --expect is
absent) is marked: red for --expect mismatches and unreadable files (exit 1),
amber for a size that only differs from the majority (no failure: ad sets mix
formats on purpose). Transparent images sit on a checkerboard so their
edges stay visible.

Needs Pillow 12.3+ (pip install -r requirements.txt). Python 3.10+.

Usage:
    python3 contact_sheet.py slide-01.png slide-02.png ... -o contact-sheet.png
    python3 contact_sheet.py renders/ -o renders/contact-sheet.png --expect 1080x1350
    python3 contact_sheet.py renders/ -o sheet-feed.png --scale feed
    python3 contact_sheet.py renders/ -o sheet.png --cols 5 --title "Carousel v2" --json

Options:
    -o, --out PATH      Output PNG (default: contact-sheet.png in the current folder).
    --scale S           Tile width: review (540 px, default), feed (375 px: one phone
                        feed column in CSS pixels, so text unreadable here is unreadable
                        in the feed), thumb (150 px: grid or profile thumbnail), full
                        (native width), or a number of pixels.
    --cols N            Columns (default: up to 5).
    --expect WxH        Expected size of every image, for example 1080x1350. Any other
                        size is flagged and makes the exit code 1.
    --title TEXT        Header line.
    --json              Print the tile list as JSON on stdout.

A folder argument takes every .png/.jpg/.jpeg/.webp inside it (not recursive),
sorted with numbers in natural order, skipping files whose name starts with
contact-sheet.

Exit codes: 0 sheet written, 1 sheet written but an image failed to open or has
an unexpected size, 2 usage error or Pillow missing.
"""

import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - depends on the machine
    Image = None  # type: ignore

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
SCALES = {"review": 540, "feed": 375, "thumb": 150}
BG = (154, 154, 154)
LABEL_BG = (32, 32, 32)
LABEL_FG = (240, 240, 240)
FLAG = (220, 38, 38)
NOTE = (180, 83, 9)
PAD = 16


def natural_key(name: str) -> List[Any]:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def collect(inputs: List[str]) -> List[str]:
    files: List[str] = []
    for item in inputs:
        if os.path.isdir(item):
            names = [n for n in os.listdir(item)
                     if n.lower().endswith(IMAGE_EXT) and not n.startswith("contact-sheet")]
            files.extend(os.path.join(item, n) for n in sorted(names, key=natural_key))
        else:
            files.append(item)
    return files


def load_font(size: int):
    for candidate in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                      "C:\\Windows\\Fonts\\arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def fit(draw: "ImageDraw.ImageDraw", text: str, font, max_w: int) -> str:
    """Truncate text with '...' so it fits in max_w pixels."""
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=font) > max_w:
        text = text[:-1]
    return text + "..."


def checkerboard(w: int, h: int, cell: int = 12) -> "Image.Image":
    board = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, h, cell):
        for x in range((y // cell) % 2 * cell, w, cell * 2):
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(214, 214, 214))
    return board


def to_tile(img: "Image.Image", width: Optional[int]) -> "Image.Image":
    if width and img.width != width:
        height = max(1, round(img.height * width / img.width))
        img = img.resize((width, height), Image.LANCZOS)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = checkerboard(*rgba.size)
        base.paste(rgba, mask=rgba.split()[3])
        return base
    return img.convert("RGB")


def parse_expect(value: str) -> Tuple[int, int]:
    m = re.fullmatch(r"(\d+)[xX](\d+)", value or "")
    if not m:
        raise ValueError(f"--expect takes WxH, for example 1080x1350, got '{value}'")
    return int(m.group(1)), int(m.group(2))


def parse_args(argv: List[str]) -> Dict[str, Any]:
    opts: Dict[str, Any] = {"out": "contact-sheet.png", "scale": "review", "cols": None,
                            "expect": None, "title": "", "json": False, "inputs": []}
    it = iter(argv)
    for arg in it:
        if arg in ("-h", "--help"):
            raise ValueError("help")
        if arg in ("-o", "--out", "--scale", "--cols", "--expect", "--title"):
            value = next(it, None)
            if value is None:
                raise ValueError(f"{arg} needs a value")
            key = "out" if arg in ("-o", "--out") else arg[2:]
            opts[key] = value
        elif arg == "--json":
            opts["json"] = True
        elif arg.startswith("-") and arg != "-":
            raise ValueError(f"unknown option {arg}")
        else:
            opts["inputs"].append(arg)
    if not opts["inputs"]:
        raise ValueError("give image files or a folder")
    scale = opts["scale"]
    if scale == "full":
        opts["tile_width"] = None
    elif scale in SCALES:
        opts["tile_width"] = SCALES[scale]
    elif str(scale).isdigit() and int(scale) >= 40:
        opts["tile_width"] = int(scale)
    else:
        raise ValueError("--scale takes review, feed, thumb, full or a width in pixels (40 or more)")
    if opts["cols"] is not None:
        if not str(opts["cols"]).isdigit() or int(opts["cols"]) < 1:
            raise ValueError("--cols takes a positive integer")
        opts["cols"] = int(opts["cols"])
    if opts["expect"]:
        opts["expect"] = parse_expect(opts["expect"])
    return opts


def build(opts: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    files = collect(opts["inputs"])
    if not files:
        raise ValueError("no image found in the inputs")
    entries: List[Dict[str, Any]] = []
    for i, path in enumerate(files, start=1):
        entry: Dict[str, Any] = {"index": i, "path": path, "name": os.path.basename(path)}
        try:
            with Image.open(path) as im:
                im.load()
                entry["width"], entry["height"] = im.size
                entry["tile"] = to_tile(im, opts["tile_width"])
        except Exception as e:  # unreadable or not an image
            entry["error"] = f"cannot open: {e.__class__.__name__}"
        entries.append(entry)

    sizes = [(e["width"], e["height"]) for e in entries if "width" in e]
    majority = max(set(sizes), key=sizes.count) if sizes else None
    if majority and sizes.count(majority) * 2 <= len(sizes):
        majority = None  # no clear majority: nothing to compare against
    for e in entries:
        e["flag"], e["note"] = None, None
        if "error" in e:
            e["flag"] = e["error"]
        elif opts["expect"] and (e["width"], e["height"]) != opts["expect"]:
            e["flag"] = f"expected {opts['expect'][0]}x{opts['expect'][1]}"
        elif not opts["expect"] and majority and (e["width"], e["height"]) != majority:
            e["note"] = f"differs from most ({majority[0]}x{majority[1]})"

    font_size = max(11, min(18, (opts["tile_width"] or 540) // 28))
    font = load_font(font_size)
    label_h = font_size * 2 + 10
    if opts["tile_width"]:
        tile_w = opts["tile_width"]
    else:
        tile_w = max((e["tile"].width for e in entries if "tile" in e), default=300)
    placeholder_h = round(tile_w * 1.25)
    cols = opts["cols"] or min(len(entries), 5)
    rows = math.ceil(len(entries) / cols)
    row_heights = []
    for r in range(rows):
        row = entries[r * cols:(r + 1) * cols]
        row_heights.append(max((e["tile"].height if "tile" in e else placeholder_h) for e in row) + label_h)
    header_h = font_size * 2 + 16

    sheet_w = cols * tile_w + (cols + 1) * PAD
    sheet_h = header_h + sum(row_heights) + (rows + 1) * PAD
    sheet = Image.new("RGB", (sheet_w, sheet_h), BG)
    draw = ImageDraw.Draw(sheet)
    flagged = sum(1 for e in entries if e["flag"])
    scale_label = opts["scale"] if opts["scale"] in SCALES or opts["scale"] == "full" else f"{tile_w} px"
    header = f"{opts['title'] + '  |  ' if opts['title'] else ''}{len(entries)} images, scale {scale_label}"
    if flagged:
        header += f", {flagged} flagged"
    draw.text((PAD, PAD // 2 + 4), header, fill=FLAG if flagged else LABEL_BG, font=font)

    y = header_h + PAD
    for r in range(rows):
        x = PAD
        for e in entries[r * cols:(r + 1) * cols]:
            if "tile" in e:
                sheet.paste(e["tile"], (x, y))
                draw.rectangle([x - 1, y - 1, x + e["tile"].width, y + e["tile"].height], outline=(0, 0, 0))
                ly = y + e["tile"].height
            else:
                draw.rectangle([x, y, x + tile_w - 1, y + placeholder_h - 1], fill=(255, 255, 255), outline=FLAG, width=3)
                ly = y + placeholder_h
            fill = FLAG if e["flag"] else NOTE if e["note"] else LABEL_BG
            draw.rectangle([x, ly, x + tile_w - 1, ly + label_h - 1], fill=fill)
            size = f"{e['width']}x{e['height']}" if "width" in e else "?"
            line2 = e["flag"] or e["note"] or e["name"]
            draw.text((x + 6, ly + 3), fit(draw, f"#{e['index']:02d}  {size}", font, tile_w - 12), fill=LABEL_FG, font=font)
            draw.text((x + 6, ly + 5 + font_size), fit(draw, line2, font, tile_w - 12), fill=LABEL_FG, font=font)
            x += tile_w + PAD
        y += row_heights[r] + PAD

    out_dir = os.path.dirname(os.path.abspath(opts["out"]))
    os.makedirs(out_dir, exist_ok=True)
    sheet.save(opts["out"])
    return entries, flagged


def main(argv: List[str]) -> int:
    try:
        opts = parse_args(argv)
    except ValueError as e:
        print(__doc__.strip().split("A folder argument")[0].rstrip(), file=sys.stderr)
        if str(e) != "help":
            print(f"\nerror: {e}", file=sys.stderr)
        return 0 if str(e) == "help" else 2
    if Image is None:
        print("contact_sheet.py needs Pillow: pip install pillow\n"
              "Without it, open the images one by one, or hand the folder to the founder "
              "for review (see reviewing-renders/SKILL.md, fallback without vision).",
              file=sys.stderr)
        return 2
    try:
        entries, flagged = build(opts)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    summary = [{k: e.get(k) for k in ("index", "path", "width", "height", "flag", "note")} for e in entries]
    if opts["json"]:
        print(json.dumps({"sheet": opts["out"], "tiles": summary, "flagged": flagged}, indent=2))
    else:
        print(f"Contact sheet: {opts['out']} ({len(entries)} images, {flagged} flagged)")
        for e in summary:
            size = f"{e['width']}x{e['height']}" if e["width"] else "?"
            mark = e["flag"] or e["note"]
            print(f"  #{e['index']:02d}  {size:<11} {e['path']}" + (f"  <- {mark}" if mark else ""))
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
