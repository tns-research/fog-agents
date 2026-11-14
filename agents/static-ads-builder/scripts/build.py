#!/usr/bin/env python3
"""build.py: ads.json + brand.json -> html/index.html (one section per ad and format)

Deterministic: the same inputs give the same HTML. The model writes ads.json
and never touches the HTML; every fix goes through the spec, the brand file
or the style CSS in templates/.

Usage:
  python3 scripts/build.py <ads.json> [--out DIR] [--brand brand.json] [--only id1,id2]

Outputs (default DIR = <ads.json dir>/html):
  index.html          <section class="ad"> per ad x format, exact canvas size
                      (1080x1080, 1080x1350, 1080x1920), fonts, CSS, fit.js inline
  assets/             media copied from the spec, downscaled past 2400 px
  expected.json       per section: the words the render must show (dom, media,
                      logo), the source of truth for qa.py and proofread.py
  build-report.json   spec issues (schema, claims, numbers, style needs,
                      media, Meta fields, copy gate) and the derived theme

What it guarantees by construction:
  - every visible word comes from ads.json (or the brand's logo_text);
  - real media are shown whole (object-fit contain) unless the spec says
    cover for a plate;
  - text sits inside the safe zone of its format (Meta Reels zones on 9:16);
  - colour roles per surface are derived from brand.json to hold WCAG
    contrast (4.5:1 text, 3:1 graphics); qa.py measures the result.

Exit code: 0 when the spec has no error, 1 when it has errors (the HTML is
still written so qa.py can show them), 2 when ads.json cannot be read.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adspec  # noqa: E402
from adspec import Issue  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = AGENT_DIR / "templates"
SCRIPTS = AGENT_DIR / "scripts"
REPO_ROOT = AGENT_DIR.parent.parent
WRITING_GATE = REPO_ROOT / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"
BRAND_SCHEMA = REPO_ROOT / "shared" / "schemas" / "brand.schema.json"
VALIDATE_JSON = REPO_ROOT / "shared" / "scripts" / "validate_json.py"

NBSP = " "
NNBSP = " "

# Fit ranges (min px, max px, max lines) per text role and canvas group.
# "sq" = 1:1, "tall" = 4:5, "story" = 9:16 (derived from "sq" by STORY_GROW:
# the Reels text zone is near-square too, but on 9:16 the media and the
# decorative panels move out of it, so the text gets larger maxima; the
# headline keeps its line budget so a list under it is not starved). Minimums hold the feed-legibility floor of the shared render
# review (body 28 px on a 1080 px canvas).
FIT_DEFAULT: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "head": {"sq": (52, 100, 4), "tall": (56, 116, 5)},
    "sub": {"sq": (30, 40, 3), "tall": (30, 44, 4)},
    "item": {"sq": (28, 44, 2), "tall": (30, 48, 2)},
    "quote": {"sq": (32, 88, 6), "tall": (34, 100, 7)},
    "cta": {"sq": (28, 34, 1), "tall": (28, 36, 1)},
    "fig": {"sq": (64, 150, 1), "tall": (72, 170, 1)},
    "comment": {"sq": (28, 60, 4), "tall": (30, 68, 5)},
}
FIT_STYLE: Dict[str, Dict[str, Dict[str, Tuple[int, int, int]]]] = {
    "bold-statement": {"head": {"sq": (64, 148, 5), "tall": (72, 168, 6)}},
    "meme-static": {"head": {"sq": (48, 92, 6), "tall": (52, 104, 7)}},
    "ugc-text-overlay": {"head": {"sq": (40, 64, 3), "tall": (44, 72, 3)}, "sub": {"sq": (28, 36, 2), "tall": (30, 38, 2)}},
    "myth-vs-fact": {"item": {"sq": (32, 84, 3), "tall": (34, 96, 4)}, "head": {"sq": (44, 100, 2), "tall": (48, 116, 3)}},
    "mini-landing-page": {"head": {"sq": (44, 76, 3), "tall": (52, 92, 3)}, "item": {"sq": (28, 40, 2), "tall": (30, 48, 2)}},
    "us-vs-them-comparison": {"head": {"sq": (44, 84, 3), "tall": (52, 100, 3)}, "item": {"sq": (28, 44, 3), "tall": (30, 52, 3)}},
    "feature-callout-arrows": {"head": {"sq": (44, 80, 2), "tall": (48, 96, 3)}, "item": {"sq": (28, 36, 3), "tall": (28, 40, 3)}},
    "social-proof-card": {"head": {"sq": (40, 64, 2), "tall": (44, 72, 3)}},
    "testimonial-screenshot": {"head": {"sq": (40, 72, 2), "tall": (44, 84, 3)}, "quote": {"sq": (30, 64, 6), "tall": (32, 72, 7)}},
    "reply-to-comment": {"head": {"sq": (40, 72, 2), "tall": (44, 88, 3)}},
    "flowchart-decision": {"head": {"sq": (40, 68, 3), "tall": (44, 80, 3)}, "item": {"sq": (28, 48, 4), "tall": (28, 56, 4)}},
    "cost-reframe-card": {"head": {"sq": (44, 80, 3), "tall": (48, 96, 3)}},
    "three-benefits-card": {"head": {"sq": (48, 112, 3), "tall": (56, 128, 3)}, "item": {"sq": (30, 60, 2), "tall": (32, 68, 2)}},
    "crossed-out-problems": {"item": {"sq": (30, 52, 2), "tall": (32, 60, 2)}},
    "benefit-timeline": {"item": {"sq": (30, 52, 2), "tall": (32, 64, 2)}, "head": {"sq": (52, 110, 3), "tall": (56, 128, 3)}},
    "before-after-asymmetric": {"item": {"sq": (28, 48, 3), "tall": (30, 56, 3)}},
    "ingredient-origin-strip": {"sub": {"sq": (30, 44, 3), "tall": (30, 48, 3)}},
}
# 9:16: (factor on the max size, extra lines) per role, applied to "sq".
STORY_GROW: Dict[str, Tuple[float, int]] = {
    "head": (1.26, 0), "quote": (1.2, 1), "fig": (1.12, 0), "comment": (1.15, 1),
    "sub": (1.15, 1), "item": (1.2, 0), "cta": (1.1, 0),
}
STORY_ITEM_FLOOR = 1.2
# 9:16 ranges set by hand where the derived ones leave the text zone half
# empty (short copy in a layout whose visual cannot leave the text zone).
FIT_STORY: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "feature-callout-arrows": {"head": (48, 132, 3), "item": (28, 46, 3)},
}
ORDER = {"head": 1, "quote": 2, "fig": 2, "sub": 3, "item": 4, "comment": 4, "cta": 5}

ICONS = {
    "check": '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12.5l5 5L20 6.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "x": '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>',
    "arrow": '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "star": '<svg class="star" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z" fill="currentColor"/></svg>',
    "dot": '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="6" fill="currentColor"/></svg>',
}


# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------

RGB = Tuple[float, float, float]


def parse_color(c: Any) -> Optional[RGB]:
    if not isinstance(c, str):
        return None
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def lum(rgb: RGB) -> float:
    def ch(v: float) -> float:
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def contrast(a: RGB, b: RGB) -> float:
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))  # type: ignore


def holding(c: RGB, bg: RGB, need: float, toward: RGB) -> RGB:
    """c itself when it holds `need` against bg, else c moved toward `toward`
    by the smallest step that does."""
    if contrast(c, bg) >= need:
        return c
    for k in range(1, 41):
        m = mix(c, toward, k / 40)
        if contrast(m, bg) >= need:
            return m
    return toward


WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)


def surface_roles(paper: RGB, ink: RGB, accents: List[RGB], card: Optional[RGB] = None, ink2: Optional[RGB] = None,
                  muted: Optional[RGB] = None) -> Dict[str, str]:
    """Colour roles for one surface. Text roles hold 4.5:1 on the paper (and
    on the card), graphics 3:1, the solid accent (buttons, fact panels) holds
    4.5:1 with its own text colour."""
    dark = lum(paper) < 0.18
    card = card or mix(paper, ink, 0.07 if dark else 0.05)
    if contrast(ink, card) < 4.5:
        card = mix(paper, ink, 0.04)
    ink2 = holding(ink2 or mix(ink, paper, 0.22), card, 4.5, ink)
    muted = holding(muted or mix(ink, paper, 0.36), card, 4.5, ink)
    acc = accents or [ink]
    acc_text = next((c for c in acc if contrast(c, paper) >= 4.5 and contrast(c, card) >= 4.5), None)
    if acc_text is None:
        acc_text = holding(acc[0], card, 4.5, ink)
    acc_mark = next((c for c in acc if contrast(c, paper) >= 3.0), holding(acc[0], paper, 3.0, ink))
    solid, on_solid = None, None
    for c in acc:
        best = max((ink, paper, WHITE, BLACK), key=lambda t: contrast(t, c))
        if contrast(best, c) >= 4.5 and contrast(c, paper) >= 1.25:
            solid, on_solid = c, best
            break
    if solid is None:
        base = acc[0]
        target = BLACK if lum(base) > 0.3 else WHITE
        away = BLACK if target == WHITE else WHITE
        solid = holding(base, target, 4.5, away)
        on_solid = target
    # Highlight behind ink text: light enough to keep 7:1 with the ink.
    hl = next((c for c in acc if contrast(c, ink) >= 7.0), None)
    if hl is None:
        hl = holding(mix(acc[0], paper if not dark else WHITE, 0.5), ink, 7.0, paper if not dark else WHITE)
    return {"paper": to_hex(paper), "ink": to_hex(ink), "ink-2": to_hex(ink2), "muted": to_hex(muted),
            "rule": to_hex(mix(paper, ink, 0.18)), "card": to_hex(card), "accent-text": to_hex(acc_text),
            "accent-mark": to_hex(acc_mark), "solid": to_hex(solid), "on-solid": to_hex(on_solid),
            "hl": to_hex(hl), "on-hl": to_hex(ink if contrast(ink, hl) >= contrast(paper, hl) else paper)}


def theme(brand: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    bg = brand.get("bg") or WHITE
    text = brand.get("text") or (WHITE if lum(bg) < 0.18 else (17, 17, 17))
    if contrast(text, bg) < 7:
        text = max((WHITE, (17, 17, 17)), key=lambda t: contrast(t, bg))
    accents = [c for c in (brand.get("accent"), brand.get("accent_2"), *brand.get("palette", [])) if c]
    out = {"brand": surface_roles(bg, text, accents, brand.get("surface"), brand.get("text_2"), brand.get("muted"))}
    dark_brand = lum(bg) < 0.18
    light_paper = brand.get("light_paper") or (mix(WHITE, accents[0], 0.07) if accents else (247, 245, 240))
    light_ink = bg if dark_brand else text
    if contrast(light_ink, light_paper) < 7:
        light_ink = (17, 17, 17)
    out["light"] = surface_roles(light_paper, light_ink, accents)
    a_roles = surface_roles(bg, text, accents)
    apaper, aink = parse_color(a_roles["solid"]), parse_color(a_roles["on-solid"])
    out["accent"] = surface_roles(apaper, aink, [c for c in ((255, 255, 255), light_paper, *accents) if c])
    return out


# --------------------------------------------------------------------------
# Brand
# --------------------------------------------------------------------------

def brand_resolver(brand_file: Path) -> Callable[[Optional[str]], Optional[Path]]:
    def resolve(p: Optional[str]) -> Optional[Path]:
        if not p:
            return None
        cand = Path(p)
        if cand.is_absolute():
            return cand if cand.exists() else None
        for base in (brand_file.parent, brand_file.parent.parent):
            q = (base / p).resolve()
            if q.exists():
                return q
        return None
    return resolve


def load_brand(path: Optional[Path], issues: List[Issue]) -> Dict[str, Any]:
    """brand.json V2 (shared/schemas/brand.schema.json), V1 mapped on load.
    Optional extras in extensions.static_ads_builder: light_paper (hex),
    palette (extra colours offered to the accent picker)."""
    if not path or not path.exists():
        issues.append(Issue("warning", "brand-missing", str(path or "brand.json"),
                            "No brand.json: neutral theme, brand name typeset as the logo."))
        return {}
    try:
        raw = adspec.load_json(path)
    except Exception as e:  # noqa: BLE001
        issues.append(Issue("warning", "brand-malformed", str(path), f"brand.json does not parse ({e}); neutral theme."))
        return {}
    resolve = brand_resolver(path)
    v2 = raw.get("schema_version") == "2.0"
    out: Dict[str, Any] = {"file": str(path), "version": "2.0" if v2 else "1", "logos": {"on_dark": {}, "on_light": {}}, "font_files": []}
    if v2 and VALIDATE_JSON.exists() and BRAND_SCHEMA.exists():
        r = subprocess.run([sys.executable, str(VALIDATE_JSON), str(BRAND_SCHEMA), str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            for line in (r.stdout + r.stderr).strip().splitlines()[:6]:
                issues.append(Issue("warning", "brand-schema", str(path), line.strip()))
    ext = ((raw.get("extensions") or {}).get("static_ads_builder") or {}) if v2 else {}
    pal = ext.get("palette") if isinstance(ext.get("palette"), dict) else {}
    out["palette"] = [c for c in (parse_color(v) for v in pal.values()) if c]
    out["light_paper"] = parse_color(ext.get("light_paper"))
    if v2:
        col = raw.get("colors") or {}
        out.update({"name": raw.get("logo_text") or raw.get("name"), "bg": parse_color(col.get("bg")),
                    "text": parse_color(col.get("text")), "text_2": parse_color(col.get("text_secondary")),
                    "muted": parse_color(col.get("text_muted")), "surface": parse_color(col.get("surface")),
                    "accent": parse_color(col.get("accent")), "accent_2": parse_color(col.get("accent_secondary")),
                    "radius": raw.get("radius")})
        fonts = raw.get("fonts") or {}
        for role in ("display", "body"):
            f = fonts.get(role) or {}
            if f.get("family"):
                out[f"font_{role}"] = f["family"]
                out[f"font_{role}_fallback"] = f.get("fallback")
                ws = [w for w in f.get("weights") or [] if isinstance(w, int)]
                if ws:
                    out[f"font_{role}_weight"] = max(ws)
            for fl in f.get("files") or []:
                p = resolve(fl.get("path"))
                if p:
                    out["font_files"].append({"family": f.get("family"), "path": p, "weight": fl.get("weight", 400), "style": fl.get("style", "normal")})
        out["fonts_url"] = fonts.get("fonts_url")
        for variant in ("on_dark", "on_light"):
            v = (raw.get("logos") or {}).get(variant) or {}
            ink = next((parse_color((v.get(k) or {}).get("ink")) for k in ("wordmark", "mark") if parse_color((v.get(k) or {}).get("ink"))), None)
            if ink:
                out.setdefault("logo_inks", {})[variant] = ink
            for kind in ("wordmark", "mark"):
                if (v.get(kind) or {}).get("path"):
                    p = resolve(v[kind]["path"])
                    if p:
                        out["logos"][variant][kind] = p
                    else:
                        issues.append(Issue("warning", "brand-asset-missing", f"brand.logos.{variant}.{kind}", f"{v[kind]['path']} not found."))
        audit = raw.get("logo_audit") or {}
        for chk in audit.get("checks") or []:
            if chk.get("status") == "fail":
                out["logos"].get(chk.get("variant"), {}).pop(chk.get("kind"), None)
                issues.append(Issue("warning", "logo-audit-fail", f"brand.logo_audit {chk.get('variant')}.{chk.get('kind')}", "Failed the brand logo audit: not used."))
    else:
        bg = parse_color(raw.get("bg"))
        out.update({"name": raw.get("logo_text") or raw.get("name"), "bg": bg, "text": parse_color(raw.get("text_primary")),
                    "accent": parse_color(raw.get("accent")), "accent_2": parse_color(raw.get("accent_secondary")),
                    "font_display": (raw.get("font_heading") or "").split(",")[0].strip("'\" ") or None,
                    "font_body": (raw.get("font_body") or "").split(",")[0].strip("'\" ") or None,
                    "fonts_url": raw.get("fonts_url")})
        logo = resolve(raw.get("logo_path") or (raw.get("assets") or {}).get("logo_path"))
        if logo:
            out["logos"]["on_dark" if bg and lum(bg) < 0.18 else "on_light"]["wordmark"] = logo
    return out


def inline_svg(path: Path, cls: str) -> Optional[str]:
    """Inline a logo SVG; a one-colour logo switches to currentColor so the
    surface sets it to its ink."""
    try:
        svg = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    svg = re.sub(r"<\?xml[^>]*\?>|<!--.*?-->|<!DOCTYPE[^>]*>", "", svg, flags=re.S).strip()
    fills = set(re.findall(r'fill="(#[0-9a-fA-F]{3,8}|white|black|[a-z]+)"', svg)) - {"none", "currentColor"}
    fills |= set(re.findall(r"fill:\s*(#[0-9a-fA-F]{3,8})", svg))
    if len(fills) <= 1:
        svg = re.sub(r'fill="(?!none)[^"]*"', 'fill="currentColor"', svg)
        svg = re.sub(r"fill:\s*#[0-9a-fA-F]{3,8}", "fill:currentColor", svg)
        if not fills:
            svg = svg.replace("<svg", '<svg fill="currentColor"', 1)
    m = re.search(r"<svg\b[^>]*>", svg)
    if not m:
        return None
    head = m.group(0)
    new = re.sub(r'\s(width|height)="[^"]*"', "", head).replace("<svg", f'<svg class="{cls}" aria-hidden="true" focusable="false"', 1)
    return svg.replace(head, new, 1)


# Logo sizing on a 1080 px canvas. The mark never goes under LOGO_MARK_MIN
# px and a wordmark never under LOGO_WORD_MIN px of height: about 22 and
# 14 CSS px in a 375 px phone feed column, the smallest a brand still reads at
# a glance. The lockup aims at LOGO_WIDTH of the canvas width (a signature,
# not a giant logo); the clear space around it is LOGO_CLEAR of its height.
LOGO_MARK_MIN, LOGO_MARK_MAX = 64, 88
LOGO_WORD_MIN, LOGO_WORD_MAX = 40, 60
LOGO_WORD_IN_LOCKUP = 0.56
LOGO_GAP = 0.24
LOGO_WIDTH = 0.24
LOGO_CLEAR = 0.5


def svg_aspect(svg: str) -> float:
    m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)"', svg)
    if m and float(m.group(2)) > 0:
        return float(m.group(1)) / float(m.group(2))
    return 1.0


def logo_size(kind: str, mark_ar: float, word_ar: float, canvas_w: int) -> Dict[str, int]:
    """Heights in px: h (mark, or wordmark alone), word (wordmark in a lockup),
    gap, clear (clear space), min (the legibility floor qa checks)."""
    target = canvas_w * LOGO_WIDTH
    k = canvas_w / 1080
    if kind == "lockup":
        lo = max(LOGO_MARK_MIN, LOGO_WORD_MIN / LOGO_WORD_IN_LOCKUP) * k
        h = target / (mark_ar + LOGO_GAP + LOGO_WORD_IN_LOCKUP * word_ar)
        h = min(max(h, lo), LOGO_MARK_MAX * k)
        word = h * LOGO_WORD_IN_LOCKUP
        return {"h": round(h), "word": round(word), "gap": round(h * LOGO_GAP), "clear": round(h * LOGO_CLEAR), "min": round(LOGO_WORD_MIN * k)}
    if kind == "wordmark":
        h = min(max(target / max(word_ar, 0.1), LOGO_WORD_MIN * k), LOGO_WORD_MAX * k)
        return {"h": round(h), "word": round(h), "gap": 0, "clear": round(h * LOGO_CLEAR), "min": round(LOGO_WORD_MIN * k)}
    h = min(max(LOGO_MARK_MIN * k, target / 3), LOGO_MARK_MAX * k)
    return {"h": round(h), "word": round(h), "gap": round(h * LOGO_GAP), "clear": round(h * LOGO_CLEAR), "min": round(LOGO_MARK_MIN * k)}


def edge_colours(path: Path, vertical: bool) -> Optional[Tuple[str, str]]:
    """Mean colour of the first and last 3 % rows (vertical) or columns of a
    photo: the flat fill that continues it into the bands a whole (contain)
    photo leaves on a taller or wider canvas."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            if vertical:
                d = max(1, round(h * 0.03))
                a, b = im.crop((0, 0, w, d)), im.crop((0, h - d, w, h))
            else:
                d = max(1, round(w * 0.03))
                a, b = im.crop((0, 0, d, h)), im.crop((w - d, 0, w, h))
            out = []
            for part in (a, b):
                px = part.resize((1, 1), Image.BOX).getpixel((0, 0))
                out.append(to_hex(px))
            return out[0], out[1]
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------

