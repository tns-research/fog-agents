#!/usr/bin/env python3
"""
seo_state.py

Memory of seo-audit between runs: the runs and what changed between them,
the refresh briefs, what shipped and when, the served-HTML verification, and
the Search Console follow-up of every modified page at 14, 28 and 56 days.
One JSON file per project, standard library only.

    <your-projects-root>/<project>/seo-audit/state.json

Commands:
  init        --state S --project P --domain URL
  record-run  --state S --run-dir DIR [--date D]
              Registers a run (its crawl.jsonl, crawl-summary.json, bands.json)
              and writes DIR/since-last-run.json and .md: pages added or gone,
              title, description, canonical, status, indexability, H1 and
              JSON-LD changes per URL, issues new and resolved, pages entering
              or leaving a band, E-E-A-T signals gained and lost per page and
              for the site (when both runs hold an eeat.json), briefs shipped
              since the previous run.
  open-brief  --state S --id ID --url URL --action A --brief PATH [--expect PATH] [--lane L] [--date D]
  ship        --state S --id ID --date D [--note TEXT]
              The change is live at the same URL: schedules the checkpoints.
  verified    --state S --id ID --report verify.json
              Records the verify_served.py result (a brief is verified only
              when every check passed).
  drop        --state S --id ID --reason TEXT
  due         --state S [--today D] [--json]
              Next actions: briefs to write, shipped changes to verify,
              checkpoints due with their exact date windows and the command
              or export that gives the data.
  track       --state S --gsc FILE [--today D]
              FILE = daily rows with date and page (API JSON with dimensions
              date,page, or a CSV with Date and Page columns). Records every
              due checkpoint the file covers.
  track       --state S --id ID --checkpoint N --before FILE --after FILE [--today D]
              Same from two page exports of the Search Console UI (the N days
              before and the N days after the ship date).
  summary     --state S [--json]
              Briefs per status, outcomes per action and checkpoint (counts,
              never a winner: an outcome is a correlation).
  show        --state S [--id ID]

Thresholds and checkpoints: the tracking object of assets/gsc-bands.json.

Exit codes: 0 done, 1 refused (unknown id, wrong status, file does not cover
the window), 2 usage error or unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, deep_merge, load_assets_json, load_gsc, load_json, normalize_url,  # noqa: E402
                     parse_day, read_jsonl, write_json, write_text)

ACTIONS = ["update", "refine", "expand", "retarget", "merge"]
DIFF_FIELDS = ["status", "title", "meta_description", "canonical", "og_url", "indexable", "h1", "jsonld_types", "meta_robots"]


class Refused(Exception):
    pass


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise InputError(f"no state at {path}: run `seo_state.py init` first")
    return load_json(path)


def save_state(path: str, st: Dict[str, Any]) -> None:
    write_json(path, st)


def tracking_cfg(config: Optional[str]) -> Dict[str, Any]:
    t = load_assets_json("gsc-bands.json")
    if config:
        t = deep_merge(t, load_json(config).get("gsc_bands", {}))
    return t["tracking"]


def rel(state_path: str, p: str) -> str:
    base = os.path.dirname(os.path.abspath(state_path))
    try:
        return os.path.relpath(os.path.abspath(p), base).replace(os.sep, "/")
    except ValueError:
        return os.path.abspath(p)


def absol(state_path: str, p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(os.path.dirname(os.path.abspath(state_path)), p)


def log(st: Dict[str, Any], day: str, event: str, ref: Optional[str] = None) -> None:
    st.setdefault("log", []).append({"date": day, "event": event, "id": ref})


# --------------------------------------------------------------------------
# runs and diff

def load_crawl(run_dir: str) -> Dict[str, Dict[str, Any]]:
    p = os.path.join(run_dir, "crawl.jsonl")
    if not os.path.exists(p):
        return {}
    return {rec["url"]: dict(rec, _line=n) for n, rec in read_jsonl(p)}


def load_bands(run_dir: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(run_dir, "bands.json")
    return load_json(p) if os.path.exists(p) else None


def load_eeat(run_dir: str) -> Optional[Dict[str, Any]]:
    p = os.path.join(run_dir, "eeat.json")
    return load_json(p) if os.path.exists(p) else None


def eeat_diff(ea: Optional[Dict[str, Any]], eb: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Signals gained and lost per page and for the site between two eeat.json files.
    A signal is met when its normalized value (score) is above 0."""
    if not ea or not eb:
        return None

    def flips(sa: Dict[str, Any], sb: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        met = lambda s: (s or {}).get("score", 0) > 0  # noqa: E731
        names = [k for k in sb if k in sa]
        return sorted(k for k in names if met(sb[k]) and not met(sa[k])), sorted(k for k in names if met(sa[k]) and not met(sb[k]))

    pa = {p["url"]: p for p in ea.get("pages", [])}
    pages = []
    for pb in eb.get("pages", []):
        a = pa.get(pb["url"])
        if not a:
            continue
        gained, lost = flips(a["signals"], pb["signals"])
        if gained or lost or a.get("score") != pb.get("score"):
            pages.append({"url": pb["url"], "ref": pb["ref"], "score_before": a.get("score"), "score_after": pb.get("score"),
                          "gained": gained, "lost": lost})
    sg, sl = flips(ea.get("site_signals", {}), eb.get("site_signals", {}))
    return {"site_score_before": ea.get("site_score"), "site_score_after": eb.get("site_score"),
            "weights_version_changed": ea.get("weights_version") != eb.get("weights_version"),
            "site_gained": sg, "site_lost": sl, "pages": pages}


def diff_runs(prev_dir: str, cur_dir: str) -> Dict[str, Any]:
    a, b = load_crawl(prev_dir), load_crawl(cur_dir)
    ok_a = {u for u, r in a.items() if r.get("status") == 200 and not r.get("redirect_chain")}
    ok_b = {u for u, r in b.items() if r.get("status") == 200 and not r.get("redirect_chain")}
    changes = []
    for u in sorted(set(a) & set(b)):
        ra, rb = bool(a[u].get("redirect_chain")), bool(b[u].get("redirect_chain"))
        if ra or rb:
            # a redirect line has no content of its own: compare where it lands
            va = a[u].get("final_url") if ra else None
            vb = b[u].get("final_url") if rb else None
            if va != vb:
                changes.append({"url": u, "field": "redirects_to", "before": va, "after": vb, "line": b[u]["_line"]})
            continue
        for f in DIFF_FIELDS:
            va, vb = a[u].get(f), b[u].get(f)
            if f == "h1":
                va, vb = (va or [None])[0], (vb or [None])[0]
            if va != vb:
                changes.append({"url": u, "field": f, "before": va, "after": vb, "line": b[u]["_line"]})
    iss_a = {(c, u) for u, r in a.items() for c in r.get("issues", [])}
    iss_b = {(c, u) for u, r in b.items() for c in r.get("issues", [])}

    def group(pairs):
        g: Dict[str, List[str]] = {}
        for c, u in sorted(pairs):
            g.setdefault(c, []).append(u)
        return [{"code": c, "count": len(v), "urls": v[:20]} for c, v in sorted(g.items(), key=lambda x: (-len(x[1]), x[0]))]

    bands = None
    ba, bb = load_bands(prev_dir), load_bands(cur_dir)
    if ba and bb:
        bands = {}
        for level, key in (("pages", "page"), ("queries", "query")):
            pa = {(r[key], b) for r in ba.get(level, []) for b in r.get("bands", [])}
            pb = {(r[key], b) for r in bb.get(level, []) for b in r.get("bands", [])}
            bands[level] = {"entered": [{"key": k, "band": bd} for k, bd in sorted(pb - pa)],
                            "left": [{"key": k, "band": bd} for k, bd in sorted(pa - pb)]}
    return {
        "previous_run": prev_dir, "current_run": cur_dir,
        "pages_added": sorted(ok_b - ok_a), "pages_gone": sorted(ok_a - ok_b),
        "changes": changes,
        "issues_new": group(iss_b - iss_a), "issues_resolved": group(iss_a - iss_b),
        "bands": bands,
        "eeat": eeat_diff(load_eeat(prev_dir), load_eeat(cur_dir)),
    }


def render_diff(d: Dict[str, Any], briefs: List[Dict[str, Any]], first: bool) -> str:
    L = ["# Since the last audit", ""]
    if first:
        L += ["First recorded run: this crawl is the baseline. The next run starts here.", ""]
        return "\n".join(L)
    L.append(f"Previous run: `{d['previous_run']}`. Current run: `{d['current_run']}`.")
    L.append("")
    L.append(f"- Pages added (200): {len(d['pages_added'])}; pages gone: {len(d['pages_gone'])}.")
    L.append(f"- Field changes: {len(d['changes'])}; issues new: {sum(i['count'] for i in d['issues_new'])}; "
             f"issues resolved: {sum(i['count'] for i in d['issues_resolved'])}.")
    L.append("")
    if briefs:
        L += ["## Shipped since the previous run", "", "| Brief | URL | Action | Shipped | Verify | Checkpoints |", "|---|---|---|---|---|---|"]
        for b in briefs:
            v = b.get("verify") or []
            cps = ", ".join(f"{k}d {c.get('outcome', c['status'])}" for k, c in sorted(b.get("checkpoints", {}).items(), key=lambda x: int(x[0])))
            L.append(f"| {b['id']} | {b['url']} | {b['action']} | {b.get('shipped_on')} | {v[-1]['status'] if v else 'not run'} | {cps} |")
        L.append("")
    if d["changes"]:
        L += ["## Changes per URL (crawl.jsonl line of this run)", "", "| URL | Field | Before | After | Line |", "|---|---|---|---|---|"]
        for c in d["changes"][:60]:
            L.append(f"| {c['url']} | {c['field']} | `{json.dumps(c['before'], ensure_ascii=False)}` | `{json.dumps(c['after'], ensure_ascii=False)}` | crawl.jsonl:{c['line']} |")
        L.append("")
    for title, key in (("New issues", "issues_new"), ("Resolved issues", "issues_resolved")):
        if d[key]:
            L += [f"## {title}", ""]
            for i in d[key]:
                L.append(f"- `{i['code']}` x{i['count']}: {', '.join(i['urls'][:5])}")
            L.append("")
    if d.get("bands"):
        L += ["## Search Console bands", ""]
        for level in ("pages", "queries"):
            e, l = d["bands"][level]["entered"], d["bands"][level]["left"]
            e_txt = ", ".join("{} {}".format(x["key"], x["band"]) for x in e[:5])
            l_txt = ", ".join("{} {}".format(x["key"], x["band"]) for x in l[:5])
            L.append(f"- {level}: {len(e)} entered a band ({e_txt}), {len(l)} left one ({l_txt}).")
        L.append("")
    e = d.get("eeat")
    if e:
        L += ["## E-E-A-T signals (eeat.json)", "",
              f"- Site score: {e['site_score_before']} -> {e['site_score_after']}"
              + (" (weights version changed: scores are not comparable)" if e["weights_version_changed"] else "") + ".",
              f"- Site signals gained: {', '.join(e['site_gained']) or 'none'}; lost: {', '.join(e['site_lost']) or 'none'}.", ""]
        if e["pages"]:
            L += ["| URL | Score | Gained | Lost | Line |", "|---|---|---|---|---|"]
            for p in e["pages"]:
                L.append(f"| {p['url']} | {p['score_before']} -> {p['score_after']} | {', '.join(p['gained']) or 'none'} | "
                         f"{', '.join(p['lost']) or 'none'} | {p['ref']} |")
            L.append("")
    return "\n".join(L)


def cmd_record_run(a, st) -> int:
    run_dir = a.run_dir
    if not os.path.exists(os.path.join(run_dir, "crawl.jsonl")):
        raise InputError(f"{run_dir}/crawl.jsonl missing: run crawl.py first")
    day = parse_day(a.date).isoformat()
    summary = os.path.join(run_dir, "crawl-summary.json")
    summ = load_json(summary) if os.path.exists(summary) else {}
    bands = load_bands(run_dir)
    eeat = load_eeat(run_dir)
    entry = {"date": day, "dir": rel(a.state, run_dir), "crawl_lines": summ.get("lines"), "pages_200": summ.get("pages_200"),
             "issue_counts": summ.get("issue_counts"), "bands_counts": (bands or {}).get("counts"),
             "eeat_site_score": (eeat or {}).get("site_score")}
    runs = [r for r in st.setdefault("runs", []) if r["dir"] != entry["dir"]]
    prev = sorted([r for r in runs if r["date"] <= day], key=lambda r: r["date"])
    first = not prev
    if first:
        d = {"previous_run": None, "current_run": entry["dir"], "pages_added": [], "pages_gone": [], "changes": [],
             "issues_new": [], "issues_resolved": [], "bands": None, "eeat": None}
        shipped = []
    else:
        p = prev[-1]
        d = diff_runs(absol(a.state, p["dir"]), run_dir)
        d["previous_run"], d["current_run"] = p["dir"], entry["dir"]
        shipped = [b for b in st.get("briefs", {}).values() if b.get("shipped_on") and p["date"] <= b["shipped_on"] <= day]
    d["first_run"] = first
    d["shipped_since"] = [b["id"] for b in shipped]
    write_json(os.path.join(run_dir, "since-last-run.json"), d)
    write_text(os.path.join(run_dir, "since-last-run.md"), render_diff(d, shipped, first))
    runs.append(entry)
    st["runs"] = sorted(runs, key=lambda r: r["date"])
    log(st, day, "run", entry["dir"])
    print(f"run {entry['dir']} recorded ({'baseline' if first else 'diff vs ' + d['previous_run']}): "
          f"{len(d['changes'])} field changes, {sum(i['count'] for i in d['issues_new'])} new issues, "
          f"{sum(i['count'] for i in d['issues_resolved'])} resolved")
    return 0


# --------------------------------------------------------------------------
# briefs

def get_brief(st: Dict[str, Any], bid: str) -> Dict[str, Any]:
    b = st.get("briefs", {}).get(bid)
    if not b:
        raise Refused(f"unknown brief id {bid}")
    return b


def cmd_open_brief(a, st) -> int:
    action = a.action.lower()
    if action not in ACTIONS:
        raise InputError(f"--action must be one of {', '.join(ACTIONS)}")
    day = parse_day(a.date).isoformat()
    url = normalize_url(a.url)
    for b in st.get("briefs", {}).values():
        if b["url"] == url and b["status"] in ("open", "shipped") and b["id"] != a.id:
            raise Refused(f"{url} already has an open brief ({b['id']}): finish or drop it first")
    existing = st.setdefault("briefs", {}).get(a.id)
    if existing and existing["status"] not in ("open",):
        raise Refused(f"brief {a.id} is already {existing['status']}")
    st["briefs"][a.id] = {"id": a.id, "url": url, "action": action, "lane": a.lane, "status": "open", "opened": day,
                          "brief": rel(a.state, a.brief), "expect": rel(a.state, a.expect) if a.expect else None,
                          "shipped_on": None, "verify": [], "checkpoints": {}}
    log(st, day, "open-brief", a.id)
    print(f"brief {a.id} open: {action} {url}")
    return 0


def cmd_ship(a, st) -> int:
    b = get_brief(st, a.id)
    if b["status"] not in ("open",):
        raise Refused(f"brief {a.id} is {b['status']}, only an open brief can ship")
    T = tracking_cfg(a.config)
    ship = parse_day(a.date)
    b["status"] = "shipped"
    b["shipped_on"] = ship.isoformat()
    b["note"] = a.note
    b["checkpoints"] = {}
    for n in T["checkpoints_days"]:
        b["checkpoints"][str(n)] = {
            "status": "scheduled",
            "before": [(ship - timedelta(days=n)).isoformat(), (ship - timedelta(days=1)).isoformat()],
            "after": [(ship + timedelta(days=1)).isoformat(), (ship + timedelta(days=n)).isoformat()],
            "due": (ship + timedelta(days=n + T["lag_days"])).isoformat(),
        }
    log(st, ship.isoformat(), "ship", a.id)
    print(f"brief {a.id} shipped on {b['shipped_on']}: verify the served page now, checkpoints due "
          + ", ".join(f"{k}d on {c['due']}" for k, c in b["checkpoints"].items()))
    return 0


def cmd_verified(a, st) -> int:
    b = get_brief(st, a.id)
    if b["status"] not in ("shipped", "verified", "tracking"):
        raise Refused(f"brief {a.id} is {b['status']}: ship it before recording a verification")
    rep = load_json(a.report)
    results = rep.get("pages", [rep])
    mine = [r for r in results if normalize_url(r.get("url", "")) == b["url"]] or results
    passed = all(r.get("passed") for r in mine)
    day = rep.get("checked_on") or date.today().isoformat()
    b["verify"].append({"date": day, "status": "pass" if passed else "fail", "report": rel(a.state, a.report),
                        "failed": [c["check"] for r in mine for c in r.get("checks", []) if c.get("status") == "fail"]})
    if passed and b["status"] == "shipped":
        b["status"] = "verified"
    log(st, day, "verify-" + ("pass" if passed else "fail"), a.id)
    print(f"brief {a.id}: verify {'pass' if passed else 'FAIL'}" + ("" if passed else f" ({', '.join(b['verify'][-1]['failed'])})"))
    return 0 if passed else 1


def cmd_drop(a, st) -> int:
    b = get_brief(st, a.id)
    b["status"] = "dropped"
    b["dropped_reason"] = a.reason
    log(st, date.today().isoformat(), "drop", a.id)
    print(f"brief {a.id} dropped")
    return 0


# --------------------------------------------------------------------------
# due and tracking

def due_items(st: Dict[str, Any], today: date) -> List[Dict[str, Any]]:
    items = []
    for b in sorted(st.get("briefs", {}).values(), key=lambda x: x["id"]):
        if b["status"] == "open":
            items.append({"id": b["id"], "kind": "write", "url": b["url"], "action": b["action"],
                          "what": f"write the {b['action']} change at the existing URL (brief {b['brief']}), then `ship`"})
        if b["status"] == "shipped" and not any(v["status"] == "pass" for v in b["verify"]):
            items.append({"id": b["id"], "kind": "verify", "url": b["url"],
                          "what": f"python3 scripts/verify_served.py --expect {b.get('expect') or '<expect.json>'} --out <verify.json>, then `verified`"})
        for n, c in sorted(b.get("checkpoints", {}).items(), key=lambda x: int(x[0])):
            if c["status"] == "scheduled" and parse_day(c["due"]) <= today:
                items.append({"id": b["id"], "kind": "checkpoint", "checkpoint": int(n), "url": b["url"],
                              "before": c["before"], "after": c["after"],
                              "what": (f"gsc analytics query --site <domain> --start {c['before'][0]} --end {c['after'][1]} "
                                       f"--dimensions date,page --limit 25000 --json > <project>/seo-audit/data/gsc-date-page-{today.isoformat()}.json, "
                                       f"then `track --gsc` (UI: export Pages for {c['before'][0]}..{c['before'][1]} and {c['after'][0]}..{c['after'][1]}, "
                                       f"then `track --id {b['id']} --checkpoint {n} --before ... --after ...`)")})
    return items


def window_metrics(rows: List[Dict[str, Any]], url: str, start: str, end: str) -> Dict[str, Any]:
    clicks = imp = 0
    pos_w = w = 0.0
    for r in rows:
        if normalize_url(r.get("page", "")) != url:
            continue
        d = r.get("date", "")[:10]
        if start <= d <= end:
            m = r["cur"]
            clicks += m["clicks"]
            imp += m["impressions"]
            if m.get("position") is not None:
                pos_w += m["position"] * (m["impressions"] or 1)
                w += m["impressions"] or 1
    return {"clicks": clicks, "impressions": imp, "ctr": round(clicks / imp, 4) if imp else 0.0,
            "position": round(pos_w / w, 2) if w else None}


def outcome(before: Dict[str, Any], after: Dict[str, Any], T: Dict[str, Any]) -> Tuple[str, Optional[float]]:
    diff = after["clicks"] - before["clicks"]
    p = round(diff * 100.0 / before["clicks"], 1) if before["clicks"] else None
    big = abs(diff) >= T["outcome_min_abs_clicks"]
    if big and (p is None or p >= T["outcome_min_change_pct"]) and diff > 0:
        return "up", p
    if big and p is not None and p <= -T["outcome_min_change_pct"]:
        return "down", p
    return "flat", p


def record_checkpoint(b: Dict[str, Any], n: str, before: Dict[str, Any], after: Dict[str, Any], T: Dict[str, Any],
                      source: str, today: str) -> None:
    c = b["checkpoints"][n]
    oc, p = outcome(before, after, T)
    c.update(status="recorded", recorded_on=today, source=source, before_metrics=before, after_metrics=after,
             clicks_change_pct=p,
             position_change=(round(after["position"] - before["position"], 2)
                              if after["position"] is not None and before["position"] is not None else None),
             outcome=oc, tag=f"refresh:{b['action']}")
    if all(x["status"] == "recorded" for x in b["checkpoints"].values()):
        b["status"] = "closed"
    elif b["status"] in ("verified", "shipped"):
        b["status"] = "tracking" if b["status"] == "verified" else b["status"]


def cmd_track(a, st) -> int:
    T = tracking_cfg(a.config)
    today = parse_day(a.today)
    recorded, skipped = 0, []
    if a.before or a.after:
        if not (a.before and a.after and a.id and a.checkpoint):
            raise InputError("--before and --after need --id and --checkpoint")
        b = get_brief(st, a.id)
        n = str(a.checkpoint)
        if n not in b.get("checkpoints", {}):
            raise Refused(f"brief {a.id} has no checkpoint {n}")
        def page_total(path):
            d = load_gsc(path, ["page"])
            rows = [r for r in d["rows"] if normalize_url(r.get("page", "")) == b["url"]] if d["rows"] and "page" in d["rows"][0] else d["rows"]
            clicks = sum(r["cur"]["clicks"] for r in rows)
            imp = sum(r["cur"]["impressions"] for r in rows)
            pos = [r["cur"]["position"] for r in rows if r["cur"]["position"] is not None]
            return {"clicks": clicks, "impressions": imp, "ctr": round(clicks / imp, 4) if imp else 0.0,
                    "position": round(sum(pos) / len(pos), 2) if pos else None}
        record_checkpoint(b, n, page_total(a.before), page_total(a.after), T, "ui-exports", today.isoformat())
        recorded = 1
    else:
        if not a.gsc:
            raise InputError("track needs --gsc FILE (date x page rows) or --before/--after exports")
        data = load_gsc(a.gsc, ["date", "page"])
        rows = [r for r in data["rows"] if "date" in r and "page" in r]
        if not rows:
            raise InputError(f"{a.gsc} has no date x page rows (export with --dimensions date,page)")
        dates = sorted(r["date"][:10] for r in rows)
        lo, hi = dates[0], dates[-1]
        for item in due_items(st, today):
            if item["kind"] != "checkpoint" or (a.id and item["id"] != a.id):
                continue
            if item["before"][0] < lo or item["after"][1] > hi:
                skipped.append(f"{item['id']} {item['checkpoint']}d: file covers {lo}..{hi}, needs {item['before'][0]}..{item['after'][1]}")
                continue
            b = st["briefs"][item["id"]]
            before = window_metrics(rows, b["url"], *item["before"])
            after = window_metrics(rows, b["url"], *item["after"])
            record_checkpoint(b, str(item["checkpoint"]), before, after, T, os.path.basename(a.gsc), today.isoformat())
            recorded += 1
    for s in skipped:
        print(f"not covered: {s}")
    for b in sorted(st.get("briefs", {}).values(), key=lambda x: x["id"]):
        for n, c in sorted(b.get("checkpoints", {}).items(), key=lambda x: int(x[0])):
            if c.get("recorded_on") == today.isoformat():
                print(f"{b['id']} {n}d: clicks {c['before_metrics']['clicks']} -> {c['after_metrics']['clicks']} "
                      f"({c['clicks_change_pct']} %), position {c['before_metrics']['position']} -> {c['after_metrics']['position']}: "
                      f"{c['outcome']} [{c['tag']}]")
    log(st, today.isoformat(), f"track {recorded}")
    print(f"track: {recorded} checkpoint(s) recorded")
    return 1 if skipped and not recorded else 0


def cmd_due(a, st) -> int:
    items = due_items(st, parse_day(a.today))
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for i in items:
            label = f"{i['kind']} {i.get('checkpoint', '')}".strip()
            print(f"- [{label}] {i['id']} {i['url']}: {i['what']}")
        print(f"due: {len(items)} action(s)")
    return 0


def summarize(st: Dict[str, Any]) -> Dict[str, Any]:
    status: Dict[str, int] = {}
    outcomes: Dict[str, Dict[str, Dict[str, int]]] = {}
    for b in st.get("briefs", {}).values():
        status[b["status"]] = status.get(b["status"], 0) + 1
        for n, c in b.get("checkpoints", {}).items():
            if c["status"] != "recorded":
                continue
            o = outcomes.setdefault(f"refresh:{b['action']}", {}).setdefault(f"{n}d", {"up": 0, "flat": 0, "down": 0})
            o[c["outcome"]] += 1
    return {"briefs_by_status": status, "outcomes": outcomes, "runs": len(st.get("runs", [])),
            "note": "Outcome counts are correlations on small samples; read them with the sample size, never as proof."}


def cmd_summary(a, st) -> int:
    s = summarize(st)
    if a.json:
        print(json.dumps(s, indent=2))
        return 0
    print(f"runs: {s['runs']}; briefs: " + ", ".join(f"{k} {v}" for k, v in sorted(s["briefs_by_status"].items())))
    for tag, per in sorted(s["outcomes"].items()):
        print(f"{tag}: " + "; ".join(f"{n} up {o['up']} flat {o['flat']} down {o['down']}" for n, o in sorted(per.items(), key=lambda x: int(x[0][:-1]))))
    print(s["note"])
    return 0


def cmd_show(a, st) -> int:
    if a.id:
        print(json.dumps(get_brief(st, a.id), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="seo-audit state between runs: runs, briefs, shipping, verification, tracking.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, **kw):
        p = sub.add_parser(name, **kw)
        p.add_argument("--state", required=True)
        p.add_argument("--config", help="project config.json (gsc_bands.tracking overrides)")
        return p

    p = add("init")
    p.add_argument("--project", required=True)
    p.add_argument("--domain", required=True)
    p = add("record-run")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--date")
    p = add("open-brief")
    p.add_argument("--id", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--brief", required=True)
    p.add_argument("--expect")
    p.add_argument("--lane")
    p.add_argument("--date")
    p = add("ship")
    p.add_argument("--id", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--note")
    p = add("verified")
    p.add_argument("--id", required=True)
    p.add_argument("--report", required=True)
    p = add("drop")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p = add("due")
    p.add_argument("--today")
    p.add_argument("--json", action="store_true")
    p = add("track")
    p.add_argument("--gsc")
    p.add_argument("--id")
    p.add_argument("--checkpoint", type=int)
    p.add_argument("--before")
    p.add_argument("--after")
    p.add_argument("--today")
    p = add("summary")
    p.add_argument("--json", action="store_true")
    p = add("show")
    p.add_argument("--id")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "init":
            if os.path.exists(a.state):
                print(f"state already exists at {a.state}, left as is")
                return 0
            st = {"schema_version": "1.0", "project": a.project, "domain": normalize_url(a.domain),
                  "created": date.today().isoformat(), "runs": [], "briefs": {}, "log": []}
            save_state(a.state, st)
            print(f"state created at {a.state}")
            return 0
        st = load_state(a.state)
        handlers = {"record-run": cmd_record_run, "open-brief": cmd_open_brief, "ship": cmd_ship, "verified": cmd_verified,
                    "drop": cmd_drop, "due": cmd_due, "track": cmd_track, "summary": cmd_summary, "show": cmd_show}
        rc = handlers[a.cmd](a, st)
        if a.cmd not in ("due", "summary", "show"):
            save_state(a.state, st)
        return rc
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
