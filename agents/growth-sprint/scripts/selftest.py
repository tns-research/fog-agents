#!/usr/bin/env python3
"""selftest.py: offline regression test of growth-sprint.

  python3 agents/growth-sprint/scripts/selftest.py [--keep DIR]

Simulates a whole sprint on a fictional swanbase project with fake agent
outputs (copies of the repo examples, plus fixtures for the agents that have
none). No network, no key, no agent is really run. The approval key is a
throwaway file in the temporary folder (FOG_APPROVAL_KEY_FILE); approvals are
typed at a pseudo-terminal (pty), as a person would. POSIX only.

1. Registry: schema, every agent folder of the repo listed, spec and schema
   paths present, the repo examples pass the registry checks.
2. Plan validation: the example sprint passes; broken plans fail with the
   expected error (unknown agent, cycle, unknown dependency, spend or publish
   flag hidden, no estimate basis, over the cap, colliding labels, bad goal).
3. Approval gate: nothing runs before approval; reserved names, no packet,
   no terminal, a code passed as an argument and a wrong code typed at the
   terminal are refused; the plan code appears in no file and no output but
   the interactive approve; an approval written into state.json by hand (or
   a sealed one whose cap was raised by hand) is refused by next; an edit of
   sprint.json voids the approval.
4. Waves: at most 3 steps, never two steps of one agent, content-publisher
   alone; a fresh context is reused; a missing input opens needs_human and
   the other steps go on.
5. Interruption and resume: a finished step is settled from the disk, an
   unfinished one restarts without counting as a failure.
6. Disk check over declarations: a step that claims done with nothing on disk
   fails; two failures in a row trip the breaker; a person clears it.
7. STOP file: next and mark running refuse while it exists.
8. Human gates: static-ads spend gate and content-publisher approval land in
   needs_human without blocking the rest; resolve refuses while the queue
   still has to_review items and refuses agent names.
9. Budget: alert at 80 %, a spending step that no longer fits waits in
   needs_human, spent above the cap trips the breaker, a re-approved plan
   with a higher cap clears it.
10. Completion: report, run line valid against the shared schema, state
    valid against its schema, the growth-pulse experiments seed a next sprint.
11. check_step standalone (stale file, missing column) and --help of every script.

Exit 0 when all hold, 1 otherwise. Work happens in a temporary folder (or
--keep DIR); the repo is never written.
"""

from __future__ import annotations

import argparse
import copy as copy_mod
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import re
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
REPO = AGENT.parent.parent
sys.path.insert(0, str(SCRIPTS))
import sprint_lib as L  # noqa: E402

FIX = SCRIPTS / "fixtures"
EXAMPLE = AGENT / "examples" / "swanbase-demo-calls-20261012" / "sprint.json"
SPRINT_ID = "demo-calls-20261012"
PERSON = "Alex Martin"  # fictional founder of the fixture project
TODAY = datetime.now().strftime("%Y%m%d")
DAY = datetime.now().strftime("%Y-%m-%d")

FAILS: List[str] = []
PASSES = 0


def check(cond: bool, what: str) -> None:
    global PASSES
    if cond:
        PASSES += 1
    else:
        FAILS.append(what)
        print(f"  FAIL {what}")


def run(script: str, *args: str) -> Tuple[int, str]:
    env = dict(os.environ)
    p = subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True,
                       env=env, stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout + p.stderr


def sp(*args: str) -> Tuple[int, str]:
    return run("sprint.py", *args)


def state(sdir: Path) -> Dict[str, Any]:
    return L.load_json(sdir / "state.json")


def status_of(sdir: Path, sid: str) -> str:
    return state(sdir)["steps"][sid]["status"]


def open_item(sdir: Path, sid: str, kind: str) -> Dict[str, Any]:
    for h in state(sdir)["needs_human"]:
        if h["step"] == sid and h["kind"] == kind and h["resolved"] is None:
            return h
    return {}


def started(out: str) -> List[str]:
    return [line.split()[1] for line in out.splitlines() if line.startswith("STARTED ")]


def code_of(sdir: Path) -> str:
    """The plan code approve would print (same throwaway key as the commands)."""
    plan = L.load_json(sdir / "sprint.json")
    return L.plan_code(plan["sprint_id"], L.canonical_hash(plan))