class Assets:
    def __init__(self, base: Path, out_dir: Path):
        self.base, self.out_dir = base, out_dir
        (out_dir / "assets").mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict[str, Any]] = {}

    def __call__(self, src: str) -> Dict[str, Any]:
        if src in self.cache:
            return self.cache[src]
        p = Path(src)
        p = p if p.is_absolute() else (self.base / src).resolve()
        if not p.is_file():
            self.cache[src] = {"ok": False, "src": src}
            return self.cache[src]
        name = hashlib.sha1(str(p).encode(), usedforsecurity=False).hexdigest()[:8] + "-" + re.sub(r"[^A-Za-z0-9._-]", "_", p.name)
        dest = self.out_dir / "assets" / name
        w = h = 1
        try:
            from PIL import Image
            with Image.open(p) as im:
                w, h = im.size
                if max(w, h) > 2400:
                    im2 = im.copy()
                    im2.thumbnail((2400, 2400))
                    w, h = im2.size
                    if im2.mode in ("RGBA", "LA", "P"):
                        dest = dest.with_suffix(".png")
                        im2.save(dest, optimize=True)
                    else:
                        dest = dest.with_suffix(".jpg")
                        im2.convert("RGB").save(dest, quality=90)
                else:
                    shutil.copyfile(p, dest)
        except Exception:  # noqa: BLE001
            shutil.copyfile(p, dest)
        self.cache[src] = {"ok": True, "url": f"assets/{dest.name}", "w": w, "h": h, "src": src, "path": p}
        return self.cache[src]


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def rich(text: str, lang: str) -> str:
    """Escape, keep units and French punctuation attached, *emphasis* becomes
    an accent span, a newline a line break."""
    s = (text or "").strip()
    if lang == "fr":
        s = re.sub(r"\s+([:;!?»])", NNBSP + r"\1", s)
        s = re.sub(r"«\s+", "«" + NNBSP, s)
    s = re.sub(r"(\d)\s+(%|s|min|h|k|M|€|\$|days?|weeks?|months?|jours?|semaines?|mois|pages?|slides?)(?=[\s.,;:!?)]|$)", r"\1" + NBSP + r"\2", s)
    out = esc(s)
    out = re.sub(r"\*([^*]+)\*", r'<em class="em">\1</em>', out)
    return out.replace("\n", "<br>")


