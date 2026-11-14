#!/usr/bin/env python3
"""
collectors/common.py

The collector contract of first-users-hunter. Standard library only, Python
3.9+. Not a command: each collector imports it.

A collector is one file per source with:
  NAME                         collector id (hn, github, reddit, luma, ...)
  ACTIVITY_NETWORKS            networks whose handles it can check for activity
  collect_signals(cfg, fetch, today, criteria) -> list of signal records
  collect_activity(handle, fetch, today, criteria, cfg) -> list of activity records
                                (optional; raises SourceError(kind="not_found")
                                for a handle that does not exist)
and a command line built by run_cli(): --help, --config, --fixtures, --record,
--today, --out, --activity HANDLE.

Signal records follow assets/signal.schema.json. Activity records:
  {"network", "handle", "activity_id", "url", "date", "date_source", "kind", "collector"}
kind is one of the keys of criteria.json activity.kind_weights.

Fetcher: live HTTP with urllib, or replay of frozen fixtures (--fixtures DIR,
used by the offline tests), or live with a copy of every response written to
a fixtures folder (--record DIR). Authorization headers are never recorded.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from fuh_lib import (InputError, load_criteria, load_json, parse_day, today_or,  # noqa: E402
                     write_jsonl)

UA = "fog-agents-first-users-hunter/2.0 (+https://example.invalid/bot)"
MAX_BYTES = 5_000_000


class SourceError(Exception):
    """A source failed. kind: error, blocked (402, 403, 429), not_found (404 or
    an empty user), skipped (disabled or no key)."""

    def __init__(self, message: str, kind: str = "error", status: Optional[int] = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


def request_key(method: str, url: str, params: Optional[Dict[str, Any]] = None,
                body: Optional[bytes] = None) -> str:
    """Readable, stable key of a request: METHOD url?sorted-params [#body-sha]."""
    q = urllib.parse.urlencode(sorted((k, str(v)) for k, v in (params or {}).items()))
    key = f"{method.upper()} {url}" + (f"?{q}" if q else "")
    if body:
        key += " #" + hashlib.sha256(body).hexdigest()[:12]
    return key


class Fetcher:
    def __init__(self, fixtures: Optional[str] = None, record: Optional[str] = None,
                 timeout: int = 20, pause: float = 0.0) -> None:
        self.fixtures = fixtures
        self.record = record
        self.timeout = timeout
        self.pause = pause
        self.mode = "fixture" if fixtures else "live"
        self._index: Dict[str, str] = {}
        if fixtures:
            path = os.path.join(fixtures, "index.json")
            if not os.path.isfile(path):
                raise InputError(f"{path} not found: a fixtures folder needs an index.json")
            self._index = load_json(path)

    def request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None,
                json_body: Any = None, form: Optional[Dict[str, str]] = None,
                headers: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
        body = None
        hdrs = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
        hdrs.update(headers or {})
        if json_body is not None:
            body = json.dumps(json_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        elif form is not None:
            body = urllib.parse.urlencode(sorted(form.items())).encode("utf-8")
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        key = request_key(method, url, params, body)
        if self.fixtures:
            name = self._index.get(key)
            if not name:
                raise SourceError(f"no fixture for {key}", kind="error")
            data = load_json(os.path.join(self.fixtures, name))
            payload = data.get("body")
            text = payload if isinstance(payload, str) else json.dumps(payload)
            return int(data.get("status", 200)), text
        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(full, data=body, headers=hdrs, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                charset = resp.headers.get_content_charset() or "utf-8"
                text = resp.read(MAX_BYTES).decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                text = e.read(MAX_BYTES).decode("utf-8", errors="replace")
            except Exception:  # body unreadable
                text = ""
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise SourceError(f"network error on {url}: {e}", kind="error")
        if self.pause:
            time.sleep(self.pause)
        if self.record:
            self._save(key, status, text)
        return status, text

    def _save(self, key: str, status: int, text: str) -> None:
        os.makedirs(self.record, exist_ok=True)
        name = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlsplit(key.split(" ", 1)[1]).netloc.lower()).strip("-")
        name = f"{name}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}.json"
        try:
            body: Any = json.loads(text)
        except json.JSONDecodeError:
            body = text
        with open(os.path.join(self.record, name), "w", encoding="utf-8") as f:
            json.dump({"key": key, "status": status, "body": body}, f, ensure_ascii=False, indent=1)
        index_path = os.path.join(self.record, "index.json")
        index = load_json(index_path) if os.path.isfile(index_path) else {}
        index[key] = name
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(index.items())), f, ensure_ascii=False, indent=1)

    def text(self, method: str, url: str, **kw: Any) -> str:
        status, text = self.request(method, url, **kw)
        check_status(status, url, text)
        return text

    def json(self, method: str, url: str, **kw: Any) -> Any:
        text = self.text(method, url, **kw)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise SourceError(f"{url} did not return JSON", kind="error")


