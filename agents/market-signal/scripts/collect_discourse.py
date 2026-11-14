#!/usr/bin/env python3
"""collect_discourse.py: posts from a public Discourse forum through /search.json (no key).

  python3 scripts/collect_discourse.py --host forum.bubble.io --query funding \
      --since 2026-07-14 --until 2026-10-12 --out run/corpus/discourse-bubble.jsonl

Many product and community forums run Discourse; their search answers JSON at
https://<host>/search.json. The search returns a truncated blurb per post, so
the collector fetches each kept post at /posts/<id>.json for its full text
(--blurbs-only skips that and keeps the blurb, flagged in the health). Window
filters use Discourse's after: and before: operators, newest first. A private
forum, or a host that is not Discourse, answers 403 or 404: health error.

Record: record_id discourse:<host>:<post_id>, url https://<host>/t/<slug>/<topic_id>/<post_number>,
community the host, context the topic title, text from the post HTML.

Exit 0 when the job ran (health ok or empty), 1 on error or quota, 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

KEEP_POST = ("id", "topic_id", "username", "created_at", "like_count", "blurb", "post_number")
KEEP_TOPIC = ("id", "title", "slug", "posts_count")


def trim(url, body):
    if not isinstance(body, dict):
        return body
    if "/search.json" in url:
        g = body.get("grouped_search_result") or {}
        return {"posts": [{k: x.get(k) for k in KEEP_POST if k in x} for x in body.get("posts", [])],
                "topics": [{k: x.get(k) for k in KEEP_TOPIC if k in x} for x in body.get("topics", [])],
                "grouped_search_result": {"more_full_page_results": g.get("more_full_page_results")}}
    return {k: body.get(k) for k in ("id", "topic_id", "topic_slug", "username", "created_at", "cooked",
                                     "post_number", "reply_count", "like_count") if k in body}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", required=True, help="forum host, e.g. forum.bubble.io")
    p.add_argument("--query", required=True, help="search terms (Discourse operators allowed, e.g. #category)")
    p.add_argument("--blurbs-only", action="store_true", help="keep the search blurb, skip the per-post fetch")
    M.add_common_args(p)
    args = p.parse_args(argv)
    host = args.host.replace("https://", "").replace("http://", "").strip("/")

    def gen(f: M.Fetcher, since, until, health):
        before = (dt.date.fromisoformat(until) + dt.timedelta(days=1)).isoformat()
        q = f"{args.query} after:{since} before:{before} order:latest"
        if args.blurbs_only:
            health.data["message"] = "blurbs only: texts are truncated search excerpts"
        for page in range(1, args.max_pages + 1):
            body = f.get_json(f"https://{host}/search.json?" + M.qs({"q": q, "page": page}))
            health.data["pages"] += 1
            if not isinstance(body, dict):
                raise M.FetchError(f"not a Discourse search answer: {str(body)[:200]}")
            topics = {t["id"]: t for t in body.get("topics", [])}
            posts = body.get("posts", [])
            for post in posts:
                t = topics.get(post.get("topic_id"), {})
                slug = t.get("slug") or "topic"
                if args.blurbs_only:
                    text, created, likes, user = M.html_to_text(post.get("blurb")), post.get("created_at"), post.get("like_count"), post.get("username")
                else:
                    full = f.get_json(f"https://{host}/posts/{post['id']}.json")
                    text, created = M.html_to_text(full.get("cooked")), full.get("created_at")
                    likes, user = full.get("like_count"), full.get("username")
                yield M.make_record(
                    source="discourse", native_id=f"{host}:{post['id']}", community=host, kind="post",
                    url=f"https://{host}/t/{slug}/{post.get('topic_id')}/{post.get('post_number')}",
                    author=user, created=created, text=text, context=t.get("title"), score=likes,
                    query=args.query, method="api:discourse-search", fetched_at=f.last_fetched_at)
            more = (body.get("grouped_search_result") or {}).get("more_full_page_results")
            if not posts or not more:
                break

    return M.run_collector(args, "discourse", f"{host} '{args.query}'", gen, trim=trim)


if __name__ == "__main__":
    sys.exit(main())
