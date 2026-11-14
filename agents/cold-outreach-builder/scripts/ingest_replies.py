#!/usr/bin/env python3
"""
ingest_replies.py

Reads the replies the founder exported (a CSV from any sequencer or inbox, or
.eml / .mbox files), classifies each one, and updates the outreach state.
Standard library only (csv, email, mailbox), Python 3.9+. No connector to
any mailbox or sending tool: the founder exports, the script reads files.

    python3 ingest_replies.py --state <state.json> \
        [--csv replies.csv ...] [--eml <file-or-folder> ...] [--mbox inbox.mbox ...] \
        [--overrides classifications.json] [--rules reply-rules.json] \
        [--report replies-<date>.md] [--today YYYY-MM-DD] [--dry-run] [--json]

Classes:
  positive       wants to talk, asks for the thing, proposes a time
  negative       not interested (an unsubscribe request is negative and
                 suppresses the contact)
  out_of_office  automatic absence reply (auto-reply headers or wording);
                 the sequence pauses until the return date found in the
                 reply, or --today + default_resume_days
  off_topic      wrong person, left the company, referral, anything else
  bounce         delivery failure: the contact is suppressed
The quoted history of each reply is removed before matching. Every class
comes with the sentence that triggered it (the quote). No cue, or cues of
several of positive / negative / off_topic: confidence low, needs_review.
The agent then reads that reply and writes an override:

    [{"message_id": "<id>", "class": "positive", "quote": "<words copied from the reply>"}]

The script accepts an override only when its quote is found in the reply.

CSV columns (detected, any case): from / email / from_email / sender /
lead_email; date / received_at / replied_at / timestamp; subject; body /
text / message / reply / reply_text / content; message_id / id.

State updates (outreach_state.py): positive -> replied_positive, negative
-> replied_negative + suppressed, unsubscribe -> unsubscribed + suppressed,
off_topic -> off_topic, bounce -> bounced + suppressed, out_of_office ->
paused with resume_after. A closed sequence cancels its remaining steps.
Already processed messages (by id) are skipped. Replies from an address the
state does not know are listed as unmatched and change nothing.

Exit codes: 0 done (even with needs_review), 1 an override was rejected,
2 usage error.
"""

from __future__ import annotations

import argparse
import email
import email.policy
import hashlib
import json
import mailbox
import os
import re
import sys
from datetime import date, datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (ASSETS, InputError, load_json, merged_config, norm_text,  # noqa: E402
                          normalize_email, read_csv, today_or)
from outreach_state import close_sequence, load_state, log, save_state  # noqa: E402

RULES = os.path.join(ASSETS, "reply-rules.json")
COLS = {
    "from": ["from", "from_email", "email", "sender", "lead_email", "reply_from"],
    "date": ["date", "received_at", "replied_at", "timestamp", "reply_date"],
    "subject": ["subject", "reply_subject"],
    "body": ["body", "text", "message", "reply", "reply_text", "content", "reply_body"],
    "id": ["message_id", "message-id", "id", "reply_id"],
}
QUOTE_START = re.compile(r"^\s*(?:On .{5,120} wrote:|Le .{5,120} a [ée]crit\s?:|-{2,}\s*Original Message\s*-{2,}|"
                         r"-{2,}\s*Message d'origine\s*-{2,}|From: .+|De ?: .+)\s*$", re.I | re.M)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], start=1)}
MONTHS.update({m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                                           "septembre", "octobre", "novembre", "décembre"], start=1)})
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


# ---------------------------------------------------------------- reading

def pick(row: Dict[str, str], key: str) -> str:
    low = {k.lower().strip(): v for k, v in row.items()}
    for c in COLS[key]:
        if low.get(c):
            return low[c]
    return ""


def msg_id(sender: str, when: str, body: str, given: str = "") -> str:
    if given:
        return given.strip().strip("<>")
    return "h-" + hashlib.sha256(f"{sender}|{when}|{body[:500]}".encode("utf-8")).hexdigest()[:16]