def plain(text: str) -> str:
    return (text or "").replace("*", "")


class Ctx:
    def __init__(self, spec: Dict[str, Any], ad: Dict[str, Any], fmt: str, brand: Dict[str, Any], assets: Assets,
                 issue: Callable[[str, str, str], None], paper: RGB = WHITE):
        self.spec, self.ad, self.fmt, self.brand, self.assets, self.issue = spec, ad, fmt, brand, assets, issue
        self.lang = spec.get("meta", {}).get("language", "en")
        self.story = fmt == "9:16"
        self.group = "tall" if fmt == "4:5" else "sq"
        self.copy = ad.get("copy") or {}
        self.style = ad.get("style", "bold-statement")
        self.paper = paper
        self.logo_is_text = False
        self.logo_kind = ""
        self.has_ext = False

    def fit(self, role: str, group_id: Optional[str] = None, extra_lines: int = 0) -> str:
        rng = FIT_STYLE.get(self.style, {}).get(role, FIT_DEFAULT[role])[self.group]
        if self.story:
            k, more = STORY_GROW.get(role, (1.0, 0))
            # List items also get a higher floor: the headline grows first and
            # must not leave the list at the feed minimum.
            lo = round(rng[0] * STORY_ITEM_FLOOR) if role == "item" else rng[0]
            rng = FIT_STORY.get(self.style, {}).get(role) or (lo, round(rng[1] * k), rng[2] + more)
        a = f'data-fit="{role}" data-fit-min="{rng[0]}" data-fit-max="{rng[1]}" data-fit-lines="{rng[2] + extra_lines}" data-fit-order="{ORDER[role]}"'
        if group_id:
            a += f' data-fit-group="{group_id}"'
        return a

    def t(self, role: str, tag: str, text: str, cls: str = "", group: Optional[str] = None) -> str:
        if not (text or "").strip():
            return ""
        klass = f"{role} {cls}".strip()
        return f'<{tag} class="{klass}" {self.fit(role, group)}>{rich(text, self.lang)}</{tag}>'

    # Pieces --------------------------------------------------------------
    def head(self, cls: str = "") -> str:
        return self.t("head", "h1", self.copy.get("headline", ""), cls)

    def sub(self, cls: str = "") -> str:
        return self.t("sub", "p", self.copy.get("subhead", ""), cls)

    def badge(self) -> str:
        b = self.copy.get("badge")
        return f'<span class="badge">{rich(b, self.lang)}</span>' if b else ""

    def cta(self, cls: str = "") -> str:
        c = self.copy.get("cta")
        if not c:
            return ""
        return f'<div class="cta {cls}"><span class="cta-t" {self.fit("cta")}>{rich(c, self.lang)}</span>{ICONS["arrow"]}</div>'

    def bullets(self, icon: str = "check", cls: str = "") -> str:
        items = self.copy.get("bullets") or []
        if not items:
            return ""
        lis = []
        for it in items:
            label, text = adspec.item_parts(it)
            lab = f'<span class="li-l">{rich(label, self.lang)}</span>' if label else ""
            ico = ICONS.get(icon, "") if icon else ""
            lis.append(f'<li {self.fit("item", "items", 1 if label else 0)}>{ico}<div class="li-b">{lab}<span class="li-t">{rich(text, self.lang)}</span></div></li>')
        return f'<ul class="list {cls}">{"".join(lis)}</ul>'

    def proof(self, big: bool = False) -> str:
        p = self.ad.get("proof") or {}
        if not p:
            return ""
        stars = ""
        if p.get("rating"):
            stars = '<div class="stars" aria-hidden="true">' + "".join(
                ICONS["star"].replace('class="star"', f'class="star{" off" if i >= p["rating"] else ""}"') for i in range(5)) + "</div>"
        role = "quote" if big else "item"
        q = f'<p class="{"pq" if big else "pf"}" {self.fit(role)}>{rich(p.get("text", ""), self.lang)}</p>'
        cap = []
        if p.get("attribution"):
            cap.append(f'<span class="attr">{rich(p["attribution"], self.lang)}</span>')
        line = adspec.proof_source_line(self.spec, self.ad)
        if line:
            cap.append(f'<span class="src">{esc(line)}</span>')
        capt = f'<div class="pcap">{"".join(cap)}</div>' if cap else ""
        return f'<figure class="proof{" big" if big else ""}">{stars}{q}{capt}</figure>'

    def logo(self, dark: bool) -> str:
        """The brand logo for the paper it sits on. Mark + wordmark lockup when
        the brand has both, else the wordmark, else the mark with the name.
        The variant is the one whose declared ink holds the most contrast on
        the real paper (luminance when no ink is declared); the other variant
        only when it is a one-colour SVG, which then follows the surface ink
        (currentColor). Size and clear space: logo_size(). The name typeset in
        text is the last resort (no logo file), flagged by build and qa."""
        if self.ad.get("logo", True) is False:
            return ""
        logos = self.brand.get("logos") or {}
        inks = self.brand.get("logo_inks") or {}

        def score(variant: str) -> float:
            ink = inks.get(variant)
            if ink:
                return contrast(ink, self.paper)
            return 1.0 if (variant == "on_dark") == (lum(self.paper) < 0.18) else 0.0
        want, other = sorted(("on_dark", "on_light"), key=score, reverse=True)
        parts: Dict[str, Tuple[str, float]] = {}
        chosen = ""
        for variant, need_mono in ((want, False), (other, True)):
            v = logos.get(variant) or {}
            for kind in ("mark", "wordmark"):
                p = v.get(kind)
                if not p:
                    continue
                cls = "logo-mark" if kind == "mark" else "logo-word"
                if p.suffix.lower() == ".svg":
                    svg = inline_svg(p, cls)
                    if svg and (not need_mono or "currentColor" in svg):
                        parts[kind] = (svg, svg_aspect(svg))
                elif not need_mono:
                    a = self.assets(str(p))
                    if a["ok"]:
                        parts[kind] = (f'<img class="{cls} logo-img" src="{esc(a["url"])}" alt="">', a["w"] / max(1, a["h"]))
            if parts:
                chosen = variant
                break
        name = self.brand.get("name") or self.spec.get("meta", {}).get("project")
        if not parts:
            if not name:
                return ""
            self.logo_is_text = True
            self.logo_kind = "text"
            self.issue("warning", "logo-text", "brand.json has no usable logo file: the brand name is typeset as the logo.")
            return f'<div class="logo" data-logo="text"><span class="logo-name">{esc(name)}</span></div>'
        kind = "lockup" if len(parts) == 2 else ("wordmark" if "wordmark" in parts else "mark")
        if kind == "mark" and name:
            self.logo_is_text = True
        self.logo_kind = kind
        size = logo_size(kind, parts.get("mark", ("", 1.0))[1], parts.get("wordmark", ("", 1.0))[1], adspec.FORMATS[self.fmt][0])
        ink = inks.get(chosen)
        mono = all("currentColor" in h for h, _ in parts.values())
        attrs = f'data-logo="{kind}" data-variant="{chosen}" data-min-h="{size["min"]}" data-clear="{size["clear"]}"'
        if ink and not mono:
            attrs += f' data-ink="{to_hex(ink)}"'
        style = ";".join(f"--logo-{k}:{v}px" for k, v in size.items() if k in ("h", "word", "gap", "clear"))
        inner = "".join(parts[k][0] for k in ("mark", "wordmark") if k in parts)
        if kind == "mark" and name:
            inner += f'<span class="logo-name">{esc(name)}</span>'
        return f'<div class="logo lk-{kind}" {attrs} aria-label="{esc(name or "")}" style="{style}">{inner}</div>'

    def ext(self, inner: str) -> str:
        """9:16 only: the visual zone under the CTA. It starts in the text
        zone and runs into Meta's bottom band (a photo may sit there, a word
        may not); build_section moves the bottom of the layout box down."""
        self.has_ext = True
        return f'<div class="ext" data-box>{inner}</div>'

    def media(self, idx: int = 0, cls: str = "") -> str:
        ms = self.ad.get("media") or []
        if idx >= len(ms):
            return ""
        m = ms[idx]
        src = m.get("src") or ""
        a = self.assets(src) if src else {"ok": False, "src": "(no src)"}
        if not a["ok"]:
            self.issue("error", "missing-asset", f"media[{idx}] {src}: file not found" + (" (plate not generated yet: scripts/plates.py)" if m.get("role") == "plate" else ""))
            return f'<div class="media missing {cls}" data-box><div class="asset-missing"><span>missing media</span><span>{esc(src)}</span></div></div>'
        fit = m.get("fit") or "contain"
        ratio = a["w"] / max(1, a["h"])
        return (f'<div class="media r-{m.get("role")} fit-{fit} {cls}" data-ratio="{ratio:.4f}">'
                f'<img class="m-img" src="{esc(a["url"])}" alt="{esc(m.get("alt") or "")}" data-w="{a["w"]}" data-h="{a["h"]}"></div>')


