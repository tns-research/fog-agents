#!/usr/bin/env python3
"""package_meta.py: ads.json + renders -> a Meta Ads package ready to import.

  python3 scripts/package_meta.py <ads.json> --renders <renders dir> [--out <dir>/meta]
      [--date YYYYMMDD] [--ledger <project>/static-ads-builder/creative-ledger.json]

Writes into --out (default <ads.json dir>/meta):
  ads-import-YYYYMMDD.csv   one row per ad and format: Campaign Name, Ad Set
                            Name, Ad Name, Ad Status (PAUSED: nothing goes
                            live by import), Title, Body, Link Description,
                            Call to Action, Link (destination with UTM),
                            URL Tags, Image File Name, Placements. Column
                            names follow the Ads Manager bulk-import sheet;
                            export a blank template from your Ads Manager
                            (Import ads in bulk) and align the headers to it
                            before importing, Meta renames columns over time.
  exports/<ad_set>/<ad name>.jpg   the upload files, one folder per ad set
  ad-copy.md                every text to paste, per ad, with lengths
  utm.csv                   ad name -> full tracked URL
and appends one line per ad and format to the creative ledger (default
<out>/creative-ledger.json), so perf.py can join next month's export back to
stage, angle, style and ratio by ad name.

Naming: <project>_<NN>_<stage>_<angle>_<style>_<ratio>, plus _t-<variable> on a
recipe variant (adspec.ad_name).
UTM: utm_source / utm_medium / utm_campaign from meta.utm (defaults
facebook / paid_social / meta.campaign), utm_content = ad name,
utm_term = ad set.

Checks (warnings, never blocks): Meta's feed guide recommends primary text of
50 to 150 characters and a headline of 27 characters
(https://www.facebook.com/business/ads-guide/update/image/facebook-feed,
read 2026-10-12); a missing meta_ad, render or end date on a dated offer.
Exit 0 when the package is written (warnings allowed), 1 when an ad has no
render or no meta_ad, 3 on unreadable input.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adspec  # noqa: E402

PRIMARY_RANGE = (50, 150)
HEADLINE_MAX = 27
PLACEMENTS = {"1:1": "Feed", "4:5": "Feed", "9:16": "Stories, Reels"}
COLUMNS = ["Campaign Name", "Ad Set Name", "Ad Name", "Ad Status", "Title", "Body", "Link Description",
           "Call to Action", "Link", "URL Tags", "Image File Name", "Placements"]


def utm_url(url: str, tags: Dict[str, str]) -> str:
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query))
    q.update(tags)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def package(spec_path: Path, renders: Path, out: Path, stamp: str, ledger: Path) -> Dict[str, Any]:
    spec = adspec.load_json(spec_path)
    meta = spec.get("meta", {})
    utm = meta.get("utm") or {}
    campaign = meta.get("campaign") or meta.get("project", "ads")
    out.mkdir(parents=True, exist_ok=True)
    rows: List[List[str]] = []
    md = [f"# Meta ad copy, {meta.get('project')} {stamp}", "",
          "Every ad imports as PAUSED. Review, then switch on in Ads Manager.", ""]
    problems: List[Dict[str, str]] = []
    led: List[Dict[str, Any]] = []
    utm_rows = []
    for i, ad in enumerate(spec.get("ads") or []):
        ma = ad.get("meta_ad")
        if not ma:
            problems.append({"level": "error", "ad": ad.get("id"), "message": "no meta_ad: primary text, headline, CTA and URL missing"})
            continue
        ad_set = ma.get("ad_set") or f"{ad.get('stage', 'all')}-default"
        body, title, desc = ma.get("primary_text", ""), ma.get("headline", ""), ma.get("description", "")
        if not PRIMARY_RANGE[0] <= len(body) <= PRIMARY_RANGE[1]:
            problems.append({"level": "warning", "ad": ad["id"], "message": f"primary text {len(body)} characters, Meta recommends {PRIMARY_RANGE[0]} to {PRIMARY_RANGE[1]}"})
        if len(title) > HEADLINE_MAX:
            problems.append({"level": "warning", "ad": ad["id"], "message": f"headline {len(title)} characters, Meta recommends {HEADLINE_MAX}"})
        md += [f"## {ad.get('n', i + 1):02d} {ad['id']} ({ad.get('stage', '').upper()}, {ad.get('angle')}, {ad.get('style')})", "",
               f"- Ad set: `{ad_set}`",
               f"- Primary text ({len(body)} characters): {body}",
               f"- Headline ({len(title)} characters): {title}",
               f"- Description: {desc or '(none)'}",
               f"- Call to action: `{ma.get('cta')}`"]
        if ma.get("end_date"):
            md.append(f"- Stop running on: {ma['end_date']}")
        if ad.get("extends"):
            md.append(f"- Extends: {ad['extends']['ad_name']} ({ad['extends']['why']})")
        for fmt in ad.get("formats") or []:
            name = adspec.ad_name(spec, ad, i, fmt)
            src = renders / f"{name}.jpg"
            if not src.exists():
                src = renders / f"{name}.png"
            if not src.exists():
                problems.append({"level": "error", "ad": ad["id"], "message": f"no render for {name}"})
                continue
            dest_dir = out / "exports" / ad_set
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{name}{src.suffix}"
            shutil.copyfile(src, dest)
            tags = {"utm_source": utm.get("source", "facebook"), "utm_medium": utm.get("medium", "paid_social"),
                    "utm_campaign": utm.get("campaign", campaign), "utm_content": name, "utm_term": ad_set}
            link = utm_url(ma["destination_url"], tags)
            rows.append([campaign, ad_set, name, "PAUSED", title, body, desc, ma.get("cta", ""), ma["destination_url"],
                         urlencode(tags), dest.name, PLACEMENTS[fmt]])
            utm_rows.append([name, link])
            md.append(f"- {fmt} ({PLACEMENTS[fmt]}): `exports/{ad_set}/{dest.name}`, link `{link}`")
            led.append({"ad_name": name, "date": meta.get("date"), "ad_id": ad["id"], "stage": ad.get("stage"), "angle": ad.get("angle"),
                        "style": ad.get("style"), "ratio": fmt, "ad_set": ad_set, "destination_url": ma["destination_url"],
                        "extends": (ad.get("extends") or {}).get("ad_name"), "test": (ad.get("test") or {}).get("variable"),
                        "file": f"exports/{ad_set}/{dest.name}"})
        md.append("")
    csv_path = out / f"ads-import-{stamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)
    with open(out / "utm.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Ad Name", "Tracked URL"])
        w.writerows(utm_rows)
    if problems:
        md += ["## Checks", ""] + [f"- {p['level'].upper()} {p['ad']}: {p['message']}" for p in problems]
    (out / "ad-copy.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    old: List[Dict[str, Any]] = []
    if ledger.exists():
        try:
            old = json.loads(ledger.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            old = []
    names = {r["ad_name"] for r in led}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps([r for r in old if r.get("ad_name") not in names] + led, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"csv": str(csv_path), "rows": len(rows), "problems": problems, "ledger": str(ledger)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="ads.json")
    ap.add_argument("--renders", required=True, help="Dir with the rendered JPG or PNG files")
    ap.add_argument("--out", help="Default <ads.json dir>/meta")
    ap.add_argument("--date", help="Stamp YYYYMMDD (default: meta.date)")
    ap.add_argument("--ledger", help="Creative ledger path (default <out>/creative-ledger.json)")
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    try:
        spec = adspec.load_json(spec_path)
    except Exception as e:  # noqa: BLE001
        print(f"package_meta: cannot read {spec_path}: {e}", file=sys.stderr)
        return 3
    stamp = a.date or (spec.get("meta", {}).get("date") or date.today().isoformat()).replace("-", "")
    out = Path(a.out).resolve() if a.out else spec_path.parent / "meta"
    r = package(spec_path, Path(a.renders).resolve(), out, stamp, Path(a.ledger).resolve() if a.ledger else out / "creative-ledger.json")
    for p in r["problems"]:
        print(f"{p['level']:5} {p['ad']}: {p['message']}")
    print(f"package_meta: {r['rows']} rows -> {r['csv']}")
    return 1 if any(p["level"] == "error" for p in r["problems"]) else 0


if __name__ == "__main__":
    sys.exit(main())