def from_csv(path: str) -> List[Dict[str, Any]]:
    _, rows = read_csv(path)
    out = []
    for r in rows:
        sender = normalize_email(parseaddr(pick(r, "from"))[1] or pick(r, "from"))
        body = pick(r, "body")
        when = pick(r, "date")
        out.append({"id": msg_id(sender, when, body, pick(r, "id")), "from": sender, "date": when[:10],
                    "subject": pick(r, "subject"), "body": body, "headers": {}, "source": os.path.basename(path)})
    return out


def from_message(m: Any, source: str) -> Dict[str, Any]:
    sender = normalize_email(parseaddr(str(m.get("From", "")))[1])
    when = ""
    if m.get("Date"):
        try:
            when = parsedate_to_datetime(str(m["Date"])).date().isoformat()
        except (TypeError, ValueError):
            when = ""
    body = ""
    try:
        part = m.get_body(preferencelist=("plain", "html"))
        if part is not None:
            body = part.get_content()
            if part.get_content_type() == "text/html":
                from outreach_lib import html_to_text
                body = html_to_text(body)
    except (AttributeError, KeyError, LookupError):
        payload = m.get_payload(decode=True)
        body = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload or "")
    headers = {k: str(v) for k, v in m.items()}
    return {"id": msg_id(sender, when, body, str(m.get("Message-ID", ""))), "from": sender, "date": when,
            "subject": str(m.get("Subject", "")), "body": body, "headers": headers, "source": source}


def from_eml(path: str) -> List[Dict[str, Any]]:
    files = [os.path.join(path, f) for f in sorted(os.listdir(path)) if f.lower().endswith(".eml")] if os.path.isdir(path) else [path]
    out = []
    for f in files:
        with open(f, "rb") as fh:
            m = email.message_from_binary_file(fh, policy=email.policy.default)
        out.append(from_message(m, os.path.basename(f)))
    return out


def from_mbox(path: str) -> List[Dict[str, Any]]:
    box = mailbox.mbox(path, factory=lambda f: email.message_from_binary_file(f, policy=email.policy.default))
    return [from_message(m, os.path.basename(path)) for m in box]


# ---------------------------------------------------------------- classify

def strip_quoted(body: str) -> str:
    m = QUOTE_START.search(body or "")
    text = body[:m.start()] if m else (body or "")
    return "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith(">")).strip()


def sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    rights = [i for i in (text.find(".", end), text.find("\n", end), text.find("!", end), text.find("?", end)) if i != -1]
    right = min(rights) + 1 if rights else len(text)
    return " ".join(text[left + 1:right].split())[:200]


def first_match(patterns: List[str], text: str) -> Optional[Tuple[int, int]]:
    for p in patterns:
        m = re.search(p, text or "", re.I | re.M)
        if m:
            return m.start(), m.end()
    return None


