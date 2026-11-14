#!/usr/bin/env python3
"""
article_visuals.py

Article visuals in the brand of the company: one cover (1200x630) and the
body visuals of one article (1200 wide, height from the content), built from
HTML, CSS and inline SVG templates (assets/visuals/) driven by brand.json,
rendered to PNG by a local Chromium (Playwright), optionally written as
standalone SVG. The model writes the spec (every visible word); this script
only typesets, renders and measures. No network, no API, no generated image.

    python3 scripts/article_visuals.py --spec visuals-spec.json \\
        --brand <project>/project-context/brand.json \\
        --out-dir <article dir>/visuals [--format png|svg|both] [--scale 2] \\
        [--no-render] [--json]
    python3 scripts/article_visuals.py qa --out-dir <article dir>/visuals [--json]

Spec: assets/visuals-spec.schema.json. Kinds: cover, comparison, steps,
checklist, stat, timeline, decision (data per kind in
skills/rendering-article-visuals/SKILL.md).

Writes, in --out-dir:
  cover.png, <id>.png             PNG at --scale (2 gives 2400 px wide)
  cover.svg, <id>.svg             --format svg|both, kinds cover, stat,
                                  steps, checklist, comparison (timeline and
                                  decision stay PNG: their layout needs the
                                  browser)
  visuals.json                    manifest for the assembly step, paths
                                  relative to the article folder (the parent
                                  of --out-dir), sizes in CSS px
                                  (assets/visuals-manifest.schema.json);
                                  written only when every listed file exists
  visuals-qa.json                 every check with its level
  _src/<id>.html, _src/fonts/     the built pages, kept for the review loop

Checks (BLOCK fails the run, WARN is listed):
  spec      schema, data keys of each kind, counts, decision depth, unique
            ids, alt and after_h2 not empty (bad spec: exit 2, nothing built)
  brand     WCAG contrast of every text role on the surfaces it is set on,
            computed from brand.json with the fallbacks of
            shared/schemas/README.md: BLOCK under 3:1, WARN under the AA
            threshold (4.5:1, 3:1 for large text); icons and accents under
            3:1 against the surface: WARN
  DOM       (Chromium, after document.fonts.ready and the fit) a text that
            does not fit at its minimum size, a word wider than its box, a
            cover that overflows, text outside the canvas, text under 20 px
            (18 px for sources), contrast measured on the page, brand font
            not loaded (WARN), body visual taller than 2000 px
  PNG       exact size (cover 1200x630 x scale), weight, flat bands (an
            unrasterised tile: BLOCK; empty band over 30 % of the height:
            WARN), as in agents/carousel-builder/scripts/render.py
  SVG       parses as XML (xml.etree)

`qa` re-runs the file checks on an existing folder (manifest against its
schema, files present, sizes, alt, weight, flat bands, SVG parse) and carries
the render-time BLOCKs of visuals-qa.json.

Dependencies: Python 3.9+ standard library for the spec, the brand checks,
the HTML and the SVG. Rendering needs Playwright with Chromium
(pip install playwright && python3 -m playwright install chromium); the PNG
checks use Pillow when installed. Without Playwright the HTML (and SVG) are
written, the run exits 1 with the install line; --no-render skips the PNG on
purpose (exit 0, no manifest unless every visual has its SVG).

Exit codes: 0 written and no BLOCK; 1 at least one BLOCK, or the renderer is
missing or failed; 2 usage error, unreadable or invalid spec, unreadable
brand.json.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE.parent
REPO_ROOT = AGENT_DIR.parent.parent
TEMPLATES = AGENT_DIR / "assets" / "visuals"
SPEC_SCHEMA = AGENT_DIR / "assets" / "visuals-spec.schema.json"
MANIFEST_SCHEMA = AGENT_DIR / "assets" / "visuals-manifest.schema.json"
BRAND_SCHEMA = REPO_ROOT / "shared" / "schemas" / "brand.schema.json"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"

W = 1200
COVER_H = 630
PAD = 64
MIN_TEXT = 20
MIN_META = 18
MAX_BODY_H = 2000
MIN_BODY_H = 240
FIT_TIMEOUT_MS = 30000
# PNG weight per CSS pixel area at scale 1; multiplied by scale^2.
PNG_WARN_KB = 450
PNG_BLOCK_KB = 1600
SVG_KINDS = ("cover", "stat", "steps", "checklist", "comparison")
KINDS = ("comparison", "steps", "checklist", "stat", "timeline", "decision")

NBSP = " "
NNBSP = " "

I18N = {
    "en": {"source": "Source", "yes": "Yes", "no": "No", "partial": "Partly", "check": "Done", "warn": "Watch", "cross": "Avoid"},
    "fr": {"source": "Source", "yes": "Oui", "no": "Non", "partial": "En partie", "check": "Fait", "warn": "Attention", "cross": "À éviter"},
    "es": {"source": "Fuente", "yes": "Sí", "no": "No", "partial": "En parte", "check": "Hecho", "warn": "Atención", "cross": "Evitar"},
    "de": {"source": "Quelle", "yes": "Ja", "no": "Nein", "partial": "Teilweise", "check": "Erledigt", "warn": "Achtung", "cross": "Vermeiden"},
}

# Data keys of each kind: (required, optional).
KIND_KEYS = {
    "comparison": ({"columns", "rows"}, {"corner", "highlight"}),
    "steps": ({"steps"}, {"layout"}),
    "checklist": ({"items"}, {"layout"}),
    "stat": ({"stats"}, set()),
    "timeline": ({"events"}, set()),
    "decision": ({"question", "yes", "no"}, {"yes_label", "no_label"}),
}
KIND_COUNTS = {"comparison": ("rows", 2, 8), "steps": ("steps", 3, 7), "checklist": ("items", 4, 10),
               "stat": ("stats", 1, 3), "timeline": ("events", 3, 8)}
LAYOUTS = {"steps": {"auto", "vertical", "horizontal"}, "checklist": {"auto", "one-column", "two-columns"}}
CELL_TOKENS = ("yes", "no", "partial")


def issue(level: str, code: str, where: str, message: str, **extra: Any) -> Dict[str, Any]:
    d = {"level": level, "code": code, "where": where, "message": message}
    d.update(extra)
    return d


def tr(lang: str, key: str) -> str:
    return I18N.get((lang or "en")[:2], I18N["en"]).get(key, I18N["en"][key])


# --------------------------------------------------------------------------
# Colours (same maths as agents/static-ads-builder/scripts/build.py, copied
# because that module imports the ads spec on load)
# --------------------------------------------------------------------------

RGB = Tuple[float, float, float]
WHITE: RGB = (255.0, 255.0, 255.0)
BLACK: RGB = (0.0, 0.0, 0.0)


def parse_hex(c: Any, under: Optional[RGB] = None) -> Optional[RGB]:
    """#rgb, #rrggbb or #rrggbbaa; alpha is flattened against `under`."""
    if not isinstance(c, str):
        return None
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", c.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    rgb = tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    if len(h) == 8:
        a = int(h[6:8], 16) / 255
        base = under or WHITE
        rgb = tuple(rgb[i] * a + base[i] * (1 - a) for i in range(3))
    return rgb  # type: ignore


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


# --------------------------------------------------------------------------
# brand.json
# --------------------------------------------------------------------------

def _validator():
    if not (SHARED_SCRIPTS / "validate_json.py").exists():
        return None
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    try:
        from validate_json import validate  # type: ignore
        return validate
    except Exception:  # noqa: BLE001
        return None


