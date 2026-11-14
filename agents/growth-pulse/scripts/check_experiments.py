#!/usr/bin/env python3
"""
check_experiments.py

Fills and checks the experiments handoff (assets/experiments.schema.json), the input
of the next sprint. The model writes the experiments (stage, hypothesis, change,
metric, threshold, duration, cost, owner, evidence); this script writes every measured
figure from pulse.json, so none is typed:

  --fill   baseline.value of each experiment (the metric's 4-week mean or report-week
           value), the readout (can the threshold be told from noise in that duration?),
           followup (last run's verdicts), budget totals, week and pulse reference.

Then it checks, with assets/pulse-rules.json (experiments) and the project config:

  BLOCK  schema           the file fails assets/experiments.schema.json
  BLOCK  count            not exactly experiments.count experiments
  BLOCK  duplicate-id     two experiments share an id
  BLOCK  unknown-metric   a metric id absent from pulse.json (use new:<id> for a metric to instrument)
  BLOCK  baseline         a baseline that differs from pulse.json (run --fill)
  BLOCK  duration         duration_days outside [min_duration_days, max_duration_days]
  BLOCK  start-date       an experiment that starts before the file's date
  BLOCK  spend-gate       cash_eur > 0 without spend_requires_approval
  BLOCK  over-budget      total cash above config budget_eur_per_sprint
  BLOCK  bad-evidence     an evidence reference that does not resolve in pulse.json
  BLOCK  unknown-number   a number in a title, hypothesis, change or kill criterion that is
                          neither in pulse.json nor in the experiment's own fields
  BLOCK  stale-pulse      pulse.inputs_hash differs from the pulse.json given
  BLOCK  followup         followup differs from pulse.json experiments_followup (run --fill)
  WARN   stages           fewer distinct stages than min_distinct_stages (no focus_stage in config)
  WARN   stage-mismatch   the metric belongs to another AARRR stage than the experiment
  WARN   undetectable     the threshold sits inside the noise for that duration
  WARN   no-lift          the threshold asks for no change against the baseline, or the wrong way
  WARN   new-metric       a metric to instrument before the experiment can be read

    python3 check_experiments.py <project>/growth-pulse/experiments-20261014.json --pulse <run>/pulse.json --fill
    python3 check_experiments.py experiments.json --pulse pulse.json --config <project>/growth-pulse/config.json --json
    python3 check_experiments.py experiments.json --pulse pulse.json --md      # markdown block for the report

Exit codes: 0 no BLOCK, 1 at least one BLOCK, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402
import check_report as CR  # noqa: E402

USAGE = ("Input of the next sprint. Each experiment is a hypothesis to test, never a finding: run it as written, "
         "record the start date, let the next growth-pulse run judge it from its metric. Spending needs the founder's "
         "approval first (spend_requires_approval).")


def metric_map(pulse: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {m["id"]: m for m in pulse["metrics"]}


def spread_of(m: Dict[str, Any], pulse: Dict[str, Any]) -> Optional[float]:
    base = set(pulse["baseline"]["weeks"])
    vals = [s["value"] for s in m["series"] if s["week"] in base and s["value"] is not None]
    if len(vals) < pulse["rules"]["noise"]["min_weeks_for_spread"]:
        return None
    mu = sum(vals) / len(vals)
    return math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1))


def readout(e: Dict[str, Any], m: Optional[Dict[str, Any]], pulse: Dict[str, Any]) -> Dict[str, Any]:
    rules = pulse["rules"]
    z, n_min = rules["noise"]["z"], rules["volume"]["min_events_for_pct"]
    if m is None:
        return {"detectable": None, "noise_band_per_week": None, "reason": "metric to instrument first: no baseline to read against"}
    b = e["baseline"]["value"]
    weeks = max(1, e["duration_days"] // 7)
    k = max(1, m["baseline_weeks_used"])
    thr = e["success_threshold"]
    per_week = thr["value"] if thr["per"] == "week" else thr["value"] / weeks
    if m["kind"] == "count" and b is not None:
        sd = math.sqrt(max(b, 0.0) * (1.0 / weeks + 1.0 / k))
        sp = spread_of(m, pulse)
        if sp is not None:
            sd = max(sd, sp * math.sqrt(1.0 / weeks + 1.0 / k))
        band = z * sd
        ok = abs(per_week - b) > band
        return {"detectable": ok, "noise_band_per_week": G.rnd(band, 1),
                "reason": (f"the target is outside the noise band of the weekly mean over {e['duration_days']} days" if ok else
                           f"the target sits inside the noise band of {e['duration_days']} days: lengthen the test, pick a bigger lever or a metric with more volume")}
    if m["kind"] == "rate":
        den = m["counts"]["baseline"]["denominator"]
        num = m["counts"]["baseline"]["numerator"]
        if not den or num is None or b is None:
            return {"detectable": False, "noise_band_per_week": None,
                    "reason": f"under {n_min} events in the reference weeks: no rate to read against, use a count target"}
        p0 = num / den
        n1 = den / k * weeks
        exp_events = p0 * n1
        se = math.sqrt(max(p0 * (1 - p0), 1e-9) * (1.0 / n1 + 1.0 / den)) * 100.0
        band = z * se
        ok = exp_events >= n_min and abs(per_week - b) > band
        reason = (f"enough events expected over {e['duration_days']} days to read the rate" if exp_events >= n_min
                  else f"fewer than {n_min} events expected over {e['duration_days']} days: the rate cannot be read, use a count target")
        return {"detectable": ok, "noise_band_per_week": G.rnd(band, 1), "reason": reason}
    return {"detectable": None, "noise_band_per_week": None, "reason": f"not assessed for a {m['kind']} metric"}


def resolve_evidence(ref: str, pulse: Dict[str, Any]) -> bool:
    kind, _, key = ref.partition("/")
    if kind == "metrics":
        return key in metric_map(pulse)
    if kind == "correlations":
        return any(c["id"] == key for c in pulse["correlations"])
    if kind == "gsc":
        g = pulse["gsc"]
        if key == "totals":
            return bool(g["available"])
        sub, _, k2 = key.partition("/")
        return sub in ("queries", "pages") and any(r.get("key") == k2 for r in g[sub])
    if kind == "sources":
        return any(s["source"] == key for s in pulse["sources"])
    if kind == "followup":
        return any(f["id"] == key for f in pulse["experiments_followup"])
    if kind == "actions":
        return any(a["date"] == key for a in pulse["actions"])
    return False


def fill(doc: Dict[str, Any], pulse: Dict[str, Any], pulse_path: str) -> None:
    ms = metric_map(pulse)
    doc["week"] = dict(pulse["week"])
    doc["project"] = doc.get("project") or pulse["project"]
    doc["pulse"] = {"file": os.path.basename(pulse_path), "inputs_hash": pulse["inputs_hash"]}
    for e in doc["experiments"]:
        mid = e["metric"]["id"]
        m = None if mid.startswith("new:") else ms.get(mid)
        if mid.startswith("new:"):
            e["baseline"] = {"value": None, "basis": "none"}
        elif m:
            basis = e.get("baseline", {}).get("basis") or "4-week mean"
            basis = "4-week mean" if basis == "none" else basis
            e["baseline"] = {"value": m["baseline"] if basis == "4-week mean" else m["current"], "basis": basis}
        e["readout"] = readout(e, m, pulse)
    doc["followup"] = pulse["experiments_followup"]
    cash = sum(float(e["cost"]["cash_eur"]) for e in doc["experiments"])
    doc["budget"] = {"cash_eur_total": G.rnd(cash, 2), "hours_total": G.rnd(sum(float(e["cost"]["hours"]) for e in doc["experiments"]), 1),
                     "requires_approval": any(e["cost"]["spend_requires_approval"] or e["cost"]["cash_eur"] > 0 for e in doc["experiments"])}
    doc["usage"] = USAGE


def own_numbers(e: Dict[str, Any]) -> set:
    vals = set()
    for _, v in CR.walk(e):
        if CR.is_num(v):
            vals.add(abs(float(v)))
    return vals


def check(doc: Dict[str, Any], pulse: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def add(level, code, where, message):
        out.append({"level": level, "code": code, "where": where, "message": message})

    errs = G.schema_errors(doc, "experiments.schema.json")
    if errs:
        for e in errs[:10]:
            add("BLOCK", "schema", "file", e)
        return out
    R = pulse["rules"]["experiments"]
    exps = doc["experiments"]
    if len(exps) != R["count"]:
        add("BLOCK", "count", "experiments", f"{len(exps)} experiment(s), the sprint takes exactly {R['count']}")
    ids = [e["id"] for e in exps]
    for i in sorted({i for i in ids if ids.count(i) > 1}):
        add("BLOCK", "duplicate-id", i, "ids must be unique")
    if doc["pulse"]["inputs_hash"] != pulse["inputs_hash"]:
        add("BLOCK", "stale-pulse", "pulse", "built on another pulse.json: run --fill against this week's file")
    if doc["followup"] != pulse["experiments_followup"]:
        add("BLOCK", "followup", "followup", "differs from pulse.json experiments_followup: run --fill")
    ms = metric_map(pulse)
    nums, _ = CR.allowed_values(pulse, None)
    gen = dt.date.fromisoformat(doc["generated_on"])
    for e in exps:
        where = e["id"]
        mid = e["metric"]["id"]
        m = ms.get(mid)
        if mid.startswith("new:"):
            add("WARN", "new-metric", where, f"{mid[4:]} must be tracked before the experiment starts; its first task is the tracking")
        elif not m:
            add("BLOCK", "unknown-metric", where, f"{mid} is not a metric of pulse.json (new:<id> for a metric to instrument)")
        if m:
            want = m["baseline"] if e["baseline"]["basis"] == "4-week mean" else m["current"]
            if e["baseline"]["basis"] == "none" or e["baseline"]["value"] != want:
                add("BLOCK", "baseline", where, f"baseline must be {want} ({e['baseline']['basis']} of {mid}): run --fill")
            if m["stage"] != e["stage"]:
                add("WARN", "stage-mismatch", where, f"{mid} is a {m['stage']} metric, the experiment is {e['stage']}")
            b, thr = e["baseline"]["value"], e["success_threshold"]
            if b is not None and m["kind"] in ("count", "rate", "currency", "position"):
                weeks = max(1, e["duration_days"] // 7)
                per_week = thr["value"] if thr["per"] == "week" else thr["value"] / weeks
                better_up = m["direction"] == "up"
                asks_more = thr["comparator"] == ">="
                if asks_more != better_up or (asks_more and per_week <= b) or (not asks_more and per_week >= b):
                    add("WARN", "no-lift", where, f"threshold {thr['comparator']} {thr['value']} per {thr['per']} against a baseline of {b}: no improvement asked")
            if e["readout"]["detectable"] is False:
                add("WARN", "undetectable", where, e["readout"]["reason"])
        if not R["min_duration_days"] <= e["duration_days"] <= R["max_duration_days"]:
            add("BLOCK", "duration", where, f"{e['duration_days']} days, allowed {R['min_duration_days']} to {R['max_duration_days']}")
        if dt.date.fromisoformat(e["start_date"]) < gen:
            add("BLOCK", "start-date", where, f"starts {e['start_date']}, before the file date {doc['generated_on']}")
        if e["cost"]["cash_eur"] > 0 and not e["cost"]["spend_requires_approval"]:
            add("BLOCK", "spend-gate", where, "any cash spend waits for the founder's approval: set spend_requires_approval")
        for ref in e["evidence"]:
            if not resolve_evidence(ref, pulse):
                add("BLOCK", "bad-evidence", where, f"{ref} does not resolve in pulse.json")
        pool = nums | own_numbers(e)
        for field in ("title", "hypothesis", "change", "kill_criterion"):
            text, _ = CR.clean_line(str(e.get(field, "")))
            for mt in CR.NUM_RE.finditer(text):
                whole, dec, kilo = mt.group(1), mt.group(2), mt.group(3)
                value = float(whole.replace(",", "") + ("." + dec if dec else ""))
                if not CR.matches(value, len(dec) if dec else 0, bool(kilo), pool):
                    add("BLOCK", "unknown-number", f"{where}.{field}", f"{mt.group(0).strip()!r} is not in pulse.json nor in the experiment's fields")
    stages = {e["stage"] for e in exps}
    if not config.get("focus_stage") and len(stages) < R["min_distinct_stages"]:
        add("WARN", "stages", "experiments", f"{len(stages)} stage(s) only: spread the bets unless config.focus_stage pins one")
    budget = config.get("budget_eur_per_sprint")
    cash = sum(float(e["cost"]["cash_eur"]) for e in exps)
    if budget is not None and cash > float(budget):
        add("BLOCK", "over-budget", "budget", f"{cash} EUR planned, budget_eur_per_sprint is {budget}")
    return out


def to_md(doc: Dict[str, Any], pulse: Dict[str, Any]) -> str:
    ms = metric_map(pulse)
    L = []
    for e in doc["experiments"]:
        thr, c = e["success_threshold"], e["cost"]
        m = ms.get(e["metric"]["id"])
        unit = "%" if m and m["kind"] == "rate" else (" " + thr["unit"] if thr["unit"] else "")
        base = "none yet (metric to instrument)" if e["baseline"]["value"] is None else f"{e['baseline']['value']:g}{'%' if unit == '%' else ''} ({e['baseline']['basis']})"
        L += [f"#### {e['id']}: {e['title']} ({e['stage']})", "",
              f"- Hypothesis: {e['hypothesis']}",
              f"- Change: {e['change']} Owner: {e['owner']}, channel: {e['channel']}.",
              f"- Metric: {e['metric']['label']}, baseline {base}.",
              f"- Success: {thr['comparator']} {thr['value']:g}{unit} {'per week' if thr['per'] == 'week' else 'in total'}, over {e['duration_days']} days from {e['start_date']}.",
              f"- Readout: {e['readout']['reason']}.",
              f"- Cost: {c['cash_eur']:g} EUR cash, {c['hours']:g} hour{'' if c['hours'] == 1 else 's'}" + (", spend waits for approval." if c["spend_requires_approval"] else "."),
              ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fill the measured fields of the experiments handoff from pulse.json, then check it.")
    ap.add_argument("experiments", help="experiments-<YYYYMMDD>.json")
    ap.add_argument("--pulse", required=True, help="pulse.json of the run")
    ap.add_argument("--config", help="<project>/growth-pulse/config.json (focus_stage, budget_eur_per_sprint)")
    ap.add_argument("--fill", action="store_true", help="write baselines, readouts, follow-up and budget into the file, then check")
    ap.add_argument("--md", action="store_true", help="print the experiments as a markdown block for the report")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    args = ap.parse_args(argv)
    try:
        doc = G.read_json(args.experiments)
        pulse = G.read_json(args.pulse)
        config = G.read_json(args.config) if args.config else {}
        if args.fill:
            fill(doc, pulse, args.pulse)
            G.write_json(args.experiments, doc)
    except (G.InputError, KeyError, TypeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = check(doc, pulse, config)
    blocks = [f for f in findings if f["level"] == "BLOCK"]
    if args.md and not blocks:
        print(to_md(doc, pulse))
        return 0
    if args.json:
        print(json.dumps({"status": "fail" if blocks else "pass", "block": len(blocks), "warn": len(findings) - len(blocks),
                          "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{f['level']} {f['code']} {f['where']}: {f['message']}")
        print(f"check_experiments: {'fail' if blocks else 'pass'}, {len(blocks)} BLOCK, {len(findings) - len(blocks)} WARN")
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
