#!/usr/bin/env python3
"""
test_write.py

Offline tests of the mode write (scripts/write_article.py) and of the H2/H3
outline of scripts/serp_analyzer.py. Fictional site fernhollow.example and
fictional competitors (tests/fixtures/write/); no network, no API key. The
mini site repository is created in the temporary folder and never modified.

    python3 agents/seo-audit/tests/test_write.py      # prints "N passed, M failed", exit 0/1

run_tests.py can import it: run(check, tmp) with check(name, cond, detail="").
"""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
FIX = os.path.join(HERE, "fixtures", "write")
TODAY = "2026-11-13"
TOPIC = "How to invoice as a freelancer"
SLUG = "how-to-invoice-as-a-freelancer"
NO_TOPICS = "/nonexistent/topics.py"


def wa(*args):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "write_article.py")] + [str(a) for a in args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def fx(name):
    return os.path.join(FIX, name)


def png(path, rgb):
    """A valid 2x2 PNG, so the patch carries real binary data."""
    raw = b"".join(b"\x00" + bytes(rgb) * 2 for _ in range(2))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)


def plan(out, *extra):
    return wa("plan", "--topic", TOPIC, "--serp", fx("serp-analysis.json"), "--context", fx("context.json"),
              "--config", fx("config.json"), "--crawl", fx("crawl.jsonl"), "--out-dir", out, "--today", TODAY,
              "--topics", NO_TOPICS, *extra)


def write_final(d, text=None, draft=True):
    if draft:
        shutil.copyfile(fx("draft.md"), os.path.join(d, "draft.md"))
    with open(os.path.join(d, "final.md"), "w", encoding="utf-8") as f:
        f.write(text if text is not None else open(fx("final.md"), encoding="utf-8").read())


def check_dir(d, *extra):
    return wa("check", "--dir", d, "--config", fx("config.json"), "--topics", NO_TOPICS, *extra)


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"] + list(args),
                          cwd=cwd, capture_output=True, text=True)


def tree(root):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = open(p, "rb").read()
    return out


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(l.split(": ", 1) for l in m.group(1).splitlines()) if m else {}


def jsonld_in(text):
    m = re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', text, re.S)
    return json.loads(m.group(1)) if m else None


# --------------------------------------------------------------------------

def t_extractor(check):
    sys.path.insert(0, SCRIPTS)
    import serp_analyzer as sa
    html = open(fx("competitor-page.html"), encoding="utf-8").read()
    r = sa.extract_page_signals(html, "", page_url="https://ledgerly.example/blog/how-to-invoice/")
    check("extractor: H2 and H3 in document order under their H2",
          r["outline"] == [{"h2": None, "h3": ["Before you start"]},
                           {"h2": "What to include on an invoice", "h3": ["Business details", "Line items"]},
                           {"h2": "How to send an invoice", "h3": ["By email"]}], r["outline"])
    check("extractor: headings of nav, aside and footer left out",
          not {"Products", "Popular posts", "Newsletter"} & set(r["h2_outline"]), r["h2_outline"])
    check("extractor: h2_outline and h3_outline kept as flat lists",
          r["h2_outline"] == ["What to include on an invoice", "How to send an invoice"]
          and r["h3_outline"] == ["Before you start", "Business details", "Line items", "By email"], r["h3_outline"])
    check("extractor: outbound links = other sites, own host, social and relative links out",
          [l["url"] for l in r["outbound_links"]] == ["https://www.taxagency.example/small-business/invoicing-records",
                                                      "https://www.paymentlaw.example/late-payment-rules"], r["outbound_links"])
    big = "<main>" + "".join(f"<h2>Section {i}</h2>" for i in range(60)) + "<h2>Last</h2>" + "".join(
        f"<h3>Sub {i}</h3>" for i in range(30)) + "</main>"
    o = sa.heading_outline(big)
    check("extractor: caps of 40 H2 and 15 H3 per H2", len(o) == 40 and all(len(x["h3"]) == 0 for x in o), len(o))
    o2 = sa.heading_outline("<h2>A</h2>" + "".join(f"<h3>s{i}</h3>" for i in range(30)))
    check("extractor: H3 cap under one H2", len(o2[0]["h3"]) == sa.OUTLINE_MAX_H3_PER_H2)
    md = sa.extract_page_signals("", "## First\n### Sub\n```\n## not a heading\n```\n## [Linked](https://x.example/) h2")
    check("extractor: markdown fallback outline (fenced code skipped, link text kept)",
          md["outline"] == [{"h2": "First", "h3": ["Sub"]}, {"h2": "Linked h2", "h3": []}], md["outline"])


