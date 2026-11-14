#!/usr/bin/env python3
"""extract_brand.py: extract a brand from its website and harvest its real assets.

One local Chromium pass (Playwright), no API key, no paid call:

  1. Page preparation. Cookie and consent banners are hidden (their buttons
     never count as brand colors), the page is scrolled to the bottom so lazy
     images load, then back to the top.
  2. Color roles measured on the render, not only in the CSS. Every visible
     text node, card and button is listed with its computed style and its box;
     the full-page screenshot is then sampled inside those boxes. bg is the
     dominant screenshot color, text / text_secondary / text_muted come from the
     text on the page background (headings, paragraphs, small print) checked
     against the glyph pixels, surface and border from the cards (pixel mode
     inside each card), accent from the primary CTA (solid background, else the
     most vivid gradient stop, checked against the button pixels), on_accent
     from its label. Radius and shadow come from the cards, the button radius
     is kept apart.
  3. Fonts actually loaded. document.fonts tells which faces loaded; the page's
     stylesheets are parsed for @font-face rules. A family declared but never
     loaded is skipped (the page renders the next one) and reported. Google
     Fonts files are downloaded for offline rendering (--font-files).
  4. Assets with their license. The logo (scored: link to the home page,
     "logo" or brand name in its label, never inside a button), og:image,
     favicon, a capture of the hero section, and 3 to 6 page images. Images are
     downloaded, then decorative ones (glows, gradients, grain textures, flat
     fills) are dropped by pixel statistics. Every harvested file is recorded
     with license "founder-site": it comes from the founder's own site and is
     reused for that brand's marketing only; stock hosts are flagged.
  5. Logo pipeline (logo_pipeline.py): viewBox audit against the rendered ink,
     wordmark and mark, on_light and on_dark variants tested in pixels on the
     brand background and its opposite, PNG fallbacks, logo_audit.
  6. brand-draft.json in the brand.json V2 contract
     (shared/schemas/brand.schema.json), validated with
     shared/scripts/validate_json.py. --finalize promotes the approved draft.

Usage:
    python3 extract_brand.py --url https://example.com --out <project>/project-context
    python3 extract_brand.py --url https://example.com --out <dir> --max-images 4 --font-files none
    python3 extract_brand.py --out <project>/project-context --finalize

Exit codes:
    0  ok
    2  robots.txt disallows the page
    3  Playwright missing or the page never loaded
    4  --finalize without a brand-draft.json
    5  the V2 draft does not match the schema (extraction: draft kept for
       diagnosis; --finalize: brand.json left unchanged)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_common import (  # noqa: E402
    RGB, between, cluster_colors, color_distance, contrast_ratio, css_length,
    flatten_on, foreground_color, is_dark, is_neutralish, mode_color,
    parse_css_color, px_value, region_pixels, rgb_to_hex, saturation, vividness,
)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}
# per-attempt navigation timeout (load, then domcontentloaded), then a short
# networkidle grace that never fails the run
GOTO_TIMEOUT_MS = 30_000
IDLE_GRACE_MS = 5_000
# full-page screenshot height cap: palettes and samples below are not needed
MAX_SHOT_HEIGHT = 8000
# images smaller than this on their shorter rendered edge are icons
MIN_ASSET_EDGE = 200
# downloads that turn out smaller than this on their shorter edge are dropped
MIN_DOWNLOAD_EDGE = 120
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
# a CTA background under this contrast with the page background is a ghost button
GHOST_CTA_MAX_CONTRAST = 1.5
# a corner radius above this is a pill, not the brand's card radius
MAX_CARD_RADIUS_PX = 48.0
# a CSS color and the rendered pixels agree when closer than this (RGB distance)
RENDER_AGREE = 45.0
# two text colors closer than this are the same role
TEXT_ROLE_DISTANCE = 24.0
# families that render without a webfont download
SYSTEM_FONTS = {
    "system-ui", "-apple-system", "blinkmacsystemfont", "ui-sans-serif", "ui-serif",
    "ui-monospace", "sans-serif", "serif", "monospace", "arial", "helvetica",
    "helvetica neue", "georgia", "times", "times new roman", "verdana", "tahoma",
    "segoe ui", "courier new", "roboto", "cursive", "fantasy",
}
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
                    "ui-serif", "ui-sans-serif", "ui-monospace", "inherit", "initial", "unset"}
SYSTEM_KEYWORDS = {"system-ui", "-apple-system", "blinkmacsystemfont"}
STOCK_HOSTS = ("unsplash.com", "pexels.com", "pixabay.com", "istockphoto.com", "gettyimages",
               "shutterstock.com", "stock.adobe.com", "freepik.com", "depositphotos.com")
IMAGE_LICENSE = "founder-site"
IMAGE_LICENSE_NOTE = ("Harvested from the founder's own site: reuse it for this brand's own marketing. "
                      "Stock photos, customer logos and photos of people need the founder's confirmation first.")


# --- Data model -------------------------------------------------------------

@dataclass
class Token:
    value: Any
    confidence: float
    source: str

    def as_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "confidence": round(self.confidence, 2), "source": self.source}


@dataclass
class Extraction:
    source_url: str
    tokens: Dict[str, Token] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    assets: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "extracted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tokens": {k: t.as_dict() for k, t in self.tokens.items()},
            "evidence": self.evidence,
            "assets": self.assets,
            "warnings": self.warnings,
        }


# --- Safe fetching -----------------------------------------------------------
# Asset, stylesheet and font URLs come from the analyzed page, so from a third
# party. Only http and https are fetched, never file:// or ftp://. A host that
# resolves to a private, loopback or link-local address is refused too, unless
# the analyzed site itself sits on such an address (a local dev server):
# main() sets _ALLOW_PRIVATE in that case. Every redirect target goes through
# the same check.

_ALLOW_PRIVATE = False


def host_is_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False  # unresolvable: the fetch fails on its own
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return True
    return False


def check_fetch_url(url: str) -> None:
    """Raise ValueError unless url is http(s) to an allowed host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError(f"refused {url[:120]!r}: only http and https URLs are fetched")
    if not _ALLOW_PRIVATE and host_is_private(parts.hostname):
        raise ValueError(f"refused {url[:120]!r}: {parts.hostname} resolves to a private, loopback or link-local address")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        check_fetch_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def safe_urlopen(req: urllib.request.Request, timeout: float):
    check_fetch_url(req.full_url)
    return _OPENER.open(req, timeout=timeout)


# --- URL + robots helpers ---------------------------------------------------

def robots_allows(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": "project-context/2.0"})
        with safe_urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return True  # no robots.txt: allowed
    path = parsed.path or "/"
    for block in re.split(r"(?im)^user-agent:\s*", body):
        head, *rest = block.split("\n", 1)
        if head.strip() in ("*", "project-context"):
            for ln in (rest[0] if rest else "").splitlines():
                if ln.lower().startswith("disallow:"):
                    rule = ln.split(":", 1)[1].strip()
                    if rule == "/" or (rule and path.startswith(rule) and rule != ""):
                        return False
    return True


def http_get(url: str, accept: str = "*/*", referer: Optional[str] = None, limit: int = MAX_DOWNLOAD_BYTES) -> Tuple[bytes, str]:
    headers = {"User-Agent": BROWSER_UA, "Accept": accept}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with safe_urlopen(req, timeout=30) as resp:
        return resp.read(limit + 1), resp.headers.get("Content-Type", "")


# --- Asset download ---------------------------------------------------------

_EXT_BY_CT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
    "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg",
    "image/avif": ".avif", "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico",
}


