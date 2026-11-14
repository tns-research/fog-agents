#!/usr/bin/env python3
"""build_handoff.py: turn a run into the sidecar v2 and the report, or refuse.

  python3 scripts/build_handoff.py --run PROJECT/market-signal/runs/20261012 \
      [--out-dir PROJECT/market-signal] [--min-authors 5 --min-communities 2] [--speakers user,practitioner] [--no-report]

Reads from the run folder: corpus.jsonl, labels.jsonl, analysis.json (the
model's spec), health.json, and changes.json when diff_runs.py wrote one.
Then, in order:
  1. validates analysis.json, labels.jsonl and every corpus record against
     their schemas (assets/*.schema.json);
  2. computes stats.json (compute_signals.py rules);
  3. verifies every quote against the corpus (verify_quotes.py rules) and
     writes quotes-check.json; any BLOCK stops here, nothing is delivered;
  4. checks the spec: references, verbatim hooks and objections, no bare
     number in the analyst's prose (summary included);
  5. assembles market-signal-<YYYYMMDD>.json with the exact quote texts from
     the corpus and every count from stats.json, validates it
     (validate_sidecar.py), and writes market-signal-<YYYYMMDD>.md, whose
     numbers all come from stats.json.

--out-dir defaults to the run's grandparent (<project>/market-signal/ when the
run sits in <project>/market-signal/runs/<date>/).

Exit 0 delivered, 1 refused (each reason printed; fix analysis.json or
labels.jsonl and run again), 2 unreadable input or an unknown --speakers value.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M
import compute_signals as C
import verify_quotes as V
import validate_sidecar as VS

USAGE = ("Quotes are public strangers' words about a problem: reuse them as language (pain phrasing, objections, "
         "headline raw material), verbatim and in their original language, with the permalink kept in the consumer's "
         "report. Never present one as a testimonial of the founder's product, never imply its author is a customer, "
         "never attach it to a company or a face. author_hash is a pseudonym: never resolve it. Hooks with verbatim "
         "false are analyst lines and go through the consumer's claims gate like its own copy.")


def spec_errors(an: Dict[str, Any], quotes_ok: Dict[str, Dict[str, Any]]) -> List[str]:
    errs = []
    pains = {p["pain_id"] for p in an["pains"]}
    qids = {q["quote_id"] for q in an["quotes"]}
    personas = {p["persona_id"] for p in an.get("personas", [])}
    hooks = {h["hook_id"] for h in an.get("hooks", [])}
    for n in VS.prose_numbers(an["summary"]):
        errs.append(f"prose: summary holds the number '{n}' (the report prints the computed counts)")
    for lim in an.get("limitations", []):
        for n in VS.prose_numbers(lim):
            errs.append(f"prose: limitation '{lim[:40]}...' holds the number '{n}'")
    for q in an["quotes"]:
        if q.get("pain_id") and q["pain_id"] not in pains:
            errs.append(f"spec: quote {q['quote_id']} names {q['pain_id']}, not in pains")
        if q.get("persona_id") and q["persona_id"] not in personas:
            errs.append(f"spec: quote {q['quote_id']} names {q['persona_id']}, not in personas")
    refs = []
    for h in an.get("hooks", []):
        refs += [(f"hook {h['hook_id']}", i) for i in h["quote_ids"]]
    for o in an.get("objections", []):
        refs += [(f"objection {o['objection_id']}", i) for i in o["quote_ids"]]
    for a in an.get("angles", []):
        refs += [(f"angle {a['angle_id']}", i) for i in [a["headline_quote_id"]] + a.get("support_quote_ids", [])]
        if a["pain_id"] not in pains:
            errs.append(f"spec: angle {a['angle_id']} names {a['pain_id']}, not in pains")
    for s in an.get("existing_solutions", []):
        refs += [(f"existing solution {s['name']}", i) for i in s["quote_ids"]]
    for pe in an.get("personas", []):
        for ids in (pe.get("jtbd_forces") or {}).values():
            refs += [(f"persona {pe['persona_id']}", i) for i in ids]
        for ap in pe.get("anti_personas", []):
            refs += [(f"persona {pe['persona_id']} anti-persona", i) for i in ap["quote_ids"]]
        for hid in pe.get("hook_ids", []):
            if hid not in hooks:
                errs.append(f"spec: persona {pe['persona_id']} names hook {hid}, not in hooks")
    for r in an.get("recommendations", []):
        refs += [("recommendation", i) for i in r.get("quote_ids", [])]
    for where, i in refs:
        if i not in qids:
            errs.append(f"spec: {where} cites {i}, not in quotes")
    return errs


def build(run: Path, out_dir: Path, args) -> int:
    try:
        corpus = M.read_jsonl(run / "corpus.jsonl")
        labels = M.read_jsonl(run / "labels.jsonl")
        an = M.read_json(run / "analysis.json")
        health = M.read_json(run / "health.json") if (run / "health.json").exists() else {"jobs": []}
        changes = M.read_json(run / "changes.json") if (run / "changes.json").exists() else None
    except (OSError, ValueError) as e:
        M.eprint(f"build_handoff: {e}")
        return 2
    errs = [f"analysis.json: {e}" for e in M.schema_errors(an, "analysis.schema.json")]
    errs += [f"labels.jsonl line {i + 1}: {e}" for i, l in enumerate(labels) for e in M.schema_errors(l, "labels.schema.json")]
    errs += [f"corpus.jsonl line {i + 1}: {e}" for i, r in enumerate(corpus) for e in M.schema_errors(r, "record.schema.json")]
    if errs:
        for e in errs[:40]:
            print(f"REFUSED {e}")
        return 1

    since, until = an["window"]["since"], an["window"]["until"]
    stats, serr = C.compute(corpus, labels, since, until, [p["pain_id"] for p in an["pains"]],
                            args.min_authors, args.min_communities, args.counted,
                            args.phrase_records, args.phrase_authors, run)
    stats["inputs"] = {"corpus": "corpus.jsonl", "corpus_sha256": M.sha256_file(run / "corpus.jsonl"),
                       "labels_sha256": M.sha256_file(run / "labels.jsonl")}
    M.write_json(run / "stats.json", stats)
    rep = V.verify(an["quotes"], corpus, since, until)
    M.write_json(run / "quotes-check.json", rep)
    errs += [f"labels: {e}" for e in serr]
    for it in rep["items"]:
        if it["status"] == "block":
            errs.append(f"quote {it['quote_id']} ({it['record_id']}): {', '.join(it['codes'])}")
    if rep["duplicate_quote_ids"]:
        errs.append(f"duplicate quote ids: {', '.join(rep['duplicate_quote_ids'])}")
    ok = {it["quote_id"]: it for it in rep["items"] if it["status"] == "pass"}
    errs += spec_errors(an, ok)
    if errs:
        for e in errs:
            print(f"REFUSED {e}")
        print(f"build_handoff: refused, {len(errs)} problems; quotes-check.json and stats.json written in {run}")
        return 1

    lab = {l["record_id"]: l for l in labels}
    rec = {r["record_id"]: r for r in corpus}
    sp = {p["pain_id"]: p for p in stats["pains"]}
    lang = an.get("language") if an.get("language") and len(an.get("language", "")) == 2 else None
    quotes = []
    for q in an["quotes"]:
        it = ok[q["quote_id"]]
        r = rec[q["record_id"]]
        quotes.append({
            "quote_id": q["quote_id"], "record_id": q["record_id"], "text_verbatim": it["text_verbatim"],
            "char_count": it["char_count"], "language": r.get("lang") or lang, "permalink": r["url"],
            "date": r["date"], "source": r["source"], "community": r["community"], "kind": r["kind"],
            "author_hash": r.get("author_hash"), "speaker": lab.get(q["record_id"], {}).get("speaker"),
            "sentiment": lab.get(q["record_id"], {}).get("sentiment"), "pain_id": q.get("pain_id"),
            "persona_id": q.get("persona_id"), "usable_as": q.get("usable_as", []), "verified": True,
            "warnings": it["warnings"],
        })
    qmap = {q["quote_id"]: q for q in quotes}
    pains = []
    for p in an["pains"]:
        s = sp[p["pain_id"]]
        pains.append({
            "pain_id": p["pain_id"], "summary": p["summary"], "kind": p.get("kind", "pain"), "force": p["force"],
            "awareness_stage": p.get("awareness_stage", "problem_aware"), "existing_solution": p.get("existing_solution"),
            "escalated": s["escalated"], "mention_count": s["voices"], "distinct_authors": s["distinct_authors"],
            "distinct_communities": s["distinct_communities"], "communities": s["communities"],
            "by_source": s["by_source"], "source_shares": s["source_shares"], "first_seen": s["first_seen"],
            "last_seen": s["last_seen"], "by_month": s["by_month"], "trend": s["trend"], "volume": s["volume"],
            "quote_ids": [q["quote_id"] for q in quotes if q["pain_id"] == p["pain_id"]],
        })
    order = {p["pain_id"]: i for i, p in enumerate(stats["pains"])}
    pains.sort(key=lambda p: order[p["pain_id"]])
    comp = {c["name"].lower(): c for c in stats["competitors"]}
    angles = [{
        "angle_id": a["angle_id"], "pain_id": a["pain_id"], "pain_escalated": sp[a["pain_id"]]["escalated"],
        "force": a["force"], "awareness_stage": a["awareness_stage"], "funnel_stage": a["funnel_stage"],
        "headline_quote_id": a["headline_quote_id"], "headline_char_count": qmap[a["headline_quote_id"]]["char_count"],
        "support_quote_ids": a.get("support_quote_ids", []), "contrast": a.get("contrast"), "formats": a["formats"],
        "why": a.get("why", ""),
    } for a in an.get("angles", [])]
    date = an.get("as_of") or until
    sc = {
        "schema_version": "2.0", "agent": "market-signal", "project": an.get("project", ""), "date": date,
        "market": an["market"], "language": an.get("language", "en"), "geography": an.get("geography", "global"),
        "window": {"since": since, "until": until, "days": stats["window"]["days"]},
        "valid_until": (dt.date.fromisoformat(date) + dt.timedelta(days=args.valid_days)).isoformat(),
        "corpus": {"path": os.path.relpath(run / "corpus.jsonl", out_dir), "sha256": stats["inputs"]["corpus_sha256"],
                   "records": len(corpus)},
        "stats": {
            "records_collected": stats["corpus"]["records"], "records_relevant": stats["corpus"]["relevant"],
            "voices": stats["corpus"]["voices"], "quotes_verified": len(quotes),
            "by_source": stats["corpus"]["by_source"], "voices_by_source": stats["corpus"]["voices_by_source"],
            "sentiment": stats["sentiment"], "forces": stats["forces"],
            "escalation_rule": {k: stats["thresholds"][k] for k in ("min_authors", "min_communities", "counted_speakers")},
            "capped_jobs": stats["capped_jobs"],
        },
        "source_health": [{k: j.get(k) for k in ("job_id", "source", "target", "status", "records", "capped", "message")}
                          for j in health.get("jobs", [])],
        "pains": pains, "quotes": quotes,
        "hooks": [dict(h, char_count=len(h["text"])) for h in an.get("hooks", [])],
        "objections": an.get("objections", []), "angles": angles,
        "existing_solutions": [dict(s, mentions=({"records": comp[s["name"].lower()]["records"],
                                                  "distinct_authors": comp[s["name"].lower()]["distinct_authors"]}
                                                 if s["name"].lower() in comp else None))
                               for s in an.get("existing_solutions", [])],
        "personas": an.get("personas", []),
        "language_bank": [{k: x[k] for k in ("phrase", "records", "distinct_authors", "pain_id")} for x in stats["language_bank"]],
        "marketing_copy": {
            "candidate_headlines": [{"text": qmap[a["headline_quote_id"]]["text_verbatim"], "source_quote_id": a["headline_quote_id"]} for a in angles],
            "candidate_subheads": [{"text": qmap[i]["text_verbatim"], "source_quote_id": i} for a in angles for i in a["support_quote_ids"]],
            "objection_responses": [],
        },
        "weak_signals": [{"pain_id": p["pain_id"], "summary": p["summary"], "distinct_authors": p["distinct_authors"],
                          "distinct_communities": p["distinct_communities"], "quote_ids": p["quote_ids"]}
                         for p in pains if not p["escalated"]],
        "rejected_pains": an.get("rejected_pains", []),
        "recommendations": an.get("recommendations", []),
        "limitations": an.get("limitations", []),
        "changes": changes, "usage": USAGE,
    }
    verrs = VS.check(sc, corpus, stats["inputs"]["corpus_sha256"], stats)
    if verrs:
        for e in verrs:
            print(f"REFUSED sidecar {e}")
        return 1
    stamp = date.replace("-", "")
    out_dir.mkdir(parents=True, exist_ok=True)
    side = out_dir / f"market-signal-{stamp}.json"
    M.write_json(side, sc)
    if not args.no_report:
        (out_dir / f"market-signal-{stamp}.md").write_text(render(sc, stats, rep, an), encoding="utf-8")
    print(f"build_handoff: delivered {side.name}" + ("" if args.no_report else f" and market-signal-{stamp}.md")
          + f": {len(quotes)} verified quotes, escalated {', '.join(stats['escalated']) or 'none'}")
    return 0


# ---------------------------------------------------------------- report

def n_(n: int, word: str) -> str:
    """'1 author', '3 authors' (regular English plurals only)."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def pct(x) -> str:
    return "n/a" if x is None else f"{round(x * 100)} %"


