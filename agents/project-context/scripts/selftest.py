#!/usr/bin/env python3
"""selftest.py: offline regression tests of the project-context scripts.

No network, no API key. A local HTTP server (127.0.0.1, random port) serves the
fixture site of tests/fixtures/site/ (images drawn by tests/make_fixture_images.py
into a temporary copy). The fixture holds the traps the scripts must handle:

  - a cookie banner with a large green "Accept all" button (never the accent)
  - a menu icon (an SVG sprite inside a button) placed before the logo
  - a one-color black SVG logo shown white through a CSS filter on a dark page
    (the harvested file is unreadable on the brand background)
  - a gradient CTA whose light stop is the color the site names --fx-accent
  - a display webfont declared in @font-face but never loaded
  - cards with surface, border, radius and shadow; paragraphs and small print
  - a product screenshot, a team photo and a lazy illustration (kept), a tiled
    grain texture and a radial glow (dropped), a 1x1 tracking pixel
  - tests/fixtures/logo-clipped.svg: a wordmark whose viewBox cuts its last
    glyph and leaves a pictogram outside on purpose
  - tests/fixtures/voice/: three texts of a fictional founder, one of them
    with a two-step correction the shared gate blocks
  - fetch guard: file:// and ftp:// URLs, a redirect to ftp:// and a
    link-local host are refused by extract_brand and build_voice
  - proof: a context.json mixing V1 strings and proof objects validates
    against the schema; shared/scripts/proof.py check reports a stale metric
    and a testimonial without consent with their reason
  - registry: the example people.json and partners.json pass
    shared/scripts/registry.py check in a project-context folder; a photo
    stored without consent and a missing logo file fail
  - docs: a four-page deck PDF (tests/make_fixture_pdf.py) and notes go
    through ingest_docs.py extract; check refuses a rounded number, a claim
    cited on the wrong page, a missing document and a page out of range;
    apply writes only what was approved; no extractor gives exit 3

Usage:
    python3 scripts/selftest.py                 # everything (about 40 s)
    python3 scripts/selftest.py --only voice    # brand | logo | board | voice | fetch | proof | registry | docs
    python3 scripts/selftest.py --keep /tmp/pc-selftest

Exit 0 when every check passes, 1 otherwise, 2 when Playwright or Pillow is
missing (the voice, fetch, proof, registry and docs parts run without them).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List

HERE = Path(__file__).resolve().parent
FIX = HERE / "tests" / "fixtures"
REPO = HERE.parents[2]
PY = sys.executable

sys.path.insert(0, str(HERE))
from brand_common import color_distance, hex_to_rgb  # noqa: E402

RESULTS: List[tuple] = []


def check(name: str, cond: bool, detail: Any = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def near(a: str, b: str, tol: float = 6.0) -> bool:
    return bool(a) and color_distance(hex_to_rgb(a), hex_to_rgb(b)) <= tol


def run(args: List[str], cwd: Path = HERE) -> subprocess.CompletedProcess:
    return subprocess.run([PY] + args, capture_output=True, text=True, cwd=str(cwd))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a: Any) -> None:
        pass


def serve(root: Path) -> tuple:
    handler = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


# --- parts --------------------------------------------------------------------------

def part_brand(tmp: Path, port: int) -> Dict[str, Any]:
    print("brand extraction on the fixture site")
    pc = tmp / "pc"
    r = run(["extract_brand.py", "--url", f"http://127.0.0.1:{port}/index.html", "--out", str(pc)])
    check("extract_brand exits 0", r.returncode == 0, r.stderr[-800:])
    if r.returncode != 0:
        return {}
    d = json.loads((pc / "brand-draft.json").read_text())
    c = d["colors"]
    check("mode dark", d["mode"] == "dark", d["mode"])
    for role, want in (("bg", "#0b0d14"), ("text", "#f2f3f7"), ("text_secondary", "#a9adbd"), ("text_muted", "#6c7086"),
                       ("surface", "#161a26"), ("border", "#262b3a"), ("accent", "#a855f7"), ("accent_secondary", "#6d28d9"),
                       ("on_accent", "#ffffff")):
        check(f"colors.{role} = {want}", near(c.get(role, ""), want), c.get(role))
    check("cookie button green is not a brand color", all(not near(v, "#22c55e", 30) for v in c.values()), c)
    check("radius 12px from the cards", d.get("radius") == "12px", d.get("radius"))
    ext = d["extensions"]["extract_brand"]
    check("card shadow recorded", "24px" in str(ext.get("shadow", "")), ext.get("shadow"))
    check("display font: undeclared webfont skipped, Georgia rendered", d["fonts"]["display"]["family"] == "Georgia", d["fonts"]["display"])
    check("warning names the font that never loaded", any("Fixture Display" in w for w in d["warnings"]), d["warnings"])
    check("body font: system stack", d["fonts"]["body"]["family"] == "system-ui" and d["fonts"]["body"]["source"] == "system", d["fonts"]["body"])
    src = (pc / ext.get("logo_source", "missing")).read_text() if ext.get("logo_source") else ""
    check("logo is the home link image, not the menu icon", 'viewBox="0 0 260 40"' in src, ext.get("logo_source"))
    logos = d.get("logos") or {}
    check("logo variants: wordmark and mark, on light and on dark",
          all(k in (logos.get(v) or {}) for v in ("on_light", "on_dark") for k in ("wordmark", "mark")), logos)
    check("on_dark ink is light", not near((logos.get("on_dark") or {}).get("wordmark", {}).get("ink", "#000000"), "#000000", 60), logos)
    audit = d.get("logo_audit") or {}
    check("logo_audit is warn (harvested file unreadable on bg)", audit.get("status") == "warn", audit.get("status"))
    check("issue explains the dark-on-dark file", any("brand background" in i for i in audit.get("issues", [])), audit.get("issues"))
    check("every variant passes its pixel test", all(ch["status"] == "pass" for ch in audit.get("checks", [])), audit.get("checks"))
    pngs = ext.get("logo_png") or {}
    check("PNG fallbacks written", all((pc / p).is_file() for v in pngs.values() for p in v.values()) and len(pngs) == 2, pngs)
    m = json.loads((pc / "assets" / "site" / "manifest.json").read_text())
    roles = sorted(i["role"] for i in m["images"])
    check("images kept: illustration, product, team", roles == ["illustration", "product", "team"], roles)
    check("hero capture kept", bool(m.get("hero")) and (pc / m["hero"]["path"]).is_file(), m.get("hero"))
    rej = " ".join(x["source"] + " " + x["reason"] for x in m["rejected"])
    check("grain and glow rejected as decoration", "grain.png" in rej and "glow.png" in rej, m["rejected"])
    check("license founder-site on every image", m["license"] == "founder-site" and all(i["license"] == "founder-site" for i in m["images"]), m["license"])
    n = len(d["assets"].get("images", []))
    check("3 to 6 images in brand-draft.json", 3 <= n <= 6, n)
    cand = json.loads((pc / "brand-candidate.json").read_text())
    check("cookie banner hidden before measuring", cand["evidence"].get("cookie_banners_hidden", 0) >= 1, cand["evidence"].get("cookie_banners_hidden"))
    v = run([str(REPO / "shared" / "scripts" / "validate_json.py"), str(REPO / "shared" / "schemas" / "brand.schema.json"), str(pc / "brand-draft.json")])
    check("brand-draft.json valid against brand.schema.json", v.returncode == 0, v.stdout + v.stderr)
    return d


def part_logo(tmp: Path) -> None:
    print("logo pipeline on the clipped wordmark and on a raster logo")
    out = tmp / "clip"
    r = run(["logo_pipeline.py", "--logo", str(FIX / "logo-clipped.svg"), "--out", str(out), "--bg", "#ffffff", "--text", "#1f2937"])
    check("logo_pipeline exits 1 (warn: clipped source)", r.returncode == 1, r.stdout + r.stderr)
    a = json.loads((out / "brand-debug" / "logo" / "audit.json").read_text())
    va = a.get("viewbox_audit", {})
    check("viewBox audit: right side clipped", va.get("clipped_sides") == ["right"], va)
    check("pictogram outside the viewBox treated as excluded", va.get("excluded_shapes") == 1, va)
    ink = va.get("ink_box", [0, 0, 0, 0])
    check("measured ink reaches the ring's right edge (x >= 200)", ink[0] + ink[2] >= 200, ink)
    fixed = (out / "assets" / "logos" / "wordmark-on-light.svg").read_text()
    check("fixed SVG drops the excluded pictogram", 'r="15"' not in fixed, fixed[:200])
    check("both variants pass", all(c["status"] == "pass" for c in a["audit"]["checks"]), a["audit"]["checks"])
    # raster: an opaque PNG (white background) gets keyed out, then variants
    from PIL import Image
    src = tmp / "pc" / "assets" / "logos" / "wordmark-on-light.png"
    if src.is_file():
        im = Image.open(src).convert("RGBA")
        flat = Image.new("RGB", im.size, (255, 255, 255))
        flat.paste(im, mask=im.getchannel("A"))
        png = tmp / "opaque-logo.png"
        flat.save(png)
        out2 = tmp / "raster"
        r = run(["logo_pipeline.py", "--logo", str(png), "--out", str(out2), "--bg", "#0b0d14", "--text", "#f2f3f7"])
        a2 = json.loads((out2 / "brand-debug" / "logo" / "audit.json").read_text())
        check("raster: opaque background keyed out", any("keyed out" in n for n in a2.get("raster_notes", [])), a2.get("raster_notes"))
        check("raster: on_dark variant generated and readable (multi-color knockout flagged as warn)",
              any(c["variant"] == "on_dark" and (c["status"] == "pass" or (c["status"] == "warn" and "knocked out" in c["note"]))
                  for c in a2["audit"]["checks"]), a2["audit"]["checks"])


def part_board(tmp: Path) -> None:
    print("brand board")
    pc = tmp / "pc"
    r = run(["render_brand_preview.py", "--brand", str(pc / "brand-draft.json")])
    check("render_brand_preview exits 0 (no failed check)", r.returncode == 0, r.stdout + r.stderr)
    board = pc / "brand-debug" / "brand-board.jpg"
    check("board image under 150 KB", board.is_file() and board.stat().st_size <= 150 * 1024, board.stat().st_size if board.is_file() else None)
    res = json.loads((pc / "brand-debug" / "board-checks.json").read_text())
    names = [c["check"] for c in res["checks"]]
    check("board checks cover contrast, fonts and logo", any("on_accent" in n for n in names) and any("font" in n for n in names)
          and "logo audit" in names, names)
    check("display font reported as not rendered (not installed, falls back)", res["fonts_rendered"].get("display") in (True, False), res["fonts_rendered"])
    html = (pc / "brand-debug" / "brand-board.html").read_text()
    check("board shows both logo variants and the harvested file", html.count('class="logo-cell"') >= 5, html.count('class="logo-cell"'))
    r = run(["extract_brand.py", "--out", str(pc), "--finalize"])
    check("--finalize writes a valid brand.json", r.returncode == 0 and (pc / "brand.json").is_file(), r.stdout + r.stderr)


def part_voice(tmp: Path) -> None:
    print("voice pack")
    pc = tmp / "voice-pc"
    r = run(["build_voice.py", "--out", str(pc), "--brand-name", "Fixturely", str(FIX / "voice")])
    check("build_voice exits 0", r.returncode == 0, r.stdout[-600:] + r.stderr[-600:])
    if r.returncode != 0:
        return
    v = json.loads((pc / "voice" / "voice.json").read_text())
    cal = v["calibration"]
    check("calibration adjusted: the founder's two-step correction lowered to WARN",
          cal["status"] == "adjusted" and any(a["code"] == "not-x-its-y" and a["change"] == "level-warn" for a in cal["adjustments"]), cal)
    check("founder texts pass at 0 BLOCK after calibration", all(t["block_after"] == 0 for t in cal["texts"]), cal["texts"])
    ids = {x["id"] for x in v["rules"]}
    check("rules measured: sentence length, speaker, address, casing, exclamation, emoji",
          {"sentence-length", "speaker", "address", "brand-casing", "exclamation", "emoji"} <= ids, ids)
    check("address is you, speaker is we", v["metrics"]["address"]["form"] == "you" and any(x["rule"].endswith("as we.") for x in v["rules"]), v["rules"])
    check("examples are verbatim sentences with a source", v["examples"] and all((pc / e["source"]).is_file() and e["text"] in (pc / e["source"]).read_text()
                                                                                  for e in v["examples"]), v["examples"][:2])
    r = run(["build_voice.py", "--out", str(pc), "--check"])
    check("--check passes", r.returncode == 0, r.stdout + r.stderr)
    # the generated rules catch the founder's patterns in new copy
    draft = tmp / "draft.md"
    draft.write_text("Try FIXTURELY today! It ships with every plan!\n", encoding="utf-8")
    lint = REPO / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"
    r = subprocess.run([PY, str(lint), "--json", "--rules", str(pc / "voice" / "rules.json"), str(draft)], capture_output=True, text=True)
    codes = {f["code"]: f["level"] for f in json.loads(r.stdout)["files"][0]["findings"]}
    check("gate blocks a wrong brand casing", codes.get("brand-casing") == "BLOCK", codes)
    check("gate escalates repeated exclamation marks", codes.get("no-exclamation") == "BLOCK", codes)
    sys.path.insert(0, str(lint.parent))
    import lint_copy  # type: ignore
    rules_file = json.loads((pc / "voice" / "rules.json").read_text())
    bad_ok = True
    for rule in rules_file["rules"]:
        compiled = lint_copy._compile_rule(rule, "test")
        bad_ok &= all(compiled["regex"].search(b) for b in rule.get("bad", []))
        bad_ok &= not any(compiled["regex"].search(g) for g in rule.get("good", []))
    check("every generated rule fires on its bad example and not on its good one", bad_ok, rules_file["rules"])
    # a banned word the founder uses in their own text: conflict, exit 1
    r = run(["build_voice.py", "--out", str(tmp / "voice-conflict"), "--ban", "calendar", str(FIX / "voice")])
    check("banned word in the founder's own text: exit 1, conflict", r.returncode == 1 and "CONFLICT" in r.stdout, r.stdout[-400:])
    short = tmp / "short.md"
    short.write_text("We ship invoices. You get paid sooner.\n", encoding="utf-8")
    r = run(["build_voice.py", "--out", str(tmp / "voice-short"), str(short)])
    check("too little text: exit 3", r.returncode == 3, r.returncode)


class Redirect(Quiet):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(302)
        self.send_header("Location", "ftp://ftp.example/file.txt")
        self.end_headers()


def part_fetch(tmp: Path) -> None:
    print("fetch guard")
    import build_voice  # type: ignore
    import extract_brand  # type: ignore
    secret = tmp / "secret.txt"
    secret.write_text("local file that must never be read", encoding="utf-8")

    def refused(fn: Callable[[], Any], words: str) -> bool:
        try:
            fn()
        except ValueError as e:
            return words in str(e)
        except Exception:  # noqa: BLE001
            return False
        return False

    for url in (secret.as_uri(), "ftp://ftp.example/file.txt"):
        scheme = url.split(":")[0]
        check(f"extract_brand.http_get refuses {scheme}://", refused(lambda: extract_brand.http_get(url), "only http and https"))
        check(f"build_voice.fetch_url_text refuses {scheme}://", refused(lambda: build_voice.fetch_url_text(url), "only http and https"))
    extract_brand._ALLOW_PRIVATE = False
    check("extract_brand refuses a link-local host (third-party asset URL)",
          refused(lambda: extract_brand.http_get("http://169.254.169.254/latest/meta-data/"), "link-local"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/r"
        extract_brand._ALLOW_PRIVATE = True
        check("extract_brand refuses a redirect to ftp://", refused(lambda: extract_brand.http_get(url), "only http and https"))
        check("build_voice refuses a redirect to ftp://", refused(lambda: build_voice.fetch_url_text(url), "only http and https"))
    finally:
        extract_brand._ALLOW_PRIVATE = False
        srv.shutdown()

    env = {k: v for k, v in os.environ.items() if k != "FOG_ALLOW_SPEND"}
    env.update({"FIRECRAWL_API_KEY": "fixture-key", "EXA_API_KEY": "fixture-key"})
    for provider in ("firecrawl", "exa"):
        r = subprocess.run([sys.executable, str(HERE / "enrich_context.py"), "--url", "https://acme.example",
                            "--out", str(tmp / f"enrich-{provider}"), "--provider", provider],
                           capture_output=True, text=True, env=env, timeout=60)
        check(f"enrich_context --provider {provider} without --confirm-spend sends nothing (exit 4)",
              r.returncode == 4 and "--confirm-spend" in r.stderr, (r.returncode, r.stderr[-300:]))


def part_proof(tmp: Path) -> None:
    print("proof objects")
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=15)).isoformat()
    ctx = tmp / "proof-pc"
    ctx.mkdir(parents=True, exist_ok=True)
    context = json.loads((FIX / "context" / "context.json").read_text(encoding="utf-8"))
    for item in context["positioning"]["proof"]:
        if isinstance(item, dict) and item.get("date") == "RECENT":
            item["date"] = recent
            if "consent" in item and "date" in item["consent"]:
                item["consent"]["date"] = recent
    path = ctx / "context.json"
    path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    r = run([str(REPO / "shared" / "scripts" / "validate_json.py"), str(HERE.parent / "assets" / "context-schema.json"), str(path)])
    check("a context.json mixing V1 strings and proof objects validates", r.returncode == 0, r.stdout + r.stderr)
    r = run([str(REPO / "shared" / "scripts" / "proof.py"), "check", str(path), "--scope", "ads", "--json"])
    rows = {x["id"]: x for x in json.loads(r.stdout)["items"]} if r.returncode == 0 else {}
    check("proof.py check exits 0 with refused items", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
    check("V1 string: usable with a warning", rows.get("proof-0", {}).get("status") == "warning", rows.get("proof-0"))
    check("fresh metric usable", rows.get("waitlist", {}).get("status") == "usable", rows.get("waitlist"))
    check("stale metric refused with its reason", rows.get("pilot-2024", {}).get("status") == "refused" and "stale" in rows["pilot-2024"]["reason"], rows.get("pilot-2024"))
    check("testimonial without consent for ads refused", rows.get("lena-quote", {}).get("status") == "refused" and "not ads" in rows["lena-quote"]["reason"], rows.get("lena-quote"))
    broken = dict(context)
    broken["positioning"] = dict(context["positioning"], proof=[{"id": "x", "claim": "y", "kind": "testimonial", "source": "https://fixturely.example/a", "date": recent}])
    path.write_text(json.dumps(broken), encoding="utf-8")
    r = run([str(REPO / "shared" / "scripts" / "proof.py"), "check", str(path)])
    check("a testimonial with no consent object is malformed: exit 1", r.returncode == 1 and "consent" in r.stdout, r.stdout[-300:])


def part_registry(tmp: Path) -> None:
    print("registries")
    ctx = tmp / "registry-pc"
    examples = REPO / "shared" / "schemas" / "examples"
    for sub in ("assets/people", "assets/partners"):
        (ctx / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy(examples / "people.fixturely.json", ctx / "people.json")
    shutil.copy(examples / "partners.fixturely.json", ctx / "partners.json")
    for rel in ("assets/people/ana-ruiz.jpg", "assets/people/lena-park.jpg", "assets/partners/acme.svg", "assets/partners/acme-white.svg"):
        (ctx / rel).write_bytes(b"fixture")
    reg = str(REPO / "shared" / "scripts" / "registry.py")
    for name in ("people", "partners"):
        r = run([str(REPO / "shared" / "scripts" / "validate_json.py"), str(REPO / "shared" / "schemas" / f"{name}.schema.json"), str(ctx / f"{name}.json")])
        check(f"{name}.json validates against its shared schema", r.returncode == 0, r.stdout)
    r = run([reg, "check", str(ctx)])
    check("registry.py check passes on the example registries", r.returncode == 0, r.stdout + r.stderr)
    r = run([reg, "allowed", str(ctx), "--scope", "carousel", "--json"])
    allowed = {e["slug"]: e["allowed"] for e in json.loads(r.stdout)["entries"]} if r.returncode == 0 else {}
    check("carousel scope: operator and consented people pass, unknown and refused do not",
          allowed == {"ana-ruiz": True, "lena-park": True, "tom-weller": False, "acme": True, "northwind-ledger": False}, allowed)
    people = json.loads((ctx / "people.json").read_text())
    people["people"][2]["photo"] = "assets/people/tom-weller.jpg"
    (ctx / "assets/people/tom-weller.jpg").write_bytes(b"fixture")
    (ctx / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (ctx / "assets/partners/acme-white.svg").unlink()
    r = run([reg, "check", str(ctx)])
    check("a photo stored without consent fails the check", r.returncode == 1 and "photo stored without granted consent" in r.stdout, r.stdout)
    check("a missing logo_on_dark file fails the check", "acme-white.svg not found" in r.stdout, r.stdout)


def part_docs(tmp: Path) -> None:
    print("deck and notes")
    sys.path.insert(0, str(HERE / "tests"))
    from make_fixture_pdf import make_pdf  # type: ignore
    import ingest_docs  # type: ignore
    ctx = tmp / "docs-pc"
    deck = make_pdf(tmp / "deck.pdf")
    cands = FIX / "docs" / "candidates.json"
    have_pdf = bool(shutil.which("pdftotext"))
    try:
        import pypdf  # noqa: F401
        have_pdf = True
    except ImportError:
        pass
    saved = (ingest_docs.which, sys.modules.get("pypdf"))
    ingest_docs.which = lambda cmd: None
    sys.modules["pypdf"] = None  # type: ignore
    try:
        try:
            ingest_docs.extract(tmp / "no-extractor-pc", [str(deck)], "auto")
            check("no PDF extractor: refused with the install line", False)
        except ingest_docs.NoExtractor:
            check("no PDF extractor: refused with the install line", True)
    finally:
        ingest_docs.which = saved[0]
        if saved[1] is None:
            sys.modules.pop("pypdf", None)
        else:
            sys.modules["pypdf"] = saved[1]
    r = run(["ingest_docs.py", "extract", "--out", str(ctx), str(FIX / "docs" / "notes.md")])
    check("notes extract to one page", r.returncode == 0 and (ctx / "docs" / "notes.md.pages.json").is_file(), r.stdout + r.stderr)
    (tmp / "deck.pptx").write_bytes(b"PK fixture")
    r = run(["ingest_docs.py", "extract", "--out", str(ctx), str(tmp / "deck.pptx")])
    check("an unsupported type exits 2", r.returncode == 2 and "unsupported type" in r.stderr, r.stderr)
    if not have_pdf:
        print("  SKIP  PDF extraction: neither pdftotext nor pypdf is installed here")
        return
    r = run(["ingest_docs.py", "extract", "--out", str(ctx), str(deck)])
    pages = json.loads((ctx / "docs" / "deck.pdf.pages.json").read_text()) if r.returncode == 0 else {"pages": []}
    check("deck extracts to 4 pages", r.returncode == 0 and len(pages["pages"]) == 4, r.stdout + r.stderr)
    check("page 3 holds the traction numbers", "1 240 freelancers" in " ".join(pages["pages"][2]["text"].split()) if len(pages["pages"]) > 2 else False, pages)
    r = run(["ingest_docs.py", "check", "--out", str(ctx), str(cands), "--json"])
    rep = json.loads(r.stdout) if r.stdout.startswith("{") else {"proof": [], "fields": []}
    status = {x["id"]: x["status"] for x in rep["proof"]}
    fields = {x["field"]: x["status"] for x in rep["fields"]}
    check("check exits 1 when a candidate is refused", r.returncode == 1, r.stdout[-300:])
    check("claims on their page word for word pass", all(status.get(k) == "ok" for k in ("waitlist", "pilot-invoices", "lena-quote", "october-studios")), status)
    check("a rounded number is refused", status.get("waitlist-rounded") == "refused", status)
    check("a claim cited on the wrong page is refused", status.get("pilot-wrong-page") == "refused", status)
    check("a document never ingested is refused", status.get("memo-figure") == "refused", status)
    check("a page out of range is refused", status.get("page-out-of-range") == "refused", status)
    check("a field whose excerpt is not on its page is refused", fields == {"one_liner": "ok", "icp.pains": "ok", "icp.who": "refused"}, fields)
    lena = next((x for x in rep["proof"] if x["id"] == "lena-quote"), {})
    check("a testimonial candidate without consent is flagged for copy", any("consent unknown" in w for w in lena.get("warnings", [])), lena)
    nodate = next((x for x in rep["proof"] if x["id"] == "pilot-invoices"), {})
    check("a candidate without date asks the founder for it", any("no date" in w for w in nodate.get("warnings", [])), nodate)
    draft = ctx / "brand-debug" / "context-draft.json"
    r = run(["ingest_docs.py", "apply", "--out", str(ctx), str(cands), "--approve", "waitlist,waitlist-rounded"])
    check("apply refuses an approved candidate that fails, writes nothing", r.returncode == 1 and not draft.exists(), r.stdout)
    r = run(["ingest_docs.py", "apply", "--out", str(ctx), str(cands), "--approve", "waitlist,october-studios", "--approve-fields", "one_liner,icp.pains"])
    data = json.loads(draft.read_text()) if draft.is_file() else {}
    check("apply writes only the approved items", r.returncode == 0 and [p["id"] for p in data.get("positioning", {}).get("proof", [])] == ["waitlist", "october-studios"]
          and data.get("icp", {}).get("pains") == ["Friday afternoons lost chasing late invoices"] and "category" not in data, data)
    r = run(["ingest_docs.py", "apply", "--out", str(ctx), str(cands), "--approve", "waitlist"])
    again = json.loads(draft.read_text())
    check("apply twice does not duplicate a proof item", len(again["positioning"]["proof"]) == 2, again)
    r = run(["ingest_docs.py", "apply", "--out", str(ctx), str(cands)])
    check("apply without approval exits 2", r.returncode == 2, r.stderr)
    (ctx / "docs" / "notes.md").write_text("changed after extract\n", encoding="utf-8")
    r = run(["ingest_docs.py", "check", "--out", str(ctx), str(cands), "--json"])
    rep = json.loads(r.stdout) if r.stdout.startswith("{") else {"proof": []}
    changed = next((x for x in rep["proof"] if x["id"] == "october-studios"), {})
    check("a document changed after extract is refused", changed.get("status") == "refused" and "changed since extract" in changed.get("reason", ""), changed)
    r = run([str(REPO / "shared" / "scripts" / "validate_json.py"), str(HERE.parent / "assets" / "doc-candidates.schema.json"), str(cands)])
    check("the candidates fixture matches its schema", r.returncode == 0, r.stdout)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=("brand", "logo", "board", "voice", "fetch", "proof", "registry", "docs"))
    ap.add_argument("--keep", help="Keep the outputs in this folder instead of a temporary one")
    args = ap.parse_args(argv)
    tmp = Path(args.keep).resolve() if args.keep else Path(tempfile.mkdtemp(prefix="pc-selftest-"))
    if args.keep and tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        if args.only in (None, "fetch"):
            part_fetch(tmp)
        if args.only in (None, "proof"):
            part_proof(tmp)
        if args.only in (None, "registry"):
            part_registry(tmp)
        if args.only in (None, "docs"):
            part_docs(tmp)
        if args.only not in ("voice", "fetch", "proof", "registry", "docs"):
            try:
                import PIL  # noqa: F401
                import playwright  # noqa: F401
            except ImportError as e:
                print(f"selftest: {e}. Install scripts/requirements.txt, or run --only voice.", file=sys.stderr)
                return 2
            site = tmp / "site"
            shutil.copytree(FIX / "site", site)
            from tests.make_fixture_images import make_images  # type: ignore
            make_images(site)
            srv, port = serve(site)
            try:
                parts: List[Callable[[], Any]] = []
                if args.only in (None, "brand", "board", "logo"):
                    parts.append(lambda: part_brand(tmp, port))
                if args.only in (None, "logo"):
                    parts.append(lambda: part_logo(tmp))
                if args.only in (None, "board"):
                    parts.append(lambda: part_board(tmp))
                for p in parts:
                    p()
            finally:
                srv.shutdown()
        if args.only in (None, "voice"):
            part_voice(tmp)
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed" + (f", outputs in {tmp}" if args.keep else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
