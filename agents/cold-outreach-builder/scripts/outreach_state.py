#!/usr/bin/env python3
"""
outreach_state.py

Memory of cold-outreach-builder between runs: who was contacted, when, in
which sequence, at which step, what they answered, who must never be
contacted again. One JSON file per project, standard library only,
Python 3.9+.

    <your-projects-root>/<project>/cold-outreach-builder/state/state.json

Commands:
  init      --state S
  check     --state S --leads CSV [--out excluded.csv] [--today D] [--recontact-after-days N]
            Which leads must not enter a new sequence: suppressed, in an
            open sequence, or touched less than N days ago (default
            state.recontact_after_days of assets/limits.json).
  register  --state S --export sequence-export.csv --sequence-id ID --start-date D
            Records every exported row with its planned step dates
            (status scheduled). Run it when the founder imports the file.
            A contact already in an open sequence is refused (exit 1)
            unless --force.
  mark-sent --state S --sequence-id ID --through-step N --date D [--contact KEY]
            Records the steps the founder's tool really sent (a paused
            contact becomes active again).
  suppress  --state S --contact KEY --reason TEXT
  answered  --state S --contact KEY [--note TEXT]
            The founder answered a positive or off-topic reply: it leaves the
            "answer" list of due.
  due       --state S [--today D] [--out followups-<date>.md]
            Deterministic next actions: replies to answer, out-of-office
            contacts to resume, planned steps due, sequences finished.
  summary   --state S [--by sequence|tier|angle]
            Contacts, steps sent and replies per class with their counts.
            Never names a winner: compare classified replies, with the
            sample size, and decide yourself.
  show      --state S --contact KEY

KEY is the contact key: email:<address>, linkedin:<host/path>, or id:<id>
(an address or a LinkedIn URL is accepted and converted).

Statuses: scheduled, active, paused (out of office), replied_positive,
replied_negative, off_topic, bounced, unsubscribed, completed. Statuses
other than scheduled, active and paused close the sequence; bounced,
unsubscribed and replied_negative also suppress the contact for good.

Exit codes: 0 done, 1 refused (conflict, unknown contact), 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (ASSETS, InputError, contact_key, load_json,  # noqa: E402
                          normalize_email, normalize_linkedin, parse_day, read_csv,
                          today_or, write_csv, write_json)

OPEN = {"scheduled", "active", "paused"}
SUPPRESSING = {"bounced", "unsubscribed", "replied_negative"}
CLOSED = {"replied_positive", "replied_negative", "off_topic", "bounced", "unsubscribed", "completed"}
LIMITS = os.path.join(ASSETS, "limits.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_state() -> Dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": now_iso(), "contacts": {}, "processed_messages": []}


def load_state(path: str, create: bool = False) -> Dict[str, Any]:
    if not os.path.isfile(path):
        if create:
            return empty_state()
        raise InputError(f"{path} not found: run 'outreach_state.py init --state {path}' first")
    data = load_json(path)
    if not isinstance(data, dict) or "contacts" not in data:
        raise InputError(f"{path} is not a cold-outreach state file")
    data.setdefault("processed_messages", [])
    return data


def save_state(path: str, state: Dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(path, state)


def to_key(value: str) -> str:
    value = (value or "").strip()
    if re.match(r"^(email|linkedin|id):", value):
        return value
    if "@" in value:
        return "email:" + normalize_email(value)
    if "linkedin.com" in value.lower():
        return "linkedin:" + normalize_linkedin(value)
    return "id:" + value


def find_contact(state: Dict[str, Any], row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Find a contact by email, then LinkedIn URL (a lead may carry both)."""
    contacts = state["contacts"]
    email = normalize_email(row.get("email", ""))
    if email and "email:" + email in contacts:
        return contacts["email:" + email]
    li = normalize_linkedin(row.get("linkedin_url") or row.get("linkedin") or "")
    for c in contacts.values():
        if email and normalize_email(c.get("email", "")) == email:
            return c
        if li and normalize_linkedin(c.get("linkedin_url", "")) == li:
            return c
    return None


