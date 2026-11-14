#!/usr/bin/env python3
"""
run_tests.py

Offline tests of first-users-hunter. Standard library only, no network, no
API key: every API answer is a frozen fixture in tests/fixtures/api/ (the
shape of the real APIs, fictional people) and every run input is the example
in examples/swanbase-preseed-founders-20261012/. Outputs go to a temporary
folder; the repo is never written.

    python3 agents/first-users-hunter/tests/run_tests.py [-v]

Covers: --help of every script and collector; dates and owners decoded from
LinkedIn and X ids; each collector on its fixture (HN Algolia, GitHub search
and events, Reddit OAuth, Luma, Notion, folk, recherche-entreprises, manual
CSV) and their skip paths without a key; the pipeline end to end (signals,
candidates, activity gate, score, shortlist, rejections, source health);
verify_people.py on the example and on tampered copies; the export and its
handoff read by cold-outreach-builder's own scripts when that agent sits next
to this one; the writing gate on the first touches; the ledger on a re-run.

Exit 0 when every test passes, 1 otherwise.
"""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(AGENT, "scripts")
API = os.path.join(HERE, "fixtures", "api")
EXAMPLE = os.path.join(AGENT, "examples", "swanbase-preseed-founders-20261012")
REPO = os.path.dirname(os.path.dirname(AGENT))
COB = os.path.join(REPO, "agents", "cold-outreach-builder")
TODAY = "2026-10-12"
DAY = date(2026, 10, 12)

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(REPO, "shared", "scripts"))
import fuh_lib  # noqa: E402
from collectors import common  # noqa: E402
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


def run(args, cwd=AGENT, env=None):
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


