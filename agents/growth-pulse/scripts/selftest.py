#!/usr/bin/env python3
"""
selftest.py: offline regression test of growth-pulse (no network, no key, stdlib only).

    python3 scripts/selftest.py                    # every check
    python3 scripts/selftest.py --only connectors,report
    python3 scripts/selftest.py --write-example    # regenerate examples/swanbase-20261014/pulse.json after a deliberate change

Checks, all on the fictional swanbase fixtures of scripts/fixtures/:
  help         every script answers --help with exit 0
  fixtures     make_fixtures.py reproduces the committed fixtures byte for byte
  connectors   API replay and CSV export give identical source files (Umami, Plausible,
               GA4, Search Console, Stripe); no key and no CSV gives a 'missing' health
               file and exit 1; a replayed HTTP 429 gives 'error' and exit 1; a Search
               Console export three days short is 'stale'; every file passes its schema;
               no customer id leaves the revenue connector
  zernio       connect_zernio.py on recorded answers: social metrics per network, the same
               figures as the CSV exports, followers as net daily changes across a gap, no
               account id, handle or email written, HTTP 402 and 403, plain http refused;
               run_pulse.py against a local HTTP server: Zernio when enabled with a key (GET
               only, bearer header), CSV fallback with its reason in the notes
  example      the example run (connectors, compute) rebuilds the committed pulse.json
               byte for byte, and it passes assets/pulse.schema.json
  rules        no percentage on fewer than min_events_for_pct events anywhere in
               pulse.json; small rates are null with their counts; every correlation is
               causal: false and comes from a pre-registered pair
  gsc          the decline definition equals seo-audit's gsc-bands.json (when that agent
               is in the repo); the example totals decline with cause position; a stale
               Search Console week computes no decline and flags the metrics incomplete
  followup     last run's three experiments come out met, running and not_measurable
  report       the example report passes check_report.py; five mutations each fail with
               the expected code (invented number, percent on a small volume, causal
               sentence, unlabeled correlation, missing section)
  experiments  the example handoff passes check_experiments.py and --fill changes
               nothing; mutations fail (two experiments, unknown metric, typed baseline,
               spend without approval, bad evidence, invented number in a hypothesis)
  runner       run_pulse.py on a temporary project with CSV exports only writes pulse.json
  shared       the example report passes the shared writing gate at 0 BLOCK and a sample
               runs.jsonl line passes the shared run-record schema (skipped when shared/
               is absent)

Exit 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
REPO = AGENT.parent.parent
FIX = SCRIPTS / "fixtures"
EX = AGENT / "examples" / "swanbase-20261014"
TODAY = "2026-10-14"
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

KEY_VARS = ["ZERNIO_API_KEY", "ZERNIO_BASE_URL", "UMAMI_API_KEY", "UMAMI_API_TOKEN", "UMAMI_USERNAME", "UMAMI_BASE_URL", "PLAUSIBLE_API_KEY", "GA4_ACCESS_TOKEN",
            "GSC_ACCESS_TOKEN", "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "UMAMI_WEBSITE_ID", "PLAUSIBLE_SITE_ID"]
ENV = {k: v for k, v in os.environ.items() if k not in KEY_VARS}
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))


def run(*args, env=None):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, env=env or ENV)
    if "Traceback" in r.stderr:
        print(r.stderr[-2500:])
    return r


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ pipelines

def example_run(out: Path) -> Path:
    """The example run: Umami and Search Console by API replay, social and revenue by CSV,
    Plausible and GA4 not configured."""
    d = out / "data"
    t = ["--today", TODAY]
    run(SCRIPTS / "connect_umami.py", *t, "--fixtures", FIX / "umami" / "api", "--out", d / "umami.json")
    run(SCRIPTS / "connect_gsc.py", *t, "--fixtures", FIX / "gsc" / "api", "--out", d / "gsc.json")
    run(SCRIPTS / "connect_social.py", *t, "--csv", f"linkedin={FIX / 'social' / 'linkedin.csv'}",
        f"instagram={FIX / 'social' / 'instagram-posts.csv'}", "--out", d / "social.json")
    run(SCRIPTS / "connect_revenue.py", *t, "--csv", FIX / "revenue" / "csv" / "payments.csv", "--currency", "eur", "--out", d / "revenue.json")
    run(SCRIPTS / "connect_plausible.py", *t, "--out", d / "plausible.json")
    run(SCRIPTS / "connect_ga4.py", *t, "--out", d / "ga4.json")
    r = run(SCRIPTS / "compute_pulse.py", "--sources", *sorted(d.glob("*.json")), "--config", EX / "config.json",
            "--actions", FIX / "actions.csv", "--previous-experiments", FIX / "previous" / "experiments-20260930.json",
            "--today", TODAY, "--out-dir", out)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
    return out / "pulse.json"


# ------------------------------------------------------------------ checks

def t_help(tmp):
    for s in sorted(SCRIPTS.glob("*.py")):
        if s.name in ("gp_lib.py", "selftest.py"):
            continue
        r = run(s, "--help")
        check(f"help {s.name}", r.returncode == 0 and "usage" in r.stdout.lower(), r.stderr[-300:])
    r = run(FIX / "make_fixtures.py", "--help")
    check("help make_fixtures.py", r.returncode == 0, r.stderr[-300:])


def t_fixtures(tmp):
    r = run(FIX / "make_fixtures.py", "--check")
    check("fixtures reproducible", r.returncode == 0, r.stdout + r.stderr)


def t_connectors(tmp):
    t = ["--today", TODAY]
    pairs = {
        "umami": (["--fixtures", FIX / "umami" / "api"], ["--csv", FIX / "umami" / "csv" / "umami-daily.csv", FIX / "umami" / "csv" / "umami-events.csv"]),
        "plausible": (["--fixtures", FIX / "plausible" / "api"], ["--csv", FIX / "plausible" / "csv" / "visitors.csv", FIX / "plausible" / "csv" / "goals.csv"]),
        "ga4": (["--fixtures", FIX / "ga4" / "api"], ["--csv", FIX / "ga4" / "csv" / "ga4-traffic.csv", FIX / "ga4" / "csv" / "ga4-events.csv"]),
        "gsc": (["--fixtures", FIX / "gsc" / "api"], ["--csv", FIX / "gsc" / "csv" / "Dates.csv"]),
        "revenue": (["--fixtures", FIX / "revenue" / "api"], ["--csv", FIX / "revenue" / "csv" / "payments.csv"]),
    }
    for name, (api_args, csv_args) in pairs.items():
        a, c = tmp / f"{name}-api.json", tmp / f"{name}-csv.json"
        ra = run(SCRIPTS / f"connect_{name}.py", *t, *api_args, "--out", a)
        rc = run(SCRIPTS / f"connect_{name}.py", *t, *csv_args, "--out", c)
        ok = ra.returncode == 0 and rc.returncode == 0
        da, dc = (load(a), load(c)) if ok else ({}, {})
        check(f"connectors {name}: API replay and CSV agree", ok and da["daily"] == dc["daily"] and da["status"] == dc["status"] == "ok",
              (ra.stderr + rc.stderr)[-300:])
        check(f"connectors {name}: schema", ok and G.schema_errors(da, "source.schema.json") in ([], None)
              and G.schema_errors(dc, "source.schema.json") in ([], None))
    rev = (tmp / "revenue-csv.json").read_text(encoding="utf-8")
    check("connectors revenue: no customer id written", "cus_" not in rev and "@" not in rev)
    check("connectors revenue: failed charge left out", any("not succeeded" in n for n in load(tmp / "revenue-csv.json")["notes"]))
    gsc_api = load(tmp / "gsc-api.json")
    check("connectors gsc: weekly query and page rows from the API", {b["dimension"] for b in gsc_api["breakdowns"]} == {"query", "page"})
    check("connectors gsc: CSV export has no breakdown", load(tmp / "gsc-csv.json")["breakdowns"] == [])
    for name in ("umami", "plausible", "ga4", "gsc", "revenue"):
        r = run(SCRIPTS / f"connect_{name}.py", *t, "--out", tmp / f"{name}-none.json")
        h = load(tmp / f"{name}-none.json") if (tmp / f"{name}-none.json").exists() else {}
        check(f"connectors {name}: no key, no CSV -> missing, exit 1", r.returncode == 1 and h.get("status") == "missing"
              and "csv" in h.get("message", "").lower(), r.stderr[-300:])
    r = run(SCRIPTS / "connect_social.py", *t, "--out", tmp / "social-none.json")
    check("connectors social: no CSV -> missing, exit 1", r.returncode == 1 and load(tmp / "social-none.json")["status"] == "missing")
    r = run(SCRIPTS / "connect_umami.py", *t, "--fixtures", FIX / "umami" / "api-error", "--out", tmp / "umami-err.json")
    check("connectors umami: HTTP 429 -> error, exit 1", r.returncode == 1 and load(tmp / "umami-err.json")["status"] == "error")
    r = run(SCRIPTS / "connect_gsc.py", *t, "--csv", FIX / "gsc" / "csv" / "Dates-lag.csv", "--out", tmp / "gsc-lag.json")
    lag = load(tmp / "gsc-lag.json")
    check("connectors gsc: export three days short -> stale", r.returncode == 0 and lag["status"] == "stale"
          and lag["missing_days"] == ["2026-10-09", "2026-10-10", "2026-10-11"], lag.get("status"))
    r = run(SCRIPTS / "connect_umami.py", *t, "--csv", tmp / "absent.csv", "--out", tmp / "x.json")
    check("connectors: unreadable CSV -> exit 2", r.returncode == 2)
    r = run(SCRIPTS / "connect_social.py", *t, "--csv", f"linkedin={FIX / 'social' / 'linkedin.csv'}",
            f"instagram={FIX / 'social' / 'instagram-posts.csv'}", "--out", tmp / "social.json")
    s = load(tmp / "social.json")
    check("connectors social: LinkedIn daily (US dates) and Instagram post export",
          r.returncode == 0 and "linkedin.impressions" in s["metrics"] and "instagram.posts" in s["metrics"] and s["status"] == "ok")


def t_zernio(tmp):
    t = ["--today", TODAY]
    api_dir = FIX / "zernio" / "api"
    out = tmp / "zernio.json"
    r = run(SCRIPTS / "connect_zernio.py", *t, "--fixtures", api_dir, "--out", out)
    ok = r.returncode == 0
    check("zernio: replay writes the social source file", ok, r.stderr[-300:])
    if not ok:
        return
    z = load(out)
    check("zernio: source social, provider fixture, every day, schema", z["source"] == "social" and z["provider"] == "fixture"
          and z["status"] == "ok" and G.schema_errors(z, "source.schema.json") in ([], None), z["status"])
    wanted = {f"{n}.{m}" for n in ("linkedin", "instagram", "x") for m in ("impressions", "engagements", "clicks", "reposts", "followers_gained", "posts")}
    check("zernio: every metric per network, twitter written as x", set(z["metrics"]) == wanted, set(z["metrics"]) ^ wanted)
    run(SCRIPTS / "connect_social.py", *t, "--csv", f"linkedin={FIX / 'social' / 'linkedin.csv'}",
        f"instagram={FIX / 'social' / 'instagram-posts.csv'}", "--out", tmp / "zernio-csv.json")
    c = load(tmp / "zernio-csv.json")
    shared = [m for m in c["metrics"] if m in z["metrics"] and m != "instagram.clicks"]
    zd, cd = {r["date"]: r["values"] for r in z["daily"]}, {r["date"]: r["values"] for r in c["daily"]}
    diff = [(d, m) for d in cd for m in shared if cd[d].get(m) != zd.get(d, {}).get(m)]
    check("zernio: same daily figures as the CSV exports on the shared metrics", len(shared) >= 8 and not diff, diff[:5])
    stats = load(api_dir / "follower-stats.json")["stats"]
    gain = lambda n: sum(v["values"][f"{n}.followers_gained"] for v in z["daily"])
    span = lambda a: stats[a][-1]["followers"] - stats[a][0]["followers"]
    check("zernio: followers are net daily changes, a gap in the history keeps the total",
          gain("linkedin") == span("fict-account-li") and gain("x") == span("fict-account-x") < 0, (gain("linkedin"), gain("x")))
    raw = out.read_text(encoding="utf-8")
    check("zernio: no account id, handle, name or email written", not any(w in raw for w in ("fict-account", "fict-profile", "@", "Swanbase Fictional")))
    r = run(SCRIPTS / "connect_zernio.py", *t, "--fixtures", api_dir, "--platforms", "x", "--out", tmp / "zernio-x.json")
    check("zernio: --platforms x reads that network only", r.returncode == 0 and {m.split(".")[0] for m in load(tmp / "zernio-x.json")["metrics"]} == {"x"})
    r = run(SCRIPTS / "connect_zernio.py", *t, "--out", tmp / "zernio-none.json")
    h = load(tmp / "zernio-none.json")
    check("zernio: no key -> missing, exit 1, names the CSV fallback", r.returncode == 1 and h["status"] == "missing" and "csv" in h["message"].lower(), h["message"])

    def broken(name, **errors):
        d = tmp / name
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(api_dir, d)
        for key, code in errors.items():
            (d / f"{key.replace('_', '-')}.json").write_text(json.dumps({"_http_error": code}), encoding="utf-8")
        return d
    r = run(SCRIPTS / "connect_zernio.py", *t, "--fixtures", broken("z402", daily_metrics_published=402), "--out", tmp / "z402.json")
    h = load(tmp / "z402.json")
    check("zernio: HTTP 402 -> error, exit 1, says analytics access", r.returncode == 1 and h["status"] == "error" and "analytics access" in h["message"], h["message"])
    r = run(SCRIPTS / "connect_zernio.py", *t, "--fixtures", broken("z403", follower_stats=403), "--out", tmp / "z403.json")
    h = load(tmp / "z403.json") if r.returncode == 0 else {"metrics": ["?"], "notes": []}
    check("zernio: follower call refused -> data without followers_gained, with a note",
          not any("followers_gained" in m for m in h["metrics"]) and "linkedin.impressions" in h["metrics"]
          and any("followers_gained left out" in n and "HTTP 403" in n for n in h["notes"]), h["notes"])
    bad = broken("zbad")
    (bad / "daily-metrics-published.json").write_text(json.dumps({"dailyData": ["not a row"]}), encoding="utf-8")
    r = run(SCRIPTS / "connect_zernio.py", *t, "--fixtures", bad, "--out", tmp / "zbad.json")
    check("zernio: an answer of an unexpected shape -> error, exit 1, no crash", r.returncode == 1 and load(tmp / "zbad.json")["status"] == "error", r.stderr[-300:])
    r = run(SCRIPTS / "connect_zernio.py", *t, "--csv", FIX / "social" / "linkedin.csv", "--out", tmp / "x.json")
    check("zernio: --csv refused, exit 2", r.returncode == 2)
    r = run(SCRIPTS / "connect_zernio.py", *t, "--out", tmp / "x.json",
            env={**ENV, "ZERNIO_API_KEY": "fictional-key", "ZERNIO_BASE_URL": "http://zernio.example/api/v1"})
    check("zernio: plain http base refused, exit 2", r.returncode == 2 and "https" in r.stderr, r.stderr[-200:])
    t_zernio_runner(tmp, api_dir)


def t_zernio_runner(tmp, api_dir):
    """run_pulse.py against a local server that answers from the fixtures: the real HTTP path."""
    seen = []
    state = {"refuse": False}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def answer(self):
            u = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            seen.append((self.command, u.path, self.headers.get("authorization")))
            name = "follower-stats" if u.path.endswith("/accounts/follower-stats") else (
                f"daily-metrics-received-{q.get('platform')}" if q.get("attribution") == "received" else "daily-metrics-published")
            body, code = b"{}", 402
            if not state["refuse"] and self.command == "GET" and (api_dir / f"{name}.json").exists():
                body, code = (api_dir / f"{name}.json").read_bytes(), 200
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = answer

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {**ENV, "ZERNIO_API_KEY": "fictional-key", "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
           "ZERNIO_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}/api/v1"}

    def project(name, zernio, csv_files):
        gp = tmp / name / "growth-pulse"
        (gp / "exports").mkdir(parents=True)
        shutil.copy(FIX / "social" / "linkedin.csv", gp / "exports" / "linkedin.csv")
        cfg = load(AGENT / "config.example.json")
        cfg["project"] = name
        cfg["sources"] = {"social": {"zernio": zernio, "csv": csv_files}}
        (gp / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        return tmp / name

    def pulse(proj, use_env):
        r = run(SCRIPTS / "run_pulse.py", "--project-dir", proj, "--today", TODAY, env=use_env)
        path = proj / "growth-pulse" / "20261014" / "data" / "social.json"
        return r, (load(path) if path.exists() else {}), proj / "growth-pulse" / "20261014" / "pulse.json"

    on = {"enabled": True, "profile_id": "fict-profile-1", "platforms": []}
    exports = ["linkedin=exports/linkedin.csv"]
    try:
        r, s, p = pulse(project("z-api", on, exports), env)
        check("zernio runner: enabled with a key reads the API before the CSV", r.returncode == 0 and s.get("provider") == "api" and p.exists(), (r.stdout + r.stderr)[-400:])
        check("zernio runner: GET only, bearer header, the key never printed", seen and all(c == "GET" and a == "Bearer fictional-key" for c, _, a in seen)
              and "fictional-key" not in r.stdout + r.stderr, seen[:3])
        check("zernio runner: pulse.json reads the net follower loss", p.exists() and any(m["id"] == "social.x.followers_gained" for m in load(p)["metrics"]))
        state["refuse"] = True
        r, s, _ = pulse(project("z-refused", on, exports), env)
        check("zernio runner: HTTP 402 falls back to the CSV, reason in the notes", r.returncode == 0 and s.get("provider") == "csv"
              and any("Zernio not used" in n and "HTTP 402" in n for n in s.get("notes", [])), s.get("notes"))
        r, s, p = pulse(project("z-refused-nocsv", on, []), env)
        check("zernio runner: HTTP 402 without a CSV -> error, the run goes on", s.get("status") == "error" and p.exists(), s.get("message"))
        state["refuse"] = False
        r, s, _ = pulse(project("z-nokey", on, exports), ENV)
        check("zernio runner: no key falls back to the CSV, reason in the notes", s.get("provider") == "csv"
              and any("ZERNIO_API_KEY is not set" in n for n in s.get("notes", [])), s.get("notes"))
        r, s, _ = pulse(project("z-nokey-nocsv", on, []), ENV)
        check("zernio runner: no key, no CSV -> missing", s.get("status") == "missing", s.get("status"))
        seen.clear()
        r, s, _ = pulse(project("z-off", dict(on, enabled=False), exports), env)
        check("zernio runner: not enabled -> CSV, no call even with a key", s.get("provider") == "csv" and not seen and not s.get("notes", [""])[-1].startswith("Zernio"), seen[:2])
    finally:
        server.shutdown()


def t_example(tmp):
    p = example_run(tmp / "example")
    ok = p.exists()
    check("example: pulse.json written", ok)
    if not ok:
        return
    check("example: pulse.json passes its schema", G.schema_errors(load(p), "pulse.schema.json") in ([], None))
    committed = EX / "pulse.json"
    check("example: rebuilds the committed pulse.json byte for byte",
          committed.exists() and committed.read_text(encoding="utf-8") == p.read_text(encoding="utf-8"),
          "run selftest.py --write-example after a deliberate change")


def t_rules(tmp):
    p = load(EX / "pulse.json")
    n_min = p["rules"]["volume"]["min_events_for_pct"]
    bad = []
    for m in p["metrics"]:
        vals = {s["week"]: s["value"] for s in m["series"]}
        if m["kind"] == "count":
            if m["vs_previous"]["pct"] is not None and (m["previous"] or 0) < n_min:
                bad.append(m["id"] + " vs_previous")
            if m["vs_baseline"]["pct"] is not None and (m["baseline"] or 0) < n_min:
                bad.append(m["id"] + " vs_baseline")
        if m["kind"] == "rate":
            for s in m["series"]:
                if s["value"] is not None and (s["numerator"] < n_min or s["denominator"] < n_min):
                    bad.append(f"{m['id']} {s['week']}")
        _ = vals
    check("rules: no percentage under min_events_for_pct", not bad, bad)
    small_rates = [m for m in p["metrics"] if m["kind"] == "rate" and m["current"] is None]
    check("rules: small rates are null with their counts", small_rates and all(m["counts"]["current"]["numerator"] is not None for m in small_rates))
    pairs = p["rules"]["correlation"]["pairs"]
    check("rules: correlations never causal", p["correlations"] and all(c["causal"] is False for c in p["correlations"]))
    check("rules: correlations only on pre-registered pairs",
          all(any(fnmatch.fnmatchcase(c["a"], q["a"]) and fnmatch.fnmatchcase(c["b"], q["b"]) for q in pairs) for c in p["correlations"]))
    check("rules: every source listed in health", [s["source"] for s in p["sources"]] == list(G.SOURCES))


def t_gsc(tmp):
    rules = load(AGENT / "assets" / "pulse-rules.json")["gsc_decline"]
    seo = REPO / "agents" / "seo-audit" / "assets" / "gsc-bands.json"
    strip = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}
    if seo.exists():
        check("gsc: decline definition equals seo-audit's gsc-bands.json", strip(rules) == strip(load(seo)["decline"]))
    else:
        print("SKIP gsc: seo-audit not in this repo")
    g = load(EX / "pulse.json")["gsc"]
    check("gsc: example totals decline, cause position", g["available"] and g["totals"]["decline"] and g["totals"]["cause"] == "position")
    check("gsc: declining pages listed", any(r["key"].endswith("/program/") for r in g["pages"]))
    d = tmp / "lag"
    run(SCRIPTS / "connect_gsc.py", "--today", TODAY, "--csv", FIX / "gsc" / "csv" / "Dates-lag.csv", "--out", d / "data" / "gsc.json")
    run(SCRIPTS / "compute_pulse.py", "--sources", d / "data" / "gsc.json", "--today", TODAY, "--out-dir", d)
    p = load(d / "pulse.json")
    clicks = next(m for m in p["metrics"] if m["id"] == "gsc.clicks")
    check("gsc: stale week -> no decline, metrics incomplete", not p["gsc"]["available"] and "incomplete_week" in clicks["flags"]
          and clicks["vs_previous"]["signal"] == "n/a")
    cfg = tmp / "seo-config.json"
    cfg.write_text(json.dumps({"_comment": "test", "gsc_bands": {"decline": {"max_change_pct": -60}}}), encoding="utf-8")
    run(SCRIPTS / "compute_pulse.py", "--sources", *sorted((tmp / "example" / "data").glob("*.json")), "--config", EX / "config.json",
        "--seo-config", cfg, "--today", TODAY, "--out-dir", tmp / "seo-override")
    q = load(tmp / "seo-override" / "pulse.json")["gsc"]
    check("gsc: seo-audit config override applies here too", q["definition"]["max_change_pct"] == -60 and not q["totals"]["decline"])


def t_followup(tmp):
    f = {e["id"]: e["verdict"] for e in load(EX / "pulse.json")["experiments_followup"]}
    check("followup: met, running, not_measurable",
          f == {"E-20260930-1": "met", "E-20260930-2": "running", "E-20260930-3": "not_measurable"}, f)


def report_files():
    reps = sorted(EX.glob("growth-pulse-*.md"))
    exps = sorted(EX.glob("experiments-*.json"))
    return (reps[0] if reps else None), (exps[0] if exps else None)


def t_report(tmp):
    rep, exp = report_files()
    if not rep or not exp:
        check("report: example report and experiments exist", False)
        return
    r = run(SCRIPTS / "check_report.py", rep, "--pulse", EX / "pulse.json", "--experiments", exp, "--json")
    out = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    check("report: example passes check_report.py", r.returncode == 0, [f for f in out.get("findings", []) if f["level"] == "BLOCK"][:5])
    text = rep.read_text(encoding="utf-8")
    mutations = {
        "unknown-number": text.replace("## What moved\n", "## What moved\n\nSite visitors reached 6123 this week.\n", 1),
        "unknown-percent": text.replace("## What moved\n", "## What moved\n\nNewsletter signups grew 8.3% on last week.\n", 1),
        "causal-claim": text.replace("## What moved\n", "## What moved\n\nThe carousel drove the LinkedIn surge.\n", 1),
        "unlabeled-correlation": text.replace("## What moved\n", "## What moved\n\nSearch clicks and visitors go together (C5).\n", 1),
        "missing-section": text.replace("## Limitations", "## Caveats"),
    }
    for code, mutated in mutations.items():
        mp = tmp / f"mut-{code}.md"
        mp.write_text(mutated, encoding="utf-8")
        r = run(SCRIPTS / "check_report.py", mp, "--pulse", EX / "pulse.json", "--experiments", exp, "--json")
        codes = {f["code"] for f in json.loads(r.stdout)["findings"] if f["level"] == "BLOCK"} if r.stdout.strip().startswith("{") else set()
        check(f"report: mutation {code} blocks", r.returncode == 1 and code in codes, codes)


def t_experiments(tmp):
    _, exp = report_files()
    if not exp:
        check("experiments: example handoff exists", False)
        return
    r = run(SCRIPTS / "check_experiments.py", exp, "--pulse", EX / "pulse.json", "--config", EX / "config.json", "--json")
    check("experiments: example passes", r.returncode == 0, r.stdout[-600:])
    cp = tmp / "exp-fill.json"
    shutil.copy(exp, cp)
    run(SCRIPTS / "check_experiments.py", cp, "--pulse", EX / "pulse.json", "--fill")
    check("experiments: --fill on the example changes nothing", cp.read_text(encoding="utf-8") == exp.read_text(encoding="utf-8"))
    base = load(exp)

    def mutate(code, fn):
        d = copy.deepcopy(base)
        fn(d)
        mp = tmp / f"exp-{code}.json"
        mp.write_text(json.dumps(d, indent=2), encoding="utf-8")
        r = run(SCRIPTS / "check_experiments.py", mp, "--pulse", EX / "pulse.json", "--config", EX / "config.json", "--json")
        codes = {f["code"] for f in json.loads(r.stdout)["findings"] if f["level"] == "BLOCK"} if r.stdout.strip().startswith("{") else set()
        check(f"experiments: mutation {code} blocks", r.returncode == 1 and code in codes, codes)

    mutate("count", lambda d: d["experiments"].pop())
    mutate("unknown-metric", lambda d: d["experiments"][0]["metric"].update(id="umami.event.demo_booked"))
    mutate("baseline", lambda d: d["experiments"][1]["baseline"].update(value=600))
    mutate("spend-gate", lambda d: d["experiments"][0]["cost"].update(cash_eur=150, spend_requires_approval=False))
    mutate("bad-evidence", lambda d: d["experiments"][0]["evidence"].append("correlations/C99"))
    mutate("unknown-number", lambda d: d["experiments"][1].update(hypothesis=d["experiments"][1]["hypothesis"].replace("because", "by 37% because", 1)))
    mutate("over-budget", lambda d: d["experiments"][0]["cost"].update(cash_eur=150, spend_requires_approval=True))


def t_runner(tmp):
    proj = tmp / "acme"
    gp = proj / "growth-pulse"
    ex = gp / "exports"
    ex.mkdir(parents=True)
    for src, dst in ((FIX / "umami" / "csv" / "umami-daily.csv", "umami-daily.csv"), (FIX / "umami" / "csv" / "umami-events.csv", "umami-events.csv"),
                     (FIX / "gsc" / "csv" / "Dates.csv", "Dates.csv"), (FIX / "social" / "linkedin.csv", "linkedin.csv"),
                     (FIX / "revenue" / "csv" / "payments.csv", "payments.csv")):
        shutil.copy(src, ex / dst)
    shutil.copy(FIX / "actions.csv", gp / "actions.csv")
    cfg = load(AGENT / "config.example.json")
    cfg["project"] = "acme"
    cfg["sources"]["umami"]["csv"] = ["exports/umami-daily.csv", "exports/umami-events.csv"]
    cfg["sources"]["gsc"]["csv"] = ["exports/Dates.csv"]
    cfg["sources"]["social"]["csv"] = ["linkedin=exports/linkedin.csv"]
    cfg["sources"]["revenue"]["csv"] = ["exports/payments.csv"]
    cfg["events"] = {"apply_click": "activation", "newsletter_signup": "activation", "invite_link_copied": "referral"}
    (gp / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    shutil.copy(FIX / "previous" / "experiments-20260930.json", gp / "experiments-20260930.json")
    r = run(SCRIPTS / "run_pulse.py", "--project-dir", proj, "--today", TODAY)
    out = gp / "20261014" / "pulse.json"
    ok = r.returncode == 0 and out.exists()
    check("runner: run_pulse.py on CSV exports writes pulse.json", ok, (r.stdout + r.stderr)[-500:])
    if ok:
        p = load(out)
        st = {s["source"]: s["status"] for s in p["sources"]}
        check("runner: health per source", st == {"plausible": "missing", "umami": "ok", "ga4": "missing", "gsc": "ok", "social": "ok", "revenue": "ok"}, st)
        check("runner: picked last run's experiments", p["previous_experiments"] and p["previous_experiments"]["file"] == "experiments-20260930.json")
        check("runner: totals only from the UI export, decline still computed", p["gsc"]["available"] and not p["gsc"]["breakdowns_available"])


def t_shared(tmp):
    lint = REPO / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"
    validator = REPO / "shared" / "scripts" / "validate_json.py"
    rep, _ = report_files()
    if not lint.exists() or not rep:
        print("SKIP shared: writing gate absent")
    else:
        r = run(lint, "--lang", "en", "--json", rep)
        check("shared: example report passes the writing gate (0 BLOCK)", r.returncode == 0, r.stdout[-800:])
    if not validator.exists():
        print("SKIP shared: validator absent")
        return
    line = {"ts": "2026-10-14T09:30:00+02:00", "agent": "growth-pulse", "label": "week-2026-W41", "status": "partial",
            "inputs_hash": load(EX / "pulse.json")["inputs_hash"],
            "outputs": ["growth-pulse/growth-pulse-20261014.md", "growth-pulse/experiments-20261014.json", "growth-pulse/20261014/pulse.json"],
            "providers": {"web_analytics": "umami api", "search_console": "api", "social_stats": "csv", "revenue": "csv"},
            "checks": {"pulse_schema": "pass", "report_numbers": "pass", "experiments": "pass", "copy_lint": "pass"},
            "critic_verdict": "none", "human_verdict": "none", "decisions_added": [], "notes": "plausible and ga4 not configured"}
    p = tmp / "runs.jsonl"
    p.write_text(json.dumps(line) + "\n", encoding="utf-8")
    r = run(validator, "--jsonl", REPO / "shared" / "schemas" / "run-record.schema.json", p)
    check("shared: runs.jsonl line passes run-record schema", r.returncode == 0, r.stdout + r.stderr)
    r = run(validator, AGENT / "assets" / "experiments.schema.json", report_files()[1])
    check("shared: example handoff passes validate_json.py", r.returncode == 0, r.stdout + r.stderr)


CHECKS = {"help": t_help, "fixtures": t_fixtures, "connectors": t_connectors, "zernio": t_zernio, "example": t_example, "rules": t_rules,
          "gsc": t_gsc, "followup": t_followup, "report": t_report, "experiments": t_experiments, "runner": t_runner, "shared": t_shared}


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline regression test of growth-pulse (fictional fixtures, no network, no key).")
    ap.add_argument("--only", help="comma-separated checks: " + ",".join(CHECKS))
    ap.add_argument("--keep", help="work in this folder instead of a temporary one")
    ap.add_argument("--write-example", action="store_true", help="rebuild examples/swanbase-20261014/pulse.json and exit")
    args = ap.parse_args()
    tmp = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="growth-pulse-"))
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        if args.write_example:
            p = example_run(tmp / "example")
            shutil.copy(p, EX / "pulse.json")
            print(f"wrote {EX / 'pulse.json'}")
            return 0
        names = args.only.split(",") if args.only else list(CHECKS)
        if "example" not in names and any(n in names for n in ("gsc",)):
            example_run(tmp / "example")
        for n in names:
            CHECKS[n](tmp)
    finally:
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