def t_plan(check, tmp):
    out = os.path.join(tmp, "articles", SLUG)
    rc, so, se = plan(out)
    check("plan: exit 0 without registry, with a warning", rc == 0 and "duplicate check is skipped" in se, so + se)
    files_ok = all(os.path.exists(os.path.join(out, f)) for f in ("outline.json", "spec.md", "decisions.md"))
    check("plan: outline.json, spec.md and decisions.md written", files_ok)
    if not files_ok:
        return out
    o = json.load(open(os.path.join(out, "outline.json")))
    p = o["plan"]
    h2 = {h["h2"]: h for h in p["h2"]}
    check("plan: must H2 groups recurring on 3 of 7 pages",
          [h["h2"] for h in p["h2"] if h["must"]] == ["What to include on a freelance invoice", "How to send an invoice"]
          and p["must_min_sources"] == 3, [(h["h2"], h["frequency"], h["must"]) for h in p["h2"]])
    check("plan: variants grouped with their sources",
          h2.get("What to include on a freelance invoice", {}).get("sources") == [1, 2, 3]
          and "Invoice details to include" in h2["What to include on a freelance invoice"]["variants"])
    check("plan: optional H2 kept, not must", "Payment terms" in h2 and not h2["Payment terms"]["must"])
    check("plan: boilerplate H2 and the site's own page left out",
          not any("Related" in h["h2"] or "Newsletter" in h["h2"] for h in p["h2"])
          and all(5 not in h["sources"] for h in p["h2"]) and p["own_pages_in_top10"][0]["position"] == 5)
    h3 = {x["h3"]: x["frequency"] for x in h2["What to include on a freelance invoice"]["h3"]}
    check("plan: recurring H3 under their H2 with frequency", h3.get("Client details") == 3 and h3.get("Line items") == 2, h3)
    qs = [(q["question"], q["source"]) for q in p["questions"]]
    check("plan: People also ask then question headings",
          [q for q, s in qs if s == "paa"] == ["What should a freelance invoice include?", "How do I send an invoice to a client?",
                                               "When should a freelancer send an invoice?"]
          and ("What is an invoice?", "headings") in qs, qs)
    check("plan: median length of competitor pages", p["length"]["median"] == 1200 and p["length"]["pages"] == 7, p["length"])
    first = p["outbound_candidates"][0]
    check("plan: outbound candidates ranked by citations, AI Overview counted",
          first["url"].startswith("https://www.taxagency.example/") and first["cited_by"] == [1, 2, 8] and first.get("ai_overview"))
    check("plan: recurring terms from titles and H2", any(t["term"] == "payment terms" for t in p["terms"])
          and not any("related" in t["term"] for t in p["terms"]), p["terms"][:8])
    ic = [c["url"] for c in o["internal_candidates"]]
    check("plan: internal candidates are 200 indexable crawl pages", "https://fernhollow.example/blog/old-guide/" not in ic
          and "https://fernhollow.example/pricing/" in ic, ic)
    check("plan: new article URL from the url pattern",
          o["article"]["url"] == f"https://fernhollow.example/blog/{SLUG}/" and o["article"]["mode"] == "new")
    spec = open(os.path.join(out, "spec.md"), encoding="utf-8").read()
    check("plan: spec carries voice, banned words, claims policy, bounds",
          "`seamless`" in spec and "no invented stats" in spec and "15 to 25 %" in spec and "at most 60 characters" in spec
          and "| h2-01 |" in spec and "first two sentences under each H2" in spec)
    before = open(os.path.join(out, "outline.json"), "rb").read()
    plan(out)
    check("plan: deterministic (same inputs, same outline.json)", before == open(os.path.join(out, "outline.json"), "rb").read())

    dup = os.path.join(tmp, "dup")
    rc, so, se = plan(dup, "--registry", fx("registry-duplicate.json"))
    check("plan: duplicate refused (built-in check), nothing written",
          rc == 1 and "duplicate" in so and "builtin" in so and not os.path.exists(os.path.join(dup, "outline.json")), so + se)
    rc, so, se = plan(dup, "--registry", fx("registry-duplicate.json"), "--force", " ")
    check("plan: --force without a reason is a usage error", rc == 2, so + se)
    rc, so, se = plan(dup, "--registry", fx("registry-duplicate.json"), "--force", "the draft was abandoned")
    forced = json.load(open(os.path.join(dup, "outline.json")))["registry"] if rc == 0 else {}
    check("plan: --force with a reason writes the plan and records it",
          rc == 0 and forced.get("forced") == "the draft was abandoned" and forced.get("verdict") == "duplicate", so + se)

    ref = os.path.join(tmp, "refresh")
    rc, so, se = plan(ref, "--registry", fx("registry-refresh.json"))
    o = json.load(open(os.path.join(ref, "outline.json"))) if rc == 0 else {"article": {}, "registry": {}}
    check("plan: a section of a live page switches to refresh of its URL",
          rc == 0 and o["article"]["mode"] == "refresh" and o["article"]["target_url"] == "https://fernhollow.example/blog/getting-paid/"
          and o["article"]["slug"] == "getting-paid" and o["registry"].get("section") == "How to invoice as a freelancer", so + se)

    fake = os.path.join(tmp, "fake_topics.py")
    with open(fake, "w") as f:
        f.write("import json\nprint(json.dumps({'verdict': 'duplicate', 'url': 'https://fernhollow.example/blog/x/', "
                "'score': 0.93, 'reason': 'same query'}))\n")
    rc, so, se = wa("plan", "--topic", TOPIC, "--serp", fx("serp-analysis.json"), "--registry", fx("registry-refresh.json"),
                    "--topics", fake, "--out-dir", os.path.join(tmp, "fake"), "--today", TODAY)
    check("plan: topics.py check is used when present", rc == 1 and "topics.py" in so and "/blog/x/" in so, so + se)
    return out