def quiet(fn, *a, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        return fn(*a, **kw), buf.getvalue()


CRIT = fuh_lib.load_criteria()
SIGNAL_SCHEMA = fuh_lib.load_json(fuh_lib.SIGNAL_SCHEMA)


def fixture_fetch():
    return common.Fetcher(fixtures=API)


def mod(name):
    import importlib
    return importlib.import_module(f"collectors.{name}")


# ---------------------------------------------------------------- 1. --help

def test_help():
    scripts = ["collect.py", "candidates.py", "check_activity.py", "score_people.py", "verify_people.py",
               "export_handoff.py", "pipeline.py", "date_from_url.py", "cache_page.py"]
    scripts += [f"collectors/{c}.py" for c in ("hn", "github", "reddit", "luma", "notion", "folk", "registry_fr", "manual")]
    for s in scripts:
        code, out = run([os.path.join(SCRIPTS, s), "--help"])
        check(f"help {s}", code == 0 and "usage" in out.lower(), out[-200:])


# ---------------------------------------------------------------- 2. dates from ids

def test_dates():
    li = "https://www.linkedin.com/posts/camille-roux-fictive_preseed-paris-activity-7510249942548603456-AbCd"
    check("linkedin id date", str(fuh_lib.post_id_date(li)) == "2026-09-28", str(fuh_lib.post_id_date(li)))
    check("linkedin id time", fuh_lib.li_activity_datetime(li).strftime("%H:%M") == "08:12")
    check("linkedin urn", str(fuh_lib.post_id_date("urn:li:activity:7510249942548603456")) == "2026-09-28")
    check("linkedin ugcPost", str(fuh_lib.post_id_date("https://www.linkedin.com/feed/update/urn:li:ugcPost:7510249942548603456/")) == "2026-09-28")
    x = "https://x.com/nadia_ships_fictive/status/2108644918686650514"
    check("x snowflake date", str(fuh_lib.post_id_date(x)) == "2026-10-09", str(fuh_lib.post_id_date(x)))
    check("twitter.com host", str(fuh_lib.post_id_date(x.replace("x.com", "twitter.com"))) == "2026-10-09")
    # round trip from a chosen instant, both formulas
    ms = 1791000000000
    check("x round trip", fuh_lib.x_status_datetime(f"https://x.com/a/status/{(ms - fuh_lib.X_EPOCH_MS) << 22}").timestamp() * 1000 == ms)
    check("li round trip", fuh_lib.li_activity_datetime(f"activity-{ms << 22}").timestamp() * 1000 == ms)
    check("owner linkedin", fuh_lib.url_owner(li) == ("linkedin", "camille-roux-fictive"))
    check("owner x", fuh_lib.url_owner(x) == ("x", "nadia_ships_fictive"))
    check("no id", fuh_lib.post_id_date("https://news.ycombinator.com/item?id=99000101") is None)
    code, out = run([os.path.join(SCRIPTS, "date_from_url.py"), li, x])
    check("date_from_url ok", code == 0 and "2026-09-28T08:12:00Z" in out and "x:nadia_ships_fictive" in out, out)
    code, out = run([os.path.join(SCRIPTS, "date_from_url.py"), "https://example.com/post"])
    check("date_from_url no id exits 1", code == 1 and "no post id" in out, out)
    check("email package@version refused", fuh_lib.email_problem("minidenticons@4.2.1") is not None)
    check("email ok", fuh_lib.email_problem("hello@studio.example") is None)


# ---------------------------------------------------------------- 3. collectors

def valid_signals(name, rows):
    errs = [f"{r.get('signal_id')}: {e}" for r in rows for e in validate(r, SIGNAL_SCHEMA)]
    check(f"{name} records match signal schema", not errs, "; ".join(errs[:3]))


def test_collectors():
    f = fixture_fetch()
    hn = mod("hn")
    cfg = {"queries": [{"id": "a", "query": "first users", "tags": "(story,comment)", "hits": 50},
                       {"id": "b", "query": "cofounder", "tags": "(story,comment)", "hits": 50}]}
    rows = hn.collect_signals(cfg, f, DAY, CRIT)
    valid_signals("hn", rows)
    by = {r["handle"]: r for r in rows}
    check("hn 3 signals", len(rows) == 3, str(len(rows)))
    check("hn ask classified", by["qforge_fictive"]["signal_type"] == "ask" and by["mtrace_fictive"]["signal_type"] == "ask")
    check("hn no-pattern comment is build", by["nledger_fictive"]["signal_type"] == "build")
    check("hn html stripped", "<p>" not in by["qforge_fictive"]["text"])
    check("hn thread url", by["qforge_fictive"]["thread_url"].endswith("id=99000100"))
    check("hn community", by["mtrace_fictive"]["community"] == "Ask HN" and by["qforge_fictive"]["community"] == "Ask HN")
    act = hn.collect_activity("qforge_fictive", f, DAY, CRIT)
    check("hn activity", len(act) == 3 and {a["kind"] for a in act} == {"comment"}, str(act))
    try:
        hn.collect_activity("gone_account_fictive", f, DAY, CRIT)
        check("hn missing user is not_found", False)
    except common.SourceError as e:
        check("hn missing user is not_found", e.kind == "not_found")

    gh = mod("github")
    rows = gh.collect_signals({"queries": [{"id": "g", "q": "\"beta testers\" type:issue"}]}, f, DAY, CRIT)
    valid_signals("github", rows)
    by = {r["handle"]: r for r in rows}
    check("github 2 signals", len(rows) == 2)
    check("github switch classified", by["lumen-sketch-fictive"]["signal_type"] == "switch", by["lumen-sketch-fictive"]["signal_type"])
    check("github community is repo", by["lumen-sketch-fictive"]["community"] == "acme-fictional/launchkit")
    act = gh.collect_activity("lumen-sketch-fictive", f, DAY, CRIT)
    kinds = sorted(a["kind"] for a in act)
    check("github activity kinds", kinds == ["comment", "issue", "other", "push"], str(kinds))
    try:
        gh.collect_activity("ghost-builder-fictive", f, DAY, CRIT)
        check("github 404 is not_found", False)
    except common.SourceError as e:
        check("github 404 is not_found", e.kind == "not_found")
    env_tok = os.environ.pop("GITHUB_TOKEN", None), os.environ.pop("GH_TOKEN", None)
    cfg = {"queries": [], "discussions": [{"id": "d", "q": "first users"}]}
    rows = gh.collect_signals(cfg, common.Fetcher(), DAY, CRIT)  # live mode, no query sent
    check("github discussions skipped without token", rows == [] and "GITHUB_TOKEN" in " ".join(cfg.get("_notes", [])))
    for k, v in zip(("GITHUB_TOKEN", "GH_TOKEN"), env_tok):
        if v:
            os.environ[k] = v

    rd = mod("reddit")
    saved = {k: os.environ.pop(k, None) for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")}
    try:
        rd.collect_signals({"subreddits": ["startups"]}, common.Fetcher(), DAY, CRIT)
        check("reddit skipped without key", False)
    except common.SourceError as e:
        check("reddit skipped without key", e.kind == "skipped" and "REDDIT_CLIENT_ID" in str(e))
    rows = rd.collect_signals({"subreddits": ["startups"], "query": "first users", "limit": 50}, f, DAY, CRIT)
    valid_signals("reddit", rows)
    check("reddit deleted author dropped", len(rows) == 1 and rows[0]["handle"] == "paris_soloist_fictive")
    check("reddit ask classified", rows[0]["signal_type"] == "ask")
    act = rd.collect_activity("paris_soloist_fictive", f, DAY, CRIT)
    check("reddit activity", sorted(a["kind"] for a in act) == ["comment", "post"])
    try:
        rd.collect_activity("suspended_fictive", f, DAY, CRIT)
        check("reddit suspended is not_found", False)
    except common.SourceError as e:
        check("reddit suspended is not_found", e.kind == "not_found")
    for k, v in saved.items():
        if v:
            os.environ[k] = v
    code, out = run([os.path.join(SCRIPTS, "collectors", "reddit.py")],
                    env={k: v for k, v in os.environ.items() if not k.startswith("REDDIT_")})
    check("reddit CLI without key exits 0 with a skip line", code == 0 and "skipped" in out, out)

    lu = mod("luma")
    rows = lu.collect_signals({"places": ["paris"], "keywords": ["founder", "pre-seed", "startup"]}, f, DAY, CRIT)
    valid_signals("luma", rows)
    check("luma one host kept", len(rows) == 1 and rows[0]["handle"] == "ines-marchal-fictive", str([r["handle"] for r in rows]))
    check("luma org host skipped, links read", rows and rows[0]["links"].get("linkedin") == "ines-marchal-fictive")
    check("luma event type and future date", rows and rows[0]["signal_type"] == "event" and rows[0]["date"] == "2026-10-20")

    no = mod("notion")
    cfg = {"lists": [{"id": "dir", "site": "https://founders-directory-example.notion.site",
                      "page_id": "11111111-2222-3333-4444-555555555555", "view_id": "66666666-7777-8888-9999-000000000000",
                      "columns": {"name": "Name", "linkedin": "LinkedIn", "role": "Role"}}]}
    rows = no.collect_signals(cfg, f, DAY, CRIT)
    valid_signals("notion", rows)
    check("notion 2 listed rows", len(rows) == 2 and {r["signal_type"] for r in rows} == {"listed"})
    check("notion linkedin handle", rows and rows[0]["handle"] == "camille-roux-fictive" and rows[0]["network"] == "linkedin")

    fo = mod("folk")
    rows = fo.collect_signals({"views": [{"id": "fictview01", "label": "fictional list"}]}, f, DAY, CRIT)
    valid_signals("folk", rows)
    check("folk 2 listed rows", len(rows) == 2 and rows[1]["network"] == "x" and rows[1]["handle"] == "nina_vidal_fictive")

    rg = mod("registry_fr")
    rows = rg.collect_signals({"queries": [{"q": "logiciel", "section_activite_principale": "J", "departement": "75", "per_page": 25}]},
                              f, DAY, CRIT)
    valid_signals("registry_fr", rows)
    blob = json.dumps(rows)
    check("registry one director in window", len(rows) == 1 and rows[0]["author_name"] == "Hugo Lemaire", blob[:200])
    check("registry drops birth date and nationality", "1994" not in blob and "Fran" not in blob)
    check("registry trigger not authored", rows and rows[0]["signal_type"] == "trigger" and rows[0]["authored"] is False)

    ma = mod("manual")
    cfg = {"_base_dir": os.path.join(EXAMPLE, "run")}
    rows, out = quiet(ma.collect_signals, cfg, f, DAY, CRIT)
    valid_signals("manual", rows)
    by = {r["handle"]: r for r in rows}
    check("manual 3 signals", len(rows) == 3, str(list(by)))
    check("manual date from linkedin id", by.get("camille-roux-fictive", {}).get("date") == "2026-09-28"
          and by["camille-roux-fictive"]["date_source"] == "post_id")
    check("manual date disagreeing with the id is rejected", "leo_builds_fictive" not in by and "disagrees" in out)
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "manual-signals.csv"), "w", encoding="utf-8") as fh:
        fh.write("network,handle,url,text\nlinkedin,camille-roux-fictive,"
                 "https://www.linkedin.com/posts/someone-else-fictive_x-activity-7510249942548603456-Zz,"
                 "A post by someone else where Camille is tagged, any recommendation welcome\n")
    rows, out = quiet(ma.collect_signals, {"_base_dir": tmp}, f, DAY, CRIT)
    check("manual tagged post rejected", rows == [] and "tagged" in out, out)
    act, _ = quiet(ma.collect_activity, "camille-roux-fictive", f, DAY, CRIT, {"_base_dir": os.path.join(EXAMPLE, "run"), "_network": "linkedin"})
    check("manual activity rows dated from ids", len(act) == 3 and all(a["date_source"] == "post_id" for a in act), str(act))
    shutil.rmtree(tmp)

    try:
        common.Fetcher(fixtures=API).json("GET", "https://hn.algolia.com/api/v1/search_by_date", params={"query": "nothing"})
        check("missing fixture raises", False)
    except common.SourceError as e:
        check("missing fixture raises", "no fixture" in str(e))


