#!/usr/bin/env python3
"""import_records.py: turn a file into corpus records (manual exports and optional paid providers).

  python3 scripts/import_records.py --input reviews.csv --format csv --source g2 \
      --community "G2: <product>" --since 2026-07-14 --until 2026-10-12 --out run/corpus/g2.jsonl
  python3 scripts/import_records.py --input exa-q1.json --format exa-json --out run/corpus/exa-q1.jsonl

For what no free API serves from a server: G2 or Capterra reviews the founder
exports, Reddit threads saved with the founder's own OAuth app, interview notes
with consent, or the JSON output of an optional search provider (exa search
--json --text or --highlights). Nothing here calls a network.

Formats:
  csv        header row; columns url, date, text required; author, title,
             community, kind, score, rating, source optional (per row overrides).
  jsonl      one object per line with the same keys.
  exa-json   the exa CLI JSON (a leading "Found N results" line is skipped):
             url, title, author, publishedDate, and text or highlights. A result
             without text or highlights is dropped (counted in the health).

Every row needs a url and a date: a row without them is dropped, never guessed.
record_id is <source>:<sha1(url + text)[:12]>, stable across imports.

Exit 0 when the import ran (health ok or empty), 1 on an unreadable file, 2 usage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M


def rows_from(path: Path, fmt: str):
    raw = path.read_text(encoding="utf-8")
    if fmt == "csv":
        yield from csv.DictReader(raw.splitlines())
    elif fmt == "jsonl":
        for line in raw.splitlines():
            if line.strip():
                yield json.loads(line)
    else:
        start = min([i for i in (raw.find("["), raw.find("{")) if i >= 0] or [0])
        data = json.loads(raw[start:])
        results = data.get("results", data) if isinstance(data, dict) else data
        for r in results:
            text = r.get("text") or "\n\n".join(r.get("highlights") or [])
            yield {"url": r.get("url"), "date": r.get("publishedDate"), "text": text,
                   "author": r.get("author"), "title": r.get("title")}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="file to import")
    p.add_argument("--format", choices=("csv", "jsonl", "exa-json"), required=True)
    p.add_argument("--source", default=None, help="source label (default: manual, or exa for exa-json)")
    p.add_argument("--community", default=None, help="community label when rows have none (default the url host)")
    p.add_argument("--kind", default=None, help="record kind when rows have none (default post, review for csv with rating)")
    M.add_common_args(p)
    args = p.parse_args(argv)
    path = Path(args.input)
    if not path.exists():
        M.eprint(f"import_records: {path} not found")
        return 2
    source = args.source or ("exa" if args.format == "exa-json" else "manual")

    def gen(f, since, until, health):
        health.data["pages"] = 1
        dropped = 0
        for r in rows_from(path, args.format):
            url, text = (r.get("url") or "").strip(), (r.get("text") or "").strip()
            if not url or not text or not M.parse_date(r.get("date")):
                dropped += 1
                health.data["dropped_incomplete"] = dropped
                continue
            src = r.get("source") or source
            host = url.split("/")[2] if "://" in url else url
            rating = r.get("rating")
            rec = M.make_record(
                source=src, native_id=hashlib.sha1((url + "\n" + text).encode("utf-8"), usedforsecurity=False).hexdigest()[:12],
                community=r.get("community") or args.community or host,
                kind=r.get("kind") or args.kind or ("review" if rating not in (None, "") else "post"),
                url=url, author=r.get("author") or None, created=r.get("date"), text=text,
                title=r.get("title") or None,
                score=int(r["score"]) if str(r.get("score") or "").lstrip("-").isdigit() else None,
                rating=int(rating) if str(rating or "").isdigit() else None,
                method=f"import:{args.format}:{path.name}", fetched_at=None)
            yield rec

    try:
        return M.run_collector(args, source, f"{path.name} ({args.format})", gen)
    except (OSError, json.JSONDecodeError, csv.Error) as e:
        M.eprint(f"import_records: cannot read {path}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
