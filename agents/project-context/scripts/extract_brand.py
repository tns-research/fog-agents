#!/usr/bin/env python3
"""extract_brand.py: Extract brand tokens AND harvest brand assets from a URL.

This is the founders-OS brand front door. It does two jobs in one pass:

  1. Brand tokens (colors, fonts, logo) with confidence scores, combining:
     - the live DOM (computed styles, CTA/button colors, theme-color meta),
     - a Playwright headless screenshot (k-means palette of what the user sees),
     - firecrawl HTML (optional, when FIRECRAWL_API_KEY is set).

  2. Real assets downloaded to disk so the rest of the stack can build creatives
     from them: the logo (including inline-SVG logos serialized to a file), the
     og:image share card, the favicon, and the largest on-page product/hero
     images. Everything lands in <out>/assets/ with a manifest.

Accent detection is the part founders care about most, so it is driven by the
background color of the primary call-to-action button (that is almost always the
brand accent) rather than guessing from a whole-page palette where a small orange
button drowns under whitespace.

Writes brand-candidate.json (tokens + confidence + assets manifest) and a
brand-debug/ folder. The extract-brand skill then runs a validation loop with the
user before promoting brand-candidate.json to brand.json.

Usage:
    python extract_brand.py --url https://example.com --out ./out/
    python extract_brand.py --url https://example.com --out ./out/ --no-firecrawl
    python extract_brand.py --url https://example.com --out ./out/ --max-images 8

Hard rules (carried by the agent):
  - heuristic, never authoritative: every token publishes confidence
  - respects robots.txt: aborts if the homepage is disallowed
  - portable: only stdlib + Playwright + Pillow + (optional) firecrawl-py
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GENERIC_FONT_FALLBACKS = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace",
    "-apple-system", "blinkmacsystemfont", "inherit", "initial", "unset",
}

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# images smaller than this on their shorter rendered edge are treated as icons,
# not harvestable product/hero assets
MIN_ASSET_EDGE = 200
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024


# --- Data model -------------------------------------------------------------

@dataclass
class Token:
    value: Any
    confidence: float
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "confidence": round(self.confidence, 2), "source": self.source}


@dataclass
class Extraction:
    source_url: str
    tokens: dict[str, Token] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    assets: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "extracted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tokens": {k: t.as_dict() for k, t in self.tokens.items()},
            "assets": self.assets,
            "warnings": self.warnings,
        }


# --- URL + robots helpers ---------------------------------------------------

def resolve_url(base: str, src: str) -> str:
    if not src:
        return ""
    if src.startswith("data:"):
        return src
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("http"):
        return src
    return urllib.parse.urljoin(base, src)


def robots_allows(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": "project-context/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return True  # no robots = allowed
    ua_blocks = re.split(r"(?im)^user-agent:\s*", body)
    for block in ua_blocks:
        head, *rest = block.split("\n", 1)
        if head.strip() in ("*", "project-context"):
            disallow_lines = [ln for ln in (rest[0] if rest else "").splitlines() if ln.lower().startswith("disallow:")]
            for ln in disallow_lines:
                rule = ln.split(":", 1)[1].strip()
                if rule == "/":
                    return False
    return True


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
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".ico"):
        return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def download(url: str, dest_dir: Path, basename: str, referer: str | None = None) -> dict[str, Any] | None:
    """Download url into dest_dir/<basename><ext>. Returns a small record or None.

    Handles http(s) and data: URLs. Caps body size. Records pixel dimensions for
    rasters via Pillow when available.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        if url.startswith("data:"):
            header, _, payload = url.partition(",")
            ct = header[5:].split(";")[0] or "image/png"
            ext = _EXT_BY_CT.get(ct, ".png")
            raw = base64.b64decode(payload) if ";base64" in header else urllib.parse.unquote_to_bytes(payload)
        else:
            headers = {"User-Agent": BROWSER_UA, "Accept": "image/*,*/*"}
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                ct = resp.headers.get("Content-Type", "")
                raw = resp.read(MAX_DOWNLOAD_BYTES + 1)
            ext = _ext_from(url, ct)
        if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
            return None
        out = dest_dir / f"{basename}{ext}"
        out.write_bytes(raw)
        rec: dict[str, Any] = {"source": url[:300], "bytes": len(raw)}
        if ext != ".svg":
            dims = _image_dims(out)
            if dims:
                rec["w"], rec["h"] = dims
        return {"path": out, **rec}
    except Exception:
        return None


