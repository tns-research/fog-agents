#!/usr/bin/env python3
"""mslib.py: shared helpers of the market-signal scripts (stdlib only, Python 3.9+).

Not a command. Imported by the collectors, collect.py, verify_quotes.py,
compute_signals.py, build_handoff.py, validate_sidecar.py and diff_runs.py.

What lives here:
  - the corpus record format (make_record, read_jsonl, write_jsonl),
  - HTTP with a frozen-fixture mode and a record mode (Fetcher),
  - HTML to plain text, dates,
  - privacy: handle pseudonyms, author hashing, redaction of contact details,
  - the text normalisation used to check that a quote is verbatim,
  - the JSON Schema validator of shared/scripts/validate_json.py.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

AGENT = Path(__file__).resolve().parent.parent
REPO = AGENT.parent.parent
ASSETS = AGENT / "assets"
USER_AGENT = "fog-agents-market-signal/2.0 (+https://github.com/tns-research/fog-agents)"

# Health states a collector reports, in the order the report sorts them.
HEALTH_STATES = ("ok", "empty", "error", "quota")

RECORD_FIELDS = (
    "record_id", "source", "community", "kind", "url", "author_hash",
    "date", "created_at", "title", "text", "context", "score", "replies",
    "rating", "lang", "query", "method", "fetched_at",
)

REMOVED_TEXTS = {"[removed]", "[deleted]", "[removed by reddit]", ""}


# ---------------------------------------------------------------- files

def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, ascii_only: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=ascii_only, indent=2, sort_keys=False)
        f.write("\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: not JSON ({e})")
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
            n += 1
    return n


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- dates

def parse_date(value: Any) -> Optional[_dt.date]:
    """YYYY-MM-DD, ISO datetime or unix seconds to a date (UTC). None when unknown."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc).date()
    s = str(value).strip()
    if re.fullmatch(r"\d{9,11}(\.\d+)?", s):
        return parse_date(float(s))
    try:
        return _dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def iso_utc(value: Any) -> Optional[str]:
    """Unix seconds or ISO string to 'YYYY-MM-DDTHH:MM:SSZ' in UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        d = _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    s = str(value).strip()
    try:
        d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=_dt.timezone.utc)
        return d.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def to_unix(day: str, end_of_day: bool = False) -> int:
    d = _dt.date.fromisoformat(day)
    t = _dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc)
    if end_of_day:
        t += _dt.timedelta(days=1)
    return int(t.timestamp())


def today_utc() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%d")


def now_utc() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def window_from(since: Optional[str], until: Optional[str], as_of: Optional[str] = None,
                recency_days: Optional[int] = None) -> Tuple[str, str]:
    """Resolve a [since, until] window (inclusive dates)."""
    end = until or as_of or today_utc()
    if since:
        return since, end
    days = recency_days if recency_days is not None else 90
    start = _dt.date.fromisoformat(end) - _dt.timedelta(days=days)
    return start.isoformat(), end


def in_window(day: Optional[str], since: str, until: str) -> bool:
    return day is not None and since <= day <= until


# ---------------------------------------------------------------- text

_BLOCK_TAGS = re.compile(r"(?i)<\s*(br|/p|p|/div|div|/li|li|/h\d|h\d|/blockquote|blockquote|/pre|pre|hr)\b[^>]*>")
_TAG = re.compile(r"<[^>]+>")


def html_to_text(raw: Optional[str]) -> str:
    """Deterministic HTML to plain text: block tags become line breaks, other tags go, entities decode."""
    if not raw:
        return ""
    s = _BLOCK_TAGS.sub("\n", raw)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t\f\v]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def markdown_links_to_text(s: str) -> str:
    """'[label](url)' becomes 'label' (corpus text from markdown scrapes or Reddit bodies)."""
    return re.sub(r"\[([^\]]*)\]\((?:https?://|/)[^)]*\)", r"\1", s or "")


_QUOTE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "«": '"', "»": '"',
}
_SPACE_CHARS = {" ", " ", " ", " ", " ", " ", " ", "\t", "\n", "\r", "\f", "\v"}
_ZERO_WIDTH = {"​", "‌", "‍", "﻿"}


def normalize_with_map(text: str) -> Tuple[str, List[int]]:
    """Normalise for verbatim matching and keep, for each output char, its index in the input.

    Allowed differences only: Unicode NFC, curly vs straight quote marks of the
    same kind (single stays single, double stays double), guillemets as double
    quotes, any run of whitespace as one space, zero-width characters dropped.
    Case, punctuation, words and order must be identical.
    """
    out: List[str] = []
    idx: List[int] = []
    prev_space = True
    for i, ch in enumerate(text):
        c = unicodedata.normalize("NFC", ch)
        if c in _ZERO_WIDTH:
            continue
        if c in _SPACE_CHARS or c == " ":
            if prev_space:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
            continue
        c = _QUOTE_MAP.get(c, c)
        for cc in c:
            out.append(cc)
            idx.append(i)
        prev_space = False
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


def find_verbatim(passage: str, text: str) -> Optional[Tuple[int, int]]:
    """Return (start, end) of passage inside text in original indexes, or None."""
    p = normalize(passage).strip()
    if not p:
        return None
    t, idx = normalize_with_map(text)
    k = t.find(p)
    if k < 0:
        return None
    start = idx[k]
    end = idx[k + len(p) - 1] + 1
    return start, end


ELLIPSIS_RE = re.compile(r"\s*(?:\.\.\.|…|\[\s*\.\.\.\s*\]|\[\s*…\s*\]|\(\s*\.\.\.\s*\))\s*")


def word_count(s: str) -> int:
    return len(re.findall(r"\w+", s or "", flags=re.UNICODE))


# ---------------------------------------------------------------- privacy

NO_AUTHOR = ("[deleted]", "deleted", "anonymous")
PSEUDONYM_RE = re.compile(r"^user-[0-9a-f]{6}$")
# Keys whose value is a handle or a display name in the answers the collectors read.
AUTHOR_KEYS = ("author", "username", "display_name")

_URL_TAIL = r"(?:[^\s\"'<>)\]]*[^\s\"'<>)\].,;:!?])?"  # rest of the link, trailing punctuation left out
_PROFILE = re.compile(
    r"(?i)(?<![\w.-])(?:https?://)?(?:[\w-]+\.)?"
    r"(?:linkedin\.com/in/|github\.com/|x\.com/|twitter\.com/|instagram\.com/|facebook\.com/|t\.me/"
    r"|reddit\.com/u(?:ser)?/|news\.ycombinator\.com/user\?id=|drive\.google\.com/|docs\.google\.com/)" + _URL_TAIL +
    r"|(?<![\w.-])(?:https?://)?[\w-]+\.github\.io\b" + _URL_TAIL)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+(?:@|\s?[(\[]at[)\]]\s?)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_REDDIT_USER = re.compile(r"(?<![\w/])/?u/[A-Za-z0-9_-]{3,20}\b")
_MENTION = re.compile(r"(?<![\w.@/+-])@[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?")
_PHONE = re.compile(r"(?<![\w+])\+\d[\d .()-]{7,}\d(?!\w)|\(?\b\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b|\b0[1-9](?:[ .-]?\d{2}){4}\b")
_DATA_USER = re.compile(r'data-username="([^"]+)"')


def pseudonym(source: str, author: Optional[str]) -> Optional[str]:
    """Deterministic stand-in for a public handle: user-<6 hex>. A pseudonym maps to itself."""
    if not author or author in NO_AUTHOR:
        return None
    if PSEUDONYM_RE.match(author):
        return author
    return "user-" + hashlib.sha256(f"{source}:{author}".encode("utf-8")).hexdigest()[:6]


def author_hash(source: str, author: Optional[str]) -> Optional[str]:
    """Stable id of an author for counting distinct people, computed on the pseudonym:
    a handle and its pseudonym give the same hash, so live runs and fixtures agree."""
    p = pseudonym(source, author)
    return hashlib.sha256(f"{source}:{p}".encode("utf-8")).hexdigest()[:12] if p else None


def redact(text: Optional[str]) -> Optional[str]:
    """Profile and document links, emails (also "name (at) host"), reddit u/ handles, @mentions
    and phone numbers to placeholders."""
    if not text:
        return text
    s = _PROFILE.sub("[profile link]", text)
    s = _EMAIL.sub("[email]", s)
    s = _REDDIT_USER.sub("[profile link]", s)
    s = _MENTION.sub("[mention]", s)
    return _PHONE.sub("[phone]", s)


def _handle_like(name: str) -> bool:
    # A plain lowercase word ("puzzled", "user") is left in texts: replacing it would rewrite prose.
    return len(name) >= 4 and not re.fullmatch(r"[a-z]+", name) and not PSEUDONYM_RE.match(name)


def scrub(data: Any, source: str) -> Any:
    """One API answer with every handle pseudonymised and contact details redacted.

    Handles are the values under AUTHOR_KEYS (and Discourse quote attributes);
    each becomes pseudonym(source, handle), also where it is written in a text of
    the same answer. Every other string goes through redact(). The Fetcher applies
    this to every answer, so collectors, corpora and recorded fixtures never hold
    a handle, an email or a profile link.
    """
    names: Dict[str, str] = {}

    def collect(x: Any, under_author: bool = False) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                collect(v, under_author or k in AUTHOR_KEYS)
        elif isinstance(x, list):
            for v in x:
                collect(v, under_author)
        elif isinstance(x, str):
            if under_author and x and not PSEUDONYM_RE.match(x):
                names[x] = pseudonym(source, x) or x
            for n in _DATA_USER.findall(x):
                names[n] = pseudonym(source, n) or n
    collect(data)
    swap = sorted((n for n in names if _handle_like(n)), key=len, reverse=True)
    pattern = re.compile("|".join(r"(?<![\w.])" + re.escape(n) + r"(?![\w])" for n in swap)) if swap else None

    def walk(x: Any, under_author: bool = False) -> Any:
        if isinstance(x, dict):
            return {k: walk(v, under_author or k in AUTHOR_KEYS) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v, under_author) for v in x]
        if isinstance(x, str):
            if under_author:
                return names.get(x, x)
            s = _DATA_USER.sub(lambda m: f'data-username="{names.get(m.group(1), m.group(1))}"', x)
            if pattern:
                s = pattern.sub(lambda m: names[m.group(0)], s)
            return redact(s)
        return x
    return walk(data)


# ---------------------------------------------------------------- records

def make_record(*, source: str, native_id: str, community: str, kind: str, url: str,
                author: Optional[str], created: Any, text: str, title: Optional[str] = None,
                context: Optional[str] = None, score: Optional[int] = None,
                replies: Optional[int] = None, rating: Optional[int] = None,
                lang: Optional[str] = None, query: Optional[str] = None,
                method: str = "", fetched_at: Optional[str] = None) -> Dict[str, Any]:
    created_at = iso_utc(created)
    day = parse_date(created)
    rec = {
        "record_id": f"{source}:{native_id}",
        "source": source,
        "community": community,
        "kind": kind,
        "url": url,
        "author_hash": author_hash(source, author),
        "date": day.isoformat() if day else None,
        "created_at": created_at,
        "title": redact(title) or None,
        "text": redact(text),
        "context": redact(context) or None,
        "score": score,
        "replies": replies,
        "rating": rating,
        "lang": lang,
        "query": query,
        "method": method,
        "fetched_at": fetched_at,
    }
    return rec


def is_removed(text: Optional[str]) -> bool:
    return (text or "").strip().lower() in REMOVED_TEXTS


# ---------------------------------------------------------------- HTTP

class FetchError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, quota: bool = False):
        super().__init__(message)
        self.status = status
        self.quota = quota


def _fixture_name(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8"), usedforsecurity=False).hexdigest()[:16] + ".json"


class Fetcher:
    """GET JSON with one of three modes.

    live      urllib, polite delay, one retry on a network error or a 5xx.
    fixtures  read <dir>/<sha1(url)[:16]>.json written by record mode; no network.
    record    live, then save the response under <dir>.

    A live answer is trimmed to the fields the collector reads (trim) and
    scrubbed (scrub: handles pseudonymised, contact details redacted) before
    the collector sees it, so a live run, its recording and its replay give the
    same records. A fixture file holds {"url", "status", "fetched_at", "body"};
    it is written ASCII-escaped so repo checks on dashes never trip on
    third-party text.
    """

    def __init__(self, fixtures: Optional[str] = None, record: Optional[str] = None,
                 delay: float = 1.0, timeout: float = 30.0, trim=None, backoff: float = 6.0,
                 source: str = ""):
        self.fixtures = Path(fixtures) if fixtures else None
        self.record = Path(record) if record else None
        self.delay = delay
        self.timeout = timeout
        self.trim = trim
        self.backoff = backoff
        self.source = source
        self.requests = 0
        self.last_fetched_at: Optional[str] = None
        self._last = 0.0

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        self.requests += 1
        if self.fixtures:
            path = self.fixtures / _fixture_name(url)
            if not path.exists():
                raise FetchError(f"no fixture for {url} ({path.name})")
            fx = read_json(path)
            self.last_fetched_at = fx.get("fetched_at")
            status = fx.get("status", 200)
            body = scrub(fx.get("body"), self.source)  # a no-op on fixtures recorded by this version
            self._raise_for(status, body, url)
            return body
        status, body = self._live(url, headers or {})
        self.last_fetched_at = now_utc()
        if self.trim and status == 200 and isinstance(body, (dict, list)):
            body = self.trim(url, body)
        body = scrub(body, self.source)
        if self.record:
            write_json(self.record / _fixture_name(url),
                       {"url": url, "status": status, "fetched_at": self.last_fetched_at, "body": body},
                       ascii_only=True)
        self._raise_for(status, body, url)
        return body

    def _raise_for(self, status: int, body: Any, url: str) -> None:
        if status == 429:
            raise FetchError(f"HTTP 429 rate limited on {url}", status, quota=True)
        if status >= 400:
            msg = body if isinstance(body, str) else json.dumps(body)[:300]
            raise FetchError(f"HTTP {status} on {url}: {msg}", status, quota=throttled(status, body))

    def _live(self, url: str, headers: Dict[str, str]) -> Tuple[int, Any]:
        wait = self.delay - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        h.update(headers)
        last_err = None
        for attempt in range(2):
            self._last = time.time()
            req = urllib.request.Request(url, headers=h)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        import gzip
                        raw = gzip.decompress(raw)
                    return r.status, _parse_body(raw)
            except urllib.error.HTTPError as e:
                raw = e.read() or b""
                if e.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        pass
                body = _parse_body(raw)
                if attempt == 0 and (e.code >= 500 or throttled(e.code, body)):
                    last_err = e
                    time.sleep(self.backoff)
                    continue
                return e.code, body
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = e
                if attempt == 0:
                    time.sleep(2.0)
                    continue
        raise FetchError(f"network error on {url}: {last_err}")


THROTTLE_HINTS = ("slow down", "rate limit", "too many requests", "throttle")


def throttled(status: int, body: Any) -> bool:
    """True when the provider says to slow down (429, or an error text that says so)."""
    if status == 429:
        return True
    text = (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).lower()
    return status >= 400 and any(h in text for h in THROTTLE_HINTS)


def _parse_body(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text[:2000]


def qs(params: Dict[str, Any]) -> str:
    return urllib.parse.urlencode([(k, v) for k, v in params.items() if v is not None and v != ""])


# ---------------------------------------------------------------- collector scaffolding

class Health:
    """Health of one collector run: ok, empty, error or quota."""

    def __init__(self, source: str, job: str, target: str):
        self.data: Dict[str, Any] = {
            "job_id": job, "source": source, "target": target, "status": "ok",
            "records": 0, "pages": 0, "requests": 0, "capped": False,
            "dropped_out_of_window": 0, "dropped_removed": 0, "dropped_duplicate": 0,
            "message": "", "errors": [],
        }

    def error(self, err: Exception) -> None:
        quota = isinstance(err, FetchError) and err.quota
        self.data["errors"].append(str(err)[:400])
        if quota:
            self.data["status"] = "quota"
        elif self.data["status"] != "quota":
            self.data["status"] = "error"

    def finish(self, records: int, requests: int, hint_empty: str = "") -> Dict[str, Any]:
        self.data["records"] = records
        self.data["requests"] = requests
        if self.data["status"] == "ok" and records == 0:
            self.data["status"] = "empty"
            self.data["message"] = hint_empty or "0 results in the window: an alert to look at, not proof of no signal"
        elif self.data["status"] in ("error", "quota") and not self.data["message"]:
            kept = f"{records} records kept before the failure" if records else "no record kept"
            self.data["message"] = f"{self.data['status']}: {kept}"
        return self.data


def add_common_args(p) -> None:
    p.add_argument("--since", help="window start, YYYY-MM-DD (inclusive)")
    p.add_argument("--until", help="window end, YYYY-MM-DD (inclusive), default today UTC")
    p.add_argument("--recency-days", type=int, default=90, help="window length when --since is absent (default 90)")
    p.add_argument("--limit", type=int, default=50, help="cap: records kept for this job (default 50)")
    p.add_argument("--max-pages", type=int, default=3, help="cap: result pages fetched (default 3)")
    p.add_argument("--job-id", default=None, help="job id written in the health file (default derived from the source)")
    p.add_argument("--out", required=True, help="corpus file to write (JSONL, one record per line)")
    p.add_argument("--health", default=None, help="health file to write (JSON), default <out>.health.json")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--fixtures", help="read frozen responses from this folder, no network")
    g.add_argument("--record", help="live run that also saves every response into this folder")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between live requests (default 1.0)")


def run_collector(args, source: str, target: str, gen, trim=None, hint_empty: str = "") -> int:
    """Shared driver: window, fetcher, dedupe, cap, window filter, health, exit code.

    gen(fetcher, since, until, health) yields records, newest first when the API allows.
    Exit 0 when the job ran (ok or empty), 1 on error or quota (partial records kept).
    """
    since, until = window_from(args.since, args.until, recency_days=args.recency_days)
    fetcher = Fetcher(fixtures=args.fixtures, record=args.record, delay=args.delay, trim=trim, source=source)
    job = args.job_id or f"{source}-{re.sub(r'[^a-z0-9]+', '-', target.lower()).strip('-')}"[:60]
    health = Health(source, job, target)
    health.data["window"] = {"since": since, "until": until}
    seen: set = set()
    rows: List[Dict[str, Any]] = []
    try:
        for rec in gen(fetcher, since, until, health):
            if rec["record_id"] in seen:
                health.data["dropped_duplicate"] += 1
                continue
            if is_removed(rec.get("text")):
                health.data["dropped_removed"] += 1
                continue
            if not in_window(rec.get("date"), since, until):
                health.data["dropped_out_of_window"] += 1
                continue
            seen.add(rec["record_id"])
            rows.append(rec)
            if len(rows) >= args.limit:
                health.data["capped"] = True
                break
    except FetchError as e:
        health.error(e)
    except (ValueError, KeyError, TypeError) as e:
        health.error(FetchError(f"unexpected response shape: {e!r}"))
    rows.sort(key=lambda r: r["record_id"])
    out = Path(args.out)
    write_jsonl(out, rows)
    data = health.finish(len(rows), fetcher.requests, hint_empty)
    data["fixtures"] = bool(args.fixtures)
    write_json(Path(args.health) if args.health else out.with_suffix(".health.json"), data)
    print(f"{job}: {data['status']}, {len(rows)} records, {data['pages']} pages, {fetcher.requests} requests"
          + (" (capped)" if data["capped"] else "") + (f": {data['message']}" if data["message"] else ""))
    return 0 if data["status"] in ("ok", "empty") else 1


# ---------------------------------------------------------------- schema validation

def load_validator():
    """Import validate() from shared/scripts/validate_json.py."""
    path = REPO / "shared" / "scripts"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    from validate_json import validate  # type: ignore
    return validate


def schema_errors(instance: Any, schema_name: str) -> List[str]:
    validate = load_validator()
    schema = read_json(ASSETS / schema_name)
    return validate(instance, schema)


def eprint(*a) -> None:
    print(*a, file=sys.stderr)


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
