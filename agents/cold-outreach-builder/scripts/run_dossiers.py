#!/usr/bin/env python3
"""
run_dossiers.py

Prepares and tracks the per-prospect research of cold-outreach-builder: one
brief file per prospect, worked in waves of three by sub-agents when the
harness has them, or one after the other in the same session when it does
not. The end of each task is a file on disk (prospect.json) that a command
checks, never a message. Standard library only, Python 3.9+.

Commands:
  prepare --leads CSV --run-dir DIR [--state state.json] [--today D]
          Normalizes the lead list into DIR/leads.csv (adds prospect_id when
          missing), drops leads the state file excludes (already contacted,
          suppressed: DIR/excluded-already-contacted.csv), writes
          DIR/dossiers/<id>/brief.md and DIR/dossiers/queue.json.
  status  --run-dir DIR
          Per prospect: done (prospect.json valid against the schema),
          invalid, or pending; prints the next wave. Exit 0 when all done.
  run     --run-dir DIR [--agent-cmd "CMD"] [--parallel 3] [--timeout 900]
          Optional: starts CMD once per pending prospect, the brief on stdin,
          working directory DIR, at most --parallel at a time, and checks the
          file afterwards. CMD comes from --agent-cmd or the FOG_AGENT_CMD
          environment variable (for example a model CLI that reads a prompt
          on stdin). Without a command, prints the briefs to work through
          sequentially and exits 0.

Resume: done prospects are never redone; run prepare again only to add leads.
Exit codes: 0 ok, 1 something pending or invalid (status, run), 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (AGENT, ASSETS, InputError, load_json, read_csv,  # noqa: E402
                          today_or, validator, write_csv, write_json)
from outreach_state import exclusion_reason, load_state  # noqa: E402

LEAD_COLUMNS = ["prospect_id", "first_name", "last_name", "role", "company", "company_url", "email",
                "linkedin_url", "profile_url", "channel", "fit_rationale", "source_url", "language", "geography"]

BRIEF = """# Research brief: {pid}

You prepare one prospect dossier for cold-outreach-builder. Work on this prospect only.

## Prospect (from the lead list)

{lead}

## Output

Write `{out}`, valid against `{schema}`.
Follow `{skill}`.

## Rules

1. Read public pages only: the company site and blog, press, registries, talks,
   public posts (linkedin.com/posts/..., x.com/<user>/status/...). Never open or
   scrape a LinkedIn profile or company page.
2. Cache every page before you use it:
   `python3 {scripts}/cache_page.py --cache {cache} <url>`
   or, when another provider fetched it: `--url <url> --from-file <file>`.
3. A fact has an id (f1, f2...), a type, a claim in your words, a date
   (YYYY-MM-DD read on the page or from the post id), the source_url and an
   excerpt copied verbatim from the cached page (15 to 400 characters), and an
   owner (self, company, third_party). No readable date: not a fact.
4. Prefer, in order: what the person did or published in the last 120 days
   (raise, company creation, launch, hiring, new role), then their posts and
   talks, then older facts. Two to five facts are enough.
5. language and register: what the person uses in public writing, with the URL.
6. relationship: none, unless the lead list or the founder says otherwise.
7. Never guess an email. Keep the one from the lead list, or one published on a
   page (email_source_url).
8. Nothing true and dated found: write the dossier with "facts": []. The
   prospect goes to tier C; that is a valid result, never a reason to invent.

## Done when