def _v1_family(stack: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(stack, str) or not stack.strip():
        return None, None
    parts = [p.strip() for p in stack.split(",")]
    return parts[0].strip("'\" ") or None, ", ".join(parts[1:]) or None


def v1_to_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a V1 brand.json (no schema_version) with the table of
    shared/schemas/README.md."""
    bg = raw.get("bg")
    out: Dict[str, Any] = {"name": raw.get("name") or raw.get("logo_text") or "",
                           "colors": {k2: raw[k1] for k1, k2 in (("bg", "bg"), ("text_primary", "text"), ("accent", "accent"),
                                                                ("accent_secondary", "accent_secondary"), ("text_secondary", "text_secondary"),
                                                                ("text_muted", "text_muted"), ("card_bg", "surface"), ("card_border", "border"))
                                      if raw.get(k1)},
                           "fonts": {}, "logos": {}}
    for k1, role in (("font_heading", "display"), ("font_body", "body")):
        fam, fb = _v1_family(raw.get(k1))
        if fam:
            out["fonts"][role] = {"family": fam, "fallback": fb} if fb else {"family": fam}
    if raw.get("card_radius"):
        out["radius"] = raw["card_radius"]
    if raw.get("logo_text"):
        out["logo_text"] = raw["logo_text"]
    lp = raw.get("logo_path") or (raw.get("assets") or {}).get("logo_path")
    pbg = parse_hex(bg)
    out["mode"] = "dark" if pbg and lum(pbg) < 0.18 else "light"
    if isinstance(lp, str) and lp:
        lp = lp[len("project-context/"):] if lp.startswith("project-context/") else lp
        fmt = lp.rsplit(".", 1)[-1].lower() if "." in lp else "svg"
        out["logos"]["on_" + out["mode"]] = {"wordmark": {"path": lp, "format": fmt}}
    return out


def load_brand(path: Path, font_cache: Optional[Path] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Resolved brand: colour roles with fallbacks and derived roles, fonts,
    logo choice. With font_cache, a Google Fonts role without files gets its
    latin woff2 faces downloaded there (shared/scripts/fetch_fonts.py);
    brand.json is never written. Raises ValueError when the file cannot be read."""
    issues: List[Dict[str, Any]] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"brand.json unreadable: {e}")
    if not isinstance(raw, dict):
        raise ValueError("brand.json is not an object")
    base = path.resolve().parent
    if raw.get("schema_version") == "2.0":
        validate = _validator()
        if validate and BRAND_SCHEMA.exists():
            for err in validate(raw, json.loads(BRAND_SCHEMA.read_text(encoding="utf-8")))[:6]:
                issues.append(issue("WARN", "brand-schema", "brand.json", str(err)))
        v2 = raw
    else:
        issues.append(issue("WARN", "brand-v1", "brand.json", "V1 brand.json (no schema_version): mapped with shared/schemas/README.md."))
        v2 = v1_to_v2(raw)

    col = v2.get("colors") or {}
    roles: Dict[str, RGB] = {}
    bg = parse_hex(col.get("bg"))
    if bg is None:
        issues.append(issue("WARN", "brand-color-missing", "colors.bg", "No usable colors.bg: white used."))
        bg = WHITE
    roles["bg"] = bg
    for key, default in (("text", None), ("accent", None)):
        c = parse_hex(col.get(key), bg)
        if c is None:
            c = (BLACK if lum(bg) > 0.18 else WHITE) if key == "text" else (47.0, 91.0, 234.0)
            issues.append(issue("WARN", "brand-color-missing", f"colors.{key}", f"No usable colors.{key}: {to_hex(c)} used."))
        roles[key] = c
    # Fallbacks, in the order of shared/schemas/README.md.
    roles["text_secondary"] = parse_hex(col.get("text_secondary"), bg) or roles["text"]
    roles["text_muted"] = parse_hex(col.get("text_muted"), bg) or roles["text_secondary"]
    roles["surface"] = parse_hex(col.get("surface"), bg) or bg
    roles["border"] = parse_hex(col.get("border"), bg) or roles["text_muted"]
    roles["accent_secondary"] = parse_hex(col.get("accent_secondary"), bg) or roles["accent"]
    roles["on_accent"] = parse_hex(col.get("on_accent"), roles["accent"]) or max((WHITE, BLACK), key=lambda t: contrast(t, roles["accent"]))
    mode = v2.get("mode") if v2.get("mode") in ("dark", "light") else ("dark" if lum(bg) < 0.18 else "light")
    # Derived roles: accent used as text only where it holds 3:1 (large
    # text), a tint of the accent for highlighted cells and outcomes.
    acc = roles["accent"]
    if contrast(acc, bg) >= 3 and contrast(acc, roles["surface"]) >= 3:
        roles["accent_ink"] = acc
    else:
        roles["accent_ink"] = roles["text"]
        issues.append(issue("INFO", "accent-ink", "colors.accent",
                            f"accent {to_hex(acc)} holds {contrast(acc, bg):.2f}:1 on bg: figures, dates and kickers use colors.text, the accent stays on badges, bars and icons."))
    roles["accent_tint"] = mix(roles["surface"], acc, 0.22 if mode == "dark" else 0.12)
    roles["text_on_tint"] = roles["text"] if contrast(roles["text"], roles["accent_tint"]) >= 4.5 else max(
        (roles["text"], WHITE, BLACK), key=lambda t: contrast(t, roles["accent_tint"]))

    radius = v2.get("radius")
    radius = radius if isinstance(radius, str) and re.fullmatch(r"0|[0-9]+(\.[0-9]+)?(px|rem|em|%)", radius) else "0"

    fonts = v2.get("fonts") or {}
    font: Dict[str, Any] = {"faces": []}
    for role, generic in (("display", "Georgia, serif"), ("body", "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif")):
        f = fonts.get(role) or (fonts.get("body") if role == "display" else None) or {}
        fam = f.get("family") if isinstance(f.get("family"), str) and f.get("family") else None
        font[role] = fam
        font[role + "_fallback"] = f.get("fallback") or (generic if role == "body" or not fonts.get("body") else (fonts["body"].get("fallback") or generic))
        ws = sorted(w for w in (f.get("weights") or []) if isinstance(w, int))
        font[role + "_weights"] = ws
        for fl in f.get("files") or []:
            p = resolve_asset(base, fl.get("path"))
            if not p:
                issues.append(issue("WARN", "brand-asset-missing", f"fonts.{role}.files", f"{fl.get('path')} not found: the {role} family falls back to the system."))
                continue
            font["faces"].append({"family": fam, "path": p, "weight": fl.get("weight", 400), "style": fl.get("style", "normal"),
                                  "format": fl.get("format") or {"woff2": "woff2", "woff": "woff", "ttf": "truetype", "otf": "opentype"}.get(p.suffix.lower().lstrip("."), "truetype")})
        if fam and not any(fc["family"] == fam for fc in font["faces"]):
            fetched = fetch_google_role(f, fam, fonts.get("fonts_url"), font_cache, issues, role)
            font["faces"].extend(fetched)
            if not fetched and fonts.get("fonts_url"):
                issues.append(issue("INFO", "fonts-url-ignored", f"fonts.{role}",
                                    f"\"{fam}\" has no files and was not fetched: the family is used when installed, else the fallback stack. "
                                    "Run shared/scripts/fetch_fonts.py on brand.json to keep the files."))
    dw = font["display_weights"]
    font["display_weight"] = max([w for w in dw if w <= 700] or [dw[0]]) if dw else 700
    bw = font["body_weights"]
    font["body_strong"] = max([w for w in bw if w <= 700] or [bw[-1]]) if bw else 600

    name = v2.get("name") or v2.get("logo_text") or ""
    logo = pick_logo(v2, roles, mode, base, name, issues)
    brand = {"name": name, "mode": mode, "roles": roles, "hex": {k: to_hex(v) for k, v in roles.items()}, "radius": radius,
             "font": font, "logo": logo, "file": str(path)}
    return brand, issues


