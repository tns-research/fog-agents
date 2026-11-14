#!/usr/bin/env python3
"""sprint_lib.py: shared helpers of growth-sprint (registry, disk checks,
state file, clock, lock). Standard library only, Python 3.9+.

Not a CLI. Imported by sprint.py, check_step.py and selftest.py.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS = Path(__file__).resolve().parent
AGENT_DIR = SCRIPTS.parent
ASSETS = AGENT_DIR / "assets"
REPO = AGENT_DIR.parent.parent
sys.path.insert(0, str(REPO / "shared" / "scripts"))
from validate_json import validate  # noqa: E402

REGISTRY = ASSETS / "agents.json"
SPRINT_SCHEMA = ASSETS / "sprint.schema.json"
STATE_SCHEMA = ASSETS / "state.schema.json"
RESULT_SCHEMA = ASSETS / "step-result.schema.json"
RUN_RECORD_SCHEMA = REPO / "shared" / "schemas" / "run-record.schema.json"

STATUSES = ("pending", "running", "done", "failed", "needs_human", "skipped")
TERMINAL = {"done", "skipped"}

# Allowed step transitions. Anything else is refused by set_status().
TRANSITIONS: Dict[str, set] = {
    "pending": {"running", "needs_human", "skipped"},
    "running": {"done", "failed", "needs_human", "pending"},
    "needs_human": {"pending", "done", "skipped"},
    "failed": {"pending", "skipped"},
    "done": set(),
    "skipped": set(),
}

# A file modified up to this many seconds before the step started still
# counts as written by the step (file system timestamp granularity).
FRESH_TOLERANCE_S = 2

# Names an agent, a model or a tool would sign with. approve and resolve
# refuse them, so every human decision carries the name of a person.
RESERVED_NAMES = {
    "agent", "ai", "assistant", "auto", "autopilot", "bot", "claude", "codex", "cursor",
    "gemini", "gpt", "llm", "model", "script", "system", "scheduler", "cron", "orchestrator",
    "subagent", "growth-sprint", "sprint", "founder",
}

DATE_TOKEN = "<YYYYMMDD>"
LABEL_TOKEN = "<label>"

# Exit codes shared by the CLIs.
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_HALTED = 3
EXIT_NOT_APPROVED = 4
EXIT_NEEDS_HUMAN = 5
EXIT_COMPLETE = 6


class Refused(Exception):
    """A command refused on the plan, the state or the disk (exit 1)."""


class GateRefused(Exception):
    """The human approval gate refused the command (exit 4)."""


# ---------------------------------------------------------------- clock


def now_dt(now: Optional[str] = None) -> datetime:
    if now:
        return parse_ts(now)
    return datetime.now(timezone.utc).astimezone()


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def parse_ts(value: str) -> datetime:
    """ISO 8601 with or without timezone ('Z' accepted); naive means local time."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


# ---------------------------------------------------------------- json io


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def canonical_hash(data: Any) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- approval key

# A random secret kept outside every project folder (default
# ~/.config/fog-agents/approval.key, mode 600, created on first use;
# FOG_APPROVAL_KEY_FILE overrides the path; content-publisher reads the same
# file). The plan code a person types and the seal of the approval recorded in
# state.json are HMACs under it, so neither can be computed from the sprint
# folder alone.
APPROVAL_KEY_ENV = "FOG_APPROVAL_KEY_FILE"
_KEY_CACHE: Dict[str, bytes] = {}


def approval_key_path() -> Path:
    env = os.environ.get(APPROVAL_KEY_ENV, "").strip()
    return Path(env).expanduser() if env else Path.home() / ".config" / "fog-agents" / "approval.key"


def approval_key() -> bytes:
    path = approval_key_path()
    cached = _KEY_CACHE.get(str(path))
    if cached:
        return cached
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="ascii") as fh:
                fh.write(secrets.token_hex(32) + "\n")
        except FileExistsError:
            pass  # another command created it first
        except OSError as e:
            raise Refused(f"cannot create the approval key {path}: {e} (set {APPROVAL_KEY_ENV} to a writable path)")
    try:
        raw = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as e:
        raise Refused(f"cannot read the approval key {path}: {e}")
    if len(raw) < 32:
        raise Refused(f"approval key {path} is shorter than 32 characters: delete it to create a new one "
                      "(the sprint must then be approved again)")
    _KEY_CACHE[str(path)] = raw.encode("ascii")
    return _KEY_CACHE[str(path)]


