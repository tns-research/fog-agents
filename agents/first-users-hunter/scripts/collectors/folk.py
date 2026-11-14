#!/usr/bin/env python3
"""
collectors/folk.py: shared folk views (public contact lists).

A folk shared view renders from a GraphQL gateway; scrape tools get an empty
shell. The gateway answers without a session:
  POST https://gateway.folk.app/networks/graphql
  sharedViewContactList(id, offset, limit) { totalCount items { ... on Person
      { fullname pJobTitle urls { value } } } }
The id is the last segment of the shared view slug, not the whole slug.

Lists are seeds: each row becomes a `listed` signal (never enough alone). The
published LinkedIn and X URLs of a row go into `links` for the activity
check. Emails in the view are not read: this agent does not collect addresses
from lists.

Config block (config.json > sources.folk):
  {"enabled": true,
   "views": [{"id": "<view id>", "url": "https://app.folk.app/shared/<slug>", "label": "Paris founders"}]}

Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import SourceError, run_cli, signal  # noqa: E402

NAME = "folk"
ACTIVITY_NETWORKS: List[str] = []
GATEWAY = "https://gateway.folk.app/networks/graphql"
QUERY = ("query($id:String!,$offset:Int,$limit:Int){sharedViewContactList(id:$id,offset:$offset,limit:$limit)"
         "{totalCount items{... on Person{fullname pJobTitle urls{value}}}}}")
PAGE = 100

EXAMPLE_CONFIG = {"enabled": False, "views": []}


def _links(urls: List[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for u in urls or []:
        v = (u or {}).get("value") or ""
        m = re.search(r"linkedin\.com/in/([^/?#]+)", v)
        if m:
            out.setdefault("linkedin", m.group(1).lower())
        m = re.search(r"(?:x|twitter)\.com/([^/?#]+)", v)
        if m:
            out.setdefault("x", m.group(1).lower())
    return out


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for view in cfg.get("views") or []:
        vid, offset, total = view["id"], 0, None
        url = view.get("url") or f"https://app.folk.app/shared/{vid}"
        while total is None or offset < total:
            data = fetch.json("POST", GATEWAY, json_body={"query": QUERY, "variables": {"id": vid, "offset": offset, "limit": PAGE}})
            if data.get("errors"):
                raise SourceError(f"folk view {vid}: {str(data['errors'])[:160]}", kind="error")
            res = (data.get("data") or {}).get("sharedViewContactList") or {}
            total = int(res.get("totalCount") or 0)
            items = res.get("items") or []
            for i, it in enumerate(items):
                if not it or not it.get("fullname"):
                    continue
                links = _links(it.get("urls") or [])
                net = "linkedin" if "linkedin" in links else ("x" if "x" in links else "folk")
                out.append(signal(
                    NAME, net, f"{vid}:{offset + i}", links.get(net, "") if net != "folk" else "", url,
                    today.isoformat(), "api", f"{it['fullname']}, {it.get('pJobTitle') or ''}".strip(", "),
                    criteria, signal_type="listed", authored=False, author_name=it["fullname"],
                    role=it.get("pJobTitle") or "", community=view.get("label") or "folk list", links=links,
                ))
            if not items:
                break
            offset += PAGE
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
