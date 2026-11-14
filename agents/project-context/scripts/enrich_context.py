#!/usr/bin/env python3
"""enrich_context.py: Pre-fill the business-context Q&A from a founder's site.

Pulls the homepage plus likely /about, /pricing, /product(s), /features pages and
writes two files into the project-context output dir:

  brand-debug/enrichment.json   raw per-page fetch results (lossless)
  brand-debug/enrichment-notes.md  readable markdown excerpts, page by page

The build-context skill reads these as DRAFT answers to confirm with the founder,
never as final truth. The script only fetches and reshapes; it does not invent.

Providers (capability `scrape`, see shared/tools.md at the repo root):
  firecrawl  Firecrawl API scrape of each candidate URL (needs FIRECRAWL_API_KEY)
  jina       Jina Reader (https://r.jina.ai/<url>), works without a key at a low
             rate; JINA_API_KEY raises it
  http       plain HTTP fetch with a browser user agent, text extracted from the
             HTML (no key, no JavaScript rendering)
  exa        the `exa` CLI for a site-scoped search (needs it on PATH + EXA_API_KEY);
             only used when asked for explicitly
  auto       firecrawl if its key is set and spend is confirmed, else jina, else
             http. A page that fails with one provider is retried with the next.

Spend gate: firecrawl and exa consume paid credits, and a JINA_API_KEY draws on
a token balance. They run only with --confirm-spend (or FOG_ALLOW_SPEND=1 in the
environment for scripted runs), passed after the founder agreed. Without it,
auto skips firecrawl and calls Jina keyless (the free default), and a pinned
--provider firecrawl or exa sends nothing and exits 4 with the estimate.

Only http and https URLs are opened (file://, ftp:// and other schemes are
refused, redirects included).

Usage:
    python enrich_context.py --url https://acme.example --out out/ [--provider auto]
    python enrich_context.py --url https://acme.example --out out/ --provider firecrawl --confirm-spend

Exit codes:
    0  enrichment written
    2  the requested provider is unusable (no key / no CLI) -> caller retries with
       --provider auto or skips pre-fill
    3  fetch error on every candidate (caller falls back to manual Q&A)
    4  spend gate closed: --provider firecrawl or exa without --confirm-spend or
       FOG_ALLOW_SPEND=1. Nothing was sent; rerun with --provider auto (free)
       or with --confirm-spend once the founder agreed.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CANDIDATE_PATHS = ["", "about", "pricing", "product", "products", "features", "how-it-works"]
FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
JINA_ENDPOINT = "https://r.jina.ai/"

# Characters of markdown kept per page (enough for a draft, small enough to read).
MAX_PAGE_CHARS = 6000

# Jina rejects a browser user agent sent from a non-browser client: API calls use a tool name.
TOOL_UA = "founders-agent-stack-enrich-context/1.1"
# Direct page fetches (http provider) use a browser user agent: some sites 403 unknown clients.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Jina answers 200 with this warning when the target page itself returned an error.
JINA_TARGET_ERROR_RE = re.compile(r"Target URL returned error [45]\d\d")

ALLOWED_SCHEMES = ("http", "https")


def _build_web_opener() -> urllib.request.OpenerDirector:
    """An opener with HTTP and HTTPS handlers only: no file://, ftp:// or data: handler,
    so neither a URL nor a redirect can read a local file or reach another scheme."""
    opener = urllib.request.OpenerDirector()
    for handler in (urllib.request.ProxyHandler(), urllib.request.UnknownHandler(),
                    urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
                    urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPRedirectHandler(),
                    urllib.request.HTTPErrorProcessor()):
        opener.add_handler(handler)
    return opener


_WEB_OPENER = _build_web_opener()


def _urlopen(req: urllib.request.Request, timeout: int):
    """urlopen restricted to http and https."""
    scheme = urllib.parse.urlsplit(req.full_url).scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"refused URL scheme {scheme or '(none)'}: only http and https are fetched")
    return _WEB_OPENER.open(req, timeout=timeout)


def spend_confirmed(flag: bool) -> bool:
    """True when the founder's agreement was passed on: --confirm-spend or FOG_ALLOW_SPEND=1."""
    return bool(flag) or os.environ.get("FOG_ALLOW_SPEND", "").strip() == "1"