# --------------------------------------------------------------------------
# Styles: each returns (background html, safe-box html)
# --------------------------------------------------------------------------

def top_row(c: Ctx, dark: bool, extra: str = "") -> str:
    lg = c.logo(dark)
    b = c.badge()
    if not (lg or b or extra):
        return ""
    return f'<div class="top">{lg}<div class="top-r">{b}{extra}</div></div>'


def foot(c: Ctx, *parts: str) -> str:
    inner = "".join(p for p in parts if p)
    return f'<div class="foot">{inner}</div>' if inner else ""


def s_bold_statement(c: Ctx, dark: bool) -> Tuple[str, str]:
    main = f'<div class="main" data-box>{c.head("display")}{c.sub()}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("link"))


def s_meme_static(c: Ctx, dark: bool) -> Tuple[str, str]:
    card = f'<div class="note" data-box>{c.head()}{c.sub()}</div>'
    return "", top_row(c, dark) + f'<div class="main" data-box>{card}</div>' + foot(c, c.proof(), c.cta("link"))


def s_three_benefits(c: Ctx, dark: bool) -> Tuple[str, str]:
    has_media = bool(c.ad.get("media"))
    body = f'<div class="tb-text">{c.bullets("check")}</div>'
    if has_media and c.story:
        main = f'<div class="main" data-box>{c.head("display")}{c.sub()}<div class="tb-grid solo" data-box>{body}</div></div>'
        return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button")) + c.ext(c.media(0, "tb-media"))
    if has_media:
        body = f'<div class="tb-grid" data-box>{c.media(0, "tb-media")}{body}</div>'
    else:
        body = f'<div class="tb-grid solo" data-box>{body}</div>'
    main = f'<div class="main" data-box>{c.head("display")}{c.sub()}{body}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def column(c: Ctx, side: str, icon: str) -> Tuple[str, List[str]]:
    col = (c.copy.get("columns") or {}).get(side) or {}
    items = col.get("items") or []
    label = f'<div class="col-l {side}" style="grid-row:1">{rich(col.get("label", ""), c.lang)}</div>'
    cells = [f'<div class="cell {side}{" last" if k == len(items) - 1 else ""}" style="grid-row:{k + 2}" {c.fit("item", "items")}>{ICONS[icon]}'
             f'<span class="li-t">{rich(t, c.lang)}</span></div>'
             for k, t in enumerate(items)]
    return label, cells


