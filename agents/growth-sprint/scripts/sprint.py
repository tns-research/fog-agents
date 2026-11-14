#!/usr/bin/env python3
"""sprint.py: the growth-sprint state machine.

The model writes sprint.json (one goal, a budget cap, a graph of agent steps);
this script validates it, writes the approval packet, records the one human
approval (typed by a person at an interactive terminal, sealed with an HMAC
under a local key kept outside the project), hands out the next runnable steps, settles each step from the disk
(never from what the model says), keeps the needs_human queue, trips the
circuit breaker, resumes after an interruption and writes the sprint report.

Usage (from the repo root; <dir> is <project>/growth-sprint/<sprint id>/):
    python3 agents/growth-sprint/scripts/sprint.py validate <dir>
    python3 agents/growth-sprint/scripts/sprint.py packet <dir>
    python3 agents/growth-sprint/scripts/sprint.py approve <dir> --by <person>   (interactive terminal only)
    python3 agents/growth-sprint/scripts/sprint.py next <dir> [--claim] [--max N] [--json]
    python3 agents/growth-sprint/scripts/sprint.py mark <dir> <step> running|done|failed|needs_human|skipped [options]
    python3 agents/growth-sprint/scripts/sprint.py resolve <dir> <H-id> --by <person> [--then rerun|done|skip] [--set k=v]
    python3 agents/growth-sprint/scripts/sprint.py status <dir> [--json]
    python3 agents/growth-sprint/scripts/sprint.py resume <dir> [--by <person> --retry STEP | --skip STEP]
    python3 agents/growth-sprint/scripts/sprint.py report <dir> [--summary FILE] [--log]

Files in <dir>: sprint.json (the plan, written by the model), state.json
(written only by this script), approval.md, briefs/<step>.md,
results/<step>.json (written by whoever ran the step), STOP (optional: any
content; also honoured at <project>/growth-sprint/STOP), sprint-report-<YYYYMMDD>.md.

Exit codes: 0 ok (next: steps returned), 1 refused or check failed,
2 usage error or unreadable file, 3 halted (STOP file or circuit breaker),
4 not approved (no approval, plan changed since, approval refused or not
recorded by approve),
5 waiting for a person (needs_human) or for running steps, 6 sprint complete.
"""

from __future__ import annotations

import argparse
import hmac
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprint_lib as L  # noqa: E402

DEFAULT_MAX_WAVE = 3
DEFAULT_ALERT = 0.8
MAX_FAILURES = 2  # consecutive failures of one step that trip the breaker


# ---------------------------------------------------------------- loading


class Ctx:
    def __init__(self, sprint_dir: Path, project: Optional[str], registry: Optional[str], now: Optional[str]) -> None:
        self.dir = sprint_dir.resolve()
        if not (self.dir / "sprint.json").is_file():
            raise FileNotFoundError(f"{self.dir / 'sprint.json'} not found")
        if project:
            self.project = Path(project).resolve()
        elif self.dir.parent.name == "growth-sprint":
            self.project = self.dir.parent.parent
        else:
            raise L.Refused(f"{self.dir} is not under <project>/growth-sprint/: pass --project")
        self.registry = L.load_registry(Path(registry) if registry else None)
        self.now = L.now_dt(now)
        self.plan_path = self.dir / "sprint.json"
        self.state_path = self.dir / "state.json"
        self.plan = L.load_json(self.plan_path)
        self.plan_hash = L.canonical_hash(self.plan)
        self.state: Optional[Dict[str, Any]] = L.load_json(self.state_path) if self.state_path.is_file() else None

    @property
    def fingerprint(self) -> str:
        """Public short form of the plan hash: printed in the packet and the logs."""
        return self.plan_hash[:12]

    @property
    def code(self) -> str:
        """Secret plan code (HMAC under the approval key): printed only by approve."""
        return L.plan_code(self.plan["sprint_id"], self.plan_hash)

    def steps(self) -> List[Dict[str, Any]]:
        return list(self.plan.get("steps", []))

    def step(self, sid: str) -> Dict[str, Any]:
        for s in self.steps():
            if s["id"] == sid:
                return s
        raise L.Refused(f"unknown step {sid}")

    def save(self) -> None:
        errs = L.schema_errors(self.state, L.STATE_SCHEMA)
        if errs:
            raise L.Refused("internal: state would be invalid: " + "; ".join(errs[:3]))
        L.write_json_atomic(self.state_path, self.state)

    def event(self, action: str, **kw: Any) -> None:
        ev = {"at": L.iso(self.now), "action": action}
        ev.update({k: str(v) for k, v in kw.items() if v is not None})
        self.state["events"].append(ev)


# ---------------------------------------------------------------- plan checks


def _cycle(steps: List[Dict[str, Any]]) -> Optional[List[str]]:
    deps = {s["id"]: list(s.get("depends_on", [])) for s in steps}
    color: Dict[str, int] = {}
    stack: List[str] = []

    def visit(n: str) -> Optional[List[str]]:
        color[n] = 1
        stack.append(n)
        for d in deps.get(n, []):
            if d not in deps:
                continue
            if color.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if color.get(d) is None:
                found = visit(d)
                if found:
                    return found
        stack.pop()
        color[n] = 2
        return None

    for n in deps:
        if color.get(n) is None:
            found = visit(n)
            if found:
                return found
    return None


