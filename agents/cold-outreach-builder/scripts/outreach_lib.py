#!/usr/bin/env python3
"""
outreach_lib.py

Helpers shared by the cold-outreach-builder scripts. Standard library only,
Python 3.9+. Not a command: the scripts import it.

- Paths of the agent, its assets and the shared layer.
- Page cache: cache/<hash>.txt (and .html), hash = first 16 hex chars of the
  sha256 of the URL without its #fragment, HTML to text.
- Text normalization used to compare an excerpt with a cached page.
- Dates read from public post ids: LinkedIn activity ids and X status ids carry
  their creation time in their top bits, so a post date never depends on a
  search engine snippet.
- Contact keys for the state file (email, else LinkedIn URL, else id).
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
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.dirname(SCRIPTS)
ASSETS = os.path.join(AGENT, "assets")
REPO = os.path.dirname(os.path.dirname(AGENT))
SHARED = os.path.join(REPO, "shared")
WRITING_GATE_SCRIPTS = os.path.join(SHARED, "skills", "writing-gate", "scripts")
SHARED_SCRIPTS = os.path.join(SHARED, "scripts")


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
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read_csv(path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = [h.strip() for h in (reader.fieldnames or []) if h]
            rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k} for r in reader]
    except OSError as e:
        raise InputError(f"cannot read {path}: {e}")
    return header, rows


def write_csv(path: str, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merged_config(default_path: str, override_path: Optional[str]) -> Dict[str, Any]:
    """Load an asset (limits, criteria, reply rules) and merge a project copy over it."""
    base = load_json(default_path)
    if override_path:
        over = load_json(override_path)
        base = deep_merge(base, over)
    return base


def deep_merge(base: Any, over: Any) -> Any:
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = deep_merge(base.get(k), v) if k in base else v
        return out
    return over


def validator():
    """Return shared/scripts/validate_json.validate."""
    if SHARED_SCRIPTS not in sys.path:
        sys.path.insert(0, SHARED_SCRIPTS)
    from validate_json import validate  # noqa: E402
    return validate


# ---------------------------------------------------------------- dates

def parse_day(value: str) -> Optional[date]:
    try:
        return datetime.strptime((value or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def today_or(value: Optional[str]) -> date:
    if value:
        d = parse_day(value)
        if not d:
            raise InputError(f"--today must be YYYY-MM-DD, got {value}")
        return d
    return date.today()


LI_ID_RE = re.compile(r"(?:activity|ugcPost|share)[-:%3A]+(\d{15,22})", re.I)
X_ID_RE = re.compile(r"(?:twitter|x)\.com/[^/]+/status(?:es)?/(\d{10,22})", re.I)
X_EPOCH_MS = 1288834974657


def li_activity_date(url: str) -> Optional[date]:
    """Creation date of a LinkedIn post from the activity id in its URL.

    The first 41 of the 64 bits of the id are a Unix time in milliseconds:
    (id >> 22) / 1000. Works for activity-, ugcPost- and share- ids and for
    urn:li:activity:<id>.
    """
    m = LI_ID_RE.search(url or "")
    if not m:
        return None
    ms = int(m.group(1)) >> 22
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def x_status_date(url: str) -> Optional[date]:
    """Creation date of an X (Twitter) post from its status id (snowflake)."""
    m = X_ID_RE.search(url or "")
    if not m:
        return None
    ms = (int(m.group(1)) >> 22) + X_EPOCH_MS
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError):
        return None


def post_id_date(url: str) -> Optional[date]:
    return li_activity_date(url) or x_status_date(url)


def linkedin_post_owner(url: str) -> Optional[str]:
    """Public slug of the author of a linkedin.com/posts/<slug>_... URL."""
    m = re.search(r"linkedin\.com/posts/([^/_?#]+)_", unquote(url or ""), re.I)
    return m.group(1).lower() if m else None


def linkedin_profile_slug(url: str) -> Optional[str]:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", unquote(url or ""), re.I)
    return m.group(1).lower().rstrip("/") if m else None


def is_linkedin_profile(url: str) -> bool:
    return bool(re.search(r"linkedin\.com/(?:in|company|sales)/", url or "", re.I))


# ---------------------------------------------------------------- cache

def canonical_url(url: str) -> str:
    url = (url or "").strip()
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:16]


def cache_paths(cache_dir: str, url: str) -> Tuple[str, str]:
    h = url_hash(url)
    return os.path.join(cache_dir, h + ".txt"), os.path.join(cache_dir, h + ".html")


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
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "«": '"', "»": '"',
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


WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:['\u2019][0-9A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*")


def words(text: str) -> List[str]:
    return WORD_RE.findall(text or "")


# ---------------------------------------------------------------- contacts

def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_linkedin(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url if "://" in url else "https://" + url)
    host = parts.netloc.lower()
    if host.endswith("linkedin.com"):
        host = "linkedin.com"
    return (host + unquote(parts.path).rstrip("/")).lower()


def contact_key(row: Dict[str, str]) -> str:
    email = normalize_email(row.get("email", ""))
    if email:
        return "email:" + email
    li = normalize_linkedin(row.get("linkedin_url") or row.get("linkedin") or "")
    if li:
        return "linkedin:" + li
    pid = (row.get("prospect_id") or "").strip()
    return "id:" + pid if pid else ""


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return code