def s_us_vs_them(c: Ctx, dark: bool) -> Tuple[str, str]:
    lt, them = column(c, "them", "x")
    lu, us = column(c, "us", "check")
    rows = len(them) + 1
    grid = [f'<div class="cmp-bg them" style="grid-row:1 / span {rows}"></div>', f'<div class="cmp-bg us" style="grid-row:1 / span {rows}"></div>', lt, lu]
    for a, b in zip(them, us):
        grid += [a, b]
    main = f'<div class="main" data-box>{c.head("display")}<div class="cmp" data-box>{"".join(grid)}</div></div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_crossed_out(c: Ctx, dark: bool) -> Tuple[str, str]:
    main = f'<div class="main" data-box>{c.head("display")}{c.bullets("x", "struck")}{c.sub("resolve")}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_social_proof(c: Ctx, dark: bool) -> Tuple[str, str]:
    main = f'<div class="main" data-box>{c.head()}<div class="quote-card" data-box>{c.proof(big=True)}</div>{c.sub()}</div>'
    return "", top_row(c, dark) + main + foot(c, c.cta("button"))


def s_feature_callout(c: Ctx, dark: bool) -> Tuple[str, str]:
    cos = c.copy.get("callouts") or []
    left, right = [], []
    for i, co in enumerate(cos):
        el = (f'<div class="co" data-x="{co["x"]}" data-y="{co["y"]}"><span class="li-t" {c.fit("item", "items")}>{rich(co["text"], c.lang)}</span></div>')
        (left if i % 2 == 0 else right).append(el)
    stage = (f'<div class="co-stage" data-box><div class="co-col l">{"".join(left)}</div>{c.media(0, "co-media")}'
             f'<div class="co-col r">{"".join(right)}</div><svg class="co-lines" aria-hidden="true"></svg></div>')
    main = f'<div class="main" data-box>{c.head("display")}{stage}</div>'
    return "", top_row(c, dark) + main + foot(c, c.sub(), c.cta("button"))


