#!/usr/bin/env python3
"""collect_stackexchange.py: questions (and optionally answers) from a Stack Exchange site (no key).

  python3 scripts/collect_stackexchange.py --site money --query investors \
      --since 2026-07-14 --until 2026-10-12 --out run/corpus/se-money.jsonl [--answers]

Uses the public API v2.3 (/search/advanced with filter=withbody), 300
requests a day per IP without a key. The API reports quota_remaining and may
ask for a backoff: the health turns to quota when the daily quota is spent or
the API throttles. An unknown site name is an error ("No site found"); some
sites close (startups.stackexchange.com no longer exists).

Record: record_id se:<site>:q<id> or se:<site>:a<id>, url of the question (an
answer url ends with #<answer_id>), text = title + body for a question, body
for an answer, HTML converted to plain text.

Exit 0 when the job ran (health ok or empty), 1 on error or quota, 2 usage.
"""

from __future__ import annotations

import argparse
import sys
import time

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

API = "https://api.stackexchange.com/2.3"
KEEP_Q = ("question_id", "answer_id", "creation_date", "title", "body", "link", "score", "answer_count", "owner", "tags")


def trim(url, body):
    if isinstance(body, dict) and isinstance(body.get("items"), list):
        items = []
        for it in body["items"]:
            x = {k: it.get(k) for k in KEEP_Q if k in it}
            if isinstance(x.get("owner"), dict):
                x["owner"] = {"display_name": x["owner"].get("display_name")}
            items.append(x)
        body = {k: body.get(k) for k in ("has_more", "quota_remaining", "backoff") if k in body} | {"items": items}
    return body


def check(body):
    if not isinstance(body, dict):
        raise M.FetchError(f"unexpected body: {str(body)[:200]}")
    if body.get("error_id"):
        quota = body.get("error_id") in (502,) or "throttle" in str(body.get("error_name", ""))
        raise M.FetchError(f"API error {body.get('error_id')} {body.get('error_name')}: {body.get('error_message')}", quota=quota)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", required=True, help="API site name, e.g. money, workplace, softwareengineering")
    p.add_argument("--query", required=True, help="free-text query (q parameter)")
    p.add_argument("--tagged", default=None, help="semicolon-separated tags to require")
    p.add_argument("--sort", choices=("relevance", "creation", "votes", "activity"), default="relevance")
    p.add_argument("--answers", action="store_true", help="also fetch the answers of the questions found (one request)")
    p.add_argument("--per-page", type=int, default=None, help="items per page (default --limit + 10, max 100)")
    M.add_common_args(p)
    args = p.parse_args(argv)
    args.per_page = args.per_page or min(100, args.limit + 10)

    def gen(f: M.Fetcher, since, until, health):
        lo, hi = M.to_unix(since), M.to_unix(until, end_of_day=True)
        links = {}
        for page in range(1, args.max_pages + 1):
            params = {"order": "desc", "sort": args.sort, "q": args.query, "tagged": args.tagged,
                      "site": args.site, "fromdate": lo, "todate": hi, "page": page,
                      "pagesize": args.per_page, "filter": "withbody"}
            body = f.get_json(f"{API}/search/advanced?" + M.qs(params))
            health.data["pages"] += 1
            check(body)
            health.data["quota_remaining"] = body.get("quota_remaining")
            for it in body.get("items", []):
                links[it["question_id"]] = it.get("link")
                yield M.make_record(
                    source="se", native_id=f"{args.site}:q{it['question_id']}", community=f"{args.site}.stackexchange",
                    kind="question", url=it.get("link"), author=(it.get("owner") or {}).get("display_name"),
                    created=it.get("creation_date"),
                    text=M.html_to_text(it.get("title")) + "\n\n" + M.html_to_text(it.get("body")),
                    title=M.html_to_text(it.get("title")), score=it.get("score"), replies=it.get("answer_count"),
                    query=args.query, method="api:stackexchange", fetched_at=f.last_fetched_at)
            if body.get("quota_remaining") == 0:
                raise M.FetchError("daily quota spent (quota_remaining 0)", quota=True)
            if body.get("backoff") and not args.fixtures:
                time.sleep(int(body["backoff"]))
            if not body.get("has_more"):
                break
        if args.answers and links:
            ids = ";".join(str(i) for i in sorted(links))
            body = f.get_json(f"{API}/questions/{ids}/answers?" + M.qs(
                {"order": "desc", "sort": "votes", "site": args.site, "pagesize": 100, "filter": "withbody"}))
            health.data["pages"] += 1
            check(body)
            for it in body.get("items", []):
                q = links.get(it["question_id"]) or ""
                yield M.make_record(
                    source="se", native_id=f"{args.site}:a{it['answer_id']}", community=f"{args.site}.stackexchange",
                    kind="answer", url=f"{q}#{it['answer_id']}", author=(it.get("owner") or {}).get("display_name"),
                    created=it.get("creation_date"), text=M.html_to_text(it.get("body")),
                    score=it.get("score"), query=args.query, method="api:stackexchange", fetched_at=f.last_fetched_at)

    return M.run_collector(args, "se", f"{args.site} '{args.query}'", gen, trim=trim)


if __name__ == "__main__":
    sys.exit(main())