def keyed(purpose: str, *parts: str) -> str:
    msg = "\x1f".join((purpose,) + tuple(str(x) for x in parts)).encode("utf-8")
    return hmac.new(approval_key(), msg, hashlib.sha256).hexdigest()


def plan_code(sprint_id: str, plan_hash: str) -> str:
    """The 8-character code a person types to approve one version of sprint.json.
    Printed only by the interactive `sprint.py approve`."""
    return keyed("growth-sprint/plan-code", sprint_id, plan_hash)[:8]


def approval_seal(sprint_id: str, approval: Dict[str, Any]) -> str:
    """HMAC of every field of an approval record except the seal itself."""
    body = {k: v for k, v in approval.items() if k != "mac"}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return keyed("growth-sprint/approval", sprint_id, blob)


def seal_ok(sprint_id: str, approval: Dict[str, Any]) -> bool:
    return hmac.compare_digest(str(approval.get("mac") or ""), approval_seal(sprint_id, approval))


def schema_errors(instance: Any, schema_path: Path) -> List[str]:
    return validate(instance, load_json(schema_path))


class Lock:
    """Exclusive lock file next to state.json, so parallel workers marking
    steps never overwrite each other. A lock older than 60 s is stale."""

    def __init__(self, path: Path, timeout_s: float = 15.0) -> None:
        self.path = path
        self.timeout_s = timeout_s

    def __enter__(self) -> "Lock":
        deadline = time.time() + self.timeout_s
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 60:
                        self.path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.time() > deadline:
                    raise Refused(f"state is locked by another process ({self.path}); retry")
                time.sleep(0.1)

    def __exit__(self, *exc: Any) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------- registry


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    reg = load_json(path or REGISTRY)
    errs = schema_errors(reg, ASSETS / "agents.schema.json")
    for name, a in reg.get("agents", {}).items():
        for g in a.get("human_gates", []):
            d = g.get("detect")
            if isinstance(d, str) and d != "result_pending":
                errs.append(f"agents.{name}.human_gates.{g.get('id')}: detect must be result_pending or a json_count object")
    if errs:
        raise Refused("registry invalid: " + "; ".join(errs[:5]))
    return reg


# ---------------------------------------------------------------- disk checks


def _glob_pattern(pattern: str, label: Optional[str]) -> str:
    return pattern.replace(LABEL_TOKEN, label or "*").replace(DATE_TOKEN, "[0-9]" * 8)


def _date_key(rel: str) -> str:
    dates = re.findall(r"(?<![0-9])([0-9]{8})(?![0-9])", rel)
    return max(dates) if dates else ""


def find_newest(project: Path, pattern: str, label: Optional[str]) -> Optional[Path]:
    """Newest match of a registry path pattern: latest date in the name, then mtime."""
    matches = [p for p in project.glob(_glob_pattern(pattern, label)) if p.exists()]
    if not matches:
        return None
    matches.sort(key=lambda p: (_date_key(str(p.relative_to(project))), p.stat().st_mtime))
    return matches[-1]


