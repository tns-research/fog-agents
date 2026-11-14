#!/usr/bin/env python3
"""
build_sequence_export.py

Companion script for the cold-outreach-builder agent (workflow Step 8).
Merges the sequence, the prospect list, the tiers and the per-prospect
messages into one generic CSV that any sequencer or mail-merge tool can
import: one row per prospect, every step's subject and body already written
or rendered for that prospect, plus the delay before each step.

Standard library only (Python 3.9+).

Usage:
    python3 build_sequence_export.py \
        --sequence <run>/cold-outreach-output.json \
        --leads    <run>/leads.csv \
        --out      <run>/sequence-export.csv \
        [--tiers <run>/tiers.json] [--messages <run>/messages.json] \
        [--dossiers <run>/dossiers] [--state <state.json>] \
        [--sender-first-name NAME] [--channel email|linkedin]

Inputs:
  --sequence  JSON with a top-level "sequence" array (the agent's sidecar).
              Each step: {"n": 1, "day": 0, "subjects": [{"variant": "A",
              "text": "..."}], "body": "..."}. "day" is the day offset from
              the first send; "subjects" may be empty for a threaded
              follow-up. "channel" at the top level is used when --channel
              is not given. These are the templates tier B rows receive.
  --leads     CSV with a header row (run_dossiers.py writes <run>/leads.csv).
              Recognized columns: prospect_id, email, first_name, last_name,
              name, company, role, linkedin_url, linkedin, profile_url,
              specific_observation, personal_hook, source_url. Any extra
              column is kept and usable as a {{token}}.
  --tiers     tiers.json from score_prospects.py. Tier C rows and rows absent
              from it are skipped with their reason. Without it every row is
              treated as tier B (V1 behavior).
  --messages  JSON object keyed by prospect_id: {"hook": "...",
              "hook_fact_id": "f1", "angle": "...", "steps": [{"n": 1,
              "subject": "...", "body": "..."}]}. hook and angle become
              tokens; steps (tier A) replace the template step of the same n.
              "hold": "<reason>" keeps the prospect out of the export (a row
              that still blocks the lint after three passes).
  --dossiers  Fills hook_source_url and hook_date from the fact
              hook_fact_id of each prospect.json.
  --state     state.json of outreach_state.py: contacts already in a
              sequence, suppressed, or touched under the recontact delay are
              skipped.
  --sender-first-name  Renders {{sender_first_name}}. Without it the token
              stays in the export for the sequencer to fill (it is the only
              token allowed to stay).

Template syntax:
  {{token}}    replaced by the prospect's value; an empty value skips the row.
  {{?token}}   optional: the whole line is dropped when the value is empty.

Output columns, in order:
  prospect_id, tier, email, first_name, last_name, company, role,
  linkedin_url, hook, hook_fact_id, hook_source_url, hook_date, angle,
  specific_observation, personal_hook, source_url, subject_variant,
  then for each step N: step_N_subject, step_N_body, step_N_delay_days,
  then any extra columns from the leads file.

Rows are skipped (never half-rendered) when the tier is C or unknown, the
state excludes them, the contact field the channel needs is empty, or a
{{token}} has no value. Skipped rows go to stderr and <out>.skipped.csv.
The export is then linted with lint_outreach.py; this script does not judge
the copy.

Exit codes: 0 success (even with skipped rows), 1 bad input.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import ASSETS, load_json, InputError  # noqa: E402

TOKEN_RE = re.compile(r"\{\{\s*(\??)\s*([A-Za-z0-9_]+)\s*\}\}")

BASE_COLUMNS = [
    "prospect_id", "tier", "email", "first_name", "last_name", "company", "role", "linkedin_url",
    "hook", "hook_fact_id", "hook_source_url", "hook_date", "angle",
    "specific_observation", "personal_hook", "source_url",
]

# Columns consumed to build BASE_COLUMNS; not repeated as extra fields.
ALIAS_COLUMNS = {"name", "linkedin"}


def fail(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def read_json_or_fail(path: str, what: str):
    try:
        return load_json(path)
    except InputError as e:
        fail(f"{what}: {e}")


def load_sequence(path: str) -> Tuple[List[dict], str]:
    data = read_json_or_fail(path, "sequence")
    steps = data.get("sequence") if isinstance(data, dict) else None
    if not isinstance(steps, list) or not steps:
        fail("sequence JSON has no non-empty 'sequence' array")
    steps = sorted(steps, key=lambda s: (s.get("day", 0), s.get("n", 0)))
    for i, step in enumerate(steps, start=1):
        if not isinstance(step.get("body"), str) or not step["body"].strip():
            fail(f"step {i} has no body")
        step.setdefault("n", i)
    channel = data.get("channel", "email") if isinstance(data, dict) else "email"
    return steps, channel


def normalize_lead(row: Dict[str, str]) -> Dict[str, str]:
    lead = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k}
    if not lead.get("first_name") and lead.get("name"):
        parts = lead["name"].split()
        lead["first_name"] = parts[0]
        lead.setdefault("last_name", " ".join(parts[1:]))
    if not lead.get("linkedin_url") and lead.get("linkedin"):
        lead["linkedin_url"] = lead["linkedin"]
    for col in BASE_COLUMNS:
        lead.setdefault(col, "")
    return lead


def render(template: str, values: Dict[str, str], keep: List[str]) -> Tuple[str, List[str]]:
    """Render tokens; drop lines whose optional token is empty. Returns (text, missing tokens)."""
    missing: List[str] = []
    out_lines: List[str] = []
    for line in template.split("\n"):
        optional_empty = any(m.group(1) == "?" and not values.get(m.group(2), "")
                             for m in TOKEN_RE.finditer(line))
        if optional_empty:
            continue

        def sub(m: "re.Match[str]") -> str:
            key = m.group(2)
            value = values.get(key, "")
            if value:
                return value
            if key in keep:
                return "{{" + key + "}}"
            missing.append(key)
            return m.group(0)

        out_lines.append(TOKEN_RE.sub(sub, line))
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    return text, missing


def pick_subject(step: dict, variant: str) -> str:
    subjects = step.get("subjects") or []
    if isinstance(subjects, str):
        return subjects
    for s in subjects:
        if isinstance(s, dict) and s.get("variant") == variant:
            return s.get("text", "")
    first = subjects[0] if subjects else {}
    return first.get("text", "") if isinstance(first, dict) else ""


def load_tiers(path: Optional[str]) -> Optional[Dict[str, dict]]:
    if not path:
        return None
    data = read_json_or_fail(path, "tiers")
    return {p["prospect_id"]: p for p in data.get("prospects", []) if isinstance(p, dict) and "prospect_id" in p}


def load_facts(dossiers: Optional[str], pid: str) -> Dict[str, dict]:
    if not dossiers or not pid:
        return {}
    path = os.path.join(dossiers, pid, "prospect.json")
    if not os.path.isfile(path):
        return {}
    try:
        data = load_json(path)
    except InputError:
        return {}
    return {f.get("id"): f for f in data.get("facts", []) if isinstance(f, dict)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a sequencer-agnostic CSV export for cold-outreach-builder")
    ap.add_argument("--sequence", required=True, help="Sidecar JSON with the 'sequence' array")
    ap.add_argument("--leads", required=True, help="Leads CSV (run_dossiers.py writes <run>/leads.csv)")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--channel", choices=["email", "linkedin"], help="Overrides the sidecar channel")
    ap.add_argument("--tiers", help="tiers.json from score_prospects.py")
    ap.add_argument("--messages", help="messages.json: hooks per prospect, full steps for tier A")
    ap.add_argument("--dossiers", help="Dossiers folder, to fill hook_source_url and hook_date")
    ap.add_argument("--state", help="state.json of outreach_state.py, to skip contacts already in a sequence")
    ap.add_argument("--sender-first-name", help="Renders {{sender_first_name}}; otherwise the token stays")
    ap.add_argument("--today", help="Reference date for the state check, YYYY-MM-DD")
    args = ap.parse_args()

    steps, channel = load_sequence(args.sequence)
    channel = args.channel or channel
    if channel not in ("email", "linkedin"):
        fail(f"unknown channel '{channel}'")
    tiers = load_tiers(args.tiers)
    messages = read_json_or_fail(args.messages, "messages") if args.messages else {}
    if not isinstance(messages, dict):
        fail("messages JSON must be an object keyed by prospect_id")
    limits = read_json_or_fail(os.path.join(ASSETS, "limits.json"), "limits")
    keep = list(limits.get("tokens", {}).get("allowed_unfilled", []))

    state = None
    recontact = int(limits.get("state", {}).get("recontact_after_days", 180))
    if args.state:
        from outreach_state import exclusion_reason, load_state
        try:
            state = load_state(args.state)
        except InputError as e:
            fail(str(e))
    today = date.today()
    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            fail("--today must be YYYY-MM-DD")

    try:
        with open(args.leads, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = [h.strip() for h in (reader.fieldnames or []) if h]
            leads = [normalize_lead(r) for r in reader]
    except OSError as e:
        fail(f"cannot read leads CSV {args.leads}: {e}")

    extra_columns = [h for h in header if h not in BASE_COLUMNS and h not in ALIAS_COLUMNS]

    # Subject variants of the first step rotate across rows (A/B/C split test).
    first_subjects = steps[0].get("subjects") or []
    variants = [s.get("variant") for s in first_subjects if isinstance(s, dict) and s.get("variant")] or [""]

    step_columns: List[str] = []
    for i in range(1, len(steps) + 1):
        step_columns += [f"step_{i}_subject", f"step_{i}_body", f"step_{i}_delay_days"]
    out_columns = BASE_COLUMNS + ["subject_variant"] + step_columns + extra_columns

    rows: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for idx, lead in enumerate(leads):
        full_name = " ".join(x for x in (lead["first_name"], lead["last_name"]) if x)
        who = lead["email"] or lead["linkedin_url"] or lead.get("profile_url") or full_name or f"CSV line {idx + 2}"
        pid = lead.get("prospect_id", "")

        tier_info = None
        if tiers is not None:
            tier_info = tiers.get(pid)
            if not tier_info:
                skipped.append({"prospect": who, "reason": "not scored (absent from tiers.json)"})
                continue
            if tier_info.get("tier") not in ("A", "B"):
                skipped.append({"prospect": who, "reason": "tier C: " + "; ".join(tier_info.get("reasons", []))})
                continue
            lead["tier"] = tier_info["tier"]
        else:
            lead["tier"] = lead.get("tier") or "B"

        if state is not None:
            why = exclusion_reason(state, lead, today, recontact)
            if why:
                skipped.append({"prospect": who, "reason": f"state: {why}"})
                continue

        if channel == "email" and not lead["email"]:
            skipped.append({"prospect": who, "reason": "no email for the email channel"})
            continue
        if channel == "linkedin" and not (lead["linkedin_url"] or lead.get("profile_url")):
            skipped.append({"prospect": who, "reason": "no linkedin_url or profile_url for the linkedin channel"})
            continue

        msg = messages.get(pid, {}) if pid else {}
        if msg.get("hold"):
            skipped.append({"prospect": who, "reason": f"held: {msg['hold']}"})
            continue
        for k in ("hook", "hook_fact_id", "angle"):
            if msg.get(k):
                lead[k] = str(msg[k])
        fact = load_facts(args.dossiers, pid).get(lead.get("hook_fact_id", ""))
        if fact:
            lead["hook_source_url"] = fact.get("source_url", "")
            lead["hook_date"] = fact.get("date", "")
        values = dict(lead)
        if args.sender_first_name:
            values["sender_first_name"] = args.sender_first_name

        personal = {int(s.get("n", 0)): s for s in msg.get("steps", []) if isinstance(s, dict)}
        if lead["tier"] == "A" and not personal:
            print(f"[warn] {who}: tier A without personal steps in messages.json, template used", file=sys.stderr)

        variant = variants[len(rows) % len(variants)]
        out = {col: lead.get(col, "") for col in BASE_COLUMNS + extra_columns}
        out["subject_variant"] = variant
        missing_all: List[str] = []
        previous_day = None
        for i, step in enumerate(steps, start=1):
            own = personal.get(int(step.get("n", i)))
            subject_t = own.get("subject", "") if own and "subject" in own else pick_subject(step, variant)
            body_t = own["body"] if own and own.get("body") else step["body"]
            subject, miss_s = render(subject_t, values, keep)
            body, miss_b = render(body_t, values, keep)
            missing_all += miss_s + miss_b
            day = int(step.get("day", 0))
            out[f"step_{i}_subject"] = subject
            out[f"step_{i}_body"] = body
            out[f"step_{i}_delay_days"] = str(0 if previous_day is None else max(day - previous_day, 0))
            previous_day = day
        if missing_all:
            tokens = ", ".join(sorted(set(missing_all)))
            skipped.append({"prospect": who, "reason": f"unresolved tokens: {tokens}"})
            continue
        rows.append(out)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns)
        writer.writeheader()
        writer.writerows(rows)

    skipped_path = args.out + ".skipped.csv"
    if skipped:
        with open(skipped_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["prospect", "reason"])
            writer.writeheader()
            writer.writerows(skipped)
        for s in skipped:
            print(f"[warn] skipped {s['prospect']}: {s['reason']}", file=sys.stderr)
    elif os.path.exists(skipped_path):
        os.remove(skipped_path)

    print(f"[info] wrote {len(rows)} prospect row(s) x {len(steps)} step(s) to {args.out}; skipped {len(skipped)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
