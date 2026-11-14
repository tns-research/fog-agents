#!/usr/bin/env python3
"""pubqueue.py: the publication queue of content-publisher.

One queue.json per project, one item per post and network. Statuses:

  to_review --approve (human only)--> approved --schedule--> scheduled --sync--> published
       |                                  |                       |
       +--reject--> rejected              +--edit--> to_review    +--> failed --reopen--> to_review

Commands (every one takes --queue PATH; --now YYYY-MM-DDTHH:MM fixes the clock):

  init     create queue.json from config.json settings (timezone, slots, window)
  add      lint a post spec, run the writing gate, add one item per network as to_review, plan slots
  edit     change a text or a slot; a content change clears the approval (back to to_review)
  plan     give every to_review and approved item a slot: weekly slots per network,
           never two posts of a network closer than window_minutes
  list     the queue as a table (--json for the raw items)
  show     one item in full, with its approval and history
  review   write the review packet the founder reads (texts per network, approve commands)
  approve  HUMAN ONLY. Moves to_review -> approved for the exact content reviewed.
           Needs --by <a person's name> and an interactive terminal: it shows each
           post with a review code (an HMAC under the local approval key, printed
           nowhere else) and asks the person to type it. An agent never runs it.
  reopen   approved, failed or rejected -> to_review
  reject   to_review or approved -> rejected, with a note
  schedule hand approved items to an adapter (default dry-run: writes outbox/<id>.json,
           sends nothing; a real adapter needs --live and its key in the environment)
  sync     ask the adapter what happened to scheduled items (published, failed)
  mark     record by hand that an approved or scheduled item was published or failed
  validate schema plus invariants: approvals match content, slot windows, transitions

Exit codes: 0 ok, 1 refused on content or state, 2 usage error or invalid file,
3 approval gate refused (not approved, no terminal, wrong code, reserved name,
approval not recorded by approve),
4 provider unavailable (no key, offline): nothing changed for that item.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import variants  # noqa: E402
from adapters import ProviderError, ProviderUnavailable, get_adapter  # noqa: E402

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
LIVE = ("to_review", "approved")


def posix_rel(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()


def human_slot(slot: Optional[str]) -> str:
    if not slot:
        return "no slot"
    d = common.parse_slot(slot)
    return f"{DAY_NAMES[d.weekday()]} {d.day} {d.strftime('%b %Y')}, {d.strftime('%H:%M')}"


# ------------------------------------------------------------------ planning

def plan(data: Dict[str, Any], now: datetime) -> List[str]:
    """Assign slots, deterministically for a given now.

    Fixed: scheduled and published items. Pass 1 keeps every to_review or
    approved item whose current slot is still valid (in the future, before the
    horizon, outside the window of the items already kept), approved items
    first. Pass 2 places the others, in order of target slot: the target when
    it is free, else the next free weekly slot of the network. A new post
    never pushes a planned one; an item moved off its target stays on its new
    slot until `edit --slot` sets it again. Returns notes on items left
    without a slot."""
    s = data["settings"]
    gap = timedelta(minutes=s["window_minutes"])
    earliest = now + timedelta(minutes=s["lead_minutes"])
    horizon = now + timedelta(days=s.get("horizon_days") or 28)
    occupied: Dict[str, List[datetime]] = {}
    for it in data["items"]:
        if it["status"] in ("scheduled", "published") and it.get("slot"):
            occupied.setdefault(it["network"], []).append(common.parse_slot(it["slot"]))

    def ok(net: str, t: Optional[datetime]) -> bool:
        return bool(t) and earliest <= t <= horizon and all(abs(t - o) >= gap for o in occupied.get(net, []))

    def weekly(net: str, start: datetime) -> List[datetime]:
        out = []
        day = start.replace(hour=0, minute=0)
        while day <= horizon:
            for spec in s["slots"].get(net, []):
                if DAYS.index(spec["day"]) == day.weekday():
                    hh, mm = (int(x) for x in spec["time"].split(":"))
                    t = day.replace(hour=hh, minute=mm)
                    if start <= t <= horizon:
                        out.append(t)
            day += timedelta(days=1)
        return sorted(out)

    order = {it["id"]: k for k, it in enumerate(data["items"])}
    movable = sorted((it for it in data["items"] if it["status"] in LIVE),
                     key=lambda it: (it["status"] != "approved", it.get("slot_target") or it.get("slot") or "9999", order[it["id"]]))
    to_place = []
    for it in movable:  # pass 1: keep what is still valid
        cur = common.parse_slot(it["slot"]) if it.get("slot") else None
        if ok(it["network"], cur):
            occupied.setdefault(it["network"], []).append(cur)
        else:
            to_place.append(it)
    notes = []
    for it in to_place:  # pass 2: place the rest
        net = it["network"]
        tgt = common.parse_slot(it["slot_target"]) if it.get("slot_target") else None
        choice = tgt if ok(net, tgt) else None
        if choice is None:
            start = max(earliest, tgt) if tgt else earliest
            choice = next((t for t in weekly(net, start) if ok(net, t)), None)
        new = common.fmt_slot(choice) if choice else None
        if new != it.get("slot"):
            if new is None:
                note = "no free slot before the horizon" if s["slots"].get(net) else f"no weekly slot configured for {net}"
                notes.append(f"{it['id']}: {note}")
            else:
                note = f"slot {human_slot(new)}" + (f" (target {human_slot(it['slot_target'])} taken or passed)"
                                                     if it.get("slot_target") and new != it["slot_target"] else "")
            common.log(it, "planned", "pubqueue", note, now)
            it["slot"] = new
        if choice:
            occupied.setdefault(net, []).append(choice)
    return notes


# ------------------------------------------------------------------ items

def item_from(post: Dict[str, Any], net: str, spec_dir: Path, queue_dir: Path, report: Dict[str, Any],
              manual_gate: bool) -> Dict[str, Any]:
    c = variants.compose(post, net)
    media = []
    for m in variants.media_for(post, net):
        entry = {"path": posix_rel(spec_dir / m["path"], queue_dir), "type": m["type"]}
        for k in ("alt", "title"):
            if m.get(k):
                entry[k] = m[k]
        media.append(entry)
    item = {
        "id": f"{post['ref']}.{net}", "ref": post["ref"], "network": net, "kind": post["kind"],
        "language": post["language"], "status": "to_review",
        "text": c["text"], "first_comment": c["first_comment"], "reply": c["reply"], "link": post.get("link"),
        "media": media, "source": dict(post.get("source") or {}),
        "slot_target": post.get("target_slot"), "slot": None, "approval": None, "provider": None, "error": None,
    }
    item["source"]["spec"] = posix_rel(spec_dir, queue_dir) if spec_dir.resolve() != queue_dir.resolve() else "."
    common.refresh_media_hashes(item, queue_dir)
    item["content_hash"] = common.content_hash(item)
    item["checks"] = item_checks(item, report, manual_gate)
    return item


def item_checks(item: Dict[str, Any], report: Dict[str, Any], manual_gate: bool) -> Dict[str, Any]:
    prefix = item["id"]
    mine = [f for f in report["findings"] if f["where"] == prefix or f["where"].startswith(prefix + ".")]
    lim = common.limits()[item["network"]]
    gate_res = [r for w, r in (report.get("gate") or {}).get("results", {}).items() if w.startswith(prefix + ".")]
    block = sum(r["block"] for r in gate_res)
    warn = sum(r["warn"] for r in gate_res)
    if report.get("gate", {}).get("ran"):
        gate = "fail" if block else "pass"
    else:
        gate = "manual" if manual_gate else "fail"
    return {
        "lint": "fail" if any(f["level"] == "error" and not f["code"].startswith("writing-gate:") for f in mine) else "pass",
        "writing_gate": gate,
        "block": block,
        "warn": warn,
        "length": f"{variants.length(item['text'], item['network'], common.limits())}/{lim['text_max']}",
        "warnings": sorted({f"{f['code']}: {f['message']}" for f in mine if f["level"] == "warning"}),
    }


def mini_post(item: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild a one-network post spec from a queue item, to re-lint an edit."""
    note = (item.get("reply") or "").replace(item.get("link") or "\0", "").strip() if item.get("reply") else ""
    var: Dict[str, Any] = {"text": item["text"]}
    if item["network"] == "linkedin" and item.get("first_comment"):
        var["first_comment"] = item["first_comment"]
    return {"ref": item["ref"], "kind": item.get("kind", "text"), "language": item.get("language", "en"),
            "link": item.get("link"), "link_note": note, "networks": [item["network"]],
            "media": [{k: v for k, v in m.items() if k != "sha256"} for m in item.get("media") or []],
            "variants": {item["network"]: dict(var, media=list(range(len(item.get("media") or []))))}}