def _get_field(data: Any, dotted: str) -> Any:
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_output(project: Path, spec: Dict[str, Any], label: Optional[str],
                 since: Optional[datetime]) -> Dict[str, Any]:
    """Check one registry output on disk. Returns {id, path, ok, required, message}."""
    required = spec.get("required", True)
    res: Dict[str, Any] = {"id": spec["id"], "pattern": spec["path"], "path": None,
                           "required": required, "ok": False, "message": ""}
    found = find_newest(project, spec["path"], label)
    if found is None:
        res["ok"] = not required
        res["message"] = "absent (optional)" if not required else "missing"
        return res
    rel = str(found.relative_to(project))
    res["path"] = rel
    if since is not None:
        mtime = datetime.fromtimestamp(found.stat().st_mtime, tz=timezone.utc)
        if mtime < since - timedelta(seconds=FRESH_TOLERANCE_S):
            res["message"] = f"stale: last modified {iso(mtime.astimezone())}, before the step started"
            return res
    kind = spec["check"]
    try:
        if kind == "dir":
            if not found.is_dir():
                res["message"] = "not a folder"
                return res
            n = sum(1 for p in found.rglob("*") if p.is_file())
            if n < spec.get("min_files", 1):
                res["message"] = f"{n} files, fewer than {spec.get('min_files', 1)}"
                return res
        else:
            if not found.is_file():
                res["message"] = "not a file"
                return res
            size = found.stat().st_size
            if size < spec.get("min_bytes", 1):
                res["message"] = f"{size} bytes, under {spec.get('min_bytes', 1)}"
                return res
        if kind in ("json", "schema"):
            data = load_json(found)
            if kind == "schema":
                errs = schema_errors(data, REPO / spec["schema"])
                if errs:
                    res["message"] = f"{len(errs)} schema error(s): " + "; ".join(errs[:3])
                    return res
        elif kind == "jsonl_schema":
            schema = load_json(REPO / spec["schema"])
            rows = 0
            with open(found, "r", encoding="utf-8") as f:
                for n, line in enumerate(f, start=1):
                    if not line.strip():
                        continue
                    rows += 1
                    errs = validate(json.loads(line), schema)
                    if errs:
                        res["message"] = f"line {n}: " + "; ".join(errs[:3])
                        return res
            if rows < spec.get("min_rows", 1):
                res["message"] = f"{rows} lines, fewer than {spec.get('min_rows', 1)}"
                return res
        elif kind == "csv_header":
            with open(found, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, [])
                rows = sum(1 for r in reader if any(c.strip() for c in r))
            missing = [c for c in spec.get("columns", []) if c not in header]
            if missing:
                res["message"] = "missing columns: " + ", ".join(missing)
                return res
            if rows < spec.get("min_rows", 1):
                res["message"] = f"{rows} rows, fewer than {spec.get('min_rows', 1)}"
                return res
    except (ValueError, OSError, UnicodeDecodeError) as e:
        res["message"] = f"unreadable: {e}"
        return res
    res["ok"] = True
    res["message"] = "ok"
    return res


def gate_pending(project: Path, gate: Dict[str, Any]) -> Optional[str]:
    """On-disk gate test. Returns a reason string when the gate waits for a person."""
    d = gate.get("detect")
    if not isinstance(d, dict) or d.get("type") != "json_count":
        return None
    path = project / d["file"]
    if not path.is_file():
        return None
    try:
        data = load_json(path)
    except (ValueError, OSError):
        return None
    arr = _get_field(data, d["array"]) or []
    count = sum(1 for it in arr if isinstance(it, dict) and it.get(d["field"]) in d["in"])
    if count >= d["min"]:
        return f"{count} item(s) of {d['file']} still {' or '.join(d['in'])}"
    return None


def input_available(project: Path, sources: List[str]) -> bool:
    for src in sources:
        rel, _, field = src.partition("#")
        path = project / rel
        if not path.is_file():
            continue
        if not field:
            return True
        try:
            value = _get_field(load_json(path), field)
        except (ValueError, OSError):
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def missing_inputs(project: Path, agent: Dict[str, Any], step: Dict[str, Any],
                   extra: Optional[Dict[str, Any]] = None) -> List[str]:
    given = dict(step.get("inputs") or {})
    given.update(extra or {})
    out = []
    for inp in agent.get("inputs", []):
        if not inp["required"] or given.get(inp["name"]) not in (None, ""):
            continue
        if inp.get("from") and input_available(project, inp["from"]):
            continue
        out.append(inp["name"])
    return out


def latest_run_line(project: Path, agent: str, since: Optional[datetime]) -> Optional[Dict[str, Any]]:
    path = project / "project-context" / "memory" / "runs.jsonl"
    if not path.is_file():
        return None
    best = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("agent") != agent:
                    continue
                ts = parse_ts(rec["ts"])
            except (ValueError, KeyError, TypeError):
                continue
            if since is not None and ts < since - timedelta(seconds=FRESH_TOLERANCE_S):
                continue
            best = rec
    return best


