#!/usr/bin/env python3
"""render_brand_preview.py: render the brand board the founder and the model review.

Fills assets/brand-board.html with a brand.json V2 (draft or final; V1 and
candidate files are mapped on load), renders it in Chromium and writes:

  - brand-debug/brand-board.html  the filled page (fonts and files linked relatively)
  - brand-debug/brand-board.jpg   the board image, kept under --max-kb (default 150)
  - brand-debug/board-checks.json mechanical checks run on the rendered page

The board shows every color role with its contrast, the display and body
families at several sizes (with a flag when the browser fell back to another
family), each logo variant on its background with its pixel-test result,
buttons, a link and a card composed with the tokens on colors.bg, the harvested
images with their role and license, and the open issues.

Checks (board-checks.json): text and text_secondary against bg (4.5:1),
text_muted (3:1), on_accent against accent (4.5:1 warn, 3:1 fail), each family
really rendered (a webfont that falls back is a fail), logo_audit status.

Without Playwright, a Pillow card (swatches, font names, PNG logos) is written
instead and the fonts are not checked.

Usage:
    python3 render_brand_preview.py --brand <project-context>/brand-draft.json
    python3 render_brand_preview.py --brand brand.json --out /tmp/board.jpg --max-kb 120

Exit codes:
    0  board written, no check failed
    1  board written, at least one check failed (listed in board-checks.json)
    3  brand JSON unreadable
    4  render error
"""

from __future__ import annotations

import argparse
import html
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand_common import better_on, contrast_ratio, hex_to_rgb, is_dark, rgb_to_hex  # noqa: E402

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "brand-board.html"
BOARD_WIDTH = 1256  # 1200 px board + body margins
GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif",
           "ui-monospace", "-apple-system", "blinkmacsystemfont"}
ROLE_ORDER = ("bg", "surface", "text", "text_secondary", "text_muted", "border", "accent", "accent_secondary", "on_accent")


# --- Loading -------------------------------------------------------------------