# ---------------------------------------------------------------- 4. pipeline

def prepare_run(tmp):
    run_dir = os.path.join(tmp, "run")
    shutil.copytree(os.path.join(EXAMPLE, "run"), run_dir)
    code, out = run([os.path.join(SCRIPTS, "pipeline.py"), "--config", os.path.join(EXAMPLE, "config.json"),
                     "--run-dir", run_dir, "--fixtures", API, "--today", TODAY])
    return run_dir, code, out


def test_pipeline(tmp):
    run_dir, code, out = prepare_run(tmp)
    check("pipeline exits 0", code == 0, out[-500:])
    sl = fuh_lib.read_jsonl(os.path.join(run_dir, "shortlist.jsonl"))
    keys = [s["person_key"] for s in sl]
    check("shortlist order", keys == ["hn:qforge_fictive", "linkedin:camille-roux-fictive", "hn:mtrace_fictive",
                                      "github:lumen-sketch-fictive", "luma:ines-marchal-fictive"], str(keys))
    check("shortlist scores", [s["score"] for s in sl] == [27, 23, 23, 22, 19], str([s["score"] for s in sl]))
    rej = {r["person_key"]: r for r in fuh_lib.read_jsonl(os.path.join(run_dir, "rejected.jsonl"))}
    check("stale signal rejected", "stale" in rej.get("linkedin:bastien-morel-fictive", {}).get("reason", ""))
    check("list seed alone rejected", "seed" in rej.get("linkedin:samuel-petit-fictive", {}).get("reason", ""))
    check("dead handle rejected", "dead_handle" in rej.get("github:ghost-builder-fictive", {}).get("reason", ""))
    for k in ("hn:nledger_fictive", "x:nadia_ships_fictive", "registry_fr:hugo-lemaire"):
        check(f"not proven rejected {k}", "not_proven" in rej.get(k, {}).get("reason", ""), str(rej.get(k)))
    cands = {c["person_key"]: c for c in fuh_lib.read_jsonl(os.path.join(run_dir, "candidates.jsonl"))}
    q = cands["hn:qforge_fictive"]
    check("identities merged from identities.json", {"hn:qforge_fictive", "linkedin:alex-dupuis-fictive"} <= set(q["keys"]))
    check("list seed merged with the person's own signal", cands["linkedin:camille-roux-fictive"]["seed_signal_ids"])
    check("luma host merged with published linkedin", "linkedin:ines-marchal-fictive" in cands["luma:ines-marchal-fictive"]["keys"])
    act = fuh_lib.load_json(os.path.join(run_dir, "activity.json"))["people"]
    check("tagged post ignored in activity", any("tagged" in i["reason"] for i in act["linkedin:camille-roux-fictive"]["ignored"]))
    check("signal and its API record count once", act["github:lumen-sketch-fictive"]["weighted_posts"] == 2.25,
          str(act["github:lumen-sketch-fictive"]["weighted_posts"]))
    check("multi network activity", act["hn:qforge_fictive"]["active_networks"] == ["hn", "linkedin"])
    check("linkedin window 45 days", act["linkedin:camille-roux-fictive"]["window_days"] == 45)
    health = fuh_lib.load_json(os.path.join(run_dir, "source-health.json"))
    st = {k: v["status"] for k, v in health["signals"].items()}
    check("source health", st == {"hn": "ok", "github": "ok", "reddit": "skipped", "luma": "ok", "notion": "ok",
                                  "folk": "skipped", "registry_fr": "ok", "manual": "ok"}, str(st))
    check("activity health", set(health["activity"]) == {"hn", "github", "manual"})
    for s in fuh_lib.read_jsonl(os.path.join(run_dir, "signals.jsonl")):
        if fuh_lib.read_cached_text(os.path.join(run_dir, "cache"), s["url"]) is None:
            check(f"signal cached {s['signal_id']}", False)
            break
    else:
        check("every signal cached", True)
    channels = fuh_lib.load_json(os.path.join(run_dir, "channels.json"))
    check("channel map from people", channels["communities"]["Ask HN"]["people"] == 2)
    code2, _ = run([os.path.join(SCRIPTS, "pipeline.py"), "--config", os.path.join(EXAMPLE, "config.json"),
                    "--run-dir", run_dir, "--fixtures", API, "--today", TODAY])
    sl2 = fuh_lib.read_jsonl(os.path.join(run_dir, "shortlist.jsonl"))
    check("re-run is deterministic", code2 == 0 and sl2 == sl)
    return run_dir


