#!/usr/bin/env python3
"""captions.py: word-by-word karaoke captions, lower third and end card, as ASS.

    python3 scripts/captions.py RUN/work/plan.json --clip ID --out RUN/work/<id>/subs.ass

Rules (each one fixed a visible defect on real shorts):

- Short groups: words_per_line words at most (default 3) and MAX_CHARS
  characters, a new group after a pause over GROUP_GAP s or a sentence end.
- The active word changes colour only (style.accent). Never a scale change: a
  scaled word re-centres the whole line on every word and reads as flicker.
- Contiguous tiling: each event ends exactly when the next one starts (same
  centisecond), a group holds at most HOLD s past its last word and never past
  the next group's start. No blank frame between words, no two events at once.
- Elisions re-merged: a token that starts with an apostrophe joins the previous
  one ("l" + "'IA" shows as L'IA).
- Placement inside the 9:16 safe area: captions above the bottom 20 % that
  platform UI covers; the lower third (speaker name and role, first seconds
  only) sits under them, above that line.
- The ASS Dialogue line is exactly Layer,Start,End,Style,MarginL,MarginR,
  MarginV,Effect,Text: one stray comma there prints a comma before every line.
- End card: when the clip's cta is enabled, a full-frame card in
  style.background dissolves in CTA_LEAD s after the last word and holds while
  the source keeps playing underneath. There is no intro card, by design.

Fonts: style.font must be installed (fontconfig); otherwise the file names
DejaVu Sans and the clip plan records a font-fallback warning.

Exit codes: 0 written; 1 unknown clip id; 2 unreadable plan.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EXIT_CHECK, OUT_H, OUT_W, PUNCT, ass_color, ends_sentence, is_elision_tail, load_json  # noqa: E402

MAX_CHARS = 18        # characters per caption line at CAPTION_SIZE on a 1080 px canvas
GROUP_GAP = 0.7       # s of silence that starts a new caption group
HOLD = 0.35           # s a group stays after its last word when nothing follows
CAPTION_SIZE = 84     # px, ASS PlayRes 1080x1920
LONG_WORD = 13        # characters: above this a single word gets a smaller size
CTA_LEAD = 0.10       # s between the last word and the end card dissolve
FALLBACK_FONT = "DejaVu Sans"
# Baseline of the caption line, from the bottom (ASS MarginV). The bottom 20 %
# (384 px) is covered by platform UI; captions sit above it with room for the
# lower third in between.
MARGIN_V = {"lower": 600, "middle": 820}
LOWER_THIRD_NAME_Y = 1446   # baseline of the speaker name (px from the top)
LOWER_THIRD_ROLE_Y = 1512   # baseline of the role, above the 1536 px safe line


def font_available(family: str) -> bool:
    if not shutil.which("fc-list"):
        return True  # cannot check; libass will fall back on its own
    r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True)
    fams = {f.strip().lower() for line in r.stdout.splitlines() for f in line.split(",")}
    return family.strip().lower() in fams


def tc(s: float) -> str:
    s = max(0.0, s)
    cs_total = int(round(s * 100))
    h, rem = divmod(cs_total, 360000)
    m, rem = divmod(rem, 6000)
    sec, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def ass_text(s: str) -> str:
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def clean(word: str, upper: bool) -> str:
    w = word.strip().replace("’", "'").strip(PUNCT.replace("'", ""))
    return w.upper() if upper else w


def group_words(words: List[Dict[str, Any]], per_line: int, upper: bool) -> List[List[Dict[str, Any]]]:
    merged: List[Dict[str, Any]] = []
    for w in words:
        if merged and is_elision_tail(w["word"]):
            merged[-1]["word"] = merged[-1]["word"].rstrip() + w["word"].strip()
            merged[-1]["end"] = w["end"]
            merged[-1]["raw_end"] = w["word"]
        else:
            merged.append({"word": w["word"], "start": w["start"], "end": w["end"], "raw_end": w["word"]})
    items = []
    for m in merged:
        t = clean(m["word"], upper)
        if t:
            items.append({"t": t, "start": m["start"], "end": m["end"], "stop": ends_sentence(m["raw_end"])})
    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for it in items:
        if cur:
            chars = sum(len(x["t"]) for x in cur) + len(cur) + len(it["t"])
            if len(cur) >= per_line or chars > MAX_CHARS or it["start"] - cur[-1]["end"] > GROUP_GAP or cur[-1]["stop"]:
                groups.append(cur)
                cur = []
        cur.append(it)
    if cur:
        groups.append(cur)
    return groups


def header(style: Dict[str, Any], font: str) -> str:
    white = ass_color(style["text"])
    black = "&H00000000"
    shadow = "&H96000000"
    bg = ass_color(style["background"])
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{CAPTION_SIZE},{white},{white},{black},{shadow},-1,0,0,0,100,100,1,0,1,6,3,2,90,90,{MARGIN_V.get(style.get('position', 'lower'), 600)},1
Style: Name,{font},64,{white},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,4,2,1,90,90,0,1
Style: Role,{font},46,{ass_color(style['accent'])},{white},{black},{shadow},-1,0,0,0,100,100,0,0,1,3,2,1,90,90,0,1
Style: Card,{font},76,{white},{white},{bg},{bg},-1,0,0,0,100,100,0,0,1,0,0,5,90,90,0,1
Style: CardLink,{font},60,{ass_color(style['accent'])},{white},{bg},{bg},-1,0,0,0,100,100,0,0,1,0,0,5,90,90,0,1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, MarginV, Effect, Text
"""