def read_result(sprint_dir: Path, step_id: str, since: Optional[datetime]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """The step result file, when it exists and was written after the step started."""
    path = sprint_dir / "results" / f"{step_id}.json"
    if not path.is_file():
        return None, None
    if since is not None:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < since - timedelta(seconds=FRESH_TOLERANCE_S):
            return None, "result file older than the step start, ignored"
    try:
        data = load_json(path)
    except (ValueError, OSError) as e:
        return None, f"result file unreadable: {e}"
    errs = schema_errors(data, RESULT_SCHEMA)
    if errs or data.get("step") != step_id:
        return None, "result file invalid: " + "; ".join(errs[:3] or ["step id mismatch"])
    return data, None


def verify_step(project: Path, registry: Dict[str, Any], step: Dict[str, Any],
                since: Optional[datetime], sprint_dir: Optional[Path] = None,
                attempt_since: Optional[datetime] = None, use_result: bool = True) -> Dict[str, Any]:
    """Decide the outcome of a step from the disk only.

    verdict: done (every required output present, fresh and valid, no gate
    waiting), needs_human (a gate or a pending item waits for a person),
    failed (an output is missing, stale or invalid, or the run reported failed).
    The result file and the run line can send a step to a person or to failure;
    they can never make it done. Outputs must be newer than `since` (first
    start of the step); the result file and the run line newer than
    `attempt_since` (start of the current attempt, defaults to `since`).
    """
    attempt_since = attempt_since or since
    agent = registry["agents"][step["agent"]]
    outputs = [check_output(project, o, step.get("label"), since) for o in agent["outputs"]]
    result, result_note = (None, None)
    if sprint_dir is not None and use_result:
        result, result_note = read_result(sprint_dir, step["id"], attempt_since)
    run_line = latest_run_line(project, step["agent"], attempt_since) if use_result else None
    pending: List[Dict[str, Any]] = []
    for g in agent.get("human_gates", []):
        why = gate_pending(project, g)
        if why:
            pending.append({"kind": g["kind"], "gate": g["id"], "reason": why, "how": g["how"]})
    if result:
        for p in result.get("pending", []):
            gate = next((g for g in agent.get("human_gates", []) if g["kind"] == p["kind"]), None)
            item = {"kind": p["kind"], "reason": p["reason"],
                    "how": p.get("how") or (gate["how"] if gate else "Decide, then resolve the item.")}
            if p.get("gate") or gate:
                item["gate"] = p.get("gate") or gate["id"]
            pending.append(item)
    outputs_ok = all(o["ok"] for o in outputs)
    reported = (result or {}).get("status") or (run_line or {}).get("status")
    if reported == "failed":
        verdict, why = "failed", "the run reported failed" + (f": {run_line.get('notes')}" if run_line and run_line.get("notes") else "")
    elif pending:
        verdict, why = "needs_human", "; ".join(p["reason"] for p in pending)
    elif not outputs_ok:
        if reported == "partial" and result is None:
            verdict = "needs_human"
            why = "run ended partial without its outputs" + (f": {run_line.get('notes')}" if run_line and run_line.get("notes") else "")
            pending.append({"kind": "other", "reason": why, "how": "Read the agent report, decide, then resolve the item."})
        else:
            bad = [f"{o['id']} {o['message']}" for o in outputs if not o["ok"]]
            verdict, why = "failed", "outputs not verified: " + "; ".join(bad)
    else:
        verdict, why = "done", "every required output present, fresh and valid"
    return {
        "step": step["id"], "agent": step["agent"], "verdict": verdict, "why": why,
        "outputs": outputs, "pending": pending, "spent_eur": float((result or {}).get("spent_eur", 0) or 0),
        "defaults_used": (result or {}).get("defaults_used", []),
        "result_note": result_note, "run_line_status": (run_line or {}).get("status"),
    }


def is_person(name: Optional[str], registry: Optional[Dict[str, Any]] = None) -> bool:
    if not name:
        return False
    n = name.strip().lower()
    if len(n) < 2 or n.startswith("<") or n in RESERVED_NAMES:
        return False
    if registry and n in registry.get("agents", {}):
        return False
    return True
