#!/usr/bin/env python3
"""
serp_analyzer.py

Companion script for the seo-audit agent. For each target query:
  1. Fetch the SERP (capability `serp`): Serper by default, SerpApi as an
     alternative, a Firecrawl scrape of the Google page as a last API resort,
     or a list of URLs the agent got from built-in web search or from the
     founder (--organic-file).
  2. Capture organic top-10, AI Overview citations, PAA, featured snippet when
     the provider returns them. Without a SERP API these fields are marked
     "unverified", never guessed.
  3. Fetch each top-10 URL (capability `scrape`) to extract on-page signals:
     Firecrawl when FIRECRAWL_API_KEY is set, else Jina Reader (keyless),
     else a plain HTTP fetch with a browser user agent. Signals are read from
     the HTML with the parser of crawl.py (seo_lib.parse_html), so the word
     count and the schema types mean the same thing for every provider.
     Headings come as an outline in document order (`outline`: each H2 with
     its H3s; `h2_outline` and `h3_outline` are the flat lists), and
     `outbound_links` lists the sources the page cites on other sites; the
     plan of write_article.py reads both.
  4. Output a per-query JSON record consumed by analyzing-serp-competition.

Every API is optional. Standard library only.

Spend gate: Serper, SerpApi and Firecrawl bill per call, and a JINA_API_KEY
draws on a token balance. When the resolved provider chains hold a paid
provider, the script sends nothing without --confirm-spend (or the environment
variable FOG_ALLOW_SPEND=1 for scripted runs): it prints the planned calls and
exits 1, like geo_panel.py. The agent passes the flag only after the founder
agreed at the Step 0 spend gate. Without the flag, Jina Reader runs keyless.

Only http and https URLs are fetched (file://, ftp:// and other schemes are
refused, redirects included), whatever --organic-file or a SERP returns.

Usage:
    python3 serp_analyzer.py \
        --queries "best invoicing freelancers" "freelance invoice template" \
        --country us --language en \
        --out /tmp/serp-analysis.json

    # Paid providers (Serper, SerpApi, Firecrawl), after the founder agreed:
    python3 serp_analyzer.py --queries "best invoicing freelancers" \
        --out /tmp/serp-analysis.json --confirm-spend

    # No SERP API: pass the result URLs found with built-in search
    python3 serp_analyzer.py --queries "best invoicing freelancers" \
        --organic-file /tmp/organic.json --out /tmp/serp-analysis.json

--organic-file is a JSON object mapping each query to its ordered list of
result URLs: {"best invoicing freelancers": ["https://a.com/x", "https://b.com/y"]}.

--country is the SERP locale (Google "gl"): a two-letter ISO 3166-1 code such
as us or fr, any case. A SERP is always fetched for one country, so "all",
"any", "global", "none", "*" or an empty value are treated as "no country
chosen" and fall back to --fallback-country (default "us") with a warning. The
agent resolves the real value first (config serp_country, then a real GSC
country code, then project-context geography.country, then us).

Exit codes: 0 written (possibly degraded, see _warnings and "providers"),
1 spend gate closed (a paid provider would run without --confirm-spend; nothing
sent, nothing written), 2 bad input (unreadable --organic-file, forced provider
without its key).
"""

import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_lib  # noqa: E402
from seo_lib import parse_html  # noqa: E402

SERPER_ENDPOINT = "https://google.serper.dev/search"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"
JINA_ENDPOINT = "https://r.jina.ai/"

# User agent for API calls (Serper, SerpApi, Firecrawl, Jina). Jina rejects a
# browser user agent sent from a non-browser client, so APIs get a plain tool name.
TOOL_UA = "founders-agent-stack-serp-analyzer/1.1"

# A desktop browser user agent for direct page fetches (http provider): some
# sites return 403 to unknown clients.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Seconds before an HTTP call is abandoned. API calls get more room than page fetches.
API_TIMEOUT = 45
PAGE_TIMEOUT = 30

