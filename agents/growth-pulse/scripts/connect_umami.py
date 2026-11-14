#!/usr/bin/env python3
"""
connect_umami.py

Daily visitors, pageviews and custom events from Umami (Cloud or self-hosted) into
the growth-pulse source file (assets/source.schema.json).

Providers, in the order --provider auto tries them:
  csv  the founder's export: a daily file (date, visitors, pageviews[, visits]) and
       optionally an events file (date, event, count); any column order, comma or
       semicolon. Build it from the dashboard or any export.
  api  Umami Cloud: UMAMI_API_KEY (header x-umami-api-key, base https://api.umami.is/v1)
       Self-hosted:  UMAMI_BASE_URL with UMAMI_USERNAME and UMAMI_PASSWORD (login, then a
       bearer token) or UMAMI_API_TOKEN (an existing bearer token).
       Website id: --website-id or UMAMI_WEBSITE_ID.
       Endpoints: /websites/{id}/pageviews (unit=day: pageviews and sessions, read as
       visitors) and /websites/{id}/events/series (unit=day, one row per event and day).
  none nothing set: a 'missing' health file with the export instructions.

    python3 connect_umami.py --today 2026-10-14 --out <run>/data/umami.json
    python3 connect_umami.py --today 2026-10-14 --csv exports/umami-daily.csv exports/umami-events.csv --out <run>/data/umami.json
    python3 connect_umami.py --today 2026-10-14 --fixtures scripts/fixtures/umami/api --out /tmp/umami.json

Visitors are daily unique visitors; compute_pulse.py sums them per week, so one person
visiting on two days counts twice (the report says so).

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

HOW = ("export the daily visitors and pageviews (and the event counts) to CSV with columns "
       "date,visitors,pageviews and date,event,count, then pass them with --csv")

DATE_COLS = ["date", "day", "x", "t"]
VISITOR_COLS = ["visitors", "unique visitors", "sessions", "uniques"]
VISIT_COLS = ["visits"]
PAGEVIEW_COLS = ["pageviews", "page views", "views"]
EVENT_COLS = ["event", "event name", "event_name", "name"]
COUNT_COLS = ["count", "events", "total", "y"]


def has_api() -> str:
    return G.env_set("UMAMI_API_KEY", "UMAMI_API_TOKEN") or (
        "UMAMI_USERNAME" if os.environ.get("UMAMI_BASE_URL") and os.environ.get("UMAMI_USERNAME") else None)


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    website = args.website_id or os.environ.get("UMAMI_WEBSITE_ID")
    if not website and not args.fixtures:
        raise G.InputError("--website-id or UMAMI_WEBSITE_ID is required for the API provider")
    headers: Dict[str, str] = {}
    if os.environ.get("UMAMI_API_KEY") and not args.fixtures:
        base = os.environ.get("UMAMI_BASE_URL", "https://api.umami.is/v1").rstrip("/")
        headers["x-umami-api-key"] = os.environ["UMAMI_API_KEY"]
    else:
        base = os.environ.get("UMAMI_BASE_URL", "http://localhost:3000").rstrip("/") + "/api"
        token = os.environ.get("UMAMI_API_TOKEN")
        if not token and not args.fixtures:
            login = G.http_json(base + "/auth/login", key="login", fixtures=None,
                                body={"username": os.environ.get("UMAMI_USERNAME", ""),
                                      "password": os.environ.get("UMAMI_PASSWORD", "")})
            token = login.get("token")
            if not token:
                raise G.ProviderError("login answered without a token")
        if token:
            headers["authorization"] = "Bearer " + token
    start_ms = int(dt.datetime.combine(since, dt.time()).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    end_ms = int(dt.datetime.combine(until, dt.time(23, 59, 59)).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    q = f"startAt={start_ms}&endAt={end_ms}&unit=day&timezone={args.timezone}"
    pv = G.http_json(f"{base}/websites/{website}/pageviews?{q}", key="pageviews", fixtures=args.fixtures, headers=headers)
    ev = G.http_json(f"{base}/websites/{website}/events/series?{q}", key="events-series", fixtures=args.fixtures, headers=headers)
    daily = G.Daily()
    for row in pv.get("pageviews", []):
        daily.add(G.parse_date_cell(str(row.get("x", ""))), "pageviews", G.parse_number(row.get("y")))
    for row in pv.get("sessions", []):
        daily.add(G.parse_date_cell(str(row.get("x", ""))), "visitors", G.parse_number(row.get("y")))
    events = set()
    for row in ev if isinstance(ev, list) else ev.get("data", []):
        name = G.event_key(str(row.get("x", "")))
        events.add(name)
        day = G.parse_date_cell(str(row.get("t", "")))
        if day in daily.values:
            daily.add(day, name, G.parse_number(row.get("y")))
    return G.build_source("umami", "fixture" if args.fixtures else "api", since, until, daily, today=today,
                          fill_zero=sorted(events),
                          notes=["visitors = daily sessions from /pageviews (daily unique visitors)"])


def from_csv(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    daily = G.Daily()
    events = set()
    used = []
    for path in args.csv:
        rows = G.read_csv(path)
        if not rows:
            continue
        hs = rows[0].keys()
        dcol = G.pick_column(hs, DATE_COLS)
        if not dcol:
            raise G.InputError(f"{path}: no date column (expected one of {DATE_COLS})")
        ecol, ccol = G.pick_column(hs, EVENT_COLS), G.pick_column(hs, COUNT_COLS)
        if ecol and ccol:
            for r in rows:
                day = G.parse_date_cell(r[dcol], args.date_format)
                if day and since <= day <= until:
                    name = G.event_key(r[ecol])
                    events.add(name)
                    daily.add(day, name, G.parse_number(r[ccol]))
            used.append(f"{os.path.basename(path)} (events)")
            continue
        cols = {"visitors": G.pick_column(hs, VISITOR_COLS), "visits": G.pick_column(hs, VISIT_COLS),
                "pageviews": G.pick_column(hs, PAGEVIEW_COLS)}
        if not cols["visitors"]:
            raise G.InputError(f"{path}: no visitors column (expected one of {VISITOR_COLS})")
        for r in rows:
            day = G.parse_date_cell(r[dcol], args.date_format)
            if day and since <= day <= until:
                daily.touch(day)
                for metric, col in cols.items():
                    if col:
                        daily.add(day, metric, G.parse_number(r[col]))
        used.append(f"{os.path.basename(path)} (daily)")
    # event-only days are not traffic days: keep only days that carry visitors
    for day in [d for d, v in daily.values.items() if "visitors" not in v]:
        del daily.values[day]
    return G.build_source("umami", "csv", since, until, daily, today=today, fill_zero=sorted(events),
                          notes=[f"read {', '.join(used)}"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Umami daily visitors, pageviews and events into a growth-pulse source file.")
    G.add_common_args(ap, "daily CSV (date, visitors, pageviews) and optional events CSV (date, event, count)")
    ap.add_argument("--website-id", help="Umami website id (or UMAMI_WEBSITE_ID)")
    ap.add_argument("--timezone", default="UTC", help="timezone of the daily buckets for the API (default UTC)")
    ap.add_argument("--date-format", help="strptime format of the CSV date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("umami", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
