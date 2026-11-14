#!/usr/bin/env python3
"""build_batch.py: turn a passing spec into the deliverables of a batch.

Runs check_spec.py first and refuses on any error. Then, next to the spec:

  posts.json                      what content-publisher takes as is (its post spec)
  lint.json                       content-publisher's own variants.py lint on posts.json
  check.json                      the report of check_spec.py
  founder-content-<YYYYMMDD>.md   the batch report for the founder
  review/critique-prompt.md       the reviewer prompt of the shared fresh-eyes skill
  review/critique-packet.md       brief, rules, rubric, mechanical results, deliverable

A failing spec leaves no posts.json behind: a stale one is deleted, so a later
step can never pick up a batch that no longer passes. Nothing is queued,
approved or published here.

Usage:
  python3 build_batch.py SPEC.json [--project DIR] [--config config.json] [--queue queue.json] [--brief brief.md]
                         [--critic-reviewer WHO --critic-verdict PASS|FAIL --critic-score N/M
                          --critic-settled TEXT --critic-changed TEXT]

Run it again after the fresh-eyes review with the --critic flags: they fill the
role log of the report and its status.

Exit codes: 0 built, 1 refused (the check or content-publisher's lint failed),
2 usage error or unreadable file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fcw_lib as L  # noqa: E402
import check_spec  # noqa: E402
from check_spec import proof_lib  # noqa: E402

FALLBACK_PROMPT = ("You review a deliverable you did not write. Judge only against the brief, the rules, the rubric and the "
                   "mechanical results below. Return: constraints PASS or FAIL with locations, rubric scores with evidence, "
                   "located problems with a proposed fix, and a PASS or FAIL verdict. Do not rewrite the deliverable.")
LABEL = {"linkedin": "LinkedIn", "x": "X"}


def env() -> Dict[str, str]:
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def publisher_lint(posts: Path, project: Optional[str], queue: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """content-publisher's own command on the file it will receive."""
    cmd = [sys.executable, str(L.PUBLISHER_SCRIPTS / "variants.py"), "lint", str(posts), "--json"]
    if project:
        cmd += ["--project", project]
    real_queue = queue or (str(L.project_paths(project)["queue"]) if project else None)
    with tempfile.TemporaryDirectory(prefix="fcw-lint-") as tmp:
        if real_queue and Path(real_queue).is_file():
            cmd += ["--queue", real_queue]
        elif config.get("x_allow_thread"):
            _, pub_common = L.publisher()
            q = Path(tmp) / "queue.json"
            L.write_json_atomic(q, pub_common.new_queue(settings={"x_allow_thread": True}))
            cmd += ["--queue", str(q)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env())
    if r.returncode not in (0, 1):
        raise L.UsageError("content-publisher's lint failed to run: " + (r.stderr or r.stdout).strip()[-400:])
    report = json.loads(r.stdout)
    report["returncode"] = r.returncode
    return report


def fence(text: str) -> List[str]:
    return ["```text", text.rstrip(), "```"]


def critic_log(a: argparse.Namespace) -> List[str]:
    if not a.critic_reviewer:
        return ["fresh-eyes: reviewer=not run", "verdict: none", "settled by: none", "changed: nothing, deliverable unreviewed"]
    return [f"fresh-eyes: reviewer={a.critic_reviewer}",
            f"verdict: {a.critic_verdict or 'none'}" + (f" (rubric {a.critic_score})" if a.critic_score else ""),
            f"settled by: {a.critic_settled or 'not recorded'}",
            f"changed: {a.critic_changed or 'not recorded'}"]


def batch_status(a: argparse.Namespace, report: Dict[str, Any]) -> str:
    reasons = []
    if not a.critic_reviewer:
        reasons.append("fresh-eyes review not run")
    elif a.critic_verdict != "PASS":
        reasons.append("reviewer verdict FAIL, see the role log")
    if not report["info"]["gate"]["ran"]:
        reasons.append("writing gate manual")
    return "ok" if not reasons else "partial: " + ", ".join(reasons)


