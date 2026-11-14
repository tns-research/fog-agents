#!/usr/bin/env python3
"""validate_sidecar.py: check a market-signal sidecar v2 before anyone reads it.

  python3 scripts/validate_sidecar.py PROJECT/market-signal/market-signal-20261012.json \
      [--corpus PATH] [--stats PATH] [--no-corpus]

Checks, in order:
  schema        assets/market-signal.schema.json (shared stdlib validator)
  ids           ids unique per list; every quote, pain, persona and hook
                reference resolves
  verbatim      a hook marked verbatim and every objection text sit inside one
                of the quotes they cite
  window        every quote date inside the sidecar window; valid_until after date
  angles        headline_char_count and pain_escalated match the quote and the pain
  prose         no bare number in analyst prose (pain summaries, angle why,
                recommendations, non-verbatim hooks, personas): numbers come from
                the computed fields, which the report prints
  corpus        (default, from corpus.path next to the sidecar) the corpus hash
                matches, and each quote is found again in its record with the
                same permalink and date (verify_quotes rules)
  stats         (with --stats) every pain count equals stats.json

Exit 0 valid, 1 invalid (one line per problem), 2 unreadable file.
Importable: check(sidecar, corpus_rows=None, corpus_sha=None, stats=None) -> list of errors.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_\-])[$€£]?\d[\d,.]*\s?(?:%|k|K|m|M|bn|x)?(?![A-Za-z0-9])")
YEAR_RE = re.compile(r"^(19|20)\d\d$")


def prose_numbers(text: str) -> List[str]:
    """Bare numbers in analyst prose. Years (1900 to 2099) pass."""
    out = []
    for m in NUMBER_RE.finditer(text or ""):
        tok = m.group(0).strip()
        if YEAR_RE.match(tok):
            continue
        out.append(tok)
    return out


def _inside(text: str, quotes: List[str]) -> bool:
    t = M.normalize(text).strip()
    return any(t and t in M.normalize(q) for q in quotes)


def check(sc: Dict[str, Any], corpus_rows: Optional[List[Dict[str, Any]]] = None,
          corpus_sha: Optional[str] = None, stats: Optional[Dict[str, Any]] = None) -> List[str]:
    errs = [f"schema: {e}" for e in M.schema_errors(sc, "market-signal.schema.json")]
    if errs:
        return errs

    def uniq(items, key, label):
        ids = [i[key] for i in items]
        for d in sorted({i for i in ids if ids.count(i) > 1}):
            errs.append(f"ids: duplicate {label} {d}")
        return set(ids)

    q = {x["quote_id"]: x for x in sc["quotes"]}
    uniq(sc["quotes"], "quote_id", "quote_id")
    pains = {p["pain_id"]: p for p in sc["pains"]}
    uniq(sc["pains"], "pain_id", "pain_id")
    personas = uniq(sc["personas"], "persona_id", "persona_id")
    hooks = uniq(sc["hooks"], "hook_id", "hook_id")
    uniq(sc["objections"], "objection_id", "objection_id")
    uniq(sc["angles"], "angle_id", "angle_id")

    def need_q(ids, where):
        for i in ids or []:
            if i not in q:
                errs.append(f"ids: {where} cites {i}, not in quotes")

    def need_p(pid, where):
        if pid and pid not in pains:
            errs.append(f"ids: {where} names {pid}, not in pains")

    for x in sc["quotes"]:
        need_p(x.get("pain_id"), f"quote {x['quote_id']}")
        if x.get("persona_id") and x["persona_id"] not in personas:
            errs.append(f"ids: quote {x['quote_id']} names persona {x['persona_id']}, not in personas")
        if not M.in_window(x["date"], sc["window"]["since"], sc["window"]["until"]):
            errs.append(f"window: quote {x['quote_id']} dated {x['date']}, outside {sc['window']['since']} to {sc['window']['until']}")
    for p in sc["pains"]:
        need_q(p["quote_ids"], f"pain {p['pain_id']}")
        for n in prose_numbers(p["summary"]):
            errs.append(f"prose: pain {p['pain_id']} summary holds the number '{n}'")
    for h in sc["hooks"]:
        need_q(h["quote_ids"], f"hook {h['hook_id']}")
        need_p(h.get("pain_id"), f"hook {h['hook_id']}")
        cited = [q[i]["text_verbatim"] for i in h["quote_ids"] if i in q]
        if h["verbatim"] and not _inside(h["text"], cited):
            errs.append(f"verbatim: hook {h['hook_id']} is marked verbatim but is not inside its quotes")
        if not h["verbatim"]:
            for n in prose_numbers(h["text"]):
                errs.append(f"prose: hook {h['hook_id']} (analyst line) holds the number '{n}'")
        if h["char_count"] != len(h["text"]):
            errs.append(f"angles: hook {h['hook_id']} char_count {h['char_count']} != {len(h['text'])}")
    for o in sc["objections"]:
        need_q(o["quote_ids"], f"objection {o['objection_id']}")
        need_p(o.get("pain_id"), f"objection {o['objection_id']}")
        if not _inside(o["text"], [q[i]["text_verbatim"] for i in o["quote_ids"] if i in q]):
            errs.append(f"verbatim: objection {o['objection_id']} text is not inside its quotes")
    for a in sc["angles"]:
        need_p(a["pain_id"], f"angle {a['angle_id']}")
        need_q([a["headline_quote_id"]] + a["support_quote_ids"], f"angle {a['angle_id']}")
        hq = q.get(a["headline_quote_id"])
        if hq and hq["char_count"] != a["headline_char_count"]:
            errs.append(f"angles: {a['angle_id']} headline_char_count {a['headline_char_count']} != {hq['char_count']}")
        if a["pain_id"] in pains and pains[a["pain_id"]]["escalated"] != a["pain_escalated"]:
            errs.append(f"angles: {a['angle_id']} pain_escalated disagrees with pain {a['pain_id']}")
        for n in prose_numbers(a.get("why", "")):
            errs.append(f"prose: angle {a['angle_id']} why holds the number '{n}'")
    for s in sc.get("existing_solutions", []):
        need_q(s["quote_ids"], f"existing solution {s['name']}")
    for pe in sc["personas"]:
        for pid in pe.get("pain_ids", []):
            need_p(pid, f"persona {pe['persona_id']}")
        for force, ids in (pe.get("jtbd_forces") or {}).items():
            need_q(ids, f"persona {pe['persona_id']} force {force}")
        for hid in pe.get("hook_ids", []):
            if hid not in hooks:
                errs.append(f"ids: persona {pe['persona_id']} names hook {hid}, not in hooks")
        for ap in pe.get("anti_personas", []):
            need_q(ap.get("quote_ids"), f"persona {pe['persona_id']} anti-persona")
        for field in ("name", "context"):
            for n in prose_numbers(pe.get(field, "")):
                errs.append(f"prose: persona {pe['persona_id']} {field} holds the number '{n}'")
    for i, r in enumerate(sc.get("recommendations", [])):
        need_q(r.get("quote_ids"), f"recommendation {i + 1}")
        if not r.get("source_urls"):
            for field in ("text", "falsified_if"):
                for n in prose_numbers(r.get(field, "")):
                    errs.append(f"prose: recommendation {i + 1} {field} holds the number '{n}' without a source url")
    if sc["valid_until"] <= sc["date"]:
        errs.append("window: valid_until is not after date")

    if corpus_rows is not None:
        if corpus_sha and corpus_sha != sc["corpus"]["sha256"]:
            errs.append("corpus: sha256 differs from the sidecar (the corpus changed after the build)")
        import verify_quotes as V
        rep = V.verify([{"quote_id": x["quote_id"], "record_id": x["record_id"], "passage": x["text_verbatim"],
                         "permalink": x["permalink"], "date": x["date"]} for x in sc["quotes"]],
                       corpus_rows, sc["window"]["since"], sc["window"]["until"])
        for it in rep["items"]:
            if it["status"] == "block":
                errs.append(f"corpus: quote {it['quote_id']} blocks: {', '.join(it['codes'])}")
            elif it.get("text_verbatim") != q[it["quote_id"]]["text_verbatim"]:
                errs.append(f"corpus: quote {it['quote_id']} text differs from the record's exact text")
    if stats is not None:
        sp = {p["pain_id"]: p for p in stats.get("pains", [])}
        for p in sc["pains"]:
            s = sp.get(p["pain_id"])
            if not s:
                errs.append(f"stats: pain {p['pain_id']} absent from stats.json")
                continue
            for k_sc, k_st in (("mention_count", "voices"), ("distinct_authors", "distinct_authors"),
                               ("distinct_communities", "distinct_communities"), ("escalated", "escalated"),
                               ("trend", "trend"), ("volume", "volume")):
                if p[k_sc] != s[k_st]:
                    errs.append(f"stats: pain {p['pain_id']} {k_sc} {p[k_sc]} != stats {s[k_st]}")
        if sc["stats"]["records_collected"] != stats["corpus"]["records"]:
            errs.append("stats: records_collected differs from stats.json")
    return errs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sidecar")
    p.add_argument("--corpus", help="corpus.jsonl (default: corpus.path relative to the sidecar)")
    p.add_argument("--no-corpus", action="store_true", help="skip the corpus re-check (consumer side, corpus absent)")
    p.add_argument("--stats", help="stats.json to compare the counts with")
    args = p.parse_args(argv)
    path = Path(args.sidecar)
    try:
        sc = M.read_json(path)
        rows = sha = None
        if not args.no_corpus and isinstance(sc, dict):
            cpath = Path(args.corpus) if args.corpus else path.parent / sc.get("corpus", {}).get("path", "")
            if not cpath.is_file():
                print(f"{path}: corpus: {cpath} not found (use --no-corpus on the consumer side)")
                return 1
            rows, sha = M.read_jsonl(cpath), M.sha256_file(cpath)
        stats = M.read_json(Path(args.stats)) if args.stats else None
    except (OSError, ValueError) as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 2
    errs = check(sc, rows, sha, stats)
    for e in errs:
        print(f"{path}: {e}")
    if not errs:
        print(f"{path}: valid ({len(sc['quotes'])} quotes, {len(sc['pains'])} pains, {len(sc['angles'])} angles"
              + (", corpus re-checked" if rows is not None else "") + ")")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
