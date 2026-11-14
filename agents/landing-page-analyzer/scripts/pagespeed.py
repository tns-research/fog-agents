#!/usr/bin/env python3
"""
Core Web Vitals fetch for the landing-page-analyzer agent.

Standard library only (Python 3.8+). Two providers:
  psi         the public PageSpeed Insights API v5 (mobile strategy), no key
              needed at low volume
  lighthouse  a local Lighthouse run through npx (needs Node and Chrome, no key)
  auto        psi, then lighthouse if psi fails (default)

Writes two files:

  psi-mobile.json   the raw API response
  psi-summary.json  the values the LEVER grid needs (U023 to U028)

Field data (real Chrome users, CrUX) is used when Google has it for the URL,
otherwise the lab values from Lighthouse. The summary says which one.

Usage:
  python3 pagespeed.py <output_dir> <url> [--provider auto|psi|lighthouse]

The API works without a key at low volume. Set PAGESPEED_API_KEY to raise the quota
(free key: https://developers.google.com/speed/docs/insights/v5/get-started).
"""

import json
import os
import shutil
import subprocess
import tempfile
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
TIMEOUT_S = 120

# Good thresholds from web.dev (https://web.dev/articles/vitals).
THRESHOLDS = {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}


def _web_opener():
    """HTTP and HTTPS handlers only: no file://, ftp:// or data: handler, redirects included."""
    opener = urllib.request.OpenerDirector()
    for handler in (urllib.request.ProxyHandler(), urllib.request.UnknownHandler(),
                    urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
                    urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPRedirectHandler(),
                    urllib.request.HTTPErrorProcessor()):
        opener.add_handler(handler)
    return opener


def open_http(url, timeout):
    """urlopen restricted to http and https URLs."""
    if urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https"):
        raise ValueError("refused {!r}: only http and https URLs are fetched".format(url[:120]))
    return _web_opener().open(url, timeout=timeout)


def fetch(url, strategy):
    if urllib.parse.urlsplit(url).scheme.lower() not in ("http", "https"):
        raise ValueError("refused {!r}: PageSpeed tests http and https pages only".format(url[:120]))
    params = [("url", url), ("strategy", strategy), ("category", "performance")]
    key = os.environ.get("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    request_url = "{}?{}".format(API, urllib.parse.urlencode(params))
    with open_http(request_url, TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def field_metric(data, name):
    metric = data.get("loadingExperience", {}).get("metrics", {}).get(name)
    return metric.get("percentile") if metric else None


def lab_value(data, audit):
    return data.get("lighthouseResult", {}).get("audits", {}).get(audit, {}).get("numericValue")


def summarize(data):
    field = {
        "lcp_ms": field_metric(data, "LARGEST_CONTENTFUL_PAINT_MS"),
        "inp_ms": field_metric(data, "INTERACTION_TO_NEXT_PAINT"),
        "cls": field_metric(data, "CUMULATIVE_LAYOUT_SHIFT_SCORE"),
    }
    if field["cls"] is not None:
        field["cls"] = field["cls"] / 100.0
    lab = {
        "lcp_ms": lab_value(data, "largest-contentful-paint"),
        "tbt_ms": lab_value(data, "total-blocking-time"),
        "cls": lab_value(data, "cumulative-layout-shift"),
    }
    has_field = field["lcp_ms"] is not None
    values = field if has_field else lab
    values = {k: (None if v is None else (round(v, 3) if k == "cls" else int(round(v)))) for k, v in values.items()}
    score = data.get("lighthouseResult", {}).get("categories", {}).get("performance", {}).get("score")
    checks = {}
    for name, limit in THRESHOLDS.items():
        value = values.get(name)
        checks[name] = None if value is None else value <= limit
    return {
        "source": "field (CrUX, p75)" if has_field else "lab (Lighthouse, INP not measurable in lab, TBT given instead)",
        "values": values,
        "passes_good_threshold": checks,
        "lighthouse_performance_score": None if score is None else round(score * 100),
    }


def find_playwright_chrome():
    """Chromium installed by `playwright install chromium`, reused so Lighthouse needs no extra browser."""
    import glob
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
        os.path.join(home, "Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        os.path.join(home, "AppData/Local/ms-playwright/chromium-*/chrome-win/chrome.exe"),
    ]
    for pattern in patterns:
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def run_lighthouse(url):
    """Local Lighthouse run. Returns a dict shaped like a PSI response (lab data only)."""
    if not shutil.which("npx"):
        raise RuntimeError("npx not found (install Node.js to use local Lighthouse)")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "lh.json")
        cmd = [
            "npx", "--yes", "lighthouse", url,
            "--only-categories=performance", "--form-factor=mobile",
            "--output=json", "--output-path={}".format(out),
            "--chrome-flags=--headless=new --no-sandbox", "--quiet",
        ]
        env = dict(os.environ)
        if not env.get("CHROME_PATH"):
            chrome = find_playwright_chrome()
            if chrome:
                env["CHROME_PATH"] = chrome
        result = subprocess.run(cmd, timeout=300, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0:
            tail = result.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
            raise RuntimeError("lighthouse exited {}: {}".format(result.returncode, " | ".join(tail)))
        with open(out, encoding="utf-8") as f:
            return {"lighthouseResult": json.load(f)}


def parse_args(argv):
    provider = "auto"
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == "--provider" and i + 1 < len(argv):
            provider = argv[i + 1]
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    return rest, provider


def main():
    args, provider = parse_args(sys.argv[1:])
    if len(args) < 2 or provider not in ("auto", "psi", "lighthouse"):
        print("Usage: python3 pagespeed.py <output_dir> <url> [--provider auto|psi|lighthouse]")
        sys.exit(1)
    output_dir = Path(args[0])
    url = args[1].strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    order = ["psi", "lighthouse"] if provider == "auto" else [provider]
    data = None
    used = None
    for name in order:
        try:
            data = fetch(url, "mobile") if name == "psi" else run_lighthouse(url)
            used = name
            break
        except Exception as e:
            print("{} failed: {}".format(name, e))
    if data is None:
        print("No page_speed provider worked. Score rows U023 to U028 as Unverified and list them in Limitations,")
        print("or ask the founder to paste LCP, INP and CLS from https://pagespeed.web.dev")
        sys.exit(2)
    (output_dir / "psi-mobile.json").write_text(json.dumps(data), encoding="utf-8")
    summary = summarize(data)
    summary["provider"] = used
    (output_dir / "psi-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