def fetch_google_role(f: Dict[str, Any], fam: str, fonts_url: Optional[str], cache: Optional[Path],
                      issues: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
    """Latin woff2 faces of a Google Fonts family, downloaded into cache once."""
    if cache is None:
        return []
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    try:
        import fetch_fonts  # type: ignore
    except Exception:  # noqa: BLE001
        return []
    if not fetch_fonts.is_google(f, fonts_url):
        return []
    weights = [w for w in (f.get("weights") or []) if isinstance(w, int)] or [400, 700]
    files, warns = fetch_fonts.fetch_role_files(fam, weights, cache, "")
    for w in warns:
        issues.append(issue("WARN", "font-fetch", f"fonts.{role}", w))
    if files:
        issues.append(issue("INFO", "font-fetched", f"fonts.{role}",
                            f"\"{fam}\" downloaded from Google Fonts into {cache.name}/ ({len({x['path'] for x in files})} files). "
                            "Run shared/scripts/fetch_fonts.py on brand.json to keep them with the brand."))
    return [{"family": fam, "path": cache / x["path"], "weight": x["weight"], "style": x["style"], "format": x["format"]} for x in files]


def resolve_asset(base: Path, p: Any) -> Optional[Path]:
    """A brand path is relative to project-context/ (the folder of
    brand.json); a V1 path may still carry the project-context/ prefix."""
    if not isinstance(p, str) or not p:
        return None
    cand = Path(p)
    if cand.is_absolute():
        return cand if cand.is_file() else None
    for root in (base, base.parent):
        q = (root / p).resolve()
        if q.is_file():
            return q
    return None


def pick_logo(v2: Dict[str, Any], roles: Dict[str, RGB], mode: str, base: Path, name: str,
              issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """logos.on_<mode> first (wordmark, then mark with the name typeset),
    the other variant only when its ink holds 3:1 on bg, else logo_text."""
    logos = v2.get("logos") or {}
    failed = {(c.get("variant"), c.get("kind")) for c in ((v2.get("logo_audit") or {}).get("checks") or []) if c.get("status") == "fail"}
    want = "on_dark" if mode == "dark" else "on_light"
    other = "on_light" if want == "on_dark" else "on_dark"
    text = v2.get("logo_text") or name
    for variant in (want, other):
        v = logos.get(variant) or {}
        if variant == other and v:
            ink = next((parse_hex((v.get(k) or {}).get("ink")) for k in ("wordmark", "mark") if parse_hex((v.get(k) or {}).get("ink"))), None)
            if not ink or contrast(ink, roles["bg"]) < 3:
                issues.append(issue("INFO", "logo-variant", f"logos.{variant}",
                                    f"No {want} logo; {variant} skipped: its ink {'is unknown' if not ink else 'holds %.2f:1 on bg' % contrast(ink, roles['bg'])}."))
                continue
        for kind in ("wordmark", "mark"):
            f = v.get(kind) or {}
            if not f.get("path"):
                continue
            if (variant, kind) in failed:
                issues.append(issue("WARN", "logo-audit-fail", f"logos.{variant}.{kind}", "Failed the brand logo audit: not used."))
                continue
            p = resolve_asset(base, f["path"])
            if not p:
                issues.append(issue("WARN", "brand-asset-missing", f"logos.{variant}.{kind}", f"{f['path']} not found."))
                continue
            fmt = (f.get("format") or p.suffix.lstrip(".")).lower()
            return {"kind": kind, "variant": variant, "path": p, "format": fmt, "text": text if kind == "mark" else None,
                    "width": f.get("width"), "height": f.get("height")}
    if text:
        issues.append(issue("INFO", "logo-text", "logos", f"No usable logo file: \"{text}\" is typeset in the display font."))
    return {"kind": "text", "variant": None, "path": None, "format": None, "text": text}


def brand_contrast(brand: Dict[str, Any]) -> List[Dict[str, Any]]:
    """WCAG ratios of the role pairs the templates use. Text: BLOCK under
    3:1, WARN under its AA threshold. Graphics (icons, bars): WARN under 3:1."""
    r = brand["roles"]
    pairs = [
        ("text", "bg", 4.5, "titles and body text"),
        ("text", "surface", 4.5, "text in cards and tables"),
        ("text_secondary", "surface", 4.5, "step and event descriptions"),
        ("text_secondary", "bg", 4.5, "step and event descriptions"),
        ("text_muted", "bg", 4.5, "sources and table corner (18 to 20 px)"),
        ("text_muted", "surface", 4.5, "sources in stat cards"),
        ("on_accent", "accent", 3.0, "step numbers and the highlighted column header (large text)"),
        ("accent_ink", "bg", 3.0, "kicker, dates and figures (large text)"),
        ("accent_ink", "surface", 3.0, "figures in stat cards (large text)"),
        ("text_on_tint", "accent_tint", 4.5, "highlighted cells and decision outcomes"),
    ]
    out = []
    for fg, bgk, need, use in pairs:
        ratio = contrast(r[fg], r[bgk])
        rec = {"fg": fg, "bg": bgk, "ratio": round(ratio, 2), "need": need}
        if ratio < 3:
            out.append(issue("BLOCK", "brand-contrast", f"colors.{fg} on colors.{bgk}",
                             f"{brand['hex'][fg]} on {brand['hex'][bgk]} is {ratio:.2f}:1 ({use}); unreadable under 3:1. Fix the role in brand.json (project-context).", **rec))
        elif ratio < need:
            out.append(issue("WARN", "brand-contrast", f"colors.{fg} on colors.{bgk}",
                             f"{brand['hex'][fg]} on {brand['hex'][bgk]} is {ratio:.2f}:1 ({use}), under WCAG AA {need}:1.", **rec))
    for g, bgk in (("accent", "surface"), ("accent", "bg")):
        ratio = contrast(r[g], r[bgk])
        if ratio < 3:
            out.append(issue("WARN", "brand-contrast-graphic", f"colors.{g} on colors.{bgk}",
                             f"{brand['hex'][g]} on {brand['hex'][bgk]} is {ratio:.2f}:1: icons, bars and borders in the accent read weakly (WCAG 1.4.11 asks 3:1).",
                             fg=g, bg=bgk, ratio=round(ratio, 2), need=3.0))
    return out


# --------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------

def _blank(s: Any) -> bool:
    return not isinstance(s, str) or not s.strip()


def validate_spec(spec: Any) -> List[Dict[str, Any]]:
    """Schema (shared validator) plus the rules the schema subset cannot say.
    Every item is a BLOCK: a bad spec builds nothing."""
    out: List[Dict[str, Any]] = []
    if not isinstance(spec, dict):
        return [issue("BLOCK", "spec-invalid", "$", "The spec is not a JSON object.")]
    validate = _validator()
    if validate:
        for err in validate(spec, json.loads(SPEC_SCHEMA.read_text(encoding="utf-8"))):
            out.append(issue("BLOCK", "spec-schema", "$", str(err)))
    cover = spec.get("cover")
    if not isinstance(cover, dict):
        out.append(issue("BLOCK", "spec-invalid", "cover", "cover is required."))
    else:
        for k in ("title", "alt"):
            if _blank(cover.get(k)):
                out.append(issue("BLOCK", "spec-empty", f"cover.{k}", f"cover.{k} is empty."))
    body = spec.get("body")
    if not isinstance(body, list):
        out.append(issue("BLOCK", "spec-invalid", "body", "body must be a list (it may be empty)."))
        return out
    seen = set()
    for i, v in enumerate(body):
        at = f"body[{i}]"
        if not isinstance(v, dict):
            out.append(issue("BLOCK", "spec-invalid", at, "A body visual is an object."))
            continue
        vid, kind = v.get("id"), v.get("kind")
        at = f"body[{i}] {vid}"
        if not isinstance(vid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", vid) or vid == "cover":
            out.append(issue("BLOCK", "spec-id", at, "id: lowercase letters, digits and hyphens, not 'cover'."))
        elif vid in seen:
            out.append(issue("BLOCK", "spec-id", at, f"id {vid} is used twice."))
        seen.add(vid)
        for k in ("title", "alt", "after_h2"):
            if _blank(v.get(k)):
                out.append(issue("BLOCK", "spec-empty", f"{at}.{k}", f"{k} is empty."))
        if kind not in KIND_KEYS:
            out.append(issue("BLOCK", "spec-kind", at, f"kind must be one of {', '.join(KINDS)}."))
            continue
        data = v.get("data")
        if not isinstance(data, dict):
            out.append(issue("BLOCK", "spec-invalid", f"{at}.data", "data is an object."))
            continue
        req, opt = KIND_KEYS[kind]
        for k in sorted(req - set(data)):
            out.append(issue("BLOCK", "spec-data", f"{at}.data.{k}", f"{kind} needs data.{k}."))
        for k in sorted(set(data) - req - opt):
            out.append(issue("BLOCK", "spec-data", f"{at}.data.{k}", f"data.{k} is not a {kind} key (keys: {', '.join(sorted(req | opt))})."))
        if kind in KIND_COUNTS:
            key, lo, hi = KIND_COUNTS[kind]
            seq = data.get(key)
            if isinstance(seq, list) and not lo <= len(seq) <= hi:
                out.append(issue("BLOCK", "spec-count", f"{at}.data.{key}", f"{kind} takes {lo} to {hi} {key}, got {len(seq)}."))
        if kind in LAYOUTS and "layout" in data and data["layout"] not in LAYOUTS[kind]:
            out.append(issue("BLOCK", "spec-data", f"{at}.data.layout", f"{kind} layout: {', '.join(sorted(LAYOUTS[kind]))}."))
        if kind == "comparison":
            cols = data.get("columns") if isinstance(data.get("columns"), list) else []
            for j, row in enumerate(data.get("rows") or []):
                if isinstance(row, dict) and isinstance(row.get("cells"), list) and len(row["cells"]) != len(cols):
                    out.append(issue("BLOCK", "spec-data", f"{at}.data.rows[{j}]", f"{len(row['cells'])} cells for {len(cols)} columns."))
            hl = data.get("highlight")
            if isinstance(hl, int) and not 0 <= hl < len(cols):
                out.append(issue("BLOCK", "spec-data", f"{at}.data.highlight", f"highlight {hl} is not a column index (0 to {len(cols) - 1})."))
        if kind == "stat":
            for j, s in enumerate(data.get("stats") or []):
                if isinstance(s, dict) and _blank(s.get("source")):
                    out.append(issue("BLOCK", "stat-source", f"{at}.data.stats[{j}]", "Every figure names its source (cited in the article or positioning.proof)."))
        if kind == "decision":
            for side in ("yes", "no"):
                out.extend(_check_branch(data.get(side), f"{at}.data.{side}"))
    return out


def _check_branch(b: Any, at: str) -> List[Dict[str, Any]]:
    if not isinstance(b, dict):
        return [issue("BLOCK", "spec-data", at, "A branch is an object: {outcome} or {question, yes, no}.")]
    has_o, has_q = not _blank(b.get("outcome")), not _blank(b.get("question"))
    if has_o == has_q:
        return [issue("BLOCK", "decision-branch", at, "A branch holds either an outcome or a question, not both and not neither.")]
    if has_o and ("yes" in b or "no" in b):
        return [issue("BLOCK", "decision-branch", at, "An outcome ends the branch: no yes or no under it.")]
    out = []
    if has_q:
        for side in ("yes", "no"):
            leaf = b.get(side)
            if not isinstance(leaf, dict) or _blank(leaf.get("outcome")) or set(leaf) - {"outcome"}:
                out.append(issue("BLOCK", "decision-depth", f"{at}.{side}", "The second question ends in two outcomes: two levels at most."))
    return out


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def typo(text: str, lang: str) -> str:
    """Escape, then keep a number with its unit and French punctuation with
    its word (same rules as agents/carousel-builder/scripts/blocks.py)."""
    s = " ".join(str(text).split())
    if (lang or "").startswith("fr"):
        s = re.sub(r"\s+([:;!?»])", NNBSP + r"\1", s)
        s = re.sub(r"«\s+", "«" + NNBSP, s)
    s = re.sub(r"(\d)\s+(%|s|min|h|k€|M€|€|\$|ans?|mois|jours?|days?|pages?|x)(?=[\s.,;:!?)]|$)", r"\1" + NBSP + r"\2", s)
    return esc(s)


def cell_token(cell: str) -> Tuple[Optional[str], str]:
    """'yes', 'no', 'partial', optionally followed by ': note'."""
    m = re.fullmatch(r"\s*(yes|no|partial)\s*(?::\s*(.*))?", cell or "", flags=re.I | re.S)
    if not m:
        return None, cell
    return m.group(1).lower(), (m.group(2) or "").strip()


def icon(state: str, hx: Dict[str, str], size: int = 32, label: str = "") -> str:
    """Inline SVG icon, literal colours (valid in HTML and in a standalone
    SVG). state: yes|check, no|cross, partial, warn."""
    a, on, muted, ink = hx["accent"], hx["on_accent"], hx["text_muted"], hx["accent_ink"]
    title = f"<title>{esc(label)}</title>" if label else ""
    if state in ("yes", "check"):
        body = (f'<circle cx="16" cy="16" r="15" fill="{a}"/>'
                f'<path d="M9.5 16.5 L14 21 L22.5 11.5" fill="none" stroke="{on}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    elif state in ("no", "cross"):
        body = (f'<circle cx="16" cy="16" r="14.5" fill="none" stroke="{muted}" stroke-width="2"/>'
                f'<path d="M11.5 11.5 L20.5 20.5 M20.5 11.5 L11.5 20.5" fill="none" stroke="{muted}" stroke-width="2.5" stroke-linecap="round"/>')
    elif state == "partial":
        body = (f'<circle cx="16" cy="16" r="14.5" fill="none" stroke="{a}" stroke-width="2"/>'
                f'<path d="M16 1.5 A14.5 14.5 0 0 0 16 30.5 Z" fill="{a}"/>')
    else:
        body = (f'<circle cx="16" cy="16" r="14.5" fill="none" stroke="{ink}" stroke-width="2.5"/>'
                f'<path d="M16 9 V18" stroke="{ink}" stroke-width="3" stroke-linecap="round"/><circle cx="16" cy="23" r="1.9" fill="{ink}"/>')
    return f'<svg class="ico" width="{size}" height="{size}" viewBox="0 0 32 32" role="img" aria-label="{esc(label)}">{title}{body}</svg>'


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

def read_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def fill(template: str, slots: Dict[str, str]) -> str:
    def rep(m: "re.Match[str]") -> str:
        k = m.group(1)
        if k not in slots:
            raise KeyError(f"template slot {{{{{k}}}}} not filled")
        return slots[k]
    return re.sub(r"\{\{(\w+)\}\}", rep, template)


def css_family(fam: Optional[str], fallback: str) -> str:
    return (f'"{fam}", ' if fam else "") + fallback


def root_css(brand: Dict[str, Any]) -> str:
    hx, f = brand["hex"], brand["font"]
    v = {
        "--bg": hx["bg"], "--surface": hx["surface"], "--text": hx["text"], "--text-secondary": hx["text_secondary"],
        "--text-muted": hx["text_muted"], "--border": hx["border"], "--accent": hx["accent"],
        "--accent-secondary": hx["accent_secondary"], "--on-accent": hx["on_accent"], "--radius": brand["radius"],
        "--accent-ink": hx["accent_ink"], "--accent-tint": hx["accent_tint"], "--text-on-tint": hx["text_on_tint"],
        "--font-display": css_family(f["display"], f["display_fallback"]), "--font-body": css_family(f["body"], f["body_fallback"]),
        "--display-weight": str(f["display_weight"]), "--body-strong": str(f["body_strong"]),
    }
    return ":root {\n" + "".join(f"  {k}: {val};\n" for k, val in v.items()) + "}"


def font_faces(brand: Dict[str, Any], src_dir: Path) -> str:
    out = []
    for face in brand["font"]["faces"]:
        if not face.get("family"):
            continue
        (src_dir / "fonts").mkdir(parents=True, exist_ok=True)
        dst = src_dir / "fonts" / face["path"].name
        if not dst.exists() or dst.stat().st_size != face["path"].stat().st_size:
            shutil.copyfile(face["path"], dst)
        out.append(f'@font-face {{ font-family: "{face["family"]}"; src: url("fonts/{dst.name}") format("{face["format"]}"); '
                   f'font-weight: {face["weight"]}; font-style: {face["style"]}; font-display: block; }}')
    return "\n".join(out)


def logo_svg_markup(path: Path) -> Optional[str]:
    try:
        svg = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None
    svg = re.sub(r"<\?xml[^>]*\?>|<!--.*?-->|<!DOCTYPE[^>]*>", "", svg, flags=re.S).strip()
    m = re.search(r"<svg\b[^>]*>", svg)
    if not m:
        return None
    head = m.group(0)
    new = re.sub(r'\s(width|height)="[^"]*"', "", head).replace("<svg", '<svg aria-hidden="true" focusable="false"', 1)
    return svg.replace(head, new, 1)


def data_uri(path: Path, fmt: str) -> str:
    mime = {"svg": "image/svg+xml", "png": "image/png", "webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(fmt, "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def logo_html(brand: Dict[str, Any]) -> str:
    lg = brand["logo"]
    parts = []
    if lg["path"]:
        markup = logo_svg_markup(lg["path"]) if lg["format"] == "svg" else None
        parts.append(markup or f'<img src="{data_uri(lg["path"], lg["format"])}" alt="">')
    if lg.get("text"):
        parts.append(f'<span class="logo-text">{esc(lg["text"])}</span>')
    if not parts:
        return ""
    return f'<div class="logo" data-where="logo" aria-label="{esc(brand["name"])}">{"".join(parts)}</div>'


def head_html(v: Dict[str, Any], lang: str) -> str:
    return (f'<header class="v-head"><h2 class="v-title tx" data-where="{esc(v["id"])}.title" data-fit data-fit-min="32" '
            f'data-fit-max="44" data-fit-lines="2" data-fit-order="1">{typo(v["title"], lang)}</h2></header>')


def foot_html(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> str:
    src = v.get("source")
    left = f'<p class="meta tx" data-where="{esc(v["id"])}.source">{esc(tr(lang, "source"))}{NNBSP if lang.startswith("fr") else ""}: {typo(src, lang)}</p>' if src else "<span></span>"
    right = logo_html(brand) if with_logo else ""
    if not src and not right:
        return ""
    return f'<footer class="v-foot">{left}{right}</footer>'


def build_cover(c: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> str:
    kicker = (f'<p class="cv-kicker tx" data-where="cover.kicker">{typo(c["kicker"], lang)}</p>' if c.get("kicker") else "")
    return fill(read_template("cover.html"), {"logo": logo_html(brand) if with_logo else "", "kicker": kicker,
                                              "title": typo(c["title"], lang)})


def build_comparison(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, hx = v["data"], brand["hex"]
    cols = d["columns"]
    hl = d.get("highlight")
    vid = esc(v["id"])
    colgroup = '<col style="width:30%">' + "".join('<col>' for _ in cols)
    heads = "".join(f'<th class="{"hi" if hl == j else ""}"><div class="tx" data-where="{vid}.columns[{j}]">{typo(c, lang)}</div></th>'
                    for j, c in enumerate(cols))
    rows = []
    for i, row in enumerate(d["rows"]):
        cells = []
        for j, cell in enumerate(row["cells"]):
            tok, note = cell_token(cell)
            cls = "c" + (" hi" if hl == j else "")
            where = f"{vid}.rows[{i}].cells[{j}]"
            if tok:
                n = f'<span class="cell-n tx" data-where="{where}">{typo(note, lang)}</span>' if note else ""
                inner = f'<div class="cell-i">{icon(tok, hx, 32, tr(lang, tok))}{n}</div>'
            else:
                inner = f'<div class="tx" data-where="{where}">{typo(cell, lang)}</div>'
            cells.append(f'<td class="{cls}">{inner}</td>')
        rows.append(f'<tr><td class="rl"><div class="tx" data-where="{vid}.rows[{i}].label">{typo(row["label"], lang)}</div></td>{"".join(cells)}</tr>')
    return {"cols": colgroup, "corner": typo(d.get("corner") or "", lang), "header_cells": heads, "rows": "".join(rows)}


def steps_layout(d: Dict[str, Any]) -> str:
    lay = d.get("layout", "auto")
    if lay == "auto":
        short = all(len(s.get("text") or "") <= 120 and len(s["title"]) <= 36 for s in d["steps"])
        lay = "horizontal" if len(d["steps"]) <= 4 and short else "vertical"
    return lay


def build_steps(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, vid = v["data"], esc(v["id"])
    lay = steps_layout(d)
    items = []
    for i, s in enumerate(d["steps"], 1):
        x = f'<p class="step-x tx" data-where="{vid}.steps[{i - 1}].text">{typo(s["text"], lang)}</p>' if s.get("text") else ""
        items.append(f'<li class="step"><span class="badge" aria-hidden="true">{i}</span><div class="step-c">'
                     f'<p class="step-t tx" data-where="{vid}.steps[{i - 1}].title">{typo(s["title"], lang)}</p>{x}</div></li>')
    return {"layout": "h" if lay == "horizontal" else "v", "n": str(len(d["steps"])), "steps": "".join(items)}


def checklist_columns(d: Dict[str, Any]) -> int:
    lay = d.get("layout", "auto")
    if lay == "two-columns":
        return 2
    if lay == "one-column":
        return 1
    return 2 if len(d["items"]) >= 6 and all(len(it["text"]) <= 60 for it in d["items"]) else 1


def build_checklist(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, vid, hx = v["data"], esc(v["id"]), brand["hex"]
    ncol = checklist_columns(d)
    n = len(d["items"])
    rows_per_col = (n + ncol - 1) // ncol
    items = []
    # Two columns fill column by column (reading order top to bottom).
    order = list(range(n))
    if ncol == 2:
        left, right = order[:rows_per_col], order[rows_per_col:]
        order = [x for pair in zip(left, right + [None] * (len(left) - len(right))) for x in pair if x is not None]
    for pos, k in enumerate(order):
        it = d["items"][k]
        state = it.get("state", "check")
        last_row = pos >= len(order) - ncol if ncol == 2 else pos == n - 1
        if ncol == 2 and n % 2 == 1:
            last_row = pos == len(order) - 1 or pos == len(order) - 2 and k < rows_per_col
        items.append(f'<li class="chk-i {state}{" last" if last_row else ""}">{icon(state, hx, 32, tr(lang, state))}'
                     f'<p class="chk-t tx" data-where="{vid}.items[{k}]">{typo(it["text"], lang)}</p></li>')
    return {"layout": "two" if ncol == 2 else "one", "items": "".join(items)}


STAT_MAX = {1: 160, 2: 120, 3: 96}


def build_stat(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, vid = v["data"], esc(v["id"])
    n = len(d["stats"])
    cards = []
    sep = (NNBSP if lang.startswith("fr") else "") + ": "
    for i, s in enumerate(d["stats"]):
        cards.append(f'<div class="stat"><p class="stat-v tx" data-where="{vid}.stats[{i}].value" data-fit data-fit-min="56" '
                     f'data-fit-max="{STAT_MAX[n]}" data-fit-lines="1" data-fit-order="2">{typo(s["value"], lang)}</p>'
                     f'<p class="stat-l tx" data-where="{vid}.stats[{i}].label">{typo(s["label"], lang)}</p>'
                     f'<p class="stat-s meta tx" data-where="{vid}.stats[{i}].source">{esc(tr(lang, "source"))}{sep}{typo(s["source"], lang)}</p></div>')
    return {"n": str(n), "stats": "".join(cards)}


def build_timeline(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, vid = v["data"], esc(v["id"])
    evs = []
    for i, e in enumerate(d["events"]):
        x = f'<p class="ev-x tx" data-where="{vid}.events[{i}].text">{typo(e["text"], lang)}</p>' if e.get("text") else ""
        evs.append(f'<li class="ev"><p class="ev-d tx" data-where="{vid}.events[{i}].date">{typo(e["date"], lang)}</p>'
                   f'<span class="ev-m" aria-hidden="true"></span><div><p class="ev-t tx" data-where="{vid}.events[{i}].title">{typo(e["title"], lang)}</p>{x}</div></li>')
    return {"events": "".join(evs)}


def build_decision(v: Dict[str, Any], brand: Dict[str, Any], lang: str) -> Dict[str, str]:
    d, vid = v["data"], esc(v["id"])
    yes_l, no_l = d.get("yes_label") or tr(lang, "yes"), d.get("no_label") or tr(lang, "no")

    def node(b: Dict[str, Any], at: str) -> str:
        if b.get("outcome"):
            return f'<div class="node o tx" data-where="{at}">{typo(b["outcome"], lang)}</div>'
        return f'<div class="node q tx" data-where="{at}.question">{typo(b["question"], lang)}</div>' + row(b, at)

    def row(b: Dict[str, Any], at: str) -> str:
        return ('<div class="br-row">'
                f'<div class="br yes"><span class="lbl">{typo(yes_l, lang)}</span>{node(b["yes"], at + ".yes")}</div>'
                f'<div class="br no"><span class="lbl">{typo(no_l, lang)}</span>{node(b["no"], at + ".no")}</div></div>')

    tree = f'<div class="node q tx" data-where="{vid}.question">{typo(d["question"], lang)}</div>' + row(d, vid)
    return {"tree": tree}


BUILDERS = {"comparison": build_comparison, "steps": build_steps, "checklist": build_checklist,
            "stat": build_stat, "timeline": build_timeline, "decision": build_decision}


def page_html(content: str, brand: Dict[str, Any], lang: str, title: str, faces: str) -> str:
    f = brand["font"]
    return fill(read_template("_page.html"), {
        "lang": esc(lang), "doc_title": esc(title), "font_faces": faces, "root_css": root_css(brand),
        "base_css": read_template("base.css"), "min_text": str(MIN_TEXT), "min_meta": str(MIN_META),
        "font_display": esc(f["display"] or ""), "font_body": esc(f["body"] or ""),
        "content": content, "visuals_js": read_template("visuals.js")})


def build_body_page(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool, faces: str) -> str:
    """Full page of one body visual: the kind template (assets/visuals/<kind>.html)
    with the common head and footer and the slots of its builder."""
    slots = BUILDERS[v["kind"]](v, brand, lang)
    slots.update({"head": head_html(v, lang), "foot": foot_html(v, brand, lang, with_logo)})
    return page_html(fill(read_template(f"{v['kind']}.html"), slots), brand, lang, v["title"], faces)


# --------------------------------------------------------------------------
# SVG (kinds whose layout is computable without a browser)
# --------------------------------------------------------------------------

def char_w(ch: str) -> float:
    """Advance width in em of a generic sans-serif, by character class.
    Deliberately a little wide so a wrapped line never runs out of its box."""
    if ch == " ":
        return 0.28
    if ch in "iljI!|.,:;'’`":
        return 0.27
    if ch in "frt()[]-/  ":
        return 0.37
    if ch in "mwMW@":
        return 0.88
    if ch.isdigit():
        return 0.6
    if ch.isupper():
        return 0.68
    return 0.56


def text_w(s: str, px: float, bold: bool = False) -> float:
    return sum(char_w(c) for c in s) * px * (1.06 if bold else 1.0) * 1.03


def wrap(s: str, px: float, width: float, bold: bool = False) -> List[str]:
    words = " ".join(str(s).split()).split(" ")
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and text_w(cand, px, bold) > width:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def xesc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def svg_french(s: str, lang: str) -> str:
    s = " ".join(str(s).split())
    if lang.startswith("fr"):
        s = re.sub(r"\s+([:;!?»])", NNBSP + r"\1", s)
    return s


class Svg:
    def __init__(self, brand: Dict[str, Any], lang: str):
        self.b, self.lang, self.hx, self.f = brand, lang, brand["hex"], brand["font"]
        self.parts: List[str] = []
        self.warn: List[str] = []
        m = re.match(r"(\d+(?:\.\d+)?)px", brand["radius"])
        self.r = min(float(m.group(1)), 40.0) if m else 0.0
        self.display = css_family(self.f["display"], self.f["display_fallback"]).replace('"', "'")
        self.body = css_family(self.f["body"], self.f["body_fallback"]).replace('"', "'")

    def rect(self, x: float, y: float, w: float, h: float, fill: str, stroke: Optional[str] = None, r: Optional[float] = None, sw: float = 1) -> None:
        rr = self.r if r is None else r
        s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rr:.1f}" fill="{fill}"{s}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str, w: float = 1) -> None:
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}"/>')

    def text(self, x: float, top: float, s: str, px: float, width: float, color: str, lh: float = 1.35, bold: bool = False,
             display: bool = False, anchor: str = "start", max_lines: int = 99) -> float:
        """Wrapped text whose first line box starts at `top`; returns the
        height used."""
        s = svg_french(s, self.lang)
        lines = wrap(s, px, width, bold)
        if len(lines) > max_lines:
            self.warn.append(f'"{s[:40]}" wraps on {len(lines)} lines in the SVG (max {max_lines}).')
        fam = self.display if display else self.body
        wt = self.f["display_weight"] if display else (self.f["body_strong"] if bold else 400)
        step = px * lh
        base = top + (step - px) / 2 + px * 0.8
        spans = "".join(f'<tspan x="{x:.1f}" y="{base + i * step:.1f}">{xesc(l)}</tspan>' for i, l in enumerate(lines))
        self.parts.append(f'<text font-family="{fam}" font-size="{px}" font-weight="{wt}" fill="{color}" text-anchor="{anchor}">{spans}</text>')
        return len(lines) * step

    def height_of(self, s: str, px: float, width: float, lh: float = 1.35, bold: bool = False) -> float:
        return len(wrap(svg_french(s, self.lang), px, width, bold)) * px * lh

    def logo(self, right: float, top: float, h: float) -> None:
        lg = self.b["logo"]
        x = right
        if lg.get("text"):
            px = h * 0.8
            tw = text_w(lg["text"], px)
            self.parts.append(f'<text x="{x:.1f}" y="{top + h * 0.78:.1f}" font-family="{self.display}" font-size="{px:.1f}" '
                              f'font-weight="{self.f["display_weight"]}" fill="{self.hx["text"]}" text-anchor="end">{xesc(lg["text"])}</text>')
            x -= tw + (12 if lg["path"] else 0)
        if lg["path"]:
            ar = logo_aspect(lg)
            w = h * ar
            self.parts.append(f'<image x="{x - w:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="xMaxYMid meet" '
                              f'href="{data_uri(lg["path"], lg["format"])}"/>')

    def logo_left(self, left: float, top: float, h: float) -> None:
        lg = self.b["logo"]
        x = left
        if lg["path"]:
            w = h * logo_aspect(lg)
            self.parts.append(f'<image x="{x:.1f}" y="{top:.1f}" width="{w:.1f}" height="{h:.1f}" preserveAspectRatio="xMinYMid meet" '
                              f'href="{data_uri(lg["path"], lg["format"])}"/>')
            x += w + 12
        if lg.get("text"):
            px = h * 0.8
            self.parts.append(f'<text x="{x:.1f}" y="{top + h * 0.78:.1f}" font-family="{self.display}" font-size="{px:.1f}" '
                              f'font-weight="{self.f["display_weight"]}" fill="{self.hx["text"]}">{xesc(lg["text"])}</text>')

    def doc(self, h: float, title: str, alt: str) -> str:
        faces = []
        for face in self.f["faces"]:
            if face.get("family"):
                mime = {"woff2": "font/woff2", "woff": "font/woff", "truetype": "font/ttf", "opentype": "font/otf"}.get(face["format"], "font/ttf")
                b64 = base64.b64encode(face["path"].read_bytes()).decode("ascii")
                faces.append(f"@font-face{{font-family:'{face['family']}';src:url(data:{mime};base64,{b64}) format('{face['format']}');"
                             f"font-weight:{face['weight']};font-style:{face['style']}}}")
        style = f"<style>{''.join(faces)}</style>" if faces else ""
        hh = int(round(h))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{hh}" viewBox="0 0 {W} {hh}" role="img" aria-labelledby="t d">'
                f'<title id="t">{xesc(title)}</title><desc id="d">{xesc(alt)}</desc>{style}'
                f'<rect width="{W}" height="{hh}" fill="{self.hx["bg"]}"/>' + "".join(self.parts) + "</svg>\n")


def logo_aspect(lg: Dict[str, Any]) -> float:
    if lg.get("width") and lg.get("height"):
        return float(lg["width"]) / float(lg["height"])
    if lg["format"] == "svg":
        try:
            m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', lg["path"].read_text(encoding="utf-8"))
            if m and float(m.group(2)):
                return float(m.group(1)) / float(m.group(2))
        except Exception:  # noqa: BLE001
            pass
    if lg["format"] == "png":
        dims = png_size(lg["path"].read_bytes())
        if dims:
            return dims[0] / dims[1]
    return 3.0


def svg_head(s: Svg, v: Dict[str, Any]) -> float:
    return PAD + s.text(PAD, PAD, v["title"], 44, 1040, s.hx["text"], lh=1.14, display=True, max_lines=2) + 40


def svg_foot(s: Svg, v: Dict[str, Any], y: float, with_logo: bool) -> float:
    if not v.get("source") and not with_logo:
        return y - 40 + PAD
    y += 0
    s.line(PAD, y, W - PAD, y, s.hx["border"])
    if v.get("source"):
        sep = (NNBSP if s.lang.startswith("fr") else "") + ": "
        s.text(PAD, y + 22, f'{tr(s.lang, "source")}{sep}{v["source"]}', MIN_META, 760, s.hx["text_muted"], lh=1.4)
    if with_logo:
        s.logo(W - PAD, y + 22, 30)
    return y + 22 + 30 + PAD


def svg_cover(c: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> Tuple[str, List[str]]:
    s = Svg(brand, lang)
    hx = s.hx
    s.parts.append(f'<g transform="translate({W - 260},{COVER_H - 260})" fill="none">'
                   f'<path d="M 260 20 A 240 240 0 0 0 20 260" stroke="{hx["border"]}" stroke-width="2"/>'
                   f'<path d="M 260 80 A 180 180 0 0 0 80 260" stroke="{hx["border"]}" stroke-width="2"/>'
                   f'<path d="M 260 140 A 120 120 0 0 0 140 260" stroke="{hx["accent"]}" stroke-width="8"/>'
                   f'<path d="M 260 200 A 60 60 0 0 0 200 260" stroke="{hx["border"]}" stroke-width="2"/></g>')
    if with_logo:
        s.logo_left(72, 64, 40)
    kicker_h = s.height_of(c["kicker"], 24, 860, 1.3, True) + 20 if c.get("kicker") else 0
    avail = COVER_H - 64 - 40 - 24 - 24 - 8 - 64 - kicker_h
    size = 48
    for px in range(84, 47, -2):
        lines = wrap(svg_french(c["title"], lang), px, 860)
        if len(lines) <= 4 and len(lines) * px * 1.08 <= avail:
            size = px
            break
    else:
        s.warn.append("cover title does not fit at 48 px in the SVG")
    block = kicker_h + len(wrap(svg_french(c["title"], lang), size, 860)) * size * 1.08
    top = 64 + 40 + (COVER_H - 64 - 40 - 8 - 64 - block) / 2
    if c.get("kicker"):
        s.text(72, top, c["kicker"], 24, 860, hx["accent_ink"], lh=1.3, bold=True)
        top += kicker_h
    s.text(72, top, c["title"], size, 860, hx["text"], lh=1.08, display=True)
    s.rect(72, COVER_H - 64 - 8, 96, 8, hx["accent"], r=min(s.r, 4))
    return s.doc(COVER_H, c["title"], c["alt"]), s.warn


def svg_stat(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> Tuple[str, List[str]]:
    s = Svg(brand, lang)
    hx = s.hx
    y = svg_head(s, v)
    stats = v["data"]["stats"]
    n = len(stats)
    cw = (W - 2 * PAD - 24 * (n - 1)) / n
    inner = cw - 72
    sep = (NNBSP if lang.startswith("fr") else "") + ": "
    sizes = []
    for st in stats:
        px = min(STAT_MAX[n], inner / max(text_w(st["value"], 1, True), 0.01))
        if px < 56:
            s.warn.append(f'value "{st["value"]}" needs {px:.0f} px in the SVG (min 56)')
        sizes.append(max(56, int(px)))
    vh = min(sizes)
    heights = [40 + vh + 18 + s.height_of(st["label"], 26, inner, 1.38) + 18 + s.height_of(f'{tr(lang, "source")}{sep}{st["source"]}', MIN_META, inner, 1.4) + 32
               for st in stats]
    ch = max(heights)
    for i, st in enumerate(stats):
        x = PAD + i * (cw + 24)
        s.rect(x, y, cw, ch, hx["surface"], hx["border"])
        s.parts.append(f'<text x="{x + 36:.1f}" y="{y + 40 + vh * 0.86:.1f}" font-family="{s.display}" font-size="{vh}" '
                       f'font-weight="{s.f["display_weight"]}" fill="{hx["accent_ink"]}">{xesc(svg_french(st["value"], lang))}</text>')
        s.text(x + 36, y + 40 + vh + 18, st["label"], 26, inner, hx["text"], lh=1.38)
        src = f'{tr(lang, "source")}{sep}{st["source"]}'
        s.text(x + 36, y + ch - 32 - s.height_of(src, MIN_META, inner, 1.4), src, MIN_META, inner, hx["text_muted"], lh=1.4)
    y += ch + 40
    h = svg_foot(s, v, y, with_logo)
    return s.doc(h, v["title"], v["alt"]), s.warn


def svg_steps(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> Tuple[str, List[str]]:
    s = Svg(brand, lang)
    hx = s.hx
    y = svg_head(s, v)
    steps = v["data"]["steps"]
    tx = PAD + 56 + 28
    tw = W - PAD - tx
    br = min(s.r, 28)
    tops = []
    for i, st in enumerate(steps, 1):
        tops.append(y)
        s.rect(PAD, y, 56, 56, hx["accent"], r=br)
        s.parts.append(f'<text x="{PAD + 28}" y="{y + 28 + 26 * 0.36:.1f}" font-family="{s.body}" font-size="26" '
                       f'font-weight="{s.f["body_strong"]}" fill="{hx["on_accent"]}" text-anchor="middle">{i}</text>')
        h = 10 + s.text(tx, y + 10, st["title"], 28, tw, hx["text"], lh=1.28, bold=True)
        if st.get("text"):
            h += 8 + s.text(tx, y + h + 8, st["text"], 22, tw, hx["text_secondary"], lh=1.5)
        y += max(56, h) + (34 if i < len(steps) else 0)
    for a, b in zip(tops, tops[1:]):
        s.line(PAD + 28, a + 64, PAD + 28, b - 8, hx["border"], 2)
    y += 40
    h = svg_foot(s, v, y, with_logo)
    return s.doc(h, v["title"], v["alt"]), s.warn


def svg_checklist(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> Tuple[str, List[str]]:
    s = Svg(brand, lang)
    hx = s.hx
    y = svg_head(s, v)
    items = v["data"]["items"]
    tx = PAD + 36 + 32 + 20
    tw = W - PAD - 36 - tx
    hs = [max(32, s.height_of(it["text"], 24, tw, 1.4)) + 40 for it in items]
    total = sum(hs) + 16
    s.rect(PAD, y, W - 2 * PAD, total, hx["surface"], hx["border"])
    cy = y + 8
    for i, (it, h) in enumerate(zip(items, hs)):
        state = it.get("state", "check")
        ico = icon(state, hx, 32, tr(lang, state)).replace('class="ico" ', "")
        s.parts.append(f'<g transform="translate({PAD + 36},{cy + 20})">{ico}</g>')
        s.text(tx, cy + 20, it["text"], 24, tw, hx["text_secondary"] if state == "cross" else hx["text"], lh=1.4)
        cy += h
        if i < len(items) - 1:
            s.line(PAD + 36, cy, W - PAD - 36, cy, hx["border"])
    y += total + 40
    h = svg_foot(s, v, y, with_logo)
    return s.doc(h, v["title"], v["alt"]), s.warn


def svg_comparison(v: Dict[str, Any], brand: Dict[str, Any], lang: str, with_logo: bool) -> Tuple[str, List[str]]:
    s = Svg(brand, lang)
    hx = s.hx
    y = svg_head(s, v)
    d = v["data"]
    cols, hl = d["columns"], d.get("highlight")
    tw = W - 2 * PAD
    lw = tw * 0.3
    cw = (tw - lw) / len(cols)
    xs = [PAD] + [PAD + lw + j * cw for j in range(len(cols))]
    widths = [lw] + [cw] * len(cols)
    hh = max([s.height_of(d.get("corner") or "", 20, lw - 48, 1.25)] + [s.height_of(c, 24, cw - 48, 1.25, True) for c in cols]) + 40

    def cell_h(cell: str, w: float) -> float:
        tok, note = cell_token(cell)
        if tok:
            return max(32, s.height_of(note, 20, w - 48 - 46, 1.35) if note else 32)
        return s.height_of(cell, 22, w - 48, 1.4)

    rhs = [max([s.height_of(r["label"], 22, lw - 48, 1.35, True)] + [cell_h(c, cw) for c in r["cells"]]) + 40 for r in d["rows"]]
    total = hh + sum(rhs)
    s.parts.append(f'<clipPath id="cmp"><rect x="{PAD}" y="{y:.1f}" width="{tw}" height="{total:.1f}" rx="{s.r:.1f}"/></clipPath>')
    s.parts.append('<g clip-path="url(#cmp)">')
    s.rect(PAD, y, tw, total, hx["surface"], r=0)
    s.rect(PAD, y, tw, hh, hx["bg"], r=0)
    if isinstance(hl, int):
        s.rect(xs[hl + 1], y, cw, hh, hx["accent"], r=0)
        s.rect(xs[hl + 1], y + hh, cw, total - hh, hx["accent_tint"], r=0)
    s.parts.append("</g>")
    s.text(PAD + 24, y + 20, d.get("corner") or "", 20, lw - 48, hx["text_muted"], lh=1.25)
    for j, c in enumerate(cols):
        s.text(xs[j + 1] + 24, y + 20, c, 24, cw - 48, hx["on_accent"] if hl == j else hx["text"], lh=1.25, bold=True)
    ry = y + hh
    for r, rh in zip(d["rows"], rhs):
        s.line(PAD, ry, W - PAD, ry, hx["border"])
        s.text(PAD + 24, ry + 20, r["label"], 22, lw - 48, hx["text"], lh=1.35, bold=True)
        for j, cell in enumerate(r["cells"]):
            x, w = xs[j + 1], widths[j + 1]
            ink = hx["text_on_tint"] if hl == j else hx["text"]
            tok, note = cell_token(cell)
            if tok:
                ch = cell_h(cell, w)
                ico = icon(tok, hx, 32, tr(lang, tok)).replace('class="ico" ', "")
                s.parts.append(f'<g transform="translate({x + 24:.1f},{ry + 20 + (ch - 32) / 2:.1f})">{ico}</g>')
                if note:
                    s.text(x + 24 + 46, ry + 20 + (ch - s.height_of(note, 20, w - 94, 1.35)) / 2, note, 20, w - 94,
                           hx["text_on_tint"] if hl == j else hx["text_secondary"], lh=1.35)
            else:
                s.text(x + 24, ry + 20, cell, 22, w - 48, ink, lh=1.4)
        ry += rh
    for x in xs[1:]:
        s.line(x, y, x, y + total, hx["border"])
    s.rect(PAD, y, tw, total, "none", hx["border"])
    y += total + 40
    h = svg_foot(s, v, y, with_logo)
    return s.doc(h, v["title"], v["alt"]), s.warn


SVG_BUILDERS = {"stat": svg_stat, "steps": svg_steps, "checklist": svg_checklist, "comparison": svg_comparison}


# --------------------------------------------------------------------------
# PNG helpers
# --------------------------------------------------------------------------

def png_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def flat_bands(data: bytes, bg: RGB, scale: float) -> Dict[str, Any]:
    """Runs of perfectly flat rows. A run of a colour other than bg is an
    unrasterised tile (render.py has_blank_band, made aware of a flat
    background); a long bg-coloured run is empty space. Needs Pillow."""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    raw = im.tobytes()
    bgb = bytes(int(round(c)) for c in bg)
    foreign = bg_run = run = 0
    prev = None
    for y in range(h):
        row = raw[y * w * 3:(y + 1) * w * 3]
        px = row[:3]
        flat = row == px * w
        key = px if flat else None
        run = run + 1 if (flat and key == prev) else (1 if flat else 0)
        prev = key
        if flat:
            if px == bgb:
                bg_run = max(bg_run, run)
            else:
                foreign = max(foreign, run)
    return {"foreign_rows": foreign, "foreign_css": foreign / scale, "bg_rows": bg_run, "bg_css": bg_run / scale, "height_css": h / scale}


def optimize_png(data: bytes) -> bytes:
    try:
        from io import BytesIO
        from PIL import Image
        im = Image.open(BytesIO(data)).convert("RGB")
        buf = BytesIO()
        im.save(buf, format="PNG", optimize=True)
        out = buf.getvalue()
        return out if len(out) < len(data) else data
    except Exception:  # noqa: BLE001
        return data


def have_pillow() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def png_checks(vid: str, data: bytes, want_w: int, want_h: int, scale: float, bg: RGB, cover: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    dims = png_size(data)
    ew, eh = round(want_w * scale), round(want_h * scale)
    if not dims:
        return [issue("BLOCK", "png-invalid", vid, "The file is not a PNG.")]
    if cover and (want_w, want_h) != (W, COVER_H):
        out.append(issue("BLOCK", "cover-size", vid, f"Cover declared {want_w}x{want_h}, must be {W}x{COVER_H}."))
    if abs(dims[0] - ew) > 1 or abs(dims[1] - eh) > 1:
        out.append(issue("BLOCK", "png-size", vid, f"PNG is {dims[0]}x{dims[1]}, expected {ew}x{eh} ({want_w}x{want_h} at scale {scale:g})."))
    kb = len(data) / 1024
    area = (want_w * want_h) / (W * 900)
    warn_kb, block_kb = PNG_WARN_KB * scale ** 2 * max(area, 0.7), PNG_BLOCK_KB * scale ** 2 * max(area, 0.7)
    if kb > block_kb:
        out.append(issue("BLOCK", "png-weight", vid, f"{kb:.0f} KB, over {block_kb:.0f} KB: noise or a photo inside the visual."))
    elif kb > warn_kb:
        out.append(issue("WARN", "png-weight", vid, f"{kb:.0f} KB, over {warn_kb:.0f} KB."))
    if have_pillow():
        fb = flat_bands(data, bg, scale)
        if fb["foreign_css"] >= 40:
            out.append(issue("BLOCK", "blank-band", vid, f"{fb['foreign_css']:.0f} px of flat rows in a colour that is not the background: an unrasterised tile."))
        if not cover and fb["bg_css"] > max(200, 0.3 * fb["height_css"]):
            out.append(issue("WARN", "dead-space", vid, f"{fb['bg_css']:.0f} px of empty background in one band ({fb['height_css']:.0f} px tall visual)."))
    else:
        out.append(issue("INFO", "pillow-missing", vid, "Pillow not installed: flat band check skipped (pip install pillow)."))
    return out


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

class RenderUnavailable(Exception):
    pass


def render_pages(jobs: List[Dict[str, Any]], scale: float, bg: RGB) -> Dict[str, Dict[str, Any]]:
    """jobs: {id, html, cover}. Returns per id {measure, png (bytes)}."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        raise RenderUnavailable(f"Playwright is not installed ({e.__class__.__name__}).")
    out: Dict[str, Dict[str, Any]] = {}
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as e:  # noqa: BLE001
                raise RenderUnavailable(f"Chromium does not start: {str(e).splitlines()[0][:200]}")
            ctx = browser.new_context(viewport={"width": W, "height": COVER_H}, device_scale_factor=scale)
            page = ctx.new_page()
            for job in jobs:
                page.set_viewport_size({"width": W, "height": COVER_H if job["cover"] else 1000})
                page.goto(job["html"].resolve().as_uri(), wait_until="load")
                page.wait_for_function("document.body.dataset.fitted === '1'", timeout=FIT_TIMEOUT_MS)
                m = page.evaluate("window.__visual")
                h = COVER_H if job["cover"] else max(1, int(m.get("height") or 1))
                page.set_viewport_size({"width": W, "height": h})
                data = b""
                for _attempt in range(4):
                    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                    data = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": W, "height": h}, animations="disabled")
                    if not have_pillow() or flat_bands(data, bg, scale)["foreign_css"] < 40:
                        break
                out[job["id"]] = {"measure": m, "png": optimize_png(data), "height": h}
            browser.close()
    except RenderUnavailable:
        raise
    return out


def dom_issues(vid: str, m: Dict[str, Any], cover: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in m.get("fit") or []:
        if f.get("status") == "fail":
            out.append(issue("BLOCK", "text-too-long", f"{vid} {f.get('where')}", f"{f.get('reason')}: shorten the text in the spec."))
    for it in m.get("issues") or []:
        code = it.get("code")
        where = f"{vid} {it.get('where')}"
        if code == "contrast":
            lvl = "BLOCK" if (it.get("ratio") or 0) < 3 else "WARN"
            out.append(issue(lvl, "contrast", where, it.get("message", ""), ratio=it.get("ratio"), need=it.get("need")))
        elif code in ("overflow", "outside", "text-too-small"):
            out.append(issue("BLOCK", code, where, it.get("message", "")))
    for role, fo in (m.get("fonts") or {}).items():
        if fo.get("family") and not fo.get("loaded"):
            out.append(issue("WARN", "font-fallback", f"{vid} fonts.{role}",
                             f'"{fo["family"]}" did not load: rendered in the fallback stack. Add fonts.{role}.files to brand.json or install the family.'))
    h = m.get("height") or 0
    if not cover:
        if h > MAX_BODY_H:
            out.append(issue("BLOCK", "too-tall", vid, f"{h} px tall (max {MAX_BODY_H}): split the visual or cut rows."))
        elif h and h < MIN_BODY_H:
            out.append(issue("WARN", "too-short", vid, f"{h} px tall: a sentence of the article may do better than an image."))
    return out


# --------------------------------------------------------------------------
# Manifest and QA file
# --------------------------------------------------------------------------

def rel_prefix(out_dir: Path, article_dir: Path) -> str:
    try:
        rel = os.path.relpath(out_dir.resolve(), article_dir.resolve())
    except ValueError:
        rel = out_dir.name
    rel = rel.replace(os.sep, "/")
    return "" if rel == "." else rel + "/"


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def summarize(issues: List[Dict[str, Any]]) -> Tuple[int, int]:
    return sum(1 for i in issues if i["level"] == "BLOCK"), sum(1 for i in issues if i["level"] == "WARN")


def print_issues(issues: List[Dict[str, Any]], stream=sys.stdout) -> None:
    for i in issues:
        if i["level"] in ("BLOCK", "WARN"):
            print(f"  {i['level']:5} {i['code']:22} {i['where']}: {i['message']}", file=stream)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> int:
    spec_path, brand_path, out_dir = Path(args.spec), Path(args.brand), Path(args.out_dir)
    if not 1 <= args.scale <= 3:
        print("article_visuals: --scale between 1 and 3", file=sys.stderr)
        return 2
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"article_visuals: spec unreadable: {e}", file=sys.stderr)
        return 2
    bad = validate_spec(spec)
    if bad:
        print(f"article_visuals: invalid spec {spec_path}, nothing built:", file=sys.stderr)
        print_issues(bad, sys.stderr)
        if args.json:
            print(json.dumps({"status": "invalid-spec", "issues": bad}, indent=2, ensure_ascii=False))
        return 2
    try:
        brand, issues = load_brand(brand_path, None if args.no_font_fetch else out_dir / "_src" / "fonts-cache")
    except ValueError as e:
        print(f"article_visuals: {e}", file=sys.stderr)
        return 2
    issues.extend(brand_contrast(brand))
    lang = spec.get("lang") or "en"
    with_logo = spec.get("logo", True) is not False
    out_dir.mkdir(parents=True, exist_ok=True)
    src = out_dir / "_src"
    src.mkdir(exist_ok=True)
    # Files of the previous run that this spec no longer lists.
    old = out_dir / "visuals.json"
    if old.exists():
        try:
            prev = json.loads(old.read_text(encoding="utf-8"))
            for e in [prev.get("cover") or {}] + list(prev.get("body") or []):
                for k in ("path", "svg"):
                    if e.get(k):
                        p = out_dir / Path(e[k]).name
                        if p.exists():
                            p.unlink()
        except Exception:  # noqa: BLE001
            pass
        old.unlink()
    faces = font_faces(brand, src)
    cover = spec["cover"]
    visuals = [{"id": "cover", "kind": "cover", "spec": cover}] + [{"id": v["id"], "kind": v["kind"], "spec": v} for v in spec["body"]]
    jobs = []
    for vis in visuals:
        if vis["kind"] == "cover":
            content = build_cover(cover, brand, lang, with_logo)
            page = page_html(content, brand, lang, cover["title"], faces)
        else:
            page = build_body_page(vis["spec"], brand, lang, with_logo, faces)
        hp = src / f"{vis['id']}.html"
        hp.write_text(page, encoding="utf-8")
        vis["html"] = hp
        jobs.append({"id": vis["id"], "html": hp, "cover": vis["kind"] == "cover"})

    want_svg = args.format in ("svg", "both")
    want_png = {vis["id"]: (args.format != "svg" or vis["kind"] not in SVG_KINDS) for vis in visuals}
    svg_heights: Dict[str, int] = {}
    if want_svg:
        for vis in visuals:
            if vis["kind"] not in SVG_KINDS:
                issues.append(issue("WARN" if args.format == "svg" else "INFO", "svg-unsupported", vis["id"],
                                    f"{vis['kind']} has no SVG builder (its layout needs the browser): PNG only."))
                continue
            if vis["kind"] == "cover":
                svg, warns = svg_cover(cover, brand, lang, with_logo)
            else:
                svg, warns = SVG_BUILDERS[vis["kind"]](vis["spec"], brand, lang, with_logo)
            try:
                root = ET.fromstring(svg)
                svg_heights[vis["id"]] = int(float(root.get("height")))
            except ET.ParseError as e:
                issues.append(issue("BLOCK", "svg-invalid", vis["id"], f"SVG does not parse: {e}"))
                continue
            (out_dir / f"{vis['id']}.svg").write_text(svg, encoding="utf-8")
            vis["svg"] = f"{vis['id']}.svg"
            for w_ in warns:
                issues.append(issue("WARN", "svg-wrap", vis["id"], w_ + " The PNG is the reference; shorten the text if it matters."))

    rendered: Dict[str, Dict[str, Any]] = {}
    render_error = None
    need_render = [j for j in jobs if want_png[j["id"]]]
    if need_render and not args.no_render:
        try:
            rendered = render_pages(need_render, args.scale, brand["roles"]["bg"])
        except RenderUnavailable as e:
            render_error = str(e)
        except Exception as e:  # noqa: BLE001
            render_error = f"render failed: {e.__class__.__name__}: {str(e).splitlines()[0][:300] if str(e) else ''}"
    for vis in visuals:
        r = rendered.get(vis["id"])
        if not r:
            continue
        cov = vis["kind"] == "cover"
        issues.extend(dom_issues(vis["id"], r["measure"], cov))
        h = COVER_H if cov else r["height"]
        issues.extend(png_checks(vis["id"], r["png"], W, h, args.scale, brand["roles"]["bg"], cov))
        (out_dir / f"{vis['id']}.png").write_bytes(r["png"])
        vis["png"] = f"{vis['id']}.png"
        vis["height"] = h
        vis["fit"] = r["measure"].get("fit")
        vis["fonts"] = r["measure"].get("fonts")

    pre = rel_prefix(out_dir, Path(args.article_dir) if args.article_dir else out_dir.parent)
    complete = True
    entries = []
    for vis in visuals:
        sp = vis["spec"]
        main = vis.get("svg") if args.format == "svg" and vis.get("svg") else vis.get("png")
        if not main:
            complete = False
            continue
        h = vis.get("height") or svg_heights.get(vis["id"]) or (COVER_H if vis["kind"] == "cover" else 0)
        e: Dict[str, Any] = {"path": pre + main}
        if vis.get("svg") and main != vis["svg"]:
            e["svg"] = pre + vis["svg"]
        e.update({"alt": sp["alt"].strip(), "width": W, "height": int(h)})
        if vis["kind"] != "cover":
            e = {"id": vis["id"], "kind": vis["kind"], "path": e["path"], **({"svg": e["svg"]} if "svg" in e else {}),
                 "alt": e["alt"], "after_h2": sp["after_h2"].strip(), "width": e["width"], "height": e["height"]}
        entries.append((vis["kind"], e))
    manifest = None
    if complete:
        manifest = {"schema_version": "1.0", "scale": args.scale, "brand": brand["name"],
                    "cover": next(e for k, e in entries if k == "cover"), "body": [e for k, e in entries if k != "cover"]}
        write_json(out_dir / "visuals.json", manifest)

    blocks, warns = summarize(issues)
    qa = {"spec": spec_path.name, "brand": brand["name"], "mode": brand["mode"], "logo": {k: (str(v.name) if isinstance(v, Path) else v) for k, v in brand["logo"].items()},
          "scale": args.scale, "format": args.format, "rendered": bool(rendered), "render_error": render_error,
          "roles": brand["hex"], "blocks": blocks, "warnings": warns, "issues": issues,
          "visuals": [{"id": v["id"], "kind": v["kind"], "html": f"_src/{v['id']}.html", "png": v.get("png"), "svg": v.get("svg"),
                       "height": v.get("height"), "fit": v.get("fit"), "fonts": v.get("fonts")} for v in visuals],
          "manifest": "visuals.json" if manifest else None}
    write_json(out_dir / "visuals-qa.json", qa)

    if args.json:
        print(json.dumps(qa, indent=2, ensure_ascii=False, default=str))
    else:
        done = sum(1 for v in visuals if v.get("png"))
        print(f"article_visuals: {len(visuals)} visuals ({done} PNG, {sum(1 for v in visuals if v.get('svg'))} SVG) -> {out_dir}")
        print(f"  brand {brand['name'] or '(no name)'} ({brand['mode']}), logo {brand['logo']['kind']}"
              + (f" {brand['logo']['variant']}" if brand["logo"]["variant"] else ""))
        print_issues(issues)
        why = "--no-render: no PNG" if args.no_render else "a visual has no file"
        print(f"  {blocks} BLOCK, {warns} WARN" + ("" if manifest else f"; visuals.json not written ({why})"))
    if render_error:
        print(f"article_visuals: {render_error} HTML written to {src}. Install the renderer: "
              "pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1
    return 1 if blocks else 0


def cmd_qa(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    mpath = out_dir / "visuals.json"
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"article_visuals qa: {mpath} unreadable: {e}", file=sys.stderr)
        return 2
    issues: List[Dict[str, Any]] = []
    validate = _validator()
    if validate:
        for err in validate(manifest, json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))):
            issues.append(issue("BLOCK", "manifest-schema", "visuals.json", str(err)))
    scale = float(manifest.get("scale") or 1)
    qa_prev: Dict[str, Any] = {}
    if (out_dir / "visuals-qa.json").exists():
        try:
            qa_prev = json.loads((out_dir / "visuals-qa.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            qa_prev = {}
    bg = parse_hex((qa_prev.get("roles") or {}).get("bg")) or WHITE
    entries = [("cover", manifest.get("cover") or {})] + [(e.get("id", "?"), e) for e in manifest.get("body") or []]
    for vid, e in entries:
        if _blank(e.get("alt")):
            issues.append(issue("BLOCK", "alt-empty", vid, "alt is empty."))
        elif re.fullmatch(r"[\w.-]+\.(png|svg|jpe?g)", e["alt"].strip(), flags=re.I):
            issues.append(issue("BLOCK", "alt-filename", vid, "alt is a file name, not a description."))
        for key in ("path", "svg"):
            if not e.get(key):
                continue
            f = out_dir / Path(e[key]).name
            if not f.exists():
                issues.append(issue("BLOCK", "file-missing", vid, f"{e[key]} not found in {out_dir}."))
                continue
            if f.suffix == ".png":
                issues.extend(png_checks(vid, f.read_bytes(), int(e.get("width") or 0), int(e.get("height") or 0), scale, bg, vid == "cover"))
            else:
                try:
                    root = ET.fromstring(f.read_text(encoding="utf-8"))
                    if not root.tag.endswith("svg"):
                        raise ET.ParseError("root is not svg")
                    if vid == "cover" and (root.get("width"), root.get("height")) != (str(W), str(COVER_H)):
                        issues.append(issue("BLOCK", "cover-size", vid, f"SVG cover is {root.get('width')}x{root.get('height')}."))
                except ET.ParseError as ex:
                    issues.append(issue("BLOCK", "svg-invalid", vid, f"{e[key]} does not parse: {ex}"))
    carried = [i for i in qa_prev.get("issues") or [] if i.get("level") == "BLOCK" and i.get("code") not in ("png-size", "png-weight", "blank-band", "cover-size")]
    for i in carried:
        issues.append(dict(i, code=i["code"], where=i["where"] + " (render)"))
    blocks, warns = summarize(issues)
    if args.json:
        print(json.dumps({"blocks": blocks, "warnings": warns, "issues": issues}, indent=2, ensure_ascii=False))
    else:
        print(f"article_visuals qa: {len(entries)} visuals in {out_dir}")
        print_issues(issues)
        print(f"  {blocks} BLOCK, {warns} WARN")
    return 1 if blocks else 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "qa":
        ap = argparse.ArgumentParser(prog="article_visuals.py qa", description="Re-check a rendered visuals folder (manifest, files, sizes, alt, weight, flat bands, SVG).")
        ap.add_argument("--out-dir", required=True, help="The visuals folder holding visuals.json")
        ap.add_argument("--json", action="store_true")
        return cmd_qa(ap.parse_args(argv[1:]))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="visuals-spec.json written by the model")
    ap.add_argument("--brand", required=True, help="<project>/project-context/brand.json")
    ap.add_argument("--out-dir", required=True, help="<article dir>/visuals")
    ap.add_argument("--format", choices=("png", "svg", "both"), default="png")
    ap.add_argument("--scale", type=float, default=2.0, help="Device scale of the PNG (2 = 2400 px wide)")
    ap.add_argument("--article-dir", help="Folder the manifest paths are relative to (default: parent of --out-dir)")
    ap.add_argument("--no-render", action="store_true", help="Write HTML (and SVG) only, no PNG")
    ap.add_argument("--no-font-fetch", action="store_true",
                    help="Never download a Google Fonts family that brand.json lists without files (offline runs)")
    ap.add_argument("--json", action="store_true", help="Print visuals-qa.json on stdout")
    return cmd_build(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
