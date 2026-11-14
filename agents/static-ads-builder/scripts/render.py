#!/usr/bin/env python3
"""render.py: html/index.html -> one exact PNG (and JPEG) per ad and format.

Local Chromium through Playwright: no service, no key, no spend.

  python3 scripts/render.py <html dir> [--out DIR] [--width 1080|1440] [--no-jpg]

- PNG: each <section class="ad"> screenshotted at its exact canvas size
  (1080x1080, 1080x1350, 1080x1920), sRGB profile, named after the ad
  (<project>_<NN>_<stage>_<angle>_<style>_<ratio>.png).
- JPEG: same pixels, quality 90, 4:4:4 chroma (sharp text), the upload files.
- --width 1440 renders at 1440 px wide (1440x1800 for 4:5), the size Meta's
  feed guide recommends; the layout is the same, only sharper. Default 1080.
- render.json: files, sizes, the fit.js report, and the DOM text of every
  section (what the browser actually laid out), read by qa.py.

Waits for document.fonts.ready, window load and fit.js (body[data-fitted]).
Exit 0 when every section rendered, 1 otherwise, 2 when index.html is missing.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

FIT_TIMEOUT_MS = 30000

DOM_TEXT_JS = r"""
() => {
  const out = {};
  document.querySelectorAll('section.ad').forEach(sec => {
    const parts = [];
    const walker = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const el = n.parentElement;
      if (!el || el.closest('.asset-missing') || el.closest('svg')) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.05) continue;
      if (n.textContent.trim()) parts.push(n.textContent);
    }
    out[sec.dataset.name] = parts.join(' ');
  });
  return out;
}
"""


def srgb_profile() -> bytes:
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # noqa: BLE001
        return b""


def render(html_dir: Path, out_dir: Path, jpg: bool = True, width: int = 1080) -> Dict[str, Any]:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    index = html_dir / "index.html"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("*.png")) + list(out_dir.glob("*.jpg")):
        if old.name.startswith("contact-sheet"):
            continue
        old.unlink()
    icc = srgb_profile() or None
    scale = width / 1080
    res: Dict[str, Any] = {"files": [], "errors": [], "scale": scale}
    t0 = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=scale)
        page.goto(index.resolve().as_uri(), wait_until="load")
        page.wait_for_function("document.body.dataset.fitted === '1'", timeout=FIT_TIMEOUT_MS)
        res["fit"] = page.evaluate("window.__fit")
        res["dom_text"] = page.evaluate(DOM_TEXT_JS)
        secs = page.locator("section.ad")
        for i in range(secs.count()):
            sec = secs.nth(i)
            name = sec.get_attribute("data-name")
            fmt = sec.get_attribute("data-format")
            try:
                im = Image.open(io.BytesIO(sec.screenshot(type="png", animations="disabled"))).convert("RGB")
            except Exception as e:  # noqa: BLE001
                res["errors"].append({"name": name, "error": str(e)[:200]})
                continue
            png = out_dir / f"{name}.png"
            im.save(png, optimize=True, icc_profile=icc)
            rec = {"name": name, "format": fmt, "png": png.name, "size": list(im.size)}
            if jpg:
                j = out_dir / f"{name}.jpg"
                im.save(j, quality=90, subsampling=0, optimize=True, progressive=True, icc_profile=icc)
                rec["jpg"] = j.name
            res["files"].append(rec)
        browser.close()
    res["seconds"] = round(time.time() - t0, 1)
    (out_dir / "render.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="Dir holding index.html (build.py output)")
    ap.add_argument("--out", help="Output dir (default <html dir>/../renders)")
    ap.add_argument("--width", type=int, default=1080, choices=[1080, 1440], help="Output width in px (1440 = Meta feed recommendation)")
    ap.add_argument("--no-jpg", action="store_true")
    args = ap.parse_args()
    html_dir = Path(args.html).resolve()
    if not (html_dir / "index.html").exists():
        print(f"render: no {html_dir / 'index.html'}, run build.py first", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else html_dir.parent / "renders"
    r = render(html_dir, out, not args.no_jpg, args.width)
    print(f"render: {len(r['files'])} files, {len(r['errors'])} errors, {r['seconds']} s -> {out}")
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
