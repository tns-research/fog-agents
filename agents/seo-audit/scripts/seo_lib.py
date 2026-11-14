#!/usr/bin/env python3
"""
seo_lib.py

Shared helpers of the seo-audit scripts. Not a command. Standard library only
(Python 3.9+); `requests` is used for fetching when it is installed and
`--http requests` or `auto` picks it, never required.

What lives here:
  - fetch(): one HTTP GET with the redirect chain recorded hop by hop
  - Origin: maps a public origin (https://acme.example) onto the origin really
    fetched (http://127.0.0.1:8000) so a local build or a fixture is audited
    with its production URLs
  - parse_html(): title, meta (any attribute order, apostrophes kept),
    canonical, robots, hreflang, og:*, lang, H1/H2/H3, links, JSON-LD parsed as
    JSON (arrays, @graph, type lists), word count of the main content
  - Robots: robots.txt parser with RFC 9309 group selection and longest-match
    rules, Sitemap lines and Content-Signal lines
  - parse_sitemap(): urlset or sitemapindex, gzip accepted
  - load_gsc(): Search Console rows from the API JSON or a UI CSV export
    (English, French, German, Spanish or Italian headers, compare exports)
  - jsonl helpers, url normalisation, dates
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(HERE)
ASSETS = os.path.join(AGENT, "assets")

TOOL_NAME = "fog-seo-audit"
USER_AGENT = "Mozilla/5.0 (compatible; fog-seo-audit/2.0)"
MAX_BYTES = 5_000_000


class InputError(Exception):
    """Bad input file or argument: scripts exit 2 on it."""


# --------------------------------------------------------------------------
# files

def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise InputError(f"{path} is not valid JSON: {e}")


def write_json(path: str, data: Any) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


def write_text(path: str, text: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_jsonl(path: str) -> List[Tuple[int, Dict[str, Any]]]:
    """Return (line_number, object) pairs; broken lines are skipped with a warning."""
    out: List[Tuple[int, Dict[str, Any]]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    warn(f"{path}:{n} is not valid JSON, skipped")
                    continue
                if isinstance(obj, dict):
                    out.append((n, obj))
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    return out


def load_assets_json(name: str) -> Any:
    return load_json(os.path.join(ASSETS, name))


def deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def parse_day(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        raise InputError(f"not a date (YYYY-MM-DD): {value}")


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "home"


# --------------------------------------------------------------------------
# URLs

def normalize_url(url: str) -> str:
    """Lowercase scheme and host, drop the fragment and default ports, keep
    the path exactly (a trailing slash is meaningful: /a and /a/ are two URLs)."""
    if not url:
        return url
    p = urllib.parse.urlsplit(url.strip())
    scheme = (p.scheme or "").lower()
    host = (p.hostname or "").lower()
    port = p.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = p.path or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, p.query, ""))


def origin_of(url: str) -> str:
    p = urllib.parse.urlsplit(normalize_url(url))
    return f"{p.scheme}://{p.netloc}"


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def path_of(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return (p.path or "/") + (("?" + p.query) if p.query else "")


def bare_host(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


class Origin:
    """Public origin (what the report shows, what canonicals should say) and
    fetch origin (what is really requested). Equal unless --as-origin is used."""

    def __init__(self, start_url: str, as_origin: Optional[str] = None) -> None:
        self.fetch = origin_of(start_url)
        self.public = origin_of(as_origin) if as_origin else self.fetch

    def to_fetch(self, url: str) -> str:
        u = normalize_url(url)
        if u.startswith(self.public + "/") or u == self.public:
            return self.fetch + u[len(self.public):]
        return u

    def to_public(self, url: str) -> str:
        u = normalize_url(url)
        if u.startswith(self.fetch + "/") or u == self.fetch:
            return self.public + u[len(self.fetch):]
        return u

    def is_internal(self, url: str) -> bool:
        u = normalize_url(url)
        return origin_of(u) in (self.public, self.fetch)

    @property
    def home(self) -> str:
        return self.public + "/"


# --------------------------------------------------------------------------
# HTTP

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _have_requests() -> bool:
    try:
        import requests  # noqa: F401
        return True
    except ImportError:
        return False


def _decode(body: bytes, content_type: str) -> str:
    if body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:2048], re.I)
        enc = m2.group(1).decode("ascii", "ignore") if m2 else "utf-8"
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _get_once(url: str, timeout: float, engine: str, user_agent: str) -> Dict[str, Any]:
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    if engine == "requests":
        import requests
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False, stream=True)
        body = r.raw.read(MAX_BYTES, decode_content=True) if r.raw is not None else r.content
        return {"status": r.status_code, "headers": {k.lower(): v for k, v in r.headers.items()}, "body": body or b""}
    req = urllib.request.Request(url, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return {"status": resp.status, "headers": {k.lower(): v for k, v in resp.headers.items()},
                    "body": resp.read(MAX_BYTES)}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(MAX_BYTES)
        except Exception:
            body = b""
        return {"status": e.code, "headers": {k.lower(): v for k, v in (e.headers or {}).items()}, "body": body}


def fetch(url: str, timeout: float = 20.0, engine: str = "auto", user_agent: str = USER_AGENT,
          max_redirects: int = 10, follow: bool = True) -> Dict[str, Any]:
    """GET url, following redirects by hand so every hop is recorded.

    Returns {url, final_url, status, chain:[{url,status,location}], headers,
    content_type, text, error, ms}. Never raises on network errors: `error`
    is set and `status` is None.
    """
    if engine == "auto":
        engine = "requests" if _have_requests() else "urllib"
    chain: List[Dict[str, Any]] = []
    current = url
    t0 = time.time()
    for _ in range(max_redirects + 1):
        try:
            r = _get_once(current, timeout, engine, user_agent)
        except Exception as e:  # network, DNS, TLS, timeout
            return {"url": url, "final_url": current, "status": None, "chain": chain, "headers": {},
                    "content_type": "", "text": "", "error": f"{type(e).__name__}: {e}"[:300],
                    "ms": int((time.time() - t0) * 1000)}
        status = r["status"]
        loc = r["headers"].get("location")
        if follow and status in (301, 302, 303, 307, 308) and loc:
            nxt = urllib.parse.urljoin(current, loc)
            chain.append({"url": current, "status": status, "location": nxt})
            current = nxt
            continue
        ctype = r["headers"].get("content-type", "")
        return {"url": url, "final_url": current, "status": status, "chain": chain, "headers": r["headers"],
                "content_type": ctype, "text": _decode(r["body"], ctype), "error": None,
                "ms": int((time.time() - t0) * 1000)}
    return {"url": url, "final_url": current, "status": None, "chain": chain, "headers": {}, "content_type": "",
            "text": "", "error": "too many redirects", "ms": int((time.time() - t0) * 1000)}


# --------------------------------------------------------------------------
# HTML

_SKIP_TEXT = {"script", "style", "noscript", "template", "svg", "head", "title"}
_CHROME = {"nav", "header", "footer", "aside"}
_MAIN = {"main", "article"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_TEXT_CAP = 60000
_BLOCK = {"p", "li", "td", "dd", "blockquote", "figcaption"}
_P_CLOSERS = {"div", "ul", "ol", "dl", "table", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "main", "header",
              "footer", "nav", "aside", "blockquote", "pre", "form", "hr", "figure", "details"}
_BLOCK_CAP = 15000
_BLOCKS_MAX = 400
_MONTHS = {m: i for i, names in enumerate([
    ("january", "jan", "janvier", "janv", "januar", "enero", "gennaio"),
    ("february", "feb", "fevrier", "février", "fevr", "févr", "februar", "febrero", "febbraio"),
    ("march", "mar", "mars", "marz", "märz", "marzo"),
    ("april", "apr", "avril", "avr", "abril", "aprile"),
    ("may", "mai", "mayo", "maggio"),
    ("june", "jun", "juin", "juni", "junio", "giugno"),
    ("july", "jul", "juillet", "juil", "juli", "julio", "luglio"),
    ("august", "aug", "aout", "août", "agosto"),
    ("september", "sep", "sept", "septembre", "septiembre", "settembre"),
    ("october", "oct", "octobre", "oktober", "octubre", "ottobre"),
    ("november", "nov", "novembre", "noviembre"),
    ("december", "dec", "décembre", "decembre", "déc", "dezember", "diciembre", "dicembre"),
], 1) for m in names}
_DATE_KEY = (r"(?P<key>published|posted|written|updated|last\s+updated|modified|last\s+modified|reviewed|"
             r"publi[ée]+|mis\s+[àa]\s+jour|actualis[ée]+|ver[öo]ffentlicht|aktualisiert|publicado|actualizado|pubblicato|aggiornato)")
_DATE_VAL = (r"(?P<val>\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}(?:er)?\.?\s+[^\W\d_]{3,10}\.?\s+\d{4}|"
             r"[^\W\d_]{3,10}\.?\s+\d{1,2},?\s+\d{4})")
DATE_PHRASE_RE = re.compile(_DATE_KEY + r"(?:\s+(?:on|le|am|el|il|:))?\s*:?\s*" + _DATE_VAL, re.I)
MODIFIED_KEYS = re.compile(r"updat|modif|mis|actualis|aktualis|aggiorn|review", re.I)
ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle", "ScholarlyArticle", "Report", "LiveBlogPosting",
                 "AnalysisNewsArticle", "OpinionNewsArticle", "ReviewNewsArticle", "SocialMediaPosting", "HowTo", "Guide"}
ORG_TYPES = {"Organization", "Corporation", "LocalBusiness", "OnlineBusiness", "OnlineStore", "NGO", "EducationalOrganization",
             "ProfessionalService", "NewsMediaOrganization", "GovernmentOrganization", "MedicalOrganization", "SportsOrganization"}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: Optional[str] = None
        self.title_parts: List[str] = []
        self.titles = 0
        self.in_title = False
        self.meta: Dict[str, List[str]] = {}
        self.links: List[Dict[str, str]] = []
        self.anchors: List[Dict[str, str]] = []
        self.jsonld_raw: List[str] = []
        self.in_jsonld = False
        self.jsonld_buf: List[str] = []
        self.headings: Dict[str, List[str]] = {"h1": [], "h2": [], "h3": []}
        self.h_stack: List[Tuple[str, List[str]]] = []
        self.skip = 0
        self.chrome = 0
        self.main = 0
        self.main_seen = False
        self.body_words = 0
        self.main_words = 0
        self.chrome_words = 0
        self.images = 0
        self.images_no_alt = 0
        self.scripts = 0
        self.comments: List[str] = []
        self.anchor_stack: List[Dict[str, Any]] = []
        self.captures: List[Dict[str, Any]] = []
        self.captured: List[Dict[str, Any]] = []
        self.itemprops: List[Dict[str, str]] = []
        self.itemtypes: List[str] = []
        self.img_no_alt: List[Dict[str, Any]] = []
        self.citations: List[Dict[str, str]] = []
        self.text_parts: List[str] = []
        self.text_len = 0
        self.block_stack: List[Tuple[str, List[str]]] = []
        self.blocks: List[Dict[str, Any]] = []
        self.blocks_len = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"].strip()
        elif tag == "title":
            self.titles += 1
            if self.titles == 1:
                self.in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").strip().lower()
            if key and "content" in a:
                self.meta.setdefault(key, []).append(a["content"].strip())
            if "charset" in a:
                self.meta.setdefault("charset", []).append(a["charset"])
        elif tag == "link":
            rel = (a.get("rel") or "").lower().split()
            self.links.append({"rel": " ".join(rel), "href": a.get("href", "").strip(),
                               "hreflang": a.get("hreflang", "").strip()})
        elif tag == "script":
            self.scripts += 1
            if (a.get("type") or "").strip().lower() == "application/ld+json":
                self.in_jsonld = True
                self.jsonld_buf = []
        elif tag == "a":
            item = {"href": a.get("href", "").strip(), "rel": (a.get("rel") or "").lower(), "text": [],
                    "zone": "chrome" if self.chrome else "body"}
            self.anchors.append(item)
            if self.block_stack:
                self.block_stack[-1][1].append("\x01")
            self.anchor_stack.append(item)
            for c in self.captures:
                if item["href"]:
                    c["links"].append(item["href"])
            if re.match(r"#(fn|footnote|ref|cite|note)", item["href"], re.I):
                self.citations.append({"selector": f'a[href="{item["href"][:40]}"]', "text": ""})
        elif tag == "img":
            self.images += 1
            if not (a.get("alt") or "").strip():
                self.images_no_alt += 1
                if len(self.img_no_alt) < 50:
                    self.img_no_alt.append({"src": a.get("src", "").strip(), "alt_attr": "alt" in a})
        self._eeat_start(tag, a)
        if tag in ("h1", "h2", "h3"):
            self.h_stack.append((tag, []))
        if tag in _SKIP_TEXT and tag not in ("head", "title"):
            self.skip += 1
        if tag in _P_CLOSERS:
            self._close_open("p")
        if tag in _CHROME:
            self.chrome += 1
        if tag in _BLOCK and not self.chrome and not self.skip:
            if tag in ("p", "li") and self.block_stack and self.block_stack[-1][0] == tag:
                self._close_block(self.block_stack.pop()[1])  # <p> and <li> close the previous one implicitly
            self.block_stack.append((tag, ["\x01"] if self.anchor_stack else []))  # a block inside a link is link text
        if tag in _MAIN:
            self.main += 1
            self.main_seen = True

    def _close_open(self, *tags: str) -> None:
        while self.block_stack and self.block_stack[-1][0] in tags:
            self._close_block(self.block_stack.pop()[1])

    def _close_block(self, parts: List[str]) -> None:
        """A text block of the body (p, li, td, dd, blockquote, figcaption outside nav, header,
        footer and aside): its text with whitespace collapsed and the character spans of the
        links it already holds, so a new link is never proposed inside an existing one."""
        if len(self.blocks) >= _BLOCKS_MAX or self.blocks_len >= _BLOCK_CAP:
            return
        raw = " ".join("".join(parts).split())
        text, spans, depth, start = [], [], 0, 0
        for ch in raw:
            if ch == "\x01":
                if depth == 0:
                    start = len(text)
                depth += 1
            elif ch == "\x02":
                if depth:
                    depth -= 1
                    if depth == 0 and len(text) > start:
                        spans.append([start, len(text)])
            else:
                text.append(ch)
        if depth and len(text) > start:
            spans.append([start, len(text)])
        t = "".join(text)
        lead = len(t) - len(t.lstrip())
        t = t.strip()
        if len(WORD_RE.findall(t)) < 3:
            return
        spans = [[max(0, a - lead), min(len(t), b - lead)] for a, b in spans if b - lead > 0]
        self.blocks.append({"text": t, "links": spans})
        self.blocks_len += len(t)

    def _eeat_start(self, tag: str, a: Dict[str, str]) -> None:
        for c in self.captures:
            if c["tag"] == tag:
                c["depth"] += 1
        prop = (a.get("itemprop") or "").strip()
        if prop:
            val = a.get("content") or a.get("datetime") or ""
            if prop in ("datePublished", "dateModified", "author", "name") and val:
                self.itemprops.append({"itemprop": prop, "value": val.strip()[:120], "tag": tag})
        if a.get("itemtype"):
            self.itemtypes.append(a["itemtype"].strip())
        if tag in ("blockquote", "q") and a.get("cite"):
            self.citations.append({"selector": f'{tag}[cite="{a["cite"][:80]}"]', "text": ""})
        if tag in _VOID:
            return
        kind, selector = None, None
        classes = (a.get("class") or "").split()
        parts = [x for c in classes + [a.get("id", "")] for x in re.split(r"[-_]", c.lower()) if x]
        if tag == "time":
            kind, selector = "time", "time"
        elif "author" in prop.lower().split():
            kind, selector = "byline", f'{tag}[itemprop="{prop}"]'
        elif tag == "a" and "author" in (a.get("rel") or "").lower().split():
            kind, selector = "byline", 'a[rel="author"]'
        elif "author" in parts or "byline" in parts:
            key = next(c for c in classes + [a.get("id", "")] if c and ({"author", "byline"} & set(re.split(r"[-_]", c.lower()))))
            kind, selector = "byline", (f"{tag}.{key}" if key in classes else f"{tag}#{key}")
        elif "testimonial" in parts or "testimonials" in parts:
            key = next(c for c in classes + [a.get("id", "")] if c and ({"testimonial", "testimonials"} & set(re.split(r"[-_]", c.lower()))))
            kind, selector = "testimonial", (f"{tag}.{key}" if key in classes else f"{tag}#{key}")
        elif tag == "cite":
            kind, selector = "cite", "cite"
        if kind:
            self.captures.append({"kind": kind, "tag": tag, "selector": selector, "depth": 0, "parts": [], "links": [],
                                  "href": a.get("href", "").strip() if tag == "a" else "",
                                  "datetime": (a.get("datetime") or "").strip(), "itemprop": prop,
                                  "class": " ".join(classes)})

    def _eeat_end(self, tag: str) -> None:
        for i in range(len(self.captures) - 1, -1, -1):
            c = self.captures[i]
            if c["tag"] != tag:
                continue
            if c["depth"]:
                c["depth"] -= 1
                continue
            self.captures.pop(i)
            text = " ".join("".join(c.pop("parts")).split())[:200]
            c.pop("depth")
            c["text"] = text
            if c["kind"] == "cite":
                self.citations.append({"selector": "cite", "text": text[:80]})
            elif len(self.captured) < 60:
                self.captured.append(c)
            break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_jsonld:
            self.jsonld_raw.append("".join(self.jsonld_buf))
            self.in_jsonld = False
        elif tag == "a" and self.anchor_stack:
            item = self.anchor_stack.pop()
            item["text"] = " ".join(" ".join(item["text"]).split())
            if self.block_stack:
                self.block_stack[-1][1].append("\x02")
        if tag in ("ul", "ol"):
            self._close_open("p", "li")
        elif tag in _P_CLOSERS:
            self._close_open("p")
        if tag in _BLOCK and any(t == tag for t, _ in self.block_stack):
            while self.block_stack:
                t, parts = self.block_stack.pop()
                self._close_block(parts)
                if t == tag:
                    break
        if tag in ("h1", "h2", "h3"):
            for i in range(len(self.h_stack) - 1, -1, -1):
                if self.h_stack[i][0] == tag:
                    t, parts = self.h_stack.pop(i)
                    self.headings[t].append(" ".join(" ".join(parts).split()))
                    break
        if tag in _SKIP_TEXT and tag not in ("head", "title") and self.skip > 0:
            self.skip -= 1
        if tag in _CHROME and self.chrome > 0:
            self.chrome -= 1
        if tag in _MAIN and self.main > 0:
            self.main -= 1
        self._eeat_end(tag)

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.in_jsonld:
            self.jsonld_buf.append(data)
            return
        if self.skip:
            return
        for _, parts in self.h_stack:
            parts.append(data)
        for item in self.anchor_stack:
            item["text"].append(data)
        if self.block_stack and not self.chrome:
            self.block_stack[-1][1].append(data)
        for c in self.captures:
            c["parts"].append(data)
        if self.text_len < _TEXT_CAP:
            self.text_parts.append(data)
            self.text_len += len(data)
        n = len(WORD_RE.findall(data))
        if not n:
            return
        self.body_words += n
        if self.main:
            self.main_words += n
        elif self.chrome:
            self.chrome_words += n

    def handle_comment(self, data: str) -> None:
        self.comments.append(data.strip()[:300])


def parse_jsonld(raw_blocks: List[str]) -> List[Dict[str, Any]]:
    """Each block: {valid, error, types, objects}. Types come from top-level
    objects, arrays and @graph members; "@type" lists are flattened."""
    out = []
    for raw in raw_blocks:
        text = raw.strip()
        item: Dict[str, Any] = {"valid": True, "error": None, "types": [], "objects": []}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            item.update(valid=False, error=f"invalid JSON at line {e.lineno}")
            out.append(item)
            continue
        nodes: List[Any] = []
        stack = data if isinstance(data, list) else [data]
        for node in stack:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                nodes.extend(node["@graph"])
                if node.get("@type"):
                    nodes.append({k: v for k, v in node.items() if k != "@graph"})
            else:
                nodes.append(node)
        for node in nodes:
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            types = t if isinstance(t, list) else ([t] if t else [])
            types = [str(x) for x in types if x]
            item["types"].extend(types)
            item["objects"].append(node)
        if not item["types"]:
            item["error"] = "no @type found"
        out.append(item)
    return out


def text_date(value: str) -> Optional[str]:
    """ISO date (YYYY-MM-DD) of a date string: ISO prefix, D/M/YYYY, 'March 4, 2026', '4 mars 2026'."""
    v = (value or "").strip().lower()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = re.fullmatch(r"(\d{1,2})(?:er)?\.?\s+([^\W\d_]+)\.?\s+(\d{4})", v) or None
            if m:
                d, mo, y = int(m.group(1)), _MONTHS.get(m.group(2), 0), int(m.group(3))
            else:
                m = re.fullmatch(r"([^\W\d_]+)\.?\s+(\d{1,2}),?\s+(\d{4})", v)
                if not m:
                    return None
                mo, d, y = _MONTHS.get(m.group(1), 0), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _names(value: Any, ids: Dict[str, Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    out = []
    for v in (value if isinstance(value, list) else [value]):
        if isinstance(v, dict) and v.get("@id") in ids and not v.get("name"):
            v = ids[v["@id"]]
        if isinstance(v, str) and v.strip():
            out.append({"name": v.strip()[:80], "url": None, "type": None})
        elif isinstance(v, dict):
            t = v.get("@type")
            out.append({"name": (str(v.get("name") or "").strip()[:80] or None), "url": (str(v.get("url") or "").strip() or None),
                        "type": (t[0] if isinstance(t, list) and t else t) or None})
    return [x for x in out if x["name"] or x["url"]]


def jsonld_entities(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compact view of every typed JSON-LD node, nested ones included: the
    fields E-E-A-T needs (author, dates, sameAs, reviews), @id references resolved."""
    ids: Dict[str, Dict[str, Any]] = {}
    nodes: List[Tuple[str, Dict[str, Any]]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, f"{path}[{i}]")
            return
        if not isinstance(node, dict):
            return
        if isinstance(node.get("@id"), str) and len(node) > 1:
            ids.setdefault(node["@id"], node)
        if node.get("@type"):
            nodes.append((path, node))
        for k, v in node.items():
            if k != "@type" and isinstance(v, (dict, list)):
                walk(v, f"{path}.{k}" if path else k)

    for b, block in enumerate(blocks):
        for o, obj in enumerate(block.get("objects", [])):
            walk(obj, f"jsonld[{b}]" + (f"[{o}]" if len(block.get("objects", [])) > 1 else ""))
    out = []
    for path, node in nodes:
        t = node["@type"]
        types = [str(x) for x in (t if isinstance(t, list) else [t]) if x]
        same_as = node.get("sameAs")
        ent = {
            "path": path, "types": types,
            "name": (str(node.get("name") or node.get("headline") or "").strip()[:120] or None),
            "author": _names(node.get("author"), ids) if node.get("author") is not None else [],
            "publisher": _names(node.get("publisher"), ids) if node.get("publisher") is not None else [],
            "date_published": str(node["datePublished"])[:40] if node.get("datePublished") else None,
            "date_modified": str(node["dateModified"])[:40] if node.get("dateModified") else None,
            "same_as": len(same_as if isinstance(same_as, list) else ([same_as] if same_as else [])),
            "has_review": bool(node.get("review") or node.get("reviews") or node.get("aggregateRating")),
        }
        out.append({k: v for k, v in ent.items() if v or k in ("path", "types")})
    return out


