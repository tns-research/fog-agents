#!/usr/bin/env python3
"""collect_reddit.py: Reddit posts or comments through the Arctic Shift archive (no key).

  python3 scripts/collect_reddit.py --subreddit startups --query pre-seed --kind comments \
      --since 2026-07-14 --until 2026-10-12 --out run/corpus/reddit-startups.jsonl

Why Arctic Shift: reddit.com/search.json and the RSS feeds answer 403 to cloud
and datacenter IPs, so a free run on a hosted harness loses Reddit. Arctic
Shift (https://arctic-shift.photon-reddit.com, open source archive) serves the
same posts and comments as JSON. Coverage lags live Reddit by hours to days;
deleted and removed texts are dropped. A founder with Reddit OAuth can import
their own exports with import_records.py instead.

Search: --kind comments searches comment bodies (fast, recommended);
--kind posts searches titles and self texts (slow on big subreddits, the
archive may answer "Timeout. Maybe slow down a bit": the health is then quota,
retry later or narrow the window). Pagination walks back in time with the
created_utc of the last item, newest first.

Record: record_id reddit:t1_<id> (comment) or reddit:t3_<id> (post),
url https://www.reddit.com<permalink>, community r/<subreddit>, text with
markdown links reduced to their label and HTML entities decoded.

Exit 0 when the job ran (health ok or empty), 1 on error or quota, 2 usage.
"""

from __future__ import annotations

import argparse
import html
import sys

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

BASE = "https://arctic-shift.photon-reddit.com/api"
KEEP_COMMENT = ("id", "author", "body", "created_utc", "permalink", "score", "subreddit", "link_id", "parent_id")
KEEP_POST = ("id", "author", "title", "selftext", "created_utc", "permalink", "score", "num_comments", "subreddit", "url")


def trim(url, body):
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        keep = KEEP_COMMENT if "/comments/" in url else KEEP_POST
        body = {"data": [{k: d.get(k) for k in keep if k in d} for d in body["data"]], "error": body.get("error")}
    return body


def clean(s):
    return M.markdown_links_to_text(html.unescape(s or "")).strip()


def to_record(d, kind, query, fetched_at):
    sub = d.get("subreddit") or ""
    if kind == "comments":
        return M.make_record(
            source="reddit", native_id=f"t1_{d['id']}", community=f"r/{sub}", kind="comment",
            url="https://www.reddit.com" + (d.get("permalink") or ""), author=d.get("author"),
            created=d.get("created_utc"), text=clean(d.get("body")), context=None,
            score=d.get("score"), query=query, method="api:arctic-shift", fetched_at=fetched_at)
    title = clean(d.get("title"))
    body = clean(d.get("selftext"))
    if M.is_removed(body):
        body = ""
    return M.make_record(
        source="reddit", native_id=f"t3_{d['id']}", community=f"r/{sub}", kind="post",
        url="https://www.reddit.com" + (d.get("permalink") or ""), author=d.get("author"),
        created=d.get("created_utc"), text=title + ("\n\n" + body if body else ""), title=title,
        score=d.get("score"), replies=d.get("num_comments"), query=query,
        method="api:arctic-shift", fetched_at=fetched_at)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--subreddit", required=True, help="subreddit name without r/")
    p.add_argument("--query", default=None, help="full-text search in comment bodies or post title and text")
    p.add_argument("--kind", choices=("comments", "posts"), default="comments", help="default comments")
    p.add_argument("--per-page", type=int, default=None, help="items per request (default --limit + 10, archive max 100)")
    M.add_common_args(p)
    args = p.parse_args(argv)
    args.per_page = args.per_page or min(100, args.limit + 10)

    def gen(f: M.Fetcher, since, until, health):
        lo, hi = M.to_unix(since), M.to_unix(until, end_of_day=True)
        before = hi
        for _ in range(args.max_pages):
            params = {"subreddit": args.subreddit, "after": lo, "before": before,
                      "limit": args.per_page, "sort": "desc"}
            if args.query:
                params["body" if args.kind == "comments" else "query"] = args.query
            body = f.get_json(f"{BASE}/{args.kind}/search?" + M.qs(params))
            health.data["pages"] += 1
            if isinstance(body, dict) and body.get("error"):
                msg = str(body["error"])
                quota = any(w in msg.lower() for w in ("slow down", "rate", "too many"))
                raise M.FetchError(f"archive error: {msg}", quota=quota)
            items = (body or {}).get("data") or []
            for d in items:
                yield to_record(d, args.kind, args.query, f.last_fetched_at)
            if len(items) < args.per_page:
                break
            oldest = min(int(d.get("created_utc") or hi) for d in items)
            if oldest <= lo or oldest >= before:
                break
            before = oldest

    target = f"r/{args.subreddit} {args.kind}" + (f" '{args.query}'" if args.query else "")
    return M.run_collector(args, "reddit", target, gen, trim=trim)


if __name__ == "__main__":
    sys.exit(main())
