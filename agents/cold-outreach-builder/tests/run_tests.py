#!/usr/bin/env python3
"""
run_tests.py

Offline regression tests of cold-outreach-builder. Standard library only, no
network, no API: every input is a fixture in tests/fixtures/ or the example in
examples/swanbase-preseed-founders-20261012/. Outputs go to a temporary
folder; the repo is never written.

    python3 agents/cold-outreach-builder/tests/run_tests.py [-v]

Covers: the outreach packs (schema, bad and good examples), the April 2026
regression (lint must block it), the structural lint checks, the example
pipeline end to end (verify, score, export, lint at 0 BLOCK), dossier
verification failures, the export template syntax, state and reply
ingestion, the parallel research runner (with a fake agent), the DNS sender
check, and the page cache.

Exit 0 when every test passes, 1 otherwise.
"""

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
FIX = os.path.join(HERE, "fixtures")
EXAMPLE = os.path.join(AGENT, "examples", "swanbase-preseed-founders-20261012")
REPO = os.path.dirname(os.path.dirname(AGENT))
TODAY = "2026-10-12"
EM = "\u2014"

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(REPO, "shared", "scripts"))
sys.path.insert(0, os.path.join(REPO, "shared", "skills", "writing-gate", "scripts"))
import lint_copy  # noqa: E402
from validate_json import validate  # noqa: E402

FAILURES = []
PASSED = 0
VERBOSE = "-v" in sys.argv


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
        if VERBOSE:
            print(f"ok   {name}")
    else:
        FAILURES.append(f"{name}: {detail}" if detail else name)
        print(f"FAIL {name}: {detail}")


def run(script, *args, env=None, stdin=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + list(args), capture_output=True,
                       text=True, env=e, input=stdin)
    if "Traceback" in p.stderr:
        FAILURES.append(f"{script} crashed: {p.stderr[-1500:]}")
        print(f"FAIL {script} crashed:\n{p.stderr[-1500:]}")
    return p.returncode, p.stdout, p.stderr


def lint_json(path, *extra):
    code, out, err = run("lint_outreach.py", path, "--json", *extra)
    try:
        return code, json.loads(out)
    except json.JSONDecodeError:
        return code, {"findings": [], "counts": {"BLOCK": 0}, "error": err}


def codes(report, level="BLOCK"):
    return [f["code"] for f in report.get("findings", []) if f["level"] == level]


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- tests

def test_packs():
    schema = json.load(open(os.path.join(REPO, "shared", "schemas", "copy-rules.schema.json"), encoding="utf-8"))
    for lang in ("en", "fr"):
        path = os.path.join(AGENT, "assets", "patterns", f"outreach.{lang}.json")
        pack = json.load(open(path, encoding="utf-8"))
        errs = validate(pack, schema)
        check(f"pack {lang} schema", not errs, "; ".join(errs))
        for rule in pack["rules"]:
            compiled = lint_copy._compile_rule(rule, path)
            for bad in rule.get("bad", []):
                hit = any(f["code"] == rule["code"] for f in lint_copy.lint_text(bad, [compiled]))
                check(f"pack {lang} {rule['code']} fires", hit, bad)
            for good in rule.get("good", []):
                hit = any(f["code"] == rule["code"] for f in lint_copy.lint_text(good, [compiled]))
                check(f"pack {lang} {rule['code']} silent", not hit, good)


