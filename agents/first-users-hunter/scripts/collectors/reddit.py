#!/usr/bin/env python3
"""
collectors/reddit.py: Reddit through the official OAuth API, optional.

Anonymous Reddit JSON (www.reddit.com/.../new.json, /search.json) answers 403
from server IPs (tested 2026-10-10: 403 on /subreddits/search.json,
/r/<sub>/new.json, old.reddit.com and api.reddit.com; the .rss feed answers
once, then 429). It may still work from a home connection; this collector does
not rely on it. The path that holds from a server is a free "script" app:

  1. https://www.reddit.com/prefs/apps > create app > type "script".
  2. export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
     (optional: REDDIT_USER_AGENT="web:<your-app>:1.0 (by /u/<you>)")

Without the two variables the collector is skipped with a clear health line
and the run continues; the founder can paste thread URLs in manual-signals.csv.

Signals: /r/<sub>/new, or /r/<sub>/search when a query is set, per subreddit.
Activity: /user/<name>/overview (404: dead handle; 403: suspended, also dead).

Config block (config.json > sources.reddit):
  {"enabled": true, "subreddits": ["startups", "SaaS"], "query": "first users", "limit": 100}

Exit codes: 0 ok or skipped, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import (SourceError, activity, activity_since, basic_auth, day_of,  # noqa: E402
                               run_cli, signal, since_day)
from fuh_lib import iso_from_epoch  # noqa: E402

NAME = "reddit"
ACTIVITY_NETWORKS = ["reddit"]
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH = "https://oauth.reddit.com"

EXAMPLE_CONFIG = {"enabled": True, "subreddits": ["startups"], "query": "first users", "limit": 50}


def _auth(fetch) -> Dict[str, str]:
    cid = os.environ.get("REDDIT_CLIENT_ID", "")
    secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    ua = os.environ.get("REDDIT_USER_AGENT", "web:fog-agents-first-users-hunter:2.0")
    if fetch.mode == "live" and not (cid and secret):
        raise SourceError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are not set: create a free script app at "
                          "https://www.reddit.com/prefs/apps, or paste thread URLs in manual-signals.csv", kind="skipped")
    headers = dict(basic_auth(cid, secret), **{"User-Agent": ua})
    tok = fetch.json("POST", TOKEN_URL, form={"grant_type": "client_credentials"}, headers=headers)
    if not tok.get("access_token"):
        raise SourceError("Reddit returned no access token (check the app credentials)", kind="blocked")
    return {"Authorization": f"Bearer {tok['access_token']}", "User-Agent": ua}


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    headers = _auth(fetch)
    since = since_day(today, criteria).isoformat()
    out: List[Dict[str, Any]] = []
    for sub in cfg.get("subreddits") or []:
        if cfg.get("query"):
            url, params = f"{OAUTH}/r/{sub}/search", {"q": cfg["query"], "restrict_sr": 1, "sort": "new",
                                                      "t": "month", "limit": int(cfg.get("limit", 100))}
        else:
            url, params = f"{OAUTH}/r/{sub}/new", {"limit": int(cfg.get("limit", 100))}
        data = fetch.json("GET", url, params=params, headers=headers)
        for child in (data.get("data") or {}).get("children") or []:
            d = child.get("data") or {}
            author = d.get("author") or ""
            day = day_of(d.get("created_utc"))
            if not author or author == "[deleted]" or not day or day < since:
                continue
            title = d.get("title") or ""
            out.append(signal(
                NAME, "reddit", d.get("id", ""), author, f"https://www.reddit.com{d.get('permalink', '')}", day,
                "api", f"{title}\n\n{d.get('selftext') or ''}".strip(), criteria,
                author_url=f"https://www.reddit.com/user/{author}",
                thread_url=f"https://www.reddit.com{d.get('permalink', '')}", title=title, community=f"r/{sub}",
                datetime=iso_from_epoch(float(d["created_utc"])) if d.get("created_utc") else "",
                metrics={"score": d.get("score"), "comments": d.get("num_comments")},
            ))
    return out


def collect_activity(handle: str, fetch, today, criteria, cfg=None) -> List[Dict[str, Any]]:
    headers = _auth(fetch)
    since = activity_since(today, criteria).isoformat()
    try:
        data = fetch.json("GET", f"{OAUTH}/user/{handle}/overview", params={"limit": 100}, headers=headers)
    except SourceError as e:
        if e.status == 403:
            raise SourceError(f"u/{handle} is suspended", kind="not_found", status=403)
        raise
    out = []
    for child in (data.get("data") or {}).get("children") or []:
        d = child.get("data") or {}
        day = day_of(d.get("created_utc"))
        if not day or day < since:
            continue
        kind = "comment" if child.get("kind") == "t1" else "post"
        out.append(activity(NAME, "reddit", handle, f"reddit:{d.get('name') or d.get('id')}",
                            f"https://www.reddit.com{d.get('permalink', '')}", day, kind))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
