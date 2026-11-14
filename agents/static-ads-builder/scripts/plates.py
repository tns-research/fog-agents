#!/usr/bin/env python3
"""plates.py: text-free photo backgrounds, the only job left to an image model.

Every word, logo, product and screenshot of an ad is set by the HTML. When a
concept needs a photographic scene nobody has (a kitchen at dawn, a crowded
desk), the ad declares a media of role "plate" with a scene prompt. This
script turns those plates into briefs for scripts/render_ads.py, so the two
spend gates of that script apply unchanged (estimate, explicit confirmation
of model, resolution and spend, one attempt, no auto-retry), and the manual
provider writes a pack for the founder's own tool at no cost.

  python3 scripts/plates.py prepare <ads.json> [--out <ads dir>/plates]
  python3 scripts/plates.py status  <ads.json> [--out <ads dir>/plates]

prepare writes <out>/plate-briefs-<ratio>.json (one file per aspect ratio, the
tallest format the ad uses: 9:16 > 4:5 > 1:1; plates render with fit cover,
so the other formats crop a plate made for the ad, never a real photo) and
prints the render_ads.py commands: --estimate first (Gate 2), --batch after
the founder's explicit yes, or --provider manual. Each prompt gets a fixed
suffix: no text, no letters, no logo, no product, no watermark.

status checks that every plate file exists where ads.json points
(media.src, by convention plates/<NN>-<id>.jpg) and lists founder-dropped
files (NN-<anything>.jpg|png|webp) that match an ad number.

Exit 0 when nothing is missing (prepare: briefs written), 1 when a plate is
missing (status), 3 on unreadable input. No network, no key.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adspec  # noqa: E402

SUFFIX = ("No text, no letters, no numbers, no logo, no signage, no product, no packaging, no watermark. "
          "Leave calm areas where type can sit. Photographic, natural light, real textures.")
RANK = {"1:1": 0, "4:5": 1, "9:16": 2}
EXTS = (".jpg", ".jpeg", ".png", ".webp")


def slug(text: str, maxlen: int = 35) -> str:
    """Same slug as render_ads.py, so the file it writes is the file ads.json expects."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "brief"


def plates(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for i, ad in enumerate(spec.get("ads") or []):
        for m in ad.get("media") or []:
            if m.get("role") != "plate":
                continue
            n = adspec.ad_number(ad, i)
            ratio = max(ad.get("formats") or ["4:5"], key=lambda f: RANK.get(f, 0))
            out.append({"n": n, "id": ad["id"], "ratio": ratio, "prompt": (m.get("prompt") or "").strip(),
                        "src": m.get("src") or f"plates/{n:02d}-{slug(ad['id'])}.jpg",
                        "expected": f"plates/{n:02d}-{slug(ad['id'])}.jpg"})
    return out


def cmd_prepare(spec_path: Path, spec: Dict[str, Any], out: Path) -> int:
    ps = plates(spec)
    if not ps:
        print("plates: no media of role plate in ads.json; nothing to generate, nothing to spend.")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    by_ratio: Dict[str, List[Dict[str, Any]]] = {}
    for p in ps:
        if p["src"] != p["expected"]:
            print(f"warn  ad {p['id']}: media.src is {p['src']}, render_ads.py will write {p['expected']}")
        by_ratio.setdefault(p["ratio"], []).append({"image_prompt": f"{p['prompt']} {SUFFIX}", "headline": "", "subheadline": "",
                                                    "_brief_n": p["n"], "_concept": p["id"]})
    rel = lambda q: q.relative_to(Path.cwd()) if q.is_relative_to(Path.cwd()) else q  # noqa: E731
    for ratio, briefs in by_ratio.items():
        f = out / f"plate-briefs-{ratio.replace(':', 'x')}.json"
        f.write_text(json.dumps(briefs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        sel = ",".join(str(b["_brief_n"]) for b in briefs)
        print(f"\n{len(briefs)} plate(s) at {ratio}: {f}")
        print(f"  Gate 2 estimate : python3 scripts/render_ads.py --estimate --provider <fal|openai> --count {len(briefs)} --model <model> --resolution 1K")
        print(f"  after an explicit yes on model, resolution and spend:")
        print(f"  python3 scripts/render_ads.py --batch {rel(f)} --select \"{sel}\" --out {rel(out)} --ratio {ratio} --provider <fal|openai> --model <model> --resolution 1K --confirm-spend")
        print(f"  no spend        : python3 scripts/render_ads.py --batch {rel(f)} --select \"{sel}\" --out {rel(out)} --ratio {ratio} --provider manual")
    return 0


def cmd_status(spec_path: Path, spec: Dict[str, Any], out: Path) -> int:
    missing = 0
    for p in plates(spec):
        target = (spec_path.parent / p["src"]).resolve()
        if target.is_file() and target.stat().st_size > 0:
            print(f"ok    ad {p['id']}: {p['src']}")
            continue
        dropped = [q for q in sorted(out.glob(f"{p['n']:02d}-*")) if q.suffix.lower() in EXTS] if out.is_dir() else []
        missing += 1
        hint = f"; founder file found: {dropped[0].relative_to(spec_path.parent)} (set media.src to it)" if dropped else ""
        print(f"MISSING ad {p['id']}: {p['src']}{hint}")
    return 1 if missing else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "status"])
    ap.add_argument("spec", help="ads.json")
    ap.add_argument("--out", help="Plates dir (default <ads.json dir>/plates)")
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    try:
        spec = adspec.load_json(spec_path)
    except Exception as e:  # noqa: BLE001
        print(f"plates: cannot read {spec_path}: {e}", file=sys.stderr)
        return 3
    out = Path(a.out).resolve() if a.out else spec_path.parent / "plates"
    return cmd_prepare(spec_path, spec, out) if a.cmd == "prepare" else cmd_status(spec_path, spec, out)


if __name__ == "__main__":
    sys.exit(main())