def check_status(status: int, url: str, text: str = "") -> None:
    if status < 400:
        return
    if status == 404:
        raise SourceError(f"404 on {url}", kind="not_found", status=status)
    if status in (401, 402, 403, 429):
        raise SourceError(f"{status} on {url} (blocked, payment required or rate limited)", kind="blocked", status=status)
    raise SourceError(f"{status} on {url}: {text[:160]}", kind="error", status=status)


def basic_auth(user: str, password: str) -> Dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------- records

def classify(title: str, text: str, criteria: Dict[str, Any]) -> str:
    cl = criteria["classifier"]
    blob = f"{title or ''}\n{text or ''}"
    for t in cl["order"]:
        for pat in cl["patterns"].get(t, []):
            if re.search(pat, blob, re.I | re.M):
                return t
    return cl.get("default_type", "build")


def signal(collector: str, network: str, sid: str, handle: str, url: str, day: str,
           date_source: str, text: str, criteria: Dict[str, Any], **kw: Any) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "schema_version": "1.0",
        "signal_id": f"{collector}:{sid}",
        "collector": collector,
        "network": network,
        "handle": (handle or "").strip().lower().lstrip("@"),
        "url": url,
        "date": day,
        "date_source": date_source,
        "text": text or "",
        "authored": kw.pop("authored", True),
    }
    stype = kw.pop("signal_type", None)
    rec["signal_type"] = stype or classify(kw.get("title", ""), text, criteria)
    for k, v in kw.items():
        if v not in (None, "", {}, []):
            rec[k] = v
    return rec


def activity(collector: str, network: str, handle: str, aid: str, url: str, day: str,
             kind: str, date_source: str = "api") -> Dict[str, Any]:
    return {"collector": collector, "network": network, "handle": (handle or "").lower(),
            "activity_id": aid, "url": url, "date": day, "date_source": date_source, "kind": kind}


def day_of(value: Any) -> str:
    """YYYY-MM-DD from an ISO string or a Unix time."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%d")
    d = parse_day(str(value))
    return d.isoformat() if d else ""


def since_day(today: date, criteria: Dict[str, Any]) -> date:
    """Oldest date any eligible signal type accepts."""
    ages = [t["max_age_days"] for t in criteria["signal_types"].values() if t.get("eligible")]
    return today - timedelta(days=max(ages or [60]))


def activity_since(today: date, criteria: Dict[str, Any]) -> date:
    act = criteria["activity"]
    widest = max([act["window_days"]] + list((act.get("window_days_by_network") or {}).values()))
    return today - timedelta(days=widest)


def epoch(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


# ---------------------------------------------------------------- CLI

def run_cli(module: Any, argv: List[str], doc: str) -> int:
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="Agent config.json (its sources.<name> block is used); default: the collector's built-in example")
    ap.add_argument("--fixtures", help="Replay frozen responses from this folder (offline)")
    ap.add_argument("--record", help="Live run that also writes every response to this folder")
    ap.add_argument("--today", help="Reference date YYYY-MM-DD (default: today)")
    ap.add_argument("--out", help="Write the records as JSONL here (default: print them)")
    ap.add_argument("--activity", metavar="HANDLE", help="Check the activity of one handle instead of collecting signals")
    a = ap.parse_args(argv)
    try:
        today = today_or(a.today)
        criteria = load_criteria()
        cfg = getattr(module, "EXAMPLE_CONFIG", {})
        if a.config:
            conf = load_json(a.config)
            cfg = (conf.get("sources") or {}).get(module.NAME, cfg)
            cfg = dict(cfg, _icp_keywords=conf.get("icp_keywords", []), _config_dir=os.path.dirname(os.path.abspath(a.config)))
        fetch = Fetcher(fixtures=a.fixtures, record=a.record)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        if a.activity:
            if not hasattr(module, "collect_activity"):
                print(f"error: {module.NAME} has no activity check", file=sys.stderr)
                return 2
            rows = module.collect_activity(a.activity, fetch, today, criteria, cfg)
        else:
            rows = module.collect_signals(cfg, fetch, today, criteria)
    except SourceError as e:
        print(f"{module.NAME}: {e.kind}: {e}", file=sys.stderr)
        return 1 if e.kind != "skipped" else 0
    if a.out:
        write_jsonl(a.out, rows)
        print(f"{module.NAME}: {len(rows)} record(s) -> {a.out}")
    else:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False, sort_keys=True))
        print(f"{module.NAME}: {len(rows)} record(s) ({fetch.mode})", file=sys.stderr)
    return 0


def keyword_hit(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    low = (text or "").lower()
    return any(k.lower() in low for k in keywords if k)


Collect = Callable[..., List[Dict[str, Any]]]
