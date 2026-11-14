#!/usr/bin/env python3
"""
candidates.py

Turns <run>/signals.jsonl into one candidate per person. Standard library
only, Python 3.9+, deterministic.

    python3 candidates.py --run-dir RUN --config CFG [--criteria FILE]
        [--identities RUN/identities.json] [--ledger <project>/first-users-hunter/ledger.csv]
        [--today YYYY-MM-DD]

Per signal:
  eligible       its type is eligible in assets/criteria.json (listed is not)
  in window      age <= max_age_days of its type; an event may lie ahead up to
                 future_horizon_days
  icp keyword    at least one of config icp_keywords in title, text or
                 community (when criteria fit.require_icp_keyword is true)
Per person:
  identities     signals are grouped by <network>:<handle>; the handles a
                 source publishes for the same person (signal links, e.g. a
                 Luma host's LinkedIn) and the groups of identities.json
                 ({"merge": [["hn:a", "x:a"]]}, written by the model from
                 evidence such as a profile linking both) are merged. Nothing
                 is merged on a name alone.
  excluded       the founder's own handles (config founder.handles),
                 config exclude_handles, and the ledger: anyone already
                 approached, and anyone listed before without a newer signal.
A person needs one eligible signal in the window to become a candidate.

Writes <run>/candidates.jsonl and <run>/rejected.jsonl (stage "candidates",
with the reason). Exit codes: 0 ok, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import (InputError, die, load_criteria, load_json, parse_day, person_key,  # noqa: E402
                     read_csv, read_jsonl, today_or, write_jsonl)

PROFILE_URL = {
    "hn": "https://news.ycombinator.com/user?id={}",
    "github": "https://github.com/{}",
    "reddit": "https://www.reddit.com/user/{}",
    "linkedin": "https://www.linkedin.com/in/{}",
    "x": "https://x.com/{}",
    "luma": "https://luma.com/user/{}",
}
APPROACHED = {"approaching", "contacted", "engaged", "connected", "met", "replied", "declined",
              "suppressed", "do_not_contact", "customer"}


class UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def signal_key(s: Dict[str, Any]) -> str:
    if s.get("handle"):
        return person_key(s["network"], s["handle"])
    return f"{s['collector']}:{slug(s.get('author_name', '')) or s['signal_id'].split(':', 1)[1]}"


def window_check(s: Dict[str, Any], rule: Dict[str, Any], today) -> Optional[str]:
    d = parse_day(s.get("date"))
    if not d:
        return "no date"
    age = (today - d).days
    if age < 0:
        ahead = -age
        if s.get("signal_type") == "event" and ahead <= rule.get("future_horizon_days", 0):
            return None
        return f"dated {ahead} day(s) ahead"
    if age > rule["max_age_days"]:
        return f"stale: {age} days old, max {rule['max_age_days']} for {s.get('signal_type')}"
    return None


def icp_hits(s: Dict[str, Any], keywords: List[str]) -> List[str]:
    blob = " ".join([s.get("title", ""), s.get("text", ""), s.get("community", "")]).lower()
    return sorted({k for k in keywords if k and k.lower() in blob})


def load_ledger(path: Optional[str]) -> Dict[str, Dict[str, str]]:
    if not path or not os.path.isfile(path):
        return {}
    return {r["person_key"].lower(): r for r in read_csv(path) if r.get("person_key")}


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--criteria")
    ap.add_argument("--identities", help="Merges written by the model (default: <run>/identities.json when present)")
    ap.add_argument("--ledger", help="ledger.csv of the project (people already listed or approached)")
    ap.add_argument("--today")
    a = ap.parse_args(argv)
    try:
        conf = load_json(a.config)
        crit = load_criteria(a.criteria, conf)
        today = today_or(a.today)
        signals = read_jsonl(os.path.join(a.run_dir, "signals.jsonl"))
        ident_path = a.identities or os.path.join(a.run_dir, "identities.json")
        merges = load_json(ident_path).get("merge", []) if os.path.isfile(ident_path) else []
        ledger = load_ledger(a.ledger)
    except InputError as e:
        return die(str(e))
    if not signals:
        return die(f"{a.run_dir}/signals.jsonl is empty or missing: run collect.py signals first")

    keywords = [k for k in conf.get("icp_keywords") or [] if k]
    require_kw = bool(crit["fit"].get("require_icp_keyword")) and bool(keywords)
    excluded = {person_key(n, h) for n, h in ((conf.get("founder") or {}).get("handles") or {}).items() if h}
    excluded |= {k.lower() for k in conf.get("exclude_handles") or [] if ":" in k}

    uf = UnionFind()
    for s in signals:
        k = signal_key(s)
        uf.find(k)
        for net, h in (s.get("links") or {}).items():
            if net in PROFILE_URL and h:
                uf.union(k, person_key(net, h))
    for group in merges:
        for other in group[1:]:
            uf.union(group[0].lower(), other.lower())

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in signals:
        groups.setdefault(uf.find(signal_key(s)), []).append(s)
    members: Dict[str, set] = {}
    for k in list(uf.parent):
        members.setdefault(uf.find(k), set()).add(k)

    cands, rejected = [], []
    for root in sorted(groups):
        sigs = sorted(groups[root], key=lambda s: (s.get("date", ""), s["signal_id"]), reverse=True)
        keys = sorted(members.get(root, {root}))
        name = next((s.get("author_name") for s in sigs if s.get("author_name")), "") or keys[0].split(":", 1)[1]
        why: List[str] = []
        hit_keys = [k for k in keys if k in excluded]
        if hit_keys:
            rejected.append({"stage": "candidates", "person_key": keys[0], "name": name,
                             "reason": f"excluded handle {hit_keys[0]} (founder or config exclude_handles)"})
            continue
        elig, notes, all_hits = [], [], set()
        for s in sigs:
            rule = crit["signal_types"].get(s.get("signal_type"), {})
            if not rule.get("eligible"):
                notes.append(f"{s['signal_id']}: {s.get('signal_type')} is a seed, not a signal")
                continue
            w = window_check(s, rule, today)
            if w:
                notes.append(f"{s['signal_id']}: {w}")
                continue
            hits = icp_hits(s, keywords)
            # A registry row is selected by the registry query itself (activity
            # code, place): its text holds no ICP words, so the keyword rule
            # does not apply to it.
            if require_kw and not hits and s.get("date_source") != "registry":
                notes.append(f"{s['signal_id']}: no icp keyword")
                continue
            all_hits |= set(hits)
            elig.append(s)
        if not elig:
            rejected.append({"stage": "candidates", "person_key": keys[0], "name": name,
                             "reason": "; ".join(notes) or "no eligible signal"})
            continue
        led = next((ledger[k] for k in keys if k in ledger), None)
        if led:
            status = (led.get("status") or "").lower()
            found = parse_day(led.get("found_on"))
            newest = parse_day(elig[0].get("date"))
            if status in APPROACHED:
                rejected.append({"stage": "candidates", "person_key": keys[0], "name": name,
                                 "reason": f"in ledger with status {status}"})
                continue
            if found and newest and newest <= found:
                rejected.append({"stage": "candidates", "person_key": keys[0], "name": name,
                                 "reason": f"listed on {found.isoformat()}, no newer signal"})
                continue
            why.append(f"listed before on {led.get('found_on')}, new signal since")
        best = elig[0]
        identities = []
        for k in keys:
            net, h = k.split(":", 1)
            if net in PROFILE_URL:
                identities.append({"network": net, "handle": h, "url": PROFILE_URL[net].format(h)})
        first = next((s for s in sigs if s.get("role") or s.get("company")), {})
        cands.append({
            "person_key": signal_key(best),
            "name": name,
            "identities": identities,
            "keys": keys,
            "signal_ids": [s["signal_id"] for s in elig],
            "seed_signal_ids": [s["signal_id"] for s in sigs if s not in elig],
            "icp_hits": sorted(all_hits),
            "role": first.get("role", ""),
            "company": first.get("company", ""),
            "notes": why,
        })
    write_jsonl(os.path.join(a.run_dir, "candidates.jsonl"), cands)
    prev = [r for r in read_jsonl(os.path.join(a.run_dir, "rejected.jsonl")) if r.get("stage") != "candidates"]
    write_jsonl(os.path.join(a.run_dir, "rejected.jsonl"), prev + rejected)
    print(f"{len(cands)} candidate(s), {len(rejected)} rejected at this stage "
          f"-> {os.path.join(a.run_dir, 'candidates.jsonl')}")
    for r in rejected:
        print(f"  rejected {r['person_key']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