def test_regression(tmp):
    src = open(os.path.join(FIX, "regression-20260428", "export.csv"), encoding="utf-8").read()
    path = os.path.join(tmp, "regression.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src.replace("\\u2014", EM))
    code, rep = lint_json(path, "--channel", "linkedin")
    blocks = codes(rep)
    check("regression exit 1", code == 1, f"exit {code}")
    check("regression >= 5 BLOCK", rep["counts"]["BLOCK"] >= 5, str(rep["counts"]))
    check("regression 6 em dashes", blocks.count("em-dash") == 6, str(blocks.count("em-dash")))
    for c in ("unsourced-number", "unfilled-variable", "no-sourced-fact", "too-long-chars", "disclaimer-pitch", "fausse-rarete"):
        check(f"regression {c}", c in blocks, str(sorted(set(blocks))))
    check("regression hardcoded-sender warn", "hardcoded-sender" in codes(rep, "WARN"))


def test_structural(tmp):
    code, rep = lint_json(os.path.join(FIX, "structural", "export.csv"), "--channel", "email")
    blocks = codes(rep)
    check("structural exit 1", code == 1)
    expected = {"duplicate-address", "duplicate-hook", "near-duplicate-hook", "unfilled-variable", "too-long",
                "too-many-links", "url-shortener", "subject-too-long", "fake-reply-subject", "signature",
                "bullets", "unsourced-number", "no-sourced-fact", "opener-cliche"}
    missing = expected - set(blocks)
    check("structural codes", not missing, f"missing {sorted(missing)}")
    by_row = {}
    for f in rep["findings"]:
        if f["level"] == "BLOCK":
            by_row.setdefault(f["prospect_id"], set()).add(f["code"])
    check("structural clean row has no BLOCK", "p001" not in by_row, str(by_row.get("p001")))
    check("structural duplicate on p002", {"duplicate-address", "duplicate-hook"} <= by_row.get("p002", set()))
    check("structural hook not in body on p006", "no-sourced-fact" in by_row.get("p006", set()))

    rows = read_rows(os.path.join(FIX, "structural", "export.csv"))[:1]
    # Fictional sender and figure: the lint must block any equity percentage.
    rows[0]["step_1_body"] = rows[0]["step_1_body"].replace("Want the", "Acme Studio takes 7" + "% equity. Want the")
    rows[0]["step_1_subject"] = "your first engineer \U0001F680"
    path = os.path.join(tmp, "equity.csv")
    write_rows(path, rows)
    code, rep = lint_json(path, "--channel", "email")
    check("equity percentage BLOCK", "equity-percentage" in codes(rep), str(codes(rep)))
    check("emoji in subject BLOCK", "emoji" in codes(rep), str(codes(rep)))


def test_example(tmp):
    out = os.path.join(tmp, "example")
    os.makedirs(out)
    verify = os.path.join(out, "verify.json")
    tiers = os.path.join(out, "tiers.json")
    export = os.path.join(out, "sequence-export.csv")
    d = os.path.join(EXAMPLE, "dossiers")
    code, o, e = run("verify_dossiers.py", d, "--cache", os.path.join(EXAMPLE, "cache"), "--today", TODAY, "--out", verify)
    check("example verify exit 0", code == 0, o + e)
    code, o, e = run("score_prospects.py", d, "--verify", verify, "--today", TODAY, "--out", tiers)
    t = {p["prospect_id"]: p["tier"] for p in json.load(open(tiers))["prospects"]}
    check("example tiers", t == {"p001": "A", "p002": "B", "p003": "C"}, str(t))
    check("example tiers.csv", os.path.isfile(os.path.join(out, "tiers.csv")))
    code, o, e = run("build_sequence_export.py", "--sequence", os.path.join(EXAMPLE, "cold-outreach-output.json"),
                     "--leads", os.path.join(EXAMPLE, "leads.csv"), "--tiers", tiers,
                     "--messages", os.path.join(EXAMPLE, "messages.json"), "--dossiers", d, "--out", export)
    rows = read_rows(export)
    check("example export rows", [r["prospect_id"] for r in rows] == ["p001", "p002"], str([r["prospect_id"] for r in rows]))
    check("example tier C skipped", "tier C" in open(export + ".skipped.csv").read())
    check("example tier A personal body", rows[0]["step_1_body"].startswith("Hi Maya,\n\nTidewell opened"))
    check("example hook source filled", rows[1]["hook_source_url"].startswith("https://hardwarenight.example"))
    check("example sender token kept", rows[0]["step_1_body"].endswith("{{sender_first_name}}"))
    code, rep = lint_json(export, "--dossiers", d, "--verify", verify, "--sequence", os.path.join(EXAMPLE, "cold-outreach-output.json"))
    check("example lint 0 BLOCK", code == 0 and rep["counts"]["BLOCK"] == 0, json.dumps(rep.get("findings"))[:600])

    # A hook on a fact that does not exist, and a number the fact does not hold.
    rows[1]["hook_fact_id"] = "f9"
    rows[1]["step_1_body"] = rows[1]["step_1_body"].replace("on three farms", "on 3 farms")
    rows[1]["hook"] = rows[1]["hook"].replace("on three farms", "on 3 farms")
    bad = os.path.join(out, "tampered.csv")
    write_rows(bad, rows)
    code, rep = lint_json(bad, "--dossiers", d, "--verify", verify)
    check("tampered hook fact BLOCK", "no-sourced-fact" in codes(rep), str(codes(rep)))
    check("tampered number BLOCK", "unsourced-number" in codes(rep), str(codes(rep)))

    # A number from positioning.proof is allowed.
    proj = os.path.join(out, "project")
    os.makedirs(os.path.join(proj, "project-context"))
    json.dump({"positioning": {"proof": ["3 farms piloted the sensor (https://ferncast.example/pilot)"]}},
              open(os.path.join(proj, "project-context", "context.json"), "w"))
    code, rep = lint_json(bad, "--dossiers", d, "--verify", verify, "--project", proj)
    check("proof number allowed", "unsourced-number" not in codes(rep), str(codes(rep)))

    # The same number from a proof object that proof.py refuses (stale metric,
    # customer without consent for outreach) stays unsourced, with the reason.
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=10)).isoformat()
    for label, item, reason in (
        ("stale metric", {"id": "pilot-farms", "claim": "3 farms piloted the sensor", "kind": "metric",
                          "source": "https://ferncast.example/pilot", "date": "2024-01-15"}, "stale"),
        ("customer without consent", {"id": "pilot-farms", "claim": "3 farms piloted the sensor", "kind": "customer",
                                      "source": "https://ferncast.example/pilot", "date": recent,
                                      "consent": {"status": "granted", "scope": ["site"], "date": recent, "by": "the farms, email"}},
         "not outreach")):
        json.dump({"positioning": {"proof": [item]}}, open(os.path.join(proj, "project-context", "context.json"), "w"))
        code, rep = lint_json(bad, "--dossiers", d, "--verify", verify, "--project", proj)
        refused = rep.get("proof_refused") or []
        check(f"proof object refused ({label}): number BLOCK", "unsourced-number" in codes(rep), str(codes(rep)))
        check(f"proof object refused ({label}): reason reported", refused and refused[0]["id"] == "pilot-farms" and reason in refused[0]["reason"], str(refused))
    fresh = {"id": "pilot-farms", "claim": "3 farms piloted the sensor", "kind": "metric",
             "source": "https://ferncast.example/pilot", "date": recent}
    json.dump({"positioning": {"proof": [fresh]}}, open(os.path.join(proj, "project-context", "context.json"), "w"))
    code, rep = lint_json(bad, "--dossiers", d, "--verify", verify, "--project", proj)
    check("fresh proof object number allowed", "unsourced-number" not in codes(rep) and rep.get("proof_refused") == [], str(codes(rep)))

    # A sender name given at export time is accepted by the signature check.
    code, o, e = run("build_sequence_export.py", "--sequence", os.path.join(EXAMPLE, "cold-outreach-output.json"),
                     "--leads", os.path.join(EXAMPLE, "leads.csv"), "--tiers", tiers,
                     "--messages", os.path.join(EXAMPLE, "messages.json"), "--dossiers", d,
                     "--sender-first-name", "Sam", "--out", os.path.join(out, "named.csv"))
    code, rep = lint_json(os.path.join(out, "named.csv"), "--dossiers", d, "--verify", verify, "--sender-first-name", "Sam")
    check("rendered sender passes", code == 0, str(codes(rep)))
    return export


