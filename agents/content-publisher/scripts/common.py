"""common.py: shared helpers of the content-publisher scripts (no CLI).

Paths, queue load and atomic save, the status machine, content hashes, the
local clock, and the stdlib JSON Schema validator of the stack. Standard
library only, Python 3.9+.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
REPO = AGENT.parent.parent
ASSETS = AGENT / "assets"
QUEUE_SCHEMA = ASSETS / "queue.schema.json"
SPEC_SCHEMA = ASSETS / "post-spec.schema.json"
LIMITS_FILE = ASSETS / "platform-limits.json"
SHARED_VALIDATOR = REPO / "shared" / "scripts" / "validate_json.py"
WRITING_GATE = REPO / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"

NETWORKS = ("linkedin", "x", "instagram", "threads", "bluesky")
STATUSES = ("to_review", "approved", "scheduled", "published", "failed", "rejected")

# Exit codes shared by every CLI of this agent.
EXIT_OK = 0
EXIT_CHECK = 1      # a check failed, a command was refused on the content
EXIT_USAGE = 2      # bad arguments, unreadable or invalid file
EXIT_GATE = 3       # the human approval gate refused the command
EXIT_PROVIDER = 4   # the publishing provider is not available (no key, offline)

# Allowed status moves. "approved" is reachable only through the human
# approval command (see transition()).
TRANSITIONS: Dict[str, set] = {
    "to_review": {"approved", "rejected"},
    "approved": {"to_review", "scheduled", "rejected", "failed"},
    "scheduled": {"published", "failed"},
    "failed": {"to_review"},
    "rejected": {"to_review"},
    "published": set(),
}

# Names an agent or a tool would sign with. approve --by refuses them, so an
# approval always carries the name of a person.
RESERVED_APPROVERS = {
    "agent", "ai", "assistant", "auto", "autopilot", "bot", "claude", "codex", "content-publisher",
    "cursor", "gemini", "gpt", "llm", "model", "pubqueue", "script", "system", "scheduler", "cron",
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "timezone": "UTC",
    "slots": {},
    "window_minutes": 120,
    "lead_minutes": 60,
    "horizon_days": 28,
    "approvers": [],
    "adapter": "dry-run",
    "x_allow_thread": False,
    "link_in_bio_patterns": [r"\blink(?:ed)? in (?:our |the |my )?bio\b", r"\blien en bio\b", r"\blien dans (?:la |notre )?bio\b"],
}


class Refused(Exception):
    """A command refused on the content or the state (exit 1)."""


class GateRefused(Exception):
    """The human approval gate refused the command (exit 3)."""


class UsageError(Exception):
    """Bad arguments or an unreadable file (exit 2)."""


# ------------------------------------------------------------------ json

def read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError(f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise UsageError(f"{path}: not valid JSON (line {e.lineno}: {e.msg})")


def write_json_atomic(path: Path, data: Any) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def schema_errors(instance: Any, schema_path: Path) -> List[str]:
    """Validate with the stack's stdlib validator (shared/scripts/validate_json.py).
    Returns [] when the shared validator is absent (the agent copied alone):
    the script checks that follow still run."""
    if not SHARED_VALIDATOR.exists():
        return []
    sys.path.insert(0, str(SHARED_VALIDATOR.parent))
    try:
        from validate_json import validate  # type: ignore
    finally:
        sys.path.pop(0)
    return validate(instance, read_json(schema_path))


def limits() -> Dict[str, Any]:
    return read_json(LIMITS_FILE)["networks"]


# ------------------------------------------------------------------ hashing

def file_sha256(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def content_hash(item: Dict[str, Any]) -> str:
    """Hash of everything the audience will see: network, texts, link, media
    files (by content). The slot is not part of it: moving a post in time does
    not need a new approval, changing a word or an image does."""
    payload = {
        "network": item.get("network"),
        "text": item.get("text") or "",
        "first_comment": item.get("first_comment") or "",
        "reply": item.get("reply") or "",
        "link": item.get("link") or "",
        "media": [[m.get("type"), m.get("sha256") or m.get("path"), m.get("alt") or "", m.get("title") or ""]
                  for m in item.get("media") or []],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ approval key

# The approval key is a random secret kept outside every project folder
# (default ~/.config/fog-agents/approval.key, mode 600, created on first use;
# FOG_APPROVAL_KEY_FILE overrides the path). Review codes and approval records
# are HMACs under this key, so neither can be computed from queue.json alone.
# growth-sprint reads the same file.
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
            raise UsageError(f"cannot create the approval key {path}: {e} (set {APPROVAL_KEY_ENV} to a writable path)")
    try:
        raw = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"cannot read the approval key {path}: {e}")
    if len(raw) < 32:
        raise UsageError(f"approval key {path} is shorter than 32 characters: delete it to create a new one "
                         "(every pending approval must then be given again)")
    _KEY_CACHE[str(path)] = raw.encode("ascii")
    return _KEY_CACHE[str(path)]


def keyed(purpose: str, *parts: str) -> str:
    msg = "\x1f".join((purpose,) + tuple(str(p) for p in parts)).encode("utf-8")
    return hmac.new(approval_key(), msg, hashlib.sha256).hexdigest()


def review_code(item: Dict[str, Any]) -> str:
    """The 6-character code a person types to approve this exact content. An
    HMAC of the item id and content hash under the local approval key: only
    the interactive `approve` command prints it."""
    return keyed("content-publisher/review-code", item["id"], item["content_hash"])[:6]


def approval_mac(item_id: str, approval: Dict[str, Any]) -> str:
    return keyed("content-publisher/approval", item_id, approval.get("content_hash") or "",
                 approval.get("by") or "", approval.get("at") or "")


# ------------------------------------------------------------------ time

def tz_now(timezone: str) -> datetime:
    """Current local time in the queue timezone, naive. Falls back to UTC when
    the zone database is missing (some Windows installs without tzdata)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(timezone)).replace(tzinfo=None, second=0, microsecond=0)
    except Exception:  # noqa: BLE001
        return datetime.utcnow().replace(second=0, microsecond=0)