# Pages larger than this (bytes) are truncated before parsing.
MAX_PAGE_BYTES = 3_000_000

# Caps of the heading outline of one result page (H2 and H3 in document order).
OUTLINE_MAX_H2 = 40
OUTLINE_MAX_H3_PER_H2 = 15
OUTLINE_MAX_H3 = 120
# Outbound links kept per result page (sources a competitor cites).
MAX_OUTBOUND = 40

# Values meaning "no specific country" (a GSC-style "all"). SERP providers and
# Google need one real country, so these resolve to the fallback country.
NO_COUNTRY_VALUES = {"", "all", "any", "global", "none", "*", "ww", "worldwide"}
DEFAULT_SERP_COUNTRY = "us"
# Language codes often passed as a country; Google gl needs a country (gl=en is rejected).
LANGUAGE_NOT_COUNTRY = {"en": "us", "ja": "jp", "zh": "cn", "ko": "kr", "sv": "se", "da": "dk", "cs": "cz", "el": "gr", "he": "il", "uk": "ua", "vi": "vn", "hi": "in", "fa": "ir", "et": "ee", "sl": "si", "nb": "no"}

SERP_PROVIDERS = ["auto", "serper", "serpapi", "firecrawl", "file", "none"]
SCRAPE_PROVIDERS = ["auto", "firecrawl", "jina", "http"]
PAID_PROVIDERS = {"serper", "serpapi", "firecrawl"}
ALLOWED_SCHEMES = ("http", "https")


def spend_confirmed(flag: bool) -> bool:
    """True when the founder's agreement was passed on: --confirm-spend or FOG_ALLOW_SPEND=1."""
    return bool(flag) or os.environ.get("FOG_ALLOW_SPEND", "").strip() == "1"


# Jina Reader gets the key only when spend is confirmed (main sets it).
_USE_JINA_KEY = False


def _build_web_opener() -> urllib.request.OpenerDirector:
    """HTTP and HTTPS handlers only: no file://, ftp:// or data: handler, redirects included."""
    opener = urllib.request.OpenerDirector()
    for handler in (urllib.request.ProxyHandler(), urllib.request.UnknownHandler(),
                    urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
                    urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPRedirectHandler(),
                    urllib.request.HTTPErrorProcessor()):
        opener.add_handler(handler)
    return opener


_WEB_OPENER = _build_web_opener()

def warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def resolve_serp_country(value: Optional[str], fallback: str = DEFAULT_SERP_COUNTRY) -> str:
    """Return a lowercase two-letter country code usable as Google's gl param.

    "all"-like or empty values fall back to `fallback`; anything that is not two
    ASCII letters also falls back, with a warning, instead of reaching the API.
    """
    raw = (value or "").strip().lower()
    fb = (fallback or DEFAULT_SERP_COUNTRY).strip().lower()
    if not re.fullmatch(r"[a-z]{2}", fb):
        fb = DEFAULT_SERP_COUNTRY
    if raw in NO_COUNTRY_VALUES:
        if raw:
            warn(f"--country '{value}' is not a single country; SERPs use '{fb}'.")
        return fb
    if not re.fullmatch(r"[a-z]{2}", raw):
        warn(f"--country '{value}' is not a two-letter ISO code; SERPs use '{fb}'.")
        return fb
    if raw in LANGUAGE_NOT_COUNTRY:
        mapped = LANGUAGE_NOT_COUNTRY[raw]
        warn(f"--country '{value}' is a language code, not a country (gl={raw} is rejected); SERPs use '{mapped}'.")
        return mapped
    return raw


# --- HTTP helpers (stdlib only) ---------------------------------------------

