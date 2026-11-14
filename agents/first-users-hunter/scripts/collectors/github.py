#!/usr/bin/env python3
"""
collectors/github.py: GitHub issues, pull requests and discussions.

Signals: REST search/issues per configured query (works without a key, 10
searches a minute), restricted to items created after the oldest date an
eligible signal type accepts. Discussions: GraphQL search, which GitHub only
serves with a token (GITHUB_TOKEN or GH_TOKEN, a free personal token with no
scope); without one, discussions are skipped and the health line says so.
Activity: public events of the user (404: dead handle). Issues, pull requests,
comments and discussions count as posts, pushes at a reduced weight.

Config block (config.json > sources.github):
  {"enabled": true,
   "queries": [{"id": "gh_alt", "q": "\\"alternative to\\" waitlist type:issue"}],
   "discussions": [{"id": "gh_disc", "q": "first users"}]}

Examples:
  python3 scripts/collectors/github.py --config <project>/first-users-hunter/config.json
  python3 scripts/collectors/github.py --activity some-user --today 2026-10-12

Health tested 2026-10-12 without a key: search/issues 200, users/<u>/events/public 200, unknown user 404.
Exit codes: 0 ok, 1 the source failed, 2 usage error.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.common import (activity, activity_since, day_of,  # noqa: E402
                               run_cli, signal, since_day)

NAME = "github"
ACTIVITY_NETWORKS = ["github"]
API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

EXAMPLE_CONFIG = {
    "enabled": True,
    "queries": [{"id": "gh_beta_testers", "q": "\"looking for beta testers\" type:issue"}],
}

DISCUSSION_QUERY = (
    "query($q:String!){search(query:$q,type:DISCUSSION,first:30){nodes{... on Discussion"
    "{id url title body createdAt author{login} repository{nameWithOwner}}}}}"
)

EVENT_KIND = {
    "IssuesEvent": "issue",
    "IssueCommentEvent": "comment",
    "PullRequestEvent": "pull_request",
    "PullRequestReviewCommentEvent": "comment",
    "DiscussionEvent": "discussion",
    "DiscussionCommentEvent": "comment",
    "PushEvent": "push",
    "ReleaseEvent": "post",
}


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _headers() -> Dict[str, str]:
    h = dict(HEADERS)
    if _token():
        h["Authorization"] = f"Bearer {_token()}"
    return h


def collect_signals(cfg: Dict[str, Any], fetch, today, criteria) -> List[Dict[str, Any]]:
    since = since_day(today, criteria).isoformat()
    out: List[Dict[str, Any]] = []
    for q in cfg.get("queries") or []:
        data = fetch.json("GET", f"{API}/search/issues", headers=_headers(),
                          params={"q": f"{q['q']} created:>={since}", "sort": "created",
                                  "order": "desc", "per_page": int(q.get("per_page", 30))})
        for it in data.get("items") or []:
            user = (it.get("user") or {}).get("login") or ""
            if not user or (it.get("user") or {}).get("type") == "Bot":
                continue
            repo = (it.get("repository_url") or "").replace(f"{API}/repos/", "")
            title = it.get("title") or ""
            out.append(signal(
                NAME, "github", str(it.get("id")), user, it.get("html_url", ""), day_of(it.get("created_at")),
                "api", f"{title}\n\n{it.get('body') or ''}".strip(), criteria,
                author_url=f"https://github.com/{user}", thread_url=it.get("html_url", ""),
                title=title, community=repo, query_id=q.get("id", ""), datetime=it.get("created_at", ""),
                metrics={"comments": it.get("comments", 0)},
            ))
    disc = cfg.get("discussions") or []
    if disc and not _token() and fetch.mode == "live":
        cfg.setdefault("_notes", []).append("discussions skipped: GraphQL search needs GITHUB_TOKEN (free, no scope)")
        disc = []
    for q in disc:
        data = fetch.json("POST", f"{API}/graphql", headers=_headers(),
                          json_body={"query": DISCUSSION_QUERY, "variables": {"q": f"{q['q']} created:>={since}"}})
        for n in ((data.get("data") or {}).get("search") or {}).get("nodes") or []:
            user = ((n.get("author") or {}).get("login")) or ""
            if not user:
                continue
            title = n.get("title") or ""
            out.append(signal(
                NAME, "github", n.get("id", ""), user, n.get("url", ""), day_of(n.get("createdAt")),
                "api", f"{title}\n\n{n.get('body') or ''}".strip(), criteria,
                author_url=f"https://github.com/{user}", thread_url=n.get("url", ""), title=title,
                community=(n.get("repository") or {}).get("nameWithOwner", ""), query_id=q.get("id", ""),
                datetime=n.get("createdAt", ""),
            ))
    return out


def collect_activity(handle: str, fetch, today, criteria, cfg=None) -> List[Dict[str, Any]]:
    since = activity_since(today, criteria).isoformat()
    events = fetch.json("GET", f"{API}/users/{handle}/events/public", headers=_headers(),
                        params={"per_page": 100})
    out = []
    for ev in events or []:
        day = day_of(ev.get("created_at"))
        if not day or day < since:
            continue
        p = ev.get("payload") or {}
        kind = EVENT_KIND.get(ev.get("type", ""), "other")
        if ev.get("type") == "IssuesEvent" and p.get("action") != "opened":
            kind = "other"
        if ev.get("type") == "PullRequestEvent" and p.get("action") != "opened":
            kind = "other"
        url = ((p.get("comment") or {}).get("html_url") or (p.get("issue") or {}).get("html_url")
               or (p.get("pull_request") or {}).get("html_url") or (p.get("discussion") or {}).get("html_url")
               or f"https://github.com/{(ev.get('repo') or {}).get('name', '')}")
        out.append(activity(NAME, "github", handle, f"gh-event:{ev.get('id')}", url, day, kind))
    return out


if __name__ == "__main__":
    sys.exit(run_cli(sys.modules[__name__], sys.argv[1:], __doc__))
