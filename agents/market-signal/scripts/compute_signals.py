#!/usr/bin/env python3
"""compute_signals.py: every number of the report, computed from the corpus and the labels.

  python3 scripts/compute_signals.py --corpus RUN/corpus.jsonl --labels RUN/labels.jsonl \
      [--analysis RUN/analysis.json] [--min-authors 5] [--min-communities 2] --out RUN/stats.json

The model labels records (labels.jsonl); it never writes a count, a share or a
trend. This script does, and the report prints only what stats.json holds.

Per pain:
  records               labelled records carrying the pain (all speakers)
  voices                those whose speaker counts (--speakers, default user and practitioner)
  distinct_authors      distinct author_hash among voices (no handle = one author per record)
  distinct_communities  distinct communities among voices
  by_source, shares     voices per source and their share of the pain's voices
  first_seen, last_seen, by_month
  halves, trend         voices in the first and second half of the window:
                        rising when the second half has at least twice the first
                        and 2 more, falling the other way round, else flat;
                        unknown when a voice came from a job that hit its cap
                        (collectors keep the newest records, so halves are biased)
  volume                complete, or lower_bound when a contributing job was capped
  resonance             median of score / median score of the same community and
                        kind in the corpus (null when the source has no score)
  escalated             distinct_authors >= --min-authors and distinct_communities
                        >= --min-communities. One author posting five times
                        counts once.
Corpus: records per source and community with shares, relevant records,
speakers, sentiment counts and shares over counted voices, JTBD forces,
competitor mentions (records and distinct authors), and a language bank:
2 to 6 word phrases found in at least --phrase-records records by at least
--phrase-authors authors among counted voices (a phrase the collection
searched for is dropped: it measures the query, not the market).

Exit 0 written, 1 when labels name an unknown record or a pain absent from
--analysis, 2 on unreadable input or an unknown --speakers value.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

STOP = set("""a an the and or but if then so of to in on at for from by with without about as is are was were be been being
it its it's this that these those there here i i'm i've i'd me my we our you your they them their he she his her
do does did doing have has had not no yes just very really more most less than too also can could would should will
what which who whom when where why how all any some one two up out into over under again only own same such
""".split())


def share(n: int, total: int) -> Optional[float]:
    return round(n / total, 3) if total else None


def month(day: str) -> str:
    return day[:7]


def tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9à-ÿ]+(?:'[a-z]+)?", M.normalize(text).lower())


def language_bank(voices: List[Dict[str, Any]], pain_of: Dict[str, List[str]], min_records: int,
                  min_authors: int, queries: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    grams: Dict[str, set] = defaultdict(set)
    authors: Dict[str, set] = defaultdict(set)
    qnorm = [" ".join(tokens(q)) for q in queries if q]
    for r in voices:
        toks = tokens(r.get("text") or "")
        seen = set()
        for n in range(2, 7):
            for i in range(len(toks) - n + 1):
                g = toks[i:i + n]
                if g[0] in STOP or g[-1] in STOP or sum(1 for t in g if t not in STOP) < 2:
                    continue
                key = " ".join(g)
                if key in seen:
                    continue
                seen.add(key)
                grams[key].add(r["record_id"])
                authors[key].add(r.get("author_hash") or r["record_id"])
    # A phrase the collection searched for is an artefact of the query, not language.
    kept = {k: v for k, v in grams.items() if len(v) >= min_records and len(authors[k]) >= min_authors
            and not any(k in q or q in k for q in qnorm)}
    # Drop a phrase contained in a longer kept phrase found in the same records.
    final = []
    for k in sorted(kept, key=lambda x: (-len(x.split()), x)):
        if any(k in f and kept[f] == kept[k] for f in final):
            continue
        final.append(k)
    out = []
    for k in final:
        pains = Counter(p for rid in kept[k] for p in pain_of.get(rid, []))
        out.append({"phrase": k, "records": len(kept[k]), "distinct_authors": len(authors[k]),
                    "pain_id": pains.most_common(1)[0][0] if pains else None,
                    "record_ids": sorted(kept[k])})
    out.sort(key=lambda x: (-x["distinct_authors"], -x["records"], -len(x["phrase"]), x["phrase"]))
    return out[:limit]


def capped_records(run: Optional[Path]):
    """Record ids that came from a job which hit its cap, and the capped job ids."""
    if not run or not (run / "health.json").exists():
        return set(), []
    jobs = [j for j in M.read_json(run / "health.json").get("jobs", []) if j.get("capped")]
    ids = set()
    for j in jobs:
        f = run / "corpus" / f"{j['job_id']}.jsonl"
        if "record_ids" in j:
            ids |= set(j["record_ids"])
        elif f.exists():
            ids |= {r["record_id"] for r in M.read_jsonl(f)}
    return ids, sorted(j["job_id"] for j in jobs)


def compute(corpus: List[Dict[str, Any]], labels: List[Dict[str, Any]], since: str, until: str,
            pain_ids: Optional[List[str]] = None, min_authors: int = 5, min_communities: int = 2,
            counted=("user", "practitioner"), phrase_records: int = 3, phrase_authors: int = 3,
            run: Optional[Path] = None):
    errors: List[str] = []
    by_id = {r["record_id"]: r for r in corpus}
    lab = {}
    for l in labels:
        if l["record_id"] not in by_id:
            errors.append(f"label for unknown record {l['record_id']}")
            continue
        lab[l["record_id"]] = l
    used = sorted({p for l in lab.values() for p in (l.get("pains") or [])})
    if pain_ids is not None:
        for p in used:
            if p not in pain_ids:
                errors.append(f"labels use {p}, absent from analysis.json pains")
    all_pains = list(pain_ids) if pain_ids is not None else used

    d0, d1 = date.fromisoformat(since), date.fromisoformat(until)
    days = (d1 - d0).days + 1
    mid = d0.toordinal() + days // 2

    def counted_voice(rid):
        l = lab.get(rid)
        return bool(l and l.get("relevant") and l.get("speaker", "other") in counted)

    medians: Dict[str, float] = {}
    groups: Dict[str, List[int]] = defaultdict(list)
    for r in corpus:
        if r.get("score") is not None:
            groups[f"{r['community']}|{r['kind']}"].append(r["score"])
    for k, v in groups.items():
        medians[k] = statistics.median(v)

    capped_ids, capped_jobs = capped_records(run)
    voices = [by_id[rid] for rid in sorted(lab) if counted_voice(rid)]
    pain_of = {rid: (lab[rid].get("pains") or []) for rid in lab}

    pains_out = []
    for pid in all_pains:
        recs = [by_id[rid] for rid in sorted(lab) if pid in (lab[rid].get("pains") or []) and lab[rid].get("relevant")]
        vs = [r for r in recs if counted_voice(r["record_id"])]
        authors = {r.get("author_hash") or r["record_id"] for r in vs}
        comms = {r["community"] for r in vs}
        src = Counter(r["source"] for r in vs)
        dates = sorted(r["date"] for r in vs if r.get("date"))
        first = sum(1 for d in dates if date.fromisoformat(d).toordinal() < mid)
        second = len(dates) - first
        capped = any(r["record_id"] in capped_ids for r in vs)
        trend = "rising" if second >= 2 * first and second - first >= 2 else (
            "falling" if first >= 2 * second and first - second >= 2 else "flat")
        if capped:
            trend = "unknown"  # a capped job keeps the newest records: halves are biased
        ratios = []
        for r in vs:
            m = medians.get(f"{r['community']}|{r['kind']}")
            if r.get("score") is not None and m and m > 0:
                ratios.append(r["score"] / m)
        sent = Counter(lab[r["record_id"]].get("sentiment", "neutral") for r in vs)
        forces = Counter(f for r in vs for f in (lab[r["record_id"]].get("forces") or []))
        pains_out.append({
            "pain_id": pid, "records": len(recs), "voices": len(vs),
            "distinct_authors": len(authors), "distinct_communities": len(comms),
            "communities": sorted(comms),
            "by_source": dict(sorted(src.items())),
            "source_shares": {k: share(v, len(vs)) for k, v in sorted(src.items())},
            "first_seen": dates[0] if dates else None, "last_seen": dates[-1] if dates else None,
            "by_month": dict(sorted(Counter(month(d) for d in dates).items())),
            "halves": {"first": first, "second": second}, "trend": trend,
            "volume": "lower_bound" if capped else "complete",
            "resonance": round(statistics.median(ratios), 2) if ratios else None,
            "sentiment": dict(sorted(sent.items())), "forces": dict(sorted(forces.items())),
            "escalated": len(authors) >= min_authors and len(comms) >= min_communities,
            "record_ids": [r["record_id"] for r in vs],
        })
    pains_out.sort(key=lambda p: (not p["escalated"], -p["distinct_authors"], -p["voices"], p["pain_id"]))

    src_all = Counter(r["source"] for r in corpus)
    comm_all = Counter(r["community"] for r in corpus)
    relevant = [rid for rid, l in lab.items() if l.get("relevant")]
    speakers = Counter(lab[rid].get("speaker", "other") for rid in relevant)
    sent_all = Counter(lab[r["record_id"]].get("sentiment", "neutral") for r in voices)
    comp_recs: Dict[str, set] = defaultdict(set)
    comp_auth: Dict[str, set] = defaultdict(set)
    for r in voices:
        for c in lab[r["record_id"]].get("competitors") or []:
            comp_recs[c].add(r["record_id"])
            comp_auth[c].add(r.get("author_hash") or r["record_id"])
    stats = {
        "schema_version": "2.0",
        "window": {"since": since, "until": until, "days": days},
        "capped_jobs": capped_jobs,
        "thresholds": {"min_authors": min_authors, "min_communities": min_communities,
                       "counted_speakers": list(counted), "phrase_records": phrase_records,
                       "phrase_authors": phrase_authors},
        "corpus": {
            "records": len(corpus), "labelled": len(lab), "unlabelled": len(corpus) - len(lab),
            "relevant": len(relevant), "voices": len(voices),
            "out_of_window": sum(1 for r in corpus if not M.in_window(r.get("date"), since, until)),
            "by_source": [{"source": k, "records": v, "share": share(v, len(corpus))} for k, v in sorted(src_all.items())],
            "voices_by_source": [{"source": k, "records": v, "share": share(v, len(voices))}
                                 for k, v in sorted(Counter(r["source"] for r in voices).items())],
            "by_community": [{"community": k, "records": v} for k, v in sorted(comm_all.items(), key=lambda x: (-x[1], x[0]))],
            "by_speaker": dict(sorted(speakers.items())),
        },
        "sentiment": {"counted": len(voices), "counts": dict(sorted(sent_all.items())),
                      "shares": {k: share(v, len(voices)) for k, v in sorted(sent_all.items())}},
        "forces": dict(sorted(Counter(f for r in voices for f in (lab[r["record_id"]].get("forces") or [])).items())),
        "pains": pains_out,
        "escalated": [p["pain_id"] for p in pains_out if p["escalated"]],
        "competitors": sorted(({"name": k, "records": len(v), "distinct_authors": len(comp_auth[k])} for k, v in comp_recs.items()),
                              key=lambda x: (-x["distinct_authors"], x["name"])),
        "language_bank": language_bank(voices, pain_of, phrase_records, phrase_authors,
                                       sorted({r.get("query") or "" for r in corpus})),
        "community_medians": {k: v for k, v in sorted(medians.items())},
    }
    return stats, errors


def parse_speakers(value: str):
    """Comma-separated speakers to count as voices; ValueError on an empty list or an unknown speaker."""
    known = M.read_json(M.ASSETS / "labels.schema.json")["properties"]["speaker"]["enum"]
    got = tuple(s.strip() for s in (value or "").split(",") if s.strip())
    bad = [s for s in got if s not in known]
    if bad or not got:
        raise ValueError(f"--speakers {value!r}: " + (f"unknown speaker {', '.join(bad)}" if bad else "empty")
                         + f" (known: {', '.join(known)})")
    return got


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--analysis", help="analysis.json: pain list and window")
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--min-authors", type=int, default=5)
    p.add_argument("--min-communities", type=int, default=2)
    p.add_argument("--speakers", default="user,practitioner", help="speakers that count as voices")
    p.add_argument("--phrase-records", type=int, default=3)
    p.add_argument("--phrase-authors", type=int, default=3)
    p.add_argument("--run", help="run folder with health.json and corpus/<job>.jsonl (default: the corpus folder)")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    try:
        counted = parse_speakers(args.speakers)
    except ValueError as e:
        M.eprint(f"compute_signals: {e}")
        return 2
    try:
        corpus = M.read_jsonl(Path(args.corpus))
        labels = M.read_jsonl(Path(args.labels))
        analysis = M.read_json(Path(args.analysis)) if args.analysis else {}
    except (OSError, ValueError) as e:
        M.eprint(f"compute_signals: {e}")
        return 2
    bad = [f"labels.jsonl line {i + 1}: {e}" for i, l in enumerate(labels) for e in M.schema_errors(l, "labels.schema.json")]
    if bad:
        for b in bad[:20]:
            M.eprint(b)
        return 1
    w = analysis.get("window") or {}
    since, until = M.window_from(args.since or w.get("since"), args.until or w.get("until"), analysis.get("as_of"))
    pain_ids = [x["pain_id"] for x in analysis.get("pains", [])] if analysis else None
    stats, errors = compute(corpus, labels, since, until, pain_ids, args.min_authors, args.min_communities,
                            counted,
                            args.phrase_records, args.phrase_authors,
                            Path(args.run) if args.run else Path(args.corpus).resolve().parent)
    stats["inputs"] = {"corpus": Path(args.corpus).name, "corpus_sha256": M.sha256_file(Path(args.corpus)),
                       "labels_sha256": M.sha256_file(Path(args.labels))}
    M.write_json(Path(args.out), stats)
    for e in errors:
        M.eprint(f"compute_signals: {e}")
    esc = ", ".join(stats["escalated"]) or "none"
    print(f"compute_signals: {stats['corpus']['records']} records, {stats['corpus']['labelled']} labelled, "
          f"{stats['corpus']['voices']} voices; escalated: {esc}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
