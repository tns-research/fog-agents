#!/usr/bin/env python3
"""
check_report.py

Gate on the seo-audit report and the briefs: a current title, meta
description or H1 is quoted only with the crawl line it comes from, and
matches that line word for word. The April 2026 run wrote "Current title
(likely): ..." for pages it never fetched; this check makes that impossible.

    python3 check_report.py <run>/seo-audit-<date>.md --crawl <run>/crawl.jsonl
    python3 check_report.py <project>/seo-audit/briefs/*/brief.md --crawl <run>/crawl.jsonl --json
    python3 check_report.py <run>/seo-audit-<date>.md --crawl <run>/crawl.jsonl --eeat <run>/eeat.json

Accepted forms (the template uses the first one):

    **Current title:** `Pricing | Acme` (crawl.jsonl:12)
    | URL | Current title | ... |      a table column named "Current title",
    | /pricing/ | `Pricing | Acme` (crawl.jsonl:12) | ... |      "Current meta description" or "Current H1"

A field the page does not have is written `(missing)` with its crawl line.

E-E-A-T is measured by eeat.py, never scored by the model. With --eeat, the
site score line and every "E-E-A-T score" table cell must equal eeat.json:

    **E-E-A-T site score:** 74 (eeat.json)
    | URL | Kind | E-E-A-T score | Missing signals |
    | https://acme.example/blog/x/ (crawl.jsonl:7) | article | 100 | none |

Codes (all BLOCK):
  no-crawl-ref     a current title, description or H1 without crawl.jsonl:N
  bad-crawl-ref    the line number is not in the crawl file
  mismatch         the quoted value differs from the crawl line
  no-value         no backticked value next to the label
  guessed-current  "likely", "probably", "seems" ... on a current-state line
  eeat-mismatch    an E-E-A-T score that differs from eeat.json
  eeat-no-source   an E-E-A-T score quoted without --eeat eeat.json
  eeat-model-score an E-E-A-T rating out of 3, 4, 10, 15... (the old checklist
                   format): the score comes from eeat.py only

Exit codes: 0 no BLOCK, 1 at least one BLOCK, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import InputError, load_json, read_jsonl  # noqa: E402

LABEL_RE = re.compile(r"current\s+(title|meta\s+description|description|meta|h1)\b", re.I)
# A quoted value is introduced by a label and a colon ("**Current title:**", "Current title (likely):");
# prose that merely mentions "current titles" is not a quote.
QUOTE_RE = re.compile(r"current\s+(title|meta\s+description|description|meta|h1)\s*(?:\([^)]*\))?\s*\**\s*:", re.I)
REF_RE = re.compile(r"crawl(?:\.jsonl)?:(\d+)")
TICK_RE = re.compile(r"`([^`]*)`")
HEDGE_RE = re.compile(r"\b(likely|probably|presumably|seems?|appears?|guess(?:ed)?|assum(?:e|ed|ing)|approximately|roughly)\b", re.I)
EEAT_SITE_RE = re.compile(r"e-e-a-t\s+site\s+score\s*\**\s*:\s*\**\s*(n/a|\d+)", re.I)
EEAT_COL_RE = re.compile(r"e-e-a-t\s+score", re.I)
EEAT_WORD_RE = re.compile(r"e-e-a-t|eeat|\bexperience\b|\bexpertise\b|authoritativeness|trustworthiness", re.I)
RATING_RE = re.compile(r"(?<![\d/.])\d{1,2}(?:\.\d)?\s*/\s*(?!100\b)\d{1,2}\b(?!\s*/)")
URL_RE = re.compile(r"https?://[^\s)|`]+")
FIELD = {"title": "title", "meta description": "meta_description", "description": "meta_description",
         "meta": "meta_description", "h1": "h1"}


def norm(s: Optional[str]) -> str:
    return " ".join((s or "").replace("\\|", "|").split())


def split_row(line: str) -> List[str]:
    """Split a markdown table row on pipes outside code spans; an escaped pipe stays in its cell."""
    cells, buf, in_tick, i = [], [], False, 0
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            buf.append("\\|")
            i += 2
            continue
        if ch == "`":
            in_tick = not in_tick
        if ch == "|" and not in_tick:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def field_of(label: str) -> str:
    return FIELD[" ".join(label.lower().split())]


def compare(rec: Dict[str, Any], field: str, value: str) -> bool:
    v = norm(value)
    if field == "h1":
        h1s = [norm(h) for h in rec.get("h1") or []]
        return (v == "(missing)" and not h1s) or v in h1s
    actual = norm(rec.get(field))
    return (v == "(missing)" and not actual) or v == actual


def check_text(text: str, crawl: Dict[int, Dict[str, Any]], crawl_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    lines = text.splitlines()
    table_fields: Dict[int, str] = {}
    in_code = False
    for n, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        cells = split_row(line) if line.strip().startswith("|") else None
        if cells is not None:
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            header_hit = {i: field_of(LABEL_RE.search(c).group(1)) for i, c in enumerate(cells) if LABEL_RE.fullmatch(c.strip("* "))}
            if header_hit:
                table_fields = header_hit
                continue
            if table_fields:
                for i, field in table_fields.items():
                    if i >= len(cells):
                        continue
                    out.extend(check_item(n, cells[i], line, field, crawl, crawl_name))
                continue
        else:
            table_fields = {}
        m = QUOTE_RE.search(line)
        if not m:
            continue
        if line.lstrip().startswith("#"):
            continue
        out.extend(check_item(n, line[m.end():], line, field_of(m.group(1)), crawl, crawl_name))
    return out


def check_item(n: int, segment: str, line: str, field: str, crawl: Dict[int, Dict[str, Any]], crawl_name: str) -> List[Dict[str, Any]]:
    issues = []
    if HEDGE_RE.search(line):
        issues.append({"line": n, "code": "guessed-current", "message": "current state is read from the crawl, never guessed"})
    refs = REF_RE.findall(line)
    ticks = TICK_RE.findall(segment)
    if not refs:
        issues.append({"line": n, "code": "no-crawl-ref", "message": f"current {field} quoted without its {crawl_name}:N line"})
        return issues
    if not ticks:
        issues.append({"line": n, "code": "no-value", "message": f"current {field}: put the value in backticks, or `(missing)`"})
        return issues
    ref = int(refs[0])
    rec = crawl.get(ref)
    if rec is None:
        issues.append({"line": n, "code": "bad-crawl-ref", "message": f"{crawl_name}:{ref} does not exist"})
        return issues
    if not compare(rec, field, ticks[0]):
        actual = rec.get(field)
        issues.append({"line": n, "code": "mismatch",
                       "message": f"current {field} differs from {crawl_name}:{ref} ({rec.get('url')}): crawl says {json.dumps(actual, ensure_ascii=False)}"})
    return issues


def check_eeat(text: str, eeat: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    pages = {p["url"]: p.get("score") for p in (eeat or {}).get("pages", [])}
    col: Optional[int] = None
    in_code = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = EEAT_SITE_RE.search(line)
        if m:
            if eeat is None:
                out.append({"line": n, "code": "eeat-no-source", "message": "E-E-A-T score quoted without eeat.json: run eeat.py and pass --eeat"})
            elif m.group(1).lower() != str(eeat.get("site_score")).lower().replace("none", "n/a"):
                out.append({"line": n, "code": "eeat-mismatch", "message": f"site score {m.group(1)} differs from eeat.json ({eeat.get('site_score')})"})
            continue
        if line.strip().startswith("|"):
            cells = split_row(line)
            hit = [i for i, c in enumerate(cells) if EEAT_COL_RE.fullmatch(c.strip("* "))]
            if hit:
                col = hit[0]
                continue
            if col is not None and not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                urls = [u for c in cells for u in URL_RE.findall(c)]
                if col < len(cells) and urls:
                    got = cells[col].strip("*` ")
                    if eeat is None:
                        out.append({"line": n, "code": "eeat-no-source", "message": "E-E-A-T score quoted without eeat.json: run eeat.py and pass --eeat"})
                    elif urls[0] not in pages:
                        out.append({"line": n, "code": "eeat-mismatch", "message": f"{urls[0]} is not in eeat.json"})
                    else:
                        want = pages[urls[0]]
                        if got.lower() != ("n/a" if want is None else str(want)):
                            out.append({"line": n, "code": "eeat-mismatch", "message": f"{urls[0]}: score {got} differs from eeat.json ({want})"})
                continue
        else:
            col = None
        if EEAT_WORD_RE.search(line) and RATING_RE.search(line):
            out.append({"line": n, "code": "eeat-model-score", "message": "E-E-A-T rated by hand: copy the eeat.json scores, comment the signals"})
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Every current title, description or H1 in a report cites its crawl.jsonl line and matches it.")
    ap.add_argument("files", nargs="+", help="report or brief markdown files")
    ap.add_argument("--crawl", required=True, help="crawl.jsonl of the run")
    ap.add_argument("--json", action="store_true", help="print the findings as JSON")
    ap.add_argument("--eeat", help="eeat.json of the run: E-E-A-T scores in the report must equal it")
    args = ap.parse_args(argv)
    try:
        crawl = {n: rec for n, rec in read_jsonl(args.crawl)}
        eeat = load_json(args.eeat) if args.eeat else None
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    name = os.path.basename(args.crawl)
    findings = []
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        for item in check_text(text, crawl, name) + check_eeat(text, eeat):
            item["file"] = path
            findings.append(item)
    if args.json:
        print(json.dumps({"block": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"BLOCK {f['code']} {f['file']}:{f['line']}  {f['message']}")
        print(f"check_report: {len(findings)} BLOCK in {len(args.files)} file(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