def s_myth_fact(c: Ctx, dark: bool) -> Tuple[str, str]:
    cols = c.copy.get("columns") or {}

    def panel(side: str, cls: str) -> str:
        col = cols.get(side) or {}
        items = "".join(f'<p class="mf-t" {c.fit("item", "mf-" + side)}>{rich(t, c.lang)}</p>' for t in col.get("items") or [])
        return f'<div class="mf {cls}" data-box><div class="mf-l">{rich(col.get("label", ""), c.lang)}</div>{items}</div>'
    main = f'<div class="main" data-box>{c.head("display")}{panel("them", "myth")}{panel("us", "fact")}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_reply_comment(c: Ctx, dark: bool) -> Tuple[str, str]:
    cm = c.copy.get("comment") or {}
    name = c.brand.get("name") or c.spec.get("meta", {}).get("project", "")
    mark = ""
    lg = (c.brand.get("logos") or {}).get("on_dark", {}).get("mark") or (c.brand.get("logos") or {}).get("on_light", {}).get("mark")
    if lg and lg.suffix.lower() == ".svg":
        mark = inline_svg(lg, "av-mark") or ""
    ui = (f'<div class="thread" data-box>'
          f'<div class="cm"><span class="av"></span><div class="cm-b"><span class="cm-a">{rich(cm.get("author", ""), c.lang)}</span>'
          f'<p class="cm-t" {c.fit("comment", "cm")}>{rich(cm.get("text", ""), c.lang)}</p></div></div>'
          f'<div class="cm reply"><span class="av brand">{mark}</span><div class="cm-b"><span class="cm-a">{esc(name)}</span>'
          f'<p class="cm-t" {c.fit("comment", "cm")}>{rich(cm.get("reply", ""), c.lang)}</p></div></div></div>')
    main = f'<div class="main" data-box>{c.head("display")}{ui}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_mini_landing(c: Ctx, dark: bool) -> Tuple[str, str]:
    has_media = bool(c.ad.get("media"))
    if has_media and c.story:
        main = (f'<div class="main" data-box>{c.head("display")}{c.sub()}<div class="ml-body" data-box>'
                f'<div class="ml-text">{c.bullets("check")}{c.proof()}</div></div></div>')
        return "", top_row(c, dark) + main + foot(c, c.cta("button wide")) + c.ext(c.media(0, "ml-media"))
    med = c.media(0, "ml-media") if has_media else ""
    main = (f'<div class="main" data-box>{c.head("display")}{c.sub()}<div class="ml-body{" with-media" if has_media else ""}" data-box>'
            f'{med}<div class="ml-text">{c.bullets("check")}{c.proof()}</div></div></div>')
    return "", top_row(c, dark) + main + foot(c, c.cta("button wide"))


def s_timeline(c: Ctx, dark: bool) -> Tuple[str, str]:
    main = f'<div class="main" data-box>{c.head("display")}{c.bullets("dot", "timeline")}{c.sub()}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_flowchart(c: Ctx, dark: bool) -> Tuple[str, str]:
    items = c.copy.get("bullets") or []
    branches = []
    for it in items:
        label, text = adspec.item_parts(it)
        branches.append(f'<div class="br"><span class="br-line"></span><span class="br-l">{rich(label, c.lang)}</span>'
                        f'<div class="br-box"><span class="li-t" {c.fit("item", "items")}>{rich(text, c.lang)}</span></div></div>')
    main = (f'<div class="main" data-box><div class="q-node">{c.head()}</div><div class="branches n{len(items)}" data-box>{"".join(branches)}</div>{c.sub()}</div>')
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_testimonial(c: Ctx, dark: bool) -> Tuple[str, str]:
    p = c.ad.get("proof") or {}
    stars = ""
    if p.get("rating"):
        stars = '<div class="stars">' + "".join(ICONS["star"].replace('class="star"', f'class="star{" off" if i >= p["rating"] else ""}"') for i in range(5)) + "</div>"
    line = adspec.proof_source_line(c.spec, c.ad)
    card = (f'<div class="review sf-light" data-box><div class="rv-h"><span class="av"></span><span class="attr">{rich(p.get("attribution", ""), c.lang)}</span></div>'
            f'{stars}<p class="pq" {c.fit("quote")}>{rich(p.get("text", ""), c.lang)}</p></div>')
    src = f'<span class="src">{esc(line)}</span>' if line else ""
    main = f'<div class="main" data-box>{c.head("display")}{card}{src}</div>'
    return "", top_row(c, dark) + main + foot(c, c.sub(), c.cta("button"))


def s_cost_reframe(c: Ctx, dark: bool) -> Tuple[str, str]:
    cols = c.copy.get("columns") or {}

    def fig(side: str) -> str:
        col = cols.get(side) or {}
        items = col.get("items") or []
        first = f'<div class="fig {side}" {c.fit("fig", "fig")}>{rich(items[0], c.lang)}</div>' if items else ""
        rest = "".join(f'<p class="fig-n">{rich(t, c.lang)}</p>' for t in items[1:])
        return f'<div class="cr {side}" data-box><div class="cr-l">{rich(col.get("label", ""), c.lang)}</div>{first}{rest}</div>'
    main = f'<div class="main" data-box>{c.head("display")}<div class="cr-grid" data-box>{fig("them")}{fig("us")}</div>{c.sub()}</div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_ugc_overlay(c: Ctx, dark: bool) -> Tuple[str, str]:
    bg = c.media(0, "full")
    ms = c.ad.get("media") or []
    if ms and (ms[0].get("fit") or "contain") == "contain" and ms[0].get("src"):
        a = c.assets(ms[0]["src"])
        if a.get("ok"):
            w, h = adspec.FORMATS[c.fmt]
            vertical = a["w"] / max(1, a["h"]) > w / h
            cols = edge_colours(a["path"], vertical)
            if cols:
                sides = ("t", "b") if vertical else ("l", "r")
                bg = "".join(f'<span class="edge {k}" style="background:{v}"></span>' for k, v in zip(sides, cols)) + bg
    cap1 = f'<div class="cap sf-light"><span class="cap-t head" {c.fit("head")}>{rich(c.copy.get("headline", ""), c.lang)}</span></div>'
    cap2 = f'<div class="cap small sf-light"><span class="cap-t sub" {c.fit("sub")}>{rich(c.copy.get("subhead", ""), c.lang)}</span></div>' if c.copy.get("subhead") else ""
    lg = c.logo(dark)
    top = f'<div class="top">{lg}<div class="top-r">{c.badge()}</div></div>' if (lg or c.copy.get("badge")) else ""
    main = f'<div class="main" data-box>{cap1}<div class="spacer"></div>{cap2}</div>'
    return bg, top + main + foot(c, c.proof(), c.cta("button"))


def s_before_after(c: Ctx, dark: bool) -> Tuple[str, str]:
    cols = c.copy.get("columns") or {}

    def panel(side: str, icon: str) -> str:
        col = cols.get(side) or {}
        items = "".join(f'<li {c.fit("item", "ba")}>{ICONS[icon]}<span class="li-t">{rich(t, c.lang)}</span></li>' for t in col.get("items") or [])
        med = c.media(0, "ba-media") if side == "us" and c.ad.get("media") else ""
        return f'<div class="ba {side}" data-box><div class="ba-l">{rich(col.get("label", ""), c.lang)}</div>{med}<ul class="list">{items}</ul></div>'
    main = f'<div class="main" data-box>{c.head("display")}<div class="ba-grid" data-box>{panel("them", "x")}{panel("us", "check")}</div></div>'
    return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