def parse_slot(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        raise UsageError(f"invalid slot {value!r}: expected YYYY-MM-DDTHH:MM (local time)")


def fmt_slot(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def resolve_now(arg: Optional[str], timezone: str) -> datetime:
    return parse_slot(arg) if arg else tz_now(timezone)


def stamp(now: Optional[datetime] = None) -> str:
    """History timestamp. Commands that take --now use it, so test runs are reproducible."""
    return fmt_slot(now) if now else datetime.now().astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------ queue

@contextlib.contextmanager
def locked(queue_path: Path) -> Iterator[None]:
    """Exclusive lock next to the queue so two commands never interleave writes.
    No-op where fcntl is missing (Windows): run one command at a time there."""
    lock = Path(str(queue_path) + ".lock")
    try:
        import fcntl
    except ImportError:
        yield
        return
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def new_queue(project: str = "", settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_SETTINGS))
    for k, v in (settings or {}).items():
        if k in merged:
            merged[k] = v
    return {"schema_version": "1.0", "project": project, "settings": merged, "items": []}


def load_queue(path: Path) -> Dict[str, Any]:
    data = read_json(path)
    errs = schema_errors(data, QUEUE_SCHEMA)
    if errs:
        raise UsageError(f"{path} does not match assets/queue.schema.json:\n  " + "\n  ".join(errs[:20]))
    for k, v in DEFAULT_SETTINGS.items():
        data["settings"].setdefault(k, json.loads(json.dumps(v)))
    return data


def save_queue(path: Path, data: Dict[str, Any]) -> None:
    errs = schema_errors(data, QUEUE_SCHEMA)
    if errs:  # a bug in this agent, never a user error: refuse to write a broken queue
        raise RuntimeError("refusing to write an invalid queue:\n  " + "\n  ".join(errs[:20]))
    write_json_atomic(path, data)


def find_item(data: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    for it in data["items"]:
        if it["id"] == item_id:
            return it
    raise UsageError(f"no item {item_id!r} in the queue (pubqueue.py list shows the ids)")


def log(item: Dict[str, Any], action: str, by: str = "", note: str = "", now: Optional[datetime] = None,
        frm: str = "", to: str = "") -> None:
    ev = {"at": stamp(now), "action": action, "by": by, "note": note}
    if frm:
        ev["from"] = frm
    if to:
        ev["to"] = to
    item.setdefault("history", []).append(ev)
    item["updated"] = ev["at"]


# Sentinel only cmd_approve in pubqueue.py holds. transition() refuses the
# move to "approved" without it, so no other code path can approve an item.
# selftest.py checks that the sentinel appears in exactly one call site.
class _HumanApproval:
    __slots__ = ()


HUMAN_APPROVAL = _HumanApproval()


def transition(item: Dict[str, Any], new: str, by: str, action: str, note: str = "",
               now: Optional[datetime] = None, token: Any = None) -> None:
    old = item["status"]
    if new not in TRANSITIONS.get(old, set()):
        raise Refused(f"{item['id']}: {old} -> {new} is not allowed")
    if new == "approved" and token is not HUMAN_APPROVAL:
        raise GateRefused(f"{item['id']}: only the human command `pubqueue.py approve` moves an item to approved")
    item["status"] = new
    if new in ("to_review", "rejected"):
        item["approval"] = None  # an approval covers one reviewed content, never a later one
    log(item, action, by, note, now, frm=old, to=new)


def approval_problem(item: Dict[str, Any]) -> Optional[str]:
    """None when the item carries an approval recorded by `pubqueue.py approve`
    for its current content, else the reason in one line. A status, an
    approval object or a history event typed into queue.json fails here."""
    ap = item.get("approval")
    if not ap:
        return "no approval recorded"
    if ap.get("content_hash") != item.get("content_hash"):
        return "the approval does not match the current content"
    if not hmac.compare_digest(str(ap.get("mac") or ""), approval_mac(item["id"], ap)):
        return ("the approval was not recorded by `pubqueue.py approve` with this machine's approval key "
                "(queue.json edited by hand, or the key changed)")
    if not any(ev.get("to") == "approved" and ev.get("action") == "approved" for ev in item.get("history", [])):
        return "no approve event in the history"
    return None


def approval_valid(item: Dict[str, Any]) -> bool:
    return approval_problem(item) is None


def project_root(queue_dir: Path) -> Path:
    """The project folder media must stay in: the parent of a queue folder
    named content-publisher (<project>/content-publisher/queue.json), else the
    queue folder itself."""
    q = Path(queue_dir).resolve()
    return q.parent if q.name == "content-publisher" else q


def media_file(queue_dir: Path, rel: str) -> Path:
    """Resolve a media path of the queue (relative to the queue folder). An
    absolute path, a ../ or a symlink that lands outside the project folder
    is refused: only project files are ever hashed or uploaded."""
    root = project_root(queue_dir)
    path = (Path(queue_dir) / rel).resolve()
    if path != root and root not in path.parents:
        raise Refused(f"media path {rel!r} resolves outside the project folder {root}: refused")
    return path


def refresh_media_hashes(item: Dict[str, Any], queue_dir: Path) -> None:
    for m in item.get("media") or []:
        m["sha256"] = file_sha256(media_file(queue_dir, m["path"]))


def window_conflicts(items: List[Dict[str, Any]], window_minutes: int) -> List[str]:
    """Pairs of live items of the same network closer than the window."""
    live = [i for i in items if i.get("slot") and i["status"] in ("to_review", "approved", "scheduled", "published")]
    out = []
    gap = timedelta(minutes=window_minutes)
    for a_i, a in enumerate(live):
        for b in live[a_i + 1:]:
            if a["network"] == b["network"] and abs(parse_slot(a["slot"]) - parse_slot(b["slot"])) < gap:
                out.append(f"{a['id']} ({a['slot']}) and {b['id']} ({b['slot']}) are closer than {window_minutes} min on {a['network']}")
    return out
