#!/usr/bin/env python3
"""
compute_pulse.py

The one place where growth-pulse turns source files into numbers. Reads the source
files written by the connectors (assets/source.schema.json), the thresholds of
assets/pulse-rules.json and the metric definitions of assets/metric-catalog.json, and
writes pulse.json (assets/pulse.schema.json) and pulse-tables.md. The model writes the
report from these two files and never computes a figure itself.

    python3 compute_pulse.py --sources <run>/data/*.json --today 2026-10-14 --out-dir <run>/
    python3 compute_pulse.py --sources <run>/data/*.json --config <project>/growth-pulse/config.json \\
        --seo-config <project>/seo-audit/config.json --actions <project>/growth-pulse/actions.csv \\
        --previous-experiments <project>/growth-pulse/experiments-20261007.json --today 2026-10-14 --out-dir <run>/
    python3 compute_pulse.py --show-rules

What it computes, all from assets/pulse-rules.json:
  - weekly values per metric over the window (ISO weeks, Monday to Sunday); a week with
    a missing day is incomplete and never compared
  - the report week against the previous week and against the 4-week mean: absolute
    change, percentage only on at least min_events_for_pct events, rate changes in
    points, a noise band and a signal (up, down, flat, small_volume, n/a), a trend that
    reads the signal with the metric's direction (better, worse, flat, ...)
  - Search Console declines with seo-audit's definition (gsc_decline, mirrored)
  - correlations on the pre-registered pairs only, weekday-adjusted daily Pearson r,
    each one marked causal: false
  - the verdict of last run's experiments (met, not_met, running, not_measurable)
  - source health, a stage summary, the notable moves and the limitations

Exit codes: 0 written, 1 written but no source had data, 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

NETWORK_NAMES = {"linkedin": "LinkedIn", "instagram": "Instagram", "x": "X", "facebook": "Facebook", "tiktok": "TikTok",
                 "youtube": "YouTube", "threads": "Threads", "bluesky": "Bluesky", "social": "Social"}
TREND = {("up", "up"): "better", ("down", "up"): "worse", ("up", "down"): "worse", ("down", "down"): "better"}


# ------------------------------------------------------------------ loading

def load_rules(config: Dict[str, Any], seo_config: Dict[str, Any]) -> Dict[str, Any]:
    rules = G.read_json(G.ASSETS / "pulse-rules.json")
    seo_decline = (seo_config.get("gsc_bands") or {}).get("decline") or {}
    rules["gsc_decline"] = G.deep_merge(rules["gsc_decline"], seo_decline)
    rules = G.deep_merge(rules, config.get("pulse_rules") or {})
    own_decline = (config.get("gsc_bands") or {}).get("decline") or {}
    rules["gsc_decline"] = G.deep_merge(rules["gsc_decline"], own_decline)
    return rules


def strip_comments(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_comments(v) for v in obj]
    return obj


class Source:
    def __init__(self, data: Dict[str, Any], path: str) -> None:
        self.data = data
        self.path = path
        self.name = data["source"]
        self.daily: Dict[dt.date, Dict[str, float]] = {dt.date.fromisoformat(r["date"]): r["values"] for r in data["daily"]}

    def week_complete(self, wid: str) -> bool:
        start = G.week_start(wid)
        return all(start + dt.timedelta(days=i) in self.daily for i in range(7))

    def week_sum(self, wid: str, metric: str) -> Optional[float]:
        if not self.week_complete(wid):
            return None
        start = G.week_start(wid)
        return sum(float(self.daily[start + dt.timedelta(days=i)].get(metric, 0.0)) for i in range(7))


# ------------------------------------------------------------------ metric definitions

def catalog_entry(catalog: Dict[str, Any], mid: str) -> Optional[Dict[str, Any]]:
    for e in catalog["metrics"]:
        if fnmatch.fnmatchcase(mid, e["match"]):
            return e
    return None


def label_for(entry: Dict[str, Any], mid: str, source: str) -> str:
    parts = mid.split(".")
    if source == "social" and len(parts) == 3:
        return f"{NETWORK_NAMES.get(parts[1], parts[1].title())} {entry['label'][0].lower() + entry['label'][1:]}"
    if ".event." in mid:
        return f"Event {mid.split('.event.', 1)[1]} ({source})"
    if source in ("gsc", "revenue"):
        return entry["label"]
    return f"{entry['label']} ({source})"


# ------------------------------------------------------------------ comparisons

def trend_of(signal: str, direction: str) -> str:
    if signal in ("up", "down"):
        return TREND[(signal, direction)]
    return signal  # flat, small_volume, n/a


def cmp_count(cur: Optional[float], ref: Optional[float], ref_is_mean: bool, k: int, rules: Dict[str, Any],
              direction: str, spread: Optional[float] = None) -> Dict[str, Any]:
    n_min, z = rules["volume"]["min_events_for_pct"], rules["noise"]["z"]
    out = {"abs": None, "pct": None, "pp": None, "noise_band": None, "z": None, "within_noise": None,
           "small_volume": False, "signal": "n/a", "trend": "n/a"}
    if cur is None or ref is None:
        return out
    diff = cur - ref
    out["abs"] = G.rnd(diff, 1)
    out["small_volume"] = ref < n_min
    if ref >= n_min:
        out["pct"] = G.rnd(diff * 100.0 / ref, 1)
    var = ref * (1 + 1.0 / k) if ref_is_mean else cur + ref
    sd = math.sqrt(var) if var > 0 else 0.0
    if spread is not None:
        # observed week-to-week spread of the reference weeks: impressions or pageviews
        # come in bursts (one post, one crawl) and vary more than independent events
        sd = max(sd, spread * math.sqrt(1 + 1.0 / k) if ref_is_mean else spread * math.sqrt(2))
    out["noise_band"] = G.rnd(z * sd, 1)
    out["z"] = G.rnd(diff / sd, 1) if sd else None
    out["within_noise"] = abs(diff) <= z * sd
    out["signal"] = "flat" if out["within_noise"] else ("up" if diff > 0 else "down")
    out["trend"] = trend_of(out["signal"], direction)
    return out


def cmp_currency(cur: Optional[float], ref: Optional[float], vol_cur: Optional[float], vol_ref: Optional[float],
                 rules: Dict[str, Any], direction: str) -> Dict[str, Any]:
    n_min = rules["volume"]["min_events_for_pct"]
    out = {"abs": None, "pct": None, "pp": None, "noise_band": None, "z": None, "within_noise": None,
           "small_volume": False, "signal": "n/a", "trend": "n/a"}
    if cur is None or ref is None:
        return out
    diff = cur - ref
    out["abs"] = G.rnd(diff, 2)
    small = (vol_cur or 0) < n_min or (vol_ref or 0) < n_min
    out["small_volume"] = small
    if small:
        out["signal"] = out["trend"] = "small_volume"
        return out
    if ref:
        out["pct"] = G.rnd(diff * 100.0 / ref, 1)
    out["signal"] = "flat" if diff == 0 else ("up" if diff > 0 else "down")
    out["trend"] = trend_of(out["signal"], direction)
    return out


def rate_pct(num: Optional[float], den: Optional[float], n_min: int) -> Optional[float]:
    if num is None or den is None or den <= 0 or num < n_min or den < n_min:
        return None
    return G.rnd(num * 100.0 / den, 1)


def cmp_rate(x1: Optional[float], n1: Optional[float], x0: Optional[float], n0: Optional[float], rules: Dict[str, Any],
             direction: str) -> Dict[str, Any]:
    n_min, z = rules["volume"]["min_events_for_pct"], rules["noise"]["z"]
    out = {"abs": None, "pct": None, "pp": None, "noise_band": None, "z": None, "within_noise": None,
           "small_volume": False, "signal": "n/a", "trend": "n/a"}
    if None in (x1, n1, x0, n0):
        return out
    if rate_pct(x1, n1, n_min) is None or rate_pct(x0, n0, n_min) is None:
        out["small_volume"] = True
        out["signal"] = out["trend"] = "small_volume"
        return out
    p1, p0 = x1 / n1, x0 / n0
    pooled = (x1 + x0) / (n1 + n0)
    se = math.sqrt(pooled * (1 - pooled) * (1.0 / n1 + 1.0 / n0))
    diff = p1 - p0
    out["pp"] = G.rnd(diff * 100.0, 1)
    out["noise_band"] = G.rnd(z * se * 100.0, 1)
    out["z"] = G.rnd(diff / se, 1) if se else None
    out["within_noise"] = abs(diff) <= z * se
    out["signal"] = "flat" if out["within_noise"] else ("up" if diff > 0 else "down")
    out["trend"] = trend_of(out["signal"], direction)
    return out


def cmp_position(cur: Optional[float], ref: Optional[float], impr_cur: Optional[float], impr_ref: Optional[float],
                 rules: Dict[str, Any], direction: str) -> Dict[str, Any]:
    n_min, band = rules["volume"]["min_events_for_pct"], rules["noise"]["position_flat_band"]
    out = {"abs": None, "pct": None, "pp": None, "noise_band": band, "z": None, "within_noise": None,
           "small_volume": False, "signal": "n/a", "trend": "n/a"}
    if cur is None or ref is None:
        return out
    diff = cur - ref
    out["abs"] = G.rnd(diff, 1)
    if (impr_cur or 0) < n_min or (impr_ref or 0) < n_min:
        out["small_volume"] = True
        out["signal"] = out["trend"] = "small_volume"
        return out
    out["within_noise"] = abs(diff) < band
    out["signal"] = "flat" if out["within_noise"] else ("up" if diff > 0 else "down")
    out["trend"] = trend_of(out["signal"], direction)
    return out


# ------------------------------------------------------------------ metrics

class Ctx:
    def __init__(self, rules, catalog, config, weeks: List[str]) -> None:
        self.rules, self.catalog, self.config, self.weeks = rules, catalog, config, weeks
        self.cur, self.prev = weeks[-1], weeks[-2]
        k = rules["weeks"]["baseline_weeks"]
        self.base = weeks[-1 - k:-1]
        self.limitations: List[str] = []


def mean(vals: List[float]) -> Optional[float]:
    return sum(vals) / len(vals) if vals else None


def stdev(vals: List[float]) -> Optional[float]:
    """Sample standard deviation (n - 1)."""
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def base_metric(ctx: Ctx, src: Source, name: str, events_map: Dict[str, str], unmapped: List[str]) -> Optional[Dict[str, Any]]:
    mid = f"{src.name}.{name}"
    entry = catalog_entry(ctx.catalog, mid)
    if not entry:
        ctx.limitations.append(f"{mid}: no definition in metric-catalog.json, left out")
        return None
    stage = entry["stage"]
    flags = []
    if stage == "event":
        ev = name.split("event.", 1)[1]
        stage = events_map.get(ev)
        if not stage:
            stage = ctx.catalog["default_event_stage"]
            flags.append("unmapped_event")
            if ev not in unmapped:
                unmapped.append(ev)
    if src.name in ctx.catalog["web_sources"] and name == "visitors":
        flags.append("daily_visitors_summed")
    series = [{"week": w, "value": G.rnd(src.week_sum(w, name), 2) if src.week_sum(w, name) is not None else None,
               "complete": src.week_complete(w)} for w in ctx.weeks]
    return {"id": mid, "label": label_for(entry, mid, src.name), "source": src.name, "stage": stage, "kind": entry["kind"],
            "unit": entry["unit"], "direction": entry["direction"], "hidden": bool(entry.get("hidden")),
            "volume_metric": entry.get("volume_metric"), "series": series, "flags": flags}


def finish_count(ctx: Ctx, m: Dict[str, Any]) -> None:
    vals = {s["week"]: s["value"] for s in m["series"]}
    cur, prev = vals.get(ctx.cur), vals.get(ctx.prev)
    base_vals = [vals[w] for w in ctx.base if vals.get(w) is not None]
    enough = len(base_vals) >= ctx.rules["weeks"]["min_complete_baseline_weeks"]
    base = mean(base_vals) if enough else None
    m["current"], m["previous"] = cur, prev
    m["baseline"] = G.rnd(base, 1) if base is not None else None
    m["baseline_weeks_used"] = len(base_vals) if enough else 0
    spread = stdev(base_vals) if len(base_vals) >= ctx.rules["noise"]["min_weeks_for_spread"] else None
    m["vs_previous"] = cmp_count(cur, prev, False, 1, ctx.rules, m["direction"], spread)
    m["vs_baseline"] = cmp_count(cur, base, True, max(len(base_vals), 1), ctx.rules, m["direction"], spread)


def finish_currency(ctx: Ctx, m: Dict[str, Any], vol: Optional[Dict[str, Any]]) -> None:
    vals = {s["week"]: s["value"] for s in m["series"]}
    vv = {s["week"]: s["value"] for s in vol["series"]} if vol else {}
    cur, prev = vals.get(ctx.cur), vals.get(ctx.prev)
    base_weeks = [w for w in ctx.base if vals.get(w) is not None]
    enough = len(base_weeks) >= ctx.rules["weeks"]["min_complete_baseline_weeks"]
    base = mean([vals[w] for w in base_weeks]) if enough else None
    vbase = mean([vv.get(w) or 0 for w in base_weeks]) if enough else None
    m["current"], m["previous"] = cur, prev
    m["baseline"] = G.rnd(base, 2) if base is not None else None
    m["baseline_weeks_used"] = len(base_weeks) if enough else 0
    m["vs_previous"] = cmp_currency(cur, prev, vv.get(ctx.cur), vv.get(ctx.prev), ctx.rules, m["direction"])
    m["vs_baseline"] = cmp_currency(cur, base, vv.get(ctx.cur), vbase, ctx.rules, m["direction"])


def derived_rate(ctx: Ctx, mid: str, label: str, stage: str, kind: str, direction: str, num: Dict[str, Any],
                 den: Dict[str, Any], flags: List[str]) -> Dict[str, Any]:
    n_min = ctx.rules["volume"]["min_events_for_pct"]
    nv = {s["week"]: s["value"] for s in num["series"]}
    dv = {s["week"]: s["value"] for s in den["series"]}
    series = []
    for w in ctx.weeks:
        x, n = nv.get(w), dv.get(w)
        if kind == "rate":
            val = rate_pct(x, n, n_min)
        else:
            val = G.rnd(x / n, 1) if x is not None and n else None
        series.append({"week": w, "value": val, "complete": x is not None and n is not None,
                       "numerator": G.rnd(x, 2) if x is not None else None, "denominator": G.rnd(n, 2) if n is not None else None})
    base_weeks = [w for w in ctx.base if nv.get(w) is not None and dv.get(w) is not None]
    enough = len(base_weeks) >= ctx.rules["weeks"]["min_complete_baseline_weeks"]
    x0 = sum(nv[w] for w in base_weeks) if enough else None
    n0 = sum(dv[w] for w in base_weeks) if enough else None
    m = {"id": mid, "label": label, "source": num["source"], "stage": stage, "kind": kind, "unit": "%" if kind == "rate" else "position",
         "direction": direction, "hidden": False, "volume_metric": None, "series": series, "flags": list(flags),
         "baseline_weeks_used": len(base_weeks) if enough else 0}
    cur = next(s for s in series if s["week"] == ctx.cur)
    prev = next(s for s in series if s["week"] == ctx.prev)
    m["current"], m["previous"] = cur["value"], prev["value"]
    m["counts"] = {"current": {"numerator": cur["numerator"], "denominator": cur["denominator"]},
                   "previous": {"numerator": prev["numerator"], "denominator": prev["denominator"]},
                   "baseline": {"numerator": G.rnd(x0, 2) if x0 is not None else None, "denominator": G.rnd(n0, 2) if n0 is not None else None}}
    if kind == "rate":
        m["baseline"] = rate_pct(x0, n0, n_min) if enough else None
        m["vs_previous"] = cmp_rate(nv.get(ctx.cur), dv.get(ctx.cur), nv.get(ctx.prev), dv.get(ctx.prev), ctx.rules, direction)
        m["vs_baseline"] = cmp_rate(nv.get(ctx.cur), dv.get(ctx.cur), x0, n0, ctx.rules, direction)
    else:
        m["baseline"] = G.rnd(x0 / n0, 1) if enough and n0 else None
        k = max(len(base_weeks), 1)
        m["vs_previous"] = cmp_position(m["current"], m["previous"], dv.get(ctx.cur), dv.get(ctx.prev), ctx.rules, direction)
        m["vs_baseline"] = cmp_position(m["current"], m["baseline"], dv.get(ctx.cur), (n0 / k) if n0 else None, ctx.rules, direction)
    if m["vs_previous"]["small_volume"] or m["vs_baseline"]["small_volume"] or (cur["numerator"] is not None and m["current"] is None):
        m["flags"].append("small_volume")
    return m


def build_metrics(ctx: Ctx, sources: List[Source]) -> List[Dict[str, Any]]:
    events_map = {str(k).lower(): v for k, v in (ctx.config.get("events") or {}).items() if not str(k).startswith("_")}
    unmapped: List[str] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    for src in sources:
        for name in src.data["metrics"]:
            m = base_metric(ctx, src, name, events_map, unmapped)
            if m:
                by_id[m["id"]] = m
    for m in by_id.values():
        if m["kind"] == "count":
            finish_count(ctx, m)
    for m in by_id.values():
        if m["kind"] == "currency":
            finish_currency(ctx, m, by_id.get(m["volume_metric"] or ""))
    n_min = ctx.rules["volume"]["min_events_for_pct"]
    for m in by_id.values():
        if m["kind"] == "count" and m["vs_previous"]["small_volume"]:
            m["flags"].append("small_volume")
        elif m["kind"] == "currency" and (m["vs_previous"]["small_volume"] or m["vs_baseline"]["small_volume"]):
            m["flags"].append("small_volume")
        if any(not s["complete"] for s in m["series"] if s["week"] == ctx.cur):
            m["flags"].append("incomplete_week")
    derived: List[Dict[str, Any]] = []
    for d in ctx.catalog["derived"]:
        if d.get("for_each") == "web_event":
            for src_name in ctx.catalog["web_sources"]:
                den = by_id.get(f"{src_name}.visitors")
                if not den:
                    continue
                for mid, num in sorted(by_id.items()):
                    if not mid.startswith(f"{src_name}.event."):
                        continue
                    ev = mid.split(".event.", 1)[1]
                    derived.append(derived_rate(ctx, d["id"].format(source=src_name, event=ev),
                                                f"Visitor to {ev} rate ({src_name})", num["stage"], "rate", d["direction"],
                                                num, den, [f for f in num["flags"] if f == "unmapped_event"]))
        else:
            num, den = by_id.get(d["numerator"]), by_id.get(d["denominator"])
            if num and den:
                derived.append(derived_rate(ctx, d["id"], d["label"], d["stage"], d["kind"], d["direction"], num, den, []))
    for m in derived:
        if any(not s["complete"] for s in m["series"] if s["week"] == ctx.cur):
            m["flags"].append("incomplete_week")
    out = [m for m in by_id.values() if not m["hidden"]] + derived
    for m in out:
        m["flags"] = sorted(set(m["flags"]))
        m.pop("hidden", None)
        m.pop("volume_metric", None)
    if unmapped:
        ctx.limitations.append(f"events without a stage in config.events, counted as {ctx.catalog['default_event_stage']}: "
                               + ", ".join(sorted(unmapped)))
    stage_order = {s: i for i, s in enumerate(ctx.rules["experiments"]["stages"])}
    out.sort(key=lambda m: (stage_order.get(m["stage"], 99), m["source"], m["id"]))
    _ = n_min
    return out


# ------------------------------------------------------------------ Search Console

def decline_row(cur: Optional[Dict[str, float]], prior: Optional[Dict[str, float]], D: Dict[str, Any], n_min: int) -> Dict[str, Any]:
    def pos(v):
        return v["position_weighted"] / v["impressions"] if v and v.get("impressions") else None
    row: Dict[str, Any] = {"clicks": {"current": G.rnd(cur["clicks"], 0) if cur else 0, "prior": G.rnd(prior["clicks"], 0) if prior else 0},
                           "impressions": {"current": G.rnd(cur["impressions"], 0) if cur else 0, "prior": G.rnd(prior["impressions"], 0) if prior else 0},
                           "position": {"current": G.rnd(pos(cur), 1) if cur else None, "prior": G.rnd(pos(prior), 1) if prior else None}}
    pc = prior["clicks"] if prior else 0
    cc = cur["clicks"] if cur else 0
    raw_pct = (cc - pc) * 100.0 / pc if pc else None
    row["clicks_change"] = G.rnd(cc - pc, 0)
    row["clicks_pct"] = G.rnd(raw_pct, 1) if raw_pct is not None and pc >= n_min else None
    pi = prior["impressions"] if prior else 0
    ci = cur["impressions"] if cur else 0
    imp_pct = (ci - pi) * 100.0 / pi if pi else None
    row["impressions_pct"] = G.rnd(imp_pct, 1) if imp_pct is not None and pi >= n_min else None
    p0, p1 = pos(prior), pos(cur)
    row["position_change"] = G.rnd(p1 - p0, 1) if p0 is not None and p1 is not None else None
    row["decline"] = bool(prior and pc >= D["min_prior_clicks"] and raw_pct is not None and raw_pct <= D["max_change_pct"])
    row["cause"] = None
    if row["decline"]:
        if not cur:
            row["cause"] = "gone"
        elif p0 is not None and p1 is not None and p1 - p0 >= D["cause_position_worse_by"]:
            row["cause"] = "position"
        elif imp_pct is not None and imp_pct <= D["cause_impressions_change_pct"]:
            row["cause"] = "demand"
        else:
            row["cause"] = "ctr"
    return row


def gsc_section(ctx: Ctx, sources: List[Source]) -> Dict[str, Any]:
    D = {k: v for k, v in ctx.rules["gsc_decline"].items() if not k.startswith("_")}
    n_min = ctx.rules["volume"]["min_events_for_pct"]
    src = next((s for s in sources if s.name == "gsc"), None)
    base = {"available": False, "definition": D, "definition_source": "decline object of seo-audit's gsc-bands.json, mirrored in pulse-rules.json gsc_decline",
            "current_week": ctx.cur, "prior_week": ctx.prev, "totals": None, "queries": [], "pages": [], "breakdowns_available": False, "note": ""}
    if not src or not src.daily:
        base["note"] = "no Search Console data"
        return base
    if not (src.week_complete(ctx.cur) and src.week_complete(ctx.prev)):
        base["note"] = "the report week or the previous week is incomplete (Search Console reports 2 to 3 days late): no decline computed"
        return base
    tot = {}
    for w in (ctx.cur, ctx.prev):
        tot[w] = {k: src.week_sum(w, k) or 0.0 for k in ("clicks", "impressions", "position_weighted")}
    base["available"] = True
    base["totals"] = decline_row(tot[ctx.cur], tot[ctx.prev], D, n_min)
    rows: Dict[Tuple[str, str], Dict[str, Dict[str, float]]] = {}
    for b in src.data["breakdowns"]:
        if b["week"] in (ctx.cur, ctx.prev):
            rows.setdefault((b["dimension"], b["key"]), {})[b["week"]] = b["values"]
    base["breakdowns_available"] = bool(rows)
    for (dim, key), wk in sorted(rows.items()):
        r = decline_row(wk.get(ctx.cur), wk.get(ctx.prev), D, n_min)
        if r["decline"]:
            r["key"] = key
            base["queries" if dim == "query" else "pages"].append(r)
    for k in ("queries", "pages"):
        base[k].sort(key=lambda r: (r["clicks_change"], r["key"]))
    if not rows:
        base["note"] = "totals only: no query or page rows in the input (UI CSV export)"
    return base


# ------------------------------------------------------------------ correlations

def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def daily_series(src: Source, name: str, days: List[dt.date]) -> Dict[dt.date, float]:
    raw = {d: float(src.daily[d].get(name, 0.0)) for d in days if d in src.daily}
    by_wd: Dict[int, List[float]] = {}
    for d, v in raw.items():
        by_wd.setdefault(d.weekday(), []).append(v)
    means = {wd: sum(v) / len(v) for wd, v in by_wd.items()}
    return {d: v - means[d.weekday()] for d, v in raw.items()}


def correlations(ctx: Ctx, sources: List[Source], metrics: List[Dict[str, Any]], since: dt.date, until: dt.date) -> List[Dict[str, Any]]:
    C = ctx.rules["correlation"]
    days = G.days_between(since, until)
    by_name = {s.name: s for s in sources}
    ids = [m["id"] for m in metrics if m["kind"] == "count"]
    out = []
    seen = set()
    for pair in C["pairs"]:
        for a in [i for i in ids if fnmatch.fnmatchcase(i, pair["a"])]:
            for b in [i for i in ids if fnmatch.fnmatchcase(i, pair["b"])]:
                if a == b or (a, b) in seen:
                    continue
                sa, sb = a.split(".", 1)[0], b.split(".", 1)[0]
                if pair.get("same_source") and sa != sb:
                    continue
                if not pair.get("same_source") and sa == sb:
                    continue
                seen.add((a, b))
                xa = daily_series(by_name[sa], a.split(".", 1)[1], days)
                xb = daily_series(by_name[sb], b.split(".", 1)[1], days)
                for lag in C["lags_days"]:
                    pts = [(xa[d], xb[d + dt.timedelta(days=lag)]) for d in days if d in xa and d + dt.timedelta(days=lag) in xb]
                    r = pearson([p[0] for p in pts], [p[1] for p in pts]) if len(pts) >= C["min_days"] else None
                    label = "insufficient_data" if len(pts) < C["min_days"] or r is None else (
                        "correlated" if abs(r) >= C["min_abs_r"] else "weak")
                    out.append({"a": a, "b": b, "lag_days": lag, "n_days": len(pts), "r": G.rnd(r, 2) if r is not None else None,
                                "label": label, "causal": False, "question": pair["question"]})
    for i, c in enumerate(out, 1):
        c["id"] = f"C{i}"
    return [{"id": c.pop("id"), **c} for c in out]


# ------------------------------------------------------------------ actions and experiments

def read_actions(path: Optional[str], since: dt.date, until: dt.date, cur: str) -> List[Dict[str, Any]]:
    if not path:
        return []
    out = []
    for r in G.read_csv(path):
        d = G.parse_date_cell(r.get("date", ""))
        if not d or not since <= d <= until:
            continue
        out.append({"date": d.isoformat(), "week": G.week_id(d), "in_report_week": G.week_id(d) == cur,
                    "channel": r.get("channel", "").strip(), "stage": r.get("stage", "").strip().lower(),
                    "action": r.get("action", "").strip()})
    out.sort(key=lambda a: (a["date"], a["action"]))
    return out


def followup(ctx: Ctx, path: Optional[str], metrics: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    if not path:
        return None, []
    prev = G.read_json(path)
    errs = G.schema_errors(prev, "experiments.schema.json")
    if errs:
        raise G.InputError(f"{path} fails assets/experiments.schema.json: {errs[:3]}")
    info = {"file": os.path.basename(path), "week": prev["week"]["id"], "generated_on": prev["generated_on"]}
    by_id = {m["id"]: m for m in metrics}
    cur_end = G.week_start(ctx.cur) + dt.timedelta(days=6)
    out = []
    for e in prev["experiments"]:
        start = dt.date.fromisoformat(e["start_date"])
        end = start + dt.timedelta(days=e["duration_days"] - 1)
        thr = e["success_threshold"]
        row = {"id": e["id"], "title": e["title"], "stage": e["stage"], "metric": e["metric"]["id"], "start_date": start.isoformat(),
               "end_date": end.isoformat(), "baseline": e["baseline"]["value"], "threshold": {"comparator": thr["comparator"], "value": thr["value"], "per": thr["per"]},
               "weeks_measured": [], "observed": None, "verdict": "not_measurable", "reason": ""}
        mid = e["metric"]["id"]
        m = by_id.get(mid[4:] if mid.startswith("new:") else mid)
        if not m:
            row["reason"] = ("metric still absent from the data: the tracking is not live yet" if mid.startswith("new:")
                             else "metric absent from this run's data: source not connected or event never recorded")
            out.append(row)
            continue
        weeks = [w for w in ctx.weeks if G.week_start(w) >= start and G.week_start(w) + dt.timedelta(days=6) <= min(end, cur_end)]
        series = {s["week"]: s for s in m["series"]}
        usable = [w for w in weeks if series.get(w, {}).get("complete") and (series[w]["value"] is not None or m["kind"] == "rate")]
        row["weeks_measured"] = usable
        if m["kind"] == "rate":
            xs = [series[w]["numerator"] for w in usable]
            ns = [series[w]["denominator"] for w in usable]
            observed = rate_pct(sum(xs), sum(ns), ctx.rules["volume"]["min_events_for_pct"]) if usable else None
            if usable and observed is None:
                row["reason"] = "too few events to state a rate"
        else:
            vals = [series[w]["value"] for w in usable]
            observed = (sum(vals) / len(vals) if thr["per"] == "week" else sum(vals)) if vals else None
        row["observed"] = G.rnd(observed, 1) if observed is not None else None
        if end > cur_end:
            row["verdict"] = "running"
            row["reason"] = f"ends {end.isoformat()}, after the report week"
        elif observed is None:
            row["reason"] = row["reason"] or "no complete week inside the experiment window"
        else:
            ok = observed >= thr["value"] if thr["comparator"] == ">=" else observed <= thr["value"]
            row["verdict"] = "met" if ok else "not_met"
            row["reason"] = "observed within the experiment window; a met threshold is a correlation with the change, not proof of its effect"
        out.append(row)
    return info, out


# ------------------------------------------------------------------ summary, limitations, tables

def notable(metrics: List[Dict[str, Any]]) -> List[str]:
    rows = []
    for m in metrics:
        a, b = m["vs_previous"]["trend"], m["vs_baseline"]["trend"]
        if a in ("better", "worse") and b == a:
            rows.append((-abs(m["vs_baseline"].get("z") or 0), m["id"]))
    return [i for _, i in sorted(rows)]


def stage_summary(ctx: Ctx, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for st in ctx.rules["experiments"]["stages"]:
        ms = [m for m in metrics if m["stage"] == st]
        cnt = {k: 0 for k in ("better", "worse", "flat", "small_volume", "n/a")}
        for m in ms:
            cnt[m["vs_baseline"]["trend"]] = cnt.get(m["vs_baseline"]["trend"], 0) + 1
        out.append({"stage": st, "metrics": len(ms), "better": cnt["better"], "worse": cnt["worse"], "flat": cnt["flat"],
                    "small_volume": cnt["small_volume"], "not_comparable": cnt["n/a"]})
    return out


def health(sources: List[Source], cur: str, since: dt.date, until: dt.date) -> List[Dict[str, Any]]:
    by = {s.name: s for s in sources}
    out = []
    for name in G.SOURCES:
        s = by.get(name)
        if not s:
            out.append({"source": name, "provider": "none", "status": "missing", "message": "not run this week",
                        "days_with_data": 0, "missing_days": [], "report_week_complete": False, "notes": []})
            continue
        miss = [d for d in s.data["missing_days"] if since.isoformat() <= d <= until.isoformat()]
        out.append({"source": name, "provider": s.data["provider"], "status": s.data["status"], "message": s.data["message"],
                    "days_with_data": len([d for d in s.daily if since <= d <= until]), "missing_days": miss,
                    "report_week_complete": s.week_complete(cur), "notes": s.data["notes"]})
    return out


def fmt(v: Any, kind: str = "count") -> str:
    if v is None:
        return "n/a"
    if kind == "currency":
        return f"{v:.2f}"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:g}" if isinstance(v, float) else str(v)


def signed(v: Any, kind: str = "count") -> str:
    if v is None:
        return "n/a"
    s = fmt(abs(v), kind)
    return ("+" if v > 0 else "-" if v < 0 else "") + s


def change_cell(m: Dict[str, Any], c: Dict[str, Any], currency: str) -> str:
    if c["signal"] == "n/a":
        return "n/a"
    k = m["kind"]
    if k == "rate":
        if c["pp"] is None:
            return "small volume"
        return f"{signed(c['pp'])} pts"
    if k == "position":
        return signed(c["abs"])
    if k == "currency":
        base = f"{signed(c['abs'], 'currency')} {currency}"
        return base + (f" ({signed(c['pct'])}%)" if c["pct"] is not None else "")
    return signed(c["abs"]) + (f" ({signed(c['pct'])}%)" if c["pct"] is not None else "")


def value_cell(m: Dict[str, Any], key: str, currency: str) -> str:
    v = m[key]
    if m["kind"] == "rate":
        cnt = m["counts"]["baseline" if key == "baseline" else key]
        if v is None and cnt["numerator"] is not None:
            return f"{fmt(cnt['numerator'])} of {fmt(cnt['denominator'])}"
        return f"{fmt(v)}%" if v is not None else "n/a"
    if m["kind"] == "currency":
        return f"{fmt(v, 'currency')} {currency}" if v is not None else "n/a"
    return fmt(v)


READ = {"better": "better", "worse": "worse", "flat": "flat (within noise)", "small_volume": "small volume", "n/a": "n/a"}


def tables_md(p: Dict[str, Any]) -> str:
    cur = p["currency"] or ""
    L = [f"<!-- Generated by compute_pulse.py from pulse.json ({p['week']['id']}). Copy blocks into the report as they are. -->", ""]
    L += ["### Source health", "", "| Source | Provider | Status | Days with data | Report week complete | Note |", "|---|---|---|---:|---|---|"]
    for h in p["sources"]:
        L.append(f"| {h['source']} | {h['provider']} | {h['status']} | {h['days_with_data']} | {'yes' if h['report_week_complete'] else 'no'} | {h['message']} |")
    L.append("")
    for st in p["rules"]["experiments"]["stages"]:
        ms = [m for m in p["metrics"] if m["stage"] == st]
        if not ms:
            continue
        L += [f"### {st.capitalize()}", "", "| Metric | This week | Last week | Change | 4-week mean | vs 4 weeks | Read |", "|---|---:|---:|---:|---:|---:|---|"]
        for m in ms:
            L.append(f"| {m['label']} | {value_cell(m, 'current', cur)} | {value_cell(m, 'previous', cur)} | {change_cell(m, m['vs_previous'], cur)} | "
                     f"{value_cell(m, 'baseline', cur)} | {change_cell(m, m['vs_baseline'], cur)} | {READ[m['vs_baseline']['trend']]} |")
        L.append("")
    g = p["gsc"]
    L += ["### Search Console declines", ""]
    if not g["available"]:
        L += [f"Not computed: {g['note']}.", ""]
    else:
        t = g["totals"]
        L.append(f"Totals {g['current_week']} vs {g['prior_week']}: {t['clicks']['current']} clicks vs {t['clicks']['prior']}"
                 + (f" ({signed(t['clicks_pct'])}%)" if t["clicks_pct"] is not None else "")
                 + f", position {fmt(t['position']['current'])} vs {fmt(t['position']['prior'])}. "
                 + (f"Decline, cause: {t['cause']}." if t["decline"] else "No decline by the shared definition."))
        L.append("")
        for k, lab in (("queries", "Query"), ("pages", "Page")):
            if g[k]:
                L += [f"| {lab} | Clicks | Prior | Change | Position | Prior | Cause |", "|---|---:|---:|---:|---:|---:|---|"]
                for r in g[k]:
                    L.append(f"| `{r['key']}` | {r['clicks']['current']} | {r['clicks']['prior']} | {signed(r['clicks_change'])} | "
                             f"{fmt(r['position']['current'])} | {fmt(r['position']['prior'])} | {r['cause']} |")
                L.append("")
        if g["note"]:
            L += [g["note"] + ".", ""]
    L += ["### Correlations (pre-registered pairs, never causes)", "", "| Id | A | B | Lag (days) | Days | r | Read |", "|---|---|---|---:|---:|---:|---|"]
    for c in p["correlations"]:
        L.append(f"| {c['id']} | {c['a']} | {c['b']} | {c['lag_days']} | {c['n_days']} | {fmt(c['r'])} | {c['label'].replace('_', ' ')} |")
    L.append("")
    if p["actions"]:
        L += ["### Actions logged by the founder", "", "| Date | Channel | Stage | Action |", "|---|---|---|---|"]
        for a in p["actions"]:
            L.append(f"| {a['date']} | {a['channel']} | {a['stage']} | {a['action']} |")
        L.append("")
    if p["previous_experiments"]:
        L += ["### Last run's experiments", "", "| Id | Metric | Threshold | Observed | Verdict |", "|---|---|---:|---:|---|"]
        for e in p["experiments_followup"]:
            L.append(f"| {e['id']} | `{e['metric']}` | {e['threshold']['comparator']} {fmt(e['threshold']['value'])} {'per week' if e['threshold']['per'] == 'week' else 'in total'} | "
                     f"{fmt(e['observed'])} | {e['verdict'].replace('_', ' ')} |")
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weekly growth numbers from growth-pulse source files: pulse.json and pulse-tables.md.")
    ap.add_argument("--sources", nargs="+", default=[], help="source files written by the connectors (<run>/data/*.json)")
    ap.add_argument("--config", help="<project>/growth-pulse/config.json (events stages, pulse_rules and gsc_bands overrides)")
    ap.add_argument("--seo-config", help="<project>/seo-audit/config.json: its gsc_bands.decline override applies here too")
    ap.add_argument("--actions", help="actions log CSV (date, channel, stage, action), optional")
    ap.add_argument("--previous-experiments", help="last run's experiments-<YYYYMMDD>.json, to judge them")
    ap.add_argument("--today", help="run date YYYY-MM-DD (default today)")
    ap.add_argument("--week", help="report week (default: the last complete ISO week before --today)")
    ap.add_argument("--project", help="project slug written in pulse.json (default: config.project)")
    ap.add_argument("--out-dir", help="writes pulse.json and pulse-tables.md here")
    ap.add_argument("--show-rules", action="store_true", help="print the applied rules and exit")
    args = ap.parse_args(argv)
    try:
        config = G.read_json(args.config) if args.config else {}
        seo = G.read_json(args.seo_config) if args.seo_config and os.path.exists(args.seo_config) else {}
        rules = load_rules(config, seo)
        if args.show_rules:
            print(G.dumps(strip_comments(rules)), end="")
            return 0
        if not args.out_dir:
            ap.error("--out-dir is required")
        catalog = G.read_json(G.ASSETS / "metric-catalog.json")
        today = G.parse_day(args.today)
        wid = args.week or G.last_complete_week(today)
        nweeks = rules["weeks"]["window_weeks"]
        since, until = G.window(today, nweeks, wid)
        weeks = [G.week_id(since + dt.timedelta(days=7 * i)) for i in range(nweeks)]
        sources: List[Source] = []
        inputs = []
        for path in sorted(args.sources):
            data = G.read_json(path)
            errs = G.schema_errors(data, "source.schema.json")
            if errs:
                raise G.InputError(f"{path} fails assets/source.schema.json: {errs[:3]}")
            if any(s.name == data["source"] for s in sources):
                raise G.InputError(f"two source files for {data['source']}")
            sources.append(Source(data, path))
            inputs.append({"file": os.path.basename(path), "source": data["source"], "sha256": G.sha256_file(path)})
        ctx = Ctx(rules, catalog, config, weeks)
        metrics = build_metrics(ctx, sources)
        prev_info, follow = followup(ctx, args.previous_experiments, metrics)
        if args.previous_experiments:
            inputs.append({"file": os.path.basename(args.previous_experiments), "source": "previous_experiments",
                           "sha256": G.sha256_file(args.previous_experiments)})
        if args.actions:
            inputs.append({"file": os.path.basename(args.actions), "source": "actions", "sha256": G.sha256_file(args.actions)})
        actions = read_actions(args.actions, since, until, wid)
    except G.InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    usable = [s for s in sources if s.daily]
    lims = list(ctx.limitations)
    for s in health(sources, wid, since, until):
        if s["status"] != "ok":
            lims.append(f"{s['source']}: {s['status']} ({s['message']})")
    if any("daily_visitors_summed" in m["flags"] for m in metrics):
        lims.append("weekly visitors are daily unique visitors summed: one person visiting on two days counts twice")
    small = [m["id"] for m in metrics if "small_volume" in m["flags"]]
    if small:
        lims.append(f"{len(small)} metric(s) under {rules['volume']['min_events_for_pct']} events: counts only, no percentage")
    lims.append("correlations come from 6 weeks of one site: they show what moved together, never what caused what")
    rev = next((s for s in sources if s.name == "revenue"), None)
    currency = None
    if rev:
        for n in rev.data["notes"]:
            if n.startswith("currency "):
                currency = n.split()[1].rstrip(";")
    h = hashlib.sha256()
    for i in inputs:
        h.update(i["sha256"].encode())
    h.update(G.dumps(strip_comments(rules)).encode())
    h.update(G.dumps(config.get("events") or {}).encode())
    h.update(wid.encode())
    pulse = {
        "schema_version": "1.0",
        "agent": "growth-pulse",
        "project": args.project or config.get("project") or "project",
        "generated_on": today.isoformat(),
        "week": {"id": wid, "start": G.week_start(wid).isoformat(), "end": (G.week_start(wid) + dt.timedelta(days=6)).isoformat()},
        "previous_week": {"id": ctx.prev, "start": G.week_start(ctx.prev).isoformat(), "end": (G.week_start(ctx.prev) + dt.timedelta(days=6)).isoformat()},
        "baseline": {"weeks": ctx.base, "count": len(ctx.base)},
        "window": {"since": since.isoformat(), "until": until.isoformat(), "weeks": nweeks},
        "currency": currency,
        "rules": strip_comments({k: v for k, v in rules.items() if k != "schema_version"}),
        "inputs": inputs,
        "inputs_hash": h.hexdigest()[:12],
        "sources": health(sources, wid, since, until),
        "metrics": metrics,
        "stage_summary": stage_summary(ctx, metrics),
        "notable": notable(metrics),
        "gsc": gsc_section(ctx, sources),
        "correlations": correlations(ctx, sources, metrics, since, until),
        "actions": actions,
        "previous_experiments": prev_info,
        "experiments_followup": follow,
        "limitations": lims,
    }
    errs = G.schema_errors(pulse, "pulse.schema.json")
    if errs:
        print("error: internal: pulse.json fails its schema:\n  " + "\n  ".join(errs[:10]), file=sys.stderr)
        return 2
    G.write_json(os.path.join(args.out_dir, "pulse.json"), pulse)
    G.write_text(os.path.join(args.out_dir, "pulse-tables.md"), tables_md(pulse) + "\n")
    print(f"pulse {wid}: {len(metrics)} metrics from {len(usable)} source(s) with data, {len(pulse['notable'])} notable, "
          f"{sum(1 for c in pulse['correlations'] if c['label'] == 'correlated')} correlated pair(s), "
          f"{len(follow)} experiment(s) followed up -> {os.path.join(args.out_dir, 'pulse.json')}")
    print(f"inputs_hash {pulse['inputs_hash']}")
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