def s_origin_strip(c: Ctx, dark: bool) -> Tuple[str, str]:
    n = len(c.ad.get("media") or [])
    if c.story and n:
        if n > 1:
            main = f'<div class="main" data-box>{c.head("display")}{c.sub()}</div>'
            vis = c.media(0, "os-media") + c.media(1, "os-media")
        else:
            main = f'<div class="main" data-box>{c.head("display")}<div class="os-text">{c.sub()}{c.bullets("check")}</div></div>'
            vis = c.media(0, "os-media")
        return "", top_row(c, dark) + main + foot(c, c.proof(), c.cta("button")) + c.ext(vis)
    second = c.media(1, "os-media") if len(c.ad.get("media") or []) > 1 else f'<div class="os-text">{c.sub()}{c.bullets("check")}</div>'
    main = f'<div class="main" data-box>{c.head("display")}<div class="os-grid" data-box>{c.media(0, "os-media")}{second}</div></div>'
    tail = c.sub() if len(c.ad.get("media") or []) > 1 else ""
    return "", top_row(c, dark) + main + foot(c, tail, c.proof(), c.cta("button"))


def s_hybrid(c: Ctx, dark: bool) -> Tuple[str, str]:
    bg = '<div class="hy-panels"><span class="hy-a"></span><span class="hy-b"></span><span class="hy-c"></span></div>'
    if c.story:
        main = f'<div class="main" data-box>{c.head("display")}{c.sub()}</div>'
        stage = f'<div class="hy-stage">{c.media(0, "hy-media")}</div>' if c.ad.get("media") else ""
        return bg, top_row(c, dark) + main + foot(c, c.proof(), c.cta("button")) + c.ext(stage)
    main = f'<div class="main" data-box>{c.head("display")}{c.sub()}<div class="hy-stage" data-box>{c.media(0, "hy-media")}</div></div>'
    return bg, top_row(c, dark) + main + foot(c, c.proof(), c.cta("button"))


STYLE_FN: Dict[str, Callable[[Ctx, bool], Tuple[str, str]]] = {
    "bold-statement": s_bold_statement, "meme-static": s_meme_static, "three-benefits-card": s_three_benefits,
    "us-vs-them-comparison": s_us_vs_them, "crossed-out-problems": s_crossed_out, "social-proof-card": s_social_proof,
    "feature-callout-arrows": s_feature_callout, "myth-vs-fact": s_myth_fact, "reply-to-comment": s_reply_comment,
    "mini-landing-page": s_mini_landing, "benefit-timeline": s_timeline, "flowchart-decision": s_flowchart,
    "testimonial-screenshot": s_testimonial, "cost-reframe-card": s_cost_reframe, "ugc-text-overlay": s_ugc_overlay,
    "before-after-asymmetric": s_before_after, "ingredient-origin-strip": s_origin_strip, "hybrid-2d-3d-fusion": s_hybrid,
}

# Default surface per style when the spec does not set one.
STYLE_SURFACE = {"meme-static": "light", "testimonial-screenshot": "brand", "reply-to-comment": "light",
                 "cost-reframe-card": "light", "myth-vs-fact": "brand", "mini-landing-page": "light",
                 "hybrid-2d-3d-fusion": "accent"}


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