def exclusion_reason(state: Dict[str, Any], row: Dict[str, str], today, recontact_days: int) -> str:
    """Why this lead must not enter a new sequence, or '' when it may."""
    c = find_contact(state, row)
    if not c:
        return ""
    if c.get("suppressed"):
        return f"suppressed ({c.get('suppressed_reason') or c.get('status')})"
    if c.get("status") in OPEN:
        return f"in open sequence {c.get('sequence_id')} (status {c.get('status')}, step {c.get('current_step', 0)})"
    last = parse_day(c.get("last_touch") or c.get("registered_at") or "")
    if last and (today - last).days < recontact_days:
        return f"touched on {last.isoformat()} in {c.get('sequence_id')} ({c.get('status')}), under {recontact_days} days"
    return ""


def log(contact: Dict[str, Any], event: str, detail: str = "") -> None:
    contact.setdefault("history", []).append({"ts": now_iso(), "event": event, "detail": detail})


def close_sequence(contact: Dict[str, Any], status: str, reason: str) -> None:
    contact["status"] = status
    for s in contact.get("steps", []):
        if not s.get("sent") and not s.get("cancelled"):
            s["cancelled"] = True
    if status in SUPPRESSING:
        contact["suppressed"] = True
        contact["suppressed_reason"] = reason
    log(contact, "status", f"{status}: {reason}")


# ---------------------------------------------------------------- commands

def cmd_check(a, state) -> int:
    limits = load_json(LIMITS)
    days = a.recontact_after_days if a.recontact_after_days is not None else int(limits["state"]["recontact_after_days"])
    today = today_or(a.today)
    header, rows = read_csv(a.leads)
    excluded = []
    for r in rows:
        why = exclusion_reason(state, r, today, days)
        if why:
            excluded.append({"prospect": r.get("email") or r.get("linkedin_url") or r.get("prospect_id") or r.get("first_name", ""),
                             "reason": why})
    for e in excluded:
        print(f"exclude {e['prospect']}: {e['reason']}")
    print(f"{len(excluded)} of {len(rows)} lead(s) excluded")
    if a.out:
        write_csv(a.out, ["prospect", "reason"], excluded)
    return 0


def cmd_register(a, state) -> int:
    start = parse_day(a.start_date)
    if not start:
        raise InputError("--start-date must be YYYY-MM-DD")
    header, rows = read_csv(a.export)
    n_steps = len([h for h in header if re.match(r"^step_\d+_body$", h)])
    conflicts, added = [], 0
    for r in rows:
        key = contact_key(r)
        if not key:
            continue
        existing = find_contact(state, r)
        if existing and existing.get("sequence_id") != a.sequence_id and not a.force:
            if existing.get("suppressed") or existing.get("status") in OPEN:
                conflicts.append(f"{key}: {existing.get('status')} in {existing.get('sequence_id')}")
                continue
        planned, day = [], start
        for i in range(1, n_steps + 1):
            if not r.get(f"step_{i}_body"):
                continue
            delay = int(r.get(f"step_{i}_delay_days") or 0)
            day = day + timedelta(days=delay) if i > 1 else start
            planned.append({"n": i, "planned": day.isoformat(), "sent": None})
        contact = existing if existing and existing.get("sequence_id") == a.sequence_id else {}
        old_history = (existing or {}).get("history", [])
        contact.update({
            "key": key, "email": r.get("email", ""), "linkedin_url": r.get("linkedin_url", ""),
            "prospect_id": r.get("prospect_id", ""), "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""), "company": r.get("company", ""),
            "sequence_id": a.sequence_id, "channel": a.channel, "tier": r.get("tier", ""),
            "angle": r.get("angle", "") or r.get("subject_variant", ""), "hook_fact_id": r.get("hook_fact_id", ""),
            "status": "scheduled", "registered_at": now_iso()[:10], "start_date": start.isoformat(),
            "steps": planned, "current_step": 0, "last_touch": None, "replies": contact.get("replies", []),
            "resume_after": None, "suppressed": False, "suppressed_reason": None, "history": old_history,
        })
        log(contact, "register", f"{a.sequence_id}, {len(planned)} step(s) from {start.isoformat()}")
        if existing and existing.get("key") != key:
            state["contacts"].pop(existing["key"], None)
        state["contacts"][key] = contact
        added += 1
    save_state(a.state, state)
    for c in conflicts:
        print(f"refused {c} (use --force only if the founder decided to recontact)")
    print(f"registered {added} contact(s) in {a.sequence_id}")
    return 1 if conflicts else 0


