#!/usr/bin/env python3
"""qa.py: measure the built deck in Chromium and write qa.json.

  python3 scripts/qa.py <html dir> [--renders <export dir>] [--out qa.json] [--no-sheet]

Checks, per slide (DOM measures after fit.js, not the model's eye):
  text-too-long      fit.js could not fit a text at its minimum size (error)
  overflow           a block, the main area or the frame overflows (error)
  outside-slide      an element leaves the slide (error)
  outside-safe-zone  text closer to the edge than the direction's safe margin (error)
  text-too-small     text under the feed-legible minimum: 24 px, 20 px for
                     sources, folios and chart ticks (error)
  contrast           WCAG ratio per text node against what is really under it
                     (elementsFromPoint): 4.5:1, 3:1 from 40 px, 7:1 on a
                     highlight (error); text over a photo is a warning
  empty-block        a block with no text and no media (error)
  missing-asset      an image that did not load (error); low-res-image (warning)
  collision          two blocks whose text or media overlap (error)
  dead-space         the largest empty horizontal band exceeds 24 % of the
                     slide height, 30 % on a calm slide (warning); fill
                     ratio in metrics
  blurred-shadow, backdrop-filter, blur-filter, gradient-text (error) and
  gradient, side-stripe, big-radius (warning): the visual tells of a
  generated deck, made mechanical
Global: font-fallback (a direction font did not load), build-report errors
(schema, claims, copy gate), output files (PNG and JPEG dimensions, sRGB
profile, PDF page count and page size, PDF weight).

Also writes the contact sheet at 25 % scale (contact-sheet.jpg) through
shared/skills/reviewing-renders/scripts/contact_sheet.py, or a local PIL
fallback when the shared script is absent.

Exit 0 when no error, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent.parent
SHARED_SHEET = REPO_ROOT / "shared" / "skills" / "reviewing-renders" / "scripts" / "contact_sheet.py"

META_SELECTOR = ".src,.handle,.folio,.c-tick,.c-note,.ph-cap,.ph-credit,.shot-url,.q-tr,.q-role,.lr-label,.vis-cap,.shot-cap,.logo,.ann-pin"

MEASURE_JS = r"""
(cfg) => {
  const W = cfg.w, H = cfg.h, SAFE = cfg.safe;
  const parse = (c) => {
    if (!c) return null;
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const v = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1};
  };
  const lum = ({r, g, b}) => [r, g, b].map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); })
    .reduce((s, x, i) => s + x * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const blend = (fg, bg) => fg.a >= 1 ? fg : {r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1};
  const gradColors = (img) => (img.match(/rgba?\([^)]+\)/g) || []).map(parse).filter(c => c && c.a >= 0.5);
  const isShape = (e) => e instanceof SVGGeometryElement;
  const visible = (el) => { const cs = getComputedStyle(el); return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05; };
  const label = (el) => { const b = el.closest('.b'); return (b ? 'block ' + b.dataset.b + ' ' : '') + el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''); };
  const shadowBlur = (s) => {
    if (!s || s === 'none') return 0;
    let mx = 0;
    for (const part of s.split(/,(?![^(]*\))/)) {
      const nums = (part.replace(/rgba?\([^)]+\)/g, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
      if (nums.length >= 3) mx = Math.max(mx, nums[2]);
    }
    return mx;
  };
  const out = [];
  const slides = [...document.querySelectorAll('section.slide')];
  slides.forEach((slide, si) => {
    slide.scrollIntoView({block: 'start'});
    const sr = slide.getBoundingClientRect();
    const errors = [], warnings = [];
    const add = (lvl, code, message, where) => (lvl === 'error' ? errors : warnings).push({code, message, where: where || ''});
    // Text nodes and their rects.
    const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT);
    const texts = new Map();
    let n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const el = n.parentElement;
      if (!el || !visible(el) || el.closest('.asset-missing')) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      const rects = [...range.getClientRects()].filter(r => r.width > 0.5 && r.height > 0.5);
      if (!rects.length) continue;
      if (!texts.has(el)) texts.set(el, []);
      texts.get(el).push(...rects);
    }
    let minSize = 999, minContrast = 99, words = 0;
    const contentRects = [];  // {block, rect}
    const blockOf = (el) => { const b = el.closest('.b'); if (b) return 'b' + b.dataset.b; if (el.closest('.s-head')) return 'head'; if (el.closest('.s-foot')) return 'foot'; return 'deco'; };
    for (const [el, rects] of texts) {
      const cs = getComputedStyle(el);
      let fs = parseFloat(cs.fontSize);
      const svg = el.closest('svg');
      if (svg) {
        const vb = svg.viewBox && svg.viewBox.baseVal;
        const r = svg.getBoundingClientRect();
        if (vb && vb.width) fs = fs * r.width / vb.width;
      }
      const meta = !!el.closest(cfg.meta);
      const min = meta ? cfg.min_meta : cfg.min_text;
      const txt = el.textContent.trim().slice(0, 48);
      words += el.textContent.trim().split(/\s+/).length;
      if (fs < min - 0.5) add('error', 'text-too-small', `"${txt}" renders at ${fs.toFixed(1)} px, min ${min} px at 1080 wide (feed scale).`, label(el));
      minSize = Math.min(minSize, fs);
      for (const r of rects) {
        // Vertical extent of the glyphs (cap height and descenders), not the
        // font's content area, which spills past a tight line-height.
        const mid = (r.top + r.bottom) / 2 - sr.top;
        const x0 = r.left - sr.left, x1 = r.right - sr.left, y0 = mid - fs * 0.45, y1 = mid + fs * 0.45;
        contentRects.push({block: blockOf(el), x0, y0, x1, y1});
        if (x0 < -1 || y0 < -1 || x1 > W + 1 || y1 > H + 1) { add('error', 'outside-slide', `"${txt}" leaves the slide.`, label(el)); break; }
        if (!el.closest('[data-bleed]') && (x0 < SAFE - 2 || y0 < SAFE - 2 || x1 > W - SAFE + 2 || y1 > H - SAFE + 2)) {
          add('error', 'outside-safe-zone', `"${txt}" is within ${SAFE} px of the edge.`, label(el)); break;
        }
      }
      // Contrast against what is under the first line.
      const r0 = rects[0];
      const cx = Math.min(Math.max(r0.left + Math.min(r0.width / 2, 40), 0), window.innerWidth - 1);
      const cy = Math.min(Math.max(r0.top + r0.height / 2, 0), window.innerHeight - 1);
      const stack = document.elementsFromPoint(cx, cy);
      let start = stack.indexOf(el); if (start < 0) start = 0;
      let bgs = null, onImage = false;
      for (let k = start; k < stack.length; k++) {
        const e = stack[k];
        if (e === el && svg) continue;
        if (['IMG', 'VIDEO', 'CANVAS'].includes(e.tagName) || e.tagName.toLowerCase() === 'image') { onImage = true; break; }
        const ecs = getComputedStyle(e);
        if (isShape(e) && e !== el) { const f = parse(ecs.fill); if (f && f.a >= 0.5 && ecs.fill !== 'none') { bgs = [f]; break; } continue; }
        const bc = parse(ecs.backgroundColor);
        const gc = ecs.backgroundImage && ecs.backgroundImage !== 'none' ? gradColors(ecs.backgroundImage) : [];
        if (gc.length) { bgs = gc; if (bc && bc.a >= 0.5) bgs.push(bc); break; }
        if (bc && bc.a >= 0.5) { bgs = [bc]; break; }
        if (e === slide) break;
      }
      if (onImage && !bgs) { add('warning', 'text-on-image', `"${txt}" sits on a photo: contrast not measurable, check it on the render.`, label(el)); continue; }
      if (!bgs) bgs = [parse(getComputedStyle(slide).backgroundColor) || {r: 255, g: 255, b: 255, a: 1}];
      const fg0 = parse(svg ? cs.fill : cs.color) || parse(cs.color);
      if (!fg0) continue;
      const bold = parseInt(cs.fontWeight) >= 700;
      let need = (fs >= 40 || (fs >= 32 && bold)) ? 3 : 4.5;
      const hlEl = el.closest('.hl');
      if (hlEl) {
        const hcs = getComputedStyle(hlEl), hb = parse(hcs.backgroundColor);
        if (hcs.backgroundImage !== 'none' || (hb && hb.a > 0.5)) need = 7;
      }
      for (const bg of bgs) {
        const fg = blend(fg0, bg);
        const rr = ratio(fg, bg);
        minContrast = Math.min(minContrast, rr);
        if (rr < need) { add('error', 'contrast', `"${txt}" ${rr.toFixed(2)}:1 on rgb(${bg.r},${bg.g},${bg.b}), needs ${need}:1.`, label(el)); break; }
      }
    }
    // Media rects, images.
    slide.querySelectorAll('img').forEach(img => {
      if (img.classList.contains('ph-mat')) return;
      const r = img.getBoundingClientRect();
      if (!img.complete || img.naturalWidth === 0) { add('error', 'missing-asset', `Image did not load: ${img.getAttribute('src')}`, label(img)); return; }
      const shown = Math.min(r.width, r.height * img.naturalWidth / img.naturalHeight);
      if (img.naturalWidth < shown * 0.8) add('warning', 'low-res-image', `${img.getAttribute('src')} is ${img.naturalWidth} px wide, shown at ${Math.round(shown)} px.`, label(img));
      contentRects.push({block: blockOf(img), x0: r.left - sr.left, y0: r.top - sr.top, x1: r.right - sr.left, y1: r.bottom - sr.top, media: true});
    });
    slide.querySelectorAll('.b > svg, .vis svg, .c-box svg, .logo svg').forEach(s => {
      const r = s.getBoundingClientRect();
      contentRects.push({block: blockOf(s), x0: r.left - sr.left, y0: r.top - sr.top, x1: r.right - sr.left, y1: r.bottom - sr.top, media: true});
    });
    slide.querySelectorAll('.asset-missing').forEach(m => add('error', 'missing-asset', [...m.children].map(c => c.textContent.trim()).join(': ').slice(0, 120), label(m)));
    // Empty blocks.
    slide.querySelectorAll('.b').forEach(b => {
      const hasText = b.textContent.trim().length > 0;
      const hasMedia = b.querySelector('img,svg,.asset-missing');
      if (!hasText && !hasMedia) add('error', 'empty-block', `Block ${b.dataset.b} (${b.className.split(' ')[1]}) renders nothing.`, 'block ' + b.dataset.b);
    });
    // Collisions between blocks (text or media of one block over another).
    const byBlock = {};
    for (const c of contentRects) { if (c.block === 'deco') continue; (byBlock[c.block] = byBlock[c.block] || []).push(c); }
    const keys = Object.keys(byBlock);
    const hit = new Set();
    for (let a = 0; a < keys.length; a++) for (let b = a + 1; b < keys.length; b++) {
      const A = byBlock[keys[a]], B = byBlock[keys[b]];
      const under = (k) => { const el = k.startsWith('b') ? slide.querySelector(`.b[data-b="${k.slice(1)}"]`) : null; return el && el.closest('[data-under]'); };
      if (under(keys[a]) || under(keys[b])) continue;
      outer: for (const p of A) for (const q of B) {
        const ix = Math.min(p.x1, q.x1) - Math.max(p.x0, q.x0), iy = Math.min(p.y1, q.y1) - Math.max(p.y0, q.y0);
        if (ix > 3 && iy > 3 && ix * iy > 24) { const key = keys[a] + '/' + keys[b]; if (!hit.has(key)) { hit.add(key); add('error', 'collision', `${keys[a]} overlaps ${keys[b]}.`, key); } break outer; }
      }
    }
    // Dead space: largest band with no text or media, inside the safe area.
    const ys = contentRects.filter(c => c.y1 > SAFE && c.y0 < H - SAFE).map(c => [Math.max(c.y0, SAFE), Math.min(c.y1, H - SAFE)]).sort((p, q) => p[0] - q[0]);
    let cursor = SAFE, gap = 0, covered = 0;
    for (const [a, b] of ys) { if (a > cursor) gap = Math.max(gap, a - cursor); if (b > cursor) { covered += b - Math.max(a, cursor); cursor = b; } }
    gap = Math.max(gap, H - SAFE - cursor);
    const fill = covered / (H - 2 * SAFE);
    const maxGap = (cfg.tones[si] === 'calm') ? cfg.max_gap_calm : cfg.max_gap;
    if (gap / H > maxGap) add('warning', 'dead-space', `An empty band of ${Math.round(gap)} px (${Math.round(gap / H * 100)} % of the height) with no text or media.`, '');
    // Tells of a generated deck.
    slide.querySelectorAll('*').forEach(e => {
      const cs = getComputedStyle(e);
      if (shadowBlur(cs.boxShadow) > 0) add('error', 'blurred-shadow', 'box-shadow with blur: use a hard offset or none.', label(e));
      if (shadowBlur(cs.textShadow) > 0) add('error', 'blurred-shadow', 'text-shadow with blur (glow).', label(e));
      if (cs.backdropFilter && cs.backdropFilter !== 'none') add('error', 'backdrop-filter', 'backdrop-filter (glassmorphism, breaks PDF export).', label(e));
      if (/blur\(/.test(cs.filter) && !e.classList.contains('ph-mat')) add('error', 'blur-filter', 'filter: blur outside a photo mat.', label(e));
      if ((cs.webkitBackgroundClip || cs.backgroundClip) === 'text') add('error', 'gradient-text', 'background-clip: text.', label(e));
      if (/gradient/.test(cs.backgroundImage)) {
        const cols = gradColors(cs.backgroundImage).map(c => `${c.r},${c.g},${c.b}`);
        if (new Set(cols).size >= 2) add('warning', 'gradient', 'Gradient between two opaque colours.', label(e));
      }
      const bl = parseFloat(cs.borderLeftWidth), others = parseFloat(cs.borderTopWidth) + parseFloat(cs.borderRightWidth) + parseFloat(cs.borderBottomWidth);
      if (bl >= 4 && others === 0 && e.getBoundingClientRect().height > 60) add('warning', 'side-stripe', 'Thick border on one side only (side-stripe card).', label(e));
      const rad = parseFloat(cs.borderTopLeftRadius);
      const r = e.getBoundingClientRect();
      if (rad > 28 && Math.abs(r.width - r.height) > 4 && rad < Math.min(r.width, r.height) / 2 - 1) add('warning', 'big-radius', `border-radius ${rad} px.`, label(e));
    });
    const dedupe = (arr) => { const seen = new Set(); return arr.filter(x => { const k = x.code + x.where + x.message; if (seen.has(k)) return false; seen.add(k); return true; }); };
    out.push({index: si + 1, id: slide.id, role: slide.dataset.role, layout: slide.dataset.layout,
      errors: dedupe(errors), warnings: dedupe(warnings),
      metrics: {min_text_px: Math.round(minSize * 10) / 10, min_contrast: Math.round(minContrast * 100) / 100,
                fill_ratio: Math.round(fill * 100) / 100, largest_gap_ratio: Math.round(gap / H * 100) / 100, words}});
  });
  const fonts = cfg.fonts.map(f => ({family: f, loaded: document.fonts.check(`32px "${f}"`)}));
  return {slides: out, fonts, fit: window.__fit};
}
"""


def measure(html_dir: Path, rep: Dict[str, Any]) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    w, h = int(rep.get("width", 1080)), int(rep.get("height", 1350))
    fonts = [f for f in rep.get("fonts", []) if f]
    min_text = rep.get("min_text") or {}
    cfg = {"w": w, "h": h, "safe": int(rep.get("safe_margin", 60)), "meta": META_SELECTOR,
           "min_text": min_text.get("text", 24), "min_meta": min_text.get("meta", 20), "max_gap": 0.24, "max_gap_calm": 0.30,
           "tones": rep.get("tones") or [], "fonts": fonts}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto((html_dir / "index.html").resolve().as_uri(), wait_until="load")
        page.wait_for_function("document.body.dataset.fitted === '1'", timeout=30000)
        page.add_style_tag(content="*{pointer-events:auto !important}.deck{gap:0 !important;padding:0 !important}")
        page.wait_for_timeout(50)
        data = page.evaluate(MEASURE_JS, cfg)
        browser.close()
    return data


def check_outputs(export: Path, rep: Dict[str, Any], n_slides: int) -> Dict[str, Any]:
    from PIL import Image
    w, h = int(rep.get("width", 1080)), int(rep.get("height", 1350))
    res: Dict[str, Any] = {"errors": [], "warnings": [], "png": [], "jpg": [], "pdf": None}
    pngs = sorted(export.glob("slide-*.png"))
    jpgs = sorted(export.glob("slide-*.jpg"))
    for kind, files in (("png", pngs), ("jpg", jpgs)):
        if files and len(files) != n_slides:
            res["errors"].append({"code": "output-count", "message": f"{len(files)} {kind} files for {n_slides} slides.", "where": str(export)})
        for f in files:
            with Image.open(f) as im:
                ok_dims = (im.size[0] == w and im.size[1] == h) if kind == "jpg" else (im.size[0] % w == 0 and im.size[0] * h == im.size[1] * w)
                res[kind].append({"file": f.name, "size": list(im.size), "kb": round(f.stat().st_size / 1024), "srgb": bool(im.info.get("icc_profile"))})
                if not ok_dims:
                    res["errors"].append({"code": "output-size", "message": f"{f.name} is {im.size[0]}x{im.size[1]}, expected {w}x{h}.", "where": f.name})
                if kind == "jpg" and f.stat().st_size > 1_500_000:
                    res["warnings"].append({"code": "heavy-jpeg", "message": f"{f.name} weighs {f.stat().st_size // 1024} KB.", "where": f.name})
    pdf = export / "carousel.pdf"
    if pdf.exists():
        info: Dict[str, Any] = {"file": pdf.name, "mb": round(pdf.stat().st_size / 1_048_576, 2)}
        try:
            from pypdf import PdfReader
            r = PdfReader(str(pdf))
            info["pages"] = len(r.pages)
            box = r.pages[0].mediabox
            info["page_pt"] = [round(float(box.width), 1), round(float(box.height), 1)]
        except Exception:  # noqa: BLE001
            try:
                out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
                info["pages"] = int(re.search(r"Pages:\s+(\d+)", out).group(1))
                m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", out)
                info["page_pt"] = [float(m.group(1)), float(m.group(2))]
            except Exception:  # noqa: BLE001
                pass
        if info.get("pages") is not None and info["pages"] != n_slides:
            res["errors"].append({"code": "pdf-pages", "message": f"PDF has {info['pages']} pages for {n_slides} slides.", "where": pdf.name})
        if info.get("page_pt"):
            pw_, ph_ = info["page_pt"]
            if abs(pw_ / ph_ - w / h) > 0.01:
                res["errors"].append({"code": "pdf-size", "message": f"PDF page {pw_}x{ph_} pt does not match {w}x{h}.", "where": pdf.name})
        if info["mb"] > 100:
            res["errors"].append({"code": "pdf-weight", "message": f"PDF is {info['mb']} MB, LinkedIn caps documents at 100 MB.", "where": pdf.name})
        elif info["mb"] > 15:
            res["warnings"].append({"code": "pdf-weight", "message": f"PDF is {info['mb']} MB; under 15 MB uploads faster.", "where": pdf.name})
        res["pdf"] = info
    return res


def contact_sheet(export: Path, rep: Dict[str, Any], title: str) -> Optional[str]:
    pngs = sorted(export.glob("slide-*.png")) or sorted(export.glob("slide-*.jpg"))
    if not pngs:
        return None
    w, h = int(rep.get("width", 1080)), int(rep.get("height", 1350))
    out_png = export / "contact-sheet.png"
    tile = str(round(w * 0.25))
    if SHARED_SHEET.exists():
        r = subprocess.run([sys.executable, str(SHARED_SHEET), *[str(p) for p in pngs], "-o", str(out_png),
                            "--scale", tile, "--cols", str(min(len(pngs), 5)), "--expect", f"{w}x{h}", "--title", title],
                           capture_output=True, text=True)
        if not out_png.exists():
            print(r.stdout, r.stderr, file=sys.stderr)
    if not out_png.exists():
        local_sheet(pngs, out_png, int(tile), title)
    from PIL import Image
    jpg = export / "contact-sheet.jpg"
    with Image.open(out_png) as im:
        im.convert("RGB").save(jpg, quality=86, optimize=True)
    out_png.unlink()
    return jpg.name


def local_sheet(files: List[Path], out: Path, tile_w: int, title: str) -> None:
    """Fallback when shared/skills/reviewing-renders is absent."""
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert("RGB") for f in files]
    tw = tile_w
    th = round(ims[0].size[1] * tw / ims[0].size[0])
    cols = min(5, len(ims))
    rows = -(-len(ims) // cols)
    pad, lab = 16, 26
    sheet = Image.new("RGB", (pad + cols * (tw + pad), 40 + rows * (th + lab + pad)), (154, 154, 154))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 12), title, fill=(20, 20, 20))
    for i, im in enumerate(ims):
        x = pad + (i % cols) * (tw + pad)
        y = 40 + (i // cols) * (th + lab + pad)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x, y + th + 6), f"#{i + 1:02d} {files[i].name}", fill=(20, 20, 20))
    sheet.save(out)


def slide_of(where: str) -> Optional[int]:
    m = re.match(r"\$\.slides\[(\d+)\]", where or "")
    return int(m.group(1)) + 1 if m else None


def run(html_dir: Path, export: Optional[Path], out: Path, sheet: bool = True) -> Dict[str, Any]:
    rep_path = html_dir / "build-report.json"
    rep = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
    data = measure(html_dir, rep)
    slides = data["slides"]
    fit = data.get("fit") or {}
    for fs in fit.get("slides", []):
        s = slides[fs["index"] - 1]
        for it in fs.get("items", []):
            if it.get("status") == "fail":
                s["errors"].insert(0, {"code": "text-too-long", "message": f"{it['kind']}: {it['reason']}. Shorten the copy in deck.json.",
                                       "where": f"block {it['block']}"})
        if fs.get("overflow"):
            s["errors"].insert(0, {"code": "overflow", "message": f"Content overflows ({', '.join(fs.get('overflowAt', []))}).", "where": ""})
        s["fit"] = [{k: it[k] for k in ("block", "kind", "size", "lines", "maxLines", "status")} for it in fs.get("items", [])]
    glob_err: List[Dict[str, Any]] = []
    glob_warn: List[Dict[str, Any]] = []
    for f in data.get("fonts", []):
        if not f["loaded"]:
            glob_warn.append({"code": "font-fallback", "message": f"Font '{f['family']}' did not load (offline or wrong name): a fallback face was measured and rendered.", "where": "fonts"})
    for lvl, bucket in (("errors", glob_err), ("warnings", glob_warn)):
        for e in rep.get(lvl, []):
            k = slide_of(e.get("where", ""))
            item = {"code": "build:" + e["code"], "message": e["message"], "where": e.get("where", "")}
            if k and k <= len(slides):
                slides[k - 1][lvl].insert(0, item)
            else:
                bucket.append(item)
    outputs = None
    sheet_name = None
    if export and export.exists():
        outputs = check_outputs(export, rep, len(slides))
        glob_err += outputs.pop("errors")
        glob_warn += outputs.pop("warnings")
        if sheet:
            sheet_name = contact_sheet(export, rep, f"{rep.get('direction', '')} {rep.get('width')}x{rep.get('height')}, 25 % scale")
    n_err = len(glob_err) + sum(len(s["errors"]) for s in slides)
    n_warn = len(glob_warn) + sum(len(s["warnings"]) for s in slides)
    result = {
        "status": "pass" if n_err == 0 else "fail",
        "summary": {"errors": n_err, "warnings": n_warn, "slides": len(slides), "direction": rep.get("direction"),
                    "format": rep.get("format"), "size": [rep.get("width"), rep.get("height")],
                    "copy_gate": rep.get("copy_gate")},
        "global": {"errors": glob_err, "warnings": glob_warn},
        "slides": slides,
        "outputs": outputs,
        "contact_sheet": sheet_name,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def print_summary(r: Dict[str, Any]) -> None:
    for e in r["global"]["errors"]:
        print(f"ERROR {e['code']}: {e['message']}")
    for s in r["slides"]:
        for e in s["errors"]:
            print(f"ERROR slide {s['index']:02d} {e['code']} {e.get('where', '')}: {e['message']}")
    for s in r["slides"]:
        for w in s["warnings"]:
            print(f"warn  slide {s['index']:02d} {w['code']} {w.get('where', '')}: {w['message']}")
    for w in r["global"]["warnings"]:
        print(f"warn  {w['code']}: {w['message']}")
    sm = r["summary"]
    print(f"qa: {r['status'].upper()}, {sm['errors']} errors, {sm['warnings']} warnings, {sm['slides']} slides")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="Dir holding index.html and build-report.json")
    ap.add_argument("--renders", help="Export dir with slide-NN.png/.jpg and carousel.pdf (default <html>/../export)")
    ap.add_argument("--out", help="qa.json path (default <renders>/qa.json)")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    html_dir = Path(args.html).resolve()
    export = Path(args.renders).resolve() if args.renders else html_dir.parent / "export"
    out = Path(args.out).resolve() if args.out else export / "qa.json"
    r = run(html_dir, export, out, not args.no_sheet)
    if not args.quiet:
        print_summary(r)
    return 0 if r["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