def t_check(check, tmp, out):
    write_final(out)
    rc, so, se = check_dir(out)
    res = json.load(open(os.path.join(out, "check.json")))
    check("check: the passing final exits 0", rc == 0 and res["status"] == "PASS", so + se)
    check("check: cut, links and FAQ measured", 0.15 <= res["metrics"]["cut"] <= 0.25 and len(res["metrics"]["outbound_links"]) == 2
          and len(res["metrics"]["internal_links_200"]) == 3 and res["metrics"]["faq_questions"] == 3, res["metrics"])
    rc, so, se = check_dir(out, "--json")
    try:
        js = json.loads(so)
    except ValueError:
        js = {}
    check("check: --json prints the result", js.get("status") == "PASS" and "final_sha256" in js)

    bad = os.path.join(tmp, "bad")
    shutil.copytree(out, bad)
    write_final(bad, open(fx("final-block.md"), encoding="utf-8").read())
    rc, so, se = check_dir(bad)
    codes = {b["code"] for b in json.load(open(os.path.join(bad, "check.json")))["blocks"]}
    check("check: the blocking final exits 1", rc == 1)
    for code in ("concision", "outbound-links", "banned-word", "placeholder", "must-h2", "description"):
        check(f"check: BLOCK {code}", code in codes, codes)

    final = open(fx("final.md"), encoding="utf-8").read()
    var = os.path.join(tmp, "var")

    def variant(text, decisions=None, extra=()):
        if os.path.exists(var):
            shutil.rmtree(var)
        shutil.copytree(out, var)
        write_final(var, text)
        if decisions is not None:
            with open(os.path.join(var, "decisions.md"), "a", encoding="utf-8") as f:
                f.write(decisions)
        rc, so, se = check_dir(var, *extra)
        return rc, {b["code"] for b in json.load(open(os.path.join(var, "check.json")))["blocks"]}, so

    no_send = final.replace("## How to send an invoice\n", "## Delivery\n")
    rc, codes, so = variant(no_send)
    check("check: a must H2 left out blocks", "must-h2" in codes, so)
    rc, codes, so = variant(no_send, "h2-02: sending is covered by the FAQ answer\n")
    check("check: a must H2 justified in decisions.md passes", rc == 0, so)
    rc, codes, so = variant(final.replace("(https://fernhollow.example/blog/late-payments/)", "(/blog/old-guide/)"))
    check("check: internal link to a 404 of the crawl blocks", "internal-link-not-200" in codes, so)
    rc, codes, so = variant(final.replace("is what gets you paid faster", "is what gets you paid faster " + chr(0x2014) + " always"))
    check("check: long dash blocks", "long-dash" in codes, so)
    rc, codes, so = variant(final.replace("## FAQ\n", "## More answers\n"))
    check("check: People also ask without an FAQ blocks", "faq" in codes, so)
    rc, codes, so = variant(final.replace("is what gets you paid faster", "is what gets you paid faster (see the SERP)"))
    check("check: production jargon blocks", "jargon" in codes, so)
    cfg = os.path.join(tmp, "config-strict.json")
    c = json.load(open(fx("config.json")))
    c["write"]["concision"] = {"min_cut": 0.25, "max_cut": 0.35}
    json.dump(c, open(cfg, "w"))
    rc, so, se = wa("check", "--dir", out, "--config", cfg, "--topics", NO_TOPICS)
    check("check: concision band overridden by config write", rc == 1 and "concision" in so, so)
    check_dir(out)


