#!/usr/bin/env python3
"""
connect_zernio.py

Daily social statistics per network from the Zernio API into the growth-pulse source
file of the source `social` (assets/source.schema.json), the same metrics as
connect_social.py: impressions, engagements, clicks, reposts, followers_gained, posts.

Provider: ZERNIO_API_KEY (bearer), ZERNIO_BASE_URL to override https://zernio.com/api/v1
(https only; plain http only to localhost). --profile-id limits the read to one Zernio
profile, --platforms to some networks. Without a key: a 'missing' health file. CSV exports
stay the fallback and are read by connect_social.py; run_pulse.py makes that choice.

Calls, GET only, one read of each per run:
  /analytics/daily-metrics?attribution=publish
      posts per network per day (`platforms` of each day) and the networks in use
  /analytics/daily-metrics?attribution=received&platform=<network>, one call per network
      the other metrics, on the day they were gained rather than on the publish day, so a
      week is not inflated by the later life of its posts
  /accounts/follower-stats?granularity=daily
      follower count per account per day, from the day before the window

Mapping (the same as connect_social.py where both read the figure):
  impressions       impressions, else views when the network reports no impressions
  engagements       likes + comments + shares + saves
  clicks            clicks
  reposts           shares
  posts             posts published that day
  followers_gained  day-to-day change of the follower count, summed per network: a net
                    figure, so it can be negative. A gap in the history lands on the next
                    day that has a point.

A read-only key is enough: POST /v1/api-keys with permission "read"
(https://docs.zernio.com/multi-tenant#scoped-api-keys). The default key can also publish.

Only metric ids and numbers are written: no account id, handle, name or email, although the
follower answer holds them. A network with nothing but zeros in the window is left out. The
network `twitter` is written `x`.

Limits, from the documentation:
  - HTTP 402 or 403 means the account has no analytics access (the follower endpoint names
    an analytics add-on, the pricing page says every account includes analytics). The source
    is reported as error, or without followers_gained when only the follower call is refused.
    Nothing is bought.
  - LinkedIn personal accounts: analytics only for posts published through Zernio. Company
    pages: all posts.
  - Post analytics are cached for 60 minutes, follower counts refresh once a day, YouTube
    views arrive 2 to 3 days late.
  - X reads are billed by Zernio at X's rate when an X account is connected, and the
    documentation does not say which analytics reads count. Set a spend cap on the Zernio
    dashboard, or pass --platforms without x.

Documentation:
  https://docs.zernio.com/analytics/get-daily-metrics
  https://docs.zernio.com/accounts/get-follower-stats
  https://docs.zernio.com/analytics/get-analytics
  https://docs.zernio.com/guides/rate-limits
  https://docs.zernio.com/pricing

    python3 connect_zernio.py --today 2026-10-14 --out <run>/data/social.json
    python3 connect_zernio.py --today 2026-10-14 --profile-id <id> --platforms linkedin,x --out <run>/data/social.json
    python3 connect_zernio.py --today 2026-10-14 --fixtures scripts/fixtures/zernio/api --out /tmp/social.json

Exit codes: 0 data written (ok, partial or stale), 1 health file written without data
(missing or error), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HOW = ("set ZERNIO_API_KEY, or export the analytics of each network to CSV and pass them to "
       "connect_social.py with --csv (linkedin=FILE instagram=FILE)")
DEFAULT_BASE = "https://zernio.com/api/v1"
CALL_GAP_S = 0.2  # the analytics window allows 6 calls per second at the lowest tier
API_METRICS = ("impressions", "views", "likes", "comments", "shares", "saves", "clicks")


def has_api() -> Optional[str]:
    return G.env_set("ZERNIO_API_KEY")


def base_url() -> str:
    base = os.environ.get("ZERNIO_BASE_URL", DEFAULT_BASE).rstrip("/")
    parts = urllib.parse.urlsplit(base)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        raise G.InputError("ZERNIO_BASE_URL must be https (plain http only to localhost): the key travels with it")
    return base


def platform_name(name: str) -> str:
    """Zernio's value for a network name of this stack."""
    name = name.strip().lower()
    return "twitter" if name == "x" else name


def network_id(platform: str) -> str:
    """The network id of the metric names, as connect_social.py writes it."""
    return "x" if platform == "twitter" else re.sub(r"[^a-z0-9_]+", "_", platform.lower())


def explain(e: G.ProviderError) -> G.ProviderError:
    if re.search(r"HTTP 40[23]\b", str(e)):
        return G.ProviderError(f"{e}: this Zernio account has no analytics access (see its plan); nothing was bought")
    if re.search(r"HTTP 401\b", str(e)):
        return G.ProviderError(f"{e}: Zernio refused the key")
    return e


def in_window(cell: Any, since: dt.date, until: dt.date) -> Optional[dt.date]:
    day = G.parse_date_cell(str(cell or ""))
    return day if day and since <= day <= until else None


