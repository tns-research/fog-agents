#!/usr/bin/env python3
"""pipeline.py: ads.json -> exact PNG/JPEG renders, QA, proofread packet, Meta package.

  python3 scripts/pipeline.py <ads.json> [--out DIR] [--brand brand.json] [--only id1,id2]
      [--transcript proofread/transcript.json] [--package] [--width 1080|1440] [--no-sheet]

Runs, in order, the deterministic steps of the agent (0 $, no key):
  1. build.py    ads.json + brand.json -> DIR/html (spec errors listed)
  2. render.py   -> DIR/renders/<ad name>.png and .jpg, exact sizes
  3. qa.py       -> DIR/renders/qa.json and contact-sheet.jpg
  4. proofread.py packet -> DIR/proofread/packet.md (blind reviewer brief);
     with --transcript, proofread.py check -> DIR/proofread/proofread.json
  5. with --package, package_meta.py -> DIR/meta/ (import CSV, exports,
     ad copy, UTM, creative ledger)
DIR defaults to the folder of ads.json.

Exit 0 when the build has no error, QA passes and (with --transcript) every
render is TEXT_OK; 1 otherwise; 2 when ads.json cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import package_meta  # noqa: E402
import proofread  # noqa: E402
import qa  # noqa: E402
import render  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", help="Output dir (default: the ads.json folder)")
    ap.add_argument("--brand")
    ap.add_argument("--only", help="Comma-separated ad ids")
    ap.add_argument("--transcript", help="Reviewer transcript to diff (proofread check)")
    ap.add_argument("--package", action="store_true", help="Write the Meta package")
    ap.add_argument("--width", type=int, default=1080, choices=[1080, 1440], help="Render width (1440 = Meta feed recommendation)")
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    if not spec_path.exists():
        print(f"pipeline: {spec_path} not found", file=sys.stderr)
        return 2
    base = Path(a.out).resolve() if a.out else spec_path.parent
    html, renders, pr = base / "html", base / "renders", base / "proofread"
    t0 = time.time()
    rep = build.build(spec_path, html, a.brand, a.only.split(",") if a.only else None)
    for e in rep["errors"]:
        print(f"ERROR build {e['code']} {e['where']}: {e['message']}")
    if not rep.get("sections"):
        print("pipeline: nothing to render (spec unreadable or empty)")
        return 2
    rr = render.render(html, renders, True, a.width)
    q = qa.run(html, renders, renders / "qa.json", not a.no_sheet)
    qa.print_summary(q)
    proofread.cmd_packet(renders, pr)
    ok = q["status"] == "pass" and not rep["errors"] and not rr["errors"]
    if a.transcript:
        code = proofread.cmd_check(html, Path(a.transcript).resolve(), pr / "proofread.json")
        ok = ok and code == 0
    if a.package:
        stamp = (json.loads(spec_path.read_text(encoding="utf-8")).get("meta", {}).get("date") or "").replace("-", "") or time.strftime("%Y%m%d")
        r = package_meta.package(spec_path, renders, base / "meta", stamp, base / "meta" / "creative-ledger.json")
        for p in r["problems"]:
            print(f"{p['level']:5} package {p['ad']}: {p['message']}")
        print(f"package: {r['rows']} rows -> {r['csv']}")
        ok = ok and not any(p["level"] == "error" for p in r["problems"])
    print(f"pipeline: {'PASS' if ok else 'FAIL'}, {len(rr['files'])} renders in {time.time() - t0:.1f} s -> {base}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