def http_request(url: str, *, data: Optional[dict] = None, headers: Optional[dict] = None,
                 timeout: int = API_TIMEOUT) -> str:
    """GET (or POST JSON when data is given) and return the body as text. Raises on failure."""
    hdrs = {"User-Agent": TOOL_UA}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    if urllib.parse.urlsplit(url).scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(f"refused {url[:120]!r}: only http and https URLs are fetched")
    req = urllib.request.Request(url, data=body, headers=hdrs)
    with _WEB_OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read(MAX_PAGE_BYTES)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def describe_error(e: Exception) -> str:
    """Short error text. For HTTP errors, append the start of the API body (for example "Not enough credits")."""
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read(300).decode("utf-8", errors="replace").strip()
        except OSError:
            body = ""
        return f"HTTP {e.code} {body}".strip()
    return f"{type(e).__name__}: {e}"


def http_json(url: str, **kwargs: Any) -> Dict[str, Any]:
    return json.loads(http_request(url, **kwargs))


# --- SERP providers -----------------------------------------------------------

def empty_serp() -> Dict[str, Any]:
    """Provider-independent SERP shape. None means "not returned by this provider"."""
    return {"organic": [], "ai_overview": None, "paa": None, "featured_snippet": None, "raw_markdown": None}


def serp_via_serper(query: str, country: str, language: str, api_key: str) -> Optional[Dict[str, Any]]:
    try:
        data = http_json(SERPER_ENDPOINT, data={"q": query, "gl": country, "hl": language, "num": 10},
                         headers={"X-API-KEY": api_key})
    except (urllib.error.URLError, OSError, ValueError) as e:
        warn(f"Serper fetch failed for '{query}': {describe_error(e)}")
        return None
    out = empty_serp()
    ai_ov = data.get("aiOverview") or {}
    out["ai_overview"] = {
        "present": bool(ai_ov),
        "text": ai_ov.get("snippet") if ai_ov else None,
        "cited_sources": [s.get("link") for s in ai_ov.get("references", []) if s.get("link")],
    }
    out["paa"] = [q.get("question") for q in data.get("peopleAlsoAsk", []) if q.get("question")][:6]
    ans = data.get("answerBox")
    if ans:
        out["featured_snippet"] = {"url": ans.get("link"), "text": ans.get("answer") or ans.get("snippet")}
    out["organic"] = [
        {"url": o.get("link"), "title": o.get("title"), "snippet": o.get("snippet")}
        for o in data.get("organic", []) if o.get("link")
    ][:10]
    return out


