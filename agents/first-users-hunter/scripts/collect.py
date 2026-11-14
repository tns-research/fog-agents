#!/usr/bin/env python3
"""
collect.py

Runs the collectors of first-users-hunter and records the health of every
source. Standard library only, Python 3.9+, no paid call.

Commands:
  signals   --config CFG --run-dir RUN [--only hn,github] [--fixtures DIR] [--record DIR] [--today D]
            Runs every enabled source of config.json > sources (manual always
            when <run>/manual-signals.csv exists). Validates each record against
            assets/signal.schema.json, merges with <run>/signals.jsonl (by
            signal_id), and caches the verbatim text of each signal under
            <run>/cache/<hash>.txt for its URL (the page the excerpts are
            checked against). Writes <run>/source-health.json (signals part).
  activity  --config CFG --run-dir RUN [--fixtures DIR] [--record DIR] [--today D]
            For every identity of <run>/candidates.jsonl, asks the collector of
            its network for the person's public posts in the activity window
            (HN, GitHub, Reddit by API; LinkedIn, X and closed groups from
            <run>/activity-manual.csv). Writes <run>/activity.jsonl (posts and
            handle checks) and the activity part of source-health.json.

Health statuses: ok, empty (answered, nothing in the window), skipped (disabled
or no key), blocked (401, 402, 403, 429), error. A failed source never stops
the run; it is listed in the report's Methodology. A page already in the cache
(a full thread stored with cache_page.py) is never overwritten.

Exit codes: 0 done (even with failed sources), 2 usage error.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collectors import ACTIVITY_COLLECTOR, COLLECTORS  # noqa: E402
from collectors.common import Fetcher, SourceError  # noqa: E402
from fuh_lib import (SIGNAL_SCHEMA, InputError, cache_paths, cache_store, die, load_criteria,  # noqa: E402
                     load_json, read_jsonl, today_or, validator, write_json, write_jsonl)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def health(status: str, records: int = 0, message: str = "", mode: str = "live", http: Any = None) -> Dict[str, Any]:
    h = {"status": status, "records": records, "mode": mode, "checked_at": now()}
    if message:
        h["message"] = message
    if http:
        h["http_status"] = http
    return h


def cached_text(rec: Dict[str, Any]) -> str:
    head = [f"Author: {rec.get('author_name') or rec.get('handle') or ''}".rstrip(),
            f"Handle: {rec.get('network')}:{rec.get('handle')}" if rec.get("handle") else "",
            f"Date: {rec.get('date')}", f"Community: {rec.get('community', '')}",
            f"Title: {rec.get('title', '')}" if rec.get("title") else ""]
    return "\n".join(h for h in head if h) + "\n\n" + rec.get("text", "") + "\n"


def load_health(path: str) -> Dict[str, Any]:
    return load_json(path) if os.path.isfile(path) else {"signals": {}, "activity": {}}


def cmd_signals(a, conf: Dict[str, Any], criteria: Dict[str, Any], fetch: Fetcher, today) -> int:
    run = a.run_dir
    sources = conf.get("sources") or {}
    only = [s.strip() for s in (a.only or "").split(",") if s.strip()]
    validate = validator()
    schema = load_json(SIGNAL_SCHEMA)
    existing = {r["signal_id"]: r for r in read_jsonl(os.path.join(run, "signals.jsonl"))}
    hpath = os.path.join(run, "source-health.json")
    hl = load_health(hpath)
    new = 0
    for name in COLLECTORS:
        if only and name not in only:
            continue
        cfg = dict(sources.get(name) or {})
        if name == "manual":
            cfg.setdefault("enabled", os.path.isfile(os.path.join(run, cfg.get("signals_csv", "manual-signals.csv"))))
        if not cfg.get("enabled"):
            hl["signals"][name] = health("skipped", message="disabled in config.json", mode=fetch.mode)
            continue
        cfg.update(_icp_keywords=conf.get("icp_keywords") or [], _base_dir=run)
        mod = importlib.import_module(f"collectors.{name}")
        try:
            rows = mod.collect_signals(cfg, fetch, today, criteria)
        except SourceError as e:
            hl["signals"][name] = health(e.kind, message=str(e), mode=fetch.mode, http=e.status)
            print(f"{name}: {e.kind}: {e}")
            continue
        kept, bad = [], 0
        for r in rows:
            r["collected_at"] = now()
            errs = validate(r, schema)
            if errs:
                bad += 1
                print(f"{name}: dropped {r.get('signal_id')}: {errs[0]}")
                continue
            kept.append(r)
        for r in kept:
            if r["signal_id"] not in existing:
                new += 1
            existing[r["signal_id"]] = r
            txt, htm = cache_paths(os.path.join(run, "cache"), r["url"])
            if not (os.path.isfile(txt) or os.path.isfile(htm)):
                cache_store(os.path.join(run, "cache"), r["url"], cached_text(r), f"api:{name}")
        notes = "; ".join(cfg.get("_notes") or [])
        if bad:
            notes = (notes + "; " if notes else "") + f"{bad} record(s) failed the signal schema"
        hl["signals"][name] = health("ok" if kept else "empty", len(kept), notes, fetch.mode)
        print(f"{name}: {len(kept)} signal(s)" + (f" ({notes})" if notes else ""))
    write_jsonl(os.path.join(run, "signals.jsonl"), sorted(existing.values(), key=lambda r: r["signal_id"]))
    write_json(hpath, hl)
    print(f"{len(existing)} signal(s) in {os.path.join(run, 'signals.jsonl')}, {new} new")
    return 0


def cmd_activity(a, conf: Dict[str, Any], criteria: Dict[str, Any], fetch: Fetcher, today) -> int:
    run = a.run_dir
    cands = read_jsonl(os.path.join(run, "candidates.jsonl"))
    if not cands:
        return die(f"{run}/candidates.jsonl is empty or missing: run candidates.py first")
    sources = conf.get("sources") or {}
    hpath = os.path.join(run, "source-health.json")
    hl = load_health(hpath)
    stats: Dict[str, Dict[str, int]] = {}
    out: List[Dict[str, Any]] = []
    done = set()
    for c in cands:
        for ident in c.get("identities") or []:
            net, handle = ident["network"], ident["handle"]
            coll = ACTIVITY_COLLECTOR.get(net)
            if not coll or not handle or (net, handle) in done:
                continue
            done.add((net, handle))
            st = stats.setdefault(coll, {"checked": 0, "records": 0, "not_found": 0, "failed": 0, "skipped": 0})
            cfg = dict(sources.get(coll) or {}, _base_dir=run, _network=net)
            mod = importlib.import_module(f"collectors.{coll}")
            try:
                rows = mod.collect_activity(handle, fetch, today, criteria, cfg)
                status, msg = "ok", ""
            except SourceError as e:
                rows, status, msg = [], ("not_found" if e.kind == "not_found" else e.kind), str(e)
            st["checked"] += 1
            st["records"] += len(rows)
            if status == "not_found":
                st["not_found"] += 1
            elif status in ("skipped",):
                st["skipped"] += 1
            elif status != "ok":
                st["failed"] += 1
            out.append({"network": net, "handle": handle, "kind": "handle_check", "status": status,
                        "collector": coll, "message": msg})
            out.extend(rows)
    for coll, st in stats.items():
        status = "ok" if st["checked"] > st["failed"] + st["skipped"] else ("skipped" if st["skipped"] else "error")
        hl["activity"][coll] = health(status, st["records"],
                                      f"{st['checked']} handle(s) checked, {st['not_found']} not found, "
                                      f"{st['failed']} failed, {st['skipped']} skipped", fetch.mode)
    write_jsonl(os.path.join(run, "activity.jsonl"), out)
    write_json(hpath, hl)
    print(f"{len(done)} handle(s) checked, {sum(1 for r in out if r.get('kind') != 'handle_check')} post(s) "
          f"-> {os.path.join(run, 'activity.jsonl')}")
    return 0


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["signals", "activity"])
    ap.add_argument("--config", required=True, help="<project>/first-users-hunter/config.json")
    ap.add_argument("--run-dir", required=True, help="Run folder, e.g. <project>/first-users-hunter/run-<YYYYMMDD>")
    ap.add_argument("--criteria", help="Project criteria.json merged over assets/criteria.json")
    ap.add_argument("--only", help="Comma-separated collectors to run (signals)")
    ap.add_argument("--fixtures", help="Replay frozen responses from this folder (offline tests)")
    ap.add_argument("--record", help="Also write every live response to this folder")
    ap.add_argument("--today", help="Reference date YYYY-MM-DD (default: today)")
    a = ap.parse_args(argv)
    try:
        conf = load_json(a.config)
        criteria = load_criteria(a.criteria, conf)
        today = today_or(a.today)
        fetch = Fetcher(fixtures=a.fixtures, record=a.record)
    except InputError as e:
        return die(str(e))
    os.makedirs(a.run_dir, exist_ok=True)
    if a.command == "signals":
        return cmd_signals(a, conf, criteria, fetch, today)
    return cmd_activity(a, conf, criteria, fetch, today)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