def t_assemble(check, tmp, out):
    fresh = os.path.join(tmp, "fresh")
    plan(fresh)
    write_final(fresh)
    rc, so, se = wa("assemble", "--dir", fresh)
    check("assemble: refused before a passing check", rc == 1 and "check" in so, so + se)

    vis = os.path.join(out, "visuals")
    os.makedirs(vis, exist_ok=True)
    shutil.copyfile(fx("visuals.json"), os.path.join(vis, "visuals.json"))
    for name, rgb in (("cover.png", (10, 20, 30)), ("fields.png", (200, 10, 10)), ("terms.png", (10, 200, 10))):
        png(os.path.join(vis, name), rgb)
    asset_url = f"/images/blog/{SLUG}/"
    rc, so, se = wa("assemble", "--dir", out, "--format", "markdown", "--frontmatter-map", "astro", "--visuals",
                    os.path.join(vis, "visuals.json"), "--asset-url", asset_url, "--config", fx("config.json"), "--today", TODAY)
    check("assemble: markdown with visuals exits 0", rc == 0, so + se)
    art_p = os.path.join(out, "article.md")
    if rc != 0 or not os.path.exists(art_p):
        return
    art = open(art_p, encoding="utf-8").read()
    fm = frontmatter(art)
    check("assemble: astro keys (pubDate, updatedDate, heroImage), slug dropped",
          fm.get("pubDate") == TODAY and fm.get("updatedDate") == TODAY and fm.get("heroImage") == f'"{asset_url}cover.png"'
          and "slug" not in fm and fm.get("title", "").startswith('"How to invoice'), fm)
    body = art.split("\n---\n", 1)[1]
    check("assemble: body H1 left to the layout", not re.search(r"(?m)^# ", body))
    lines = body.splitlines()
    i_h2 = lines.index("## What to include on a freelance invoice")
    i_img = next((i for i, l in enumerate(lines) if l.startswith("![The seven fields")), -1)
    i_next = next(i for i, l in enumerate(lines) if i > i_h2 and l.startswith("#"))
    check("assemble: body visual after the first paragraph of its H2",
          i_h2 + 1 < i_img < i_next and lines[i_h2 + 2].startswith("A freelance invoice includes"), (i_h2, i_img, i_next))
    check("assemble: second visual under Payment terms",
          f"![Net 15 and net 30 on a calendar]({asset_url}terms.png)" in body.split("## Payment terms", 1)[1].split("## FAQ")[0])
    ld = jsonld_in(art)
    ld_file = json.load(open(os.path.join(out, "jsonld.json")))
    check("assemble: embedded JSON-LD parses and equals jsonld.json", ld is not None and ld == ld_file)
    types = [x["@type"] for x in ld or []]
    check("assemble: JSON-LD types BlogPosting, FAQPage, BreadcrumbList", types == ["BlogPosting", "FAQPage", "BreadcrumbList"], types)
    a = (ld or [{}])[0]
    check("assemble: Article fields (headline, dates, author, image, url)",
          a.get("headline") == TOPIC and a.get("datePublished") == TODAY and a.get("author", {}).get("name") == "Fernhollow editorial team"
          and a.get("image") == f"https://fernhollow.example{asset_url}cover.png" and a.get("url") == f"https://fernhollow.example/blog/{SLUG}/"
          and isinstance(a.get("wordCount"), int) and a.get("publisher", {}).get("logo", {}).get("url"), a)
    faq = ld[1]["mainEntity"] if len(ld or []) > 1 else []
    check("assemble: FAQPage questions and answers from the FAQ H3",
          len(faq) == 3 and faq[0]["name"] == "What should a freelance invoice include?" and faq[0]["acceptedAnswer"]["text"].startswith("Your details"))
    bc = ld[-1]["itemListElement"] if ld else []
    check("assemble: breadcrumb Home, Blog (crawl page), article",
          [(x["position"], x["name"]) for x in bc] == [(1, "Home"), (2, "Blog"), (3, TOPIC)], bc)
    check("assemble: no HTML comment left in the article", "<!--" not in art)
    man = json.load(open(os.path.join(out, "assembled.json")))
    check("assemble: manifest lists the three images with local paths",
          sorted(i["id"] for i in man["images"]) == ["cover", "v1", "v2"] and all(i["local"] for i in man["images"]))

    rc, so, se = wa("assemble", "--dir", out, "--format", "html", "--visuals", os.path.join(vis, "visuals.json"),
                    "--asset-url", asset_url, "--config", fx("config.json"), "--today", TODAY)
    html = open(os.path.join(out, "article.html"), encoding="utf-8").read() if rc == 0 else ""
    check("assemble: html format (head, H1, images, JSON-LD)",
          rc == 0 and "<h1>How to invoice as a freelancer</h1>" in html and '<link rel="canonical"' in html
          and f'src="{asset_url}fields.png" alt="The seven fields of a freelance invoice" width="1200" height="800"' in html
          and jsonld_in(html) == ld_file, so + se)

    mp = os.path.join(tmp, "map.json")
    json.dump({"preset": "hugo", "keys": {"slug": None}, "static": {"draft": True}}, open(mp, "w"))
    rc, so, se = wa("assemble", "--dir", out, "--frontmatter-map", mp, "--config", fx("config.json"), "--today", TODAY,
                    "--no-embed-jsonld")
    fm2 = frontmatter(open(art_p, encoding="utf-8").read())
    check("assemble: frontmatter map file (preset, dropped key, static key), JSON-LD not embedded",
          rc == 0 and fm2.get("lastmod") == TODAY and fm2.get("draft") == "true" and "slug" not in fm2
          and "ld+json" not in open(art_p, encoding="utf-8").read(), fm2)

    badv = os.path.join(vis, "visuals-bad.json")
    v = json.load(open(fx("visuals.json")))
    v["body"][0]["after_h2"] = "A heading that does not exist"
    json.dump(v, open(badv, "w"))
    rc, so, se = wa("assemble", "--dir", out, "--visuals", badv, "--asset-url", asset_url, "--config", fx("config.json"))
    check("assemble: a visual without its H2 exits 1", rc == 1 and "no H2" in so, so)

    # final assembly kept for the patch
    rc, so, se = wa("assemble", "--dir", out, "--format", "markdown", "--frontmatter-map", "astro", "--visuals",
                    os.path.join(vis, "visuals.json"), "--asset-url", asset_url, "--config", fx("config.json"), "--today", TODAY)
    with open(os.path.join(fresh, "check.json"), "w") as f:
        json.dump({"status": "PASS", "final_sha256": "0"}, f)
    rc, so, se = wa("assemble", "--dir", fresh)
    check("assemble: refused when final.md changed after the check", rc == 1, so)