def build(plan: Dict[str, Any], clip: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    style = plan["style"]
    font = style.get("font") or FALLBACK_FONT
    info: Dict[str, Any] = {"font": font, "font_fallback": False}
    if not font_available(font):
        info.update({"font_fallback": True, "font_requested": font})
        font = FALLBACK_FONT
        info["font"] = font
    accent = ass_color(style["accent"]).replace("&H00", "&H")  # inline \1c takes &HBBGGRR&
    upper = bool(style.get("uppercase", True))
    groups = group_words(clip["words"], int(style.get("words_per_line", 3)), upper)
    lines: List[str] = []
    events: List[Tuple[float, float]] = []
    for gi, g in enumerate(groups):
        g_end = g[-1]["end"]
        nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else g_end + HOLD
        disp_end = min(g_end + HOLD, nxt)
        for wi, w in enumerate(g):
            a = w["start"]
            b = g[wi + 1]["start"] if wi + 1 < len(g) else disp_end
            b = min(b, disp_end)
            if b <= a:
                continue
            parts = []
            for k, ww in enumerate(g):
                txt = ass_text(ww["t"])
                size = f"\\fs{int(CAPTION_SIZE * LONG_WORD / len(ww['t']))}" if len(ww["t"]) > LONG_WORD else ""
                if k == wi:
                    parts.append(f"{{\\1c{accent}&{size}}}{txt}{{\\r}}")
                elif size:
                    parts.append(f"{{{size}}}{txt}{{\\r}}")
                else:
                    parts.append(txt)
            lines.append(f"Dialogue: 0,{tc(a)},{tc(b)},Cap,0,0,0,,{' '.join(parts)}")
            events.append((a, b))

    spk = plan.get("speaker") or {}
    if spk.get("name") or spk.get("role"):
        t1 = min(float(spk.get("show_seconds", 4.0)), clip["speech_end"])
        if t1 > 0.5:
            fade = "\\fad(250,350)"
            if spk.get("name"):
                lines.append(f"Dialogue: 1,{tc(0.15)},{tc(t1)},Name,0,0,0,,{{\\an1\\pos(90,{LOWER_THIRD_NAME_Y}){fade}}}{ass_text(spk['name'])}")
            if spk.get("role"):
                lines.append(f"Dialogue: 1,{tc(0.15)},{tc(t1)},Role,0,0,0,,{{\\an1\\pos(90,{LOWER_THIRD_ROLE_Y}){fade}}}{ass_text(spk['role'])}")

    cta = clip.get("cta") or {}
    card: Optional[Tuple[float, float]] = None
    if cta.get("enabled"):
        c0 = clip["speech_end"] + CTA_LEAD
        c1 = clip["duration"]
        if c1 - c0 > 0.3:
            card = (c0, c1)
            box = f"{{\\an7\\pos(0,0)\\bord0\\shad0\\fad(400,0)\\1c{ass_color(style['background']).replace('&H00', '&H')}&\\p1}}m 0 0 l {OUT_W} 0 l {OUT_W} {OUT_H} l 0 {OUT_H}{{\\p0}}"
            lines.append(f"Dialogue: 5,{tc(c0)},{tc(c1)},Card,0,0,0,,{box}")
            texts = list(cta.get("lines") or [])
            y = 860 - 50 * max(0, len(texts) - 1)
            for t in texts:
                lines.append(f"Dialogue: 6,{tc(c0)},{tc(c1)},Card,0,0,0,,{{\\an5\\pos({OUT_W // 2},{y})\\fad(400,0)}}{ass_text(t)}")
                y += 100
            if cta.get("url"):
                lines.append(f"Dialogue: 6,{tc(c0)},{tc(c1)},CardLink,0,0,0,,{{\\an5\\pos({OUT_W // 2},{y + 40})\\fad(400,0)}}{ass_text(cta['url'])}")

    first = events[0][0] if events else None
    gaps = sum(1 for (a0, b0), (a1, b1) in zip(events, events[1:]) if 0 < a1 - b0 < 0.02)
    overlaps = sum(1 for (a0, b0), (a1, b1) in zip(events, events[1:]) if a1 < b0 - 0.001)
    info.update({"groups": len(groups), "events": len(events), "first_caption": first,
                 "micro_gaps": gaps, "overlaps": overlaps, "card": card})
    return header(style, font) + "\n".join(lines) + "\n", info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="work/plan.json written by clipspec.py")
    ap.add_argument("--clip", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    plan = load_json(Path(args.plan))
    clip = next((c for c in plan.get("clips", []) if c["id"] == args.clip), None)
    if not clip:
        print(f"captions: no clip {args.clip!r} in the plan", file=sys.stderr)
        return EXIT_CHECK
    text, info = build(plan, clip)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"captions: {info['events']} events in {info['groups']} groups, font {info['font']}"
          + (" (fallback)" if info["font_fallback"] else "") + f" -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