# ------------------------------------------------------------------ commands

def cmd_init(a, qpath: Path) -> int:
    if qpath.exists() and not a.force:
        raise common.Refused(f"{qpath} exists (use --force to overwrite)")
    settings: Dict[str, Any] = {}
    project = a.project_name or ""
    if a.config:
        cfg = common.read_json(Path(a.config))
        project = project or cfg.get("project", "")
        settings = {k: v for k, v in cfg.items() if k in common.DEFAULT_SETTINGS}
    if a.timezone:
        settings["timezone"] = a.timezone
    qpath.parent.mkdir(parents=True, exist_ok=True)
    data = common.new_queue(project, settings)
    common.save_queue(qpath, data)
    print(f"created {qpath} (timezone {data['settings']['timezone']}, networks with slots: "
          f"{', '.join(sorted(data['settings']['slots'])) or 'none'})")
    return 0


def cmd_add(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    spec_path = Path(a.spec)
    spec = common.read_json(spec_path)
    report = variants.lint_spec(spec, spec_path.parent, data["settings"], a.project, gate=not a.manual_gate)
    variants.print_findings(report)
    if report["status"] != "pass":
        print("\nNothing added: fix the spec (each finding names the post and network), then run add again.")
        return common.EXIT_CHECK
    if a.manual_gate:
        print("writing gate: manual (--manual-gate): record who checked the copy by hand in the report")
    queue_dir = qpath.parent
    existing = {it["id"]: it for it in data["items"]}
    new_items = [item_from(p, n, spec_path.parent, queue_dir, report, a.manual_gate)
                 for p in spec["posts"] for n in p["networks"]]
    locked_ids = [i["id"] for i in new_items if i["id"] in existing and existing[i["id"]]["status"] in ("scheduled", "published")]
    if locked_ids:
        raise common.Refused("already at the provider, not replaced: " + ", ".join(locked_ids)
                             + " (cancel there and mark --failed, or give the post a new ref)")
    added = updated = same = 0
    for it in new_items:
        old = existing.get(it["id"])
        if old is None:
            it["created"] = common.stamp(now)
            common.log(it, "created", "pubqueue", f"from {posix_rel(spec_path, queue_dir)}", now, to="to_review")
            data["items"].append(it)
            added += 1
            continue
        if old["content_hash"] == it["content_hash"] and old["status"] in ("to_review", "approved"):
            same += 1
            continue
        if old["status"] != "to_review":
            common.transition(old, "to_review", "pubqueue", "content-changed", "re-added from the spec: review again", now)
        for k in ("text", "first_comment", "reply", "link", "media", "kind", "language", "source", "content_hash", "checks"):
            old[k] = it[k]
        if it.get("slot_target"):
            old["slot_target"] = it["slot_target"]
        old["error"] = None
        common.log(old, "updated", "pubqueue", "content replaced from the spec", now)
        updated += 1
    notes = plan(data, now)
    common.save_queue(qpath, data)
    print(f"\nqueue: {added} added, {updated} updated (back to to_review), {same} unchanged. Status of new items: to_review.")
    for n in notes:
        print(f"  unplanned: {n}")
    print(f"Next: python3 {script_rel()} review --queue {qpath} --out <review.md>, then the founder approves.")
    return 0


def script_rel() -> str:
    """This script's path as the reader will type it: relative to the current
    folder when the script is under it (agents/content-publisher/scripts/...
    from the repo root), absolute otherwise."""
    here = Path(__file__).resolve()
    try:
        return here.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return here.as_posix()


def cmd_edit(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    it = common.find_item(data, a.id)
    if it["status"] in ("scheduled", "published"):
        raise common.Refused(f"{it['id']} is {it['status']} at the provider: cancel it there, mark --failed, then edit")
    by = a.by or "pubqueue"
    changed_content = False
    if a.text_file or a.text is not None:
        it["text"] = (Path(a.text_file).read_text(encoding="utf-8") if a.text_file else a.text).strip()
        changed_content = True
    if a.first_comment is not None:
        if it["network"] != "linkedin":
            raise common.UsageError("--first-comment applies to LinkedIn items only")
        it["first_comment"] = a.first_comment.strip() or None
        changed_content = True
    if a.slot:
        common.parse_slot(a.slot)
        it["slot_target"] = a.slot
        it["slot"] = a.slot
        common.log(it, "slot-set", by, f"target {human_slot(a.slot)}", now)
    if changed_content:
        common.refresh_media_hashes(it, qpath.parent)
        report = variants.lint_spec({"schema_version": "1.0", "posts": [mini_post(it)]}, qpath.parent, data["settings"],
                                    a.project, gate=not a.manual_gate)
        variants.print_findings(report)
        if report["status"] != "pass":
            print("\nEdit refused: the queue is unchanged.")
            return common.EXIT_CHECK
        it["content_hash"] = common.content_hash(it)
        it["checks"] = item_checks(it, report, a.manual_gate)
        if it["status"] != "to_review":
            common.transition(it, "to_review", by, "edited", "content changed: approval cleared", now)
        else:
            common.log(it, "edited", by, "content changed", now)
    notes = plan(data, now)
    common.save_queue(qpath, data)
    print(f"{it['id']}: {it['status']}, {human_slot(it.get('slot'))}")
    for n in notes:
        print(f"  unplanned: {n}")
    return 0


def cmd_plan(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    notes = plan(data, now)
    common.save_queue(qpath, data)
    for it in data["items"]:
        if it["status"] in LIVE + ("scheduled",):
            print(f"  {it['id']:<40} {it['status']:<10} {human_slot(it.get('slot'))}")
    for n in notes:
        print(f"  unplanned: {n}")
    return 0


def cmd_list(a, data: Dict[str, Any]) -> int:
    items = [it for it in data["items"] if (not a.status or it["status"] == a.status) and (not a.network or it["network"] == a.network)]
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    print(f"{'id':<42} {'status':<10} {'slot':<17} {'length':<10} checks")
    for it in sorted(items, key=lambda x: (x.get("slot") or "9999", x["id"])):
        ck = "ok" if it["checks"]["lint"] == "pass" and it["checks"]["writing_gate"] != "fail" else "FAIL"
        print(f"{it['id']:<42} {it['status']:<10} {it.get('slot') or '-':<17} {it['checks'].get('length', ''):<10} {ck}")
    return 0


def cmd_show(a, data: Dict[str, Any]) -> int:
    it = common.find_item(data, a.id)
    print(f"{it['id']}  [{it['status']}]  {human_slot(it.get('slot'))}")
    print(f"checks: lint {it['checks']['lint']}, writing gate {it['checks']['writing_gate']} "
          f"({it['checks'].get('block', 0)} BLOCK, {it['checks'].get('warn', 0)} WARN), length {it['checks'].get('length')}")
    print("\n--- body ---\n" + it["text"])
    if it.get("first_comment"):
        print("\n--- first comment ---\n" + it["first_comment"])
    if it.get("reply"):
        print("\n--- first reply ---\n" + it["reply"])
    for m in it.get("media") or []:
        print(f"media: {m['type']} {m['path']}" + (f" (alt: {m['alt']})" if m.get("alt") else ""))
    if it.get("approval"):
        problem = common.approval_problem(it)
        print(f"approved by {it['approval']['by']} at {it['approval']['at']}" + (f"  (NOT VALID: {problem})" if problem else ""))
    print("\nhistory:")
    for ev in it.get("history", []):
        print(f"  {ev['at']}  {ev['action']:<16} {ev.get('by', ''):<12} {ev.get('note', '')}")
    return 0


def fenced(text: str) -> str:
    return "```text\n" + text + "\n```"


def cmd_review(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    lim = common.limits()
    todo = [it for it in data["items"] if it["status"] == "to_review"]
    for it in todo:  # the packet shows the files as they are now, so it matches what approve checks
        common.refresh_media_hashes(it, qpath.parent)
        if common.content_hash(it) != it["content_hash"]:
            it["content_hash"] = common.content_hash(it)
            common.log(it, "media-changed", "pubqueue", "a media file changed on disk: review it again", now)
    common.save_queue(qpath, data)
    lines = [f"# Publication review: {data.get('project') or qpath.parent.name}", "",
             f"Queue `{qpath.name}` · timezone {data['settings']['timezone']} · generated {common.fmt_slot(now)}", "",
             f"{len(todo)} item(s) to review. Nothing reaches a network before a person approves it: "
             "the agent prepares, checks and schedules, it never approves.", "",
             "## How to answer", "",
             "- **Approve**: run the approve line of each post you accept, yourself, in your own terminal. It shows "
             "the post again with a review code and asks you to type the code: your approval is bound to the exact "
             "text and media below, and any later edit sends the item back here.",
             "- **Change**: tell the agent what to change. It edits, re-runs the checks, and the item comes back in the next packet.",
             f"- **Refuse**: `python3 {script_rel()} reject <id> --queue {qpath} --by <your-name> --note \"why\"`.", ""]
    for ref in sorted({it["ref"] for it in todo}, key=lambda r: min(i.get("slot") or "9999" for i in todo if i["ref"] == r)):
        group = [it for it in todo if it["ref"] == ref]
        lines += [f"## {ref} ({group[0].get('kind', '')})", ""]
        src = group[0].get("source") or {}
        if src.get("agent") or src.get("path"):
            lines += [f"From {src.get('agent', 'founder')}: `{src.get('path', '')}`", ""]
        for it in sorted(group, key=lambda i: common.NETWORKS.index(i["network"])):
            ck = it["checks"]
            lines += [f"### {lim[it['network']]['label']} · {human_slot(it.get('slot'))}", "",
                      f"Checks: lint {ck['lint']}, writing gate {ck['writing_gate']} ({ck.get('block', 0)} BLOCK, "
                      f"{ck.get('warn', 0)} WARN), length {ck.get('length')}"]
            for w in ck.get("warnings") or []:
                lines.append(f"- warning: {w}")
            if it.get("media"):
                lines.append("Media: " + ", ".join(f"{Path(m['path']).name} ({m['type']})" for m in it["media"]))
            lines += ["", "Body:", "", fenced(it["text"]), ""]
            if it.get("first_comment"):
                lines += ["First comment:", "", fenced(it["first_comment"]), ""]
            if it.get("reply"):
                lines += ["First reply:", "", fenced(it["reply"]), ""]
            lines += ["Approve:", "", "```bash",
                      f"python3 {script_rel()} approve {it['id']} --queue {qpath} --by <your-name>",
                      "```", ""]
    others = [it for it in data["items"] if it["status"] in ("approved", "scheduled", "failed")]
    if others:
        lines += ["## Already decided", "", "| Item | Status | Slot |", "|------|--------|------|"]
        for it in sorted(others, key=lambda i: i.get("slot") or ""):
            lines.append(f"| `{it['id']}` | {it['status']} | {human_slot(it.get('slot'))} |")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"review packet: {a.out} ({len(todo)} item(s) to review)")
    else:
        print(text)
    return 0


def print_for_approval(it: Dict[str, Any]) -> None:
    lim = common.limits()[it["network"]]
    print(f"\n=== {it['id']} · {lim['label']} · {human_slot(it['slot'])} ===")
    print("--- body ---\n" + it["text"])
    if it.get("first_comment"):
        print("--- first comment ---\n" + it["first_comment"])
    if it.get("reply"):
        print("--- first reply ---\n" + it["reply"])
    for m in it.get("media") or []:
        print(f"media: {m['type']} {m['path']}" + (f" (alt: {m['alt']})" if m.get("alt") else ""))


def cmd_approve(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    """The human gate: the only function that holds the approval sentinel.

    It runs only at an interactive terminal (stdin and stdout are TTYs), shows
    each post, prints its review code and asks the person to type it. The code
    is never an argument and never printed by another command, so an agent
    that follows its workflow or edits queue.json cannot approve. An agent
    with an unrestricted shell under the same user can still drive a terminal
    or read the key: see the README for what the gate does not cover."""
    by = (a.by or "").strip()
    if not by or by.lower() in common.RESERVED_APPROVERS or by.startswith("<"):
        raise common.GateRefused(f"--by must be the name of the person approving, not {by!r}")
    allowed = data["settings"].get("approvers") or []
    if allowed and by not in allowed:
        raise common.GateRefused(f"{by!r} is not in settings.approvers ({', '.join(allowed)})")
    if a.code:
        raise common.GateRefused("review codes are not accepted as arguments: run approve yourself in an interactive "
                                 "terminal; it shows each post with its code and asks you to type it")
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise common.GateRefused("approve needs a person at an interactive terminal (stdin and stdout must be a TTY): "
                                 "the founder runs it in their own terminal, an agent never runs it")
    done = 0
    for item_id in a.ids:
        it = common.find_item(data, item_id)
        if it["status"] != "to_review":
            raise common.Refused(f"{item_id} is {it['status']}, only to_review items are approved")
        common.refresh_media_hashes(it, qpath.parent)
        if common.content_hash(it) != it["content_hash"]:
            it["content_hash"] = common.content_hash(it)
            common.save_queue(qpath, data)
            raise common.Refused(f"{item_id}: a media file changed since the review packet: regenerate it and read again")
        ck = it["checks"]
        if ck["lint"] != "pass" or ck["writing_gate"] == "fail" or ck.get("block"):
            raise common.Refused(f"{item_id}: checks do not pass (lint {ck['lint']}, writing gate {ck['writing_gate']})")
        if not it.get("slot") or common.parse_slot(it["slot"]) <= now:
            raise common.Refused(f"{item_id}: no future slot ({it.get('slot')}): run plan or edit --slot first")
        print_for_approval(it)
        code = common.review_code(it)
        print(f"Review code: {code}")
        try:
            typed = input(f"Type the review code to approve {item_id} (Enter skips it): ").strip()
        except EOFError:
            raise common.GateRefused(f"{item_id}: no answer at the terminal")
        if not typed:
            print(f"skipped: {item_id} stays to_review")
            continue
        if not hmac_equal(typed.lower(), code):
            raise common.GateRefused(f"{item_id}: wrong review code; nothing approved for this item")
        common.transition(it, "approved", by, "approved", "review code typed at the terminal", now, token=common.HUMAN_APPROVAL)
        it["approval"] = {"by": by, "at": common.stamp(now), "content_hash": it["content_hash"]}
        it["approval"]["mac"] = common.approval_mac(it["id"], it["approval"])
        common.save_queue(qpath, data)
        done += 1
        print(f"approved: {item_id} by {by}, {human_slot(it['slot'])}")
    print(f"approve: {done} of {len(a.ids)} item(s) approved")
    return 0


def hmac_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def cmd_reopen(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    it = common.find_item(data, a.id)
    common.transition(it, "to_review", a.by or "", "reopened", a.note or "", now)
    it["error"] = None
    plan(data, now)
    common.save_queue(qpath, data)
    print(f"{it['id']}: to_review, {human_slot(it.get('slot'))}")
    return 0


def cmd_reject(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    if not (a.note or "").strip():
        raise common.UsageError("--note is required: say why, so the next run does not propose it again")
    it = common.find_item(data, a.id)
    common.transition(it, "rejected", a.by or "", "rejected", a.note, now)
    plan(data, now)
    common.save_queue(qpath, data)
    print(f"{it['id']}: rejected")
    return 0


def adapter_ctx(qpath: Path, data: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    return {"queue_dir": qpath.parent, "settings": data["settings"], "now": now, "outbox": qpath.parent / "outbox"}


def cmd_schedule(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    adapter = get_adapter(a.adapter or data["settings"].get("adapter") or "dry-run")
    if adapter.real and not a.live:
        raise common.UsageError(f"{adapter.name} sends for real: add --live (the default dry-run adapter sends nothing)")
    if a.id:
        not_approved = [i for i in a.id if common.find_item(data, i)["status"] != "approved"]
        if not_approved:
            raise common.GateRefused("not approved, a person must run approve first: " + ", ".join(
                f"{i} ({common.find_item(data, i)['status']})" for i in not_approved))
    reason = adapter.available()
    if reason:
        print(f"provider unavailable: {reason}. Nothing was scheduled; items stay approved.", file=sys.stderr)
        return common.EXIT_PROVIDER
    ctx = adapter_ctx(qpath, data, now)
    todo = [it for it in data["items"] if it["status"] == "approved" and (not a.id or it["id"] in a.id)]
    if a.due_hours is not None:
        limit = now + timedelta(hours=a.due_hours)
        todo = [it for it in todo if it.get("slot") and common.parse_slot(it["slot"]) <= limit]
    refused = 0
    for it in sorted(todo, key=lambda i: i.get("slot") or ""):
        try:
            common.refresh_media_hashes(it, qpath.parent)
        except common.Refused as e:
            it["error"] = str(e)[:400]
            common.transition(it, "failed", "pubqueue", "media-refused", str(e)[:200], now)
            common.save_queue(qpath, data)
            refused += 1
            print(f"  failed: {it['id']}: {e}")
            continue
        current = common.content_hash(it)
        if current != it["content_hash"]:
            it["content_hash"] = current
            common.transition(it, "to_review", "pubqueue", "approval-cleared", "a media file changed after approval", now)
            refused += 1
            print(f"  back to review: {it['id']} (media changed after approval)")
            continue
        problem = common.approval_problem(it)
        if problem:
            common.transition(it, "to_review", "pubqueue", "approval-refused", problem, now)
            refused += 1
            print(f"  back to review: {it['id']}: {problem}. A person must run `pubqueue.py approve` again.")
            continue
        if not it.get("slot") or common.parse_slot(it["slot"]) <= now:
            refused += 1
            print(f"  not scheduled: {it['id']} (slot {it.get('slot')} passed: run plan)")
            continue
        payload = adapter.build_payload(it, ctx)
        try:
            res = adapter.schedule(it, payload, ctx)
        except ProviderUnavailable as e:
            common.save_queue(qpath, data)
            print(f"provider unavailable: {e}. {it['id']} stays approved.", file=sys.stderr)
            return common.EXIT_PROVIDER
        except ProviderError as e:
            it["error"] = str(e)[:400]
            common.transition(it, "failed", "pubqueue", "provider-error", str(e)[:200], now)
            common.save_queue(qpath, data)
            refused += 1
            print(f"  failed: {it['id']}: {e}")
            continue
        outbox_file = ctx["outbox"] / f"{it['id']}.json"
        it["provider"] = {"name": adapter.name, "post_id": res.get("post_id"), "at": common.stamp(now),
                          "payload": posix_rel(outbox_file, qpath.parent) if outbox_file.exists() else ""}
        note = "dry run: nothing sent, payload in the outbox" if not adapter.real else f"{adapter.name} post {res.get('post_id')}"
        common.transition(it, "scheduled", "pubqueue", "scheduled", note, now)
        if res.get("status") == "published":
            common.transition(it, "published", "pubqueue", "published", "published at once by the provider", now)
        common.save_queue(qpath, data)
        print(f"  scheduled: {it['id']} for {human_slot(it['slot'])} via {adapter.name}")
    common.save_queue(qpath, data)
    print(f"schedule: {len(todo) - refused} scheduled, {refused} not scheduled")
    return common.EXIT_CHECK if refused else 0


def cmd_sync(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    ctx = adapter_ctx(qpath, data, now)
    unavailable = False
    for it in data["items"]:
        if it["status"] != "scheduled":
            continue
        name = (it.get("provider") or {}).get("name") or "dry-run"
        try:
            adapter = get_adapter(name)
            if adapter.real and adapter.available():
                raise ProviderUnavailable(adapter.available())
            st = adapter.status(it, ctx)
        except (ProviderUnavailable, ProviderError) as e:
            unavailable = True
            print(f"  {it['id']}: status unknown ({e})")
            continue
        if st == "published":
            common.transition(it, "published", "pubqueue", "published",
                              "dry run: simulated, slot passed" if not adapter.real else f"confirmed by {name}", now)
            print(f"  published: {it['id']}")
        elif st == "failed":
            common.transition(it, "failed", "pubqueue", "provider-failed", f"reported by {name}", now)
            print(f"  failed: {it['id']}")
    common.save_queue(qpath, data)
    return common.EXIT_PROVIDER if unavailable else 0


def cmd_mark(a, qpath: Path, data: Dict[str, Any], now: datetime) -> int:
    it = common.find_item(data, a.id)
    if a.published:
        if it["status"] == "approved":
            problem = common.approval_problem(it)
            if problem:
                raise common.GateRefused(f"{it['id']}: {problem}")
            common.transition(it, "scheduled", a.by or "", "posted-by-hand", a.note or "", now)
            it["provider"] = {"name": "manual", "post_id": a.post_id, "at": common.stamp(now), "payload": ""}
        common.transition(it, "published", a.by or "", "published", a.note or "marked by hand", now)
    else:
        it["error"] = a.note or "marked failed by hand"
        common.transition(it, "failed", a.by or "", "failed", a.note or "", now)
    common.save_queue(qpath, data)
    print(f"{it['id']}: {it['status']}")
    return 0


def cmd_validate(a, qpath: Path, data: Dict[str, Any]) -> int:
    problems: List[str] = []
    warnings: List[str] = []
    ids = [it["id"] for it in data["items"]]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate id {d}")
    for it in data["items"]:
        if common.content_hash(it) != it["content_hash"]:
            problems.append(f"{it['id']}: content_hash does not match the texts and media fields (edited by hand?)")
        if it["status"] in ("approved", "scheduled", "published"):
            problem = common.approval_problem(it)
            if problem:
                problems.append(f"{it['id']}: {it['status']} but {problem}")
            elif (it["approval"]["by"] or "").lower() in common.RESERVED_APPROVERS:
                problems.append(f"{it['id']}: approved by a reserved name {it['approval']['by']!r}")
        for ev in it.get("history", []):
            if ev.get("from") and ev.get("to") and ev["to"] not in common.TRANSITIONS.get(ev["from"], set()):
                problems.append(f"{it['id']}: history holds an illegal move {ev['from']} -> {ev['to']}")
        for m in it.get("media") or []:
            try:
                sha = common.file_sha256(common.media_file(qpath.parent, m["path"]))
            except common.Refused as e:
                problems.append(f"{it['id']}: {e}")
                continue
            if sha is None:
                (problems if it["status"] in ("to_review", "approved") else warnings).append(f"{it['id']}: media missing {m['path']}")
            elif m.get("sha256") and sha != m["sha256"]:
                (problems if it["status"] in ("approved",) else warnings).append(f"{it['id']}: media changed on disk {m['path']}")
    problems += common.window_conflicts(data["items"], data["settings"]["window_minutes"])
    for w in warnings:
        print(f"  WARNING {w}")
    for p in problems:
        print(f"  ERROR   {p}")
    print(f"validate: {'PASS' if not problems else 'FAIL'} ({len(data['items'])} items, {len(problems)} errors, {len(warnings)} warnings)")
    return 0 if not problems else common.EXIT_CHECK


# ------------------------------------------------------------------ cli

def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--queue", required=True, help="path to queue.json")
        p.add_argument("--now", help="local time YYYY-MM-DDTHH:MM instead of the clock (tests, replays)")
        return p

    p = add("init", "create queue.json")
    p.add_argument("--config", help="config.json whose settings seed the queue")
    p.add_argument("--project-name", help="project slug")
    p.add_argument("--timezone", help="IANA timezone, for example Europe/Paris")
    p.add_argument("--force", action="store_true")
    p = add("add", "lint a post spec and add it as to_review items")
    p.add_argument("spec")
    p.add_argument("--project", help="project folder: its voice rules join the writing gate")
    p.add_argument("--manual-gate", action="store_true", help="the writing gate cannot run: the copy was checked by hand")
    p = add("edit", "change the text, first comment or slot of an item")
    p.add_argument("id")
    p.add_argument("--text")
    p.add_argument("--text-file")
    p.add_argument("--first-comment")
    p.add_argument("--slot", help="new target slot, YYYY-MM-DDTHH:MM")
    p.add_argument("--by", default="")
    p.add_argument("--project")
    p.add_argument("--manual-gate", action="store_true")
    add("plan", "assign slots")
    p = add("list", "list items")
    p.add_argument("--status", choices=common.STATUSES)
    p.add_argument("--network", choices=common.NETWORKS)
    p.add_argument("--json", action="store_true")
    p = add("show", "one item in full")
    p.add_argument("id")
    p = add("review", "write the founder's review packet")
    p.add_argument("--out", help="markdown file (default: print)")
    p = add("approve", "HUMAN ONLY, interactive terminal: approve to_review items for the exact content reviewed")
    p.add_argument("ids", nargs="+")
    p.add_argument("--by", required=True, help="name of the person approving")
    p.add_argument("--code", action="append", help=argparse.SUPPRESS)  # refused with a clear message
    for name in ("reopen", "reject"):
        p = add(name, f"{name} an item")
        p.add_argument("id")
        p.add_argument("--by", default="")
        p.add_argument("--note", default="")
    p = add("schedule", "hand approved items to the publishing adapter")
    p.add_argument("--id", action="append", help="only these items (repeatable)")
    p.add_argument("--adapter", help="dry-run (default), zernio, command, webhook")
    p.add_argument("--live", action="store_true", help="required for any adapter that really sends")
    p.add_argument("--due-hours", type=float, help="only items whose slot is within this many hours")
    add("sync", "update scheduled items from the provider")
    p = add("mark", "record by hand that an item was published or failed")
    p.add_argument("id")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--published", action="store_true")
    g.add_argument("--failed", action="store_true")
    p.add_argument("--by", default="")
    p.add_argument("--note", default="")
    p.add_argument("--post-id")
    add("validate", "check schema and invariants")
    return ap


def main(argv: List[str]) -> int:
    a = parser().parse_args(argv)
    qpath = Path(a.queue)
    try:
        if a.cmd == "init":
            return cmd_init(a, qpath)
        with common.locked(qpath):
            data = common.load_queue(qpath)
            now = common.resolve_now(a.now, data["settings"]["timezone"])
            if a.cmd == "list":
                return cmd_list(a, data)
            if a.cmd == "show":
                return cmd_show(a, data)
            if a.cmd == "validate":
                return cmd_validate(a, qpath, data)
            handler = {"add": cmd_add, "edit": cmd_edit, "plan": cmd_plan, "review": cmd_review, "approve": cmd_approve,
                       "reopen": cmd_reopen, "reject": cmd_reject, "schedule": cmd_schedule, "sync": cmd_sync,
                       "mark": cmd_mark}[a.cmd]
            return handler(a, qpath, data, now)
    except common.GateRefused as e:
        print(f"approval gate: {e}", file=sys.stderr)
        return common.EXIT_GATE
    except common.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return common.EXIT_CHECK
    except ProviderUnavailable as e:
        print(f"provider unavailable: {e}", file=sys.stderr)
        return common.EXIT_PROVIDER
    except common.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return common.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
