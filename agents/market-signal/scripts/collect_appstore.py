#!/usr/bin/env python3
"""collect_appstore.py: App Store reviews of one app through the public iTunes RSS JSON feed (no key).

  python3 scripts/collect_appstore.py --app-id 1137735263 --country us --app-name Carta \
      --since 2026-07-14 --until 2026-10-12 --out run/corpus/appstore-carta.jsonl

Feed: https://itunes.apple.com/<cc>/rss/customerreviews/page=<n>/id=<app>/sortby=mostrecent/json,
50 reviews a page, 10 pages at most, newest first. The feed has no date
filter: the collector stops paging once a page ends before --since. Find an
app id with https://itunes.apple.com/search?term=<name>&entity=software.

Known behaviour: the feed often answers a valid empty feed (no "entry") for
hours, page by page and country by country. The health is then empty with that
hint; try another country or later. Reviews have no public permalink: url is
the app's review listing, the review id stays in record_id.

Record: record_id appstore:<app_id>:<review_id>, community "App Store <cc>: <name>",
text = review title + body, rating 1 to 5.

Exit 0 when the job ran (health ok or empty), 1 on error or quota, 2 usage.
"""

from __future__ import annotations

import argparse
import sys

sys.dont_write_bytecode = True  # keep the agent folder free of __pycache__
import mslib as M

HINT = "the iTunes review feed answered no entries; it does this intermittently, retry later or with another --country"


def trim(url, body):
    if isinstance(body, dict) and isinstance(body.get("feed"), dict):
        e = body["feed"].get("entry", [])
        if isinstance(e, dict):
            e = [e]
        keep = ("author", "updated", "im:rating", "im:version", "id", "title", "content", "im:voteSum")
        entries = [{k: x.get(k) for k in keep if k in x} for x in e]
        for x in entries:
            if isinstance(x.get("author"), dict):  # the reviewer's profile uri goes, the name is pseudonymised
                x["author"] = {"name": x["author"].get("name")}
        body = {"feed": {"entry": entries}}
    return body


def label(x, *path):
    for k in path:
        x = (x or {}).get(k) if isinstance(x, dict) else None
    return x


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app-id", required=True, help="numeric App Store id")
    p.add_argument("--country", default="us", help="storefront country code (default us)")
    p.add_argument("--app-name", default=None, help="label used in the community field")
    M.add_common_args(p)
    args = p.parse_args(argv)
    cc = args.country.lower()
    community = f"App Store {cc}: {args.app_name or 'id' + args.app_id}"

    def gen(f: M.Fetcher, since, until, health):
        got_any = False
        for page in range(1, min(args.max_pages, 10) + 1):
            url = f"https://itunes.apple.com/{cc}/rss/customerreviews/page={page}/id={args.app_id}/sortby=mostrecent/json"
            body = f.get_json(url)
            health.data["pages"] += 1
            entries = label(body, "feed", "entry") or []
            if isinstance(entries, dict):
                entries = [entries]
            oldest = None
            for e in entries:
                if "im:rating" not in e:
                    continue  # the app's own metadata entry in some feed versions
                title = label(e, "title", "label") or ""
                content = label(e, "content", "label") or ""
                updated = label(e, "updated", "label")
                rating = label(e, "im:rating", "label")
                rec = M.make_record(
                    source="appstore", native_id=f"{args.app_id}:{label(e, 'id', 'label')}", community=community,
                    kind="review", url=f"https://apps.apple.com/{cc}/app/id{args.app_id}?see-all=reviews",
                    author=label(e, "author", "name", "label"), created=updated,
                    text=(title + "\n\n" + content).strip(), title=title or None,
                    rating=int(rating) if rating and str(rating).isdigit() else None,
                    score=int(label(e, "im:voteSum", "label") or 0), query=None,
                    method="rss:itunes-customerreviews", fetched_at=f.last_fetched_at)
                oldest = rec["date"] if oldest is None or (rec["date"] or "") < oldest else oldest
                yield rec
            if entries:
                got_any = True
            # An empty page ends the feed only after a page with entries: the
            # feed sometimes answers page 1 empty and page 2 full.
            if (not entries and got_any) or (oldest and oldest < since):
                break

    return M.run_collector(args, "appstore", community, gen, trim=trim, hint_empty=HINT)


if __name__ == "__main__":
    sys.exit(main())