def validate_plan(ctx: Ctx) -> Tuple[List[str], List[str]]:
    plan, reg = ctx.plan, ctx.registry["agents"]
    errors = [f"schema {e}" for e in L.schema_errors(plan, L.SPRINT_SCHEMA)]
    warnings: List[str] = []
    if errors:
        return errors, warnings
    if plan["project"] != ctx.project.name:
        warnings.append(f"project '{plan['project']}' differs from the folder name '{ctx.project.name}'")
    if plan["sprint_id"] != ctx.dir.name:
        warnings.append(f"sprint_id '{plan['sprint_id']}' differs from the folder name '{ctx.dir.name}'")
    ids = [s["id"] for s in plan["steps"]]
    for sid in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate step id {sid}")
    seen_runs: Dict[Tuple[str, str], str] = {}
    total = 0.0
    for s in plan["steps"]:
        sid, name = s["id"], s["agent"]
        a = reg.get(name)
        if a is None:
            errors.append(f"{sid}: unknown agent '{name}' (registry: {', '.join(sorted(reg))})")
            continue
        for d in s["depends_on"]:
            if d == sid:
                errors.append(f"{sid}: depends on itself")
            elif d not in ids:
                errors.append(f"{sid}: depends on unknown step {d}")
        if a["spends"] and not s["spends"]:
            errors.append(f"{sid}: {name} can spend money, set spends: true so the founder sees it before approving")
        if a["publishes"] and not s["publishes"]:
            errors.append(f"{sid}: {name} can publish, set publishes: true so the founder sees it before approving")
        if s["spends"] and not s.get("estimate_basis"):
            errors.append(f"{sid}: spends: true needs estimate_basis (where the figure comes from)")
        if not s["spends"] and s["estimate_eur"] > 0:
            errors.append(f"{sid}: estimate_eur {s['estimate_eur']} on a step that does not spend")
        total += s["estimate_eur"]
        labelled = any(L.LABEL_TOKEN in o["path"] for o in a["outputs"])
        if labelled and not s.get("label"):
            warnings.append(f"{sid}: no label, any {name} run folder written during the step will match")
        key = (name, s.get("label") or "")
        if key in seen_runs:
            errors.append(f"{sid}: same agent and label as {seen_runs[key]}, their outputs would collide (give each a label)")
        seen_runs[key] = sid
        miss = L.missing_inputs(ctx.project, a, s)
        if miss:
            warnings.append(f"{sid}: required input(s) {', '.join(miss)} not given and not in the project: the step will wait in needs_human")
    cyc = _cycle(plan["steps"])
    if cyc:
        errors.append("dependency cycle: " + " -> ".join(cyc))
    cap = plan["budget"]["cap_eur"]
    if total > cap + 1e-9:
        errors.append(f"step estimates total {total:.2f} EUR, above the cap {cap:.2f} EUR")
    src = plan["goal"]["source"]
    if src != "founder":
        rel, _, exp_id = src.partition("#")
        path = ctx.project / rel
        if not path.is_file():
            errors.append(f"goal.source: {rel} not found in the project")
        else:
            try:
                exps = L.load_json(path).get("experiments", [])
            except (ValueError, OSError) as e:
                exps = []
                errors.append(f"goal.source: {rel} unreadable: {e}")
            exp = next((e for e in exps if e.get("id") == exp_id), None)
            if exps and exp is None:
                errors.append(f"goal.source: experiment {exp_id} not in {rel}")
            cash = float(((exp or {}).get("cost") or {}).get("cash_eur") or 0)
            if cash > cap + 1e-9:
                warnings.append(f"goal.source: experiment {exp_id} costs {cash:.2f} EUR, above the cap {cap:.2f} EUR")
    for rel in plan.get("context_read", []):
        if not (ctx.project / rel).exists():
            warnings.append(f"context_read: {rel} not found in the project")
    return errors, warnings


# ---------------------------------------------------------------- state


def new_step_state() -> Dict[str, Any]:
    return {"status": "pending", "attempts": 0, "consecutive_failures": 0, "started_at": None,
            "last_started_at": None, "finished_at": None, "spent_eur": 0, "outputs": [], "notes": []}


def sync_state(ctx: Ctx) -> None:
    if ctx.state is None:
        ctx.state = {
            "schema_version": "1.0", "sprint_id": ctx.plan["sprint_id"], "plan_hash": ctx.plan_hash,
            "status": "draft", "approval": None, "approvals": [], "halt": None,
            "budget": {"cap_eur": ctx.plan["budget"]["cap_eur"], "spent_eur": 0, "alerted": False},
            "steps": {}, "needs_human": [], "events": [],
        }
        ctx.event("created")
    st = ctx.state
    ids = [s["id"] for s in ctx.steps()]
    for sid in ids:
        st["steps"].setdefault(sid, new_step_state())
    for sid in list(st["steps"]):
        if sid not in ids:
            if st["steps"][sid]["status"] == "pending":
                del st["steps"][sid]
                ctx.event("step_removed", step=sid)
    if st["plan_hash"] != ctx.plan_hash:
        ctx.event("plan_changed", note=f"{st['plan_hash'][:12]} -> {ctx.fingerprint}")
        st["plan_hash"] = ctx.plan_hash
    st["budget"]["spent_eur"] = round(sum(x["spent_eur"] for x in st["steps"].values()), 2)


def approved_cap(ctx: Ctx) -> float:
    ap = ctx.state.get("approval") if ctx.state else None
    return float(ap["cap_eur"]) if ap and L.seal_ok(ctx.plan["sprint_id"], ap) else 0.0


def approval_problem(ctx: Ctx) -> Optional[str]:
    ap = ctx.state.get("approval") if ctx.state else None
    if not ap:
        return "not approved: run `sprint.py packet`, then a person runs `sprint.py approve` in their own terminal"
    if not L.seal_ok(ctx.plan["sprint_id"], ap):
        return ("the approval in state.json was not recorded by `sprint.py approve` with this machine's approval key "
                "(state.json edited by hand, or the key changed): a person runs `sprint.py approve` again in their own terminal")
    if ap["plan_hash"] != ctx.plan_hash:
        return (f"sprint.json changed since the approval of {ap['at']} (plan {ap['plan_hash'][:12]}, now {ctx.fingerprint}): "
                "run `sprint.py packet` and have it approved again")
    return None


def require_approval(ctx: Ctx) -> None:
    why = approval_problem(ctx)
    if why:
        raise L.GateRefused(why)


def stop_files(ctx: Ctx) -> List[Path]:
    return [p for p in (ctx.dir / "STOP", ctx.project / "growth-sprint" / "STOP") if p.exists()]


def halt_reason(ctx: Ctx) -> Optional[str]:
    stops = stop_files(ctx)
    if stops:
        return f"STOP file present ({stops[0]}): remove it to continue"
    h = ctx.state.get("halt")
    if h:
        return f"circuit breaker ({h['reason']}): {h['detail']}"
    return None


def set_status(ctx: Ctx, sid: str, to: str, note: Optional[str] = None, by: Optional[str] = None) -> None:
    ss = ctx.state["steps"][sid]
    frm = ss["status"]
    if to != frm and to not in L.TRANSITIONS[frm]:
        raise L.Refused(f"{sid}: transition {frm} -> {to} not allowed")
    ss["status"] = to
    if note:
        ss["notes"].append(note)
    if to in ("done", "skipped", "failed"):
        ss["finished_at"] = L.iso(ctx.now)
    ctx.event("status", step=sid, **{"from": frm, "to": to}, by=by, note=note)


def open_items(ctx: Ctx, sid: Optional[str] = None) -> List[Dict[str, Any]]:
    return [h for h in ctx.state["needs_human"] if h["resolved"] is None and (sid is None or h["step"] == sid)]


def open_human(ctx: Ctx, sid: str, kind: str, reason: str, how: str, gate: Optional[str] = None) -> Dict[str, Any]:
    for h in open_items(ctx, sid):
        if h["kind"] == kind and h.get("gate") == gate and h["reason"] == reason:
            return h
    hid = f"H-{len(ctx.state['needs_human']) + 1:02d}"
    how = how.replace("<H-id>", hid).replace("<dir>", str(ctx.dir)).replace("<project>", str(ctx.project))
    item = {"id": hid, "step": sid, "kind": kind,
            "reason": reason, "how": how, "opened_at": L.iso(ctx.now), "resolved": None}
    if gate:
        item["gate"] = gate
    ctx.state["needs_human"].append(item)
    ctx.event("needs_human", step=sid, note=f"{item['id']} {kind}: {reason}")
    return item