def test_verify_fixtures(tmp):
    d = os.path.join(FIX, "dossiers")
    out = os.path.join(tmp, "verify-fixtures.json")
    code, o, e = run("verify_dossiers.py", d, "--cache", os.path.join(d, "cache"), "--today", TODAY, "--out", out)
    res = json.load(open(out))["prospects"]
    check("verify fixtures exit 1", code == 1)
    check("verify only prospect folders", set(res) == {"d-ok", "d-bad", "d-schema"}, str(sorted(res)))
    check("verify d-ok", res["d-ok"]["status"] == "ok", json.dumps(res["d-ok"]["errors"]))
    bad = {e["code"] for e in res["d-bad"]["errors"]}
    for c in ("excerpt-not-found", "not-cached", "post-date", "owner-mismatch", "future-date", "email-not-on-page"):
        check(f"verify d-bad {c}", c in bad, str(sorted(bad)))
    check("verify stale is a warning", res["d-bad"]["facts"]["f6"]["status"] == "stale")
    check("verify d-schema", "schema" in {e["code"] for e in res["d-schema"]["errors"]})


def test_export_syntax(tmp):
    seq = {"channel": "email", "sequence": [
        {"n": 1, "day": 0, "subjects": [{"variant": "A", "text": "hi {{company}}"}],
         "body": "Hi {{first_name}},\n\n{{?hook}}\n\nLine kept.\n\n{{sender_first_name}}"},
        {"n": 2, "day": 4, "subjects": [], "body": "{{first_name}}, {{missing_token}}\n\n{{sender_first_name}}"}]}
    sp = os.path.join(tmp, "seq.json")
    json.dump(seq, open(sp, "w"))
    leads = os.path.join(tmp, "leads.csv")
    with open(leads, "w", newline="") as f:
        f.write("prospect_id,email,first_name,company,missing_token\np1,a@x.example,Ann,Xco,filled\np2,b@x.example,Bob,Yco,\n")
    out = os.path.join(tmp, "syntax.csv")
    run("build_sequence_export.py", "--sequence", sp, "--leads", leads, "--out", out)
    rows = read_rows(out)
    check("optional line dropped", len(rows) == 1 and "{{?hook}}" not in rows[0]["step_1_body"]
          and "\n\n\n" not in rows[0]["step_1_body"], rows[0]["step_1_body"] if rows else "no row")
    check("unresolved token skips row", "missing_token" in open(out + ".skipped.csv").read())
    check("delay days", rows[0]["step_2_delay_days"] == "4")
    msgs = os.path.join(tmp, "hold.json")
    json.dump({"p1": {"hold": "still blocks after 3 lint passes"}}, open(msgs, "w"))
    run("build_sequence_export.py", "--sequence", sp, "--leads", leads, "--messages", msgs, "--out", out)
    check("hold keeps a prospect out", read_rows(out) == [] and "held: still blocks" in open(out + ".skipped.csv").read())


