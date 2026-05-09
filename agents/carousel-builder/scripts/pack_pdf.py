#!/usr/bin/env python3
"""
pack_pdf.py - assemble a PNG sequence into a single PDF.

Used in the Playwright fallback path (when slides2pdf is unavailable). Reads
slide-*.png from --in, sorts by name, writes a single multipage PDF to --out.
Each PNG becomes one PDF page at its native pixel dimensions.

Usage:
    python pack_pdf.py --in /path/to/png/ --out /path/to/carousel.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack PNG sequence into a single PDF.")
    ap.add_argument("--in", dest="in_dir", required=True, type=Path,
                    help="Directory containing slide-NN.png files")
    ap.add_argument("--out", required=True, type=Path, help="Output PDF path")
    ap.add_argument("--pattern", default="slide-*.png",
                    help="Glob pattern for slide PNGs (default: slide-*.png)")
    args = ap.parse_args()

    try:
        import img2pdf
    except ImportError:
        print("ERROR: img2pdf not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    pngs = sorted(args.in_dir.glob(args.pattern))
    if not pngs:
        print(f"ERROR: no PNGs matching {args.pattern} in {args.in_dir}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(img2pdf.convert([str(p) for p in pngs]))

    size_kb = args.out.stat().st_size / 1024
    print(f"Wrote {args.out} ({len(pngs)} pages, {size_kb:.1f} KB)")
    if size_kb < 50:
        print("WARNING: PDF < 50 KB, may be blank. Inspect source PNGs.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
