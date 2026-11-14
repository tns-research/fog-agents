#!/usr/bin/env python3
"""
test_links.py

Offline tests of internal linking (scripts/links.py and the anchors and text
blocks crawl.py records). Fictional site fernwood.example served on
127.0.0.1 by tests/fixture_server.py, fictional Search Console bands and a
mini Astro source repository (tests/fixtures/links/); no network, no API key.
The repository is copied before git apply and never modified.

    python3 agents/seo-audit/tests/test_links.py      # prints "N passed, M failed", exit 0/1

run_tests.py can import it: run(check, tmp) with check(name, cond, detail="").
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
FIX = os.path.join(HERE, "fixtures", "links")
REPO = os.path.join(FIX, "repo")
PUBLIC = "https://fernwood.example"
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)

import fixture_server  # noqa: E402


def sh(script, *args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + [str(a) for a in args], capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def digest(root):
    h = hashlib.sha256()
    for d, _, files in sorted(os.walk(root)):
        for f in sorted(files):
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, root).encode())
            h.update(open(p, "rb").read())
    return h.hexdigest()


def U(path):
    return PUBLIC + path


def run(check, tmp):
    print("links.py")
    from seo_lib import parse_html
    sig = parse_html('<header><nav><a href="/a">Home</a></nav></header><main><p>See the <a href="/g">burn rate guide</a> first.'
                     '<p>Second paragraph left open<ul><li>one item about runway<li>two</ul>'
                     '<a href="/c"><p>card excerpt inside a link</p></a></main><footer><p>Footer words <a href="/l">legal</a></p></footer>',
                     "https://x.example/")
    zones = {a["url"].rsplit("/", 1)[-1]: a["zone"] for a in sig["anchors"]}
    check("parser: nav and footer links are chrome, body links are body", zones == {"a": "chrome", "g": "body", "c": "body", "l": "chrome"}, zones)
    texts = [b["text"] for b in sig["blocks"]]
    check("parser: implicit </p> and </li> close blocks, footer text stays out",
          "See the burn rate guide first." in texts and "Second paragraph left open" in texts
          and "one item about runway" in texts and not any("Footer" in t for t in texts), texts)
    b0 = next(b for b in sig["blocks"] if b["text"].startswith("See"))
    check("parser: the span of an existing link is recorded", [b0["text"][x:y] for x, y in b0["links"]] == ["burn rate guide"], b0)
    card = next(b for b in sig["blocks"] if b["text"].startswith("card"))
    check("parser: a block inside a link is link text from end to end", card["links"] == [[0, len(card["text"])]], card)

    srv, base = fixture_server.start(site_dir=os.path.join(FIX, "site"))
    run_dir = os.path.join(tmp, "run")
    try:
        rc, so, se = sh("crawl.py", base + "/", "--as-origin", PUBLIC, "--out-dir", run_dir, "--delay", "0")
    finally:
        srv.shutdown()
    check("crawl of fernwood.example exits 0", rc == 0, se[-400:])
    recs = {json.loads(l)["url"]: json.loads(l) for l in open(os.path.join(run_dir, "crawl.jsonl"))}
    home = recs[U("/")]
    check("crawl records anchor text and zone", {"url": U("/blog/"), "text": "articles", "zone": "body"} in home["internal_anchors"]
          and {"url": U("/blog/"), "text": "Blog", "zone": "chrome"} in home["internal_anchors"], home["internal_anchors"])
    check("crawl records body_inlinks apart from inlinks", recs[U("/guides/runway/")]["body_inlinks"] == 0
          and recs[U("/guides/runway/")]["inlinks"] >= 6, (recs[U("/guides/runway/")]["inlinks"], recs[U("/guides/runway/")]["body_inlinks"]))

    out = os.path.join(tmp, "links")
    rc, so, se = sh("links.py", "audit", "--crawl", os.path.join(run_dir, "crawl.jsonl"), "--bands", os.path.join(FIX, "bands.json"),
                    "--new-page", "/blog/cap-table/=" + os.path.join(FIX, "draft-cap-table.md"), "--out-dir", out, "--today", "2026-11-13")
    check("audit exits 0", rc == 0, se[-400:])
    doc = json.load(open(os.path.join(out, "links.json")))
    codes = {(x["code"], x["url"]) for x in doc["issues"]}
    check("orphan: a page only the sitemap knows", ("orphan", U("/fr/")) in codes, codes)
    check("orphan-body: a page reached only from the nav", ("orphan-body", U("/guides/runway/")) in codes, codes)
    check("anchor-generic: read more", ("anchor-generic", U("/about/")) in codes, codes)
    check("link-to-redirect with its fix", ("link-to-redirect", U("/about")) in codes
          and doc["redirect_fixes"] == [{"id": "R01", "old": U("/about"), "new": U("/about/"), "from": [U("/blog/burn-rate/")], "status": "proposed"}],
          doc["redirect_fixes"])
    check("weak-inlinks: the new page", ("weak-inlinks", U("/blog/cap-table/")) in codes, codes)
    check("the legal page and the server's own pages are never targets", not any(x["code"] == "orphan-body" and "legal" in x["url"] for x in doc["issues"]))
    S = {(s["source"], s["target"]): s for s in doc["suggestions"]}
    check("a Search Console query becomes an anchor where the page already wrote it",
          S.get((U("/blog/burn-rate/"), U("/guides/runway/")), {}).get("anchor") == "startup runway"
          and S[(U("/blog/burn-rate/"), U("/guides/runway/"))]["phrase_kind"] == "gsc"
          and S[(U("/blog/burn-rate/"), U("/guides/runway/"))]["confidence"] == "high", S.get((U("/blog/burn-rate/"), U("/guides/runway/"))))
    check("the new page gets an inbound link from its keyword",
          S.get((U("/guides/runway/"), U("/blog/cap-table/")), {}).get("phrase_kind") == "keyword")
    check("the orphan target gets a link from the page that names it", (U("/about/"), U("/blog/pitch-deck/")) in S)
    check("no link from a page that already links the target from its body", (U("/blog/pitch-deck/"), U("/blog/burn-rate/")) not in S)
    check("no link from the legal page", not any(s["source"] == U("/legal/") for s in doc["suggestions"]))
    check("no link across languages", not any(s["source"] == U("/fr/") for s in doc["suggestions"]))
    check("no anchor inside a longer name or across punctuation",
          not any(s["anchor"] in ("Burn Rate", "Burn Rate Monitor") or "," in s["anchor"] for s in doc["suggestions"]), [s["anchor"] for s in doc["suggestions"]])
    check("no link inside the text of an existing link (listing cards)", not any(s["source"] == U("/blog/") for s in doc["suggestions"]))
    check("every suggestion carries its sentence", all("[[" + s["anchor"] + "]]" in s["context"] for s in doc["suggestions"]))
    md = open(os.path.join(out, "links.md")).read()
    check("links.md has the sections", "## Internal linking" in md and "### Links to add" in md and "### Linking defects" in md
          and "### Links that go through a redirect" in md, md[:400])
    rc2, so2, se2 = sh("links.py", "audit", "--crawl", os.path.join(run_dir, "crawl.jsonl"), "--bands", os.path.join(FIX, "bands.json"),
                       "--new-page", "/blog/cap-table/=" + os.path.join(FIX, "draft-cap-table.md"), "--out-dir", os.path.join(tmp, "links2"), "--today", "2026-11-13")
    check("audit is deterministic", open(os.path.join(tmp, "links2", "links.md")).read() == md)

    before = digest(REPO)
    rc, so, se = sh("links.py", "patch", "--out-dir", out, "--repo", REPO, "--json")
    res = json.loads(so) if so.strip().startswith("{") else {}
    check("patch exits 0, every patch passes git apply --check", rc == 0 and res.get("git_apply_check_ok"), se[-400:] + so[-400:])
    check("every suggestion and the redirect fix are placed", not res.get("manual") and len(res.get("placed", [])) == len(doc["suggestions"]) + 1,
          res.get("manual"))
    work = os.path.join(tmp, "repo-applied")
    shutil.copytree(REPO, work)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)
    ok = all(subprocess.run(["git", "apply", os.path.join(out, p["patch"])], cwd=work, capture_output=True).returncode == 0 for p in res.get("patches", []))
    br = open(os.path.join(work, "src", "content", "blog", "burn-rate.md")).read()
    idx = open(os.path.join(work, "src", "pages", "index.astro")).read()
    rw = open(os.path.join(work, "src", "content", "guides", "runway.md")).read()
    check("patches apply on a copy", ok)
    check("Markdown link in .md, the redirect pointed at its final URL",
          "months of [startup runway](/guides/runway/) you" in br and "[read more](/about/)" in br, br)
    check("<a href> in .astro, the heading line left alone",
          '<p>Track your <a href="/blog/burn-rate/">burn rate</a> every month' in idx and "<h2>Burn rate</h2>" in idx, idx)
    check("code fences left alone", "runway = cash / burn rate\n" in rw and "monthly [burn rate](/blog/burn-rate/) of" in rw, rw)
    check("the source repository is never modified", digest(REPO) == before)
    rc, so, se = sh("links.py", "patch", "--out-dir", out, "--repo", REPO, "--only", "L01")
    one = json.load(open(os.path.join(out, "links-patch.json")))
    check("--only keeps the listed ids", rc == 0 and [p["id"] for p in one["placed"]] == ["L01"], one["placed"])
    rc, so, se = sh("links.py", "patch", "--out-dir", os.path.join(tmp, "nothing"), "--repo", REPO)
    check("patch without links.json is a usage error", rc == 2)
    bad = os.path.join(tmp, "old-crawl.jsonl")
    open(bad, "w").write(json.dumps({"url": U("/"), "status": 200, "internal_links": []}) + "\n")
    rc, so, se = sh("links.py", "audit", "--crawl", bad, "--out-dir", os.path.join(tmp, "old"))
    check("a crawl without anchors asks for a new crawl", rc == 2 and "crawl it again" in se, se)


if __name__ == "__main__":
    res = {"passed": 0, "failed": 0}

    def check(name, cond, detail=""):
        if cond:
            res["passed"] += 1
        else:
            res["failed"] += 1
            print(f"FAIL {name}: {str(detail)[:600]}")

    tmp = tempfile.mkdtemp(prefix="seo-links-tests-")
    try:
        run(check, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{res['passed']} passed, {res['failed']} failed")
    sys.exit(1 if res["failed"] else 0)
