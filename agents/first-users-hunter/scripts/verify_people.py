#!/usr/bin/env python3
"""
verify_people.py

The mechanical gate on people-<YYYYMMDD>.jsonl, before anything is exported.
Standard library only, Python 3.9+, no network.

    python3 verify_people.py PEOPLE.jsonl --run-dir RUN [--cache DIR] [--config CFG]
        [--criteria FILE] [--today YYYY-MM-DD] [--out FILE] [--json]

Per line (errors unless marked warning):
  schema            valid against assets/person.schema.json; person_id and
                    person_key unique in the file
  signal
    not-cached      no cached page for signal.url (cache: <run>/cache)
    excerpt         signal.excerpt is not in the cached page (case, quotes,
                    dashes and whitespace folded, accents kept)
    stale / future  the signal is older than max_age_days of its type, or
                    dated ahead (an event may be ahead up to future_horizon_days)
    post-date       a LinkedIn or X signal URL whose id gives another date
                    (beyond date_tolerance_days), or date_source post_id on a
                    URL without a post id
    owner           a LinkedIn or X signal URL whose author is not one of the
                    person's handles on that network (tagged post, homonym)
    not-in-run      signal_id unknown to <run>/signals.jsonl, or a signal URL
                    or date that differs from the collected one
  activity          status active, and status and weighted_posts equal to
                    <run>/activity.json (the script's result, never retyped)
  score             score and score_breakdown equal to <run>/shortlist.jsonl
  fit               source_url cached; fit.excerpt, when given, in that page
  email             published on email_source_url (cached), real TLD, not a
                    package@version string
  touches           first_touch present; no link in it; at most one link in
                    the second touch; length within criteria touch_limits
                    (X replies 280 characters, LinkedIn notes 200); no
                    placeholder left except {{sender_first_name}}; no em or en
                    dash; the same first touch never sent to two people
  pages_read (warning) a listed URL that is not cached

Writes <people>.verify.json (or --out). Fix the file, never this script.
Exit codes: 0 no error (warnings allowed), 1 at least one error, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import (PERSON_SCHEMA, InputError, canonical_url, die, email_problem,  # noqa: E402
                     linkedin_profile_slug, load_criteria, load_json, norm_text, parse_day, post_id_date,
                     read_cached_text, read_jsonl, today_or, url_owner, validator, write_json)

URL_RE = re.compile(r"(https?://|www\.)\S+|\b[a-z0-9-]+\.(com|io|co|fr|ai|app|dev|net|org)/\S*", re.I)
TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}|<[a-z_ ]{3,30}>|\[(?:name|first name|company|link)\]", re.I)
DASHES = ("\u2014", "\u2013")


def links_in(text: str) -> int:
    return len(URL_RE.findall(text or ""))


def touch_problems(t: Dict[str, Any], limits: Dict[str, Any], first: bool) -> List[str]:
    out = []
    text = t.get("text") or ""
    ch = t.get("channel", "")
    lim = limits.get(ch, {})
    max_chars = lim.get("max_chars")
    if ch == "reply_in_thread" and t.get("network") == "x":
        max_chars = lim.get("max_chars_x", max_chars)
    if max_chars and len(text) > max_chars:
        out.append(f"{len(text)} characters, max {max_chars} for {ch}" + (" on x" if t.get("network") == "x" else ""))
    if lim.get("max_words") and len(text.split()) > lim["max_words"]:
        out.append(f"{len(text.split())} words, max {lim['max_words']} for {ch}")
    n_links = links_in(text)
    max_links = lim.get("max_links", 0) if first else limits.get("second_touch_max_links", 1)
    if n_links > max_links:
        out.append(f"{n_links} link(s), max {max_links} in the {'first' if first else 'second'} touch")
    for m in TOKEN_RE.finditer(text):
        if (m.group(1) or "").lower() != "sender_first_name":
            out.append(f"placeholder left: {m.group(0)}")
    if any(d in text for d in DASHES):
        out.append("em or en dash")
    return out


def check_signal_date(sig: Dict[str, Any], rule: Dict[str, Any], today, tol: int) -> List[str]:
    errs = []
    d = parse_day(sig.get("date"))
    if not d:
        return ["no-date"]
    age = (today - d).days
    if age < 0 and not (sig.get("type") == "event" and -age <= rule.get("future_horizon_days", 0)):
        errs.append(f"future: dated {sig['date']}, after {today}")
    if age > rule.get("max_age_days", 0):
        errs.append(f"stale: {age} days old, max {rule.get('max_age_days')} for {sig.get('type')}")
    id_day = post_id_date(sig.get("url", ""))
    if id_day and abs((d - id_day).days) > tol:
        errs.append(f"post-date: the post id says {id_day}, the row says {sig['date']}")
    if sig.get("date_source") == "post_id" and not id_day:
        errs.append("post-date: date_source is post_id but the URL has no post id")
    return errs


def verify(rows: List[Dict[str, Any]], run: str, cache: str, crit: Dict[str, Any], today) -> Dict[str, Any]:
    schema = load_json(PERSON_SCHEMA)
    validate = validator()
    signals = {s["signal_id"]: s for s in read_jsonl(os.path.join(run, "signals.jsonl"))}
    apath = os.path.join(run, "activity.json")
    activity = load_json(apath)["people"] if os.path.isfile(apath) else {}
    shortlist = {s["person_key"]: s for s in read_jsonl(os.path.join(run, "shortlist.jsonl"))}
    tol = int(crit["activity"].get("date_tolerance_days", 1))
    limits = crit["touch_limits"]
    res: Dict[str, Any] = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "today": today.isoformat(), "people": {}}
    seen_ids, seen_keys, touches = {}, {}, {}
    for n, p in enumerate(rows, start=1):
        pid = str(p.get("person_id") or f"line{n}")
        out = {"status": "ok", "errors": [], "warnings": []}
        res["people"][pid] = out
        err = lambda code, msg: out["errors"].append({"code": code, "message": msg})  # noqa: E731
        for e in validate(p, schema):
            err("schema", e)
        if out["errors"]:
            out["status"] = "errors"
            continue
        if pid in seen_ids:
            err("schema", f"person_id {pid} also on line {seen_ids[pid]}")
        seen_ids[pid] = n
        if p["person_key"] in seen_keys:
            err("schema", f"person_key {p['person_key']} also on line {seen_keys[p['person_key']]}")
        seen_keys[p["person_key"]] = n

        sig = p["signal"]
        rule = crit["signal_types"].get(sig["type"], {})
        for e in check_signal_date(sig, rule, today, tol):
            err(e.split(":")[0], e)
        text = read_cached_text(cache, sig["url"])
        if text is None:
            err("not-cached", f"signal page {sig['url']} is not in {cache}")
        elif norm_text(sig["excerpt"]) not in norm_text(text):
            err("excerpt", f"signal excerpt not found in the cached page of {sig['url']}")
        owner = url_owner(sig["url"])
        if owner:
            handles = {n["handle"].lower() for n in p["networks"] if n["network"] == owner[0]}
            if owner[1] not in handles:
                err("owner", f"{sig['url']} is by {owner[0]}:{owner[1]}, not one of the person's {owner[0]} handles")
        coll = signals.get(sig["signal_id"])
        if not coll:
            err("not-in-run", f"{sig['signal_id']} is not in {run}/signals.jsonl")
        elif canonical_url(coll["url"]) != canonical_url(sig["url"]) or coll["date"] != sig["date"]:
            err("not-in-run", f"{sig['signal_id']}: url or date differs from the collected signal")

        act = p["activity"]
        if act["status"] != "active":
            err("activity", f"status {act['status']}: only active people are delivered")
        ref = activity.get(p["person_key"])
        if not ref:
            err("activity", f"{p['person_key']} has no result in {apath}")
        elif ref["status"] != act["status"] or abs(float(ref["weighted_posts"]) - float(act["weighted_posts"])) > 1e-6:
            err("activity", f"activity differs from check_activity.py: {ref['status']} {ref['weighted_posts']} "
                            f"vs {act['status']} {act['weighted_posts']}")
        sl = shortlist.get(p["person_key"])
        if not sl:
            err("score", f"{p['person_key']} is not in {run}/shortlist.jsonl")
        elif float(sl["score"]) != float(p["score"]) or sl["score_breakdown"] != p["score_breakdown"]:
            err("score", f"score differs from score_people.py: {sl['score']} {sl['score_breakdown']}")

        fit = p["fit"]
        ftext = read_cached_text(cache, fit["source_url"])
        if ftext is None:
            err("not-cached", f"fit source {fit['source_url']} is not cached")
        elif fit.get("excerpt") and norm_text(fit["excerpt"]) not in norm_text(ftext):
            err("excerpt", f"fit excerpt not found in the cached page of {fit['source_url']}")

        email = (p.get("email") or "").strip()
        if email:
            prob = email_problem(email)
            if prob:
                err("email", f"{email}: {prob}")
            src = p.get("email_source_url") or ""
            page = read_cached_text(cache, src) if src.startswith("http") else None
            if page is None:
                err("email", "email without a cached email_source_url: only a published address, never a guessed one")
            elif email.lower() not in page.lower():
                err("email", f"{email} is not on {src}")
        li = p.get("linkedin_url") or ""
        if li and not linkedin_profile_slug(li):
            err("schema", f"linkedin_url is not a /in/ profile URL: {li}")

        for label, t in (("first_touch", p["first_touch"]), ("second_touch", p.get("second_touch"))):
            if not t:
                continue
            for prob in touch_problems(t, limits, first=(label == "first_touch")):
                err("touch", f"{label}: {prob}")
        key = norm_text(p["first_touch"]["text"])
        if key in touches:
            err("touch", f"first_touch identical to {touches[key]}'s: every message is written for one person")
        touches[key] = pid
        for u in p.get("pages_read") or []:
            if read_cached_text(cache, u) is None:
                out["warnings"].append({"code": "page-not-cached", "message": f"pages_read lists {u}, not cached"})
        if out["errors"]:
            out["status"] = "errors"
    people = res["people"].values()
    res["summary"] = {"people": len(res["people"]), "ok": sum(1 for x in people if x["status"] == "ok"),
                      "with_errors": sum(1 for x in people if x["status"] != "ok")}
    return res


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("people", help="people-<YYYYMMDD>.jsonl")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--cache", help="Page cache (default: <run>/cache)")
    ap.add_argument("--config")
    ap.add_argument("--criteria")
    ap.add_argument("--today")
    ap.add_argument("--out", help="Result file (default: <people>.verify.json)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        conf: Optional[Dict[str, Any]] = load_json(a.config) if a.config else None
        crit = load_criteria(a.criteria, conf)
        today = today_or(a.today)
        rows = read_jsonl(a.people)
    except InputError as e:
        return die(str(e))
    if not rows:
        return die(f"{a.people} is empty or missing")
    res = verify(rows, a.run_dir, a.cache or os.path.join(a.run_dir, "cache"), crit, today)
    out = a.out or re.sub(r"\.jsonl$", "", a.people) + ".verify.json"
    write_json(out, res)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for pid, r in res["people"].items():
            print(f"{pid}: {r['status']}, {len(r['errors'])} error(s), {len(r['warnings'])} warning(s)")
            for e in r["errors"]:
                print(f"  ERROR {e['code']}: {e['message']}")
            for w in r["warnings"]:
                print(f"  warn  {w['code']}: {w['message']}")
        s = res["summary"]
        print(f"\n{s['people']} people, {s['ok']} ok, {s['with_errors']} with errors -> {out}")
    return 1 if res["summary"]["with_errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