def add_spend(ctx: Ctx, sid: str, amount: float) -> None:
    if amount <= 0:
        return
    st = ctx.state
    st["steps"][sid]["spent_eur"] = round(st["steps"][sid]["spent_eur"] + amount, 2)
    st["budget"]["spent_eur"] = round(sum(x["spent_eur"] for x in st["steps"].values()), 2)
    ctx.event("spent", step=sid, note=f"{amount:.2f} EUR, total {st['budget']['spent_eur']:.2f}")
    if not ctx.step(sid)["spends"]:
        st["steps"][sid]["notes"].append(f"unplanned spend of {amount:.2f} EUR")
    cap = approved_cap(ctx)
    ratio = float(ctx.plan["budget"].get("alert_ratio", DEFAULT_ALERT))
    spent = st["budget"]["spent_eur"]
    if spent > cap + 1e-9:
        st["halt"] = {"reason": "budget", "at": L.iso(ctx.now), "step": sid,
                      "detail": f"spent {spent:.2f} EUR above the approved cap {cap:.2f} EUR"}
        st["status"] = "halted"
        ctx.event("halt", step=sid, note=st["halt"]["detail"])
    elif cap > 0 and spent >= ratio * cap and not st["budget"]["alerted"]:
        st["budget"]["alerted"] = True
        ctx.event("budget_alert", note=f"spent {spent:.2f} EUR, {spent / cap:.0%} of the cap {cap:.2f} EUR")


def record_failure(ctx: Ctx, sid: str, why: str) -> int:
    ss = ctx.state["steps"][sid]
    ss["consecutive_failures"] += 1
    if ss["consecutive_failures"] >= MAX_FAILURES:
        set_status(ctx, sid, "failed", note=f"failure {ss['consecutive_failures']}: {why}")
        ctx.state["halt"] = {"reason": "failures", "at": L.iso(ctx.now), "step": sid,
                             "detail": f"{sid} failed {ss['consecutive_failures']} times in a row: {why}"}
        ctx.state["status"] = "halted"
        ctx.event("halt", step=sid, note=ctx.state["halt"]["detail"])
        return L.EXIT_HALTED
    set_status(ctx, sid, "pending", note=f"failure {ss['consecutive_failures']}, will retry: {why}")
    return L.EXIT_FAIL


def ts_or_none(value: Optional[str]) -> Optional[datetime]:
    return L.parse_ts(value) if value else None


def verify(ctx: Ctx, sid: str, use_result: bool = True) -> Dict[str, Any]:
    ss = ctx.state["steps"][sid]
    return L.verify_step(ctx.project, ctx.registry, ctx.step(sid), ts_or_none(ss["started_at"]),
                         ctx.dir, ts_or_none(ss["last_started_at"]), use_result=use_result)


def settle(ctx: Ctx, sid: str, v: Dict[str, Any], spent: Optional[float]) -> int:
    """Apply a verification verdict to a running step."""
    ss = ctx.state["steps"][sid]
    add_spend(ctx, sid, spent if spent is not None else v["spent_eur"])
    for d in v.get("defaults_used", []):
        note = f"default: {d}"
        if note not in ss["notes"]:
            ss["notes"].append(note)
    if v["result_note"]:
        ss["notes"].append(v["result_note"])
    if v["verdict"] == "done":
        ss["outputs"] = [o["path"] for o in v["outputs"] if o["path"]]
        ss["consecutive_failures"] = 0
        set_status(ctx, sid, "done", note=v["why"])
        code = L.EXIT_OK
    elif v["verdict"] == "needs_human":
        ss["outputs"] = [o["path"] for o in v["outputs"] if o["path"] and o["ok"]]
        set_status(ctx, sid, "needs_human", note=v["why"])
        for p in v["pending"]:
            open_human(ctx, sid, p["kind"] if p["kind"] in ("spend", "publish", "input", "other") else "other",
                       p["reason"], p["how"], p.get("gate"))
        code = L.EXIT_NEEDS_HUMAN
    else:
        code = record_failure(ctx, sid, v["why"])
    if ctx.state.get("halt"):
        return L.EXIT_HALTED
    return code


def deps_state(ctx: Ctx, s: Dict[str, Any]) -> str:
    sts = [ctx.state["steps"][d]["status"] for d in s["depends_on"]]
    if all(x in L.TERMINAL for x in sts):
        return "ready"
    return "waiting"


def reuse_ok(ctx: Ctx, s: Dict[str, Any]) -> Optional[str]:
    days = s.get("reuse_if_fresh_days")
    if not days:
        return None
    a = ctx.registry["agents"][s["agent"]]
    newest = None
    for o in a["outputs"]:
        r = L.check_output(ctx.project, o, s.get("label"), None)
        if not r["ok"]:
            return None
        if r["path"]:
            mt = datetime.fromtimestamp((ctx.project / r["path"]).stat().st_mtime).astimezone()
            newest = mt if newest is None or mt > newest else newest
    if newest is None:
        return None
    age = (ctx.now - newest).total_seconds() / 86400
    if age > days:
        return None
    return f"reused existing outputs ({age:.0f} days old, limit {days})"


def is_complete(ctx: Ctx) -> bool:
    return all(x["status"] in L.TERMINAL for x in ctx.state["steps"].values())


