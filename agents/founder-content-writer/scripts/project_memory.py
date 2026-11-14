#!/usr/bin/env python3
"""project_memory.py: what this agent keeps in the founder's project memory.

Follows shared/skills/keeping-project-memory/SKILL.md. Three files under
<project>/project-context/memory/:

  posts.jsonl    this agent's past posts: openings, hook types, angles, rejections
  decisions.md   the founder's corrections as rules, in the shared format
  runs.jsonl     one line per run, validated against the shared schema

A rejection from the founder is recorded on the post and becomes a decision.
Without --confirmed the decision stays `Status: proposed` and nothing is enforced
yet: a rule is the agent's reading of what the founder said, the founder confirms it.

Usage:
  python3 project_memory.py record SPEC.json --project DIR [--now ISO]
  python3 project_memory.py reject REF --project DIR --reason "founder's words" --rule "what to do next time"
        [--spec SPEC.json] [--network linkedin|x] [--how TEXT] [--scope TEXT] [--ban WORD ...]
        [--avoid-hook TYPE] [--avoid-angle-type TYPE] [--keep-angle] [--confirmed] [--now ISO]
  python3 project_memory.py confirm D-YYYYMMDD-NN --project DIR [--now ISO]
  python3 project_memory.py log-run --run RUN_DIR --project DIR --status ok|partial|failed|skipped
        [--critic PASS|FAIL|none] [--human approved|changes_requested|rejected|none]
        [--decision ID ...] [--provider CAPABILITY=PROVIDER ...] [--notes TEXT] [--now ISO]
  python3 project_memory.py seen --run RUN_DIR --project DIR     # exit 0 when the same inputs already ran

Exit codes: 0 ok (seen: already done), 1 refused or not seen, 2 usage error or unreadable file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fcw_lib as L  # noqa: E402

INDEX_HEADER = "# Decisions\n"


def timestamp(now: Optional[str]) -> str:
    return now or datetime.now().astimezone().isoformat(timespec="seconds")


def append_line(path: Path, row: Dict[str, Any], schema: Path) -> None:
    errs = L.schema_errors(row, schema)
    if errs:
        raise L.UsageError("refusing to write an invalid memory line: " + "; ".join(errs[:5]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def need_project(project: str) -> Dict[str, Any]:
    return L.project_paths(project)


# ------------------------------------------------------------------ past posts

def lines_for(spec: Dict[str, Any], now: str) -> List[Dict[str, Any]]:
    rows = []
    for p in spec["posts"]:
        for net in p["networks"]:
            body = (p["variants"].get(net) or {}).get("text", "")
            if not body.strip():
                continue
            rows.append({"ts": now, "agent": L.AGENT_NAME, "label": spec["label"], "ref": p["ref"], "network": net, "status": "written",
                         "opening": L.first_line(body), "hook_type": p["hook_type"], "angle": p["angle"], "sha256": L.sha256_text(body)})
    return rows


def cmd_record(a: argparse.Namespace) -> int:
    paths = need_project(a.project)
    spec = L.read_json(Path(a.spec))
    errs = L.schema_errors(spec, L.SPEC_SCHEMA)
    if errs:
        raise L.UsageError(f"{a.spec} does not match the schema: " + "; ".join(errs[:5]))
    existing, broken = L.read_jsonl(paths["posts"])
    if broken:
        print(f"WARNING memory/posts.jsonl: unreadable lines skipped: {broken}")
    seen = {(r.get("ref"), r.get("network"), r.get("sha256")) for r in existing}
    added = 0
    for row in lines_for(spec, timestamp(a.now)):
        if (row["ref"], row["network"], row["sha256"]) not in seen:
            append_line(paths["posts"], row, L.PAST_SCHEMA)
            added += 1
    print(f"memory/posts.jsonl: {added} lines added, {len(existing)} already there")
    return L.EXIT_OK


# ------------------------------------------------------------------ decisions

def next_id(text: str, day: str) -> str:
    nums = [int(n) for n in re.findall(rf"D-{day}-(\d+)", text)]
    return f"D-{day}-{max(nums, default=0) + 1:02d}"


def insert_decision(path: Path, did: str, title: str, scope: str, body: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else INDEX_HEADER + "\n## Active\n\n## Superseded\n"
    if "## Active" not in text:
        marker = text.find("## Superseded")
        text = (text + "\n## Active\n\n") if marker < 0 else text[:marker] + "## Active\n\n" + text[marker:]
    index = f"- {did}: {title} ({scope})\n"
    head = text.find("## Active")
    last_index = [m.end() for m in re.finditer(r"^- D-\d{8}-\d+:.*\n", text[:head], re.M)]
    if last_index:
        text = text[:last_index[-1]] + index + text[last_index[-1]:]
    else:
        at = text.find("\n", text.find(INDEX_HEADER.strip())) + 1 if INDEX_HEADER.strip() in text[:head] else 0
        text = text[:at] + "\n" + index + text[at:]
    head = text.find("## Active")
    at = text.find("\n", head) + 1
    text = text[:at] + "\n" + body + "\n" + text[at:].lstrip("\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def apply_bans(project: str, words: List[str]) -> None:
    """A confirmed decision that bans a word becomes a rule of the project pack,
    so the writing gate of every agent enforces it."""
    path = L.project_paths(project)["voice_rules"]
    pack = L.read_json(path) if path.is_file() else {"language": "any", "banned_words": []}
    pack.setdefault("banned_words", [])
    for w in words:
        if w not in pack["banned_words"]:
            pack["banned_words"].append(w)
    errs = L.schema_errors(pack, L.COPY_RULES_SCHEMA)
    if errs:
        raise L.UsageError(f"{path}: refusing to write an invalid pack: " + "; ".join(errs[:5]))
    L.write_json_atomic(path, pack)


def cmd_reject(a: argparse.Namespace) -> int:
    paths = need_project(a.project)
    now = timestamp(a.now)
    rows, _ = L.read_jsonl(paths["posts"])
    written = {r["network"]: r for r in rows if r.get("ref") == a.ref and r.get("status") == "written"}
    if not written and a.spec:
        spec = L.read_json(Path(a.spec))
        written = {r["network"]: r for r in lines_for(spec, now) if r["ref"] == a.ref}
    if not written:
        print(f"refused: no post {a.ref!r} in memory/posts.jsonl: pass --spec with the batch that holds it")
        return L.EXIT_CHECK
    networks = [a.network] if a.network else sorted(written)
    if any(n not in written for n in networks):
        print(f"refused: post {a.ref} has no {a.network} variant")
        return L.EXIT_CHECK
    day = now[:10].replace("-", "")
    decisions_path = paths["decisions"]
    current = decisions_path.read_text(encoding="utf-8") if decisions_path.is_file() else ""
    did = next_id(current, day)
    enforced = []
    enforced += [f'writing-gate banned-word "{w}"' for w in a.ban or []]
    if a.avoid_hook:
        enforced.append(f"{L.AGENT_NAME} hook:{a.avoid_hook}")
    if a.avoid_angle_type:
        enforced.append(f"{L.AGENT_NAME} angle-type:{a.avoid_angle_type}")
    status = "active" if a.confirmed else "proposed"
    title = " ".join(a.rule.split())
    title = title if len(title) <= 80 else title[:77].rstrip() + "..."
    scope = a.scope or f"{L.AGENT_NAME}, all networks"
    label = next(iter(written.values())).get("label", "")
    body = "\n".join([
        f"### {did}: {title}",
        f"- Rule: {' '.join(a.rule.split())}",
        f"- Why: the founder rejected the post \"{a.ref}\" on {now[:10]}: \"{' '.join(a.reason.split())}\"",
        f"- How to apply: {a.how or 'before writing a batch, read this rule against every angle and hook of the batch'}",
        f"- Scope: {scope}",
        f"- Date: {now[:10]}",
        f"- Source: {L.AGENT_NAME}, batch \"{label}\"",
        f"- Status: {status}",
        f"- Enforced by: {'; '.join(enforced) if enforced else 'none'}",
        "- Replaces: none",
        "",
    ])
    insert_decision(decisions_path, did, title, scope, body)
    for net in networks:
        row = dict(written[net])
        row.update({"ts": now, "status": "rejected", "reason": " ".join(a.reason.split()), "decision": did})
        if a.keep_angle:
            row.pop("angle", None)
        append_line(paths["posts"], row, L.PAST_SCHEMA)
    if a.confirmed and a.ban:
        apply_bans(a.project, a.ban)
    print(f"{did} ({status}): {title}")
    print(f"memory/posts.jsonl: {a.ref} rejected on {', '.join(networks)}")
    return L.EXIT_OK


def cmd_confirm(a: argparse.Namespace) -> int:
    path = L.project_paths(a.project)["decisions"]
    if not path or not path.is_file():
        print("refused: no memory/decisions.md")
        return L.EXIT_CHECK
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^### {re.escape(a.decision)}:.*?(?=^### |^## |\Z)", text, re.M | re.S)
    if not m:
        print(f"refused: no entry {a.decision}")
        return L.EXIT_CHECK
    entry = m.group(0)
    if "- Status: proposed" not in entry:
        print(f"{a.decision} is not proposed, nothing to do")
        return L.EXIT_OK
    bans = re.findall(r'writing-gate banned-word "([^"]+)"', entry)
    path.write_text(text[:m.start()] + entry.replace("- Status: proposed", "- Status: active") + text[m.end():], encoding="utf-8")
    if bans:
        apply_bans(a.project, bans)
    print(f"{a.decision} active" + (f", banned in voice/rules.json: {', '.join(bans)}" if bans else ""))
    return L.EXIT_OK


# ------------------------------------------------------------------ runs

def inputs_hash(run: Path, project: str) -> str:
    """Hash of the raw material, the config and the brief of a batch."""
    h = hashlib.sha256()
    manifest = run / "sources" / "manifest.json"
    data = L.read_json(manifest) if manifest.is_file() else {"sources": []}
    for s in sorted(data.get("sources", []), key=lambda x: x.get("source_id", "")):
        h.update(f"{s.get('source_id')}={s.get('sha256')}\n".encode("utf-8"))
    for extra in (Path(project) / L.AGENT_NAME / "config.json", run / "brief.md"):
        if extra.is_file():
            h.update(extra.read_bytes())
    return h.hexdigest()[:16]


def cmd_log_run(a: argparse.Namespace) -> int:
    run, paths = Path(a.run), need_project(a.project)
    outputs = [L.relative_to_project(p, a.project) for p in sorted(run.glob("*")) if p.is_file() and p.suffix in (".json", ".md")]
    checks: Dict[str, str] = {}
    report, _ = L.read_optional_json(run / "check.json")
    if isinstance(report, dict):
        codes = [f["code"] for f in report.get("findings", []) if f["level"] == "error"]
        gate_ran = (report.get("info") or {}).get("gate", {}).get("ran")
        checks["copy_lint"] = "skipped" if gate_ran is False else ("fail" if any(c.startswith("writing-gate:") for c in codes) else "pass")
        checks["founder_content_check"] = report.get("status", "fail") if report.get("status") in ("pass", "fail") else "fail"
    lint, _ = L.read_optional_json(run / "lint.json")
    if isinstance(lint, dict) and lint.get("status") in ("pass", "fail"):
        checks["content_publisher_lint"] = lint["status"]
    providers = {}
    for item in a.provider or []:
        if "=" not in item:
            raise L.UsageError(f"--provider {item!r}: expected capability=provider")
        k, v = item.split("=", 1)
        providers[k] = v
    row: Dict[str, Any] = {"ts": timestamp(a.now), "agent": L.AGENT_NAME, "label": run.resolve().name, "status": a.status,
                           "inputs_hash": inputs_hash(run, a.project), "outputs": outputs, "checks": checks,
                           "critic_verdict": a.critic, "human_verdict": a.human, "decisions_added": a.decision or []}
    if providers:
        row["providers"] = providers
    if a.notes:
        row["notes"] = a.notes
    append_line(paths["runs"], row, L.RUN_RECORD_SCHEMA)
    print(f"memory/runs.jsonl: {row['label']} {a.status}, inputs {row['inputs_hash']}")
    return L.EXIT_OK


def cmd_seen(a: argparse.Namespace) -> int:
    run, paths = Path(a.run), need_project(a.project)
    want = inputs_hash(run, a.project)
    rows, _ = L.read_jsonl(paths["runs"])
    for r in reversed(rows):
        if r.get("agent") == L.AGENT_NAME and r.get("inputs_hash") == want and r.get("status") in ("ok", "partial"):
            if all((Path(a.project) / o).exists() for o in r.get("outputs", [])):
                print(f"already done: {r.get('label')} on {str(r.get('ts'))[:10]}, same inputs ({want})")
                return L.EXIT_OK
    print(f"not done yet: inputs {want}")
    return L.EXIT_CHECK


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record", help="append a batch's posts to memory/posts.jsonl")
    p.add_argument("spec")
    p.add_argument("--project", required=True)
    p.add_argument("--now")
    p = sub.add_parser("reject", help="record a founder's rejection and the rule it implies")
    p.add_argument("ref")
    p.add_argument("--project", required=True)
    p.add_argument("--reason", required=True, help="the founder's own words")
    p.add_argument("--rule", required=True, help="the rule a different agent can follow without this conversation")
    p.add_argument("--spec", help="the batch, when the post was never recorded")
    p.add_argument("--network", choices=("linkedin", "x"))
    p.add_argument("--how", help="how to apply the rule")
    p.add_argument("--scope", help="where it applies, default this agent on all networks")
    p.add_argument("--ban", action="append", help="a word to ban: goes to voice/rules.json once confirmed")
    p.add_argument("--avoid-hook", help="a hook type to refuse once confirmed")
    p.add_argument("--avoid-angle-type", help="an angle type to refuse once confirmed")
    p.add_argument("--keep-angle", action="store_true", help="the founder refused the wording, not the angle")
    p.add_argument("--confirmed", action="store_true", help="the founder confirmed the rule: write it active")
    p.add_argument("--now")
    p = sub.add_parser("confirm", help="the founder confirmed a proposed decision: make it active")
    p.add_argument("decision")
    p.add_argument("--project", required=True)
    p.add_argument("--now")
    p = sub.add_parser("log-run", help="append the run line to memory/runs.jsonl")
    p.add_argument("--run", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--status", required=True, choices=("ok", "partial", "failed", "skipped"))
    p.add_argument("--critic", default="none", choices=("PASS", "FAIL", "none"))
    p.add_argument("--human", default="none", choices=("approved", "changes_requested", "rejected", "none"))
    p.add_argument("--decision", action="append")
    p.add_argument("--provider", action="append")
    p.add_argument("--notes")
    p.add_argument("--now")
    p = sub.add_parser("seen", help="did the same inputs already run?")
    p.add_argument("--run", required=True)
    p.add_argument("--project", required=True)
    a = ap.parse_args(argv)
    try:
        return {"record": cmd_record, "reject": cmd_reject, "confirm": cmd_confirm, "log-run": cmd_log_run, "seen": cmd_seen}[a.cmd](a)
    except L.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return L.EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
