#!/usr/bin/env python3
"""
proof.py

Reads positioning.proof of a project's context.json and says, item by item,
whether a copy may use it. Standard library only (Python 3.8+), shared by every
agent that writes copy.

An item is either:

  - a string (V1 format): still accepted, read as an item with no kind, no
    source and no date. usable() lets it through with a warning;
  - an object {id, claim, kind, source, date, valid_days, consent}, contract in
    agents/project-context/assets/context-schema.json (definitions.proof_item),
    rules per kind in agents/project-context/assets/proof-kinds.json.

usable(proof, scope, today) refuses a stale fact (date + valid_days passed), a
testimonial or customer without consent granted for the scope, an item without
the source or the date its kind needs, a date in the future and a malformed
object. Only usable items enter a copy; the reason of every refusal goes into
the deliverable.

As a module:
    from proof import load_proof, usable, proof_text
    for p in load_proof(context):
        ok, reason = usable(p, "posts", today)   # ok and reason == "": clean
                                                  # ok and reason: a warning
                                                  # not ok: refused, reason says why

Usage:
    python3 shared/scripts/proof.py check <context.json> [--scope posts] [--today YYYY-MM-DD]
                                          [--root <project-context>] [--json]

check prints every item with its status for the scope (usable, warning,
refused) and the schema errors of the objects. --root also checks that a file
source exists under the project-context folder.

Exit codes: 0 no malformed item (refused items allowed), 1 at least one
malformed object or duplicate id, 2 usage error or unreadable file.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PC_ASSETS = os.path.join(REPO, "agents", "project-context", "assets")
KINDS_FILE = os.path.join(PC_ASSETS, "proof-kinds.json")
CONTEXT_SCHEMA = os.path.join(PC_ASSETS, "context-schema.json")

sys.path.insert(0, HERE)
from validate_json import validate  # noqa: E402

Today = Union[date, str, None]


@dataclass
class Proof:
    index: int
    id: str
    claim: str
    kind: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None
    valid_days: Optional[int] = None
    consent: Optional[Dict[str, Any]] = None
    legacy: bool = False
    errors: List[str] = field(default_factory=list)


_CACHE: Dict[str, Any] = {}


def _load(path: str) -> Any:
    if path not in _CACHE:
        with open(path, "r", encoding="utf-8") as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def kinds() -> Dict[str, Dict[str, Any]]:
    return _load(KINDS_FILE)["kinds"]


def scopes() -> List[str]:
    return list(_load(KINDS_FILE)["scopes"])


def _as_date(value: Today) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_date(text: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(str(text)) if text else None
    except ValueError:
        return None


def _item_errors(item: Dict[str, Any]) -> List[str]:
    schema = _load(CONTEXT_SCHEMA)
    errors = validate(item, schema["definitions"]["proof_item"], schema)
    rules = kinds().get(item.get("kind"), {})
    if rules.get("requires_consent") and "consent" not in item:
        errors.append(f"kind {item.get('kind')} needs a consent object (status granted, refused or unknown)")
    if item.get("date") and _parse_date(item["date"]) is None:
        errors.append(f"date: {item['date']!r} is not a calendar date")
    consent = item.get("consent")
    if isinstance(consent, dict) and consent.get("date") and _parse_date(consent["date"]) is None:
        errors.append(f"consent.date: {consent['date']!r} is not a calendar date")
    return errors


def load_proof(context: Any) -> List[Proof]:
    """positioning.proof of a context.json (dict), normalized. A missing list
    gives []. A string is a legacy item; an object is checked against the
    schema and carries its errors."""
    if not isinstance(context, dict):
        return []
    raw = (context.get("positioning") or {}).get("proof") or []
    if not isinstance(raw, list):
        return []
    items: List[Proof] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            p = Proof(index=i, id=str(item.get("id") or f"proof-{i}"), claim=str(item.get("claim") or ""),
                      kind=item.get("kind"), source=item.get("source"), date=item.get("date"),
                      valid_days=item.get("valid_days"), consent=item.get("consent"))
            p.errors = _item_errors(item)
        else:
            p = Proof(index=i, id=f"proof-{i}", claim=str(item), legacy=True)
            if not isinstance(item, str):
                p.errors = [f"expected a string or an object, got {type(item).__name__}"]
        items.append(p)
    seen: Dict[str, int] = {}
    for p in items:
        if not p.legacy and p.id in seen:
            p.errors.append(f"id {p.id!r} already used by positioning.proof[{seen[p.id]}]")
        seen.setdefault(p.id, p.index)
    return items


def proof_text(p: Union[Proof, str, Dict[str, Any]]) -> str:
    """The claim as copy may state it."""
    if isinstance(p, Proof):
        return p.claim
    if isinstance(p, dict):
        return str(p.get("claim") or "")
    return str(p)


def expires_on(p: Proof) -> Optional[date]:
    days = p.valid_days if p.valid_days is not None else kinds().get(p.kind or "", {}).get("valid_days")
    start = _parse_date(p.date)
    if days is None or start is None:
        return None
    return start + timedelta(days=int(days))


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def usable(p: Proof, scope: str, today: Today = None, root: Optional[str] = None) -> Tuple[bool, str]:
    """(True, "") usable; (True, warning) usable with a warning (legacy item);
    (False, reason) refused. scope is the use of the copy: ads, carousel,
    posts, outreach, site or video. root: the project-context folder, to check
    that a file source exists."""
    if p.legacy:
        if p.errors:
            return False, "malformed: " + "; ".join(p.errors)
        return True, "legacy string item: no kind, no source, no date. Convert it to an object with its source and date"
    if p.errors:
        return False, "malformed: " + "; ".join(p.errors)
    day = _as_date(today)
    rules = kinds()[p.kind or ""]
    if rules["requires_source"] and not p.source:
        return False, f"a {p.kind} needs a source (a URL or a file of the project): none recorded"
    if rules["requires_date"] and not p.date:
        return False, f"a {p.kind} needs the date of the fact: none recorded"
    start = _parse_date(p.date)
    if start and start > day:
        return False, f"dated {p.date}, after today ({day.isoformat()}): the date is the day of the fact"
    end = expires_on(p)
    if end and day > end:
        days = p.valid_days if p.valid_days is not None else rules["valid_days"]
        return False, (f"stale: {p.kind} of {p.date}, valid {days} days, expired on {end.isoformat()}. "
                       "Measure it again and update the claim and its date")
    if rules["requires_consent"]:
        c = p.consent or {}
        status = c.get("status", "unknown")
        if status == "refused":
            return False, f"consent refused ({c.get('date', 'no date')}, {c.get('by', 'no record')}): never use it"
        if status != "granted":
            return False, f"consent {status}: ask the {('customer' if p.kind == 'customer' else 'person quoted')} before any use"
        if not c.get("date") or not c.get("by"):
            return False, "consent granted without its date or who gave it: record both"
        covered = c.get("scope") or []
        if scope not in covered:
            return False, f"consent covers {', '.join(covered) or 'no use'}, not {scope}"
    if root and p.source and not _is_url(p.source):
        rel = p.source.split("#", 1)[0]
        if not os.path.isfile(os.path.join(root, rel)):
            return False, f"source file {rel} not found under the project-context folder"
    return True, ""


def partition(items: List[Proof], scope: str, today: Today = None,
              root: Optional[str] = None) -> Tuple[List[Proof], List[Tuple[Proof, str]], List[Tuple[Proof, str]]]:
    """(usable, refused with reason, warnings with text)."""
    ok_items: List[Proof] = []
    refused: List[Tuple[Proof, str]] = []
    warnings: List[Tuple[Proof, str]] = []
    for p in items:
        ok, reason = usable(p, scope, today, root)
        if ok:
            ok_items.append(p)
            if reason:
                warnings.append((p, reason))
        else:
            refused.append((p, reason))
    return ok_items, refused, warnings


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Status of every proof item for a scope")
    c.add_argument("context", help="context.json")
    c.add_argument("--scope", default="posts", help="Use of the copy (default posts)")
    c.add_argument("--today", help="YYYY-MM-DD (default: today)")
    c.add_argument("--root", help="project-context folder: also check that file sources exist")
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.scope not in scopes():
        print(f"error: --scope must be one of {', '.join(scopes())}", file=sys.stderr)
        return 2
    try:
        today = _as_date(a.today)
    except ValueError:
        print(f"error: --today {a.today!r} is not YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        with open(a.context, "r", encoding="utf-8") as f:
            context = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"{a.context}: cannot read: {e}", file=sys.stderr)
        return 2
    root = a.root or os.path.dirname(os.path.abspath(a.context))
    items = load_proof(context)
    rows = []
    for p in items:
        ok, reason = usable(p, a.scope, today, root)
        status = "refused" if not ok else ("warning" if reason else "usable")
        rows.append({"index": p.index, "id": p.id, "kind": p.kind, "status": status, "reason": reason,
                     "claim": p.claim, "errors": p.errors})
    malformed = [r for r in rows if r["errors"]]
    if a.json:
        print(json.dumps({"scope": a.scope, "today": today.isoformat(), "items": rows,
                          "counts": {s: sum(r["status"] == s for r in rows) for s in ("usable", "warning", "refused")},
                          "malformed": len(malformed)}, ensure_ascii=False, indent=2))
    else:
        if not rows:
            print("positioning.proof is empty: every copy is written proof-free.")
        for r in rows:
            line = f"positioning.proof[{r['index']}] {r['id']}: {r['status']}"
            print(line + (f": {r['reason']}" if r["reason"] else ""))
        print(f"{sum(r['status'] == 'usable' for r in rows)} usable, {sum(r['status'] == 'warning' for r in rows)} warning, "
              f"{sum(r['status'] == 'refused' for r in rows)} refused for scope {a.scope} on {today.isoformat()}.")
    return 1 if malformed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