def test_state_and_replies(tmp):
    st = os.path.join(tmp, "state", "state.json")
    rf = os.path.join(FIX, "replies")
    run("outreach_state.py", "init", "--state", st)
    code, o, e = run("outreach_state.py", "register", "--state", st, "--export", os.path.join(rf, "export.csv"),
                     "--sequence-id", "outreach-20261012", "--start-date", TODAY)
    check("register exit 0", code == 0, o + e)
    run("outreach_state.py", "mark-sent", "--state", st, "--sequence-id", "outreach-20261012", "--through-step", "1", "--date", TODAY)
    code, o, e = run("ingest_replies.py", "--state", st, "--csv", os.path.join(rf, "replies.csv"),
                     "--eml", os.path.join(rf, "eml"), "--today", "2026-10-16", "--json")
    res = {r["from"]: r for r in json.loads(o)["results"]}
    check("ingest exit 0", code == 0, e)
    expect = {"ana@quill.example": "positive", "ben@larch.example": "negative", "chloe@fennel.example": "negative",
              "dev@oriel.example": "out_of_office", "eli@sorrel.example": "off_topic",
              "mailer-daemon@mail.example": "bounce"}
    for who, cls in expect.items():
        check(f"classify {who}", res.get(who, {}).get("class") == cls, str(res.get(who, {}).get("class")))
    check("quoted history ignored", res["ana@quill.example"]["confidence"] == "high")
    check("mixed reply needs review", res["hal@birch.example"]["needs_review"] is True)
    check("unknown sender unmatched", res["gil@unknown.example"]["state"] == "unmatched")
    check("ooo return date", res["dev@oriel.example"].get("return_date") == "2026-10-21", str(res["dev@oriel.example"].get("return_date")))
    state = json.load(open(st))["contacts"]
    status = {c["email"]: c["status"] for c in state.values()}
    check("state statuses", status == {
        "ana@quill.example": "replied_positive", "ben@larch.example": "replied_negative",
        "chloe@fennel.example": "unsubscribed", "dev@oriel.example": "paused", "eli@sorrel.example": "off_topic",
        "fay@tansy.example": "bounced", "hal@birch.example": "active"}, str(status))
    check("suppressed", {c["email"] for c in state.values() if c.get("suppressed")} ==
          {"ben@larch.example", "chloe@fennel.example", "fay@tansy.example"})
    check("remaining steps cancelled", all(s.get("cancelled") for s in state["email:ana@quill.example"]["steps"] if not s.get("sent")))

    code, o, e = run("ingest_replies.py", "--state", st, "--csv", os.path.join(rf, "replies.csv"), "--today", "2026-10-16", "--json")
    again = json.loads(o)["results"]
    check("idempotent ingest", [r["from"] for r in again] == ["hal@birch.example", "gil@unknown.example"], str([r["from"] for r in again]))
    code, o, e = run("ingest_replies.py", "--state", st, "--csv", os.path.join(rf, "replies.csv"),
                     "--overrides", os.path.join(rf, "overrides-bad.json"), "--today", "2026-10-16")
    check("override without quote rejected", code == 1)
    code, o, e = run("ingest_replies.py", "--state", st, "--csv", os.path.join(rf, "replies.csv"),
                     "--overrides", os.path.join(rf, "overrides.json"), "--today", "2026-10-16")
    check("override with quote accepted", code == 0 and
          json.load(open(st))["contacts"]["email:hal@birch.example"]["status"] == "replied_positive")

    code, o, e = run("outreach_state.py", "due", "--state", st, "--today", "2026-10-22")
    check("due answer list", "ana@quill.example" in o.split("## Read")[0] and "hal@birch.example" in o.split("## Read")[0])
    check("due resume after absence", "dev@oriel.example" in o.split("## Resume")[1].split("##")[0])
    run("outreach_state.py", "answered", "--state", st, "--contact", "ana@quill.example")
    code, o, e = run("outreach_state.py", "due", "--state", st, "--today", "2026-10-22")
    check("answered leaves the list", "ana@quill.example" not in o)
    code, o, e = run("outreach_state.py", "check", "--state", st, "--leads", os.path.join(rf, "export.csv"), "--today", "2026-10-22")
    check("check excludes every contact", "7 of 7 lead(s) excluded" in o, o[-200:])
    code, o, e = run("outreach_state.py", "register", "--state", st, "--export", os.path.join(rf, "export.csv"),
                     "--sequence-id", "outreach-20261101", "--start-date", "2026-11-01")
    check("register refuses open or suppressed contacts", code == 1 and "refused" in o)
    code, o, e = run("outreach_state.py", "summary", "--state", st)
    check("summary has no winner", "no winner" in o)
    return st


