#!/usr/bin/env python3
"""
pipeline.py

Runs the deterministic part of a first-users-hunter run in one command, from
collection to the shortlist the model drafts from. Standard library only,
Python 3.9+. Each step is also a script of its own.

    python3 pipeline.py --config CFG --run-dir RUN [--fixtures DIR] [--record DIR]
        [--ledger LEDGER.csv] [--criteria FILE] [--today YYYY-MM-DD] [--only hn,github]

Steps, in order (stops at the first failing one):
  1. collect.py signals      signals.jsonl, cache/, source-health.json
  2. candidates.py           candidates.jsonl, rejected.jsonl
  3. collect.py activity     activity.jsonl, source-health.json
  4. check_activity.py       activity.json
  5. score_people.py         shortlist.jsonl, channels.json, rejected.jsonl

Inputs the founder or the model adds to the run folder before running:
manual-signals.csv, activity-manual.csv (and their text files), identities.json.
Run again after adding them: collected signals are merged by id and cached
pages are kept.

Exit codes: 0 shortlist written, 1 a step failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candidates  # noqa: E402
import check_activity  # noqa: E402
import collect  # noqa: E402
import score_people  # noqa: E402


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--fixtures")
    ap.add_argument("--record")
    ap.add_argument("--ledger")
    ap.add_argument("--criteria")
    ap.add_argument("--today")
    ap.add_argument("--only")
    ap.add_argument("--max", type=int)
    a = ap.parse_args(argv)
    common = ["--config", a.config, "--run-dir", a.run_dir]
    opt = lambda flag, val: [flag, val] if val else []  # noqa: E731
    fetch = opt("--fixtures", a.fixtures) + opt("--record", a.record)
    day = opt("--today", a.today)
    crit = opt("--criteria", a.criteria)
    steps = [
        ("collect signals", collect.main, ["signals"] + common + fetch + day + crit + opt("--only", a.only)),
        ("candidates", candidates.main, common + day + crit + opt("--ledger", a.ledger)),
        ("collect activity", collect.main, ["activity"] + common + fetch + day + crit),
        ("check activity", check_activity.main, common + day + crit),
        ("score", score_people.main, common + day + crit + (["--max", str(a.max)] if a.max else [])),
    ]
    for label, fn, args in steps:
        print(f"\n== {label}")
        code = fn(args)
        if code != 0:
            print(f"pipeline stopped at '{label}' (exit {code})", file=sys.stderr)
            return 1 if code == 1 else code
    print(f"\nshortlist ready: {os.path.join(a.run_dir, 'shortlist.jsonl')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
