#!/usr/bin/env python3
"""make_fixture_images.py: draw the images of the offline test site.

The fixture site (fixtures/site/index.html) references raster images that are
not versioned: this script draws them with Pillow, deterministically, into the
folder given as argument (selftest.py calls it on a temporary copy).

    python3 make_fixture_images.py <site-dir>

Images: product.png (a UI screenshot: sharp edges, kept as product),
team.jpg (a photo-like scene, kept as team), illustration.png (transparent,
kept as illustration), grain.png (tiled noise, dropped as texture), glow.png
(radial glow, dropped as decoration), og.png, favicon.png, pixel.gif (1x1).
Exit 0, or 2 when Pillow is missing.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path


def make_images(dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    dest.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)

    # product.png: a dashboard with a sidebar, rows of text bars and a chart
    im = Image.new("RGB", (800, 500), (22, 26, 38))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 180, 500], fill=(14, 17, 26))
    for i in range(7):
        d.rounded_rectangle([24, 40 + i * 44, 150, 58 + i * 44], 4, fill=(60, 66, 86) if i else (168, 85, 247))
    for r in range(8):
        y = 40 + r * 52
        d.rounded_rectangle([210, y, 770, y + 40], 6, fill=(30, 35, 50), outline=(44, 50, 68))
        d.rectangle([228, y + 12, 228 + rnd.randint(120, 260), y + 20], fill=(200, 204, 216))
        d.rectangle([228, y + 26, 228 + rnd.randint(60, 160), y + 31], fill=(110, 116, 136))
        color = [(34, 197, 94), (234, 179, 8), (239, 68, 68)][r % 3]
        d.rounded_rectangle([680, y + 12, 750, y + 28], 8, fill=color)
    im.save(dest / "product.png")

    # team.jpg: a photo-like scene (sky gradient, ground, two figures, blur, grain)
    im = Image.new("RGB", (600, 600))
    px = im.load()
    for y in range(600):
        for x in range(600):
            t = y / 600.0
            base = (int(214 - 90 * t), int(170 - 60 * t), int(140 - 70 * t)) if y < 380 else (90, 72, 60)
            n = rnd.randint(-10, 10)
            px[x, y] = tuple(max(0, min(255, c + n)) for c in base)
    d = ImageDraw.Draw(im)
    for cx, color in ((210, (40, 52, 80)), (390, (120, 40, 50))):
        d.ellipse([cx - 45, 170, cx + 45, 260], fill=(222, 184, 150))
        d.rounded_rectangle([cx - 80, 260, cx + 80, 560], 40, fill=color)
    d.rectangle([0, 470, 600, 600], fill=(70, 56, 46))
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    im.save(dest / "team.jpg", quality=82)

    # illustration.png: an envelope on a transparent background
    im = Image.new("RGBA", (520, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([60, 140, 460, 400], 24, fill=(168, 85, 247, 255), outline=(242, 243, 247, 255), width=6)
    d.line([66, 150, 260, 300, 454, 150], fill=(242, 243, 247, 255), width=8)
    d.ellipse([360, 90, 440, 170], fill=(34, 197, 94, 255))
    im.save(dest / "illustration.png")

    # grain.png: grey noise, tiled by the page (a texture, never a product shot)
    im = Image.new("L", (128, 128))
    im.putdata([118 + rnd.randint(-22, 22) for _ in range(128 * 128)])
    im.convert("RGB").save(dest / "grain.png")

    # glow.png: a soft radial glow
    im = Image.new("RGB", (256, 256))
    px = im.load()
    for y in range(256):
        for x in range(256):
            r = ((x - 128) ** 2 + (y - 128) ** 2) ** 0.5 / 181.0
            k = max(0.0, 1.0 - r) ** 2
            px[x, y] = (int(11 + 120 * k), int(13 + 40 * k), int(20 + 200 * k))
    im.save(dest / "glow.png")

    # og.png, favicon.png, pixel.gif
    im = Image.new("RGB", (1200, 630), (11, 13, 20))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([80, 260, 1120, 370], 20, fill=(168, 85, 247))
    im.save(dest / "og.png")
    im = Image.new("RGBA", (192, 192), (11, 13, 20, 255))
    ImageDraw.Draw(im).rounded_rectangle([36, 36, 156, 156], 28, fill=(242, 243, 247, 255))
    im.save(dest / "favicon.png")
    Image.new("RGB", (1, 1), (255, 255, 255)).save(dest / "pixel.gif")


def main(argv: list) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    try:
        make_images(Path(argv[0]))
    except ImportError:
        print("make_fixture_images: Pillow is required (pip install Pillow)", file=sys.stderr)
        return 2
    print(f"fixture images written to {argv[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
