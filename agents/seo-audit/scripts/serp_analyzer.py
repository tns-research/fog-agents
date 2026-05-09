#!/usr/bin/env python3
"""
serp_analyzer.py

Companion script for the seo-audit agent. For each target query:
  1. Fetch SERP via SERPER.dev (free tier, 2500 queries/month).
  2. Capture organic top-10, AI Overview citations, PAA, featured snippet.
  3. Crawl each top-10 URL via firecrawl to extract on-page signals.
  4. Output a per-query JSON record consumed by analyzing-serp-competition.

Usage:
    SERPER_API_KEY=... FIRECRAWL_API_KEY=... \
        python serp_analyzer.py \
            --queries "best invoicing freelancers" "freelance invoice template" \
            --country US --language en \
            --out /tmp/serp-analysis.json

Falls back to firecrawl SERP scraping if SERPER is unavailable.
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Optional
from urllib.parse import quote_plus

import requests

SERPER_ENDPOINT = "https://google.serper.dev/search"
FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"

SCHEMA_TYPES = [
    "Article", "FAQPage", "HowTo", "Product", "BreadcrumbList",
    "Organization", "Person", "Review", "AggregateRating", "VideoObject",
]


def fetch_serp_via_serper(query: str, country: str, language: str, api_key: str) -> Optional[dict[str, Any]]:
    payload = {"q": query, "gl": country.lower(), "hl": language, "num": 10}
    try:
        r = requests.post(
            SERPER_ENDPOINT,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"[warn] SERPER fetch failed for '{query}': {e}", file=sys.stderr)
        return None


def fetch_serp_via_firecrawl(query: str, country: str, language: str, api_key: str) -> Optional[dict[str, Any]]:
    """Fallback when SERPER is unavailable. Less reliable AI Overview parsing."""
    serp_url = f"https://www.google.com/search?q={quote_plus(query)}&hl={language}&gl={country.lower()}"
    try:
        r = requests.post(
            FIRECRAWL_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": serp_url, "formats": ["markdown"], "onlyMainContent": True},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        return {"_fallback": True, "markdown": data.get("data", {}).get("markdown", "")}
    except requests.RequestException as e:
        print(f"[warn] firecrawl SERP fallback failed for '{query}': {e}", file=sys.stderr)
        return None


def crawl_url(url: str, api_key: str) -> Optional[dict[str, Any]]:
    try:
        r = requests.post(
            FIRECRAWL_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown", "html"], "onlyMainContent": True},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("data", {})
    except requests.RequestException as e:
        print(f"[warn] firecrawl scrape failed for '{url}': {e}", file=sys.stderr)
        return None


def extract_page_signals(html: str, markdown: str) -> dict[str, Any]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.IGNORECASE | re.DOTALL)
    meta_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
        html or "",
        re.IGNORECASE,
    )
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.IGNORECASE | re.DOTALL)
    h2_matches = re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.IGNORECASE | re.DOTALL)
    h3_matches = re.findall(r"<h3[^>]*>(.*?)</h3>", html or "", re.IGNORECASE | re.DOTALL)

    schema_present = []
    for typ in SCHEMA_TYPES:
        if re.search(rf'"@type"\s*:\s*"{typ}"', html or ""):
            schema_present.append(typ)

    author_signal = bool(
        re.search(r'rel=["\']author["\']', html or "", re.IGNORECASE)
        or re.search(r"author", html or "", re.IGNORECASE)
    )

    word_count = len((markdown or "").split())

    def clean(s: Optional[str]) -> str:
        if not s:
            return ""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

    return {
        "title": clean(title_match.group(1)) if title_match else None,
        "meta": clean(meta_match.group(1)) if meta_match else None,
        "meta_length": len(clean(meta_match.group(1))) if meta_match else 0,
        "h1": clean(h1_match.group(1)) if h1_match else None,
        "h2_outline": [clean(h) for h in h2_matches][:20],
        "h3_outline": [clean(h) for h in h3_matches][:30],
        "word_count": word_count,
        "schema_types": schema_present,
        "author_signal": author_signal,
    }


def analyze_query(query: str, country: str, language: str, serper_key: Optional[str], firecrawl_key: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "query": query,
        "country": country,
        "language": language,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ai_overview": {"present": False, "text": None, "cited_sources": []},
        "features": {"paa": [], "featured_snippet": None},
        "top_10": [],
        "_warnings": [],
    }

    serp = None
    if serper_key:
        serp = fetch_serp_via_serper(query, country, language, serper_key)

    if serp and not serp.get("_fallback"):
        ai_ov = serp.get("aiOverview") or {}
        record["ai_overview"] = {
            "present": bool(ai_ov),
            "text": ai_ov.get("snippet") if ai_ov else None,
            "cited_sources": [s.get("link") for s in ai_ov.get("references", []) if s.get("link")],
        }
        record["features"]["paa"] = [q.get("question") for q in serp.get("peopleAlsoAsk", [])][:6]
        ans = serp.get("answerBox")
        if ans:
            record["features"]["featured_snippet"] = {
                "url": ans.get("link"),
                "text": ans.get("answer") or ans.get("snippet"),
            }
        organic = serp.get("organic", [])[:10]
        for i, item in enumerate(organic, start=1):
            url = item.get("link")
            if not url:
                continue
            crawl = crawl_url(url, firecrawl_key) or {}
            signals = extract_page_signals(crawl.get("html", ""), crawl.get("markdown", ""))
            record["top_10"].append({
                "position": i,
                "url": url,
                "serp_title": item.get("title"),
                "serp_snippet": item.get("snippet"),
                **signals,
            })
    else:
        record["_warnings"].append("SERPER unavailable; using firecrawl SERP fallback (AI Overview unreliable).")
        fb = fetch_serp_via_firecrawl(query, country, language, firecrawl_key)
        if fb:
            record["_warnings"].append("Fallback SERP captured; manual review of AI Overview required.")
            record["features"]["raw_markdown"] = fb.get("markdown", "")[:5000]

    return record


def main() -> int:
    ap = argparse.ArgumentParser(description="SERP + page analyzer for seo-audit")
    ap.add_argument("--queries", nargs="+", required=True, help="Target queries")
    ap.add_argument("--country", default="us", help="ISO country code (lowercase)")
    ap.add_argument("--language", default="en", help="hl language code")
    ap.add_argument("--out", required=True, help="Output JSON path")
    args = ap.parse_args()

    serper_key = os.environ.get("SERPER_API_KEY")
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")

    if not firecrawl_key:
        print("[error] FIRECRAWL_API_KEY not set", file=sys.stderr)
        return 2
    if not serper_key:
        print("[warn] SERPER_API_KEY not set; AI Overview audit degraded.", file=sys.stderr)

    results = []
    for q in args.queries:
        print(f"[info] analyzing: {q}", file=sys.stderr)
        results.append(analyze_query(q, args.country, args.language, serper_key, firecrawl_key))
        time.sleep(1)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"version": "1.0", "queries_analyzed": len(results), "data": results}, f, indent=2)

    print(f"[info] wrote {len(results)} records to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