def load_brand(path: Path) -> Dict[str, Any]:
    """Read V2 as is; map a candidate file or a V1 file onto the V2 shape."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    if data.get("schema_version"):
        return data
    if isinstance(data.get("tokens"), dict):
        flat = {k: v.get("value") for k, v in data["tokens"].items() if isinstance(v, dict)}
    else:
        flat = data

    def split(stack: str) -> Dict[str, str]:
        parts = [p.strip() for p in str(stack or "").split(",") if p.strip()]
        if not parts:
            return {"family": "system-ui"}
        out = {"family": parts[0].strip("'\"")}
        if parts[1:]:
            out["fallback"] = ", ".join(parts[1:])
        return out
    bg = str(flat.get("bg") or "#ffffff")
    colors = {"bg": bg, "text": str(flat.get("text_primary") or "#111111"), "accent": str(flat.get("accent") or "#5b8def")}
    if flat.get("accent_secondary"):
        colors["accent_secondary"] = str(flat["accent_secondary"])
    return {"schema_version": "mapped", "name": str(flat.get("name") or "brand"),
            "mode": "dark" if is_dark(hex_to_rgb(bg)) else "light", "colors": colors,
            "fonts": {"display": split(flat.get("font_heading", "")), "body": split(flat.get("font_body", ""))},
            "warnings": list(data.get("warnings") or [])}


def resolved_colors(brand: Dict[str, Any]) -> Dict[str, str]:
    """Every role, with the reader fallbacks of shared/schemas/README.md."""
    c = dict(brand.get("colors") or {})
    c.setdefault("text_secondary", c.get("text", "#111111"))
    c.setdefault("text_muted", c["text_secondary"])
    c.setdefault("surface", c.get("bg", "#ffffff"))
    c.setdefault("border", c["text_muted"])
    c.setdefault("accent_secondary", c.get("accent", "#5b8def"))
    c.setdefault("on_accent", rgb_to_hex(better_on(hex_to_rgb(c.get("accent", "#5b8def")))))
    return c


def font_stack(f: Dict[str, Any]) -> str:
    fam = (f or {}).get("family") or "system-ui"
    head = fam if fam.lower() in GENERIC else f"'{fam}'"
    return f"{head}, {f['fallback']}" if f.get("fallback") else f"{head}, sans-serif"


def rel_from(base_dir: Path, target: Path) -> str:
    return os.path.relpath(target, base_dir).replace(os.sep, "/")


# --- Filling the template ---------------------------------------------------------

def build_html(brand: Dict[str, Any], pc_dir: Path, html_dir: Path) -> Tuple[str, Dict[str, Any]]:
    c = resolved_colors(brand)
    bg = hex_to_rgb(c["bg"])
    fonts = brand.get("fonts") or {}
    ext = (brand.get("extensions") or {}).get("extract_brand") or {}
    faces = []
    for role in ("display", "body"):
        f = fonts.get(role) or {}
        for fl in f.get("files") or []:
            p = pc_dir / fl["path"]
            if p.is_file():
                faces.append(f"@font-face {{ font-family: '{f['family']}'; src: url('{rel_from(html_dir, p)}') format('{fl.get('format', 'woff2')}'); "
                             f"font-weight: {fl.get('weight', 400)}; font-style: {fl.get('style', 'normal')}; }}")
    font_link = f'<link rel="stylesheet" href="{html.escape(fonts["fonts_url"])}">' if fonts.get("fonts_url") else ""

    def ratio_line(role: str) -> str:
        if role in ("text", "text_secondary", "text_muted", "accent", "border", "surface", "accent_secondary"):
            return f"{contrast_ratio(hex_to_rgb(c[role]), bg):.1f}:1 on bg"
        if role == "on_accent":
            return f"{contrast_ratio(hex_to_rgb(c[role]), hex_to_rgb(c['accent'])):.1f}:1 on accent"
        return "mode " + str(brand.get("mode", ""))
    given = set((brand.get("colors") or {}).keys())
    sw = []
    for role in ROLE_ORDER:
        if role not in c:
            continue
        derived = "" if role in given else " (derived)"
        sw.append(f'<div class="sw"><div class="chip" style="background:{c[role]}"></div><div class="txt"><b>{role}{derived}</b>'
                  f'{c[role]}<br><span class="ratio">{ratio_line(role)}</span></div></div>')

    def flabel(role: str) -> str:
        f = fonts.get(role) or {}
        w = ", ".join(str(x) for x in f.get("weights") or []) or "weights not read"
        files = f"{len(f.get('files') or [])} local file(s)" if f.get("files") else ("fonts_url" if fonts.get("fonts_url") else "no file")
        return (f"<b>{html.escape(f.get('family', 'system-ui'))}</b> &middot; {html.escape(f.get('fallback', ''))} &middot; {w} &middot; "
                f"{f.get('source', 'unknown')} &middot; {files} &middot; <span id='chk-{role}'>checking</span>")

    # logos: every variant x kind, on its test background, plus the brand bg cell
    audit = brand.get("logo_audit") or {}
    checks = {(ch.get("variant"), ch.get("kind")): ch for ch in audit.get("checks") or []}
    dbg = pc_dir / "brand-debug" / "logo" / "audit.json"
    test_bgs = {}
    if dbg.is_file():
        try:
            test_bgs = json.loads(dbg.read_text(encoding="utf-8")).get("test_backgrounds") or {}
        except (OSError, ValueError):
            test_bgs = {}
    light_bg = test_bgs.get("on_light") or (c["bg"] if not is_dark(bg) else c["text"])
    dark_bg = test_bgs.get("on_dark") or (c["bg"] if is_dark(bg) else c["text"])
    cells = []
    logos = brand.get("logos") or {}
    for variant, stage_bg in (("on_light", light_bg), ("on_dark", dark_bg)):
        for kind in ("wordmark", "mark"):
            lf = (logos.get(variant) or {}).get(kind)
            if not lf:
                continue
            p = pc_dir / lf["path"]
            ch = checks.get((variant, kind), {})
            cap = f"{kind} {variant}: {ch.get('status', 'unchecked')}" + (f", {ch['contrast_ratio']}:1" if ch.get("contrast_ratio") else "")
            if ch.get("viewbox_clips_ink"):
                cap += ", source viewBox clipped"
            img = f'<img src="{rel_from(html_dir, p)}" alt="">' if p.is_file() else '<span class="missing">file missing</span>'
            cells.append(f'<div class="logo-cell"><div class="stage" style="background:{stage_bg}">{img}</div><div class="cap">{cap}</div></div>')
    src = ext.get("logo_source")
    if src and (pc_dir / src).is_file():
        cells.append(f'<div class="logo-cell"><div class="stage" style="background:{c["bg"]}"><img src="{rel_from(html_dir, pc_dir / src)}" alt=""></div>'
                     f'<div class="cap">harvested file on colors.bg</div></div>')
    if not cells:
        name = html.escape(brand.get("logo_text") or brand.get("name", ""))
        cells.append(f'<div class="logo-cell"><div class="stage" style="background:{c["bg"]};color:{c["text"]};font-family:var(--font-display);font-size:34px">{name}</div>'
                     f'<div class="cap">no logo file: logo_text typeset</div></div>')

    imgs = []
    assets = brand.get("assets") or {}
    license_ = ext.get("image_license", "unknown")
    for im in (assets.get("images") or [])[:6]:
        p = pc_dir / im["path"]
        if p.is_file():
            fit = ' style="object-fit:contain;background:#222"' if im.get("role") == "hero" else ""
            imgs.append(f'<div class="im"><img src="{rel_from(html_dir, p)}"{fit} alt=""><div class="cap">{html.escape(im.get("role", "other"))} &middot; '
                        f'{html.escape(license_)} &middot; {im.get("w", "?")}x{im.get("h", "?")}</div></div>')
    if not imgs:
        imgs.append('<div class="im"><div class="cap">no harvested image</div></div>')

    issues: List[Tuple[str, str]] = []
    for i in audit.get("issues") or []:
        issues.append(("warn", "Logo: " + i))
    for w in brand.get("warnings") or []:
        issues.append(("warn", w))
    meta = " &middot; ".join(x for x in (html.escape(brand.get("source_url", "")), f"as of {brand.get('as_of', '?')}",
                                         f"mode {brand.get('mode', '?')}", f"radius {brand.get('radius', '0 (fallback)')}") if x)
    status = f"logo audit: {audit.get('status', 'none')} &middot; schema {brand.get('schema_version', '?')}"
    values = {
        "name": html.escape(brand.get("name", "brand")), "meta": meta, "status": status, "font_link": font_link,
        "font_faces": "\n".join(faces), "font_display": font_stack(fonts.get("display") or {}),
        "font_body": font_stack(fonts.get("body") or {}), "radius": brand.get("radius", "0"),
        "shadow": ext.get("shadow") or "none", "swatches": "".join(sw), "display_label": flabel("display"),
        "body_label": flabel("body"), "logos": "".join(cells), "images": "".join(imgs),
        "issues": "".join(f'<li class="{lvl}">{html.escape(t)}</li>' for lvl, t in issues) or "<li>none</li>",
        **{k: c[k] for k in ROLE_ORDER},
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text, {"colors": c, "issues": issues}


FONT_CHECK_JS = r"""async (fams) => {
  await document.fonts.ready;
  const s = 'Hamburgefonstiv 0123456789';
  const ctx = document.createElement('canvas').getContext('2d');
  const width = (f) => { ctx.font = f; return ctx.measureText(s).width; };
  const out = {};
  for (const [role, fam, generic] of fams) {
    if (generic) { out[role] = true; const g = document.getElementById('chk-' + role); if (g) g.textContent = 'system family: each viewer sees their own OS font'; continue; }
    const a = width(`40px monospace`) !== width(`40px "${fam}", monospace`);
    const b = width(`40px serif`) !== width(`40px "${fam}", serif`);
    out[role] = a || b;
    const el = document.getElementById('chk-' + role);
    if (el) { el.textContent = out[role] ? 'rendered' : 'NOT rendered: fallback shown'; if (!out[role]) el.className = 'bad'; }
  }
  return out;
}"""


def run_checks(brand: Dict[str, Any], colors: Dict[str, str], rendered: Dict[str, bool]) -> List[Dict[str, Any]]:
    bg = hex_to_rgb(colors["bg"])
    out: List[Dict[str, Any]] = []

    def add(check: str, value: float, warn_at: float, fail_at: float) -> None:
        level = "pass" if value >= warn_at else ("warn" if value >= fail_at else "fail")
        out.append({"check": check, "value": round(value, 2), "status": level, "min": warn_at})
    add("text on bg", contrast_ratio(hex_to_rgb(colors["text"]), bg), 4.5, 3.0)
    add("text_secondary on bg", contrast_ratio(hex_to_rgb(colors["text_secondary"]), bg), 4.5, 3.0)
    add("text_muted on bg", contrast_ratio(hex_to_rgb(colors["text_muted"]), bg), 3.0, 2.0)
    add("on_accent on accent", contrast_ratio(hex_to_rgb(colors["on_accent"]), hex_to_rgb(colors["accent"])), 4.5, 3.0)
    add("text on surface", contrast_ratio(hex_to_rgb(colors["text"]), hex_to_rgb(colors["surface"])), 4.5, 3.0)
    fonts = brand.get("fonts") or {}
    for role, ok in rendered.items():
        f = fonts.get(role) or {}
        expected = f.get("source") in ("google_fonts", "self_hosted", "other")
        status = "pass" if ok else ("fail" if expected else "warn")
        out.append({"check": f"{role} font {f.get('family')} rendered", "value": bool(ok), "status": status})
    a = (brand.get("logo_audit") or {}).get("status")
    if a:
        out.append({"check": "logo audit", "value": a, "status": {"pass": "pass", "warn": "warn", "fail": "fail"}.get(a, "warn")})
    return out


def save_jpeg(png: bytes, out: Path, max_kb: int) -> Tuple[int, int, int]:
    """Save under max_kb: quality 85 down to 55, then 85 % of the width."""
    from PIL import Image
    img = Image.open(io.BytesIO(png)).convert("RGB")
    while True:
        for q in (85, 78, 70, 62, 55):
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
            if buf.tell() <= max_kb * 1024 or (q == 55 and img.width < 700):
                out.write_bytes(buf.getvalue())
                return buf.tell(), q, img.width
        img = img.resize((int(img.width * 0.85), int(img.height * 0.85)), Image.LANCZOS)


def render_playwright(brand: Dict[str, Any], pc_dir: Path, out: Path, max_kb: int) -> Dict[str, Any]:
    from playwright.sync_api import sync_playwright
    html_dir = out.parent
    html_dir.mkdir(parents=True, exist_ok=True)
    text, info = build_html(brand, pc_dir, html_dir)
    html_path = out.with_suffix(".html")
    html_path.write_text(text, encoding="utf-8")
    fonts = brand.get("fonts") or {}
    fams = [[r, (fonts.get(r) or {}).get("family", "system-ui"), (fonts.get(r) or {}).get("family", "system-ui").lower() in GENERIC]
            for r in ("display", "body")]
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            page = b.new_page(viewport={"width": BOARD_WIDTH, "height": 900})
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=45_000)
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:  # noqa: BLE001
                pass
            rendered = page.evaluate(FONT_CHECK_JS, fams)
            png = page.screenshot(full_page=True)
        finally:
            b.close()
    size, q, w = save_jpeg(png, out, max_kb)
    checks = run_checks(brand, info["colors"], rendered)
    return {"board": str(out), "html": str(html_path), "bytes": size, "jpeg_quality": q, "width": w, "fonts_rendered": rendered,
            "checks": checks, "engine": "playwright"}


def render_pillow(brand: Dict[str, Any], pc_dir: Path, out: Path, max_kb: int) -> Dict[str, Any]:
    """Fallback card without a browser: swatches, font names, PNG logos."""
    from PIL import Image, ImageDraw, ImageFont
    c = resolved_colors(brand)

    def font(size: int) -> Any:
        for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()
    W = 1200
    img = Image.new("RGB", (W, 900), (233, 233, 236))
    d = ImageDraw.Draw(img)
    d.text((40, 30), f"Brand board (no browser): {brand.get('name', '')}", font=font(30), fill=(20, 20, 24))
    x, y = 40, 90
    for role in ROLE_ORDER:
        rgb = hex_to_rgb(c[role])
        d.rectangle([x, y, x + 120, y + 70], fill=rgb, outline=(150, 150, 160))
        d.text((x, y + 76), f"{role}\n{c[role]}", font=font(14), fill=(20, 20, 24))
        x += 128
    fonts = brand.get("fonts") or {}
    d.text((40, 230), f"Display: {(fonts.get('display') or {}).get('family')}   Body: {(fonts.get('body') or {}).get('family')}   (names only: no browser to render them)",
           font=font(16), fill=(20, 20, 24))
    x, y = 40, 280
    for variant, stage in (("on_light", (255, 255, 255)), ("on_dark", (17, 17, 17))):
        for kind in ("wordmark", "mark"):
            png = ((brand.get("extensions") or {}).get("extract_brand", {}).get("logo_png") or {}).get(variant, {}).get(kind)
            lf = (brand.get("logos") or {}).get(variant, {}).get(kind) or {}
            path = pc_dir / (png or lf.get("path", ""))
            d.rectangle([x, y, x + 260, y + 120], fill=stage, outline=(150, 150, 160))
            if path.is_file() and path.suffix.lower() != ".svg":
                logo = Image.open(path).convert("RGBA")
                logo.thumbnail((220, 70))
                img.paste(logo, (x + (260 - logo.width) // 2, y + (120 - logo.height) // 2), logo)
            d.text((x, y + 126), f"{kind} {variant}", font=font(14), fill=(20, 20, 24))
            x += 280
    buf = io.BytesIO()
    img.save(buf, "PNG")
    size, q, w = save_jpeg(buf.getvalue(), out, max_kb)
    checks = run_checks(brand, c, {})
    return {"board": str(out), "bytes": size, "jpeg_quality": q, "width": w, "fonts_rendered": {}, "checks": checks, "engine": "pillow"}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brand", required=True, help="brand-draft.json or brand.json (V2; V1 and candidate files are mapped)")
    ap.add_argument("--out", help="Board image path (default: <brand dir>/brand-debug/brand-board.jpg)")
    ap.add_argument("--max-kb", type=int, default=150, help="Size budget of the JPEG (default 150)")
    ap.add_argument("--engine", choices=("auto", "playwright", "pillow"), default="auto")
    args = ap.parse_args(argv)

    bpath = Path(args.brand).expanduser().resolve()
    try:
        brand = load_brand(bpath)
    except (OSError, ValueError) as e:
        print(f"render_brand_preview: cannot read {bpath}: {e}", file=sys.stderr)
        return 3
    pc_dir = bpath.parent
    out = Path(args.out).expanduser().resolve() if args.out else pc_dir / "brand-debug" / "brand-board.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.engine == "pillow":
            res = render_pillow(brand, pc_dir, out, args.max_kb)
        else:
            try:
                res = render_playwright(brand, pc_dir, out, args.max_kb)
            except ImportError:
                if args.engine == "playwright":
                    raise
                print("render_brand_preview: Playwright missing, Pillow card instead (fonts not rendered)", file=sys.stderr)
                res = render_pillow(brand, pc_dir, out, args.max_kb)
    except Exception as e:  # noqa: BLE001
        print(f"render_brand_preview: render error: {e}", file=sys.stderr)
        return 4
    checks_path = out.parent / "board-checks.json"
    checks_path.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    fails = [c for c in res["checks"] if c["status"] == "fail"]
    warns = [c for c in res["checks"] if c["status"] == "warn"]
    print(f"board: {out} ({res['bytes'] // 1024} KB, {res['engine']})")
    for c in fails + warns:
        print(f"  {c['status'].upper():<4} {c['check']}: {c['value']}")
    print(f"checks: {len(fails)} fail, {len(warns)} warn -> {checks_path}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
