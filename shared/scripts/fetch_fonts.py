#!/usr/bin/env python3
"""fetch_fonts.py: local font files for the Google Fonts families of a brand.json.

A brand whose families come from Google Fonts often has no `files` for them
(the page loaded them through a stylesheet the extraction did not capture,
a V1 file, a brand typed by hand). Every renderer that refuses remote assets
then falls back to the system stack. This script downloads the latin woff2
face of each weight and style the brand uses, writes it under
`assets/fonts/` next to brand.json and adds the `files` entries.

    python3 shared/scripts/fetch_fonts.py --brand <project>/project-context/brand.json [--dry-run] [--json]

Only Google Fonts families are fetched (source `google_fonts`, or a family
named in a fonts.googleapis.com `fonts_url`): their licenses (OFL, Apache)
allow the copy. Self-hosted families are never downloaded here; the founder
adds their files. A role that already has files is left alone. No key, no
cost; the only hosts called are fonts.googleapis.com and fonts.gstatic.com.

Exit codes: 0 every Google family has its files (or nothing to do), 1 at least
one family could not be fetched (brand.json still gets what was fetched),
2 usage or unreadable brand.json.

Importable: fetch_role_files(...) is used by renderers that keep the files in
their own folder without writing brand.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GOOGLE_CSS = "https://fonts.googleapis.com/css2"
# Tests point this at a local server (FOG_FONTS_CSS_BASE); 127.0.0.1 is then allowed too.
CSS_BASE = os.environ.get("FOG_FONTS_CSS_BASE") or GOOGLE_CSS
ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")
# Google serves woff2 with unicode-range subsets to a current browser.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MAX_FONT_BYTES = 4 * 1024 * 1024
FACE_RE = re.compile(r"(?:/\*\s*([\w-]+)\s*\*/\s*)?@font-face\s*{([^}]*)}", re.S)


def _get(url: str, allow_local: bool, timeout: float) -> bytes:
    host = urllib.parse.urlsplit(url).hostname or ""
    if host not in ALLOWED_HOSTS and not (allow_local and host in ("127.0.0.1", "localhost")):
        raise ValueError(f"refused host {host}")
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/css,font/woff2,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (host checked above)
        data = r.read(MAX_FONT_BYTES + 1)
    if len(data) > MAX_FONT_BYTES:
        raise ValueError("file too large")
    return data


def google_families(fonts_url: Optional[str]) -> List[str]:
    if not fonts_url or "fonts.googleapis.com" not in fonts_url:
        return []
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(fonts_url).query)
    return [f.split(":")[0].replace("+", " ").strip() for f in q.get("family", [])]


def is_google(font: Dict[str, Any], fonts_url: Optional[str]) -> bool:
    fam = (font.get("family") or "").strip().lower()
    return bool(fam) and (font.get("source") == "google_fonts" or fam in {f.lower() for f in google_families(fonts_url)})


def css_url(family: str, weights: List[int], italic: bool, base: str = CSS_BASE) -> str:
    ws = sorted(set(weights)) or [400]
    if italic:
        axis = "ital,wght@" + ";".join([f"0,{w}" for w in ws] + [f"1,{w}" for w in ws])
    else:
        axis = "wght@" + ";".join(str(w) for w in ws)
    return f"{base}?family={urllib.parse.quote_plus(family)}:{axis}&display=swap"


def parse_faces(css: str) -> List[Dict[str, Any]]:
    out = []
    for subset, body in FACE_RE.findall(css):
        prop = lambda n: (re.search(rf"{n}\s*:\s*([^;]+);", body) or [None, ""])[1].strip()  # noqa: E731
        url = re.search(r"url\(([^)]+)\)", prop("src") or "")
        if not url:
            continue
        w = re.findall(r"\d+", prop("font-weight") or "400")
        out.append({"subset": subset or "", "family": prop("font-family").strip("'\" "), "url": url.group(1).strip("'\" "),
                    "weight": int(w[0]) if w else 400, "weight_max": int(w[-1]) if w else 400,
                    "style": "italic" if "italic" in (prop("font-style") or "") else "normal",
                    "unicode_range": prop("unicode-range")})
    return out


def _latin(face: Dict[str, Any]) -> bool:
    if face["subset"]:
        return face["subset"] == "latin"
    ur = face["unicode_range"].upper()
    return not ur or "U+0000-00FF" in ur or "U+0000-00" in ur


def fetch_role_files(family: str, weights: List[int], dest: Path, rel_prefix: str, *, italic: bool = True,
                     css_base: str = CSS_BASE, timeout: float = 20.0) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Download the latin face of every weight (and italic when Google has it) of a Google family
    into dest. Returns (files entries with paths prefixed by rel_prefix, warnings)."""
    allow_local = not css_base.startswith(GOOGLE_CSS)
    warnings: List[str] = []
    css = None
    for ital in ((True, False) if italic else (False,)):
        try:
            css = _get(css_url(family, weights or [400], ital, css_base), allow_local, timeout).decode("utf-8", "replace")
            break
        except Exception as e:  # noqa: BLE001
            if not ital:
                warnings.append(f"{family}: stylesheet not fetched ({e})")
    if not css:
        return [], warnings
    faces = [f for f in parse_faces(css) if _latin(f)]
    if not faces:
        return [], warnings + [f"{family}: no latin face in the stylesheet"]
    files, seen = [], set()
    by_url: Dict[str, str] = {}
    stem = re.sub(r"[^A-Za-z0-9]+", "", family)
    for want in sorted(set(weights or [400])):
        for style in ("normal", "italic"):
            face = next((f for f in faces if f["style"] == style and f["weight"] <= want <= f["weight_max"]), None)
            if not face or (want, style) in seen:
                continue
            ext = Path(urllib.parse.urlsplit(face["url"]).path).suffix.lower() or ".woff2"
            fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(ext)
            if not fmt:
                continue
            shared = sum(1 for f in faces if f["url"] == face["url"]) > 1 or face["weight"] != face["weight_max"]
            name = by_url.get(face["url"]) or f"{stem}-{'var' if shared else want}{'-italic' if style == 'italic' else ''}{ext}"
            by_url[face["url"]] = name
            target = dest / name
            try:
                if not target.exists():
                    data = _get(face["url"], allow_local, timeout)
                    dest.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            except Exception as e:  # noqa: BLE001
                warnings.append(f"{family} {want} {style}: not downloaded ({e})")
                continue
            seen.add((want, style))
            files.append({"path": f"{rel_prefix}{name}", "weight": want, "style": style, "format": fmt})
    if not files:
        warnings.append(f"{family}: no face matched the weights {sorted(set(weights or [400]))}")
    return files, warnings


