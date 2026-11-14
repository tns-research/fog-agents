#!/usr/bin/env python3
"""verify_quotes.py: check every quote against the stored corpus; BLOCK on any doubt.

  python3 scripts/verify_quotes.py --corpus RUN/corpus.jsonl --quotes RUN/analysis.json \
      [--since 2026-07-14 --until 2026-10-12] [--out RUN/quotes-check.json]

--quotes takes any JSON with a "quotes" list: the model's analysis.json
(quote_id, record_id, passage), a market-signal sidecar v2 (record_id,
text_verbatim) or a bare citations file. The window comes from --since and
--until, else from the file's "window", else --as-of minus --recency-days.

The model never retypes a quote as the truth: it names a record and copies a
passage; this script finds the passage in the record and returns the exact
original text (text_verbatim), its url and date.

Accepted differences: whitespace runs, curly versus straight quote marks of the
same kind, Unicode composition. Anything else blocks.

BLOCK codes (the quote cannot ship):
  no-record            record_id missing: a line with no source
  record-not-in-corpus record_id names no record of the corpus
  not-found            the passage is not in the record
  case-changed         found only when ignoring case (recapitalised)
  elided               the passage joins cut parts with ... or [...]: cite each part as its own quote
  out-of-window        the record's date is outside the window
  no-date              the record has no date
  no-url               the record has no url
  removed              the record text is [removed] or [deleted]
  metadata-mismatch    the quote states a url or date that differs from its record
WARN codes (shipped, shown in the report):
  short                fewer than 4 words
  mid-word             the passage starts or ends inside a word

Exit 0 when no quote blocks (warnings allowed), 1 when at least one blocks,
2 on unreadable input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

BLOCK = ("no-record", "record-not-in-corpus", "not-found", "case-changed", "elided",
         "out-of-window", "no-date", "no-url", "removed", "metadata-mismatch")
WARN = ("short", "mid-word")


def _found_ci(passage: str, text: str) -> bool:
    return M.normalize(passage).strip().lower() in M.normalize(text).lower()


def check_quote(q: Dict[str, Any], corpus: Dict[str, Dict[str, Any]], since: str, until: str) -> Dict[str, Any]:
    qid = q.get("quote_id") or "?"
    rid = q.get("record_id")
    passage = q.get("passage") or q.get("text_verbatim") or ""
    res: Dict[str, Any] = {"quote_id": qid, "record_id": rid, "status": "pass", "codes": [], "warnings": []}
    if not rid:
        res["codes"].append("no-record")
    elif rid not in corpus:
        res["codes"].append("record-not-in-corpus")
    if res["codes"]:
        res["status"] = "block"
        return res
    rec = corpus[rid]
    text = rec.get("text") or ""
    if M.is_removed(text):
        res["codes"].append("removed")
    span = M.find_verbatim(passage, text)
    if span is None:
        if M.ELLIPSIS_RE.search(passage):
            res["codes"].append("elided")
            parts = [p for p in M.ELLIPSIS_RE.split(passage) if p.strip()]
            missing = [p for p in parts if M.find_verbatim(p, text) is None]
            if missing:
                res["codes"].append("case-changed" if all(_found_ci(p, text) for p in missing) else "not-found")
        elif _found_ci(passage, text):
            res["codes"].append("case-changed")
        else:
            res["codes"].append("not-found")
    else:
        a, b = span
        res["text_verbatim"] = text[a:b]
        res["char_count"] = len(text[a:b])
        if M.word_count(passage) < 4:
            res["warnings"].append("short")
        if (a > 0 and text[a - 1].isalnum() and text[a].isalnum()) or (b < len(text) and text[b - 1].isalnum() and text[b].isalnum()):
            res["warnings"].append("mid-word")
    day = rec.get("date")
    if not day:
        res["codes"].append("no-date")
    elif not M.in_window(day, since, until):
        res["codes"].append("out-of-window")
    if not rec.get("url"):
        res["codes"].append("no-url")
    for key, rkey in (("permalink", "url"), ("url", "url"), ("date", "date")):
        if q.get(key) and rec.get(rkey) and q[key] != rec[rkey]:
            res["codes"].append("metadata-mismatch")
            break
    res.update({"url": rec.get("url"), "date": day, "source": rec.get("source"),
                "community": rec.get("community"), "kind": rec.get("kind"), "author_hash": rec.get("author_hash")})
    res["status"] = "block" if res["codes"] else "pass"
    return res


def verify(quotes: List[Dict[str, Any]], corpus_rows: List[Dict[str, Any]], since: str, until: str) -> Dict[str, Any]:
    corpus = {r["record_id"]: r for r in corpus_rows}
    items = [check_quote(q, corpus, since, until) for q in quotes]
    ids = [i["quote_id"] for i in items]
    dups = sorted({i for i in ids if ids.count(i) > 1})
    blocked = [i for i in items if i["status"] == "block"]
    return {
        "status": "block" if blocked or dups else "pass",
        "window": {"since": since, "until": until},
        "checked": len(items), "passed": len(items) - len(blocked), "blocked": len(blocked),
        "warned": sum(1 for i in items if i["warnings"]), "duplicate_quote_ids": dups,
        "by_code": {c: sum(1 for i in items if c in i["codes"]) for c in BLOCK if any(c in i["codes"] for i in items)},
        "items": items,
    }


def resolve_window(args, doc: Dict[str, Any]):
    w = doc.get("window") or {}
    since = args.since or w.get("since") or w.get("start")
    until = args.until or w.get("until") or w.get("end")
    return M.window_from(since, until, args.as_of or doc.get("as_of") or doc.get("date"),
                         args.recency_days or w.get("recency_days"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", required=True, help="corpus.jsonl of the run")
    p.add_argument("--quotes", required=True, help="analysis.json, sidecar v2 or citations file with a quotes list")
    p.add_argument("--since")
    p.add_argument("--until")
    p.add_argument("--as-of", help="end of the window when the file has none (default today UTC)")
    p.add_argument("--recency-days", type=int, help="window length when no start is given (default 90)")
    p.add_argument("--out", help="write the JSON report here (default: stdout summary only)")
    p.add_argument("--json", action="store_true", help="print the JSON report on stdout")
    args = p.parse_args(argv)
    try:
        rows = M.read_jsonl(Path(args.corpus))
        doc = M.read_json(Path(args.quotes))
    except (OSError, ValueError) as e:
        M.eprint(f"verify_quotes: {e}")
        return 2
    quotes = doc.get("quotes") if isinstance(doc, dict) else doc
    if not isinstance(quotes, list):
        M.eprint("verify_quotes: no quotes list in the file")
        return 2
    since, until = resolve_window(args, doc if isinstance(doc, dict) else {})
    rep = verify(quotes, rows, since, until)
    if args.out:
        M.write_json(Path(args.out), rep)
    if args.json:
        import json
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        for it in rep["items"]:
            if it["status"] == "block" or it["warnings"]:
                tag = "BLOCK" if it["status"] == "block" else "WARN "
                print(f"{tag} {it['quote_id']} ({it['record_id']}): {', '.join(it['codes'] + it['warnings'])}"
                      + (f" [record date {it.get('date')}]" if "out-of-window" in it["codes"] else ""))
        if rep["duplicate_quote_ids"]:
            print(f"BLOCK duplicate quote ids: {', '.join(rep['duplicate_quote_ids'])}")
        print(f"verify_quotes: {rep['status'].upper()}, {rep['passed']}/{rep['checked']} pass, "
              f"window {since} to {until}")
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
