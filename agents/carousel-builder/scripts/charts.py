"""charts.py: data-viz blocks as inline SVG, styled by the direction CSS.

Rules baked in (references/design-rules.md, "Data-viz"):
- one accent only, on the value that carries the message (`highlight`), every
  other mark in the direction's chart greys;
- direct labels on the marks, no legend box;
- the unit lives in the chart title (build.py appends it);
- linear scale, zero always included for bars;
- the source line is printed by build.py in the slide footer and the build
  fails without one (deck.schema.json makes `source` required).

Colours come from CSS classes, never from hex in the SVG, so a direction or a
brand recolours every chart: .c-bar, .c-bar.is-hl, .c-label, .c-value,
.c-axis, .c-tick, .c-grid, .c-line, .c-line.is-hl, .c-dot, .c-seg, .c-seg.is-hl,
.c-center, .c-center-label, .c-swatch.

All sizes are in viewBox units with a 1000-unit width. The SVG is drawn for
the aspect ratio of the box the direction gives charts (direction.json
chart_box), so 1 unit is about 0.9 px on a 1080 slide.
"""

from __future__ import annotations

import html
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

VW = 1000.0

# Font sizes in viewBox units. On a 1080 px slide the chart box is about
# 900 px wide, so 34 units render near 31 px: legible at feed scale.
F_LABEL = 34
F_VALUE = 36
F_TICK = 28


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def fmt(v: Optional[float], decimals: Optional[int], lang: str, suffix: str = "") -> str:
    if v is None:
        return ""
    if decimals is None:
        decimals = 0 if float(v).is_integer() else 1
    s = f"{v:,.{decimals}f}"
    if lang.startswith("fr"):
        s = s.replace(",", " ").replace(".", ",")
    elif lang.startswith(("de", "es", "it", "pt", "nl")):
        s = s.replace(",", " ").replace(".", ",")
    return s + (suffix or "")


def text_w(s: str, size: float) -> float:
    """Rough advance width of a string. Conservative (wide) on purpose."""
    w = 0.0
    for ch in s:
        if ch in "il.,:;!|'":
            w += 0.30
        elif ch in "mwMW@%":
            w += 0.86
        elif ch.isupper() or ch.isdigit():
            w += 0.64
        elif ch == " ":
            w += 0.28
        else:
            w += 0.54
    return w * size


def nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * base >= v:
            return m * base
    return 10 * base


def svg_open(vh: float, label: str) -> str:
    return (f'<svg class="chart-svg" viewBox="0 0 {VW:.0f} {vh:.0f}" preserveAspectRatio="xMidYMid meet" '
            f'role="img" aria-label="{esc(label)}" xmlns="http://www.w3.org/2000/svg">')


# --------------------------------------------------------------------------
# Bar
# --------------------------------------------------------------------------

