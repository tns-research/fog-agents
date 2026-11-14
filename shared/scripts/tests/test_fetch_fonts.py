#!/usr/bin/env python3
"""Offline tests of shared/scripts/fetch_fonts.py and of its use by
agents/seo-audit/scripts/article_visuals.py. A local HTTP server plays Google
Fonts: a css2 stylesheet with latin and cyrillic subsets, a variable face
shared by several weights, and fake woff2 bytes. No network beyond 127.0.0.1.

    python3 shared/scripts/tests/test_fetch_fonts.py
"""

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SCRIPT = HERE.parent / "fetch_fonts.py"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / "agents" / "seo-audit" / "scripts"))

RESULTS = {"passed": 0, "failed": 0}
HITS = []


def check(name, cond, detail=""):
    RESULTS["passed" if cond else "failed"] += 1
    if not cond:
        print(f"  FAIL {name} {detail}")


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        HITS.append(self.path)
        u = urllib.parse.urlsplit(self.path)
        port = self.server.server_address[1]
        if u.path == "/css2":
            fam = urllib.parse.parse_qs(u.query)["family"][0].split(":")[0]
            if fam == "Nofont":
                self.send_response(400)
                self.end_headers()
                return
            slug = fam.replace(" ", "")
            css = ""
            for style in ("normal", "italic"):
                if style == "italic" and "ital" not in u.query:
                    continue
                for w in (400, 600):
                    css += (f"/* cyrillic */\n@font-face {{ font-family: '{fam}'; font-style: {style}; font-weight: {w};"
                            f" src: url(http://127.0.0.1:{port}/s/{slug}-cyr-{style}.woff2) format('woff2');"
                            " unicode-range: U+0400-045F; }\n")
                    css += (f"/* latin */\n@font-face {{ font-family: '{fam}'; font-style: {style}; font-weight: {w};"
                            f" src: url(http://127.0.0.1:{port}/s/{slug}-lat-{style}.woff2) format('woff2');"
                            " unicode-range: U+0000-00FF, U+0131; }\n")
            body, ct = css.encode(), "text/css"
        elif u.path.startswith("/s/"):
            body, ct = b"wOF2" + u.path.encode(), "font/woff2"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(body)


def main():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/css2"
    os.environ["FOG_FONTS_CSS_BASE"] = base
    import fetch_fonts as ff

    tmp = Path(tempfile.mkdtemp())
    brand = {
        "schema_version": "2.0", "name": "Larkspur", "mode": "light",
        "colors": {"bg": "#F6F4EF", "text": "#1A1A17", "accent": "#2F5D50"},
        "fonts": {
            "display": {"family": "Fraunces", "weights": [600], "source": "google_fonts"},
            "body": {"family": "Inter Tight", "weights": [400, 600]},
            "fonts_url": "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;600&display=swap",
        },
    }
    bp = tmp / "brand.json"
    bp.write_text(json.dumps(brand), encoding="utf-8")

    r = subprocess.run([sys.executable, str(SCRIPT), "--brand", str(bp), "--dry-run", "--json"], capture_output=True, text=True,
                       env={**os.environ})
    rep = json.loads(r.stdout or "{}")
    check("dry run lists both Google roles, writes nothing", r.returncode == 0 and rep["roles"]["display"]["status"] == "to fetch"
          and rep["roles"]["body"]["status"] == "to fetch" and not (tmp / "assets").exists(), r.stdout + r.stderr)

    r = subprocess.run([sys.executable, str(SCRIPT), "--brand", str(bp), "--json"], capture_output=True, text=True, env={**os.environ})
    out = json.loads(bp.read_text(encoding="utf-8"))
    d, b = out["fonts"]["display"], out["fonts"]["body"]
    check("exit 0 and brand.json completed", r.returncode == 0 and d.get("files") and b.get("files"), r.stdout + r.stderr)
    check("family read from fonts_url gets source google_fonts", b.get("source") == "google_fonts")
    paths = [f["path"] for f in d["files"] + b["files"]]
    check("only latin faces downloaded", all("-cyr-" not in p for p in paths) and not any("cyr" in h for h in HITS), HITS)
    check("one file per distinct face url, shared by the weights", len(set(p for p in (f["path"] for f in b["files"]))) == 2
          and len(b["files"]) == 4, b["files"])
    check("files exist next to brand.json", all((tmp / p).exists() for p in paths))
    check("italic kept when Google has it", any(f["style"] == "italic" for f in b["files"]))
    sys.path.insert(0, str(ROOT / "shared" / "scripts"))
    from validate_json import validate
    schema = json.loads((ROOT / "shared" / "schemas" / "brand.schema.json").read_text(encoding="utf-8"))
    check("completed brand.json still valid against brand.schema.json", not validate(out, schema), validate(out, schema))

    before = len(HITS)
    r = subprocess.run([sys.executable, str(SCRIPT), "--brand", str(bp)], capture_output=True, text=True, env={**os.environ})
    check("second run: roles with files left alone, no request", r.returncode == 0 and len(HITS) == before and "has files" in r.stdout,
          r.stdout)

    sh = json.loads(json.dumps(brand))
    sh["fonts"]["display"] = {"family": "Brandsans", "source": "self_hosted"}
    sh["fonts"]["body"] = {"family": "Nofont", "source": "google_fonts"}
    sp = tmp / "b2" / "brand.json"
    sp.parent.mkdir()
    sp.write_text(json.dumps(sh), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "--brand", str(sp), "--json"], capture_output=True, text=True, env={**os.environ})
    rep = json.loads(r.stdout or "{}")
    check("self-hosted family never downloaded", rep["roles"]["display"]["status"].startswith("skipped"), rep)
    check("a family Google refuses exits 1 with a warning", r.returncode == 1 and rep["roles"]["body"]["status"] == "failed"
          and rep["warnings"], rep)

    try:
        ff._get("https://example.com/x.woff2", True, 5)
        refused = False
    except ValueError:
        refused = True
    check("hosts other than Google Fonts (and the local test server) are refused", refused)
    check("google_families reads a css2 URL", ff.google_families("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400")
          == ["Instrument Serif", "Inter"])

    r = subprocess.run([sys.executable, str(SCRIPT), "--brand", str(tmp / "missing.json")], capture_output=True, text=True)
    check("unreadable brand.json exits 2", r.returncode == 2)

    import article_visuals as av
    vb = tmp / "vis" / "brand.json"
    vb.parent.mkdir()
    vb.write_text(json.dumps(brand), encoding="utf-8")
    cache = tmp / "vis-cache"
    b1, issues = av.load_brand(vb, cache)
    fams = {f["family"] for f in b1["font"]["faces"]}
    check("article_visuals fetches a Google role without files into its cache", fams == {"Fraunces", "Inter Tight"}
          and all(Path(f["path"]).exists() for f in b1["font"]["faces"]), fams)
    check("article_visuals never writes brand.json", "files" not in json.loads(vb.read_text())["fonts"]["body"])
    check("article_visuals reports the fetch", any(i.get("code") == "font-fetched" for i in issues), issues)
    b2, issues2 = av.load_brand(vb, None)
    check("--no-font-fetch: no face, the role falls back with an INFO", not b2["font"]["faces"]
          and any(i.get("code") == "fonts-url-ignored" for i in issues2), issues2)

    srv.shutdown()
    print(f"{RESULTS['passed']} passed, {RESULTS['failed']} failed")
    return 1 if RESULTS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
