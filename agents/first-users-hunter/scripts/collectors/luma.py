#!/usr/bin/env python3
"""
collectors/luma.py: public Luma pages (city discovery pages and event pages).

A Luma page ships its data in the __NEXT_DATA__ script tag: each event entry
carries the event (name, start date, url slug) and its hosts (name, username,
and the LinkedIn, X and website handles the host chose to publish). No key.

Signals: one `event` signal per host of an event whose name matches a keyword
(the config's keywords, else the agent's icp_keywords), starting between
today minus the event max age and today plus future_horizon_days
(assets/criteria.json). Hosts that are organizations (LinkedIn /company/ or
/showcase/ handle) are skipped. The published LinkedIn and X handles go into
`links` so the activity check can use them; nothing is guessed.
Activity: none (Luma is not a posting network); use the linked handles.

Config block (config.json > sources.luma):
  {"enabled": true, "places": ["paris"], "events": ["<event-slug>"], "keywords": ["founder"]}

Health tested 2026-10-12: lu.ma/<place> redirects to luma.com/<place>, 200,
20 events in __NEXT_DATA__. JavaScript is not needed.
Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import timedelta
from typing import Any, Dict, Iterator, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import SourceError, day_of, keyword_hit, run_cli, signal  # noqa: E402

NAME = "luma"
ACTIVITY_NETWORKS: List[str] = []
BASE = "https://luma.com"
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

EXAMPLE_CONFIG = {"enabled": True, "places": ["paris"], "keywords": ["founder", "startup"]}


def entries(obj: Any) -> Iterator[Dict[str, Any]]:
    """Every dict holding an `event` dict and a `hosts` list, at any depth."""
    if isinstance(obj, dict):
        if isinstance(obj.get("event"), dict) and isinstance(obj.get("hosts"), list):
            yield obj
        for v in obj.values():
            yield from entries(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from entries(v)


def page_data(fetch, url: str) -> Any:
    html = fetch.text("GET", url)
    m = NEXT_RE.search(html)
    if not m:
        raise SourceError(f"{url}: no __NEXT_DATA__ (page layout changed?)", kind="error")
    return json.loads(m.group(1))


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    ev_rule = criteria["signal_types"]["event"]
    lo = (today - timedelta(days=ev_rule["max_age_days"])).isoformat()
    hi = (today + timedelta(days=ev_rule.get("future_horizon_days", 60))).isoformat()
    keywords = cfg.get("keywords") or cfg.get("_icp_keywords") or []
    pages = [(f"{BASE}/{p}", f"Luma {p}") for p in cfg.get("places") or []]
    pages += [(f"{BASE}/{e}", "Luma event") for e in cfg.get("events") or []]
    out: List[Dict[str, Any]] = []
    seen = set()
    for url, label in pages:
        for entry in entries(page_data(fetch, url)):
            ev = entry["event"]
            name = ev.get("name") or ""
            day = day_of(ev.get("start_at") or entry.get("start_at"))
            if not day or not (lo <= day <= hi) or not keyword_hit(name, keywords):
                continue
            ev_url = f"{BASE}/{ev.get('url', '')}"
            cal = (entry.get("calendar") or {}).get("name") or label
            for h in entry["hosts"]:
                li = (h.get("linkedin_handle") or "").strip()
                if li.startswith(("/company/", "/showcase/", "/school/")):
                    continue
                handle = h.get("username") or h.get("api_id") or ""
                key = (ev.get("api_id"), handle)
                if not handle or key in seen:
                    continue
                seen.add(key)
                links = {}
                if li.startswith("/in/"):
                    links["linkedin"] = li[len("/in/"):].strip("/").lower()
                if h.get("twitter_handle"):
                    links["x"] = h["twitter_handle"].lstrip("@").lower()
                if h.get("website"):
                    links["website"] = h["website"]
                hosts = ", ".join(x.get("name") or "" for x in entry["hosts"] if x.get("name"))
                out.append(signal(
                    NAME, "luma", f"{ev.get('api_id')}:{handle}", handle, ev_url, day, "page",
                    f"{name}\nHosted by {hosts}", criteria, signal_type="event",
                    author_name=h.get("name") or "", author_url=f"{BASE}/user/{handle}",
                    thread_url=ev_url, title=name, community=cal, links=links,
                    datetime=ev.get("start_at", ""),
                    metrics={"guest_count": entry.get("guest_count")},
                ))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
