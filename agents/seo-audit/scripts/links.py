#!/usr/bin/env python3
"""
links.py

Internal linking of seo-audit: the link graph of the crawl, its defects, and
the links worth adding, each one placed on words the site already wrote.

    python3 links.py audit --crawl <run>/crawl.jsonl --out-dir <run>/links [--bands <run>/bands.json]
                           [--new-page URL=FILE ...] [--config C] [--today YYYY-MM-DD] [--json]
    python3 links.py patch --out-dir <run>/links --repo <site-repo> [--only L01,L03,R01] [--json]

audit reads crawl.jsonl (crawl.py records the anchor text and zone of every
internal link, body or chrome, and the text blocks of each body) and, when
given, bands.json of gsc_bands.py. It measures, per page, the pages that link
to it from their body (nav, header, footer and aside links counted apart),
the click depth and the outgoing body links, then flags:

  orphan            no page links to it at all (error)
  orphan-body       only nav, header, footer or aside links reach it (warning)
  weak-inlinks      a page at position 4 to 20 in Search Console, or a new
                    page, with fewer body inlinks than weak_body_inlinks
  deep-page         click depth at deep_page_depth or more
  anchor-generic    a body link whose anchor says nothing (here, read more,
                    en savoir plus...)
  anchor-monotone   one anchor text carries more than max_share of the body
                    links of a page that has min_body_inlinks or more
  link-to-redirect  a link that answers with a redirect: the fix is the final
                    URL (patchable)
  link-broken       a link to a 4xx or 5xx page (repo_fix.py patches those)
  dead-end          a page whose body links to no other page (info)

Then it proposes links. A target page gets phrases from its Search Console
queries (bands.json), its H1, its URL slug and its title without the brand;
a new article given with --new-page URL=FILE gets its frontmatter keyword,
title and H1. Every text block of every other page of the same language is
scanned for those phrases, outside the links the block already holds. A
match becomes a suggestion: link the words already written in that sentence
to the target. Scores favour new pages, orphans, quick wins (position 4 to
20), strong source pages (body inlinks, clicks) and pages on the same
subject. Caps: max_new_links_per_source per source page, one new link per
block, max_suggestions_per_target per target, the same anchor at most
max_same_anchor_per_target times for one target, and never a second link
from a page that already links to the target from its body. Thresholds live
in assets/link-rules.json (override with a links object in config.json).

patch turns the suggestions (and the redirect fixes) into unified patches of
the site's source repository, one per file, checked with git apply --check on
a temporary copy: the anchor words are wrapped in a Markdown link in .md and
.mdx files and in an <a href> elsewhere, on the single line of the page's
source file that holds them outside any existing link, tag, code or heading.
A phrase found on zero or several lines, or only in a shared component, is
listed to place by hand. The repository is read, never written.

Writes (in --out-dir):
  links.json        metrics, pages, issues, suggestions (L01...), redirect fixes (R01...)
  links.md          the "Internal linking" section of the report
  repo/patches/     with patch: one .patch per source file
  links-patch.json  with patch: patches, manual placements, git checks

Exit codes: audit 0; patch 0 written, 1 a patch failed git apply --check or
git is missing; 2 usage or unreadable input.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seo_lib import (InputError, deep_merge, load_assets_json, load_json, normalize_url, path_of, read_jsonl,  # noqa: E402
                     write_json, write_text)
import topics  # noqa: E402
import repo_fix  # noqa: E402

SCHEMA_VERSION = "1.0"
CHROME_FOLDS = {"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss"}
BREAK = re.compile(r"[,;:()\[\]{}!?\u00ab\u00bb\"/|\u2192\u2190*_#]|\s[-\u2013\u2014]\s|\.\s")
KEYWORD_KEYS = ("keyword", "keywords", "primary_keyword", "focus_keyword", "target_keyword", "query")


# --------------------------------------------------------------------------
# text folding: lower case, no accents, one space between words, with the map
# from each folded character back to the original text

def fold(text: str) -> Tuple[str, List[int]]:
    out: List[str] = []
    idx: List[int] = []
    for i, ch in enumerate(text or ""):
        d = CHROME_FOLDS.get(ch)
        if d is None:
            d = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c)).lower()
        if d and all(c.isalnum() for c in d):
            for c in d:
                out.append(c)
                idx.append(i)
        elif out and out[-1] != " ":
            out.append(" ")
            idx.append(i)
    return "".join(out), idx


def fold_words(text: str) -> List[str]:
    return fold(text)[0].split()


def inside_name(text: str, a: int, b: int) -> bool:
    """The words sit between two capitalised words with no punctuation between: a longer proper name."""
    before = re.search(r"([^\W\d_][\w'\u2019-]*)\s+$", text[:a])
    after = re.match(r"\s+([^\W\d_][\w'\u2019-]*)", text[b:])
    return bool(before and after and before.group(1)[0].isupper() and after.group(1)[0].isupper())


def load_rules(config: Optional[str]) -> Dict[str, Any]:
    rules = load_assets_json("link-rules.json")
    if config:
        rules = deep_merge(rules, load_json(config).get("links", {}) or {})
    return rules


def lang_of(rec: Dict[str, Any]) -> Optional[str]:
    lang = (rec.get("lang") or "").strip().lower()[:2]
    if lang:
        return lang
    return topics.url_lang(rec.get("url"))


# --------------------------------------------------------------------------
# audit

class Audit:
    def __init__(self, a: argparse.Namespace) -> None:
        self.a = a
        self.rules = load_rules(a.config)
        self.cfg = load_json(a.config) if a.config else {}
        self.trules = topics.load_rules(a.config)
        self.matcher = topics.Matcher(self.trules)
        self.stop = {w for lst in self.trules["stopwords"].values() for w in (fold(x)[0].strip() for x in lst) if w}
        self.generic = {fold(g)[0].strip() for lst in self.rules["generic_anchors"].values() for g in lst}
        self.skip_target = [re.compile(p, re.I) for p in self.rules["skip_target_paths"] + self.trules["exclude_path_patterns"]]
        self.skip_source = [re.compile(p, re.I) for p in self.rules["skip_source_paths"] + self.trules["exclude_path_patterns"]]
        rows = read_jsonl(a.crawl)
        if not rows:
            raise InputError(f"{a.crawl} holds no record")
        self.recs: Dict[str, Dict[str, Any]] = {}
        self.line_of: Dict[str, int] = {}
        for n, r in rows:
            self.recs[r["url"]] = r
            self.line_of[r["url"]] = n
        if not any("internal_anchors" in r for r in self.recs.values()):
            raise InputError(f"{a.crawl} has no internal_anchors: crawl it again with this version of crawl.py")
        first = rows[0][1]["url"]
        self.origin = re.match(r"https?://[^/]+", first).group(0)
        domain = self.cfg.get("domain") or self.origin
        self.brand = topics.brand_labels_for(domain, self.cfg)
        self.final_of = {u: (r.get("final_url") or u) for u, r in self.recs.items()}
        self.pages = {u: r for u, r in self.recs.items() if self.is_page(r)}
        self.gsc_pages: Dict[str, Dict[str, Any]] = {}
        self.gsc_queries: Dict[str, List[Tuple[str, int]]] = {}
        if a.bands:
            self.read_bands(load_json(a.bands))
        self.new_pages: Dict[str, Dict[str, Any]] = {}
        for spec in a.new_page or []:
            self.add_new_page(spec)

    # -- inputs --------------------------------------------------------------
    def is_page(self, r: Dict[str, Any]) -> bool:
        if r.get("status") != 200 or r.get("redirect_chain") or not r.get("indexable"):
            return False
        if "html" not in (r.get("content_type") or "html").lower():
            return False
        if re.match(r"(directory listing for|index of) /", (r.get("title") or "").strip(), re.I):
            return False  # a server's folder listing, not a page of the site
        return r.get("canonical_status") in (None, "self", "missing")

    def final(self, url: str) -> str:
        seen = set()
        while url in self.final_of and self.final_of[url] != url and url not in seen:
            seen.add(url)
            url = self.final_of[url]
        return url

    def read_bands(self, b: Dict[str, Any]) -> None:
        g = self.rules["gsc"]
        for row in b.get("pages") or []:
            url = normalize_url(row.get("page") or "")
            cur = row.get("cur") or {}
            self.gsc_pages[url] = {"position": cur.get("position"), "clicks": cur.get("clicks") or 0,
                                   "impressions": cur.get("impressions") or 0, "bands": row.get("bands") or []}
        for row in b.get("queries") or []:
            cur = row.get("cur") or {}
            page = row.get("top_page") or (row.get("pages") or [{}])[0].get("page")
            if not page or (cur.get("impressions") or 0) < g["min_impressions"]:
                continue
            self.gsc_queries.setdefault(normalize_url(page), []).append((row["query"], int(cur.get("impressions") or 0)))
        for page, q in (b.get("top_query_by_page") or {}).items():
            lst = self.gsc_queries.setdefault(normalize_url(page), [])
            if q and q not in [x for x, _ in lst]:
                lst.append((q, g["min_impressions"]))
        for page in self.gsc_queries:
            self.gsc_queries[page] = sorted(self.gsc_queries[page], key=lambda x: -x[1])[:g["queries_per_page"]]

    def add_new_page(self, spec: str) -> None:
        if "=" not in spec:
            raise InputError(f"--new-page {spec}: expected URL=FILE")
        url, path = spec.split("=", 1)
        if not os.path.isfile(path):
            raise InputError(f"--new-page {spec}: {path} not found")
        url = normalize_url(url if "://" in url else self.origin + "/" + url.lstrip("/"))
        text = open(path, encoding="utf-8", errors="replace").read()
        fm: Dict[str, str] = {}
        body = text
        m = re.match(r"---\s*\n(.*?)\n---\s*\n", text, re.S)
        if m:
            body = text[m.end():]
            for line in m.group(1).splitlines():
                k = re.match(r"([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
                if k:
                    fm[k.group(1).lower()] = k.group(2).strip().strip("'\"")
        h1 = re.search(r"^#\s+(.+)$", body, re.M)
        keywords = []
        for k in KEYWORD_KEYS:
            v = fm.get(k)
            if v:
                keywords += [x.strip().strip("'\"") for x in v.strip("[]").split(",") if x.strip()]
        self.new_pages[url] = {"url": url, "title": fm.get("title"), "h1": [h1.group(1).strip()] if h1 else [],
                               "keywords": keywords, "lang": (fm.get("lang") or "")[:2].lower() or topics.url_lang(url),
                               "file": path}

    # -- graph ---------------------------------------------------------------
    def graph(self) -> None:
        self.body_in: Dict[str, set] = {}
        self.chrome_in: Dict[str, set] = {}
        self.body_out: Dict[str, set] = {}
        self.anchors_to: Dict[str, List[Dict[str, str]]] = {}
        T = self.rules["template_links"]
        seen: Dict[Tuple[str, str], set] = {}
        for u, r in self.pages.items():
            for an in r.get("internal_anchors") or []:
                if an["zone"] == "body":
                    seen.setdefault((self.final(an["url"]), fold(an["text"])[0].strip()), set()).add(u)
        per_lang: Dict[Optional[str], int] = {}
        for r in self.pages.values():
            per_lang[lang_of(r)] = per_lang.get(lang_of(r), 0) + 1
        self.template = set()
        for k, v in seen.items():
            langs = {lang_of(self.pages[u]) for u in v}
            pool = sum(per_lang.get(l, 0) for l in langs)
            if len(v) >= max(T["min_pages"], T["share"] * pool):
                self.template.add(k)
        for u, r in self.pages.items():
            for an in r.get("internal_anchors") or []:
                t = self.final(an["url"])
                if t == u:
                    continue
                if an["zone"] == "body" and (t, fold(an["text"])[0].strip()) not in self.template:
                    self.body_in.setdefault(t, set()).add(u)
                    self.body_out.setdefault(u, set()).add(t)
                    self.anchors_to.setdefault(t, []).append({"from": u, "text": an["text"], "url": an["url"]})
                else:
                    self.chrome_in.setdefault(t, set()).add(u)

    def target_ok(self, url: str) -> bool:
        p = path_of(url)
        if p in ("", "/") or re.fullmatch(r"/[a-z]{2}(-[a-z]{2})?/?", p, re.I):
            return False
        return not any(rx.search(p) for rx in self.skip_target)

    def source_ok(self, url: str) -> bool:
        return not any(rx.search(path_of(url)) for rx in self.skip_source)

    def quick_win(self, url: str) -> bool:
        g = self.gsc_pages.get(url)
        if not g:
            return False
        lo, hi = self.rules["quick_win_positions"]
        return "quick_win" in g["bands"] or (g["position"] is not None and lo <= g["position"] <= hi)

    def issues(self) -> List[Dict[str, Any]]:
        R = self.rules
        out: List[Dict[str, Any]] = []
        start = None
        for u, r in self.recs.items():
            if r.get("depth") == 0:
                start = u
        for u, r in sorted(self.pages.items()):
            if u == start or path_of(u) in ("", "/"):
                continue
            b, c = len(self.body_in.get(u, ())), len(self.chrome_in.get(u, ()))
            if b == 0 and c == 0:
                out.append({"code": "orphan", "severity": "error", "url": u, "detail": "no page of the crawl links to it"})
            elif b == 0 and self.target_ok(u):
                hub = c >= R["hub_chrome_inlinks"]
                out.append({"code": "orphan-body", "severity": "info" if hub else "warning", "url": u,
                            "detail": f"only nav, header, footer, aside or repeated template links reach it ({c} page(s))"
                                      + ("; a menu entry of the site, a link from an article body would still help" if hub else "")})
            elif b < R["weak_body_inlinks"] and self.quick_win(u):
                g = self.gsc_pages[u]
                out.append({"code": "weak-inlinks", "severity": "warning", "url": u,
                            "detail": f"position {g['position']} in Search Console with {b} body inlink(s), "
                                      f"{R['weak_body_inlinks']} expected"})
            if r.get("depth") is not None and r["depth"] >= R["deep_page_depth"]:
                out.append({"code": "deep-page", "severity": "warning", "url": u, "detail": f"click depth {r['depth']}"})
            if not self.body_out.get(u):
                out.append({"code": "dead-end", "severity": "info", "url": u, "detail": "its body links to no other page"})
        for u, b in sorted(self.new_pages.items()):
            n = len(self.body_in.get(u, ()))
            if n < R["weak_body_inlinks"]:
                out.append({"code": "weak-inlinks", "severity": "warning", "url": u,
                            "detail": f"new page with {n} body inlink(s), {R['weak_body_inlinks']} expected"})
        generic: Dict[Tuple[str, str], List[str]] = {}
        for t, lst in sorted(self.anchors_to.items()):
            texts = [fold(x["text"])[0].strip() for x in lst]
            for x, f in zip(lst, texts):
                if f in self.generic:
                    generic.setdefault((t, x["text"]), []).append(x["from"])
            ad = R["anchor_diversity"]
            short = [f for f in texts if f and len(f.split()) <= ad["max_anchor_words"]]
            if len(short) >= ad["min_body_inlinks"]:
                counts: Dict[str, int] = {}
                for f in short:
                    counts[f] = counts.get(f, 0) + 1
                top, n = max(sorted(counts.items()), key=lambda kv: kv[1])
                if n / len(short) > ad["max_share"]:
                    label = next(x["text"] for x, f in zip(lst, texts) if f == top)
                    out.append({"code": "anchor-monotone", "severity": "warning", "url": t,
                                "detail": f"\"{label}\" carries {n} of its {len(short)} short body anchors"})
        for (t, text), frm in sorted(generic.items()):
            out.append({"code": "anchor-generic", "severity": "warning", "url": t, "anchor": text, "from": sorted(set(frm)),
                        "detail": f"\"{text or '(empty)'}\" from {len(set(frm))} page(s)"})
        broken: Dict[str, set] = {}
        redirects: Dict[str, set] = {}
        for u, r in self.pages.items():
            for an in r.get("internal_anchors") or []:
                t = self.recs.get(an["url"])
                if not t:
                    continue
                if t.get("redirect_chain") and self.final(an["url"]) != an["url"]:
                    fr = self.recs.get(self.final(an["url"]))
                    if fr and fr.get("status") == 200:
                        redirects.setdefault(an["url"], set()).add(u)
                elif (t.get("status") or 0) >= 400:
                    broken.setdefault(an["url"], set()).add(u)
        self.redirect_fixes = []
        for i, (old, frm) in enumerate(sorted(redirects.items()), 1):
            new = self.final(old)
            self.redirect_fixes.append({"id": f"R{i:02d}", "old": old, "new": new, "from": sorted(frm), "status": "proposed"})
            out.append({"code": "link-to-redirect", "severity": "warning", "url": old, "fix": f"R{i:02d}",
                        "detail": f"redirects to {new}, linked from {len(frm)} page(s)"})
        for old, frm in sorted(broken.items()):
            out.append({"code": "link-broken", "severity": "error", "url": old, "from": sorted(frm),
                        "detail": f"answers {self.recs[old].get('status')}, linked from {len(frm)} page(s) (repo_fix.py patches it)"})
        order = {"error": 0, "warning": 1, "info": 2}
        out.sort(key=lambda x: (order[x["severity"]], x["code"], x["url"]))
        return out

    # -- phrases -------------------------------------------------------------
    def valid_phrase(self, words: List[str], kind: str) -> bool:
        P = self.rules["phrase"]
        if not (P["min_words"] <= len(words) <= P["max_words"]) or len(" ".join(words)) < P["min_chars"]:
            return False
        content = [w for w in words if w not in self.stop and not w.isdigit()]
        if not content or all(any(b == w or b.startswith(w) for b in self.brand) for w in content):
            return False
        if " ".join(words) in self.generic:
            return False
        return len(content) >= 2 or kind in ("gsc", "keyword")

    def variants(self, text: str, kind: str) -> List[str]:
        words = fold_words(text)
        i, j = 0, len(words)
        while i < j and words[i] in self.stop:
            i += 1
        while j > i and words[j - 1] in self.stop:
            j -= 1
        out = []
        for w in (words[i:j], words):
            if self.valid_phrase(w, kind) and " ".join(w) not in out:
                out.append(" ".join(w))
        return out

    def phrases(self) -> Dict[str, List[Dict[str, Any]]]:
        """folded phrase -> [{target, kind, weight, text}]"""
        W = self.rules["weights"]["phrase"]
        index: Dict[str, List[Dict[str, Any]]] = {}

        def add(target: str, kind: str, text: Optional[str], extra: float = 0.0) -> None:
            if not text:
                return
            for v in self.variants(text, kind):
                lst = index.setdefault(v, [])
                if not any(x["target"] == target for x in lst):
                    lst.append({"target": target, "kind": kind, "weight": W[kind] + extra, "text": text})

        seps = self.trules["title_separators"]
        for u, r in sorted(self.pages.items()):
            if not self.target_ok(u):
                continue
            for q, imp in self.gsc_queries.get(u, []):
                add(u, "gsc", q, 0.1 * math.log10(1 + imp))
            for h in (r.get("h1") or [])[:1]:
                add(u, "h1", topics.strip_brand(h, self.brand, seps))
            slug = [s for s in path_of(u).split("?")[0].strip("/").split("/") if s]
            if slug and not re.fullmatch(r"[\d-]+", slug[-1]):
                add(u, "slug", re.sub(r"[-_]+", " ", slug[-1]))
            add(u, "title", topics.strip_brand(r.get("title"), self.brand, seps))
        for u, p in sorted(self.new_pages.items()):
            for k in p["keywords"]:
                add(u, "keyword", k)
            for h in p["h1"][:1]:
                add(u, "h1", h)
            add(u, "title", topics.strip_brand(p.get("title"), self.brand, seps))
            slug = [s for s in path_of(u).strip("/").split("/") if s]
            if slug:
                add(u, "slug", re.sub(r"[-_]+", " ", slug[-1]))
        owned = set(index)
        named = [" " + " ".join(fold_words(" ".join(filter(None, [r.get("title")] + list(r.get("h1") or []) + [path_of(u)])))) + " "
                 for u, r in self.pages.items()]
        for u, p in sorted(self.new_pages.items()):
            # a new page has no query yet: shorter pieces of its keyword and H1, when no other page owns them
            for text in p["keywords"] + p["h1"][:1]:
                words = fold_words(text)
                for n in range(len(words) - 1, 1, -1):
                    for i in range(0, len(words) - n + 1):
                        sub = words[i:i + n]
                        if sub[0] in self.stop or sub[-1] in self.stop:
                            continue
                        key = " ".join(sub)
                        if key in owned or any(f" {key} " in t for t in named) or not self.valid_phrase(sub, "partial"):
                            continue
                        lst = index.setdefault(key, [])
                        if not any(x["target"] == u for x in lst):
                            lst.append({"target": u, "kind": "partial", "weight": W["partial"], "text": text})
        return index

    # -- suggestions ---------------------------------------------------------
    def target_info(self, url: str) -> Dict[str, Any]:
        if url in self.new_pages:
            p = self.new_pages[url]
            return {"title": p.get("title"), "h1": p["h1"], "lang": p["lang"]}
        r = self.pages[url]
        return {"title": r.get("title"), "h1": r.get("h1") or [], "lang": lang_of(r)}

    def target_boost(self, url: str) -> Tuple[float, List[str]]:
        W = self.rules["weights"]["target"]
        b, why = 1.0, []
        if url in self.new_pages:
            b += W["new_page"]
            why.append("new page")
        else:
            n = len(self.body_in.get(url, ()))
            if n == 0:
                b += W["orphan"]
                why.append("no body inlink yet")
            elif n < self.rules["weak_body_inlinks"]:
                b += W["weak"]
                why.append(f"{n} body inlink(s)")
            if self.quick_win(url):
                b += W["quick_win"]
                why.append(f"position {self.gsc_pages[url]['position']} in Search Console")
            d = self.pages[url].get("depth")
            if d is not None and d >= self.rules["deep_page_depth"]:
                b += W["deep"]
                why.append(f"click depth {d}")
        return b, why

    def suggest(self) -> List[Dict[str, Any]]:
        R = self.rules
        W = R["weights"]
        index = self.phrases()
        if not index:
            return []
        lens = sorted({len(k.split()) for k in index}, reverse=True)
        tinfo = {t: self.target_info(t) for t in {x["target"] for lst in index.values() for x in lst}}
        tseq = {t: self.matcher.seq(" ".join(filter(None, [i.get("title")] + list(i["h1"])))) for t, i in tinfo.items()}
        boosts = {t: self.target_boost(t) for t in tinfo}
        cands: List[Dict[str, Any]] = []
        for s, r in sorted(self.pages.items()):
            if not self.source_ok(s) or len(self.body_out.get(s, ())) > R["max_source_body_outlinks"]:
                continue  # a listing page: its excerpts change with every new article
            slang = lang_of(r)
            sseq = self.matcher.seq(" ".join(filter(None, [r.get("title")] + list(r.get("h1") or []))))
            sname = " " + " ".join(fold_words(" ".join(filter(None, [r.get("title")] + list(r.get("h1") or []) + [path_of(s)])))) + " "
            linked = self.body_out.get(s, set())
            g = self.gsc_pages.get(s, {})
            strength = 1 + W["source_inlinks"] * math.log10(1 + len(self.body_in.get(s, ()))) \
                + W["source_clicks"] * math.log10(1 + (g.get("clicks") or 0))
            for bi, blk in enumerate(r.get("text_blocks") or []):
                if len(blk["links"]) >= R["max_existing_links_per_block"]:
                    continue
                folded, idx = fold(blk["text"])
                toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", folded)]
                words = [folded[a:b] for a, b in toks]
                used: List[Tuple[int, int]] = []
                for n in lens:
                    for i in range(0, len(words) - n + 1):
                        key = " ".join(words[i:i + n])
                        hits = index.get(key)
                        if not hits or f" {key} " in sname:
                            continue  # no target, or the source page is itself about these words
                        a0, b0 = idx[toks[i][0]], idx[toks[i + n - 1][1] - 1] + 1
                        if BREAK.search(blk["text"][a0:b0]):
                            continue  # the words run across punctuation: not one phrase of the sentence
                        if inside_name(blk["text"], a0, b0):
                            continue  # part of a longer name (NYSE OPEN Venture Capital Unicorn)
                        if any(a0 < y and x < b0 for x, y in blk["links"]) or any(a0 < y and x < b0 for x, y in used):
                            continue
                        best = None
                        for h in hits:
                            t = h["target"]
                            if t == s or t in linked or self.final(t) == s:
                                continue
                            tl = tinfo[t]["lang"]
                            if slang and tl and slang != tl:
                                continue
                            rel = self.matcher.score(sseq, tseq[t]) if sseq and tseq[t] else 0.0
                            boost, why = boosts[t]
                            score = h["weight"] * (1 + W["longer_phrase_bonus"] * (n - 2)) * boost * strength * (1 + W["relevance"] * rel)
                            if not best or score > best["score"]:
                                best = {"source": s, "target": t, "anchor": blk["text"][a0:b0], "phrase": key, "phrase_kind": h["kind"],
                                        "phrase_from": h["text"], "block": bi, "start": a0, "end": b0, "words": n,
                                        "relevance": rel, "score": round(score, 3), "why": why}
                        if best:
                            used.append((a0, b0))
                            ctx_a, ctx_b = max(0, a0 - 70), min(len(blk["text"]), b0 + 70)
                            best["context"] = ("..." if ctx_a else "") + blk["text"][ctx_a:a0] + "[[" + best["anchor"] + "]]" \
                                + blk["text"][b0:ctx_b] + ("..." if ctx_b < len(blk["text"]) else "")
                            cands.append(best)
        cands.sort(key=lambda c: (-c["score"], c["source"], c["block"], c["start"]))
        per_src: Dict[str, int] = {}
        per_tgt: Dict[str, int] = {}
        pairs, blocks = set(), {}
        anchors_per_tgt: Dict[Tuple[str, str], int] = {}
        hc = R["high_confidence"]
        out = []
        for c in cands:
            s, t = c["source"], c["target"]
            fa = fold(c["anchor"])[0].strip()
            if (s, t) in pairs or per_src.get(s, 0) >= R["max_new_links_per_source"] \
                    or per_tgt.get(t, 0) >= R["max_suggestions_per_target"] \
                    or blocks.get((s, c["block"]), 0) >= R["max_new_links_per_block"] \
                    or anchors_per_tgt.get((t, fa), 0) >= R["max_same_anchor_per_target"]:
                continue
            pairs.add((s, t))
            per_src[s] = per_src.get(s, 0) + 1
            per_tgt[t] = per_tgt.get(t, 0) + 1
            blocks[(s, c["block"])] = blocks.get((s, c["block"]), 0) + 1
            anchors_per_tgt[(t, fa)] = anchors_per_tgt.get((t, fa), 0) + 1
            c["confidence"] = "high" if (c["phrase_kind"] in hc["kinds"] or c["words"] >= hc["min_words"]) and \
                (c["relevance"] > 0 or c["phrase_kind"] in hc["kinds"]) else "medium"
            c["status"] = "proposed"
            out.append(c)
        out.sort(key=lambda c: (-c["score"], c["target"], c["source"]))
        for i, c in enumerate(out, 1):
            c["id"] = f"L{i:02d}"
        return out

    # -- run -----------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        self.graph()
        issues = self.issues()
        sugg = self.suggest()
        pages = []
        for u, r in sorted(self.pages.items()):
            g = self.gsc_pages.get(u, {})
            pages.append({"url": u, "crawl_line": self.line_of[u], "title": r.get("title"), "h1": r.get("h1") or [],
                          "lang": lang_of(r), "depth": r.get("depth"), "body_inlinks": len(self.body_in.get(u, ())),
                          "chrome_inlinks": len(self.chrome_in.get(u, ())), "body_outlinks": len(self.body_out.get(u, ())),
                          "gsc_position": g.get("position"), "gsc_clicks": g.get("clicks"),
                          "new_links_proposed": sum(1 for s in sugg if s["target"] == u)})
        for u, p in sorted(self.new_pages.items()):
            pages.append({"url": u, "new_page": True, "file": p["file"], "title": p.get("title"), "h1": p["h1"], "lang": p["lang"],
                          "body_inlinks": len(self.body_in.get(u, ())), "new_links_proposed": sum(1 for s in sugg if s["target"] == u)})
        bi = [p["body_inlinks"] for p in pages if not p.get("new_page")]
        counts: Dict[str, int] = {}
        for x in issues:
            counts[x["code"]] = counts.get(x["code"], 0) + 1
        metrics = {
            "pages": len(self.pages), "new_pages": len(self.new_pages),
            "body_links": sum(len(v) for v in self.body_out.values()),
            "median_body_inlinks": sorted(bi)[len(bi) // 2] if bi else 0,
            "pages_without_body_inlink": sum(1 for x in bi if x == 0),
            "issues": counts, "suggestions": len(sugg),
            "suggestions_high": sum(1 for s in sugg if s["confidence"] == "high"),
            "redirect_fixes": len(self.redirect_fixes),
            "gsc": bool(self.a.bands),
        }
        return {"schema_version": SCHEMA_VERSION, "generated_by": "links.py", "today": self.a.today or date.today().isoformat(),
                "inputs": {"crawl": os.path.abspath(self.a.crawl), "bands": os.path.abspath(self.a.bands) if self.a.bands else None,
                           "new_pages": sorted(self.new_pages)},
                "metrics": metrics, "pages": pages, "issues": issues, "suggestions": sugg, "redirect_fixes": self.redirect_fixes}


def md_cell(s: Any) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def render_md(doc: Dict[str, Any]) -> str:
    m = doc["metrics"]
    L = ["## Internal linking", ""]
    L.append(f"{m['pages']} indexable pages, {m['body_links']} links between pages in their body text, median "
             f"{m['median_body_inlinks']} body inlink(s) per page, {m['pages_without_body_inlink']} page(s) without any. "
             f"{m['suggestions']} link(s) to add ({m['suggestions_high']} high confidence), {m['redirect_fixes']} link(s) to "
             f"point past a redirect." + ("" if m["gsc"] else " No Search Console bands: quick wins not weighted."))
    L.append("")
    flagged = {x["url"] for x in doc["issues"] if x["code"] in ("orphan", "orphan-body", "weak-inlinks") and x["severity"] != "info"}
    prio = [p for p in doc["pages"] if p.get("new_page") or p["url"] in flagged or p["new_links_proposed"]]
    if prio:
        L += ["### Pages that need links", "", "| Page | Body inlinks | Nav/footer inlinks | Position | Links proposed |", "|---|---|---|---|---|"]
        for p in sorted(prio, key=lambda p: (not p.get("new_page"), p["body_inlinks"], p["url"]))[:40]:
            L.append(f"| {md_cell(p['url'])}{' (new)' if p.get('new_page') else ''} | {p['body_inlinks']} | "
                     f"{p.get('chrome_inlinks', '')} | {md_cell(p.get('gsc_position') or '')} | {p['new_links_proposed']} |")
        L.append("")
    if doc["suggestions"]:
        L += ["### Links to add", "", "Each anchor is a phrase the source page already holds: the link wraps those words, nothing is rewritten.", "",
              "| Id | From | To | Anchor | Sentence | Why |", "|---|---|---|---|---|---|"]
        for s in doc["suggestions"]:
            why = ", ".join(s["why"] + (["same subject"] if s["relevance"] else []))
            L.append(f"| {s['id']} | {md_cell(s['source'])} | {md_cell(s['target'])} | {md_cell(s['anchor'])} | "
                     f"{md_cell(s['context'])} | {md_cell(why or s['phrase_kind'])} ({s['confidence']}) |")
        L.append("")
    issues = [x for x in doc["issues"] if x["severity"] != "info"]
    if issues:
        L += ["### Linking defects", "", "| Severity | Defect | Page | Detail |", "|---|---|---|---|"]
        for x in issues:
            L.append(f"| {x['severity']} | {x['code']} | {md_cell(x['url'])} | {md_cell(x['detail'])} |")
        L.append("")
    dead = [x for x in doc["issues"] if x["code"] == "dead-end"]
    if dead:
        L += [f"{len(dead)} page(s) link to no other page from their body: " + ", ".join(x["url"] for x in dead[:15])
              + (" ..." if len(dead) > 15 else ""), ""]
    if doc["redirect_fixes"]:
        L += ["### Links that go through a redirect", "", "| Id | Linked URL | Final URL | From |", "|---|---|---|---|"]
        for r in doc["redirect_fixes"]:
            L.append(f"| {r['id']} | {md_cell(r['old'])} | {md_cell(r['new'])} | {len(r['from'])} page(s) |")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def cmd_audit(a) -> int:
    doc = Audit(a).run()
    os.makedirs(a.out_dir, exist_ok=True)
    write_json(os.path.join(a.out_dir, "links.json"), doc)
    write_text(os.path.join(a.out_dir, "links.md"), render_md(doc))
    if a.json:
        print(json.dumps(doc["metrics"], ensure_ascii=False, indent=2))
    else:
        m = doc["metrics"]
        print(f"{m['pages']} pages, {m['suggestions']} link(s) to add, {sum(m['issues'].values())} linking defect(s), "
              f"{m['redirect_fixes']} redirect fix(es): {os.path.join(a.out_dir, 'links.md')}")
    return 0


# --------------------------------------------------------------------------
# patch

PROTECT = [
    re.compile(r"!?\[[^\]]*\]\([^)]*\)"),
    re.compile(r"<a\b[^>]*>.*?</a\s*>", re.I),
    re.compile(r"<[^>]+>"),
    re.compile(r"`[^`]*`"),
    re.compile(r"https?://\S+"),
]
PROTECT_CODE = re.compile(r"\{[^{}]*\}")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s|<h[1-6]\b", re.I)
CODE_EXT = (".astro", ".jsx", ".tsx", ".vue", ".svelte", ".njk")


def anchor_rx(anchor: str) -> "re.Pattern[str]":
    words = anchor.split()
    parts = []
    for w in words:
        parts.append("".join("['\u2019]" if ch in "'\u2019" else re.escape(ch) for ch in w))
    return re.compile(r"(?<![\w])" + r"[\s\u00a0]+".join(parts) + r"(?![\w])")


def protected(line: str, rel: str) -> List[Tuple[int, int]]:
    spans = []
    rxs = PROTECT + ([PROTECT_CODE] if rel.lower().endswith(CODE_EXT) else [])
    for rx in rxs:
        spans += [(m.start(), m.end()) for m in rx.finditer(line)]
    return spans


def body_lines(repo: "repo_fix.Repo", rel: str) -> List[int]:
    L = repo.lines[rel]
    fm = repo.frontmatter(rel)
    start = fm["end"] + 1 if fm else 0
    if rel.lower().endswith(".astro") and L and L[0].strip() == "---":
        for i in range(1, len(L)):
            if L[i].strip() == "---":
                start = i + 1
                break
    out, fence = [], False
    for i in range(start, len(L)):
        s = L[i].lstrip()
        if s.startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence or HEADING.search(L[i]) or s.startswith(("import ", "export ", "<script", "<style", "//")):
            continue
        out.append(i)
    return out


def find_in_line(line: str, rx: "re.Pattern[str]", rel: str) -> Optional["re.Match[str]"]:
    prot = protected(line, rel)
    for m in rx.finditer(line):
        if not any(m.start() < b and a < m.end() for a, b in prot):
            return m
    return None


def link_markup(rel: str, text: str, href: str) -> str:
    if rel.lower().endswith(repo_fix.MD_EXT):
        return f"[{text}]({href})"
    return f'<a href="{href}">{text}</a>'


def href_of(url: str) -> str:
    p = path_of(url)
    return p if p else "/"


class Patcher:
    def __init__(self, repo: "repo_fix.Repo") -> None:
        self.repo = repo
        self.edits: Dict[Tuple[str, int], str] = {}
        self.ids: Dict[Tuple[str, int], List[str]] = {}

    def current(self, rel: str, i: int) -> str:
        return self.edits.get((rel, i), self.repo.lines[rel][i].rstrip("\r\n"))

    def set(self, rel: str, i: int, text: str, fid: str) -> None:
        self.edits[(rel, i)] = text
        self.ids.setdefault((rel, i), []).append(fid)

    def fixes(self) -> List[Dict[str, Any]]:
        return [{"id": "+".join(self.ids[k]), "file": k[0], "line": k[1] + 1, "op": "replace", "new": [v], "placeholders": []}
                for k, v in sorted(self.edits.items())]


def locate(repo: "repo_fix.Repo", url: str, page: Dict[str, Any]) -> Tuple[Optional[str], List[str], str]:
    """repo_fix.locate_page, then, among several candidates, the one file named after the URL slug
    inside a folder named after the parent segment (content/fr/blog/x.md over drafts/x/article.md)."""
    rel, cands, how = repo_fix.locate_page(repo, {"url": url, "h1": page.get("h1"), "title": page.get("title")})
    if rel or len(cands) < 2:
        return rel, cands, how
    segs = [x for x in path_of(url).split("?")[0].strip("/").split("/") if x]
    if not segs:
        return rel, cands, how

    def score(f: str) -> int:
        route = repo_fix.route_of(f)
        sc = 2 if route and route[-1] == segs[-1] else 0
        if len(segs) > 1 and len(route) > 1 and route[-2] == segs[-2]:
            sc += 1
        return sc
    ranked = sorted(cands, key=lambda f: -score(f))
    if score(ranked[0]) >= 2 and (len(ranked) == 1 or score(ranked[1]) < score(ranked[0])):
        return ranked[0], cands, "file named after the URL slug among " + ", ".join(cands[:3])
    return rel, cands, how


def place_link(p: Patcher, s: Dict[str, Any], page: Dict[str, Any], block_text: Optional[str]) -> Dict[str, Any]:
    repo = p.repo
    rel, cands, how = locate(repo, s["source"], page)
    if not rel:
        return {"placed": False, "reason": how, "candidates": cands[:5]}
    rx = anchor_rx(s["anchor"])
    hits = []
    for i in body_lines(repo, rel):
        m = find_in_line(p.current(rel, i), rx, rel)
        if m:
            hits.append((i, m))
    if len(hits) > 1 and block_text:
        before = fold_words(block_text[:s["start"]])[-3:]
        after = fold_words(block_text[s["end"]:])[:3]
        scored = [(sum(1 for w in before + after if w in fold(p.current(rel, i))[0].split()), i, m) for i, m in hits]
        top = max(x[0] for x in scored)
        best = [(i, m) for sc, i, m in scored if sc == top]
        if top > 0 and len(best) == 1:
            hits = best
    if len(hits) != 1:
        others = [f for f in repo.scope(rel)[1:] if any(find_in_line(p.current(f, i), rx, f) for i in body_lines(repo, f))]
        reason = (f"\"{s['anchor']}\" found on {len(hits)} lines of {rel}" if hits else
                  f"\"{s['anchor']}\" not found on one line of {rel} outside links, tags and code"
                  + (f"; it sits in a shared file ({', '.join(others[:3])}): a link there appears on every page using it" if others else ""))
        return {"placed": False, "reason": reason, "file": rel, "candidates": [f"{rel}:{i + 1}" for i, _ in hits][:5]}
    i, m = hits[0]
    line = p.current(rel, i)
    new = line[:m.start()] + link_markup(rel, m.group(0), href_of(s["target"])) + line[m.end():]
    p.set(rel, i, new, s["id"])
    return {"placed": True, "file": rel, "line": i + 1}


def place_redirect(p: Patcher, r: Dict[str, Any], pages: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    old_path, new_path = href_of(r["old"]), href_of(r["new"])
    forms = [(r["old"], r["new"]), (old_path, new_path)]
    touched, files, unlocated = [], [], []
    for u in r["from"]:
        rel, _, _ = locate(p.repo, u, pages.get(u, {}))
        if not rel:
            unlocated.append(u)
            continue
        for f in p.repo.scope(rel):
            if f not in files:
                files.append(f)
    for rel in files:
        for i in range(len(p.repo.lines[rel])):
            line = p.current(rel, i)
            new = line
            for old, rep in forms:
                rx = re.compile(r"(\]\(\s*|href\s*=\s*\{?\s*[\"']|^\s*\[[^\]]+\]:\s*)" + re.escape(old) + r"(?=[\"')#?\s}]|$)")
                new = rx.sub(lambda m: m.group(1) + rep, new)
            if new != line:
                p.set(rel, i, new, r["id"])
                touched.append(f"{rel}:{i + 1}")
    if not touched:
        return {"placed": False, "reason": f"no href to {old_path} found in the source files of the {len(r['from'])} linking page(s)"
                + (f" ({len(unlocated)} not located)" if unlocated else "") + ": the link may be built at runtime"}
    res = {"placed": True, "lines": touched}
    if unlocated:
        res["not_located"] = unlocated
    return res


def cmd_patch(a) -> int:
    path = os.path.join(a.out_dir, "links.json")
    if not os.path.isfile(path):
        raise InputError(f"{path} not found: run links.py audit first")
    doc = load_json(path)
    repo = repo_fix.Repo(a.repo)
    only = {x.strip() for x in (a.only or "").split(",") if x.strip()}
    pages = {p["url"]: p for p in doc["pages"]}
    crawl = {}
    if doc["inputs"].get("crawl") and os.path.isfile(doc["inputs"]["crawl"]):
        crawl = {r["url"]: r for _, r in read_jsonl(doc["inputs"]["crawl"])}
    p = Patcher(repo)
    placed, manual = [], []
    for s in doc["suggestions"]:
        if only and s["id"] not in only:
            continue
        blocks = (crawl.get(s["source"]) or {}).get("text_blocks") or []
        bt = blocks[s["block"]]["text"] if s["block"] < len(blocks) else None
        res = place_link(p, s, pages.get(s["source"], {}), bt)
        (placed if res["placed"] else manual).append(dict(res, id=s["id"], source=s["source"], target=s["target"], anchor=s["anchor"]))
    for r in doc["redirect_fixes"]:
        if only and r["id"] not in only:
            continue
        res = place_redirect(p, r, pages)
        (placed if res["placed"] else manual).append(dict(res, id=r["id"], old=r["old"], new=r["new"]))
    out = os.path.join(a.out_dir, "repo")
    patches = repo_fix.write_patches(out, repo, p.fixes(), {})
    for x in patches:
        x["patch"] = "repo/" + x["patch"]
    ok = all(x["git_apply_check"]["ok"] for x in patches)
    res = {"repo": repo.root, "patches": patches, "placed": placed, "manual": manual, "git_apply_check_ok": ok}
    write_json(os.path.join(a.out_dir, "links-patch.json"), res)
    L = ["### Internal links: source patches", "",
         f"{len(placed)} change(s) in {len(patches)} file(s), {len(manual)} to place by hand. Apply with "
         "`git apply <patch>` in the site repository, then build and run verify_served.py --check-links.", ""]
    for x in patches:
        L.append(f"- `{x['patch']}`: {x['file']} ({', '.join(x['fixes'])}), git apply --check "
                 f"{'ok' if x['git_apply_check']['ok'] else 'FAILED: ' + x['git_apply_check']['message']}")
    if manual:
        L += ["", "To place by hand:", ""]
        for x in manual:
            L.append(f"- {x['id']}: {x.get('anchor') or x.get('old')} -> {x.get('target') or x.get('new')}: {x['reason']}")
    write_text(os.path.join(a.out_dir, "links-patch.md"), "\n".join(L) + "\n")
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"{len(placed)} placed in {len(patches)} patch(es), {len(manual)} by hand: {os.path.join(a.out_dir, 'links-patch.md')}")
    return 0 if ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Internal linking: link graph defects and links to add, as repository patches.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("Writes")[0][-900:])
    sub = ap.add_subparsers(dest="cmd", required=True)
    au = sub.add_parser("audit", help="graph metrics, defects and links to add")
    au.add_argument("--crawl", required=True, help="crawl.jsonl of the run")
    au.add_argument("--bands", help="bands.json of gsc_bands.py (queries per page, quick wins)")
    au.add_argument("--new-page", action="append", metavar="URL=FILE", help="a page not online yet (draft.md of the write mode); repeatable")
    au.add_argument("--config", help="project config.json (links overrides)")
    au.add_argument("--out-dir", required=True)
    au.add_argument("--today")
    au.add_argument("--json", action="store_true")
    pa = sub.add_parser("patch", help="suggestions and redirect fixes as patches of the site repository")
    pa.add_argument("--out-dir", required=True, help="folder of links.json")
    pa.add_argument("--repo", required=True, help="the site's source repository (read only)")
    pa.add_argument("--only", help="comma-separated ids (L01,R02); default every proposed link and fix")
    pa.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return cmd_audit(a) if a.cmd == "audit" else cmd_patch(a)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