def build_report(spec: Dict[str, Any], report: Dict[str, Any], a: argparse.Namespace, run: Path, project: Optional[str],
                 lint: Dict[str, Any]) -> str:
    info = report["info"]
    status = batch_status(a, report)
    addr = info["address"]
    compact = spec["date"].replace("-", "")
    posts_rel = L.relative_to_project(run / "posts.json", project)
    out: List[str] = [
        f"# Founder posts: {spec['project']}, {spec['date']}",
        "",
        f"**Batch:** `{spec['label']}` · **Language:** {spec['language']} · **Audience address:** "
        f"{addr['form'] or 'n/a'} ({addr['origin']}) · **Status:** {status}",
        "",
        spec["summary"].strip(),
        "",
        f"**Next step:** content-publisher takes `{posts_rel}` as is: `python3 agents/content-publisher/scripts/pubqueue.py add "
        f"<project>/{posts_rel} --queue <project>/content-publisher/queue.json --project <project>`, then a person approves each item. "
        "This agent never queues, approves or publishes.",
        "",
        "---",
        "",
        "## 1. Posts",
        "",
    ]
    by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for row in report["passages"]:
        by_ref.setdefault(row["ref"], []).append(row)
    for post in spec["posts"]:
        out += [f"### `{post['ref']}` ({post['hook_type']}, {post['angle_type']}, {post['structure']})", "", f"Angle: {post['angle']}", ""]
        for net in post["networks"]:
            body = post["variants"][net]["text"]
            out += [f"**{LABEL[net]}** ({report['limits'][post['ref']][net]})", ""] + fence(body) + [""]
        if post.get("link"):
            out += [f"Link, placed by content-publisher: {post['link']}", ""]
        out += ["Comes from:", ""]
        for row in by_ref.get(post["ref"], []):
            where = f"{row['source_id']}, line {row['line']}" if row["line"] else f"{row['source_id']}: {row['url']} ({row['date']})"
            out.append(f"- {where}: \"{' '.join(row['passage'].split())}\"")
        out.append("")
    out += ["## 2. Claims ledger", ""]
    if report["ledger"]:
        out += ["| Claim (as written) | Used in | Source |", "|--------------------|---------|--------|"]
        for row in report["ledger"]:
            out.append(f"| {row['claim']} | {row['ref']}: {', '.join(row['used_in'])} | {row['source']} |")
    else:
        out.append("No claims used.")
    out.append("")
    refused = info.get("proof_refused") or []
    if refused:
        out += ["Proof items refused for posts by `shared/scripts/proof.py`, kept out of every post:", ""]
        out += [f"- `positioning.proof[{r['index']}]` {r['id']}: {r['reason']}" for r in refused] + [""]
    dropped = spec.get("dropped") or []
    if dropped:
        out += ["Dropped, because no allowed source covers it. Add it to `positioning.proof` with its source if you want it in a post:", ""]
        for d in dropped:
            out.append(f"- \"{d['text']}\": {d['reason']}" + (f" Fix: {d['fix']}" if d.get("fix") else ""))
        out.append("")
    warnings = [f for f in report["findings"] if f["level"] == "warning"]
    out += ["## 3. Checks", "",
            f"- **Sources:** {len(report['passages'])} passages found word for word in {len(report['sources'])} files with unchanged hashes.",
            f"- **Claims:** {len(report['ledger'])} declared, every number traced ({info['proof_items']} items in `positioning.proof`"
            + (f", {len(refused)} refused" if refused else "") + ").",
            f"- **Writing gate:** {'0 BLOCK' if info['gate']['ran'] else 'manual'}.",
            f"- **Network rules:** content-publisher's `variants.py lint` on `posts.json`: {lint['status']}.",
            f"- **Openings:** compared inside the batch and against {info['past']['compared']} past posts ({'; '.join(info['past']['origins']) or 'none on record'}).",
            f"- **Voice:** {voice_line(info['voice'])}. {info['decisions_applied']} active decisions applied.",
            f"- **Warnings kept:** {len(warnings)}."]
    for f in warnings:
        out.append(f"  - `{f['code']}` {f['where']}: {f['message']}")
    out.append("")
    for sig in report["signals"]:
        if sig["code"] == "injection":
            out.append(f"Instruction found in raw material, ignored: {sig['source_id']}, line {sig['line']}: \"{sig['excerpt'][:100]}\"")
    if any(s["code"] == "injection" for s in report["signals"]):
        out.append("")
    out += ["## 4. Fresh-eyes review", ""] + fence("\n".join(critic_log(a))) + [""]
    out += ["## Methodology", "",
            f"- Providers: copy_lint {'local' if info['gate']['ran'] else 'manual'}, critic {a.critic_reviewer or 'not run'}.",
            f"- Inputs: {', '.join(s['source_id'] + ' (' + s['kind'] + ')' for s in report['sources'])}. "
            f"Project context: {'loaded' if info['project_context'] else 'none'}.",
            f"- Report: `{L.AGENT_NAME}` batch `{spec['label']}-{compact}`.",
            "",
            "## Limitations", ""]
    limits = list(report["limitations"]) + [
        "The scripts prove that a passage exists, that numbers and names trace to a source and that the rules hold. Whether a sentence stays faithful to its passage is the reviewer's and the founder's call.",
    ]
    if not a.critic_reviewer:
        limits.insert(0, "Fresh-eyes review: not run. This batch is unreviewed.")
    out += [f"- {x}" for x in limits]
    return "\n".join(out) + "\n"


