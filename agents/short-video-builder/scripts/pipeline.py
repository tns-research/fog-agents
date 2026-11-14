#!/usr/bin/env python3
"""pipeline.py: every clip of clips.json, rendered, measured and laid out for review.

    python3 scripts/pipeline.py RUN/clips.json [--out RUN] [--only id1,id2] [--quick]
                                [--allow-unproofread] [--project DIR] [--no-review]

1. clipspec.py: schema, intro-card ban, spans snapped and checked against the
   transcript and the source, hooks verbatim, copy through the writing gate.
   Any error: exit 1, nothing rendered.
2. Proofread gate: words.json must carry a valid signature (proofread.py sign).
   Missing or stale: exit 1, nothing rendered. --allow-unproofread renders
   drafts whose QA fails with not-proofread, so they can never ship by mistake.
3. Per clip: render.py (crop path, captions, ffmpeg), qa.py (measures), review
   frames, caption strip and contact sheets.
4. RUN/export/qa.json (every clip, every finding), RUN/review/first-frames.png,
   RUN/posts.md (per clip: file, hook, reason, title and post copy).

Exit codes: 0 every clip passes QA; 1 spec errors, gate not satisfied or a clip
with QA errors; 2 fatal (ffmpeg, OpenCV, unreadable source).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clipspec  # noqa: E402
import proofread  # noqa: E402
import qa as qa_mod  # noqa: E402
import render as render_mod  # noqa: E402
from common import EXIT_CHECK, OUT_H, OUT_W, fmt_time, write_json  # noqa: E402


def posts_md(plan: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    lines = ["# Shorts", ""]
    for c in plan["clips"]:
        r = next((x for x in results if x["id"] == c["id"]), None)
        if not r:
            continue
        lines += [
            f"## {c['id']}",
            "",
            f"- File: `export/{c['id']}.mp4` ({c['duration']:.1f} s, source {fmt_time(c['start'])}-{fmt_time(c['end'])})",
            f"- QA: {r['qa']['status']}" + (f", errors: {', '.join(e['code'] for e in r['qa']['errors'])}" if r["qa"]["errors"] else ""),
            f"- Hook (spoken, verbatim): {c['hook']}",
            f"- Why this excerpt: {c['reason']}",
        ]
        if c.get("title"):
            lines.append(f"- Title: {c['title']}")
        if c.get("post"):
            lines += ["", c["post"]]
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="clips.json")
    ap.add_argument("--out", help="Run folder (default: the spec's folder)")
    ap.add_argument("--only", help="Comma-separated clip ids")
    ap.add_argument("--quick", action="store_true", help="Fast preview encode (ultrafast, crf 28, no sub-pixel pan)")
    ap.add_argument("--allow-unproofread", action="store_true", help="Render drafts before the proofread signature (QA fails)")
    ap.add_argument("--project", help="Project folder for the writing gate's project pack")
    ap.add_argument("--no-review", action="store_true", help="Skip review frames and contact sheets")
    args = ap.parse_args()

    t0 = time.time()
    spec = Path(args.spec).resolve()
    run_dir = Path(args.out).resolve() if args.out else spec.parent
    plan = clipspec.resolve(spec, args.project)
    write_json(run_dir / "work" / "plan.json", plan)
    clipspec.print_report(plan)
    if plan["status"] != "pass":
        print("pipeline: spec errors, nothing rendered (fix clips.json, rerun)")
        return EXIT_CHECK
    ok, why = proofread.gate(Path(plan["transcript"]))
    print(f"proofread: {why}")
    if not ok and not args.allow_unproofread:
        print("pipeline: transcript not proofread, nothing rendered")
        return EXIT_CHECK

    wanted = set(args.only.split(",")) if args.only else None
    clips = [c for c in plan["clips"] if not wanted or c["id"] in wanted]
    if wanted and len(clips) != len(wanted):
        print(f"pipeline: unknown clip id in --only ({sorted(wanted - {c['id'] for c in clips})})")
        return EXIT_CHECK
    results = []
    firsts = run_dir / "review" / "first-frames"
    if firsts.exists():
        shutil.rmtree(firsts)
    firsts.mkdir(parents=True)
    for c in clips:
        info = render_mod.render_clip(plan, c, run_dir, args.quick, not ok)
        expect = {
            "fps": plan["fps"], "duration": c["duration"], "frames": info["frames"],
            "target_lufs": plan["audio"]["target_lufs"], "true_peak": plan["audio"]["true_peak"],
            "captions": info["captions"], "track": info["track"], "unproofread": info["unproofread"],
            "logo_skipped": info["captions"].get("logo_skipped"),
        }
        res = qa_mod.check(Path(info["file"]), expect)
        if plan.get("timing") == "estimated":
            res["warnings"].append({"code": "timing-estimated", "message": "karaoke timed from cue-level subtitles: check sync on the caption strip"})
        review = None
        if not args.no_review:
            review = qa_mod.review_assets(Path(info["file"]), run_dir / "review" / c["id"], c["duration"],
                                          info["captions"].get("first_caption") or 0.0, f"{c['id']} ({c['duration']:.1f} s)")
            if review["frames"]:
                shutil.copyfile(review["frames"][0], firsts / f"{c['id']}.jpg")
        entry = {"id": c["id"], "file": info["file"], "render": info, "qa": res, "review": review}
        write_json(run_dir / "export" / f"{c['id']}.json", entry)
        results.append(entry)
        print(f"clip {c['id']}: qa {res['status']}, {len(res['errors'])} error(s) {[e['code'] for e in res['errors']]}, "
              f"{len(res['warnings'])} warning(s) {[w['code'] for w in res['warnings']]}, "
              f"{res['probe']['fps'] if 'probe' in res else '?'} fps, {res.get('loudness', {}).get('integrated')} LUFS, "
              f"render {info['seconds']} s")

    if not args.no_review and qa_mod.CONTACT_SHEET.exists():
        subprocess.run([sys.executable, str(qa_mod.CONTACT_SHEET), str(firsts), "-o", str(run_dir / "review" / "first-frames.png"),
                        "--expect", f"{OUT_W}x{OUT_H}", "--scale", "feed", "--title", "First frame of every short"],
                       capture_output=True, text=True)
    status = "pass" if all(r["qa"]["status"] == "pass" for r in results) else "fail"
    summary = {
        "spec": str(spec),
        "status": status,
        "fps": plan["fps"],
        "fps_note": plan["fps_note"],
        "proofread": why,
        "quick": args.quick,
        "spec_warnings": plan["warnings"],
        "clips": [{"id": r["id"], "file": r["file"], "status": r["qa"]["status"], "errors": r["qa"]["errors"],
                   "warnings": r["qa"]["warnings"], "loudness": r["qa"].get("loudness"),
                   "track": r["render"]["track"]} for r in results],
        "seconds": round(time.time() - t0, 1),
    }
    write_json(run_dir / "export" / "qa.json", summary)
    (run_dir / "posts.md").write_text(posts_md(plan, results), encoding="utf-8")
    print(f"pipeline: {status}, {len(results)} clip(s) in {summary['seconds']} s -> {run_dir / 'export'}")
    return 0 if status == "pass" else EXIT_CHECK


if __name__ == "__main__":
    sys.exit(main())
