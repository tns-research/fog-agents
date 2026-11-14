#!/usr/bin/env python3
"""logo_pipeline.py: audit a harvested logo and build its light and dark variants.

What it does, in order:

  1. viewBox audit (SVG). The logo is rendered in Chromium with its viewBox
     widened by 30 % on each side, so ink that the declared viewBox cuts off
     becomes visible. Shapes lying entirely outside the declared viewBox are
     treated as excluded on purpose (a wordmark cropped out of a lockup leaves the
     pictogram outside) and are dropped; shapes crossing its edge are clipped
     glyphs. The measured ink box (pixels, antialiasing included) replaces the
     declared viewBox in every variant, with a 2 % margin.
     Raster logos: ink touching the file edge is reported the same way.
  2. Mark split. A lockup whose left cluster is square-ish and separated by a
     gap from a wide text cluster gives a mark (the left cluster) and a wordmark
     (the whole lockup). Otherwise the width/height ratio decides.
  3. Variants. The file keeps its own colors under the background it reads on
     (light ink: on_dark). The other variant is recolored to one brand ink
     (one-color logos) or knocked out to one ink (multi-color logos, flagged).
  4. Pixel test. Every variant is rendered, composited on its test background
     (colors.bg for the brand's mode, the brand's opposite color otherwise) and
     each ink pixel's WCAG contrast is measured: pass when 90 % of the ink reads
     at 3:1 or more, warn from 60 %, fail below. The harvested file itself is
     also tested on colors.bg (dark ink on a dark site is the classic miss).
  5. PNG fallbacks at 1024 px on the long edge for every SVG variant.

Usage:
    python3 logo_pipeline.py --logo assets/logos/source.svg --out <project-context> --bg '#08090a' --text '#f7f8f8'
    python3 logo_pipeline.py --logo new-logo.png --out <project-context> --brand <project-context>/brand-draft.json --update
    python3 logo_pipeline.py --logo logo.svg --out /tmp/x --bg '#ffffff' --json

Writes assets/logos/{wordmark,mark}-on-{light,dark}.{svg,png} and
brand-debug/logo/ (test composites, audit.json) under --out. With --brand and
--update, rewrites logos, logo_audit and extensions.extract_brand.logo_png in
that brand JSON.

Exit codes:
    0  audit pass
    1  audit warn or fail (files written; read logo_audit.issues)
    2  usage error, unreadable logo or brand file
    3  Playwright missing (needed for SVG logos; raster logos work without it)
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_common import (  # noqa: E402
    RGB, cluster_colors, color_distance, contrast_ratio, hex_to_rgb, is_dark,
    luminance, rgb_to_hex,
)

# viewBox widened by this share of its size on each side for the audit render
EXPAND = 0.30
# long side of the declared viewBox, in px, for the audit render
AUDIT_PX = 800
# ink beyond the declared viewBox by more than this many px (audit scale) = clipped
CLIP_TOL_PX = 1.5
# margin around the measured ink box: twice this share of its shorter side
# (4 % of the height of a wordmark), so wide and square logos get the same air
PAD = 0.02
# alpha above which a pixel counts as ink (0..255)
INK_ALPHA = 128
# share of ink pixels at 3:1 or more for pass / warn
PASS_SHARE = 0.90
WARN_SHARE = 0.60
# WCAG 1.4.11 non-text contrast
LOGO_MIN_CONTRAST = 3.0
# one color covering this share of the ink = a one-color logo
MONO_SHARE = 0.92
# width/height above which a single logo file is a wordmark
WORDMARK_MIN_RATIO = 1.8
# PNG fallback size, long edge
FALLBACK_PX = 1024
# x gap between shape clusters, share of the ink width, that separates a mark
SPLIT_GAP = 0.05
RASTER_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".bmp"}


# --- SVG text helpers ---------------------------------------------------------

def clean_svg_text(svg: str) -> str:
    """Drop the XML prolog, doctype and comments so the SVG can sit inside HTML."""
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg, flags=re.I)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    start = svg.find("<svg")
    return svg[start:].strip() if start >= 0 else svg.strip()


def recolor_svg(svg: str, ink: str) -> str:
    """Every fill, stroke, stop-color and color that paints something becomes ink;
    none, transparent and url() references stay. The root gets fill=ink so shapes
    that rely on the default black fill follow."""
    keep = ("none", "transparent", "inherit")

    def swap(value: str) -> str:
        v = value.strip().lower()
        if v in keep or v.startswith("url("):
            return value
        return ink

    svg = re.sub(r'(\b(?:fill|stroke|stop-color|color)\s*=\s*")([^"]*)(")',
                 lambda m: m.group(1) + swap(m.group(2)) + m.group(3), svg)
    svg = re.sub(r"(\b(?:fill|stroke|stop-color|color)\s*=\s*')([^']*)(')",
                 lambda m: m.group(1) + swap(m.group(2)) + m.group(3), svg)
    svg = re.sub(r"((?<![-\w])(?:fill|stroke|stop-color|color)\s*:\s*)([^;\"'}]+)",
                 lambda m: m.group(1) + swap(m.group(2)), svg)
    svg = re.sub(r"currentColor", ink, svg, flags=re.I)
    m = re.match(r"<svg\b[^>]*>", svg)
    if m and not re.search(r"\sfill\s*=", m.group(0)):
        svg = svg[:4] + f' fill="{ink}"' + svg[4:]
    return svg


# --- Browser rendering -----------------------------------------------------------

MEASURE_JS = r"""(args) => {
  const svg = document.querySelector('svg');
  if (!svg) return { error: 'no svg element' };
  let vx, vy, vw, vh, had = false;
  const vb = svg.viewBox && svg.viewBox.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) { vx = vb.x; vy = vb.y; vw = vb.width; vh = vb.height; had = true; }
  else {
    const w = parseFloat(svg.getAttribute('width')) || 0, h = parseFloat(svg.getAttribute('height')) || 0;
    if (w > 0 && h > 0) { vx = 0; vy = 0; vw = w; vh = h; }
    else { const b = svg.getBBox(); vx = b.x; vy = b.y; vw = b.width || 1; vh = b.height || 1; }
  }
  const pad = args.expand;
  const ex = vx - pad * vw, ey = vy - pad * vh, ew = vw * (1 + 2 * pad), eh = vh * (1 + 2 * pad);
  const scale = args.px / Math.max(vw, vh);
  svg.setAttribute('viewBox', `${ex} ${ey} ${ew} ${eh}`);
  svg.setAttribute('width', ew * scale); svg.setAttribute('height', eh * scale);
  svg.setAttribute('preserveAspectRatio', 'xMinYMin meet');
  svg.style.display = 'block'; svg.style.overflow = 'visible';
  const sr = svg.getBoundingClientRect();
  const toU = (cx, cy) => [ex + (cx - sr.left) / scale, ey + (cy - sr.top) / scale];
  const sel = 'path,rect,circle,ellipse,polygon,polyline,line,text,image,use';
  const out = [];
  Array.from(svg.querySelectorAll(sel)).forEach((el, i) => {
    if (el.closest('defs,clipPath,mask,symbol,pattern,marker')) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (cs.fill === 'none' && cs.stroke === 'none' && el.tagName !== 'image' && el.tagName !== 'use') return;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const sw = cs.stroke !== 'none' ? (parseFloat(cs.strokeWidth) || 0) * scale / 2 : 0;
    const a = toU(r.left - sw, r.top - sw), b = toU(r.right + sw, r.bottom + sw);
    el.setAttribute('data-lp', String(i));
    out.push({ i, tag: el.tagName.toLowerCase(), x0: a[0], y0: a[1], x1: b[0], y1: b[1] });
  });
  return { declared: [vx, vy, vw, vh], had_viewbox: had, expanded: [ex, ey, ew, eh], scale, elements: out };
}"""

HIDE_JS = r"""(ids) => { for (const id of ids) { const el = document.querySelector(`[data-lp="${id}"]`); if (el) el.style.display = 'none'; } }"""

SERIALIZE_JS = r"""(args) => {
  const svg = document.querySelector('svg').cloneNode(true);
  const keep = args.keep ? new Set(args.keep.map(String)) : null;
  for (const el of Array.from(svg.querySelectorAll('[data-lp]'))) {
    const id = el.getAttribute('data-lp');
    if ((args.drop || []).map(String).includes(id) || (keep && !keep.has(id))) { el.remove(); continue; }
    el.removeAttribute('data-lp'); el.style.removeProperty('display');
    if (el.getAttribute('style') === '') el.removeAttribute('style');
  }
  const [x, y, w, h] = args.box;
  svg.setAttribute('viewBox', `${+x.toFixed(3)} ${+y.toFixed(3)} ${+w.toFixed(3)} ${+h.toFixed(3)}`);
  svg.setAttribute('width', String(+w.toFixed(2))); svg.setAttribute('height', String(+h.toFixed(2)));
  svg.removeAttribute('preserveAspectRatio');
  svg.style.removeProperty('display'); svg.style.removeProperty('overflow');
  if (svg.getAttribute('style') === '') svg.removeAttribute('style');
  return new XMLSerializer().serializeToString(svg);
}"""


class Renderer:
    """One Chromium page reused for every SVG render (Playwright sync API)."""

    def __enter__(self) -> "Renderer":
        from playwright.sync_api import sync_playwright  # ImportError handled by the caller
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        self.page = self.browser.new_page(viewport={"width": 1600, "height": 1600})
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            self.browser.close()
        finally:
            self._pw.stop()

    def load(self, svg: str) -> None:
        html = ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;padding:0;"
                "background:transparent}</style></head><body>" + clean_svg_text(svg) + "</body></html>")
        self.page.set_content(html, wait_until="load")

    def shot(self) -> Any:
        from PIL import Image
        box = self.page.evaluate("() => { const r = document.querySelector('svg').getBoundingClientRect(); return [r.width, r.height]; }")
        need_w, need_h = int(box[0]) + 20, int(box[1]) + 20
        vp = self.page.viewport_size or {"width": 1600, "height": 1600}
        if need_w > vp["width"] or need_h > vp["height"]:
            self.page.set_viewport_size({"width": max(vp["width"], need_w), "height": max(vp["height"], need_h)})
        png = self.page.locator("svg").first.screenshot(omit_background=True)
        return Image.open(io.BytesIO(png)).convert("RGBA")

    def rasterize(self, svg: str, long_edge: int) -> Any:
        """Render an SVG with its own viewBox at long_edge px on the long side."""
        self.load(svg)
        self.page.evaluate("""(px) => { const s = document.querySelector('svg');
            const vb = s.viewBox.baseVal; let w = vb && vb.width ? vb.width : (parseFloat(s.getAttribute('width')) || 100);
            let h = vb && vb.height ? vb.height : (parseFloat(s.getAttribute('height')) || 100);
            const k = px / Math.max(w, h); s.setAttribute('width', w * k); s.setAttribute('height', h * k);
            s.style.display = 'block'; }""", long_edge)
        return self.shot()


def alpha_bbox(img: Any, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
    return img.getchannel("A").point(lambda a: 255 if a > threshold else 0).getbbox()


def measure_svg(r: Renderer, svg: str) -> Dict[str, Any]:
    """viewBox audit of one SVG. Returns measurements plus the fixed SVG text
    (outside shapes dropped, viewBox on the measured ink with a margin)."""
    r.load(svg)
    m = r.page.evaluate(MEASURE_JS, {"expand": EXPAND, "px": AUDIT_PX})
    if m.get("error"):
        raise ValueError(m["error"])
    vx, vy, vw, vh = m["declared"]
    ex, ey, _ew, _eh = m["expanded"]
    scale = m["scale"]
    tol = CLIP_TOL_PX / scale
    inside, crossing, outside = [], [], []
    for e in m["elements"]:
        fully_out = e["x1"] <= vx + tol or e["x0"] >= vx + vw - tol or e["y1"] <= vy + tol or e["y0"] >= vy + vh - tol
        fully_in = e["x0"] >= vx - tol and e["x1"] <= vx + vw + tol and e["y0"] >= vy - tol and e["y1"] <= vy + vh + tol
        (inside if fully_in else outside if fully_out else crossing).append(e)
    if outside:
        r.page.evaluate(HIDE_JS, [e["i"] for e in outside])
    img = r.shot()
    bb = alpha_bbox(img)
    if bb is None:
        raise ValueError("the SVG renders no visible ink")
    ux0, uy0 = ex + bb[0] / scale, ey + bb[1] / scale
    ux1, uy1 = ex + bb[2] / scale, ey + bb[3] / scale
    over = {"left": vx - ux0, "top": vy - uy0, "right": ux1 - (vx + vw), "bottom": uy1 - (vy + vh)}
    over_px = {k: round(v * scale, 1) for k, v in over.items()}
    clipped_sides = [k for k, v in over_px.items() if v > CLIP_TOL_PX]
    # share of the ink the declared viewBox cuts off
    a = img.getchannel("A")
    dx0, dy0 = int(round((vx - ex) * scale)), int(round((vy - ey) * scale))
    dx1, dy1 = int(round((vx + vw - ex) * scale)), int(round((vy + vh - ey) * scale))
    total = sum(1 for v in (a.get_flattened_data() if hasattr(a, "get_flattened_data") else a.getdata()) if v > INK_ALPHA)
    inner = a.crop((max(0, dx0), max(0, dy0), max(0, dx1), max(0, dy1)))
    kept = sum(1 for v in (inner.get_flattened_data() if hasattr(inner, "get_flattened_data") else inner.getdata()) if v > INK_ALPHA)
    cut_share = round(1 - kept / total, 4) if total else 0.0
    iw, ih = ux1 - ux0, uy1 - uy0
    pad = PAD * 2 * min(iw, ih)
    box = [ux0 - pad, uy0 - pad, iw + 2 * pad, ih + 2 * pad]
    fixed = r.page.evaluate(SERIALIZE_JS, {"box": box, "drop": [e["i"] for e in outside]})
    loose = (iw * ih) / (vw * vh) if vw * vh else 1.0
    return {
        "declared_viewbox": [round(v, 3) for v in (vx, vy, vw, vh)],
        "had_viewbox": m["had_viewbox"],
        "ink_box": [round(v, 3) for v in (ux0, uy0, iw, ih)],
        "overflow_px": over_px,
        "clipped_sides": clipped_sides,
        "viewbox_clips_ink": bool(clipped_sides),
        "cut_share": cut_share,
        "excluded_shapes": len(outside),
        "crossing_shapes": len(crossing),
        "ink_area_share_of_viewbox": round(loose, 3),
        "height_factor": round(box[3] / vh, 4) if vh else 1.0,
        "fixed_svg": fixed,
        "elements": [e for e in inside + crossing],
        "scale": scale,
    }


def split_mark(r: Renderer, measured: Dict[str, Any]) -> Optional[str]:
    """SVG of the mark when the lockup has a square-ish left cluster followed by
    a wide cluster (the wordmark text), else None. Reloads the fixed SVG."""
    els = sorted(measured["elements"], key=lambda e: e["x0"])
    if len(els) < 2:
        return None
    ink_x0, _iy, ink_w, ink_h = measured["ink_box"]
    groups: List[List[Dict[str, Any]]] = [[els[0]]]
    right = els[0]["x1"]
    for e in els[1:]:
        if e["x0"] - right > SPLIT_GAP * ink_w:
            groups.append([e])
        else:
            groups[-1].append(e)
        right = max(right, e["x1"])
    if len(groups) < 2:
        return None
    first, rest = groups[0], [e for g in groups[1:] for e in g]
    fx0, fx1 = min(e["x0"] for e in first), max(e["x1"] for e in first)
    fy0, fy1 = min(e["y0"] for e in first), max(e["y1"] for e in first)
    rx0, rx1 = min(e["x0"] for e in rest), max(e["x1"] for e in rest)
    ry0, ry1 = min(e["y0"] for e in rest), max(e["y1"] for e in rest)
    fw, fh = fx1 - fx0, fy1 - fy0
    if not fh or not (0.55 <= fw / fh <= 1.8) or fw > 0.45 * ink_w:
        return None
    if (rx1 - rx0) < 1.5 * (ry1 - ry0):
        return None  # the rest is not a wide wordmark
    pad = PAD * 2 * min(fw, fh)
    r.load(measured["fixed_svg"])
    # the fixed SVG lost the data-lp marks: re-measure to tag shapes again
    m2 = r.page.evaluate(MEASURE_JS, {"expand": 0.0, "px": AUDIT_PX})
    keep = [e["i"] for e in m2["elements"]
            if e["x1"] <= fx1 + pad and e["x0"] >= fx0 - pad]
    if not keep:
        return None
    return r.page.evaluate(SERIALIZE_JS, {"box": [fx0 - pad, fy0 - pad, fw + 2 * pad, fh + 2 * pad], "keep": keep})


# --- Pixel analysis ---------------------------------------------------------------

def ink_pixels(img: Any) -> List[RGB]:
    small = img.copy()
    small.thumbnail((400, 400))
    data = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    return [p[:3] for p in data if p[3] > 200]


def ink_profile(img: Any) -> Dict[str, Any]:
    px = ink_pixels(img)
    if not px:
        return {"ink": None, "mono": True, "colors": []}
    clusters = cluster_colors([(p, 1.0) for p in px], radius=40)
    total = float(len(px))
    dom, w = clusters[0]
    members = sorted((p for p in px if color_distance(p, dom) <= 40), key=lambda p: sum(p))
    ink = members[len(members) // 2] if members else dom
    mean_lum = sum(luminance(p) for p in px) / total
    return {
        "ink": tuple(ink),
        "mono": w / total >= MONO_SHARE,
        "colors": [(rgb_to_hex(c), round(cw / total, 3)) for c, cw in clusters[:5]],
        "mean_luminance": round(mean_lum, 4),
    }


def contrast_test(img: Any, bg: RGB) -> Dict[str, Any]:
    """Composite the logo on bg and measure each ink pixel's contrast with bg."""
    small = img.copy()
    small.thumbnail((500, 500))
    data = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    contrasts: List[float] = []
    for r_, g_, b_, a_ in data:
        if a_ < INK_ALPHA:
            continue
        k = a_ / 255.0
        comp = (r_ * k + bg[0] * (1 - k), g_ * k + bg[1] * (1 - k), b_ * k + bg[2] * (1 - k))
        contrasts.append(contrast_ratio(comp, bg))
    if not contrasts:
        return {"status": "fail", "share_readable": 0.0, "contrast_ratio": 1.0, "ink_pixels": 0}
    share = sum(1 for c in contrasts if c >= LOGO_MIN_CONTRAST) / len(contrasts)
    contrasts.sort()
    med = contrasts[len(contrasts) // 2]
    status = "pass" if share >= PASS_SHARE else ("warn" if share >= WARN_SHARE else "fail")
    return {"status": status, "share_readable": round(share, 3),
            "contrast_ratio": round(max(1.0, min(21.0, med)), 2), "ink_pixels": len(contrasts)}


def composite_card(img: Any, bg: RGB, height: int = 140) -> Any:
    from PIL import Image
    logo = img.copy()
    logo.thumbnail((int(height * 4.5), int(height * 0.62)))
    card = Image.new("RGB", (max(logo.width + 60, 220), height), bg)
    card.paste(logo, ((card.width - logo.width) // 2, (height - logo.height) // 2), logo)
    return card


# --- Raster logos -------------------------------------------------------------------

def load_raster(path: Path) -> Tuple[Any, List[str]]:
    """RGBA logo with a transparent background. An opaque file gets its border
    color keyed out when the border is uniform."""
    from PIL import Image
    notes: List[str] = []
    img = Image.open(path).convert("RGBA")
    a = img.getchannel("A")
    if a.getextrema()[0] >= 250:
        rgb = img.convert("RGB")
        w, h = rgb.size
        border = [rgb.getpixel((x, 0)) for x in range(0, w, max(1, w // 64))] + \
                 [rgb.getpixel((x, h - 1)) for x in range(0, w, max(1, w // 64))] + \
                 [rgb.getpixel((0, y)) for y in range(0, h, max(1, h // 64))] + \
                 [rgb.getpixel((w - 1, y)) for y in range(0, h, max(1, h // 64))]
        clusters = cluster_colors([(p, 1.0) for p in border], radius=24)
        key, kw = clusters[0]
        if kw / len(border) >= 0.85:
            px = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
            out = []
            for p in px:
                d = color_distance(p, key)
                alpha = 0 if d < 28 else (255 if d > 70 else int((d - 28) / 42 * 255))
                out.append((p[0], p[1], p[2], alpha))
            img.putdata(out)
            notes.append(f"opaque file: its {rgb_to_hex(key)} background was keyed out to transparency")
        else:
            notes.append("opaque file with a non-uniform background: it shows as a box on any background")
    return img, notes


def edge_touch(img: Any) -> bool:
    """Ink on the outermost pixel rows or columns: the file may cut the logo."""
    a = img.getchannel("A")
    w, h = a.size
    hits = sum(1 for x in range(w) if a.getpixel((x, 0)) > INK_ALPHA or a.getpixel((x, h - 1)) > INK_ALPHA)
    hits += sum(1 for y in range(h) if a.getpixel((0, y)) > INK_ALPHA or a.getpixel((w - 1, y)) > INK_ALPHA)
    return hits > 0.005 * 2 * (w + h)


def recolor_raster(img: Any, ink: RGB) -> Any:
    from PIL import Image
    solid = Image.new("RGBA", img.size, ink + (255,))
    solid.putalpha(img.getchannel("A"))
    return solid


def crop_to_ink(img: Any) -> Any:
    bb = alpha_bbox(img)
    if not bb:
        return img
    pad = int(PAD * 2 * min(bb[2] - bb[0], bb[3] - bb[1])) + 1
    return img.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(img.width, bb[2] + pad), min(img.height, bb[3] + pad)))


# --- Orchestration ------------------------------------------------------------------

def test_backgrounds(colors: Dict[str, str], mode: str) -> Tuple[RGB, RGB]:
    """(light_bg, dark_bg) the variants are tested on: the brand bg for its own
    mode, the brand's opposite color (usually its text color) for the other."""
    bg = hex_to_rgb(colors.get("bg", ""), (255, 255, 255))
    text = hex_to_rgb(colors.get("text", ""), (0, 0, 0))
    if mode == "dark":
        dark_bg = bg
        light_bg = text if not is_dark(text) else (255, 255, 255)
    else:
        light_bg = bg
        dark_bg = text if is_dark(text) else (0, 0, 0)
    return light_bg, dark_bg


def variant_inks(light_bg: RGB, dark_bg: RGB) -> Dict[str, RGB]:
    """Ink of a generated variant: the brand's light color on dark, its dark
    color on light, pure white or near-black when that color is too weak."""
    light_ink = light_bg if contrast_ratio(light_bg, dark_bg) >= 4.5 else (255, 255, 255)
    dark_ink = dark_bg if contrast_ratio(dark_bg, light_bg) >= 4.5 else (17, 17, 17)
    return {"on_dark": light_ink, "on_light": dark_ink}


def run_pipeline(source: Path, out_dir: Path, colors: Dict[str, str], mode: str,
                 today: Optional[str] = None) -> Dict[str, Any]:
    """Audit `source` and write the variants under out_dir (the project-context
    folder). Returns {logos, logo_audit, png_fallbacks, debug}."""
    from PIL import Image
    today = today or dt.date.today().isoformat()
    logos_dir = out_dir / "assets" / "logos"
    dbg_dir = out_dir / "brand-debug" / "logo"
    logos_dir.mkdir(parents=True, exist_ok=True)
    dbg_dir.mkdir(parents=True, exist_ok=True)
    light_bg, dark_bg = test_backgrounds(colors, mode)
    brand_bg = hex_to_rgb(colors.get("bg", ""), (255, 255, 255))
    inks = variant_inks(light_bg, dark_bg)
    test_bg = {"on_light": light_bg, "on_dark": dark_bg}
    issues: List[str] = []
    debug: Dict[str, Any] = {"source": str(source.name), "test_backgrounds": {k: rgb_to_hex(v) for k, v in test_bg.items()}}
    is_svg = source.suffix.lower() == ".svg"

    # per kind: {"svg": text} or {"img": RGBA}
    kinds: Dict[str, Dict[str, Any]] = {}
    clip_flag = False
    renderer: Optional[Renderer] = None
    try:
        if is_svg:
            renderer = Renderer().__enter__()
            svg_text = source.read_text(encoding="utf-8", errors="ignore")
            meas = measure_svg(renderer, svg_text)
            debug["viewbox_audit"] = {k: v for k, v in meas.items() if k not in ("fixed_svg", "elements")}
            clip_flag = meas["viewbox_clips_ink"]
            if clip_flag:
                issues.append(
                    f"The harvested SVG's viewBox cuts the ink on the {', '.join(meas['clipped_sides'])} side "
                    f"({round(meas['cut_share'] * 100, 1)} % of the ink hidden): every variant uses the measured ink box; "
                    f"scale CSS heights by {meas['height_factor']} to keep the optical size.")
            if meas["excluded_shapes"]:
                debug["note_excluded"] = (f"{meas['excluded_shapes']} shape(s) lie entirely outside the declared viewBox "
                                          "(cropped out on purpose, for example a pictogram) and were dropped")
            full_img = renderer.rasterize(meas["fixed_svg"], 600)
            ink_box = meas["ink_box"]
            ratio = ink_box[2] / max(ink_box[3], 1e-6)
            mark_svg = split_mark(renderer, meas)
            if mark_svg:
                kinds["wordmark"] = {"svg": meas["fixed_svg"], "img": full_img}
                kinds["mark"] = {"svg": mark_svg, "img": renderer.rasterize(mark_svg, 600)}
            else:
                kinds["wordmark" if ratio >= WORDMARK_MIN_RATIO else "mark"] = {"svg": meas["fixed_svg"], "img": full_img}
            original_img = full_img
        else:
            img, notes = load_raster(source)
            debug["raster_notes"] = notes
            if any("non-uniform" in n for n in notes):
                issues.append("The logo file has an opaque, non-uniform background: it shows as a box; ask for a transparent PNG or an SVG.")
            clip_flag = edge_touch(img)
            if clip_flag:
                issues.append("The logo's ink touches the edge of the file: the file may cut part of the logo; ask for the original.")
            img = crop_to_ink(img)
            ratio = img.width / max(1, img.height)
            kinds["wordmark" if ratio >= WORDMARK_MIN_RATIO else "mark"] = {"img": img}
            original_img = img

        # the harvested file on the brand's own background (the dark-on-dark miss)
        orig = contrast_test(original_img, brand_bg)
        debug["original_on_brand_bg"] = {**orig, "bg": rgb_to_hex(brand_bg)}
        composite_card(original_img, brand_bg).save(dbg_dir / "original-on-brand-bg.png")

        prof = ink_profile(original_img)
        debug["ink_profile"] = {k: (rgb_to_hex(v) if k == "ink" and v else v) for k, v in prof.items()}
        if prof["ink"] is None:
            raise ValueError("no ink found in the logo")
        natural = "on_light" if is_dark(prof["ink"]) else "on_dark"
        other = "on_light" if natural == "on_dark" else "on_dark"
        if orig["status"] != "pass":
            issues.append(
                f"The harvested logo reads at {orig['contrast_ratio']}:1 on the brand background {rgb_to_hex(brand_bg)} "
                f"({int(orig['share_readable'] * 100)} % of its ink at 3:1): the site shows it through CSS (a filter or a "
                f"color set by the page). Use logos.{'on_dark' if mode == 'dark' else 'on_light'} on that background.")

        logos: Dict[str, Dict[str, Any]] = {}
        fallbacks: Dict[str, Dict[str, str]] = {}
        checks: List[Dict[str, Any]] = []
        for kind, data in kinds.items():
            for variant in (natural, other):
                generated = variant != natural
                ink = inks[variant]
                base = f"{kind}-{variant.replace('_', '-')}"
                if is_svg:
                    svg_out = recolor_svg(data["svg"], rgb_to_hex(ink)) if generated else data["svg"]
                    path = logos_dir / f"{base}.svg"
                    path.write_text(svg_out + "\n", encoding="utf-8")
                    rendered = renderer.rasterize(svg_out, FALLBACK_PX)  # type: ignore[union-attr]
                    rendered.save(logos_dir / f"{base}.png")
                    fallbacks.setdefault(variant, {})[kind] = f"assets/logos/{base}.png"
                    m = re.search(r'viewBox="\s*[-\d.e]+\s+[-\d.e]+\s+([\d.e]+)\s+([\d.e]+)', svg_out)
                    w_h = (max(1, int(round(float(m.group(1))))), max(1, int(round(float(m.group(2)))))) if m else rendered.size
                    fmt = "svg"
                else:
                    rendered = recolor_raster(data["img"], ink) if generated else data["img"]
                    path = logos_dir / f"{base}.png"
                    rendered.save(path)
                    w_h = rendered.size
                    fmt = "png"
                ink_hex = rgb_to_hex(ink) if generated else rgb_to_hex(ink_profile(rendered)["ink"] or prof["ink"])
                test = contrast_test(rendered, test_bg[variant])
                composite_card(rendered, test_bg[variant]).save(dbg_dir / f"{base}-test.png")
                note = (f"{'generated, one color ' + rgb_to_hex(ink) if generated else 'original colors'}; "
                        f"{int(test['share_readable'] * 100)} % of ink pixels at 3:1 or more on {rgb_to_hex(test_bg[variant])}")
                status = test["status"]
                if generated and not prof["mono"] and status == "pass":
                    status = "warn"
                    note += "; knocked out from a multi-color logo, confirm with the founder"
                checks.append({"variant": variant, "kind": kind, "status": status,
                               "viewbox_clips_ink": bool(clip_flag), "contrast_ratio": test["contrast_ratio"], "note": note})
                logos.setdefault(variant, {})[kind] = {"path": f"assets/logos/{path.name}", "format": fmt,
                                                       "width": int(w_h[0]), "height": int(w_h[1]), "ink": ink_hex}
                if status == "fail":
                    issues.append(f"The {kind} {variant} variant reads at {test['contrast_ratio']}:1 on {rgb_to_hex(test_bg[variant])}: not usable there.")
    finally:
        if renderer is not None:
            renderer.__exit__(None, None, None)

    states = [c["status"] for c in checks]
    status = "fail" if "fail" in states else ("warn" if ("warn" in states or issues) else "pass")
    audit = {"status": status, "method": "render", "checked_at": today, "checks": checks, "issues": issues}
    debug["audit"] = audit
    (dbg_dir / "audit.json").write_text(json.dumps(debug, indent=2) + "\n", encoding="utf-8")
    return {"logos": logos, "logo_audit": audit, "png_fallbacks": fallbacks, "debug": debug}


# --- CLI ------------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logo", required=True, help="Logo file (SVG, PNG, WebP, JPEG)")
    p.add_argument("--out", required=True, help="project-context folder (writes assets/logos/ and brand-debug/logo/)")
    p.add_argument("--brand", help="brand-draft.json or brand.json to read colors.bg, colors.text and mode from")
    p.add_argument("--bg", help="Brand background color (#rrggbb), when no --brand")
    p.add_argument("--text", help="Brand text color (#rrggbb), when no --brand")
    p.add_argument("--update", action="store_true", help="Write logos, logo_audit and the PNG fallbacks into the --brand file")
    p.add_argument("--json", action="store_true", help="Print the result as JSON")
    args = p.parse_args(argv)

    src = Path(args.logo).expanduser()
    if not src.is_file():
        print(f"logo_pipeline: {src} not found", file=sys.stderr)
        return 2
    if src.suffix.lower() != ".svg" and src.suffix.lower() not in RASTER_EXT:
        print(f"logo_pipeline: unsupported format {src.suffix}; give an SVG, PNG, WebP or JPEG", file=sys.stderr)
        return 2
    brand: Dict[str, Any] = {}
    if args.brand:
        try:
            brand = json.loads(Path(args.brand).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"logo_pipeline: cannot read {args.brand}: {e}", file=sys.stderr)
            return 2
    colors = dict(brand.get("colors") or {})
    if args.bg:
        colors["bg"] = args.bg
    if args.text:
        colors["text"] = args.text
    if not colors.get("bg"):
        print("logo_pipeline: give --brand or --bg", file=sys.stderr)
        return 2
    bg = hex_to_rgb(colors["bg"], (255, 255, 255))
    colors.setdefault("text", "#ffffff" if is_dark(bg) else "#111111")
    mode = brand.get("mode") or ("dark" if is_dark(bg) else "light")
    out = Path(args.out).expanduser().resolve()
    try:
        res = run_pipeline(src, out, colors, mode)
    except ImportError as e:
        print(f"logo_pipeline: Playwright or Pillow missing ({e}). Install with "
              "`pip install -r agents/project-context/scripts/requirements.txt && python -m playwright install chromium`.",
              file=sys.stderr)
        return 3
    except (ValueError, OSError) as e:
        print(f"logo_pipeline: {e}", file=sys.stderr)
        return 2
    if args.brand and args.update:
        brand["logos"] = res["logos"]
        brand["logo_audit"] = res["logo_audit"]
        ext = brand.setdefault("extensions", {}).setdefault("extract_brand", {})
        ext["logo_png"] = res["png_fallbacks"]
        Path(args.brand).write_text(json.dumps(brand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({k: v for k, v in res.items() if k != "debug"}, indent=2))
    else:
        a = res["logo_audit"]
        print(f"logo audit: {a['status']}")
        for c in a["checks"]:
            print(f"  {c['kind']:<9} {c['variant']:<9} {c['status']:<5} {c['contrast_ratio']}:1  {c['note']}")
        for i in a["issues"]:
            print(f"  - {i}")
        print(f"files in {out / 'assets' / 'logos'}, test composites in {out / 'brand-debug' / 'logo'}")
    return 0 if res["logo_audit"]["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
