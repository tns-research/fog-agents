#!/usr/bin/env python3
"""build.py: deck.json + direction + brand.json -> build/index.html

Deterministic: the same inputs always give the same HTML. The model writes
deck.json and never touches the HTML; every fix goes through the spec, the
direction or the brand file.

Usage:
  python3 scripts/build.py <deck.json> [--out DIR] [--direction ID] [--brand brand.json]
  python3 scripts/build.py <deck.json> --covers [--directions a,b,c] [--out DIR]
  python3 scripts/build.py --list-directions

Outputs (default DIR = <deck dir>/html, a name outside .gitignore):
  index.html          one <section class="slide"> per slide, fonts, CSS and fit.js inline
  assets/             images copied from the deck, downscaled past 2400 px
  build-report.json   spec issues (schema, claims, dashes, budgets, rhythm, assets)

--covers writes DIR/covers/<direction>/html/index.html for every direction asked,
each holding hooks x cover layouts (meta.covers), plus DIR/covers/manifest.json.

Exit code: 0 when the spec has no error, 1 when it has errors (the HTML is
still written so qa.py can show them), 2 when deck.json cannot be read.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blocks  # noqa: E402
import deckspec  # noqa: E402
from deckspec import Issue  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parent.parent
DIRECTIONS_DIR = AGENT_DIR / "directions"
SCRIPTS_DIR = AGENT_DIR / "scripts"
REPO_ROOT = AGENT_DIR.parent.parent
SHARED_BRAND_SCHEMA = REPO_ROOT / "shared" / "schemas" / "brand.schema.json"

DEFAULT_SCALE = {
    "cover_title": {"min": 72, "max": 160, "lines": 5},
    "cover_sub": {"min": 32, "max": 44, "lines": 4},
    "title": {"min": 56, "max": 104, "lines": 4},
    "sub": {"min": 30, "max": 40, "lines": 3},
    "body": {"min": 30, "max": 40, "lines": 10},
    "list": {"min": 30, "max": 44, "lines": 3},
    "stat_value": {"min": 120, "max": 300, "lines": 1},
    "stat_label": {"min": 34, "max": 52, "lines": 3},
    "stat_context": {"min": 28, "max": 34, "lines": 4},
    "chart_title": {"min": 30, "max": 40, "lines": 2},
    "quote": {"min": 40, "max": 76, "lines": 7},
    "cta_title": {"min": 64, "max": 128, "lines": 4},
    "cta": {"min": 48, "max": 96, "lines": 3},
    "cta_sub": {"min": 30, "max": 40, "lines": 3},
}

AUTO_LAYOUT_ORDER = [
    ("chart", "chart"), ("stat", "stat"), ("quote", "quote"), ("screenshot", "media"),
    ("photo", "media"), ("logo-row", "logos"), ("visual", "visual"), ("list", "list"),
]


# --------------------------------------------------------------------------
# Colour maths
# --------------------------------------------------------------------------

def parse_color(c: Any) -> Optional[Tuple[int, int, int]]:
    if not isinstance(c, str):
        return None
    c = c.strip()
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(x * 2 for x in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    m = re.fullmatch(r"rgba?\(([^)]+)\)", c)
    if m:
        parts = [p for p in re.split(r"[ ,/]+", m.group(1)) if p]
        try:
            return tuple(int(float(p)) for p in parts[:3])  # type: ignore
        except ValueError:
            return None
    return None


def to_hex(rgb: Tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def lum(rgb: Tuple[float, float, float]) -> float:
    def ch(v: float) -> float:
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def mix(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))  # type: ignore


def pick(cands: List[Tuple[int, int, int]], test, toward: Tuple[int, int, int]) -> Tuple[float, float, float]:
    for c in cands:
        if test(c):
            return c
    base = cands[0]
    for k in range(1, 21):
        m = mix(base, toward, k / 20)
        if test(m):
            return m
    return toward


def derive_accents(paper, ink, cands) -> Dict[str, str]:
    """Accent roles that hold their contrast on a given surface.

    mark  graphics, bars, rules: 3:1 against the paper (WCAG 1.4.11)
    text  accent-coloured words: 4.5:1 against the paper
    fill  highlight behind ink text: 7:1 against the ink and visible on paper
    solid accent surface; on-solid is the readable text colour on it
    """
    mark = pick(cands, lambda c: contrast(c, paper) >= 3.0, ink)
    text = pick(cands, lambda c: contrast(c, paper) >= 4.5, ink)
    fill = pick(cands, lambda c: contrast(c, ink) >= 7.0 and contrast(c, paper) >= 1.12, paper)
    if contrast(fill, ink) < 7.0:
        fill = mix(paper, ink, 0.0)
    # Accent surface: the first candidate that carries ink or paper text at 7:1.
    solid = next((c for c in cands if max(contrast(c, ink), contrast(c, paper)) >= 7.0), cands[0])
    on_solid = max([ink, paper, (255, 255, 255), (0, 0, 0)], key=lambda c: contrast(c, solid))
    return {"mark": to_hex(mark), "text": to_hex(text), "fill": to_hex(fill), "on_fill": to_hex(ink),
            "solid": to_hex(solid), "on_solid": to_hex(on_solid)}


# --------------------------------------------------------------------------
# Directions and brand
# --------------------------------------------------------------------------

def list_directions() -> List[str]:
    return sorted(p.name for p in DIRECTIONS_DIR.iterdir() if (p / "direction.json").exists())


def load_direction(did: str, issues: List[Issue]) -> Tuple[Dict[str, Any], str, Path]:
    d = DIRECTIONS_DIR / did
    if not (d / "direction.json").exists():
        avail = list_directions()
        issues.append(Issue("error", "unknown-direction", "$.meta.direction", f"No direction '{did}'. Available: {', '.join(avail)}."))
        did = avail[0]
        d = DIRECTIONS_DIR / did
    conf = deckspec.load_json(d / "direction.json")
    css = (d / "style.css").read_text(encoding="utf-8") if (d / "style.css").exists() else ""
    return conf, css, d


def brand_path_resolver(brand_file: Path):
    """V2 paths are relative to the project-context/ folder (the brand.json
    folder). V1 paths are relative to the project root and start with
    project-context/. Try the file folder, then its parents."""
    def resolve(p: Optional[str]) -> Optional[Path]:
        if not p:
            return None
        cand = Path(p)
        if cand.is_absolute():
            return cand if cand.exists() else None
        for base in (brand_file.parent, brand_file.parent.parent, brand_file.parent.parent.parent):
            q = (base / p).resolve()
            if q.exists():
                return q
        return None
    return resolve


def font_family(stack: Optional[str]) -> Optional[str]:
    if not stack:
        return None
    first = stack.split(",")[0].strip().strip("'\"")
    return first or None


def validate_brand_v2(path: Path, issues: List[Issue]) -> None:
    validator = REPO_ROOT / "shared" / "scripts" / "validate_json.py"
    if not (validator.exists() and SHARED_BRAND_SCHEMA.exists()):
        return
    import subprocess
    r = subprocess.run([sys.executable, str(validator), str(SHARED_BRAND_SCHEMA), str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        for line in (r.stdout + r.stderr).strip().splitlines()[:8]:
            issues.append(Issue("warning", "brand-schema", str(path), line.strip()))


def load_brand(path: Optional[Path], issues: List[Issue]) -> Dict[str, Any]:
    """Read brand.json defensively.

    V2 (schema_version "2.0", shared/schemas/brand.schema.json): colors{},
    fonts.display/body{family, fallback, files}, fonts.fonts_url,
    logos.on_light/on_dark{mark, wordmark}, logo_text, extensions.
    V1 (no schema_version): bg, text_primary, accent, accent_secondary,
    font_heading, font_body, logo_path, assets{}; mapped as in
    shared/schemas/README.md. Optional extras this agent reads from
    extensions.carousel_builder (V2) or the top level (V1): handle, palette
    (extra brand colours offered to the accent picker, in order)."""
    if not path:
        return {}
    if not path.exists():
        issues.append(Issue("warning", "brand-missing", str(path), "brand.json not found, building without brand."))
        return {}
    try:
        raw = deckspec.load_json(path)
    except Exception as e:  # noqa: BLE001
        issues.append(Issue("warning", "brand-malformed", str(path), f"brand.json does not parse ({e}); building without brand."))
        return {}
    resolve = brand_path_resolver(path)
    v2 = raw.get("schema_version") == "2.0"
    out: Dict[str, Any] = {"file": str(path), "version": "2.0" if v2 else "1", "font_files": [], "google": [],
                           "logos": {"on_light": {}, "on_dark": {}}}
    ext = (raw.get("extensions") or {}).get("carousel_builder", {}) if v2 else raw
    ext = ext if isinstance(ext, dict) else {}
    pal = ext.get("palette") if isinstance(ext.get("palette"), dict) else {}
    out["palette"] = [c for c in (parse_color(v) for v in pal.values()) if c]
    out["handle"] = ext.get("handle")
    if v2:
        validate_brand_v2(path, issues)
        colors = raw.get("colors") or {}
        out.update({
            "name": raw.get("name") or raw.get("logo_text"), "mode": raw.get("mode"),
            "bg": parse_color(colors.get("bg")), "text": parse_color(colors.get("text")),
            "accent": parse_color(colors.get("accent")), "accent_2": parse_color(colors.get("accent_secondary")),
        })
        fonts = raw.get("fonts") or {}
        for role, key in (("display", "font_heading"), ("body", "font_body")):
            f = fonts.get(role) or {}
            if f.get("family"):
                out[key] = f["family"]
                out[key + "_fallback"] = f.get("fallback")
            for fl in f.get("files") or []:
                p = resolve(fl.get("path"))
                if p:
                    out["font_files"].append({"family": f.get("family"), "path": p, "weight": str(fl.get("weight", 400)),
                                              "style": fl.get("style", "normal")})
                else:
                    issues.append(Issue("warning", "brand-font-missing", "brand.fonts", f"{fl.get('path')} not found."))
        out["fonts_url"] = fonts.get("fonts_url")
        for variant in ("on_light", "on_dark"):
            v = (raw.get("logos") or {}).get(variant) or {}
            for kind in ("mark", "wordmark"):
                if v.get(kind):
                    p = resolve(v[kind].get("path"))
                    if p:
                        out["logos"][variant][kind] = p
                    else:
                        issues.append(Issue("warning", "brand-asset-missing", f"brand.logos.{variant}.{kind}", f"{v[kind].get('path')} not found."))
    else:
        assets = raw.get("assets") if isinstance(raw.get("assets"), dict) else {}
        bg = parse_color(raw.get("bg"))
        out.update({
            "name": raw.get("name") or raw.get("logo_text"), "mode": ("dark" if bg and lum(bg) < 0.2 else "light"),
            "bg": bg, "text": parse_color(raw.get("text_primary")),
            "accent": parse_color(raw.get("accent")), "accent_2": parse_color(raw.get("accent_secondary")),
            "font_heading": font_family(raw.get("font_heading")), "font_body": font_family(raw.get("font_body")),
            "fonts_url": raw.get("fonts_url"),
        })
        logo = resolve(raw.get("logo_path") or assets.get("logo_path"))
        if logo:
            out["logos"][f"on_{out['mode']}"]["wordmark"] = logo
        elif raw.get("logo_path") or assets.get("logo_path"):
            issues.append(Issue("warning", "brand-asset-missing", "brand.logo_path", f"{raw.get('logo_path') or assets.get('logo_path')} not found."))
    if not any(out["logos"][v] for v in out["logos"]):
        issues.append(Issue("warning", "no-logo", "brand", "No logo file resolved: cover and CTA set the brand name in text."))
    return out


def inline_svg(path: Path, cls: str) -> Optional[str]:
    """Inline a logo SVG. A one-colour logo switches to currentColor so the
    direction can set it to ink or paper."""
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
    new_head = re.sub(r'\s(width|height)="[^"]*"', "", head)
    new_head = new_head.replace("<svg", f'<svg class="{cls}" aria-hidden="true" focusable="false"', 1)
    return svg.replace(head, new_head, 1)


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------

class Assets:
    def __init__(self, deck_dir: Path, out_dir: Path):
        self.deck_dir = deck_dir
        self.out_dir = out_dir
        self.cache: Dict[str, Dict[str, Any]] = {}
        (out_dir / "assets").mkdir(parents=True, exist_ok=True)

    def resolve(self, src: str) -> Optional[Path]:
        p = Path(src)
        if not p.is_absolute():
            p = (self.deck_dir / src).resolve()
        return p if p.exists() and p.is_file() else None

    def __call__(self, src: str) -> Dict[str, Any]:
        if src in self.cache:
            return self.cache[src]
        p = self.resolve(src)
        if p is None:
            res = {"ok": False, "w": 1, "h": 1}
            self.cache[src] = res
            return res
        digest = hashlib.sha1(str(p).encode(), usedforsecurity=False).hexdigest()[:8]
        name = f"{digest}-{re.sub(r'[^A-Za-z0-9._-]', '_', p.name)}"
        dest = self.out_dir / "assets" / name
        w = h = 1
        if p.suffix.lower() == ".svg":
            shutil.copyfile(p, dest)
            txt = p.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', txt)
            if m:
                w, h = int(float(m.group(1))), int(float(m.group(2)))
        else:
            try:
                from PIL import Image
                with Image.open(p) as im:
                    w, h = im.size
                    if max(w, h) > 2400 or p.stat().st_size > 1_500_000:
                        im2 = im.copy()
                        im2.thumbnail((2400, 2400))
                        w, h = im2.size
                        if im2.mode in ("RGBA", "LA", "P") and p.suffix.lower() == ".png":
                            dest = dest.with_suffix(".png")
                            im2.save(dest, optimize=True)
                        else:
                            dest = dest.with_suffix(".jpg")
                            im2.convert("RGB").save(dest, quality=90, optimize=True)
                    else:
                        shutil.copyfile(p, dest)
            except Exception:  # noqa: BLE001
                shutil.copyfile(p, dest)
        res = {"ok": True, "url": f"assets/{dest.name}", "w": w, "h": h, "path": str(p)}
        self.cache[src] = res
        return res


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def google_link(specs: List[str]) -> str:
    specs = [s for s in dict.fromkeys(specs) if s]
    if not specs:
        return ""
    fam = "&".join("family=" + s.replace(" ", "+") for s in specs)
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{fam}&display=block">')


def font_faces(files: List[Dict[str, Any]], out_dir: Path) -> str:
    css = []
    fdir = out_dir / "fonts"
    for f in files:
        p = Path(f["path"])
        if not p.exists():
            continue
        fdir.mkdir(parents=True, exist_ok=True)
        dest = fdir / p.name
        if not dest.exists():
            shutil.copyfile(p, dest)
        fmt = {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype"}.get(p.suffix.lower().lstrip("."), "truetype")
        css.append(f'@font-face{{font-family:"{f["family"]}";src:url("fonts/{p.name}") format("{fmt}");'
                   f'font-weight:{f.get("weight", "100 900")};font-style:{f.get("style", "normal")};font-display:block}}')
    return "".join(css)


def palette_vars(p: Dict[str, Any]) -> str:
    keys = ["paper", "ink", "muted", "rule", "chart_base", "chart_base_2", "chart_base_3", "mat"]
    out = []
    for k in keys:
        if p.get(k):
            out.append(f"--{k.replace('_', '-')}:{p[k]};")
    return "".join(out)


def accent_vars(a: Dict[str, str]) -> str:
    return (f"--accent-mark:{a['mark']};--accent-text:{a['text']};--accent-fill:{a['fill']};"
            f"--on-accent-fill:{a['on_fill']};--accent-solid:{a['solid']};--on-accent-solid:{a['on_solid']};")


def theme_css(direction: Dict[str, Any], brand: Dict[str, Any], use_brand_fonts: bool) -> Tuple[str, Dict[str, Any]]:
    pal = dict(direction.get("palette", {}))
    inv = dict(pal.get("inverse", {}))
    info: Dict[str, Any] = {}
    # Brand surface: a dark brand background can become the inverse surface.
    bconf = direction.get("brand", {})
    if bconf.get("inverse_from_brand") and brand.get("bg") and lum(brand["bg"]) < 0.18:
        inv["paper"] = to_hex(brand["bg"])
        if brand.get("text") and contrast(brand["text"], brand["bg"]) >= 7:
            inv["ink"] = to_hex(brand["text"])
        info["inverse_from_brand"] = True
    cands: List[Tuple[int, int, int]] = []
    for c in (brand.get("accent"), brand.get("accent_2"), *brand.get("palette", [])):
        if c and c not in cands:
            cands.append(c)
    for c in (parse_color(pal.get("accent")), parse_color(pal.get("accent_2"))):
        if c and c not in cands:
            cands.append(c)
    if not cands:
        cands = [(200, 60, 40)]
    paper, ink = parse_color(pal.get("paper", "#ffffff")), parse_color(pal.get("ink", "#111111"))
    # A direction can ask for the brand colour that stands out most on its
    # paper (dark directions: a light accent beats a mid-tone one).
    if bconf.get("accent_pick") == "max-contrast":
        cands = sorted(cands, key=lambda c: -contrast(c, paper))
    acc = derive_accents(paper, ink, cands)
    css = [":root{", palette_vars(pal), f"--brand-accent:{to_hex(cands[0])};"]
    fonts = direction.get("fonts", {})
    for role, f in fonts.items():
        if isinstance(f, dict) and f.get("family"):
            css.append(f'--font-{role}:"{f["family"]}",{f.get("fallback", "system-ui, sans-serif")};')
    if use_brand_fonts:
        hf, bf = brand.get("font_heading"), brand.get("font_body")
        if hf:
            css.append(f'--font-display:"{hf}",{fonts.get("display", {}).get("fallback", "serif")};')
            info["brand_display_font"] = hf
        if bf:
            css.append(f'--font-text:"{bf}",{fonts.get("text", {}).get("fallback", "sans-serif")};')
            info["brand_text_font"] = bf
    css.append("}")
    css.append(".slide{" + accent_vars(acc) + "}")
    info["accents"] = acc
    if inv:
        ipaper = parse_color(inv.get("paper", "#111111"))
        iink = parse_color(inv.get("ink", "#ffffff"))
        iacc = derive_accents(ipaper, iink, cands)
        css.append(".slide.surface-inverse{" + palette_vars(inv) + accent_vars(iacc) + "}")
        info["accents_inverse"] = iacc
    solid, on_solid = parse_color(acc["solid"]), parse_color(acc["on_solid"])
    sp = {"paper": acc["solid"], "ink": acc["on_solid"], "muted": to_hex(mix(on_solid, solid, 0.25)),
          "rule": acc["on_solid"], "chart_base": to_hex(mix(on_solid, solid, 0.55)), "mat": acc["solid"]}
    sacc = {"mark": acc["on_solid"], "text": acc["on_solid"], "fill": to_hex(paper) if contrast(paper, ink) >= 7 else acc["on_solid"],
            "on_fill": to_hex(ink), "solid": acc["on_solid"], "on_solid": acc["solid"]}
    css.append(".slide.surface-accent{" + palette_vars(sp) + accent_vars(sacc) + "}")
    return "".join(css), info


def slide_sources(slide: Dict[str, Any], registry: Dict[str, Any], lang: str) -> str:
    labels: List[str] = []
    for b in slide.get("blocks", []):
        if not isinstance(b, dict):
            continue
        s = deckspec.resolve_source(b.get("source"), registry)
        if s and s.get("label") and s["label"] not in labels:
            labels.append(s["label"])
    if not labels:
        return ""
    word = blocks.t(lang, "sources" if len(labels) > 1 else "source")
    sep = blocks.NNBSP + ":" if lang.startswith("fr") else ":"
    return f"{word}{sep} " + " ; ".join(labels) if lang.startswith("fr") else f"{word}{sep} " + "; ".join(labels)


def auto_layout(slide: Dict[str, Any], direction: Dict[str, Any]) -> str:
    role = slide.get("role")
    if role == "cover":
        return (direction.get("cover_layouts") or ["cover-a"])[0]
    if role == "cta":
        return "cta"
    types = [b.get("type") for b in slide.get("blocks", []) if isinstance(b, dict)]
    for t, name in AUTO_LAYOUT_ORDER:
        if t in types:
            return name
    return "text"


def logo_html(brand: Dict[str, Any], assets: "Assets", dark: bool) -> str:
    """Logo lockup for a light or dark surface. Uses the matching V2 variant;
    the other variant only when it is a one-colour SVG (it then follows the
    text colour). Falls back to the brand name typeset in the display font."""
    def one(path: Path, cls: str, need_mono: bool) -> str:
        if path.suffix.lower() == ".svg":
            s = inline_svg(path, cls)
            if s and (not need_mono or "currentColor" in s):
                return s
            if need_mono:
                return ""
        elif need_mono:
            return ""
        a = assets(str(path))
        return f'<img class="{cls}" src="{blocks.esc(a.get("url", ""))}" alt="">' if a["ok"] else ""
    logos = brand.get("logos") or {}
    want, other = ("on_dark", "on_light") if dark else ("on_light", "on_dark")
    parts: List[str] = []
    for variant, need_mono in ((want, False), (other, True)):
        v = logos.get(variant) or {}
        if not v:
            continue
        cand = []
        if v.get("mark"):
            cand.append(one(v["mark"], "logo-mark", need_mono))
        if v.get("wordmark"):
            cand.append(one(v["wordmark"], "logo-word" if v.get("mark") else "logo-full", need_mono))
        cand = [c for c in cand if c]
        if cand:
            parts = cand
            break
    if parts and not any("logo-word" in p or "logo-full" in p for p in parts) and brand.get("name"):
        parts.append(f'<span class="logo-name">{blocks.esc(brand["name"])}</span>')
    if not parts and brand.get("name"):
        parts = [f'<span class="logo-name">{blocks.esc(brand["name"])}</span>']
    if not parts:
        return ""
    return f'<div class="logo" aria-label="{blocks.esc(brand.get("name") or "")}">{"".join(parts)}</div>'


def build_slide(slide: Dict[str, Any], idx: int, total: int, deck: Dict[str, Any], direction: Dict[str, Any],
                brand: Dict[str, Any], ctx_factory, issues: List[Issue], registry: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    meta = deck["meta"]
    lang = meta.get("language", "en")
    role = slide.get("role", "content")
    layouts = direction.get("layouts", {})
    layout = slide.get("layout")
    if layout and layout not in layouts:
        issues.append(Issue("warning", "unknown-layout", f"$.slides[{idx - 1}].layout",
                            f"'{layout}' is not a layout of {direction.get('id')}; picked one from the blocks."))
        layout = None
    layout = layout or auto_layout(slide, direction)
    tone = deckspec.slide_tone(slide)
    surface = slide.get("surface", "default")
    types = [b.get("type") for b in slide.get("blocks", []) if isinstance(b, dict)]

    def issue(level: str, code: str, where: str, msg: str) -> None:
        issues.append(Issue(level, code, f"$.slides[{idx - 1}] {where}", msg))

    ctx = ctx_factory(issue, layout)
    ctx.has_media = bool({"photo", "screenshot", "visual"} & set(types))
    ctx.layout = layout
    parts = []
    for i, b in enumerate(slide.get("blocks", [])):
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        try:
            if t == "visual":
                parts.append(blocks.visual(b, i, role, ctx, ctx_factory.read_text))
            elif t in blocks.RENDERERS:
                parts.append(blocks.RENDERERS[t](b, i, role, ctx))
            else:
                issue("error", "unknown-block", f"blocks[{i}]", f"Unknown block type {t!r}.")
        except KeyError as e:
            issue("error", "block-field", f"blocks[{i}]", f"{t} block is missing {e}; rendered as an empty block.")
            parts.append(f'<div class="b b-{blocks.esc(t)} b-broken" data-b="{i}"></div>')

    chrome = direction.get("chrome", {})
    show_logo = role in chrome.get("logo", ["cover", "cta"])
    handle = meta.get("handle") or brand.get("handle")
    show_handle = role in chrome.get("handle", ["content"]) and handle
    show_folio = meta.get("page_numbers", chrome.get("folio", False)) and role == "content"
    head = ""
    if show_logo:
        dark = (surface == "inverse") != (direction.get("mood") == "dark")
        lg = logo_html(brand, ctx_factory.assets, dark)
        if lg:
            head = f'<header class="s-head">{lg}</header>'
    foot_parts = []
    src = slide_sources(slide, registry, lang)
    if src:
        foot_parts.append(f'<p class="src">{blocks.esc(src)}</p>')
    if show_handle:
        foot_parts.append(f'<p class="handle">{blocks.esc(handle)}</p>')
    if show_folio:
        foot_parts.append(f'<p class="folio">{idx}<span class="folio-of">/{total}</span></p>')
    foot = f'<footer class="s-foot">{"".join(foot_parts)}</footer>' if foot_parts else ""
    classes = ["slide", f"role-{role}", f"layout-{layout}", f"surface-{surface}", f"tone-{tone}"]
    classes += [f"has-{t}" for t in dict.fromkeys(types) if t]
    sid = slide.get("id") or f"s{idx:02d}"
    html_ = (f'<section class="{" ".join(classes)}" id="{blocks.esc(sid)}" data-index="{idx}" data-role="{role}" '
             f'data-layout="{layout}" aria-label="{idx}/{total}">'
             f'<div class="s-deco" aria-hidden="true"></div>'
             f'<div class="s-frame">{head}<div class="s-main">{"".join(parts)}</div>{foot}</div></section>')
    return html_, {"index": idx, "id": sid, "role": role, "layout": layout, "tone": tone, "surface": surface, "blocks": types}


class CtxFactory:
    def __init__(self, deck: Dict[str, Any], direction: Dict[str, Any], assets: Assets, deck_dir: Path):
        self.lang = deck["meta"].get("language", "en")
        scale = copy.deepcopy(DEFAULT_SCALE)
        for k, v in (direction.get("type_scale") or {}).items():
            scale[k] = {**scale.get(k, {}), **v}
        self.scale = scale
        self.direction = direction
        self.assets = assets
        self.deck_dir = deck_dir

    def __call__(self, issue, layout: str) -> blocks.Ctx:
        boxes = self.direction.get("chart_box", {})
        box = boxes.get(layout) if isinstance(boxes, dict) else boxes
        if not box:
            box = boxes.get("default", [912, 640]) if isinstance(boxes, dict) else [912, 640]
        return blocks.Ctx(self.lang, self.scale, self.assets, box, issue)

    def read_text(self, rel: str) -> Optional[str]:
        p = Path(rel) if Path(rel).is_absolute() else self.deck_dir / rel
        try:
            return p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            return None


def build_html(deck: Dict[str, Any], deck_dir: Path, out_dir: Path, direction_id: str, brand: Dict[str, Any],
               issues: List[Issue], debug: bool = False) -> Dict[str, Any]:
    meta = deck["meta"]
    lang = meta.get("language", "en")
    fmt = meta.get("format", "linkedin")
    W, H = deckspec.FORMATS.get(fmt, (1080, 1350))
    direction, dcss, ddir = load_direction(direction_id, issues)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = Assets(deck_dir, out_dir)
    use_brand_fonts = meta.get("use_brand_fonts", direction.get("brand", {}).get("fonts", False))
    theme, theme_info = theme_css(direction, brand, bool(use_brand_fonts))
    registry = {s["id"]: s for s in deck.get("sources", []) or [] if isinstance(s, dict) and "id" in s}
    factory = CtxFactory(deck, direction, assets, deck_dir)
    slides = [s for s in deck.get("slides", []) if isinstance(s, dict)]
    sections, manifest = [], []
    for i, s in enumerate(slides, 1):
        h, m = build_slide(s, i, len(slides), deck, direction, brand, factory, issues, registry)
        sections.append(h)
        manifest.append(m)
    # Fonts: direction Google fonts + local files, brand fonts in their own link
    # (an unknown family must not break the direction's request).
    specs = [f.get("google") for f in direction.get("fonts", {}).values() if isinstance(f, dict)]
    files = []
    for f in direction.get("fonts", {}).values():
        for fl in (f.get("files") or []) if isinstance(f, dict) else []:
            files.append({"family": f["family"], "path": str(ddir / fl["path"]), "weight": fl.get("weight", "400"), "style": fl.get("style", "normal")})
    brand_link = ""
    if use_brand_fonts:
        if brand.get("fonts_url"):
            brand_link = f'<link rel="stylesheet" href="{blocks.esc(brand["fonts_url"])}">'
        else:
            brand_link = google_link([f for f in (brand.get("font_heading"), brand.get("font_body")) if f])
        files += brand.get("font_files", [])
    base_css = (DIRECTIONS_DIR / "_base.css").read_text(encoding="utf-8")
    fit_js = (SCRIPTS_DIR / "fit.js").read_text(encoding="utf-8")
    title = blocks.esc(meta.get("title") or meta.get("id") or "carousel")
    doc = (f'<!doctype html><html lang="{blocks.esc(lang)}"><head><meta charset="utf-8">'
           f'<meta name="generator" content="fog-agents carousel-builder build.py">'
           f'<title>{title}</title>{google_link(specs)}{brand_link}'
           f'<style>{font_faces(files, out_dir)}:root{{--W:{W}px;--H:{H}px}}@page{{size:{W}px {H}px;margin:0}}</style>'
           f'<style>{base_css}</style><style>{dcss}</style><style>{theme}</style></head>'
           f'<body class="d-{blocks.esc(direction.get("id", direction_id))} f-{fmt}" data-direction="{blocks.esc(direction.get("id", direction_id))}" '
           f'data-format="{fmt}" data-w="{W}" data-h="{H}"{" data-debug" if debug else ""}>'
           f'<main class="deck">{"".join(sections)}</main><script>{fit_js}</script></body></html>')
    (out_dir / "index.html").write_text(doc, encoding="utf-8")
    return {"direction": direction.get("id", direction_id), "format": fmt, "width": W, "height": H,
            "slides": manifest, "theme": theme_info, "fonts": [f.get("family") for f in direction.get("fonts", {}).values() if isinstance(f, dict)],
            "brand_fonts": bool(use_brand_fonts), "safe_margin": direction.get("safe_margin", 60),
            "min_text": direction.get("min_text", {}),
            "tones": [m["tone"] for m in manifest]}


WRITING_GATE = REPO_ROOT / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"


def copy_gate(deck: Dict[str, Any], brand_path: Optional[Path], out_dir: Path, issues: List[Issue]) -> Dict[str, Any]:
    """Run the shared writing gate on every visible text of the deck and the
    captions. BLOCK becomes a build error, WARN a warning. Skipped with a
    warning when the shared gate is absent."""
    if not WRITING_GATE.exists():
        issues.append(Issue("warning", "copy-gate-missing", "shared/skills/writing-gate", "Shared writing gate not found; copy was only checked for dashes."))
        return {"ran": False}
    import subprocess
    lines: List[str] = []
    where: Dict[int, str] = {}
    for i, slide in enumerate(deck.get("slides", [])):
        if not isinstance(slide, dict):
            continue
        for j, b in enumerate(slide.get("blocks", []) or []):
            if not isinstance(b, dict) or b.get("type") == "quote":
                continue  # quotes are verbatim, never rewritten
            for text in deckspec.iter_texts(b):
                for para in re.split(r"\n\s*\n", text):
                    where[len(lines) + 1] = f"$.slides[{i}].blocks[{j}]"
                    lines.append(para.replace("\n", " ").strip())
                    lines.append("")
    caps = deck.get("meta", {}).get("captions") or {}
    for key in ("linkedin", "instagram", "first_comment"):
        for para in re.split(r"\n\s*\n", caps.get(key) or ""):
            if para.strip():
                where[len(lines) + 1] = f"$.meta.captions.{key}"
                lines.append(para.replace("\n", " ").strip())
                lines.append("")
    tmp = out_dir / "copy-gate.md"
    tmp.write_text("\n".join(lines), encoding="utf-8")
    lang = deck.get("meta", {}).get("language", "auto")[:2]
    cmd = [sys.executable, str(WRITING_GATE), "--json", "--lang", lang if lang in ("en", "fr") else "auto"]
    if brand_path and brand_path.parent.name == "project-context":
        cmd += ["--project", str(brand_path.parent.parent)]
    r = subprocess.run(cmd + [str(tmp)], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        issues.append(Issue("warning", "copy-gate-failed", str(WRITING_GATE), (r.stderr or r.stdout)[:200]))
        return {"ran": False}
    counts = {"BLOCK": 0, "WARN": 0}
    for f in data.get("files", []):
        for hit in f.get("findings", []):
            if "dash" in str(hit.get("code", "")):
                continue  # already reported by deckspec (code "dash")
            lvl = "error" if hit.get("level") == "BLOCK" else "warning"
            counts["BLOCK" if lvl == "error" else "WARN"] += 1
            line = hit.get("line", 0)
            loc = where.get(line) or where.get(max([k for k in where if k <= line] or [0]), "$")
            issues.append(Issue(lvl, f"copy:{hit.get('code')}", loc, f"\"{hit.get('match', '')}\": {hit.get('message', '')}"))
    tmp.unlink(missing_ok=True)
    return {"ran": True, **counts}


def write_report(out_dir: Path, info: Dict[str, Any], issues: List[Issue], deck_path: Path, brand_file: Optional[str]) -> Dict[str, Any]:
    rep = {
        "deck": str(deck_path),
        "brand": brand_file,
        **info,
        "errors": [i.to_dict() for i in issues if i.level == "error"],
        "warnings": [i.to_dict() for i in issues if i.level == "warning"],
    }
    (out_dir / "build-report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return rep


def load_deck(deck_path: Path) -> Tuple[Optional[Dict[str, Any]], List[Issue]]:
    try:
        deck = deckspec.load_json(deck_path)
    except Exception as e:  # noqa: BLE001
        return None, [Issue("error", "json", str(deck_path), f"deck.json does not parse: {e}")]
    issues = deckspec.validate_deck(deck)
    if not isinstance(deck, dict) or not isinstance(deck.get("meta"), dict) or not isinstance(deck.get("slides"), list):
        return None, issues
    return deck, issues


def resolve_brand_path(deck: Dict[str, Any], deck_path: Path, cli: Optional[str]) -> Optional[Path]:
    if cli:
        return Path(cli).resolve()
    if deck["meta"].get("brand"):
        return (deck_path.parent / deck["meta"]["brand"]).resolve()
    return None


def build_deck(deck_path: Path, out_dir: Path, direction: Optional[str] = None, brand_cli: Optional[str] = None,
               debug: bool = False) -> Dict[str, Any]:
    deck, issues = load_deck(deck_path)
    if deck is None:
        out_dir.mkdir(parents=True, exist_ok=True)
        return write_report(out_dir, {"fatal": True}, issues, deck_path, None)
    did = direction or deck["meta"].get("direction", "editorial-paper")
    dconf = deckspec.load_json(DIRECTIONS_DIR / did / "direction.json") if (DIRECTIONS_DIR / did / "direction.json").exists() else {}
    issues += deckspec.lint_deck(deck, dconf)
    bpath = resolve_brand_path(deck, deck_path, brand_cli)
    brand = load_brand(bpath, issues)
    info = build_html(deck, deck_path.parent, out_dir, did, brand, issues, debug)
    info["copy_gate"] = copy_gate(deck, bpath, out_dir, issues)
    return write_report(out_dir, info, issues, deck_path, str(bpath) if bpath else None)


# --------------------------------------------------------------------------
# Covers mode
# --------------------------------------------------------------------------

def build_covers(deck_path: Path, out_dir: Path, directions: Optional[List[str]], brand_cli: Optional[str]) -> Dict[str, Any]:
    deck, issues = load_deck(deck_path)
    if deck is None:
        raise SystemExit("deck.json does not parse; fix it before --covers.")
    cover_idx = next((i for i, s in enumerate(deck["slides"]) if isinstance(s, dict) and s.get("role") == "cover"), 0)
    cover = deck["slides"][cover_idx]
    tblock = next((b for b in cover.get("blocks", []) if b.get("type") == "title"), None)
    covers = deck["meta"].get("covers") or {}
    hooks = covers.get("hooks") or ([{"id": "a", "title": tblock["text"], "accent": tblock.get("accent"), "sub": tblock.get("sub")}] if tblock else [])
    dirs = directions or [deck["meta"]["direction"]]
    bpath = resolve_brand_path(deck, deck_path, brand_cli)
    manifest: Dict[str, Any] = {"deck": str(deck_path), "variants": []}
    for did in dirs:
        dconf = deckspec.load_json(DIRECTIONS_DIR / did / "direction.json")
        lays = covers.get("layouts") or dconf.get("cover_layouts") or ["cover-a"]
        lays = [l for l in lays if l in dconf.get("layouts", {})] or (dconf.get("cover_layouts") or ["cover-a"])[:1]
        variant_deck = copy.deepcopy(deck)
        variant_deck["meta"]["direction"] = did
        slides = []
        for k, hook in enumerate(hooks):
            hid = hook.get("id") or chr(97 + k)
            for lay in lays:
                s = copy.deepcopy(cover)
                s["layout"] = lay
                s["id"] = f"{did}--{hid}--{lay}"
                for b in s["blocks"]:
                    if b.get("type") == "title":
                        b["text"] = hook["title"]
                        b.pop("accent", None)
                        b.pop("sub", None)
                        if hook.get("accent") and hook["accent"] in hook["title"]:
                            b["accent"] = hook["accent"]
                        if hook.get("sub"):
                            b["sub"] = hook["sub"]
                slides.append(s)
                manifest["variants"].append({"id": s["id"], "direction": did, "hook": hid, "layout": lay})
        variant_deck["slides"] = slides
        vissues: List[Issue] = []
        brand = load_brand(bpath, vissues)
        info = build_html(variant_deck, deck_path.parent, out_dir / "covers" / did / "html", did, brand, vissues)
        write_report(out_dir / "covers" / did / "html", info, vissues, deck_path, str(bpath) if bpath else None)
    (out_dir / "covers").mkdir(parents=True, exist_ok=True)
    (out_dir / "covers" / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", nargs="?", help="Path to deck.json")
    ap.add_argument("--out", help="Output dir (default <deck dir>/html)")
    ap.add_argument("--direction", help="Override meta.direction")
    ap.add_argument("--brand", help="Path to brand.json (overrides meta.brand)")
    ap.add_argument("--covers", action="store_true", help="Build cover variants (hooks x layouts) per direction")
    ap.add_argument("--directions", help="Comma-separated directions for --covers (default: the deck's)")
    ap.add_argument("--list-directions", action="store_true")
    ap.add_argument("--debug", action="store_true", help="Outline fit failures in the HTML")
    args = ap.parse_args()
    if args.list_directions:
        for d in list_directions():
            conf = deckspec.load_json(DIRECTIONS_DIR / d / "direction.json")
            print(f"{d:18s} {conf.get('summary', '')}")
        return 0
    if not args.deck:
        ap.error("deck.json path required")
    deck_path = Path(args.deck).resolve()
    out_dir = Path(args.out).resolve() if args.out else deck_path.parent / "html"
    if args.covers:
        dirs = [d.strip() for d in args.directions.split(",")] if args.directions else None
        m = build_covers(deck_path, out_dir, dirs, args.brand)
        print(f"covers: {len(m['variants'])} variants in {out_dir / 'covers'}")
        return 0
    rep = build_deck(deck_path, out_dir, args.direction, args.brand, args.debug)
    if rep.get("fatal"):
        for e in rep["errors"]:
            print(f"ERROR {e['code']} {e['where']}: {e['message']}", file=sys.stderr)
        return 2
    for e in rep["errors"]:
        print(f"ERROR {e['code']} {e['where']}: {e['message']}")
    for w in rep["warnings"]:
        print(f"warn  {w['code']} {w['where']}: {w['message']}")
    print(f"build: {len(rep['slides'])} slides, direction {rep['direction']}, {rep['width']}x{rep['height']} -> {out_dir / 'index.html'}")
    return 1 if rep["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
