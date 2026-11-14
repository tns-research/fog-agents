#!/usr/bin/env python3
"""
cache_page.py

Keeps a local copy of every page read for a prospect dossier, so each fact's
excerpt can be checked against the page it came from (verify_dossiers.py).
Standard library only, Python 3.9+.

Files: <cache>/<hash>.txt (text the checks read) and, when fetched,
<cache>/<hash>.html (raw page). <hash> = first 16 hex chars of the sha256 of
the URL without its #fragment. <cache>/index.json maps hashes to URLs.

Usage:
    python3 cache_page.py --cache <run>/cache URL [URL ...]          # fetch with urllib
    python3 cache_page.py --cache <run>/cache --url URL --from-file page.txt
                                     # store text already fetched by another
                                     # provider (host web fetch, a scrape API,
                                     # a page the founder pasted); .html files
                                     # are converted to text
    python3 cache_page.py --hash URL                                  # print the hash only
    python3 cache_page.py --cache <run>/cache --check URL             # exit 0 when cached

Rules:
  - LinkedIn profile and company pages (linkedin.com/in/, /company/) are never
    fetched: they sit behind a login wall and their terms forbid scraping.
    Public post URLs (linkedin.com/posts/...) are fine.
  - Only http and https URLs are fetched (file://, ftp:// and the rest are
    refused), redirects included. Hosts that resolve to a private, loopback or
    link-local address are refused too, since the URLs come from web results;
    --allow-private-hosts lifts that check for a local test server.
  - A page already cached is not fetched again unless --refresh is given.
  - No JavaScript rendering: a page that comes back empty needs another
    provider of the scrape capability, then --from-file.

Exit codes: 0 every URL cached, 1 at least one URL failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (InputError, cache_paths, canonical_url, html_to_text,  # noqa: E402
                          is_linkedin_profile, load_json, url_hash, write_json)

UA = "Mozilla/5.0 (compatible; fog-agents-cold-outreach/2.0; +https://example.invalid/bot)"
MAX_BYTES = 3_000_000


def record(cache: str, url: str, source: str, chars: int) -> None:
    index_path = os.path.join(cache, "index.json")
    index = load_json(index_path) if os.path.isfile(index_path) else {}
    index[url_hash(url)] = {
        "url": canonical_url(url),
        "source": source,
        "cached_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chars": chars,
    }
    write_json(index_path, dict(sorted(index.items())))


def store(cache: str, url: str, text: str, raw_html: str = "", source: str = "fetch") -> int:
    os.makedirs(cache, exist_ok=True)
    txt, htm = cache_paths(cache, url)
    if raw_html:
        with open(htm, "w", encoding="utf-8") as f:
            f.write(raw_html)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(f"URL: {canonical_url(url)}\n\n{text}")
    record(cache, url, source, len(text))
    return len(text)



# --- Safe fetching ------------------------------------------------------------
# URLs reach this script from web results and model output, so from third
# parties. Only http and https are fetched; unless --allow-private-hosts is
# given, a host that resolves to a private, loopback or link-local address is
# refused, and every redirect target goes through the same check.

_ALLOW_PRIVATE = False


def _host_is_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return False  # unresolvable: the fetch fails on its own
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:
            return True
    return False


def check_fetch_url(url: str) -> None:
    """Raise ValueError unless url is http(s) to a public host (see _ALLOW_PRIVATE)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError(f"refused {url[:120]!r}: only http and https URLs are fetched")
    if not _ALLOW_PRIVATE and _host_is_private(parts.hostname):
        raise ValueError(f"refused {url[:120]!r}: {parts.hostname} resolves to a private, loopback or link-local address")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        check_fetch_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)

def fetch(url: str, timeout: int) -> str:
    check_fetch_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.5"})
    with _OPENER.open(req, timeout=timeout) as resp:
        data = resp.read(MAX_BYTES)
        charset = resp.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="URLs to fetch")
    ap.add_argument("--cache", help="Cache folder, usually <run>/cache")
    ap.add_argument("--url", help="URL the --from-file text belongs to")
    ap.add_argument("--from-file", help="Text or HTML file already fetched by another provider")
    ap.add_argument("--hash", metavar="URL", help="Print the cache hash of URL and exit")
    ap.add_argument("--check", metavar="URL", help="Exit 0 when URL is cached, 1 otherwise")
    ap.add_argument("--refresh", action="store_true", help="Fetch again even when cached")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--allow-private-hosts", action="store_true",
                    help="Also fetch hosts on private, loopback or link-local addresses (local test server)")
    a = ap.parse_args(argv)
    global _ALLOW_PRIVATE
    _ALLOW_PRIVATE = a.allow_private_hosts

    if a.hash:
        print(url_hash(a.hash))
        return 0
    if not a.cache:
        print("error: --cache is required", file=sys.stderr)
        return 2
    if a.check:
        txt, htm = cache_paths(a.cache, a.check)
        ok = os.path.isfile(txt) or os.path.isfile(htm)
        print(f"{'cached' if ok else 'missing'}: {a.check} -> {url_hash(a.check)}")
        return 0 if ok else 1

    try:
        if a.from_file:
            if not a.url:
                print("error: --from-file needs --url", file=sys.stderr)
                return 2
            with open(a.from_file, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            is_html = a.from_file.lower().endswith((".html", ".htm")) or raw.lstrip().lower().startswith(("<!doctype", "<html"))
            text = html_to_text(raw) if is_html else raw
            n = store(a.cache, a.url, text, raw if is_html else "", source=f"file:{os.path.basename(a.from_file)}")
            print(f"cached {a.url} -> {url_hash(a.url)}.txt ({n} chars, from file)")
            return 0
    except (OSError, InputError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not a.urls:
        print("error: give at least one URL, or --url with --from-file", file=sys.stderr)
        return 2

    failed = 0
    for url in a.urls:
        if is_linkedin_profile(url):
            print(f"refused {url}: LinkedIn profile and company pages are not fetched (login wall, terms). "
                  "Use public post URLs, the company site, or text the founder pastes (--from-file).", file=sys.stderr)
            failed += 1
            continue
        txt, htm = cache_paths(a.cache, url)
        if not a.refresh and (os.path.isfile(txt) or os.path.isfile(htm)):
            print(f"already cached {url} -> {url_hash(url)}")
            continue
        try:
            raw = fetch(url, a.timeout)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"failed {url}: {e}. Switch the scrape provider and store its text with --from-file.", file=sys.stderr)
            failed += 1
            continue
        text = html_to_text(raw)
        if len(text.strip()) < 200:
            print(f"warning {url}: only {len(text.strip())} chars of text (JavaScript page or wall?)", file=sys.stderr)
        n = store(a.cache, url, text, raw, source="fetch:urllib")
        print(f"cached {url} -> {url_hash(url)}.txt ({n} chars)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