def _candidate_urls(base: str) -> list[str]:
    parsed = urllib.parse.urlparse(base if "://" in base else f"https://{base}")
    root = f"{parsed.scheme}://{parsed.netloc}"
    urls = []
    for path in CANDIDATE_PATHS:
        u = root if path == "" else f"{root}/{path}"
        if u not in urls:
            urls.append(u)
    return urls


def _firecrawl_scrape(url: str, api_key: str) -> dict | None:
    body = json.dumps({
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "waitFor": 1200,
    }).encode("utf-8")
    req = urllib.request.Request(
        FIRECRAWL_ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with _urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"[firecrawl] {url}: {e}\n")
        return None


class PageMissing(Exception):
    """The candidate page does not exist (4xx/5xx reported by the provider): no retry."""


def _fetch_text(url: str, headers: dict, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers=headers)
    with _urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read(3_000_000).decode(charset, errors="replace")


def _jina_scrape(url: str, use_key: bool = False) -> str | None:
    headers = {"User-Agent": TOOL_UA}
    key = os.environ.get("JINA_API_KEY") if use_key else None
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        text = _fetch_text(JINA_ENDPOINT + url, headers, timeout=60)
    except Exception as e:
        sys.stderr.write(f"[jina] {url}: {e}\n")
        return None
    if JINA_TARGET_ERROR_RE.search(text[:1500]):
        raise PageMissing(url)
    return text