def serp_via_serpapi(query: str, country: str, language: str, api_key: str) -> Optional[Dict[str, Any]]:
    params = urllib.parse.urlencode({
        "engine": "google", "q": query, "gl": country, "hl": language, "num": 10, "api_key": api_key,
    })
    try:
        data = http_json(f"{SERPAPI_ENDPOINT}?{params}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        # The message can echo the URL, which holds the key: print the type only.
        warn(f"SerpApi fetch failed for '{query}': {describe_error(e) if isinstance(e, urllib.error.HTTPError) else type(e).__name__}")
        return None
    out = empty_serp()
    ai_ov = data.get("ai_overview") or {}
    text_blocks = ai_ov.get("text_blocks") or []
    out["ai_overview"] = {
        "present": bool(ai_ov),
        "text": " ".join(b.get("snippet", "") for b in text_blocks if isinstance(b, dict)).strip() or None,
        "cited_sources": [r.get("link") for r in ai_ov.get("references", []) if r.get("link")],
    }
    out["paa"] = [q.get("question") for q in data.get("related_questions", []) if q.get("question")][:6]
    ans = data.get("answer_box")
    if ans:
        out["featured_snippet"] = {"url": ans.get("link"), "text": ans.get("answer") or ans.get("snippet")}
    out["organic"] = [
        {"url": o.get("link"), "title": o.get("title"), "snippet": o.get("snippet")}
        for o in data.get("organic_results", []) if o.get("link")
    ][:10]
    return out


def serp_via_firecrawl(query: str, country: str, language: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Scrapes the Google results page. Organic order is not parsed, AI Overview is unreliable."""
    serp_url = (f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
                f"&hl={language}&gl={country}")
    try:
        data = http_json(FIRECRAWL_ENDPOINT,
                         data={"url": serp_url, "formats": ["markdown"], "onlyMainContent": True},
                         headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
    except (urllib.error.URLError, OSError, ValueError) as e:
        warn(f"Firecrawl SERP scrape failed for '{query}': {describe_error(e)}")
        return None
    out = empty_serp()
    out["raw_markdown"] = (data.get("data", {}) or {}).get("markdown", "")[:5000]
    return out


def serp_via_file(query: str, organic_map: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    urls = organic_map.get(query)
    if not urls:
        return None
    out = empty_serp()
    out["organic"] = [{"url": u, "title": None, "snippet": None} for u in urls if isinstance(u, str)][:10]
    return out


# --- scrape providers ---------------------------------------------------------

def html_to_text(html: str) -> str:
    """Rough visible text for word counts: drops script, style and tags."""
    text = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def scrape_firecrawl(url: str, api_key: str) -> Dict[str, Any]:
    data = http_json(FIRECRAWL_ENDPOINT,
                     data={"url": url, "formats": ["markdown", "rawHtml"], "onlyMainContent": True},
                     headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
    d = data.get("data", {}) or {}
    meta = d.get("metadata", {}) or {}
    return {"html": d.get("rawHtml") or d.get("html") or "", "markdown": d.get("markdown") or "",
            "meta_title": meta.get("title"), "meta_description": meta.get("description")}


def scrape_jina(url: str) -> Dict[str, Any]:
    headers = {"X-Return-Format": "html"}
    jina_key = os.environ.get("JINA_API_KEY") if _USE_JINA_KEY else None
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"
    html = http_request(JINA_ENDPOINT + url, headers=headers, timeout=PAGE_TIMEOUT + 30)
    return {"html": html, "markdown": html_to_text(html)}


def scrape_http(url: str) -> Dict[str, Any]:
    html = http_request(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml",
                                      "Accept-Language": "en;q=0.9,*;q=0.5"}, timeout=PAGE_TIMEOUT)
    return {"html": html, "markdown": html_to_text(html)}


def scrape_chain(requested: str, firecrawl_key: Optional[str]) -> List[str]:
    """Providers to try in order. A failing provider drops to the next tier."""
    if requested == "auto":
        chain = (["firecrawl"] if firecrawl_key else []) + ["jina", "http"]
    else:
        tiers = ["firecrawl", "jina", "http"]
        chain = tiers[tiers.index(requested):]
    return chain


def crawl_url(url: str, chain: List[str], firecrawl_key: Optional[str]) -> Dict[str, Any]:
    for provider in chain:
        try:
            if provider == "firecrawl":
                page = scrape_firecrawl(url, firecrawl_key or "")
            elif provider == "jina":
                page = scrape_jina(url)
            else:
                page = scrape_http(url)
        except (urllib.error.URLError, OSError, ValueError) as e:
            warn(f"{provider} fetch failed for '{url}': {describe_error(e)}")
            continue
        if (page.get("html") or page.get("markdown") or "").strip():
            page["provider"] = provider
            return page
    return {"html": "", "markdown": "", "provider": None}


class _OutlineParser(seo_lib._PageParser):
    """The crawl parser, plus the order of H2 and H3 as they close. Headings
    inside nav, header, footer or aside (site chrome) are left out."""

    def __init__(self) -> None:
        super().__init__()
        self.order: List[Any] = []

    def handle_endtag(self, tag: str) -> None:
        before = len(self.headings[tag]) if tag in ("h2", "h3") else None
        in_chrome = self.chrome > 0
        super().handle_endtag(tag)
        if before is not None and len(self.headings[tag]) > before and not in_chrome:
            text = self.headings[tag][-1]
            if text:
                self.order.append((tag, text))


def outline_from_sequence(seq: List[Any]) -> List[Dict[str, Any]]:
    """[(tag, text)] in document order to [{"h2": text, "h3": [...]}]. H3s
    before the first H2 sit under {"h2": None}. Capped per OUTLINE_* above."""
    out: List[Dict[str, Any]] = []
    n_h3 = 0
    for tag, text in seq:
        if tag == "h2":
            if sum(1 for o in out if o["h2"] is not None) >= OUTLINE_MAX_H2:
                break
            out.append({"h2": text, "h3": []})
        elif tag == "h3":
            if not out:
                out.append({"h2": None, "h3": []})
            if len(out[-1]["h3"]) < OUTLINE_MAX_H3_PER_H2 and n_h3 < OUTLINE_MAX_H3:
                out[-1]["h3"].append(text)
                n_h3 += 1
    return out


def heading_outline(html: str) -> List[Dict[str, Any]]:
    """H2 and H3 of an HTML page in document order, each H3 under its parent H2."""
    p = _OutlineParser()
    try:
        p.feed(html or "")
        p.close()
    except Exception as e:  # malformed markup never stops an analysis
        warn(f"HTML parse error while reading headings: {e}")
    return outline_from_sequence(p.order)


def markdown_outline(markdown: str) -> List[Dict[str, Any]]:
    """Same outline from a provider's markdown (## and ### lines, fenced code skipped)."""
    seq, fenced = [], False
    for line in (markdown or "").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        m = None if fenced else re.match(r"^(#{2,3})\s+(.+?)\s*#*\s*$", line)
        if m:
            text = " ".join(re.sub(r"[*_`]|\[([^\]]*)\]\([^)]*\)", lambda x: x.group(1) or "", m.group(2)).split())
            if text:
                seq.append(("h2" if len(m.group(1)) == 2 else "h3", text))
    return outline_from_sequence(seq)


_SOCIAL = None


def social_domains() -> List[str]:
    global _SOCIAL
    if _SOCIAL is None:
        try:
            _SOCIAL = list(seo_lib.load_assets_json("eeat-weights.json").get("social_domains", []))
        except Exception:
            _SOCIAL = []
    return _SOCIAL


def outbound_links(anchors: List[Dict[str, Any]], page_url: Optional[str]) -> List[Dict[str, str]]:
    """Links of a result page to other sites: the sources it cites. The page's
    own host (www. or not), social networks and unresolved relative links are left out."""
    own = seo_lib.bare_host(seo_lib.host_of(page_url)) if page_url else ""
    social = social_domains()
    out, seen = [], set()
    for a in anchors:
        url = a.get("url") or ""
        host = seo_lib.bare_host(seo_lib.host_of(url))
        if not host or host == "example.invalid" or (own and (host == own or host.endswith("." + own))):
            continue
        if any(host == d or host.endswith("." + d) for d in social):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "text": (a.get("text") or "")[:120]})
        if len(out) >= MAX_OUTBOUND:
            break
    return out