# ---------------------------------------------------------------- 5. verify

PEOPLE = os.path.join(EXAMPLE, "people-20261012.jsonl")


def verify_rows(rows, run_dir, today=TODAY):
    sys.path.insert(0, SCRIPTS)
    import verify_people
    return verify_people.verify(rows, run_dir, os.path.join(run_dir, "cache"), CRIT, fuh_lib.parse_day(today))


def codes(res, pid):
    return {e["code"] for e in res["people"][pid]["errors"]}


def test_verify(run_dir):
    code, out = run([os.path.join(SCRIPTS, "verify_people.py"), PEOPLE, "--run-dir", run_dir, "--today", TODAY,
                     "--out", os.path.join(run_dir, "verify.json")])
    check("example people verify", code == 0, out[-600:])
    code, out = run([os.path.join(REPO, "shared", "scripts", "validate_json.py"), "--jsonl",
                     os.path.join(AGENT, "assets", "person.schema.json"), PEOPLE])
    check("example people match person schema", code == 0, out)
    base = fuh_lib.read_jsonl(PEOPLE)

    def tamper(fn, pid="p001"):
        rows = json.loads(json.dumps(base))
        row = next(r for r in rows if r["person_id"] == pid)
        fn(row, rows)
        return rows

    r = verify_rows(tamper(lambda p, _: p["signal"].__setitem__("excerpt", "Words that this person never wrote anywhere.")), run_dir)
    check("tamper excerpt", "excerpt" in codes(r, "p001"), str(codes(r, "p001")))
    r = verify_rows(tamper(lambda p, _: p["signal"].__setitem__("date", "2026-10-05"), "p002"), run_dir)
    check("tamper linkedin date vs post id", {"post-date", "not-in-run"} <= codes(r, "p002"), str(codes(r, "p002")))
    r = verify_rows(tamper(lambda p, _: p["activity"].__setitem__("weighted_posts", 9)), run_dir)
    check("tamper activity", "activity" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["activity"].__setitem__("status", "not_proven")), run_dir)
    check("inactive person refused", "activity" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p.__setitem__("score", 40)), run_dir)
    check("tamper score", "score" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["first_touch"].__setitem__("text", p["first_touch"]["text"] + " See https://swanbase.co/apply")), run_dir)
    check("link in first touch", "touch" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["first_touch"].update({"network": "x", "text": "word " * 70})), run_dir)
    check("x reply over 280", "touch" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["first_touch"].__setitem__("text", "A sentence with a dash \u2014 here, and more words.")), run_dir)
    check("em dash in touch", "touch" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["first_touch"].__setitem__("text", "Hi {{first_name}}, a placeholder was left in this message.")), run_dir)
    check("placeholder left", "touch" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, rows: p["first_touch"].__setitem__("text", rows[1]["first_touch"]["text"])), run_dir)
    check("same first touch for two people", "touch" in codes(r, "p001") or "touch" in codes(r, "p002"))
    r = verify_rows(tamper(lambda p, _: p["second_touch"].__setitem__("text", "x" * 230)), run_dir)
    check("connection note over 200", "touch" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p.update({"email": "minidenticons@4.2.1",
                                                  "email_source_url": "https://news.ycombinator.com/item?id=99000101"})), run_dir)
    check("package@version email refused", "email" in codes(r, "p001"))
    r = verify_rows(tamper(lambda p, _: p["networks"].__setitem__(0, {"network": "linkedin", "handle": "someone-else-fictive"}), "p002"), run_dir)
    check("signal owner mismatch", "owner" in codes(r, "p002"), str(codes(r, "p002")))
    r = verify_rows(tamper(lambda p, _: p.pop("first_touch")), run_dir)
    check("first touch required", "schema" in codes(r, "p001"))
    r = verify_rows(base, run_dir, today="2026-12-30")
    check("stale later", "stale" in codes(r, "p001"))
    return base


