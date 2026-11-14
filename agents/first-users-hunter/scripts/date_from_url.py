#!/usr/bin/env python3
"""
date_from_url.py

Reads the creation date of a public post from its URL, without fetching it.
Standard library only, Python 3.9+.

    python3 date_from_url.py URL [URL ...] [--json]

LinkedIn: activity, ugcPost and share ids (and urn:li:activity:<id>) hold a
Unix time in milliseconds in their first 41 bits: (id >> 22) / 1000.
X (Twitter): status ids are snowflakes: ((id >> 22) + 1288834974657) / 1000.
The script also prints the author the URL names (LinkedIn public slug, X
handle), which is how a post where the person is only tagged is told apart
from their own post.

Other sources carry their date in their API (HN created_at_i, GitHub
created_at, Reddit created_utc): the collectors read it there. A URL with no
post id prints "no post id" and makes the exit code 1.

Exit codes: 0 every URL dated, 1 at least one URL without a post id, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuh_lib import post_id_datetime, url_owner  # noqa: E402


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--json", action="store_true", help="One JSON object per URL")
    a = ap.parse_args(argv)
    missing = 0
    for url in a.urls:
        dt = post_id_datetime(url)
        owner = url_owner(url)
        rec = {"url": url, "datetime": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
               "date": dt.date().isoformat() if dt else None,
               "network": owner[0] if owner else None, "owner": owner[1] if owner else None}
        missing += dt is None
        if a.json:
            print(json.dumps(rec))
        else:
            who = f"  {rec['network']}:{rec['owner']}" if owner else ""
            print(f"{rec['datetime'] or 'no post id'}{who}  {url}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