def sp_tty(answer: Callable[[str], str], *args: str, timeout: float = 60.0) -> Tuple[int, str]:
    """sprint.py under a pseudo-terminal, as a person runs it in their own
    terminal: at the plan-code prompt, answer(output so far) is typed."""
    import pty
    import select
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, str(SCRIPTS / "sprint.py"), *args], stdin=slave, stdout=slave, stderr=slave,
                            env=dict(os.environ), close_fds=True)
    os.close(slave)
    buf, answered, deadline = b"", False, time.time() + timeout
    try:
        while time.time() < deadline:
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:  # EIO: the child closed the terminal
                    break
                if not chunk:
                    break
                buf += chunk
                text = buf.decode("utf-8", "replace")
                if not answered and "Type the plan code" in text:
                    answered = True
                    os.write(master, (answer(text) + "\n").encode("utf-8"))
            elif proc.poll() is not None:
                break
        else:
            proc.kill()
    finally:
        os.close(master)
    return proc.wait(timeout=10), buf.decode("utf-8", "replace")


def shown_code(text: str) -> str:
    found = re.findall(r"Plan code: ([0-9a-f]{8})", text)
    return found[-1] if found else ""


def approve(sdir: Path) -> int:
    sp("packet", str(sdir))
    rc, out = sp_tty(shown_code, "approve", str(sdir), "--by", PERSON)
    return rc


# ---------------------------------------------------------------- fake agents


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


REPORT = "# Report\n\n" + "Fictional fixture report written by the growth-sprint selftest. " * 6 + "\n"


def fake_outputs(project: Path, agent: str, label: str, mode: str = "ok") -> None:
    """Write what the agent would write. mode: ok, gate (stop at the spend gate),
    invalid (broken JSON), rerun (content-publisher after the approval)."""
    d = TODAY
    if agent == "market-signal":
        copy(REPO / "agents/market-signal/examples/swanbase-preseed-fundraising-20261012/market-signal-20261012.json",
             project / f"market-signal/market-signal-{d}.json")
        write(project / f"market-signal/market-signal-{d}.md", REPORT)
    elif agent == "first-users-hunter":
        copy(REPO / "agents/first-users-hunter/examples/swanbase-preseed-founders-20261012/people-20261012.jsonl",
             project / f"first-users-hunter/people-{d}.jsonl")
        copy(FIX / "outputs/prospects.csv", project / f"first-users-hunter/prospects-{d}.csv")
        write(project / f"first-users-hunter/first-users-{d}.md", REPORT)
    elif agent == "landing-page-analyzer":
        body = "{ broken" if mode == "invalid" else json.dumps({"page": "https://swanbase.co", "fixes": []})
        write(project / f"landing-page-analyzer/landing-audit-{d}.json", body)
        write(project / f"landing-page-analyzer/landing-audit-{d}.md", REPORT)
    elif agent == "carousel-builder":
        run_dir = project / f"carousel-builder/{label}-{d}"
        ex = REPO / "agents/carousel-builder/examples/swanbase-seed-deck-20261010"
        copy(ex / "deck.json", run_dir / "deck.json")
        copy(ex / "captions.md", run_dir / "captions.md")
        write(run_dir / "export/carousel.pdf", "%PDF-1.4\n" + "% fixture\n" * 200)
        write(run_dir / "export/qa.json", json.dumps({"pass": True}))
    elif agent == "static-ads-builder":
        run_dir = project / f"static-ads-builder/{label}-{d}"
        ex = REPO / "agents/static-ads-builder/examples/swanbase-mini-batch-20261012"
        copy(ex / "ads.json", run_dir / "ads.json")
        if mode != "gate":
            copy(ex / "preview.jpg", run_dir / "renders/contact-sheet.jpg")
            write(run_dir / f"static-ads-{d}.md", REPORT)
    elif agent == "cold-outreach-builder":
        run_dir = project / f"cold-outreach-builder/outreach-{d}"
        write(run_dir / "cold-outreach-output.json", json.dumps({"templates": []}))
        write(run_dir / "sequence-export.csv", "email,first_name,step1_subject\n")
        write(run_dir / f"outreach-summary-{d}.md", REPORT)
    elif agent == "content-publisher":
        run_dir = project / f"content-publisher/{label}-{d}"
        copy(REPO / "agents/content-publisher/examples/swanbase-week-20261019/posts.json", run_dir / "posts.json")
        write(run_dir / f"review-{d}.md", REPORT)
        qpath = project / "content-publisher/queue.json"
        if mode == "rerun":
            q = L.load_json(qpath)
            for it in q["items"]:
                if it["status"] == "approved":
                    it["status"] = "scheduled"
        else:
            q = json.loads((FIX / "outputs/queue.json").read_text(encoding="utf-8").replace("__DAY__", DAY))
            for it in q["items"]:
                it["content_hash"] = hashlib.sha256(it["text"].encode("utf-8")).hexdigest()
        L.write_json_atomic(qpath, q)
    elif agent == "short-video-builder":
        run_dir = project / f"short-video-builder/{label}-{d}"
        copy(REPO / "agents/short-video-builder/examples/synthetic-talk/clips.json", run_dir / "clips.json")
        write(run_dir / "export/qa.json", json.dumps({"pass": True}))
        write(run_dir / "posts.md", REPORT)
    elif agent == "growth-pulse":
        text = (FIX / "outputs/experiments.json").read_text(encoding="utf-8").replace("__DATE__", d).replace("__DAY__", DAY)
        write(project / f"growth-pulse/experiments-{d}.json", text)
        write(project / f"growth-pulse/growth-pulse-{d}.md", REPORT)
    else:
        raise ValueError(agent)


