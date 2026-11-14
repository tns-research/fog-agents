#!/usr/bin/env python3
"""proofread.py: blind transcription of every rendered ad, diffed word by word.

The DOM check in qa.py proves the HTML holds the right words. It cannot see
what the pixels show: a glyph missing from a font, a word hidden behind a
shape, or the text printed on a product photo or a generated plate
(packaging, labels, signs). A batch rendered by an image model shipped
"DELICESSE" for "DELICATESSE" and "NAISSIS" for "VANILLE" on a jam label.
This step makes a reviewer copy every visible word of every PNG without
seeing ads.json, then compares the copy with ads.json.

  # 1. Packet for the reviewer (no expected text in it: the read is blind)
  python3 scripts/proofread.py packet <renders dir> [--out <dir>/proofread]

  # 2. The reviewer fills proofread/transcript.json (one entry per PNG)
  #    [{"file": "<name>.png", "text": "every word seen, any order",
  #      "unreadable": false, "notes": ""}]

  # 3. Diff against ads.json (through html/expected.json)
  python3 scripts/proofread.py check <html dir> <transcript.json> [--out proofread.json]

Expected words per render = the DOM copy + media visible_text (labels,
packaging, UI) + the logo wordmark. Comparison: NFC, case and accents kept,
edge punctuation ignored, typographic apostrophes equal straight ones, word
order free (columns make reading order ambiguous).

Verdict per render:
  TEXT_OK              every expected word seen, nothing else
  TEXT_MISMATCH        a word of the copy is misspelled, missing or extra
  ASSET_TEXT_MISMATCH  a word printed on the media differs (label, packaging)
  TEXT_UNREADABLE      the reviewer could not read some text: a human looks
  NOT_PROOFREAD        the render has no transcript entry
Every verdict but TEXT_OK is a BLOCK. Exit 0 when all TEXT_OK, 1 on any
BLOCK, 3 on unreadable input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adspec  # noqa: E402

REVIEWER_RULES = """You proofread rendered ads you did not make. You have the PNG files only.

For every file, write down EVERY word you can see, exactly as it is drawn:
- the big text, the small text, the button, the source line, the logo wordmark;
- every word printed on a product, a label, a package, a sign, a shirt, a
  screen or any object in a photo, even tiny, even if it looks like decoration;
- keep the spelling, accents and capitals you see, even when they look wrong.
  Never correct toward what the ad probably meant;
- any order is fine; punctuation does not matter;
- when a word is too small, cut, blurred or low contrast to read with
  certainty, set "unreadable": true and say where in "notes". Never guess.

Open each PNG at full size. Do not open ads.json, the HTML or any brief before
the transcript is written: the point is to read what the pixels say.

Answer by filling transcript.json: one object per file,
{"file": "<file name>", "text": "<every word>", "unreadable": false, "notes": ""}.
"""


def cmd_packet(renders: Path, out: Path) -> int:
    pngs = sorted(p.name for p in renders.glob("*.png") if not p.name.startswith("contact-sheet"))
    if not pngs:
        print(f"proofread: no PNG in {renders}", file=sys.stderr)
        return 3
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Proofread packet", "", REVIEWER_RULES, "## Files", ""]
    lines += [f"- `{renders / n}`" for n in pngs]
    (out / "packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tpl = [{"file": n, "text": "", "unreadable": False, "notes": ""} for n in pngs]
    (out / "transcript.template.json").write_text(json.dumps(tpl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"proofread: packet for {len(pngs)} renders -> {out / 'packet.md'}; fill {out / 'transcript.json'}")
    return 0


def check(html_dir: Path, transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    exp = json.loads((html_dir / "expected.json").read_text(encoding="utf-8"))["sections"]
    by_file = {Path(str(t.get("file", ""))).stem: t for t in transcript}
    results = []
    for e in exp:
        t = by_file.get(e["name"])
        dom = adspec.tokens(" ".join(e["dom"]))
        media = adspec.tokens(" ".join(e["media"]))
        logo = adspec.tokens(" ".join(e["logo"]))
        rec: Dict[str, Any] = {"file": e["name"] + ".png", "ad": e.get("ad"), "format": e.get("format")}
        if t is None:
            rec.update(verdict="NOT_PROOFREAD", diff=None)
            results.append(rec)
            continue
        seen = adspec.tokens(str(t.get("text", "")))
        d = adspec.word_diff(dom + media + logo, seen)
        media_set = set(media)
        asset = [p for p in d["misspelled"] if p["expected"] in media_set] + [{"expected": m, "observed": None, "kind": "missing"} for m in d["missing"] if m in media_set]
        if t.get("unreadable"):
            verdict = "TEXT_UNREADABLE"
        elif d["ok"]:
            verdict = "TEXT_OK"
        elif asset:
            verdict = "ASSET_TEXT_MISMATCH"
        else:
            verdict = "TEXT_MISMATCH"
        rec.update(verdict=verdict, diff={k: v for k, v in d.items() if k != "ok"}, words_expected=len(dom + media + logo), words_seen=len(seen),
                   notes=t.get("notes", ""))
        results.append(rec)
    known = {e["name"] for e in exp}
    stray = [t.get("file") for t in transcript if Path(str(t.get("file", ""))).stem not in known]
    blocks = [r for r in results if r["verdict"] != "TEXT_OK"]
    return {"status": "pass" if not blocks else "block", "renders": len(results), "blocks": len(blocks),
            "stray_entries": stray, "results": results}


def cmd_check(html_dir: Path, tpath: Path, out: Path) -> int:
    try:
        transcript = json.loads(tpath.read_text(encoding="utf-8"))
        assert isinstance(transcript, list) and all(isinstance(t, dict) for t in transcript)
    except Exception as e:  # noqa: BLE001
        print(f"proofread: cannot read {tpath}: {e}", file=sys.stderr)
        return 3
    if not (html_dir / "expected.json").exists():
        print(f"proofread: no expected.json in {html_dir}, run build.py first", file=sys.stderr)
        return 3
    r = check(html_dir, transcript)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for x in r["results"]:
        if x["verdict"] == "TEXT_OK":
            continue
        d = x.get("diff") or {}
        parts = [f"{p['expected']} -> {p['observed']} ({p['kind']})" for p in d.get("misspelled", [])]
        parts += [f"missing '{m}'" for m in d.get("missing", [])] + [f"extra '{w}'" for w in d.get("extra", [])]
        print(f"BLOCK {x['verdict']} {x['file']}: {'; '.join(parts) or x.get('notes', '')}")
    print(f"proofread: {r['status'].upper()}, {r['renders'] - r['blocks']}/{r['renders']} TEXT_OK -> {out}")
    return 0 if r["status"] == "pass" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("packet", help="Write the blind reviewer packet and a transcript template")
    p.add_argument("renders")
    p.add_argument("--out", help="Default <renders>/../proofread")
    c = sub.add_parser("check", help="Diff a transcript against ads.json")
    c.add_argument("html", help="build.py output dir (holds expected.json)")
    c.add_argument("transcript")
    c.add_argument("--out", help="Default <html>/../proofread/proofread.json")
    a = ap.parse_args()
    if a.cmd == "packet":
        r = Path(a.renders).resolve()
        return cmd_packet(r, Path(a.out).resolve() if a.out else r.parent / "proofread")
    h = Path(a.html).resolve()
    return cmd_check(h, Path(a.transcript).resolve(), Path(a.out).resolve() if a.out else h.parent / "proofread" / "proofread.json")


if __name__ == "__main__":
    sys.exit(main())
