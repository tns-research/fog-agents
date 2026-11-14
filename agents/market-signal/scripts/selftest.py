#!/usr/bin/env python3
"""selftest.py: offline regression test of the market-signal scripts (no network, stdlib only).

  python3 scripts/selftest.py [--keep DIR] [--only NAME[,NAME]]

Checks, each on frozen fixtures:
  help        every script answers --help with exit 0
  collectors  each collector on recorded responses (fictional content): ok (App
              Store), error (closed Stack Exchange site, non-Discourse host), quota
              (Arctic Shift "slow down", synthetic HTTP 429 on HN), and the import
              of a CSV export and of the April Exa output (no text, no date: dropped)
  collect     the reference run replayed from its fixtures, in parallel and in
              sequence: corpus.jsonl byte-identical to the committed one, same
              health per job; watch mode (--seen) drops what was already seen,
              and a re-run in the same run folder keeps its corpus and window
  april       the April 2026 quotes against their scrapes (rebuilt on fictional
              articles): every one blocks with the expected codes (2018 and 2020
              texts in a 90-day window, recapitalised, elided, absent); the V2
              citation passes and returns the original curly apostrophes
  verify      synthetic cases: no date, unknown record, metadata mismatch,
              removed text, short and mid-word warnings
  signals     compute_signals on both reference runs equals the committed
              stats.json; one author posting twice counts once
  diff        diff_runs equals the committed changes.json
  handoff     build_handoff rebuilds the committed sidecar and report byte for
              byte; it refuses a spec citing an April quote and writes nothing;
              --speakers reaches stats.json and the sidecar, an unknown one exits 2
  sidecar     the committed sidecar validates; six mutations each fail with
              the expected check (corpus, window, verbatim, prose, ids, schema)
  privacy     no fixture or corpus under examples/ holds an email, a profile
              link or a handle that is not a pseudonym; scrub() pseudonymises
              a handle in its field and in the text, and a live record and its
              replayed fixture get the same author_hash

Exit 0 when all hold, 1 otherwise. Work happens in a temporary folder (or --keep DIR).
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
FIX = SCRIPTS / "fixtures"
EX = AGENT / "examples" / "swanbase-preseed-fundraising-20261012"
CUR, PREV = EX / "runs" / "20261012", EX / "runs" / "20260713"
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))


def run(*args, cwd=None):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=cwd)
    if "Traceback" in r.stderr:
        print(r.stderr[-2000:])
    return r


def t_help(tmp):
    for s in sorted(SCRIPTS.glob("*.py")):
        if s.name in ("mslib.py", "selftest.py"):
            continue
        r = run(s, "--help")
        check(f"help {s.name}", r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:])


def collector(tmp, script, fixtures, *args):
    out = tmp / f"{Path(fixtures).name}.jsonl"
    r = run(SCRIPTS / script, *args, "--out", out, "--fixtures", fixtures)
    health = json.loads(out.with_suffix(".health.json").read_text(encoding="utf-8"))
    rows = M.read_jsonl(out)
    return r.returncode, health, rows


def t_collectors(tmp):
    code, h, rows = collector(tmp, "collect_appstore.py", FIX / "appstore-ok", "--app-id", "9990000002", "--country", "fr",
                              "--app-name", "Comptoir Pro", "--since", "2026-09-01", "--until", "2026-10-12", "--limit", "3", "--max-pages", "3")
    errs = [e for r in rows for e in M.schema_errors(r, "record.schema.json")]
    check("collector appstore ok", code == 0 and h["status"] == "ok" and len(rows) == 3 and h["capped"] and not errs
          and all(r["rating"] in range(1, 6) for r in rows), f"{code} {h['status']} {len(rows)} {errs[:2]}")
    code, h, rows = collector(tmp, "collect_stackexchange.py", FIX / "se-closed-site", "--site", "startups", "--query", "investors",
                              "--since", "2026-07-14", "--until", "2026-10-12", "--limit", "5")
    check("collector stackexchange error (closed site)", code == 1 and h["status"] == "error" and "No site found" in h["errors"][0], h)
    code, h, rows = collector(tmp, "collect_discourse.py", FIX / "discourse-not-found", "--host", "community.nocode.example",
                              "--query", "funding", "--since", "2026-07-14", "--until", "2026-10-12", "--limit", "5")
    check("collector discourse error (not Discourse)", code == 1 and h["status"] == "error" and "404" in h["errors"][0], h)
    code, h, rows = collector(tmp, "collect_reddit.py", FIX / "reddit-throttled", "--subreddit", "ycombinator", "--query", "raise",
                              "--since", "2026-04-15", "--until", "2026-07-13", "--limit", "8")
    check("collector reddit quota (archive asks to slow down)", code == 1 and h["status"] == "quota", h)
    # Synthetic 429 for HN, written here and never committed.
    hn_fx = tmp / "hn-429"
    hn_fx.mkdir()
    url = ("https://hn.algolia.com/api/v1/search?" + M.qs({
        "query": "pre-seed", "tags": "comment",
        "numericFilters": f"created_at_i>={M.to_unix('2026-07-14')},created_at_i<{M.to_unix('2026-10-12', True)}",
        "hitsPerPage": 15, "page": 0, "advancedSyntax": "true", "typoTolerance": "false"}))
    M.write_json(hn_fx / M._fixture_name(url), {"url": url, "status": 429, "fetched_at": None, "body": {"message": "synthetic"}})
    code, h, rows = collector(tmp, "collect_hn.py", hn_fx, "--query", "pre-seed", "--tags", "comment",
                              "--since", "2026-07-14", "--until", "2026-10-12", "--limit", "5")
    check("collector hn quota (synthetic 429)", code == 1 and h["status"] == "quota", h)
    out = tmp / "import-csv.jsonl"
    r = run(SCRIPTS / "import_records.py", "--input", FIX / "import" / "synthetic-reviews.csv", "--format", "csv",
            "--source", "g2", "--since", "2026-07-14", "--until", "2026-10-12", "--out", out)
    h = json.loads(out.with_suffix(".health.json").read_text(encoding="utf-8"))
    rows = M.read_jsonl(out)
    check("import csv: dated rows in window kept, undated and old rows dropped",
          r.returncode == 0 and len(rows) == 2 and h.get("dropped_incomplete") == 1 and h["dropped_out_of_window"] == 1
          and all(x["kind"] == "review" for x in rows), h)
    out = tmp / "import-exa.jsonl"
    r = run(SCRIPTS / "import_records.py", "--input", FIX / "import" / "exa-april-q0.txt", "--format", "exa-json",
            "--since", "2026-01-28", "--until", "2026-04-28", "--out", out)
    h = json.loads(out.with_suffix(".health.json").read_text(encoding="utf-8"))
    check("import exa-json (April output, no text no date): empty", r.returncode == 0 and h["status"] == "empty"
          and h.get("dropped_incomplete") == 2, h)


def t_collect(tmp):
    want = (CUR / "corpus.jsonl").read_bytes()
    committed = {j["job_id"]: (j["status"], j["records"], j["capped"], j["record_ids"])
                 for j in json.loads((CUR / "health.json").read_text(encoding="utf-8"))["jobs"]}
    for mode in ("parallel", "sequential"):
        out = tmp / f"collect-{mode}"
        args = [SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", out, "--fixtures", CUR / "fixtures"]
        r = run(*args, *(["--sequential"] if mode == "sequential" else []))
        got = {j["job_id"]: (j["status"], j["records"], j["capped"], j["record_ids"])
               for j in json.loads((out / "health.json").read_text(encoding="utf-8"))["jobs"]}
        check(f"collect {mode}: corpus identical to the committed run", r.returncode == 0 and (out / "corpus.jsonl").read_bytes() == want,
              r.stdout[-500:])
        check(f"collect {mode}: same health per job", got == committed,
              {k: (got.get(k), v) for k, v in committed.items() if got.get(k) != v})
    seen = tmp / "state" / "seen.json"
    a = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch1", "--fixtures", CUR / "fixtures", "--seen", seen)
    b = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch2", "--fixtures", CUR / "fixtures", "--seen", seen)
    h2 = json.loads((tmp / "watch2" / "health.json").read_text(encoding="utf-8"))
    st = json.loads(seen.read_text(encoding="utf-8"))
    check("collect --seen: a second pass keeps nothing already seen", a.returncode == 0 and b.returncode == 1
          and h2["records"] == 0 and h2["already_seen"] >= 65 and st["last_until"] == "2026-10-12" and len(st["record_ids"]) == 65,
          {k: h2[k] for k in ("records", "already_seen")})
    c = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch3", "--fixtures", CUR / "fixtures",
            "--seen", seen, "--since-last-run")
    h3 = json.loads((tmp / "watch3" / "health.json").read_text(encoding="utf-8"))
    check("collect --since-last-run starts at the last run's end", h3["window"]["since"] == "2026-10-12", h3["window"])
    same = tmp / "state" / "seen-same.json"
    a = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch-same", "--fixtures", CUR / "fixtures", "--seen", same)
    b = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch-same", "--fixtures", CUR / "fixtures", "--seen", same)
    h4 = json.loads((tmp / "watch-same" / "health.json").read_text(encoding="utf-8"))
    check("collect --seen: a re-run in the same run folder keeps the stored corpus",
          a.returncode == 0 and b.returncode == 0 and h4["records"] == 65 and h4["already_seen"] == 0
          and (tmp / "watch-same" / "corpus.jsonl").read_bytes() == want, {k: h4[k] for k in ("records", "already_seen")})
    c = run(SCRIPTS / "collect.py", "--plan", CUR / "plan.json", "--out", tmp / "watch-same", "--fixtures", CUR / "fixtures",
            "--seen", same, "--since-last-run", "--only", "hn-pre-seed")
    h5 = json.loads((tmp / "watch-same" / "health.json").read_text(encoding="utf-8"))
    check("collect --seen --since-last-run --only: a second wave in the same run folder keeps its window and corpus",
          c.returncode == 0 and h5["records"] == 65 and h5["window"] == h4["window"]
          and (tmp / "watch-same" / "corpus.jsonl").read_bytes() == want, {k: h5[k] for k in ("records", "window")})


APRIL = {
    "q_a01": ["out-of-window"], "q_a02": ["not-found"], "q_a03": ["elided", "not-found"],
    "q_a04": ["out-of-window"], "q_a06": ["elided", "not-found", "out-of-window"],
    "q_a07": ["case-changed"], "q_a08": ["out-of-window"], "q_a09": ["elided", "case-changed", "out-of-window"],
    "q_a10": ["not-found"], "q_a11": ["no-record"], "q_fix": [],
}


def t_april(tmp):
    out = tmp / "april-check.json"
    r = run(SCRIPTS / "verify_quotes.py", "--corpus", FIX / "april-2026" / "corpus.jsonl",
            "--quotes", FIX / "april-2026" / "citations.json", "--out", out)
    rep = json.loads(out.read_text(encoding="utf-8"))
    got = {i["quote_id"]: i["codes"] for i in rep["items"]}
    check("april: verify_quotes exits 1 (BLOCK)", r.returncode == 1, r.stdout[-300:])
    check("april: every quote has the expected codes", got == APRIL, {k: (got.get(k), v) for k, v in APRIL.items() if got.get(k) != v})
    fix = next(i for i in rep["items"] if i["quote_id"] == "q_fix")
    check("april: the V2 citation returns the original text", fix["text_verbatim"] == "Theory doesn’t help at this stage. Templates don’t help.",
          fix.get("text_verbatim"))


def t_verify(tmp):
    import verify_quotes as V
    rows = [
        M.make_record(source="manual", native_id="a", community="c", kind="post", url="https://example.com/a", author="x",
                      created="2026-09-01", text="We never hear back after the intro call, ever."),
        M.make_record(source="manual", native_id="b", community="c", kind="post", url="https://example.com/b", author="y",
                      created=None, text="No date on this one."),
        M.make_record(source="manual", native_id="c", community="c", kind="comment", url="https://example.com/c", author="z",
                      created="2026-09-02", text="[removed]"),
    ]
    quotes = [
        {"quote_id": "q_ok", "record_id": "manual:a", "passage": "We never hear back after the intro call"},
        {"quote_id": "q_nodate", "record_id": "manual:b", "passage": "No date on this one."},
        {"quote_id": "q_unknown", "record_id": "manual:zz", "passage": "anything"},
        {"quote_id": "q_meta", "record_id": "manual:a", "passage": "intro call", "permalink": "https://example.com/other"},
        {"quote_id": "q_removed", "record_id": "manual:c", "passage": "[removed]"},
        {"quote_id": "q_mid", "record_id": "manual:a", "passage": "ever hear back after"},
    ]
    rep = V.verify(quotes, rows, "2026-07-14", "2026-10-12")
    it = {i["quote_id"]: i for i in rep["items"]}
    check("verify: a clean passage passes", it["q_ok"]["status"] == "pass" and not it["q_ok"]["warnings"], it["q_ok"])
    check("verify: a record without date blocks (no-date)", it["q_nodate"]["codes"] == ["no-date"], it["q_nodate"])
    check("verify: an unknown record blocks", it["q_unknown"]["codes"] == ["record-not-in-corpus"], it["q_unknown"])
    check("verify: a stated permalink that differs blocks", "metadata-mismatch" in it["q_meta"]["codes"]
          and "short" in it["q_meta"]["warnings"], it["q_meta"])
    check("verify: a removed text blocks", "removed" in it["q_removed"]["codes"], it["q_removed"])
    check("verify: a passage cut inside a word warns", it["q_mid"]["status"] == "pass" and "mid-word" in it["q_mid"]["warnings"], it["q_mid"])


def t_signals(tmp):
    for run_dir in (PREV, CUR):
        out = tmp / f"stats-{run_dir.name}.json"
        r = run(SCRIPTS / "compute_signals.py", "--corpus", run_dir / "corpus.jsonl", "--labels", run_dir / "labels.jsonl",
                "--analysis", run_dir / "analysis.json", "--run", run_dir, "--out", out)
        got = json.loads(out.read_text(encoding="utf-8"))
        want = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
        got["inputs"]["corpus"] = want["inputs"]["corpus"] = None
        check(f"signals {run_dir.name}: equal to the committed stats.json", r.returncode == 0 and got == want, r.stderr[-300:])
    prev = json.loads((PREV / "stats.json").read_text(encoding="utf-8"))
    acc = next(p for p in prev["pains"] if p["pain_id"] == "pain_investor_access")
    import collect_hn
    check("privacy: HN job-seeker threads are never collected",
          collect_hn.is_job_seeker_post({"story_title": "Ask HN: Who wants to be hired? (October 2026)"})
          and not collect_hn.is_job_seeker_post({"story_title": "Ask HN: How did you raise your pre-seed?"}), "")
    check("signals: one author posting twice counts once", acc["voices"] == acc["distinct_authors"] + 1, acc)
    cur = json.loads((CUR / "stats.json").read_text(encoding="utf-8"))
    check("signals: a pain fed by a capped collector has an unknown trend and a lower-bound volume",
          all((p["trend"] == "unknown") == (p["volume"] == "lower_bound") for p in cur["pains"]), cur["pains"])


def t_diff(tmp):
    r = run(SCRIPTS / "diff_runs.py", "--previous", PREV, "--current", CUR, "--out-json", tmp / "changes.json", "--out-md", tmp / "changes.md")
    got = json.loads((tmp / "changes.json").read_text(encoding="utf-8"))
    want = json.loads((CUR / "changes.json").read_text(encoding="utf-8"))
    check("diff: equal to the committed changes.json", r.returncode == 0 and got == want)
    check("diff: new, rising, disappeared and newly escalated pains",
          got["summary"]["new"] == ["pain_vc_misalignment", "pain_intro_black_box"] and got["summary"]["rising"] == ["pain_traction_bar"]
          and got["summary"]["disappeared"] == ["pain_founder_salary"] and got["newly_escalated"] == ["pain_traction_bar"], got["summary"])
    check("diff: a collector back from quota is reported", any(s["job_id"] == "reddit-ycombinator-raise" and s["previous"] == "quota"
                                                                for s in got["sources"]), got["sources"])


def t_handoff(tmp):
    ex = tmp / "example"
    shutil.copytree(EX, ex, ignore=shutil.ignore_patterns("fixtures"))
    for f in ("market-signal-20261012.json", "market-signal-20261012.md"):
        (ex / f).unlink()
    r = run(SCRIPTS / "build_handoff.py", "--run", ex / "runs" / "20261012")
    same = all((ex / f).exists() and (ex / f).read_bytes() == (EX / f).read_bytes()
               for f in ("market-signal-20261012.json", "market-signal-20261012.md"))
    check("handoff: rebuilds the committed sidecar and report byte for byte", r.returncode == 0 and same, r.stdout[-800:])
    bad = ex / "runs" / "20261012"
    an = json.loads((bad / "analysis.json").read_text(encoding="utf-8"))
    an["quotes"].append({"quote_id": "q_april", "record_id": "reddit:t1_fictive48", "passage": "Mentors who never shipped anything"})
    an["summary"] += " Roughly 40% of founders say so."
    (bad / "analysis.json").write_text(json.dumps(an), encoding="utf-8")
    for f in ("market-signal-20261012.json", "market-signal-20261012.md"):
        (ex / f).unlink()
    r = run(SCRIPTS / "build_handoff.py", "--run", bad)
    check("handoff: refuses an unverifiable quote and a number in the summary, writes nothing",
          r.returncode == 1 and "q_april" in r.stdout and "40%" in r.stdout and not (ex / "market-signal-20261012.json").exists(),
          r.stdout[-800:])
    t_handoff_speakers(tmp / "speakers")


def t_handoff_speakers(tmp):
    tmp.mkdir()
    ex = tmp / "example"
    shutil.copytree(EX, ex, ignore=shutil.ignore_patterns("fixtures"))
    run_dir = ex / "runs" / "20261012"
    r = run(SCRIPTS / "build_handoff.py", "--run", run_dir, "--speakers", "user")
    st = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
    sc = json.loads((ex / "market-signal-20261012.json").read_text(encoding="utf-8"))
    check("handoff --speakers: the counted speakers reach stats.json and the sidecar",
          r.returncode == 0 and st["thresholds"]["counted_speakers"] == ["user"]
          and sc["stats"]["escalation_rule"]["counted_speakers"] == ["user"], r.stdout[-800:])
    for f in ("market-signal-20261012.json", "market-signal-20261012.md"):
        (ex / f).unlink()
    r = run(SCRIPTS / "build_handoff.py", "--run", run_dir, "--speakers", "user,founders")
    check("handoff --speakers: an unknown speaker is a usage error, nothing written",
          r.returncode == 2 and "founders" in r.stderr and not (ex / "market-signal-20261012.json").exists(), r.stderr[-800:])
    r = run(SCRIPTS / "compute_signals.py", "--corpus", run_dir / "corpus.jsonl", "--labels", run_dir / "labels.jsonl",
            "--analysis", run_dir / "analysis.json", "--speakers", "users", "--out", tmp / "stats.json")
    check("compute_signals --speakers: an unknown speaker is a usage error",
          r.returncode == 2 and "users" in r.stderr and not (tmp / "stats.json").exists(), r.stderr[-800:])


def t_sidecar(tmp):
    import validate_sidecar as VS
    path = EX / "market-signal-20261012.json"
    r = run(SCRIPTS / "validate_sidecar.py", path, "--stats", CUR / "stats.json")
    check("sidecar: the committed sidecar is valid, corpus re-checked", r.returncode == 0, r.stdout[-800:])
    sc = json.loads(path.read_text(encoding="utf-8"))
    rows = M.read_jsonl(CUR / "corpus.jsonl")

    def mutated(fn):
        s = copy.deepcopy(sc)
        fn(s)
        return VS.check(s, rows, None, None)

    cases = [
        ("a quote retyped with one word added", lambda s: s["quotes"][0].update(text_verbatim=s["quotes"][0]["text_verbatim"] + " really"), "corpus:"),
        ("a quote dated outside the window", lambda s: s["quotes"][1].update(date="2018-05-29"), "window:"),
        ("a hook marked verbatim that is not", lambda s: s["hooks"][0].update(text="Founders cannot get meetings"), "verbatim:"),
        ("a number in an angle's why", lambda s: s["angles"][0].update(why="Seen in 40% of threads."), "prose:"),
        ("a dangling quote id", lambda s: s["angles"][0].update(headline_quote_id="q_missing"), "ids:"),
        ("a missing required field", lambda s: s.pop("valid_until"), "schema:"),
    ]
    for name, fn, prefix in cases:
        errs = mutated(fn)
        check(f"sidecar: fails on {name}", any(e.startswith(prefix) for e in errs), errs[:3])


def t_privacy(tmp):
    leaks = []

    def handles(x, under=False, where=""):
        if isinstance(x, dict):
            for k, v in x.items():
                handles(v, under or k in M.AUTHOR_KEYS, where)
        elif isinstance(x, list):
            for v in x:
                handles(v, under, where)
        elif under and isinstance(x, str) and x and not M.PSEUDONYM_RE.match(x):
            leaks.append(f"{where}: handle {x!r}")

    files = sorted((AGENT / "examples").glob("**/fixtures/**/*.json")) + sorted((AGENT / "examples").glob("**/corpus.jsonl"))
    for f in files:
        raw = f.read_text(encoding="utf-8")
        text = raw if f.suffix == ".jsonl" else json.dumps(json.loads(raw), ensure_ascii=False)
        where = str(f.relative_to(AGENT))
        leaks += [f"{where}: {m.group(0)}" for rx in (M._EMAIL, M._PROFILE) for m in rx.finditer(text)]
        if f.suffix == ".jsonl":
            leaks += [f"{where}: record {r['record_id']} stores author" for r in M.read_jsonl(f) if "author" in r]
        else:
            handles(json.loads(raw), where=where)
    check("privacy: example fixtures and corpora hold no email, profile link or handle", files and not leaks, leaks[:5])
    body = {"hits": [{"author": "Jane_Doe42", "comment_text": "Thanks Jane_Doe42, mail me at jane@corp.example or see linkedin.com/in/jane"}]}
    got = M.scrub(body, "hn")["hits"][0]
    live = M.make_record(source="hn", native_id="1", community="c", kind="comment", url="https://example.com/1",
                         author="Jane_Doe42", created="2026-09-01", text=got["comment_text"])
    replay = M.make_record(source="hn", native_id="1", community="c", kind="comment", url="https://example.com/1",
                           author=got["author"], created="2026-09-01", text=got["comment_text"])
    check("privacy: scrub pseudonymises the handle everywhere and redacts contact details",
          M.PSEUDONYM_RE.match(got["author"]) and "Jane" not in got["comment_text"] and "[email]" in got["comment_text"]
          and "[profile link]" in got["comment_text"] and M.scrub(body, "hn") == M.scrub(M.scrub(body, "hn"), "hn")
          and live["author_hash"] == replay["author_hash"] and "author" not in live, got)


TESTS = {"help": t_help, "collectors": t_collectors, "collect": t_collect, "april": t_april, "verify": t_verify,
         "signals": t_signals, "diff": t_diff, "handoff": t_handoff, "sidecar": t_sidecar, "privacy": t_privacy}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keep", help="work in this folder and keep it")
    p.add_argument("--only", help="comma-separated test names: " + ", ".join(TESTS))
    args = p.parse_args(argv)
    names = args.only.split(",") if args.only else list(TESTS)
    tmp = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="ms-selftest-"))
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        for n in names:
            d = tmp / n
            d.mkdir(exist_ok=True)
            TESTS[n](d)
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in RESULTS if not r[1]]
    print(f"\nselftest: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