def finish(project: Path, sdir: Path, sid: str, agent: str, status: str = "ok", spent: float = 0,
           pending: List[Dict[str, str]] = None, defaults: List[str] = None) -> None:
    """The step runner's last acts: the agent's run line and the step result file."""
    mem = project / "project-context/memory/runs.jsonl"
    with open(mem, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": L.iso(L.now_dt()), "agent": agent, "status": status}) + "\n")
    res = {"step": sid, "status": status, "spent_eur": spent, "pending": pending or [],
           "defaults_used": defaults or []}
    L.write_json_atomic(sdir / "results" / f"{sid}.json", res)


def run_step(project: Path, sdir: Path, sid: str, mode: str = "ok", spent: float = 0, **kw: Any) -> None:
    plan = L.load_json(sdir / "sprint.json")
    step = next(s for s in plan["steps"] if s["id"] == sid)
    fake_outputs(project, step["agent"], step.get("label") or "", mode)
    finish(project, sdir, sid, step["agent"], spent=spent, **kw)


def set_cap(sdir: Path, cap: float) -> None:
    p = L.load_json(sdir / "sprint.json")
    p["budget"]["cap_eur"] = cap
    L.write_json_atomic(sdir / "sprint.json", p)


# ---------------------------------------------------------------- sections


def t_registry() -> None:
    print("1. registry")
    reg = L.load_registry()
    check(not L.schema_errors(reg, AGENT / "assets/agents.schema.json"), "agents.json valid against its schema")
    folders = sorted(p.name for p in (REPO / "agents").iterdir()
                     if p.is_dir() and not p.name.startswith("_") and p.name != "growth-sprint")
    for name in folders:
        check(name in reg["agents"], f"agent folder {name} listed in agents.json")
    for name, a in reg["agents"].items():
        check((REPO / "agents" / name).is_dir(), f"{name}: folder exists")
        spec = REPO / a["spec"]
        if not spec.is_file():
            print(f"  NOTE {name}: {a['spec']} not written yet (agent in progress)")
        for o in a["outputs"]:
            if o.get("schema"):
                ok = (REPO / o["schema"]).is_file()
                check(ok, f"{name}: schema {o['schema']} exists")
                if ok:
                    L.load_json(REPO / o["schema"])
        for g in a["human_gates"]:
            check(g["kind"] in ("spend", "publish", "input", "other"), f"{name}: gate kind")
    check(reg["agents"]["static-ads-builder"]["spends"] and reg["agents"]["content-publisher"]["publishes"],
          "static-ads spends, content-publisher publishes")
    check(any(g["kind"] == "publish" for g in reg["agents"]["content-publisher"]["human_gates"]),
          "content-publisher approval is a registry gate")
    check(any(g["kind"] == "spend" for g in reg["agents"]["static-ads-builder"]["human_gates"]),
          "static-ads spend gates are a registry gate")
    for script in ("sprint.py", "check_step.py", "sprint_lib.py"):
        src = (SCRIPTS / script).read_text(encoding="utf-8")
        check("subprocess" not in src and "os.system" not in src,
              f"{script} runs no other program (it can never approve or publish for anyone)")


def t_plan(project: Path) -> Path:
    print("2. plan validation")
    gs = project / "growth-sprint"
    sdir = gs / SPRINT_ID
    sdir.mkdir(parents=True)
    copy(EXAMPLE, sdir / "sprint.json")
    rc, out = sp("validate", str(sdir))
    check(rc == 0, f"example sprint validates (rc {rc}): {out[-300:]}")
    check("s09-shorts" in out and "video" in out, "validate warns that s09 has no video input")
    base = L.load_json(EXAMPLE)

    def bad(mutate: Any, expect: str, name: str) -> None:
        p = copy_mod.deepcopy(base)
        mutate(p)
        d = gs / f"bad-{name}"
        d.mkdir(exist_ok=True)
        L.write_json_atomic(d / "sprint.json", p)
        rc, out = sp("validate", str(d))
        check(rc == 1 and expect in out, f"broken plan '{name}' refused with '{expect}' (rc {rc}): {out[-200:]}")

    bad(lambda p: p["steps"][1].update(agent="newsletter-bot"), "unknown agent", "agent")
    bad(lambda p: p["steps"][0]["depends_on"].append("s11-pulse"), "dependency cycle", "cycle")
    bad(lambda p: p["steps"][2]["depends_on"].append("s99-ghost"), "unknown step", "dep")
    bad(lambda p: p["steps"][5].update(spends=False, estimate_eur=0), "can spend money", "spend-flag")
    bad(lambda p: p["steps"][7].update(publishes=False), "can publish", "publish-flag")
    bad(lambda p: p["steps"][5].pop("estimate_basis"), "estimate_basis", "basis")
    bad(lambda p: p["budget"].update(cap_eur=10), "above the cap", "cap")
    bad(lambda p: p["steps"][9].update(label="demo-tofu"), "would collide", "label")
    bad(lambda p: p["goal"].update(source="growth-pulse/experiments-20261005.json#E-20261005-1"), "not found", "goal")
    bad(lambda p: p["steps"][3].update(estimate_eur=5), "does not spend", "estimate")
    for d in gs.glob("bad-*"):
        shutil.rmtree(d)
    return sdir


def t_approval(sdir: Path) -> None:
    print("3. approval gate")
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 4 and "not approved" in out, f"next before approval exits 4 (rc {rc})")
    rc, out = sp("approve", str(sdir), "--by", PERSON)
    check(rc == 4 and "packet" in out, f"approve without a packet refused (rc {rc})")
    rc, out = sp("packet", str(sdir))
    packet = (sdir / "approval.md").read_text(encoding="utf-8")
    fingerprint = L.canonical_hash(L.load_json(sdir / "sprint.json"))[:12]
    check(rc == 0 and fingerprint in packet, "packet written with the plan fingerprint")
    check(code_of(sdir) not in packet and code_of(sdir) not in out and "--code" not in packet,
          "the plan code is in neither the packet nor the packet command output")
    check("static-ads-builder, spend gate" in packet and "content-publisher, publish gate" in packet,
          "packet lists the gates that stay with the founder")
    check("`s06-ads` (12.00 EUR)" in packet and "`s08-publish`" in packet, "packet lists spending and publishing steps")
    for name in ("claude", "growth-sprint", "content-publisher", "<your-name>", "bot"):
        rc, out = sp("approve", str(sdir), "--by", name)
        check(rc == 4 and "person's name" in out, f"approve --by {name!r} refused (rc {rc})")
    rc, out = sp("approve", str(sdir), "--by", PERSON)
    check(rc == 4 and "interactive terminal" in out, f"approve without a terminal refused (rc {rc})")
    rc, out = sp("approve", str(sdir), "--by", PERSON, "--code", code_of(sdir))
    check(rc == 4 and "not accepted as an argument" in out, f"approve --code with the right code refused (rc {rc})")
    rc, out = sp_tty(lambda t: "00000000" if shown_code(t) != "00000000" else "11111111", "approve", str(sdir), "--by", PERSON)
    check(rc == 4 and "wrong plan code" in out, f"wrong plan code typed at the terminal refused (rc {rc})")
    rc, out = sp("validate", str(sdir))
    check(rc == 0 and code_of(sdir) not in out, "validate prints no plan code")

    # An approval written into state.json by hand, with the right plan hash.
    plan = L.load_json(sdir / "sprint.json")
    clean = (sdir / "state.json").read_text(encoding="utf-8")
    st = state(sdir)
    st["approval"] = {"by": PERSON, "at": L.iso(L.now_dt()), "plan_hash": L.canonical_hash(plan),
                      "cap_eur": float(plan["budget"]["cap_eur"]), "spend_steps": [], "publish_steps": []}
    st["approvals"].append(st["approval"])
    st["status"] = "approved"
    L.write_json_atomic(sdir / "state.json", st)
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 4 and "not recorded by" in out, f"an approval written into state.json by hand is refused by next (rc {rc})")
    st["approval"]["mac"] = "0" * 64
    L.write_json_atomic(sdir / "state.json", st)
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 4 and "not recorded by" in out, f"...also with a made-up seal (rc {rc})")
    (sdir / "state.json").write_text(clean, encoding="utf-8")

    rc, out = sp_tty(shown_code, "approve", str(sdir), "--by", PERSON)
    check(rc == 0, f"approval by a person typing the code at the terminal (rc {rc}): {out[-300:]}")
    st = state(sdir)
    check(st["approval"]["by"] == PERSON and st["approval"]["spend_steps"] == ["s05-carousel", "s06-ads", "s10-retarget"],
          "approval records the person and the spending steps")
    check(len(st["approval"].get("mac", "")) == 64, "the approval carries its seal")
    check(code_of(sdir) not in (sdir / "state.json").read_text(encoding="utf-8"), "the plan code is not written into state.json")

    # A sealed approval whose cap is raised by hand.
    sealed = (sdir / "state.json").read_text(encoding="utf-8")
    st["approval"]["cap_eur"] = 5000.0
    L.write_json_atomic(sdir / "state.json", st)
    rc, out = sp("next", str(sdir))
    check(rc == 4 and "not recorded by" in out, f"a cap raised by hand in state.json voids the approval (rc {rc})")
    (sdir / "state.json").write_text(sealed, encoding="utf-8")


