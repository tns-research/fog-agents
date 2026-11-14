"""
gp_lib.py

Shared helpers of the growth-pulse scripts. Python 3.9+, standard library only.

  - dates and ISO weeks (Monday to Sunday), the default 6-week window
  - CSV reading (delimiter sniffing, comment lines, BOM), number and date parsing
  - the source-file contract every connector writes (assets/source.schema.json)
  - HTTP with fixture replay (--fixtures DIR), so API code paths run offline in tests
  - the common connector runner: provider choice (api, csv, none), health, exit codes
  - JSON Schema validation through shared/scripts/validate_json.py when the repo is complete

Never prints or writes a key value.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
ASSETS = AGENT / "assets"
REPO = AGENT.parent.parent
SHARED_SCRIPTS = REPO / "shared" / "scripts"

SOURCES = ("plausible", "umami", "ga4", "gsc", "social", "revenue")
HTTP_TIMEOUT_S = 30  # one API call; a slower provider is reported as an error, never retried in a loop


class InputError(Exception):
    """Unreadable input or bad arguments: exit code 2."""


class ProviderError(Exception):
    """The provider answered with an error or not at all: the source is reported as error."""


# ------------------------------------------------------------------ dates and weeks

def parse_day(s: Optional[str]) -> dt.date:
    if not s:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        raise InputError(f"bad date {s!r}, expected YYYY-MM-DD")


def week_id(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start(wid: str) -> dt.date:
    m = re.fullmatch(r"(\d{4})-W(\d{2})", wid or "")
    if not m:
        raise InputError(f"bad ISO week {wid!r}, expected YYYY-Www")
    return dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)


def last_complete_week(today: dt.date) -> str:
    """The last Monday-to-Sunday week that ended before today."""
    return week_id(today - dt.timedelta(days=today.isoweekday()))


def window(today: dt.date, weeks: int, week: Optional[str] = None) -> Tuple[dt.date, dt.date]:
    """since (Monday) and until (Sunday) of the `weeks` weeks ending with the report week."""
    wid = week or last_complete_week(today)
    end = week_start(wid) + dt.timedelta(days=6)
    start = week_start(wid) - dt.timedelta(days=7 * (weeks - 1))
    return start, end


def days_between(since: dt.date, until: dt.date) -> List[dt.date]:
    return [since + dt.timedelta(days=i) for i in range((until - since).days + 1)]


DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d",
                "%b %d, %Y", "%d %b %Y", "%B %d, %Y")


def parse_date_cell(s: str, fmt: Optional[str] = None) -> Optional[dt.date]:
    """Dates as exports write them. Slash dates are read MM/DD/YYYY (US exports such as
    LinkedIn) unless the first part is above 12; pass --date-format to force it."""
    s = (s or "").strip().strip('"')
    if not s:
        return None
    if fmt:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ]", s)
    if m:
        s = m.group(1)
    m = re.match(r"^(\d{1,2}[/.]\d{1,2}[/.]\d{4})[T ,]", s)
    if m:
        s = m.group(1)
    for f in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        month, day = (b, a) if a > 12 else (a, b)
        try:
            return dt.date(y, month, day)
        except ValueError:
            return None
    return None


# ------------------------------------------------------------------ numbers and CSV

NUM_CLEAN_RE = re.compile(r"[\s  %€$£]|EUR|USD|GBP", re.I)


def parse_number(s: Any) -> Optional[float]:
    """'1,234' '1 234' '3,2 %' '12.50 EUR' '' -> float or None. A lone comma with up to
    two digits after it is a decimal comma; otherwise commas are thousands separators."""
    if s is None:
        return None
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    t = NUM_CLEAN_RE.sub("", str(s))
    if t in ("", "-", "--", "n/a", "N/A"):
        return None
    if "," in t and "." not in t and re.fullmatch(r"-?\d+,\d{1,2}", t):
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").replace("﻿", "").strip().strip('"').lower())


def read_csv(path: str) -> List[Dict[str, str]]:
    """Rows as dicts with normalized headers. Skips '#' comment lines (GA4 exports) and
    blank lines; sniffs comma, semicolon or tab."""
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror}")
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return []
    head = lines[0]
    delim = max([",", ";", "\t"], key=lambda d: head.count(d))
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delim)
    rows = list(reader)
    headers = [norm_header(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        out.append({headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))})
    return out


def pick_column(headers: Iterable[str], aliases: List[str]) -> Optional[str]:
    hs = list(headers)
    for a in aliases:
        if a in hs:
            return a
    return None


# ------------------------------------------------------------------ JSON, hashing

def read_json(path: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror}")
    except json.JSONDecodeError as e:
        raise InputError(f"{path} is not JSON: {e}")


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_json(path: Any, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(obj), encoding="utf-8")


def write_text(path: Any, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def sha256_file(path: Any) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


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


def rnd(v: Optional[float], digits: int = 1) -> Optional[float]:
    """Rounded for the JSON output; whole numbers are written as integers."""
    if v is None:
        return None
    r = round(float(v), digits)
    return int(r) if r.is_integer() else r


def num(v: float) -> Any:
    """Integers stay integers in the JSON output."""
    return int(v) if float(v).is_integer() else round(float(v), 4)


# ------------------------------------------------------------------ schema validation

def schema_errors(instance: Any, schema_name: str) -> Optional[List[str]]:
    """Errors against assets/<schema_name>, or None when the shared validator is absent
    (the agent folder was copied without shared/)."""
    if not (SHARED_SCRIPTS / "validate_json.py").exists():
        return None
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    from validate_json import validate  # type: ignore
    return validate(instance, read_json(ASSETS / schema_name))


# ------------------------------------------------------------------ HTTP with fixture replay

def http_json(url: str, *, key: str, fixtures: Optional[str], headers: Optional[Dict[str, str]] = None,
              body: Optional[Dict[str, Any]] = None, form: Optional[Dict[str, str]] = None,
              method: Optional[str] = None) -> Any:
    """One JSON call. With fixtures, reads <fixtures>/<key>.json instead (no network):
    a fixture holding {"_http_error": 429} replays an error."""
    if fixtures:
        p = Path(fixtures) / f"{key}.json"
        if not p.exists():
            raise ProviderError(f"fixture {p.name} missing")
        data = read_json(p)
        if isinstance(data, dict) and "_http_error" in data:
            raise ProviderError(f"HTTP {data['_http_error']} (fixture)")
        return data
    h = {"accept": "application/json", "user-agent": "growth-pulse/1.0"}
    h.update(headers or {})
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        h["content-type"] = "application/json"
    elif form is not None:
        payload = urllib.parse.urlencode(form).encode("utf-8")
        h["content-type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=payload, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ProviderError(f"HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError(f"no answer from {urllib.parse.urlsplit(url).netloc}: {getattr(e, 'reason', e)}")
    except json.JSONDecodeError:
        raise ProviderError(f"{urllib.parse.urlsplit(url).netloc} did not answer JSON")


def env_set(*names: str) -> Optional[str]:
    """Name of the first environment variable that is set (never its value)."""
    for n in names:
        if os.environ.get(n):
            return n
    return None


# ------------------------------------------------------------------ source file contract

class Daily:
    """Accumulates summable daily values: values[date][metric] += x."""

    def __init__(self) -> None:
        self.values: Dict[dt.date, Dict[str, float]] = {}

    def add(self, day: Optional[dt.date], metric: str, x: Optional[float]) -> None:
        if day is None or x is None:
            return
        d = self.values.setdefault(day, {})
        d[metric] = d.get(metric, 0.0) + float(x)

    def touch(self, day: Optional[dt.date]) -> None:
        if day is not None:
            self.values.setdefault(day, {})


def build_source(source: str, provider: str, since: dt.date, until: dt.date, daily: Daily,
                 breakdowns: Optional[List[Dict[str, Any]]] = None, notes: Optional[List[str]] = None,
                 status: Optional[str] = None, message: str = "", today: Optional[dt.date] = None,
                 fill_zero: Optional[List[str]] = None) -> Dict[str, Any]:
    """The source file (assets/source.schema.json). Days inside [since, until] with no row
    are missing days; a metric absent on a day that has a row is 0 when listed in
    fill_zero (event counts), else absent."""
    all_days = days_between(since, until)
    present = sorted(d for d in daily.values if since <= d <= until)
    metrics = sorted({m for d in present for m in daily.values[d]} | set(fill_zero or []))
    rows = []
    for d in present:
        vals = dict(daily.values[d])
        for m in fill_zero or []:
            vals.setdefault(m, 0.0)
        rows.append({"date": d.isoformat(), "values": {k: num(vals[k]) for k in sorted(vals)}})
    # a source without any data lists no missing day: days_with_data 0 says it all
    missing = [d.isoformat() for d in all_days if d not in daily.values] if present else []
    if status is None:
        if not present:
            status = "error" if provider != "none" else "missing"
        elif missing:
            # days missing only at the end of the window: the provider has not caught up
            # (an export made too early, or the reporting lag of Search Console)
            tail = [d.isoformat() for d in all_days[-len(missing):]]
            status = "stale" if missing == tail else "partial"
        else:
            status = "ok"
    if not message:
        message = {"ok": "complete", "partial": f"{len(missing)} day(s) missing inside the window",
                   "stale": f"data ends before {until.isoformat()}: {len(missing)} day(s) missing at the end",
                   "missing": "no provider", "error": "no data"}[status]
    return {
        "schema_version": "1.0",
        "source": source,
        "provider": provider,
        "status": status,
        "message": message,
        "generated_on": (today or dt.date.today()).isoformat(),
        "range": {"since": since.isoformat(), "until": until.isoformat()},
        "days_with_data": len(present),
        "missing_days": missing,
        "metrics": metrics,
        "daily": rows,
        "breakdowns": breakdowns or [],
        "notes": notes or [],
    }


# ------------------------------------------------------------------ connector runner

def add_common_args(ap, csv_help: str) -> None:
    ap.add_argument("--today", help="run date, YYYY-MM-DD (default: today); the window ends with the last complete ISO week before it")
    ap.add_argument("--week", help="report week instead of the last complete one, e.g. 2026-W41")
    ap.add_argument("--weeks", type=int, default=6, help="weeks of data to fetch, ending with the report week (default 6)")
    ap.add_argument("--since", help="explicit start date (overrides --weeks)")
    ap.add_argument("--until", help="explicit end date (overrides the report week)")
    ap.add_argument("--provider", choices=["auto", "api", "csv"], default="auto",
                    help="auto: the CSV when one is given, else the API when its key is set, else a 'missing' health file")
    ap.add_argument("--csv", nargs="+", default=[], help=csv_help)
    ap.add_argument("--fixtures", help="replay recorded API responses from this folder (tests, no network)")
    ap.add_argument("--out", required=True, help="source file to write, e.g. <run>/data/umami.json")


def resolve_window(args) -> Tuple[dt.date, dt.date, dt.date]:
    today = parse_day(args.today)
    since, until = window(today, args.weeks, args.week)
    if args.since:
        since = parse_day(args.since)
    if args.until:
        until = parse_day(args.until)
    if since > until:
        raise InputError("--since is after --until")
    return today, since, until


def run_connector(source: str, args, *, has_api: Callable[[], Optional[str]], api: Callable[..., Dict[str, Any]],
                  from_csv: Optional[Callable[..., Dict[str, Any]]], how_to_export: str) -> int:
    """Pick the provider, run it, write the source file, return the exit code.

    Exit codes: 0 data written (status ok, partial or stale), 1 health file written without
    data (status missing or error), 2 usage error or unreadable input (nothing written)."""
    try:
        today, since, until = resolve_window(args)
        provider = args.provider
        if provider == "auto":
            if args.csv and from_csv:
                provider = "csv"
            elif args.fixtures or has_api():
                provider = "api"
            else:
                provider = "none"
        if provider == "csv" and (not args.csv or not from_csv):
            raise InputError(f"--provider csv needs --csv FILE ({how_to_export})")
        if provider == "api" and not (args.fixtures or has_api()):
            out = build_source(source, "api", since, until, Daily(), status="missing", today=today,
                               message=f"no API key set: {how_to_export}")
            write_json(args.out, out)
            print(f"{source}: missing (no API key). {how_to_export}", file=sys.stderr)
            return 1
        if provider == "none":
            out = build_source(source, "none", since, until, Daily(), status="missing", today=today,
                               message=f"not configured, no API key and no CSV: {how_to_export}")
            write_json(args.out, out)
            print(f"{source}: missing. {how_to_export}", file=sys.stderr)
            return 1
        try:
            if provider == "csv":
                out = from_csv(args, since, until, today)
            else:
                out = api(args, since, until, today)
        except ProviderError as e:
            out = build_source(source, provider if provider == "csv" else ("fixture" if args.fixtures else "api"),
                               since, until, Daily(), status="error", today=today,
                               message=f"{e}; fallback: {how_to_export}")
            write_json(args.out, out)
            print(f"{source}: error: {e}", file=sys.stderr)
            return 1
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    errs = schema_errors(out, "source.schema.json")
    if errs:
        print(f"error: internal: source file fails its schema: {errs[:3]}", file=sys.stderr)
        return 2
    write_json(args.out, out)
    print(f"{source}: {out['status']} via {out['provider']}, {out['days_with_data']} day(s), "
          f"{len(out['metrics'])} metric(s) -> {args.out}")
    return 0 if out["status"] in ("ok", "partial", "stale") else 1


def event_key(name: str) -> str:
    """Event names become metric ids: lowercase, spaces and dots to underscores."""
    return "event." + re.sub(r"[^a-z0-9_\-]+", "_", name.strip().lower()).strip("_")
