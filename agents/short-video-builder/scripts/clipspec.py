#!/usr/bin/env python3
"""clipspec.py: validate clips.json and resolve it into a render plan.

    python3 scripts/clipspec.py RUN/clips.json [--plan RUN/work/plan.json] [--project DIR] [--json]

Checks, in order:
  1. Schema (assets/clips.schema.json, through shared/scripts/validate_json.py).
     Any intro, title or hook card key is refused with its own code: a short
     opens on the speaker, never on a card.
  2. Against the source and the transcript, per clip: the span is ordered and
     inside the source; it is snapped onto word boundaries (never half a word,
     never a dangling elision); its length is within duration_limits; it holds
     speech; it opens on its hook, word for word; it starts and ends on a
     sentence boundary (warnings); the hook lands fast; the end card has text.
  3. Across clips: unique ids, heavy overlaps (warning).
  4. Copy (title, post, end card lines) through the shared writing gate
     (shared/skills/writing-gate/scripts/lint_copy.py): a BLOCK is an error.
     The hook is never linted: it is the speaker's words, verbatim.

Writes the resolved plan (snapped times, words per clip on the clip timeline,
style with brand.json applied, output frame rate) to --plan (default
<spec dir>/work/plan.json), even when there are errors, so they can be read.

Error codes: schema, intro-card, source-missing, transcript-missing, span-order,
out-of-source, no-speech, too-short, too-long, hook-mismatch, cta-empty,
duplicate-id, copy:<rule>. Warning codes: starts-mid-sentence,
ends-mid-sentence, slow-hook, overlap, cta-short, timing-estimated,
copy-lint-unavailable, brand-json-missing.

Exit codes: 0 no error (warnings allowed); 1 errors listed with their clip and
code; 2 unreadable spec, transcript or source.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (AGENT, EXIT_CHECK, SHARED, die, ends_sentence, fmt_time, is_elision_tail,  # noqa: E402
                    load_json, load_words, norm_token, output_fps, parse_time, probe, rel_or_abs, write_json)

SCHEMA = AGENT / "assets" / "clips.schema.json"
LINT = SHARED / "skills" / "writing-gate" / "scripts" / "lint_copy.py"

DEFAULT_LIMITS = {"min_seconds": 15.0, "max_seconds": 60.0}
DEFAULT_STYLE = {
    "accent": "#FFD400",       # neutral caption yellow; the brand accent replaces it
    "text": "#FFFFFF",
    "background": "#111111",
    "font": "Inter",
    "uppercase": True,
    "words_per_line": 3,
    "position": "lower",
    "logo": None,
    "progress_bar": True,
}
DEFAULT_AUDIO = {"target_lufs": -14.0, "true_peak": -1.5, "denoise": True}
DEFAULT_CTA = {"enabled": False, "lines": [], "url": "", "seconds": 2.5}
DEFAULT_SPEAKER_SECONDS = 4.0

HEAD_PAD = 0.12    # s of silence kept before the first word when there is room
TAIL_PAD = 0.25    # s kept after the last word: speech recognisers stamp word ends early
GUARD = 0.06       # s always left against a neighbouring word
CTA_LEAD = 0.10    # s between the last word and the end card dissolve
SENTENCE_GAP = 0.35  # s of silence that counts as a sentence boundary without punctuation
SLOW_HOOK = 6.0    # s: a hook longer than this is spoken too slowly to stop a scroll
HOOK_MATCH_WORDS = 12  # leading words of the hook compared with the clip's first words
INTRO_KEYS = {"intro", "intro_card", "title_card", "hook_card", "opening_card", "intro_seconds"}


def shared_validate():
    sys.path.insert(0, str(SHARED / "scripts"))
    try:
        from validate_json import validate  # type: ignore
        return validate
    except ImportError:
        die("shared/scripts/validate_json.py not found: copy shared/ next to agents/")


def find_intro_keys(obj: Any, path: str = "") -> List[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k in INTRO_KEYS:
                out.append(p)
            out += find_intro_keys(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += find_intro_keys(v, f"{path}[{i}]")
    return out


def snap_span(start: float, end: float, words: List[Dict[str, Any]]) -> Tuple[float, float, int, int]:
    """Move a raw span onto word boundaries. Returns (start, end, first word, last word)."""
    hit = next((w for w in words if w["start"] < start < w["end"]), None)
    if hit:
        start = hit["start"] if (start - hit["start"]) <= (hit["end"] - start) else hit["end"]
    i0 = next((i for i, w in enumerate(words) if w["start"] >= start - 0.001), len(words) - 1)
    while i0 > 0 and is_elision_tail(words[i0]["word"]):
        i0 -= 1
    lo = words[i0 - 1]["end"] + GUARD if i0 > 0 else 0.0
    s = max(min(words[i0]["start"], start), lo, words[i0]["start"] - HEAD_PAD)
    s = min(s, words[i0]["start"])

    hit_i = next((i for i, w in enumerate(words) if w["start"] < end < w["end"]), None)
    if hit_i is None:
        hit_i = next((i for i in range(len(words) - 1, -1, -1) if words[i]["end"] <= end + 0.001), 0)
    i1 = hit_i
    while i1 + 1 < len(words) and is_elision_tail(words[i1 + 1]["word"]):
        i1 += 1
    hi = words[i1]["end"] + TAIL_PAD
    if i1 + 1 < len(words):
        hi = min(hi, max(words[i1]["end"], words[i1 + 1]["start"] - GUARD))
    e = max(hi, words[i1]["end"])
    return s, e, i0, i1


def merged_tokens(raw: List[str]) -> List[str]:
    out: List[str] = []
    for w in raw:
        if out and is_elision_tail(w):
            out[-1] = out[-1] + norm_token(w)
        else:
            t = norm_token(w)
            if t:
                out.append(t)
    return out


def resolve_style(spec: Dict[str, Any], base: Path, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    style = dict(DEFAULT_STYLE)
    given = dict(spec.get("style") or {})
    bj = given.pop("brand_json", None)
    if bj:
        p = rel_or_abs(base, bj)
        if p.exists():
            brand = load_json(p)
            colors = brand.get("colors") or {}
            fonts = brand.get("fonts") or {}
            for key, src in (("accent", "accent"), ("text", "text"), ("background", "bg")):
                if colors.get(src):
                    style[key] = colors[src]
            fam = ((fonts.get("body") or {}).get("family"))
            if fam:
                style["font"] = fam
        else:
            warnings.append({"clip": None, "code": "brand-json-missing", "message": f"{bj} not found, default style used"})
    style.update({k: v for k, v in given.items() if v is not None})
    if style.get("logo"):
        style["logo"] = str(rel_or_abs(base, style["logo"]))
    return style


def lint_copy(items: List[Tuple[str, str]], lang: Optional[str], project: Optional[str],
              errors: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> str:
    """items: (clip id or '*', text). Returns the gate status: pass, fail, unavailable or empty."""
    items = [(c, t.replace("\n", " ").strip()) for c, t in items if t and t.strip()]
    if not items:
        return "empty"
    if not LINT.exists():
        warnings.append({"clip": None, "code": "copy-lint-unavailable", "message": "shared writing gate not found: apply its checklist by hand"})
        return "unavailable"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("\n".join(t for _, t in items) + "\n")
        tmp = f.name
    cmd = [sys.executable, str(LINT), "--json", tmp]
    if lang in ("en", "fr"):
        cmd[2:2] = ["--lang", lang]
    if project:
        cmd[2:2] = ["--project", project]
    r = subprocess.run(cmd, capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        warnings.append({"clip": None, "code": "copy-lint-unavailable", "message": f"writing gate output unreadable: {r.stderr.strip()[:120]}"})
        return "unavailable"
    for fi in report.get("files", []):
        for hit in fi.get("findings", []):
            clip, text = items[hit["line"] - 1]
            entry = {"clip": None if clip == "*" else clip, "code": f"copy:{hit['code']}",
                     "message": f"{hit['match']!r} in {text[:60]!r}: {hit['message']}"}
            (errors if hit["level"] == "BLOCK" else warnings).append(entry)
    return report.get("status", "unknown")


def resolve(spec_path: Path, project: Optional[str] = None) -> Dict[str, Any]:
    spec = load_json(spec_path)
    base = spec_path.parent
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    for p in find_intro_keys(spec):
        errors.append({"clip": None, "code": "intro-card",
                       "message": f"{p}: no intro, title or hook card. The short opens on the speaker's first words; put the hook in what they say, and the title in the post."})
    validate = shared_validate()
    for msg in validate(spec, load_json(SCHEMA)):
        errors.append({"clip": None, "code": "schema", "message": msg})
    if errors:
        return {"spec": str(spec_path), "status": "fail", "errors": errors, "warnings": warnings, "clips": []}

    source = rel_or_abs(base, spec["source"])
    transcript = rel_or_abs(base, spec["transcript"])
    if not source.exists():
        errors.append({"clip": None, "code": "source-missing", "message": f"source video not found: {source}"})
    if not transcript.exists():
        errors.append({"clip": None, "code": "transcript-missing", "message": f"transcript not found: {transcript} (run transcribe.py)"})
    if errors:
        return {"spec": str(spec_path), "status": "fail", "errors": errors, "warnings": warnings, "clips": []}

    info = probe(source)
    if not info.get("has_video"):
        die(f"{source} has no video stream")
    if not info.get("has_audio"):
        die(f"{source} has no audio stream: a talk short needs the speaker's voice")
    duration = info["duration"]
    fps_str, fps, fps_note = output_fps(info)
    tdoc = load_words(transcript)
    words = tdoc["words"]
    if tdoc.get("timing") == "estimated":
        warnings.append({"clip": None, "code": "timing-estimated",
                         "message": "word times were estimated from cue times: karaoke highlight may drift; transcribe locally for exact timing"})

    limits = dict(DEFAULT_LIMITS)
    limits.update(spec.get("duration_limits") or {})
    style = resolve_style(spec, base, warnings)
    audio = dict(DEFAULT_AUDIO)
    audio.update(spec.get("audio") or {})
    speaker = dict(spec.get("speaker") or {})
    if speaker:
        speaker.setdefault("show_seconds", DEFAULT_SPEAKER_SECONDS)
    cta_global = dict(DEFAULT_CTA)
    cta_global.update(spec.get("cta") or {})

    clips_out: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    copy_items: List[Tuple[str, str]] = [("*", line) for line in cta_global.get("lines", [])]
    for n, c in enumerate(spec["clips"]):
        cid = c["id"]
        if cid in seen:
            errors.append({"clip": cid, "code": "duplicate-id", "message": f"clips {seen[cid]} and {n} share the id {cid}"})
        seen[cid] = n
        s_raw, e_raw = parse_time(c["start"]), parse_time(c["end"])
        if e_raw <= s_raw:
            errors.append({"clip": cid, "code": "span-order", "message": f"end {fmt_time(e_raw)} is not after start {fmt_time(s_raw)}"})
            continue
        if s_raw >= duration or e_raw > duration + 0.05:
            errors.append({"clip": cid, "code": "out-of-source",
                           "message": f"{fmt_time(s_raw)}-{fmt_time(e_raw)} is outside the source (0:00-{fmt_time(duration)})"})
            continue
        inside = [w for w in words if w["end"] > s_raw and w["start"] < e_raw]
        if not inside:
            errors.append({"clip": cid, "code": "no-speech", "message": f"no transcribed word between {fmt_time(s_raw)} and {fmt_time(e_raw)}"})
            continue
        s, e, i0, i1 = snap_span(s_raw, e_raw, words)
        e = min(e, duration)
        span_words = words[i0:i1 + 1]
        notes = []
        if abs(s - s_raw) > 0.02 or abs(e - e_raw) > 0.02:
            notes.append(f"snapped {fmt_time(s_raw)}-{fmt_time(e_raw)} to {fmt_time(s)}-{fmt_time(e)}")
        length = e - s
        if length < limits["min_seconds"]:
            errors.append({"clip": cid, "code": "too-short", "message": f"{length:.1f} s, under {limits['min_seconds']:g} s"})
        if length > limits["max_seconds"]:
            errors.append({"clip": cid, "code": "too-long", "message": f"{length:.1f} s, over {limits['max_seconds']:g} s"})

        hook_toks = merged_tokens(c["hook"].split())
        clip_toks = merged_tokens([w["word"] for w in span_words])
        k = min(len(hook_toks), HOOK_MATCH_WORDS)
        if clip_toks[:k] != hook_toks[:k]:
            opening = " ".join(w["word"] for w in span_words[:max(k, 4)])
            errors.append({"clip": cid, "code": "hook-mismatch",
                           "message": f"the clip opens on {opening!r} but the hook is {c['hook']!r}: move start to the hook, or copy the hook verbatim from the proofread transcript"})
        else:
            # time the hook takes to say: from the first word to the end of the hook's last word
            count, j = 0, i0
            while j <= i1 and count < len(hook_toks):
                if not is_elision_tail(words[j]["word"]):
                    count += 1
                j += 1
            hook_secs = words[min(j - 1, i1)]["end"] - words[i0]["start"]
            if hook_secs > SLOW_HOOK:
                warnings.append({"clip": cid, "code": "slow-hook", "message": f"the hook takes {hook_secs:.1f} s to say; a shorter first sentence stops the scroll better"})

        if i0 > 0 and not ends_sentence(words[i0 - 1]["word"]) and words[i0]["start"] - words[i0 - 1]["end"] < SENTENCE_GAP:
            warnings.append({"clip": cid, "code": "starts-mid-sentence",
                             "message": f"previous word {words[i0 - 1]['word']!r} runs straight into the first one"})
        if not ends_sentence(words[i1]["word"]) and i1 + 1 < len(words) and words[i1 + 1]["start"] - words[i1]["end"] < SENTENCE_GAP:
            warnings.append({"clip": cid, "code": "ends-mid-sentence",
                             "message": f"ends on {words[i1]['word']!r} while the speaker goes on with {words[i1 + 1]['word']!r}"})

        cta = dict(cta_global)
        cta.update(c.get("cta") or {})
        if c.get("cta"):
            copy_items += [(cid, line) for line in (c["cta"].get("lines") or [])]
        speech_end = words[i1]["end"] - s
        render_end = e
        if cta.get("enabled"):
            if not cta.get("lines") and not cta.get("url"):
                errors.append({"clip": cid, "code": "cta-empty", "message": "end card enabled with no lines and no url"})
            render_end = min(duration, max(e, s + speech_end + CTA_LEAD + float(cta["seconds"])))
            shown = render_end - s - (speech_end + CTA_LEAD)
            if shown < 1.0:
                warnings.append({"clip": cid, "code": "cta-short", "message": f"the source ends {shown:.1f} s after the last word: the end card barely shows"})
        for key in ("title", "post"):
            if c.get(key):
                copy_items.append((cid, c[key]))
        rel = []
        for w in span_words:
            item = {"word": w["word"], "start": round(max(0.0, w["start"] - s), 3), "end": round(max(0.0, w["end"] - s), 3)}
            rel.append(item)
        clips_out.append({
            "id": cid,
            "start": round(s, 3),
            "end": round(e, 3),
            "render_end": round(render_end, 3),
            "duration": round(render_end - s, 3),
            "speech_end": round(speech_end, 3),
            "first_word": round(words[i0]["start"] - s, 3),
            "words_index": [i0, i1],
            "hook": c["hook"],
            "reason": c["reason"],
            "title": c.get("title"),
            "post": c.get("post"),
            "framing": c.get("framing") or {"mode": "track"},
            "cta": cta,
            "words": rel,
            "notes": notes,
        })

    for a in range(len(clips_out)):
        for b in range(a + 1, len(clips_out)):
            x, y = clips_out[a], clips_out[b]
            inter = min(x["end"], y["end"]) - max(x["start"], y["start"])
            shorter = min(x["end"] - x["start"], y["end"] - y["start"])
            if inter > 0 and inter / shorter > 0.5:
                warnings.append({"clip": y["id"], "code": "overlap",
                                 "message": f"shares {inter:.1f} s with {x['id']}: two shorts of the same moment"})

    copy_status = lint_copy(copy_items, spec.get("language") or tdoc.get("language"), project, errors, warnings)
    return {
        "spec": str(spec_path),
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "source": str(source),
        "transcript": str(transcript),
        "source_info": {k: info.get(k) for k in ("width", "height", "duration", "r_frame_rate", "avg_frame_rate", "sample_rate", "rotation")},
        "fps": fps_str,
        "fps_float": fps,
        "fps_note": fps_note,
        "timing": tdoc.get("timing", "word"),
        "language": spec.get("language") or tdoc.get("language"),
        "limits": limits,
        "style": style,
        "audio": audio,
        "speaker": speaker,
        "copy_gate": copy_status,
        "clips": clips_out,
    }


def print_report(plan: Dict[str, Any]) -> None:
    for e in plan["errors"]:
        print(f"ERROR   {e.get('clip') or '-':24} {e['code']:22} {e['message']}")
    for w in plan["warnings"]:
        print(f"warning {w.get('clip') or '-':24} {w['code']:22} {w['message']}")
    for c in plan.get("clips", []):
        card = " with end card" if (c.get("cta") or {}).get("enabled") else ""
        print(f"clip    {c['id']:24} {fmt_time(c['start'])}-{fmt_time(c['end'])} ({c['duration']:.1f} s{card})"
              + (f"  [{'; '.join(c['notes'])}]" if c["notes"] else ""))
    if plan.get("fps"):
        print(f"output  {plan['fps']} fps ({plan['fps_note']}), copy gate {plan.get('copy_gate')}")
    print(f"clipspec: {plan['status']}, {len(plan['errors'])} error(s), {len(plan['warnings'])} warning(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="clips.json")
    ap.add_argument("--plan", help="Where to write the resolved plan (default <spec dir>/work/plan.json)")
    ap.add_argument("--project", help="Project folder for the writing gate's project pack")
    ap.add_argument("--json", action="store_true", help="Print the plan as JSON")
    args = ap.parse_args()
    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        die(f"spec not found: {spec_path}")
    plan = resolve(spec_path, args.project)
    out = Path(args.plan) if args.plan else spec_path.parent / "work" / "plan.json"
    write_json(out, plan)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=1))
    else:
        print_report(plan)
    return 0 if plan["status"] == "pass" else EXIT_CHECK


if __name__ == "__main__":
    sys.exit(main())