def extract_page_signals(html: str, markdown: str, fallback_title: Optional[str] = None,
                         fallback_meta: Optional[str] = None, page_url: Optional[str] = None) -> Dict[str, Any]:
    """On-page signals of one result, read from its HTML with the same parser
    as crawl.py (attributes in any order, apostrophes kept, JSON-LD parsed as
    JSON with arrays and @graph). The word count is the main content of the
    HTML whatever the scrape provider, so pages compare with each other;
    without HTML it falls back to the provider's text, flagged.

    outline lists H2 and H3 in document order, each H3 under its H2 (site
    chrome left out); h2_outline and h3_outline are its flat lists, kept for
    the readers of version 1.1. outbound_links are the links to other sites
    (relative links resolve to the page_url when given)."""
    base = "https://example.invalid/"
    if html and html.strip():
        sig = parse_html(html, page_url or base)
        outline = heading_outline(html)
        types = sorted({t for b in sig["jsonld"] for t in b["types"]})
        authors = []
        dates: Dict[str, Optional[str]] = {"published": None, "modified": None}
        for b in sig["jsonld"]:
            for obj in b["objects"]:
                a = obj.get("author")
                for x in (a if isinstance(a, list) else [a] if a else []):
                    if isinstance(x, dict) and x.get("name"):
                        authors.append(str(x["name"]))
                    elif isinstance(x, str):
                        authors.append(x)
                dates["published"] = dates["published"] or obj.get("datePublished")
                dates["modified"] = dates["modified"] or obj.get("dateModified")
        rel_author = bool(
            re.search(r"<(?:a|link)[^>]+rel=[\"'][^\"']*\bauthor\b", html, re.I))
        return {
            "title": sig["title"] or (fallback_title or None),
            "meta": sig["meta_description"] or (fallback_meta or None),
            "meta_length": len(sig["meta_description"] or fallback_meta or ""),
            "h1": sig["h1"][0] if sig["h1"] else None,
            "outline": outline,
            "h2_outline": [o["h2"] for o in outline if o["h2"]],
            "h3_outline": [h for o in outline for h in o["h3"]],
            "word_count": sig["word_count"],
            "word_count_basis": "html-main-content",
            "schema_types": types,
            "jsonld_invalid": sum(1 for b in sig["jsonld"] if not b["valid"]),
            "author_signal": bool(authors) or rel_author,
            "authors": sorted(set(authors)),
            "date_published": dates["published"],
            "date_modified": dates["modified"],
            "canonical": sig["canonical"] if sig["canonical"] and not sig["canonical"].startswith(base) else None,
            "outbound_links": outbound_links(sig["anchors"], page_url),
            "meta_robots": sig["meta_robots"],
            "lang": sig["lang"],
            "images": sig["images"],
        }
    outline = markdown_outline(markdown)
    return {
        "title": fallback_title or None, "meta": fallback_meta or None, "meta_length": len(fallback_meta or ""),
        "h1": None, "outline": outline, "h2_outline": [o["h2"] for o in outline if o["h2"]],
        "h3_outline": [h for o in outline for h in o["h3"]], "outbound_links": [],
        "word_count": len((markdown or "").split()), "word_count_basis": "provider-text (not comparable)",
        "schema_types": [], "jsonld_invalid": 0, "author_signal": None, "authors": [],
        "date_published": None, "date_modified": None, "canonical": None, "meta_robots": None, "lang": None, "images": None,
    }


