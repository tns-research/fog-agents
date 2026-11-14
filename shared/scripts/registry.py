#!/usr/bin/env python3
"""
registry.py

Reads the people and partners registries of a project (people.json,
partners.json in <project>/project-context/) and says whether a person or a
company may appear in a deliverable. Standard library only (Python 3.8+).

Contracts: shared/schemas/people.schema.json, shared/schemas/partners.schema.json.
Every asset path (photo, logo, logo_on_dark) is relative to the project-context
folder.

Rule: a person or a logo goes into a visual or a copy only when
consent.status is granted, the consent has its date and source, and its scope
covers the use (ads for static-ads-builder, carousel for carousel-builder,
posts, outreach, site, video). An entry absent from the registry is consent
unknown: blocked. The person marked is_operator (the founder running the
agent) needs no recorded consent.

As a module:
    from registry import load_people, load_partners, allowed, is_operator, find, asset_path, logo_for
    people = load_people(ctx_dir)                     # [] when people.json is absent
    ok, reason = allowed(find(people, "Ana Ruiz"), "ads")
    path = logo_for(find(load_partners(ctx_dir), "acme"), "dark", ctx_dir)

Usage:
    python3 shared/scripts/registry.py check <project-context>
    python3 shared/scripts/registry.py allowed <project-context> --scope ads [--json]

check validates both files against their schema, then the rules a schema
cannot hold: unique slugs, a granted consent with its scope, date and source,
no photo stored without granted consent (operator excepted), asset files
present. allowed lists every entry with its decision for the scope.

Exit codes: 0 ok, 1 at least one error, 2 usage error or unreadable file.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS = os.path.join(os.path.dirname(HERE), "schemas")
SCOPES = ("ads", "carousel", "posts", "outreach", "site", "video")
FILES = {"people": ("people.json", "people.schema.json", ("photo",)),
         "partners": ("partners.json", "partners.schema.json", ("logo", "logo_on_dark"))}

sys.path.insert(0, HERE)
from validate_json import validate  # noqa: E402


class RegistryError(Exception):
    """A registry file that cannot be read or is not JSON."""


def _read(ctx_dir: str, kind: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(ctx_dir, FILES[kind][0])
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RegistryError(f"{path}: cannot read: {e}")
    return data


def _entries(ctx_dir: str, kind: str) -> List[Dict[str, Any]]:
    data = _read(ctx_dir, kind)
    if not isinstance(data, dict) or not isinstance(data.get(kind), list):
        return []
    return [e for e in data[kind] if isinstance(e, dict)]


def load_people(ctx_dir: str) -> List[Dict[str, Any]]:
    """Entries of people.json; [] when the file is absent."""
    return _entries(ctx_dir, "people")


def load_partners(ctx_dir: str) -> List[Dict[str, Any]]:
    """Entries of partners.json; [] when the file is absent."""
    return _entries(ctx_dir, "partners")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def find(entries: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    """The entry whose slug or name matches key (case and accents ignored)."""
    want = _fold(key)
    for e in entries:
        if _fold(e.get("slug", "")) == want or _fold(e.get("name", "")) == want:
            return e
    return None


def is_operator(entry: Optional[Dict[str, Any]]) -> bool:
    return bool(entry) and entry.get("is_operator") is True


def allowed(entry: Optional[Dict[str, Any]], scope: str) -> Tuple[bool, str]:
    """(True, why) when the entry may appear in a deliverable of this scope,
    (False, reason) otherwise. None (not in the registry) is consent unknown."""
    if scope not in SCOPES:
        return False, f"unknown scope {scope!r}: one of {', '.join(SCOPES)}"
    if not entry:
        return False, "not in the registry: consent unknown, blocked. Add the entry with its consent"
    name = entry.get("name") or entry.get("slug") or "entry"
    if is_operator(entry):
        return True, f"{name} is the operator (the founder running the agent)"
    c = entry.get("consent") if isinstance(entry.get("consent"), dict) else {}
    status = c.get("status", "unknown")
    if status == "refused":
        return False, f"{name}: consent refused ({c.get('date', 'no date')}, {c.get('source', 'no record')}). Never use"
    if status != "granted":
        return False, f"{name}: consent {status}. Ask before any use and record the answer"
    if not c.get("date") or not c.get("source"):
        return False, f"{name}: consent granted without its date or source. Record both"
    covered = [s for s in c.get("scope") or [] if isinstance(s, str)]
    if scope not in covered:
        return False, f"{name}: consent covers {', '.join(covered) or 'no use'}, not {scope}"
    return True, f"{name}: consent granted for {scope} on {c['date']} ({c['source']})"


def asset_path(ctx_dir: str, rel: Optional[str]) -> Optional[str]:
    """Absolute path of an asset of the registry, or None."""
    if not rel:
        return None
    return os.path.join(ctx_dir, rel)


def logo_for(entry: Optional[Dict[str, Any]], background: str, ctx_dir: str) -> Optional[str]:
    """The logo file for a light or dark background. A dark background takes
    logo_on_dark only: placing the light-background logo on dark is a contrast
    check the caller must run, never a silent fallback."""
    if not entry:
        return None
    key = "logo_on_dark" if background == "dark" else "logo"
    return asset_path(ctx_dir, entry.get(key))


def check(ctx_dir: str) -> List[str]:
    errors: List[str] = []
    for kind, (fname, sname, asset_keys) in FILES.items():
        try:
            data = _read(ctx_dir, kind)
        except RegistryError as e:
            errors.append(str(e))
            continue
        if data is None:
            continue
        with open(os.path.join(SCHEMAS, sname), "r", encoding="utf-8") as f:
            schema = json.load(f)
        errors += [f"{fname}: {e}" for e in validate(data, schema)]
        seen: Dict[str, int] = {}
        for i, e in enumerate(data.get(kind) or []):
            if not isinstance(e, dict):
                continue
            where = f"{fname}: {kind}[{i}] {e.get('slug', '?')}"
            slug = e.get("slug")
            if slug in seen:
                errors.append(f"{where}: slug already used by {kind}[{seen[slug]}]")
            seen.setdefault(slug, i)
            c = e.get("consent") if isinstance(e.get("consent"), dict) else {}
            if c.get("status") == "granted":
                if not c.get("scope"):
                    errors.append(f"{where}: consent granted with no scope: list the uses covered")
                if not c.get("date") or not c.get("source"):
                    errors.append(f"{where}: consent granted without its date or source")
            if kind == "people" and e.get("photo") and c.get("status") != "granted" and not is_operator(e):
                errors.append(f"{where}: photo stored without granted consent: delete the file and the field, or record the consent")
            for key in asset_keys:
                rel = e.get(key)
                if isinstance(rel, str) and not os.path.isfile(os.path.join(ctx_dir, rel)):
                    errors.append(f"{where}: {key} {rel} not found under the project-context folder")
    return errors


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="Validate people.json and partners.json")
    c.add_argument("ctx", help="project-context folder")
    al = sub.add_parser("allowed", help="Decision for every entry, for one scope")
    al.add_argument("ctx", help="project-context folder")
    al.add_argument("--scope", required=True, choices=SCOPES)
    al.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.ctx):
        print(f"error: {a.ctx} is not a folder", file=sys.stderr)
        return 2
    if a.cmd == "check":
        errors = check(a.ctx)
        for e in errors:
            print(e)
        found = [f for f, _, _ in FILES.values() if os.path.isfile(os.path.join(a.ctx, f))]
        print(f"{len(errors)} errors in {', '.join(found) or 'no registry file'}.")
        return 1 if errors else 0
    try:
        rows = []
        for kind, entries in (("people", load_people(a.ctx)), ("partners", load_partners(a.ctx))):
            for e in entries:
                ok, reason = allowed(e, a.scope)
                rows.append({"kind": kind, "slug": e.get("slug"), "name": e.get("name"), "allowed": ok, "reason": reason})
    except RegistryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({"scope": a.scope, "entries": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{'allowed' if r['allowed'] else 'blocked'}  {r['kind']}/{r['slug']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
