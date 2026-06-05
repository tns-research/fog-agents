#!/usr/bin/env python3
"""render_brand_preview.py: Render a self-contained brand preview card.

Reads a brand-candidate.json (or brand.json) and composes a single PNG card
showing the color swatches with hex labels, the heading/body font names, and
the logo if one is supplied. This is what the user validates in the
extract-brand checkpoint. It deliberately depends on nothing but Pillow so the
project-context agent never reaches into another agent's render skill.

Usage:
    python render_brand_preview.py \
        --brand out/brand-candidate.json \
        --out   out/brand-debug/brand-preview.png \
        [--logo out/assets/logo.png]

Exit codes:
    0  preview written (or Pillow absent: token table printed to stdout instead)
    3  brand json unreadable / malformed
    4  render error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CARD_W = 1080
CARD_H = 1620  # taller than 4:5 to fit a harvested-asset contact strip
MARGIN = 80
SWATCH_KEYS = ("bg", "text_primary", "accent", "accent_secondary")
THUMB_COLS = 5
THUMB_GAP = 16


def _load_tokens(brand_path: Path) -> dict[str, str]:
    """Accept both the candidate shape ({tokens:{k:{value}}}) and the flat
    brand.json shape ({k:value}). Returns a flat {token: str_value} dict."""
    data = json.loads(brand_path.read_text())
    if isinstance(data.get("tokens"), dict):
        return {k: str(v.get("value", "")) for k, v in data["tokens"].items()}
    return {k: str(v) for k, v in data.items() if not k.startswith("_")}


def _hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) >= 6:
        try:
            return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    return (128, 128, 128)  # neutral grey for an unparseable color


def _readable_text_on(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    # WCAG-ish luminance pick: white text on dark, near-black on light.
    r, g, b = (c / 255 for c in rgb)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (17, 17, 17) if lum > 0.55 else (255, 255, 255)


def _font(size: int):
    from PIL import ImageFont

    # Try a few common truetype faces; fall back to Pillow's bitmap default.
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _print_table(tokens: dict[str, str]) -> None:
    print("Brand tokens (Pillow not installed; preview card skipped):")
    for k, v in tokens.items():
        print(f"  {k:<18} {v}")


def _load_assets(brand_path: Path) -> list[tuple[str, Path]]:
    """Resolve the harvested-asset thumbnails to show on the contact strip, as
    (label, absolute_path). Reads the `assets` block from the brand JSON and
    resolves each path relative to the brand JSON's own directory. Accepts both
    the candidate shape (paths relative to project-context) and the finalized
    brand.json shape (project-root-relative under an `assets` key)."""
    try:
        data = json.loads(brand_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    assets = data.get("assets")
    if not isinstance(assets, dict):
        return []
    base = brand_path.parent

    def resolve(p: str) -> Path | None:
        if not p:
            return None
        cand = (base / p)
        if cand.exists():
            return cand
        # finalized brand.json stores project-root-relative paths like
        # "project-context/assets/site/og-image.jpg"; strip the leading dir.
        parts = Path(p).parts
        if len(parts) > 1:
            alt = base / Path(*parts[1:])
            if alt.exists():
                return alt
        return None

    out: list[tuple[str, Path]] = []
    # candidate shape: {logo:{path}, og_image:{path}, images:[{path}]}
    # finalized shape: {logo_path, og_image_path, images:[str]}
    og = assets.get("og_image")
    og_path = og.get("path") if isinstance(og, dict) else assets.get("og_image_path")
    if (rp := resolve(og_path or "")):
        out.append(("og:image", rp))
    for item in (assets.get("images") or []):
        ip = item.get("path") if isinstance(item, dict) else item
        if (rp := resolve(ip or "")):
            out.append(("", rp))
    return out


def _thumb(img_path: Path, box: int):
    """Open an image and fit it into a box x box square, or None if unreadable
    (e.g. an SVG, which Pillow cannot rasterize without extra deps)."""
    from PIL import Image

    try:
        im = Image.open(img_path).convert("RGB")
    except Exception:
        return None
    im.thumbnail((box, box))
    return im


def render(brand_path: Path, out_path: Path, logo_path: Path | None) -> int:
    try:
        tokens = _load_tokens(brand_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"render_brand_preview: cannot read {brand_path}: {e}\n")
        return 3

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _print_table(tokens)
        return 0  # caller treats this as "validate from the table"

    try:
        bg = _hex_to_rgb(tokens.get("bg", "#0d0d10"))
        fg = _hex_to_rgb(tokens.get("text_primary", "#ffffff"))
        card = Image.new("RGB", (CARD_W, CARD_H), bg)
        d = ImageDraw.Draw(card)

        title_f = _font(54)
        label_f = _font(30)
        small_f = _font(26)

        y = MARGIN
        d.text((MARGIN, y), "Brand preview", font=title_f, fill=fg)
        y += 90

        # Logo, if present.
        if logo_path and logo_path.exists():
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((360, 160))
                card.paste(logo, (MARGIN, y), logo)
                y += logo.height + 40
            except Exception:
                pass  # a broken logo file should not kill the preview

        # Color swatches.
        sw_h = 150
        for key in SWATCH_KEYS:
            if key not in tokens:
                continue
            rgb = _hex_to_rgb(tokens[key])
            d.rectangle([MARGIN, y, CARD_W - MARGIN, y + sw_h], fill=rgb)
            label = f"{key}  {tokens[key]}"
            d.text((MARGIN + 24, y + sw_h // 2 - 16), label,
                   font=label_f, fill=_readable_text_on(rgb))
            y += sw_h + 20

        y += 20
        d.text((MARGIN, y), f"Heading font:  {tokens.get('font_heading', '-')}",
               font=small_f, fill=fg)
        y += 44
        d.text((MARGIN, y), f"Body font:     {tokens.get('font_body', '-')}",
               font=small_f, fill=fg)
        y += 70

        # Harvested-asset contact strip: proof the agent grabbed real material.
        thumbs = _load_assets(brand_path)
        if thumbs:
            d.text((MARGIN, y), "Harvested assets", font=label_f, fill=fg)
            y += 50
            box = (CARD_W - 2 * MARGIN - (THUMB_COLS - 1) * THUMB_GAP) // THUMB_COLS
            x = MARGIN
            for i, (_label, path) in enumerate(thumbs[: THUMB_COLS * 2]):
                col = i % THUMB_COLS
                if i and col == 0:
                    x = MARGIN
                    y += box + THUMB_GAP
                cell_x = MARGIN + col * (box + THUMB_GAP)
                d.rectangle([cell_x, y, cell_x + box, y + box], outline=fg, width=2)
                im = _thumb(path, box - 8)
                if im is not None:
                    off_x = cell_x + (box - im.width) // 2
                    off_y = y + (box - im.height) // 2
                    card.paste(im, (off_x, off_y))
                else:
                    d.text((cell_x + 10, y + box // 2 - 12), path.suffix.lstrip(".") or "?",
                           font=small_f, fill=fg)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        card.save(out_path, "PNG")
    except Exception as e:
        sys.stderr.write(f"render_brand_preview: render error: {e}\n")
        return 4

    sys.stderr.write(f"render_brand_preview: wrote {out_path}\n")
    print(str(out_path))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brand", required=True, help="Path to brand-candidate.json or brand.json")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--logo", default="", help="Optional logo image to paste into the card")
    args = p.parse_args()

    logo = Path(args.logo) if args.logo else None
    return render(Path(args.brand), Path(args.out), logo)


if __name__ == "__main__":
    sys.exit(main())
