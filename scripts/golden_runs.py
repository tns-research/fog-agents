#!/usr/bin/env python3
"""golden_runs.py: run every agent's offline test suite with no API key in the environment.

Each agent ships frozen fixtures and one offline suite (tests/run_tests.py or
scripts/selftest.py). This script finds them, strips every variable that looks
like a credential (*_KEY, *_TOKEN, *_SECRET, *_PASSWORD, *_API, *_CREDENTIALS)
from the environment, runs each suite from its agent folder and prints one line
per agent. A suite that only passes with a key set is a bug: every external API
in the stack is optional.

Usage:
  python3 scripts/golden_runs.py                 # every agent
  python3 scripts/golden_runs.py --quick         # pass --quick to suites that accept it
  python3 scripts/golden_runs.py --only seo-audit carousel-builder
  python3 scripts/golden_runs.py --json runs.json

Exit codes: 0 all suites pass, 1 at least one suite fails, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"
SHARED_SUITES = [
    ("shared/validate_json", ROOT / "shared" / "scripts" / "tests" / "test_validate_json.py"),
    ("shared/writing-gate", ROOT / "shared" / "skills" / "writing-gate" / "tests" / "run_tests.py"),
]
SECRET_RE = re.compile(r"(_KEY|_TOKEN|_SECRET|_PASSWORD|_API|_CREDENTIALS|_PAT)$|^(OPENAI|ANTHROPIC|EXA|FIRECRAWL|SERP|FAL|META|GOOGLE)_", re.I)
TIMEOUT_S = 900


def find_suite(agent_dir: Path) -> Path | None:
    for rel in ("tests/run_tests.py", "scripts/selftest.py"):
        p = agent_dir / rel
        if p.is_file():
            return p
    return None


def accepts_quick(script: Path) -> bool:
    try:
        out = subprocess.run([sys.executable, str(script), "--help"], cwd=script.parent,
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return re.search(r"\[--quick\]", out) is not None


def clean_env() -> tuple[dict, list[str]]:
    env, stripped = {}, []
    for k, v in os.environ.items():
        if SECRET_RE.search(k):
            stripped.append(k)
        else:
            env[k] = v
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env, sorted(stripped)


def run_suite(name: str, script: Path, cwd: Path, quick: bool, env: dict) -> dict:
    cmd = [sys.executable, str(script)]
    if quick and accepts_quick(script):
        cmd.append("--quick")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
        rc, out = proc.returncode, (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        rc, out = 124, f"timeout after {TIMEOUT_S} s"
    last = out.splitlines()[-1] if out else ""
    return {"suite": name, "path": str(script.relative_to(ROOT)), "rc": rc,
            "seconds": round(time.time() - t0, 1), "summary": last[:160],
            "tail": "\n".join(out.splitlines()[-15:]) if rc else ""}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="pass --quick to suites that support it")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="agent folder names (or shared/...) to run")
    ap.add_argument("--json", metavar="PATH", help="write the results as JSON")
    args = ap.parse_args()

    suites: list[tuple[str, Path, Path]] = [(n, p, ROOT) for n, p in SHARED_SUITES if p.is_file()]
    missing = []
    for d in sorted(AGENTS.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        s = find_suite(d)
        if s:
            suites.append((d.name, s, d))
        else:
            missing.append(d.name)
    if args.only:
        known = {n for n, _, _ in suites}
        unknown = [n for n in args.only if n not in known]
        if unknown:
            print(f"unknown suite(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}", file=sys.stderr)
            return 2
        suites = [s for s in suites if s[0] in args.only]

    env, stripped = clean_env()
    print(f"golden runs: {len(suites)} suite(s), {len(stripped)} credential variable(s) removed from the environment")
    results = []
    for name, script, cwd in suites:
        r = run_suite(name, script, cwd, args.quick, env)
        results.append(r)
        mark = "PASS" if r["rc"] == 0 else "FAIL"
        print(f"  {mark}  {name:<26} {r['seconds']:>6.1f} s  {r['summary']}")
        if r["rc"]:
            print("        " + r["tail"].replace("\n", "\n        "))
    for name in missing:
        print(f"  MISS  {name:<26} no tests/run_tests.py or scripts/selftest.py")
    failed = [r for r in results if r["rc"]]
    if args.json:
        Path(args.json).write_text(json.dumps({"results": results, "missing": missing,
                                               "stripped_vars": len(stripped)}, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(results) - len(failed)}/{len(results)} suites pass" + (f", {len(missing)} agent(s) without a suite" if missing else ""))
    return 1 if failed or missing else 0


if __name__ == "__main__":
    sys.exit(main())
