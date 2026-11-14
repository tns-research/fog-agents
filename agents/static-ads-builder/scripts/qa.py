#!/usr/bin/env python3
"""qa.py: measure the built ads in Chromium and write qa.json.

  python3 scripts/qa.py <html dir> [--renders DIR] [--out qa.json] [--no-sheet]

Checks per ad and format (DOM measures after fit.js, not the model's eye):
  text-too-long      fit.js could not fit a text at its minimum size (error)
  overflow           a box of the ad overflows (error)
  outside-canvas     text leaves the canvas (error)
  outside-safe-zone  text or logo outside the safe box of its format: 72 px
                     on feed formats, Meta Reels zones on 9:16 (top 14 %,
                     bottom 35 %, sides 6 %) (error)
  text-too-small     under 28 px (copy) or 22 px (source, labels) on a
                     1080 px canvas, the feed-legibility floor (error)
  contrast           WCAG ratio per text node against what is really under
                     it: 4.5:1, 3:1 from 40 px or 32 px bold (error); text
                     straight on a photo is a warning (no measurable colour)
  dom-text-mismatch  the words the browser laid out differ from ads.json (error)
  missing-asset      media that did not load (error); low-res-image (warning)
  dead-space         an empty band over 30 % of the safe box height, feed
                     formats (warning)
  dead-space-9x16    9:16 only: the text zone (Reels safe box) leaves an empty
                     band over 14 % of its height at the top, between blocks
                     or above the Reels line (warning)
  empty-band         9:16 only: under half of Meta's reserved bottom band (35 %)
                     carries the photo, a panel or the footer slab, so the ad
                     reads as letterboxed when the interface is off (warning)
  logo-too-small     a mark under 64 px or a wordmark under 40 px high on a
                     1080 px canvas, the feed-legibility floor (error)
  logo-contrast      the logo under 3:1 against what is really under it, the
                     WCAG 1.4.11 floor for graphics (error)
  logo-clear-space   text, media or a panel inside the logo's clear space
                     (half its height around the visible logo) (error)
  build:logo-text    the brand has no usable logo file and its name is
                     typeset instead (warning)
  blurred-shadow, backdrop-filter, blur-filter, gradient-text (error) and
  gradient (warning): the visual tells of a generated ad, made mechanical
Global: font-fallback (a brand font did not load), build-report errors
(schema, claims, numbers, style needs, copy gate), output files (one PNG per
section at the exact size).

Also writes the contact sheet (renders/contact-sheet.jpg, 360 px tiles)
through shared/skills/reviewing-renders/scripts/contact_sheet.py.

Exit 0 when no error, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adspec  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent.parent
SHARED_SHEET = REPO_ROOT / "shared" / "skills" / "reviewing-renders" / "scripts" / "contact_sheet.py"

META_SELECTOR = ".src,.attr,.li-l,.badge,.cm-a,.col-l,.mf-l,.br-l,.cr-l,.ba-l,.logo-name"
PANELS = ".note,.quote-card,.thread,.mf,.cmp-bg,.review,.cr,.ba,.br-box,.q-node,.co,.cta.button,.hy-panels span"
MIN_TEXT, MIN_META = 28, 22
MAX_GAP = 0.30
MAX_GAP_STORY = 0.14
MIN_BAND_FILL = 0.5

MEASURE_JS = r"""
(cfg) => {
  const parse = (c) => {
    if (!c) return null;
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const v = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number);
    return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1};
  };
  const lum = ({r, g, b}) => [r, g, b].map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); })
    .reduce((s, x, i) => s + x * [0.2126, 0.7152, 0.0722][i], 0);
  const hexRgb = (h) => { const n = parseInt(h.slice(1), 16); return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const blend = (fg, bg) => fg.a >= 1 ? fg : {r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1};
  const gradColors = (img) => (img.match(/rgba?\([^)]+\)/g) || []).map(parse).filter(c => c && c.a >= 0.5);
  const visible = (el) => { const cs = getComputedStyle(el); return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05; };
  const label = (el) => el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.split(' ')[0] : '');
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
  document.querySelectorAll('section.ad').forEach(sec => {
    sec.scrollIntoView({block: 'start'});
    const sr = sec.getBoundingClientRect();
    const W = sr.width, H = sr.height;
    const st = parseFloat(sec.style.getPropertyValue('--st')), sx = parseFloat(sec.style.getPropertyValue('--sr')), sb = parseFloat(sec.style.getPropertyValue('--sb')), sl = parseFloat(sec.style.getPropertyValue('--sl'));
    const errors = [], warnings = [];
    const add = (lvl, code, message, where) => (lvl === 'error' ? errors : warnings).push({code, message, where: where || ''});
    const texts = new Map();
    const walker = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if (!n.textContent.trim()) continue;
      const el = n.parentElement;
      if (!el || !visible(el) || el.closest('.asset-missing') || el.closest('svg')) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      const rects = [...range.getClientRects()].filter(r => r.width > 0.5 && r.height > 0.5);
      if (!rects.length) continue;
      if (!texts.has(el)) texts.set(el, []);
      texts.get(el).push(...rects);
    }
    let minSize = 999, minContrast = 99;
    const ys = [];
    for (const [el, rects] of texts) {
      const cs = getComputedStyle(el);
      const fs = parseFloat(cs.fontSize);
      const meta = !!el.closest(cfg.meta);
      const min = meta ? cfg.min_meta : cfg.min_text;
      const txt = el.textContent.trim().slice(0, 48);
      if (fs < min - 0.5) add('error', 'text-too-small', `"${txt}" renders at ${fs.toFixed(1)} px, min ${min} px on a 1080 px canvas.`, label(el));
      minSize = Math.min(minSize, fs);
      for (const r of rects) {
        const mid = (r.top + r.bottom) / 2 - sr.top;
        const x0 = r.left - sr.left, x1 = r.right - sr.left, y0 = mid - fs * 0.45, y1 = mid + fs * 0.45;
        ys.push([y0, y1]);
        if (x0 < -1 || y0 < -1 || x1 > W + 1 || y1 > H + 1) { add('error', 'outside-canvas', `"${txt}" leaves the canvas.`, label(el)); break; }
        if (x0 < sl - 2 || y0 < st - 2 || x1 > W - sx + 2 || y1 > H - sb + 2) {
          add('error', 'outside-safe-zone', `"${txt}" is outside the safe zone (${st}/${sx}/${sb}/${sl} px).`, label(el)); break;
        }
      }
      const r0 = rects[0];
      const cx = Math.min(Math.max(r0.left + Math.min(r0.width / 2, 30), 0), window.innerWidth - 1);
      const cy = Math.min(Math.max(r0.top + r0.height / 2, 0), window.innerHeight - 1);
      const stack = document.elementsFromPoint(cx, cy);
      let start = stack.indexOf(el); if (start < 0) start = 0;
      let bgs = null, onImage = false;
      for (let k = start; k < stack.length; k++) {
        const e = stack[k];
        if (['IMG', 'VIDEO', 'CANVAS'].includes(e.tagName)) { onImage = true; break; }
        const ecs = getComputedStyle(e);
        const bc = parse(ecs.backgroundColor);
        const gc = ecs.backgroundImage && ecs.backgroundImage !== 'none' ? gradColors(ecs.backgroundImage) : [];
        if (gc.length) { bgs = gc; if (bc && bc.a >= 0.5) bgs.push(bc); break; }
        if (bc && bc.a >= 0.5) { bgs = [bc]; break; }
        if (e === sec) break;
      }
      if (onImage && !bgs) { add('warning', 'text-on-image', `"${txt}" sits on a photo: contrast not measurable, check it on the render.`, label(el)); continue; }
      if (!bgs) bgs = [parse(getComputedStyle(sec).backgroundColor) || {r: 255, g: 255, b: 255, a: 1}];
      const fg0 = parse(cs.color);
      if (!fg0) continue;
      const bold = parseInt(cs.fontWeight) >= 700;
      const need = (fs >= 40 || (fs >= 32 && bold)) ? 3 : 4.5;
      for (const bg of bgs) {
        const rr = ratio(blend(fg0, bg), bg);
        minContrast = Math.min(minContrast, rr);
        if (rr < need) { add('error', 'contrast', `"${txt}" ${rr.toFixed(2)}:1 on rgb(${bg.r},${bg.g},${bg.b}), needs ${need}:1.`, label(el)); break; }
      }
    }
    // Logo: inside the safe box, legible size, contrast, clear space.
    sec.querySelectorAll('.logo').forEach(l => {
      const r = l.getBoundingClientRect();
      const x0 = r.left - sr.left, y0 = r.top - sr.top, x1 = r.right - sr.left, y1 = r.bottom - sr.top;
      if (r.width > 0 && (x0 < sl - 2 || y0 < st - 2 || x1 > W - sx + 2 || y1 > H - sb + 2)) add('error', 'outside-safe-zone', 'The logo is outside the safe zone.', 'logo');
      ys.push([y0, y1]);
      const parts = [...l.querySelectorAll('.logo-mark, .logo-word')];
      if (!parts.length) return;
      for (const pt of parts) {
        const h = pt.getBoundingClientRect().height;
        const word = pt.classList.contains('logo-word');
        const min = word ? cfg.logo_word_min : cfg.logo_mark_min;
        if (h < min - 0.5) add('error', 'logo-too-small', `${word ? 'Wordmark' : 'Mark'} ${h.toFixed(0)} px high, min ${min} px on a 1080 px canvas.`, 'logo');
      }
      const vr = parts.map(pt => pt.getBoundingClientRect());
      const v = {l: Math.min(...vr.map(q => q.left)), t: Math.min(...vr.map(q => q.top)), r: Math.max(...vr.map(q => q.right)), b: Math.max(...vr.map(q => q.bottom))};
      // Contrast against what is under the logo (its own chip included).
      const cx = (v.l + v.r) / 2, cy = (v.t + v.b) / 2;
      const ink = parse(l.dataset.ink ? hexRgb(l.dataset.ink) : getComputedStyle(l).color);
      let under = null;
      for (const e of document.elementsFromPoint(cx, cy)) {
        if (e.closest('.logo') === l && !e.classList.contains('logo')) continue;
        if (['IMG', 'VIDEO', 'CANVAS'].includes(e.tagName)) break;
        const bc = parse(getComputedStyle(e).backgroundColor);
        if (bc && bc.a >= 0.5) { under = bc; break; }
        if (e === sec) break;
      }
      if (!under) under = parse(getComputedStyle(sec).backgroundColor);
      if (ink && under) {
        const rr = ratio(ink, under);
        if (rr < 3) add('error', 'logo-contrast', `Logo ${rr.toFixed(2)}:1 on rgb(${under.r},${under.g},${under.b}), needs 3:1: pick the other logo variant or another surface.`, 'logo');
      }
      // Clear space.
      const c = parseFloat(l.dataset.clear || '0');
      if (c > 0) {
        const z = {l: v.l - c, t: v.t - c, r: v.r + c, b: v.b + c};
        const hit = (q) => q.width > 0 && q.height > 0 && q.left < z.r && q.right > z.l && q.top < z.b && q.bottom > z.t;
        let bad = null;
        for (const [el, rects] of texts) {
          if (l.contains(el)) continue;
          const f = parseFloat(getComputedStyle(el).fontSize);
          // Ink box of each line, as for the safe zone: the line box of a
          // large display face runs well past its glyphs.
          if (rects.some(q => { const m = (q.top + q.bottom) / 2; return hit({left: q.left, right: q.right, top: m - f * 0.45, bottom: m + f * 0.45, width: q.width, height: f * 0.9}); })) { bad = el; break; }
        }
        if (!bad) sec.querySelectorAll(cfg.panels + ',.media').forEach(p => { if (!bad && !p.closest('.bg') && !p.contains(l) && hit(p.getBoundingClientRect())) bad = p; });
        if (bad) add('error', 'logo-clear-space', `${label(bad)} sits inside the logo's ${c} px clear space.`, 'logo');
      }
    });
    // Media.
    sec.querySelectorAll('img').forEach(img => {
      const r = img.getBoundingClientRect();
      if (!img.complete || img.naturalWidth === 0) { add('error', 'missing-asset', `Image did not load: ${img.getAttribute('src')}`, label(img)); return; }
      if (img.classList.contains('logo-img')) return;
      const shown = Math.min(r.width, r.height * img.naturalWidth / img.naturalHeight);
      if (img.naturalWidth < shown * 0.8) add('warning', 'low-res-image', `${img.getAttribute('src')} is ${img.naturalWidth} px wide, shown at ${Math.round(shown)} px.`, label(img));
      const box = img.closest('.media');
      if (box) ys.push([Math.max(r.top - sr.top, 0), Math.min(r.bottom - sr.top, H)]);
    });
    sec.querySelectorAll('.asset-missing').forEach(m => add('error', 'missing-asset', m.innerText.replace(/\s+/g, ' ').trim().slice(0, 120), 'media'));
    // Panels (cards, columns, buttons) are deliberate design elements.
    sec.querySelectorAll(cfg.panels).forEach(p => { const r = p.getBoundingClientRect(); if (r.height > 0) ys.push([r.top - sr.top, r.bottom - sr.top]); });
    // Dead space inside the safe box.
    const top = st, bottom = H - sb;
    const bands = ys.filter(y => y[1] > top && y[0] < bottom).map(y => [Math.max(y[0], top), Math.min(y[1], bottom)]).sort((a, b) => a[0] - b[0]);
    let cursor = top, gap = 0;
    for (const [a, b] of bands) { if (a > cursor) gap = Math.max(gap, a - cursor); cursor = Math.max(cursor, b); }
    gap = Math.max(gap, bottom - cursor);
    if (sec.dataset.format !== '9:16' && gap / (bottom - top) > cfg.max_gap) add('warning', 'dead-space', `An empty band of ${Math.round(gap)} px (${Math.round(gap / (bottom - top) * 100)} % of the safe box).`, '');
    let bandFill = null;
    if (sec.dataset.format === '9:16') {
      // Text zone: content from the top of the Reels safe box to its bottom line.
      const zone = bottom - top;
      let cur = top, worst = 0, where = '';
      for (const [a, b] of bands) { if (a - cur > worst) { worst = a - cur; where = cur === top ? 'under the top of the text zone' : 'between two blocks'; } cur = Math.max(cur, b); }
      if (bottom - cur > worst) { worst = bottom - cur; where = 'above the Reels line'; }
      if (worst / zone > cfg.max_gap_story) add('warning', 'dead-space-9x16', `Empty band of ${Math.round(worst)} px (${Math.round(worst / zone * 100)} % of the 9:16 text zone) ${where}: let the type grow, move the CTA down to the line or the photo up.`, '');
      // Meta's reserved bottom band: photo, panel or slab, never bare paper.
      const y0 = H - sb, y1 = H, paper = parse(getComputedStyle(sec).backgroundColor);
      let filled = 0, total = 0;
      for (let yy = y0 + 10; yy < y1; yy += 24) for (let xx = 20; xx < W; xx += 60) {
        total++;
        for (const e of document.elementsFromPoint(sr.left + xx, sr.top + yy)) {
          if (e === sec) break;
          if (['IMG', 'svg', 'VIDEO', 'CANVAS'].includes(e.tagName)) { filled++; break; }
          const bc = parse(getComputedStyle(e).backgroundColor);
          if (bc && bc.a >= 0.5 && !(paper && bc.r === paper.r && bc.g === paper.g && bc.b === paper.b)) { filled++; break; }
        }
      }
      bandFill = total ? filled / total : 1;
      if (bandFill < cfg.min_band_fill) add('warning', 'empty-band', `Only ${Math.round(bandFill * 100)} % of the reserved bottom band carries the photo, a panel or the footer slab: the ad reads as letterboxed.`, '');
    }
    // Tells of a generated ad.
    sec.querySelectorAll('*').forEach(e => {
      const cs = getComputedStyle(e);
      if (shadowBlur(cs.boxShadow) > 0) add('error', 'blurred-shadow', 'box-shadow with blur: use a hard offset or none.', label(e));
      if (shadowBlur(cs.textShadow) > 0) add('error', 'blurred-shadow', 'text-shadow with blur (glow).', label(e));
      if (cs.backdropFilter && cs.backdropFilter !== 'none') add('error', 'backdrop-filter', 'backdrop-filter (glassmorphism).', label(e));
      if (/blur\(/.test(cs.filter)) add('error', 'blur-filter', 'filter: blur.', label(e));
      if ((cs.webkitBackgroundClip || cs.backgroundClip) === 'text') add('error', 'gradient-text', 'background-clip: text.', label(e));
      if (cs.textTransform && cs.textTransform !== 'none') add('error', 'text-transform', 'text-transform changes the case the proofread compares.', label(e));
      if (/gradient/.test(cs.backgroundImage)) {
        const cols = gradColors(cs.backgroundImage).map(c => `${c.r},${c.g},${c.b}`);
        if (new Set(cols).size >= 2) add('warning', 'gradient', 'Gradient between two opaque colours.', label(e));
      }
    });
    const dedupe = (arr) => { const seen = new Set(); return arr.filter(x => { const k = x.code + x.where + x.message; if (seen.has(k)) return false; seen.add(k); return true; }); };
    out.push({name: sec.dataset.name, format: sec.dataset.format, errors: dedupe(errors), warnings: dedupe(warnings),
              metrics: {min_text_px: Math.round(minSize * 10) / 10, min_contrast: Math.round(minContrast * 100) / 100, largest_gap_ratio: Math.round(gap / (bottom - top) * 100) / 100,
              logo: sec.dataset.logo || '', band_fill: bandFill === null ? null : Math.round(bandFill * 100) / 100}});
  });
  const fonts = cfg.fonts.map(f => ({family: f, loaded: document.fonts.check(`40px "${f}"`)}));
  return {sections: out, fonts, fit: window.__fit};
}
"""


def measure(html_dir: Path, fonts: List[str]) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    import build
    cfg = {"meta": META_SELECTOR, "panels": PANELS, "min_text": MIN_TEXT, "min_meta": MIN_META, "max_gap": MAX_GAP, "fonts": fonts,
           "max_gap_story": MAX_GAP_STORY, "min_band_fill": MIN_BAND_FILL,
           "logo_mark_min": build.LOGO_MARK_MIN, "logo_word_min": build.LOGO_WORD_MIN}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto((html_dir / "index.html").resolve().as_uri(), wait_until="load")
        page.wait_for_function("document.body.dataset.fitted === '1'", timeout=30000)
        data = page.evaluate(MEASURE_JS, cfg)
        browser.close()
    return data


def contact_sheet(renders: Path, title: str) -> Optional[str]:
    pngs = sorted(p for p in renders.glob("*.png") if not p.name.startswith("contact-sheet"))
    if not pngs or not SHARED_SHEET.exists():
        return None
    out_png = renders / "contact-sheet.png"
    subprocess.run([sys.executable, str(SHARED_SHEET), *[str(p) for p in pngs], "-o", str(out_png), "--scale", "360",
                    "--cols", str(min(len(pngs), 3)), "--title", title], capture_output=True, text=True)
    if not out_png.exists():
        return None
    from PIL import Image
    jpg = renders / "contact-sheet.jpg"
    with Image.open(out_png) as im:
        im.convert("RGB").save(jpg, quality=84, optimize=True)
    out_png.unlink()
    return jpg.name


def run(html_dir: Path, renders: Optional[Path], out: Path, sheet: bool = True) -> Dict[str, Any]:
    rep = json.loads((html_dir / "build-report.json").read_text(encoding="utf-8"))
    exp = {s["name"]: s for s in json.loads((html_dir / "expected.json").read_text(encoding="utf-8"))["sections"]}
    data = measure(html_dir, rep.get("fonts") or [])
    secs = data["sections"]
    fit = {s["name"]: s for s in (data.get("fit") or {}).get("sections", [])}
    for s in secs:
        e = exp.get(s["name"], {})
        f = fit.get(s["name"], {})
        for it in f.get("items", []):
            if it.get("status") == "fail":
                s["errors"].insert(0, {"code": "text-too-long", "message": f"{it['kind']} \"{it.get('text', '')}\": {it['reason']}. Shorten the copy in ads.json.", "where": it["kind"]})
        if f.get("overflow"):
            s["errors"].insert(0, {"code": "overflow", "message": f"Content overflows ({', '.join(f.get('overflowAt', []))}).", "where": ""})
        s["fit"] = [{k: it[k] for k in ("kind", "count", "size", "lines", "maxLines", "status")} for it in f.get("items", [])]
        for iss in e.get("issues", []):
            (s["errors"] if iss["level"] == "error" else s["warnings"]).insert(0, {"code": "build:" + iss["code"], "message": iss["message"], "where": iss["where"]})
        s["ad"], s["n"], s["style"] = e.get("ad"), e.get("n"), e.get("style")
    # DOM text against ads.json.
    dom_text = {}
    if renders and (renders / "render.json").exists():
        dom_text = json.loads((renders / "render.json").read_text(encoding="utf-8")).get("dom_text", {})
    for s in secs:
        e = exp.get(s["name"])
        if e is None or s["name"] not in dom_text:
            continue
        d = adspec.word_diff(adspec.tokens(" ".join(e["dom"])), adspec.tokens(dom_text[s["name"]]))
        if not d["ok"]:
            s["errors"].append({"code": "dom-text-mismatch", "message": f"Rendered words differ from ads.json: {json.dumps({k: v for k, v in d.items() if k != 'ok' and v}, ensure_ascii=False)}", "where": "dom"})
    glob_err: List[Dict[str, Any]] = []
    glob_warn: List[Dict[str, Any]] = []
    for f in data.get("fonts", []):
        if not f["loaded"]:
            glob_warn.append({"code": "font-fallback", "message": f"Font '{f['family']}' did not load (offline or wrong name): a fallback face was measured and rendered.", "where": "fonts"})
    for lvl, bucket in (("errors", glob_err), ("warnings", glob_warn)):
        for i in rep.get(lvl, []):
            if i["code"] in ("missing-asset",):
                continue  # reported per section
            bucket.append({"code": "build:" + i["code"], "message": i["message"], "where": i.get("where", "")})
    outputs = []
    sheet_name = None
    if renders and renders.exists():
        from PIL import Image
        scale = 1.0
        if (renders / "render.json").exists():
            scale = json.loads((renders / "render.json").read_text(encoding="utf-8")).get("scale", 1.0) or 1.0
        for s in secs:
            p = renders / f"{s['name']}.png"
            if not p.exists():
                glob_err.append({"code": "output-missing", "message": f"{p.name} was not rendered.", "where": p.name})
                continue
            with Image.open(p) as im:
                want = tuple(round(v * scale) for v in exp.get(s["name"], {}).get("size", im.size))
                outputs.append({"file": p.name, "size": list(im.size), "kb": round(p.stat().st_size / 1024)})
                if tuple(im.size) != want:
                    glob_err.append({"code": "output-size", "message": f"{p.name} is {im.size[0]}x{im.size[1]}, expected {want[0]}x{want[1]}.", "where": p.name})
        if sheet:
            sheet_name = contact_sheet(renders, f"{Path(rep.get('spec', 'ads')).parent.name}: {len(secs)} renders, 360 px tiles")
    n_err = len(glob_err) + sum(len(s["errors"]) for s in secs)
    n_warn = len(glob_warn) + sum(len(s["warnings"]) for s in secs)
    result = {"status": "pass" if n_err == 0 else "fail",
              "summary": {"errors": n_err, "warnings": n_warn, "renders": len(secs), "copy_gate": rep.get("copy_gate")},
              "global": {"errors": glob_err, "warnings": glob_warn}, "sections": secs, "outputs": outputs, "contact_sheet": sheet_name}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def print_summary(r: Dict[str, Any]) -> None:
    for e in r["global"]["errors"]:
        print(f"ERROR {e['code']}: {e['message']}")
    for s in r["sections"]:
        for e in s["errors"]:
            print(f"ERROR {s['name']} {e['code']}: {e['message']}")
    for s in r["sections"]:
        for w in s["warnings"]:
            print(f"warn  {s['name']} {w['code']}: {w['message']}")
    for w in r["global"]["warnings"]:
        print(f"warn  {w['code']}: {w['message']}")
    sm = r["summary"]
    print(f"qa: {r['status'].upper()}, {sm['errors']} errors, {sm['warnings']} warnings, {sm['renders']} renders")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="Dir holding index.html, expected.json, build-report.json")
    ap.add_argument("--renders", help="Dir with the PNGs and render.json (default <html>/../renders)")
    ap.add_argument("--out", help="qa.json path (default <renders>/qa.json)")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    html_dir = Path(args.html).resolve()
    renders = Path(args.renders).resolve() if args.renders else html_dir.parent / "renders"
    out = Path(args.out).resolve() if args.out else renders / "qa.json"
    r = run(html_dir, renders, out, not args.no_sheet)
    if not args.quiet:
        print_summary(r)
    return 0 if r["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