def _html_to_text(raw: str) -> str:
    """Readable text from HTML: title, meta description, headings kept as markdown."""
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    meta = re.search(r'(?is)<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', raw)
    body = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", raw)
    body = re.sub(r"(?is)<h([1-3])[^>]*>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + m.group(2) + "\n", body)
    body = re.sub(r"(?is)<(br|/p|/li|/div|/section)[^>]*>", "\n", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    lines = [re.sub(r"[ \t]+", " ", htmllib.unescape(l)).strip() for l in body.splitlines()]
    text = "\n".join(l for l in lines if l)
    head = []
    if title:
        head.append("Title: " + htmllib.unescape(re.sub(r"\s+", " ", title.group(1))).strip())
    if meta:
        head.append("Description: " + htmllib.unescape(meta.group(1)).strip())
    return "\n".join(head + ["", text]).strip()


def _http_scrape(url: str) -> str | None:
    try:
        raw = _fetch_text(url, {"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml"}, timeout=30)
    except Exception as e:
        sys.stderr.write(f"[http] {url}: {e}\n")
        return None
    return _html_to_text(raw)


def _chain_run(base: str, chain: list[str], fc_key: str | None,
               jina_key: bool = False) -> tuple[list[dict], list[str]]:
    """Fetch every candidate URL, trying each provider of the chain in order."""
    results, used = [], []
    for url in _candidate_urls(base):
        for provider in chain:
            md = ""
            if provider == "firecrawl":
                data = _firecrawl_scrape(url, fc_key or "")
                if data:
                    inner = data.get("data") if isinstance(data.get("data"), dict) else data
                    md = inner.get("markdown", "") or ""
            elif provider == "jina":
                try:
                    md = _jina_scrape(url, jina_key) or ""
                except PageMissing:
                    sys.stderr.write(f"[jina] {url}: page not found, skipped\n")
                    break
            else:
                md = _http_scrape(url) or ""
            if md.strip():
                results.append({"url": url, "provider": provider, "markdown": md[:MAX_PAGE_CHARS]})
                if provider not in used:
                    used.append(provider)
                break
    return results, used


def _exa_run(base: str) -> list[dict]:
    """Best-effort: use the `exa` CLI to search within the site's domain."""
    parsed = urllib.parse.urlparse(base if "://" in base else f"https://{base}")
    domain = parsed.netloc
    query = f"site:{domain} what it is, who it is for, pricing, features"
    try:
        proc = subprocess.run(
            ["exa", "search", query, "--num-results", "6", "--text"],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(f"[exa] unavailable: {e}\n")
        return []
    if proc.returncode != 0:
        sys.stderr.write(f"[exa] exit {proc.returncode}: {proc.stderr[:300]}\n")
        return []
    return [{"url": f"exa:site:{domain}", "markdown": proc.stdout[:8000]}]


def _write_notes(results: list[dict], out_dir: Path) -> None:
    lines = ["# Enrichment notes (draft, confirm before writing context)\n"]
    lines.append("These are raw excerpts pulled from the site. Treat every line as a\n"
                 "candidate answer to verify with the founder, not as fact.\n")
    for r in results:
        lines.append(f"\n## {r['url']}\n")
        lines.append(r["markdown"].strip())
        lines.append("\n")
    (out_dir / "enrichment-notes.md").write_text("\n".join(lines))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True, help="project-context output dir")
    p.add_argument("--provider", default="auto", choices=["auto", "firecrawl", "jina", "http", "exa"],
                   help="auto = firecrawl if FIRECRAWL_API_KEY and spend confirmed, else jina (keyless), else http")
    p.add_argument("--confirm-spend", action="store_true",
                   help="The founder agreed to paid credits: allow firecrawl, exa and a keyed Jina. "
                        "FOG_ALLOW_SPEND=1 in the environment does the same for scripted runs.")
    args = p.parse_args()

    if "://" in args.url and urllib.parse.urlsplit(args.url).scheme.lower() not in ALLOWED_SCHEMES:
        sys.stderr.write("enrich_context: --url must be an http or https address.\n")
        return 2

    out_dir = Path(args.out).expanduser().resolve()
    debug_dir = out_dir / "brand-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    fc_key = os.environ.get("FIRECRAWL_API_KEY")
    provider = args.provider

    if provider == "firecrawl" and not fc_key:
        sys.stderr.write("enrich_context: --provider firecrawl needs FIRECRAWL_API_KEY; "
                         "rerun with --provider auto (keyless Jina Reader, then plain HTTP).\n")
        return 2
    if provider == "exa" and not os.environ.get("EXA_API_KEY"):
        sys.stderr.write("enrich_context: --provider exa needs EXA_API_KEY and the exa CLI; "
                         "rerun with --provider auto.\n")
        return 2

    spend_ok = spend_confirmed(args.confirm_spend)
    if provider in ("firecrawl", "exa") and not spend_ok:
        cost = (f"up to {len(_candidate_urls(args.url))} Firecrawl scrapes (1 credit per page)"
                if provider == "firecrawl" else "1 Exa search with page text (billed by Exa per request)")
        sys.stderr.write(f"enrich_context: spend gate closed, nothing was sent. --provider {provider} "
                         f"would use {cost}. Ask the founder, then rerun with --confirm-spend "
                         "(or FOG_ALLOW_SPEND=1); or rerun with --provider auto (keyless Jina "
                         "Reader, then plain HTTP, no spend).\n")
        return 4

    if provider == "exa":
        results = _exa_run(args.url)
        used = ["exa"] if results else []
    else:
        if provider == "auto":
            chain = (["firecrawl"] if fc_key and spend_ok else []) + ["jina", "http"]
            if fc_key and not spend_ok:
                sys.stderr.write("enrich_context: FIRECRAWL_API_KEY is set but spend is not confirmed; "
                                 "skipping firecrawl (add --confirm-spend once the founder agreed).\n")
        else:
            chain = ["firecrawl", "jina", "http"][["firecrawl", "jina", "http"].index(provider):]
        sys.stderr.write(f"enrich_context: scrape chain = {' > '.join(chain)}\n")
        results, used = _chain_run(args.url, chain, fc_key, jina_key=spend_ok)

    if not results:
        sys.stderr.write("enrich_context: no pages fetched; fall back to manual Q&A.\n")
        return 3

    (debug_dir / "enrichment.json").write_text(json.dumps(
        {"url": args.url, "provider": ", ".join(used), "pages": results}, indent=2))
    _write_notes(results, debug_dir)

    sys.stderr.write(f"enrich_context: wrote {len(results)} page(s) via {', '.join(used)}\n")
    print(str(debug_dir / "enrichment-notes.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
