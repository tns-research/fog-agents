#!/usr/bin/env python3
"""
write_briefs.py

Turns bands.json (Search Console) and crawl.jsonl (the served pages) into
refresh briefs a writer can execute without the audit conversation: one
folder per page with brief.md (format: assets/refresh-brief-template.md) and
expect.json (what verify_served.py checks once the change is live), plus an
index sorted by priority. Standard library only, deterministic.

    python3 write_briefs.py --bands <run>/bands.json --crawl <run>/crawl.jsonl \
        --out-dir <project>/seo-audit/briefs --date 2026-10-12 [--state <project>/seo-audit/state.json] [--top 8]

Candidates, in this order:
  1. cannibalized queries: one merge brief per group, on the URL with the most
     clicks (a trailing-slash pair becomes a technical merge: 301 the variant)
  2. pages with a primary band (lost, decline, ctr_gap, quick_win)
Suggested action per page (the SERP drift check of the skill confirms or
changes it): ctr_gap -> refine; quick_win at position 10 or better -> refine,
11 to 20 -> expand; decline from position -> update, from CTR -> refine, from
demand -> update after checking the query trend; lost -> update; merge for
cannibalization. Effort: update 1, refine 1, expand 2, retarget 2, merge 3.
Priority = score / effort, score = impressions x (position - 3), x1.3 when
the page lost clicks (recovering equity is cheaper than new ranking).

A page missing from the crawl, or not 200 and indexable there, gets no
content brief: it is listed as blocked with the crawl line to fix first.

Exit codes: 0 briefs written, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (ASSETS, InputError, load_json, normalize_url, parse_day,  # noqa: E402
                     path_of, read_jsonl, slugify, write_json, write_text)

EFFORT = {"update": 1, "refine": 1, "expand": 2, "retarget": 2, "merge": 3}
BLOCKING = {"status-4xx", "status-5xx", "noindex", "canonical-home", "canonical-other", "canonical-other-host",
            "canonical-multiple", "jsonld-invalid", "slash-duplicate", "blocked-by-robots", "thin-raw-html",
            "sitemap-noindex", "canonical-target-not-200"}


def suggest(row: Dict[str, Any]) -> Tuple[str, str]:
    pb = row["primary_band"]
    pos = (row.get("cur") or {}).get("position")
    if pb == "ctr_gap":
        return "refine", f"Rule: CTR under the site median of its position bucket ({row.get('ctr_bucket_median')}) at position {pos}."
    if pb == "quick_win":
        if pos is not None and pos <= 10:
            return "refine", f"Rule: quick win at position {pos} (10 or better): title, description, internal links, schema."
        return "expand", f"Rule: quick win at position {pos} (11 to 20): the page is thinner than what ranks."
    if pb == "decline":
        cause = row.get("decline_cause")
        if cause == "ctr":
            return "refine", "Rule: decline with stable position and impressions: the snippet lost clicks."
        if cause == "demand":
            return "update", "Rule: decline driven by fewer impressions at a stable position: check the query trend before changing the page."
        return "update", f"Rule: decline with position loss ({(row.get('delta') or {}).get('position')} places): facts and dates first, retarget if the SERP format shifted."
    if pb == "lost":
        return "update", "Rule: fell out of the top 20: update, or retarget if the SERP drift check shows a format shift."
    return "refine", "Rule: default."


def score_of(row: Dict[str, Any]) -> float:
    cur = row.get("cur") or {}
    pos = cur.get("position")
    imp = cur.get("impressions") or (row.get("prev") or {}).get("impressions") or 0
    base = imp * max(0.0, (pos if pos is not None else 20.0) - 3.0)
    if "decline" in row.get("bands", []) or "lost" in row.get("bands", []):
        base *= 1.3
    return round(base, 1)


def crawl_index(path: str) -> Dict[str, Any]:
    idx = {}
    for n, rec in read_jsonl(path):
        idx[rec["url"]] = (n, rec)
    return idx


def tick(v: Optional[str]) -> str:
    v = " ".join((v or "").split())
    return f"`{v}`" if v else "`(missing)`"


def current_state(url: str, crawl: Dict[str, Any], name: str) -> Tuple[str, Optional[Dict[str, Any]], List[str]]:
    hit = crawl.get(url)
    if not hit:
        return (f"Not in `{name}`: crawl this URL before writing anything about its current state.", None, ["not-crawled"])
    n, r = hit
    lines = [
        f"- **Current title:** {tick(r.get('title'))} ({name}:{n})",
        f"- **Current meta description:** {tick(r.get('meta_description'))} ({name}:{n})",
        f"- **Current H1:** {tick((r.get('h1') or [None])[0])} ({name}:{n})",
        f"- Status {r.get('status')}, canonical {r.get('canonical') or 'none'} ({r.get('canonical_status')}), "
        f"indexable {'yes' if r.get('indexable') else 'no'}, {r.get('word_count')} words in the raw HTML, "
        f"JSON-LD {', '.join(r.get('jsonld_types') or []) or 'none'}, {r.get('inlinks')} internal links in, depth {r.get('depth')}.",
    ]
    blockers = [c for c in r.get("issues", []) if c in BLOCKING]
    if r.get("status") != 200 or r.get("redirect_chain"):
        blockers.insert(0, f"status-{r.get('status')}" + (" after redirect" if r.get("redirect_chain") else ""))
    return "\n".join(lines), r, blockers


def gsc_block(row: Dict[str, Any]) -> str:
    cur, prev, d = row.get("cur") or {}, row.get("prev") or {}, row.get("delta") or {}
    s = (f"- Current period: {cur.get('clicks', 0)} clicks, {cur.get('impressions', 0)} impressions, "
         f"position {cur.get('position')}, CTR {cur.get('ctr')}.")
    if prev:
        s += (f"\n- Prior period: {prev.get('clicks')} clicks, {prev.get('impressions')} impressions, position {prev.get('position')} "
              f"(clicks {d.get('clicks_pct')} %, position change {d.get('position')}).")
    if row.get("decline_cause"):
        s += f"\n- Decline cause: {row['decline_cause']}."
    if row.get("artifact_suspect"):
        s += "\n- Artifact suspect: deep position, stable rank, falling impressions. Check for a measurement change before acting."
    return s


def render(template: str, values: Dict[str, Any]) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Refresh briefs (brief.md + expect.json per page) from bands.json and crawl.jsonl.")
    ap.add_argument("--bands", required=True)
    ap.add_argument("--crawl", required=True)
    ap.add_argument("--out-dir", required=True, help="briefs folder, usually <project>/seo-audit/briefs")
    ap.add_argument("--date", help="brief date (YYYY-MM-DD, default today)")
    ap.add_argument("--top", type=int, default=8, help="briefs written (default 8, merges included)")
    ap.add_argument("--state", help="state.json: register each brief as open")
    args = ap.parse_args(argv)
    try:
        bands = load_json(args.bands)
        crawl = crawl_index(args.crawl)
        template = open(os.path.join(ASSETS, "refresh-brief-template.md"), encoding="utf-8").read()
        day = parse_day(args.date)
    except (InputError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    name = os.path.basename(args.crawl)
    stamp = day.strftime("%Y%m%d")
    pages = {normalize_url(r["page"]): r for r in bands.get("pages", [])}
    candidates: List[Dict[str, Any]] = []
    merged_away = set()

    top_query = bands.get("top_query_by_page", {})
    for g in bands.get("cannibalization", []):
        survivor = g["survivor_by_clicks"]
        if g.get("slash_variants"):
            hit = crawl.get(survivor)
            if hit and hit[1].get("canonical") and hit[1]["canonical"] in {p["page"] for p in g["pages"]}:
                survivor = hit[1]["canonical"]
        # Merge only a page whose main query is this one (or a slash variant of the survivor);
        # a page that ranks here by overlap keeps its own intent and only links to the survivor.
        losers = [p["page"] for p in g["pages"] if p["page"] != survivor
                  and (p["page"].rstrip("/") == survivor.rstrip("/") or top_query.get(p["page"]) == g["query"])]
        overlap = [p["page"] for p in g["pages"] if p["page"] != survivor and p["page"] not in losers]
        if not losers:
            continue
        merged_away.update(losers)
        row = pages.get(survivor) or {"page": survivor, "cur": next(p for p in g["pages"] if p["page"] == survivor),
                                      "prev": None, "delta": None, "bands": [], "primary_band": None}
        technical = all(p.rstrip("/") == survivor.rstrip("/") for p in losers)
        score = sum(p["impressions"] * max(0.0, (p["position"] or 20.0) - 3.0) for p in g["pages"]) * 1.3
        candidates.append({
            "row": row, "url": survivor, "action": "merge",
            "rule": (f"Rule: query `{g['query']}` is split across {len(g['pages'])} URLs of the site"
                     + (" (trailing-slash variants: a technical merge, 301 the variant)." if technical else ".")),
            "merge": {"query": g["query"], "from": losers, "overlap": overlap, "pages": g["pages"], "technical": technical},
            "score": round(score, 1),
        })
    for url, row in pages.items():
        if url in merged_away or any(c["url"] == url for c in candidates) or not row.get("primary_band"):
            continue
        action, rule = suggest(row)
        candidates.append({"row": row, "url": url, "action": action, "rule": rule, "merge": None, "score": score_of(row)})
    for c in candidates:
        c["effort"] = EFFORT[c["action"]]
        c["priority"] = round(c["score"] / c["effort"], 1)
    candidates.sort(key=lambda c: (-c["priority"], c["url"]))

    written, blocked = [], []
    st = None
    if args.state:
        import seo_state
        st = seo_state.load_state(args.state)
    for c in candidates:
        if len(written) >= args.top:
            break
        url = c["url"]
        state_md, rec, blockers = current_state(url, crawl, name)
        if rec is None or rec.get("status") != 200 or rec.get("redirect_chain") or not rec.get("indexable"):
            blocked.append({"url": url, "action": c["action"], "reason": ", ".join(blockers) or "not 200 and indexable",
                            "line": crawl[url][0] if url in crawl else None})
            continue
        bid = f"{stamp}-{slugify(path_of(url))}"
        folder = os.path.join(args.out_dir, bid)
        row = c["row"]
        merge_md = ""
        if c["merge"]:
            m = c["merge"]
            items = []
            for p in m["pages"]:
                hit = crawl.get(p["page"])
                ref = f"{name}:{hit[0]}" if hit else f"not in {name}"
                items.append(f"- {p['page']}: position {p['position']}, {p['clicks']} clicks, {round(p['share'] * 100)} % of the query's impressions"
                             f" ({ref}{', canonical ' + str(hit[1].get('canonical')) if hit else ''})")
            merge_md = (f"## Merge plan for `{m['query']}`\n\nSurviving URL: {url}. Merged: {', '.join(m['from'])}.\n\n" + "\n".join(items) + "\n\n"
                        + ("Technical merge: 301 the variant to the surviving URL and link only to it; no content change.\n"
                           if m["technical"] else
                           "Move the unique sections of the merged pages to the surviving URL, then 301 each merged URL to it.\n")
                        + (f"Not merged (their main query is another one): {', '.join(m['overlap'])}. "
                           "Keep them, add one link from each to the surviving URL with the query as anchor, "
                           "and avoid the query in their title.\n" if m["overlap"] else ""))
        expect = {
            "schema_version": "1.0", "id": bid, "url": url, "action": c["action"],
            "title": None,
            "_title": "Put the final published title here before verifying; null only requires a non-empty title.",
            "canonical": url, "og_url": url,
            "hreflang": rec.get("hreflang") or [],
            "jsonld_types": rec.get("jsonld_types") or [],
            "indexable": True, "in_sitemap": True,
            "redirects": c["merge"]["from"] if c["merge"] else [],
        }
        values = {
            "id": bid, "url": url, "action": c["action"], "effort": c["effort"], "action_rule": c["rule"],
            "bands": ", ".join(row.get("bands") or ["cannibalization"]), "priority": c["priority"], "score": c["score"],
            "target_query": (c["merge"]["query"] if c["merge"] else row.get("top_query")) or "(no query x page rows: pick it from bands.md)",
            "current_state": state_md,
            "blockers": "\n".join(f"- `{b}` ({name}:{crawl[url][0]})" for b in blockers) or "None in the crawl.",
            "gsc": gsc_block(row), "merge": merge_md.rstrip(),
            "word_count": rec.get("word_count"), "jsonld_types": ", ".join(rec.get("jsonld_types") or []) or "none",
            "expect_path": f"{bid}/expect.json",
        }
        write_text(os.path.join(folder, "brief.md"), render(template, values).replace("\n\n\n\n", "\n\n").replace("\n\n\n", "\n\n"))
        write_json(os.path.join(folder, "expect.json"), expect)
        written.append({"id": bid, "url": url, "action": c["action"], "priority": c["priority"], "line": crawl[url][0]})
        if st is not None:
            import argparse as _ap
            import seo_state
            ns = _ap.Namespace(state=args.state, id=bid, url=url, action=c["action"], brief=os.path.join(folder, "brief.md"),
                               expect=os.path.join(folder, "expect.json"), lane=row.get("primary_band") or "cannibalization",
                               date=day.isoformat(), config=None)
            try:
                seo_state.cmd_open_brief(ns, st)
            except seo_state.Refused as e:
                print(f"state: {e}", file=sys.stderr)
    if st is not None:
        import seo_state
        seo_state.save_state(args.state, st)

    L = [f"# Refresh queue ({day.isoformat()})", "",
         f"From `{os.path.basename(args.bands)}` and `{name}`. Suggested actions are confirmed or changed by the SERP drift check of each brief.", "",
         "| # | Brief | URL | Action | Priority | Crawl line |", "|---|---|---|---|---:|---|"]
    for i, w in enumerate(written, 1):
        L.append(f"| {i} | [{w['id']}]({w['id']}/brief.md) | {w['url']} | {w['action']} | {w['priority']} | {name}:{w['line']} |")
    if blocked:
        L += ["", "## Blocked: fix the page before any content change", ""]
        for b in blocked:
            L.append(f"- {b['url']} ({b['action']} suggested): {b['reason']}" + (f" ({name}:{b['line']})" if b["line"] else f" (not in {name})"))
    write_text(os.path.join(args.out_dir, f"index-{stamp}.md"), "\n".join(L) + "\n")
    print(f"briefs: {len(written)} written, {len(blocked)} blocked -> {os.path.join(args.out_dir, f'index-{stamp}.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