def write_brief(ctx: Ctx, s: Dict[str, Any]) -> Path:
    a = ctx.registry["agents"][s["agent"]]
    ss = ctx.state["steps"][s["id"]]
    inputs = dict(s.get("inputs") or {})
    inputs.update(ss.get("inputs_extra") or {})
    lines = [
        f"# Step {s['id']}: {s['agent']}",
        "",
        f"- Sprint: `{ctx.plan['sprint_id']}`, goal: {ctx.plan['goal']['text']}",
        f"- Project folder: `{ctx.project}`",
        f"- Agent workflow: `{a['spec']}` in the fog-agents repo. Read it from start to finish.",
        f"- Label: `{s.get('label') or 'none'}`. Attempt {ss['attempts']}, started {ss['last_started_at']}.",
        "",
        "## What this step must produce",
        "",
        s["brief"],
        "",
        "## Inputs",
        "",
    ]
    lines += [f"- `{k}`: {json.dumps(v, ensure_ascii=False)}" for k, v in inputs.items()] or ["- none beyond the agent's Step 0 defaults"]
    cleared = [h for h in ctx.state["needs_human"] if h["step"] == s["id"] and h["resolved"]]
    if cleared:
        lines += ["", "## Rerun after a person decided", ""]
        lines += [f"- `{h['id']}` ({h['kind']}): {h['reason']}. Cleared by {h['resolved']['by']}, then {h['resolved']['then']}"
                  + (f": {h['resolved']['note']}" if h['resolved'].get('note') else "") for h in cleared]
        lines.append("- Continue from where the agent stopped; do not redo finished work.")
    lines += ["", "## Rules", "",
              "- Run the agent in its Autonomous mode: no question to the founder; use the documented default for every missing input and list it in `defaults_used` below.",
              "- Stop at any step that spends money or publishes: write everything up to the gate, end the run `partial`, and list the gate in `pending`. Never confirm a spend, never approve a publication, never run an approval command for anyone.",
              (f"- Budget for this step: {s['estimate_eur']:.2f} EUR ({s.get('estimate_basis')}). Above it, or at any gate of the agent, stop and list a `spend` item in `pending`."
               if s["spends"] else "- This step is not approved to spend: any paid call goes to `pending` as a `spend` item instead of running."),
              "- End with the agent's own run line in `project-context/memory/runs.jsonl` (keeping-project-memory), failures included.",
              "", "## Expected outputs (checked on disk, written after the step started)", ""]
    for o in a["outputs"]:
        extra = f" against `{o['schema']}`" if o.get("schema") else ""
        opt = " (optional)" if not o.get("required", True) else ""
        lines.append(f"- `{o['path'].replace(L.LABEL_TOKEN, s.get('label') or L.LABEL_TOKEN)}`: {o['check']}{extra}{opt}")
    lines += ["", "## Last act: the step result file", "",
              f"Write `{ctx.dir / 'results' / (s['id'] + '.json')}` (contract: `agents/growth-sprint/assets/step-result.schema.json`):", "",
              "```json",
              json.dumps({"step": s["id"], "status": "ok", "spent_eur": 0, "pending": [],
                          "defaults_used": ["<input or choice>: <default used>"], "notes": ""}, indent=2),
              "```", "",
              "It can only send the step to a person or record a spend. The step is done when this command exits 0:", "",
              "```bash",
              f"python3 agents/growth-sprint/scripts/check_step.py --sprint {ctx.dir} --step {s['id']}",
              "```", ""]
    path = ctx.dir / "briefs" / f"{s['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def start_step(ctx: Ctx, sid: str) -> None:
    ss = ctx.state["steps"][sid]
    set_status(ctx, sid, "running")
    ss["attempts"] += 1
    ss["last_started_at"] = L.iso(ctx.now)
    if ss["started_at"] is None:
        ss["started_at"] = ss["last_started_at"]
    ctx.state["status"] = "running"


# ---------------------------------------------------------------- commands


def cmd_validate(ctx: Ctx, args: argparse.Namespace) -> int:
    errors, warnings = validate_plan(ctx)
    for e in errors:
        print(f"ERROR {e}")
    for w in warnings:
        print(f"WARN  {w}")
    if errors:
        print(f"sprint.json: {len(errors)} error(s)")
        return L.EXIT_FAIL
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        ctx.save()
    print(f"sprint.json valid: {len(ctx.steps())} steps, plan {ctx.fingerprint}")
    return L.EXIT_OK


def cmd_packet(ctx: Ctx, args: argparse.Namespace) -> int:
    errors, warnings = validate_plan(ctx)
    if errors:
        for e in errors:
            print(f"ERROR {e}")
        return L.EXIT_FAIL
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        ctx.save()
    p, reg = ctx.plan, ctx.registry["agents"]
    g = p["goal"]
    total = sum(s["estimate_eur"] for s in p["steps"])
    out = [f"# Sprint approval: {p['sprint_id']}", "",
           f"- Project: `{p['project']}`",
           f"- Goal: {g['text']}",
           f"- Measured by: {g['metric']}" + (f", target {g['target']}" if g.get("target") is not None else "") + (f", by {g['deadline']}" if g.get("deadline") else ""),
           f"- Goal source: `{g['source']}`",
           f"- Plan fingerprint: `{ctx.fingerprint}` (start of the sha256 of sprint.json; any edit changes it and voids the approval)", "",
           "## Steps", "",
           "| Step | Agent | After | Spends | Publishes | Estimate (EUR) | Basis |",
           "|------|-------|-------|--------|-----------|----------------|-------|"]
    for s in p["steps"]:
        out.append(f"| `{s['id']}` | {s['agent']} | {', '.join(s['depends_on']) or 'start'} | {'yes' if s['spends'] else 'no'} | "
                   f"{'yes' if s['publishes'] else 'no'} | {s['estimate_eur']:.2f} | {s.get('estimate_basis') or 'no spend'} |")
    ratio = float(p["budget"].get("alert_ratio", DEFAULT_ALERT))
    out += ["", "## Budget", "",
            f"- Cap: {p['budget']['cap_eur']:.2f} EUR ({p['budget']['basis']}). Step estimates total {total:.2f} EUR.",
            f"- Alert at {ratio:.0%} of the cap. Spent above the cap stops the sprint (circuit breaker) until you approve a new plan.",
            "- A spending step whose estimate no longer fits in what is left waits for you in needs_human; the other steps go on.", "",
            "## What this approval lets the sprint do without asking you again", ""]
    spend = [s for s in p["steps"] if s["spends"]]
    pub = [s for s in p["steps"] if s["publishes"]]
    out.append("- Run every step above in order, in parallel where the graph allows, and retry a failed step once.")
    out.append("- Steps that may spend, each up to its estimate: " + (", ".join(f"`{s['id']}` ({s['estimate_eur']:.2f} EUR)" for s in spend) or "none") + ".")
    out.append("- Steps that prepare a publication: " + (", ".join(f"`{s['id']}`" for s in pub) or "none") + ".")
    out += ["", "## What stays with you (never cleared by the sprint)", ""]
    gates = []
    for s in p["steps"]:
        for gt in reg.get(s["agent"], {}).get("human_gates", []):
            gates.append(f"- `{s['id']}` {s['agent']}, {gt['kind']} gate `{gt['id']}`: {gt['how']}")
    out += gates or ["- No agent gate in this plan."]
    out += ["- Any input nobody can supply, any spend beyond the cap, any step failing twice in a row.",
            "- These land in the needs_human queue (`sprint.py status`); the steps that do not depend on them keep running.", ""]
    if warnings:
        out += ["## Warnings", ""] + [f"- {w}" for w in warnings] + [""]
    out += ["## Approve", "",
            "Read the plan, then run this yourself, in your own terminal (the sprint never runs it for you). "
            "It shows the plan fingerprint, the cap and the steps that spend or publish, prints a plan code "
            "and asks you to type it:", "",
            "```bash",
            f"python3 agents/growth-sprint/scripts/sprint.py approve {ctx.dir} --by <your-name>",
            "```", "",
            "To change the plan, edit sprint.json, run `sprint.py packet` again and approve the new version.", ""]
    (ctx.dir / "approval.md").write_text("\n".join(out), encoding="utf-8")
    print(f"approval packet: {ctx.dir / 'approval.md'} (plan {ctx.fingerprint})")
    return L.EXIT_OK