def _ext_from(url: str, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _EXT_BY_CT:
        return _EXT_BY_CT[ct]
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".ico"):
        return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def download(url: str, dest_dir: Path, basename: str, referer: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Download an image (http(s) or data: URL) to dest_dir/<basename><ext>."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        if url.startswith("data:"):
            header, _, payload = url.partition(",")
            ct = header[5:].split(";")[0] or "image/png"
            ext = _EXT_BY_CT.get(ct, ".png")
            raw = base64.b64decode(payload) if ";base64" in header else urllib.parse.unquote_to_bytes(payload)
        else:
            raw, ct = http_get(url, "image/*,*/*", referer)
            main_ct = (ct or "").split(";")[0].strip().lower()
            if main_ct and not main_ct.startswith("image/") and main_ct != "application/octet-stream":
                return None  # an HTML error page, not an image
            ext = _ext_from(url, ct)
        if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
            return None
        out = dest_dir / f"{basename}{ext}"
        out.write_bytes(raw)
        rec: Dict[str, Any] = {"path": out, "source": url[:300], "bytes": len(raw)}
        if ext != ".svg":
            dims = _image_dims(out)
            if dims:
                rec["w"], rec["h"] = dims
        return rec
    except Exception:
        return None


def _image_dims(path: Path) -> Optional[Tuple[int, int]]:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# --- Browser: prepare, capture, probe ----------------------------------------

PREPARE_JS = r"""async () => {
  // 1. hide cookie / consent banners, so their buttons never count as brand colors
  const idWords = /(cookie|consent|gdpr|rgpd|onetrust|didomi|axeptio|cookiebot|tarteaucitron|cc-window|cc-banner|cmp-|usercentrics|iubenda|klaro|quantcast)/i;
  let hidden = 0;
  const hide = (el) => { el.style.setProperty('display', 'none', 'important'); hidden++; };
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    if (el.closest('[data-pc-hidden]')) continue;
    const cls = typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
    const label = `${el.id} ${cls} ${el.getAttribute('aria-label') || ''}`;
    const cs = getComputedStyle(el);
    const floating = cs.position === 'fixed' || cs.position === 'sticky';
    if (idWords.test(label) && (floating || el.getAttribute('role') === 'dialog' || /banner|modal|dialog|popup|notice/i.test(label))) {
      el.setAttribute('data-pc-hidden', '1'); hide(el); continue;
    }
    if (floating && !el.querySelector('h1') && el.querySelector('button, a, [role="button"]')) {
      const t = (el.innerText || '').slice(0, 2000);
      if (t.length < 1500 && /\b(cookies?|consent|traceurs|tracking)\b/i.test(t)) { el.setAttribute('data-pc-hidden', '1'); hide(el); }
    }
  }
  // 2. load lazy images: eager loading, then scroll to the bottom and back
  document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; });
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let y = 0;
  const step = Math.max(400, window.innerHeight * 0.8);
  for (let i = 0; i < 40 && y < document.documentElement.scrollHeight; i++) { y += step; window.scrollTo(0, y); await sleep(120); }
  window.scrollTo(0, 0);
  await sleep(400);
  return { hidden };
}"""

DOM_PROBE_JS = r"""() => {
  const css = (el) => (el ? getComputedStyle(el) : null);
  const abs = (u) => { try { return new URL(u, document.baseURI).href; } catch (e) { return u || ''; } };
  const meta = (sel, attr) => { const el = document.querySelector(sel); return el ? (el.getAttribute(attr) || '') : ''; };
  const transparent = (c) => !c || c === 'transparent' || c === 'rgba(0, 0, 0, 0)';
  const box = (r) => ({ x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) });
  const visible = (el, cs) => cs && cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity || '1') > 0.05 && !el.closest('[data-pc-hidden]');
  const effBg = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = css(n);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && !cs.backgroundImage.startsWith('linear-gradient(rgba(0, 0, 0, 0)')) return { bg: cs.backgroundColor, img: true };
      if (!transparent(cs.backgroundColor)) return { bg: cs.backgroundColor, img: false };
    }
    return { bg: '', img: false };
  };
  const siteName = meta('meta[property="og:site_name"]', 'content') || meta('meta[name="application-name"]', 'content');
  const hostLabel = (location.hostname || '').replace(/^www\./, '').split('.')[0] || '';
  const brandHint = (siteName || hostLabel).toLowerCase();

  // --- logo: scored candidates in the top band ---------------------------------
  const logoSel = 'header img, header svg, nav img, nav svg, [class*="logo" i] img, [class*="logo" i] svg, [id*="logo" i] img, [id*="logo" i] svg, img[alt*="logo" i], img[class*="logo" i], a[href] > img, a[href] > svg, a[href] picture img';
  const seen = new Set();
  const cands = [];
  for (const el of Array.from(document.querySelectorAll(logoSel))) {
    if (seen.has(el)) continue; seen.add(el);
    if (el.tagName.toLowerCase() === 'svg' && el.parentElement && el.parentElement.closest('svg')) continue;
    const cs = css(el); if (!visible(el, cs)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 16 || r.height < 10 || r.top > 240 || r.bottom < 0) continue;
    const a = el.closest('a');
    let home = false;
    if (a) { try { const u = new URL(a.getAttribute('href') || '', location.href); home = u.origin === location.origin && /^\/([a-z]{2}(-[a-z]{2})?\/?)?(index\.html)?$/i.test(u.pathname) && !u.hash; } catch (e) {} }
    const t = el.querySelector ? el.querySelector('title') : null;
    const label = [el.getAttribute('alt'), el.getAttribute('aria-label'), a && a.getAttribute('aria-label'), a && a.getAttribute('title'),
      typeof el.className === 'string' ? el.className : (el.getAttribute('class') || ''), el.id, a && a.getAttribute('class'), t && t.textContent,
      el.getAttribute('src')].join(' ').toLowerCase();
    let score = 0;
    if (home) score += 5;
    if (/logo|brand|wordmark/.test(label)) score += 4;
    if (brandHint && brandHint.length > 2 && label.includes(brandHint)) score += 3;
    if (el.closest('button, [role="button"]')) score -= 6;
    if (r.width <= 28 && r.height <= 28) score -= 3;
    if (r.width / Math.max(r.height, 1) >= 1.8) score += 1;
    score += Math.max(0, 2 - r.left / (window.innerWidth * 0.25));
    cands.push({ el, score, r, cs });
  }
  cands.sort((p, q) => q.score - p.score);
  let logo = { kind: 'none', src: '', svg: '', w: 0, h: 0, score: 0, filter: '' };
  if (cands.length) {
    const { el, score, r, cs } = cands[0];
    const filter = cs.filter && cs.filter !== 'none' ? cs.filter : '';
    if (el.tagName.toLowerCase() === 'img') {
      logo = { kind: 'img', src: abs(el.currentSrc || el.src), svg: '', w: Math.round(r.width), h: Math.round(r.height), score, filter };
    } else {
      // serialize with the colors the page paints: computed fill and stroke on
      // every shape, <use> sprites inlined, currentColor resolved
      const clone = el.cloneNode(true);
      const shapeSel = 'path,rect,circle,ellipse,polygon,polyline,line,text,tspan,use';
      const src = el.querySelectorAll(shapeSel), dst = clone.querySelectorAll(shapeSel);
      src.forEach((sh, i) => {
        const d = dst[i]; const s = css(sh); if (!d || !s) return;
        for (const prop of ['fill', 'stroke']) { const v = s[prop]; if (v) d.setAttribute(prop, v); }
      });
      const NS = 'http://www.w3.org/2000/svg';
      Array.from(clone.querySelectorAll('use')).forEach((u) => {
        const href = u.getAttribute('href') || u.getAttribute('xlink:href') || '';
        if (!href.startsWith('#')) return;
        const ref = document.getElementById(href.slice(1)); if (!ref) return;
        const g = document.createElementNS(NS, 'g');
        for (const p of ['fill', 'stroke', 'class', 'style', 'opacity']) { if (u.getAttribute(p)) g.setAttribute(p, u.getAttribute(p)); }
        const x = parseFloat(u.getAttribute('x') || '0'), y = parseFloat(u.getAttribute('y') || '0');
        if (x || y) g.setAttribute('transform', `translate(${x} ${y})`);
        if (ref.tagName.toLowerCase() === 'symbol') {
          const inner = document.createElementNS(NS, 'svg');
          if (ref.getAttribute('viewBox')) inner.setAttribute('viewBox', ref.getAttribute('viewBox'));
          inner.setAttribute('width', u.getAttribute('width') || '100%'); inner.setAttribute('height', u.getAttribute('height') || '100%');
          Array.from(ref.childNodes).forEach((c) => inner.appendChild(c.cloneNode(true)));
          g.appendChild(inner);
        } else { g.appendChild(ref.cloneNode(true)); }
        u.replaceWith(g);
      });
      if (!clone.getAttribute('viewBox')) {
        try { const b = el.getBBox(); if (b.width > 0 && b.height > 0) clone.setAttribute('viewBox', `${b.x} ${b.y} ${b.width} ${b.height}`); } catch (e) {}
      }
      let svg = clone.outerHTML || '';
      svg = svg.replace(/currentColor/gi, cs.color || '#000000');
      if (!svg.includes('xmlns=')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
      logo = { kind: 'svg', src: '', svg: svg.slice(0, 200000), w: Math.round(r.width), h: Math.round(r.height), score, filter };
    }
  }

  // --- CTAs: styled clickables with a fill or a gradient -----------------------
  const ctas = [];
  for (const el of Array.from(document.querySelectorAll('button, a, [role="button"], input[type="submit"], input[type="button"]'))) {
    const s = css(el); if (!visible(el, s)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 18) continue;
    const solid = !transparent(s.backgroundColor);
    const grad = (s.backgroundImage || '').includes('gradient');
    if (!solid && !grad) continue;
    ctas.push({ bg: s.backgroundColor, bgi: s.backgroundImage || '', color: s.color, border: s.borderTopColor,
      radius: s.borderTopLeftRadius || '', area: Math.round(r.width * r.height), top: Math.round(r.top + scrollY),
      ...box(r), text: (el.innerText || '').trim().slice(0, 40) });
  }

  // --- text samples: every element holding visible text --------------------------
  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const done = new Set();
  while (walker.nextNode() && texts.length < 1500) {
    const node = walker.currentNode; const str = (node.textContent || '').trim();
    if (str.length < 2) continue;
    const el = node.parentElement; if (!el || done.has(el)) continue; done.add(el);
    if (el.closest('script,style,noscript,svg')) continue;
    const s = css(el); if (!visible(el, s)) continue;
    const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
    const e = effBg(el);
    const cta = el.closest('button, [role="button"], a');
    const ctaStyled = cta && (!transparent(css(cta).backgroundColor) || (css(cta).backgroundImage || '').includes('gradient'));
    texts.push({ color: s.color, fs: parseFloat(s.fontSize) || 16, fw: s.fontWeight, ff: s.fontFamily, chars: str.length,
      tag: el.tagName, heading: !!el.closest('h1,h2,h3'), h1: !!el.closest('h1'), link: !!el.closest('a'), cta: !!ctaStyled,
      footer: !!el.closest('footer'), small: !!el.closest('small,figcaption,caption,time,label,.caption'),
      clip: (s.webkitBackgroundClip || s.backgroundClip || '') === 'text', ebg: e.bg, eimg: e.img, ...box(r) });
  }

  // --- surfaces: card-like boxes ------------------------------------------------
  const surfaces = [];
  for (const el of Array.from(document.querySelectorAll('div,section,article,aside,li,a,form,figure,details'))) {
    if (surfaces.length >= 400) break;
    const r = el.getBoundingClientRect(); const area = r.width * r.height;
    if (area < 15000 || r.width >= window.innerWidth * 0.97) continue;
    const s = css(el); if (!visible(el, s)) continue;
    if (el.closest('button, [role="button"], header, nav')) continue;
    const hasBg = !transparent(s.backgroundColor);
    const bw = parseFloat(s.borderTopWidth) || 0;
    const shadow = s.boxShadow && s.boxShadow !== 'none' ? s.boxShadow : '';
    if (!hasBg && !(bw && s.borderTopStyle !== 'none') && !shadow) continue;
    surfaces.push({ bg: hasBg ? s.backgroundColor : '', radius: s.borderTopLeftRadius, shadow, border: bw ? s.borderTopColor : '', bw,
      ebg: effBg(el.parentElement || el).bg, ...box(r) });
  }

  // --- images: <img> by rendered area, plus large CSS backgrounds ----------------
  const imgs = [];
  for (const el of Array.from(document.querySelectorAll('img'))) {
    const r = el.getBoundingClientRect(); const w = Math.round(r.width), h = Math.round(r.height);
    if (w < 40 || h < 40) continue;
    if (el.closest('[data-pc-hidden]')) continue;
    imgs.push({ src: abs(el.currentSrc || el.src), w, h, nw: el.naturalWidth || 0, nh: el.naturalHeight || 0, area: w * h,
      top: Math.round(r.top + scrollY), alt: (el.getAttribute('alt') || '').slice(0, 120), kind: 'img' });
  }
  const bgs = []; const seenBg = new Set();
  for (const el of Array.from(document.querySelectorAll('div,section,header,a,span,figure'))) {
    const r = el.getBoundingClientRect(); if (r.width * r.height < 60000) continue;
    const bi = css(el).backgroundImage || '';
    const m = bi.match(/url\((['"]?)(.*?)\1\)/);
    if (m && m[2] && !m[2].startsWith('data:') && !seenBg.has(m[2])) {
      seenBg.add(m[2]);
      bgs.push({ src: abs(m[2]), w: Math.round(r.width), h: Math.round(r.height), area: Math.round(r.width * r.height),
        top: Math.round(r.top + scrollY), alt: '', kind: 'css-background', repeat: css(el).backgroundRepeat || '' });
    }
  }

  // --- hero: the block holding the first h1, else the first viewport -------------
  let hero = { x: 0, y: 0, w: window.innerWidth, h: window.innerHeight };
  const h1 = document.querySelector('h1');
  if (h1) {
    for (let n = h1; n && n !== document.body; n = n.parentElement) {
      const r = n.getBoundingClientRect();
      if (r.width >= window.innerWidth * 0.8 && r.height >= 250) { hero = { x: 0, y: Math.max(0, Math.round(r.top + scrollY)), w: window.innerWidth, h: Math.min(Math.round(r.height), window.innerHeight) }; break; }
    }
  }

  // --- fonts: faces the page loaded, stylesheets to parse --------------------------
  let faces = [];
  try { faces = Array.from(document.fonts || []).map((f) => ({ family: (f.family || '').replace(/["']/g, ''), weight: String(f.weight), style: f.style, status: f.status })); } catch (e) {}
  const sheets = Array.from(document.querySelectorAll('link[rel~="stylesheet"][href]')).map((l) => abs(l.getAttribute('href')));
  const inlineCss = Array.from(document.querySelectorAll('style')).map((s) => s.textContent || '').join('\n').slice(0, 400000);
  const fontLinks = Array.from(document.querySelectorAll('link[href*="fonts.googleapis.com"]')).map((l) => abs(l.getAttribute('href') || ''));

  // --- custom properties on :root (the site's named palette, when it has one) ----
  const vars = {};
  for (const sh of Array.from(document.styleSheets)) {
    let rules; try { rules = sh.cssRules; } catch (e) { continue; }
    for (const rule of Array.from(rules || [])) {
      if (!rule.selectorText || !/(^|,)\s*(:root|html)\s*(,|$)/.test(rule.selectorText)) continue;
      for (let i = 0; i < rule.style.length; i++) {
        const name = rule.style[i];
        if (name.startsWith('--') && Object.keys(vars).length < 200) vars[name] = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      }
    }
  }

  const icons = Array.from(document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="apple-touch-icon-precomposed"], link[rel="shortcut icon"]'))
    .map((l) => ({ href: abs(l.getAttribute('href') || ''), sizes: l.getAttribute('sizes') || '', rel: l.getAttribute('rel') || '' })).filter((i) => i.href);
  const ogRaw = meta('meta[property="og:image"]', 'content') || meta('meta[name="twitter:image"]', 'content') || meta('meta[property="twitter:image"]', 'content');
  const h1el = document.querySelector('h1') || document.querySelector('h2');
  return {
    site_name: siteName, title: document.title || '', lang: document.documentElement.lang || '',
    theme_color: meta('meta[name="theme-color"]', 'content'), og_image: ogRaw ? abs(ogRaw) : '', icons,
    body_bg: css(document.body).backgroundColor, html_bg: css(document.documentElement).backgroundColor,
    body_color: css(document.body).color, body_font: css(document.body).fontFamily, body_weight: css(document.body).fontWeight,
    h1_font: h1el ? css(h1el).fontFamily : '', h1_weight: h1el ? css(h1el).fontWeight : '',
    link_color: (() => { const a = document.querySelector('main a, article a, p a'); return a ? css(a).color : ''; })(),
    page_height: document.documentElement.scrollHeight,
    logo, ctas, texts, surfaces, images: imgs, backgrounds: bgs, hero, faces, sheets, inline_css: inlineCss,
    font_links: fontLinks, css_vars: vars, logo_candidates: cands.slice(0, 5).map((c) => ({ score: Math.round(c.score * 10) / 10, tag: c.el.tagName.toLowerCase(), w: Math.round(c.r.width), h: Math.round(c.r.height) })),
  };
}"""


async def capture(url: str, debug_dir: Path) -> Dict[str, Any]:
    """Load the page, prepare it, take the screenshots and run the DOM probe."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport=VIEWPORT, user_agent=BROWSER_UA, ignore_https_errors=True)
            page = await ctx.new_page()
            loaded, last_err = False, ""
            for wait_until in ("load", "domcontentloaded"):
                try:
                    await page.goto(url, wait_until=wait_until, timeout=GOTO_TIMEOUT_MS)
                    loaded = True
                    break
                except Exception as e:  # noqa: BLE001
                    last_err = str(e).splitlines()[0]
            if not loaded:
                raise RuntimeError(f"page did not load within {GOTO_TIMEOUT_MS // 1000} s per attempt ({last_err})")
            try:
                await page.wait_for_load_state("networkidle", timeout=IDLE_GRACE_MS)
            except Exception:  # noqa: BLE001
                pass  # analytics and chat widgets never settle: the DOM is enough
            prep = await page.evaluate(PREPARE_JS)
            try:
                await page.evaluate("document.fonts && document.fonts.ready.then(() => true)")
            except Exception:  # noqa: BLE001
                pass
            await page.wait_for_timeout(500)
            height = int(await page.evaluate("document.documentElement.scrollHeight"))
            full = debug_dir / "homepage.png"
            await page.screenshot(path=str(full), full_page=True,
                                  clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": min(max(height, VIEWPORT["height"]), MAX_SHOT_HEIGHT)})
            await page.screenshot(path=str(debug_dir / "header-crop.png"), clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 200})
            viewport = debug_dir / "viewport.png"
            await page.screenshot(path=str(viewport), full_page=False)
            probe = await page.evaluate(DOM_PROBE_JS)
            hero = probe.get("hero") or {}
            hero_path = debug_dir / "hero.png"
            try:
                await page.screenshot(path=str(hero_path), full_page=True, clip={
                    "x": 0, "y": float(hero.get("y", 0)), "width": float(VIEWPORT["width"]),
                    "height": float(max(200, min(hero.get("h", VIEWPORT["height"]), VIEWPORT["height"])))})
            except Exception:  # noqa: BLE001
                shutil.copyfile(viewport, hero_path)
            probe["cookie_banners_hidden"] = int((prep or {}).get("hidden", 0))
            return {"full": full, "viewport": viewport, "hero": hero_path, "probe": probe}
        finally:
            await browser.close()


# --- Pixel sampling ---------------------------------------------------------------

class Shot:
    """The full-page screenshot, opened once, sampled in page coordinates."""

    def __init__(self, path: Path):
        from PIL import Image
        self.img = Image.open(path).convert("RGB")

    def pixels(self, b: Dict[str, Any], inset: float = 0.0) -> list:
        return region_pixels(self.img, (b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 0)), inset)

    def palette(self, k: int = 8) -> List[Tuple[RGB, float]]:
        from PIL import Image
        img = self.img.copy()
        img.thumbnail((600, 600))
        quant = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette() or []
        data = quant.get_flattened_data() if hasattr(quant, "get_flattened_data") else quant.getdata()
        counts = Counter(data)
        total = sum(counts.values()) or 1
        return [(tuple(palette[i * 3: i * 3 + 3]), c / total) for i, c in counts.most_common(k)]  # type: ignore[misc]


# --- Color roles -------------------------------------------------------------------

def gradient_stops(bgi: str) -> List[RGB]:
    if not bgi or "gradient" not in bgi:
        return []
    out = []
    for m in re.finditer(r"rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}", bgi):
        rgb = parse_css_color(m.group(0))
        if rgb:
            out.append(rgb)
    return out


def cta_primary_color(c: Dict[str, Any]) -> Tuple[Optional[RGB], List[RGB]]:
    """A CTA's brand color: the most vivid gradient stop, else its solid fill."""
    stops = gradient_stops(c.get("bgi", ""))
    color_stops = [s for s in stops if not is_neutralish(s)]
    if color_stops:
        return max(color_stops, key=vividness), stops
    rgb = parse_css_color(c.get("bg", ""))
    if rgb and not is_neutralish(rgb):
        return rgb, stops
    return None, stops


def accent_from_ctas(ctas: List[Dict[str, Any]]) -> Tuple[List[Tuple[RGB, float]], List[RGB]]:
    """CTA brand colors ranked by area, discounted by depth, nav-zone CTA boosted."""
    weights: Dict[RGB, float] = {}
    best_w, best_stops = -1.0, []
    for c in ctas:
        primary, stops = cta_primary_color(c)
        top = float(c.get("top", 0))
        w = float(c.get("area", 0)) / (1.0 + max(0.0, top) / 1200.0)
        if top < 150:
            w *= 3.0
        if primary is not None:
            weights[primary] = weights.get(primary, 0.0) + w
        nn = [s for s in stops if not is_neutralish(s)]
        if len(nn) >= 2 and w > best_w:
            best_w, best_stops = w, nn
    return sorted(weights.items(), key=lambda kv: kv[1], reverse=True), best_stops


def page_background(shot: Shot, probe: Dict[str, Any]) -> Token:
    palette = shot.palette(8)
    bg_rgb, share = palette[0]
    if max(bg_rgb) - min(bg_rgb) < 12 and share < 0.55:
        for rgb, s in palette[1:]:
            if s > 0.40 and saturation(rgb) > 0.20:
                bg_rgb, share = rgb, s
                break
    css_bg = parse_css_color(probe.get("body_bg", "")) or parse_css_color(probe.get("html_bg", ""))
    if css_bg and color_distance(css_bg, bg_rgb) < 12:
        return Token(rgb_to_hex(css_bg), min(0.97, 0.7 + share), "render:dominant+css:body")
    return Token(rgb_to_hex(bg_rgb), min(0.95, 0.55 + share), "render:dominant")


def on_page_bg(sample: Dict[str, Any], bg: RGB) -> bool:
    if sample.get("eimg"):
        return False
    ebg = flatten_on(sample.get("ebg", ""), bg) if sample.get("ebg") else None
    return ebg is None or color_distance(ebg, bg) < 14


def verify_text_color(shot: Shot, samples: List[Dict[str, Any]], css_rgb: RGB, bg: RGB) -> Tuple[RGB, Dict[str, Any]]:
    """Check a CSS text color against the glyph pixels of up to 6 of its boxes.
    A rendered color between bg and the CSS color is antialiasing and agrees; a
    rendered color off that line (a parent opacity, a blend mode, a gradient
    clipped to the text) replaces the CSS value."""
    rendered: List[RGB] = []
    for s in sorted(samples, key=lambda s: -s["fs"])[:6]:
        if s["fs"] < 15:
            continue
        fg = foreground_color(shot.pixels(s))
        if fg:
            rendered.append(fg)
    if not rendered:
        return css_rgb, {"checked": 0}
    agree = sum(1 for r in rendered if color_distance(r, css_rgb) < RENDER_AGREE or between(r, bg, css_rgb))
    info: Dict[str, Any] = {"checked": len(rendered), "agree": agree}
    if agree * 2 < len(rendered):
        rendered.sort(key=lambda p: sum(p))
        info["rendered"] = rgb_to_hex(rendered[len(rendered) // 2])
        return rendered[len(rendered) // 2], info
    return css_rgb, info


def text_roles(shot: Shot, probe: Dict[str, Any], bg: RGB, ex: Extraction) -> None:
    samples = []
    for s in probe.get("texts") or []:
        if s.get("cta") or not on_page_bg(s, bg):
            continue
        rgb = flatten_on(s.get("color", ""), bg)
        if rgb is None or s.get("clip"):
            fg = foreground_color(shot.pixels(s))
            if not fg:
                continue
            rgb = fg
        s = dict(s, rgb=rgb, weight=s["chars"] * s["fs"])
        samples.append(s)
    if not samples:
        body = parse_css_color(probe.get("body_color", ""))
        if body:
            ex.tokens["text_primary"] = Token(rgb_to_hex(body), 0.6, "css:body.color")
        return

    def top_clusters(pool: List[Dict[str, Any]]) -> List[Tuple[RGB, float]]:
        return cluster_colors([(s["rgb"], s["weight"]) for s in pool], radius=TEXT_ROLE_DISTANCE)

    headings = [s for s in samples if s["heading"]]
    body = [s for s in samples if not s["heading"] and not s["link"] and not s["small"] and not s["footer"] and 14.5 <= s["fs"] <= 26]
    small = [s for s in samples if not s["heading"] and not s["link"] and (s["fs"] < 14.5 or s["small"] or s["footer"])]

    def members(pool: List[Dict[str, Any]], rgb: RGB) -> List[Dict[str, Any]]:
        return [s for s in pool if color_distance(s["rgb"], rgb) <= TEXT_ROLE_DISTANCE]

    text_rgb, text_src = None, ""
    for pool, src in ((headings, "headings"), (body, "body text"), (samples, "all text")):
        for rgb, _w in top_clusters(pool)[:2]:
            if contrast_ratio(rgb, bg) >= 4.5:
                text_rgb, text_src = rgb, src
                break
        if text_rgb:
            break
    if text_rgb is None:
        text_rgb, text_src = top_clusters(samples)[0][0], "all text (low contrast)"
    text_rgb, check = verify_text_color(shot, members(samples, text_rgb), text_rgb, bg)
    ex.tokens["text_primary"] = Token(rgb_to_hex(text_rgb), 0.9 if check.get("agree") else 0.75, f"css+render:{text_src}")
    ex.evidence["text_render_check"] = check

    sec = None
    total_body = sum(s["weight"] for s in body) or 1.0
    for rgb, w in top_clusters(body):
        if color_distance(rgb, text_rgb) > TEXT_ROLE_DISTANCE and contrast_ratio(rgb, bg) >= 3.0 and w / total_body >= 0.15:
            sec = rgb
            break
    if sec:
        sec, chk = verify_text_color(shot, members(body, sec), sec, bg)
        ex.tokens["text_secondary"] = Token(rgb_to_hex(sec), 0.8, "css+render:paragraphs")
        ex.evidence["text_secondary_render_check"] = chk
    # muted: the quietest grey-ish text, from small print first, then the body
    # colors left after text and text_secondary; it must read quieter than them
    muted = None
    louder = contrast_ratio(sec or text_rgb, bg)
    for pool in (small, body):
        for rgb, _w in top_clusters(pool):
            if color_distance(rgb, text_rgb) <= TEXT_ROLE_DISTANCE or (sec and color_distance(rgb, sec) <= TEXT_ROLE_DISTANCE / 2):
                continue
            if saturation(rgb) > 0.45 or not (2.0 <= contrast_ratio(rgb, bg) < louder):
                continue
            muted = rgb
            break
        if muted:
            break
    if muted:
        ex.tokens["text_muted"] = Token(rgb_to_hex(muted), 0.7, "css+render:small print")
    heads = top_clusters(headings)
    if heads and color_distance(heads[0][0], text_rgb) > TEXT_ROLE_DISTANCE:
        ex.evidence["heading_color"] = rgb_to_hex(heads[0][0])


def surface_roles(shot: Shot, probe: Dict[str, Any], bg: RGB, ex: Extraction) -> None:
    cards = []
    for s in probe.get("surfaces") or []:
        parent_bg = flatten_on(s.get("ebg", ""), bg) if s.get("ebg") else bg
        if parent_bg is not None and color_distance(parent_bg, bg) > 14:
            continue  # a card inside a colored band, not on the page background
        radius = px_value(s.get("radius")) or 0.0
        rendered = mode_color(shot.pixels(s, inset=max(6.0, radius) + 2))
        if rendered is None:
            continue
        cards.append(dict(s, rendered=rendered, radius_px=radius, area=s["w"] * s["h"]))
    if not cards:
        return
    filled = [(c["rendered"], float(c["area"])) for c in cards
              if color_distance(c["rendered"], bg) > 6 and contrast_ratio(c["rendered"], bg) < 3.0]
    if filled:
        rgb = cluster_colors(filled, radius=10)[0][0]
        ex.tokens["surface"] = Token(rgb_to_hex(rgb), 0.8, "render:card pixels")
    borders = []
    for c in cards:
        if c.get("bw", 0) >= 0.5 and c.get("border"):
            on = parse_css_color(ex.tokens["surface"].value) if "surface" in ex.tokens else bg
            b = flatten_on(c["border"], on or bg)
            if b and color_distance(b, on or bg) > 4:
                borders.append((b, float(c["area"])))
    if borders:
        ex.tokens["border"] = Token(rgb_to_hex(cluster_colors(borders, radius=10)[0][0]), 0.75, "css:card border")
    radii = sorted(c["radius_px"] for c in cards if c["radius_px"] <= MAX_CARD_RADIUS_PX)
    if radii:
        ex.tokens["radius"] = Token(css_length(radii[len(radii) // 2]), 0.75, "css:card border-radius (median)")
    shadows = Counter(c["shadow"] for c in cards if c.get("shadow"))
    if shadows:
        ex.evidence["shadow"] = shadows.most_common(1)[0][0]
    ex.evidence["cards_measured"] = len(cards)


ACCENT_VAR_NAME = re.compile(r"(accent|primary|brand|main|cta)", re.I)
ACCENT_VAR_SKIP = re.compile(r"(deep|dark|light|hover|active|soft|muted|subtle|bg|background|text|fg|border|shadow|\d{2,3})", re.I)


def named_accents(css_vars: Dict[str, str]) -> List[RGB]:
    """Colors the site itself names accent, primary or brand in its :root
    custom properties (variants such as --accent-dark are skipped)."""
    out = []
    for name, value in (css_vars or {}).items():
        if ACCENT_VAR_NAME.search(name) and not ACCENT_VAR_SKIP.search(name):
            rgb = parse_css_color(value)
            if rgb and not is_neutralish(rgb):
                out.append(rgb)
    return out


def accent_roles(shot: Shot, probe: Dict[str, Any], bg: RGB, ex: Extraction) -> None:
    ctas = probe.get("ctas") or []
    ranked, grad_stops = accent_from_ctas(ctas)
    ranked = [(rgb, w) for rgb, w in ranked if contrast_ratio(rgb, bg) >= GHOST_CTA_MAX_CONTRAST]
    # a gradient CTA whose stops include the color the site names "accent" in
    # its custom properties: that stop is the accent, whatever its vividness
    named = named_accents(probe.get("css_vars") or {})
    if ranked and grad_stops and named:
        for stop in grad_stops:
            if any(color_distance(stop, n) < 8 for n in named) and stop != ranked[0][0]:
                ranked = [(stop, ranked[0][1])] + [(rgb, w) for rgb, w in ranked if rgb != stop]
                ex.evidence["accent_named_by_css_var"] = rgb_to_hex(stop)
                break
    theme = parse_css_color(probe.get("theme_color", ""))
    accent: Optional[RGB] = None
    if ranked:
        accent = ranked[0][0]
        conf = 0.9 if (theme and contrast_ratio(theme, accent) < 1.3) or ex.evidence.get("accent_named_by_css_var") else 0.82
        ex.tokens["accent"] = Token(rgb_to_hex(accent), conf, "css:cta-background" + ("+css-var" if ex.evidence.get("accent_named_by_css_var") else ""))
    elif theme and not is_neutralish(theme):
        accent = theme
        ex.tokens["accent"] = Token(rgb_to_hex(theme), 0.7, "meta:theme-color")
    else:
        sat = [(rgb, s) for rgb, s in shot.palette(8) if rgb != bg and saturation(rgb) > 0.35 and contrast_ratio(rgb, bg) >= 1.8]
        link = parse_css_color(probe.get("link_color", ""))
        if sat:
            accent = sat[0][0]
            ex.tokens["accent"] = Token(rgb_to_hex(accent), min(0.75, 0.45 + sat[0][1] * 2), "render:saturated")
        elif link and not is_neutralish(link):
            accent = link
            ex.tokens["accent"] = Token(rgb_to_hex(link), 0.55, "css:link-color")
        else:
            accent = parse_css_color(ex.tokens["text_primary"].value) if "text_primary" in ex.tokens else (91, 141, 239)
            ex.tokens["accent"] = Token(rgb_to_hex(accent), 0.25, "fallback:text-color")
            ex.warnings.append("No brand accent found on buttons, theme-color or the page: the text color stands in. Confirm the accent.")

    # render check on the button that carries the accent
    cta = None
    for c in sorted(ctas, key=lambda c: -float(c.get("area", 0))):
        prim, stops = cta_primary_color(c)
        if prim == accent or (accent is not None and accent in stops):
            cta = c
            break
    if cta and accent:
        px = shot.pixels(cta, inset=3)
        if px:
            nearest = min(color_distance(p, accent) for p in px)
            ex.evidence["accent_render_check"] = {"cta_text": cta.get("text", ""), "nearest_pixel_distance": round(nearest, 1),
                                                  "button_mode": rgb_to_hex(mode_color(px) or accent)}
            if nearest > RENDER_AGREE:
                ex.warnings.append(f"The accent {rgb_to_hex(accent)} read in the CSS does not appear in the button's pixels "
                                   f"(closest {round(nearest)}): check the button on the board.")
        on = flatten_on(cta.get("color", ""), accent)
        if on and contrast_ratio(on, accent) >= 1.5:
            ex.tokens["on_accent"] = Token(rgb_to_hex(on), 0.85, "css:cta-label")
        rpx = px_value(cta.get("radius"))
        if rpx is not None:
            ex.evidence["radius_button"] = css_length(rpx) if rpx <= 999 else "999px"

    sec: Optional[RGB] = None
    if accent is not None and grad_stops:
        far = max(grad_stops, key=lambda s: color_distance(s, accent))
        if color_distance(far, accent) > 12:
            sec = far
            ex.tokens["accent_secondary"] = Token(rgb_to_hex(far), 0.7, "css:cta-gradient-stop")
    if sec is None and accent is not None:
        for rgb, _w in ranked[1:]:
            if contrast_ratio(rgb, accent) > 1.25:
                ex.tokens["accent_secondary"] = Token(rgb_to_hex(rgb), 0.6, "css:cta-secondary")
                break


# --- Fonts ----------------------------------------------------------------------------

FACE_RE = re.compile(r"@font-face\s*{([^}]*)}", re.I | re.S)


def fetch_css(probe: Dict[str, Any], page_url: str) -> List[Tuple[str, str]]:
    """(url, text) of the page's stylesheets (one level of @import followed) plus
    its inline <style> blocks."""
    out: List[Tuple[str, str]] = [(page_url, probe.get("inline_css") or "")]
    queue = list(dict.fromkeys(probe.get("sheets") or []))
    seen = set()
    while queue and len(seen) < 25:
        u = queue.pop(0)
        if u in seen or not u.startswith(("http://", "https://")):
            continue
        seen.add(u)
        try:
            raw, _ct = http_get(u, "text/css,*/*;q=0.1", page_url, limit=3 * 1024 * 1024)
        except Exception:  # noqa: BLE001
            continue
        text = raw.decode("utf-8", errors="ignore")
        out.append((u, text))
        for m in re.finditer(r"@import\s+(?:url\()?['\"]?([^'\")\s;]+)", text):
            queue.append(urllib.parse.urljoin(u, m.group(1)))
    for _u, text in list(out):
        for m in re.finditer(r"@import\s+(?:url\()?['\"]?([^'\")\s;]+)", text):
            iu = urllib.parse.urljoin(page_url, m.group(1))
            if iu not in seen and iu.startswith("http"):
                seen.add(iu)
                try:
                    raw, _ct = http_get(iu, "text/css,*/*;q=0.1", page_url, limit=3 * 1024 * 1024)
                    out.append((iu, raw.decode("utf-8", errors="ignore")))
                except Exception:  # noqa: BLE001
                    pass
    return out


def parse_font_faces(css_texts: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    faces = []
    for base, text in css_texts:
        for m in FACE_RE.finditer(text):
            body = m.group(1)

            def prop(name: str) -> str:
                pm = re.search(rf"{name}\s*:\s*([^;]+)", body, re.I)
                return pm.group(1).strip() if pm else ""
            fam = prop("font-family").strip("'\" ")
            src = prop("src")
            urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)\s*(?:format\(\s*['\"]?([\w-]+)['\"]?\s*\))?", src)
            if not fam or not urls:
                continue
            urls.sort(key=lambda u: 0 if "woff2" in (u[1] or u[0]) else (1 if "woff" in (u[1] or u[0]) else 2))
            faces.append({"family": fam, "url": urllib.parse.urljoin(base, urls[0][0]), "format": urls[0][1],
                          "weight": prop("font-weight") or "400", "style": (prop("font-style") or "normal").lower(),
                          "unicode_range": prop("unicode-range")})
    return faces


def split_stack(stack: str) -> List[str]:
    return [p.strip().strip("'\"").strip() for p in (stack or "").split(",") if p.strip()]


def covers_latin(unicode_range: str) -> bool:
    if not unicode_range:
        return True
    for part in unicode_range.split(","):
        part = part.strip().upper().replace("U+", "")
        try:
            if "-" in part:
                a, b = part.split("-")
                if int(a, 16) <= 0x41 <= int(b, 16):
                    return True
            elif "?" in part:
                if int(part.replace("?", "0"), 16) <= 0x41 <= int(part.replace("?", "F"), 16):
                    return True
            elif int(part, 16) == 0x41:
                return True
        except ValueError:
            continue
    return False


def resolve_font(stack: str, faces_loaded: List[Dict[str, Any]], declared: List[Dict[str, Any]], role: str,
                 warnings: List[str]) -> Tuple[str, str, str]:
    """(family, fallback, source) of the family the page really renders for a
    CSS stack: the first one that is loaded, or a system family."""
    fams = split_stack(stack)
    loaded = {f["family"].lower() for f in faces_loaded if f.get("status") == "loaded"}
    declared_names = {f["family"].lower() for f in declared} | {f["family"].lower() for f in faces_loaded}
    skipped = []
    for i, fam in enumerate(fams):
        low = fam.lower()
        rest = ", ".join(fams[i + 1:])
        if low in SYSTEM_KEYWORDS:
            return "system-ui", rest, "system"
        if low in GENERIC_FAMILIES:
            return low, rest, "system"
        if low in loaded:
            src_urls = [f["url"] for f in declared if f["family"].lower() == low]
            source = "google_fonts" if any("fonts.gstatic.com" in u for u in src_urls) else ("self_hosted" if src_urls else "other")
            if skipped:
                warnings.append(f"{role} font: {', '.join(skipped)} never loaded on the page; it renders in {fam}.")
            return fam, rest, source
        if low in declared_names:
            skipped.append(fam)
            continue
        if low in SYSTEM_FONTS:
            if skipped:
                warnings.append(f"{role} font: {', '.join(skipped)} is declared but never loaded; the page renders {fam}.")
            return fam, rest, "system"
        skipped.append(fam)
    if skipped:
        warnings.append(f"{role} font: none of {', '.join(skipped)} loaded; the browser default renders.")
    return "system-ui", "sans-serif", "system"


def font_weights(samples: List[Dict[str, Any]], heading: bool) -> List[int]:
    ws = set()
    for s in samples:
        if bool(s.get("heading")) != heading:
            continue
        try:
            w = int(round(float(str(s.get("fw", "400")))))
        except ValueError:
            w = {"bold": 700, "normal": 400}.get(str(s.get("fw")).lower(), 400)
        if 100 <= w <= 900:
            ws.add(int(round(w / 100.0)) * 100)
    return sorted(ws)


def download_font_files(family: str, weights: List[int], declared: List[Dict[str, Any]], out_dir: Path,
                        policy: str, referer: str) -> List[Dict[str, Any]]:
    """Copy the latin face files of a family for offline rendering. policy:
    google (only Google Fonts files, open licenses), all, none."""
    if policy == "none":
        return []
    files = []
    picked = set()
    for f in declared:
        if f["family"].lower() != family.lower() or not covers_latin(f.get("unicode_range", "")):
            continue
        if policy == "google" and "fonts.gstatic.com" not in f["url"]:
            continue
        wraw = str(f.get("weight", "400")).split()
        try:
            lo, hi = int(wraw[0]), int(wraw[-1])
        except ValueError:
            lo = hi = 400
        style = "italic" if "italic" in f.get("style", "") else "normal"
        for w in (weights or [400]):
            if not (lo <= w <= hi) or (w, style) in picked:
                continue
            ext = os.path.splitext(urllib.parse.urlparse(f["url"]).path)[1].lower() or ".woff2"
            fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(ext)
            if not fmt:
                continue
            name = f"{re.sub(r'[^A-Za-z0-9]+', '', family)}-{w}{'-italic' if style == 'italic' else ''}{ext}"
            dest = out_dir / "assets" / "fonts" / name
            try:
                if not dest.exists():
                    raw, _ct = http_get(f["url"], "font/*,*/*", referer, limit=4 * 1024 * 1024)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(raw)
            except Exception:  # noqa: BLE001
                continue
            picked.add((w, style))
            files.append({"path": f"assets/fonts/{name}", "weight": w, "style": style, "format": fmt})
            if lo == hi:
                break  # a static face serves one weight
    return files


# --- Images -----------------------------------------------------------------------------

def classify_image(path: Path, meta: Dict[str, Any]) -> Tuple[bool, str, str]:
    """(keep, role, reason). Decorative files (glows, gradients, grain, flat
    fills) are dropped by pixel statistics; the role comes from alt text, alpha
    and position."""
    from PIL import Image, ImageFilter, ImageStat
    alt = (meta.get("alt") or "").lower()
    try:
        with Image.open(path) as im:
            rgba = im.convert("RGBA")
    except Exception:
        if path.suffix.lower() == ".svg" and meta.get("kind") == "img":
            return True, "illustration", "svg illustration"
        return False, "other", "unreadable image"
    small = rgba.copy()
    small.thumbnail((96, 96))
    alpha = small.getchannel("A")
    transparent = sum(1 for a in (alpha.get_flattened_data() if hasattr(alpha, "get_flattened_data") else alpha.getdata()) if a < 128) / float(small.width * small.height)
    rgb = Image.new("RGB", small.size, (255, 255, 255))
    rgb.paste(small, mask=alpha)
    gray = rgb.convert("L")
    std = ImageStat.Stat(gray).stddev[0]
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    sat = ImageStat.Stat(rgb.convert("HSV").getchannel("S")).mean[0]
    used = len(rgb.quantize(colors=32).getcolors() or [])
    stats = f"std {std:.0f}, edges {edges:.1f}, sat {sat:.0f}, colors {used}"
    if transparent < 0.5:
        if used <= 2:
            return False, "texture", f"flat fill ({stats})"
        if edges < 4.0 and std < 40:
            return False, "texture", f"smooth gradient or glow ({stats})"
        if sat < 25 and std < 30 and edges > 10:
            return False, "texture", f"grain or noise texture ({stats})"
    if meta.get("kind") == "css-background" and str(meta.get("repeat", "")).startswith("repeat") and meta.get("repeat") != "no-repeat":
        return False, "texture", f"tiled CSS background ({stats})"
    if re.search(r"team|founder|portrait|people|équipe|equipe|fondateur|headshot|photo of", alt):
        role = "team"
    elif re.search(r"screenshot|dashboard|app|product|interface|\bui\b|capture|produit", alt):
        role = "product"
    elif transparent >= 0.2:
        role = "illustration"
    elif meta.get("top", 9999) < 900 and meta.get("w", 0) >= 600:
        role = "hero"
    else:
        role = "other"
    return True, role, stats


def harvest_assets(url: str, probe: Dict[str, Any], out_dir: Path, max_images: int,
                   shots: Dict[str, Path], warnings: List[str]) -> Dict[str, Any]:
    """Download the logo, favicon, og:image and page images, copy the captures.
    Paths in the manifest are relative to out_dir (the project-context folder)."""
    assets_dir = out_dir / "assets"
    site_dir = assets_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    rel = lambda p: str(Path(p).relative_to(out_dir))  # noqa: E731
    manifest: Dict[str, Any] = {"license": IMAGE_LICENSE, "license_note": IMAGE_LICENSE_NOTE, "source_page": url,
                                "logo": None, "favicon": None, "og_image": None, "screenshot": None, "hero": None,
                                "images": [], "rejected": []}

    logo = probe.get("logo") or {}
    logos_dir = assets_dir / "logos"
    if logo.get("kind") == "img" and logo.get("src"):
        rec = download(logo["src"], logos_dir, "source", referer=url)
        if rec:
            manifest["logo"] = {"path": rel(rec["path"]), "kind": "img", "source": logo["src"][:300],
                                "w": rec.get("w"), "h": rec.get("h"), "css_filter": logo.get("filter", "")}
    elif logo.get("kind") == "svg" and logo.get("svg"):
        logos_dir.mkdir(parents=True, exist_ok=True)
        out = logos_dir / "source.svg"
        out.write_text(logo["svg"], encoding="utf-8")
        manifest["logo"] = {"path": rel(out), "kind": "svg", "source": "inline-svg", "w": logo.get("w"), "h": logo.get("h"),
                            "css_filter": logo.get("filter", "")}
    if manifest["logo"] and manifest["logo"].get("css_filter"):
        warnings.append(f"The site paints its logo through a CSS filter ({manifest['logo']['css_filter']}): the file's own colors differ from what visitors see.")

    icons = probe.get("icons") or []
    if icons:
        def icon_score(i: Dict[str, Any]) -> int:
            m = re.search(r"(\d+)", i.get("sizes", "") or "")
            return (int(m.group(1)) if m else 0) + (200 if "apple-touch" in (i.get("rel") or "") else 0)
        best = sorted(icons, key=icon_score, reverse=True)[0]
        rec = download(best["href"], site_dir, "favicon", referer=url)
        if rec:
            manifest["favicon"] = {"path": rel(rec["path"]), "source": best["href"][:300], "w": rec.get("w"), "h": rec.get("h")}
            if manifest["logo"] is None and (rec.get("w") or 0) >= 96:
                manifest["logo"] = {"path": rel(rec["path"]), "kind": "icon-fallback", "source": best["href"][:300],
                                    "w": rec.get("w"), "h": rec.get("h")}

    if probe.get("og_image"):
        rec = download(probe["og_image"], site_dir, "og-image", referer=url)
        if rec:
            manifest["og_image"] = {"path": rel(rec["path"]), "source": probe["og_image"][:300], "w": rec.get("w"), "h": rec.get("h")}

    vp = shots.get("viewport")
    if vp and vp.exists():
        dest = site_dir / "screenshot.png"
        shutil.copyfile(vp, dest)
        dims = _image_dims(dest)
        manifest["screenshot"] = {"path": rel(dest), "source": "playwright:viewport", "w": dims[0] if dims else None, "h": dims[1] if dims else None}
    hero = shots.get("hero")
    if hero and hero.exists():
        try:
            from PIL import Image
            dest = site_dir / "hero.jpg"
            with Image.open(hero) as im:
                im.convert("RGB").save(dest, "JPEG", quality=85)
            dims = _image_dims(dest)
            manifest["hero"] = {"path": rel(dest), "source": url, "w": dims[0] if dims else None, "h": dims[1] if dims else None,
                                "alt": "Capture of the hero section", "role": "hero", "license": IMAGE_LICENSE}
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Hero capture not saved: {e}")

    # page images: <img> and big CSS backgrounds, deduplicated, largest first
    by_src: Dict[str, Dict[str, Any]] = {}
    for c in list(probe.get("images") or []) + list(probe.get("backgrounds") or []):
        src = c.get("src") or ""
        if not src or src == logo.get("src") or src == probe.get("og_image"):
            continue
        if c.get("area", 0) > by_src.get(src, {}).get("area", -1):
            by_src[src] = c
    ranked = sorted(by_src.values(), key=lambda c: c.get("area", 0), reverse=True)
    kept: List[Dict[str, Any]] = []
    n = 0
    for c in ranked:
        if len(kept) >= max(0, max_images - (1 if manifest["hero"] else 0)) or n >= 30:
            break
        if min(c.get("w", 0), c.get("h", 0)) < MIN_ASSET_EDGE and c.get("kind") != "css-background":
            continue
        n += 1
        rec = download(c["src"], site_dir, f"asset-{len(kept) + 1:02d}", referer=url)
        if not rec:
            manifest["rejected"].append({"source": c["src"][:300], "reason": "download failed or not an image"})
            continue
        if rec.get("w") and rec.get("h") and min(rec["w"], rec["h"]) < MIN_DOWNLOAD_EDGE:
            rec["path"].unlink()
            manifest["rejected"].append({"source": c["src"][:300], "reason": "too small"})
            continue
        keep, role, reason = classify_image(rec["path"], c)
        if not keep:
            rec["path"].unlink()
            manifest["rejected"].append({"source": c["src"][:300], "reason": reason})
            continue
        host = urllib.parse.urlparse(c["src"]).netloc.lower()
        entry = {"path": rel(rec["path"]), "source": c["src"][:300], "w": rec.get("w") or c.get("w"), "h": rec.get("h") or c.get("h"),
                 "alt": c.get("alt", ""), "role": role, "license": IMAGE_LICENSE, "pixel_stats": reason}
        if any(s in host for s in STOCK_HOSTS):
            entry["license_note"] = f"served by a stock host ({host}): check the stock license covers ads before reuse"
        kept.append(entry)
    manifest["images"] = kept
    (site_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


# --- Brand name ---------------------------------------------------------------------------

def brand_name(url: str, probe: Dict[str, Any]) -> str:
    name = (probe.get("site_name") or "").strip()
    if not name:
        title = (probe.get("title") or "").strip()
        name = re.split("\\s[|\\-:·•]\\s|\\s\u2013\\s|\\s\u2014\\s", title)[0].strip() if title else ""
    if not name or len(name) > 40:
        host = urllib.parse.urlparse(url).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        name = host.split(".")[0] if host and not host.startswith(("127.", "localhost")) else "brand"
    return name


# --- Pipeline --------------------------------------------------------------------------------

def run_heuristics(url: str, cap: Dict[str, Any], out_dir: Path, font_policy: str) -> Tuple[Extraction, Dict[str, Any]]:
    probe = cap["probe"]
    ex = Extraction(source_url=url)
    shot = Shot(cap["full"])
    bg_tok = page_background(shot, probe)
    ex.tokens["bg"] = bg_tok
    bg = parse_css_color(bg_tok.value) or (255, 255, 255)
    text_roles(shot, probe, bg, ex)
    if "text_primary" not in ex.tokens:
        ex.tokens["text_primary"] = Token(rgb_to_hex((0, 0, 0) if not is_dark(bg) else (255, 255, 255)), 0.3, "fallback:contrast")
    surface_roles(shot, probe, bg, ex)
    accent_roles(shot, probe, bg, ex)

    # fonts actually rendered
    css_texts = fetch_css(probe, url)
    declared = parse_font_faces(css_texts)
    faces = probe.get("faces") or []
    fonts: Dict[str, Any] = {}
    for role, stack, heading in (("display", probe.get("h1_font", "") or probe.get("body_font", ""), True),
                                 ("body", probe.get("body_font", ""), False)):
        fam, fallback, source = resolve_font(stack, faces, declared, role, ex.warnings)
        entry: Dict[str, Any] = {"family": fam}
        if fallback:
            entry["fallback"] = fallback
        weights = font_weights(probe.get("texts") or [], heading)
        if weights:
            entry["weights"] = weights
        entry["source"] = source
        if source in ("google_fonts", "self_hosted"):
            files = download_font_files(fam, weights, declared, out_dir, font_policy if source == "google_fonts" or font_policy == "all" else "none", url)
            if files:
                entry["files"] = files
            elif source == "self_hosted" and font_policy != "all":
                ex.warnings.append(f"{role} font {fam} is self-hosted by the site: its license is unknown, so the files were not copied "
                                   "(rerun with --font-files all once the founder confirms the license allows it).")
        fonts[role] = entry
        ex.tokens[f"font_{role}"] = Token(f"{fam}{', ' + fallback if fallback else ''}", 0.85 if source != "system" else 0.7, f"render:document.fonts ({source})")
    links = [h for h in (probe.get("font_links") or []) if h.startswith("https://") and "family=" in h]
    if not links:
        for _u, t in css_texts:
            for m in re.finditer(r"@import\s+(?:url\()?['\"]?(https://fonts\.googleapis\.com/[^'\")\s;]+)", t):
                links.append(m.group(1))
    if links and any(fonts[r]["source"] == "google_fonts" for r in fonts):
        fonts["fonts_url"] = links[0]
    for role in ("display", "body"):
        if fonts[role]["source"] not in ("system",) and not fonts[role].get("files") and "fonts_url" not in fonts:
            ex.warnings.append(f"{role} font {fonts[role]['family']} needs the site's own stylesheet or local files to render elsewhere.")
    ex.evidence["fonts_loaded"] = sorted({f["family"] for f in faces if f.get("status") == "loaded"})
    ex.evidence["font_faces_declared"] = len(declared)
    color_vars = {k: rgb_to_hex(parse_css_color(v)) for k, v in (probe.get("css_vars") or {}).items()  # type: ignore[arg-type]
                  if parse_css_color(v)}
    ex.evidence["css_color_vars"] = dict(list(color_vars.items())[:24])
    ex.evidence["logo_candidates"] = probe.get("logo_candidates") or []
    if probe.get("cookie_banners_hidden"):
        ex.evidence["cookie_banners_hidden"] = probe["cookie_banners_hidden"]
    return ex, fonts


def build_brand_v2(url: str, ex: Extraction, probe: Dict[str, Any], fonts: Dict[str, Any], manifest: Dict[str, Any],
                   logo_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    tok = ex.tokens
    val = lambda k: parse_css_color(str(tok[k].value)) if k in tok else None  # noqa: E731
    bg = val("bg") or (255, 255, 255)
    text = val("text_primary") or (0, 0, 0)
    accent = val("accent") or text
    mode = "dark" if is_dark(bg) else "light"
    colors: Dict[str, str] = {"bg": rgb_to_hex(bg)}
    if "surface" in tok:
        colors["surface"] = str(tok["surface"].value)
    colors["text"] = rgb_to_hex(text)
    for key, role in (("text_secondary", "text_secondary"), ("text_muted", "text_muted"), ("border", "border")):
        if key in tok:
            colors[role] = str(tok[key].value)
    colors["accent"] = rgb_to_hex(accent)
    sec = val("accent_secondary")
    if sec and contrast_ratio(sec, bg) >= GHOST_CTA_MAX_CONTRAST:
        colors["accent_secondary"] = rgb_to_hex(sec)
    if "on_accent" in tok:
        colors["on_accent"] = str(tok["on_accent"].value)

    name = brand_name(url, probe)
    brand: Dict[str, Any] = {"schema_version": "2.0", "name": name}
    if url.startswith(("http://", "https://")):
        brand["source_url"] = url
    brand.update({"as_of": dt.date.today().isoformat(), "mode": mode, "colors": colors})
    if "radius" in tok:
        brand["radius"] = str(tok["radius"].value)
    elif ex.evidence.get("radius_button") and (px_value(ex.evidence["radius_button"]) or 0) <= MAX_CARD_RADIUS_PX:
        brand["radius"] = ex.evidence["radius_button"]
    brand["fonts"] = fonts
    if logo_result:
        brand["logos"] = logo_result["logos"]
    brand["logo_text"] = name
    if logo_result:
        brand["logo_audit"] = logo_result["logo_audit"]
    elif manifest.get("logo"):
        brand["logo_audit"] = {"status": "unchecked", "issues": ["The logo pipeline did not run on the harvested file."]}

    assets: Dict[str, Any] = {}
    for key, out_key in (("og_image", "og_image_path"), ("favicon", "favicon_path"), ("screenshot", "screenshot_path")):
        if (manifest.get(key) or {}).get("path"):
            assets[out_key] = manifest[key]["path"]
    images = []
    for im in ([manifest["hero"]] if manifest.get("hero") else []) + list(manifest.get("images") or []):
        e: Dict[str, Any] = {"path": im["path"], "role": im.get("role", "other")}
        for k in ("w", "h"):
            if isinstance(im.get(k), (int, float)) and im[k] >= 1:
                e[k] = int(im[k])
        if im.get("alt"):
            e["alt"] = im["alt"][:120]
        if str(im.get("source", "")).startswith(("http://", "https://")):
            e["source_url"] = im["source"]
        images.append(e)
    if images:
        assets["images"] = images
    if assets:
        brand["assets"] = assets
    brand["warnings"] = list(ex.warnings)
    ext: Dict[str, Any] = {
        "candidate": "brand-candidate.json",
        "confidence": {k: round(t.confidence, 2) for k, t in tok.items()},
        "image_license": IMAGE_LICENSE,
        "image_license_note": IMAGE_LICENSE_NOTE,
    }
    for k in ("shadow", "radius_button", "heading_color", "css_color_vars"):
        if ex.evidence.get(k):
            ext[k] = ex.evidence[k]
    if logo_result:
        ext["logo_png"] = logo_result["png_fallbacks"]
        if manifest.get("logo"):
            ext["logo_source"] = manifest["logo"]["path"]
    brand["extensions"] = {"extract_brand": ext}
    return brand


def validate_brand(path: Path) -> Tuple[Optional[bool], str]:
    """Validate a brand.json V2 file with the stack's stdlib validator. (None,
    reason) when shared/ is not next to agents/."""
    root = Path(__file__).resolve().parents[3]
    validator = root / "shared" / "scripts" / "validate_json.py"
    schema = root / "shared" / "schemas" / "brand.schema.json"
    if not validator.is_file() or not schema.is_file():
        return None, "shared/scripts/validate_json.py or shared/schemas/brand.schema.json not found next to agents/; copy shared/ to validate"
    proc = subprocess.run([sys.executable, str(validator), str(schema), str(path)], capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def finalize(out_dir: Path) -> int:
    """Promote the approved brand-draft.json to brand.json, dated today, only
    when it validates against the V2 schema."""
    draft = out_dir / "brand-draft.json"
    if not draft.is_file():
        print(f"[finalize] {draft} not found. Run the extraction first.", file=sys.stderr)
        return 4
    try:
        data = json.loads(draft.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[finalize] {draft} is not valid JSON: {e}", file=sys.stderr)
        return 5
    if isinstance(data, dict):
        data["as_of"] = dt.date.today().isoformat()
    tmp = out_dir / "brand.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok, detail = validate_brand(tmp)
    if ok is False:
        tmp.unlink()
        print(f"[finalize] brand-draft.json does not match shared/schemas/brand.schema.json; brand.json left unchanged:\n{detail}", file=sys.stderr)
        return 5
    os.replace(tmp, out_dir / "brand.json")
    print(f"wrote {out_dir / 'brand.json'}")
    print(f"schema: {'valid' if ok else 'not validated (' + detail + ')'}")
    return 0


# --- CLI -------------------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="Public URL of the brand's home page (required unless --finalize)")
    parser.add_argument("--out", required=True, help="The project-context folder (creates assets/ and brand-debug/ inside)")
    parser.add_argument("--finalize", action="store_true", help="After approval: validate brand-draft.json and write brand.json")
    parser.add_argument("--max-images", type=int, default=6, help="Page images to keep, hero capture included (default 6)")
    parser.add_argument("--font-files", choices=("google", "all", "none"), default="google",
                        help="Copy font files for offline rendering: google (Google Fonts only, open licenses; default), all, none")
    parser.add_argument("--no-logo-pipeline", action="store_true", help="Skip the logo audit and variants (debug only)")
    parser.add_argument("--no-firecrawl", action="store_true", help=argparse.SUPPRESS)  # kept for old command lines; no API is called
    args = parser.parse_args(argv)

    out_dir = Path(args.out).expanduser().resolve()
    if args.finalize:
        return finalize(out_dir)
    if not args.url:
        parser.error("--url is required unless --finalize is given")
    debug_dir = out_dir / "brand-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    url_parts = urllib.parse.urlsplit(args.url)
    if url_parts.scheme.lower() not in ("http", "https") or not url_parts.hostname:
        parser.error("--url must be an http or https URL")
    global _ALLOW_PRIVATE
    _ALLOW_PRIVATE = host_is_private(url_parts.hostname)  # local dev site: its own assets are local too
    if not robots_allows(args.url):
        print(f"[robots] {args.url} disallows crawling. Aborting.", file=sys.stderr)
        return 2
    try:
        cap = asyncio.run(capture(args.url, debug_dir))
    except ImportError as e:
        print(f"[playwright] not installed ({e}). Install it with "
              "`pip install -r agents/project-context/scripts/requirements.txt && python -m playwright install chromium`, "
              "or skip extraction and give the brand colors and logo in chat.", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"[playwright] {e}", file=sys.stderr)
        return 3
    probe = cap["probe"]

    ex, fonts = run_heuristics(args.url, cap, out_dir, args.font_files)
    if probe.get("cookie_banners_hidden"):
        ex.warnings.append(f"{probe['cookie_banners_hidden']} cookie or consent element(s) hidden before measuring; their buttons were ignored.")
    try:
        manifest = harvest_assets(args.url, probe, out_dir, max(0, args.max_images), cap, ex.warnings)
    except Exception as e:  # noqa: BLE001
        print(f"[harvest] non-fatal: {e}", file=sys.stderr)
        manifest = {"logo": None, "favicon": None, "og_image": None, "images": []}
    ex.assets = manifest
    n_imgs = len(manifest.get("images") or []) + (1 if manifest.get("hero") else 0)
    if n_imgs < 3:
        ex.warnings.append(f"Only {n_imgs} usable image(s) on this page (hero capture included): ask the founder for product or team photos, or run on a richer page.")

    logo_result = None
    if manifest.get("logo"):
        ex.tokens["logo"] = Token(manifest["logo"]["path"], 0.85 if manifest["logo"]["kind"] in ("img", "svg") else 0.5, f"asset:{manifest['logo']['kind']}")
        if not args.no_logo_pipeline:
            import logo_pipeline
            colors = {"bg": ex.tokens["bg"].value, "text": ex.tokens["text_primary"].value}
            mode = "dark" if is_dark(parse_css_color(colors["bg"]) or (255, 255, 255)) else "light"
            src = out_dir / manifest["logo"]["path"]
            if src.suffix.lower() in (".svg",) or src.suffix.lower() in logo_pipeline.RASTER_EXT:
                try:
                    logo_result = logo_pipeline.run_pipeline(src, out_dir, colors, mode)
                except Exception as e:  # noqa: BLE001
                    ex.warnings.append(f"Logo pipeline failed on {manifest['logo']['path']}: {e}")
            else:
                ex.warnings.append(f"Logo file {manifest['logo']['path']} is {src.suffix}: convert it to SVG or PNG and run logo_pipeline.py.")
    else:
        ex.warnings.append("No logo found on the page. Ask the founder for the file (SVG first), then run logo_pipeline.py on it.")

    (out_dir / "brand-candidate.json").write_text(json.dumps(ex.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    draft = build_brand_v2(args.url, ex, probe, fonts, manifest, logo_result)
    draft_path = out_dir / "brand-draft.json"
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    valid, detail = validate_brand(draft_path)

    print(f"wrote {out_dir / 'brand-candidate.json'}")
    print(f"wrote {draft_path} (schema: {'valid' if valid else ('INVALID' if valid is False else 'not validated')})")
    if valid is False:
        print(detail, file=sys.stderr)
    elif valid is None:
        print(f"  {detail}")
    print("\nColor roles:")
    for k, v in draft["colors"].items():
        src_key = {"text": "text_primary"}.get(k, k)
        t = ex.tokens.get(src_key)
        print(f"  {k:<17} {v}  {('conf=' + format(t.confidence, '.2f') + '  ' + t.source) if t else ''}")
    print(f"  radius            {draft.get('radius', '(none)')}")
    print(f"Fonts: display {fonts['display']['family']} ({fonts['display']['source']}), body {fonts['body']['family']} ({fonts['body']['source']})")
    print(f"Logo: {(manifest.get('logo') or {}).get('path', '(none)')}  audit: {(draft.get('logo_audit') or {}).get('status', 'n/a')}")
    print(f"Images: {n_imgs} kept (license {IMAGE_LICENSE}), {len(manifest.get('rejected') or [])} rejected")
    for w in ex.warnings:
        print(f"  - {w}")
    for issue in (draft.get("logo_audit") or {}).get("issues", []):
        print(f"  - logo: {issue}")
    print("\nNext: python3 render_brand_preview.py --brand " + str(draft_path))
    return 5 if valid is False else 0


if __name__ == "__main__":
    sys.exit(main())