def font_css(brand: Dict[str, Any], out_dir: Path) -> Tuple[str, str, List[str]]:
    faces = []
    for f in brand.get("font_files") or []:
        p = Path(f["path"])
        (out_dir / "fonts").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out_dir / "fonts" / p.name)
        fmt = {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype"}.get(p.suffix.lower().lstrip("."), "truetype")
        faces.append(f'@font-face{{font-family:"{f["family"]}";src:url("fonts/{p.name}") format("{fmt}");font-weight:{f["weight"]};font-style:{f["style"]};font-display:block}}')
    link = ""
    if brand.get("fonts_url") and not faces:
        url = brand["fonts_url"].replace("display=swap", "display=block")
        link = f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="{esc(url)}">'
    fams = [x for x in (brand.get("font_display"), brand.get("font_body")) if x]
    return "".join(faces), link, fams


def root_css(brand: Dict[str, Any], th: Dict[str, Dict[str, str]]) -> str:
    disp = brand.get("font_display")
    body = brand.get("font_body")
    dfb = brand.get("font_display_fallback") or "Georgia, serif"
    bfb = brand.get("font_body_fallback") or "system-ui, sans-serif"
    css = [":root{",
           f'--font-display:{chr(34) + disp + chr(34) + "," if disp else ""}{dfb};',
           f'--font-body:{chr(34) + body + chr(34) + "," if body else ""}{bfb};']
    rad = brand.get("radius")
    m = re.match(r"(\d+(?:\.\d+)?)px", str(rad or ""))
    r = min(float(m.group(1)), 24.0) if m else 12.0
    css.append(f"--radius:{r:g}px;")
    css.append(f"--display-weight:{brand.get('font_display_weight') or 700};")
    css.append(f"--body-strong:{min(brand.get('font_body_weight') or 700, 700)};}}")
    for name, roles in th.items():
        css.append(f".sf-{name}{{" + "".join(f"--{k}:{v};" for k, v in roles.items()) + "}")
    return "".join(css)


def build_section(spec: Dict[str, Any], ad: Dict[str, Any], i: int, fmt: str, brand: Dict[str, Any], th: Dict[str, Dict[str, str]],
                  assets: Assets, issues: List[Issue]) -> Tuple[str, Dict[str, Any]]:
    name = adspec.ad_name(spec, ad, i, fmt)
    w, h = adspec.FORMATS[fmt]
    st, sr, sb, sl = adspec.SAFE[fmt]
    surface = ad.get("surface") or STYLE_SURFACE.get(ad.get("style", ""), "brand")
    paper = parse_color(th[surface]["paper"]) or WHITE
    dark = lum(paper) < 0.18
    local: List[Issue] = []

    def issue(level: str, code: str, msg: str) -> None:
        local.append(Issue(level, code, f"$.ads[{i}] {fmt}", msg))
    c = Ctx(spec, ad, fmt, brand, assets, issue, paper)
    fn = STYLE_FN.get(ad.get("style", ""), s_bold_statement)
    bg, inner = fn(c, dark)
    issues.extend(local)
    cls = ""
    if c.story and not c.has_ext and ad.get("style") != "ugc-text-overlay":
        # The footer panel (proof, CTA) runs to the bottom edge through
        # Meta's bottom band: a designed base instead of an empty band.
        slab = "brand" if surface == "accent" else "accent"
        bg += f'<div class="slab sf-{slab}"></div>'
        inner = inner.replace('<div class="foot">', f'<div class="foot on-slab sf-{slab}">', 1)
        cls = " has-slab"
    elif c.has_ext:
        # The visual stands on a panel that runs to the bottom edge.
        if ad.get("style") != "hybrid-2d-3d-fusion":
            bg += '<div class="stage"></div>'
        cls = " has-ext"
    clear = re.search(r"--logo-clear:(\d+)px", inner)
    sec = (f'<section class="ad st-{esc(ad.get("style", ""))} f-{adspec.ratio_tag(fmt)} sf-{surface}{" dark" if dark else ""}{cls}" id="{esc(name)}" '
           f'data-name="{esc(name)}" data-format="{fmt}" data-ad="{esc(ad.get("id", ""))}" data-logo="{c.logo_kind}" '
           f'style="width:{w}px;height:{h}px;--st:{st}px;--sr:{sr}px;--sb:{sb}px;--sl:{sl}px;--sbl:{adspec.STORY_VISUAL_BOTTOM if c.has_ext else sb}px'
           f'{";--logo-clear:" + clear.group(1) + "px" if clear else ""}">'
           f'<div class="bg">{bg}</div><div class="safe" data-box>{inner}</div></section>')
    # The brand name in a reply-to-comment thread is DOM text (in vt["dom"]).
    vt = adspec.visible_text(spec, ad, brand.get("name") or spec.get("meta", {}).get("project"))
    if c.logo_is_text:
        vt["dom"] = vt["logo"] + vt["dom"]
        vt["logo"] = []
    exp = {"name": name, "ad": ad.get("id"), "n": adspec.ad_number(ad, i), "format": fmt, "size": [w, h],
           "safe": [st, sr, sb, sl], "surface": surface, "style": ad.get("style"),
           "dom": [plain(x) for x in vt["dom"]], "media": vt["media"], "logo": vt["logo"],
           "issues": [x.to_dict() for x in local]}
    return sec, exp


def copy_gate(spec: Dict[str, Any], out_dir: Path, project_dir: Optional[Path], issues: List[Issue]) -> Dict[str, Any]:
    """Shared writing gate on every on-ad string and the Meta ad text.
    BLOCK becomes an error, WARN a warning."""
    if not WRITING_GATE.exists():
        issues.append(Issue("warning", "copy-gate-missing", str(WRITING_GATE), "Shared writing gate not found; copy only checked for dashes."))
        return {"ran": False}
    lines: List[str] = []
    where: Dict[int, str] = {}
    for i, ad in enumerate(spec.get("ads") or []):
        c = ad.get("copy") or {}
        texts = [("headline", c.get("headline")), ("subhead", c.get("subhead")), ("badge", c.get("badge")), ("cta", c.get("cta"))]
        texts += [(f"bullets[{j}]", adspec.item_parts(b)[1]) for j, b in enumerate(c.get("bullets") or [])]
        for side in ("them", "us"):
            texts += [(f"columns.{side}", t) for t in ((c.get("columns") or {}).get(side) or {}).get("items") or []]
        texts += [(f"callouts[{j}]", co.get("text")) for j, co in enumerate(c.get("callouts") or [])]
        if c.get("comment"):
            texts.append(("comment.reply", c["comment"].get("reply")))
        ma = ad.get("meta_ad") or {}
        texts += [(f"meta_ad.{k}", ma.get(k)) for k in ("primary_text", "headline", "description")]
        for key, t in texts:
            if isinstance(t, str) and t.strip():
                where[len(lines) + 1] = f"$.ads[{i}].{key}"
                lines.append(plain(t).replace("\n", " "))
                lines.append("")
    tmp = out_dir / "copy-gate.md"
    tmp.write_text("\n".join(lines), encoding="utf-8")
    lang = spec.get("meta", {}).get("language", "en")
    cmd = [sys.executable, str(WRITING_GATE), "--json", "--lang", lang]
    if project_dir:
        cmd += ["--project", str(project_dir)]
    r = subprocess.run(cmd + [str(tmp)], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        issues.append(Issue("warning", "copy-gate-failed", str(WRITING_GATE), (r.stderr or r.stdout)[:200]))
        return {"ran": False}
    n = {"BLOCK": 0, "WARN": 0}
    for f in data.get("files", []):
        for hit in f.get("findings", []):
            if "dash" in str(hit.get("code", "")):
                continue
            lvl = "error" if hit.get("level") == "BLOCK" else "warning"
            n["BLOCK" if lvl == "error" else "WARN"] += 1
            line = hit.get("line", 0)
            loc = where.get(line) or where.get(max([k for k in where if k <= line] or [0]), "$")
            issues.append(Issue(lvl, f"copy:{hit.get('code')}", loc, f"\"{hit.get('match', '')}\": {hit.get('message', '')}"))
    tmp.unlink()
    return {"ran": True, **n}


def resolve_brand(spec: Dict[str, Any], spec_path: Path, cli: Optional[str]) -> Optional[Path]:
    if cli:
        return Path(cli).resolve()
    rel = spec.get("meta", {}).get("brand")
    if rel:
        return (spec_path.parent / rel).resolve()
    for cand in (spec_path.parent / "project-context" / "brand.json", spec_path.parent.parent / "project-context" / "brand.json",
                 spec_path.parent.parent.parent / "project-context" / "brand.json"):
        if cand.exists():
            return cand.resolve()
    return None


def build(spec_path: Path, out_dir: Path, brand_cli: Optional[str] = None, only: Optional[List[str]] = None,
          gate: bool = True) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec, issues = adspec.load_spec(spec_path)
    if spec is None:
        rep = {"spec": str(spec_path), "errors": [i.to_dict() for i in issues], "warnings": [], "sections": []}
        (out_dir / "build-report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        return rep
    brand_path = resolve_brand(spec, spec_path, brand_cli)
    brand = load_brand(brand_path, issues)
    th = theme(brand)
    assets = Assets(spec_path.parent, out_dir)
    faces, link, fams = font_css(brand, out_dir)
    css = (TEMPLATES / "base.css").read_text(encoding="utf-8") + "\n" + (TEMPLATES / "styles.css").read_text(encoding="utf-8")
    fit_js = (SCRIPTS / "fit.js").read_text(encoding="utf-8")
    sections, expected = [], []
    for i, ad in enumerate(spec["ads"]):
        if only and ad.get("id") not in only:
            continue
        for fmt in ad.get("formats") or ["4:5"]:
            if fmt not in adspec.FORMATS:
                continue
            sec, exp = build_section(spec, ad, i, fmt, brand, th, assets, issues)
            sections.append(sec)
            expected.append(exp)
    lang = spec.get("meta", {}).get("language", "en")
    page = (f'<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8"><title>{esc(spec["meta"].get("project", "ads"))} ads</title>'
            f'{link}<style>{faces}{root_css(brand, th)}\n{css}</style></head><body>{"".join(sections)}'
            f'<script>{fit_js}</script></body></html>')
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    gate_res = {"ran": False}
    if gate:
        project_dir = brand_path.parent.parent if brand_path and brand_path.parent.name == "project-context" and (brand_path.parent / "context.json").exists() else None
        gate_res = copy_gate(spec, out_dir, project_dir, issues)
    (out_dir / "expected.json").write_text(json.dumps({"spec": str(spec_path), "sections": expected}, indent=2, ensure_ascii=False), encoding="utf-8")
    rep = {"spec": str(spec_path), "brand": str(brand_path) if brand_path else None, "brand_version": brand.get("version"),
           "fonts": fams, "theme": th, "copy_gate": gate_res, "sections": [e["name"] for e in expected],
           "errors": [x.to_dict() for x in issues if x.level == "error"],
           "warnings": [x.to_dict() for x in issues if x.level == "warning"]}
    (out_dir / "build-report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="ads.json")
    ap.add_argument("--out", help="Output dir (default <ads.json dir>/html)")
    ap.add_argument("--brand", help="brand.json (default: meta.brand, else the nearest project-context/brand.json)")
    ap.add_argument("--only", help="Comma-separated ad ids to build")
    ap.add_argument("--no-gate", action="store_true", help="Skip the shared writing gate")
    args = ap.parse_args()
    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"build: {spec_path} not found", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else spec_path.parent / "html"
    rep = build(spec_path, out, args.brand, args.only.split(",") if args.only else None, not args.no_gate)
    for e in rep["errors"]:
        print(f"ERROR {e['code']} {e['where']}: {e['message']}")
    for w in rep["warnings"]:
        print(f"warn  {w['code']} {w['where']}: {w['message']}")
    if not rep.get("sections") and rep["errors"] and rep["errors"][0]["code"] == "json":
        return 2
    print(f"build: {len(rep.get('sections', []))} sections, {len(rep['errors'])} errors, {len(rep['warnings'])} warnings -> {out}")
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
