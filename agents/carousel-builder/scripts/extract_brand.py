#!/usr/bin/env python3
"""extract_brand.py — Extract brand tokens from a public URL.

Combines two signals:
  1. DOM/CSS via firecrawl (when FIRECRAWL_API_KEY is set).
  2. Visual via Playwright headless screenshot + k-means heuristics.

Writes brand-candidate.json with confidence scores and a brand-debug/
folder for traceability. The agent's extract-brand skill then runs a
validation loop with the user before promoting brand-candidate.json
to brand.json.

Usage:
    python extract_brand.py --url https://swanbase.co --out ./out/
    python extract_brand.py --url https://example.com --out ./out/ --no-firecrawl

Hard rules (carried by the agent):
  - heuristic, never authoritative: every token publishes confidence
  - respects robots.txt: aborts if homepage is disallowed
  - portable: only stdlib + Playwright + Pillow + (optional) firecrawl-py
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import re
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


# ─── Data model ─────────────────────────────────────────────────────────────

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

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "extracted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tokens": {k: t.as_dict() for k, t in self.tokens.items()},
            "warnings": self.warnings,
        }


# ─── robots.txt check ───────────────────────────────────────────────────────

def robots_allows(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": "carousel-builder/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return True  # no robots = allowed
    ua_blocks = re.split(r"(?im)^user-agent:\s*", body)
    for block in ua_blocks:
        head, *rest = block.split("\n", 1)
        if head.strip() in ("*", "carousel-builder"):
            disallow_lines = [ln for ln in (rest[0] if rest else "").splitlines() if ln.lower().startswith("disallow:")]
            for ln in disallow_lines:
                rule = ln.split(":", 1)[1].strip()
                if rule == "/":
                    return False
    return True


# ─── Screenshot via Playwright ──────────────────────────────────────────────

async def capture_screenshot(url: str, out_path: Path) -> tuple[Path, dict[str, str]]:
    """Returns (full_page_path, computed_styles_dict).

    computed_styles is a small dict pulled directly from the live DOM:
      - body_color, body_bg, body_font, h1_font, h2_font, header_bg
      - logo_src (best-effort)
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
            except Exception:
                # SPAs sometimes never reach networkidle; fall back to load + grace
                await page.goto(url, wait_until="load", timeout=30_000)
            await page.wait_for_timeout(2000)
            try:
                await page.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass

            # full-page screenshot
            full = out_path / "homepage.png"
            await page.screenshot(path=str(full), full_page=True)

            # header crop (top 200px of viewport-sized capture)
            header = out_path / "header-crop.png"
            await page.screenshot(path=str(header), clip={"x": 0, "y": 0, "width": 1440, "height": 200})

            # pull computed styles from DOM
            styles = await page.evaluate(
                """() => {
                    const bodyStyle = window.getComputedStyle(document.body);
                    const h1 = document.querySelector('h1');
                    const h2 = document.querySelector('h2');
                    const header = document.querySelector('header') || document.querySelector('nav');
                    const headerStyle = header ? window.getComputedStyle(header) : null;
                    const logoCandidates = Array.from(document.querySelectorAll(
                        'img[alt*="logo" i], img[class*="logo" i], header img, nav img, header svg, nav svg'
                    ));
                    let logo = null;
                    for (const el of logoCandidates) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width >= 16 && rect.height >= 16 && rect.top < 200) {
                            if (el.tagName === 'IMG') {
                                logo = el.currentSrc || el.src;
                            } else {
                                // serialize inline SVG
                                logo = 'inline-svg';
                            }
                            break;
                        }
                    }
                    return {
                        body_color: bodyStyle.color,
                        body_bg: bodyStyle.backgroundColor,
                        body_font: bodyStyle.fontFamily,
                        h1_font: h1 ? window.getComputedStyle(h1).fontFamily : '',
                        h2_font: h2 ? window.getComputedStyle(h2).fontFamily : '',
                        header_bg: headerStyle ? headerStyle.backgroundColor : '',
                        logo_src: logo || '',
                    };
                }"""
            )
            return full, styles
        finally:
            await browser.close()


# ─── Color heuristics (k-means lite via PIL quantize) ───────────────────────

def parse_css_color(s: str) -> tuple[int, int, int] | None:
    if not s:
        return None
    s = s.strip().lower()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            try:
                return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
            except ValueError:
                return None
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", s)
    if m:
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