def bar_chart(b: Dict[str, Any], aspect: float, lang: str) -> str:
    data = [d for d in (b.get("data") or []) if isinstance(d, dict) and isinstance(d.get("value"), (int, float))]
    hl = b.get("highlight")
    dec = b.get("decimals")
    suf = b.get("value_suffix", "")
    n = len(data)
    if n == 0:
        return ""
    orient = b.get("orientation", "auto")
    if orient == "auto":
        short = all(len(str(d["label"])) <= 7 for d in data)
        orient = "vertical" if (short and n <= 8) else "horizontal"
    # Ranked bars read best sorted; columns usually carry an order (time,
    # steps) that sorting would break, so they keep the given order.
    sort = b.get("sort", "desc" if orient == "horizontal" else "none")
    if sort == "desc":
        data = sorted(data, key=lambda d: -d["value"])
    elif sort == "asc":
        data = sorted(data, key=lambda d: d["value"])
    vh = VW / aspect
    lo = min(0.0, min(d["value"] for d in data))
    hi = max(0.0, max(d["value"] for d in data))
    if hi == lo:
        hi = lo + 1
    parts = [svg_open(vh, b.get("title", "chart"))]

    if orient == "horizontal":
        labels_above = n <= 6
        val_w = max(text_w(fmt(d["value"], dec, lang, suf), F_VALUE) for d in data) + 22
        if labels_above:
            x0 = 0.0
            row_h = vh / n
            bar_h = min(row_h * 0.42, 70)
        else:
            lab_w = min(VW * 0.42, max(text_w(str(d["label"]), F_LABEL) for d in data) + 24)
            x0 = lab_w
            row_h = vh / n
            bar_h = min(row_h * 0.62, 64)
        span = VW - x0 - val_w
        scale = span / (hi - lo)
        zero_x = x0 + (0 - lo) * scale
        for i, d in enumerate(data):
            is_hl = " is-hl" if d["label"] == hl else ""
            top = i * row_h
            if labels_above:
                ly = top + row_h * 0.5 - bar_h * 0.5 - 12
                by = ly + 14
                parts.append(f'<text class="c-label{is_hl}" x="0" y="{ly:.1f}" font-size="{F_LABEL}">{esc(d["label"])}</text>')
            else:
                by = top + (row_h - bar_h) / 2
                parts.append(f'<text class="c-label{is_hl}" x="{x0 - 18:.1f}" y="{by + bar_h / 2:.1f}" dominant-baseline="central" '
                             f'text-anchor="end" font-size="{F_LABEL}">{esc(d["label"])}</text>')
            v = d["value"]
            x_a, x_b = sorted((zero_x, zero_x + v * scale))
            w = max(x_b - x_a, 2)
            parts.append(f'<rect class="c-bar{is_hl}" x="{x_a:.1f}" y="{by:.1f}" width="{w:.1f}" height="{bar_h:.1f}"/>')
            vx = x_b + 14 if v >= 0 else x_a - 14
            anchor = "start" if v >= 0 else "end"
            parts.append(f'<text class="c-value{is_hl}" x="{vx:.1f}" y="{by + bar_h / 2:.1f}" dominant-baseline="central" '
                         f'text-anchor="{anchor}" font-size="{F_VALUE}">{esc(fmt(v, dec, lang, suf))}</text>')
        parts.append(f'<line class="c-axis" x1="{zero_x:.1f}" y1="0" x2="{zero_x:.1f}" y2="{vh:.1f}"/>')
    else:
        lab_h = F_LABEL * 1.9
        val_h = F_VALUE * 1.6
        plot_top = val_h
        plot_h = vh - lab_h - val_h
        col_w = VW / n
        bar_w = min(col_w * 0.62, 150)
        scale = plot_h / (hi - lo)
        zero_y = plot_top + hi * scale
        for i, d in enumerate(data):
            is_hl = " is-hl" if d["label"] == hl else ""
            cx = col_w * i + col_w / 2
            v = d["value"]
            y_a, y_b = sorted((zero_y, zero_y - v * scale))
            h = max(y_b - y_a, 2)
            parts.append(f'<rect class="c-bar{is_hl}" x="{cx - bar_w / 2:.1f}" y="{y_a:.1f}" width="{bar_w:.1f}" height="{h:.1f}"/>')
            vy = y_a - 14 if v >= 0 else y_b + F_VALUE
            parts.append(f'<text class="c-value{is_hl}" x="{cx:.1f}" y="{vy:.1f}" text-anchor="middle" font-size="{F_VALUE}">{esc(fmt(v, dec, lang, suf))}</text>')
            parts.append(f'<text class="c-label{is_hl}" x="{cx:.1f}" y="{vh - lab_h * 0.28:.1f}" text-anchor="middle" font-size="{F_LABEL}">{esc(d["label"])}</text>')
        parts.append(f'<line class="c-axis" x1="0" y1="{zero_y:.1f}" x2="{VW:.0f}" y2="{zero_y:.1f}"/>')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Line
# --------------------------------------------------------------------------

