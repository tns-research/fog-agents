#!/usr/bin/env python3
"""
test_visuals.py

Offline tests of scripts/article_visuals.py: the spec (schema and kind
rules), brand.json (roles, fallbacks of shared/schemas/README.md, V1 mapping,
logo variant by mode, logo audit, local font files), the contrast gate, the
HTML built from the templates, the standalone SVG, visuals.json against its
schema, the qa subcommand, the missing-renderer path, and, when Playwright
and Chromium are installed, a real render (sizes, cover 1200x630 x scale,
overflow caught). Render checks are skipped, not failed, without Playwright.

Fixtures: tests/fixtures/visuals/ (the fictional Larkspur brand of
larkspur.example, its logos, a spec with every kind).

    python3 tests/test_visuals.py            # alone: "N passed, M failed, K skipped"

From run_tests.py: import test_visuals; test_visuals.run(check, tmp).
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
SCRIPT = AGENT / "scripts" / "article_visuals.py"
FIX = HERE / "fixtures" / "visuals"
REPO = AGENT.parent.parent
VALIDATE = REPO / "shared" / "scripts" / "validate_json.py"
SPEC_SCHEMA = AGENT / "assets" / "visuals-spec.schema.json"
MANIFEST_SCHEMA = AGENT / "assets" / "visuals-manifest.schema.json"
BRAND_SCHEMA = REPO / "shared" / "schemas" / "brand.schema.json"

sys.path.insert(0, str(AGENT / "scripts"))
import article_visuals as av  # noqa: E402

SKIPPED = []


def skip(name, why):
    SKIPPED.append(name)
    print(f"  skip {name} ({why})")


def sh(*args, env=None):
    r = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(obj, p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return Path(p)


def project(tmp, name, brand):
    """A project-context folder holding brand.json and the fixture logos."""
    pc = Path(tmp) / name / "project-context"
    if pc.exists():
        shutil.rmtree(pc)
    shutil.copytree(FIX / "assets", pc / "assets")
    return dump(brand, pc / "brand.json")


def codes(issues, level=None):
    return {i["code"] for i in issues if level is None or i["level"] == level}


def svg_only_spec(spec):
    s = copy.deepcopy(spec)
    s["body"] = [v for v in s["body"] if v["kind"] in av.SVG_KINDS]
    return s


def run(check, tmp):
    print("visuals")
    tmp = Path(tmp) / "visuals"
    tmp.mkdir(parents=True, exist_ok=True)
    spec = load(FIX / "spec.json")
    brand = load(FIX / "brand.json")

    # ---- spec ---------------------------------------------------------
    check("visuals: fixture spec passes", av.validate_spec(spec) == [], av.validate_spec(spec))
    rc = subprocess.run([sys.executable, str(VALIDATE), str(SPEC_SCHEMA), str(FIX / "spec.json")], capture_output=True, text=True).returncode
    check("visuals: fixture spec valid against assets/visuals-spec.schema.json", rc == 0)
    rc = subprocess.run([sys.executable, str(VALIDATE), str(BRAND_SCHEMA), str(FIX / "brand.json")], capture_output=True, text=True).returncode
    check("visuals: fixture brand.json valid against the shared brand schema", rc == 0)

    bad = copy.deepcopy(spec)
    bad["body"][0]["alt"] = "   "
    check("visuals: blank alt blocks", "spec-empty" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    bad["cover"]["alt"] = ""
    check("visuals: empty cover alt blocks", av.validate_spec(bad) != [])
    bad = copy.deepcopy(spec)
    bad["body"][3]["data"]["stats"][0]["source"] = " "
    check("visuals: a figure without source blocks", "stat-source" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    del bad["body"][3]["data"]["stats"][1]["source"]
    check("visuals: a figure without the source key blocks (schema)", "spec-schema" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    bad["body"][0]["data"]["rows"][0]["cells"] = ["a", "b"]
    check("visuals: comparison row with the wrong cell count blocks", "spec-data" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    bad["body"][5]["data"]["yes"]["yes"] = {"question": "Third level?", "yes": {"outcome": "x"}, "no": {"outcome": "y"}}
    check("visuals: a third decision level blocks", av.validate_spec(bad) != [])
    bad = copy.deepcopy(spec)
    bad["body"][5]["data"]["no"] = {"outcome": "A", "question": "B?"}
    check("visuals: a branch with outcome and question blocks", "decision-branch" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    bad["body"][2]["data"]["steps"] = [{"title": "x"}] * 3
    check("visuals: a key of another kind blocks", "spec-data" in codes(av.validate_spec(bad)))
    bad = copy.deepcopy(spec)
    bad["body"][1]["data"]["steps"] = bad["body"][1]["data"]["steps"][:2]
    check("visuals: two steps block (3 to 7)", av.validate_spec(bad) != [])
    bad = copy.deepcopy(spec)
    bad["body"][1]["id"] = "v1"
    check("visuals: duplicate id blocks", "spec-id" in codes(av.validate_spec(bad)))

    bp = dump(bad, tmp / "bad-spec.json")
    rc, so, se = sh("--spec", bp, "--brand", FIX / "brand.json", "--out-dir", tmp / "bad" / "visuals")
    check("visuals: invalid spec exits 2 and builds nothing", rc == 2 and not (tmp / "bad" / "visuals").exists(), se[-300:])

    # ---- brand --------------------------------------------------------
    b, issues = av.load_brand(FIX / "brand.json")
    check("visuals: brand roles read from brand.json", b["hex"]["bg"] == "#f7f5f0" and b["hex"]["accent"] == "#2f5d50" and b["hex"]["surface"] == "#ffffff")
    check("visuals: light mode picks logos.on_light", b["logo"]["variant"] == "on_light" and b["logo"]["kind"] == "wordmark")
    check("visuals: fixture brand has no contrast BLOCK", not [i for i in av.brand_contrast(b) if i["level"] == "BLOCK"], av.brand_contrast(b))

    minimal = {"schema_version": "2.0", "name": "Minimal", "mode": "light",
               "colors": {"bg": "#ffffff", "text": "#222222", "accent": "#ffd400"},
               "fonts": {"display": {"family": "Nonexistent Display"}, "body": {"family": "Nonexistent Body"}}}
    mb, mi = av.load_brand(project(tmp, "minimal", minimal))
    h = mb["hex"]
    check("visuals: fallbacks surface=bg, text_muted=text, border=text_muted",
          h["surface"] == "#ffffff" and h["text_secondary"] == "#222222" and h["text_muted"] == "#222222" and h["border"] == "#222222")
    check("visuals: on_accent fallback is the colour that contrasts more (black on yellow)", h["on_accent"] == "#000000")
    check("visuals: accent too light to be text: figures fall back to colors.text", h["accent_ink"] == "#222222" and "accent-ink" in codes(mi))
    check("visuals: radius fallback 0 and no logo file: logo_text typeset", mb["radius"] == "0" and mb["logo"]["kind"] == "text" and mb["logo"]["text"] == "Minimal")

    dark = copy.deepcopy(brand)
    dark["mode"] = "dark"
    dark["colors"] = {"bg": "#10201b", "text": "#f4f1ea", "accent": "#9fd3c0"}
    db, _ = av.load_brand(project(tmp, "dark", dark))
    check("visuals: dark mode picks logos.on_dark", db["logo"]["variant"] == "on_dark")
    only_light = copy.deepcopy(dark)
    del only_light["logos"]["on_dark"]
    ob, oi = av.load_brand(project(tmp, "onlylight", only_light))
    check("visuals: on_light logo refused on a dark bg (ink under 3:1): logo_text", ob["logo"]["kind"] == "text" and "logo-variant" in codes(oi))
    audit = copy.deepcopy(brand)
    audit["logo_audit"] = {"status": "fail", "checks": [{"variant": "on_light", "kind": "wordmark", "status": "fail"}]}
    ab, ai = av.load_brand(project(tmp, "audit", audit))
    check("visuals: a logo that failed the audit is not used", ab["logo"]["variant"] != "on_light" and "logo-audit-fail" in codes(ai))
    v1 = {"bg": "#0b0b0f", "text_primary": "#ffffff", "accent": "#7c5cff", "font_heading": "'Some Serif', Georgia, serif",
          "font_body": "Inter, sans-serif", "logo_path": "project-context/assets/logos/wordmark-on-dark.svg"}
    vb, vi = av.load_brand(project(tmp, "v1", v1))
    check("visuals: V1 brand.json mapped (colors, font split, logo prefix stripped)",
          vb["hex"]["text"] == "#ffffff" and vb["font"]["display"] == "Some Serif" and vb["font"]["display_fallback"] == "Georgia, serif"
          and vb["logo"]["variant"] == "on_dark" and "brand-v1" in codes(vi))

    # ---- contrast gate --------------------------------------------------
    unreadable = copy.deepcopy(brand)
    unreadable["colors"] = {"bg": "#ffffff", "text": "#d8d8d8", "accent": "#2f5d50"}
    ub, _ = av.load_brand(project(tmp, "unreadable", unreadable))
    ui = av.brand_contrast(ub)
    check("visuals: unreadable text role blocks under 3:1", any(i["level"] == "BLOCK" and i["fg"] == "text" for i in ui), ui)
    grey = copy.deepcopy(brand)
    grey["colors"]["text_muted"] = "#8a8a8a"
    gb, _ = av.load_brand(project(tmp, "grey", grey))
    gi = [i for i in av.brand_contrast(gb) if i["fg"] == "text_muted"]
    check("visuals: muted text between 3:1 and 4.5:1 warns, does not block", gi and all(i["level"] == "WARN" for i in gi), gi)
    up = tmp / "unreadable" / "project-context" / "brand.json"
    rc, so, se = sh("--spec", FIX / "spec.json", "--brand", up, "--out-dir", tmp / "unreadable-out" / "visuals", "--no-render")
    check("visuals: unreadable brand exits 1", rc == 1 and "brand-contrast" in so, so[-300:])

    # ---- HTML -------------------------------------------------------------
    out = tmp / "html" / "visuals"
    rc, so, se = sh("--spec", FIX / "spec.json", "--brand", FIX / "brand.json", "--out-dir", out, "--no-render")
    pages = {p.stem: p.read_text(encoding="utf-8") for p in (out / "_src").glob("*.html")}
    check("visuals: --no-render writes one page per visual, exit 0", rc == 0 and set(pages) == {"cover", "v1", "v2", "v3", "v4", "v5", "v6"}, se[-300:] + so[-300:])
    check("visuals: pages carry the brand colours as CSS variables",
          all("--bg: #f7f5f0;" in t and "--accent: #2f5d50;" in t and "--surface: #ffffff;" in t for t in pages.values()))
    check("visuals: pages carry the brand families", all('"Fraunces", Georgia, serif' in t and '"Inter", system-ui' in t for t in pages.values()))
    check("visuals: no slot left, no remote asset",
          not any("{{" in t for t in pages.values()) and not any(("src=\"http" in t or "href=\"http" in t or "url(http" in t) for t in pages.values()))
    check("visuals: light brand inlines the on_light logo", "#1c1b17" in pages["v1"] and "#f4f1ea" not in pages["v1"])
    check("visuals: yes/no/partial cells drawn as labelled icons", 'aria-label="Oui"' in pages["v1"] and 'aria-label="Non"' in pages["v1"] and 'aria-label="En partie"' in pages["v1"])
    check("visuals: French spacing before the colon", " :" in pages["v1"])
    check("visuals: no manifest without PNG", not (out / "visuals.json").exists())
    rc2, _, _ = sh("--spec", FIX / "spec.json", "--brand", FIX / "brand.json", "--out-dir", out, "--no-render")
    again = {p.stem: p.read_text(encoding="utf-8") for p in (out / "_src").glob("*.html")}
    check("visuals: deterministic HTML", rc2 == 0 and again == pages)

    fontb = copy.deepcopy(brand)
    fontb["fonts"]["display"]["files"] = [{"path": "assets/fonts/Display.woff2", "weight": 600, "style": "normal", "format": "woff2"}]
    fp = project(tmp, "fonts", fontb)
    (fp.parent / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    (fp.parent / "assets" / "fonts" / "Display.woff2").write_bytes(b"wOF2 fake font for tests")
    fo = tmp / "fonts-out" / "visuals"
    sh("--spec", FIX / "spec.json", "--brand", fp, "--out-dir", fo, "--no-render")
    cov = (fo / "_src" / "cover.html").read_text(encoding="utf-8") if (fo / "_src" / "cover.html").exists() else ""
    check("visuals: local font files become @font-face, copied next to the page",
          '@font-face { font-family: "Fraunces"; src: url("fonts/Display.woff2") format("woff2")' in cov and (fo / "_src" / "fonts" / "Display.woff2").exists())

    # ---- SVG and manifest -------------------------------------------------
    so_spec = dump(svg_only_spec(spec), tmp / "svg-spec.json")
    art = tmp / "article-svg"
    rc, so, se = sh("--spec", so_spec, "--brand", FIX / "brand.json", "--out-dir", art / "visuals", "--format", "svg", "--no-render")
    svgs = sorted((art / "visuals").glob("*.svg"))
    ok = True
    for f in svgs:
        try:
            root = ET.parse(f).getroot()
            ok = ok and root.tag.endswith("svg") and root.find("{http://www.w3.org/2000/svg}title") is not None
        except ET.ParseError:
            ok = False
    check("visuals: SVG for cover, stat, steps, checklist, comparison parse as XML with a title", rc == 0 and len(svgs) == 5 and ok, se[-300:])
    croot = ET.parse(art / "visuals" / "cover.svg").getroot() if (art / "visuals" / "cover.svg").exists() else None
    check("visuals: SVG cover is 1200x630", croot is not None and croot.get("width") == "1200" and croot.get("height") == "630")
    mp = art / "visuals" / "visuals.json"
    rc_m = subprocess.run([sys.executable, str(VALIDATE), str(MANIFEST_SCHEMA), str(mp)], capture_output=True, text=True).returncode if mp.exists() else 1
    m = load(mp) if mp.exists() else {}
    check("visuals: visuals.json written and valid against its schema", rc_m == 0)
    check("visuals: manifest paths relative to the article folder, alt and after_h2 copied",
          m.get("cover", {}).get("path") == "visuals/cover.svg" and all(e["path"].startswith("visuals/") and e["alt"] and e["after_h2"] for e in m.get("body", []))
          and [e["id"] for e in m.get("body", [])] == ["v1", "v2", "v3", "v4"])
    _, so_all, _ = sh("--spec", FIX / "spec.json", "--brand", FIX / "brand.json", "--out-dir", tmp / "svg-all" / "visuals", "--format", "svg", "--no-render")
    check("visuals: timeline and decision have no SVG, reported", "svg-unsupported" in so_all and not (tmp / "svg-all" / "visuals" / "v5.svg").exists())
    rc, so, se = sh("qa", "--out-dir", art / "visuals")
    check("visuals: qa passes on a clean folder", rc == 0, so[-300:])
    m2 = copy.deepcopy(m)
    m2["body"][0]["alt"] = ""
    dump(m2, mp)
    rc, so, se = sh("qa", "--out-dir", art / "visuals")
    check("visuals: qa blocks an empty alt", rc == 1 and "alt" in so)
    dump(m, mp)
    (art / "visuals" / "v2.svg").write_text("<svg><unclosed></svg>", encoding="utf-8")
    rc, so, se = sh("qa", "--out-dir", art / "visuals")
    check("visuals: qa blocks an SVG that does not parse", rc == 1 and "svg-invalid" in so)

    # ---- PNG checks on synthetic images ------------------------------------
    if av.have_pillow():
        from io import BytesIO
        from PIL import Image, ImageDraw

        def png(img):
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        img = Image.new("RGB", (1200, 600), (247, 245, 240))
        d = ImageDraw.Draw(img)
        for y in range(0, 600, 12):
            d.line([(100, y), (1100, y)], fill=(20, 20, 20))
        d.rectangle([0, 200, 1199, 300], fill=(128, 128, 128))
        iss = av.png_checks("t", png(img), 1200, 600, 1, (247, 245, 240), False)
        check("visuals: a flat band of a foreign colour blocks (unrasterised tile)", "blank-band" in codes(iss, "BLOCK"), iss)
        img = Image.new("RGB", (1200, 900), (247, 245, 240))
        ImageDraw.Draw(img).rectangle([100, 50, 1100, 300], fill=(0, 0, 0))
        iss = av.png_checks("t", png(img), 1200, 900, 1, (247, 245, 240), False)
        check("visuals: a large empty band warns (dead space)", "dead-space" in codes(iss, "WARN"), iss)
        iss = av.png_checks("cover", png(Image.new("RGB", (1200, 600), (0, 0, 0))), 1200, 600, 1, (0, 0, 0), True)
        check("visuals: a cover that is not 1200x630 blocks", "cover-size" in codes(iss, "BLOCK"))
    else:
        for n in ("blank band", "dead space", "cover size"):
            skip(f"visuals: {n}", "Pillow not installed")

    # ---- missing renderer ---------------------------------------------------
    fake = tmp / "fake-pw" / "playwright"
    fake.mkdir(parents=True, exist_ok=True)
    (fake / "__init__.py").write_text("raise ImportError('playwright hidden by the test')\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(fake.parent) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    nr = tmp / "norender" / "visuals"
    rc, so, se = sh("--spec", FIX / "spec.json", "--brand", FIX / "brand.json", "--out-dir", nr, env=env)
    check("visuals: without Playwright exit 1, clear message, HTML still written",
          rc == 1 and "pip install playwright" in se and (nr / "_src" / "v1.html").exists() and not (nr / "visuals.json").exists(), se[-300:])

    # ---- real render ----------------------------------------------------------
    real = tmp / "article" / "visuals"
    rc, so, se = sh("--spec", FIX / "spec.json", "--brand", FIX / "brand.json", "--out-dir", real, "--format", "both", "--scale", "2")
    if rc == 1 and "Install the renderer" in se:
        for n in ("render exit 0", "cover 2400x1260", "body PNG 2400 wide", "manifest sizes", "no BLOCK", "overflow caught", "cover overflow caught"):
            skip(f"visuals: {n}", "Playwright or Chromium not installed")
        return
    check("visuals: real render exits 0 with 7 PNG", rc == 0 and len(list(real.glob("*.png"))) == 7, (so + se)[-500:])
    dims = av.png_size((real / "cover.png").read_bytes()) if (real / "cover.png").exists() else None
    check("visuals: cover PNG is 1200x630 at scale 2 (2400x1260)", dims == (2400, 1260), dims)
    man = load(real / "visuals.json") if (real / "visuals.json").exists() else {"body": []}
    sizes_ok = bool(man["body"])
    for e in man["body"]:
        d2 = av.png_size((real.parent / e["path"]).read_bytes())
        sizes_ok = sizes_ok and d2 is not None and d2[0] == 2400 and abs(d2[1] - 2 * e["height"]) <= 1 and e["width"] == 1200
    check("visuals: body PNG 2400 wide, manifest height x scale", sizes_ok)
    check("visuals: manifest lists PNG with the SVG beside", man.get("cover", {}).get("svg") == "visuals/cover.svg" and man["body"][0]["path"] == "visuals/v1.png")
    qa = load(real / "visuals-qa.json")
    check("visuals: fixture renders without BLOCK, every fit holds", qa["blocks"] == 0 and all(f["status"] == "ok" for v in qa["visuals"] for f in (v["fit"] or [])), qa["issues"])
    rc, so, se = sh("qa", "--out-dir", real)
    check("visuals: qa passes on the rendered folder", rc == 0, so[-300:])

    long_spec = copy.deepcopy(spec)
    long_spec["body"] = [long_spec["body"][0]]
    long_spec["body"][0]["data"]["rows"][0]["cells"][0] = "Hyperconfigurabilitedesplanningsmultiequipes"
    lp = dump(long_spec, tmp / "long-spec.json")
    rc, so, se = sh("--spec", lp, "--brand", FIX / "brand.json", "--out-dir", tmp / "long" / "visuals", "--scale", "1")
    check("visuals: a word wider than its cell blocks (overflow)", rc == 1 and "overflow" in so, so[-400:])
    cov_spec = copy.deepcopy(spec)
    cov_spec["body"] = []
    cov_spec["cover"]["title"] = "Planification " + "W" * 40 + " des equipes"
    cp = dump(cov_spec, tmp / "cover-spec.json")
    rc, so, se = sh("--spec", cp, "--brand", FIX / "brand.json", "--out-dir", tmp / "cover-long" / "visuals", "--scale", "1")
    check("visuals: a cover title that cannot fit at 48 px blocks", rc == 1 and ("text-too-long" in so or "overflow" in so), so[-400:])


if __name__ == "__main__":
    counts = {"passed": 0, "failed": 0}

    def _check(name, cond, detail=""):
        if cond:
            counts["passed"] += 1
        else:
            counts["failed"] += 1
            print(f"  FAIL {name} {detail}")

    keep = sys.argv[1] if len(sys.argv) > 1 else None
    d = keep or tempfile.mkdtemp(prefix="seo-visuals-")
    try:
        run(_check, d)
    finally:
        if not keep:
            shutil.rmtree(d, ignore_errors=True)
    print(f"{counts['passed']} passed, {counts['failed']} failed, {len(SKIPPED)} skipped")
    sys.exit(1 if counts["failed"] else 0)
