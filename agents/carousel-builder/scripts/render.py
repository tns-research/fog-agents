#!/usr/bin/env python3
"""render.py: build/index.html -> PNG per slide, Instagram JPEGs, LinkedIn PDF.

Local Chromium through Playwright, no service, no API key.

  python3 scripts/render.py <build dir> [--out DIR] [--scale 1] [--no-pdf] [--no-jpg]

- PNG: each <section class="slide"> screenshotted at its exact size
  (1080x1350 or 1080x1080 at --scale 1). No PDF rasterisation, so no crop:
  the old pdftoppm -W/-H path cut every Instagram PNG.
- JPEG: 1080 wide, quality 88, 4:4:4 chroma (sharp text), sRGB ICC profile.
- PDF: Chromium print, one page per slide, vector text, fonts embedded.
  Page count and page size are checked by qa.py.

Waits for document.fonts.ready, window load and fit.js (body[data-fitted]).
Writes DIR/render.json (files, sizes, fit results) for qa.py.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

FIT_TIMEOUT_MS = 30000


def srgb_profile() -> bytes:
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # noqa: BLE001
        return b""


def has_blank_band(im, min_rows: int = 40) -> bool:
    """True when the image holds min_rows consecutive perfectly flat rows:
    an unrasterised tile (slides always carry grain or content)."""
    w, h = im.size
    small = im.resize((w // 4, h // 4))
    px = small.load()
    run = 0
    for y in range(small.size[1]):
        first = px[0, y]
        if all(px[x, y] == first for x in range(0, small.size[0], 3)):
            run += 1
            if run * 4 >= min_rows:
                return True
        else:
            run = 0
    return False


def open_page(pw, html: Path, w: int, h: int, scale: float):
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=scale)
    page = ctx.new_page()
    page.goto(html.resolve().as_uri(), wait_until="load")
    page.wait_for_function("document.body.dataset.fitted === '1'", timeout=FIT_TIMEOUT_MS)
    return browser, page


def render(build_dir: Path, out_dir: Path, scale: float = 1.0, pdf: bool = True, jpg: bool = True,
           png: bool = True, prefix: str = "slide") -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    from PIL import Image

    html = build_dir / "index.html"
    if not html.exists():
        raise SystemExit(f"no {html}: run build.py first")
    rep = json.loads((build_dir / "build-report.json").read_text(encoding="utf-8")) if (build_dir / "build-report.json").exists() else {}
    w, h = int(rep.get("width", 1080)), int(rep.get("height", 1350))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob(f"{prefix}-*.png")) + list(out_dir.glob(f"{prefix}-*.jpg")):
        old.unlink()
    icc = srgb_profile()
    result: Dict[str, Any] = {"width": w, "height": h, "scale": scale, "png": [], "jpg": [], "pdf": None}
    t0 = time.time()
    with sync_playwright() as pw:
        browser, page = open_page(pw, html, w, h, scale)
        result["fit"] = page.evaluate("window.__fit")
        # PDF first: element screenshots leave the page scrolled, and Chromium
        # then prints blank pages.
        if pdf:
            p = out_dir / "carousel.pdf"
            page.pdf(path=str(p), width=f"{w}px", height=f"{h}px", print_background=True,
                     margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}, prefer_css_page_size=True)
            result["pdf"] = p.name
        sections = page.locator("section.slide")
        n = sections.count()
        for i in range(n):
            # Chromium sometimes captures a tile before it is rasterised (a flat
            # grey band, seen under gVisor): settle two frames, then retry.
            for _attempt in range(4):
                sections.nth(i).scroll_into_view_if_needed()
                page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                buf = sections.nth(i).screenshot(type="png", animations="disabled")
                im = Image.open(io.BytesIO(buf)).convert("RGB")
                if not has_blank_band(im):
                    break
            name = f"{prefix}-{i + 1:02d}"
            if png:
                p = out_dir / f"{name}.png"
                im.save(p, optimize=True, icc_profile=icc or None)
                result["png"].append(p.name)
            if jpg:
                j = out_dir / f"{name}.jpg"
                jim = im if im.size[0] == 1080 else im.resize((1080, round(1080 * im.size[1] / im.size[0])), Image.LANCZOS)
                jim.save(j, quality=88, subsampling=0, optimize=True, progressive=True, icc_profile=icc or None)
                result["jpg"].append(j.name)
        browser.close()
    result["seconds"] = round(time.time() - t0, 1)
    (out_dir / "render.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build", help="Build dir holding index.html")
    ap.add_argument("--out", help="Output dir (default: <html dir>/../export)")
    ap.add_argument("--scale", type=float, default=1.0, help="Device scale for PNG (1 = exact 1080 px)")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-jpg", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    build_dir = Path(args.build).resolve()
    out_dir = Path(args.out).resolve() if args.out else build_dir.parent / "export"
    r = render(build_dir, out_dir, args.scale, not args.no_pdf, not args.no_jpg, not args.no_png)
    print(f"render: {len(r['png']) or len(r['jpg'])} slides, pdf={r['pdf']}, {r['seconds']} s -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
