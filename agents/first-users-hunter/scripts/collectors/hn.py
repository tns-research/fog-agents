#!/usr/bin/env python3
"""
collectors/hn.py: Hacker News through the Algolia API. Free, no key.

Signals: search_by_date per configured query (stories and comments), newest
first, created after the oldest date an eligible signal type accepts.
Activity: the user API (a missing user returns null: dead handle), then every
story and comment by that author in the activity window (tags=author_<user>).

Config block (config.json > sources.hn):
  {"enabled": true,
   "queries": [{"id": "hn_first_users", "query": "first users", "tags": "(story,comment)", "hits": 50}]}

Examples:
  python3 scripts/collectors/hn.py --config <project>/first-users-hunter/config.json --out signals-hn.jsonl
  python3 scripts/collectors/hn.py --activity some_user --today 2026-10-12
  python3 scripts/collectors/hn.py --fixtures tests/fixtures/api --today 2026-10-12

Health tested 2026-10-12 from a server IP: search_by_date 200, user API 200.
Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import (SourceError, activity, activity_since, classify, day_of, epoch,  # noqa: E402
                               keyword_hit, run_cli, signal, since_day)
from fuh_lib import clip, iso_from_epoch, strip_tags  # noqa: E402

NAME = "hn"
ACTIVITY_NETWORKS = ["hn"]
SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
USER = "https://hacker-news.firebaseio.com/v0/user/{}.json"
ITEM = "https://news.ycombinator.com/item?id={}"

EXAMPLE_CONFIG = {
    "enabled": True,
    "queries": [
        {"id": "hn_first_users", "query": "first users", "tags": "(story,comment)", "hits": 50},
    ],
}


def _community(hit: Dict[str, Any]) -> str:
    tags = hit.get("_tags") or []
    if "ask_hn" in tags:
        return "Ask HN"
    if "show_hn" in tags:
        return "Show HN"
    title = hit.get("story_title") or hit.get("title") or ""
    if title.lower().startswith(("ask hn", "show hn", "launch hn")):
        return title.split(":")[0].strip()
    return f"HN: {clip(title, 80)}" if title else "Hacker News"


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    since = since_day(today, criteria)
    out: List[Dict[str, Any]] = []
    for q in cfg.get("queries") or []:
        params = {"tags": q.get("tags", "(story,comment)"), "hitsPerPage": int(q.get("hits", 50)),
                  "numericFilters": f"created_at_i>{epoch(since)}"}
        if q.get("query"):
            params["query"] = q["query"]
        data = fetch.json("GET", SEARCH, params=params)
        for h in data.get("hits") or []:
            author = h.get("author") or ""
            oid = str(h.get("objectID") or "")
            if not author or not oid:
                continue
            is_comment = "comment" in (h.get("_tags") or [])
            title = h.get("title") or ""
            text = strip_tags(h.get("comment_text") or h.get("story_text") or "") or title
            if not keyword_hit(f"{title}\n{text}\n{h.get('story_title') or ''}", q.get("keywords") or []):
                continue
            story = h.get("story_id") or (h.get("objectID") if not is_comment else None)
            out.append(signal(
                NAME, "hn", oid, author, ITEM.format(oid), day_of(h.get("created_at_i") or h.get("created_at")),
                "api", text, criteria,
                # a comment is classified on its own words, not on the story title
                signal_type=classify("" if is_comment else title, text, criteria),
                author_url=f"https://news.ycombinator.com/user?id={author}",
                thread_url=ITEM.format(story) if story else "",
                title=title or (f"Re: {h.get('story_title')}" if h.get("story_title") else ""),
                community=_community(h), query_id=q.get("id", ""),
                datetime=iso_from_epoch(float(h["created_at_i"])) if h.get("created_at_i") else "",
                metrics={k: h[k] for k in ("points", "num_comments") if h.get(k) is not None},
            ))
    return out


def collect_activity(handle: str, fetch, today, criteria, cfg=None) -> List[Dict[str, Any]]:
    user = fetch.json("GET", USER.format(handle))
    if not user:
        raise SourceError(f"HN user {handle} does not exist", kind="not_found")
    since = activity_since(today, criteria)
    data = fetch.json("GET", SEARCH, params={"tags": f"author_{handle}", "hitsPerPage": 100,
                                             "numericFilters": f"created_at_i>{epoch(since)}"})
    out = []
    for h in data.get("hits") or []:
        oid = str(h.get("objectID") or "")
        kind = "comment" if "comment" in (h.get("_tags") or []) else "post"
        out.append(activity(NAME, "hn", handle, f"hn:{oid}", ITEM.format(oid),
                            day_of(h.get("created_at_i") or h.get("created_at")), kind))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
