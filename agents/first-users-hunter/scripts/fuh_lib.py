#!/usr/bin/env python3
"""
fuh_lib.py

Helpers shared by the first-users-hunter scripts. Standard library only,
Python 3.9+. Not a command: the scripts import it.

- Paths of the agent, its assets and the shared layer.
- JSON, JSONL and CSV files, criteria merged with a project override.
- Page cache: <cache>/<hash>.txt, hash = first 16 hex chars of the sha256 of
  the URL without its #fragment. Same layout and hash as the cache of
  cold-outreach-builder (scripts/cache_page.py there), so a handoff cache is
  read by that agent as is.
- Text normalization used to compare an excerpt with a cached page.
- Dates read from public post ids: LinkedIn activity ids and X status ids
  carry their creation time in their top bits.
- Owners read from URLs: the LinkedIn public slug of a post, the X handle of
  a status.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(SCRIPTS)
ASSETS = os.path.join(AGENT, "assets")
REPO = os.path.dirname(os.path.dirname(AGENT))
SHARED_SCRIPTS = os.path.join(REPO, "shared", "scripts")

CRITERIA = os.path.join(ASSETS, "criteria.json")
PERSON_SCHEMA = os.path.join(ASSETS, "person.schema.json")
SIGNAL_SCHEMA = os.path.join(ASSETS, "signal.schema.json")
HANDOFF_SCHEMA = os.path.join(ASSETS, "handoff", "cold-outreach-prospect.schema.json")


class InputError(Exception):
    """A user-facing input problem: the scripts print it and exit 2."""


# ---------------------------------------------------------------- files

def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        raise InputError(f"cannot read {path}: {e}")
    except json.JSONDecodeError as e:
        raise InputError(f"{path} is not valid JSON: {e}")


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise InputError(f"{path}:{n} is not valid JSON: {e}")
    return rows


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_csv(path: str) -> List[Dict[str, str]]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k}
                    for r in csv.DictReader(f)]
    except OSError as e:
        raise InputError(f"cannot read {path}: {e}")


def write_csv(path: str, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def deep_merge(base: Any, over: Any) -> Any:
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return over


def load_criteria(override: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """assets/criteria.json, then a project criteria file, then the config's
    recency_days and activity keys (cross-cutting convention C4)."""
    crit = load_json(CRITERIA)
    if override:
        crit = deep_merge(crit, load_json(override))
    if config:
        for t, days in (config.get("recency_days") or {}).items():
            if t in crit["signal_types"] and isinstance(days, (int, float)):
                crit["signal_types"][t]["max_age_days"] = int(days)
        if isinstance(config.get("activity"), dict):
            crit["activity"] = deep_merge(crit["activity"], config["activity"])
    return crit


def validator():
    """shared/scripts/validate_json.validate (stdlib subset of JSON Schema)."""
    if SHARED_SCRIPTS not in sys.path:
        sys.path.insert(0, SHARED_SCRIPTS)
    from validate_json import validate  # noqa: E402
    return validate


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code


# ---------------------------------------------------------------- dates

def parse_day(value: Any) -> Optional[date]:
    try:
        return datetime.strptime(str(value or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def today_or(value: Optional[str]) -> date:
    if value:
        d = parse_day(value)
        if not d:
            raise InputError(f"--today must be YYYY-MM-DD, got {value}")
        return d
    return date.today()


def iso_from_epoch(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


LI_ID_RE = re.compile(r"(?:activity|ugcPost|share)(?:[-:]|%3A)+(\d{15,22})", re.I)
X_ID_RE = re.compile(r"(?:twitter|x)\.com/([^/?#]+)/status(?:es)?/(\d{10,22})", re.I)
# X (Twitter) snowflake epoch, in milliseconds: 2010-11-04T01:42:54.657Z.
X_EPOCH_MS = 1288834974657


def li_activity_datetime(url: str) -> Optional[datetime]:
    """Creation time of a LinkedIn post from the activity id in its URL.

    The first 41 of the 64 bits of the id are a Unix time in milliseconds:
    (id >> 22) / 1000. Works for activity-, ugcPost- and share- ids and for
    urn:li:activity:<id>.
    """
    m = LI_ID_RE.search(unquote(url or ""))
    if not m:
        return None
    try:
        return datetime.fromtimestamp((int(m.group(1)) >> 22) / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def x_status_datetime(url: str) -> Optional[datetime]:
    """Creation time of an X post from its status id (snowflake):
    ((id >> 22) + 1288834974657) / 1000."""
    m = X_ID_RE.search(url or "")
    if not m:
        return None
    try:
        return datetime.fromtimestamp(((int(m.group(2)) >> 22) + X_EPOCH_MS) / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def post_id_datetime(url: str) -> Optional[datetime]:
    return li_activity_datetime(url) or x_status_datetime(url)


def post_id_date(url: str) -> Optional[date]:
    dt = post_id_datetime(url)
    return dt.date() if dt else None


def linkedin_post_owner(url: str) -> Optional[str]:
    """Public slug of the author of a linkedin.com/posts/<slug>_... URL."""
    m = re.search(r"linkedin\.com/posts/([^/_?#]+)_", unquote(url or ""), re.I)
    return m.group(1).lower() if m else None


def linkedin_profile_slug(url: str) -> Optional[str]:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", unquote(url or ""), re.I)
    return m.group(1).lower().rstrip("/") if m else None


def x_status_owner(url: str) -> Optional[str]:
    m = X_ID_RE.search(url or "")
    return m.group(1).lower() if m else None


def url_owner(url: str) -> Optional[Tuple[str, str]]:
    """(network, handle) when the URL itself names its author."""
    li = linkedin_post_owner(url)
    if li:
        return "linkedin", li
    x = x_status_owner(url)
    if x and x not in ("i", "intent", "search"):
        return "x", x
    return None


def is_linkedin_profile(url: str) -> bool:
    return bool(re.search(r"linkedin\.com/(?:in|company|sales)/", url or "", re.I))


# ---------------------------------------------------------------- cache

def canonical_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:16]


def cache_paths(cache_dir: str, url: str) -> Tuple[str, str]:
    h = url_hash(url)
    return os.path.join(cache_dir, h + ".txt"), os.path.join(cache_dir, h + ".html")


def cache_store(cache_dir: str, url: str, text: str, source: str, raw_html: str = "",
                cached_at: Optional[str] = None) -> str:
    """Write <cache>/<hash>.txt (and .html) and record the URL in index.json."""
    os.makedirs(cache_dir, exist_ok=True)
    txt, htm = cache_paths(cache_dir, url)
    if raw_html:
        with open(htm, "w", encoding="utf-8") as f:
            f.write(raw_html)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(f"URL: {canonical_url(url)}\n\n{text}")
    index_path = os.path.join(cache_dir, "index.json")
    index = load_json(index_path) if os.path.isfile(index_path) else {}
    index[url_hash(url)] = {
        "url": canonical_url(url),
        "source": source,
        "cached_at": cached_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chars": len(text),
    }
    write_json(index_path, dict(sorted(index.items())))
    return txt


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section",
             "article", "header", "footer", "blockquote", "pre", "dd", "dt", "figcaption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip = 0
        self.meta: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in self.SKIP:
            self.skip += 1
        if tag == "meta":
            a = dict(attrs)
            if (a.get("property") or a.get("name") or "").lower() in (
                    "og:description", "description", "og:title", "article:published_time"):
                if a.get("content"):
                    self.meta.append(a["content"])
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:  # malformed HTML: keep what was parsed
        pass
    text = "".join(parser.parts)
    if parser.meta:
        text = "\n".join(parser.meta) + "\n" + text
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip() + "\n"


def read_cached_text(cache_dir: str, url: str) -> Optional[str]:
    txt, htm = cache_paths(cache_dir, url)
    if os.path.isfile(txt):
        with open(txt, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    if os.path.isfile(htm):
        with open(htm, "r", encoding="utf-8", errors="replace") as f:
            return html_to_text(f.read())
    return None


# ---------------------------------------------------------------- text

QUOTES = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'", "\u00b4": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u00ab": '"', "\u00bb": '"',
    "\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u00ad": "",
    "\u2014": "-", "\u2013": "-", "\u2010": "-", "\u2011": "-",
}


def norm_text(text: str) -> str:
    """Case, quotes, dashes, entities and whitespace folded, accents kept."""
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKC", text)
    for a, b in QUOTES.items():
        text = text.replace(a, b)
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_tags(text: str) -> str:
    """HTML fragments returned by APIs (HN comment_text) to plain text."""
    if not text or "<" not in text:
        return html.unescape(text or "")
    text = re.sub(r"<p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def clip(text: Any, n: int) -> str:
    text = str(text or "")
    return text if len(text) <= n else text[: n - 3].rstrip() + "..."


def person_key(network: str, handle: str) -> str:
    return f"{(network or '').strip().lower()}:{(handle or '').strip().lower().lstrip('@')}"


# Published-email sanity: a real TLD, and not a package@version string that a
# regex lifted from a product page (seen in the wild: "minidenticons@4.2.1").
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}$")
PACKAGE_AT_VERSION_RE = re.compile(r"@\d+(?:\.\d+)+$")


def email_problem(email: str) -> Optional[str]:
    email = (email or "").strip()
    if not email:
        return None
    if PACKAGE_AT_VERSION_RE.search(email):
        return "looks like package@version, not an address"
    if not EMAIL_RE.match(email):
        return "not a valid address with a real top-level domain"
    return None
