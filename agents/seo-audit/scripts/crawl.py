#!/usr/bin/env python3
"""
crawl.py

Local crawl of the audited site, first step of every seo-audit run. Reads
robots.txt (and obeys it), the sitemaps it declares plus the standard
locations, then crawls from the start URL breadth first up to a page cap.
Standard library only; uses `requests` when installed (--http auto).

    python3 crawl.py https://acme.example/ --out-dir <run>/
    python3 crawl.py http://127.0.0.1:8000/ --as-origin https://acme.example --out-dir <run>/
    python3 crawl.py --lookup <run>/crawl.jsonl https://acme.example/pricing/

Writes:
  crawl.jsonl         one line per URL: url, final_url, status, redirect_chain,
                      x_robots_tag, title, meta_description, h1, h2 and h3 (40 each
                      at most, the outline the topic registry reads), canonical and
                      canonical_status, meta_robots, indexable, hreflang, og_url,
                      lang, word_count (main content of the raw HTML, no
                      JavaScript), internal_links, external_links, jsonld
                      (types, valid, error), images_no_alt_src, eeat_raw (the
                      raw evidence eeat.py scores: bylines, rel=author, <time>,
                      dated phrases, citations, author and date meta, JSON-LD
                      entities with author, dates, sameAs and reviews),
                      internal_anchors (url, anchor text, zone body or chrome:
                      nav, header, footer, aside), text_blocks (paragraphs and
                      list items of the body with the spans of the links they
                      hold, read by links.py), in_sitemap, depth, inlinks,
                      body_inlinks (pages linking from their body), issues
  crawl-summary.json  robots.txt (groups, sitemaps, Content-Signal), AI crawler
                      access table, sitemaps read, host and slash variants,
                      issue counts with example URLs, broken internal links

The report quotes a current title, description or H1 only with the line
number of crawl.jsonl it comes from: --lookup prints that reference
(`crawl.jsonl:12`) and the fields, and check_report.py enforces it.

--as-origin maps a local server (a build, a staging copy, a test fixture)
onto the production origin: URLs are fetched from the start URL's origin and
reported, compared and checked with the production origin.

Issue codes and severities: assets/crawl-rules.json.

Exit codes: 0 crawl written (issues are findings, not failures), 1 start URL
unreachable or not HTML, 2 usage error. --lookup: 0 found, 1 not in the crawl.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import time
from collections import deque
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, Origin, Robots, ai_crawler_table, deep_merge,  # noqa: E402
                     fetch, host_of, is_noindex, load_assets_json, load_json, normalize_url,
                     parse_html, parse_sitemap, path_of, read_jsonl, write_json, TOOL_NAME, USER_AGENT)

ASSET_EXT = re.compile(r"\.(png|jpe?g|gif|webp|avif|svg|ico|pdf|zip|gz|xml|css|js|mjs|json|txt|mp4|webm|mp3|woff2?|ttf|eot)$", re.I)
SEV_ORDER = {"error": 0, "warning": 1, "info": 2}
MAX_SITEMAP_FILES = 50


def is_local_host(host: str) -> bool:
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".test") or host.endswith(".example"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


class Crawler:
    def __init__(self, args: argparse.Namespace, rules: Dict[str, Any]) -> None:
        self.args = args
        self.rules = rules
        self.origin = Origin(args.start_url, args.as_origin)
        self.start = self.origin.to_public(normalize_url(args.start_url))
        self.engine = args.http
        self.records: Dict[str, Dict[str, Any]] = {}
        self.order: List[str] = []
        self.sources: Dict[str, str] = {}
        self.sitemap_urls: List[str] = []
        self.sitemaps: List[Dict[str, Any]] = []
        self.site_issues: List[Dict[str, Any]] = []
        self.variants: List[Dict[str, Any]] = []
        self.not_crawled: List[str] = []
        self.robots = Robots(None)
        self.robots_info: Dict[str, Any] = {}
        self.delay = max(0.0, args.delay)

    # -- helpers ---------------------------------------------------------
    def get(self, public_url: str, follow: bool = True) -> Dict[str, Any]:
        res = fetch(self.origin.to_fetch(public_url), timeout=self.args.timeout, engine=self.engine,
                    user_agent=self.args.user_agent, follow=follow)
        res["final_url"] = self.origin.to_public(res["final_url"])
        res["chain"] = [{"url": self.origin.to_public(h["url"]), "status": h["status"],
                         "location": self.origin.to_public(h["location"])} for h in res["chain"]]
        return res

    def site_issue(self, code: str, detail: str, url: Optional[str] = None) -> None:
        self.site_issues.append({"code": code, "detail": detail, "url": url})

    # -- robots and sitemaps ---------------------------------------------
    def read_robots(self) -> None:
        url = self.origin.home + "robots.txt"
        res = self.get(url)
        ok = res["status"] == 200 and "html" not in (res["content_type"] or "").lower()
        self.robots = Robots(res["text"] if ok else None)
        self.robots_info = {
            "url": url, "status": res["status"], "error": res["error"],
            "sitemaps": self.robots.sitemaps, "content_signals": self.robots.content_signals,
            "groups": [{"agents": g["agents"], "rules": [("allow " if a else "disallow ") + p for a, p in g["rules"]]}
                       for g in self.robots.groups],
            "text": (res["text"][:4000] if ok else None),
        }
        if not ok:
            self.site_issue("robots-missing", f"robots.txt answered {res['status'] or res['error']}", url)
        delay = self.robots.crawl_delay(TOOL_NAME)
        if delay and not self.args.ignore_robots:
            self.delay = max(self.delay, min(delay, 5.0))

    def read_sitemaps(self) -> None:
        declared = [normalize_url(u) for u in self.robots.sitemaps] + [normalize_url(u) for u in self.args.sitemap]
        probes = [self.origin.home + "sitemap.xml", self.origin.home + "sitemap_index.xml"]
        queue = deque([(u, "declared") for u in declared] + [(u, "probe") for u in probes])
        seen = set()
        urls: List[str] = []
        files = 0
        while queue and files < MAX_SITEMAP_FILES:
            sm, how = queue.popleft()
            if sm in seen:
                continue
            seen.add(sm)
            if not self.origin.is_internal(sm):
                self.site_issue("sitemap-other-host", f"sitemap on another host: {sm}", sm)
                self.sitemaps.append({"url": sm, "how": how, "status": None, "kind": "not fetched (other host)", "urls": 0})
                continue
            files += 1
            res = self.get(sm)
            entry = {"url": sm, "how": how, "status": res["status"], "kind": None, "urls": 0}
            if res["status"] != 200:
                if how != "probe":
                    self.site_issue("sitemap-unreadable", f"{sm} answered {res['status'] or res['error']}", sm)
                entry["kind"] = "missing" if how == "probe" else "unreadable"
                self.sitemaps.append(entry)
                continue
            parsed = parse_sitemap(res["text"])
            entry["kind"] = parsed["kind"]
            if parsed["kind"] == "sitemapindex":
                for child in parsed["locs"]:
                    queue.append((normalize_url(child), "index"))
            elif parsed["kind"] == "urlset":
                for loc in parsed["locs"]:
                    pu = self.origin.to_public(normalize_url(loc))
                    if pu not in urls:
                        urls.append(pu)
                entry["urls"] = len(parsed["locs"])
            else:
                self.site_issue("sitemap-unreadable", f"{sm} is not a sitemap (no urlset or sitemapindex)", sm)
            self.sitemaps.append(entry)
        self.sitemap_urls = urls
        if not urls:
            self.site_issue("sitemap-missing", "no URL found in any sitemap (declared in robots.txt or at the standard locations)")

    # -- page crawl ------------------------------------------------------
    def crawlable(self, url: str) -> bool:
        if not self.origin.is_internal(url):
            return False
        p = path_of(url)
        if ASSET_EXT.search(p.split("?")[0]):
            return False
        if "?" in p and not self.args.follow_query:
            return False
        return True

    def crawl(self) -> None:
        queue = deque([self.start])
        self.sources[self.start] = "start"
        for u in self.sitemap_urls:
            if u not in self.sources:
                self.sources[u] = "sitemap"
                queue.append(u)
        queued = set(queue)
        fetched = 0
        while queue:
            url = queue.popleft()
            if url in self.records:
                continue
            if not self.args.ignore_robots and not self.robots.allowed(TOOL_NAME, url):
                self.records[url] = self.blank(url)
                self.records[url]["blocked_by_robots"] = True
                self.order.append(url)
                continue
            if fetched >= self.args.max_pages:
                self.not_crawled.append(url)
                continue
            fetched += 1
            res = self.get(url)
            rec = self.build(url, res)
            self.records[url] = rec
            self.order.append(url)
            targets = list(rec.get("internal_links", []))
            if rec["redirect_chain"] and rec["final_url"]:
                targets.insert(0, rec["final_url"])
            for link in targets:
                if link not in queued and self.crawlable(link):
                    queued.add(link)
                    self.sources.setdefault(link, "link")
                    queue.append(link)
            if self.delay:
                time.sleep(self.delay)

    def blank(self, url: str) -> Dict[str, Any]:
        return {
            "url": url, "final_url": None, "status": None, "redirect_chain": [], "content_type": None,
            "x_robots_tag": None, "error": None, "blocked_by_robots": False, "source": self.sources.get(url, "link"),
            "in_sitemap": url in self.sitemap_urls, "depth": None, "inlinks": 0,
            "lang": None, "title": None, "title_length": 0, "meta_description": None, "description_length": 0,
            "h1": [], "h1_count": 0, "h2": [], "h3": [], "canonical": None, "canonical_status": None, "meta_robots": None,
            "indexable": False, "hreflang": [], "og_url": None, "og_title": None, "word_count": 0,
            "internal_links": [], "internal_links_count": 0, "external_links_count": 0,
            "internal_anchors": [], "body_inlinks": 0, "text_blocks": [],
            "jsonld": [], "jsonld_types": [], "images": 0, "images_no_alt": 0, "images_no_alt_src": [],
            "external_links": [], "eeat_raw": None, "issues": [],
        }

    def build(self, url: str, res: Dict[str, Any]) -> Dict[str, Any]:
        rec = self.blank(url)
        rec.update(final_url=res["final_url"], status=res["status"], redirect_chain=res["chain"],
                   content_type=(res["content_type"] or None), x_robots_tag=res["headers"].get("x-robots-tag"),
                   error=res["error"])
        if res["chain"] or res["status"] != 200 or "html" not in (res["content_type"] or "").lower():
            return rec  # a redirect is recorded with its chain; the target gets its own line
        sig = parse_html(res["text"], res["final_url"])
        internal, external, external_urls = [], 0, []
        anchors, seen_anchor = [], set()
        for a in sig["anchors"]:
            pu = self.origin.to_public(a["url"])
            if self.origin.is_internal(pu):
                if pu not in internal:
                    internal.append(pu)
                key = (pu, a["text"], a["zone"])
                if key not in seen_anchor and len(anchors) < 400:
                    seen_anchor.add(key)
                    anchors.append({"url": pu, "text": a["text"][:120], "zone": a["zone"]})
            else:
                external += 1
                if pu not in external_urls and len(external_urls) < 100:
                    external_urls.append(pu)
        eeat_raw = sig["eeat"]
        for el in eeat_raw["elements"]:
            if el.get("links"):
                el["links"] = [self.origin.to_public(l) for l in el["links"]]
        eeat_raw["rel_author"] = [self.origin.to_public(l) for l in eeat_raw["rel_author"]]
        canonical = self.origin.to_public(sig["canonical"]) if sig["canonical"] else None
        og_url = sig["og"].get("og:url")
        og_url = self.origin.to_public(normalize_url(og_url)) if og_url else None
        rec.update(
            lang=sig["lang"], title=sig["title"], title_length=len(sig["title"] or ""),
            title_count=sig["title_count"],
            meta_description=sig["meta_description"], description_length=len(sig["meta_description"] or ""),
            h1=sig["h1"], h1_count=len(sig["h1"]), h2=sig["h2"][:40], h3=sig["h3"][:40], canonical=canonical, canonical_count=sig["canonical_count"],
            canonical_status=self.canonical_status(rec["final_url"], canonical),
            meta_robots=sig["meta_robots"],
            indexable=not is_noindex(sig["meta_robots"], rec["x_robots_tag"]),
            hreflang=[{"lang": h["lang"], "href": self.origin.to_public(h["href"])} for h in sig["hreflang"]],
            og_url=og_url, og_title=sig["og"].get("og:title"), word_count=sig["word_count"],
            internal_links=internal, internal_links_count=len(internal), external_links_count=external,
            internal_anchors=anchors, text_blocks=sig["blocks"],
            jsonld=[{"types": j["types"], "valid": j["valid"], "error": j["error"]} for j in sig["jsonld"]],
            jsonld_types=sorted({t for j in sig["jsonld"] for t in j["types"]}),
            images=sig["images"], images_no_alt=sig["images_no_alt"], images_no_alt_src=sig["images_no_alt_src"],
            external_links=external_urls, eeat_raw=eeat_raw,
        )
        return rec

    def canonical_status(self, page_url: str, canonical: Optional[str]) -> str:
        if not canonical:
            return "missing"
        if canonical == page_url:
            return "self"
        if host_of(canonical) != host_of(self.origin.public):
            return "other-host"
        if canonical == self.origin.home and page_url != self.origin.home:
            return "home"
        return "other"

    # -- variants --------------------------------------------------------
    def check_variants(self) -> None:
        if self.args.no_variants:
            return
        host = host_of(self.origin.public)
        if not self.args.as_origin and not is_local_host(host):
            scheme_variant = ("http://" if self.origin.public.startswith("https://") else "https://") + host + "/"
            www = host[4:] if host.startswith("www.") else "www." + host
            host_variant = self.origin.public.split("://")[0] + "://" + www + "/"
            for v in (scheme_variant, host_variant):
                res = fetch(v, timeout=self.args.timeout, engine=self.engine, user_agent=self.args.user_agent)
                final = normalize_url(res["final_url"]) if res["final_url"] else None
                entry = {"kind": "host", "url": v, "status": res["status"], "final_url": final,
                         "redirects_to_home": final == self.origin.home, "error": res["error"]}
                self.variants.append(entry)
                if res["status"] == 200 and final != self.origin.home:
                    self.site_issue("host-variant-not-redirected", f"{v} serves 200 at {final} instead of redirecting to {self.origin.home}", v)
        sample = [u for u in self.order if self.records[u]["status"] == 200 and not self.records[u]["redirect_chain"]
                  and path_of(u) not in ("/",) and "?" not in u]
        sample.sort(key=lambda u: (0 if self.records[u]["in_sitemap"] else 1, self.order.index(u)))
        for u in sample[: self.args.variant_sample]:
            toggled = u[:-1] if u.endswith("/") else u + "/"
            known = self.records.get(toggled)
            if known and known["status"] is not None:
                status, final, chain = known["status"], known["final_url"], known["redirect_chain"]
            else:
                res = self.get(toggled)
                status, final, chain = res["status"], res["final_url"], res["chain"]
            dup = status == 200 and not chain and normalize_url(final or "") == toggled
            self.variants.append({"kind": "slash", "url": toggled, "of": u, "status": status, "final_url": final,
                                  "duplicate": dup})
            if dup:
                self.records[u]["issues"].append("slash-duplicate")
                self.records[u].setdefault("variants_200", []).append(toggled)

    # -- graph and rules -------------------------------------------------
    def graph(self) -> None:
        final_of = {u: (r["final_url"] or u) for u, r in self.records.items()}
        inl: Dict[str, set] = {}
        body_inl: Dict[str, set] = {}
        for u, r in self.records.items():
            for l in r.get("internal_links", []):
                inl.setdefault(l, set()).add(u)
                f = final_of.get(l)
                if f and f != l:
                    inl.setdefault(f, set()).add(u)
            for a in r.get("internal_anchors", []):
                if a["zone"] == "body":
                    for target in {a["url"], final_of.get(a["url"], a["url"])}:
                        body_inl.setdefault(target, set()).add(u)
        depth = {self.start: 0}
        q = deque([self.start])
        while q:
            u = q.popleft()
            r = self.records.get(u)
            if not r:
                continue
            for l in r.get("internal_links", []):
                for target in {l, final_of.get(l, l)}:
                    if target not in depth:
                        depth[target] = depth[u] + 1
                        q.append(target)
        for u, r in self.records.items():
            r["inlinks"] = len(inl.get(u, set()) - {u})
            r["body_inlinks"] = len(body_inl.get(u, set()) - {u})
            r["depth"] = depth.get(u)
            r["in_sitemap"] = u in self.sitemap_urls

    def apply_rules(self) -> List[Dict[str, Any]]:
        R = self.rules
        broken = []
        recs = self.records
        for u in self.order:
            r = recs[u]
            codes = r["issues"]
            if r["blocked_by_robots"]:
                codes.append("blocked-by-robots")
                if r["in_sitemap"]:
                    codes.append("sitemap-blocked-by-robots")
                continue
            if r["error"]:
                codes.append("fetch-error")
                continue
            st = r["status"] or 0
            if 400 <= st < 500:
                codes.append("status-4xx")
            elif st >= 500:
                codes.append("status-5xx")
            if r["redirect_chain"]:
                codes.append("redirect")
                if r["in_sitemap"]:
                    codes.append("sitemap-redirect")
            if r["in_sitemap"] and st != 200:
                codes.append("sitemap-non-200")
            if st != 200 or r["redirect_chain"] or "html" not in (r["content_type"] or "").lower():
                continue
            if not r["indexable"]:
                codes.append("noindex")
                if r["in_sitemap"]:
                    codes.append("sitemap-noindex")
            cs = r["canonical_status"]
            if r.get("canonical_count", 0) > 1:
                codes.append("canonical-multiple")
            if cs == "missing":
                codes.append("canonical-missing")
            elif cs == "home":
                codes.append("canonical-home")
            elif cs == "other":
                codes.append("canonical-other")
            elif cs == "other-host":
                codes.append("canonical-other-host")
            if cs in ("home", "other", "other-host") and r["in_sitemap"]:
                codes.append("sitemap-non-canonical")
            if r["canonical"] and r["canonical"] != r["final_url"]:
                t = recs.get(r["canonical"])
                if t and (t["status"] != 200 or t["redirect_chain"]):
                    codes.append("canonical-target-not-200")
            if not r["title"]:
                codes.append("title-missing")
            elif r["title_length"] > R["title_max_chars"]:
                codes.append("title-long")
            if r.get("title_count", 1) > 1:
                codes.append("title-multiple")
            if not r["meta_description"]:
                codes.append("description-missing")
            elif not (R["description_min_chars"] <= r["description_length"] <= R["description_max_chars"]):
                codes.append("description-length")
            if r["h1_count"] == 0:
                codes.append("h1-missing")
            elif r["h1_count"] > 1:
                codes.append("h1-multiple")
            if not r["og_url"]:
                codes.append("og-url-missing")
            elif r["og_url"] != (r["canonical"] or r["final_url"]):
                codes.append("og-url-mismatch")
            if r["hreflang"]:
                hrefs = {h["href"] for h in r["hreflang"]}
                if r["final_url"] not in hrefs and (r["canonical"] or "") not in hrefs:
                    codes.append("hreflang-no-self")
                for h in r["hreflang"]:
                    t = recs.get(h["href"])
                    if not t or h["href"] == r["final_url"]:
                        continue
                    if t["status"] != 200:
                        codes.append("hreflang-target-not-200")
                    elif r["final_url"] not in {x["href"] for x in t["hreflang"]}:
                        codes.append("hreflang-not-reciprocal")
            if any(not j["valid"] for j in r["jsonld"]):
                codes.append("jsonld-invalid")
            if r["indexable"] and r["word_count"] < R["thin_raw_html_words"]:
                codes.append("thin-raw-html")
            if r["depth"] is not None and r["depth"] >= R["deep_page_depth"]:
                codes.append("deep-page")
            if r["in_sitemap"] and r["inlinks"] == 0 and u != self.start and not r["redirect_chain"]:
                codes.append("orphan-in-sitemap")
            for l in r["internal_links"]:
                t = recs.get(l)
                if t and t["status"] and t["status"] >= 400:
                    broken.append({"from": u, "to": l, "status": t["status"]})
                    if "broken-internal-link" not in codes:
                        codes.append("broken-internal-link")
        for code_field, issue in (("title", "title-duplicate"), ("meta_description", "description-duplicate")):
            groups: Dict[str, List[str]] = {}
            for u in self.order:
                r = recs[u]
                if r["status"] == 200 and r["indexable"] and r.get(code_field):
                    groups.setdefault(r[code_field], []).append(u)
            for urls in groups.values():
                if len(urls) > 1:
                    for u in urls:
                        recs[u]["issues"].append(issue)
                        recs[u].setdefault("duplicates", {})[issue] = [x for x in urls if x != u]
        for r in recs.values():
            seen = []
            for c in r["issues"]:
                if c not in seen:
                    seen.append(c)
            r["issues"] = seen
        return broken

    # -- output ----------------------------------------------------------
    def summary(self, broken: List[Dict[str, Any]], crawlers: List[Dict[str, Any]]) -> Dict[str, Any]:
        sev = self.rules["severity"]
        by_code: Dict[str, List[str]] = {}
        for u in self.order:
            for c in self.records[u]["issues"]:
                by_code.setdefault(c, []).append(u)
        for si in self.site_issues:
            by_code.setdefault(si["code"], []).append(si.get("url") or si["detail"])
        issues = [{"code": c, "severity": sev.get(c, "info"), "count": len(v), "examples": v[:20]}
                  for c, v in by_code.items()]
        issues.sort(key=lambda i: (SEV_ORDER.get(i["severity"], 3), -i["count"], i["code"]))
        counts = {"error": 0, "warning": 0, "info": 0}
        for i in issues:
            counts[i["severity"]] = counts.get(i["severity"], 0) + i["count"]
        ok_pages = [u for u in self.order if self.records[u]["status"] == 200]
        return {
            "schema_version": "1.0",
            "generated_by": "crawl.py",
            "start_url": self.start,
            "public_origin": self.origin.public,
            "fetched_from_alias": self.origin.fetch != self.origin.public,
            "max_pages": self.args.max_pages,
            "lines": len(self.order),
            "pages_200": len(ok_pages),
            "robots": self.robots_info,
            "ai_crawlers": crawlers,
            "sitemaps": self.sitemaps,
            "sitemap_urls": len(self.sitemap_urls),
            "not_crawled_due_to_cap": {"count": len(self.not_crawled), "examples": self.not_crawled[:50]},
            "variants": self.variants,
            "site_issues": self.site_issues,
            "issues": issues,
            "issue_counts": counts,
            "broken_links": broken,
        }


def lookup(path: str, url: str, fields: Optional[List[str]]) -> int:
    target = normalize_url(url)
    name = os.path.basename(path)
    for n, rec in read_jsonl(path):
        if rec.get("url") == target or rec.get("final_url") == target:
            keep = fields or ["url", "status", "title", "meta_description", "h1", "canonical", "canonical_status",
                              "indexable", "word_count", "jsonld_types", "issues"]
            out = {"ref": f"{name}:{n}"}
            out.update({k: rec.get(k) for k in keep})
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
    print(f"{target} is not in {path}: crawl it before quoting its current state", file=sys.stderr)
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Crawl the audited site: robots.txt, sitemaps, pages -> crawl.jsonl + crawl-summary.json.")
    ap.add_argument("start_url", nargs="?", help="start URL, usually the home page")
    ap.add_argument("--out-dir", help="run folder that receives crawl.jsonl and crawl-summary.json")
    ap.add_argument("--max-pages", type=int, default=200, help="page cap (default 200)")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests (default 0.5; a larger robots.txt Crawl-delay wins, capped at 5)")
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--as-origin", help="production origin to report and compare with (start URL is fetched, e.g. a local build)")
    ap.add_argument("--sitemap", action="append", default=[], help="extra sitemap URL (repeatable)")
    ap.add_argument("--no-variants", action="store_true", help="skip the host and trailing-slash variant checks")
    ap.add_argument("--variant-sample", type=int, default=5, help="pages tested for a trailing-slash duplicate (default 5)")
    ap.add_argument("--follow-query", action="store_true", help="also crawl internal URLs with a query string")
    ap.add_argument("--ignore-robots", action="store_true", help="crawl paths robots.txt disallows (only for your own staging copy)")
    ap.add_argument("--http", choices=["auto", "urllib", "requests"], default="auto")
    ap.add_argument("--user-agent", default=USER_AGENT)
    ap.add_argument("--config", help="project config.json; its crawl_rules object overrides assets/crawl-rules.json")
    ap.add_argument("--lookup", nargs=2, metavar=("CRAWL_JSONL", "URL"), help="print the crawl line of URL with its reference")
    ap.add_argument("--fields", help="comma-separated fields for --lookup")
    args = ap.parse_args(argv)

    try:
        if args.lookup:
            return lookup(args.lookup[0], args.lookup[1], args.fields.split(",") if args.fields else None)
        if not args.start_url or not args.out_dir:
            ap.error("start_url and --out-dir are required (or use --lookup)")
        if not re.match(r"^https?://", args.start_url):
            ap.error("start_url must start with http:// or https://")
        rules = load_assets_json("crawl-rules.json")
        if args.config:
            rules = deep_merge(rules, load_json(args.config).get("crawl_rules", {}))
        crawlers = load_assets_json("ai-crawlers.json")["crawlers"]
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    c = Crawler(args, rules)
    c.read_robots()
    c.read_sitemaps()
    c.crawl()
    first = c.records.get(c.start)
    c.graph()
    c.check_variants()
    broken = c.apply_rules()
    summary = c.summary(broken, ai_crawler_table(c.robots, crawlers, ("/",)))

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "crawl.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for u in c.order:
            f.write(json.dumps(c.records[u], ensure_ascii=False, sort_keys=False) + "\n")
    write_json(os.path.join(args.out_dir, "crawl-summary.json"), summary)
    cnt = summary["issue_counts"]
    print(f"crawl: {len(c.order)} lines ({summary['pages_200']} pages 200), {summary['sitemap_urls']} sitemap URLs, "
          f"issues: {cnt.get('error', 0)} error, {cnt.get('warning', 0)} warning, {cnt.get('info', 0)} info -> {out}")
    if not first or first["status"] != 200 or "html" not in (first.get("content_type") or "").lower():
        print(f"error: start URL {c.start} did not answer 200 HTML ({first and (first['status'] or first['error'])})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