# ---------------------------------------------------------------- 6. export and handoff

def test_export(run_dir, tmp):
    out_dir = os.path.join(tmp, "project", "first-users-hunter")
    ledger = os.path.join(out_dir, "ledger.csv")
    code, out = run([os.path.join(SCRIPTS, "export_handoff.py"), PEOPLE, "--run-dir", run_dir, "--out-dir", out_dir,
                     "--today", TODAY, "--ledger", ledger])
    check("export exits 0", code == 0, out)
    with open(os.path.join(out_dir, "prospects-20261012.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        fh.seek(0)
        header = fh.readline().strip().split(",")
    v1 = ["prospect_id", "first_name", "last_name", "role", "company", "company_url", "profile_url", "email",
          "linkedin_url", "channel", "fit_rationale", "source_url", "language", "geography", "found_on"]
    check("csv v1 columns first, in order", header[:len(v1)] == v1, str(header[:16]))
    check("csv v2 signal columns", {"signal_url", "signal_date", "signal_excerpt", "activity_status", "first_touch_draft"} <= set(header))
    check("csv one row per person", len(rows) == 4 and all(r["activity_status"] == "active" for r in rows))
    schema = fuh_lib.load_json(fuh_lib.HANDOFF_SCHEMA)
    hand = os.path.join(out_dir, "handoff-20261012")
    for pid in ("p001", "p002", "p003", "p004"):
        d = fuh_lib.load_json(os.path.join(hand, "dossiers", pid, "prospect.json"))
        errs = validate(d, schema)
        check(f"dossier {pid} matches cold-outreach schema", not errs, "; ".join(errs[:2]))
        f1 = d["facts"][0]
        text = fuh_lib.read_cached_text(os.path.join(hand, "cache"), f1["source_url"])
        check(f"dossier {pid} excerpt in handoff cache", text and fuh_lib.norm_text(f1["excerpt"]) in fuh_lib.norm_text(text))
        check(f"dossier {pid} fact not in the future", f1["date"] <= TODAY)
    check("first touches file", os.path.isfile(os.path.join(out_dir, "first-touches-20261012.md")))
    led = fuh_lib.read_csv(ledger)
    check("ledger rows", len(led) == 4 and {r["status"] for r in led} == {"new"})

    # Re-run with the ledger: nobody comes back without a newer signal.
    c2 = os.path.join(tmp, "rerun")
    shutil.copytree(run_dir, c2)
    code, out = run([os.path.join(SCRIPTS, "candidates.py"), "--run-dir", c2, "--config", os.path.join(EXAMPLE, "config.json"),
                     "--ledger", ledger, "--today", TODAY])
    keys = {c["person_key"] for c in fuh_lib.read_jsonl(os.path.join(c2, "candidates.jsonl"))}
    check("ledger excludes people already listed", code == 0 and "hn:qforge_fictive" not in keys and "github:lumen-sketch-fictive" in keys, out[-300:])
    led[0]["status"] = "contacted"
    fuh_lib.write_csv(ledger, list(led[0].keys()), led)
    _, out = run([os.path.join(SCRIPTS, "candidates.py"), "--run-dir", c2, "--config", os.path.join(EXAMPLE, "config.json"),
                  "--ledger", ledger, "--today", TODAY])
    check("ledger contacted reason", "status contacted" in out, out[-300:])

    # Rows never contacted are purged after ledger_purge_days (default 60).
    led = fuh_lib.read_csv(ledger)
    led.append({"person_key": "hn:someone_old", "person_id": "p009", "name": "someone_old", "status": "new",
                "found_on": "2026-07-01", "signal_url": "https://news.ycombinator.com/item?id=1"})
    led.append({"person_key": "hn:someone_met", "person_id": "p010", "name": "someone_met", "status": "met",
                "found_on": "2026-07-01", "signal_url": "https://news.ycombinator.com/item?id=2"})
    fuh_lib.write_csv(ledger, list(led[0].keys()), led)
    code, out = run([os.path.join(SCRIPTS, "export_handoff.py"), PEOPLE, "--run-dir", run_dir, "--out-dir", out_dir,
                     "--today", TODAY, "--ledger", ledger])
    keys = {r["person_key"] for r in fuh_lib.read_csv(ledger)}
    check("ledger purge of old uncontacted rows", code == 0 and "hn:someone_old" not in keys and "hn:someone_met" in keys, out)

    # Export refused while an error remains.
    bad = os.path.join(tmp, "bad.jsonl")
    rows_bad = fuh_lib.read_jsonl(PEOPLE)
    rows_bad[0]["signal"]["excerpt"] = "Words that this person never wrote anywhere."
    fuh_lib.write_jsonl(bad, rows_bad)
    code, out = run([os.path.join(SCRIPTS, "export_handoff.py"), bad, "--run-dir", run_dir, "--out-dir", out_dir + "-bad", "--today", TODAY])
    check("export refused on errors", code == 1 and not os.path.exists(out_dir + "-bad"), out)

    # Writing gate on the first touches (shared engine).
    lint = os.path.join(REPO, "shared", "skills", "writing-gate", "scripts", "lint_copy.py")
    if os.path.isfile(lint):
        code, out = run([lint, os.path.join(out_dir, "first-touches-20261012.md")])
        check("writing gate 0 BLOCK on first touches", code == 0, out[-400:])

    # The handoff schema copy has not drifted from cold-outreach-builder's.
    src = os.path.join(COB, "assets", "prospect.schema.json")
    if os.path.isfile(src):
        check("handoff schema copy in sync", fuh_lib.load_json(src) == schema)
        # cold-outreach-builder reads the handoff with its own scripts.
        code, out = run([os.path.join(COB, "scripts", "verify_dossiers.py"), os.path.join(hand, "dossiers"),
                         "--cache", os.path.join(hand, "cache"), "--today", TODAY, "--out", os.path.join(tmp, "cob-verify.json")])
        check("cold-outreach verify_dossiers on the handoff", code == 0, out[-400:])
        cob_run = os.path.join(tmp, "cob-run")
        code, out = run([os.path.join(COB, "scripts", "run_dossiers.py"), "prepare", "--leads",
                         os.path.join(out_dir, "prospects-20261012.csv"), "--run-dir", cob_run])
        for sub in ("dossiers", "cache"):
            shutil.copytree(os.path.join(hand, sub), os.path.join(cob_run, sub), dirs_exist_ok=True)
        code2, out2 = run([os.path.join(COB, "scripts", "run_dossiers.py"), "status", "--run-dir", cob_run])
        check("cold-outreach run_dossiers sees every dossier done", code == 0 and code2 == 0 and "4 done" in out2, out + out2)
    elif VERBOSE:
        print("skip cold-outreach-builder integration: agent folder not found")


# ---------------------------------------------------------------- 7. fetch guard

def test_fetch_guard(tmp):
    cache = os.path.join(tmp, "guard-cache")
    secret = os.path.join(tmp, "secret.txt")
    with open(secret, "w", encoding="utf-8") as fh:
        fh.write("local file that must never reach the cache")
    for url in ("file://" + secret, "ftp://ftp.example/file.txt"):
        code, out = run([os.path.join(SCRIPTS, "cache_page.py"), "--cache", cache, url])
        check(f"cache_page refuses {url.split(':')[0]}://", code == 1 and "only http and https" in out, out[-300:])
        check(f"nothing cached for {url.split(':')[0]}://", not any(os.path.isfile(p) for p in fuh_lib.cache_paths(cache, url)))
    code, out = run([os.path.join(SCRIPTS, "cache_page.py"), "--cache", cache, "http://169.254.169.254/latest/meta-data/"])
    check("cache_page refuses a link-local host", code == 1 and "link-local" in out, out[-300:])


# ---------------------------------------------------------------- 8. hygiene

def test_hygiene():
    banned = ("exa ", "firecrawl", "serpapi", "smtplib", "apollo", "perplexity", "read.cv", "new.json", "search.json")
    for root, _, files in os.walk(SCRIPTS):
        for name in files:
            if name.endswith(".py"):
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    low = fh.read().lower()
                hits = [b for b in banned if b in low and not (b in ("new.json", "search.json") and name == "reddit.py")]
                check(f"no paid API or dead source in {name}", not hits, str(hits))


def main():
    tmp = tempfile.mkdtemp(prefix="fuh-tests-")
    try:
        test_help()
        test_dates()
        test_collectors()
        run_dir = test_pipeline(tmp)
        test_verify(run_dir)
        test_export(run_dir, tmp)
        test_fetch_guard(tmp)
        test_hygiene()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{PASSED} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
