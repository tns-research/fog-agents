#!/usr/bin/env python3
"""
eeat.py

E-E-A-T signals measured on the crawl, scored by a fixed formula. The model
comments the result, it never scores a page. Reads crawl.jsonl (the eeat_raw,
external_links and jsonld fields written by crawl.py), never the network.

    python3 eeat.py --crawl <run>/crawl.jsonl --out-dir <run> [--today YYYY-MM-DD] [--config <project>/seo-audit/config.json]

Per 200 HTML page: author visible (byline, a[rel=author], itemprop author),
author in the JSON-LD, author page linked and answering 200, publication and
update dates (JSON-LD, meta, <time>, visible text), days since the update,
outbound links to sources (social networks and the site's own hosts
excluded), citations and reference lists. Per site: About, Contact, legal
and privacy pages, Organization JSON-LD and its sameAs, reviews marked up,
author pages, testimonial blocks. Every signal is a boolean or a number with
its evidence (selector, JSON-LD path, URL and crawl line, or the excerpt).

Score: assets/eeat-weights.json (formula in its _comment). Article pages get
a page score, the other pages carry their signals with score null. The same
crawl.jsonl, weights and --today give byte-identical outputs; --today
defaults to the system date and is written in the output.

Writes:
  eeat.json   site score, site signals, per page kind, score, signals, missing
  eeat.md     the E-E-A-T section of the report (scores copied, never edited)

The comparison with the previous run is done by `seo_state.py record-run`
(signals gained and lost per page) when both runs hold an eeat.json.

Exit codes: 0 written, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, deep_merge, host_of, load_assets_json, load_json, parse_day,  # noqa: E402
                     path_of, read_jsonl, text_date, write_json, write_text)

MODIFIED_CLASS = ("updat", "modif", "revis", "edited")


def half_up(x: float) -> int:
    return int(x + 0.5)


def load_weights(config: Optional[str]) -> Dict[str, Any]:
    w = load_assets_json("eeat-weights.json")
    if config:
        w = deep_merge(w, load_json(config).get("eeat", {}))
    return w


def bare(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def host_in(host: str, domains: List[str]) -> bool:
    h = bare(host)
    return any(h == d or h.endswith("." + d) for d in domains)


def ref(crawl_name: str, n: int) -> str:
    return f"{crawl_name}:{n}"


class Site:
    def __init__(self, lines: List[Tuple[int, Dict[str, Any]]], crawl_name: str) -> None:
        self.lines = lines
        self.name = crawl_name
        self.by_url = {}
        for n, r in lines:
            self.by_url.setdefault(r["url"], (n, r))
        first = lines[0][1]["url"] if lines else ""
        self.host = bare(host_of(first))

    def ok(self, url: str) -> Optional[Tuple[int, Dict[str, Any]]]:
        hit = self.by_url.get(url)
        if hit and hit[1].get("status") == 200 and not hit[1].get("redirect_chain"):
            return hit
        return None

    def internal(self, url: str) -> bool:
        h = bare(host_of(url))
        return h == self.host or h.endswith("." + self.host)


def html_ok(r: Dict[str, Any]) -> bool:
    return r.get("status") == 200 and not r.get("redirect_chain") and "html" in (r.get("content_type") or "").lower()


def article_kind(r: Dict[str, Any], W: Dict[str, Any]) -> Tuple[str, str]:
    det = W["article_detection"]
    raw = r.get("eeat_raw") or {}
    types = set(r.get("jsonld_types") or [])
    hit = sorted(types & set(det["jsonld_types"]))
    if hit:
        return "article", f"JSON-LD {hit[0]}"
    og = (raw.get("meta") or {}).get("og:type", "").lower()
    if og in det["og_types"]:
        return "article", f"og:type {og}"
    p = path_of(r["url"]).split("?")[0]
    for pre in det["path_prefixes"]:
        if p.startswith(pre) and p.strip("/") != pre.strip("/"):
            return "article", f"path {pre}"
    return "page", "not an article: site signals apply"


def article_entities(raw: Dict[str, Any], W: Dict[str, Any]) -> List[Dict[str, Any]]:
    types = set(W["article_detection"]["jsonld_types"])
    return [e for e in raw.get("jsonld_entities", []) if set(e["types"]) & types]


def sig(value: Any, evidence: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    out = {"value": value, "evidence": evidence}
    out.update(extra)
    return out


def page_signals(r: Dict[str, Any], site: Site, W: Dict[str, Any], today: date) -> Dict[str, Dict[str, Any]]:
    raw = r.get("eeat_raw") or {}
    meta = raw.get("meta") or {}
    els = raw.get("elements") or []
    arts = article_entities(raw, W)
    S: Dict[str, Dict[str, Any]] = {}

    bylines = [e for e in els if e["kind"] == "byline" and e.get("text")]
    S["author_visible"] = sig(bool(bylines), [{"selector": e["selector"], "text": e["text"][:120]} for e in bylines[:3]])

    ev = []
    for e in arts:
        for a in e.get("author", []):
            if a.get("name"):
                ev.append({"source": f"{e['path']}.author", "value": a["name"]})
    for ip in raw.get("itemprops") or []:
        if ip["itemprop"] == "author":
            ev.append({"source": f'[itemprop="author"] {ip["tag"]}', "value": ip["value"]})
    for e in bylines:
        if "author" in (e.get("itemprop") or "").split():
            ev.append({"source": e["selector"], "value": e["text"][:80]})
    S["author_schema"] = sig(bool(ev), ev[:3])

    cand: List[Tuple[str, str]] = []
    for u in raw.get("rel_author") or []:
        cand.append((u, "rel=author"))
    for e in bylines:
        for u in e.get("links", []):
            cand.append((u, e["selector"]))
    for e in arts:
        for a in e.get("author", []):
            if a.get("url"):
                cand.append((a["url"], f"{e['path']}.author.url"))
    linked, tried, seen = [], [], set()
    for u, how in cand:
        if u in seen or not site.internal(u) or u == r["url"]:
            continue
        seen.add(u)
        hit = site.ok(u)
        if hit:
            linked.append({"url": u, "via": how, "ref": ref(site.name, hit[0])})
        else:
            st = site.by_url.get(u)
            tried.append({"url": u, "via": how, "status": st[1].get("status") if st else "not in the crawl"})
    S["author_page_linked"] = sig(bool(linked), linked[:3] or tried[:3])

    pub, mod = date_sources(raw, arts, meta, els)
    S["date_published"] = sig(bool(pub), pub[:3], date=pub[0]["date"] if pub else None)
    S["date_modified"] = sig(bool(mod), mod[:3], date=mod[0]["date"] if mod else None)

    vis = [{"selector": "time", "text": e["text"][:60], "datetime": e.get("datetime")} for e in els if e["kind"] == "time" and e.get("text")]
    vis += [{"text": p["text"]} for p in raw.get("date_phrases") or []]
    S["date_visible"] = sig(bool(vis), vis[:3])

    days = None
    note = None
    if mod and mod[0]["date"]:
        days = (today - parse_day(mod[0]["date"])).days
        if days < 0:
            note = "update date after --today"
    S["freshness"] = sig(days, [{"date_modified": mod[0]["date"], "today": today.isoformat()}] if mod else [], days_since_modified=days,
                         **({"note": note} if note else {}))

    social = W["social_domains"]
    ext = [u for u in r.get("external_links") or [] if not site.internal(u) and not host_in(host_of(u), social)]
    ext = sorted(dict.fromkeys(ext))
    S["external_sources"] = sig(len(ext), [{"url": u} for u in ext[:5]])

    cites = [dict(c) for c in raw.get("citations") or []]
    heads = [h for h in raw.get("headings") or [] if " ".join(h.lower().split()).strip(" :") in W["reference_headings"]]
    cites += [{"selector": "h2/h3", "text": h} for h in heads[:1]]
    S["citations"] = sig(len(cites), cites[:5])
    return S


def date_sources(raw: Dict[str, Any], arts: List[Dict[str, Any]], meta: Dict[str, str],
                 els: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pub: List[Dict[str, Any]] = []
    mod: List[Dict[str, Any]] = []

    def add(lst, source, value):
        d = text_date(value or "")
        if d:
            lst.append({"source": source, "value": value, "date": d})

    for e in arts + [x for x in raw.get("jsonld_entities", []) if x not in arts]:
        if e.get("date_published"):
            add(pub, f"{e['path']}.datePublished", e["date_published"])
        if e.get("date_modified"):
            add(mod, f"{e['path']}.dateModified", e["date_modified"])
    for k in ("article:published_time", "date", "dc.date"):
        if meta.get(k):
            add(pub, f'meta[{k}]', meta[k])
    for k in ("article:modified_time", "og:updated_time", "dcterms.modified", "last-modified"):
        if meta.get(k):
            add(mod, f'meta[{k}]', meta[k])
    for ip in raw.get("itemprops") or []:
        if ip["itemprop"] == "datePublished":
            add(pub, f'[itemprop="datePublished"] {ip["tag"]}', ip["value"])
        elif ip["itemprop"] == "dateModified":
            add(mod, f'[itemprop="dateModified"] {ip["tag"]}', ip["value"])
    for e in els:
        if e["kind"] != "time":
            continue
        value = e.get("datetime") or e.get("text") or ""
        cls = (e.get("class") or "").lower()
        if e.get("itemprop") in ("datePublished", "dateModified"):
            continue
        target = mod if any(m in cls for m in MODIFIED_CLASS) else pub
        add(target, "time" + (f".{cls.split()[0]}" if cls else ""), value)
    for p in raw.get("date_phrases") or []:
        if p.get("date"):
            (mod if p["kind"] == "modified" else pub).append({"source": "visible text", "value": p["text"], "date": p["date"]})
    return pub, mod


def norm_value(name: str, s: Dict[str, Any], spec: Dict[str, Any]) -> float:
    v = s["value"]
    if name == "freshness":
        if v is None or v < 0:
            return 0.0
        for band in spec["bands"]:
            if v <= band["max_days"]:
                return float(band["value"])
        return float(spec["else"])
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        cap = spec.get("cap") or 1
        return min(float(v), float(cap)) / float(cap)
    return 0.0


def score(signals: Dict[str, Dict[str, Any]], specs: Dict[str, Dict[str, Any]]) -> Tuple[Optional[int], List[str]]:
    num = den = 0.0
    missing = []
    for name, spec in specs.items():
        s = signals.get(name)
        if s is None:
            continue
        v = norm_value(name, s, spec)
        s["weight"] = spec["weight"]
        s["score"] = round(v, 3)
        if spec["weight"]:
            num += spec["weight"] * v
            den += spec["weight"]
            if v == 0:
                missing.append(name)
    return (half_up(100 * num / den) if den else None), missing


def site_signals(site: Site, pages: List[Dict[str, Any]], W: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    S: Dict[str, Dict[str, Any]] = {}
    ok = [(n, r) for n, r in site.lines if html_ok(r)]
    for key, segs in W["site_pages"].items():
        hits = []
        for n, r in ok:
            parts = [x.lower() for x in path_of(r["url"]).split("?")[0].strip("/").split("/") if x]
            if parts and any(p in segs for p in parts) and len(parts) <= 2:
                hits.append({"url": r["url"], "ref": ref(site.name, n)})
        S[key] = sig(bool(hits), hits[:3])
    orgs = []
    for n, r in ok:
        for e in (r.get("eeat_raw") or {}).get("jsonld_entities", []):
            if set(e["types"]) & set(W["organization_types"]):
                orgs.append((e.get("same_as", 0), n, r["url"], e))
    orgs.sort(key=lambda x: (-x[0], x[1]))
    S["organization_schema"] = sig(bool(orgs), [{"url": u, "ref": ref(site.name, n), "source": e["path"], "name": e.get("name")}
                                                for _, n, u, e in orgs[:3]])
    best = orgs[0] if orgs else None
    S["organization_same_as"] = sig(best[0] if best else 0, [{"url": best[2], "ref": ref(site.name, best[1]), "source": best[3]["path"] + ".sameAs"}] if best else [])
    reviews: List[Dict[str, Any]] = []
    rtypes = set(W["review_types"])
    for n, r in ok:
        raw = r.get("eeat_raw") or {}
        for e in raw.get("jsonld_entities", []):
            if set(e["types"]) & rtypes or e.get("has_review"):
                reviews.append({"url": r["url"], "ref": ref(site.name, n), "source": e["path"], "types": e["types"]})
        for it in raw.get("itemtypes", []):
            if any(it.rstrip("/").lower().endswith("/" + t.lower()) for t in rtypes):
                reviews.append({"url": r["url"], "ref": ref(site.name, n), "source": f'[itemtype="{it}"]'})
    first_per_url = list({e["url"]: e for e in reversed(reviews)}.values())[::-1]
    S["reviews_marked_up"] = sig(bool(reviews), first_per_url[:3], count=len(reviews))
    authors = {}
    for p in pages:
        s = p["signals"].get("author_page_linked")
        if s and s["value"]:
            for e in s["evidence"]:
                authors.setdefault(e["url"], e)
    S["author_pages"] = sig(len(authors), [authors[u] for u in sorted(authors)][:5])
    blocks = []
    for n, r in ok:
        for e in (r.get("eeat_raw") or {}).get("elements", []):
            if e["kind"] == "testimonial":
                blocks.append({"url": r["url"], "ref": ref(site.name, n), "selector": e["selector"], "text": e["text"][:80]})
    S["testimonial_blocks"] = sig(len(blocks), blocks[:3])
    return S


def evaluate(crawl_path: str, W: Dict[str, Any], today: date) -> Dict[str, Any]:
    lines = read_jsonl(crawl_path)
    name = os.path.basename(crawl_path)
    site = Site(lines, name)
    pages = []
    for n, r in lines:
        if not html_ok(r):
            continue
        kind, why = article_kind(r, W)
        sigs = page_signals(r, site, W, today)
        entry = {"url": r["url"], "ref": ref(name, n), "kind": kind, "kind_reason": why, "indexable": bool(r.get("indexable")),
                 "score": None, "missing": [], "signals": sigs}
        if kind == "article":
            entry["score"], entry["missing"] = score(sigs, W["page_signals"])
        else:
            score(sigs, W["page_signals"])
        pages.append(entry)
    ss = site_signals(site, pages, W)
    site_signal_score, site_missing = score(ss, W["site_signals"])
    arts = [p["score"] for p in pages if p["kind"] == "article" and p["indexable"] and p["score"] is not None]
    mean = round(sum(arts) / len(arts), 1) if arts else None
    share = float(W["site_score"]["site_signals_share"])
    if mean is None:
        total = site_signal_score
    else:
        total = half_up(share * (site_signal_score or 0) + (1 - share) * mean)
    return {
        "schema_version": "1.0",
        "generated_by": "eeat.py",
        "crawl": name,
        "today": today.isoformat(),
        "weights": "assets/eeat-weights.json",
        "weights_version": W.get("version"),
        "site_host": site.host,
        "site_score": total,
        "site_signal_score": site_signal_score,
        "article_mean": mean,
        "articles_scored": len(arts),
        "site_missing": site_missing,
        "site_signals": ss,
        "pages": pages,
        "note": "Measured by script on the served HTML of the crawl. The model comments these signals and never changes a score.",
    }


def fmt(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if v is None:
        return "n/a"
    return str(v)


def evidence_text(s: Dict[str, Any]) -> str:
    out = []
    for e in s.get("evidence", [])[:2]:
        if "selector" in e and "text" in e:
            out.append(f'`{e["selector"]}`' + (f' "{e["text"][:60]}"' if e["text"] else ""))
        elif "source" in e and "value" in e:
            out.append(f'`{e["source"]}` = `{str(e["value"])[:60]}`')
        elif "url" in e and "ref" in e:
            out.append(f'{e["url"]} ({e["ref"]})')
        elif "url" in e:
            out.append(f'{e["url"]}' + (f' ({e.get("status")})' if e.get("status") else ""))
        elif "text" in e:
            out.append(f'"{e["text"][:60]}"')
        elif "date_modified" in e:
            out.append(f'dateModified {e["date_modified"]}, today {e["today"]}')
    return "; ".join(out).replace("|", "\\|") or "none found"


def render(res: Dict[str, Any]) -> str:
    L = ["## E-E-A-T (measured)", "",
         f"From `eeat.json` (`eeat.py`, weights `{res['weights']}` version {res['weights_version']}, today {res['today']}). "
         "Scores are copied, never edited: the comment explains the missing signals and the fix, it does not score.", "",
         f"**E-E-A-T site score:** {fmt(res['site_score'])} (eeat.json)", "",
         f"Site signals {fmt(res['site_signal_score'])}/100, mean of {res['articles_scored']} indexable article(s) {fmt(res['article_mean'])}/100.", "",
         "| Site signal | Value | Weight | Evidence |", "|---|---|---:|---|"]
    for k, s in res["site_signals"].items():
        L.append(f"| `{k}` | {fmt(s['value'])} | {s.get('weight', 0)} | {evidence_text(s)} |")
    L += ["", "| URL | Kind | E-E-A-T score | Missing signals |", "|---|---|---:|---|"]
    for p in res["pages"]:
        miss = ", ".join(f"`{m}`" for m in p["missing"]) or ("none" if p["score"] is not None else "n/a")
        L.append(f"| {p['url']} ({p['ref']}) | {p['kind']} | {fmt(p['score'])} | {miss} |")
    arts = [p for p in res["pages"] if p["kind"] == "article"]
    for p in arts:
        L += ["", f"### {p['url']} ({p['ref']})", "", f"Kind: {p['kind_reason']}. Score {fmt(p['score'])}.", "",
              "| Signal | Value | Evidence |", "|---|---|---|"]
        for k, s in p["signals"].items():
            v = s["value"]
            if k == "freshness":
                v = f"{v} days" if v is not None else "n/a"
            L.append(f"| `{k}` | {fmt(v)} | {evidence_text(s)} |")
    L.append("")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="E-E-A-T signals measured on crawl.jsonl, scored by assets/eeat-weights.json -> eeat.json + eeat.md.")
    ap.add_argument("--crawl", required=True, help="crawl.jsonl of the run")
    ap.add_argument("--out-dir", required=True, help="run folder that receives eeat.json and eeat.md")
    ap.add_argument("--today", help="reference date for the days since the update (default: system date)")
    ap.add_argument("--config", help="project config.json; its eeat object overrides assets/eeat-weights.json")
    args = ap.parse_args(argv)
    try:
        W = load_weights(args.config)
        today = parse_day(args.today)
        res = evaluate(args.crawl, W, today)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    write_json(os.path.join(args.out_dir, "eeat.json"), res)
    write_text(os.path.join(args.out_dir, "eeat.md"), render(res))
    print(f"eeat: site score {fmt(res['site_score'])} (site signals {fmt(res['site_signal_score'])}, "
          f"{res['articles_scored']} article(s), mean {fmt(res['article_mean'])}), {len(res['pages'])} page(s) -> "
          f"{os.path.join(args.out_dir, 'eeat.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
