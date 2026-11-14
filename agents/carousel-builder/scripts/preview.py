#!/usr/bin/env python3
"""preview.py: regenerate directions/<id>/preview.jpg from the reference deck.

  python3 scripts/preview.py <direction id> [<direction id> ...] [--all]

Builds examples/swanbase-seed-deck-20261010/deck.json in the direction,
renders it, and keeps four slides (cover, chart, a calm stat, list) side by
side at feed size (360 px wide each). The vignette is generated, never drawn
by hand, so it always shows what the direction really produces.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build  # noqa: E402
import render  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parent.parent
DECK = AGENT_DIR / "examples" / "swanbase-seed-deck-20261010" / "deck.json"
PICK = [1, 3, 7, 6]  # cover, chart, inverse stat, list


def preview(did: str) -> Path:
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        build.build_deck(DECK, t / "html", did)
        render.render(t / "html", t / "export", 1.0, pdf=False, jpg=False)
        tiles = []
        for k in PICK:
            p = t / "export" / f"slide-{k:02d}.png"
            if p.exists():
                im = Image.open(p).convert("RGB")
                tiles.append(im.resize((360, round(360 * im.size[1] / im.size[0])), Image.LANCZOS))
        gap = 12
        sheet = Image.new("RGB", (len(tiles) * 360 + (len(tiles) + 1) * gap, tiles[0].size[1] + 2 * gap), (138, 138, 134))
        for i, im in enumerate(tiles):
            sheet.paste(im, (gap + i * (360 + gap), gap))
        out = AGENT_DIR / "directions" / did / "preview.jpg"
        sheet.save(out, quality=72, optimize=True, progressive=True)
        return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    ids = build.list_directions() if args.all else args.ids
    for did in ids:
        print(f"preview: {preview(did)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