def cmd_mark_sent(a, state) -> int:
    day = parse_day(a.date)
    if not day:
        raise InputError("--date must be YYYY-MM-DD")
    targets = [state["contacts"].get(to_key(a.contact))] if a.contact else \
        [c for c in state["contacts"].values() if c.get("sequence_id") == a.sequence_id]
    targets = [c for c in targets if c]
    if not targets:
        print("no matching contact", file=sys.stderr)
        return 1
    n = 0
    for c in targets:
        if c.get("status") in CLOSED:
            continue
        for s in c.get("steps", []):
            if s["n"] <= a.through_step and not s.get("sent") and not s.get("cancelled"):
                s["sent"] = day.isoformat()
        c["current_step"] = max([s["n"] for s in c.get("steps", []) if s.get("sent")] or [0])
        c["last_touch"] = day.isoformat()
        if c.get("status") in ("scheduled", "paused"):
            c["status"] = "active"
            c["resume_after"] = None
        if c["current_step"] >= len(c.get("steps", [])) and c["status"] == "active":
            c["status"] = "completed"
        log(c, "sent", f"through step {a.through_step} on {day.isoformat()}")
        n += 1
    save_state(a.state, state)
    print(f"marked {n} contact(s) through step {a.through_step}")
    return 0


def cmd_suppress(a, state) -> int:
    c = state["contacts"].get(to_key(a.contact))
    if not c:
        c = {"key": to_key(a.contact), "status": "unsubscribed", "steps": [], "history": []}
        if c["key"].startswith("email:"):
            c["email"] = c["key"][6:]
        state["contacts"][c["key"]] = c
    if c.get("status") in OPEN or c.get("status") == "unsubscribed":
        close_sequence(c, "unsubscribed", a.reason)
    c["suppressed"] = True
    c["suppressed_reason"] = a.reason
    save_state(a.state, state)
    print(f"suppressed {c['key']}: {a.reason}")
    return 0


def cmd_answered(a, state) -> int:
    c = state["contacts"].get(to_key(a.contact))
    if not c:
        print(f"unknown contact {a.contact}", file=sys.stderr)
        return 1
    c["answered"] = True
    log(c, "answered", a.note or "")
    save_state(a.state, state)
    print(f"{c['key']}: marked answered")
    return 0


def due_actions(state: Dict[str, Any], today) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"reply_now": [], "resume": [], "send_due": [], "finished": [], "read_reply": []}
    for c in sorted(state["contacts"].values(), key=lambda x: x.get("key", "")):
        who = f"{c.get('first_name', '')} {c.get('last_name', '')} <{c.get('email') or c.get('linkedin_url') or c.get('key')}>".strip()
        last_reply = (c.get("replies") or [{}])[-1]
        quote = f' "{last_reply.get("quote", "")}"' if last_reply.get("quote") else ""
        st = c.get("status")
        if st == "replied_positive" and not c.get("answered"):
            out["reply_now"].append(f"{who}: replied {last_reply.get('date', '')}{quote}. Draft the answer for the founder to validate.")
        elif st == "off_topic" and not c.get("answered"):
            out["read_reply"].append(f"{who}: off-topic reply {last_reply.get('date', '')}{quote}. Founder reads it (referral, wrong person, question).")
        elif st == "paused":
            resume = parse_day(c.get("resume_after") or "")
            if resume and resume <= today:
                out["resume"].append(f"{who}: back since {resume.isoformat()}, resume at step {c.get('current_step', 0) + 1}.")
        elif st in ("scheduled", "active"):
            pending = [s for s in c.get("steps", []) if not s.get("sent") and not s.get("cancelled")]
            if not pending:
                out["finished"].append(f"{who}: every step sent, no reply. Mark completed.")
            elif parse_day(pending[0]["planned"]) and parse_day(pending[0]["planned"]) <= today:
                out["send_due"].append(f"{who}: step {pending[0]['n']} planned {pending[0]['planned']} ({c.get('sequence_id')}).")
    return out