def darken(rgb: tuple[int, int, int], factor: float = 0.7) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


def dominant_palette(image_path: Path, k: int = 8) -> list[tuple[tuple[int, int, int], float]]:
    """Returns (rgb, share) pairs sorted by share desc. Uses PIL median-cut quantize."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    # downsample for speed: max 600px on long edge
    img.thumbnail((600, 600))
    quant = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette() or []
    counts = Counter(quant.getdata())
    total = sum(counts.values())
    out: list[tuple[tuple[int, int, int], float]] = []
    for idx, count in counts.most_common(k):
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        out.append(((r, g, b), count / total))
    return out


# ─── firecrawl integration ──────────────────────────────────────────────────

def fetch_firecrawl(url: str) -> dict[str, Any] | None:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    try:
        import urllib.request as _u

        req = _u.Request(
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
        with _u.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[firecrawl] failed: {e}", file=sys.stderr)
        return None


def font_from_css(family: str) -> str | None:
    """Returns the first non-generic family in a font-family stack."""
    if not family:
        return None
    for raw in family.split(","):
        name = raw.strip().strip("'").strip('"')
        if name and name.lower() not in GENERIC_FONT_FALLBACKS:
            return name
    return None


# ─── Heuristic pipeline ─────────────────────────────────────────────────────

def run_heuristics(
    url: str,
    screenshot_path: Path,
    header_crop_path: Path,
    dom_styles: dict[str, str],
    firecrawl: dict[str, Any] | None,
) -> Extraction:
    extraction = Extraction(source_url=url)
    palette = dominant_palette(screenshot_path, k=8)
    header_palette = dominant_palette(header_crop_path, k=5)

    # bg: dominant color of full page, but skip near-pure-white if a saturated tone holds >40% (dark themes)
    bg_rgb, bg_share = palette[0]
    is_neutral = max(bg_rgb) - min(bg_rgb) < 12
    if is_neutral and bg_share < 0.55:
        # try to find a more characteristic tone
        for rgb, share in palette[1:]:
            if share > 0.40 and saturation(rgb) > 0.20:
                bg_rgb, bg_share = rgb, share
                break
    bg_conf = min(0.95, 0.55 + bg_share)
    extraction.tokens["bg"] = Token(rgb_to_hex(bg_rgb), bg_conf, "screenshot:dominant")

    # text_primary: prefer DOM body color, else max-contrast vs bg
    body_rgb = parse_css_color(dom_styles.get("body_color", ""))
    if body_rgb:
        extraction.tokens["text_primary"] = Token(rgb_to_hex(body_rgb), 0.88, "css:body.color")
    else:
        # pick palette color with highest contrast vs bg
        cand = max(palette, key=lambda p: contrast_ratio(p[0], bg_rgb))[0]
        extraction.tokens["text_primary"] = Token(rgb_to_hex(cand), 0.55, "screenshot:max-contrast")

    # accent: most saturated color in palette that's not bg and has decent contrast
    accent_candidates = [
        (rgb, share)
        for rgb, share in palette
        if rgb != bg_rgb and saturation(rgb) > 0.35 and contrast_ratio(rgb, bg_rgb) >= 1.8
    ]
    if accent_candidates:
        accent_rgb, accent_share = accent_candidates[0]
        extraction.tokens["accent"] = Token(rgb_to_hex(accent_rgb), min(0.85, 0.50 + accent_share * 2), "screenshot:cta-detection")
    else:
        # fallback: take the second palette color and warn
        accent_rgb = palette[1][0] if len(palette) > 1 else (91, 141, 239)
        extraction.tokens["accent"] = Token(rgb_to_hex(accent_rgb), 0.30, "fallback:second-palette")
        extraction.warnings.append("Could not detect a saturated accent color; using second palette entry as a guess.")

    # accent_secondary: second saturated color, else darken accent
    secondary_candidates = [c for c in accent_candidates[1:]]
    if secondary_candidates:
        sec_rgb, sec_share = secondary_candidates[0]
        extraction.tokens["accent_secondary"] = Token(rgb_to_hex(sec_rgb), 0.55, "screenshot:second-saturated")
    else:
        sec_rgb = darken(accent_rgb, 0.6)
        extraction.tokens["accent_secondary"] = Token(rgb_to_hex(sec_rgb), 0.40, "derived:darken-accent")

    # fonts: prefer DOM
    body_font_raw = dom_styles.get("body_font", "")
    h1_font_raw = dom_styles.get("h1_font", "") or dom_styles.get("h2_font", "")
    body_font = font_from_css(body_font_raw)
    heading_font = font_from_css(h1_font_raw) or body_font
    if body_font:
        extraction.tokens["font_body"] = Token(body_font_raw, 0.85, "css:body.font-family")
    else:
        extraction.tokens["font_body"] = Token("'Inter', sans-serif", 0.20, "fallback:default")
        extraction.warnings.append("Could not detect a body font from DOM; falling back to Inter.")
    if heading_font:
        src = "css:h1.font-family" if dom_styles.get("h1_font") else "css:body.font-family"
        extraction.tokens["font_heading"] = Token(h1_font_raw or body_font_raw, 0.75, src)
    else:
        extraction.tokens["font_heading"] = Token("'Instrument Serif', Georgia, serif", 0.20, "fallback:default")

    # logo: prefer DOM logo_src; resolve relative URLs
    logo_src = dom_styles.get("logo_src", "")
    if logo_src and logo_src != "inline-svg":
        if logo_src.startswith("//"):
            logo_src = "https:" + logo_src
        elif logo_src.startswith("/"):
            parsed = urllib.parse.urlparse(url)
            logo_src = f"{parsed.scheme}://{parsed.netloc}{logo_src}"
        elif not logo_src.startswith("http"):
            logo_src = urllib.parse.urljoin(url, logo_src)
        extraction.tokens["logo_url"] = Token(logo_src, 0.75, "dom:img-or-svg-near-top")
    elif logo_src == "inline-svg":
        extraction.warnings.append("Logo found as inline SVG; cannot capture as a file from DOM. User must provide a path manually.")
        extraction.tokens["logo_url"] = Token("", 0.20, "dom:inline-svg-detected")
    else:
        extraction.tokens["logo_url"] = Token("", 0.0, "not-found")
        extraction.warnings.append("No logo detected near top of page. User can supply one manually in chat.")

    # webfont warning
    for token_key in ("font_heading", "font_body"):
        val = extraction.tokens[token_key].value or ""
        if any(name.lower() in str(val).lower() for name in ("inter", "roboto", "open sans", "poppins", "montserrat", "instrument")):
            extraction.warnings.append(f"{token_key} appears to be a Google Fonts family; render machine needs internet to load it.")
            break

    if firecrawl is None:
        extraction.warnings.append("FIRECRAWL_API_KEY not set; ran in screenshot-only mode. DOM-confidence tokens may be lower.")

    return extraction


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Extract brand tokens from a URL.")
    parser.add_argument("--url", required=True, help="Public URL of the brand homepage")
    parser.add_argument("--out", required=True, help="Output directory (will create brand-debug/ inside)")
    parser.add_argument("--no-firecrawl", action="store_true", help="Skip firecrawl even if key is set")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    debug_dir = out_dir / "brand-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    if not robots_allows(args.url):
        print(f"[robots] {args.url} disallows scraping. Aborting.", file=sys.stderr)
        return 2

    # 1. screenshot + DOM
    try:
        full, dom_styles = asyncio.run(capture_screenshot(args.url, debug_dir))
    except Exception as e:
        print(f"[playwright] {e}", file=sys.stderr)
        return 3

    # 2. firecrawl (optional)
    firecrawl = None if args.no_firecrawl else fetch_firecrawl(args.url)
    if firecrawl is not None:
        (debug_dir / "firecrawl.json").write_text(json.dumps(firecrawl, indent=2))

    # 3. heuristics
    extraction = run_heuristics(
        args.url,
        screenshot_path=full,
        header_crop_path=debug_dir / "header-crop.png",
        dom_styles=dom_styles,
        firecrawl=firecrawl,
    )

    # 4. write candidate
    candidate_path = out_dir / "brand-candidate.json"
    candidate_path.write_text(json.dumps(extraction.as_dict(), indent=2))
    print(f"wrote {candidate_path}")
    print(f"debug artifacts in {debug_dir}")

    # 5. console summary
    print("\nExtracted tokens:")
    for name, tok in extraction.tokens.items():
        print(f"  {name:<18} {str(tok.value):<45} conf={tok.confidence:.2f}  ({tok.source})")
    if extraction.warnings:
        print("\nWarnings:")
        for w in extraction.warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