def parse_html(html: str, base_url: str) -> Dict[str, Any]:
    """Signals of one HTML document. base_url resolves relative URLs."""
    p = _PageParser()
    try:
        p.feed(html or "")
        p.close()
    except Exception as e:  # malformed markup never stops an audit
        warn(f"HTML parse error on {base_url}: {e}")
    while p.block_stack:
        p._close_block(p.block_stack.pop()[1])

    def first(key: str) -> Optional[str]:
        v = p.meta.get(key)
        return " ".join(v[0].split()) if v else None

    canonicals = [urllib.parse.urljoin(base_url, l["href"]) for l in p.links
                  if "canonical" in l["rel"].split() and l["href"]]
    hreflang = []
    for l in p.links:
        if "alternate" in l["rel"].split() and l["hreflang"] and l["href"]:
            hreflang.append({"lang": l["hreflang"], "href": normalize_url(urllib.parse.urljoin(base_url, l["href"]))})
    anchors = []
    for a in p.anchors:
        href = a["href"]
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absu = urllib.parse.urljoin(base_url, href)
        if urllib.parse.urlsplit(absu).scheme not in ("http", "https"):
            continue
        anchors.append({"url": normalize_url(absu), "text": a["text"] if isinstance(a["text"], str) else "",
                        "nofollow": "nofollow" in a["rel"], "zone": a["zone"]})
    jsonld = parse_jsonld(p.jsonld_raw)
    title = " ".join("".join(p.title_parts).split()) if p.titles else None
    if p.main_seen:
        words = p.main_words
    else:
        words = max(0, p.body_words - p.chrome_words)
    robots_vals = [v.lower() for v in p.meta.get("robots", []) + p.meta.get("googlebot", [])]
    return {
        "lang": p.lang,
        "title": title,
        "title_count": p.titles,
        "meta_description": first("description"),
        "meta_description_count": len(p.meta.get("description", [])),
        "meta_robots": ", ".join(robots_vals) if robots_vals else None,
        "canonical": normalize_url(canonicals[0]) if canonicals else None,
        "canonical_count": len(canonicals),
        "hreflang": hreflang,
        "og": {k: first(k) for k in ("og:title", "og:description", "og:url", "og:type", "og:image")},
        "h1": p.headings["h1"],
        "h2": p.headings["h2"][:40],
        "h3": p.headings["h3"][:40],
        "anchors": anchors,
        "blocks": p.blocks,
        "jsonld": jsonld,
        "word_count": words,
        "body_word_count": p.body_words,
        "images": p.images,
        "images_no_alt": p.images_no_alt,
        "scripts": p.scripts,
        "comments": p.comments,
        "images_no_alt_src": p.img_no_alt,
        "eeat": _eeat_raw(p, jsonld, base_url),
    }