def cmd_approve(ctx: Ctx, args: argparse.Namespace) -> int:
    """The one human approval. Runs only at an interactive terminal (stdin and
    stdout are TTYs): it shows the plan, prints the plan code (an HMAC under
    the local approval key, printed by no other command) and asks the person
    to type it. The record it writes is sealed, so an approval typed into
    state.json is refused by next. An agent with an unrestricted shell under
    the same user can still drive a terminal or read the key: see the README."""
    errors, _ = validate_plan(ctx)
    if errors:
        for e in errors:
            print(f"ERROR {e}")
        return L.EXIT_FAIL
    if not L.is_person(args.by, ctx.registry):
        raise L.GateRefused(f"--by must be a person's name, not {args.by!r}")
    approvers = args.approvers
    cfg = ctx.project / "growth-sprint" / "config.json"
    if approvers is None and cfg.is_file():
        try:
            approvers = L.load_json(cfg).get("approvers") or []
        except (ValueError, OSError):
            approvers = []
    approvers = [a.strip().lower() for a in (approvers or [])]
    if approvers and args.by.strip().lower() not in approvers:
        raise L.GateRefused(f"{args.by!r} is not in the approvers list")
    packet = ctx.dir / "approval.md"
    if not packet.is_file() or ctx.fingerprint not in packet.read_text(encoding="utf-8"):
        raise L.GateRefused("no approval packet for this version of sprint.json: run `sprint.py packet` and read it first")
    if args.code:
        raise L.GateRefused("the plan code is not accepted as an argument: run approve yourself in an interactive "
                            "terminal; it prints the code and asks you to type it")
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise L.GateRefused("approve needs a person at an interactive terminal (stdin and stdout must be a TTY): "
                            "the founder runs it in their own terminal, an agent never runs it")
    p = ctx.plan
    spend = [s for s in ctx.steps() if s["spends"]]
    pub = [s for s in ctx.steps() if s["publishes"]]
    print(f"Sprint {p['sprint_id']}: {p['goal']['text']}")
    print(f"Plan fingerprint {ctx.fingerprint} (the one in {packet})")
    print(f"Budget cap {float(p['budget']['cap_eur']):.2f} EUR, {len(ctx.steps())} steps")
    print("Steps that may spend: " + (", ".join(f"{s['id']} ({s['estimate_eur']:.2f} EUR)" for s in spend) or "none"))
    print("Steps that prepare a publication: " + (", ".join(s["id"] for s in pub) or "none"))
    print(f"Plan code: {ctx.code}")
    try:
        typed = input("Type the plan code to approve this plan (Enter cancels): ").strip().lower()
    except EOFError:
        raise L.GateRefused("no answer at the terminal")
    if not typed:
        print("cancelled: nothing approved")
        return L.EXIT_NOT_APPROVED
    if not hmac.compare_digest(typed.encode("utf-8"), ctx.code.encode("utf-8")):
        raise L.GateRefused("wrong plan code: nothing approved")
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        st = ctx.state
        ap = {"by": args.by.strip(), "at": L.iso(ctx.now), "plan_hash": ctx.plan_hash,
              "cap_eur": float(ctx.plan["budget"]["cap_eur"]),
              "spend_steps": [s["id"] for s in ctx.steps() if s["spends"]],
              "publish_steps": [s["id"] for s in ctx.steps() if s["publishes"]]}
        if args.note:
            ap["note"] = args.note
        ap["mac"] = L.approval_seal(ctx.plan["sprint_id"], ap)
        st["approval"] = ap
        st["approvals"].append(dict(ap))
        st["budget"]["cap_eur"] = ap["cap_eur"]
        ctx.event("approved", by=ap["by"], note=f"plan {ctx.fingerprint}, cap {ap['cap_eur']:.2f} EUR")
        h = st.get("halt")
        if h and h["reason"] == "budget" and st["budget"]["spent_eur"] <= ap["cap_eur"] + 1e-9:
            st["halt"] = None
            ctx.event("halt_cleared", by=ap["by"], note="new cap approved")
        if not st.get("halt"):
            st["status"] = "running" if any(x["status"] != "pending" for x in st["steps"].values()) else "approved"
        ctx.save()
    print(f"approved by {args.by} (plan {ctx.fingerprint}, cap {ctx.plan['budget']['cap_eur']:.2f} EUR)")
    return L.EXIT_OK


def plan_wave(ctx: Ctx, max_n: int) -> List[Dict[str, Any]]:
    """Apply automatic decisions (reuse, missing input, budget) and pick a wave."""
    st = ctx.state
    reg = ctx.registry["agents"]
    running = [s for s in ctx.steps() if st["steps"][s["id"]]["status"] == "running"]
    busy_agents = {s["agent"] for s in running}
    exclusive_running = any(not reg[s["agent"]]["parallel_safe"] for s in running)
    ready = []
    for s in ctx.steps():
        sid = s["id"]
        if st["steps"][sid]["status"] != "pending" or deps_state(ctx, s) != "ready":
            continue
        reuse = reuse_ok(ctx, s)
        if reuse:
            set_status(ctx, sid, "skipped", note=reuse)
            continue
        miss = L.missing_inputs(ctx.project, reg[s["agent"]], s, st["steps"][sid].get("inputs_extra"))
        if miss:
            set_status(ctx, sid, "needs_human", note=f"missing input: {', '.join(miss)}")
            open_human(ctx, sid, "input", f"required input(s) {', '.join(miss)}: not in the plan nor in the project",
                       f"Give the value: python3 agents/growth-sprint/scripts/sprint.py resolve <dir> <H-id> --by <your-name> --set {miss[0]}=<value> (or --then skip).")
            continue
        if s["spends"] and s["estimate_eur"] > 0:
            left = approved_cap(ctx) - st["budget"]["spent_eur"]
            if s["estimate_eur"] > left + 1e-9:
                set_status(ctx, sid, "needs_human", note="estimate above the budget left")
                open_human(ctx, sid, "budget", f"estimate {s['estimate_eur']:.2f} EUR, budget left {left:.2f} EUR",
                           "Raise budget.cap_eur in sprint.json, run sprint.py packet and approve the new code, then resolve; or resolve with --then skip.")
                continue
        ready.append(s)
    if exclusive_running:
        return []
    slots = max(0, max_n - len(running))
    wave: List[Dict[str, Any]] = []
    for s in ready:
        if len(wave) >= slots:
            break
        if s["agent"] in busy_agents or any(w["agent"] == s["agent"] for w in wave):
            continue
        if not reg[s["agent"]]["parallel_safe"]:
            if not wave and not running:
                wave.append(s)
                break
            continue
        wave.append(s)
    return wave


