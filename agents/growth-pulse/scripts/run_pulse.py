#!/usr/bin/env python3
"""
run_pulse.py

One command for the weekly collection and computation: runs every connector the
project config declares, then compute_pulse.py. The report and the experiments are
written afterwards by the model (skills writing-the-pulse-report and
designing-aarrr-experiments) and checked by check_report.py and check_experiments.py.

    python3 run_pulse.py --project-dir <your-projects-root>/<project> --today 2026-10-14
    python3 run_pulse.py --project-dir <project> --previous <project>/growth-pulse/experiments-20261007.json

Reads <project>/growth-pulse/config.json (sources, events, overrides). Per source:
  "csv": [...]          export files, relative to <project>/growth-pulse/ (social: NETWORK=FILE)
  ids                   website_id (umami), site_id (plausible), property_id and events (ga4),
                        site_url (gsc), currency (revenue)
  "enabled": false      skip it (it then shows as 'not run this week')
API keys come from the environment only (see each connector's --help). A source with
neither a key nor a CSV writes a 'missing' health file and the run goes on.

Source social: "zernio": {"enabled": true, "profile_id": null, "platforms": []} reads the
Zernio API when ZERNIO_API_KEY is set (connect_zernio.py). The CSV exports are the fallback
(connect_social.py): used when Zernio is not enabled, when the key is not set, or when the
API call ends without data; the reason goes in the notes of data/social.json.

Also picks up, when present: <project>/growth-pulse/actions.csv (the founder's action
log), <project>/seo-audit/config.json (shared decline override) and the latest
<project>/growth-pulse/experiments-<YYYYMMDD>.json older than the run (last run's
experiments, to judge them), unless --previous names another file.

Writes <project>/growth-pulse/<YYYYMMDD>/data/<source>.json, pulse.json and
pulse-tables.md, and prints the run folder.

Exit codes: 0 pulse written, 1 pulse written but no source had data, 2 usage error,
unreadable config or a connector usage error.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import gp_lib as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FLAGS = {
    "umami": [("website_id", "--website-id")],
    "plausible": [("site_id", "--site-id")],
    "ga4": [("property_id", "--property-id")],
    "gsc": [("site_url", "--site-url")],
    "social": [],
    "revenue": [("currency", "--currency")],
}


def connector_args(name: str, conf: Dict[str, Any], base: str) -> List[str]:
    args: List[str] = []
    for key, flag in FLAGS[name]:
        if conf.get(key):
            args += [flag, str(conf[key])]
    if name == "ga4" and conf.get("events"):
        args += ["--events", ",".join(conf["events"])]
    files = conf.get("csv") or []
    if isinstance(files, str):
        files = [files]
    paths = []
    for f in files:
        if name == "social" and "=" in f:
            net, p = f.split("=", 1)
            paths.append(f"{net}={os.path.join(base, p)}")
        else:
            paths.append(os.path.join(base, f))
    if paths:
        args += ["--csv", *paths]
    return args


def run_connector(script: str, args: List[str], out: str) -> int:
    """One connector: prints its last line, reports a usage error, returns its exit code."""
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args, "--out", out], capture_output=True, text=True)
    line = (r.stdout.strip() or r.stderr.strip()).splitlines()
    print(line[-1] if line else f"{script}: exit {r.returncode}")
    if r.returncode == 2:
        print(f"error: {script} usage error: {r.stderr.strip()}", file=sys.stderr)
    return r.returncode


def run_social(conf: Dict[str, Any], common: List[str], base: str, out: str) -> int:
    """Zernio when it is enabled and its key is set, the CSV exports as the fallback."""
    zernio = conf.get("zernio") or {}
    csv_args = connector_args("social", conf, base)
    if zernio.get("enabled") is not True:
        return run_connector("connect_social.py", common + csv_args, out)
    if os.environ.get("ZERNIO_API_KEY") or not csv_args:
        args = list(common)
        if zernio.get("profile_id"):
            args += ["--profile-id", str(zernio["profile_id"])]
        if zernio.get("platforms"):
            args += ["--platforms", ",".join(zernio["platforms"])]
        code = run_connector("connect_zernio.py", args, out)
        if code != 1 or not csv_args:
            return code
        reason = G.read_json(out).get("message", "no data")
    else:
        reason = "ZERNIO_API_KEY is not set"
    code = run_connector("connect_social.py", common + csv_args, out)
    if code != 2:
        data = G.read_json(out)
        data["notes"].append(f"Zernio not used ({reason}): CSV exports read instead")
        G.write_json(out, data)
    return code


def latest_previous(base: str, stamp: str) -> Optional[str]:
    best = None
    for p in glob.glob(os.path.join(base, "experiments-*.json")):
        m = re.search(r"experiments-(\d{8})\.json$", p)
        if m and m.group(1) < stamp and (best is None or m.group(1) > best[0]):
            best = (m.group(1), p)
    return best[1] if best else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the growth-pulse connectors declared in the project config, then compute pulse.json.")
    ap.add_argument("--project-dir", required=True, help="<your-projects-root>/<project>")
    ap.add_argument("--today", help="run date YYYY-MM-DD (default today)")
    ap.add_argument("--week", help="report week (default: the last complete ISO week)")
    ap.add_argument("--previous", help="last run's experiments file (default: the latest experiments-<YYYYMMDD>.json before today)")
    args = ap.parse_args(argv)
    base = os.path.join(args.project_dir, "growth-pulse")
    cfg_path = os.path.join(base, "config.json")
    try:
        config = G.read_json(cfg_path)
        today = G.parse_day(args.today)
    except G.InputError as e:
        print(f"error: {e} (copy agents/growth-pulse/config.example.json there first)", file=sys.stderr)
        return 2
    stamp = today.strftime("%Y%m%d")
    run = os.path.join(base, stamp)
    data = os.path.join(run, "data")
    os.makedirs(data, exist_ok=True)
    common = ["--today", today.isoformat()] + (["--week", args.week] if args.week else [])
    weeks = ((config.get("pulse_rules") or {}).get("weeks") or {}).get("window_weeks")
    if weeks:
        common += ["--weeks", str(weeks)]
    written = []
    for name, conf in (config.get("sources") or {}).items():
        if name.startswith("_") or name not in FLAGS or (conf or {}).get("enabled") is False:
            continue
        out = os.path.join(data, f"{name}.json")
        if name == "social":
            code = run_social(conf or {}, common, base, out)
        else:
            code = run_connector(f"connect_{name}.py", common + connector_args(name, conf or {}, base), out)
        if code == 2:
            return 2
        written.append(out)
    cmd = [sys.executable, os.path.join(HERE, "compute_pulse.py"), "--sources", *written, "--config", cfg_path,
           "--today", today.isoformat(), "--out-dir", run] + (["--week", args.week] if args.week else [])
    seo = os.path.join(args.project_dir, "seo-audit", "config.json")
    if os.path.exists(seo):
        cmd += ["--seo-config", seo]
    actions = os.path.join(base, "actions.csv")
    if os.path.exists(actions):
        cmd += ["--actions", actions]
    prev = args.previous or latest_previous(base, stamp)
    if prev:
        cmd += ["--previous-experiments", prev]
        print(f"previous experiments: {os.path.basename(prev)}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode in (0, 1):
        print(f"run folder: {run}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
