#!/usr/bin/env python3
"""
connect_plausible.py

Daily visitors, visits, pageviews and goal conversions from Plausible (cloud or
self-hosted) into the growth-pulse source file (assets/source.schema.json).

Providers, in the order --provider auto tries them:
  csv  the dashboard export (Export > CSV: the zip holds visitors.csv with
       date,visitors,pageviews,visits,...) and optionally a goals file
       (date,event,count) for daily conversions, which the export does not give per day.
  api  Stats API v2: PLAUSIBLE_API_KEY (bearer), PLAUSIBLE_BASE_URL for a self-hosted
       instance (default https://plausible.io), --site-id (the site domain).
       POST /api/v2/query with dimensions time:day, then time:day and event:goal.
  none nothing set: a 'missing' health file with the export instructions.

    python3 connect_plausible.py --today 2026-10-14 --site-id example.com --out <run>/data/plausible.json
    python3 connect_plausible.py --today 2026-10-14 --csv exports/visitors.csv exports/goals.csv --out <run>/data/plausible.json

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("in Plausible, Export > CSV, unzip, pass visitors.csv with --csv; add a date,event,count "
       "file for daily goal conversions")
METRICS = ["visitors", "visits", "pageviews"]


def has_api() -> str:
    return G.env_set("PLAUSIBLE_API_KEY")


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    site = args.site_id or os.environ.get("PLAUSIBLE_SITE_ID")
    if not site and not args.fixtures:
        raise G.InputError("--site-id (or PLAUSIBLE_SITE_ID) is required for the API provider")
    base = os.environ.get("PLAUSIBLE_BASE_URL", "https://plausible.io").rstrip("/")
    headers = {} if args.fixtures else {"authorization": "Bearer " + os.environ.get("PLAUSIBLE_API_KEY", "")}
    rng = [since.isoformat(), until.isoformat()]
    ts = G.http_json(base + "/api/v2/query", key="query-timeseries", fixtures=args.fixtures, headers=headers,
                     body={"site_id": site, "metrics": METRICS, "date_range": rng, "dimensions": ["time:day"]})
    goals = G.http_json(base + "/api/v2/query", key="query-goals", fixtures=args.fixtures, headers=headers,
                        body={"site_id": site, "metrics": ["events"], "date_range": rng,
                              "dimensions": ["time:day", "event:goal"]})
    daily = G.Daily()
    for row in ts.get("results", []):
        day = G.parse_date_cell(str(row["dimensions"][0]))
        daily.touch(day)
        for name, value in zip(METRICS, row.get("metrics", [])):
            daily.add(day, name, G.parse_number(value))
    events = set()
    for row in goals.get("results", []):
        day = G.parse_date_cell(str(row["dimensions"][0]))
        name = G.event_key(str(row["dimensions"][1]))
        events.add(name)
        if day in daily.values:
            daily.add(day, name, G.parse_number(row["metrics"][0]))
    return G.build_source("plausible", "fixture" if args.fixtures else "api", since, until, daily, today=today,
                          fill_zero=sorted(events), notes=["goal conversions = events per goal per day"])


def from_csv(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    daily = G.Daily()
    events = set()
    for path in args.csv:
        rows = G.read_csv(path)
        if not rows:
            continue
        hs = rows[0].keys()
        dcol = G.pick_column(hs, ["date", "day"])
        if not dcol:
            raise G.InputError(f"{path}: no date column")
        ecol = G.pick_column(hs, ["event", "goal", "name", "event name"])
        ccol = G.pick_column(hs, ["count", "events", "conversions", "total_conversions"])
        for r in rows:
            day = G.parse_date_cell(r[dcol], args.date_format)
            if not day or not since <= day <= until:
                continue
            if ecol and ccol:
                name = G.event_key(r[ecol])
                events.add(name)
                daily.add(day, name, G.parse_number(r[ccol]))
                continue
            daily.touch(day)
            for m in METRICS:
                if m in r:
                    daily.add(day, m, G.parse_number(r[m]))
    for day in [d for d, v in daily.values.items() if "visitors" not in v]:
        del daily.values[day]
    return G.build_source("plausible", "csv", since, until, daily, today=today, fill_zero=sorted(events),
                          notes=[f"read {', '.join(os.path.basename(p) for p in args.csv)}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Plausible daily traffic and goals into a growth-pulse source file.")
    G.add_common_args(ap, "visitors.csv of the Plausible export, optional goals CSV (date, event, count)")
    ap.add_argument("--site-id", help="Plausible site id, the domain (or PLAUSIBLE_SITE_ID)")
    ap.add_argument("--date-format", help="strptime format of the CSV date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("plausible", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
