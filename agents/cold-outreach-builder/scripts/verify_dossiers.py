#!/usr/bin/env python3
"""
verify_dossiers.py

Checks every prospect dossier mechanically before anything is scored or
written. Standard library only, Python 3.9+.

    python3 verify_dossiers.py <run>/dossiers --cache <run>/cache \
        [--criteria <project>/cold-outreach-builder/criteria.json] [--today YYYY-MM-DD] [--json]

For each prospect of <run>/dossiers/queue.json (written by run_dossiers.py),
or else each folder holding a prospect.json or a brief.md:
  schema           valid against assets/prospect.schema.json, folder name = prospect_id
  per fact:
    not-cached        the page at source_url has no cache/<hash>.txt or .html
    excerpt-not-found the excerpt is not in the cached page (case, quotes,
                      dashes and whitespace folded; accents kept)
    future-date       the fact is dated after --today
    post-date         the source is a LinkedIn or X post: its id gives its
                      creation date; a fact of type post, or dated from the
                      post id, must match it within one day
    owner-mismatch    owner is self but the LinkedIn post belongs to another
                      public slug than the prospect's linkedin_url
    stale (warning)   older than freshness.fact_max_age_days of the criteria:
                      kept, never scored, never used as a hook
    duplicate-id      two facts share an id
  email-not-on-page   email_source_url is a URL and the address is not on it
                      (email_source_url "lead_list": the founder's own list)

Writes <run>/dossiers/verify.json (read by score_prospects.py and
lint_outreach.py). Fix the dossier (correct the excerpt, cache the page,
drop the fact), never this script, then run it again.

Exit codes: 0 no error (warnings allowed), 1 at least one error, 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (ASSETS, InputError, linkedin_post_owner,  # noqa: E402
                          linkedin_profile_slug, load_json, merged_config, norm_text,
                          parse_day, post_id_date, read_cached_text, today_or, validator,
                          write_json)

SCHEMA = os.path.join(ASSETS, "prospect.schema.json")
CRITERIA = os.path.join(ASSETS, "criteria.example.json")


def verify_one(path: str, folder_id: str, cache: str, schema: Dict[str, Any], max_age: int,
               today, validate) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": "ok", "errors": [], "warnings": [], "facts": {}}
    try:
        data = load_json(path)
    except InputError as e:
        out["status"] = "errors"
        out["errors"].append({"code": "unreadable", "message": str(e)})
        return out
    for err in validate(data, schema):
        out["errors"].append({"code": "schema", "message": err})
    if not isinstance(data, dict):
        out["status"] = "errors"
        return out
    if data.get("prospect_id") and data["prospect_id"] != folder_id:
        out["errors"].append({"code": "schema", "message": f"prospect_id {data['prospect_id']} does not match folder {folder_id}"})

    li_slug = linkedin_profile_slug(data.get("linkedin_url", ""))
    seen = set()
    for fact in data.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        fid = str(fact.get("id", "?"))
        res: Dict[str, Any] = {"status": "verified", "reasons": [], "age_days": None,
                               "type": fact.get("type"), "date": fact.get("date"),
                               "source_url": fact.get("source_url", "")}
        if fid in seen:
            res["reasons"].append("duplicate-id")
        seen.add(fid)
        url = fact.get("source_url", "")
        day = parse_day(fact.get("date", ""))
        if day is None:
            res["reasons"].append("no-date")
        else:
            res["age_days"] = (today - day).days
            if day > today:
                res["reasons"].append("future-date")
        text = read_cached_text(cache, url) if url else None
        if text is None:
            res["reasons"].append("not-cached")
        else:
            excerpt = norm_text(fact.get("excerpt", ""))
            if not excerpt or excerpt not in norm_text(text):
                res["reasons"].append("excerpt-not-found")
        id_day = post_id_date(url)
        if id_day and day:
            from_id = fact.get("date_source") == "post_id" or fact.get("type") == "post"
            if from_id and abs((day - id_day).days) > 1:
                res["reasons"].append(f"post-date (post id says {id_day.isoformat()})")
        if fact.get("date_source") == "post_id" and not id_day:
            res["reasons"].append("post-date (date_source is post_id but the URL has no post id)")
        owner = linkedin_post_owner(url)
        if fact.get("owner") == "self" and owner:
            if li_slug and owner != li_slug:
                res["reasons"].append(f"owner-mismatch (post by {owner}, prospect is {li_slug})")
            elif not li_slug:
                out["warnings"].append({"code": "owner-unchecked", "message": f"{fid}: no linkedin_url to check the post owner"})
        if res["reasons"]:
            res["status"] = "failed"
            for r in res["reasons"]:
                out["errors"].append({"code": r.split(" ")[0], "fact": fid, "message": f"{fid}: {r} ({url})"})
        elif res["age_days"] is not None and res["age_days"] > max_age:
            res["status"] = "stale"
            out["warnings"].append({"code": "stale", "fact": fid,
                                    "message": f"{fid}: {res['age_days']} days old, over {max_age}: kept, not scored, not a hook"})
        out["facts"][fid] = res

    if url_list_missing := [u for u in (data.get("pages_read") or []) if read_cached_text(cache, u) is None]:
        for u in url_list_missing:
            out["warnings"].append({"code": "page-not-cached", "message": f"pages_read lists {u} but it is not in the cache"})

    email = (data.get("email") or "").strip()
    src = (data.get("email_source_url") or "").strip()
    if email and src == "lead_list":
        pass
    elif email and src:
        text = read_cached_text(cache, src)
        if text is None:
            out["errors"].append({"code": "not-cached", "message": f"email_source_url {src} is not cached"})
        elif email.lower() not in text.lower():
            out["errors"].append({"code": "email-not-on-page", "message": f"{email} is not on {src}"})
    elif email and not src:
        out["warnings"].append({"code": "email-source-missing",
                                "message": "email has no email_source_url: write lead_list when it came from the founder's list; never a guessed address"})
    if not data.get("facts"):
        out["warnings"].append({"code": "no-facts", "message": "no fact: the prospect goes to tier C"})
    if out["errors"]:
        out["status"] = "errors"
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossiers", help="Folder holding <prospect_id>/prospect.json")
    ap.add_argument("--cache", required=True, help="Page cache folder (cache_page.py)")
    ap.add_argument("--criteria", help="Project criteria.json merged over assets/criteria.example.json")
    ap.add_argument("--today", help="Reference date, YYYY-MM-DD (default: today)")
    ap.add_argument("--out", help="Output path (default: <dossiers>/verify.json)")
    ap.add_argument("--json", action="store_true", help="Print the result as JSON")
    a = ap.parse_args(argv)

    try:
        today = today_or(a.today)
        criteria = merged_config(CRITERIA, a.criteria)
        schema = load_json(SCHEMA)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not os.path.isdir(a.dossiers):
        print(f"error: {a.dossiers} is not a folder", file=sys.stderr)
        return 2
    max_age = int(criteria.get("freshness", {}).get("fact_max_age_days", 730))
    validate = validator()

    result: Dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today.isoformat(),
        "fact_max_age_days": max_age,
        "prospects": {},
    }
    queue_path = os.path.join(a.dossiers, "queue.json")
    if os.path.isfile(queue_path):
        names = list(load_json(queue_path).get("prospects", []))
    else:
        names = [n for n in sorted(os.listdir(a.dossiers))
                 if os.path.isfile(os.path.join(a.dossiers, n, "prospect.json"))
                 or os.path.isfile(os.path.join(a.dossiers, n, "brief.md"))]
    for name in names:
        folder = os.path.join(a.dossiers, name)
        path = os.path.join(folder, "prospect.json")
        if not os.path.isfile(path):
            result["prospects"][name] = {"status": "missing", "errors": [{"code": "missing", "message": "no prospect.json yet"}],
                                         "warnings": [], "facts": {}}
            continue
        result["prospects"][name] = verify_one(path, name, a.cache, schema, max_age, today, validate)

    facts = [f for p in result["prospects"].values() for f in p["facts"].values()]
    result["summary"] = {
        "dossiers": len(result["prospects"]),
        "ok": sum(1 for p in result["prospects"].values() if p["status"] == "ok"),
        "with_errors": sum(1 for p in result["prospects"].values() if p["status"] != "ok"),
        "facts": len(facts),
        "verified": sum(1 for f in facts if f["status"] == "verified"),
        "stale": sum(1 for f in facts if f["status"] == "stale"),
        "failed": sum(1 for f in facts if f["status"] == "failed"),
    }
    write_json(a.out or os.path.join(a.dossiers, "verify.json"), result)

    if a.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for pid, p in result["prospects"].items():
            print(f"{pid}: {p['status']}, {len(p['errors'])} error(s), {len(p['warnings'])} warning(s)")
            for e in p["errors"]:
                print(f"  ERROR {e['code']}: {e['message']}")
            for w in p["warnings"]:
                print(f"  warn  {w['code']}: {w['message']}")
        s = result["summary"]
        print(f"\n{s['dossiers']} dossier(s), {s['ok']} ok; facts: {s['verified']} verified, {s['stale']} stale, {s['failed']} failed")
    return 1 if any(p["status"] != "ok" for p in result["prospects"].values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