# --- orchestration --------------------------------------------------------------

def serp_chain(requested: str, keys: Dict[str, Optional[str]], has_file: bool) -> List[str]:
    if requested == "none":
        return []
    if requested != "auto":
        return [requested] + (["file"] if has_file and requested != "file" else [])
    chain = [p for p in ("serper", "serpapi") if keys.get(p)]
    if has_file:
        chain.append("file")
    if keys.get("firecrawl"):
        chain.append("firecrawl")
    return chain


def fetch_serp(query: str, country: str, language: str, chain: List[str],
               keys: Dict[str, Optional[str]], organic_map: Dict[str, List[str]]):
    for provider in chain:
        if provider == "serper":
            serp = serp_via_serper(query, country, language, keys["serper"] or "")
        elif provider == "serpapi":
            serp = serp_via_serpapi(query, country, language, keys["serpapi"] or "")
        elif provider == "firecrawl":
            serp = serp_via_firecrawl(query, country, language, keys["firecrawl"] or "")
        else:
            serp = serp_via_file(query, organic_map)
        if serp is not None:
            return provider, serp
    return None, None


def analyze_query(query: str, country: str, language: str, serp_providers: List[str],
                  scrape_providers: List[str], keys: Dict[str, Optional[str]],
                  organic_map: Dict[str, List[str]]) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "query": query,
        "country": country,
        "language": language,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "serp_provider": None,
        "ai_overview": {"present": None, "text": None, "cited_sources": [], "status": "unverified"},
        "features": {"paa": [], "paa_status": "unverified", "featured_snippet": None,
                     "featured_snippet_status": "unverified"},
        "top_10": [],
        "_warnings": [],
    }

    provider, serp = fetch_serp(query, country, language, serp_providers, keys, organic_map)
    record["serp_provider"] = provider
    if serp is None:
        record["_warnings"].append(
            "No SERP provider returned results: top_10, AI Overview, PAA and featured snippet are Unverified. "
            "Set SERPER_API_KEY or SERPAPI_API_KEY, or pass --organic-file with URLs from built-in search.")
        return record

    if serp["ai_overview"] is not None:
        record["ai_overview"] = dict(serp["ai_overview"], status="captured")
    if serp["paa"] is not None:
        record["features"]["paa"] = serp["paa"]
        record["features"]["paa_status"] = "captured"
    if serp["paa"] is not None or serp["ai_overview"] is not None:
        record["features"]["featured_snippet"] = serp["featured_snippet"]
        record["features"]["featured_snippet_status"] = "captured"
    if serp["raw_markdown"] is not None:
        record["features"]["raw_markdown"] = serp["raw_markdown"]
        record["_warnings"].append(
            "Firecrawl SERP scrape: organic order not parsed and AI Overview unreliable; review raw_markdown manually.")
    if provider == "file":
        record["_warnings"].append(
            "Organic URLs from --organic-file (built-in search or manual): AI Overview, PAA and featured snippet are Unverified.")

    for i, item in enumerate(serp["organic"], start=1):
        page = crawl_url(item["url"], scrape_providers, keys.get("firecrawl"))
        if page["provider"] is None:
            record["_warnings"].append(f"Could not fetch {item['url']} with any scrape provider.")
        signals = extract_page_signals(page.get("html", ""), page.get("markdown", ""),
                                       page.get("meta_title"), page.get("meta_description"), page_url=item["url"])
        record["top_10"].append({
            "position": i,
            "url": item["url"],
            "serp_title": item.get("title"),
            "serp_snippet": item.get("snippet"),
            "scrape_provider": page["provider"],
            **signals,
        })
    return record


