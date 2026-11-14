#!/usr/bin/env python3
"""
collectors/manual.py: signals and activity found outside the API collectors.

Covers what no free API serves from a server: public LinkedIn and X posts
found with the host's web search (`site:linkedin.com/posts "<phrase>"`,
`site:x.com "<phrase>"`), threads the founder pastes (Reddit without OAuth,
forums, Indie Hackers), market-signal quotes whose author is a person, and
closed groups (Slack, Discord, WhatsApp, Telegram) read from the founder's
screenshots or exported text.

manual-signals.csv (in the run folder), one row per signal:
  network       linkedin | x | hn | github | reddit | web | community
  handle        author handle on that network (LinkedIn: the public slug)
  author_name   as shown publicly (optional)
  url           the post or thread URL
  text | text_file   the page text, verbatim (text_file: path relative to the CSV)
  date          YYYY-MM-DD; optional for LinkedIn and X: the post id gives it
  date_source   page (read on the page, default) or founder (closed group)
  signal_type   ask | switch | complaint | question | trigger | event | build (optional: classifier)
  community, title, thread_url, linkedin, x, github, role, company (optional)

activity-manual.csv, one row per public post of a person (the activity check):
  network, handle, url, kind (post | comment | reply | repost), date (optional for LinkedIn and X)

Rules applied here: a LinkedIn or X URL is dated from its id, and a row whose
date disagrees with the id by more than the tolerance is rejected; a LinkedIn
post whose URL slug is not the handle (a post where the person is only tagged,
or a homonym) is rejected. Rejections are printed and noted in the health line.

Examples:
  python3 scripts/collectors/manual.py --config <run>/config.json
  python3 scripts/collectors/manual.py --activity camille-roux --config <run>/config.json
Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import SourceError, activity, run_cli, signal  # noqa: E402
from fuh_lib import InputError, parse_day, post_id_datetime, read_csv, url_owner  # noqa: E402

NAME = "manual"
ACTIVITY_NETWORKS = ["linkedin", "x", "community", "web"]

EXAMPLE_CONFIG = {"signals_csv": "manual-signals.csv", "activity_csv": "activity-manual.csv"}


def _base(cfg: Dict[str, Any]) -> str:
    return cfg.get("_base_dir") or cfg.get("_config_dir") or os.getcwd()


def _path(cfg: Dict[str, Any], key: str) -> str:
    p = cfg.get(key) or EXAMPLE_CONFIG[key]
    return p if os.path.isabs(p) else os.path.join(_base(cfg), p)


def _note(cfg: Dict[str, Any], msg: str) -> None:
    cfg.setdefault("_notes", []).append(msg)
    print(f"manual: {msg}", file=sys.stderr)


def dated(url: str, given: str, tolerance: int):
    """(date, date_source, problem) for a URL and an optional given date."""
    dt = post_id_datetime(url)
    if dt:
        d = dt.date()
        g = parse_day(given)
        if g and abs((g - d).days) > tolerance:
            return "", "", f"date {given} disagrees with the post id ({d.isoformat()})"
        return d.isoformat(), "post_id", ""
    g = parse_day(given)
    if not g:
        return "", "", "no date and no post id in the URL"
    return g.isoformat(), "", ""


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    path = _path(cfg, "signals_csv")
    if not os.path.isfile(path):
        return []
    try:
        rows = read_csv(path)
    except InputError as e:
        raise SourceError(str(e), kind="error")
    tol = int(criteria["activity"].get("date_tolerance_days", 1))
    out: List[Dict[str, Any]] = []
    for n, r in enumerate(rows, start=2):
        url, net = r.get("url", ""), (r.get("network") or "web").lower()
        if not url.startswith(("http://", "https://")):
            _note(cfg, f"{os.path.basename(path)} line {n}: no URL, skipped")
            continue
        handle = (r.get("handle") or "").lower().lstrip("@")
        owner = url_owner(url)
        if owner:
            if not handle:
                handle = owner[1]
            elif owner[1] != handle:
                _note(cfg, f"line {n}: {url} belongs to {owner[1]}, not {handle} (tagged post or homonym), skipped")
                continue
        day, src, problem = dated(url, r.get("date", ""), tol)
        if problem:
            _note(cfg, f"line {n}: {problem}, skipped")
            continue
        text = r.get("text", "")
        if not text and r.get("text_file"):
            tf = r["text_file"] if os.path.isabs(r["text_file"]) else os.path.join(os.path.dirname(path), r["text_file"])
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            except OSError as e:
                _note(cfg, f"line {n}: cannot read {tf}: {e}, skipped")
                continue
        if not text:
            _note(cfg, f"line {n}: no text, skipped (the excerpt check needs the page text)")
            continue
        links = {k: r[k].lower().lstrip("@") for k in ("linkedin", "x", "github") if r.get(k)}
        out.append(signal(
            NAME, net, f"{net}:{handle or 'anon'}:{n}", handle, url, day,
            src or (r.get("date_source") or "page"), text, criteria,
            signal_type=r.get("signal_type") or None, author_name=r.get("author_name", ""),
            thread_url=r.get("thread_url") or url, title=r.get("title", ""), community=r.get("community", ""),
            links=links, role=r.get("role", ""), company=r.get("company", ""),
        ))
    return out


def collect_activity(handle: str, fetch, today, criteria, cfg=None) -> List[Dict[str, Any]]:
    cfg = cfg or {}
    path = _path(cfg, "activity_csv")
    if not os.path.isfile(path):
        return []
    want_net = cfg.get("_network")
    tol = int(criteria["activity"].get("date_tolerance_days", 1))
    out = []
    for n, r in enumerate(read_csv(path), start=2):
        if (r.get("handle") or "").lower().lstrip("@") != handle.lower():
            continue
        net = (r.get("network") or "").lower()
        if want_net and net != want_net:
            continue
        day, src, problem = dated(r.get("url", ""), r.get("date", ""), tol)
        if problem:
            _note(cfg, f"{os.path.basename(path)} line {n}: {problem}, skipped")
            continue
        out.append(activity(NAME, net, handle, f"manual:{r.get('url', '')}", r.get("url", ""), day,
                            (r.get("kind") or "post").lower(), src or "page"))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
