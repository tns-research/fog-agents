#!/usr/bin/env python3
"""
collectors/notion.py: public Notion databases (directories, community lists).

A page published on <space>.notion.site renders in the browser from XHR
calls; scrape tools and curl get an empty shell. The same calls work without
a session:
  POST <site>/api/v3/loadPageChunk   gives the page block, its collection id
                                     and the collection schema (column names)
  POST <site>/api/v3/queryCollection gives the row ids of a view; the rows
                                     are blocks of its recordMap
Values sit in properties, keyed by the short column keys of the schema.

Lists are seeds: each row becomes a `listed` signal, which never qualifies a
person alone (assets/criteria.json) and carries the retrieval date. A list whose rows hold the person's own
dated words (an "asks" board with a date column) can declare
"signal_type": "ask" and a "date" column; the row date is then the signal date.

Config block (config.json > sources.notion):
  {"enabled": true,
   "lists": [{"id": "fr-founders", "site": "https://<space>.notion.site",
              "page_id": "<uuid>", "view_id": "<uuid>",
              "columns": {"name": "Name", "linkedin": "LinkedIn", "x": "X", "role": "Role",
                          "company": "Company", "text": "Looking for", "date": "Added"},
              "signal_type": "listed"}]}

Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import SourceError, day_of, run_cli, signal  # noqa: E402

NAME = "notion"
ACTIVITY_NETWORKS: List[str] = []

EXAMPLE_CONFIG = {"enabled": False, "lists": []}


def _val(rec: Dict[str, Any]) -> Dict[str, Any]:
    v = (rec or {}).get("value") or {}
    return v.get("value", v) if isinstance(v, dict) else {}


def _text(prop: Any) -> str:
    if not isinstance(prop, list):
        return ""
    return "".join(seg[0] for seg in prop if isinstance(seg, list) and seg and isinstance(seg[0], str)).strip()


def _date(prop: Any) -> str:
    for seg in prop or []:
        for ann in (seg[1] if isinstance(seg, list) and len(seg) > 1 else []) or []:
            if isinstance(ann, list) and len(ann) > 1 and ann[0] == "d" and isinstance(ann[1], dict):
                return day_of(ann[1].get("start_date"))
    return day_of(_text(prop))


def _handle(value: str, network: str) -> str:
    value = (value or "").strip()
    if network == "linkedin":
        m = re.search(r"linkedin\.com/in/([^/?#]+)", value)
        return m.group(1).lower() if m else ""
    m = re.search(r"(?:x|twitter)\.com/([^/?#]+)", value)
    return (m.group(1) if m else value).lstrip("@").lower()


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for lst in cfg.get("lists") or []:
        site = lst["site"].rstrip("/")
        pid, vid = str(uuid.UUID(lst["page_id"])), str(uuid.UUID(lst["view_id"]))
        chunk = fetch.json("POST", f"{site}/api/v3/loadPageChunk", json_body={
            "pageId": pid, "limit": 100, "cursor": {"stack": []}, "chunkNumber": 0, "verticalColumns": False})
        rm = chunk.get("recordMap") or {}
        page = _val((rm.get("block") or {}).get(pid))
        cid = page.get("collection_id")
        if not cid:
            raise SourceError(f"{site}: page {pid} holds no database", kind="error")
        schema = _val((rm.get("collection") or {}).get(cid)).get("schema") or {}
        key_of = {v.get("name"): k for k, v in schema.items()}
        res = fetch.json("POST", f"{site}/api/v3/queryCollection", json_body={
            "collection": {"id": cid}, "collectionView": {"id": vid},
            "loader": {"type": "reducer", "reducers": {"collection_group_results": {"type": "results", "limit": 1000}},
                       "searchQuery": "", "userTimeZone": "UTC"}})
        ids = (((res.get("result") or {}).get("reducerResults") or {}).get("collection_group_results") or {}).get("blockIds") or []
        blocks = ((res.get("recordMap") or {}).get("block")) or {}
        cols = lst.get("columns") or {}
        stype = lst.get("signal_type", "listed")
        for rid in ids:
            props = _val(blocks.get(rid)).get("properties") or {}
            get = lambda c: props.get(key_of.get(cols.get(c, ""), ""), None)  # noqa: E731
            name = _text(get("name")) or _text(props.get("title"))
            if not name:
                continue
            links = {n: h for n in ("linkedin", "x") if (h := _handle(_text(get(n)), n))}
            day = _date(get("date")) if cols.get("date") else ""
            if stype != "listed" and not day:
                continue
            words = _text(get("text"))
            out.append(signal(
                NAME, links and ("linkedin" if "linkedin" in links else "x") or "notion",
                f"{lst.get('id', cid)}:{rid}", links.get("linkedin") or links.get("x") or "",
                f"{site}/{rid.replace('-', '')}", day or today.isoformat(), "page" if day else "api",
                words or name, criteria, signal_type=stype, authored=False, author_name=name,
                role=_text(get("role")), company=_text(get("company")), community=lst.get("id", "Notion list"),
                links=links, title=name,
            ))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