def api(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    """The source file; an answer of an unexpected shape is a provider error, never a crash."""
    try:
        return read_zernio(args, since, until, today)
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        raise G.ProviderError(f"unexpected answer from Zernio ({type(e).__name__}): check the fields in the documentation")


def read_zernio(args, since: dt.date, until: dt.date, today: dt.date) -> Dict[str, Any]:
    fixtures = args.fixtures
    base = DEFAULT_BASE if fixtures else base_url()
    headers = {} if fixtures else {"authorization": "Bearer " + os.environ.get("ZERNIO_API_KEY", "")}
    profile = {"profileId": args.profile_id} if args.profile_id else {}
    span = {"fromDate": f"{since.isoformat()}T00:00:00.000Z", "toDate": f"{until.isoformat()}T23:59:59.999Z", **profile}
    wanted = [platform_name(p) for p in (args.platforms or "").split(",") if p.strip()]

    def get(path: str, key: str, query: Dict[str, str]) -> Any:
        if not fixtures:
            time.sleep(CALL_GAP_S)
        return G.http_json(f"{base}{path}?{urllib.parse.urlencode(query)}", key=key, fixtures=fixtures, headers=headers)

    try:
        published = get("/analytics/daily-metrics", "daily-metrics-published", {**span, "attribution": "publish"})
    except G.ProviderError as e:
        raise explain(e)
    notes = ["daily-metrics with attribution=received: engagement on the day it arrived; posts on their publish day",
             "engagements = likes + comments + shares + saves; reposts = shares; impressions fall back to views",
             "followers_gained = net change of the follower count per day, summed per network"]
    try:
        followers = get("/accounts/follower-stats", "follower-stats",
                        {"fromDate": (since - dt.timedelta(days=1)).isoformat(), "toDate": until.isoformat(),
                         "granularity": "daily", **profile})
    except G.ProviderError as e:
        followers = {}
        notes.append(f"followers_gained left out, the follower call failed: {explain(e)}")

    posts: Dict[str, Dict[dt.date, float]] = {}
    seen: Set[dt.date] = set()
    in_use = {str(p.get("platform")) for p in published.get("platformBreakdown") or [] if p.get("platform")}
    for row in published.get("dailyData") or []:
        day = in_window(row.get("date"), since, until)
        for platform, count in (row.get("platforms") or {}).items():
            in_use.add(platform)
            if day:
                posts.setdefault(platform, {})[day] = G.parse_number(count) or 0.0
                seen.add(day)
    accounts = followers.get("accounts") or []
    in_use |= {str(a.get("platform")) for a in accounts if a.get("platform")}
    platforms = sorted(set(wanted) or in_use)
    if not platforms:
        raise G.ProviderError("Zernio lists no network for this window")

    daily = G.Daily()
    for platform in platforms:
        try:
            answer = get("/analytics/daily-metrics", f"daily-metrics-received-{platform}",
                         {**span, "attribution": "received", "platform": platform})
        except G.ProviderError as e:
            raise explain(e)
        rows: List[Any] = []
        for row in answer.get("dailyData") or []:
            day = in_window(row.get("date"), since, until)
            if day:
                seen.add(day)
                m = {k: G.parse_number((row.get("metrics") or {}).get(k)) or 0.0 for k in API_METRICS}
                rows.append((day, m))
        net = network_id(platform)
        if any(any(m.values()) for _, m in rows):
            for day, m in rows:
                daily.add(day, f"{net}.impressions", m["impressions"] or m["views"])
                daily.add(day, f"{net}.engagements", m["likes"] + m["comments"] + m["shares"] + m["saves"])
                daily.add(day, f"{net}.clicks", m["clicks"])
                daily.add(day, f"{net}.reposts", m["shares"])
        for day, count in posts.get(platform, {}).items():
            daily.add(day, f"{net}.posts", count)

    stats = followers.get("stats") or {}
    for account in accounts:
        if account.get("platform") not in platforms:
            continue
        net = network_id(str(account["platform"]))
        points = sorted((G.parse_date_cell(str(p.get("date", ""))), G.parse_number(p.get("followers")))
                        for p in stats.get(account.get("_id")) or []
                        if G.parse_date_cell(str(p.get("date", ""))) and G.parse_number(p.get("followers")) is not None)
        for (_, before), (day, after) in zip(points, points[1:]):
            if since <= day <= until:
                daily.add(day, f"{net}.followers_gained", after - before)
                seen.add(day)
    if not seen:
        raise G.ProviderError("Zernio returned no row for this window")
    # Inside the answered range, a day without a row is a quiet day; days after the last row
    # stay missing, so a sync that has not caught up reads as stale.
    for day in G.days_between(since, max(seen)):
        daily.touch(day)
    fill = sorted({m for values in daily.values.values() for m in values})
    return G.build_source("social", "fixture" if fixtures else "api", since, until, daily, today=today,
                          fill_zero=fill, notes=notes)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Zernio daily social metrics per network into a growth-pulse source file.")
    G.add_common_args(ap, "not read here: CSV exports go through connect_social.py")
    ap.add_argument("--profile-id", help="read one Zernio profile only (default: every profile of the key)")
    ap.add_argument("--platforms", help="comma-separated networks to read, e.g. linkedin,instagram,x (default: every network in use)")
    args = ap.parse_args(argv)
    if args.csv or args.provider == "csv":
        print("error: connect_zernio.py reads the API only; CSV exports go through connect_social.py", file=sys.stderr)
        return 2
    return G.run_connector("social", args, has_api=has_api, api=api, from_csv=None, how_to_export=HOW)


if __name__ == "__main__":
    sys.exit(main())
