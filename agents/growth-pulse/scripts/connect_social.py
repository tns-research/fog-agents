#!/usr/bin/env python3
"""
connect_social.py

Social network statistics from CSV exports into the growth-pulse source file
(assets/source.schema.json). This is the fallback of the source social: run_pulse.py reads
the Zernio API first when it is enabled and its key is set (connect_zernio.py). Every
network exports a CSV, and any tool or script of the founder that writes the same columns
works too.

Accepted files, one per network, passed as NETWORK=PATH (or a file whose name holds the
network, or a normalized file with a network column):

  daily export   one row per day (LinkedIn page analytics, X account analytics):
                 Date, Impressions, Clicks, Reactions, Comments, Reposts, New followers...
                 LinkedIn "(total)" columns are preferred over "(organic)".
  post export    one row per post (Instagram or Facebook content export from Meta
                 Business Suite, LinkedIn post export): Publish time, Permalink or Post ID,
                 Impressions or Views, Likes, Comments, Shares, Saves, Follows. Each row
                 counts as one post; its lifetime figures are attributed to its publish day.
  normalized     date,network,impressions,engagements,clicks,reposts,followers_gained,posts

Metrics written per network: impressions, engagements (the column, else reactions +
comments + reposts + saves), clicks, reposts, followers_gained, posts.

    python3 connect_social.py --today 2026-10-14 --csv linkedin=exports/linkedin.csv instagram=exports/instagram-posts.csv --out <run>/data/social.json

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("export the analytics of each network to CSV (LinkedIn page analytics, Meta Business Suite content, "
       "X analytics) and pass them as --csv linkedin=FILE instagram=FILE, or set up Zernio (connect_zernio.py)")
NETWORKS = ("linkedin", "instagram", "facebook", "x", "twitter", "tiktok", "youtube", "threads", "bluesky")
DATE = ["date", "day", "publish time", "published", "publish date", "created", "time"]
ALIASES = {
    "impressions": ["impressions (total)", "impressions", "views", "post impressions", "impressions (organic)"],
    "engagements": ["engagements (total)", "engagements", "total engagements", "interactions"],
    "clicks": ["clicks (total)", "clicks", "url clicks", "link clicks", "clicks (organic)"],
    "reposts": ["reposts (total)", "reposts", "retweets", "shares", "reposts (organic)"],
    "followers_gained": ["new followers", "followers gained", "new follows", "follows", "followers_gained"],
    "posts": ["posts"],
}
PARTS = {"reactions": ["reactions (total)", "reactions", "likes", "reactions (organic)"],
         "comments": ["comments (total)", "comments", "replies", "comments (organic)"],
         "saves": ["saves", "saved"]}
POST_ID = ["permalink", "post id", "post link", "post url", "tweet id", "url", "post"]


def guess_network(path: str) -> str:
    stem = os.path.basename(path).lower()
    for n in NETWORKS:
        if re.search(rf"(^|[^a-z]){n}([^a-z]|$)", stem):
            return "x" if n == "twitter" else n
    return "social"


def has_api() -> Optional[str]:
    return None


def api(args, since, until, today) -> Dict[str, Any]:
    raise G.ProviderError("no API provider for social statistics")


def from_csv(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    daily = G.Daily()
    notes = []
    networks = set()
    daily_export_days = set()
    post_level_seen = False
    for spec in args.csv:
        net, path = (spec.split("=", 1) if "=" in spec and not os.path.exists(spec) else (None, spec))
        rows = G.read_csv(path)
        if not rows:
            notes.append(f"{os.path.basename(path)}: empty")
            continue
        hs = list(rows[0].keys())
        dcol = G.pick_column(hs, DATE)
        if not dcol:
            raise G.InputError(f"{path}: no date column (expected one of {DATE})")
        ncol = G.pick_column(hs, ["network", "platform"])
        cols = {m: G.pick_column(hs, a) for m, a in ALIASES.items()}
        parts = {m: G.pick_column(hs, a) for m, a in PARTS.items()}
        post_level = not cols["posts"] and bool(G.pick_column(hs, POST_ID))
        post_level_seen = post_level_seen or post_level
        for r in rows:
            day = G.parse_date_cell(r[dcol], args.date_format)
            if not day or not since <= day <= until:
                continue
            n = (r[ncol].strip().lower() if ncol else None) or (net or "").strip().lower() or guess_network(path)
            n = "x" if n == "twitter" else re.sub(r"[^a-z0-9_]+", "_", n)
            networks.add(n)
            daily.touch(day)
            if not post_level:
                daily_export_days.add(day)
            for m, col in cols.items():
                if col and m != "engagements":
                    daily.add(day, f"{n}.{m}", G.parse_number(r[col]))
            if cols["engagements"]:
                daily.add(day, f"{n}.engagements", G.parse_number(r[cols["engagements"]]))
            elif any(parts.values()) or cols["reposts"]:
                total = sum(G.parse_number(r[c]) or 0.0 for c in [*parts.values(), cols["reposts"]] if c)
                daily.add(day, f"{n}.engagements", total)
            if post_level:
                daily.add(day, f"{n}.posts", 1)
        notes.append(f"{os.path.basename(path)}: {'post-level export, lifetime figures on the publish day' if post_level else 'daily export'}")
    # A post-level export has rows only on publishing days: the days between are real zeros,
    # not missing data. When a daily export is also given, it alone decides where the data ends.
    fill = sorted({m for v in daily.values.values() for m in v})
    if post_level_seen:
        last = max(daily_export_days) if daily_export_days else until
        for d in G.days_between(since, last):
            daily.touch(d)
    return G.build_source("social", "csv", since, until, daily, today=today, fill_zero=fill, notes=notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Social network CSV exports into a growth-pulse source file.")
    G.add_common_args(ap, "NETWORK=FILE pairs (linkedin=exports/linkedin.csv), or files named after the network")
    ap.add_argument("--date-format", help="strptime format of the date column when auto-detection is wrong")
    args = ap.parse_args(argv)
    return G.run_connector("social", args, has_api=has_api, api=api, from_csv=from_csv, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