def _image_dims(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# --- Screenshot + rich DOM probe via Playwright -----------------------------

DOM_PROBE_JS = r"""() => {
    const css = (el) => el ? window.getComputedStyle(el) : null;
    const body = document.body;
    const bodyStyle = css(body);

    const abs = (u) => { try { return new URL(u, document.baseURI).href; } catch (e) { return u || ''; } };

    // theme-color + social share image + icons
    const meta = (sel, attr) => {
        const el = document.querySelector(sel);
        return el ? (el.getAttribute(attr) || '') : '';
    };
    const themeColor = meta('meta[name="theme-color"]', 'content');
    const ogImage = abs(meta('meta[property="og:image"]', 'content')
        || meta('meta[name="og:image"]', 'content')
        || meta('meta[name="twitter:image"]', 'content')
        || meta('meta[property="twitter:image"]', 'content'));

    const icons = Array.from(document.querySelectorAll(
        'link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="apple-touch-icon-precomposed"], link[rel="mask-icon"], link[rel="shortcut icon"]'
    )).map(l => ({
        href: abs(l.getAttribute('href') || ''),
        sizes: l.getAttribute('sizes') || '',
        rel: l.getAttribute('rel') || '',
    })).filter(i => i.href);

    // logo: first visible img/svg in header/nav near the top-left
    let logo = { kind: 'none', src: '', svg: '', w: 0, h: 0 };
    const logoCands = Array.from(document.querySelectorAll(
        'header img, nav img, [class*="logo" i] img, img[alt*="logo" i], img[class*="logo" i], header svg, nav svg, [class*="logo" i] svg'
    ));
    for (const el of logoCands) {
        const r = el.getBoundingClientRect();
        if (r.width >= 16 && r.height >= 12 && r.top < 240 && r.left < window.innerWidth * 0.6) {
            if (el.tagName === 'IMG') {
                logo = { kind: 'img', src: abs(el.currentSrc || el.src), svg: '', w: Math.round(r.width), h: Math.round(r.height) };
            } else {
                let svg = el.outerHTML || '';
                if (!svg.includes('xmlns')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
                logo = { kind: 'svg', src: '', svg: svg.slice(0, 60000), w: Math.round(r.width), h: Math.round(r.height) };
            }
            break;
        }
    }

    // CTA colors: any button / clickable with a real filled or gradient
    // background (skips plain text links). Class-agnostic so a styled <a> nav
    // button is captured the same as a <button>. Ranked later in python.
    const ctaSel = 'button, a, [role="button"], input[type="submit"], input[type="button"]';
    const ctas = [];
    for (const el of Array.from(document.querySelectorAll(ctaSel))) {
        const s = css(el);
        const r = el.getBoundingClientRect();
        if (r.width < 40 || r.height < 18) continue;
        const bg = s.backgroundColor || '';
        const bgi = s.backgroundImage || '';
        const solid = bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)';
        const grad = bgi.includes('gradient');
        if (!solid && !grad) continue;  // plain text link, not a styled button
        ctas.push({
            bg: s.backgroundColor,
            bgi: s.backgroundImage || '',
            color: s.color,
            border: s.borderTopColor,
            area: Math.round(r.width * r.height),
            top: Math.round(r.top + window.scrollY),
            text: (el.innerText || '').trim().slice(0, 40),
        });
    }

    // first in-content link color (often the accent / link color)
    let linkColor = '';
    const mainLink = document.querySelector('main a, article a, p a, section a');
    if (mainLink) linkColor = css(mainLink).color;

    // raster image inventory, ranked by rendered area
    const imgs = [];
    for (const el of Array.from(document.querySelectorAll('img'))) {
        const r = el.getBoundingClientRect();
        const w = Math.round(r.width), h = Math.round(r.height);
        if (w < 40 || h < 40) continue;
        imgs.push({
            src: abs(el.currentSrc || el.src),
            w, h,
            nw: el.naturalWidth || 0,
            nh: el.naturalHeight || 0,
            area: w * h,
            top: Math.round(r.top + window.scrollY),
            alt: (el.getAttribute('alt') || '').slice(0, 80),
        });
    }

    // large CSS background images (hero blocks often use these)
    const bgs = [];
    const seen = new Set();
    for (const el of Array.from(document.querySelectorAll('div,section,header,a,span'))) {
        const r = el.getBoundingClientRect();
        if (r.width * r.height < 60000) continue;
        const bi = css(el).backgroundImage || '';
        const m = bi.match(/url\((['"]?)(.*?)\1\)/);
        if (m && m[2] && !m[2].startsWith('data:') && !seen.has(m[2])) {
            seen.add(m[2]);
            bgs.push({ src: abs(m[2]), w: Math.round(r.width), h: Math.round(r.height), area: Math.round(r.width * r.height), top: Math.round(r.top + window.scrollY), alt: 'css-background' });
        }
    }

    return {
        body_color: bodyStyle.color,
        body_bg: bodyStyle.backgroundColor,
        body_font: bodyStyle.fontFamily,
        h1_font: (() => { const h = document.querySelector('h1'); return h ? css(h).fontFamily : ''; })(),
        h2_font: (() => { const h = document.querySelector('h2'); return h ? css(h).fontFamily : ''; })(),
        header_bg: (() => { const h = document.querySelector('header') || document.querySelector('nav'); return h ? css(h).backgroundColor : ''; })(),
        theme_color: themeColor,
        og_image: ogImage,
        icons: icons,
        logo: logo,
        ctas: ctas,
        link_color: linkColor,
        images: imgs,
        backgrounds: bgs,
    };
}"""


async def capture_screenshot(url: str, out_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    """Returns (full_page_path, viewport_path, dom_probe_dict).

    full_page_path feeds the color palette analysis; viewport_path is the clean
    above-the-fold shot promoted as a creative asset (a usable product/UI screenshot
    for SaaS briefs), whereas the full-page image is usually too tall to drop into a
    device mockup."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=BROWSER_UA,
                ignore_https_errors=True,
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                await page.goto(url, wait_until="load", timeout=30_000)
            await page.wait_for_timeout(2000)
            try:
                await page.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass

            full = out_path / "homepage.png"
            await page.screenshot(path=str(full), full_page=True)
            header = out_path / "header-crop.png"
            await page.screenshot(path=str(header), clip={"x": 0, "y": 0, "width": 1440, "height": 200})
            viewport = out_path / "viewport.png"
            await page.screenshot(path=str(viewport), full_page=False)

            probe = await page.evaluate(DOM_PROBE_JS)
            return full, viewport, probe
        finally:
            await browser.close()


# --- Color heuristics -------------------------------------------------------

def parse_css_color(s: str) -> tuple[int, int, int] | None:
    if not s:
        return None
    s = s.strip().lower()
    if s in ("transparent", "rgba(0, 0, 0, 0)"):
        return None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            try:
                return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
            except ValueError:
                return None
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?", s)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.1:
            return None  # fully transparent
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def luminance(rgb: tuple[int, int, int]) -> float:
    def chan(c: int) -> float:
        c2 = c / 255.0
        return c2 / 12.92 if c2 <= 0.03928 else ((c2 + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a) + 0.05, luminance(b) + 0.05
    return max(la, lb) / min(la, lb)


def saturation(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255 for c in rgb)
    cmax, cmin = max(r, g, b), min(r, g, b)
    if cmax == 0:
        return 0.0
    return (cmax - cmin) / cmax


def vividness(rgb: tuple[int, int, int]) -> float:
    """How much a color reads as 'the brand color' rather than a depth/shadow
    stop. Saturated AND bright wins, so the lit side of a gradient (swanbase's
    #a855f7 over its #4a276e shadow) is preferred over the dark stop."""
    cmax, cmin = max(rgb), min(rgb)
    light = (cmax + cmin) / 510.0  # (max+min)/2 normalized to 0..1
    return saturation(rgb) * (0.2 + 0.8 * light)


def is_neutralish(rgb: tuple[int, int, int]) -> bool:
    """White, black, or grey: not a brand accent.

    Near-white means ALL channels are high (min high), not just one, so vivid
    colors with a single ~max channel (orange #f97316, yellow) stay accents."""
    return saturation(rgb) < 0.18 or min(rgb) > 235 or max(rgb) < 18


def darken(rgb: tuple[int, int, int], factor: float = 0.7) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


def dominant_palette(image_path: Path, k: int = 8) -> list[tuple[tuple[int, int, int], float]]:
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    img.thumbnail((600, 600))
    quant = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette() or []
    counts = Counter(quant.getdata())
    total = sum(counts.values()) or 1
    out: list[tuple[tuple[int, int, int], float]] = []
    for idx, count in counts.most_common(k):
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        out.append(((r, g, b), count / total))
    return out


def gradient_stops(bgi: str) -> list[tuple[int, int, int]]:
    """Color stops from a CSS gradient string, in declared order."""
    if not bgi or "gradient" not in bgi:
        return []
    stops: list[tuple[int, int, int]] = []
    for m in re.finditer(r"rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}", bgi):
        rgb = parse_css_color(m.group(0))
        if rgb:
            stops.append(rgb)
    return stops


def cta_primary_color(c: dict[str, Any]) -> tuple[tuple[int, int, int] | None, list[tuple[int, int, int]]]:
    """A CTA's brand color: solid background, else first non-neutral gradient stop.
    Returns (primary_rgb_or_None, gradient_stops)."""
    stops = gradient_stops(c.get("bgi", ""))
    rgb = parse_css_color(c.get("bg", ""))
    if rgb and not is_neutralish(rgb):
        return rgb, stops
    # gradient-only button: the brand color is the most vivid (lit) stop, not the
    # first-declared one, which is often the darker shadow side of the gradient.
    color_stops = [s for s in stops if not is_neutralish(s)]
    if color_stops:
        return max(color_stops, key=vividness), stops
    return None, stops


def accent_from_ctas(
    ctas: list[dict[str, Any]],
) -> tuple[list[tuple[tuple[int, int, int], float]], list[tuple[int, int, int]]]:
    """Rank CTA brand colors (solid or gradient) by total rendered area.

    Returns (ranked [(rgb, weight)], stops_of_largest_gradient_cta). Gradient
    buttons are the common case for primary CTAs, so they are first-class."""
    weights: dict[tuple[int, int, int], float] = {}
    best_grad_w = -1.0
    best_grad_stops: list[tuple[int, int, int]] = []
    for c in ctas:
        primary, stops = cta_primary_color(c)
        # the nav/hero CTA is the canonical brand button, so discount buttons by
        # vertical position and strongly boost the persistent nav-zone CTA
        top = float(c.get("top", 0))
        weight = float(c.get("area", 0)) / (1.0 + max(0.0, top) / 1200.0)
        if top < 150:
            weight *= 3.0
        if primary is not None:
            weights[primary] = weights.get(primary, 0.0) + weight
        non_neutral_stops = [s for s in stops if not is_neutralish(s)]
        if len(non_neutral_stops) >= 2 and weight > best_grad_w:
            best_grad_w = weight
            best_grad_stops = non_neutral_stops
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    return ranked, best_grad_stops


# --- firecrawl integration --------------------------------------------------

def fetch_firecrawl(url: str) -> dict[str, Any] | None:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    try:
        req = urllib.request.Request(
            "https://api.firecrawl.dev/v1/scrape",
            data=json.dumps({
                "url": url,
                "formats": ["html", "links"],
                "onlyMainContent": False,
                "waitFor": 1500,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[firecrawl] failed: {e}", file=sys.stderr)
        return None


def font_from_css(family: str) -> str | None:
    if not family:
        return None
    for raw in family.split(","):
        name = raw.strip().strip("'").strip('"')
        if name and name.lower() not in GENERIC_FONT_FALLBACKS:
            return name
    return None


# --- Asset harvesting -------------------------------------------------------

def harvest_assets(
    url: str,
    probe: dict[str, Any],
    assets_dir: Path,
    max_images: int,
    screenshot_src: Path | None = None,
) -> dict[str, Any]:
    """Download the logo, favicon, og:image and the largest on-page images, and
    promote the above-the-fold screenshot as a usable creative asset.

    Returns an assets manifest (paths relative to the project-context dir, i.e.
    the parent of assets_dir)."""
    site_dir = assets_dir / "site"
    project_dir = assets_dir.parent

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(project_dir))
        except ValueError:
            return str(p)

    manifest: dict[str, Any] = {"logo": None, "favicon": None, "og_image": None, "screenshot": None, "images": []}

    # 1. logo
    logo = probe.get("logo") or {}
    if logo.get("kind") == "img" and logo.get("src"):
        rec = download(logo["src"], assets_dir, "logo", referer=url)
        if rec:
            manifest["logo"] = {"path": rel(rec["path"]), "kind": "img", "source": logo["src"][:300],
                                "w": rec.get("w"), "h": rec.get("h")}
    elif logo.get("kind") == "svg" and logo.get("svg"):
        out = assets_dir / "logo.svg"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(logo["svg"], encoding="utf-8")
        manifest["logo"] = {"path": rel(out), "kind": "svg", "source": "inline-svg",
                            "w": logo.get("w"), "h": logo.get("h")}

    # 2. favicon / app icon (best by declared size), also a logo fallback
    icons = probe.get("icons") or []
    def icon_score(i: dict[str, Any]) -> int:
        m = re.search(r"(\d+)", i.get("sizes", "") or "")
        base = int(m.group(1)) if m else 0
        if "apple-touch" in (i.get("rel", "") or ""):
            base += 200  # apple touch icons are big and clean
        return base
    if icons:
        best = sorted(icons, key=icon_score, reverse=True)[0]
        rec = download(best["href"], site_dir, "favicon", referer=url)
        if rec:
            manifest["favicon"] = {"path": rel(rec["path"]), "source": best["href"][:300],
                                   "w": rec.get("w"), "h": rec.get("h")}
            if manifest["logo"] is None:
                # promote a large apple-touch-icon to logo when no real logo found
                if (rec.get("w") or 0) >= 96:
                    manifest["logo"] = {"path": rel(rec["path"]), "kind": "icon-fallback",
                                        "source": best["href"][:300], "w": rec.get("w"), "h": rec.get("h")}

    # 3. og:image share card
    og = probe.get("og_image") or ""
    if og:
        rec = download(og, site_dir, "og-image", referer=url)
        if rec:
            manifest["og_image"] = {"path": rel(rec["path"]), "source": og[:300],
                                    "w": rec.get("w"), "h": rec.get("h")}

    # 4. above-the-fold screenshot, promoted from brand-debug as a creative asset
    #    (a real product/UI shot for SaaS briefs that have no physical packshot)
    if screenshot_src and screenshot_src.exists() and screenshot_src.stat().st_size > 0:
        site_dir.mkdir(parents=True, exist_ok=True)
        dest = site_dir / "screenshot.png"
        try:
            shutil.copyfile(screenshot_src, dest)
            dims = _image_dims(dest)
            manifest["screenshot"] = {
                "path": rel(dest), "source": "playwright:viewport",
                "w": dims[0] if dims else None, "h": dims[1] if dims else None,
            }
        except Exception:
            pass

    # 5. largest on-page product/hero images (img + css backgrounds)
    candidates = list(probe.get("images") or []) + list(probe.get("backgrounds") or [])
    # dedup by source url, prefer the largest rendered instance
    by_src: dict[str, dict[str, Any]] = {}
    logo_src = (logo.get("src") or "")
    for c in candidates:
        src = c.get("src") or ""
        if not src or src == logo_src:
            continue
        prev = by_src.get(src)
        if prev is None or c.get("area", 0) > prev.get("area", 0):
            by_src[src] = c
    ranked = sorted(by_src.values(), key=lambda c: c.get("area", 0), reverse=True)

    grabbed = 0
    for c in ranked:
        if grabbed >= max_images:
            break
        # skip clearly-small or icon-like by rendered edge
        if min(c.get("w", 0), c.get("h", 0)) < MIN_ASSET_EDGE and c.get("alt") != "css-background":
            continue
        rec = download(c["src"], site_dir, f"asset-{grabbed + 1:02d}", referer=url)
        if not rec:
            continue
        # drop downloads that turned out tiny (tracking pixels, sprites)
        if rec.get("w") and rec.get("h") and min(rec["w"], rec["h"]) < 120:
            try:
                rec["path"].unlink()
            except Exception:
                pass
            continue
        manifest["images"].append({
            "path": rel(rec["path"]),
            "source": c["src"][:300],
            "w": rec.get("w") or c.get("w"),
            "h": rec.get("h") or c.get("h"),
            "alt": c.get("alt", ""),
        })
        grabbed += 1

    (site_dir).mkdir(parents=True, exist_ok=True)
    (site_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# --- Heuristic pipeline -----------------------------------------------------

def run_heuristics(
    url: str,
    screenshot_path: Path,
    header_crop_path: Path,
    probe: dict[str, Any],
    firecrawl: dict[str, Any] | None,
) -> Extraction:
    extraction = Extraction(source_url=url)
    palette = dominant_palette(screenshot_path, k=8)

    # bg: dominant color, skip near-neutral if a saturated tone holds >40% (dark themes)
    bg_rgb, bg_share = palette[0]
    is_neutral = max(bg_rgb) - min(bg_rgb) < 12
    if is_neutral and bg_share < 0.55:
        for rgb, share in palette[1:]:
            if share > 0.40 and saturation(rgb) > 0.20:
                bg_rgb, bg_share = rgb, share
                break
    bg_conf = min(0.95, 0.55 + bg_share)
    extraction.tokens["bg"] = Token(rgb_to_hex(bg_rgb), bg_conf, "screenshot:dominant")

    # text_primary: DOM body color first
    body_rgb = parse_css_color(probe.get("body_color", ""))
    if body_rgb:
        extraction.tokens["text_primary"] = Token(rgb_to_hex(body_rgb), 0.88, "css:body.color")
    else:
        cand = max(palette, key=lambda p: contrast_ratio(p[0], bg_rgb))[0]
        extraction.tokens["text_primary"] = Token(rgb_to_hex(cand), 0.55, "screenshot:max-contrast")

    # accent: PRIMARY signal is the CTA button background (solid or gradient).
    cta_ranked, grad_stops = accent_from_ctas(probe.get("ctas") or [])
    theme_rgb = parse_css_color(probe.get("theme_color", ""))
    accent_rgb: tuple[int, int, int] | None = None
    if cta_ranked:
        accent_rgb = cta_ranked[0][0]
        conf = 0.90 if (theme_rgb and contrast_ratio(theme_rgb, accent_rgb) < 1.3) else 0.82
        extraction.tokens["accent"] = Token(rgb_to_hex(accent_rgb), conf, "css:cta-background")
    elif theme_rgb and not is_neutralish(theme_rgb):
        accent_rgb = theme_rgb
        extraction.tokens["accent"] = Token(rgb_to_hex(theme_rgb), 0.70, "meta:theme-color")
    else:
        # fall back to the most saturated palette color with decent contrast
        sat_cands = [
            (rgb, share) for rgb, share in palette
            if rgb != bg_rgb and saturation(rgb) > 0.35 and contrast_ratio(rgb, bg_rgb) >= 1.8
        ]
        if sat_cands:
            accent_rgb = sat_cands[0][0]
            extraction.tokens["accent"] = Token(rgb_to_hex(accent_rgb), min(0.75, 0.45 + sat_cands[0][1] * 2), "screenshot:saturated")
        else:
            link_rgb = parse_css_color(probe.get("link_color", ""))
            if link_rgb and not is_neutralish(link_rgb):
                accent_rgb = link_rgb
                extraction.tokens["accent"] = Token(rgb_to_hex(link_rgb), 0.55, "css:link-color")
            else:
                accent_rgb = palette[1][0] if len(palette) > 1 else (91, 141, 239)
                extraction.tokens["accent"] = Token(rgb_to_hex(accent_rgb), 0.25, "fallback:second-palette")
                extraction.warnings.append("Could not detect a brand accent from CTAs, theme-color, or palette; using a low-confidence guess. Confirm the accent color.")

    # accent_secondary: gradient second stop, else a distinct CTA color, else palette, else darken
    sec_rgb: tuple[int, int, int] | None = None
    if accent_rgb is not None and grad_stops:
        # the most color-distant gradient stop is the natural secondary, even when
        # both stops share a hue (e.g. orange-500 -> orange-600 gradients)
        def dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
            return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5
        far = max((s for s in grad_stops), key=lambda s: dist(s, accent_rgb), default=None)
        if far is not None and dist(far, accent_rgb) > 12:
            sec_rgb = far
            extraction.tokens["accent_secondary"] = Token(rgb_to_hex(far), 0.70, "css:cta-gradient-stop")
    if sec_rgb is None:
        for rgb, _w in cta_ranked[1:]:
            if accent_rgb and contrast_ratio(rgb, accent_rgb) > 1.25:
                sec_rgb = rgb
                extraction.tokens["accent_secondary"] = Token(rgb_to_hex(rgb), 0.60, "css:cta-secondary")
                break
    if sec_rgb is None:
        sat_palette = [rgb for rgb, _ in palette if accent_rgb and rgb != accent_rgb and saturation(rgb) > 0.30 and contrast_ratio(rgb, accent_rgb) > 1.3]
        if sat_palette:
            sec_rgb = sat_palette[0]
            extraction.tokens["accent_secondary"] = Token(rgb_to_hex(sec_rgb), 0.45, "screenshot:second-saturated")
        else:
            sec_rgb = darken(accent_rgb or (91, 141, 239), 0.6)
            extraction.tokens["accent_secondary"] = Token(rgb_to_hex(sec_rgb), 0.40, "derived:darken-accent")

    # fonts: prefer DOM
    body_font_raw = probe.get("body_font", "")
    h1_font_raw = probe.get("h1_font", "") or probe.get("h2_font", "")
    body_font = font_from_css(body_font_raw)
    heading_font = font_from_css(h1_font_raw) or body_font
    if body_font:
        extraction.tokens["font_body"] = Token(body_font_raw, 0.85, "css:body.font-family")
    else:
        extraction.tokens["font_body"] = Token("'Inter', sans-serif", 0.20, "fallback:default")
        extraction.warnings.append("Could not detect a body font from DOM; falling back to Inter.")
    if heading_font:
        src = "css:h1.font-family" if probe.get("h1_font") else "css:body.font-family"
        extraction.tokens["font_heading"] = Token(h1_font_raw or body_font_raw, 0.75, src)
    else:
        extraction.tokens["font_heading"] = Token("'Instrument Serif', Georgia, serif", 0.20, "fallback:default")

    # logo token mirrors the harvested asset (filled in by caller after harvest)
    logo = probe.get("logo") or {}
    if logo.get("kind") == "img" and logo.get("src"):
        extraction.tokens["logo_url"] = Token(logo["src"], 0.80, "dom:img-near-top")
    elif logo.get("kind") == "svg":
        extraction.tokens["logo_url"] = Token("inline-svg", 0.75, "dom:inline-svg-serialized")
    else:
        extraction.tokens["logo_url"] = Token("", 0.0, "not-found")

    # webfont warning
    for token_key in ("font_heading", "font_body"):
        val = extraction.tokens[token_key].value or ""
        if any(name.lower() in str(val).lower() for name in ("inter", "roboto", "open sans", "poppins", "montserrat", "instrument", "manrope", "cabinet")):
            extraction.warnings.append(f"{token_key} appears to be a webfont; the render machine needs internet to load it.")
            break

    if firecrawl is None:
        extraction.warnings.append("FIRECRAWL_API_KEY not set; ran in screenshot + DOM mode (no firecrawl HTML cross-check).")

    return extraction


# --- CLI --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Extract brand tokens and harvest brand assets from a URL.")
    parser.add_argument("--url", required=True, help="Public URL of the brand homepage")
    parser.add_argument("--out", required=True, help="Output directory (creates assets/ and brand-debug/ inside)")
    parser.add_argument("--no-firecrawl", action="store_true", help="Skip firecrawl even if key is set")
    parser.add_argument("--max-images", type=int, default=6, help="Max on-page product/hero images to harvest (default 6)")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    debug_dir = out_dir / "brand-debug"
    assets_dir = out_dir / "assets"
    debug_dir.mkdir(parents=True, exist_ok=True)

    if not robots_allows(args.url):
        print(f"[robots] {args.url} disallows scraping. Aborting.", file=sys.stderr)
        return 2

    # 1. screenshot + rich DOM probe
    try:
        full, viewport, probe = asyncio.run(capture_screenshot(args.url, debug_dir))
    except Exception as e:
        print(f"[playwright] {e}", file=sys.stderr)
        return 3

    # 2. firecrawl (optional cross-check / archive)
    firecrawl = None if args.no_firecrawl else fetch_firecrawl(args.url)
    if firecrawl is not None:
        (debug_dir / "firecrawl.json").write_text(json.dumps(firecrawl, indent=2))

    # 3. heuristics
    extraction = run_heuristics(
        args.url,
        screenshot_path=full,
        header_crop_path=debug_dir / "header-crop.png",
        probe=probe,
        firecrawl=firecrawl,
    )

    # 4. harvest real assets to disk
    try:
        manifest = harvest_assets(args.url, probe, assets_dir, max_images=max(0, args.max_images), screenshot_src=viewport)
    except Exception as e:
        print(f"[harvest] non-fatal: {e}", file=sys.stderr)
        manifest = {"logo": None, "favicon": None, "og_image": None, "images": []}
    extraction.assets = manifest

    # reconcile logo token with the harvested file
    if manifest.get("logo"):
        extraction.tokens["logo_url"] = Token(
            manifest["logo"].get("source", "") or manifest["logo"]["path"],
            0.85 if manifest["logo"]["kind"] in ("img", "svg") else 0.55,
            f"asset:{manifest['logo']['kind']}",
        )
    else:
        extraction.warnings.append("No logo asset captured. Provide a logo path/URL in chat at the validation step.")

    n_imgs = len(manifest.get("images") or [])
    if n_imgs == 0:
        extraction.warnings.append("No on-page product/hero images were large enough to harvest. The creative agent will rely on the og:image, logo, and homepage screenshot instead.")

    # 5. write candidate
    candidate_path = out_dir / "brand-candidate.json"
    candidate_path.write_text(json.dumps(extraction.as_dict(), indent=2))
    print(f"wrote {candidate_path}")
    print(f"debug artifacts in {debug_dir}")
    print(f"assets in {assets_dir}")

    # 6. console summary
    print("\nExtracted tokens:")
    for name, tok in extraction.tokens.items():
        print(f"  {name:<18} {str(tok.value):<46} conf={tok.confidence:.2f}  ({tok.source})")
    print("\nHarvested assets:")
    logo = manifest.get("logo")
    print(f"  logo       {logo['path'] if logo else '(none)'}")
    print(f"  favicon    {manifest['favicon']['path'] if manifest.get('favicon') else '(none)'}")
    print(f"  og_image   {manifest['og_image']['path'] if manifest.get('og_image') else '(none)'}")
    print(f"  screenshot {manifest['screenshot']['path'] if manifest.get('screenshot') else '(none)'}")
    print(f"  images     {n_imgs} harvested")
    for im in (manifest.get("images") or []):
        print(f"            {im['path']}  ({im.get('w')}x{im.get('h')})  {im.get('alt','')[:40]}")
    if extraction.warnings:
        print("\nWarnings:")
        for w in extraction.warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
