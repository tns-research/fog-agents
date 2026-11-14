#!/usr/bin/env python3
"""perf.py: read Meta ads results, rank the ads, diagnose, write the next batch input.

  python3 scripts/perf.py <export.csv | insights.json> [--previous <file>]
      [--target-cpa 20] [--min-spend 20] [--conversion purchase|lead|registration|results]
      [--config config.json] [--out ads-performance-YYYYMMDD.json] [--md report.md]

Input, any of:
  - an Ads Manager export (Reports > Export table data > .csv), level Ad, with
    the standard columns: "Ad name", "Ad set name", "Campaign name",
    "Reporting starts", "Reporting ends", "Amount spent (<CUR>)",
    "Impressions", "Link clicks", "Landing page views", "Purchases" (or
    "Leads", "Registrations completed", "Results"), "3-second video plays".
    English column names; comma or semicolon separated; 1,234.5 or 1 234,5.
  - a Marketing API insights JSON (GET /<account>/insights?level=ad), the
    raw {"data": [...]} or a list: ad_name, adset_name, campaign_name, spend,
    impressions, inline_link_clicks, actions[{action_type, value}].
Conversions are read from ONE source, first found in a priority list, never
summed (pixel and omni counts of the same purchase would double).

Rules (all explicit, all overridable in config.json "perf" or by flag; they
are decision rules, not market benchmarks):
  target_cpa       from config or --target-cpa; else the account median CPA
                   of the ads with conversions (said in the output)
  min_spend        an ad is judged only past this spend (default 1 x target CPA)
  winner           >= 3 conversions and CPA <= target CPA
  loser            0 conversions after 2 x target CPA spent, or
                   CPA >= 1.5 x target CPA after 3 x target CPA spent
  inconclusive     everything else past min_spend; insufficient_data below it
  diagnosis        against the account's own medians:
    creative       CTR < 0.75 x median CTR (>= 1000 impressions), or hook
                   rate (3-second plays / impressions) < 0.75 x median
    post_click     CTR holds but conversion rate (conversions / link clicks)
                   < 0.75 x median (>= 50 clicks), or landing page views /
                   link clicks < 0.70 (the page loses people before it loads)
    both, healthy, insufficient_data
  account          with --previous: CTR stable (> -15 %) and conversion rate
                   down > 25 % = post_click (fix the page, the offer, the
                   checkout or retargeting before producing more creatives);
                   CTR down > 15 % = creative fatigue; CPM up > 25 % with
                   CTR and CVR stable = auction or audience pressure.
  noise            under 15 conversions in the period, every verdict carries
                   a small-sample warning.

Ad names that follow the agent's convention
(<project>_<NN>_<stage>_<angle>_<style>_<ratio>, plus _t-<variable> for a
one-variable test from scripts/recipe_variants.py) are split back, so the
output aggregates spend, conversions, CPA and CTR per angle, style, stage,
ratio and tested variable, and the next batch knows which angle to extend.

Output: ads-performance-YYYYMMDD.json (ads, winners, losers, inconclusive,
aggregates, account diagnosis, next_batch) and a markdown summary (--md, or
stdout). Exit 0 on success, 3 on unreadable input. No API call: fetching
the export or the insights JSON is the founder's (or a provider's) job.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adspec  # noqa: E402

DEFAULTS = {
    "target_cpa": None, "min_spend": None, "min_conversions": 3, "kill_spend_multiple": 2.0,
    "loser_cpa_multiple": 1.5, "loser_spend_multiple": 3.0, "min_impressions_ctr": 1000, "min_clicks_cvr": 50,
    "weak_ratio": 0.75, "min_lpv_rate": 0.70, "noise_conversions": 15, "extend_share": 0.6,
}

ALIASES = {
    "ad_name": ["ad name", "ad_name"],
    "ad_set": ["ad set name", "adset_name", "ad_set_name"],
    "campaign": ["campaign name", "campaign_name"],
    "start": ["reporting starts", "date_start"],
    "end": ["reporting ends", "date_stop"],
    "spend": ["amount spent", "spend"],
    "impressions": ["impressions"],
    "reach": ["reach"],
    "clicks": ["link clicks", "inline_link_clicks"],
    "lpv": ["landing page views", "website landing page views"],
    "plays3s": ["3-second video plays", "video_3s_plays"],
    "purchase": ["purchases", "website purchases"],
    "lead": ["leads", "website leads"],
    "registration": ["registrations completed", "website registrations completed"],
    "results": ["results"],
}
# Insights JSON: action types per conversion kind, in priority order. The
# first one present is used; they are never added up.
ACTION_TYPES = {
    "purchase": ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase", "onsite_web_purchase"],
    "lead": ["lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"],
    "registration": ["complete_registration", "offsite_conversion.fb_pixel_complete_registration"],
    "lpv": ["landing_page_view", "omni_landing_page_view"],
    "plays3s": ["video_view"],
    "clicks": ["link_click"],
}


def num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if s in ("", "-", "--"):
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", s)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) != 3 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def read_csv(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(raw.splitlines()[0], delimiters=",;\t")
    rows = list(csv.DictReader(io.StringIO(raw), dialect=dialect))
    if not rows:
        return []
    cols = {c: c.lower().strip() for c in rows[0].keys() if c}
    pick: Dict[str, Optional[str]] = {}
    currency = None
    for key, names in ALIASES.items():
        pick[key] = None
        for c, lc in cols.items():
            base = re.sub(r"\s*\([^)]*\)\s*$", "", lc)
            if base in names:
                pick[key] = c
                if key == "spend":
                    m = re.search(r"\(([A-Z]{3})\)", c)
                    currency = m.group(1) if m else None
                break
    out = []
    for r in rows:
        if not (r.get(pick["ad_name"] or "") or "").strip():
            continue  # total rows
        rec = {k: (r.get(c) if c else None) for k, c in pick.items()}
        rec["currency"] = currency
        out.append(rec)
    return out


def read_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("data", data) if isinstance(data, dict) else data
    out = []
    for it in items:
        acts = {a.get("action_type"): a.get("value") for a in it.get("actions") or []}
        rec: Dict[str, Any] = {"ad_name": it.get("ad_name"), "ad_set": it.get("adset_name"), "campaign": it.get("campaign_name"),
                               "start": it.get("date_start"), "end": it.get("date_stop"), "spend": it.get("spend"),
                               "impressions": it.get("impressions"), "reach": it.get("reach"),
                               "clicks": it.get("inline_link_clicks"), "currency": it.get("account_currency")}
        for kind, types in ACTION_TYPES.items():
            for t in types:
                if t in acts:
                    if kind not in rec or rec.get(kind) in (None, ""):
                        rec[kind] = acts[t]
                    break
        out.append(rec)
    return out


def load(path: Path) -> List[Dict[str, Any]]:
    return read_json(path) if path.suffix.lower() == ".json" else read_csv(path)


def pick_conversion(rows: List[Dict[str, Any]], wanted: Optional[str]) -> str:
    if wanted:
        return wanted
    for k in ("purchase", "lead", "registration", "results"):
        if any(num(r.get(k)) > 0 for r in rows):
            return k
    return "results"


def metrics(r: Dict[str, Any], conv_key: str) -> Dict[str, Any]:
    spend, imp, clk = num(r.get("spend")), num(r.get("impressions")), num(r.get("clicks"))
    conv, lpv, p3 = num(r.get(conv_key)), num(r.get("lpv")), num(r.get("plays3s"))
    m = {"ad_name": (r.get("ad_name") or "").strip(), "ad_set": r.get("ad_set"), "campaign": r.get("campaign"),
         "spend": round(spend, 2), "impressions": int(imp), "clicks": int(clk), "conversions": conv, "landing_page_views": int(lpv),
         "ctr": clk / imp if imp else None, "cpm": spend / imp * 1000 if imp else None, "cpc": spend / clk if clk else None,
         "cvr": conv / clk if clk else None, "cpa": spend / conv if conv else None,
         "lpv_rate": lpv / clk if clk and lpv else None, "hook_rate": p3 / imp if imp and p3 else None}
    parsed = adspec.parse_ad_name(m["ad_name"])
    m["parsed"] = parsed
    return m


def median(vals: List[float]) -> Optional[float]:
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def totals(ms: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = sum(m["spend"] for m in ms)
    i = sum(m["impressions"] for m in ms)
    c = sum(m["clicks"] for m in ms)
    v = sum(m["conversions"] for m in ms)
    return {"spend": round(s, 2), "impressions": i, "clicks": c, "conversions": v,
            "ctr": c / i if i else None, "cvr": v / c if c else None, "cpa": s / v if v else None, "cpm": s / i * 1000 if i else None}


def change(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return (a - b) / b if a is not None and b else None


def analyse(rows: List[Dict[str, Any]], prev_rows: Optional[List[Dict[str, Any]]], rules: Dict[str, Any], conv_wanted: Optional[str]) -> Dict[str, Any]:
    conv_key = pick_conversion(rows, conv_wanted)
    ms = [metrics(r, conv_key) for r in rows]
    notes: List[str] = []
    target = rules.get("target_cpa")
    if not target:
        target = median([m["cpa"] for m in ms if m["cpa"]])
        notes.append("No target CPA given: the account median CPA of the ads with conversions is the target." if target else
                     "No conversion in the period: no CPA target, every ad is judged on delivery only.")
    min_spend = rules.get("min_spend") or (target or 0)
    med_ctr = median([m["ctr"] for m in ms if m["impressions"] >= rules["min_impressions_ctr"]])
    med_cvr = median([m["cvr"] for m in ms if m["clicks"] >= rules["min_clicks_cvr"]])
    med_hook = median([m["hook_rate"] for m in ms if m["hook_rate"]])
    weak = rules["weak_ratio"]
    for m in ms:
        # Verdict.
        if m["spend"] < min_spend:
            v, why = "insufficient_data", f"spend {m['spend']} under the {round(min_spend, 2)} minimum"
        elif target and m["conversions"] >= rules["min_conversions"] and m["cpa"] <= target:
            v, why = "winner", f"CPA {m['cpa']:.2f} <= target {target:.2f} on {m['conversions']:g} conversions"
        elif target and m["conversions"] == 0 and m["spend"] >= rules["kill_spend_multiple"] * target:
            v, why = "loser", f"0 conversions after {m['spend']} spent (>= {rules['kill_spend_multiple']:g} x target CPA)"
        elif target and m["cpa"] and m["cpa"] >= rules["loser_cpa_multiple"] * target and m["spend"] >= rules["loser_spend_multiple"] * target:
            v, why = "loser", f"CPA {m['cpa']:.2f} >= {rules['loser_cpa_multiple']:g} x target after {m['spend']} spent"
        else:
            v, why = "inconclusive", "between the winner and loser rules"
        m["verdict"], m["why"] = v, why
        # Diagnosis.
        creative = (m["impressions"] >= rules["min_impressions_ctr"] and med_ctr and m["ctr"] is not None and m["ctr"] < weak * med_ctr) or \
                   (m["hook_rate"] is not None and med_hook and m["hook_rate"] < weak * med_hook)
        post = (m["clicks"] >= rules["min_clicks_cvr"] and med_cvr and m["cvr"] is not None and m["cvr"] < weak * med_cvr) or \
               (m["lpv_rate"] is not None and m["clicks"] >= rules["min_clicks_cvr"] and m["lpv_rate"] < rules["min_lpv_rate"])
        if m["impressions"] < rules["min_impressions_ctr"]:
            d = "insufficient_data"
        elif creative and post:
            d = "both"
        elif creative:
            d = "creative"
        elif post:
            d = "post_click"
        else:
            d = "healthy"
        m["diagnosis"] = d
        reasons = []
        if creative:
            reasons.append(f"CTR {m['ctr']:.2%} vs account median {med_ctr:.2%}" if m["ctr"] is not None and med_ctr else "low hook rate")
        if post:
            if m["lpv_rate"] is not None and m["lpv_rate"] < rules["min_lpv_rate"]:
                reasons.append(f"only {m['lpv_rate']:.0%} of link clicks reach the page")
            if m["cvr"] is not None and med_cvr and m["cvr"] < weak * med_cvr:
                reasons.append(f"conversion rate {m['cvr']:.2%} vs account median {med_cvr:.2%}")
        m["diagnosis_why"] = "; ".join(reasons)
    cur = totals(ms)
    account: Dict[str, Any] = {"current": cur}
    if prev_rows is not None:
        prev = totals([metrics(r, conv_key) for r in prev_rows])
        account["previous"] = prev
        d_ctr, d_cvr, d_cpm = change(cur["ctr"], prev["ctr"]), change(cur["cvr"], prev["cvr"]), change(cur["cpm"], prev["cpm"])
        account["change"] = {"ctr": d_ctr, "cvr": d_cvr, "cpm": d_cpm}
        if d_ctr is not None and d_cvr is not None and d_ctr > -0.15 and d_cvr < -0.25:
            account["diagnosis"] = "post_click"
            account["why"] = f"CTR {d_ctr:+.0%} (holds) while the conversion rate moved {d_cvr:+.0%}: people still click, the page or the offer stopped converting."
        elif d_ctr is not None and d_ctr < -0.15:
            account["diagnosis"] = "creative"
            account["why"] = f"CTR {d_ctr:+.0%} against the previous period: creative fatigue."
        elif d_cpm is not None and d_cpm > 0.25:
            account["diagnosis"] = "audience"
            account["why"] = f"CPM {d_cpm:+.0%} with CTR and conversion rate stable: auction or audience pressure, not the creative."
        else:
            account["diagnosis"] = "stable"
            account["why"] = "No move past the thresholds between the two periods."
    else:
        judged = [m for m in ms if m["diagnosis"] not in ("insufficient_data",)]
        cre = sum(1 for m in judged if m["diagnosis"] in ("creative", "both"))
        pc = sum(1 for m in judged if m["diagnosis"] in ("post_click", "both"))
        account["diagnosis"] = "post_click" if pc > cre else ("creative" if cre else "stable")
        account["why"] = f"{cre} ads with a creative problem, {pc} with a post-click problem (no previous period to compare)."
    if cur["conversions"] < rules["noise_conversions"]:
        notes.append(f"{cur['conversions']:g} conversions in the period: under {rules['noise_conversions']}, rankings are noisy; read them as hints.")
    # Aggregates by the naming convention.
    agg: Dict[str, Dict[str, Any]] = {}
    for dim in ("angle", "style", "stage", "ratio", "test"):
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for m in ms:
            if m["parsed"] and dim in m["parsed"]:
                groups.setdefault(m["parsed"][dim], []).append(m)
        agg[dim] = {k: totals(v) for k, v in sorted(groups.items())}
    unparsed = [m["ad_name"] for m in ms if not m["parsed"]]
    if unparsed:
        notes.append(f"{len(unparsed)} ad names do not follow <project>_<NN>_<stage>_<angle>_<style>_<ratio>: they count in the rankings, not in the aggregates.")
    winners = sorted([m for m in ms if m["verdict"] == "winner"], key=lambda m: m["cpa"])
    losers = [m for m in ms if m["verdict"] == "loser"]
    tested_angles = set(agg["angle"])
    extend = [{"ad_name": m["ad_name"], "why": m["why"], **({k: m["parsed"][k] for k in ("stage", "angle", "style", "ratio")} if m["parsed"] else {})} for m in winners]
    fix_first = account.get("diagnosis") == "post_click"
    share = rules["extend_share"] if winners else 0.0
    next_batch = {
        "fix_post_click_first": fix_first,
        "post_click_actions": (["Re-read the landing page against each ad's promise (preflight).",
                                "Check page load and the checkout or form: landing page views per link click, errors, steps.",
                                "Retarget the clickers who did not convert before buying more top-of-funnel reach."] if fix_first else []),
        "extend_share": share, "explore_share": round(1 - share, 2),
        "extend": extend,
        "retire": [m["ad_name"] for m in losers],
        "creative_fixes": [{"ad_name": m["ad_name"], "problem": m["diagnosis_why"]} for m in ms if m["diagnosis"] in ("creative", "both") and m["verdict"] != "winner"],
        "angles_tested": sorted(tested_angles),
        "note": ("Produce new creatives only after the post-click fixes: the clicks are there, the conversions are not." if fix_first
                 else "Extend the winners (same angle, new execution or format), explore untested angles with the rest."),
    }
    periods = sorted({(r.get("start") or "", r.get("end") or "") for r in rows})
    return {"schema_version": "1.0", "agent": "static-ads-builder", "generated": date.today().isoformat(),
            "period": {"start": periods[0][0] if periods else None, "end": periods[-1][1] if periods else None},
            "currency": next((r.get("currency") for r in rows if r.get("currency")), None), "conversion": conv_key,
            "rules": {**rules, "target_cpa": target, "min_spend": min_spend},
            "medians": {"ctr": med_ctr, "cvr": med_cvr, "hook_rate": med_hook},
            "account": account, "ads": ms,
            "winners": [m["ad_name"] for m in winners], "losers": [m["ad_name"] for m in losers],
            "inconclusive": [m["ad_name"] for m in ms if m["verdict"] == "inconclusive"],
            "insufficient_data": [m["ad_name"] for m in ms if m["verdict"] == "insufficient_data"],
            "aggregates": agg, "notes": notes, "next_batch": next_batch}


def pct(v: Optional[float]) -> str:
    return "n/a" if v is None else f"{v:.2%}"


def money(v: Optional[float], cur: Optional[str]) -> str:
    return "n/a" if v is None else f"{v:.2f} {cur or ''}".strip()


def markdown(r: Dict[str, Any]) -> str:
    cur = r.get("currency")
    a = r["account"]
    lines = [f"# Ads performance, {r['period']['start']} to {r['period']['end']}", "",
             f"Conversion read: `{r['conversion']}`. Target CPA: {money(r['rules']['target_cpa'], cur)}. Minimum spend to judge an ad: {money(r['rules']['min_spend'], cur)}.", "",
             f"**Account diagnosis: {a.get('diagnosis')}.** {a.get('why')}", "",
             f"Account: spend {money(a['current']['spend'], cur)}, CTR {pct(a['current']['ctr'])}, conversion rate {pct(a['current']['cvr'])}, CPA {money(a['current']['cpa'], cur)}.", ""]
    if "previous" in a:
        p = a["previous"]
        lines += [f"Previous period: CTR {pct(p['ctr'])}, conversion rate {pct(p['cvr'])}, CPA {money(p['cpa'], cur)}.", ""]
    lines += ["| Ad | Spend | CTR | Conv. rate | Conversions | CPA | Verdict | Diagnosis |", "|---|---|---|---|---|---|---|---|"]
    order = {"winner": 0, "loser": 1, "inconclusive": 2, "insufficient_data": 3}
    for m in sorted(r["ads"], key=lambda m: (order[m["verdict"]], -m["spend"])):
        lines.append(f"| {m['ad_name']} | {m['spend']:.2f} | {pct(m['ctr'])} | {pct(m['cvr'])} | {m['conversions']:g} | {money(m['cpa'], None)} | "
                     f"{m['verdict']} | {m['diagnosis']}{(': ' + m['diagnosis_why']) if m['diagnosis_why'] else ''} |")
    nb = r["next_batch"]
    lines += ["", "## Next batch", "", nb["note"], ""]
    if nb["fix_post_click_first"]:
        lines += [f"- {x}" for x in nb["post_click_actions"]] + [""]
    lines += [f"- Extend ({nb['extend_share']:.0%} of the batch): " + (", ".join(f"{e['ad_name']} ({e['why']})" for e in nb["extend"]) or "no winner yet"),
              f"- Explore ({nb['explore_share']:.0%}): angles not in {', '.join(nb['angles_tested']) or 'none'}",
              f"- Retire: {', '.join(nb['retire']) or 'none'}"]
    if r["notes"]:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in r["notes"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="Ads Manager CSV export or insights JSON (level ad)")
    ap.add_argument("--previous", help="Same export for the previous period (account diagnosis)")
    ap.add_argument("--config", help="config.json holding a 'perf' object")
    ap.add_argument("--target-cpa", type=float)
    ap.add_argument("--min-spend", type=float)
    ap.add_argument("--conversion", choices=["purchase", "lead", "registration", "results"])
    ap.add_argument("--out", help="JSON output (default ads-performance-<today>.json next to the input)")
    ap.add_argument("--md", help="Markdown summary path (default: printed)")
    a = ap.parse_args()
    rules = dict(DEFAULTS)
    if a.config:
        try:
            rules.update({k: v for k, v in (json.loads(Path(a.config).read_text(encoding="utf-8")).get("perf") or {}).items() if k in DEFAULTS and v is not None})
        except Exception as e:  # noqa: BLE001
            print(f"perf: config not read ({e}), defaults used", file=sys.stderr)
    if a.target_cpa:
        rules["target_cpa"] = a.target_cpa
    if a.min_spend:
        rules["min_spend"] = a.min_spend
    try:
        rows = load(Path(a.input))
        prev = load(Path(a.previous)) if a.previous else None
    except Exception as e:  # noqa: BLE001
        print(f"perf: cannot read the input ({e})", file=sys.stderr)
        return 3
    if not rows:
        print("perf: no ad row found (export at the Ad level, with an 'Ad name' column)", file=sys.stderr)
        return 3
    r = analyse(rows, prev, rules, a.conversion)
    out = Path(a.out) if a.out else Path(a.input).resolve().parent / f"ads-performance-{date.today():%Y%m%d}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = markdown(r)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    else:
        print(md)
    print(f"perf: {len(r['winners'])} winners, {len(r['losers'])} losers, {len(r['inconclusive'])} inconclusive, "
          f"{len(r['insufficient_data'])} insufficient data; account {r['account'].get('diagnosis')} -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