def cmd_next(ctx: Ctx, args: argparse.Namespace) -> int:
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        require_approval(ctx)
        why = halt_reason(ctx)
        if why:
            ctx.save()
            print(f"HALTED {why}")
            return L.EXIT_HALTED
        max_n = min(args.max or ctx.plan.get("max_wave", DEFAULT_MAX_WAVE), DEFAULT_MAX_WAVE)
        wave = plan_wave(ctx, max_n)
        briefs = {}
        if args.claim:
            for s in wave:
                start_step(ctx, s["id"])
                briefs[s["id"]] = str(write_brief(ctx, s))
        st = ctx.state
        if not wave:
            if is_complete(ctx):
                st["status"] = "complete"
            ctx.save()
            if st["status"] == "complete":
                print("COMPLETE every step is done or skipped: run `sprint.py report`")
                return L.EXIT_COMPLETE
            running = [sid for sid, x in st["steps"].items() if x["status"] == "running"]
            waiting = open_items(ctx)
            print(f"WAITING running: {', '.join(running) or 'none'}; needs_human open: {', '.join(h['id'] + ' (' + h['step'] + ')' for h in waiting) or 'none'}")
            return L.EXIT_NEEDS_HUMAN
        ctx.save()
    if args.json:
        print(json.dumps([{"step": s["id"], "agent": s["agent"], "label": s.get("label"),
                           "brief": briefs.get(s["id"]), "spec": ctx.registry["agents"][s["agent"]]["spec"]} for s in wave], indent=2))
    else:
        verb = "STARTED" if args.claim else "READY"
        for s in wave:
            extra = f" brief {briefs[s['id']]}" if s["id"] in briefs else ""
            print(f"{verb} {s['id']} {s['agent']}{extra}")
    return L.EXIT_OK


def cmd_mark(ctx: Ctx, args: argparse.Namespace) -> int:
    sid, to = args.step, args.status
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        ctx.step(sid)
        require_approval(ctx)
        ss = ctx.state["steps"][sid]
        code = L.EXIT_OK
        if to == "running":
            why = halt_reason(ctx)
            if why:
                print(f"HALTED {why}")
                return L.EXIT_HALTED
            if ss["status"] != "pending" or deps_state(ctx, ctx.step(sid)) != "ready":
                raise L.Refused(f"{sid} is {ss['status']} or waits on a dependency: use `sprint.py next --claim`")
            start_step(ctx, sid)
            write_brief(ctx, ctx.step(sid))
        elif to == "done":
            if ss["status"] != "running":
                raise L.Refused(f"{sid} is {ss['status']}, not running")
            v = verify(ctx, sid)
            code = settle(ctx, sid, v, args.spent)
            print(f"{sid}: {v['verdict']} ({v['why']})")
        elif to == "failed":
            if ss["status"] != "running":
                raise L.Refused(f"{sid} is {ss['status']}, not running")
            if args.spent:
                add_spend(ctx, sid, args.spent)
            code = record_failure(ctx, sid, args.note or "reported failed")
        elif to == "needs_human":
            if not args.reason:
                raise L.Refused("--reason is required")
            if args.spent:
                add_spend(ctx, sid, args.spent)
            set_status(ctx, sid, "needs_human", note=args.reason)
            item = open_human(ctx, sid, args.kind, args.reason, args.how or "Decide, then resolve the item.")
            print(f"{sid}: needs_human {item['id']}")
            code = L.EXIT_NEEDS_HUMAN
        elif to == "skipped":
            if not args.reason:
                raise L.Refused("--reason is required")
            waiting = open_items(ctx, sid)
            if waiting and not L.is_person(args.by, ctx.registry):
                raise L.GateRefused(f"{sid} has open needs_human items ({', '.join(h['id'] for h in waiting)}): "
                                    "only a person skips it, with --by <name> (or resolve the items with --then skip)")
            set_status(ctx, sid, "skipped", note=args.reason, by=args.by)
            for h in waiting:
                h["resolved"] = {"by": args.by.strip(), "at": L.iso(ctx.now), "then": "skip", "note": args.reason}
        if ctx.state.get("halt"):
            code = L.EXIT_HALTED
        if is_complete(ctx):
            ctx.state["status"] = "complete"
        ctx.save()
    return code


def cmd_resolve(ctx: Ctx, args: argparse.Namespace) -> int:
    if not L.is_person(args.by, ctx.registry):
        raise L.GateRefused(f"--by must be a person's name, not {args.by!r}")
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        require_approval(ctx)
        item = next((h for h in ctx.state["needs_human"] if h["id"] == args.item), None)
        if item is None:
            raise L.Refused(f"unknown item {args.item}")
        if item["resolved"] is not None:
            raise L.Refused(f"{args.item} already resolved by {item['resolved']['by']}")
        sid = item["step"]
        s = ctx.step(sid)
        ss = ctx.state["steps"][sid]
        then = args.then
        agent = ctx.registry["agents"][s["agent"]]
        if then != "skip":
            if item["kind"] == "publish" or item.get("gate"):
                gate = next((g for g in agent["human_gates"] if g["id"] == item.get("gate")), None)
                if gate is not None:
                    still = L.gate_pending(ctx.project, gate)
                    if still:
                        raise L.Refused(f"{args.item}: still waiting on disk ({still}). {gate['how']}")
            if item["kind"] == "budget":
                left = approved_cap(ctx) - ctx.state["budget"]["spent_eur"]
                if s["estimate_eur"] > left + 1e-9:
                    raise L.Refused(f"{args.item}: estimate {s['estimate_eur']:.2f} EUR still above the approved budget left "
                                    f"{left:.2f} EUR: approve a plan with a higher cap first, or --then skip")
            if item["kind"] == "input":
                extra = dict(ss.get("inputs_extra") or {})
                for kv in args.set or []:
                    k, _, val = kv.partition("=")
                    if not k or not val:
                        raise L.Refused(f"--set expects name=value, got {kv!r}")
                    extra[k.strip()] = val.strip()
                miss = L.missing_inputs(ctx.project, agent, s, extra)
                if miss:
                    raise L.Refused(f"{args.item}: still missing {', '.join(miss)}: pass --set {miss[0]}=<value>")
                ss["inputs_extra"] = extra
        item["resolved"] = {"by": args.by.strip(), "at": L.iso(ctx.now), "then": then}
        if args.note:
            item["resolved"]["note"] = args.note
        ctx.event("resolved", step=sid, by=args.by.strip(), note=f"{item['id']} then {then}")
        code = L.EXIT_OK
        if not open_items(ctx, sid) and ss["status"] == "needs_human":
            if then == "skip":
                set_status(ctx, sid, "skipped", note=f"skipped by {args.by.strip()}", by=args.by.strip())
            elif then == "done":
                v = verify(ctx, sid, use_result=False)
                if v["verdict"] != "done":
                    item["resolved"] = None
                    raise L.Refused(f"{sid}: cannot be done: {v['why']}")
                ss["outputs"] = [o["path"] for o in v["outputs"] if o["path"]]
                set_status(ctx, sid, "done", note=f"done after {args.by.strip()} cleared {item['id']}", by=args.by.strip())
            else:
                set_status(ctx, sid, "pending", note=f"rerun after {args.by.strip()} cleared {item['id']}", by=args.by.strip())
        elif open_items(ctx, sid):
            print(f"{sid}: other items still open: {', '.join(h['id'] for h in open_items(ctx, sid))}")
        if is_complete(ctx):
            ctx.state["status"] = "complete"
        ctx.save()
    print(f"{args.item} resolved by {args.by} ({then}); {sid} is {ctx.state['steps'][sid]['status']}")
    return code


