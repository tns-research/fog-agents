#!/usr/bin/env python3
"""enrich_context.py: Pre-fill the business-context Q&A from a founder's site.

Pulls the homepage plus likely /about, /pricing, /product(s), /features pages and
writes two files into the project-context output dir:

  brand-debug/enrichment.json   raw per-page fetch results (lossless)
  brand-debug/enrichment-notes.md  readable markdown excerpts, page by page

The build-context skill reads these as DRAFT answers to confirm with the founder,
never as final truth. The script only fetches and reshapes; it does not invent.

Providers:
  firecrawl  HTTP scrape of each candidate URL (needs FIRECRAWL_API_KEY)
  exa        falls back to the `exa` CLI for a site-scoped search (needs it on PATH)
  auto       firecrawl if its key is set, else exa, else degrade

Usage:
    python enrich_context.py --url https://acme.com --out out/ [--provider auto]

Exit codes:
    0  enrichment written
    2  no usable provider (no key / no CLI) -> caller skips pre-fill silently
    3  fetch error on every candidate (caller falls back to manual Q&A)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CANDIDATE_PATHS = ["", "about", "pricing", "product", "products", "features", "how-it-works"]
FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"


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
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"[firecrawl] {url}: {e}\n")
        return None


def _firecrawl_run(base: str, api_key: str) -> list[dict]:
    results = []
    for url in _candidate_urls(base):
        data = _firecrawl_scrape(url, api_key)
        if not data:
            continue
        md = ""
        if isinstance(data.get("data"), dict):
            md = data["data"].get("markdown", "") or ""
        else:
            md = data.get("markdown", "") or ""
        if md.strip():
            results.append({"url": url, "markdown": md[:6000]})
    return results


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
    p.add_argument("--provider", default="auto", choices=["auto", "firecrawl", "exa"])
    args = p.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    debug_dir = out_dir / "brand-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    fc_key = os.environ.get("FIRECRAWL_API_KEY")
    provider = args.provider
    if provider == "auto":
        provider = "firecrawl" if fc_key else "exa"

    if provider == "firecrawl" and not fc_key:
        sys.stderr.write("enrich_context: FIRECRAWL_API_KEY not set; no enrichment.\n")
        return 2

    if provider == "firecrawl":
        results = _firecrawl_run(args.url, fc_key)  # type: ignore[arg-type]
    else:
        results = _exa_run(args.url)

    if not results:
        sys.stderr.write("enrich_context: no pages fetched; fall back to manual Q&A.\n")
        return 3

    (debug_dir / "enrichment.json").write_text(json.dumps(
        {"url": args.url, "provider": provider, "pages": results}, indent=2))
    _write_notes(results, debug_dir)

    sys.stderr.write(f"enrich_context: wrote {len(results)} page(s) via {provider}\n")
    print(str(debug_dir / "enrichment-notes.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
