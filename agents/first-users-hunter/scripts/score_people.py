#!/usr/bin/env python3
"""
score_people.py

Scores the active candidates and writes the shortlist the model drafts from.
Standard library only, Python 3.9+, deterministic: the same files give the
same scores and the same order. The model never scores.

    python3 score_people.py --run-dir RUN --config CFG [--criteria FILE] [--max N] [--today YYYY-MM-DD]

Score (assets/criteria.json), per person, from the best eligible signal:
  signal       points of its type (ask 12, switch 10, complaint 9, ...)
  recency      recency_points by age of that signal (an event ahead counts as fresh)
  activity     activity.steps on the weighted posts of activity.json
  networks     multi_network_bonus when active on two networks or more
  icp          icp_keyword_points per keyword hit, capped at icp_keyword_max
  signals      multi_signal_bonus when the person has two eligible signals or more
Best signal: highest type points, then most recent, then signal id.
Order: score, then signal date, then person_key.

Writes <run>/shortlist.jsonl (top --max, default config max_people or
criteria max_people_default, with a suggested person_id p001...),
<run>/channels.json (where the shortlisted people acted: community and
network counts, the base of the channel map) and appends to <run>/rejected.jsonl
(stage activity: not active; stage cut: below the top N).
Exit codes: 0 ok, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import (InputError, clip, die, load_criteria, load_json, parse_day, read_jsonl,  # noqa: E402
                     today_or, write_json, write_jsonl)


def steps(value: float, table: List[List[float]]) -> int:
    pts = 0
    for threshold, p in table:
        if value >= threshold:
            pts = int(p)
    return pts


def recency(age: int, table: List[List[int]]) -> int:
    for max_age, p in table:
        if age <= max_age:
            return int(p)
    return 0


def best_signal(sigs: List[Dict[str, Any]], crit: Dict[str, Any]) -> Dict[str, Any]:
    def key(s: Dict[str, Any]) -> Tuple[int, str, str]:
        return (crit["signal_types"][s["signal_type"]]["points"], s.get("date", ""), s["signal_id"])
    return sorted(sigs, key=key, reverse=True)[0]


def score(cand: Dict[str, Any], sigs: List[Dict[str, Any]], act: Dict[str, Any], crit: Dict[str, Any],
          today) -> Tuple[float, Dict[str, Any], Dict[str, Any]]:
    best = best_signal(sigs, crit)
    age = max(0, (today - parse_day(best["date"])).days)
    a = crit["activity"]
    bd = {
        "signal": crit["signal_types"][best["signal_type"]]["points"],
        "recency": recency(age, crit["recency_points"]),
        "activity": steps(float(act["weighted_posts"]), a["steps"]),
        "networks": a["multi_network_bonus"] if len(act.get("active_networks") or []) >= 2 else 0,
        "icp": min(len(cand.get("icp_hits") or []) * crit["fit"]["icp_keyword_points"], crit["fit"]["icp_keyword_max"]),
        "signals": crit["multi_signal_bonus"] if len(sigs) >= 2 else 0,
    }
    return float(sum(bd.values())), bd, best


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--criteria")
    ap.add_argument("--max", type=int)
    ap.add_argument("--today")
    a = ap.parse_args(argv)
    try:
        conf = load_json(a.config)
        crit = load_criteria(a.criteria, conf)
        today = today_or(a.today)
        cands = read_jsonl(os.path.join(a.run_dir, "candidates.jsonl"))
        signals = {s["signal_id"]: s for s in read_jsonl(os.path.join(a.run_dir, "signals.jsonl"))}
        apath = os.path.join(a.run_dir, "activity.json")
        if not os.path.isfile(apath):
            return die(f"{apath} missing: run check_activity.py first")
        activity = load_json(apath)["people"]
    except InputError as e:
        return die(str(e))
    limit = a.max or int(conf.get("max_people") or crit.get("max_people_default", 20))

    scored, rejected = [], []
    for c in cands:
        act = activity.get(c["person_key"])
        if not act or act["status"] != "active":
            rejected.append({"stage": "activity", "person_key": c["person_key"], "name": c["name"],
                             "reason": f"activity {act['status'] if act else 'not checked'}: "
                                       f"{act['weighted_posts'] if act else 0} weighted post(s), gate "
                                       f"{crit['activity']['min_weighted_posts']}"})
            continue
        sigs = [signals[s] for s in c["signal_ids"] if s in signals]
        if not sigs:
            rejected.append({"stage": "activity", "person_key": c["person_key"], "name": c["name"],
                             "reason": "signals missing from signals.jsonl"})
            continue
        total, bd, best = score(c, sigs, act, crit, today)
        scored.append((total, best["date"], c, bd, best, sigs, act))
    scored.sort(key=lambda t: (-t[0], -int(t[1].replace("-", "")), t[2]["person_key"]))

    shortlist, channels = [], {"communities": {}, "networks": {}}
    for rank, (total, _, c, bd, best, sigs, act) in enumerate(scored, start=1):
        if rank > limit:
            rejected.append({"stage": "cut", "person_key": c["person_key"], "name": c["name"],
                             "reason": f"rank {rank}, below the top {limit} (score {total:g})"})
            continue
        shortlist.append({
            "rank": rank,
            "suggested_person_id": f"p{rank:03d}",
            "person_key": c["person_key"],
            "name": c["name"],
            "role": c.get("role", ""),
            "company": c.get("company", ""),
            "identities": c["identities"],
            "signal": {k: best.get(k, "") for k in ("signal_id", "signal_type", "network", "url", "thread_url",
                                                     "date", "date_source", "community", "title")}
                      | {"text": clip(best.get("text", ""), 2000)},
            "other_signals": [{"signal_id": s["signal_id"], "type": s["signal_type"], "url": s["url"],
                               "date": s["date"]} for s in sigs if s is not best],
            "activity": {k: act[k] for k in ("status", "weighted_posts", "window_days", "last_active_at",
                                             "active_networks", "evidence_urls")},
            "icp_hits": c.get("icp_hits", []),
            "score": total,
            "score_breakdown": bd,
        })
        com = best.get("community") or best.get("network")
        e = channels["communities"].setdefault(com, {"people": 0, "signal_types": {}, "network": best.get("network")})
        e["people"] += 1
        e["signal_types"][best["signal_type"]] = e["signal_types"].get(best["signal_type"], 0) + 1
        for n in act.get("active_networks") or []:
            channels["networks"][n] = channels["networks"].get(n, 0) + 1
    channels["communities"] = dict(sorted(channels["communities"].items(), key=lambda kv: (-kv[1]["people"], kv[0])))
    write_jsonl(os.path.join(a.run_dir, "shortlist.jsonl"), shortlist)
    write_json(os.path.join(a.run_dir, "channels.json"), channels)
    prev = [r for r in read_jsonl(os.path.join(a.run_dir, "rejected.jsonl")) if r.get("stage") not in ("activity", "cut")]
    write_jsonl(os.path.join(a.run_dir, "rejected.jsonl"), prev + rejected)
    for s in shortlist:
        print(f"{s['rank']:>2}. {s['person_key']}: {s['score']:g} {s['score_breakdown']} "
              f"[{s['signal']['signal_type']} {s['signal']['date']}]")
    print(f"{len(shortlist)} shortlisted, {len(rejected)} rejected at this stage "
          f"-> {os.path.join(a.run_dir, 'shortlist.jsonl')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
