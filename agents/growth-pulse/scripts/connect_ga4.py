#!/usr/bin/env python3
"""
connect_ga4.py

Daily users, sessions, views and chosen events from Google Analytics 4 into the
growth-pulse source file (assets/source.schema.json).

Providers, in the order --provider auto tries them:
  csv  the report export (Reports > Share > Download CSV). Lines starting with '#'
       are skipped; a table with Date and Active users / Sessions / Views columns
       gives the traffic, a table with Date, Event name and Event count gives events.
  api  Data API v1beta: GA4_ACCESS_TOKEN (an OAuth access token with the
       analytics.readonly scope, for example from
       `gcloud auth application-default print-access-token`) and --property-id.
       POST /v1beta/properties/{id}:runReport, dimension date, then date and eventName
       filtered on --events.
  none nothing set: a 'missing' health file with the export instructions.

    python3 connect_ga4.py --today 2026-10-14 --property-id 123456789 --events sign_up,generate_lead --out <run>/data/ga4.json
    python3 connect_ga4.py --today 2026-10-14 --csv exports/ga4-traffic.csv exports/ga4-events.csv --out <run>/data/ga4.json

Metric names: activeUsers -> visitors, sessions -> visits, screenPageViews -> pageviews,
newUsers -> new_users.

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("in GA4, open the report, Share > Download CSV (one table by Date with Active users, Sessions, "
       "Views; one by Date and Event name with Event count) and pass the files with --csv")
API_METRICS = [("activeUsers", "visitors"), ("sessions", "visits"), ("screenPageViews", "pageviews"), ("newUsers", "new_users")]
CSV_METRICS = {"visitors": ["active users", "users", "total users"], "visits": ["sessions"],
               "pageviews": ["views", "screen page views", "page views"], "new_users": ["new users"]}


def has_api() -> str:
    return G.env_set("GA4_ACCESS_TOKEN")


def run_report(args, body: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{args.property_id}:runReport"
    headers = {} if args.fixtures else {"authorization": "Bearer " + os.environ.get("GA4_ACCESS_TOKEN", "")}
    data = G.http_json(url, key=key, fixtures=args.fixtures, headers=headers, body=body)
    return data.get("rows", [])


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    if not args.property_id and not args.fixtures:
        raise G.InputError("--property-id is required for the API provider")
    rng = [{"startDate": since.isoformat(), "endDate": until.isoformat()}]
    daily = G.Daily()
    rows = run_report(args, {"dateRanges": rng, "dimensions": [{"name": "date"}],
                             "metrics": [{"name": m} for m, _ in API_METRICS], "limit": 10000}, "run-report-totals")
    for r in rows:
        day = G.parse_date_cell(r["dimensionValues"][0]["value"])
        daily.touch(day)
        for (_, name), mv in zip(API_METRICS, r.get("metricValues", [])):
            daily.add(day, name, G.parse_number(mv.get("value")))
    events = set()
    wanted = [e.strip() for e in (args.events or "").split(",") if e.strip()]
    if wanted or args.fixtures:
        body = {"dateRanges": rng, "dimensions": [{"name": "date"}, {"name": "eventName"}],
                "metrics": [{"name": "eventCount"}], "limit": 10000}
        if wanted:
            body["dimensionFilter"] = {"filter": {"fieldName": "eventName", "inListFilter": {"values": wanted}}}
        for r in run_report(args, body, "run-report-events"):
            day = G.parse_date_cell(r["dimensionValues"][0]["value"])
            name = G.event_key(r["dimensionValues"][1]["value"])
            events.add(name)
            if day in daily.values:
                daily.add(day, name, G.parse_number(r["metricValues"][0].get("value")))
    return G.build_source("ga4", "fixture" if args.fixtures else "api", since, until, daily, today=today,
                          fill_zero=sorted(events), notes=["visitors = activeUsers per day"])


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
            raise G.InputError(f"{path}: no Date column")
        ecol, ccol = G.pick_column(hs, ["event name", "eventname"]), G.pick_column(hs, ["event count", "eventcount"])
        cols = {m: G.pick_column(hs, a) for m, a in CSV_METRICS.items()}
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
            for m, col in cols.items():
                if col:
                    daily.add(day, m, G.parse_number(r[col]))
    for day in [d for d, v in daily.values.items() if "visitors" not in v]:
        del daily.values[day]
    return G.build_source("ga4", "csv", since, until, daily, today=today, fill_zero=sorted(events),
                          notes=[f"read {', '.join(os.path.basename(p) for p in args.csv)}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GA4 daily traffic and events into a growth-pulse source file.")
    G.add_common_args(ap, "GA4 report CSV exports (traffic by Date, events by Date and Event name)")
    ap.add_argument("--property-id", help="GA4 property id (digits)")
    ap.add_argument("--events", help="comma-separated event names to fetch with the API (key events)")
    ap.add_argument("--date-format", help="strptime format of the CSV date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("ga4", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
