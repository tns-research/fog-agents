#!/usr/bin/env python3
"""check_step.py: verify on disk that a sprint step (or any agent run) wrote
its outputs, and that they are fresh and valid.

A step ends on this check, never on what the model or a subagent says. For
each output the registry (assets/agents.json) declares, it finds the newest
matching file in the project, refuses it when it was modified before the
step started, then runs the declared check: file (non-empty, min_bytes),
dir, json (parses), schema (validates against the agent's JSON Schema with
shared/scripts/validate_json.py), jsonl_schema (every line), csv_header
(required columns, at least one row). It also reports human gates waiting on
disk (content-publisher items still to_review), the step result file and the
agent's last run line.

Usage (from the repo root):
    python3 agents/growth-sprint/scripts/check_step.py --sprint <dir> --step <id> [--json]
    python3 agents/growth-sprint/scripts/check_step.py --project <project> --agent <name> [--label L] [--since ISO] [--json]

Exit codes: 0 done (every required output present, fresh and valid, no gate
waiting), 1 failed (an output missing, stale or invalid, or the run reported
failed), 2 usage error, 5 needs a person (a gate or a pending item waits).
It never changes state.json: `sprint.py mark <dir> <step> done` runs the same
verification and records the outcome.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprint_lib as L  # noqa: E402

EXIT_BY_VERDICT = {"done": L.EXIT_OK, "failed": L.EXIT_FAIL, "needs_human": L.EXIT_NEEDS_HUMAN}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a sprint step or an agent run on disk (outputs, freshness, schemas, gates).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Exit codes: 0 done, 1 failed, 2 usage error, 5 needs a person.")
    ap.add_argument("--sprint", help="sprint folder <project>/growth-sprint/<sprint id>/")
    ap.add_argument("--step", help="step id in sprint.json")
    ap.add_argument("--project", help="project folder (standalone mode, or to override the sprint's)")
    ap.add_argument("--agent", help="agent name (standalone mode)")
    ap.add_argument("--label", help="run label (standalone mode)")
    ap.add_argument("--since", help="ISO 8601: outputs must be newer (standalone mode; default: no freshness check)")
    ap.add_argument("--registry", help="agent registry (default: assets/agents.json)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        registry = L.load_registry(Path(args.registry) if args.registry else None)
        sprint_dir = None
        if args.sprint:
            if not args.step:
                ap.error("--sprint needs --step")
            sprint_dir = Path(args.sprint).resolve()
            project = Path(args.project).resolve() if args.project else sprint_dir.parent.parent
            plan = L.load_json(sprint_dir / "sprint.json")
            step = next((s for s in plan["steps"] if s["id"] == args.step), None)
            if step is None:
                print(f"ERROR unknown step {args.step}", file=sys.stderr)
                return L.EXIT_USAGE
            state = L.load_json(sprint_dir / "state.json") if (sprint_dir / "state.json").is_file() else {"steps": {}}
            ss = state["steps"].get(args.step, {})
            since = L.parse_ts(ss["started_at"]) if ss.get("started_at") else None
            attempt = L.parse_ts(ss["last_started_at"]) if ss.get("last_started_at") else since
        elif args.project and args.agent:
            project = Path(args.project).resolve()
            step = {"id": "s00-standalone", "agent": args.agent, "label": args.label}
            since = L.parse_ts(args.since) if args.since else None
            attempt = since
        else:
            ap.error("give --sprint and --step, or --project and --agent")
            return L.EXIT_USAGE
        if step["agent"] not in registry["agents"]:
            print(f"ERROR agent {step['agent']} is not in the registry", file=sys.stderr)
            return L.EXIT_USAGE
        v = L.verify_step(project, registry, step, since, sprint_dir, attempt)
    except (FileNotFoundError, json.JSONDecodeError, L.Refused, ValueError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return L.EXIT_USAGE
    if args.json:
        print(json.dumps(v, indent=2, ensure_ascii=False))
    else:
        for o in v["outputs"]:
            flag = "OK  " if o["ok"] else "FAIL"
            print(f"{flag} {o['id']:<14} {o['path'] or o['pattern']}: {o['message']}")
        for p in v["pending"]:
            print(f"WAIT [{p['kind']}] {p['reason']}\n     how: {p['how']}")
        if v["result_note"]:
            print(f"NOTE {v['result_note']}")
        print(f"{v['step']} ({v['agent']}): {v['verdict']}: {v['why']}")
    return EXIT_BY_VERDICT[v["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
