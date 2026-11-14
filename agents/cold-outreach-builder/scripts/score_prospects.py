#!/usr/bin/env python3
"""
score_prospects.py

Scores verified prospect dossiers with the criteria grid and assigns a tier.
The model never scores: it writes facts, verify_dossiers.py checks them, this
script applies the grid. Standard library only, Python 3.9+.

    python3 score_prospects.py <run>/dossiers \
        [--criteria <project>/cold-outreach-builder/criteria.json] \
        [--today YYYY-MM-DD] [--out <run>/tiers.json]

Reads <run>/dossiers/<id>/prospect.json and <run>/dossiers/verify.json (run
verify_dossiers.py first). Only facts with status "verified" score; stale and
failed facts never do.

Points (assets/criteria.example.json): best fact per type (capped at
facts_max), recency of the freshest verified fact, role tier, geography,
ICP keywords in verified facts, role and company.

Tiers:
  A  score >= tiers.A.min_score and a strong fact younger than
     freshness.strong_max_age_days: the whole sequence is written for this
     person around that fact.
  B  score >= tiers.B.min_score and at least one verified fact: the shared
     template plus a hook line built on that fact.
  C  everything else, with the reason: no verified fact, a disqualifier, a
     known relationship, a dossier with errors, or a score under B. Never
     exported, listed in the report.

Writes tiers.json (and tiers.csv next to it). Prints one line per prospect.

Exit codes: 0 done, 2 usage error (no verify.json, unreadable criteria).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (ASSETS, InputError, load_json, merged_config,  # noqa: E402
                          parse_day, today_or, write_csv, write_json)

CRITERIA = os.path.join(ASSETS, "criteria.example.json")


def role_points(role: str, grid: Dict[str, Any]) -> Tuple[int, str]:
    text = (role or "").lower()
    for tier in grid.get("tiers", []):
        if any(p.lower() in text for p in tier.get("patterns", [])):
            return int(tier["points"]), tier.get("label", "")
    return 0, "none"


def recency_points(age: Optional[int], grid: Dict[str, Any]) -> int:
    if age is None:
        return 0
    for step in grid.get("steps", []):
        if age <= step["max_days"]:
            return int(step["points"])
    return 0


def score_one(pid: str, data: Dict[str, Any], ver: Dict[str, Any], crit: Dict[str, Any], today) -> Dict[str, Any]:
    name = " ".join(x for x in (data.get("first_name", ""), data.get("last_name", "")) if x)
    out: Dict[str, Any] = {"prospect_id": pid, "name": name, "company": data.get("company", ""),
                           "score": 0, "tier": "C", "reasons": [], "breakdown": {},
                           "best_fact_id": "", "best_fact_type": "", "best_fact_date": "", "best_fact_url": ""}
    if ver.get("status") != "ok":
        out["reasons"].append("dossier has verification errors: fix and re-run verify_dossiers.py")
        return out

    facts = {f["id"]: f for f in data.get("facts") or [] if isinstance(f, dict) and "id" in f}
    checked = ver.get("facts", {})
    verified = [facts[fid] for fid, r in checked.items() if r.get("status") == "verified" and fid in facts]
    types = crit.get("fact_types", {})
    fresh = crit.get("freshness", {})
    strong_max = int(fresh.get("strong_max_age_days", 120))

    def age(f: Dict[str, Any]) -> Optional[int]:
        d = parse_day(f.get("date", ""))
        return (today - d).days if d else None

    best_by_type: Dict[str, int] = {}
    for f in verified:
        pts = int(types.get(f.get("type"), types.get("other", {"points": 0})).get("points", 0))
        best_by_type[f["type"]] = max(best_by_type.get(f["type"], 0), pts)
    b = out["breakdown"]
    b["facts"] = min(int(crit.get("facts_max", 40)), sum(best_by_type.values()))
    ages = [a for a in (age(f) for f in verified) if a is not None]
    b["recency"] = recency_points(min(ages) if ages else None, crit.get("recency", {}))
    rp, rlabel = role_points(data.get("role", ""), crit.get("role", {}))
    b["role"] = min(int(crit.get("role", {}).get("max", 25)), rp)
    b["role_tier"] = rlabel

    geo = crit.get("geography", {})
    g = (data.get("geography") or "").lower()
    pts = geo.get("points", {})
    b["geography"] = int(pts.get("unknown", 0) if not g else pts.get("target", 0) if g in geo.get("target", []) else pts.get("other", 0))

    kw = crit.get("icp_keywords", {})
    corpus = " ".join([data.get("role", ""), data.get("company", "")] +
                      [f.get("claim", "") + " " + f.get("excerpt", "") for f in verified]).lower()
    hits = sum(1 for k in kw.get("keywords", []) if k.lower() in corpus)
    b["icp_keywords"] = min(int(kw.get("max", 10)), hits * int(kw.get("points_per_hit", 5)))

    score = b["facts"] + b["recency"] + b["role"] + b["geography"] + b["icp_keywords"]
    out["score"] = score

    # Best hook candidate: strong and fresh first, then most points, then freshest.
    def rank(f: Dict[str, Any]):
        t = types.get(f.get("type"), {})
        a = age(f)
        strong_fresh = bool(t.get("strong")) and a is not None and a <= strong_max
        return (strong_fresh, int(t.get("points", 0)), -(a if a is not None else 10 ** 6))
    best = max(verified, key=rank) if verified else None
    if best:
        out.update({"best_fact_id": best["id"], "best_fact_type": best.get("type", ""),
                    "best_fact_date": best.get("date", ""), "best_fact_url": best.get("source_url", "")})

    excl = crit.get("exclude", {})
    rel = data.get("relationship", "none")
    if rel in excl.get("relationships", []):
        out["reasons"].append(f"relationship {rel}: the founder writes to this person directly")
        return out
    if data.get("disqualifiers"):
        out["reasons"].append("disqualified: " + "; ".join(d.get("reason", "") for d in data["disqualifiers"]))
        return out
    if not verified:
        out["reasons"].append("no verified fact inside the freshness window: nothing true and recent to open on")
        return out

    tiers = crit.get("tiers", {})
    a_rule, b_rule = tiers.get("A", {}), tiers.get("B", {})
    has_strong = best is not None and rank(best)[0]
    if score >= int(a_rule.get("min_score", 65)) and (has_strong or not a_rule.get("requires_strong_fact", True)):
        out["tier"] = "A"
        out["reasons"].append(f"score {score}, strong fact {best['id']} ({best.get('type')}, {best.get('date')})")
    elif score >= int(b_rule.get("min_score", 35)):
        out["tier"] = "B"
        why = "no strong fact under the strong window" if not has_strong else f"score under {a_rule.get('min_score')}"
        out["reasons"].append(f"score {score}, {why}; hook on {best['id']}")
    else:
        out["reasons"].append(f"score {score} under {b_rule.get('min_score')}")
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossiers", help="Folder holding <prospect_id>/prospect.json and verify.json")
    ap.add_argument("--criteria", help="Project criteria.json merged over assets/criteria.example.json")
    ap.add_argument("--verify", help="verify.json path (default: <dossiers>/verify.json)")
    ap.add_argument("--today", help="Reference date, YYYY-MM-DD (default: today)")
    ap.add_argument("--out", help="Output path (default: <dossiers>/../tiers.json)")
    a = ap.parse_args(argv)
    try:
        today = today_or(a.today)
        crit = merged_config(CRITERIA, a.criteria)
        vpath = a.verify or os.path.join(a.dossiers, "verify.json")
        if not os.path.isfile(vpath):
            raise InputError(f"{vpath} not found: run verify_dossiers.py first")
        ver = load_json(vpath)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    results: List[Dict[str, Any]] = []
    for pid, v in sorted(ver.get("prospects", {}).items()):
        path = os.path.join(a.dossiers, pid, "prospect.json")
        try:
            data = load_json(path) if os.path.isfile(path) else {}
        except InputError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        results.append(score_one(pid, data, v, crit, today))

    out_path = a.out or os.path.join(os.path.dirname(os.path.abspath(a.dossiers)), "tiers.json")
    counts = {t: sum(1 for r in results if r["tier"] == t) for t in "ABC"}
    write_json(out_path, {"today": today.isoformat(), "counts": counts, "prospects": results})
    cols = ["prospect_id", "name", "company", "tier", "score", "best_fact_id", "best_fact_type",
            "best_fact_date", "best_fact_url", "reasons"]
    write_csv(os.path.splitext(out_path)[0] + ".csv", cols,
              [dict(r, reasons=" | ".join(r["reasons"])) for r in results])
    for r in results:
        print(f"{r['prospect_id']}: tier {r['tier']}, score {r['score']} ({'; '.join(r['reasons'])})")
    print(f"\ntiers: A {counts['A']}, B {counts['B']}, C {counts['C']} -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