def line_chart(b: Dict[str, Any], aspect: float, lang: str) -> str:
    xs = list(b.get("x") or [])
    series = [s for s in (b.get("series") or []) if isinstance(s, dict)]
    if len(xs) < 2 or not series:
        return ""
    hl = b.get("highlight") or (series[0]["name"] if len(series) == 1 else None)
    dec = b.get("decimals")
    suf = b.get("value_suffix", "")
    vh = VW / aspect
    vals = [v for s in series for v in s.get("values", []) if isinstance(v, (int, float))]
    lo = min(0.0, min(vals))
    hi = nice_max(max(vals)) if max(vals) > 0 else 1.0
    end_w = max(text_w(f"{s['name']} {fmt(s['values'][-1], dec, lang, suf)}", F_LABEL) for s in series) + 30
    end_w = min(end_w, VW * 0.36)
    left = max(text_w(fmt(hi, dec, lang), F_TICK), text_w(fmt(lo, dec, lang), F_TICK)) + 18
    top, bottom = 24, F_TICK * 2.4
    pw = VW - left - end_w
    ph = vh - top - bottom
    sx = lambda i: left + pw * i / (len(xs) - 1)
    sy = lambda v: top + ph * (1 - (v - lo) / (hi - lo))
    parts = [svg_open(vh, b.get("title", "chart"))]
    # Light grid: zero, mid, max. Labels on the left in the tick style.
    for t in sorted({lo, (lo + hi) / 2, hi}):
        y = sy(t)
        cls = "c-axis" if t == 0 else "c-grid"
        parts.append(f'<line class="{cls}" x1="{left:.1f}" y1="{y:.1f}" x2="{left + pw:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="c-tick" x="{left - 12:.1f}" y="{y:.1f}" dominant-baseline="central" text-anchor="end" font-size="{F_TICK}">{esc(fmt(t, dec, lang))}</text>')
    # x labels: at most 6, always first and last.
    step = max(1, math.ceil(len(xs) / 6))
    idx = sorted(set(list(range(0, len(xs), step)) + [len(xs) - 1]))
    if len(idx) > 2 and idx[-1] - idx[-2] < step:
        idx.pop(-2)
    for i in idx:
        anchor = "start" if i == 0 else ("end" if i == len(xs) - 1 else "middle")
        parts.append(f'<text class="c-tick" x="{sx(i):.1f}" y="{vh - F_TICK * 0.5:.1f}" text-anchor="{anchor}" font-size="{F_TICK}">{esc(xs[i])}</text>')
    # Draw grey series first, the highlighted one last (on top).
    ordered = sorted(series, key=lambda s: s["name"] == hl)
    ends: List[Tuple[float, str, str]] = []
    for s in ordered:
        is_hl = " is-hl" if s["name"] == hl else ""
        pts = [(sx(i), sy(v)) for i, v in enumerate(s["values"]) if isinstance(v, (int, float))]
        if len(pts) < 2:
            continue
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polyline class="c-line{is_hl}" fill="none" points="{d}"/>')
        last_v = [v for v in s["values"] if isinstance(v, (int, float))][-1]
        if is_hl:
            parts.append(f'<circle class="c-dot{is_hl}" cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="9"/>')
        ends.append((pts[-1][1], s["name"], f"{s['name']} {fmt(last_v, dec, lang, suf)}" if len(series) > 1 else fmt(last_v, dec, lang, suf)))
    # End labels, pushed apart vertically.
    ends.sort()
    min_gap = F_LABEL * 1.15
    placed: List[float] = []
    for y, _, _ in ends:
        y = max(y, placed[-1] + min_gap) if placed else y
        placed.append(y)
    for (y0, name, label), y in zip(ends, placed):
        is_hl = " is-hl" if name == hl else ""
        parts.append(f'<text class="c-value{is_hl}" x="{left + pw + 16:.1f}" y="{min(y, vh - bottom):.1f}" dominant-baseline="central" font-size="{F_LABEL}">{esc(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Donut (part of a whole, 4 segments max)
# --------------------------------------------------------------------------

def donut_chart(b: Dict[str, Any], aspect: float, lang: str) -> str:
    data = [d for d in (b.get("data") or []) if isinstance(d, dict) and isinstance(d.get("value"), (int, float)) and d["value"] > 0]
    if not data:
        return ""
    hl = b.get("highlight") or data[0]["label"]
    dec = b.get("decimals")
    suf = b.get("value_suffix", "")
    vh = VW / aspect
    total = sum(d["value"] for d in data)
    r = min(vh * 0.44, VW * 0.22)
    cx, cy = r + 20, vh / 2
    sw = r * 0.34
    parts = [svg_open(vh, b.get("title", "chart"))]
    # Highlighted segment starts at 12 o'clock, others follow in grey shades.
    ordered = sorted(data, key=lambda d: d["label"] != hl)
    offset = 0.0
    grey = 0
    for d in ordered:
        frac = d["value"] / total * 100
        if d["label"] == hl:
            cls = "c-seg is-hl"
        else:
            grey += 1
            cls = f"c-seg g{min(grey, 3)}"
        parts.append(f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r - sw / 2:.1f}" fill="none" stroke-width="{sw:.1f}" '
                     f'pathLength="100" stroke-dasharray="{max(frac - 0.6, 0.1):.2f} {100 - frac + 0.6:.2f}" stroke-dashoffset="{-offset:.2f}" '
                     f'transform="rotate(-90 {cx:.1f} {cy:.1f})"/>')
        offset += frac
    hd = next(d for d in data if d["label"] == hl)
    parts.append(f'<text class="c-center" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" font-size="{min(r * 0.5, 120):.0f}">{esc(fmt(hd["value"], dec, lang, suf))}</text>')
    # Direct labels to the right, one row per segment, in segment order.
    lx = cx + r + 60
    row = min(vh / (len(ordered) + 1), F_LABEL * 2.6)
    y = cy - row * (len(ordered) - 1) / 2
    grey = 0
    for d in ordered:
        if d["label"] == hl:
            sw_cls = "c-swatch is-hl"
            t_cls = "c-label is-hl"
        else:
            grey += 1
            sw_cls = f"c-swatch g{min(grey, 3)}"
            t_cls = "c-label"
        parts.append(f'<rect class="{sw_cls}" x="{lx:.1f}" y="{y - 13:.1f}" width="26" height="26"/>')
        parts.append(f'<text class="{t_cls}" x="{lx + 42:.1f}" y="{y:.1f}" dominant-baseline="central" font-size="{F_LABEL}">'
                     f'{esc(d["label"])} <tspan class="c-value{" is-hl" if d["label"] == hl else ""}">{esc(fmt(d["value"], dec, lang, suf))}</tspan></text>')
        y += row
    parts.append("</svg>")
    return "".join(parts)


