#!/usr/bin/env python3
"""
connect_gsc.py

Daily Search Console clicks, impressions and position, plus weekly query and page
rows, into the growth-pulse source file (assets/source.schema.json).

Providers, in the order --provider auto tries them:
  csv  the Performance export of the Search Console UI (Export > CSV, the zip holds
       Dates.csv): Date, Clicks, Impressions, CTR, Position, headers in English,
       French, German, Spanish or Italian. Totals only: the UI export has no query or
       page by date, so query and page declines are not computed.
       --csv also takes API-shaped JSON files written by another tool (the gsc CLI of
       cli-skills, a script of the founder): {"dimensions": ["date", "query"], "rows":
       [{"keys": [...], "clicks", "impressions", "ctr", "position"}]}; the provider is
       then reported as json.
  api  Search Console API: GSC_ACCESS_TOKEN (an OAuth access token with the
       webmasters.readonly scope) and --site-url (sc-domain:example.com or
       https://example.com/). POST searchAnalytics/query with dimensions date, then
       date+query and date+page (rowLimit 25000, dataState final).
  none nothing set: a 'missing' health file with the export instructions.

    python3 connect_gsc.py --today 2026-10-14 --site-url sc-domain:example.com --out <run>/data/gsc.json
    python3 connect_gsc.py --today 2026-10-14 --csv exports/Dates.csv --out <run>/data/gsc.json
    python3 connect_gsc.py --today 2026-10-14 --csv exports/gsc-date.json exports/gsc-date-query.json --out <run>/data/gsc.json

Position travels as position_weighted = position x impressions, so compute_pulse.py can
average it over a week weighted by impressions. Search Console data arrives 2 to 3 days
late: a run on Monday sees the last days of the week missing and reports the source as
stale; run on Wednesday or later for a complete week.

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import urllib.parse
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("in Search Console, Performance > Export > Download CSV, unzip and pass Dates.csv with --csv "
       "(or an API-shaped JSON with dimensions date, date+query, date+page)")
COLS = {
    "date": ["date", "dates", "datum", "fecha", "data"],
    "clicks": ["clicks", "click", "clics", "clic", "klicks", "klick", "clic"],
    "impressions": ["impressions", "impression", "impressionen", "impresiones", "impressioni"],
    "position": ["position", "posición", "posizione", "posicion"],
}


def has_api() -> str:
    return G.env_set("GSC_ACCESS_TOKEN")


class Acc:
    def __init__(self) -> None:
        self.daily = G.Daily()
        self.weekly: Dict[tuple, Dict[str, float]] = {}

    def total(self, day: dt.date, clicks: float, impressions: float, position: float) -> None:
        self.daily.add(day, "clicks", clicks)
        self.daily.add(day, "impressions", impressions)
        self.daily.add(day, "position_weighted", position * impressions)

    def breakdown(self, dim: str, key: str, day: dt.date, clicks: float, impressions: float, position: float) -> None:
        w = self.weekly.setdefault((dim, key, G.week_id(day)), {"clicks": 0.0, "impressions": 0.0, "position_weighted": 0.0})
        w["clicks"] += clicks
        w["impressions"] += impressions
        w["position_weighted"] += position * impressions

    def rows(self) -> List[Dict[str, Any]]:
        out = []
        for (dim, key, week) in sorted(self.weekly):
            v = self.weekly[(dim, key, week)]
            out.append({"dimension": dim, "key": key, "week": week, "values": {k: G.num(round(x, 4)) for k, x in v.items()}})
        return out


def ingest_api_rows(acc: Acc, dims: List[str], rows: List[Dict[str, Any]], since: dt.date, until: dt.date) -> None:
    for r in rows:
        keys = dict(zip(dims, r.get("keys", [])))
        day = G.parse_date_cell(str(keys.get("date", "")))
        if not day or not since <= day <= until:
            continue
        c, i = float(r.get("clicks", 0) or 0), float(r.get("impressions", 0) or 0)
        p = float(r.get("position", 0) or 0)
        if dims == ["date"]:
            acc.total(day, c, i, p)
        else:
            for dim in ("query", "page"):
                if dim in keys:
                    acc.breakdown(dim, str(keys[dim]), day, c, i, p)


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    if not args.site_url and not args.fixtures:
        raise G.InputError("--site-url is required for the API provider")
    site = urllib.parse.quote(args.site_url or "fixture", safe="")
    url = f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
    headers = {} if args.fixtures else {"authorization": "Bearer " + os.environ.get("GSC_ACCESS_TOKEN", "")}
    acc = Acc()
    for dims, key in ((["date"], "query-date"), (["date", "query"], "query-date-query"), (["date", "page"], "query-date-page")):
        body = {"startDate": since.isoformat(), "endDate": until.isoformat(), "dimensions": dims,
                "rowLimit": 25000, "dataState": "final"}
        data = G.http_json(url, key=key, fixtures=args.fixtures, headers=headers, body=body)
        ingest_api_rows(acc, dims, data.get("rows", []), since, until)
    return G.build_source("gsc", "fixture" if args.fixtures else "api", since, until, acc.daily, breakdowns=acc.rows(),
                          today=today, notes=["query rows exclude anonymized queries; their sum is below the totals"])


def from_csv(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    acc = Acc()
    provider = "csv"
    notes = []
    for path in args.csv:
        if path.lower().endswith(".json"):
            provider = "json"
            data = G.read_json(path)
            dims = data.get("dimensions") or args.dimensions.split(",")
            ingest_api_rows(acc, [d.strip() for d in dims], data.get("rows", []), since, until)
            notes.append(f"read {os.path.basename(path)} ({','.join(dims)})")
            continue
        rows = G.read_csv(path)
        if not rows:
            continue
        hs = rows[0].keys()
        cols = {k: G.pick_column(hs, a) for k, a in COLS.items()}
        if not cols["date"] or not cols["clicks"] or not cols["impressions"]:
            raise G.InputError(f"{path}: expected the Dates.csv export (Date, Clicks, Impressions, CTR, Position)")
        for r in rows:
            day = G.parse_date_cell(r[cols["date"]], args.date_format)
            if not day or not since <= day <= until:
                continue
            pos = G.parse_number(r.get(cols["position"], "")) if cols["position"] else 0.0
            acc.total(day, G.parse_number(r[cols["clicks"]]) or 0.0, G.parse_number(r[cols["impressions"]]) or 0.0, pos or 0.0)
        notes.append(f"read {os.path.basename(path)} (totals by date; no query or page rows in the UI export)")
    return G.build_source("gsc", provider, since, until, acc.daily, breakdowns=acc.rows(), today=today, notes=notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Search Console daily totals and weekly query and page rows into a growth-pulse source file.")
    G.add_common_args(ap, "Dates.csv of the UI export, or API-shaped JSON files (dimensions date / date,query / date,page)")
    ap.add_argument("--site-url", help="Search Console property: sc-domain:example.com or https://example.com/")
    ap.add_argument("--dimensions", default="date", help="key order of JSON rows without a dimensions field (default date)")
    ap.add_argument("--date-format", help="strptime format of the CSV date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("gsc", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