def t_run(project: Path, sdir: Path) -> None:
    print("4. first wave: reuse, missing input, wave size")
    rc, out = sp("next", str(sdir), "--claim")
    first = started(out)
    check(rc == 0 and first == ["s02-signal", "s03-people", "s04-landing"], f"first wave is s02, s03, s04 (got {first})")
    check(status_of(sdir, "s01-context") == "skipped", "fresh project-context reused (skipped)")
    check("reused" in " ".join(state(sdir)["steps"]["s01-context"]["notes"]), "reuse recorded in the notes")
    check(status_of(sdir, "s09-shorts") == "needs_human" and open_item(sdir, "s09-shorts", "input"),
          "s09 without a video waits in needs_human")
    check((sdir / "briefs/s02-signal.md").is_file(), "brief written for each started step")
    brief = (sdir / "briefs/s02-signal.md").read_text(encoding="utf-8")
    check("Autonomous mode" in brief and "check_step.py" in brief and "results" in brief, "brief carries the rules and the done check")

    print("5. interruption and resume")
    run_step(project, sdir, "s02-signal")              # finished, but the session dies before mark
    fake_outputs(project, "landing-page-analyzer", "", "invalid")
    finish(project, sdir, "s04-landing", "landing-page-analyzer")
    rc, out = sp("mark", str(sdir), "s04-landing", "done")
    check(rc == 1 and status_of(sdir, "s04-landing") == "pending", f"invalid JSON output fails the step (rc {rc})")
    check(state(sdir)["steps"]["s04-landing"]["consecutive_failures"] == 1, "first failure counted")
    rc, out = sp("resume", str(sdir))
    check(rc == 0, f"resume exits 0 (rc {rc}): {out}")
    check(status_of(sdir, "s02-signal") == "done", "s02 settled done from the disk after the interruption")
    check(status_of(sdir, "s03-people") == "pending", "s03 (nothing written) back to pending")
    check(state(sdir)["steps"]["s03-people"]["consecutive_failures"] == 0, "an interruption is not a failure")

    print("6. disk check over declarations, failures breaker")
    rc, out = sp("next", str(sdir), "--claim")
    wave = started(out)
    check(wave == ["s03-people", "s04-landing", "s05-carousel"], f"second wave (got {wave})")
    check("s06-ads" not in wave, "wave capped at 3")
    finish(project, sdir, "s04-landing", "landing-page-analyzer")   # claims ok, writes nothing
    os.remove(project / f"landing-page-analyzer/landing-audit-{TODAY}.json")
    rc, out = sp("mark", str(sdir), "s04-landing", "done")
    check(rc == 3 and status_of(sdir, "s04-landing") == "failed", f"second failure trips the breaker (rc {rc})")
    check("missing" in out, "the refusal names the missing output")
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 3 and "circuit breaker" in out, f"next refused while halted (rc {rc})")
    run_step(project, sdir, "s03-people")
    run_step(project, sdir, "s05-carousel", defaults=["direction: editorial-paper, best ranked at the cover board"])
    rc3, _ = sp("mark", str(sdir), "s03-people", "done")
    rc5, _ = sp("mark", str(sdir), "s05-carousel", "done")
    check(status_of(sdir, "s03-people") == "done" and status_of(sdir, "s05-carousel") == "done",
          "steps already in flight still settle while halted")
    rc, out = sp("resume", str(sdir), "--by", "assistant", "--retry", "s04-landing")
    check(rc == 4, f"breaker not cleared by an agent name (rc {rc})")
    rc, out = sp("resume", str(sdir), "--by", PERSON, "--retry", "s04-landing")
    check(rc == 0 and status_of(sdir, "s04-landing") == "pending", f"a person clears the breaker with --retry (rc {rc}): {out}")

    print("7. STOP file")
    write(sdir / "STOP", "pause\n")
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 3 and "STOP" in out, f"next refused with a STOP file (rc {rc})")
    rc, out = sp("mark", str(sdir), "s04-landing", "running")
    check(rc == 3, f"mark running refused with a STOP file (rc {rc})")
    os.remove(sdir / "STOP")
    write(project / "growth-sprint/STOP", "")
    rc, out = sp("next", str(sdir))
    check(rc == 3, "project-level STOP file honoured")
    os.remove(project / "growth-sprint/STOP")

    print("8. human gates do not block the rest")
    rc, out = sp("next", str(sdir), "--claim")
    wave = started(out)
    check(wave == ["s04-landing", "s06-ads", "s07-outreach"], f"third wave (got {wave})")
    check("s08-publish" not in wave, "content-publisher never shares a wave")
    run_step(project, sdir, "s04-landing")
    run_step(project, sdir, "s07-outreach")
    fake_outputs(project, "static-ads-builder", "demo-tofu", "gate")
    finish(project, sdir, "s06-ads", "static-ads-builder", status="partial",
           pending=[{"kind": "spend", "reason": "Gate 1: two concepts need a photo plate"}])
    for sid in ("s04-landing", "s07-outreach"):
        rc, _ = sp("mark", str(sdir), sid, "done")
        check(rc == 0 and status_of(sdir, sid) == "done", f"{sid} done (rc {rc})")
    rc, out = sp("mark", str(sdir), "s06-ads", "done")
    item = open_item(sdir, "s06-ads", "spend")
    check(rc == 5 and status_of(sdir, "s06-ads") == "needs_human" and item.get("gate") == "plates-gate-1-and-2",
          f"static-ads spend gate surfaced in needs_human (rc {rc})")
    check("Gate 2" in item.get("how", ""), "the item says how the founder clears the gate")
    rc, out = sp("next", str(sdir), "--claim")
    check(started(out) == ["s08-publish"], f"content-publisher runs alone while s06 waits (got {started(out)})")
    run_step(project, sdir, "s08-publish")
    rc, out = sp("mark", str(sdir), "s08-publish", "done")
    pub = open_item(sdir, "s08-publish", "publish")
    check(rc == 5 and pub, f"queued posts to_review open a publish item (rc {rc})")
    rc, out = sp("resolve", str(sdir), pub["id"], "--by", PERSON)
    check(rc == 1 and "to_review" in out, f"resolve refused while items are still to_review (rc {rc})")
    rc, out = sp("resolve", str(sdir), pub["id"], "--by", "content-publisher")
    check(rc == 4, f"resolve refuses an agent name (rc {rc})")
    q = L.load_json(project / "content-publisher/queue.json")      # fixture: stands for the founder approving in their own terminal (the gate itself is tested by content-publisher)
    for it in q["items"]:
        it["status"] = "approved"
        it["approval"] = {"by": PERSON, "at": DAY + "T10:00", "content_hash": it["content_hash"]}
    L.write_json_atomic(project / "content-publisher/queue.json", q)
    rc, out = sp("resolve", str(sdir), pub["id"], "--by", PERSON)
    check(rc == 0 and status_of(sdir, "s08-publish") == "pending", f"after the approval on disk, s08 reruns (rc {rc})")
    rc, out = sp("resolve", str(sdir), item["id"], "--by", PERSON, "--note", "Gate 1 and 2 answered in the agent session")
    check(rc == 0 and status_of(sdir, "s06-ads") == "pending", f"spend gate cleared by a person, s06 reruns (rc {rc})")
    inp = open_item(sdir, "s09-shorts", "input")
    rc, out = sp("mark", str(sdir), "s09-shorts", "skipped", "--reason", "no video")
    check(rc == 4 and status_of(sdir, "s09-shorts") == "needs_human", f"the orchestrator cannot skip a step a person must decide (rc {rc})")
    rc, out = sp("resolve", str(sdir), inp["id"], "--by", PERSON)
    check(rc == 1 and "video" in out, f"input item refused without --set (rc {rc})")
    rc, out = sp("resolve", str(sdir), inp["id"], "--by", PERSON, "--set", "video=media/pitch-talk.mp4")
    check(rc == 0 and status_of(sdir, "s09-shorts") == "pending", f"input supplied, s09 pending (rc {rc})")

    print("9. budget")
    rc, out = sp("next", str(sdir), "--claim")
    check(started(out) == ["s06-ads", "s09-shorts"], f"fourth wave without the exclusive s08 (got {started(out)})")
    check("video" in (sdir / "briefs/s09-shorts.md").read_text(encoding="utf-8"), "the supplied input reaches the brief")
    run_step(project, sdir, "s06-ads", spent=34)
    run_step(project, sdir, "s09-shorts")
    rc, _ = sp("mark", str(sdir), "s06-ads", "done")
    check(rc == 0 and status_of(sdir, "s06-ads") == "done", f"s06 done after the gate (rc {rc})")
    st = state(sdir)
    check(st["budget"]["spent_eur"] == 34 and st["budget"]["alerted"], "spend recorded, alert at 80 % of the cap")
    rc, _ = sp("mark", str(sdir), "s09-shorts", "done")
    rc, out = sp("next", str(sdir), "--claim")
    check(started(out) == ["s08-publish"], f"s08 reruns alone (got {started(out)})")
    check(status_of(sdir, "s10-retarget") == "needs_human" and open_item(sdir, "s10-retarget", "budget"),
          "s10 estimate above the budget left waits in needs_human")
    run_step(project, sdir, "s08-publish", mode="rerun")
    rc, _ = sp("mark", str(sdir), "s08-publish", "done")
    check(rc == 0 and status_of(sdir, "s08-publish") == "done", f"s08 done once approved items are scheduled (rc {rc})")
    rc, out = sp("next", str(sdir), "--claim")
    check(started(out) == ["s11-pulse"], f"growth-pulse runs while s10 waits (got {started(out)})")
    run_step(project, sdir, "s11-pulse")
    rc, _ = sp("mark", str(sdir), "s11-pulse", "done")
    check(rc == 0, f"s11 done (rc {rc})")
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 5 and "H-" in out, f"only a person can move the sprint now (rc {rc})")
    b = open_item(sdir, "s10-retarget", "budget")
    rc, out = sp("resolve", str(sdir), b["id"], "--by", PERSON)
    check(rc == 1 and "above the approved budget" in out, f"budget item refused before a new cap is approved (rc {rc})")
    set_cap(sdir, 60)
    rc, out = sp("next", str(sdir))
    check(rc == 4 and "changed since the approval" in out, f"an edited plan voids the approval (rc {rc})")
    check(approve(sdir) == 0, "new cap approved by a person")
    rc, out = sp("resolve", str(sdir), b["id"], "--by", PERSON)
    check(rc == 0 and status_of(sdir, "s10-retarget") == "pending", f"budget item resolved after the new approval (rc {rc})")
    rc, out = sp("next", str(sdir), "--claim")
    check(started(out) == ["s10-retarget"], f"s10 starts (got {started(out)})")
    run_step(project, sdir, "s10-retarget", spent=30)
    rc, out = sp("mark", str(sdir), "s10-retarget", "done")
    check(rc == 3 and status_of(sdir, "s10-retarget") == "done", f"spent above the cap trips the breaker (rc {rc})")
    check(state(sdir)["halt"]["reason"] == "budget", "halt reason: budget")
    rc, out = sp("resume", str(sdir), "--by", PERSON, "--retry", "s10-retarget")
    check(rc == 3, f"a budget breaker is not cleared by resume (rc {rc})")
    set_cap(sdir, 70)
    check(approve(sdir) == 0, "a person approves a plan with a cap above the spend")
    check(state(sdir)["halt"] is None, "budget breaker cleared by the new approval")

    print("10. completion and next sprint")
    rc, out = sp("next", str(sdir), "--claim")
    check(rc == 6 and "COMPLETE" in out, f"sprint complete (rc {rc})")
    summary = sdir / "summary.md"
    write(summary, "Fictional summary written by the orchestrator in the selftest.\n")
    rc, out = sp("report", str(sdir), "--summary", str(summary), "--log")
    reports = list(sdir.glob("sprint-report-*.md"))
    check(rc == 0 and reports, f"report written (rc {rc}): {out}")
    rep = reports[0].read_text(encoding="utf-8") if reports else ""
    check(f"growth-pulse/experiments-{TODAY}.json" in rep, "report points to the experiments for the next sprint")
    check("direction: editorial-paper" in rep, "report lists the defaults decided without the founder")
    check("plates-gate-1-and-2" not in rep or "spend" in rep, "report lists the human decisions")
    for line in rep.splitlines():
        check(chr(0x2014) not in line and chr(0x2013) not in line, "no long dash in the report")
    mem = project / "project-context/memory/runs.jsonl"
    last = json.loads(mem.read_text(encoding="utf-8").strip().splitlines()[-1])
    check(last["agent"] == "growth-sprint" and last["status"] == "ok", f"sprint run line logged ok ({last.get('status')})")
    check(not L.schema_errors(last, L.RUN_RECORD_SCHEMA), "run line valid against shared/schemas/run-record.schema.json")
    st = state(sdir)
    check(not L.schema_errors(st, L.STATE_SCHEMA), "state.json valid against its schema")
    check(all(h["resolved"] is None or L.is_person(h["resolved"]["by"]) for h in st["needs_human"]),
          "every needs_human item was resolved by a person")
    check(all(a["by"] == PERSON for a in st["approvals"]) and len(st["approvals"]) == 3, "three approvals, all by a person")
    rc, out = sp("status", str(sdir), "--json")
    check(rc == 0 and json.loads(out)["status"] == "complete", "status --json")
    nxt = project / "growth-sprint/next-sprint"
    nxt.mkdir()
    p = {"schema_version": "1.0", "sprint_id": "next-sprint", "project": "swanbase", "created": DAY,
         "goal": {"text": "Demo call link in the carousel first comment", "metric": "demo calls booked",
                  "source": f"growth-pulse/experiments-{TODAY}.json#E-{TODAY}-1"},
         "budget": {"cap_eur": 0, "basis": "no spend in this experiment"},
         "steps": [{"id": "s01-publish", "agent": "content-publisher", "label": "next-week",
                    "brief": "Queue the next carousel with the booking link.", "inputs": {"deliverables": "carousel"},
                    "depends_on": [], "spends": False, "publishes": True, "estimate_eur": 0}]}
    L.write_json_atomic(nxt / "sprint.json", p)
    rc, out = sp("validate", str(nxt))
    check(rc == 0, f"a growth-pulse experiment seeds the next sprint (rc {rc}): {out}")
    p["goal"]["source"] = f"growth-pulse/experiments-{TODAY}.json#E-{TODAY}-9"
    L.write_json_atomic(nxt / "sprint.json", p)
    rc, out = sp("validate", str(nxt))
    check(rc == 1 and "not in" in out, f"an unknown experiment id is refused (rc {rc})")