def render_chart(b: Dict[str, Any], box: Sequence[float], lang: str) -> str:
    """Return the SVG for a chart block, drawn for a box of (w, h) px."""
    w, h = (box[0], box[1]) if box else (900, 640)
    aspect = max(0.6, min(3.0, w / max(h, 1)))
    kind = b.get("kind")
    if kind == "bar":
        return bar_chart(b, aspect, lang)
    if kind == "line":
        return line_chart(b, aspect, lang)
    if kind == "donut":
        return donut_chart(b, aspect, lang)
    return ""


def chart_title(b: Dict[str, Any]) -> str:
    """Title with the unit appended unless the title already names it."""
    title = (b.get("title") or "").strip()
    unit = (b.get("unit") or "").strip()
    if unit and unit.lower() not in title.lower():
        return f"{title} ({unit})"
    return title


def describe(b: Dict[str, Any], lang: str) -> str:
    """Plain-language description used for alt text."""
    kind = b.get("kind")
    dec = b.get("decimals")
    suf = b.get("value_suffix", "")
    if kind in ("bar", "donut"):
        data = sorted([d for d in b.get("data") or [] if isinstance(d, dict)], key=lambda d: -(d.get("value") or 0))
        items = ", ".join(f"{d['label']} {fmt(d['value'], dec, lang, suf)}" for d in data)
        return f"{chart_title(b)}: {items}."
    if kind == "line":
        xs = b.get("x") or []
        out = []
        for s in b.get("series") or []:
            v = [x for x in s.get("values", []) if isinstance(x, (int, float))]
            if v and xs:
                out.append(f"{s['name']} from {fmt(v[0], dec, lang, suf)} ({xs[0]}) to {fmt(v[-1], dec, lang, suf)} ({xs[-1]})")
        return f"{chart_title(b)}: " + "; ".join(out) + "."
    return chart_title(b)
