#!/usr/bin/env python3
"""collect.py: run every collector of a plan in parallel and store one corpus.

  python3 scripts/collect.py --plan RUN/plan.json --out RUN [--workers 5] [--sequential]
        [--fixtures RUN/fixtures | --record RUN/fixtures] [--seen STATE/seen.json [--since-last-run]] [--only id,id]

plan.json (contract: assets/plan.schema.json) lists the window, the caps and
one job per source and query: {"id", "source", "args"}. source is one of hn,
reddit, stackexchange, discourse, appstore, import. args become the collector's
flags (key some_flag gives --some-flag; a list repeats the flag; true gives a
bare flag). Each job runs as its own process. Sources run in parallel lanes
(one lane per source, its jobs in turn, so no provider gets concurrent
requests); a slow or failing source never blocks the others. --sequential runs
every job one after the other with the same result (the fallback for a host
that cannot run processes in parallel).

Writes into --out:
  corpus/<job>.jsonl, health/<job>.json   one file per job
  corpus.jsonl                            merged, deduplicated by record_id, sorted
  health.json                             status per job (ok, empty, error, quota), its record ids, totals
  manifest.json                           plan hash, window, jobs, commands, fixtures mode

Watch mode: --seen STATE/seen.json drops records already seen in a previous run
(counted as already_seen) and adds the new ids to the file; --since-last-run
starts the window at the end of the last run recorded there. A re-run in the
same run folder (a second wave, --only) keeps the stored corpus.jsonl: its
records are never dropped as already seen, records no job returns again are
kept (kept_from_stored_corpus), and --since-last-run keeps the window of that
run when the last run in --seen is this one.

Exit 0 when the merged corpus has at least one record, 1 when it is empty
(health.json says why), 2 on a usage error or an invalid plan.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

SCRIPTS = Path(__file__).resolve().parent
COLLECTORS = {
    "hn": "collect_hn.py",
    "reddit": "collect_reddit.py",
    "stackexchange": "collect_stackexchange.py",
    "discourse": "collect_discourse.py",
    "appstore": "collect_appstore.py",
    "import": "import_records.py",
}


def job_command(job, window, caps, out: Path, fixtures, record, plan_dir: Path):
    cmd = [sys.executable, str(SCRIPTS / COLLECTORS[job["source"]]),
           "--job-id", job["id"], "--since", window[0], "--until", window[1],
           "--limit", str(job.get("limit", caps.get("records_per_job", 50))),
           "--max-pages", str(job.get("max_pages", caps.get("pages_per_job", 3))),
           "--out", str(out / "corpus" / f"{job['id']}.jsonl"),
           "--health", str(out / "health" / f"{job['id']}.json")]
    for k, v in (job.get("args") or {}).items():
        flag = "--" + k.replace("_", "-")
        if job["source"] == "import" and k == "input" and not Path(str(v)).is_absolute():
            v = str((plan_dir / str(v)).resolve())
        if v is True:
            cmd.append(flag)
        elif v is False or v is None:
            continue
        elif isinstance(v, list):
            for x in v:
                cmd += [flag, str(x)]
        else:
            cmd += [flag, str(v)]
    if fixtures and job["source"] != "import":
        cmd += ["--fixtures", str(Path(fixtures) / job["id"])]
    if record and job["source"] != "import":
        cmd += ["--record", str(Path(record) / job["id"])]
    return cmd


def run_job(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def portable(cmd, out: Path):
    """Command line without the interpreter and absolute paths, for the manifest."""
    res = []
    for c in cmd[1:]:
        if c.startswith(str(SCRIPTS)):
            c = "scripts/" + Path(c).name
        elif c.startswith(str(out)):
            c = "<run>/" + str(Path(c).relative_to(out))
        res.append(c)
    return res


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", required=True, help="plan.json")
    p.add_argument("--out", required=True, help="run folder")
    p.add_argument("--workers", type=int, default=5, help="parallel collector processes (default 5)")
    p.add_argument("--sequential", action="store_true", help="run the jobs one after the other")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--fixtures", help="frozen responses, one subfolder per job id (no network)")
    g.add_argument("--record", help="live run that saves every response, one subfolder per job id")
    p.add_argument("--seen", help="state file of record ids already collected (watch mode)")
    p.add_argument("--since-last-run", action="store_true", help="window starts at the end of the last run in --seen")
    p.add_argument("--only", help="comma-separated job ids to run")
    args = p.parse_args(argv)

    plan_path = Path(args.plan)
    try:
        plan = M.read_json(plan_path)
    except (OSError, ValueError) as e:
        M.eprint(f"collect: cannot read plan: {e}")
        return 2
    errs = M.schema_errors(plan, "plan.schema.json")
    if errs:
        for e in errs:
            M.eprint(f"collect: plan.json: {e}")
        return 2
    seen_state = M.read_json(Path(args.seen)) if args.seen and Path(args.seen).exists() else {"last_until": None, "record_ids": []}
    w = plan.get("window", {})
    since, until = M.window_from(w.get("since"), w.get("until"), plan.get("as_of"), w.get("recency_days"))
    out = Path(args.out)
    stored = {r["record_id"]: r for r in M.read_jsonl(out / "corpus.jsonl")} if args.seen and (out / "corpus.jsonl").exists() else {}
    prev_manifest = M.read_json(out / "manifest.json") if stored and (out / "manifest.json").exists() else {}
    if args.since_last_run:
        if not args.seen or not seen_state.get("last_until"):
            M.eprint("collect: --since-last-run needs a --seen file from a previous run")
            return 2
        since = seen_state["last_until"]
        pw = prev_manifest.get("window") or {}
        if prev_manifest.get("watch") and pw.get("until") == seen_state["last_until"] and pw.get("since"):
            since = pw["since"]
    caps = plan.get("caps", {})
    jobs = [j for j in plan["jobs"] if not args.only or j["id"] in args.only.split(",")]
    ids = [j["id"] for j in jobs]
    if len(set(ids)) != len(ids):
        M.eprint("collect: job ids must be unique")
        return 2
    for d in ("corpus", "health"):
        (out / d).mkdir(parents=True, exist_ok=True)
    cmds = {j["id"]: job_command(j, (since, until), caps, out, args.fixtures, args.record, plan_path.parent) for j in jobs}

    # One lane per source: sources run in parallel, the jobs of one source run in
    # turn, so no provider sees concurrent requests from this run (Arctic Shift
    # answers 422 "slow down" to parallel queries).
    lanes = {}
    for j in jobs:
        lanes.setdefault(j["source"], []).append(j["id"])

    def run_lane(lane_ids):
        return {i: run_job(cmds[i]) for i in lane_ids}

    results = {}
    mode = "sequential" if args.sequential or args.workers <= 1 else "parallel"
    if mode == "parallel":
        try:
            with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
                for fu in cf.as_completed([ex.submit(run_lane, l) for l in lanes.values()]):
                    results.update(fu.result())
        except (OSError, RuntimeError) as e:
            M.eprint(f"collect: parallel run failed ({e}), falling back to sequential")
            mode, results = "sequential", {}
    if mode == "sequential":
        for i in ids:
            results[i] = run_job(cmds[i])

    seen_ids = set(seen_state.get("record_ids") or [])
    merged, dup, already = {}, 0, 0
    jobs_health = []
    # --only re-runs some jobs; the merge still covers every job of the plan
    # whose files are already in the run folder.
    all_ids = [j["id"] for j in plan["jobs"]]
    merge_ids = [i for i in all_ids if i in results or (out / "health" / f"{i}.json").exists()]
    for i in merge_ids:
        code, log = results.get(i, (0, ""))
        if log:
            print(log.splitlines()[-1])
        hpath = out / "health" / f"{i}.json"
        h = M.read_json(hpath) if hpath.exists() else {
            "job_id": i, "source": next(j["source"] for j in plan["jobs"] if j["id"] == i), "status": "error",
            "records": 0, "message": f"collector crashed (exit {code}): {log[-300:]}", "errors": [log[-300:]]}
        cpath = out / "corpus" / f"{i}.jsonl"
        job_rows = M.read_jsonl(cpath) if cpath.exists() else []
        h["record_ids"] = [r["record_id"] for r in job_rows]
        jobs_health.append(h)
        for rec in job_rows:
            if rec["record_id"] in seen_ids and rec["record_id"] not in stored:
                already += 1
                continue
            if rec["record_id"] in merged:
                dup += 1
                continue
            merged[rec["record_id"]] = rec
    kept = 0
    for k, rec in stored.items():
        if k not in merged:
            merged[k] = rec
            kept += 1
    rows = [merged[k] for k in sorted(merged)]
    M.write_jsonl(out / "corpus.jsonl", rows)
    summary = {s: sum(1 for h in jobs_health if h.get("status") == s) for s in M.HEALTH_STATES}
    by_source = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    health = {"window": {"since": since, "until": until}, "mode": mode, "jobs": jobs_health,
              "summary": summary, "records": len(rows), "by_source": dict(sorted(by_source.items())),
              "duplicates_across_jobs": dup, "already_seen": already}
    if args.seen:
        health["kept_from_stored_corpus"] = kept
    M.write_json(out / "health.json", health)
    manifest = {
        "plan": plan_path.name, "plan_sha256": M.sha256_file(plan_path),
        "window": {"since": since, "until": until}, "mode": mode,
        "fixtures": bool(args.fixtures), "watch": bool(args.seen),
        "jobs": [{"id": i, "command": portable(cmds[i], out)} for i in ids],
        "corpus_sha256": M.sha256_file(out / "corpus.jsonl"), "records": len(rows),
        "generated_at": None if args.fixtures else M.now_utc(),
    }
    M.write_json(out / "manifest.json", manifest)
    if args.seen:
        state = {"last_until": until, "record_ids": sorted(seen_ids | set(merged))}
        M.write_json(Path(args.seen), state)
    print(f"collect: {len(rows)} records, jobs ok {summary['ok']}, empty {summary['empty']}, "
          f"error {summary['error']}, quota {summary['quota']} ({mode}); duplicates {dup}, already seen {already}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