`python3 {scripts}/verify_dossiers.py {dossiers} --cache {cache}` shows
`{pid}: ok`. Fix the dossier, never the check.
"""


def norm_lead(row: Dict[str, str], idx: int) -> Dict[str, str]:
    lead = dict(row)
    if not lead.get("first_name") and lead.get("name"):
        parts = lead["name"].split()
        lead["first_name"] = parts[0]
        lead.setdefault("last_name", " ".join(parts[1:]))
    if not lead.get("linkedin_url") and lead.get("linkedin"):
        lead["linkedin_url"] = lead["linkedin"]
    if not lead.get("prospect_id"):
        lead["prospect_id"] = f"p{idx:03d}"
    lead["prospect_id"] = lead["prospect_id"].strip().lower()
    return lead


def cmd_prepare(a) -> int:
    header, rows = read_csv(a.leads)
    today = today_or(a.today)
    state = load_state(a.state) if a.state and os.path.isfile(a.state) else None
    recontact = int(load_json(os.path.join(ASSETS, "limits.json"))["state"]["recontact_after_days"])
    leads, excluded, seen = [], [], set()
    for i, r in enumerate(rows, start=1):
        lead = norm_lead(r, i)
        if lead["prospect_id"] in seen:
            raise InputError(f"duplicate prospect_id {lead['prospect_id']} in {a.leads}")
        seen.add(lead["prospect_id"])
        why = exclusion_reason(state, lead, today, recontact) if state else ""
        if why:
            excluded.append({"prospect_id": lead["prospect_id"], "prospect": lead.get("email") or lead.get("linkedin_url") or lead["first_name"], "reason": why})
            continue
        leads.append(lead)
    extra = [h for h in header if h not in LEAD_COLUMNS and h not in ("name", "linkedin")]
    run = os.path.abspath(a.run_dir)
    dossiers = os.path.join(run, "dossiers")
    cache = os.path.join(run, "cache")
    os.makedirs(cache, exist_ok=True)
    write_csv(os.path.join(run, "leads.csv"), LEAD_COLUMNS + extra, leads)
    if excluded:
        write_csv(os.path.join(run, "excluded-already-contacted.csv"), ["prospect_id", "prospect", "reason"], excluded)
    queue = []
    for lead in leads:
        pid = lead["prospect_id"]
        folder = os.path.join(dossiers, pid)
        os.makedirs(folder, exist_ok=True)
        shown = "\n".join(f"- {k}: {v}" for k, v in lead.items() if v)
        with open(os.path.join(folder, "brief.md"), "w", encoding="utf-8") as f:
            f.write(BRIEF.format(pid=pid, lead=shown, out=os.path.join(folder, "prospect.json"),
                                 schema=os.path.join(ASSETS, "prospect.schema.json"),
                                 skill=os.path.join(AGENT, "skills", "researching-prospects", "SKILL.md"),
                                 scripts=os.path.join(AGENT, "scripts"), cache=cache, dossiers=dossiers))
        queue.append(pid)
    write_json(os.path.join(dossiers, "queue.json"), {"prospects": queue, "wave_size": 3})
    print(f"{len(leads)} brief(s) in {dossiers}, {len(excluded)} lead(s) excluded by the state file")
    for w in range(0, len(queue), 3):
        print(f"  wave {w // 3 + 1}: {', '.join(queue[w:w + 3])}")
    return 0


def statuses(run: str) -> Dict[str, str]:
    dossiers = os.path.join(run, "dossiers")
    queue = load_json(os.path.join(dossiers, "queue.json")).get("prospects", [])
    schema = load_json(os.path.join(ASSETS, "prospect.schema.json"))
    validate = validator()
    out = {}
    for pid in queue:
        path = os.path.join(dossiers, pid, "prospect.json")
        if not os.path.isfile(path):
            out[pid] = "pending"
            continue
        try:
            errs = validate(load_json(path), schema)
        except InputError:
            errs = ["unreadable"]
        out[pid] = "done" if not errs else "invalid"
    return out


def cmd_status(a) -> int:
    st = statuses(os.path.abspath(a.run_dir))
    for pid, s in st.items():
        print(f"{pid}: {s}")
    todo = [p for p, s in st.items() if s != "done"]
    print(f"\n{len(st) - len(todo)} done, {len(todo)} to do")
    if todo:
        print(f"next wave: {', '.join(todo[:3])}")
    return 0 if not todo else 1


def cmd_run(a) -> int:
    run = os.path.abspath(a.run_dir)
    st = statuses(run)
    todo = [p for p, s in st.items() if s != "done"]
    cmd = a.agent_cmd or os.environ.get("FOG_AGENT_CMD", "")
    if not todo:
        print("every dossier is done")
        return 0
    if not cmd:
        print("No --agent-cmd or FOG_AGENT_CMD: work the briefs in this session, one after the other:")
        for pid in todo:
            print(f"  {os.path.join(run, 'dossiers', pid, 'brief.md')}")
        return 0
    argv = shlex.split(cmd)
    for w in range(0, len(todo), a.parallel):
        wave = todo[w:w + a.parallel]
        procs: List[Any] = []
        for pid in wave:
            folder = os.path.join(run, "dossiers", pid)
            with open(os.path.join(folder, "brief.md"), "r", encoding="utf-8") as f:
                brief = f.read()
            log = open(os.path.join(folder, "agent.log"), "w", encoding="utf-8")
            try:
                p = subprocess.Popen(argv, cwd=run, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
            except OSError as e:
                log.close()
                raise InputError(f"cannot start {argv[0]}: {e}")
            p.stdin.write(brief)
            p.stdin.close()
            procs.append((pid, p, log, time.time()))
        for pid, p, log, started in procs:
            try:
                p.wait(timeout=max(1, a.timeout - (time.time() - started)))
            except subprocess.TimeoutExpired:
                p.kill()
                print(f"{pid}: timed out after {a.timeout}s")
            log.close()
        st = statuses(run)
        print(f"wave {w // a.parallel + 1}: " + ", ".join(f"{pid} {st[pid]}" for pid in wave))
    st = statuses(run)
    left = [p for p, s in st.items() if s != "done"]
    print(f"{len(st) - len(left)} done, {len(left)} left" + (f": {', '.join(left)} (see their agent.log, then work them in this session)" if left else ""))
    return 0 if not left else 1


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--leads", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--state")
    p.add_argument("--today")
    p = sub.add_parser("status")
    p.add_argument("--run-dir", required=True)
    p = sub.add_parser("run")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--agent-cmd")
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args(argv)
    try:
        return {"prepare": cmd_prepare, "status": cmd_status, "run": cmd_run}[a.cmd](a)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
