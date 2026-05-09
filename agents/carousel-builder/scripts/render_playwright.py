#!/usr/bin/env python3
"""
render_playwright.py - HTML to PNG fallback renderer.

Fallback path used when slides2pdf is unavailable. Reads a self-contained
index.html (one <section class="slide"> per slide inside <main class="deck">),
takes one viewport-sized PNG per slide.

Hard rules carried from agent-social-slides:
  - wait_for_load_state('networkidle') before any screenshot
  - await document.fonts.ready (web font flicker would otherwise leak)
  - viewport must match the slide ratio exactly so scroll-snap aligns

Usage:
    python render_playwright.py \\
        --html /path/to/output/index.html \\
        --width 1080 --height 1350 \\
        --out /path/to/output/

PNGs are written as slide-01.png, slide-02.png, ... next to --out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def render(html_path: Path, width: int, height: int, out_dir: Path,
           per_slide_index: int | None = None) -> int:
    """Render slides to PNG. Returns number of PNGs written."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install -r requirements.txt && playwright install chromium",
              file=sys.stderr)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    file_url = "file://" + str(html_path.resolve())

    written = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=2,
        )
        page = context.new_page()
        page.goto(file_url, wait_until="networkidle", timeout=30_000)
        page.evaluate("document.fonts && document.fonts.ready")
        page.wait_for_timeout(300)

        slides = page.query_selector_all(".slide")
        if not slides:
            print("ERROR: no .slide elements found in HTML", file=sys.stderr)
            browser.close()
            return 0

        targets = (
            [(per_slide_index, slides[per_slide_index])]
            if per_slide_index is not None and 0 <= per_slide_index < len(slides)
            else list(enumerate(slides))
        )

        for i, slide in targets:
            slide.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            out_file = out_dir / f"slide-{i + 1:02d}.png"
            slide.screenshot(path=str(out_file))
            written += 1
            print(f"  wrote {out_file.name}")

        browser.close()

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Render HTML slides to PNG via Playwright (fallback path).")
    ap.add_argument("--html", required=True, type=Path, help="Path to index.html")
    ap.add_argument("--width", type=int, default=1080, help="Slide width in px")
    ap.add_argument("--height", type=int, default=1350, help="Slide height in px (1080 for 1:1, 1350 for 4:5)")
    ap.add_argument("--out", required=True, type=Path, help="Output directory for slide-NN.png files")
    ap.add_argument("--slide", type=int, default=None,
                    help="Optional: render just one slide (0-indexed) for per-slide repair")
    args = ap.parse_args()

    if not args.html.exists():
        print(f"ERROR: {args.html} does not exist", file=sys.stderr)
        return 1

    n = render(args.html, args.width, args.height, args.out, per_slide_index=args.slide)
    if n == 0:
        return 2
    print(f"Rendered {n} slide(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