def test_export_respects_state(tmp, state_path):
    rf = os.path.join(FIX, "replies")
    seq = os.path.join(EXAMPLE, "cold-outreach-output.json")
    leads = os.path.join(tmp, "leads-state.csv")
    with open(leads, "w", newline="") as f:
        f.write("prospect_id,email,first_name,company,hook,hook_fact_id\n"
                "p1,ana@quill.example,Ana,Quill,Hook one.,f1\np2,new@person.example,New,Corp,Hook two.,f1\n")
    out = os.path.join(tmp, "state-export.csv")
    run("build_sequence_export.py", "--sequence", seq, "--leads", leads, "--state", state_path, "--today", "2026-10-22", "--out", out)
    rows = read_rows(out)
    check("export skips contacted", [r["email"] for r in rows] == ["new@person.example"], str([r["email"] for r in rows]))
    check("export skip reason", "state:" in open(out + ".skipped.csv").read())
    assert os.path.isdir(rf)


def test_runner(tmp):
    run_dir = os.path.join(tmp, "run")
    fake = f"{sys.executable} {os.path.join(HERE, 'fake_agent.py')}"
    code, o, e = run("run_dossiers.py", "prepare", "--leads", os.path.join(EXAMPLE, "leads.csv"), "--run-dir", run_dir)
    check("prepare briefs", all(os.path.isfile(os.path.join(run_dir, "dossiers", p, "brief.md")) for p in ("p001", "p002", "p003")))
    code, o, e = run("run_dossiers.py", "status", "--run-dir", run_dir)
    check("status pending exit 1", code == 1)
    code, o, e = run("run_dossiers.py", "run", "--run-dir", run_dir, "--agent-cmd", fake, env={"FAKE_AGENT_FAIL": "p002"})
    check("run reports the failed one", code == 1 and "p002" in o.split("left")[-1], o)
    code, o, e = run("run_dossiers.py", "run", "--run-dir", run_dir, "--agent-cmd", fake)
    check("run resumes", code == 0 and "3 done, 0 left" in o, o)
    code, o, e = run("run_dossiers.py", "run", "--run-dir", run_dir)
    check("run without command when done", code == 0)
    code, o, e = run("verify_dossiers.py", os.path.join(run_dir, "dossiers"), "--cache", os.path.join(run_dir, "cache"), "--today", TODAY)
    check("fake dossiers verify", code == 0, o)