def voice_line(voice: Dict[str, Any]) -> str:
    if voice.get("status") != "pack":
        return "no voice pack"
    return (f"voice pack, {voice['rules']} rules: {len(voice['by_gate'])} through the gate, {len(voice['by_script'])} measured by script, "
            f"{len(voice['by_reviewer'])} left to the reviewer")


def reviewer_prompt() -> str:
    if L.FRESH_EYES_SKILL.is_file():
        m = re.search(r"## 3\. Reviewer prompt.*?```text\n(.*?)```", L.FRESH_EYES_SKILL.read_text(encoding="utf-8"), re.S)
        if m:
            return m.group(1).strip() + "\n"
    return FALLBACK_PROMPT + "\n"


def build_packet(spec: Dict[str, Any], report: Dict[str, Any], run: Path, project: Optional[str], brief: Optional[str], lint: Dict[str, Any]) -> str:
    paths = L.project_paths(project)
    brief_path = Path(brief) if brief else run / "brief.md"
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else "No brief recorded for this batch: judge against the rules below."
    context, _ = L.read_optional_json(paths["context"])
    voice, _ = L.read_optional_json(paths["voice"])
    claims_policy = ((context or {}).get("voice") or {}).get("claims_policy") if isinstance(context, dict) else None
    proof = [proof_lib.proof_text(p) for p in proof_lib.load_proof(context)]
    refused = {r["index"]: r["reason"] for r in (report.get("info") or {}).get("proof_refused") or []}
    decisions = L.active_decisions(paths["decisions"])
    out: List[str] = ["# Critique packet", "", "## 1. Brief", "", brief_text.strip(), "", "## 2. Rules", "",
                      L.HARD_RULES.read_text(encoding="utf-8").strip(), "",
                      "### Claims policy of the project", "", claims_policy or "no invented stats, every metric must trace to a URL or be omitted", ""]
    out += ["### positioning.proof", ""] + ([f"{i}. {p}" + (f" (refused, may not be used: {refused[i]})" if i in refused else "")
                                             for i, p in enumerate(proof)] if proof else ["Empty: no number may appear in a post."]) + [""]
    out += ["### Decisions of the project", ""] + ([f"- {d['id']} ({d['status']}): {d['rule']}" for d in decisions] or ["None."]) + [""]
    out += ["### Voice rules", ""]
    if isinstance(voice, dict) and voice.get("rules"):
        out += [f"- {r.get('rule', '')} (measured: {r.get('evidence', '')})" for r in voice["rules"] if isinstance(r, dict)]
    else:
        out.append("No voice pack: judge against the raw material, the founder's own words.")
    out += ["", "## 3. Rubric", "", L.RUBRIC.read_text(encoding="utf-8").strip(), "", "## 4. Mechanical results", "",
            f"check_spec.py: {report['status']}, {report['counts']['error']} errors, {report['counts']['warning']} warnings. "
            f"content-publisher lint: {lint['status']}.", ""]
    out += [f"- {f['level']} `{f['code']}` {f['where']}: {f['message']}" for f in report["findings"]]
    out += ["", "### Claims ledger", ""] + ([f"- {r['ref']}: \"{r['claim']}\" from {r['source']}" for r in report["ledger"]] or ["No claims used."])
    out += ["", "## 5. Deliverable", ""]
    by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for row in report["passages"]:
        by_ref.setdefault(row["ref"], []).append(row)
    for post in spec["posts"]:
        out += [f"### {post['ref']}", "", f"Angle: {post['angle']}. Hook type: {post['hook_type']}.", ""]
        out += ["Source passages:", ""] + [f"- {r['source_id']}: \"{' '.join(r['passage'].split())}\"" for r in by_ref.get(post["ref"], [])] + [""]
        for net in post["networks"]:
            out += [f"{LABEL[net]}:", ""] + fence(post["variants"][net]["text"]) + [""]
    return "\n".join(out) + "\n"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--project")
    ap.add_argument("--config")
    ap.add_argument("--queue")
    ap.add_argument("--brief", help="the founder's request, verbatim (default: brief.md next to the spec)")
    ap.add_argument("--critic-reviewer", help="subagent, blank session, <model> CLI, founder")
    ap.add_argument("--critic-verdict", choices=("PASS", "FAIL"))
    ap.add_argument("--critic-score", help="rubric total, for example 11/12")
    ap.add_argument("--critic-settled", help="hard check, written constraint or reasoned taste, per point")
    ap.add_argument("--critic-changed", help="what the revision changed")
    a = ap.parse_args(argv)
    spec_path = Path(a.spec)
    run = spec_path.parent
    posts_path = run / "posts.json"
    try:
        config = check_spec.load_config(a.config, a.project)
        report = check_spec.check(spec_path, a.project, config, a.queue, gate=True)
        L.write_json_atomic(run / "check.json", report)
        if report["status"] != "pass":
            posts_path.unlink(missing_ok=True)
            print(a.spec)
            check_spec.print_report(report)
            print("\nRefused: posts.json not written. Fix the spec (each finding names the post and the network), then run this again.")
            return L.EXIT_CHECK
        spec = L.read_json(spec_path)
        compiled = L.compile_posts(spec, L.relative_to_project(spec_path, a.project))
        L.write_json_atomic(posts_path, compiled)
        lint = publisher_lint(posts_path, a.project, a.queue, config)
        L.write_json_atomic(run / "lint.json", lint)
        if lint["returncode"] != 0:
            posts_path.unlink(missing_ok=True)
            for f in lint["findings"]:
                if f["level"] == "error":
                    print(f"  ERROR {f['code']} {f['where']}: {f['message']}")
            print("\nRefused: content-publisher's lint rejects this batch, posts.json removed.")
            return L.EXIT_CHECK
        compact = spec["date"].replace("-", "")
        report_path = run / f"founder-content-{compact}.md"
        report_path.write_text(build_report(spec, report, a, run, a.project, lint), encoding="utf-8")
        (run / "review").mkdir(exist_ok=True)
        (run / "review" / "critique-prompt.md").write_text(reviewer_prompt(), encoding="utf-8")
        (run / "review" / "critique-packet.md").write_text(build_packet(spec, report, run, a.project, a.brief, lint), encoding="utf-8")
    except L.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return L.EXIT_USAGE
    print(f"built {posts_path} ({len(compiled['posts'])} posts), {report_path}, review/critique-packet.md")
    print(f"status: {batch_status(a, report)}; warnings: {report['counts']['warning']}")
    for item in report["limitations"]:
        print(f"  LIMIT {item}")
    return L.EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