def cmd_due(a, state) -> int:
    today = today_or(a.today)
    actions = due_actions(state, today)
    titles = {
        "reply_now": "Answer (they wrote last, positive)",
        "read_reply": "Read (off-topic replies)",
        "resume": "Resume (back from absence)",
        "send_due": "Check the sequencer sent these steps",
        "finished": "Close (sequence finished without reply)",
    }
    lines = [f"# Follow-ups {today.isoformat()}", ""]
    for k, title in titles.items():
        lines.append(f"## {title} ({len(actions[k])})")
        lines.append("")
        lines += [f"- {x}" for x in actions[k]] or ["- none"]
        lines.append("")
    text = "\n".join(lines)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0


def cmd_summary(a, state) -> int:
    field = {"sequence": "sequence_id", "tier": "tier", "angle": "angle"}[a.by]
    groups: Dict[str, Dict[str, int]] = {}
    for c in state["contacts"].values():
        g = groups.setdefault(c.get(field) or "(none)", {"contacts": 0, "sent": 0, "positive": 0, "negative": 0,
                                                        "out_of_office": 0, "off_topic": 0, "bounced": 0})
        g["contacts"] += 1
        if any(s.get("sent") for s in c.get("steps", [])):
            g["sent"] += 1
        for r in c.get("replies", []):
            cls = r.get("class")
            if cls in g:
                g[cls] += 1
        if c.get("status") == "bounced":
            g["bounced"] += 1
    cols = ["contacts", "sent", "positive", "negative", "out_of_office", "off_topic", "bounced"]
    print(f"| {a.by} | " + " | ".join(cols) + " |")
    print("|---|" + "---:|" * len(cols))
    for k in sorted(groups):
        print(f"| {k} | " + " | ".join(str(groups[k][c]) for c in cols) + " |")
    print("\nCounts only. Compare classified replies between groups with their sample size; "
          "no winner is named by this script. Opens are never counted.")
    return 0


def cmd_show(a, state) -> int:
    import json
    c = state["contacts"].get(to_key(a.contact))
    if not c:
        print(f"unknown contact {a.contact}", file=sys.stderr)
        return 1
    print(json.dumps(c, ensure_ascii=False, indent=2))
    return 0


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str):
        p = sub.add_parser(name)
        p.add_argument("--state", required=True, help="Path of state.json")
        return p

    add("init")
    p = add("check")
    p.add_argument("--leads", required=True)
    p.add_argument("--out")
    p.add_argument("--today")
    p.add_argument("--recontact-after-days", type=int)
    p = add("register")
    p.add_argument("--export", required=True)
    p.add_argument("--sequence-id", required=True)
    p.add_argument("--start-date", required=True)
    p.add_argument("--channel", default="email", choices=["email", "linkedin"])
    p.add_argument("--force", action="store_true")
    p = add("mark-sent")
    p.add_argument("--sequence-id")
    p.add_argument("--contact")
    p.add_argument("--through-step", type=int, required=True)
    p.add_argument("--date", required=True)
    p = add("answered")
    p.add_argument("--contact", required=True)
    p.add_argument("--note")
    p = add("suppress")
    p.add_argument("--contact", required=True)
    p.add_argument("--reason", required=True)
    p = add("due")
    p.add_argument("--today")
    p.add_argument("--out")
    p = add("summary")
    p.add_argument("--by", default="sequence", choices=["sequence", "tier", "angle"])
    p = add("show")
    p.add_argument("--contact", required=True)
    a = ap.parse_args(argv)

    try:
        if a.cmd == "init":
            if os.path.isfile(a.state):
                print(f"{a.state} exists, left as is")
                return 0
            save_state(a.state, empty_state())
            print(f"created {a.state}")
            return 0
        state = load_state(a.state)
        if a.cmd == "mark-sent" and not (a.sequence_id or a.contact):
            raise InputError("mark-sent needs --sequence-id or --contact")
        return {"check": cmd_check, "register": cmd_register, "mark-sent": cmd_mark_sent,
                "suppress": cmd_suppress, "answered": cmd_answered, "due": cmd_due, "summary": cmd_summary, "show": cmd_show}[a.cmd](a, state)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
