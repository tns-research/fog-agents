#!/usr/bin/env python3
"""
check_activity.py

Proves, for every candidate, that the person publishes now. Standard library
only, Python 3.9+, deterministic, no network.

    python3 check_activity.py --run-dir RUN [--config CFG] [--criteria FILE] [--today YYYY-MM-DD]

Reads <run>/candidates.jsonl, <run>/activity.jsonl (collect.py activity) and
<run>/signals.jsonl. Rules (assets/criteria.json > activity):
  - A post counts when it is the person's own: a LinkedIn post whose URL slug is
    the person's slug (a post where they are only tagged, or a homonym, is
    ignored), an X status under their handle, an API record of their handle.
  - Its date: decoded from the id for LinkedIn and X (the date given by a
    search engine or a CSV is ignored; a gap over date_tolerance_days is
    reported), the API date elsewhere.
  - Window: window_days (LinkedIn: window_days_by_network.linkedin, wider
    because search engines index a fraction of LinkedIn posts).
  - Weight by kind (kind_weights): own posts, comments, issues 1; replies,
    reposts, pushes 0.25. The person's own signals count as posts when
    count_signal_as_post is true. Duplicates (same id or URL) count once.
  - Status: active when the weighted total >= min_weighted_posts; dead_handle
    when every handle checked does not exist (their posts, the signal
    included, no longer count);
    not_proven otherwise. Zero posts found is "not proven", never "inactive".
Only active people go on to score_people.py.

Writes <run>/activity.json (per person: status, weighted_posts, window_days,
last_active_at, active_networks, per network counts, evidence_urls, ignored
records with the reason). Exit codes: 0 ok, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import (InputError, die, load_criteria, load_json, parse_day,  # noqa: E402
                     post_id_date, read_jsonl, today_or, url_owner, write_json)

POST_NETWORKS = {"hn", "github", "reddit", "linkedin", "x", "community", "luma"}


def evaluate(cand: Dict[str, Any], records: List[Dict[str, Any]], signals: Dict[str, Dict[str, Any]],
             act: Dict[str, Any], today) -> Dict[str, Any]:
    weights = act["kind_weights"]
    tol = int(act.get("date_tolerance_days", 1))
    handles = {(i["network"], i["handle"].lower()) for i in cand.get("identities") or []}
    items: List[Dict[str, Any]] = []
    for r in records:
        if (r.get("network"), (r.get("handle") or "").lower()) in handles and r.get("kind") != "handle_check":
            items.append(dict(r))
    if act.get("count_signal_as_post", True):
        for sid in cand.get("signal_ids") or []:
            s = signals.get(sid) or {}
            if s.get("authored") and s.get("network") in POST_NETWORKS and s.get("handle"):
                kind = "event_host" if s.get("signal_type") == "event" else "post"
                items.append({"network": s["network"], "handle": s["handle"], "activity_id": sid,
                              "url": s["url"], "date": s["date"], "date_source": s["date_source"], "kind": kind})
    checks = [r for r in records if r.get("kind") == "handle_check"
              and (r.get("network"), (r.get("handle") or "").lower()) in handles]
    gone = {(c["network"], (c.get("handle") or "").lower()) for c in checks if c.get("status") == "not_found"}

    per_net: Dict[str, Dict[str, Any]] = {}
    ignored, warnings, seen, evidence = [], [], set(), []
    total, last = 0.0, ""
    for it in sorted(items, key=lambda x: (x.get("date") or "", x.get("activity_id") or ""), reverse=True):
        net, url = it.get("network"), it.get("url") or ""
        if (net, (it.get("handle") or "").lower()) in gone:
            ignored.append({"url": url, "reason": f"{net}:{it.get('handle')} no longer exists"})
            continue
        owner = url_owner(url)
        if owner and owner[0] == net and owner[1] != (it.get("handle") or "").lower():
            ignored.append({"url": url, "reason": f"post by {owner[1]}, not {it.get('handle')} (tagged or homonym)"})
            continue
        day = parse_day(it.get("date"))
        id_day = post_id_date(url) if net in ("linkedin", "x") else None
        if id_day:
            if day and abs((day - id_day).days) > tol:
                warnings.append(f"{url}: date {day} disagrees with the post id ({id_day}), id date used")
            day = id_day
        if not day:
            ignored.append({"url": url, "reason": "no date"})
            continue
        window = int((act.get("window_days_by_network") or {}).get(net, act["window_days"]))
        ahead = day > today and it.get("kind") != "event_host"  # an event being organized counts
        if ahead or (today - day).days > window:
            continue
        key = it.get("activity_id") or url
        # Same post reached twice (a signal and its API record): the full URL,
        # fragment included, so two comments of one thread stay two posts.
        ukey = ("url", url.strip().rstrip("/").lower()) if it.get("kind") not in ("push", "other") else ("id", key)
        if key in seen or ukey in seen:
            continue
        seen.update({key, ukey})
        w = float(weights.get(it.get("kind") or "other", weights.get("other", 0)))
        if w <= 0:
            continue
        n = per_net.setdefault(net, {"weighted": 0.0, "posts": 0, "low_weight": 0, "window_days": window,
                                     "last_post_at": ""})
        n["weighted"] = round(n["weighted"] + w, 2)
        n["posts" if w >= 1 else "low_weight"] += 1
        n["last_post_at"] = max(n["last_post_at"], day.isoformat())
        total += w
        last = max(last, min(day, today).isoformat())
        if w >= 1 and len(evidence) < 10:
            evidence.append(url)

    dead = [f"{c['network']}:{c['handle']}" for c in checks if c.get("status") == "not_found"]
    checked = [c for c in checks if c.get("status") in ("ok", "not_found")]
    total = round(total, 2)
    if total >= float(act["min_weighted_posts"]):
        status = "active"
    elif checked and len(dead) == len(checked) and total == 0:
        status = "dead_handle"
    else:
        status = "not_proven"
    return {
        "status": status,
        "weighted_posts": total,
        "window_days": max([n["window_days"] for n in per_net.values()] or [int(act["window_days"])]),
        "last_active_at": last,
        "active_networks": sorted(n for n, v in per_net.items() if v["weighted"] > 0),
        "networks": per_net,
        "evidence_urls": evidence,
        "dead_handles": dead,
        "unchecked": sorted(f"{c['network']}:{c['handle']}: {c.get('status')} {c.get('message', '')}".strip()
                            for c in checks if c.get("status") not in ("ok", "not_found")),
        "ignored": ignored,
        "warnings": warnings,
    }


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config")
    ap.add_argument("--criteria")
    ap.add_argument("--today")
    a = ap.parse_args(argv)
    try:
        conf = load_json(a.config) if a.config else None
        act = load_criteria(a.criteria, conf)["activity"]
        today = today_or(a.today)
        cands = read_jsonl(os.path.join(a.run_dir, "candidates.jsonl"))
        records = read_jsonl(os.path.join(a.run_dir, "activity.jsonl"))
        signals = {s["signal_id"]: s for s in read_jsonl(os.path.join(a.run_dir, "signals.jsonl"))}
    except InputError as e:
        return die(str(e))
    if not cands:
        return die(f"{a.run_dir}/candidates.jsonl is empty or missing: run candidates.py first")
    result = {"today": today.isoformat(), "gate": act["min_weighted_posts"], "people": {}}
    counts: Dict[str, int] = {}
    for c in cands:
        ev = evaluate(c, records, signals, act, today)
        result["people"][c["person_key"]] = ev
        counts[ev["status"]] = counts.get(ev["status"], 0) + 1
        print(f"{c['person_key']}: {ev['status']} ({ev['weighted_posts']} weighted post(s), "
              f"last {ev['last_active_at'] or 'none'})")
    write_json(os.path.join(a.run_dir, "activity.json"), result)
    print(", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + f" -> {os.path.join(a.run_dir, 'activity.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
