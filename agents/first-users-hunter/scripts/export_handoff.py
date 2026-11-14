#!/usr/bin/env python3
"""
export_handoff.py

Turns a verified people-<YYYYMMDD>.jsonl into the files the founder and
cold-outreach-builder use. Standard library only, Python 3.9+, no network.

    python3 export_handoff.py PEOPLE.jsonl --run-dir RUN --out-dir <project>/first-users-hunter
        [--date YYYYMMDD] [--today YYYY-MM-DD] [--ledger <project>/first-users-hunter/ledger.csv]

Runs verify_people.py first and refuses to export while an error remains.
Writes, in --out-dir:
  prospects-<date>.csv     the prospect list of shared/handoffs.md (v1 columns
                           first, in their order) plus the v2 signal columns:
                           signal_type, signal_date, signal_url, signal_excerpt,
                           signal_community, last_active_at, activity_status,
                           active_networks, score, score_breakdown,
                           first_touch_channel, first_touch_draft,
                           second_touch_draft, status
  handoff-<date>/dossiers/<person_id>/prospect.json
                           one cold-outreach-builder dossier per person (its
                           schema 1.0, copied in assets/handoff/): the signal
                           as a dated fact with its URL and verbatim excerpt
  handoff-<date>/cache/    the cached pages those facts point to, same layout
                           and hash as cold-outreach-builder's cache
  first-touches-<date>.md  touch 1 and touch 2 per person, with the signal
                           link: what the founder sends, and the file the
                           writing gate reads
With --ledger, appends every exported person (status new) to the ledger the
next run reads, so nobody is listed twice without a newer signal, and purges
rows still "new" (never contacted) after config ledger_purge_days (default 60).

cold-outreach-builder then runs on the CSV as its prospect_list:
  run_dossiers.py prepare --leads prospects-<date>.csv --run-dir <run>
  cp -R handoff-<date>/dossiers handoff-<date>/cache <run>/
  run_dossiers.py status --run-dir <run>        (every dossier done)
Exit codes: 0 exported, 1 verification errors (nothing written), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import (HANDOFF_SCHEMA, InputError, cache_paths, clip, die, load_criteria, load_json,  # noqa: E402
                     parse_day, read_csv, read_jsonl, today_or, url_hash, validator, write_csv, write_json)
from verify_people import verify  # noqa: E402

V1_COLUMNS = ["prospect_id", "first_name", "last_name", "role", "company", "company_url", "profile_url",
              "email", "linkedin_url", "channel", "fit_rationale", "source_url", "language", "geography", "found_on"]
V2_COLUMNS = ["person_key", "signal_type", "signal_date", "signal_url", "signal_excerpt", "signal_community",
              "last_active_at", "activity_status", "active_networks", "score", "score_breakdown",
              "first_touch_channel", "first_touch_network", "first_touch_draft", "second_touch_channel",
              "second_touch_draft", "status"]
LEDGER_COLUMNS = ["person_key", "person_id", "name", "status", "found_on", "signal_url", "touched_at",
                  "replied_at", "notes"]
FACT_TYPE = {"trigger": "company_creation", "event": "talk"}
DATE_SOURCE = {"post_id": "post_id", "registry": "registry", "founder": "founder"}
TYPE_PHRASE = {
    "ask": "Asked publicly for help", "switch": "Said publicly they are leaving a tool",
    "complaint": "Complained publicly about the status quo", "question": "Asked a public question",
    "trigger": "Public registry event", "event": "Hosts an event", "build": "Builds in public",
}


def channel_of(p: Dict[str, Any]) -> str:
    t = p["first_touch"]
    if t["channel"] == "email":
        return "email"
    if t["channel"] == "event_intro":
        return "event"
    return t.get("network") or p["signal"]["network"]


def row_of(p: Dict[str, Any], found_on: str) -> Dict[str, Any]:
    sig, act = p["signal"], p["activity"]
    ft, st = p["first_touch"], p.get("second_touch") or {}
    return {
        "prospect_id": p["person_id"], "first_name": p["first_name"], "last_name": p.get("last_name", ""),
        "role": p.get("role", ""), "company": p.get("company", ""), "company_url": p.get("company_url", ""),
        "profile_url": p["profile_url"], "email": p.get("email", ""), "linkedin_url": p.get("linkedin_url", ""),
        "channel": channel_of(p), "fit_rationale": p["fit"]["reason"], "source_url": p["fit"]["source_url"],
        "language": p["language"], "geography": p.get("geography", ""), "found_on": found_on,
        "person_key": p["person_key"], "signal_type": sig["type"], "signal_date": sig["date"],
        "signal_url": sig["url"], "signal_excerpt": sig["excerpt"], "signal_community": sig.get("community", ""),
        "last_active_at": act["last_active_at"], "activity_status": act["status"],
        "active_networks": ";".join(act.get("active_networks") or []), "score": f"{p['score']:g}",
        "score_breakdown": json.dumps(p["score_breakdown"], sort_keys=True),
        "first_touch_channel": ft["channel"], "first_touch_network": ft.get("network", ""),
        "first_touch_draft": ft["text"], "second_touch_channel": st.get("channel", ""),
        "second_touch_draft": st.get("text", ""), "status": p["status"],
    }


def dossier_of(p: Dict[str, Any], today: str, cache: str) -> Dict[str, Any]:
    sig, act = p["signal"], p["activity"]
    where = sig.get("community") or sig["network"]
    claim = clip(f"{TYPE_PHRASE.get(sig['type'], 'Public signal')} on {where} ({sig['type']} signal).", 240)
    fact_date, fact_source = sig["date"], DATE_SOURCE.get(sig["date_source"], "page")
    if sig["date"] > today:
        # An announced event ahead: cold-outreach-builder refuses future facts, so the
        # fact is the announcement as read today, and the claim keeps the event date.
        claim = clip(f"Hosts an event on {sig['date']} ({where}), announced on its public page.", 240)
        fact_date, fact_source = today, "page"
    facts = [{
        "id": "f1", "type": FACT_TYPE.get(sig["type"], "post"), "claim": claim,
        "date": fact_date, "date_source": fact_source, "source_url": sig["url"],
        "excerpt": sig["excerpt"], "owner": "third_party" if sig["date_source"] == "registry" else "self",
    }]
    pages = [sig["url"], sig.get("thread_url", ""), p["fit"]["source_url"]] + list(p.get("pages_read") or [])
    pages_read = []
    for u in pages:
        if u and u.startswith("http") and u not in pages_read and any(os.path.isfile(x) for x in cache_paths(cache, u)):
            pages_read.append(u)
    d = {
        "schema_version": "1.0", "prospect_id": p["person_id"], "first_name": p["first_name"],
        "researched_at": today, "language": p["language"], "relationship": "none", "facts": facts,
        "pages_read": pages_read,
        "notes": (f"From first-users-hunter: {sig['type']} signal of {sig['date']}, activity {act['status']} "
                  f"({act['weighted_posts']:g} weighted posts in {act['window_days']} days, last {act['last_active_at']}). "
                  f"Touch 1 is drafted there ({p['first_touch']['channel']}); this agent writes the follow-up sequence."),
    }
    for k in ("last_name", "role", "company", "company_url", "linkedin_url", "profile_url", "geography"):
        if p.get(k):
            d[k] = p[k]
    if p.get("email"):
        d["email"] = p["email"]
        d["email_source_url"] = p.get("email_source_url", "")
    if p["language"] != "fr":
        d["register"] = "n/a"
    return d


def first_touches_md(people: List[Dict[str, Any]], date: str) -> str:
    out = [f"# First touches, {date}", "",
           "One block per person. Touch 1 goes where the signal was said; touch 2 only after touch 1 went out. "
           "Nothing is sent by the agent.", ""]
    for p in people:
        sig = p["signal"]
        out += [f"## {p['person_id']}, {p['name']}", "",
                f"Signal: {sig['type']}, {sig['date']}, {sig.get('community') or sig['network']}: {sig['url']}", "",
                f"Touch 1 ({p['first_touch']['channel']}, {p['first_touch'].get('network', sig['network'])}):", "",
                p["first_touch"]["text"], ""]
        if p.get("second_touch"):
            out += [f"Touch 2 ({p['second_touch']['channel']}, {p['second_touch'].get('network', '')}):".replace(", )", ")"),
                    "", p["second_touch"]["text"], ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("people")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cache", help="Page cache (default: <run>/cache)")
    ap.add_argument("--config")
    ap.add_argument("--criteria")
    ap.add_argument("--date", help="YYYYMMDD in the file names (default: --today)")
    ap.add_argument("--today")
    ap.add_argument("--ledger")
    a = ap.parse_args(argv)
    try:
        conf = load_json(a.config) if a.config else None
        crit = load_criteria(a.criteria, conf)
        today = today_or(a.today)
        people = read_jsonl(a.people)
        schema = load_json(HANDOFF_SCHEMA)
    except InputError as e:
        return die(str(e))
    if not people:
        return die(f"{a.people} is empty or missing")
    cache = a.cache or os.path.join(a.run_dir, "cache")
    res = verify(people, a.run_dir, cache, crit, today)
    if res["summary"]["with_errors"]:
        for pid, r in res["people"].items():
            for e in r["errors"]:
                print(f"{pid}: ERROR {e['code']}: {e['message']}")
        print("nothing exported: fix people.jsonl and run again (verify_people.py lists the same errors)")
        return 1
    date = a.date or today.strftime("%Y%m%d")
    found_on = today.isoformat()
    os.makedirs(a.out_dir, exist_ok=True)
    rows = [row_of(p, found_on) for p in people]
    csv_path = os.path.join(a.out_dir, f"prospects-{date}.csv")
    write_csv(csv_path, V1_COLUMNS + V2_COLUMNS, rows)

    hand = os.path.join(a.out_dir, f"handoff-{date}")
    validate = validator()
    index_src = os.path.join(cache, "index.json")
    index = load_json(index_src) if os.path.isfile(index_src) else {}
    new_index: Dict[str, Any] = {}
    for p in people:
        d = dossier_of(p, found_on, cache)
        errs = validate(d, schema)
        if errs:
            return die(f"{p['person_id']}: dossier fails the cold-outreach schema: {errs[0]} (report this as a bug)", 1)
        write_json(os.path.join(hand, "dossiers", p["person_id"], "prospect.json"), d)
        for u in d["pages_read"]:
            for src in cache_paths(cache, u):
                if os.path.isfile(src):
                    os.makedirs(os.path.join(hand, "cache"), exist_ok=True)
                    shutil.copyfile(src, os.path.join(hand, "cache", os.path.basename(src)))
            h = url_hash(u)
            new_index[h] = index.get(h, {"url": u, "source": "first-users-hunter"})
    write_json(os.path.join(hand, "cache", "index.json"), dict(sorted(new_index.items())))
    md_path = os.path.join(a.out_dir, f"first-touches-{date}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(first_touches_md(people, found_on))
    if a.ledger:
        existing = read_csv(a.ledger) if os.path.isfile(a.ledger) else []
        # Personal data: rows never contacted ("new") older than ledger_purge_days are purged.
        purge = int((conf or {}).get("ledger_purge_days", 60))
        kept_rows = []
        for r in existing:
            found = parse_day(r.get("found_on"))
            if (r.get("status") or "new") == "new" and found and (today - found).days > purge:
                continue
            kept_rows.append(r)
        purged = len(existing) - len(kept_rows)
        existing = kept_rows
        known = {r.get("person_key") for r in existing}
        for p in people:
            if p["person_key"] not in known:
                existing.append({"person_key": p["person_key"], "person_id": p["person_id"], "name": p["name"],
                                 "status": "new", "found_on": found_on, "signal_url": p["signal"]["url"]})
            else:
                for r in existing:
                    if r.get("person_key") == p["person_key"] and (r.get("status") or "new") == "new":
                        r["found_on"], r["signal_url"] = found_on, p["signal"]["url"]
        write_csv(a.ledger, LEDGER_COLUMNS, existing)
    print(f"{len(rows)} person(s) -> {csv_path}")
    print(f"{len(people)} dossier(s) and {len(new_index)} cached page(s) -> {hand}")
    print(f"first touches -> {md_path}")
    if a.ledger:
        print(f"ledger -> {a.ledger} ({purged} row(s) never contacted purged after {purge} days)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
