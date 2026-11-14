#!/usr/bin/env python3
"""
check_report.py

Gate on the growth-pulse report: every number in the prose and the tables exists in
pulse.json (or in the experiments handoff), every percentage is one the script
computed (so none was computed on a small volume), correlations are written as
correlations and never as causes, and the required sections are there. Same idea as
a claims check, applied to numbers: the model writes, this script decides whether a
figure may stand.

    python3 check_report.py <project>/growth-pulse/growth-pulse-20261014.md --pulse <run>/pulse.json \\
        --experiments <project>/growth-pulse/experiments-20261014.json
    python3 check_report.py report.md --pulse pulse.json --json > report-check.json

How a number is read: digits with an optional sign, thousands commas, decimals and a
k suffix. It matches a value of pulse.json or of the experiments file when they are
equal at the precision written (7.1 matches 7.14; 14.4k matches 14365). A number
followed by %, pts, points or pp must match a percentage field (pct, pp, a rate value).
Not read: dates (2026-10-05), ISO weeks (2026-W41), times, experiment ids
(E-20261014-1), correlation ids (C5), URLs, HTML comments, fenced code, inline code
spans, markdown list markers.

Codes (BLOCK unless noted):
  unknown-number         a number that is in neither file
  unknown-percent        a percentage or a points change that the script did not compute
  number-in-code         a figure hidden in an inline code span
  causal-claim           causal wording (because, drove, led to, thanks to, due to,
                         boosted, resulted in...) outside the experiments section, in a
                         sentence that does not negate it
  unlabeled-correlation  a line citing r = or a correlation id without the word correlation
  missing-section        a required heading is absent
  missing-experiment     an experiment of the handoff or of last run's follow-up is not named
  notable-not-mentioned  WARN: a notable metric of pulse.json is not named in the report
  decline-not-mentioned  WARN: Search Console declined and the report never says decline

Exit codes: 0 no BLOCK, 1 at least one BLOCK, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

REQUIRED = ["summary", "source health", "this week by stage", "what moved", "search console", "correlations",
            "last run's experiments", "next sprint", "methodology", "limitations"]
EXPERIMENTS_SECTION = "next sprint"

STRIP_RES = [
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r"https?://\S+"),
    re.compile(r"\]\([^)]*\)"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{4}-W\d{2}\b"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\bE-\d{8}-\d+\b"),
]
NUM_RE = re.compile(
    r"(?<![\w.#/:@])(?<![A-Za-z0-9]-)(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(k\b)?"
    r"(\s*(?:%|percent\b|pts\b|points?\b|pp\b|percentage points?\b))?",
    re.I)
CAUSAL_RE = re.compile(
    r"\b(because|caused|causes|causing|drove|drives|driving|driven by|led to|leads to|leading to|thanks to|due to|"
    r"resulted in|results in|resulting in|as a result|boosted|boosts|triggered|triggers|explains|explained by|"
    r"responsible for|attributable to|attributed to|owing to|paid off|worked)\b", re.I)
NEGATION_RE = re.compile(r"\b(not|never|no|cannot|can't|doesn't|don't|isn't|without)\b", re.I)
CORR_REF_RE = re.compile(r"\br\s*=\s*[-+]?\d|\bC\d+\b")
LIST_MARKER_RE = re.compile(r"^(\s*(?:#+\s*)?)\d+[.)]\s")
CODE_SPAN_RE = re.compile(r"`([^`\n]*)`")
NUMERIC_CODE_RE = re.compile(r"^[\s\d.,%+\-]+$")


# ------------------------------------------------------------------ allowed values

def walk(obj: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[Tuple[str, ...], Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, path + (str(k),))
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, path)
    else:
        yield path, obj


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def allowed_values(pulse: Dict[str, Any], experiments: Optional[Dict[str, Any]]) -> Tuple[Set[float], Set[float]]:
    """(every number, the numbers that are percentages or points)."""
    nums: Set[float] = set()
    pcts: Set[float] = set()
    for path, v in walk(pulse):
        if is_num(v):
            nums.add(abs(float(v)))
            if path and (path[-1].endswith("pct") or path[-1] == "pp"):
                pcts.add(abs(float(v)))
    rate_ids = set()
    for m in pulse.get("metrics", []):
        if m.get("kind") != "rate":
            continue
        rate_ids.add(m["id"])
        for k in ("current", "previous", "baseline"):
            if is_num(m.get(k)):
                pcts.add(abs(float(m[k])))
        for s in m.get("series", []):
            if is_num(s.get("value")):
                pcts.add(abs(float(s["value"])))
        for c in ("vs_previous", "vs_baseline"):
            if is_num(m[c].get("noise_band")):
                pcts.add(abs(float(m[c]["noise_band"])))
    for e in pulse.get("experiments_followup", []):
        if e.get("metric") in rate_ids:
            for v in (e.get("observed"), e.get("baseline"), e.get("threshold", {}).get("value")):
                if is_num(v):
                    pcts.add(abs(float(v)))
    # numbers the scripts wrote inside sentences (limitations, health messages, notes)
    texts = list(pulse.get("limitations", [])) + [(pulse.get("gsc") or {}).get("note", "")]
    for src in pulse.get("sources", []):
        texts += [src.get("message", "")] + list(src.get("notes", []))
    for t in texts:
        for m in NUM_RE.finditer(clean_line(t)[0]):
            nums.add(float(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else "")))
    for c in pulse.get("correlations", []):
        if is_num(c.get("r")):
            nums.add(abs(float(c["r"])))
    if experiments:
        for path, v in walk(experiments):
            if is_num(v):
                nums.add(abs(float(v)))
        for e in experiments.get("experiments", []):
            unit = str(e.get("success_threshold", {}).get("unit", "")).lower()
            rate = e.get("metric", {}).get("id") in rate_ids
            if rate or "%" in unit or "pt" in unit or "point" in unit or "percent" in unit:
                for v in (e["success_threshold"].get("value"), e.get("baseline", {}).get("value"),
                          e.get("readout", {}).get("noise_band_per_week")):
                    if is_num(v):
                        pcts.add(abs(float(v)))
    return nums, pcts


def matches(token: float, decimals: int, kilo: bool, pool: Set[float]) -> bool:
    for v in pool:
        x = v / 1000.0 if kilo else v
        if abs(round(x, decimals) - token) < 1e-9:
            return True
        if decimals == 0 and not kilo and abs(x - token) < 1e-9:
            return True
    return False


# ------------------------------------------------------------------ reading the report

def clean_line(line: str) -> Tuple[str, List[str]]:
    """Line without the regions never read; returns the inline code spans separately."""
    spans = CODE_SPAN_RE.findall(line)
    line = CODE_SPAN_RE.sub(" ", line)
    for rx in STRIP_RES:
        line = rx.sub(" ", line)
    line = LIST_MARKER_RE.sub(r"\1", line)
    return line, spans


def sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def check(report: str, pulse: Dict[str, Any], experiments: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nums, pcts = allowed_values(pulse, experiments)
    findings: List[Dict[str, Any]] = []

    def add(level, code, line_no, match, message):
        findings.append({"level": level, "code": code, "line": line_no, "match": match, "message": message})

    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), report, flags=re.S)
    lines = text.split("\n")
    section = ""
    headings: List[str] = []
    in_fence = False
    for i, raw in enumerate(lines, 1):
        if raw.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        h = re.match(r"^##\s+(.+?)\s*$", raw)
        if h and not raw.startswith("###"):
            section = h.group(1).strip().lower()
            headings.append(section)
        line, spans = clean_line(raw)
        for sp in spans:
            if re.search(r"\d", sp) and NUMERIC_CODE_RE.match(sp):
                add("BLOCK", "number-in-code", i, sp, "write figures as plain text so the check can read them")
        for m in NUM_RE.finditer(line):
            whole, dec, kilo, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
            value = float(whole.replace(",", "") + ("." + dec if dec else ""))
            decimals = len(dec) if dec else 0
            if suffix:
                if not matches(value, decimals, bool(kilo), pcts):
                    add("BLOCK", "unknown-percent", i, m.group(0).strip(),
                        "not a percentage of pulse.json: under the volume threshold write counts, never a computed percentage")
            elif not matches(value, decimals, bool(kilo), nums):
                add("BLOCK", "unknown-number", i, m.group(0).strip(), "not in pulse.json nor in the experiments file")
        if raw.lstrip().startswith(("|", ">")):
            continue
        if CORR_REF_RE.search(line + " " + " ".join(spans)) and not re.search(r"correlat", raw, re.I):
            add("BLOCK", "unlabeled-correlation", i, CORR_REF_RE.search(line + " " + " ".join(spans)).group(0),
                "say 'correlation' on the line that cites it")
        if section.startswith(EXPERIMENTS_SECTION):
            continue
        for s in sentences(line):
            c = CAUSAL_RE.search(s)
            if c and not NEGATION_RE.search(s):
                add("BLOCK", "causal-claim", i, c.group(0),
                    "pulse.json shows what moved together, not why: write 'in the same week', 'moved with', or turn it into an experiment")
    for req in REQUIRED:
        if not any(h.startswith(req) for h in headings):
            add("BLOCK", "missing-section", None, f"## {req}", "the template's section is missing")
    low = report.lower()
    ids = [e["id"] for e in pulse.get("experiments_followup", [])]
    if experiments:
        ids += [e["id"] for e in experiments.get("experiments", [])]
    for eid in ids:
        if eid not in report:
            add("BLOCK", "missing-experiment", None, eid, "every experiment followed up or proposed is named in the report")
    labels = {m["id"]: m["label"] for m in pulse.get("metrics", [])}
    for mid in pulse.get("notable", []):
        if labels.get(mid, mid).lower() not in low and mid not in report:
            add("WARN", "notable-not-mentioned", None, labels.get(mid, mid), "a notable move of pulse.json is not named")
    g = pulse.get("gsc") or {}
    if g.get("available") and (g.get("totals") or {}).get("decline") and "decline" not in low:
        add("WARN", "decline-not-mentioned", None, "decline", "Search Console totals declined by the shared definition")
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check that every number of the growth-pulse report comes from pulse.json, and that correlations are not written as causes.")
    ap.add_argument("report", help="the report markdown")
    ap.add_argument("--pulse", required=True, help="pulse.json of the run")
    ap.add_argument("--experiments", help="experiments-<YYYYMMDD>.json handoff, when written")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    args = ap.parse_args(argv)
    try:
        with open(args.report, "r", encoding="utf-8") as f:
            report = f.read()
        pulse = G.read_json(args.pulse)
        exps = G.read_json(args.experiments) if args.experiments else None
    except (OSError, G.InputError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = check(report, pulse, exps)
    blocks = [f for f in findings if f["level"] == "BLOCK"]
    status = "fail" if blocks else "pass"
    if args.json:
        print(json.dumps({"status": status, "file": os.path.basename(args.report), "block": len(blocks),
                          "warn": len(findings) - len(blocks), "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            where = f"line {f['line']}" if f["line"] else "report"
            print(f"{f['level']} {f['code']} {where}: {f['match']!r}: {f['message']}")
        print(f"check_report: {status}, {len(blocks)} BLOCK, {len(findings) - len(blocks)} WARN")
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