def cmd_resume(ctx: Ctx, args: argparse.Namespace) -> int:
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        st = ctx.state
        for sid, ss in st["steps"].items():
            if ss["status"] != "running":
                continue
            v = verify(ctx, sid)
            if v["verdict"] in ("done", "needs_human"):
                settle(ctx, sid, v, None)
                print(f"{sid}: {v['verdict']} after the interruption ({v['why']})")
            else:
                set_status(ctx, sid, "pending", note=f"interrupted without verified outputs, restarted: {v['why']}")
                ctx.event("interrupted", step=sid)
                print(f"{sid}: back to pending (interrupted, not counted as a failure)")
        h = st.get("halt")
        if h and h["reason"] == "failures" and (args.retry or args.skip):
            if not L.is_person(args.by, ctx.registry):
                raise L.GateRefused(f"--by must be a person's name, not {args.by!r}")
            target = args.retry or args.skip
            if target != h.get("step"):
                raise L.Refused(f"the breaker tripped on {h.get('step')}, not {target}")
            ss = st["steps"][target]
            if args.retry:
                ss["consecutive_failures"] = 0
                set_status(ctx, target, "pending", note=f"retry allowed by {args.by.strip()}", by=args.by.strip())
            else:
                set_status(ctx, target, "skipped", note=f"skipped by {args.by.strip()} after repeated failures", by=args.by.strip())
            st["halt"] = None
            ctx.event("halt_cleared", step=target, by=args.by.strip())
        elif h and h["reason"] == "budget":
            print("budget breaker: raise budget.cap_eur in sprint.json, run `sprint.py packet`, and have the new code approved")
        if not st.get("halt") and st["status"] == "halted":
            st["status"] = "running"
        if is_complete(ctx):
            st["status"] = "complete"
        ctx.save()
        why = halt_reason(ctx)
    if why:
        print(f"HALTED {why}")
        return L.EXIT_HALTED
    print("resumed: run `sprint.py next --claim`")
    return L.EXIT_OK


def summary(ctx: Ctx) -> Dict[str, Any]:
    st = ctx.state
    return {
        "sprint_id": ctx.plan["sprint_id"], "status": st["status"], "halt": halt_reason(ctx),
        "approved": approval_problem(ctx) is None,
        "budget": {"cap_eur": approved_cap(ctx), "spent_eur": st["budget"]["spent_eur"]},
        "steps": {sid: {"agent": ctx.step(sid)["agent"], "status": x["status"], "attempts": x["attempts"],
                        "spent_eur": x["spent_eur"], "outputs": x["outputs"]} for sid, x in st["steps"].items()},
        "needs_human": open_items(ctx),
    }


def cmd_status(ctx: Ctx, args: argparse.Namespace) -> int:
    sync_state(ctx)
    sm = summary(ctx)
    if args.json:
        print(json.dumps(sm, indent=2, ensure_ascii=False))
        return L.EXIT_OK
    print(f"{sm['sprint_id']}: {sm['status']}{' (not approved for this plan)' if not sm['approved'] else ''}")
    if sm["halt"]:
        print(f"  HALTED {sm['halt']}")
    print(f"  budget: {sm['budget']['spent_eur']:.2f} / {sm['budget']['cap_eur']:.2f} EUR")
    for sid, x in sm["steps"].items():
        print(f"  {sid:<28} {x['agent']:<22} {x['status']:<12} attempts {x['attempts']}")
    for h in sm["needs_human"]:
        print(f"  {h['id']} [{h['kind']}] {h['step']}: {h['reason']}\n      how: {h['how']}")
    return L.EXIT_OK


