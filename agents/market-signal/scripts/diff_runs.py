#!/usr/bin/env python3
"""diff_runs.py: what changed between two market-signal runs (watch mode).

  python3 scripts/diff_runs.py --previous PROJECT/market-signal/runs/20260713 \
      --current PROJECT/market-signal/runs/20261012 [--out-json changes.json] [--out-md changes.md]

Reads stats.json (and health.json when present) of each run folder; a path to
a stats.json works too. Pains match by pain_id, plus the aliases listed in the
current analysis.json (a renamed pain keeps its history).

Per pain, distinct authors are scaled to a 30-day rate so windows of different
lengths compare:
  new           absent from the previous run, present now
  disappeared   present before, no voice now
  rising        rate at least --rise-ratio times the previous one and at least
                --min-delta authors more (scaled)
  falling       the other way round
  stable        anything else
plus newly_escalated and no_longer_escalated against the validity threshold.
A pain whose volume is a lower bound in either run (a collector hit its cap)
is flagged lower_bound: its direction is a hint, not a measure.

Also: collector health that changed (ok to error, quota, empty and back), jobs
added or dropped, competitors named for the first time or no longer named.

Exit 0 written, 2 on unreadable input.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M


def load_run(path: Path) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    folder = path.parent if path.is_file() else path
    stats = M.read_json(path if path.is_file() else path / "stats.json")
    health = M.read_json(folder / "health.json") if (folder / "health.json").exists() else None
    analysis = M.read_json(folder / "analysis.json") if (folder / "analysis.json").exists() else None
    return stats, health, analysis


def rate(authors: int, days: int) -> float:
    return authors * 30.0 / max(days, 1)


def diff(prev: Dict[str, Any], cur: Dict[str, Any], prev_health=None, cur_health=None, cur_analysis=None,
         rise_ratio: float = 1.5, min_delta: float = 2.0) -> Dict[str, Any]:
    alias = {}
    for p in (cur_analysis or {}).get("pains", []):
        for a in p.get("aliases") or []:
            alias[a] = p["pain_id"]
    pp = {}
    for p in prev.get("pains", []):
        pp[alias.get(p["pain_id"], p["pain_id"])] = p
    cp = {p["pain_id"]: p for p in cur.get("pains", [])}
    dp, dc = prev["window"]["days"], cur["window"]["days"]
    rows = []
    for pid in sorted(set(pp) | set(cp)):
        a, b = pp.get(pid), cp.get(pid)
        pa, ca = (a or {}).get("distinct_authors", 0), (b or {}).get("distinct_authors", 0)
        ra, rb = rate(pa, dp), rate(ca, dc)
        if pa == 0 and ca > 0:
            status = "new"
        elif pa > 0 and ca == 0:
            status = "disappeared"
        elif pa == 0 and ca == 0:
            status = "absent"
        elif rb >= ra * rise_ratio and rb - ra >= min_delta:
            status = "rising"
        elif ra >= rb * rise_ratio and ra - rb >= min_delta:
            status = "falling"
        else:
            status = "stable"
        esc_a, esc_b = bool((a or {}).get("escalated")), bool((b or {}).get("escalated"))
        rows.append({
            "pain_id": pid, "status": status,
            "previous": {"distinct_authors": pa, "per_30_days": round(ra, 1), "escalated": esc_a},
            "current": {"distinct_authors": ca, "per_30_days": round(rb, 1), "escalated": esc_b},
            "newly_escalated": esc_b and not esc_a, "no_longer_escalated": esc_a and not esc_b,
            "lower_bound": (a or {}).get("volume") == "lower_bound" or (b or {}).get("volume") == "lower_bound",
        })
    order = {"new": 0, "rising": 1, "disappeared": 2, "falling": 3, "stable": 4, "absent": 5}
    rows.sort(key=lambda r: (order[r["status"]], -r["current"]["distinct_authors"], r["pain_id"]))
    rows = [r for r in rows if r["status"] != "absent"]

    sources = []
    if prev_health and cur_health:
        ph = {j["job_id"]: j for j in prev_health.get("jobs", [])}
        ch = {j["job_id"]: j for j in cur_health.get("jobs", [])}
        for jid in sorted(set(ph) | set(ch)):
            s0 = ph.get(jid, {}).get("status", "absent")
            s1 = ch.get(jid, {}).get("status", "absent")
            if s0 != s1:
                sources.append({"job_id": jid, "previous": s0, "current": s1,
                                "message": ch.get(jid, {}).get("message", "")})
    pc = {c["name"] for c in prev.get("competitors", [])}
    cc = {c["name"] for c in cur.get("competitors", [])}
    pb = {x["phrase"] for x in prev.get("language_bank", [])}
    return {
        "schema_version": "2.0",
        "previous_window": prev["window"], "current_window": cur["window"],
        "rules": {"rise_ratio": rise_ratio, "min_delta_per_30_days": min_delta},
        "pains": rows,
        "summary": {s: [r["pain_id"] for r in rows if r["status"] == s] for s in ("new", "rising", "falling", "disappeared", "stable")},
        "newly_escalated": [r["pain_id"] for r in rows if r["newly_escalated"]],
        "no_longer_escalated": [r["pain_id"] for r in rows if r["no_longer_escalated"]],
        "sources": sources,
        "competitors": {"new": sorted(cc - pc), "gone": sorted(pc - cc)},
        "new_phrases": [x["phrase"] for x in cur.get("language_bank", []) if x["phrase"] not in pb],
    }


def to_md(ch: Dict[str, Any]) -> str:
    pw, cw = ch["previous_window"], ch["current_window"]
    out = [f"# Changes since the last run", "",
           f"Previous window {pw['since']} to {pw['until']}, current window {cw['since']} to {cw['until']}. "
           f"Counts are distinct authors, scaled to 30 days. A pain marked (lower bound) came partly from a "
           f"collector that hit its cap: its direction is a hint.", "",
           "| Pain | Change | Before (per 30 days) | Now (per 30 days) | Escalated |", "|---|---|---|---|---|"]
    for r in ch["pains"]:
        esc = "newly" if r["newly_escalated"] else ("no longer" if r["no_longer_escalated"] else
                                                    ("yes" if r["current"]["escalated"] else "no"))
        lb = " (lower bound)" if r["lower_bound"] else ""
        out.append(f"| `{r['pain_id']}` | {r['status']}{lb} | {r['previous']['distinct_authors']} "
                   f"({r['previous']['per_30_days']}) | {r['current']['distinct_authors']} ({r['current']['per_30_days']}) | {esc} |")
    out.append("")
    if ch["sources"]:
        out += ["## Collectors whose health changed", "",
                "A collector that failed or came back empty in one run lowers that run's counts: read the table above against this list.", ""]
        out += [f"- `{s['job_id']}`: {s['previous']} to {s['current']}" + (f" ({s['message']})" if s["message"] else "")
                for s in ch["sources"]]
        out.append("")
    if ch["competitors"]["new"] or ch["competitors"]["gone"]:
        out += ["## Alternatives named", "",
                f"- Named for the first time: {', '.join(ch['competitors']['new']) or 'none'}",
                f"- No longer named: {', '.join(ch['competitors']['gone']) or 'none'}", ""]
    if ch["new_phrases"]:
        out += ["## New recurring phrases", ""] + [f"- {p}" for p in ch["new_phrases"]] + [""]
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--previous", required=True, help="previous run folder or its stats.json")
    p.add_argument("--current", required=True, help="current run folder or its stats.json")
    p.add_argument("--rise-ratio", type=float, default=1.5)
    p.add_argument("--min-delta", type=float, default=2.0)
    p.add_argument("--out-json", help="default <current run>/changes.json")
    p.add_argument("--out-md", help="default <current run>/changes.md")
    args = p.parse_args(argv)
    try:
        prev, ph, _ = load_run(Path(args.previous))
        cur, chh, ca = load_run(Path(args.current))
    except (OSError, ValueError, KeyError) as e:
        M.eprint(f"diff_runs: {e}")
        return 2
    ch = diff(prev, cur, ph, chh, ca, args.rise_ratio, args.min_delta)
    folder = Path(args.current) if Path(args.current).is_dir() else Path(args.current).parent
    M.write_json(Path(args.out_json) if args.out_json else folder / "changes.json", ch)
    md = Path(args.out_md) if args.out_md else folder / "changes.md"
    md.write_text(to_md(ch) + "\n", encoding="utf-8")
    s = ch["summary"]
    print("diff_runs: " + ", ".join(f"{k} {len(v)}" for k, v in s.items())
          + f"; newly escalated: {', '.join(ch['newly_escalated']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