def classify(msg: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    cls = rules["classes"]
    own = strip_quoted(msg["body"])
    subj = msg.get("subject", "")
    res: Dict[str, Any] = {"class": "off_topic", "confidence": "low", "needs_review": True, "quote": "", "unsubscribe": False}

    b = cls.get("bounce", {})
    if any(msg["from"].startswith(x) for x in b.get("from", [])) or first_match(b.get("subject", []), subj) or \
            first_match(b.get("body", []), msg["body"]):
        hit = first_match(b.get("body", []), msg["body"]) or first_match(b.get("subject", []), subj)
        src = msg["body"] if first_match(b.get("body", []), msg["body"]) else subj
        res.update({"class": "bounce", "confidence": "high", "needs_review": False,
                    "quote": sentence_around(src, *hit) if hit else msg["from"]})
        return res

    hdr = {k.lower(): v for k, v in msg.get("headers", {}).items()}
    auto = any(re.search(p, hdr.get(h.lower(), ""), re.I) for h, p in rules.get("auto_reply_headers", {}).items() if hdr.get(h.lower()))
    o = cls.get("out_of_office", {})
    ooo_hit = first_match(o.get("body", []), own)
    ooo_subj = first_match(o.get("subject", []), subj)
    if auto or ooo_hit or ooo_subj:
        quote = sentence_around(own, *ooo_hit) if ooo_hit else (subj if ooo_subj else "auto-reply header")
        res.update({"class": "out_of_office", "confidence": "high", "needs_review": False, "quote": quote,
                    "return_date": return_date(own, rules, msg.get("date", ""))})
        return res

    hits = {}
    unsub = first_match(cls.get("unsubscribe", {}).get("body", []), own)
    if unsub:
        hits["negative"] = unsub
        res["unsubscribe"] = True
    for name in ("negative", "off_topic", "positive"):
        if name in hits:
            continue
        h = first_match(cls.get(name, {}).get("body", []), own)
        if h:
            hits[name] = h
    if len(hits) == 1:
        name, h = next(iter(hits.items()))
        res.update({"class": name, "confidence": "high", "needs_review": False, "quote": sentence_around(own, *h)})
    elif hits:
        name = next(n for n in ("negative", "off_topic", "positive") if n in hits)
        res.update({"class": name, "confidence": "low", "needs_review": True,
                    "quote": sentence_around(own, *hits[name]),
                    "conflict": sorted(hits)})
        if res["unsubscribe"]:
            res.update({"confidence": "high", "needs_review": False})
    else:
        res["quote"] = " ".join(own.split())[:200]
    return res


def return_date(text: str, rules: Dict[str, Any], received: str) -> str:
    for p in rules.get("out_of_office_return", []):
        m = re.search(p, text, re.I)
        if not m:
            continue
        d = parse_loose_date(m.group("date"), received)
        if d:
            return d.isoformat()
    return ""


def parse_loose_date(s: str, received: str) -> Optional[date]:
    s = s.strip().lower().replace(",", " ")
    base = None
    try:
        base = datetime.strptime(received[:10], "%Y-%m-%d").date() if received else None
    except ValueError:
        base = None
    year_default = base.year if base else date.today().year
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b", s)
    if m:
        y = int(m.group(3)) if m.group(3) else year_default
        y = y + 2000 if y < 100 else y
        return roll(safe_date(y, int(m.group(2)), int(m.group(1))), base, bool(m.group(3)))
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th|er)?\s+([a-zéû]+)\.?(?:\s+(\d{4}))?", s)
    if m and m.group(2)[:3] in MONTHS or (m and m.group(2) in MONTHS):
        mon = MONTHS.get(m.group(2), MONTHS.get(m.group(2)[:3]))
        y = int(m.group(3)) if m.group(3) else year_default
        return roll(safe_date(y, mon, int(m.group(1))), base, bool(m.group(3)))
    m = re.search(r"\b([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?", s)
    if m and (m.group(1) in MONTHS or m.group(1)[:3] in MONTHS):
        mon = MONTHS.get(m.group(1), MONTHS.get(m.group(1)[:3]))
        y = int(m.group(3)) if m.group(3) else year_default
        return roll(safe_date(y, mon, int(m.group(2))), base, bool(m.group(3)))
    return None


def safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def roll(d: Optional[date], base: Optional[date], explicit_year: bool) -> Optional[date]:
    if d and base and not explicit_year and d < base:
        return safe_date(d.year + 1, d.month, d.day)
    return d


# ---------------------------------------------------------------- state

def find_by_sender(state: Dict[str, Any], sender: str) -> Optional[Dict[str, Any]]:
    c = state["contacts"].get("email:" + sender)
    if c:
        return c
    for c in state["contacts"].values():
        if normalize_email(c.get("email", "")) == sender:
            return c
    return None


