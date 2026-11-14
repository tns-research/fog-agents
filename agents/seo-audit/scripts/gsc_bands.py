#!/usr/bin/env python3
"""
gsc_bands.py

The one place where seo-audit decides what a decline, a quick win, a CTR gap,
a lost query and a cannibalized query are. Thresholds come from
assets/gsc-bands.json (overridable with the gsc_bands object of the project
config.json); the model never recomputes them. Standard library only.

Reads Search Console exports, in any mix:
  - API JSON: {"rows": [{"keys": [query, page], "clicks", "impressions", "ctr", "position"}]}
    (dimensions from the file's "dimensions" key, else --dimensions, default query,page)
  - UI CSV export (Queries.csv, Pages.csv), English, French, German, Spanish
    or Italian headers, comma or semicolon separated, decimal comma accepted
  - UI compare export (both periods in one file: "Last 28 days Clicks",
    "Previous period Clicks", ...)
  - any CSV with query and page columns (Looker Studio, a GSC tool)

    python3 gsc_bands.py --current data/gsc-current.json --prior data/gsc-prior.json --site https://acme.example --out-dir <run>/
    python3 gsc_bands.py --current data/Queries.csv data/Pages.csv --out-dir <run>/      # compare export: both periods inside
    python3 gsc_bands.py --show-thresholds

Writes <out-dir>/bands.json and <out-dir>/bands.md:
  - queries and pages with their bands (lost, decline, ctr_gap, quick_win),
    the primary band (priority order of the thresholds file), the position
    band (top3, striking, deep), the decline cause (position, demand, ctr)
    and the measurement-artifact flag
  - cannibalization: queries where two URLs or more of the site share the
    impressions (query x page rows only), trailing-slash variants marked
  - totals and limitations (what the inputs could not show)

Exit codes: 0 written, 2 unreadable input or bad arguments.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, aggregate, deep_merge, load_assets_json, load_gsc, load_json,  # noqa: E402
                     median, normalize_url, origin_of, bare_host, host_of, parse_day, write_json, write_text)


def load_thresholds(config_path: Optional[str]) -> Dict[str, Any]:
    t = load_assets_json("gsc-bands.json")
    if config_path:
        t = deep_merge(t, load_json(config_path).get("gsc_bands", {}))
    return t


def pct(new: float, old: float) -> Optional[float]:
    if not old:
        return None
    return round((new - old) * 100.0 / old, 1)


def position_band(pos: Optional[float], bands: List[Dict[str, Any]]) -> Optional[str]:
    if pos is None:
        return None
    for b in bands:
        if pos >= b["min"] and (b["max"] is None or pos <= b["max"]):
            return b["name"]
    return None


def bucket_of(pos: Optional[float], buckets: List[List[float]]) -> Optional[str]:
    if pos is None:
        return None
    for lo, hi in buckets:
        if lo <= pos <= hi:
            return f"{lo:g}-{hi:g}"
    return None


ALPHA2_TO_3 = {
    "fr": "fra", "be": "bel", "ch": "che", "lu": "lux", "ca": "can", "us": "usa", "gb": "gbr", "uk": "gbr",
    "ie": "irl", "de": "deu", "at": "aut", "nl": "nld", "es": "esp", "pt": "prt", "it": "ita", "se": "swe",
    "no": "nor", "dk": "dnk", "fi": "fin", "pl": "pol", "cz": "cze", "ro": "rou", "gr": "grc", "ma": "mar",
    "tn": "tun", "dz": "dza", "sn": "sen", "ci": "civ", "au": "aus", "nz": "nzl", "in": "ind", "br": "bra",
    "mx": "mex", "ar": "arg", "jp": "jpn", "kr": "kor", "cn": "chn", "sg": "sgp", "ae": "are", "il": "isr",
    "za": "zaf", "tr": "tur",
}


def country_code(value: Optional[str]) -> Optional[str]:
    """Search Console country dimension values are lowercase ISO alpha-3."""
    v = (value or "").strip().lower()
    if v in ("", "all"):
        return None
    if len(v) == 3:
        return v
    if v in ALPHA2_TO_3:
        return ALPHA2_TO_3[v]
    try:
        import pycountry  # optional
        c = pycountry.countries.get(alpha_2=v.upper())
        if c:
            return c.alpha_3.lower()
    except ImportError:
        pass
    raise InputError(f"country {value!r}: give the ISO alpha-3 code Search Console uses (e.g. fra)")


class Dataset:
    def __init__(self, current: List[str], prior: List[str], dims: List[str], site: Optional[str],
                 country: Optional[str] = None) -> None:
        self.inputs: List[Dict[str, Any]] = []
        self.cur_rows: List[Dict[str, Any]] = []
        self.prev_rows: List[Dict[str, Any]] = []
        self.site = site
        self.country = country
        for role, paths in (("current", current), ("prior", prior)):
            for p in paths:
                d = load_gsc(p, dims)
                self.inputs.append({"path": os.path.basename(p), "role": role, "format": d["format"],
                                    "dimensions": d["dimensions"], "compare": d["compare"], "rows": len(d["rows"])})
                for r in d["rows"]:
                    if role == "current":
                        self.cur_rows.append(r)
                        if r.get("prev"):
                            self.prev_rows.append({**{k: v for k, v in r.items() if k not in ("cur", "prev")}, "cur": r["prev"]})
                    else:
                        self.prev_rows.append(r)
        self.cur_rows = [r for r in self.cur_rows if self.keep(r)]
        self.prev_rows = [r for r in self.prev_rows if self.keep(r)]

    def keep(self, r: Dict[str, Any]) -> bool:
        if "country" in r:
            if self.country and r["country"].lower() != self.country:
                return False
            del r["country"]
        if not self.site or "page" not in r:
            return True
        return bare_host(host_of(r["page"])) == bare_host(host_of(self.site))

    @staticmethod
    def level(rows: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
        other = "page" if key == "query" else "query"
        own = [r for r in rows if key in r and other not in r]
        if own:
            return aggregate(own, key)
        return aggregate([r for r in rows if key in r], key)

    def pairs(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [r for r in rows if "query" in r and "page" in r]

    @property
    def has_prior(self) -> bool:
        return bool(self.prev_rows)


def evaluate(cur: Dict[str, Dict[str, Any]], prev: Dict[str, Dict[str, Any]], T: Dict[str, Any],
             has_prior: bool, label: str) -> List[Dict[str, Any]]:
    qw, dc, lo, cg, ar = T["quick_win"], T["decline"], T["lost"], T["ctr_gap"], T["artifact"]
    medians: Dict[str, float] = {}
    by_bucket: Dict[str, List[float]] = {}
    for k, m in cur.items():
        b = bucket_of(m["position"], cg["buckets"])
        if b and m["impressions"] >= cg["min_impressions"]:
            by_bucket.setdefault(b, []).append(m["ctr"])
    for b, vals in by_bucket.items():
        if len(vals) >= cg["min_queries_per_bucket"]:
            medians[b] = round(median(vals) or 0.0, 4)
    out = []
    for k in sorted(set(cur) | (set(prev) if has_prior else set())):
        c = cur.get(k)
        p = prev.get(k) if has_prior else None
        bands: List[str] = []
        row: Dict[str, Any] = {label: k, "cur": c, "prev": p}
        delta = None
        if c and p:
            delta = {
                "clicks": c["clicks"] - p["clicks"],
                "clicks_pct": pct(c["clicks"], p["clicks"]),
                "impressions_pct": pct(c["impressions"], p["impressions"]),
                "position": round(c["position"] - p["position"], 2) if c["position"] is not None and p["position"] is not None else None,
            }
        row["delta"] = delta
        row["position_band"] = position_band(c["position"], T["position_bands"]) if c else None
        if c and c["position"] is not None and qw["position_min"] <= c["position"] <= qw["position_max"] \
                and c["impressions"] >= qw["min_impressions"]:
            bands.append("quick_win")
        if p and p["clicks"] >= dc["min_prior_clicks"]:
            change = pct(c["clicks"] if c else 0, p["clicks"])
            if change is not None and change <= dc["max_change_pct"]:
                bands.append("decline")
                cause = "ctr"
                if not c:
                    cause = "gone"
                elif delta and delta["position"] is not None and delta["position"] >= dc["cause_position_worse_by"]:
                    cause = "position"
                elif delta and delta["impressions_pct"] is not None and delta["impressions_pct"] <= dc["cause_impressions_change_pct"]:
                    cause = "demand"
                row["decline_cause"] = cause
        if p and p["position"] is not None and p["position"] <= lo["prior_position_max"] \
                and p["impressions"] >= lo["min_prior_impressions"] \
                and (not c or c["position"] is None or c["position"] > lo["prior_position_max"]):
            bands.append("lost")
        if c:
            b = bucket_of(c["position"], cg["buckets"])
            if b in medians and c["impressions"] >= cg["min_impressions"] and c["ctr"] < cg["ratio"] * medians[b]:
                bands.append("ctr_gap")
                row["ctr_bucket_median"] = medians[b]
        if c and p and delta and c["position"] is not None and p["position"] is not None \
                and c["position"] >= ar["min_position"] and abs(delta["position"] or 0) <= ar["max_abs_position_change"] \
                and delta["impressions_pct"] is not None and delta["impressions_pct"] <= ar["max_impressions_change_pct"]:
            row["artifact_suspect"] = True
        if not bands and not row.get("artifact_suspect"):
            continue
        ordered = [b for b in T["priority"] if b in bands]
        row["bands"] = ordered
        row["primary_band"] = ordered[0] if ordered else None
        pos = c["position"] if c and c["position"] is not None else None
        row["opportunity"] = round(c["impressions"] * max(0.0, (pos or 0) - 3.0), 1) if c else 0.0
        row["click_loss"] = (p["clicks"] - (c["clicks"] if c else 0)) if p else 0
        out.append(row)
    rank = {b: i for i, b in enumerate(T["priority"])}
    out.sort(key=lambda r: (rank.get(r["primary_band"], 99),
                            -(r["click_loss"] if r["primary_band"] in ("lost", "decline") else r["opportunity"]),
                            r[label]))
    return out, medians


def cannibalization(pairs: List[Dict[str, Any]], T: Dict[str, Any]) -> List[Dict[str, Any]]:
    C = T["cannibalization"]
    per_q: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for r in pairs:
        q, pg = r["query"], normalize_url(r["page"])
        m = r["cur"]
        a = per_q.setdefault(q, {}).setdefault(pg, {"clicks": 0, "impressions": 0, "pos_w": 0.0, "w": 0})
        a["clicks"] += m["clicks"]
        a["impressions"] += m["impressions"]
        if m.get("position") is not None:
            w = m["impressions"] or 1
            a["pos_w"] += m["position"] * w
            a["w"] += w
    out = []
    for q, pages in per_q.items():
        total = sum(v["impressions"] for v in pages.values())
        if not total:
            continue
        keep = []
        for pg, v in pages.items():
            share = v["impressions"] / total
            if v["impressions"] >= C["min_impressions_per_url"] and share >= C["min_share"]:
                keep.append({"page": pg, "clicks": v["clicks"], "impressions": v["impressions"],
                             "position": round(v["pos_w"] / v["w"], 2) if v["w"] else None, "share": round(share, 3)})
        if len(keep) < 2:
            continue
        keep.sort(key=lambda x: (-x["clicks"], -x["impressions"], x["page"]))
        stripped = {x["page"].rstrip("/") for x in keep}
        out.append({"query": q, "impressions": total, "pages": keep, "survivor_by_clicks": keep[0]["page"],
                    "slash_variants": len(stripped) < len(keep)})
    out.sort(key=lambda x: (-x["impressions"], x["query"]))
    return out


def totals(cur: Dict[str, Dict[str, Any]], prev: Dict[str, Dict[str, Any]], has_prior: bool) -> Dict[str, Any]:
    def s(d):
        return {"clicks": sum(v["clicks"] for v in d.values()), "impressions": sum(v["impressions"] for v in d.values())}
    t = {"current": s(cur), "prior": s(prev) if has_prior else None}
    if has_prior:
        t["clicks_pct"] = pct(t["current"]["clicks"], t["prior"]["clicks"])
        t["impressions_pct"] = pct(t["current"]["impressions"], t["prior"]["impressions"])
    return t


def fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def render_md(res: Dict[str, Any], top: int) -> str:
    L = ["# Search Console bands", "",
         f"Generated by `gsc_bands.py` on {res['generated_on']} from {', '.join(i['path'] for i in res['inputs'])}. "
         "Thresholds: `assets/gsc-bands.json` (applied values in `bands.json`).", ""]
    t = res["totals"]
    L.append(f"Exported rows, current period: {t['current']['clicks']} clicks, {t['current']['impressions']} impressions.")
    if t.get("prior"):
        L.append(f"Prior period: {t['prior']['clicks']} clicks, {t['prior']['impressions']} impressions "
                 f"(clicks {fmt(t['clicks_pct'])} %, impressions {fmt(t['impressions_pct'])} %).")
    L.append("")
    c = res["counts"]
    L.append("| Band | Queries | Pages |")
    L.append("|------|--------:|------:|")
    for b in ("lost", "decline", "ctr_gap", "quick_win"):
        L.append(f"| {b} | {c['queries'].get(b, 0)} | {c['pages'].get(b, 0)} |")
    L.append(f"| cannibalized queries | {c['cannibalization']} | |")
    L.append(f"| artifact suspects | {c['queries'].get('artifact_suspect', 0)} | {c['pages'].get('artifact_suspect', 0)} |")
    L.append("")
    for level, label in (("pages", "page"), ("queries", "query")):
        rows = res[level]
        L.append(f"## {level.capitalize()} (top {top} per primary band)")
        L.append("")
        if not rows:
            L.append("None.")
            L.append("")
            continue
        L.append(f"| {label.capitalize()} | Primary | Bands | Pos now | Pos prior | Clicks now | Clicks prior | Impr now | Δ clicks % | Cause | Artifact? |")
        L.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|---|")
        seen: Dict[str, int] = {}
        for r in rows:
            pb = r["primary_band"] or "artifact"
            seen[pb] = seen.get(pb, 0) + 1
            if seen[pb] > top:
                continue
            cur, prev, d = r["cur"] or {}, r["prev"] or {}, r["delta"] or {}
            L.append(f"| `{r[label]}` | {pb} | {', '.join(r['bands'])} | {fmt(cur.get('position'))} | {fmt(prev.get('position'))} | "
                     f"{fmt(cur.get('clicks'))} | {fmt(prev.get('clicks'))} | {fmt(cur.get('impressions'))} | {fmt(d.get('clicks_pct'))} | "
                     f"{r.get('decline_cause', '')} | {'yes' if r.get('artifact_suspect') else ''} |")
        L.append("")
    L.append("## Cannibalization")
    L.append("")
    if not res["cannibalization"]:
        L.append("None found." if res["has_pairs"] else "Not computable: no query x page rows in the inputs.")
    for x in res["cannibalization"][:top]:
        L.append(f"- `{x['query']}` ({x['impressions']} impressions){', trailing-slash variants' if x['slash_variants'] else ''}: "
                 + "; ".join(f"{p['page']} (pos {fmt(p['position'])}, {p['clicks']} clicks, {round(p['share'] * 100)} % of impressions)" for p in x["pages"]))
    L.append("")
    if res["limitations"]:
        L.append("## Limitations")
        L.append("")
        for lim in res["limitations"]:
            L.append(f"- {lim}")
        L.append("")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Bands, declines, quick wins and cannibalization from Search Console exports.")
    ap.add_argument("--current", nargs="+", default=[], help="current-period exports (JSON or CSV; compare exports carry both periods)")
    ap.add_argument("--prior", nargs="+", default=[], help="prior-period exports")
    ap.add_argument("--dimensions", default="query,page", help="key order of API JSON rows without a dimensions field")
    ap.add_argument("--site", help="keep only pages of this site (www and bare host both kept)")
    ap.add_argument("--country", help="with a country dimension in the rows: keep this country only (ISO alpha-2 or alpha-3)")
    ap.add_argument("--config", help="project config.json (gsc_bands object overrides the thresholds)")
    ap.add_argument("--out-dir", help="writes bands.json and bands.md here")
    ap.add_argument("--top", type=int, default=10, help="rows per band in bands.md (default 10)")
    ap.add_argument("--today", help="date written in the output (YYYY-MM-DD, default today)")
    ap.add_argument("--show-thresholds", action="store_true", help="print the applied thresholds and exit")
    args = ap.parse_args(argv)
    try:
        T = load_thresholds(args.config)
        if args.show_thresholds:
            import json
            print(json.dumps({k: v for k, v in T.items() if not k.startswith("_")}, indent=2))
            return 0
        if not args.current or not args.out_dir:
            ap.error("--current and --out-dir are required")
        ds = Dataset(args.current, args.prior, [d.strip() for d in args.dimensions.split(",")], args.site,
                     country_code(args.country))
        today = parse_day(args.today).isoformat()
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    limitations: List[str] = []
    q_cur, q_prev = Dataset.level(ds.cur_rows, "query"), Dataset.level(ds.prev_rows, "query")
    p_cur, p_prev = Dataset.level(ds.cur_rows, "page"), Dataset.level(ds.prev_rows, "page")
    queries, q_medians = evaluate(q_cur, q_prev, T, ds.has_prior, "query")
    pages, p_medians = evaluate(p_cur, p_prev, T, ds.has_prior, "page")
    pairs = ds.pairs(ds.cur_rows)
    top_page: Dict[str, Tuple[int, str]] = {}
    top_query: Dict[str, Tuple[int, str]] = {}
    for r in pairs:
        q, pg, imp = r["query"], normalize_url(r["page"]), r["cur"]["impressions"]
        if imp > top_page.get(q, (-1, ""))[0]:
            top_page[q] = (imp, pg)
        if imp > top_query.get(pg, (-1, ""))[0]:
            top_query[pg] = (imp, q)
    for r in queries:
        r["top_page"] = top_page.get(r["query"], (0, None))[1]
    for r in pages:
        r["top_query"] = top_query.get(r["page"], (0, None))[1]
    cann = cannibalization(pairs, T) if pairs else []

    if not ds.has_prior:
        limitations.append("No prior period: decline, lost and artifact checks not computed (quick wins and CTR gaps only).")
    if not pairs:
        limitations.append("No query x page rows: cannibalization not computed, and a query's page comes from the crawl or the SERP, not from Search Console.")
    if not q_cur:
        limitations.append("No query rows: query bands empty.")
    if not p_cur:
        limitations.append("No page rows: page bands empty.")
    if not q_medians and q_cur:
        limitations.append("No position bucket had enough queries for a site CTR median: CTR gaps not computed.")
    if any(i["format"] == "csv" and not i["compare"] and i["rows"] >= 1000 for i in ds.inputs):
        limitations.append("A CSV export holds 1000 rows or more: the Search Console UI caps exports at 1000 rows per table, long-tail rows are missing.")
    limitations.append("Totals are sums of exported rows, not the Search Console totals (anonymized queries never appear in exports).")

    if p_cur and (p_prev or not ds.has_prior):
        tot = totals(p_cur, p_prev, ds.has_prior)
    else:
        tot = totals(q_cur or p_cur, q_prev if q_cur else p_prev, ds.has_prior and bool(q_prev if q_cur else p_prev))
    if ds.has_prior and p_cur and not p_prev:
        limitations.append("Pages have no prior period in the inputs: page declines and lost pages not computed (queries only).")
    if ds.has_prior and q_cur and not q_prev:
        limitations.append("Queries have no prior period in the inputs: query declines and lost queries not computed (pages only).")
    counts = {"queries": {}, "pages": {}, "cannibalization": len(cann)}
    for level, rows in (("queries", queries), ("pages", pages)):
        for r in rows:
            for b in r["bands"]:
                counts[level][b] = counts[level].get(b, 0) + 1
            if r.get("artifact_suspect"):
                counts[level]["artifact_suspect"] = counts[level].get("artifact_suspect", 0) + 1
    res = {
        "schema_version": "1.0",
        "generated_by": "gsc_bands.py",
        "generated_on": today,
        "inputs": ds.inputs,
        "site": origin_of(args.site) if args.site else None,
        "thresholds": {k: v for k, v in T.items() if not k.startswith("_")},
        "has_prior": ds.has_prior,
        "has_pairs": bool(pairs),
        "ctr_medians": {"queries": q_medians, "pages": p_medians},
        "totals": tot,
        "counts": counts,
        "pages": pages,
        "queries": queries,
        "cannibalization": cann,
        "top_query_by_page": {pg: q for pg, (_, q) in sorted(top_query.items())},
        "limitations": limitations,
    }
    write_json(os.path.join(args.out_dir, "bands.json"), res)
    write_text(os.path.join(args.out_dir, "bands.md"), render_md(res, args.top))
    print(f"bands: {len(pages)} pages and {len(queries)} queries in a band, {len(cann)} cannibalized queries -> "
          f"{os.path.join(args.out_dir, 'bands.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