def test_sender():
    dns = os.path.join(FIX, "dns")
    code, o, e = run("check_sender.py", "--domain", "outreach.swanbase.example", "--dkim-selector", "s1",
                     "--records", os.path.join(dns, "records-good.json"), "--inbox-age-days", "45", "--list-size", "120", "--json")
    r = json.loads(o)
    check("sender good exit 0", code == 0 and r["status"] == "pass", o[-300:])
    check("sender plan", r["sending_plan"]["days_to_send_step_1"] == 6, str(r["sending_plan"]))
    check("sender never probes SMTP", r["smtp_probe"] is False)
    code, o, e = run("check_sender.py", "--domain", "cold.acme.example", "--dkim-selector", "s1",
                     "--records", os.path.join(dns, "records-bad.json"), "--json")
    r = json.loads(o)
    fails = {c["check"] for c in r["checks"] if c["status"] == "fail"}
    check("sender bad exit 1", code == 1)
    check("sender bad checks", fails == {"spf", "dkim", "dmarc", "mx"}, str(fails))
    code, o, e = run("check_sender.py", "--domain", "outreach.swanbase.example", "--records", os.path.join(dns, "records-good.json"), "--json")
    check("sender without selector warns", code == 0 and json.loads(o)["status"] == "warn")
    src = open(os.path.join(SCRIPTS, "check_sender.py"), encoding="utf-8").read()
    check("no smtplib anywhere", "import smtplib" not in src and "socket.create_connection" not in src)


def test_cache(tmp):
    code, o, e = run("cache_page.py", "--hash", "https://Example.com/a#frag")
    code2, o2, e2 = run("cache_page.py", "--hash", "https://example.com/a")
    check("hash ignores fragment and host case", o.strip() == o2.strip() and len(o.strip()) == 16)
    cache = os.path.join(tmp, "cache")
    code, o, e = run("cache_page.py", "--cache", cache, "https://www.linkedin.com/in/someone/")
    check("linkedin profile refused", code == 1 and "refused" in e)
    secret = os.path.join(tmp, "secret.txt")
    open(secret, "w").write("local file that must never reach the cache")
    for url in ("file://" + secret, "ftp://ftp.example/file.txt"):
        code, o, e = run("cache_page.py", "--cache", cache, url)
        check(f"{url.split(':')[0]}:// refused", code == 1 and "only http and https" in e, e[-300:])
    code, o, e = run("cache_page.py", "--cache", cache, "http://169.254.169.254/latest/meta-data/")
    check("link-local host refused", code == 1 and "link-local" in e, e[-300:])
    check("refused URLs leave no cache file", not os.path.exists(os.path.join(cache, "index.json")) or "secret" not in open(os.path.join(cache, "index.json")).read())
    page = os.path.join(tmp, "page.html")
    open(page, "w").write("<html><head><script>var x=1;</script></head><body><p>Hello &amp; welcome</p></body></html>")
    code, o, e = run("cache_page.py", "--cache", cache, "--url", "https://site.example/p", "--from-file", page)
    from outreach_lib import read_cached_text
    text = read_cached_text(cache, "https://site.example/p") or ""
    check("html stored as text", "Hello & welcome" in text and "var x" not in text, text)


def main():
    tmp = tempfile.mkdtemp(prefix="cob-tests-")
    try:
        test_packs()
        test_regression(tmp)
        test_structural(tmp)
        test_example(tmp)
        test_verify_fixtures(tmp)
        test_export_syntax(tmp)
        st = test_state_and_replies(tmp)
        test_export_respects_state(tmp, st)
        test_runner(tmp)
        test_sender()
        test_cache(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