def load_organic_file(path: Optional[str]) -> Optional[Dict[str, List[str]]]:
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"[error] cannot read --organic-file '{path}': {e}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print("[error] --organic-file must be a JSON object: {\"query\": [\"url\", ...]}", file=sys.stderr)
        return None
    return {str(k): [u for u in v if isinstance(u, str)] for k, v in data.items() if isinstance(v, list)}


def main() -> int:
    ap = argparse.ArgumentParser(description="SERP + page analyzer for seo-audit. Every API is optional.")
    ap.add_argument("--queries", nargs="+", required=True, help="Target queries")
    ap.add_argument("--country", default=DEFAULT_SERP_COUNTRY,
                    help="SERP country, two-letter ISO code (any case). 'all' or empty falls back to --fallback-country.")
    ap.add_argument("--fallback-country", default=DEFAULT_SERP_COUNTRY,
                    help="Country used when --country is 'all', empty or invalid (default: us)")
    ap.add_argument("--language", default="en", help="hl language code")
    ap.add_argument("--serp-provider", default="auto", choices=SERP_PROVIDERS,
                    help="auto = serper if SERPER_API_KEY, else serpapi if SERPAPI_API_KEY, else --organic-file, "
                         "else a firecrawl scrape of Google if FIRECRAWL_API_KEY, else none (degraded)")
    ap.add_argument("--scrape-provider", default="auto", choices=SCRAPE_PROVIDERS,
                    help="auto = firecrawl if FIRECRAWL_API_KEY, else jina (keyless Jina Reader), else http. "
                         "A failing provider drops to the next one.")
    ap.add_argument("--organic-file",
                    help="JSON object {query: [ordered result URLs]} from built-in web search or pasted by the founder")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--confirm-spend", action="store_true",
                    help="The founder agreed to the paid calls: allow Serper, SerpApi, Firecrawl and a keyed Jina. "
                         "FOG_ALLOW_SPEND=1 in the environment does the same for scripted runs.")
    args = ap.parse_args()

    keys = {
        "serper": os.environ.get("SERPER_API_KEY"),
        "serpapi": os.environ.get("SERPAPI_API_KEY"),
        "firecrawl": os.environ.get("FIRECRAWL_API_KEY"),
    }

    organic_map = load_organic_file(args.organic_file)
    if organic_map is None:
        return 2

    forced_key = {"serper": "SERPER_API_KEY", "serpapi": "SERPAPI_API_KEY", "firecrawl": "FIRECRAWL_API_KEY"}
    if args.serp_provider in forced_key and not keys[args.serp_provider]:
        print(f"[error] --serp-provider {args.serp_provider} needs {forced_key[args.serp_provider]}; "
              "use --serp-provider auto to fall back.", file=sys.stderr)
        return 2
    if args.serp_provider == "file" and not organic_map:
        print("[error] --serp-provider file needs --organic-file.", file=sys.stderr)
        return 2
    if args.scrape_provider == "firecrawl" and not keys["firecrawl"]:
        warn("--scrape-provider firecrawl without FIRECRAWL_API_KEY; falling back to jina, then http.")

    serp_providers = serp_chain(args.serp_provider, keys, bool(organic_map))
    scrape_providers = scrape_chain(args.scrape_provider, keys["firecrawl"])
    if args.scrape_provider == "firecrawl" and not keys["firecrawl"]:
        scrape_providers = ["jina", "http"]

    spend_ok = spend_confirmed(args.confirm_spend)
    paid_serp = [p for p in serp_providers if p in PAID_PROVIDERS]
    paid_scrape = "firecrawl" in scrape_providers
    if (paid_serp or paid_scrape) and not spend_ok:
        n = len(args.queries)
        plan = []
        if paid_serp:
            plan.append(f"up to {n} SERP call(s) on {paid_serp[0]}"
                        + (f" (then {', '.join(paid_serp[1:])} for a query that fails)" if len(paid_serp) > 1 else ""))
        if paid_scrape:
            plan.append(f"up to {n * 10} Firecrawl page scrape(s) (10 results per query, 1 credit each)")
        print(f"spend gate: {' and '.join(plan)} for {n} quer{'y' if n == 1 else 'ies'}. Nothing was sent. "
              "Re-run with --confirm-spend once the founder agreed (quota or money), "
              "or without spend: --serp-provider file --organic-file <urls.json> (or none) --scrape-provider jina.")
        return 1
    global _USE_JINA_KEY
    _USE_JINA_KEY = spend_ok

    if not serp_providers:
        warn("No SERP provider available (no SERPER_API_KEY, SERPAPI_API_KEY, --organic-file or FIRECRAWL_API_KEY). "
             "Records will hold empty top_10 and Unverified SERP features.")
    elif serp_providers[0] not in ("serper", "serpapi"):
        warn(f"SERP provider '{serp_providers[0]}' returns no AI Overview, PAA or featured snippet: those fields will be Unverified.")
    print(f"[info] providers: serp = {' > '.join(serp_providers) or 'none'}, "
          f"scrape = {' > '.join(scrape_providers)}", file=sys.stderr)

    country = resolve_serp_country(args.country, args.fallback_country)

    results = []
    for n, q in enumerate(args.queries):
        print(f"[info] analyzing: {q}", file=sys.stderr)
        results.append(analyze_query(q, country, args.language, serp_providers, scrape_providers, keys, organic_map))
        if n < len(args.queries) - 1:
            time.sleep(1)  # stay polite with every provider

    used_scrape = sorted({p["scrape_provider"] for r in results for p in r["top_10"] if p["scrape_provider"]})
    used_serp = sorted({r["serp_provider"] for r in results if r["serp_provider"]})
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.2",
            "country_requested": args.country,
            "serp_country": country,
            "providers": {"serp": used_serp or ["none"], "scrape": used_scrape or ["none"]},
            "queries_analyzed": len(results),
            "data": results,
        }, f, indent=2)

    print(f"[info] wrote {len(results)} records to {args.out} "
          f"(serp: {', '.join(used_serp) or 'none'}; scrape: {', '.join(used_scrape) or 'none'})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
