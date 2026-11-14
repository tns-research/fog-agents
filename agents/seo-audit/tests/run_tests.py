#!/usr/bin/env python3
"""
run_tests.py

Offline tests of seo-audit. Standard library only, no API key, no call to a
paid service: the site is the fictional swanbase.example served on 127.0.0.1
by tests/fixture_server.py, Search Console data and GEO answers are fictional
fixtures, the answer engine is tests/fixtures/geo/fake_answers.py. Outputs go
to a temporary folder (or --keep DIR); the repo is never written.

    python3 agents/seo-audit/tests/run_tests.py [-v] [--keep DIR] [--only NAME]

Covers: the HTML parser (attribute order, apostrophes, JSON-LD arrays,
@graph, invalid blocks), robots.txt (group choice, longest match), sitemaps,
Search Console CSV headers in English and French and compare exports; the
crawl of the fixture site (every planted defect found, lookup, determinism);
the bands (decline, quick win, CTR gap, lost, artifact, cannibalization,
thresholds override); the report gate (the April 2026 "Current title
(likely)" regression blocks); briefs and expect files; the served-HTML check
before and after the fix; state, diff between runs, shipping, 14/28/56-day
tracking; the GEO panel (spend gate, fake engine, manual capture, scores,
spread, unverified surface, AI crawler access); E-E-A-T measured on the
fictional larkspur.example (signals, evidence, fixed formula, determinism,
report gate, gained and lost on the next run); repo mode on its mini source
repository (source lines, patches checked by git apply, placeholders, fill
and check, repository untouched); the SERP extractor fixes; the topic registry,
the write mode, the article visuals and internal linking
(tests/test_topics.py, test_write.py, test_visuals.py, test_links.py);
--help of every script; no dash characters in the agent folder.

Exit 0 when every test passes, 1 otherwise.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
FIX = os.path.join(HERE, "fixtures")
GSC = os.path.join(FIX, "gsc")
GEO = os.path.join(FIX, "geo")
EXAMPLE = os.path.join(AGENT, "examples", "swanbase-example-20261012")
EEAT_SITE = os.path.join(FIX, "eeat-site")
EEAT_REPO = os.path.join(FIX, "eeat-repo")
TODAY = "2026-10-12"
PUBLIC = "https://swanbase.example"
LARK = "https://larkspur.example"

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, HERE)
import fixture_server  # noqa: E402
import seo_lib  # noqa: E402

RESULTS = {"passed": 0, "failed": 0}
VERBOSE = False


def check(name, cond, detail=""):
    if cond:
        RESULTS["passed"] += 1
        if VERBOSE:
            print(f"  ok   {name}")
    else:
        RESULTS["failed"] += 1
        print(f"  FAIL {name} {detail}")


def run(script, *args, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout, r.stderr


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def by_url(path):
    return {r["url"]: r for r in jsonl(path)}


# --------------------------------------------------------------------------

def t_lib(tmp):
    print("seo_lib")
    h = ('<html lang="fr"><head><title> Le  titre </title>'
         '<meta content="L\'accélérateur qu\'il vous faut" name="description">'
         '<meta name="robots" content="noindex">'
         '<link href="/a/" rel="canonical"><link rel="alternate" hreflang="en" href="/en/">'
         '<script type="application/ld+json">{"@type":["Article","NewsArticle"]}</script>'
         '<script type="application/ld+json">{"@context":"x","@graph":[{"@type":"BlogPosting","author":{"@type":"Person"}},{"@type":"BreadcrumbList"}]}</script>'
         '<script type="application/ld+json">{"@type":"FAQPage",}</script></head>'
         '<body><nav>menu one two</nav><main><h1>Un <b>H1</b></h1><p>quatre mots ici aujourd\'hui</p>'
         '<a href="/b">b</a><a href="https://other.example/x">x</a><a href="mailto:a@b.c">m</a></main></body></html>')
    s = seo_lib.parse_html(h, "https://site.example/page")
    check("meta with apostrophe and content before name", s["meta_description"] == "L'accélérateur qu'il vous faut", s["meta_description"])
    check("title whitespace normalised", s["title"] == "Le titre", s["title"])
    check("canonical resolved", s["canonical"] == "https://site.example/a/", s["canonical"])
    check("hreflang resolved", s["hreflang"] == [{"lang": "en", "href": "https://site.example/en/"}])
    types = sorted({t for b in s["jsonld"] for t in b["types"]})
    check("JSON-LD type arrays and @graph", types == ["Article", "BlogPosting", "BreadcrumbList", "NewsArticle"], types)
    check("invalid JSON-LD flagged", [b["valid"] for b in s["jsonld"]] == [True, True, False])
    check("Person nested in author is not a page type", "Person" not in types)
    check("H1 with inline markup", s["h1"] == ["Un H1"], s["h1"])
    check("main-content word count ignores nav (H1, paragraph, link texts)", s["word_count"] == 9, s["word_count"])
    check("anchors: mailto dropped", [a["url"] for a in s["anchors"]] == ["https://site.example/b", "https://other.example/x"])
    check("noindex read", seo_lib.is_noindex(s["meta_robots"], None) and seo_lib.is_noindex(None, "googlebot: none, noarchive"))

    rb = seo_lib.Robots("User-agent: *\nDisallow: /private/\nAllow: /private/open$\n\nUser-agent: GPTBot\nUser-agent: CCBot\nDisallow: /\n\n"
                        "User-agent: PerplexityBot\nAllow: /blog/\nDisallow: /\nCrawl-delay: 2\nSitemap: https://x.example/s.xml\nContent-Signal: ai-train=no\n")
    check("robots: grouped agents share rules", not rb.allowed("CCBot", "/") and not rb.allowed("gptbot", "/a"))
    check("robots: longest match wins", rb.allowed("PerplexityBot", "/blog/x") and not rb.allowed("PerplexityBot", "/about"))
    check("robots: $ anchor and * group", rb.allowed("Googlebot", "/private/open") and not rb.allowed("Googlebot", "/private/open2"))
    check("robots: crawl-delay, sitemap, content signal",
          rb.crawl_delay("PerplexityBot") == 2.0 and rb.sitemaps == ["https://x.example/s.xml"] and rb.content_signals == ["ai-train=no"])
    check("robots: empty file allows all", seo_lib.Robots("").allowed("GPTBot", "/"))
    sm = seo_lib.parse_sitemap('<sitemapindex><sitemap><loc><![CDATA[https://a.example/s1.xml]]></loc></sitemap></sitemapindex>')
    check("sitemap index with CDATA", sm["kind"] == "sitemapindex" and sm["locs"] == ["https://a.example/s1.xml"], sm)
    check("normalize keeps trailing slash, drops fragment and default port",
          seo_lib.normalize_url("HTTPS://A.example:443/x/#top") == "https://a.example/x/" and seo_lib.normalize_url("https://a.example/x") == "https://a.example/x")

    en = seo_lib.load_gsc(os.path.join(GSC, "ui-compare-queries-en.csv"))
    row = next(r for r in en["rows"] if r["query"] == "first pitch accelerator")
    check("GSC English compare export: both periods", en["compare"] and row["cur"]["clicks"] == 12 and row["prev"]["clicks"] == 40
          and abs(row["cur"]["ctr"] - 0.0286) < 0.0001 and row["prev"]["position"] == 4.2, row)
    fr = seo_lib.load_gsc(os.path.join(GSC, "ui-pages-fr.csv"))
    row = next(r for r in fr["rows"] if r["page"].endswith("/program/"))
    check("GSC French export: semicolon, decimal comma, percent", fr["dimensions"] == ["page"] and row["cur"]["position"] == 8.1
          and abs(row["cur"]["ctr"] - 0.022) < 0.0001 and row["cur"]["clicks"] == 45, row)
    api = seo_lib.load_gsc(os.path.join(GSC, "api-current.json"))
    check("GSC API JSON keys mapped by dimensions", api["dimensions"] == ["query", "page"] and api["rows"][0]["page"] == PUBLIC + "/")
    e = seo_lib.parse_html(
        '<html><head><meta name="author" content="Jo Doe"><meta property="article:modified_time" content="2026-03-04T10:00:00Z">'
        '<script type="application/ld+json">{"@graph":[{"@type":"BlogPosting","author":{"@id":"#jo"},"datePublished":"2026-01-02"},'
        '{"@id":"#jo","@type":"Person","name":"Jo Doe","url":"/team/jo/"},{"@type":"Organization","name":"Acme","sameAs":["https://x.example/a","https://y.example/b"]}]}</script>'
        '</head><body><div class="authority-badge">badge</div><p class="post-byline">By <a href="/team/jo/">Jo Doe</a></p>'
        '<p>Updated on March 4, 2026. Publié le 2 mars 2026.</p><time datetime="2026-01-02">2 Jan</time>'
        '<blockquote cite="https://src.example/a">q</blockquote><a href="#fn1">1</a><img src="/a.png"><img src="/b.png" alt="">'
        '<h2>Sources</h2></body></html>', "https://site.example/blog/x/")
    er = e["eeat"]
    check("eeat raw: byline with its link, 'authority' is not a byline",
          [(x["selector"], x["text"], x.get("links")) for x in er["elements"] if x["kind"] == "byline"]
          == [("p.post-byline", "By Jo Doe", ["https://site.example/team/jo/"])], er["elements"])
    check("eeat raw: time element and dated phrases in two languages",
          [x.get("datetime") for x in er["elements"] if x["kind"] == "time"] == ["2026-01-02"]
          and [(p["kind"], p["date"]) for p in er["date_phrases"]] == [("modified", "2026-03-04"), ("published", "2026-03-02")], er["date_phrases"])
    art = next(x for x in er["jsonld_entities"] if "BlogPosting" in x["types"])
    org = next(x for x in er["jsonld_entities"] if "Organization" in x["types"])
    check("eeat raw: JSON-LD author resolved through @id, sameAs counted",
          art["author"] == [{"name": "Jo Doe", "url": "/team/jo/", "type": "Person"}] and org["same_as"] == 2, er["jsonld_entities"])
    check("eeat raw: meta author and modified time, citations, reference heading",
          er["meta"]["author"] == "Jo Doe" and er["meta"]["article:modified_time"].startswith("2026-03-04")
          and len(er["citations"]) == 2 and "Sources" in er["headings"], er)
    check("images without alt keep their src and whether alt was written",
          e["images_no_alt_src"] == [{"src": "/a.png", "alt_attr": False}, {"src": "/b.png", "alt_attr": True}], e["images_no_alt_src"])
    check("text dates: ISO, day month year, month day year", seo_lib.text_date("2026-03-02T10:00:00Z") == "2026-03-02"
          and seo_lib.text_date("4 mars 2026") == "2026-03-04" and seo_lib.text_date("March 4, 2026") == "2026-03-04"
          and seo_lib.text_date("31/02/2026") is None)

    bad = os.path.join(tmp, "bad.csv")
    open(bad, "w").write("foo,bar\n1,2\n")
    try:
        seo_lib.load_gsc(bad)
        check("GSC CSV without known header refused", False)
    except seo_lib.InputError:
        check("GSC CSV without known header refused", True)


def crawl_site(tmp, name, routes="routes.json", site=fixture_server.SITE, public=PUBLIC):
    srv, base = fixture_server.start(site_dir=site, routes_file=routes)
    out = os.path.join(tmp, name)
    try:
        rc, so, se = run("crawl.py", base + "/", "--as-origin", public, "--out-dir", out, "--delay", "0")
    finally:
        srv.shutdown()
    return rc, so, se, out


def t_crawl(tmp):
    print("crawl.py")
    rc, so, se, out = crawl_site(tmp, "run1")
    check("crawl exits 0", rc == 0, se[-500:])
    pages = by_url(os.path.join(out, "crawl.jsonl"))
    summ = json.load(open(os.path.join(out, "crawl-summary.json")))
    U = lambda p: PUBLIC + p  # noqa: E731
    expect = {
        "/program/": ["canonical-home", "sitemap-non-canonical"],
        "/blog/": ["description-missing"],
        "/blog/first-pitch/": ["og-url-mismatch", "title-duplicate"],
        "/blog/pitch-deck-mistakes/": ["slash-duplicate", "jsonld-invalid", "title-duplicate"],
        "/blog/pitch-deck-mistakes": ["canonical-other"],
        "/old-program/": ["redirect", "sitemap-redirect"],
        "/events/": ["thin-raw-html", "h1-missing"],
        "/apply/": ["noindex", "sitemap-noindex"],
        "/legal/": ["noindex"],
        "/about/": ["status-4xx"],
        "/private/": ["blocked-by-robots"],
        "/": ["hreflang-not-reciprocal", "broken-internal-link"],
        "/blog/orphan-guide/": ["orphan-in-sitemap"],
    }
    for path, codes in expect.items():
        got = pages.get(U(path), {}).get("issues", [])
        check(f"crawl finds {', '.join(codes)} on {path}", all(c in got for c in codes), got)
    check("clean page has no error issue", not [c for c in pages[U("/fr/")]["issues"] if c not in ("orphan-in-sitemap",)], pages[U("/fr/")]["issues"])
    check("redirect line keeps its chain, no content", pages[U("/old-program/")]["redirect_chain"][0]["status"] == 301
          and pages[U("/old-program/")]["title"] is None)
    check("X-Robots-Tag header read", pages[U("/legal/")]["x_robots_tag"] == "noindex" and not pages[U("/legal/")]["indexable"])
    check("meta with apostrophe kept", "you'll want" in (pages[U("/program/")]["meta_description"] or ""))
    check("BlogPosting found in @graph with type list", {"BlogPosting", "BreadcrumbList"} <= set(pages[U("/blog/first-pitch/")]["jsonld_types"]))
    check("URLs reported with the production origin", all(u.startswith(PUBLIC) for u in pages))
    codes = {i["code"]: i for i in summ["issues"]}
    check("sitemap on another host flagged", "sitemap-other-host" in codes and codes["sitemap-other-host"]["severity"] == "error")
    check("sitemap URLs read", summ["sitemap_urls"] == 10, summ["sitemap_urls"])
    ai = {r["token"]: r for r in summ["ai_crawlers"]}
    check("AI crawler table in summary", not ai["GPTBot"]["allowed"]["/"] and ai["ClaudeBot"]["allowed"]["/"])
    check("broken link listed with its source", {"from": U("/"), "to": U("/about/"), "status": 404} in summ["broken_links"])
    rc, so, se = run("crawl.py", "--lookup", os.path.join(out, "crawl.jsonl"), U("/program/"))
    ref = json.loads(so) if rc == 0 else {}
    lines = open(os.path.join(out, "crawl.jsonl")).read().splitlines()
    n = int(ref.get("ref", "x:0").split(":")[1])
    check("lookup prints crawl.jsonl:N and the fields", rc == 0 and json.loads(lines[n - 1])["url"] == U("/program/")
          and ref["title"] == json.loads(lines[n - 1])["title"])
    rc, so, se = run("crawl.py", "--lookup", os.path.join(out, "crawl.jsonl"), U("/nope/"))
    check("lookup of an uncrawled URL exits 1", rc == 1)
    rc2, _, _, out2 = crawl_site(tmp, "run1-again")
    check("crawl is deterministic", open(os.path.join(out, "crawl.jsonl")).read() == open(os.path.join(out2, "crawl.jsonl")).read())
    srv, base = fixture_server.start()
    try:
        rc, so, se = run("crawl.py", base + "/nothing-here/", "--out-dir", os.path.join(tmp, "dead"), "--delay", "0", "--no-variants")
    finally:
        srv.shutdown()
    check("start URL not 200 exits 1", rc == 1, so + se)
    rc, so, se = run("crawl.py", "ftp://x", "--out-dir", tmp)
    check("bad start URL is a usage error", rc == 2)
    return out


def t_bands(tmp, run1):
    print("gsc_bands.py")
    rc, so, se = run("gsc_bands.py", "--current", os.path.join(GSC, "api-current.json"), "--prior", os.path.join(GSC, "api-prior.json"),
                     "--site", PUBLIC, "--out-dir", run1, "--today", TODAY)
    check("bands exit 0", rc == 0, se)
    b = json.load(open(os.path.join(run1, "bands.json")))
    pages = {r["page"]: r for r in b["pages"]}
    queries = {r["query"]: r for r in b["queries"]}
    fp = pages.get(PUBLIC + "/blog/first-pitch/", {})
    check("decline: page lost >= 20 % of >= 10 prior clicks, cause position",
          fp.get("primary_band") == "decline" and fp.get("decline_cause") == "position", fp.get("bands"))
    check("lost: fell out of the top 20", pages.get(PUBLIC + "/blog/orphan-guide/", {}).get("primary_band") == "lost")
    check("quick win: positions 4 to 20 with impressions", pages.get(PUBLIC + "/program/", {}).get("primary_band") == "quick_win")
    check("artifact flagged, not a band", pages.get(PUBLIC + "/events/", {}).get("artifact_suspect") is True
          and pages[PUBLIC + "/events/"]["bands"] == [])
    check("CTR gap against the site's own bucket median", "ctr_gap" in queries.get("pre seed program europe", {}).get("bands", []))
    check("brand query in top 3 is in no band", "swanbase" not in queries)
    check("priority: lost before decline before quick win",
          [r["primary_band"] for r in b["pages"]][:3] == ["lost", "decline", "decline"], [r["primary_band"] for r in b["pages"]])
    c = b["cannibalization"]
    check("cannibalization with slash variants", len(c) == 1 and c[0]["query"] == "pitch deck mistakes" and c[0]["slash_variants"]
          and len(c[0]["pages"]) == 3, c)
    check("thresholds come from the asset", b["thresholds"]["decline"]["max_change_pct"] == -20 and b["thresholds"]["quick_win"]["position_max"] == 20)
    cfg = os.path.join(tmp, "config.json")
    json.dump({"_comment": "test", "gsc_bands": {"quick_win": {"min_impressions": 5000}}}, open(cfg, "w"))
    rc, so, se = run("gsc_bands.py", "--current", os.path.join(GSC, "api-current.json"), "--prior", os.path.join(GSC, "api-prior.json"),
                     "--config", cfg, "--out-dir", os.path.join(tmp, "bands-cfg"), "--today", TODAY)
    b2 = json.load(open(os.path.join(tmp, "bands-cfg", "bands.json")))
    check("project config overrides one threshold", rc == 0 and b2["counts"]["pages"].get("quick_win", 0) == 0
          and b2["thresholds"]["quick_win"]["position_max"] == 20)
    rc, so, se = run("gsc_bands.py", "--current", os.path.join(GSC, "ui-compare-queries-en.csv"), os.path.join(GSC, "ui-pages-fr.csv"),
                     "--out-dir", os.path.join(tmp, "bands-csv"), "--today", TODAY)
    b3 = json.load(open(os.path.join(tmp, "bands-csv", "bands.json")))
    check("UI CSV exports: query declines from the compare file", rc == 0 and
          {r["query"]: r for r in b3["queries"]}["first pitch accelerator"]["primary_band"] == "decline")
    check("UI CSV exports: limitations say what is missing",
          any("cannibalization not computed" in l for l in b3["limitations"]) and any("Pages have no prior" in l for l in b3["limitations"]))
    rc, so, se = run("gsc_bands.py", "--current", os.path.join(GSC, "api-current.json"), "--out-dir", os.path.join(tmp, "bands-noprior"), "--today", TODAY)
    b4 = json.load(open(os.path.join(tmp, "bands-noprior", "bands.json")))
    check("no prior period: no decline, said in limitations", rc == 0 and not b4["counts"]["pages"].get("decline")
          and any("No prior period" in l for l in b4["limitations"]))
    rc, so, se = run("gsc_bands.py", "--current", os.path.join(tmp, "missing.csv"), "--out-dir", tmp)
    check("unreadable export exits 2", rc == 2)
    cli = os.path.join(tmp, "cli-country.json")
    json.dump({"responseAggregationType": "byPage", "rows": [
        {"keys": ["pitch deck", PUBLIC + "/blog/deck/", "fra"], "clicks": 4, "impressions": 200, "ctr": 0.02, "position": 7.0},
        {"keys": ["pitch deck", PUBLIC + "/blog/deck/", "usa"], "clicks": 50, "impressions": 900, "ctr": 0.05, "position": 3.0}]},
        open(cli, "w"))
    rc, so, se = run("gsc_bands.py", "--current", cli, "--dimensions", "query,page,country", "--country", "fr",
                     "--out-dir", os.path.join(tmp, "bands-country"), "--today", TODAY)
    b5 = json.load(open(os.path.join(tmp, "bands-country", "bands.json")))
    q5 = {r["query"]: r for r in b5["queries"]}.get("pitch deck", {})
    check("gsc CLI JSON with a country dimension: --country fr keeps France only", rc == 0 and "quick_win" in q5.get("bands", []), q5)
    rc, so, se = run("gsc_bands.py", "--current", cli, "--dimensions", "query,page,country", "--country", "zz",
                     "--out-dir", os.path.join(tmp, "bands-country2"))
    check("unknown country code exits 2", rc == 2)


def t_report_gate(tmp, run1):
    print("check_report.py")
    crawl = os.path.join(run1, "crawl.jsonl")
    reg = os.path.join(FIX, "regression-20260428", "report-excerpt.md")
    rc, so, se = run("check_report.py", reg, "--crawl", crawl, "--json")
    res = json.loads(so)
    codes = {f["code"] for f in res["findings"]}
    check("April 2026 regression blocks (guessed titles, no crawl line)", rc == 1 and {"guessed-current", "no-crawl-ref"} <= codes, codes)
    recs = jsonl(crawl)
    n = next(i for i, r in enumerate(recs, 1) if r["url"] == PUBLIC + "/program/")
    title = recs[n - 1]["title"]
    good = os.path.join(tmp, "good.md")
    open(good, "w").write(f"# Report\n\n**Current title:** `{title}` (crawl.jsonl:{n})\n"
                          f"**Current meta description:** `{recs[n - 1]['meta_description']}` (crawl.jsonl:{n})\n\n"
                          f"| URL | Current title | Proposed |\n|---|---|---|\n| /blog/ | `{recs[3]['title'].replace('|', chr(92) + '|')}` (crawl.jsonl:4) | x |\n"
                          f"| /events/ | `(missing)` (crawl.jsonl:{n}) | x |\n")
    rc, so, se = run("check_report.py", good, "--crawl", crawl, "--json")
    res = json.loads(so)
    check("table with an escaped pipe passes, (missing) on a page that has a title blocks",
          rc == 1 and [f["line"] for f in res["findings"]] == [9], res["findings"])
    open(good, "w").write(f"**Current title:** `{title}` (crawl.jsonl:{n})\n**Current H1:** `The program` (crawl.jsonl:{n})\n")
    rc, so, se = run("check_report.py", good, "--crawl", crawl)
    check("exact quotes with their crawl line pass", rc == 0, so)
    open(good, "w").write(f"**Current title:** `{title} 2026` (crawl.jsonl:{n})\n**Current title:** `x` (crawl.jsonl:999)\n")
    rc, so, se = run("check_report.py", good, "--crawl", crawl, "--json")
    codes = [f["code"] for f in json.loads(so)["findings"]]
    check("edited quote and unknown line block", rc == 1 and codes == ["mismatch", "bad-crawl-ref"], codes)


def t_briefs_state_verify(tmp, run1):
    print("write_briefs.py, verify_served.py, seo_state.py")
    state = os.path.join(tmp, "project", "seo-audit", "state.json")
    briefs = os.path.join(tmp, "project", "seo-audit", "briefs")
    rc, so, se = run("seo_state.py", "init", "--state", state, "--project", "swanbase", "--domain", PUBLIC)
    check("state init", rc == 0 and os.path.exists(state))
    rc, so, se = run("write_briefs.py", "--bands", os.path.join(run1, "bands.json"), "--crawl", os.path.join(run1, "crawl.jsonl"),
                     "--out-dir", briefs, "--date", TODAY, "--state", state)
    check("briefs written", rc == 0, se)
    st = json.load(open(state))
    ids = sorted(st["briefs"])
    check("each brief registered open in the state", len(ids) == 5 and all(b["status"] == "open" for b in st["briefs"].values()), ids)
    by = {b["url"]: b for b in st["briefs"].values()}
    check("decline page gets an update brief", by.get(PUBLIC + "/blog/first-pitch/", {}).get("action") == "update")
    check("quick win at position 8 gets a refine brief", by.get(PUBLIC + "/program/", {}).get("action") == "refine")
    m = by.get(PUBLIC + "/blog/pitch-deck-mistakes/", {})
    check("slash variants give a merge brief on the canonical URL", m.get("action") == "merge")
    exp = json.load(open(os.path.join(briefs, m["id"], "expect.json")))
    check("merge expect lists the redirect to verify", exp["redirects"] == [PUBLIC + "/blog/pitch-deck-mistakes"])
    check("overlapping page with another main query is not merged", PUBLIC + "/blog/first-pitch/" not in exp["redirects"])
    md = open(os.path.join(briefs, by[PUBLIC + "/program/"]["id"], "brief.md")).read()
    check("brief says rewrite at the existing URL, never a new one", "Never create a new URL" in md and "(keep it)" in md)
    check("brief lists the crawl blocker", "`canonical-home`" in md)
    rc, so, se = run("check_report.py", *[os.path.join(briefs, i, "brief.md") for i in ids], "--crawl", os.path.join(run1, "crawl.jsonl"))
    check("every brief passes the report gate", rc == 0, so)
    fp = by[PUBLIC + "/blog/first-pitch/"]["id"]
    rc, so, se = run("seo_state.py", "open-brief", "--state", state, "--id", "dup", "--url", PUBLIC + "/blog/first-pitch/",
                     "--action", "expand", "--brief", "x.md")
    check("a second open brief on the same URL is refused", rc == 1)

    expect = os.path.join(briefs, fp, "expect.json")
    srv, base = fixture_server.start()
    try:
        rc, so, se = run("verify_served.py", "--expect", expect, "--fetch-base", base, "--out", os.path.join(tmp, "verify-before.json"), "--today", TODAY)
    finally:
        srv.shutdown()
    v = json.load(open(os.path.join(tmp, "verify-before.json")))
    failed = {c["check"] for c in v["pages"][0]["checks"] if c["status"] == "fail"}
    check("verify before the fix fails on og:url, sitemap host and jargon", rc == 1 and failed == {"og_url", "sitemap", "jargon"}, failed)
    srv, base = fixture_server.start(routes_file="routes-fixed.json")
    try:
        rc, so, se = run("verify_served.py", "--expect", expect, "--fetch-base", base, "--out", os.path.join(tmp, "verify-after.json"),
                         "--today", TODAY, "--check-links")
        rc_m, so_m, _ = run("verify_served.py", "--expect", os.path.join(briefs, m["id"], "expect.json"), "--fetch-base", base, "--today", TODAY,
                            "--out", os.path.join(tmp, "verify-merge.json"))
        rc_u, so_u, _ = run("verify_served.py", "--url", PUBLIC + "/apply/", "--fetch-base", base, "--today", TODAY)
        rc_t, so_t, _ = run("verify_served.py", "--url", PUBLIC + "/", "--title", "Another title", "--jsonld-types", "Organization,FAQPage",
                            "--fetch-base", base, "--today", TODAY)
    finally:
        srv.shutdown()
    check("verify after the fix passes", rc == 0, so)
    vm = {c["check"]: c["status"] for c in json.load(open(os.path.join(tmp, "verify-merge.json")))["pages"][0]["checks"]}
    check("merge: the 301 of the variant passes, the invalid JSON-LD still fails", rc_m == 1 and vm.get("redirects") == "pass"
          and vm.get("jsonld_valid") == "fail", vm)
    check("noindex page fails indexable", rc_u == 1 and "indexable" in so_u)
    check("wrong title and missing JSON-LD type fail", rc_t == 1 and "title" in so_t and "FAQPage" in so_t, so_t)
    rc, so, se = run("verify_served.py", "--url", "http://127.0.0.1:9/x/")
    check("unreachable page exits 2", rc == 2)

    rc, so, se = run("seo_state.py", "verified", "--state", state, "--id", fp, "--report", os.path.join(tmp, "verify-after.json"))
    check("verification refused before ship", rc == 1)
    rc, so, se = run("seo_state.py", "ship", "--state", state, "--id", fp, "--date", TODAY)
    check("ship schedules 14/28/56", rc == 0 and "14d on 2026-10-29" in so and "56d on 2026-12-10" in so, so)
    rc, so, se = run("seo_state.py", "verified", "--state", state, "--id", fp, "--report", os.path.join(tmp, "verify-before.json"))
    check("failed verification recorded, brief stays shipped", rc == 1 and json.load(open(state))["briefs"][fp]["status"] == "shipped")
    rc, so, se = run("seo_state.py", "verified", "--state", state, "--id", fp, "--report", os.path.join(tmp, "verify-after.json"))
    check("passed verification moves the brief to verified", rc == 0 and json.load(open(state))["briefs"][fp]["status"] == "verified")

    pid = "20260825-program"
    run("seo_state.py", "drop", "--state", state, "--id", by[PUBLIC + "/program/"]["id"], "--reason", "test: replaced by an older brief")
    rc, so, se = run("seo_state.py", "open-brief", "--state", state, "--id", pid, "--url", PUBLIC + "/program/", "--action", "refine",
                     "--brief", "briefs/x/brief.md", "--date", "2026-08-25")
    rc2, so2, _ = run("seo_state.py", "ship", "--state", state, "--id", pid, "--date", "2026-09-01")
    check("older brief opened and shipped", rc == 0 and rc2 == 0, so + so2)
    rc, so, se = run("seo_state.py", "due", "--state", state, "--today", TODAY, "--json")
    due = json.loads(so)
    cps = sorted((d["id"], d["checkpoint"]) for d in due if d["kind"] == "checkpoint")
    check("due lists the 14 and 28 day checkpoints only", cps == [(pid, 14), (pid, 28)], cps)
    check("due lists the unverified shipped brief", any(d["kind"] == "verify" and d["id"] == pid for d in due))
    check("due gives the exact window", any(d.get("before") == ["2026-08-18", "2026-08-31"] for d in due))
    rc, so, se = run("seo_state.py", "track", "--state", state, "--gsc", os.path.join(GSC, "api-date-page.json"), "--today", TODAY)
    st = json.load(open(state))
    c14 = st["briefs"][pid]["checkpoints"]["14"]
    check("track records due checkpoints from date x page rows", rc == 0 and c14["status"] == "recorded"
          and st["briefs"][pid]["checkpoints"]["28"]["status"] == "recorded" and st["briefs"][pid]["checkpoints"]["56"]["status"] == "scheduled", so)
    check("checkpoint metrics and outcome", c14["before_metrics"]["clicks"] == 23 and c14["after_metrics"]["clicks"] == 51
          and c14["outcome"] == "up" and c14["tag"] == "refresh:refine" and c14["position_change"] == -2.2, c14)
    rc, so, se = run("seo_state.py", "track", "--state", state, "--id", pid, "--checkpoint", "56", "--before", os.path.join(GSC, "ui-pages-fr.csv"),
                     "--after", os.path.join(GSC, "ui-pages-fr.csv"), "--today", TODAY)
    st = json.load(open(state))
    check("track from two UI exports, last checkpoint closes the brief", rc == 0 and st["briefs"][pid]["checkpoints"]["56"]["outcome"] == "flat"
          and st["briefs"][pid]["status"] == "closed", so + se)
    rc, so, se = run("seo_state.py", "summary", "--state", state, "--json")
    s = json.loads(so)
    check("summary counts outcomes per action, no winner", s["outcomes"]["refresh:refine"]["14d"]["up"] == 1 and "correlation" in s["note"], s)
    return state


def t_runs_diff(tmp, run1, state):
    print("seo_state.py record-run (diff between runs)")
    rc, so, se = run("seo_state.py", "record-run", "--state", state, "--run-dir", run1, "--date", "2026-10-12")
    check("first run recorded as baseline", rc == 0 and "baseline" in so, so + se)
    rc, so, se, run2 = crawl_site(tmp, "run2", "routes-fixed.json")
    rc, so, se = run("seo_state.py", "record-run", "--state", state, "--run-dir", run2, "--date", "2026-10-26")
    d = json.load(open(os.path.join(run2, "since-last-run.json")))
    ch = {(c["url"], c["field"]) for c in d["changes"]}
    check("diff sees the new title of the refreshed page", (PUBLIC + "/blog/first-pitch/", "title") in ch, ch)
    check("diff sees the slash variant now redirecting", (PUBLIC + "/blog/pitch-deck-mistakes", "redirects_to") in ch
          and (PUBLIC + "/blog/pitch-deck-mistakes", "title") not in ch, ch)
    resolved = {i["code"] for i in d["issues_resolved"]}
    check("diff lists resolved issues", {"slash-duplicate", "sitemap-other-host"} - resolved == {"sitemap-other-host"}
          and "og-url-mismatch" in resolved, resolved)
    fp = next(b["id"] for b in json.load(open(state))["briefs"].values() if b["url"] == PUBLIC + "/blog/first-pitch/")
    check("diff lists briefs shipped since the previous run", d["shipped_since"] == [fp], d["shipped_since"])
    md = open(os.path.join(run2, "since-last-run.md")).read()
    check("since-last-run.md written with crawl lines", "crawl.jsonl:" in md and "Resolved issues" in md)
    st = json.load(open(state))
    check("state keeps both runs in date order", [r["date"] for r in st["runs"]] == ["2026-10-12", "2026-10-26"])


def t_geo(tmp, run1):
    print("geo_panel.py")
    panel = os.path.join(GEO, "panel.json")
    ans = os.path.join(tmp, "geo", "answers.jsonl")
    out = os.path.join(tmp, "geo")
    check("panel check passes", run("geo_panel.py", "check", "--panel", panel)[0] == 0)
    badp = os.path.join(tmp, "bad-panel.json")
    json.dump({"brand": {"name": "x"}, "topics": [{"id": "t", "questions": [{"id": "q", "text": "?"}]}]}, open(badp, "w"))
    rc, so, se = run("geo_panel.py", "check", "--panel", badp)
    check("panel without domains or question source fails", rc == 1 and "domains" in so and "source" in so, so)
    cmd = f'"{sys.executable}" "{os.path.join(GEO, "fake_answers.py")}"'
    rc, so, se = run("geo_panel.py", "run", "--panel", panel, "--surface", "perplexity", "--provider", "command", "--cmd", cmd, "--out", ans, "--date", TODAY)
    check("spend gate closed without --confirm-spend", rc == 1 and "9 call(s)" in so and not os.path.exists(ans), so)
    rc, so, se = run("geo_panel.py", "run", "--panel", panel, "--surface", "perplexity", "--provider", "command", "--cmd", cmd, "--out", ans,
                     "--date", TODAY, "--confirm-spend")
    check("fake engine: 3 questions x 3 draws", rc == 0 and len(jsonl(ans)) == 9, so + se)
    rc, so, se = run("geo_panel.py", "run", "--panel", panel, "--surface", "perplexity", "--provider", "command", "--cmd", cmd, "--out", ans,
                     "--date", TODAY, "--confirm-spend")
    check("run is resumable", rc == 0 and "nothing to do" in so and len(jsonl(ans)) == 9)
    rc, so, se = run("geo_panel.py", "import", "--capture", os.path.join(GEO, "capture-chatgpt.md"), "--out", ans, "--date", TODAY)
    check("manual capture imported, empty block skipped", rc == 0 and len(jsonl(ans)) == 12, so)
    rc, so, se = run("geo_panel.py", "score", "--panel", panel, "--answers", ans, "--out-dir", out, "--date", TODAY)
    s = json.load(open(os.path.join(out, "geo-score.json")))
    p = s["surfaces"]["perplexity"]
    check("mention rate over draws", rc == 0 and p["mention_rate"] == 0.556, p["mention_rate"])
    check("citation rate only over answers with citations", p["citation_rate"] == 0.375 and p["answers_with_citations"] == 8, p)
    check("share of voice against competitors", p["share_of_voice"] == 0.5 and p["competitors"]["Northpier"]["mention_rate"] == 0.333, p)
    check("spread between draws", abs(p["spread"] - 0.333) < 0.002 and p["mention_rate_by_draw"] == {"1": 0.667, "2": 0.333, "3": 0.667}, p["mention_rate_by_draw"])
    check("surface without answers is Unverified, not 0", s["unverified_surfaces"] == ["claude"] and "claude" not in s["surfaces"])
    check("incomplete draws listed", {"prompt_id": "first-pitch.q1", "surface": "chatgpt", "draws": 0, "expected": 3} in s["incomplete"])
    q2 = next(x for x in s["prompts"] if x["prompt_id"] == "paris-accelerators.q2" and x["surface"] == "perplexity")
    check("per question k/n and stability", q2["brand_mentioned"] == "3/3" and q2["brand_cited"] == "2/3" and q2["stable"])
    md = open(os.path.join(out, "geo-score.md")).read()
    check("geo-score.md shows Unverified surface", "| claude | 0 | Unverified" in md)
    prev = os.path.join(tmp, "geo-prev.json")
    s_prev = json.loads(json.dumps(s))
    s_prev["surfaces"]["perplexity"]["mention_rate"] = 0.333
    json.dump(s_prev, open(prev, "w"))
    rc, so, se = run("geo_panel.py", "score", "--panel", panel, "--answers", ans, "--out-dir", out, "--date", TODAY, "--previous", prev)
    s2 = json.load(open(os.path.join(out, "geo-score.json")))
    check("delta against the previous panel", rc == 0 and "+22 pts" in s2["since_previous"]["perplexity"]["mention_rate"], s2.get("since_previous"))
    rc, so, se = run("geo_panel.py", "links", "--panel", panel, "--out", os.path.join(out, "links.md"))
    links = open(os.path.join(out, "links.md")).read()
    check("prefilled links", rc == 0 and "https://chatgpt.com/?q=Which%20pre-seed" in links and "perplexity.ai/search/new?q=" in links)
    rc, so, se = run("geo_panel.py", "template", "--panel", panel, "--surface", "claude", "--out", os.path.join(out, "capture.md"))
    tpl = open(os.path.join(out, "capture.md")).read()
    check("capture template has one block per question and draw", rc == 0 and tpl.count("## ") == 9 and "Link: https://claude.ai/new?q=" in tpl)
    rc, so, se = run("geo_panel.py", "import", "--capture", os.path.join(out, "capture.md"), "--out", ans)
    check("an untouched template imports nothing", rc == 0 and len(jsonl(ans)) == 12)
    rc, so, se = run("geo_panel.py", "robots", "--robots-file", os.path.join(FIX, "site", "pages", "robots.txt"),
                     "--crawl", os.path.join(run1, "crawl.jsonl"), "--paths", "/,/blog/", "--out-dir", out)
    a = json.load(open(os.path.join(out, "ai-access.json")))
    t = {r["token"]: r for r in a["crawlers"]}
    check("robots: GPTBot and CCBot blocked, ClaudeBot allowed", not t["GPTBot"]["allowed"]["/"] and not t["CCBot"]["allowed"]["/"]
          and t["ClaudeBot"]["allowed"]["/"])
    check("robots: PerplexityBot blocked on / but allowed on /blog/", not t["PerplexityBot"]["allowed"]["/"] and t["PerplexityBot"]["allowed"]["/blog/"])
    check("robots: blocked search agents named, content signal read", a["blocked_search_or_user_agents"] == ["PerplexityBot"]
          and a["content_signals"] == ["search=yes, ai-train=no"])
    check("robots: JavaScript shell pages listed from the crawl", [x["url"] for x in a["thin_raw_html_pages"]] == [PUBLIC + "/events/"])
    srv, base = fixture_server.start()
    try:
        rc, so, se = run("geo_panel.py", "robots", "--site", PUBLIC, "--fetch-base", base, "--out-dir", os.path.join(out, "live"))
    finally:
        srv.shutdown()
    check("robots read from the site", rc == 0 and json.load(open(os.path.join(out, "live", "ai-access.json")))["robots_found"])


def t_serp_extractor():
    print("serp_analyzer.py extractor")
    import serp_analyzer as sa
    h = ('<html><head><title>A</title><meta content="L\'accélérateur qu\'il vous faut" name="description">'
         '<script type="application/ld+json">{"@type":["Article","NewsArticle"]}</script>'
         '<script type="application/ld+json">{"@graph":[{"@type":"BlogPosting","author":{"@type":"Person","name":"Jo"}}]}</script>'
         '</head><body><div class="authority-badge">x</div><main><h1>T</h1><p>one two three</p></main></body></html>')
    r = sa.extract_page_signals(h, "")
    check("serp extractor: apostrophe and attribute order", r["meta"] == "L'accélérateur qu'il vous faut")
    check("serp extractor: type arrays, BlogPosting, no Person", r["schema_types"] == ["Article", "BlogPosting", "NewsArticle"], r["schema_types"])
    check("serp extractor: author from schema", r["author_signal"] and r["authors"] == ["Jo"])
    r2 = sa.extract_page_signals('<html><body><div class="authority-badge">author</div></body></html>', "")
    check("serp extractor: 'authority' is not an author", r2["author_signal"] is False)
    check("serp country: en is a language, gl=us", sa.resolve_serp_country("en") == "us" and sa.resolve_serp_country("FR") == "fr")

    print("serp_analyzer.py spend gate and fetch guard")
    env = {k: v for k, v in os.environ.items()
           if k not in ("FOG_ALLOW_SPEND", "SERPER_API_KEY", "SERPAPI_API_KEY", "FIRECRAWL_API_KEY", "JINA_API_KEY")}
    env["SERPER_API_KEY"] = "selftest-not-a-key"
    out = os.path.join(tempfile.mkdtemp(prefix="serp-gate-"), "serp.json")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "serp_analyzer.py"), "--queries", "a", "b", "--out", out],
                       capture_output=True, text=True, env=env, timeout=60)
    check("serp spend gate closed without --confirm-spend", r.returncode == 1 and "2 SERP call(s) on serper" in r.stdout
          and "--confirm-spend" in r.stdout and not os.path.exists(out), r.stdout + r.stderr[-300:])
    for url in ("file:///etc/hostname", "ftp://ftp.example/file.txt"):
        try:
            sa.http_request(url)
            refused = False
        except ValueError as e:
            refused = "only http and https" in str(e)
        except Exception:
            refused = False
        check(f"serp http_request refuses {url.split(':')[0]}://", refused)


def t_eeat(tmp):
    print("eeat.py")
    rc, so, se, run1 = crawl_site(tmp, "eeat-run1", site=EEAT_SITE, public=LARK)
    check("crawl of the E-E-A-T fixture exits 0", rc == 0, se[-300:])
    pages = by_url(os.path.join(run1, "crawl.jsonl"))
    strong, weak = LARK + "/blog/pricing-experiments/", LARK + "/blog/onboarding-checklist/"
    check("crawl stores external links and E-E-A-T evidence", len(pages[strong]["external_links"]) == 4
          and pages[strong]["eeat_raw"]["rel_author"] == [LARK + "/authors/ana-ruiz/"])
    rc, so, se = run("eeat.py", "--crawl", os.path.join(run1, "crawl.jsonl"), "--out-dir", run1, "--today", "2026-11-03")
    check("eeat.py exits 0", rc == 0, se)
    e = json.load(open(os.path.join(run1, "eeat.json")))
    P = {p["url"]: p for p in e["pages"]}
    s = P[strong]["signals"]
    check("strong article: every signal met, score 100", P[strong]["score"] == 100 and P[strong]["missing"] == [], P[strong]["missing"])
    check("byline evidence names its selector", {"selector": "p.byline", "text": "By Ana Ruiz, published February 10, 2026"} in s["author_visible"]["evidence"],
          s["author_visible"]["evidence"])
    check("author page linked with its crawl line", s["author_page_linked"]["evidence"][0]["url"] == LARK + "/authors/ana-ruiz/"
          and s["author_page_linked"]["evidence"][0]["ref"].startswith("crawl.jsonl:") and len(s["author_page_linked"]["evidence"]) == 1)
    check("dates from the JSON-LD first, days since the update", s["date_modified"]["date"] == "2026-09-15"
          and s["date_modified"]["evidence"][0]["source"] == "jsonld[0].dateModified" and s["freshness"]["value"] == 49)
    check("sources: social links excluded, citations counted", s["external_sources"]["value"] == 3
          and "https://x.com/larkspur_example" not in [x["url"] for x in s["external_sources"]["evidence"]] and s["citations"]["value"] == 3)
    w = P[weak]
    check("weak article: fixed formula gives 12 (only datePublished, weight 2 of 17)", w["score"] == 12, w["score"])
    check("weak article: missing signals listed", w["missing"] == ["author_visible", "author_schema", "author_page_linked", "date_modified",
                                                                     "date_visible", "freshness", "external_sources", "citations"], w["missing"])
    check("a share link to a social network is not a source", w["signals"]["external_sources"]["value"] == 0)
    check("non-article page: signals, no score", P[LARK + "/"]["score"] is None and P[LARK + "/"]["kind"] == "page")
    ss = e["site_signals"]
    check("site signals: About, Contact, privacy found, no legal notice", ss["about_page"]["value"] and ss["contact_page"]["value"]
          and ss["privacy_page"]["value"] and not ss["legal_page"]["value"], {k: v["value"] for k, v in ss.items()})
    check("site signals: Organization with 2 sameAs, AggregateRating, author pages, testimonials reported unscored",
          ss["organization_schema"]["value"] and ss["organization_same_as"]["value"] == 2 and ss["reviews_marked_up"]["value"]
          and ss["author_pages"]["value"] == 1 and ss["testimonial_blocks"]["value"] == 2 and ss["testimonial_blocks"]["weight"] == 0)
    check("site score = half site signals (91) + half article mean (56)", e["site_signal_score"] == 91 and e["article_mean"] == 56.0
          and e["site_score"] == 74, (e["site_signal_score"], e["article_mean"], e["site_score"]))
    first = open(os.path.join(run1, "eeat.json")).read()
    run("eeat.py", "--crawl", os.path.join(run1, "crawl.jsonl"), "--out-dir", run1, "--today", "2026-11-03")
    check("same crawl and date give the same eeat.json", open(os.path.join(run1, "eeat.json")).read() == first)
    late = os.path.join(tmp, "eeat-late")
    run("eeat.py", "--crawl", os.path.join(run1, "crawl.jsonl"), "--out-dir", late, "--today", "2027-12-01")
    pl = {p["url"]: p for p in json.load(open(os.path.join(late, "eeat.json")))["pages"]}[strong]
    check("an older update falls into the half band", pl["signals"]["freshness"]["value"] == 442 and pl["signals"]["freshness"]["score"] == 0.5
          and pl["score"] == 94, (pl["signals"]["freshness"], pl["score"]))
    cfg = os.path.join(tmp, "eeat-config.json")
    json.dump({"_comment": "test", "eeat": {"page_signals": {"date_published": {"weight": 0}}}}, open(cfg, "w"))
    rc, so, se = run("eeat.py", "--crawl", os.path.join(run1, "crawl.jsonl"), "--out-dir", os.path.join(tmp, "eeat-cfg"), "--today", "2026-11-03", "--config", cfg)
    pc = {p["url"]: p for p in json.load(open(os.path.join(tmp, "eeat-cfg", "eeat.json")))["pages"]}
    check("project config overrides a weight", rc == 0 and pc[weak]["score"] == 0, pc[weak]["score"])

    md = os.path.join(run1, "eeat.md")
    rc, so, se = run("check_report.py", md, "--crawl", os.path.join(run1, "crawl.jsonl"), "--eeat", os.path.join(run1, "eeat.json"))
    check("eeat.md passes the report gate with its eeat.json", rc == 0, so)
    rc, so, se = run("check_report.py", md, "--crawl", os.path.join(run1, "crawl.jsonl"), "--json")
    check("an E-E-A-T score without eeat.json blocks", rc == 1 and {f["code"] for f in json.loads(so)["findings"]} == {"eeat-no-source"})
    bad = os.path.join(tmp, "eeat-bad.md")
    open(bad, "w").write("**E-E-A-T site score:** 80 (eeat.json)\n\n| URL | Kind | E-E-A-T score |\n|---|---|---:|\n"
                         f"| {weak} (crawl.jsonl:8) | article | 40 |\n| {LARK}/ (crawl.jsonl:1) | page | n/a |\n\n"
                         "Expertise 2/4, trust 3/4 on this page. Updated 10/12/2026.\n")
    rc, so, se = run("check_report.py", bad, "--crawl", os.path.join(run1, "crawl.jsonl"), "--eeat", os.path.join(run1, "eeat.json"), "--json")
    f = [(x["line"], x["code"]) for x in json.loads(so)["findings"]]
    check("edited scores and a hand rating block, n/a on a page passes", rc == 1 and f == [(1, "eeat-mismatch"), (5, "eeat-mismatch"), (8, "eeat-model-score")], f)

    rc, so, se, run2 = crawl_site(tmp, "eeat-run2", "routes-after.json", site=EEAT_SITE, public=LARK)
    run("eeat.py", "--crawl", os.path.join(run2, "crawl.jsonl"), "--out-dir", run2, "--today", "2026-11-03")
    state = os.path.join(tmp, "eeat-state.json")
    run("seo_state.py", "init", "--state", state, "--project", "larkspur", "--domain", LARK)
    run("seo_state.py", "record-run", "--state", state, "--run-dir", run1, "--date", "2026-10-06")
    rc, so, se = run("seo_state.py", "record-run", "--state", state, "--run-dir", run2, "--date", "2026-11-03")
    d = json.load(open(os.path.join(run2, "since-last-run.json")))["eeat"]
    dp = {p["url"]: p for p in d["pages"]}
    check("next run: signals gained on the fixed article", dp[weak]["gained"] == ["author_schema", "author_visible", "date_modified", "date_visible", "freshness"]
          and dp[weak]["lost"] == [] and (dp[weak]["score_before"], dp[weak]["score_after"]) == (12, 71), dp.get(weak))
    check("next run: signals lost on the article that dropped its sources", dp[strong]["lost"] == ["citations", "external_sources"]
          and dp[strong]["score_after"] == 82, dp.get(strong))
    check("next run: site score moves, recorded in the state", (d["site_score_before"], d["site_score_after"]) == (74, 84)
          and json.load(open(state))["runs"][-1]["eeat_site_score"] == 84)
    check("since-last-run.md shows the E-E-A-T table", "E-E-A-T signals" in open(os.path.join(run2, "since-last-run.md")).read())
    return run1


def files_digest(root):
    import hashlib
    h = hashlib.sha256()
    for d, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()


def t_repo_fix(tmp, run1):
    print("repo_fix.py")
    crawl = os.path.join(run1, "crawl.jsonl")
    out = os.path.join(tmp, "repo-fix")
    before = files_digest(EEAT_REPO)
    rc, so, se = run("repo_fix.py", "plan", "--crawl", crawl, "--repo", EEAT_REPO, "--out-dir", out)
    check("plan exits 0", rc == 0, so + se)
    plan = json.load(open(os.path.join(out, "repo-fix.json")))
    check("every patch passes git apply --check", plan["patches"] and all(p["git_apply_check"]["ok"] for p in plan["patches"]),
          [p["git_apply_check"] for p in plan["patches"]])
    check("one patch per file", sorted(p["file"] for p in plan["patches"]) == [
        "src/components/Footer.astro", "src/components/Hero.jsx", "src/content/blog/onboarding-checklist.mdx",
        "src/layouts/BlogPost.astro", "src/pages/about.astro", "src/pages/changelog.md"], [p["file"] for p in plan["patches"]])
    loc = {(c, fx["file"], fx["line"]) for fx in plan["fixes"] for c in fx["codes"]}
    want = {("broken-internal-link", "src/components/Footer.astro", 5), ("img-alt-missing", "src/components/Hero.jsx", 5),
            ("title-long", "src/content/blog/onboarding-checklist.mdx", 3), ("description-missing", "src/content/blog/onboarding-checklist.mdx", 5),
            ("h1-multiple", "src/content/blog/onboarding-checklist.mdx", 9), ("img-alt-missing", "src/content/blog/onboarding-checklist.mdx", 14),
            ("jsonld-datemodified-missing", "src/layouts/BlogPost.astro", 8), ("jsonld-author-missing", "src/layouts/BlogPost.astro", 8),
            ("canonical-missing", "src/layouts/BlogPost.astro", 17), ("img-alt-missing", "src/pages/about.astro", 8),
            ("title-missing", "src/pages/changelog.md", 4)}
    check("each defect traced to its source file and line (frontmatter, layout, component)", loc == want, sorted(loc ^ want))
    footer = next(fx for fx in plan["fixes"] if fx["file"] == "src/components/Footer.astro")
    check("a broken link in a shared footer is one fix for every page", len(footer["urls"]) == 10, len(footer["urls"]))
    man = {(m["code"], m["url"]): m for m in plan["manual"]}
    check("ambiguous image: listed by hand with both candidates, no patch",
          man.get(("img-alt-missing", LARK + "/customers/"), {}).get("candidates") == ["src/components/Gallery.jsx:5", "src/components/LogoStrip.vue:3"])
    check("page without source file: listed by hand", ("h1-missing", LARK + "/contact/") in man
          and man[("h1-missing", LARK + "/contact/")]["candidates"] == [])
    check("empty alt is left to a person", "empty alt" in man.get(("img-alt-missing", LARK + "/"), {}).get("reason", ""))
    md = open(os.path.join(out, "patches", "src__content__blog__onboarding-checklist.mdx.patch")).read()
    check("markdown patch: frontmatter title placeholder with the budget left by the layout suffix",
          '+title: "TODO(seo-audit) p03: title of at most 49 characters (the template adds 11)"' in md, md[:600])
    check("markdown patch: extra H1 demoted, description added, alt placeholder", "+## Checklist" in md and '+description: "TODO(seo-audit)' in md
          and "+![TODO(seo-audit)" in md)
    lay = open(os.path.join(out, "patches", "src__layouts__BlogPost.astro.patch")).read()
    check("JSON-LD patch: comma added to the last property, dateModified and author placeholders",
          '+  "datePublished": frontmatter.date,' in lay and '+  "dateModified": "TODO(seo-audit)' in lay and '+  "author": "TODO(seo-audit)' in lay)
    added = [l for p in plan["patches"] for l in open(os.path.join(out, p["patch"])).read().splitlines() if l.startswith("+") and not l.startswith("+++")]
    free = [l for l in added if "TODO(seo-audit)" not in l]
    check("the script invents no text: added lines are placeholders or structural",
          sorted(free) == sorted(["+## Checklist", '+  "datePublished": frontmatter.date,']), free)
    check("report section and fills template written", "### To locate by hand" in open(os.path.join(out, "repo-fix.md")).read()
          and set(json.load(open(os.path.join(out, "fills.json")))["values"]) == {f"p{i:02d}" for i in range(1, 11)})
    rc, so, se = run("repo_fix.py", "check", "--out-dir", out, "--json")
    res = json.loads(so)
    check("check blocks while placeholders are left", rc == 1 and {f["code"] for f in res["findings"]} == {"placeholder-left"}
          and len(res["findings"]) == 10, res["findings"][:3])
    first = open(os.path.join(out, "repo-fix.json")).read()
    run("repo_fix.py", "plan", "--crawl", crawl, "--repo", EEAT_REPO, "--out-dir", os.path.join(tmp, "repo-fix-2"))
    check("plan is deterministic", open(os.path.join(tmp, "repo-fix-2", "repo-fix.json")).read() == first
          and open(os.path.join(tmp, "repo-fix-2", "patches", "src__layouts__BlogPost.astro.patch")).read() == lay)

    fills = json.load(open(os.path.join(out, "fills.json")))
    good = {"p01": "/about/", "p02": "The Larkspur team around the weekly pricing report", "p03": "The onboarding checklist for software teams",
            "p04": "Five gaps cause most support tickets in the first week of a software trial. The checklist that closes them, step by step.",
            "p05": "Checklist of the five onboarding steps", "p06": "frontmatter.updated", "p07": None, "p08": "{Astro.url.href}",
            "p09": "The Larkspur office", "p10": "Changelog of the Larkspur weekly report"}
    badv = dict(good, p01="/careers/", p02="", p03="x" * 55, p04='Too "short"', p10="TODO(seo-audit) p10: x")
    fb, fg = os.path.join(tmp, "fills-bad.json"), os.path.join(tmp, "fills-good.json")
    json.dump(dict(fills, values=badv), open(fb, "w"))
    json.dump(dict(fills, values=good), open(fg, "w"))
    run("repo_fix.py", "fill", "--out-dir", out, "--fills", fb)
    rc, so, se = run("repo_fix.py", "check", "--out-dir", out, "--json")
    got = sorted((f["where"].split()[0], f["code"]) for f in json.loads(so)["findings"])
    check("check blocks a 404 URL, an empty value, a long title, a quote and a short description, a placeholder kept", rc == 1 and got == [
        ("p01", "value-out-of-bounds"), ("p02", "placeholder-left"), ("p03", "value-out-of-bounds"), ("p04", "value-out-of-bounds"),
        ("p04", "value-out-of-bounds"), ("p10", "placeholder-left")], got)
    rc, so, se = run("repo_fix.py", "fill", "--out-dir", out, "--fills", fg)
    rc2, so2, se2 = run("repo_fix.py", "check", "--out-dir", out)
    check("filled values: check passes, null dropped the JSON-LD fix", rc == 0 and rc2 == 0
          and json.load(open(os.path.join(out, "repo-fix.json")))["fill"]["dropped_fixes"] == ["f07"], so + so2)
    work = os.path.join(tmp, "repo-applied")
    shutil.copytree(EEAT_REPO, work)
    subprocess.run(["git", "init", "-q"], cwd=work, capture_output=True)
    ok = all(subprocess.run(["git", "apply", os.path.join(out, p["patch"])], cwd=work, capture_output=True).returncode == 0
             for p in json.load(open(os.path.join(out, "repo-fix.json")))["patches"])
    chg = open(os.path.join(work, "src", "pages", "changelog.md")).read()
    check("patches apply on a copy and carry the filled values", ok and 'title: "Changelog of the Larkspur weekly report"' in chg
          and "{Astro.url.href}" in open(os.path.join(work, "src", "layouts", "BlogPost.astro")).read())
    check("the source repository is never modified", files_digest(EEAT_REPO) == before)
    rc, so, se = run("repo_fix.py", "plan", "--crawl", crawl, "--repo", os.path.join(tmp, "no-such-repo"), "--out-dir", os.path.join(tmp, "rf-x"))
    check("missing repository is a usage error", rc == 2)
    one = os.path.join(tmp, "one-line-repo")
    os.makedirs(os.path.join(one, "src", "pages"))
    open(os.path.join(one, "src", "pages", "x.html"), "w").write('<html><head><title>T</title></head>\n<body><main><p>x</p></main></body></html>\n')
    oc = os.path.join(tmp, "one-line-crawl.jsonl")
    open(oc, "w").write(json.dumps({"url": "https://s.example/x/", "final_url": "https://s.example/x/", "status": 200, "redirect_chain": [],
                                    "content_type": "text/html", "title": "T", "h1": [], "issues": ["h1-missing", "canonical-missing", "description-missing"],
                                    "images_no_alt_src": [], "internal_links": [], "eeat_raw": {}}) + "\n")
    rc, so, se = run("repo_fix.py", "plan", "--crawl", oc, "--repo", one, "--out-dir", os.path.join(tmp, "rf-one"))
    p1 = json.load(open(os.path.join(tmp, "rf-one", "repo-fix.json")))
    check("markup on one line: no line insertion guessed, listed by hand", rc == 0 and not p1["patches"] and len(p1["manual"]) == 3, p1["manual"])


def t_hygiene():
    print("hygiene")
    for s in sorted(os.listdir(SCRIPTS)):
        if s.endswith(".py") and s != "seo_lib.py":
            rc, so, se = run(s, "--help")
            check(f"{s} --help", rc == 0, se[-300:])
    bad = []
    for root, _, files in os.walk(AGENT):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith((".md", ".py", ".json", ".txt", ".html", ".csv")):
                text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                if chr(0x2014) in text or chr(0x2013) in text:
                    bad.append(os.path.relpath(os.path.join(root, f), AGENT))
    check("no em or en dash in the agent folder", not bad, bad)


def t_example(tmp):
    print("example")
    if not os.path.isdir(EXAMPLE):
        check("example folder present", False, EXAMPLE)
        return
    rc, so, se, out = crawl_site(tmp, "example-crawl")
    committed = os.path.join(EXAMPLE, "crawl.jsonl")
    check("example crawl.jsonl regenerates byte for byte", open(committed).read() == open(os.path.join(out, "crawl.jsonl")).read())
    rc, so, se = run("check_report.py", os.path.join(EXAMPLE, "seo-audit-20261012.md"), "--crawl", committed)
    check("example report passes the report gate", rc == 0, so)
    rc, so, se = run("geo_panel.py", "check", "--panel", os.path.join(EXAMPLE, "geo-panel.json"))
    check("example GEO panel is valid", rc == 0, so)
    cfg = json.load(open(os.path.join(EXAMPLE, "config.json")))
    check("example config has the keys of config.example.json",
          set(json.load(open(os.path.join(AGENT, "config.example.json")))) <= set(cfg) | {"_comment"})


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description="Offline tests of seo-audit.")
    ap.add_argument("-v", action="store_true")
    ap.add_argument("--keep", help="keep outputs in this folder")
    ap.add_argument("--only", help="lib, crawl, bands, gate, briefs, diff, geo, eeat, repo, serp, topics, write, visuals, links, hygiene, example")
    a = ap.parse_args()
    VERBOSE = a.v
    tmp = a.keep or tempfile.mkdtemp(prefix="seo-audit-tests-")
    os.makedirs(tmp, exist_ok=True)
    try:
        only = a.only
        if not only or only == "lib":
            t_lib(tmp)
        if not only or only in ("crawl", "bands", "gate", "briefs", "diff", "geo"):
            run1 = t_crawl(tmp) if not only or only == "crawl" else crawl_site(tmp, "run1")[3]
            if not only or only in ("bands", "gate", "briefs", "diff"):
                if only and only != "bands":
                    run("gsc_bands.py", "--current", os.path.join(GSC, "api-current.json"), "--prior", os.path.join(GSC, "api-prior.json"),
                        "--site", PUBLIC, "--out-dir", run1, "--today", TODAY)
                else:
                    t_bands(tmp, run1)
            if not only or only == "gate":
                t_report_gate(tmp, run1)
            if not only or only in ("briefs", "diff"):
                state = t_briefs_state_verify(tmp, run1)
                if not only or only == "diff":
                    t_runs_diff(tmp, run1, state)
            if not only or only == "geo":
                t_geo(tmp, run1)
        if not only or only in ("eeat", "repo"):
            erun = t_eeat(tmp)
            if not only or only == "repo":
                t_repo_fix(tmp, erun)
        if not only or only == "serp":
            t_serp_extractor()
        for name in ("topics", "write", "visuals", "links"):
            if not only or only == name:
                mod = __import__(f"test_{name}")
                sub = os.path.join(tmp, f"mod-{name}")
                os.makedirs(sub, exist_ok=True)
                mod.run(check, sub)
        if not only or only == "hygiene":
            t_hygiene()
        if not only or only == "example":
            t_example(tmp)
    except Exception:
        traceback.print_exc()
        RESULTS["failed"] += 1
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"{RESULTS['passed']} passed, {RESULTS['failed']} failed")
    return 1 if RESULTS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