def apply(state: Dict[str, Any], msg: Dict[str, Any], res: Dict[str, Any], today: date, resume_days: int) -> str:
    """Update the contact; return a one-line description of the change."""
    c = find_by_sender(state, msg["from"])
    if not c and res["class"] == "bounce":
        # A bounce comes from the mail system: the failed recipient is in the body.
        for addr in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", msg["body"]):
            c = find_by_sender(state, normalize_email(addr))
            if c:
                break
    if not c:
        return "unmatched"
    reply = {"date": msg.get("date") or today.isoformat(), "class": res["class"], "quote": res["quote"],
             "confidence": res["confidence"], "message_id": msg["id"], "source": msg["source"]}
    c.setdefault("replies", []).append(reply)
    c["last_reply"] = reply["date"]
    c["last_touch"] = max(filter(None, [c.get("last_touch"), reply["date"]]))
    c["answered"] = False
    cls = res["class"]
    if cls == "bounce":
        close_sequence(c, "bounced", "hard bounce")
    elif cls == "out_of_office":
        if c.get("status") in ("scheduled", "active", "paused"):
            ret = res.get("return_date") or (today + timedelta(days=resume_days)).isoformat()
            c["status"] = "paused"
            c["resume_after"] = ret
            log(c, "status", f"paused until {ret} (out of office)")
    elif cls == "negative":
        if res.get("unsubscribe"):
            close_sequence(c, "unsubscribed", "asked to stop")
        else:
            close_sequence(c, "replied_negative", "not interested")
    elif cls == "positive":
        close_sequence(c, "replied_positive", "positive reply")
    else:
        close_sequence(c, "off_topic", "off-topic reply")
    return c["status"]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True)
    ap.add_argument("--csv", action="append", default=[])
    ap.add_argument("--eml", action="append", default=[])
    ap.add_argument("--mbox", action="append", default=[])
    ap.add_argument("--overrides", help="JSON list of {message_id, class, quote} written after reading needs_review replies")
    ap.add_argument("--rules", help="Project reply-rules.json merged over assets/reply-rules.json")
    ap.add_argument("--report", help="Markdown report path")
    ap.add_argument("--today")
    ap.add_argument("--dry-run", action="store_true", help="Classify and report, do not write the state")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        today = today_or(a.today)
        rules = merged_config(RULES, a.rules)
        state = load_state(a.state)
        msgs: List[Dict[str, Any]] = []
        for p in a.csv:
            msgs += from_csv(p)
        for p in a.eml:
            msgs += from_eml(p)
        for p in a.mbox:
            msgs += from_mbox(p)
        overrides = {o["message_id"].strip("<>"): o for o in (load_json(a.overrides) if a.overrides else [])}
    except (InputError, OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not msgs:
        print("error: no reply read: give --csv, --eml or --mbox", file=sys.stderr)
        return 2

    processed = set(state.get("processed_messages", []))
    results, rejected = [], []
    for msg in msgs:
        if msg["id"] in processed:
            continue
        res = classify(msg, rules)
        ov = overrides.get(msg["id"])
        if ov:
            if ov.get("class") not in ("positive", "negative", "out_of_office", "off_topic", "bounce"):
                rejected.append(f"{msg['id']}: unknown class {ov.get('class')}")
            elif not ov.get("quote") or norm_text(ov["quote"]) not in norm_text(msg["body"]):
                rejected.append(f"{msg['id']}: the override quote is not in the reply")
            else:
                res.update({"class": ov["class"], "quote": ov["quote"], "confidence": "override", "needs_review": False,
                            "unsubscribe": bool(ov.get("unsubscribe"))})
        if res["needs_review"]:
            change = "needs_review (state unchanged)"
        else:
            change = apply(state, msg, res, today, int(rules.get("default_resume_days", 7)))
            if change != "unmatched":
                processed.add(msg["id"])
        results.append({"message_id": msg["id"], "from": msg["from"], "date": msg["date"], "subject": msg["subject"],
                        "source": msg["source"], **res, "state": change})

    state["processed_messages"] = sorted(processed)
    if not a.dry_run:
        save_state(a.state, state)

    lines = [f"# Replies ingested {today.isoformat()}", ""]
    order = ["needs_review", "positive", "out_of_office", "off_topic", "negative", "bounce", "unmatched"]
    for group in order:
        if group == "needs_review":
            sel = [r for r in results if r["needs_review"]]
        elif group == "unmatched":
            sel = [r for r in results if r["state"] == "unmatched"]
        else:
            sel = [r for r in results if not r["needs_review"] and r["class"] == group and r["state"] != "unmatched"]
        lines.append(f"## {group} ({len(sel)})")
        lines.append("")
        for r in sel:
            extra = f", back {r['return_date']}" if r.get("return_date") else ""
            lines.append(f"- {r['from']} ({r['date']}, {r['source']}, id {r['message_id']}): \"{r['quote']}\" "
                         f"[{r['confidence']}{extra}] -> {r['state']}")
        if not sel:
            lines.append("- none")
        lines.append("")
    if rejected:
        lines += ["## Rejected overrides", ""] + [f"- {x}" for x in rejected] + [""]
    text = "\n".join(lines)
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(text)
    if a.json:
        print(json.dumps({"results": results, "rejected": rejected}, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