def make_repo(tmp):
    repo = os.path.join(tmp, "site-repo")
    os.makedirs(os.path.join(repo, "src", "content", "blog"), exist_ok=True)
    with open(os.path.join(repo, "src", "content", "blog", "getting-paid.md"), "w") as f:
        f.write('---\ntitle: "Getting paid as a freelancer"\ndescription: "Old description of the page, kept short."\n'
                'pubDate: 2025-03-02\ncategory: "guides"\ntags:\n  - invoicing\n  - payments\n---\n\nOld body.\n')
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("fictional site\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def t_patch(check, tmp, out):
    if not shutil.which("git"):
        check("patch: git available", False, "git not installed")
        return None
    repo = make_repo(tmp)
    snap = tree(repo)
    dest = f"src/content/blog/{SLUG}.md"
    adir = f"public/images/blog/{SLUG}"
    rc, so, se = wa("patch", "--dir", out, "--repo", repo, "--dest", dest, "--asset-dir", adir)
    info = json.load(open(os.path.join(out, "patch", "patch.json"))) if rc == 0 else {}
    check("patch: new article plus images, git apply --check ok", rc == 0 and info.get("git_apply_check", {}).get("ok")
          and len(info.get("files", [])) == 4, so + se)
    pt = open(os.path.join(out, "patch", "article.patch"), "rb").read() if rc == 0 else b""
    check("patch: images carried as binary", pt.count(b"GIT binary patch") == 3 and f"b/{dest}".encode() in pt)
    check("patch: repository untouched", tree(repo) == snap and git(repo, "status", "--porcelain").stdout == ""
          and info.get("repository_untouched") is True)
    copy = os.path.join(tmp, "repo-copy")
    shutil.copytree(repo, copy)
    r = git(copy, "apply", os.path.abspath(os.path.join(out, "patch", "article.patch")))
    applied = tree(copy)
    check("patch: applied on a copy, the article and image bytes match",
          r.returncode == 0 and applied.get(dest) == open(os.path.join(out, "article.md"), "rb").read()
          and applied.get(f"{adir}/fields.png") == open(os.path.join(out, "visuals", "fields.png"), "rb").read(), r.stderr)
    rc, so, se = wa("patch", "--dir", out, "--repo", repo, "--dest", "src/content/blog/getting-paid.md", "--asset-dir", adir)
    check("patch: a new article never overwrites an existing file", rc == 1 and "already exists" in so, so)
    rc, so, se = wa("patch", "--dir", out, "--repo", repo, "--dest", "../outside.md", "--asset-dir", adir)
    check("patch: destination outside the repository refused", rc == 2, se)
    rc, so, se = wa("patch", "--dir", out, "--repo", repo, "--dest", dest)
    check("patch: images without --asset-dir refused", rc == 2 and "asset-dir" in se, se)
    return repo


def t_refresh_patch(check, tmp, repo):
    ref = os.path.join(tmp, "refresh")
    write_final(ref)
    rc, so, se = check_dir(ref)
    check("refresh: check passes on the refreshed article", rc == 0, so + se)
    rc, so, se = wa("assemble", "--dir", ref, "--frontmatter-map", "astro", "--config", fx("config.json"), "--today", TODAY)
    ld = json.load(open(os.path.join(ref, "jsonld.json"))) if rc == 0 else [{}]
    check("refresh: original publication date read from the crawl JSON-LD",
          rc == 0 and ld[0].get("datePublished") == "2025-03-02" and ld[0].get("dateModified") == TODAY
          and ld[0].get("url") == "https://fernhollow.example/blog/getting-paid/", so + se)
    if repo is None:
        return
    snap = tree(repo)
    dest = "src/content/blog/getting-paid.md"
    rc, so, se = wa("patch", "--dir", ref, "--repo", repo, "--dest", dest)
    check("refresh: rewrite of the existing file checked", rc == 0, so + se)
    copy = os.path.join(tmp, "repo-copy-refresh")
    shutil.copytree(repo, copy)
    r = git(copy, "apply", os.path.abspath(os.path.join(ref, "patch", "article.patch")))
    new = open(os.path.join(copy, dest), encoding="utf-8").read() if r.returncode == 0 else ""
    check("refresh: other frontmatter keys and the publication date kept, title replaced",
          'category: "guides"' in new and "  - payments" in new and "pubDate: 2025-03-02" in new
          and 'title: "How to invoice as a freelancer: what to include, how to send"' in new and "Old body." not in new, new[:400])
    check("refresh: repository untouched", tree(repo) == snap)
    rc, so, se = wa("patch", "--dir", ref, "--repo", repo, "--dest", "src/content/blog/missing.md")
    check("refresh: a destination that does not exist is refused", rc == 1 and "does not exist" in so, so)


def t_register(check, tmp, out):
    reg = os.path.join(tmp, "topics.json")
    rc, so, se = wa("register", "--dir", out, "--registry", reg, "--topics", NO_TOPICS, "--today", TODAY)
    d = json.load(open(reg)) if os.path.exists(reg) else {"topics": []}
    line = d["topics"][0] if d["topics"] else {}
    check("register: without topics.py the line is written in the shared format, with a warning",
          rc == 0 and "topics.py not found" in se and line.get("status") == "draft" and line.get("source") == "write"
          and line.get("query") == "how to invoice as a freelancer" and line.get("url") is None
          and "How to send an invoice" in line.get("h2", []) and "Client details" in line.get("h3", []), so + se)
    wa("register", "--dir", out, "--registry", reg, "--topics", NO_TOPICS, "--today", TODAY)
    check("register: idempotent (one line per topic)", len(json.load(open(reg))["topics"]) == 1)
    rc, so, se = check_dir(out, "--registry", reg)
    check("register: the article's own registry line is not a duplicate on a later check", rc == 0, so + se)
    other = os.path.join(tmp, "topics-other.json")
    shutil.copyfile(fx("registry-duplicate.json"), other)
    rc, so, se = check_dir(out, "--registry", other)
    check("check: --registry blocks a duplicate written since the plan", rc == 1 and "duplicate" in so, so)
    check_dir(out)
    reg2 = os.path.join(tmp, "topics-refresh.json")
    shutil.copyfile(fx("registry-refresh.json"), reg2)
    rc, so, se = wa("register", "--dir", os.path.join(tmp, "refresh"), "--registry", reg2, "--topics", NO_TOPICS, "--today", TODAY)
    lines = [t for t in json.load(open(reg2))["topics"] if t.get("url") == "https://fernhollow.example/blog/getting-paid/"]
    check("register: a refresh keeps the single live line of its URL",
          rc == 0 and len(lines) == 1 and lines[0]["status"] == "live" and "refresh" in lines[0]["notes"], so + se)
    check("register: headings.json written for topics.py add --h2-file", os.path.exists(os.path.join(out, "headings.json")))


def t_topics_integration(check, tmp, out):
    """With the real scripts/topics.py, when it is present (it ships with the registry)."""
    real = os.path.join(SCRIPTS, "topics.py")
    if not os.path.exists(real):
        print("  (topics.py absent: integration checks skipped)")
        return
    d = os.path.join(tmp, "int-refresh")
    rc, so, se = wa("plan", "--topic", TOPIC, "--serp", fx("serp-analysis.json"), "--registry", fx("registry-refresh.json"),
                    "--config", fx("config.json"), "--out-dir", d, "--today", TODAY, "--topics", real)
    reg = json.load(open(os.path.join(d, "outline.json")))["registry"] if rc == 0 else {}
    check("topics.py: refresh verdict and section read from check --json",
          rc == 0 and reg.get("checker") == "topics.py" and reg.get("verdict") == "refresh"
          and reg.get("section") == "How to invoice as a freelancer", so + se)
    rc, so, se = wa("plan", "--topic", TOPIC, "--serp", fx("serp-analysis.json"), "--registry", fx("registry-duplicate.json"),
                    "--out-dir", os.path.join(tmp, "int-dup"), "--today", TODAY, "--topics", real)
    check("topics.py: duplicate verdict refuses the plan", rc == 1 and "topics.py" in so, so + se)
    regp = os.path.join(tmp, "int-topics.json")
    json.dump({"schema_version": "1.0", "domain": "https://fernhollow.example/", "updated": TODAY, "topics": []}, open(regp, "w"))
    rc, so, se = wa("register", "--dir", out, "--registry", regp, "--topics", real, "--today", TODAY)
    lines = json.load(open(regp))["topics"]
    check("topics.py: register adds the draft line with the final H2 and H3",
          rc == 0 and len(lines) == 1 and lines[0]["status"] == "draft" and lines[0]["source"] == "write"
          and "How to send an invoice" in lines[0]["h2"] and "Line items" in lines[0]["h3"], so + se)


def t_help(check):
    for sub in ("plan", "check", "assemble", "patch", "register"):
        rc, so, se = wa(sub, "--help")
        check(f"write_article.py {sub} --help", rc == 0, se[-200:])


def run(check, tmp):
    print("write_article.py and the SERP outline")
    tmp = os.path.join(tmp, "write")
    os.makedirs(tmp, exist_ok=True)
    t_extractor(check)
    out = t_plan(check, tmp)
    t_check(check, tmp, out)
    t_assemble(check, tmp, out)
    repo = t_patch(check, tmp, out)
    t_refresh_patch(check, tmp, repo)
    t_register(check, tmp, out)
    t_topics_integration(check, tmp, out)
    t_help(check)


if __name__ == "__main__":
    results = {"passed": 0, "failed": 0}
    verbose = "-v" in sys.argv

    def _check(name, cond, detail=""):
        if cond:
            results["passed"] += 1
            if verbose:
                print(f"  ok   {name}")
        else:
            results["failed"] += 1
            print(f"  FAIL {name} {detail}")
    tmpdir = tempfile.mkdtemp(prefix="seo-write-tests-")
    try:
        run(_check, tmpdir)
    except Exception:
        import traceback
        traceback.print_exc()
        results["failed"] += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"{results['passed']} passed, {results['failed']} failed")
    sys.exit(1 if results["failed"] else 0)
