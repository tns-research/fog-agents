#!/usr/bin/env python3
"""
test_topics.py

Offline tests of scripts/topics.py and of the H2/H3 fields of crawl.py, on the
fictional fernhill.example site (tests/fixtures/topics/site/, served on
127.0.0.1 by tests/fixture_server.py) and fictional Search Console, autocomplete,
People also ask and competitor sitemap files (tests/fixtures/topics/). No
network beyond 127.0.0.1, no API key.

    python3 agents/seo-audit/tests/test_topics.py        # prints "N passed, M failed", exit 0 or 1

run_tests.py imports run(check, tmp).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
FIX = os.path.join(HERE, "fixtures", "topics")
SITE = os.path.join(FIX, "site")
PUBLIC = "https://fernhill.example"
TODAY = "2026-11-13"

sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)
import fixture_server  # noqa: E402


def topics(*args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "topics.py")] + [str(a) for a in args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def check_json(reg, subject, *extra):
    rc, so, se = topics("check", "--registry", reg, subject, "--json", *extra)
    return json.loads(so) if rc == 0 else {"rc": rc, "err": se}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(check, tmp):
    print("topics.py")
    d = os.path.join(tmp, "topics")
    os.makedirs(d, exist_ok=True)
    U = lambda p: PUBLIC + p  # noqa: E731

    # crawl exposes H2 and H3 -------------------------------------------------
    srv, base = fixture_server.start(site_dir=SITE)
    try:
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "crawl.py"), base + "/", "--as-origin", PUBLIC,
                            "--out-dir", os.path.join(d, "run"), "--delay", "0", "--no-variants"], capture_output=True, text=True)
    finally:
        srv.shutdown()
    crawl = os.path.join(d, "run", "crawl.jsonl")
    check("topics: crawl of the fixture exits 0", r.returncode == 0, r.stderr[-300:])
    lines = {json.loads(l)["url"]: json.loads(l) for l in open(crawl, encoding="utf-8") if l.strip()}
    br = lines.get(U("/blog/burn-rate/"), {})
    check("crawl line carries h2 in page order", br.get("h2", [])[:4] == ["What burn rate means", "Gross vs net burn",
                                                                          "Runway from burn rate", "FAQ"], br.get("h2"))
    check("crawl line carries h3", br.get("h3") == ["Monthly or quarterly?", "A worked example"], br.get("h3"))
    check("redirect line has empty h2 and h3", lines.get(U("/blog/old-post/"), {}).get("h2") == []
          and lines.get(U("/blog/old-post/"), {}).get("h3") == [])
    import seo_lib
    big = seo_lib.parse_html("<html><body>" + "".join(f"<h2>H2 {i}</h2><h3>H3 {i}</h3>" for i in range(60)) + "</body></html>",
                             "https://x.example/")
    check("parser caps h2 and h3 at 40 each", len(big["h2"]) == 40 and len(big["h3"]) == 40 and big["h3"][0] == "H3 0")

    # build -------------------------------------------------------------------
    reg = os.path.join(d, "topics.json")
    rc, so, se = topics("build", "--registry", reg, "--crawl", crawl, "--state", os.path.join(FIX, "state.json"),
                        "--bands", os.path.join(FIX, "bands.json"), "--today", TODAY)
    check("build exits 0", rc == 0, se[-300:])
    R = json.load(open(reg, encoding="utf-8"))
    by_url = {t["url"]: t for t in R["topics"] if t["status"] == "live"}
    want = {U("/blog/burn-rate/"), U("/blog/pitch-deck-template/"), U("/fr/blog/levee-de-fonds/"), U("/pricing/")}
    check("build keeps one live line per content page", set(by_url) == want and len(by_url) == 4, sorted(by_url))
    left_out = ["/", "/blog/", "/contact/", "/legal/", "/tag/finance/", "/blog/page/2/", "/blog/hidden-draft/",
                "/blog/burn-rate", "/blog/old-post/"]
    check("home, index, contact, legal, tag, pagination, noindex, canonical elsewhere and redirect left out",
          not [p for p in left_out if U(p) in {t["url"] for t in R["topics"]}])
    bt = by_url.get(U("/blog/burn-rate/"), {})
    check("live query is the normalized H1", bt.get("query") == "how to calculate your burn rate", bt.get("query"))
    check("page without H1 takes the title without the brand", by_url.get(U("/pricing/"), {}).get("query") == "pricing"
          and by_url.get(U("/pricing/"), {}).get("kind") == "page")
    check("article detected", bt.get("kind") == "article")
    check("template headings dropped, real ones kept", "Fernhill weekly" not in bt.get("h2", []) and "Newsletter" not in bt.get("h2", [])
          and "Gross vs net burn" in bt.get("h2", []) and bt.get("h3") == ["Monthly or quarterly?", "A worked example"], bt.get("h2"))
    check("accents kept in the query", by_url.get(U("/fr/blog/levee-de-fonds/"), {}).get("query") == "préparer sa levée de fonds en 2026")
    check("top Search Console query of the page becomes an alias", "burn rate calculation" in bt.get("aliases", []))
    check("open brief recorded on its live line", bt.get("brief_id") == "b-burn-rate")
    ct = next((t for t in R["topics"] if t.get("brief_id") == "b-cap-table"), {})
    check("brief on a page outside the crawl gets a brief line", ct.get("status") == "brief" and ct.get("query") == "cap table guide"
          and ct.get("source") == "brief", ct)
    check("dropped brief not recorded", by_url.get(U("/pricing/"), {}).get("brief_id") is None)
    keys = ["id", "query", "aliases", "url", "status", "source", "title", "h2", "h3", "first_seen", "updated", "brief_id", "notes"]
    check("every line has the contract fields and a t- id", all(all(k in t for k in keys) and t["id"].startswith("t-") for t in R["topics"])
          and R["schema_version"] == "1.0" and R["domain"] == PUBLIC + "/" and R["updated"] == TODAY)
    before = read(reg)
    topics("build", "--registry", reg, "--crawl", crawl, "--state", os.path.join(FIX, "state.json"),
           "--bands", os.path.join(FIX, "bands.json"), "--today", TODAY)
    same_day = read(reg) == before
    rc, so, _ = topics("build", "--registry", reg, "--crawl", crawl, "--state", os.path.join(FIX, "state.json"),
                       "--bands", os.path.join(FIX, "bands.json"), "--today", "2026-12-01")
    check("build is idempotent (same day, and a later day with the same crawl)", same_day and read(reg) == before and "unchanged" in so, so)

    # check -------------------------------------------------------------------
    c = check_json(reg, "how to calculate burn rate")
    check("check: main subject of a live page is a duplicate with its URL", c.get("verdict") == "duplicate"
          and c.get("url") == U("/blog/burn-rate/") and c.get("score", 0) >= 0.85 and c.get("reason"), c)
    c = check_json(reg, "cap table guide")
    check("check: subject of an open brief is a duplicate", c.get("verdict") == "duplicate" and c.get("topic_id") == ct.get("id"), c)
    c = check_json(reg, "gross vs net burn")
    check("check: a subject in an H2 of the page is a refresh with its section", c.get("verdict") == "refresh"
          and c.get("section") == {"level": "h2", "text": "Gross vs net burn"} and c.get("url") == U("/blog/burn-rate/"), c)
    c = check_json(reg, "cap table slide")
    check("check: a subject treated in an H2 of another article is a refresh of that article", c.get("verdict") == "refresh"
          and c.get("url") == U("/blog/pitch-deck-template/") and (c.get("section") or {}).get("text") == "Cap table slide", c)
    c = check_json(reg, "monthly or quarterly")
    check("check: an H3 counts as a section", c.get("verdict") == "refresh" and (c.get("section") or {}).get("level") == "h3", c)
    c = check_json(reg, "lever des fonds")
    check("check: a broad subject inside a longer live H1 (stemming, accents) is a refresh of that URL",
          c.get("verdict") == "refresh" and c.get("url") == U("/fr/blog/levee-de-fonds/") and c.get("section") is None, c)
    import topics as T_
    rules = T_.load_rules(None)
    m = T_.Matcher(rules)
    s_one = m.score(m.seq("prix expert comptable startup"), m.seq("Le prix"))
    check("check: a one-word heading inside a longer subject gets no substring bonus", s_one < rules["thresholds"]["refresh_section"], s_one)
    s_two = m.score(m.seq("pacte associés"), m.seq("Le pacte d'associés"))
    check("check: a two-word heading equal to the subject still scores high", s_two >= rules["thresholds"]["duplicate"], s_two)
    check("check: an English subject is detected, a French one falls back to the default language",
          T_.subject_lang("how to hire a first salesperson", rules) == "en"
          and T_.subject_lang("recruter son premier commercial", rules) is None, "")
    check("check: split spellings are joined (start up, co-fondateur)",
          m.seq("incubateur start-up") == m.seq("incubateur startup") and m.seq("trouver un co-fondateur") == m.seq("trouver un cofondateur"), "")
    check("check: two words joined when the registry writes them as one (brand names)",
          m.joined("fern hill pricing", {m.stem("fernhill")}) == (m.stem("fernhill"),) + m.seq("pricing")
          and m.joined("burn rate", {m.stem("fernhill")}) == m.seq("burn rate"), "")
    big = {"schema_version": "1.0", "domain": "https://fernhill.example/", "topics": []}
    cities = ["lyon", "nantes", "lille", "rennes", "nice", "brest", "metz", "dijon", "tours", "reims"]
    for i in range(40):
        city = cities[i % 10]
        q = f"incubateur startup {city}" if i < 10 else f"startup sujet{i} conseil"
        big["topics"].append({"id": f"t-{i}", "query": q, "aliases": [], "url": f"https://fernhill.example/blog/p{i}/",
                              "status": "live", "title": q, "h2": [], "h3": []})
    big["topics"].append({"id": "t-paris", "query": "les 12 meilleurs incubateurs et accélérateurs à paris",
                          "aliases": [], "url": "https://fernhill.example/blog/paris/", "status": "live",
                          "title": "Les 12 meilleurs incubateurs et accélérateurs à Paris", "h2": [], "h3": []})
    r = T_.check_subject("accelerateur start up paris", big, rules, T_.Matcher(rules))
    check("check: on 30+ lines a word every page shares weighs less (startup), the place decides",
          r["verdict"] in ("refresh", "duplicate") and r["url"] == "https://fernhill.example/blog/paris/", r)
    for i in range(10, 16):
        big["topics"][i]["h3"] = ["Les 12 meilleurs incubateurs et accélérateurs à Paris"]
    r = T_.check_subject("incubateurs et accélérateurs paris", big, rules, T_.Matcher(rules))
    check("check: a heading equal to another page's title is a link card, not a section", r["url"] == "https://fernhill.example/blog/paris/"
          and not r.get("broad") and r["section"] is None, r)
    for i in range(20, 24):
        big["topics"][i]["h2"] = [f"Créer sa société à {cities[i % 10]}"]
    r = T_.check_subject("créer sa société", big, rules, T_.Matcher(rules))
    check("check: a subject several pages touch and none owns is new and broad, pages listed",
          r["verdict"] == "new" and len(r.get("broad") or []) >= 3, r)
    r = T_.check_subject("incubateur startup brest", big, rules, T_.Matcher(rules))
    check("check: word weights keep an exact page an exact match", r["verdict"] == "duplicate"
          and r["url"] == "https://fernhill.example/blog/p5/", r)
    check("check: url_lang reads the language prefix", T_.url_lang("https://a.example/en/blog/x/") == "en"
          and T_.url_lang("https://a.example/blog/x/") is None, "")
    c = check_json(reg, "Préparer une levée de fonds")
    check("check: French phrasing of a live H1 is a duplicate", c.get("verdict") == "duplicate", c)
    c = check_json(reg, "customer churn benchmarks")
    check("check: an unrelated subject is new (a noindex page does not count)", c.get("verdict") == "new" and c.get("url") is None, c)
    c = check_json(reg, "FAQ")
    check("check: generic headings (FAQ) never match", c.get("verdict") == "new", c)
    c = check_json(reg, "the how of what")
    check("check: only stop words gives new with a reason", c.get("verdict") == "new" and "stop words" in c.get("reason", ""), c)
    rc, so, _ = topics("check", "--registry", reg, "gross vs net burn")
    check("check text output names verdict, URL and section", rc == 0 and so.startswith("refresh ") and "[h2: Gross vs net burn]" in so, so)
    sf = os.path.join(d, "subjects.txt")
    open(sf, "w", encoding="utf-8").write("gross vs net burn\ncustomer churn benchmarks\n")
    rc, so, _ = topics("check", "--registry", reg, "--subjects-file", sf, "--json")
    lst = json.loads(so) if rc == 0 else []
    check("check --subjects-file gives one verdict per line", [x["verdict"] for x in lst] == ["refresh", "new"], lst)
    cfg = os.path.join(d, "config.json")
    json.dump({"topics": {"thresholds": {"duplicate": 1.01, "duplicate_contained": 1.01}}}, open(cfg, "w"))
    c = check_json(reg, "how to calculate burn rate", "--config", cfg)
    check("threshold override from config.json topics", c.get("verdict") == "refresh" and c.get("thresholds", {}).get("duplicate") == 1.01, c)
    rc, _, _ = topics("check", "--registry", os.path.join(d, "nope.json"), "x")
    rc2, _, _ = topics("check", "--registry", reg)
    check("check without registry or without subject exits 2", rc == 2 and rc2 == 2)

    # add (on a copy) ---------------------------------------------------------
    reg2 = os.path.join(d, "topics-add.json")
    shutil.copy(reg, reg2)
    rc, so, se = topics("add", "--registry", reg2, "--query", "Customer churn benchmarks", "--status", "proposed", "--today", TODAY)
    c = check_json(reg2, "customer churn benchmarks")
    check("add proposed, then check: new and already proposed", rc == 0 and c.get("verdict") == "new"
          and (c.get("already_proposed") or "").startswith("t-customer-churn"), (so, se, c))
    rc, so, se = topics("add", "--registry", reg2, "--query", "how to calculate burn rate", "--status", "draft", "--today", TODAY)
    check("add refuses a duplicate of a live page (exit 1)", rc == 1 and "duplicates" in se, se)
    n_before = len(json.load(open(reg2))["topics"])
    rc, so, se = topics("add", "--registry", reg2, "--query", "burn rate refresh", "--status", "draft", "--url", U("/blog/burn-rate/"),
                        "--brief-id", "b-burn-rate", "--today", TODAY)
    R2 = json.load(open(reg2))
    b2 = next(t for t in R2["topics"] if t["url"] == U("/blog/burn-rate/"))
    check("draft of a refresh keeps the live line live, one line per URL", rc == 0 and b2["status"] == "live"
          and len(R2["topics"]) == n_before and "draft" in b2["notes"], (so, b2))
    md = os.path.join(d, "outline.md")
    open(md, "w", encoding="utf-8").write("# Seed round valuation\n\n## Valuation methods\n\n### Comparable rounds\n\n## Dilution\n")
    rc, so, se = topics("add", "--registry", reg2, "--query", "seed round valuation", "--status", "draft", "--source", "write",
                        "--h2-file", md, "--title", "Seed round valuation", "--today", TODAY)
    dr = next((t for t in json.load(open(reg2))["topics"] if t["query"] == "seed round valuation"), {})
    check("add a draft with its outline (## and ### of a Markdown file)", rc == 0 and dr.get("h2") == ["Valuation methods", "Dilution"]
          and dr.get("h3") == ["Comparable rounds"] and dr.get("url") is None, dr)
    c = check_json(reg2, "comparable rounds")
    check("check: a section of a draft sends the subject to that draft", c.get("verdict") == "refresh" and c.get("topic_id") == dr.get("id"), c)
    rc, _, _ = topics("add", "--registry", reg2, "--query", "x y z", "--status", "live")
    check("add live without URL refused", rc == 1)
    rc, _, _ = topics("add", "--registry", reg2, "--query", "how to calculate burn rate", "--status", "draft", "--force", "--today", TODAY)
    check("add --force overrides the duplicate refusal", rc == 0)

    # propose, offline --------------------------------------------------------
    reg_bytes = read(reg)
    common = ["--registry", reg, "--bands", os.path.join(FIX, "bands.json"), "--seed", "burn rate", "--seed", "pitch deck", "--expand",
              "--suggest-file", os.path.join(FIX, "suggest.json"), "--serp", os.path.join(FIX, "serp-analysis.json"),
              "--competitor-sitemap", os.path.join(FIX, "competitor-sitemap.xml"), "--offline", "--today", TODAY]
    rc, so, se = topics("propose", "--out-dir", os.path.join(d, "p1"), *common)
    pj = os.path.join(d, "p1", "propose-20261113.json")
    check("propose offline exits 0 and writes json and md", rc == 0 and os.path.exists(pj)
          and os.path.exists(os.path.join(d, "p1", "propose-20261113.md")), se[-300:])
    P = json.load(open(pj)) if os.path.exists(pj) else {"ideas": [], "excluded_duplicates": [], "excluded_brand": [], "sources": {}}
    check("propose without --add leaves the registry untouched", read(reg) == reg_bytes and P.get("added_to_registry") == [])
    ideas = {i["topic"]: i for i in P["ideas"]}
    top = P["ideas"][0] if P["ideas"] else {}
    check("ideas converging from three sources rank first, priority explained", top.get("topic") == "burn rate formula"
          and top.get("sources") == ["autocomplete", "competitor", "gsc"] and "120 Search Console impressions" in top.get("priority_why", ""), top)
    check("duplicates set aside with the URL that covers them",
          any(x["topic"] == "how to calculate burn rate" and x["check"]["url"] == U("/blog/burn-rate/") for x in P["excluded_duplicates"])
          and "how to calculate burn rate" not in ideas)
    rv = ideas.get("burn rate vs runway", {}).get("check", {})
    check("refresh idea keeps its URL and section", rv.get("verdict") == "refresh" and (rv.get("section") or {}).get("text") == "Runway from burn rate", rv)
    check("brand queries set aside (Search Console and autocomplete)",
          set(P["excluded_brand"]) == {"fernhill pricing", "pitch deck for investors fernhill"}, P["excluded_brand"])
    check("only kept verdicts are new or refresh", all(i["check"]["verdict"] in ("new", "refresh") for i in P["ideas"]) and P["ideas"])
    check("People also ask questions become ideas", any("paa" in i["sources"] for i in P["ideas"]))
    check("competitor slugs: articles kept, news, tag, about, index and pagination dropped",
          "employee stock options explained" in ideas and not [t for t in ideas if "press" in t or t in ("finance", "about")]
          and P["sources"]["competitors"]["list"][0]["news_dropped"] == 1, sorted(ideas))
    check("Search Console queries under the impression floor ignored", not any("seed round valuation" == i["topic"] for i in P["ideas"]))
    check("similar ideas grouped (one line, variants listed)", "pitch deck cap table slide" not in ideas
          and any("pitch deck cap table slide" in i["variants"] for i in P["ideas"]), sorted(ideas))
    check("autocomplete expand read a to z keys", P["sources"]["autocomplete"]["requests"] == 54
          and "burn rate accounting" in ideas and "burn rate benchmark saas" in ideas)
    check("propose writes no machine path", "/home/" not in read(pj) and "\\\\" not in read(pj) and P["registry"] == "../topics.json", P.get("registry"))
    topics("propose", "--out-dir", os.path.join(d, "p2"), *common)
    check("propose is deterministic", read(pj) == read(os.path.join(d, "p2", "propose-20261113.json"))
          and read(os.path.join(d, "p1", "propose-20261113.md")) == read(os.path.join(d, "p2", "propose-20261113.md")))
    rc, so, _ = topics("propose", "--registry", reg, "--out-dir", os.path.join(d, "p3"), "--competitor", "rival.example",
                       "--seed", "burn rate", "--offline", "--today", TODAY)
    P3 = json.load(open(os.path.join(d, "p3", "propose-20261113.json")))
    check("--offline sends nothing: autocomplete and competitor fetches skipped",
          rc == 0 and P3["sources"]["autocomplete"]["status"] == "skipped" and P3["sources"]["competitors"]["status"] == "skipped"
          and P3["ideas"] == [])

    # propose --add -----------------------------------------------------------
    reg3 = os.path.join(d, "topics-propose.json")
    shutil.copy(reg, reg3)
    json.dump({"target_queries": ["burn rate"], "language": "en"}, open(cfg, "w"))
    rc, so, se = topics("propose", "--registry", reg3, "--out-dir", os.path.join(d, "p4"), "--config", cfg,
                        "--suggest-file", os.path.join(FIX, "suggest.json"), "--offline", "--add", "--today", TODAY)
    P4 = json.load(open(os.path.join(d, "p4", "propose-20261113.json")))
    R3 = json.load(open(reg3))
    prop = [t for t in R3["topics"] if t["status"] == "proposed"]
    check("seeds default to target_queries of the config", P4["sources"]["autocomplete"]["seeds"] == ["burn rate"])
    check("propose --add records kept ideas as proposed lines", rc == 0 and len(prop) == len(P4["ideas"]) > 0
          and sorted(P4["added_to_registry"]) == sorted(t["id"] for t in prop) and all(t["url"] is None and t["source"] == "propose" for t in prop))
    check("a refresh idea added as proposed names its target in notes",
          any("refresh of " + U("/blog/burn-rate/") in t["notes"] for t in prop))
    topics("propose", "--registry", reg3, "--out-dir", os.path.join(d, "p5"), "--config", cfg,
           "--suggest-file", os.path.join(FIX, "suggest.json"), "--offline", "--add", "--today", TODAY)
    check("propose --add twice adds no line", len(json.load(open(reg3))["topics"]) == len(R3["topics"]))
    rc, so, se = topics("add", "--registry", reg3, "--query", "burn rate calculator", "--status", "dropped",
                        "--notes", "founder: not our audience", "--today", TODAY)
    topics("propose", "--registry", reg3, "--out-dir", os.path.join(d, "p7"), "--config", cfg,
           "--suggest-file", os.path.join(FIX, "suggest.json"), "--offline", "--today", TODAY)
    P7 = json.load(open(os.path.join(d, "p7", "propose-20261113.json")))
    check("an idea the founder refused is not proposed again", rc == 0
          and [x["topic"] for x in P7["excluded_dropped_before"]] == ["burn rate calculator"]
          and "burn rate calculator" not in [i["topic"] for i in P7["ideas"]], P7.get("excluded_dropped_before"))

    # propose with a served competitor and --fetch-titles ---------------------
    csite = os.path.join(d, "rival-site")
    os.makedirs(os.path.join(csite, "pages"), exist_ok=True)
    art = '<!doctype html><html><head><title>{t} | Rival</title></head><body><main><h1>{h}</h1><p>Fictional.</p></main></body></html>'
    open(os.path.join(csite, "pages", "a.html"), "w").write(art.format(t="Runway plan", h="Runway planning checklist for founders"))
    open(os.path.join(csite, "pages", "b.html"), "w").write(art.format(t="Equity split", h=""))
    json.dump({"routes": {"/sitemap.xml": {"status": 200, "file": "sitemap.xml", "headers": {"Content-Type": "application/xml"}},
                          "/blog/rp-2026/": {"status": 200, "file": "a.html"},
                          "/blog/cofounder-equity-split/": {"status": 200, "file": "b.html"}}},
              open(os.path.join(csite, "routes.json"), "w"))
    srv, base = fixture_server.start(site_dir=csite)
    try:
        open(os.path.join(csite, "pages", "sitemap.xml"), "w").write(
            '<urlset><url><loc>' + base + '/blog/rp-2026/</loc></url><url><loc>' + base + '/blog/cofounder-equity-split/</loc></url>'
            '<url><loc>https://elsewhere.example/blog/other-host-post/</loc></url></urlset>')
        rc, so, se = topics("propose", "--registry", reg, "--out-dir", os.path.join(d, "p6"), "--competitor", base, "--fetch-titles",
                            "--today", TODAY)
    finally:
        srv.shutdown()
    P6 = json.load(open(os.path.join(d, "p6", "propose-20261113.json"))) if rc == 0 else {"ideas": [], "sources": {}}
    t6 = sorted(i["topic"] for i in P6["ideas"])
    check("served competitor sitemap read, H1 preferred over the slug, title without brand as fallback",
          rc == 0 and t6 == ["equity split", "runway planning checklist for founders"]
          and P6["sources"]["competitors"]["titles_fetched"] == 2, (t6, se[-300:]))

    # list, help, dashes --------------------------------------------------------
    rc, so, _ = topics("list", "--registry", reg)
    check("list prints Markdown per status", rc == 0 and "## live (4)" in so and "## brief (1)" in so and "t-burn-rate" in so, so[:300])
    rc, so, _ = topics("list", "--registry", reg, "--status", "brief", "--json")
    check("list --status --json", rc == 0 and [t["status"] for t in json.loads(so)] == ["brief"])
    helps = [topics(*([c, "--help"] if c else ["--help"]))[0] for c in ("", "build", "check", "add", "propose", "list")]
    check("topics.py --help and every subcommand --help exit 0", helps == [0] * 6, helps)
    rc, _, _ = topics("bogus")
    check("unknown subcommand is a usage error", rc == 2)
    files = [os.path.join(SCRIPTS, "topics.py"), os.path.join(AGENT, "assets", "topics-rules.json"), os.path.abspath(__file__),
             os.path.join(AGENT, "skills", "managing-topic-registry", "SKILL.md")]
    for root, _, fs in os.walk(FIX):
        files += [os.path.join(root, f) for f in fs]
    for root, _, fs in os.walk(d):
        files += [os.path.join(root, f) for f in fs if f.startswith(("propose-", "topics"))]
    bad = [os.path.relpath(f, AGENT) for f in files if os.path.exists(f)
           and (chr(0x2014) in read(f) or chr(0x2013) in read(f))]
    check("skill managing-topic-registry present with its frontmatter",
          os.path.exists(files[3]) and read(files[3]).startswith("---\nname: managing-topic-registry\n"))
    check("no em or en dash in topics files, fixtures, skill and outputs", not bad, bad)


def main():
    results = {"passed": 0, "failed": 0}
    verbose = "-v" in sys.argv

    def check(name, cond, detail=""):
        if cond:
            results["passed"] += 1
            if verbose:
                print(f"  ok   {name}")
        else:
            results["failed"] += 1
            print(f"  FAIL {name} {detail}")

    tmp = tempfile.mkdtemp(prefix="seo-topics-tests-")
    try:
        run(check, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{results['passed']} passed, {results['failed']} failed")
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
