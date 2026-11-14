#!/usr/bin/env python3
"""
verify_served.py

Reads the HTML the server really sends after a publication and checks it
against the brief's expect.json. A tag built from an environment variable
(canonical, og:url, sitemap, robots) can fall back to a wrong domain with
green tests and correct code: only the served response shows it. A JSON-LD
block can be stripped by a Markdown sanitizer at build time without any
error: only the served HTML shows it. Standard library only.

    python3 verify_served.py --expect <project>/seo-audit/briefs/<id>/expect.json --out verify-<date>.json
    python3 verify_served.py --url https://acme.example/pricing/ --jsonld-types Organization,BreadcrumbList
    python3 verify_served.py --expect expect.json --fetch-base http://127.0.0.1:4321   # local build, production URLs

Checks per page (fail unless noted):
  status          200 at the exact URL, no redirect
  indexable       no noindex in meta robots or the X-Robots-Tag header
  robots_txt      the path is allowed for Googlebot and for *
  title           equals expect.title when set, else present
  canonical       equals expect.canonical (default: the URL itself)
  og_url          equals the canonical (missing og:url is a warning)
  hreflang        every expected alternate present, and one points at the page
  sitemap         the URL is listed in a sitemap of the same host; a sitemap
                  declared on another host fails
  jsonld_valid    every application/ld+json block parses
  jsonld_types    every expected @type present (arrays and @graph read)
  jargon          no production jargon, unrendered template token or brief
                  marker in the visible text or the HTML comments
                  (assets/pipeline-jargon.json, plus --jargon FILE)
  redirects       every URL in expect.redirects ends at the page through a
                  permanent redirect (301 or 308)
  internal_links  with --check-links: no internal link answers 4xx or 5xx

Exit codes: 0 every page passes, 1 at least one check failed, 2 usage error,
unreadable expect file or page unreachable.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, Origin, Robots, fetch, is_noindex, load_assets_json, load_json,  # noqa: E402
                     normalize_url, parse_html, parse_sitemap, path_of, visible_text, write_json)


class Site:
    """robots.txt and sitemaps of one public origin, fetched once."""

    def __init__(self, origin: Origin, timeout: float, extra_sitemaps: List[str]) -> None:
        self.origin = origin
        self.timeout = timeout
        res = self.get(origin.home + "robots.txt")
        ok = res["status"] == 200 and "html" not in (res["content_type"] or "").lower()
        self.robots = Robots(res["text"] if ok else None)
        self.urls: set = set()
        self.foreign: List[str] = []
        self.read: List[str] = []
        queue = [normalize_url(u) for u in self.robots.sitemaps + extra_sitemaps] + [origin.home + "sitemap.xml"]
        seen = set()
        while queue and len(seen) < 50:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            if not origin.is_internal(sm):
                self.foreign.append(sm)
                continue
            r = self.get(sm)
            if r["status"] != 200:
                continue
            self.read.append(sm)
            p = parse_sitemap(r["text"])
            if p["kind"] == "sitemapindex":
                queue.extend(normalize_url(x) for x in p["locs"])
            else:
                self.urls.update(origin.to_public(normalize_url(x)) for x in p["locs"])

    def get(self, public_url: str, follow: bool = True) -> Dict[str, Any]:
        r = fetch(self.origin.to_fetch(public_url), timeout=self.timeout, follow=follow)
        r["final_url"] = self.origin.to_public(r["final_url"])
        r["chain"] = [{"url": self.origin.to_public(h["url"]), "status": h["status"],
                       "location": self.origin.to_public(h["location"])} for h in r["chain"]]
        return r


def load_jargon(extra: Optional[str]) -> Dict[str, Any]:
    j = load_assets_json("pipeline-jargon.json")
    if extra:
        e = load_json(extra)
        for lang, items in e.get("visible_text", {}).items():
            j["visible_text"].setdefault(lang, []).extend(items)
        j["comments"].extend(e.get("comments", []))
    return j


def find_jargon(text: str, patterns: List[str]) -> List[str]:
    hits = []
    for p in patterns:
        if p.startswith("re:"):
            m = re.search(p[3:], text, re.I)
            if m:
                hits.append(m.group(0))
        elif p.lower() in text.lower():
            hits.append(p)
    return hits


def verify_page(exp: Dict[str, Any], site: Site, jargon: Dict[str, Any], check_links: bool) -> Dict[str, Any]:
    url = normalize_url(exp["url"])
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: Optional[bool], detail: str, warn: bool = False) -> None:
        status = "skip" if ok is None else ("pass" if ok else ("warn" if warn else "fail"))
        checks.append({"check": name, "status": status, "detail": detail})

    res = site.get(url)
    if res["error"]:
        add("status", False, f"unreachable: {res['error']}")
        return {"url": url, "passed": False, "checks": checks}
    redirected = bool(res["chain"]) or normalize_url(res["final_url"]) != url
    add("status", res["status"] == 200 and not redirected,
        f"{res['status']}" + (f" after redirect to {res['final_url']}" if redirected else ""))
    html = res["text"] if "html" in (res["content_type"] or "").lower() else ""
    sig = parse_html(html, res["final_url"])
    canonical = site.origin.to_public(sig["canonical"]) if sig["canonical"] else None
    noindex = is_noindex(sig["meta_robots"], res["headers"].get("x-robots-tag"))
    if exp.get("indexable", True):
        add("indexable", not noindex, f"meta robots {sig['meta_robots'] or 'none'}, X-Robots-Tag {res['headers'].get('x-robots-tag') or 'none'}")
    p = path_of(url)
    allowed = site.robots.allowed("Googlebot", p) and site.robots.allowed("*", p)
    add("robots_txt", allowed, f"{p} {'allowed' if allowed else 'disallowed'} for Googlebot and *")
    want_title = exp.get("title")
    title = sig["title"]
    if want_title:
        add("title", " ".join(want_title.split()) == (title or ""), f"served {title!r}, expected {want_title!r}")
    else:
        add("title", bool(title), f"served {title!r}")
    want_canonical = normalize_url(exp.get("canonical") or url)
    add("canonical", canonical == want_canonical, f"served {canonical}, expected {want_canonical}")
    og = sig["og"].get("og:url")
    og = site.origin.to_public(normalize_url(og)) if og else None
    want_og = normalize_url(exp.get("og_url") or want_canonical)
    if og is None:
        add("og_url", False, "no og:url", warn=True)
    else:
        add("og_url", og == want_og, f"served {og}, expected {want_og}")
    served_h = {(h["lang"].lower(), site.origin.to_public(h["href"])) for h in sig["hreflang"]}
    want_h = {(h["lang"].lower(), normalize_url(h["href"])) for h in exp.get("hreflang") or []}
    if want_h or served_h:
        missing = sorted(want_h - served_h)
        self_ref = any(href in (url, want_canonical) for _, href in served_h)
        add("hreflang", not missing and self_ref,
            ("missing " + ", ".join(f"{l} {h}" for l, h in missing) + "; " if missing else "")
            + ("self-reference present" if self_ref else "no alternate points at the page"))
    else:
        add("hreflang", None, "none expected, none served")
    if exp.get("in_sitemap", True):
        listed = url in site.urls
        detail = f"{'listed' if listed else 'not listed'} in {len(site.read)} sitemap(s) read"
        if site.foreign:
            detail += f"; sitemap on another host: {', '.join(site.foreign)}"
        add("sitemap", listed and not site.foreign, detail)
    blocks = sig["jsonld"]
    bad = [b["error"] for b in blocks if not b["valid"]]
    add("jsonld_valid", not bad if blocks else None, "; ".join(bad) if bad else f"{len(blocks)} block(s) parsed")
    want_types = exp.get("jsonld_types") or []
    have = sorted({t for b in blocks for t in b["types"]})
    if want_types:
        missing_t = [t for t in want_types if t not in have]
        add("jsonld_types", not missing_t, f"served {', '.join(have) or 'none'}" + (f"; missing {', '.join(missing_t)}" if missing_t else ""))
    else:
        add("jsonld_types", None, f"none expected; served {', '.join(have) or 'none'}")
    lang = (sig["lang"] or "").split("-")[0].lower()
    patterns = jargon["visible_text"].get("all", []) + jargon["visible_text"].get(lang, [])
    hits = find_jargon(visible_text(html), patterns)
    c_hits = find_jargon(" \n".join(sig["comments"]), jargon["comments"])
    add("jargon", not hits and not c_hits,
        ("visible: " + ", ".join(repr(h) for h in hits) if hits else "visible text clean")
        + ("; comments: " + ", ".join(repr(h) for h in c_hits) if c_hits else ""))
    if exp.get("redirects"):
        wrong = []
        for src in exp["redirects"]:
            r = site.get(normalize_url(src))
            first = r["chain"][0]["status"] if r["chain"] else r["status"]
            if normalize_url(r["final_url"]) != url or first not in (301, 308):
                wrong.append(f"{src} -> {first} {r['final_url']}")
        add("redirects", not wrong, "; ".join(wrong) if wrong else f"{len(exp['redirects'])} URL(s) 301 to the page")
    if check_links:
        broken = []
        for a in sig["anchors"]:
            pu = site.origin.to_public(a["url"])
            if not site.origin.is_internal(pu):
                continue
            r = site.get(pu)
            if r["status"] is None or r["status"] >= 400:
                broken.append(f"{pu} ({r['status'] or r['error']})")
        add("internal_links", not broken, "; ".join(broken) if broken else "every internal link answers below 400")
    passed = all(c["status"] in ("pass", "skip", "warn") for c in checks)
    return {"url": url, "passed": passed, "checks": checks}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Check the served HTML of published pages against their expect.json.")
    ap.add_argument("--expect", action="append", default=[], help="expect.json written by write_briefs.py (repeatable)")
    ap.add_argument("--url", action="append", default=[], help="page URL to check without an expect file (repeatable)")
    ap.add_argument("--title", help="expected title (with --url)")
    ap.add_argument("--jsonld-types", help="expected JSON-LD types, comma-separated (with --url)")
    ap.add_argument("--fetch-base", help="fetch from this origin (a local build) while checking production URLs")
    ap.add_argument("--sitemap", action="append", default=[], help="extra sitemap URL")
    ap.add_argument("--check-links", action="store_true", help="also fetch every internal link of the page")
    ap.add_argument("--jargon", help="project jargon list, same shape as assets/pipeline-jargon.json")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--today", help="date written in the report (YYYY-MM-DD)")
    ap.add_argument("--out", help="write the JSON report here")
    args = ap.parse_args(argv)
    try:
        expects = [load_json(p) for p in args.expect]
        for u in args.url:
            expects.append({"url": u, "title": args.title,
                            "jsonld_types": [t.strip() for t in (args.jsonld_types or "").split(",") if t.strip()]})
        if not expects:
            ap.error("give --expect or --url")
        jargon = load_jargon(args.jargon)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sites: Dict[str, Site] = {}
    pages = []
    for exp in expects:
        url = normalize_url(exp["url"])
        origin = Origin(args.fetch_base or url, url if args.fetch_base else None)
        key = origin.public
        if key not in sites:
            sites[key] = Site(origin, args.timeout, args.sitemap)
        pages.append(verify_page(exp, sites[key], jargon, args.check_links))
    report = {"schema_version": "1.0", "generated_by": "verify_served.py",
              "checked_on": args.today or date.today().isoformat(),
              "passed": all(p["passed"] for p in pages), "pages": pages}
    for p in pages:
        print(f"{'PASS' if p['passed'] else 'FAIL'} {p['url']}")
        for c in p["checks"]:
            if c["status"] != "pass":
                print(f"  {c['status']:<4} {c['check']}: {c['detail']}")
    if args.out:
        write_json(args.out, report)
    unreachable = any(c["check"] == "status" and c["detail"].startswith("unreachable") for p in pages for c in p["checks"])
    if unreachable:
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