def t_check_step(project: Path) -> None:
    print("11. check_step standalone and --help")
    since = L.iso(L.now_dt())
    later = L.iso(L.now_dt() + timedelta(seconds=60))  # past the 2 s tolerance, whatever the earlier steps wrote a second ago
    rc, out = run("check_step.py", "--project", str(project), "--agent", "market-signal", "--since", later)
    check(rc == 1 and "stale" in out, f"an output older than --since is stale (rc {rc})")
    fake_outputs(project, "market-signal", "")
    rc, out = run("check_step.py", "--project", str(project), "--agent", "market-signal", "--since", since)
    check(rc == 0, f"fresh valid sidecar passes (rc {rc}): {out[-200:]}")
    side = project / f"market-signal/market-signal-{TODAY}.json"
    data = L.load_json(side)
    data.pop("quotes", None)
    L.write_json_atomic(side, data)
    rc, out = run("check_step.py", "--project", str(project), "--agent", "market-signal")
    check(rc == 1 and "schema error" in out, f"a sidecar that breaks its schema fails (rc {rc})")
    csv_path = project / f"first-users-hunter/prospects-{TODAY}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([["prospect_id", "first_name"], ["p001", "Jordan"]])
    rc, out = run("check_step.py", "--project", str(project), "--agent", "first-users-hunter", "--json")
    check(rc == 1 and "missing columns" in out, f"a prospect CSV without its columns fails (rc {rc})")
    old = time.time() - 3600
    os.utime(project / f"growth-pulse/experiments-{TODAY}.json", (old, old))
    rc, out = run("check_step.py", "--project", str(project), "--agent", "growth-pulse", "--since", since)
    check(rc == 1 and "stale" in out, f"an experiments file from before the step is stale (rc {rc})")
    for script in ("sprint.py", "check_step.py", "selftest.py"):
        rc, out = run(script, "--help")
        check(rc == 0 and "usage" in out.lower(), f"{script} --help")
    rc, out = sp("next", str(project / "nowhere"))
    check(rc == 2, f"missing sprint folder exits 2 (rc {rc})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline regression test of growth-sprint (fake agents, fictional swanbase project).")
    ap.add_argument("--keep", help="work in this folder and keep it")
    args = ap.parse_args()
    work = Path(args.keep).resolve() if args.keep else Path(tempfile.mkdtemp(prefix="growth-sprint-"))
    if args.keep and work.exists():
        shutil.rmtree(work)
    project = work / "swanbase"
    shutil.copytree(FIX / "swanbase", project)
    os.environ[L.APPROVAL_KEY_ENV] = str(work / "keys" / "approval.key")  # throwaway key, outside the project
    t0 = time.time()
    try:
        t_registry()
        sdir = t_plan(project)
        t_approval(sdir)
        t_run(project, sdir)
        t_check_step(project)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
    print(f"\n{PASSES} checks passed, {len(FAILS)} failed ({time.time() - t0:.1f} s)")
    if FAILS:
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("growth-sprint selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