def complete_brand(brand: Dict[str, Any], brand_dir: Path, *, css_base: str = CSS_BASE, dry_run: bool = False,
                   timeout: float = 20.0) -> Dict[str, Any]:
    """Adds files to every Google Fonts role that has none. Returns a report."""
    fonts = brand.get("fonts") or {}
    report: Dict[str, Any] = {"roles": {}, "warnings": [], "changed": False}
    fetched: Dict[str, List[Dict[str, Any]]] = {}
    for role in ("display", "body"):
        f = fonts.get(role)
        if not isinstance(f, dict):
            continue
        fam = f.get("family")
        if f.get("files"):
            report["roles"][role] = {"family": fam, "status": "has files"}
            continue
        if not is_google(f, fonts.get("fonts_url")):
            report["roles"][role] = {"family": fam, "status": f"skipped ({f.get('source') or 'not Google Fonts'})"}
            continue
        weights = [w for w in (f.get("weights") or []) if isinstance(w, int)] or [400, 700]
        if dry_run:
            report["roles"][role] = {"family": fam, "status": "to fetch", "weights": weights}
            continue
        if fam in fetched:
            files, warns = fetched[fam], []
        else:
            files, warns = fetch_role_files(fam, weights, brand_dir / "assets" / "fonts", "assets/fonts/",
                                            css_base=css_base, timeout=timeout)
            fetched[fam] = files
        report["warnings"] += warns
        if files:
            f["files"] = files
            if not f.get("source"):
                f["source"] = "google_fonts"
            report["changed"] = True
            report["roles"][role] = {"family": fam, "status": "fetched", "files": [x["path"] for x in files]}
        else:
            report["roles"][role] = {"family": fam, "status": "failed"}
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--brand", required=True, help="brand.json (V2) to complete in place")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched, write nothing")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--css-base", default=CSS_BASE, help=argparse.SUPPRESS)
    ap.add_argument("--timeout", type=float, default=20.0)
    a = ap.parse_args(argv)
    path = Path(a.brand)
    try:
        brand = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(brand, dict):
            raise ValueError("not an object")
    except Exception as e:  # noqa: BLE001
        print(f"fetch_fonts: {path} unreadable: {e}", file=sys.stderr)
        return 2
    rep = complete_brand(brand, path.resolve().parent, css_base=a.css_base, dry_run=a.dry_run, timeout=a.timeout)
    if rep["changed"]:
        path.write_text(json.dumps(brand, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for role, r in rep["roles"].items():
            print(f"{role}: {r['family']}: {r['status']}" + (f" ({', '.join(r['files'])})" if r.get("files") else ""))
        for w in rep["warnings"]:
            print(f"warning: {w}")
    return 1 if any(r["status"] == "failed" for r in rep["roles"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
