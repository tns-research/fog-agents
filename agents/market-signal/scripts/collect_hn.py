#!/usr/bin/env python3
"""collect_hn.py: Hacker News through the free Algolia API (no key).

  python3 scripts/collect_hn.py --query '"warm intro"' --since 2026-07-14 --until 2026-10-12 \
      --out run/corpus/hn-warm-intro.jsonl [--tags story,comment] [--thread-comments 3]

Searches stories and comments in the window (Algolia numericFilters on
created_at_i), page by page up to --max-pages, keeps at most --limit records.
--thread-comments N also pulls the comments of the N best matching stories,
which is where the signal usually is. Quotes in the query give an exact phrase
(advancedSyntax on, typo tolerance off unless --fuzzy).

Record: record_id hn:<objectID>, url https://news.ycombinator.com/item?id=<id>,
text = comment text, or title + story text, HTML converted to plain text.

Exit 0 when the job ran (health ok or empty), 1 on error or quota, 2 usage.
"""

from __future__ import annotations

import re
import argparse
import sys

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

API = "https://hn.algolia.com/api/v1/search"
API_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"
KEEP = ("objectID", "created_at", "created_at_i", "author", "comment_text", "story_text", "title",
        "story_title", "story_id", "parent_id", "points", "num_comments", "url", "_tags")


def trim(url, body):
    if isinstance(body, dict) and "hits" in body:
        hits = [{k: h.get(k) for k in KEEP if k in h} for h in body["hits"]]
        for h in hits:  # Algolia repeats the handle as an author_<handle> tag
            if "_tags" in h:
                h["_tags"] = [t for t in h["_tags"] or [] if not str(t).startswith("author_")]
        body = {k: body[k] for k in ("nbHits", "nbPages", "page", "hitsPerPage") if k in body} | {"hits": hits}
    return body


JOB_SEEKER_THREAD = re.compile(r"who wants to be hired|seeking freelancer", re.I)


def is_job_seeker_post(h):
    """Monthly HN threads where people post their CV and email: never market signal, never stored."""
    return bool(JOB_SEEKER_THREAD.search(str(h.get("story_title") or "")))


def to_record(h, query, fetched_at):
    tags = h.get("_tags") or []
    oid = str(h["objectID"])
    if "comment" in tags or h.get("comment_text"):
        kind, title = "comment", None
        text = M.html_to_text(h.get("comment_text"))
        context = h.get("story_title")
    else:
        kind, title = "story", h.get("title")
        body = M.html_to_text(h.get("story_text"))
        text = (title or "") + ("\n\n" + body if body else "")
        context = None
    return M.make_record(
        source="hn", native_id=oid, community="Hacker News", kind=kind,
        url=f"https://news.ycombinator.com/item?id={oid}", author=h.get("author"),
        created=h.get("created_at_i") or h.get("created_at"), text=text, title=title, context=context,
        score=h.get("points"), replies=h.get("num_comments"), query=query,
        method="api:hn-algolia", fetched_at=fetched_at)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", action="append", required=True, help="search query (repeatable); quotes make an exact phrase")
    p.add_argument("--tags", default="story,comment", help="story, comment or story,comment (default)")
    p.add_argument("--sort", choices=("relevance", "date"), default="relevance", help="Algolia ranking (default relevance)")
    p.add_argument("--fuzzy", action="store_true", help="keep Algolia typo tolerance and loose syntax")
    p.add_argument("--thread-comments", type=int, default=0, help="also fetch the comments of the N best stories found")
    p.add_argument("--per-page", type=int, default=None, help="hits per page (default --limit + 10, max 1000)")
    M.add_common_args(p)
    args = p.parse_args(argv)
    args.per_page = args.per_page or min(100, args.limit + 10)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    tag_filter = tags[0] if len(tags) == 1 else "(" + ",".join(tags) + ")"

    def gen(f: M.Fetcher, since, until, health):
        lo, hi = M.to_unix(since), M.to_unix(until, end_of_day=True)
        base = API_BY_DATE if args.sort == "date" else API
        stories = []
        for q in args.query:
            for page in range(args.max_pages):
                params = {"query": q, "tags": tag_filter,
                          "numericFilters": f"created_at_i>={lo},created_at_i<{hi}",
                          "hitsPerPage": args.per_page, "page": page}
                if not args.fuzzy:
                    params.update({"advancedSyntax": "true", "typoTolerance": "false"})
                body = f.get_json(base + "?" + M.qs(params))
                health.data["pages"] += 1
                for h in body.get("hits", []):
                    if is_job_seeker_post(h):
                        continue
                    if "story" in (h.get("_tags") or []) and (h.get("num_comments") or 0) > 0:
                        stories.append(h)
                    yield to_record(h, q, f.last_fetched_at)
                if page + 1 >= int(body.get("nbPages") or 0):
                    break
        stories.sort(key=lambda h: (-(h.get("points") or 0), str(h["objectID"])))
        for s in stories[: max(0, args.thread_comments)]:
            sid = s["objectID"]
            for page in range(args.max_pages):
                params = {"tags": f"comment,story_{sid}", "hitsPerPage": args.per_page, "page": page,
                          "numericFilters": f"created_at_i>={lo},created_at_i<{hi}"}
                body = f.get_json(API + "?" + M.qs(params))
                health.data["pages"] += 1
                for h in body.get("hits", []):
                    if is_job_seeker_post(h):
                        continue
                    yield to_record(h, f"thread:{sid}", f.last_fetched_at)
                if page + 1 >= int(body.get("nbPages") or 0):
                    break

    return M.run_collector(args, "hn", " | ".join(args.query), gen, trim=trim)


if __name__ == "__main__":
    sys.exit(main())