def render(sc: Dict[str, Any], st: Dict[str, Any], rep: Dict[str, Any], an: Dict[str, Any]) -> str:
    q = {x["quote_id"]: x for x in sc["quotes"]}
    w = sc["window"]
    rule = sc["stats"]["escalation_rule"]
    L: List[str] = []
    a = L.append
    a(f"# Market signal: {sc['market']}")
    a("")
    a(f"Project `{sc['project']}`, built {sc['date']}, window {w['since']} to {w['until']} ({w['days']} days), "
      f"language {sc['language']}, geography {sc['geography']}. Valid until {sc['valid_until']}.")
    a("")
    a("Every number below comes from `stats.json` (scripts/compute_signals.py). Every quote was found again, word for word, in the stored corpus by scripts/verify_quotes.py.")
    a("")
    a("## Summary")
    a("")
    a(an["summary"])
    a("")
    esc = [p for p in sc["pains"] if p["escalated"]]
    a("Escalated pains: " + ("; ".join(f"`{p['pain_id']}` ({n_(p['distinct_authors'], 'author')}, {p['distinct_communities']} {'community' if p['distinct_communities'] == 1 else 'communities'})" for p in esc) or "none")
      + f". Rule: at least {rule['min_authors']} distinct authors across at least {rule['min_communities']} communities, speakers counted: {', '.join(rule['counted_speakers'])}.")
    a("")
    a("## Sources and health")
    a("")
    s = sc["stats"]
    a(f"{s['records_collected']} records collected, {s['records_relevant']} relevant after reading, {s['voices']} counted voices, {s['quotes_verified']} quotes verified.")
    a("")
    a("| Collector job | Source | Status | Records | Capped | Note |")
    a("|---|---|---|---|---|---|")
    for j in sc["source_health"]:
        a(f"| `{j['job_id']}` | {j['source']} | {j['status']} | {j['records']} | {'yes' if j.get('capped') else 'no'} | {j.get('message') or ''} |")
    a("")
    a("Records by source: " + ", ".join(f"{x['source']} {x['records']} ({pct(x['share'])})" for x in s["by_source"])
      + ". Counted voices by source: " + (", ".join(f"{x['source']} {x['records']} ({pct(x['share'])})" for x in s["voices_by_source"]) or "none") + ".")
    a("")
    sent = s["sentiment"]
    a("Sentiment of counted voices: " + ", ".join(f"{k} {v} ({pct(sent['shares'].get(k))})" for k, v in sent["counts"].items())
      + f", out of {sent['counted']}. Labels are the model's reading of each record; the split is a count of those labels.")
    a("")
    a("## Pains")
    a("")
    a("| Pain | Escalated | Authors | Communities | Voices | By source | First seen | Last seen | Trend | Volume |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for p in sc["pains"]:
        bys = ", ".join(f"{k} {v}" for k, v in p["by_source"].items()) or "none"
        a(f"| `{p['pain_id']}`: {p['summary']} | {'yes' if p['escalated'] else 'no'} | {p['distinct_authors']} | {p['distinct_communities']} | "
          f"{p['mention_count']} | {bys} | {p['first_seen'] or 'n/a'} | {p['last_seen'] or 'n/a'} | {p['trend']} | {p['volume']} |")
    a("")
    a("Trend compares the two halves of the window and reads `unknown` when a collector feeding the pain hit its cap: collectors keep the newest records, so the halves would be biased. Volume `lower_bound` means more records exist than were collected.")
    a("")
    if sc["weak_signals"]:
        a("Weak signals (under the threshold, kept for transparency, never as findings): "
          + "; ".join(f"`{x['pain_id']}` ({n_(x['distinct_authors'], 'author')}, {x['distinct_communities']} {'community' if x['distinct_communities'] == 1 else 'communities'})" for x in sc["weak_signals"]) + ".")
        a("")
    if sc["rejected_pains"]:
        a("Rejected pains:")
        a("")
        for r in sc["rejected_pains"]:
            a(f"- {r['summary']}: {r['reason']}")
        a("")
    a("## Quotes")
    a("")
    for p in sc["pains"] + [{"pain_id": None, "summary": "Not tied to a pain"}]:
        group = [x for x in sc["quotes"] if x["pain_id"] == p["pain_id"]]
        if not group:
            continue
        a(f"### {p['summary']}")
        a("")
        for x in group:
            a(f"> {x['text_verbatim']}")
            a("")
            warn = f", warnings: {', '.join(x['warnings'])}" if x["warnings"] else ""
            a(f"`{x['quote_id']}`, {x['community']}, {x['date']}, {x.get('speaker') or 'unlabelled'}, {x['char_count']} characters{warn}: [permalink]({x['permalink']})")
            a("")
    a("## Hooks, objections, angles")
    a("")
    for h in sc["hooks"]:
        a(f"> {h['text']}")
        a("")
        a(f"`{h['hook_id']}`, {'verbatim' if h['verbatim'] else 'analyst line, goes through the claims gate'}, {h['char_count']} characters, cites {', '.join(h['quote_ids'])}")
        a("")
    for o in sc["objections"]:
        a(f"> {o['text']}")
        a("")
        a(f"`{o['objection_id']}`, objection ({o['force']}), cites {', '.join(o['quote_ids'])}")
        a("")
    a("| Angle | Pain | Force | Awareness | Funnel | Headline quote | Support | Contrast | Formats |")
    a("|---|---|---|---|---|---|---|---|---|")
    for g in sc["angles"]:
        a(f"| `{g['angle_id']}` | `{g['pain_id']}`{'' if g['pain_escalated'] else ' (weak)'} | {g['force']} | {g['awareness_stage']} | {g['funnel_stage']} | "
          f"`{g['headline_quote_id']}` ({g['headline_char_count']} characters) | {', '.join(g['support_quote_ids']) or 'none'} | {g.get('contrast') or 'none'} | {', '.join(g['formats'])} |")
    a("")
    for g in sc["angles"]:
        if g.get("why"):
            a(f"- `{g['angle_id']}`: {g['why']}")
    a("")
    a("## Persona and forces")
    a("")
    for pe in sc["personas"]:
        a(f"**{pe['name']}**{' (primary)' if pe.get('primary') else ''}. {pe['context']}.")
        a("")
        forces = pe.get("jtbd_forces") or {}
        for f in ("push", "pull", "anxiety", "habit"):
            ids = forces.get(f) or []
            a(f"- {f.capitalize()}: " + (", ".join(f"`{i}`" for i in ids) if ids else "absent in this corpus"))
        for ap in pe.get("anti_personas", []):
            a(f"- Not for: {ap['segment']}. {ap['reason']} ({', '.join(ap['quote_ids'])})")
        a("")
    a("Force labels across counted voices: " + (", ".join(f"{k} {v}" for k, v in st["forces"].items()) or "none") + ".")
    a("")
    a("## Existing solutions")
    a("")
    for x in sc["existing_solutions"]:
        m = x.get("mentions")
        cnt = f"{n_(m['records'], 'record')} by {n_(m['distinct_authors'], 'author')}" if m else "not in the counted voices"
        a(f"- {x['name']} ({x['type']}, {x.get('sentiment', 'n/a')}): {cnt}; quotes {', '.join(x['quote_ids']) or 'none'}")
    a("")
    a("## Language bank")
    a("")
    if sc["language_bank"]:
        for x in sc["language_bank"]:
            a(f"- `{x['phrase']}`: {n_(x['records'], 'record')}, {n_(x['distinct_authors'], 'author')}" + (f", `{x['pain_id']}`" if x.get("pain_id") else ""))
    else:
        th = st["thresholds"]
        a(f"No phrase reached the threshold ({th['phrase_records']} records by {th['phrase_authors']} authors among counted voices, query words excluded).")
    a("")
    if sc.get("changes"):
        ch = sc["changes"]
        a("## Changes since the last run")
        a("")
        a(f"Previous window {ch['previous_window']['since']} to {ch['previous_window']['until']}. Distinct authors, then per 30 days.")
        a("")
        for r in ch["pains"]:
            lb = " (lower bound)" if r["lower_bound"] else ""
            flag = ", newly escalated" if r["newly_escalated"] else (", no longer escalated" if r["no_longer_escalated"] else "")
            a(f"- `{r['pain_id']}`: {r['status']}{lb}, {r['previous']['distinct_authors']} ({r['previous']['per_30_days']}) to {r['current']['distinct_authors']} ({r['current']['per_30_days']}){flag}")
        for x in ch.get("sources", []):
            a(f"- Collector `{x['job_id']}`: {x['previous']} to {x['current']}")
        if ch["competitors"]["new"]:
            a(f"- Alternatives named for the first time: {', '.join(ch['competitors']['new'])}")
        a("")
    a("## Recommendations")
    a("")
    for i, r in enumerate(sc["recommendations"], start=1):
        a(f"{i}. {r['text']} False if: {r['falsified_if']}" + (f" Quotes: {', '.join(r['quote_ids'])}." if r.get("quote_ids") else ""))
    a("")
    a("## Methodology")
    a("")
    a(f"- Collection: one collector per source (scripts/collect.py, parallel lanes per source), window {w['since']} to {w['until']}, corpus `{sc['corpus']['path']}` ({sc['corpus']['records']} records, sha256 `{sc['corpus']['sha256'][:12]}`).")
    a("- Coding: the model read every record and wrote one label per record (relevance, speaker, pains, sentiment, forces, awareness, alternatives named).")
    a(f"- Counting: scripts/compute_signals.py; a pain escalates at {rule['min_authors']} distinct authors and {rule['min_communities']} communities; one author posting several times counts once.")
    a(f"- Quotes: cited by record id and passage, verified by scripts/verify_quotes.py: {rep['passed']} of {rep['checked']} pass, {rep['warned']} with a warning.")
    a("- Sidecar: built and validated by scripts/build_handoff.py and scripts/validate_sidecar.py against assets/market-signal.schema.json.")
    a("")
    a("## Limitations")
    a("")
    for lim in sc["limitations"]:
        a(f"- {lim}")
    for j in sc["source_health"]:
        if j["status"] != "ok":
            a(f"- Collector `{j['job_id']}` ended {j['status']}: {j.get('message') or 'see health.json'}.")
    if sc["stats"]["capped_jobs"]:
        a(f"- Capped collectors (newest records kept, volumes are lower bounds): {', '.join(sc['stats']['capped_jobs'])}.")
    a("- Public discourse over-represents people who complain in public; silence in the corpus is not absence of the pain.")
    a("")
    a(f"*Generated by `market-signal` (scripts/build_handoff.py) from `{sc['corpus']['path']}`. Quotes are public strangers' words about a problem, never testimonials.*")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True, help="run folder")
    p.add_argument("--out-dir", help="where the sidecar and report go (default: the run's grandparent)")
    p.add_argument("--min-authors", type=int, default=5)
    p.add_argument("--min-communities", type=int, default=2)
    p.add_argument("--speakers", default="user,practitioner", help="speakers that count as voices (default user,practitioner)")
    p.add_argument("--phrase-records", type=int, default=3)
    p.add_argument("--phrase-authors", type=int, default=3)
    p.add_argument("--valid-days", type=int, default=90, help="valid_until = date + N days (default 90)")
    p.add_argument("--no-report", action="store_true")
    args = p.parse_args(argv)
    try:
        args.counted = C.parse_speakers(args.speakers)
    except ValueError as e:
        M.eprint(f"build_handoff: {e}")
        return 2
    run = Path(args.run).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else run.parent.parent
    return build(run, out_dir, args)


if __name__ == "__main__":
    sys.exit(main())