def _eeat_raw(p: "_PageParser", jsonld: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    def absu(h: str) -> Optional[str]:
        if not h or h.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            return None
        u = urllib.parse.urljoin(base_url, h)
        return normalize_url(u) if urllib.parse.urlsplit(u).scheme in ("http", "https") else None

    elements = []
    for c in p.captured:
        if c["kind"] not in ("byline", "time", "testimonial"):
            continue
        item = {"kind": c["kind"], "selector": c["selector"], "text": c["text"]}
        links = [absu(h) for h in ([c["href"]] if c["href"] else []) + c["links"]]
        links = [l for l in dict.fromkeys(links) if l]
        if links:
            item["links"] = links[:5]
        if c["datetime"]:
            item["datetime"] = c["datetime"][:40]
        if c["itemprop"]:
            item["itemprop"] = c["itemprop"]
        if c["class"] and c["kind"] == "time":
            item["class"] = c["class"][:80]
        elements.append(item)
    rel_author = [absu(l["href"]) for l in p.links if "author" in l["rel"].split()]
    rel_author += [absu(a["href"]) for a in p.anchors if "author" in a["rel"].split()]
    text = " ".join(" ".join(p.text_parts).split())
    phrases, seen = [], set()
    for m in DATE_PHRASE_RE.finditer(text):
        snippet = m.group(0)[:80]
        if snippet in seen:
            continue
        seen.add(snippet)
        phrases.append({"text": snippet, "date": text_date(m.group("val")),
                        "kind": "modified" if MODIFIED_KEYS.search(m.group("key")) else "published"})
        if len(phrases) >= 10:
            break
    meta_keys = ("author", "article:author", "article:published_time", "article:modified_time", "og:updated_time",
                 "date", "dc.date", "dcterms.modified", "last-modified", "og:type")
    meta = {k: " ".join(p.meta[k][0].split())[:120] for k in meta_keys if p.meta.get(k)}
    return {
        "meta": meta,
        "elements": elements,
        "rel_author": [u for u in dict.fromkeys(rel_author) if u],
        "itemprops": p.itemprops[:20],
        "itemtypes": sorted(set(p.itemtypes))[:20],
        "citations": p.citations[:30],
        "headings": (p.headings["h2"] + p.headings["h3"])[:40],
        "date_phrases": phrases,
        "jsonld_entities": jsonld_entities(jsonld),
    }


def visible_text(html: str) -> str:
    """Visible text of a document (no script, style, template, head)."""

    class _T(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0
            self.parts: List[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in _SKIP_TEXT:
                self.skip += 1

        def handle_endtag(self, tag):
            if tag in _SKIP_TEXT and self.skip:
                self.skip -= 1

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    t = _T()
    try:
        t.feed(html or "")
        t.close()
    except Exception:
        pass
    return " ".join(" ".join(t.parts).split())


def is_noindex(meta_robots: Optional[str], x_robots: Optional[str]) -> bool:
    vals = " ".join([meta_robots or "", x_robots or ""]).lower()
    return bool(re.search(r"\b(noindex|none)\b", vals))


# --------------------------------------------------------------------------
# robots.txt (RFC 9309)

def _rule_regex(pattern: str) -> "re.Pattern[str]":
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile("^" + rx + ("$" if anchored else ""))


class Robots:
    def __init__(self, text: Optional[str]) -> None:
        self.text = text or ""
        self.groups: List[Dict[str, Any]] = []
        self.sitemaps: List[str] = []
        self.content_signals: List[str] = []
        self._parse()

    def _parse(self) -> None:
        current: Optional[Dict[str, Any]] = None
        last_was_ua = False
        for raw in self.text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                if current is None or not last_was_ua:
                    current = {"agents": [], "rules": [], "crawl_delay": None}
                    self.groups.append(current)
                current["agents"].append(val.split("/")[0].strip().lower())
                last_was_ua = True
                continue
            last_was_ua = False
            if key == "sitemap":
                self.sitemaps.append(val)
            elif key == "content-signal":
                self.content_signals.append(val)
            elif key in ("allow", "disallow") and current is not None:
                if val:
                    current["rules"].append((key == "allow", val))
                elif key == "disallow":
                    pass  # empty Disallow allows everything
            elif key == "crawl-delay" and current is not None:
                try:
                    current["crawl_delay"] = float(val)
                except ValueError:
                    pass

    def group_for(self, agent: str) -> Tuple[Optional[str], List[Tuple[bool, str]], Optional[float]]:
        """Rules for a crawler token: the groups naming it exactly (merged),
        else the * groups, else none (everything allowed)."""
        token = agent.lower()
        exact = [g for g in self.groups if token in g["agents"]]
        if exact:
            rules = [r for g in exact for r in g["rules"]]
            delay = next((g["crawl_delay"] for g in exact if g["crawl_delay"] is not None), None)
            return agent, rules, delay
        star = [g for g in self.groups if "*" in g["agents"]]
        if star:
            rules = [r for g in star for r in g["rules"]]
            delay = next((g["crawl_delay"] for g in star if g["crawl_delay"] is not None), None)
            return "*", rules, delay
        return None, [], None

    def allowed(self, agent: str, url_or_path: str) -> bool:
        path = url_or_path
        if "://" in url_or_path:
            path = path_of(url_or_path)
        if path == "/robots.txt":
            return True
        _, rules, _ = self.group_for(agent)
        best: Optional[Tuple[int, bool]] = None
        for allow, pattern in rules:
            if _rule_regex(pattern).match(path):
                length = len(pattern)
                if best is None or length > best[0] or (length == best[0] and allow and not best[1]):
                    best = (length, allow)
        return True if best is None else best[1]

    def crawl_delay(self, agent: str) -> Optional[float]:
        return self.group_for(agent)[2]


def ai_crawler_table(robots: Robots, crawlers: List[Dict[str, Any]], paths: Iterable[str] = ("/",)) -> List[Dict[str, Any]]:
    """One row per AI-related user agent: which group applies and whether each path is allowed."""
    rows = []
    for c in crawlers:
        group, _, _ = robots.group_for(c["token"])
        rows.append({
            "token": c["token"],
            "operator": c.get("operator"),
            "purpose": c.get("purpose"),
            "group": group or "none (no matching group)",
            "allowed": {p: robots.allowed(c["token"], p) for p in paths},
            "doc": c.get("doc"),
        })
    return rows


# --------------------------------------------------------------------------
# sitemaps

def parse_sitemap(text: str) -> Dict[str, Any]:
    kind = "sitemapindex" if re.search(r"<sitemapindex[\s>]", text or "", re.I) else (
        "urlset" if re.search(r"<urlset[\s>]", text or "", re.I) else "unknown")
    locs = []
    for m in re.finditer(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", text or "", re.I | re.S):
        locs.append(m.group(1).replace("&amp;", "&").strip())
    return {"kind": kind, "locs": locs}


# --------------------------------------------------------------------------
# Search Console data

DIM_HEADERS = {
    "query": ["top queries", "queries", "query", "requêtes les plus fréquentes", "requêtes", "requête",
              "suchanfragen", "häufigste suchanfragen", "consultas principales", "consultas", "consulta",
              "query più frequenti", "keys_query"],
    "page": ["top pages", "pages", "page", "pages les plus populaires", "url", "landing page", "seiten",
             "häufigste seiten", "páginas principales", "páginas", "pagine principali", "pagine"],
    "date": ["date", "dates", "datum", "fecha", "data", "day", "jour"],
    "country": ["country", "countries", "pays", "land", "país", "paese"],
    "device": ["device", "devices", "appareil", "appareils", "gerät", "dispositivo"],
}
METRIC_WORDS = {
    "clicks": ["clicks", "click", "clics", "clic", "klicks", "klick"],
    "impressions": ["impressions", "impression", "impressionen", "impresiones", "impressioni"],
    "ctr": ["ctr"],
    "position": ["position", "posición", "posizione"],
}
PRIOR_WORDS = ["previous", "prior", "précédent", "précédente", "precedent", "vorherig", "anterior", "precedente",
               "vorheriger", "vorige"]


def _num_int(s: str) -> int:
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def _num_float(s: str) -> Optional[float]:
    t = (s or "").strip().replace(" ", "").replace(" ", "").replace("%", "")
    if not t or t in ("-", "n/a"):
        return None
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def _classify_header(h: str) -> Tuple[Optional[str], Optional[str], bool]:
    """(dimension, metric, is_prior) for one CSV header cell."""
    low = h.strip().lstrip("﻿").lower()
    for metric, words in METRIC_WORDS.items():
        if any(re.search(r"(^|\W)" + re.escape(w) + r"($|\W)", low) for w in words):
            return None, metric, any(w in low for w in PRIOR_WORDS)
    for dim, names in DIM_HEADERS.items():
        if low in names:
            return dim, None, False
    return None, None, False


def _metrics(clicks: Any, impressions: Any, ctr: Any, position: Any) -> Dict[str, Any]:
    return {"clicks": clicks, "impressions": impressions, "ctr": ctr, "position": position}


def load_gsc_csv(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0] if text else ",", delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        raise InputError(f"{path} is empty")
    header = rows[0]
    cols: Dict[int, Tuple[Optional[str], Optional[str], bool]] = {i: _classify_header(h) for i, h in enumerate(header)}
    dims = [(i, c[0]) for i, c in cols.items() if c[0]]
    if not dims:
        raise InputError(f"{path}: no query, page or date column recognised in header {header}")
    has_prior = any(c[1] and c[2] for c in cols.values())
    if not any(c[1] == "clicks" for c in cols.values()):
        raise InputError(f"{path}: no clicks column recognised in header {header}")
    out_rows = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        rec: Dict[str, Any] = {}
        cur: Dict[str, Any] = {}
        prev: Dict[str, Any] = {}
        for i, cell in enumerate(r):
            dim, metric, prior = cols.get(i, (None, None, False))
            if dim:
                rec[dim] = cell.strip()
            elif metric:
                target = prev if prior else cur
                if metric in ("clicks", "impressions"):
                    target[metric] = _num_int(cell)
                else:
                    v = _num_float(cell)
                    if metric == "ctr" and v is not None:
                        v = v / 100.0 if ("%" in cell or v > 1) else v
                    target[metric] = v
        rec["cur"] = _fill(cur)
        if has_prior:
            rec["prev"] = _fill(prev)
        out_rows.append(rec)
    return {"path": path, "format": "csv", "dimensions": [d for _, d in dims], "compare": has_prior, "rows": out_rows}


def _fill(m: Dict[str, Any]) -> Dict[str, Any]:
    clicks = int(m.get("clicks") or 0)
    imp = int(m.get("impressions") or 0)
    ctr = m.get("ctr")
    if ctr is None:
        ctr = (clicks / imp) if imp else 0.0
    return _metrics(clicks, imp, round(float(ctr), 6), m.get("position"))


def load_gsc_json(path: str, dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
    data = load_json(path)
    dims = None
    rows = data
    if isinstance(data, dict):
        rows = data.get("rows", [])
        d = data.get("dimensions") or (data.get("request") or {}).get("dimensions")
        if isinstance(d, list):
            dims = [str(x).lower() for x in d]
    dims = dims or dimensions or ["query", "page"]
    if not isinstance(rows, list):
        raise InputError(f"{path}: expected a list of rows or an object with 'rows'")
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        rec: Dict[str, Any] = {}
        keys = r.get("keys")
        if isinstance(keys, list):
            for name, val in zip(dims, keys):
                rec[name] = str(val)
        else:
            for name in ("query", "page", "date", "country", "device"):
                if name in r:
                    rec[name] = str(r[name])
        rec["cur"] = _fill({"clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                            "ctr": r.get("ctr"), "position": r.get("position")})
        out.append(rec)
    present = [d for d in dims if any(d in x for x in out)] or dims
    return {"path": path, "format": "json", "dimensions": present, "compare": False, "rows": out}


def load_gsc(path: str, dimensions: Optional[List[str]] = None) -> Dict[str, Any]:
    if path.lower().endswith((".json", ".jsonl")):
        return load_gsc_json(path, dimensions)
    return load_gsc_csv(path)


def aggregate(rows: List[Dict[str, Any]], key: str, which: str = "cur") -> Dict[str, Dict[str, Any]]:
    """Sum clicks and impressions per key; position is impression-weighted."""
    acc: Dict[str, Dict[str, float]] = {}
    for r in rows:
        k = r.get(key)
        m = r.get(which)
        if k is None or not m:
            continue
        if key == "page":
            k = normalize_url(k)
        a = acc.setdefault(k, {"clicks": 0, "impressions": 0, "pos_w": 0.0, "pos_n": 0.0})
        a["clicks"] += m["clicks"]
        a["impressions"] += m["impressions"]
        if m.get("position") is not None:
            w = m["impressions"] or 1
            a["pos_w"] += m["position"] * w
            a["pos_n"] += w
    out = {}
    for k, a in acc.items():
        pos = round(a["pos_w"] / a["pos_n"], 2) if a["pos_n"] else None
        imp = int(a["impressions"])
        out[k] = {"clicks": int(a["clicks"]), "impressions": imp,
                  "ctr": round(a["clicks"] / imp, 4) if imp else 0.0, "position": pos}
    return out


def median(values: List[float]) -> Optional[float]:
    return statistics.median(values) if values else None