def cmd_report(ctx: Ctx, args: argparse.Namespace) -> int:
    with L.Lock(ctx.dir / "state.json.lock"):
        sync_state(ctx)
        if is_complete(ctx):
            ctx.state["status"] = "complete"
        ctx.save()
    st, p = ctx.state, ctx.plan
    g = p["goal"]
    day = ctx.now.strftime("%Y%m%d")
    out = [f"# Sprint report: {p['sprint_id']}", "",
           f"- Goal: {g['text']} (measured by {g['metric']}" + (f", target {g['target']}" if g.get("target") is not None else "") + ")",
           f"- Status: {st['status']}" + (f", halted: {halt_reason(ctx)}" if halt_reason(ctx) else ""),
           f"- Approved by: {st['approval']['by'] if st.get('approval') else 'nobody'}" + (f" on {st['approval']['at']}" if st.get("approval") else ""),
           f"- Budget: {st['budget']['spent_eur']:.2f} EUR spent of {approved_cap(ctx):.2f} EUR approved", ""]
    if args.summary:
        out += ["## Summary", "", Path(args.summary).read_text(encoding="utf-8").strip(), ""]
    out += ["## Steps", "", "| Step | Agent | Status | Attempts | Spent (EUR) | Verified outputs |",
            "|------|-------|--------|----------|-------------|------------------|"]
    for s in p["steps"]:
        x = st["steps"][s["id"]]
        outs = "<br>".join(f"`{o}`" for o in x["outputs"]) or "none"
        out.append(f"| `{s['id']}` | {s['agent']} | {x['status']} | {x['attempts']} | {x['spent_eur']:.2f} | {outs} |")
    opened = open_items(ctx)
    out += ["", "## Waiting for you", ""]
    out += [f"- `{h['id']}` ({h['kind']}, step `{h['step']}`): {h['reason']}. How: {h['how']}" for h in opened] or ["- Nothing."]
    done_items = [h for h in st["needs_human"] if h["resolved"] is not None]
    out += ["", "## Decided by a person during the sprint", ""]
    out += [f"- `{h['id']}` ({h['kind']}, `{h['step']}`): {h['reason']}. Cleared by {h['resolved']['by']} on {h['resolved']['at']}, then {h['resolved']['then']}"
            + (f" ({h['resolved']['note']})" if h["resolved"].get("note") else "") for h in done_items] or ["- Nothing beyond the plan approval."]
    defaults = [(sid, n[len("default: "):]) for sid, x in st["steps"].items() for n in x["notes"] if n.startswith("default: ")]
    out += ["", "## Decided without you (agent defaults)", ""]
    out += [f"- `{sid}`: {d}" for sid, d in defaults] or ["- None recorded."]
    incidents = [e for e in st["events"] if e["action"] in ("halt", "halt_cleared", "interrupted", "budget_alert", "plan_changed")]
    out += ["", "## Breaker, interruptions, budget alerts", ""]
    out += [f"- {e['at']} {e['action']}" + (f" `{e['step']}`" if e.get("step") else "") + (f": {e['note']}" if e.get("note") else "") for e in incidents] or ["- None."]
    nxt = []
    for s in p["steps"]:
        a = ctx.registry["agents"][s["agent"]]
        if a.get("next_sprint_input") and st["steps"][s["id"]]["status"] == "done":
            nxt += [o for o in st["steps"][s["id"]]["outputs"] if "experiments-" in o]
    out += ["", "## Input for the next sprint", ""]
    out += [f"- `{o}`: pick one experiment as the next goal (`goal.source`: `{o}#<experiment id>`)." for o in nxt] or ["- No growth-pulse experiments produced in this sprint."]
    out.append("")
    report = ctx.dir / f"sprint-report-{day}.md"
    report.write_text("\n".join(out), encoding="utf-8")
    print(f"report: {report}")
    if args.log:
        if st.get("halt") and st["halt"]["reason"] == "failures":
            status = "failed"
        elif st["status"] == "complete" and not opened:
            status = "ok"
        else:
            status = "partial"
        rel = lambda q: str(q.relative_to(ctx.project))  # noqa: E731
        rec = {"ts": L.iso(ctx.now), "agent": "growth-sprint", "label": p["sprint_id"], "status": status,
               "inputs_hash": ctx.plan_hash[:12], "outputs": [rel(ctx.plan_path), rel(ctx.state_path), rel(report)],
               "checks": {"plan_schema": "pass", "steps_verified": "pass" if all(x["status"] in L.TERMINAL for x in st["steps"].values()) else "fail"},
               "human_verdict": "approved" if st.get("approval") else "none",
               "notes": f"{sum(1 for x in st['steps'].values() if x['status'] == 'done')} done, {len(opened)} waiting for a person, {st['budget']['spent_eur']:.2f} EUR spent"}
        errs = L.schema_errors(rec, L.RUN_RECORD_SCHEMA)
        if errs:
            raise L.Refused("run line invalid: " + "; ".join(errs))
        mem = ctx.project / "project-context" / "memory" / "runs.jsonl"
        mem.parent.mkdir(parents=True, exist_ok=True)
        with open(mem, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"run line appended to {mem} ({status})")
    return L.EXIT_OK


# ---------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="growth-sprint state machine: validate, approve, next, mark, resolve, status, resume, report.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("Exit codes:")[1].join(["Exit codes:", ""]))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("dir", help="sprint folder: <project>/growth-sprint/<sprint id>/")
        p.add_argument("--project", help="project folder (default: two levels above the sprint folder)")
        p.add_argument("--registry", help="agent registry (default: assets/agents.json)")
        p.add_argument("--now", help="clock override, ISO 8601 (tests)")

    p = sub.add_parser("validate", help="check sprint.json (schema, registry, graph, flags, budget) and create or sync state.json")
    common(p)
    p = sub.add_parser("packet", help="write approval.md: plan, budget, spending and publishing steps, gates kept by the founder, plan code")
    common(p)
    p = sub.add_parser("approve", help="HUMAN ONLY, interactive terminal: record the one approval (a person's name, the plan code typed at the prompt)")
    common(p)
    p.add_argument("--by", required=True, help="name of the person approving")
    p.add_argument("--code", help=argparse.SUPPRESS)  # refused with a clear message
    p.add_argument("--approvers", nargs="*", help="restrict approval to these names (default: approvers of <project>/growth-sprint/config.json)")
    p.add_argument("--note")
    p = sub.add_parser("next", help="the next runnable steps (a wave of up to 3); --claim starts them and writes their briefs")
    common(p)
    p.add_argument("--claim", action="store_true")
    p.add_argument("--max", type=int, help="wave size, 1 to 3 (default: sprint.json max_wave, else 3; 1 = sequential)")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("mark", help="move a step; done is settled from the disk by check_step, never taken on trust")
    common(p)
    p.add_argument("step")
    p.add_argument("status", choices=["running", "done", "failed", "needs_human", "skipped"])
    p.add_argument("--spent", type=float, help="cash spent by the step, EUR (overrides the result file)")
    p.add_argument("--note")
    p.add_argument("--kind", default="other", choices=["spend", "publish", "input", "other"])
    p.add_argument("--reason")
    p.add_argument("--how")
    p.add_argument("--by")
    p = sub.add_parser("resolve", help="a person closes a needs_human item (checked on disk when it can be)")
    common(p)
    p.add_argument("item", help="H-NN")
    p.add_argument("--by", required=True)
    p.add_argument("--then", default="rerun", choices=["rerun", "done", "skip"])
    p.add_argument("--set", action="append", help="name=value for a missing input (repeatable)")
    p.add_argument("--note")
    p = sub.add_parser("status", help="steps, budget, breaker, open needs_human items")
    common(p)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("resume", help="after an interruption: settle running steps from the disk; a person can clear a failures breaker")
    common(p)
    p.add_argument("--by")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--retry", help="step the breaker tripped on: allow two more attempts")
    g.add_argument("--skip", help="step the breaker tripped on: skip it")
    p = sub.add_parser("report", help="write sprint-report-<YYYYMMDD>.md; --log appends the run line to project memory")
    common(p)
    p.add_argument("--summary", help="markdown file with the orchestrator's summary, inserted at the top")
    p.add_argument("--log", action="store_true")
    return ap


COMMANDS = {"validate": cmd_validate, "packet": cmd_packet, "approve": cmd_approve, "next": cmd_next, "mark": cmd_mark,
            "resolve": cmd_resolve, "status": cmd_status, "resume": cmd_resume, "report": cmd_report}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = Ctx(Path(args.dir), args.project, args.registry, args.now)
        return COMMANDS[args.cmd](ctx, args)
    except L.GateRefused as e:
        print(f"REFUSED {e}", file=sys.stderr)
        return L.EXIT_NOT_APPROVED
    except L.Refused as e:
        print(f"REFUSED {e}", file=sys.stderr)
        return L.EXIT_FAIL
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return L.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
