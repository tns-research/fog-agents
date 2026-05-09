#!/usr/bin/env python3
"""svg_helpers.py — Brand-aware SVG generators for carousel slides.

Ships 15 starter helpers covering the most common carousel visual needs.
Each helper:
  - takes (data: dict, brand: dict, width: int, height: int)
  - returns a complete <svg>...</svg> string
  - uses brand colors (passed in via the brand dict, never hardcoded)
  - has no JS, no external libs, no <foreignObject>
  - is safe to inline directly into slide HTML

The agent is also free to author bespoke SVG inline when no helper fits,
following the same color-via-CSS-vars pattern.

CLI usage (for debugging / preview):
    python svg_helpers.py bar_chart \\
        --data '{"items":[{"label":"A","value":40},{"label":"B","value":80}]}' \\
        --brand '{"accent":"#5b8def","accent_secondary":"#2a4a99","text_primary":"#fff"}' \\
        --width 800 --height 400 > out.svg
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from html import escape
from typing import Any, Callable

# ─── helpers ────────────────────────────────────────────────────────────────


def _color(brand: dict[str, Any], key: str, default: str) -> str:
    val = brand.get(key) or default
    return str(val)


def _esc(s: Any) -> str:
    return escape(str(s), quote=True)


def _svg_open(width: int, height: int, vb: str | None = None) -> str:
    vb = vb or f"0 0 {width} {height}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="{vb}" role="img" aria-hidden="true">'
    )


# ─── 1. bar_chart ───────────────────────────────────────────────────────────


def bar_chart(data: dict, brand: dict, width: int = 900, height: int = 500) -> str:
    """data = {"items":[{"label":"A","value":40}, ...], "max":<optional>, "orientation":"horizontal"|"vertical"}"""
    items = data.get("items", [])
    if not items:
        return _svg_open(width, height) + "</svg>"
    orientation = data.get("orientation", "horizontal")
    accent = _color(brand, "accent", "#5b8def")
    accent_2 = _color(brand, "accent_secondary", "#2a4a99")
    fg = _color(brand, "text_primary", "#fff")
    max_val = data.get("max") or max(it.get("value", 0) for it in items)
    max_val = max(max_val, 1)
    pad = 40
    label_w = 200 if orientation == "horizontal" else 0
    out = [_svg_open(width, height)]
    if orientation == "horizontal":
        bar_h = (height - 2 * pad) / max(len(items), 1)
        bar_h = min(bar_h, 80)
        for i, it in enumerate(items):
            y = pad + i * bar_h + bar_h * 0.15
            bw = (width - label_w - 2 * pad) * (it.get("value", 0) / max_val)
            color = accent if i % 2 == 0 else accent_2
            out.append(
                f'<rect x="{label_w}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h * 0.7:.1f}" '
                f'fill="{color}" rx="4"/>'
            )
            out.append(
                f'<text x="{label_w - 10}" y="{y + bar_h * 0.5:.1f}" '
                f'fill="{fg}" font-size="22" font-family="inherit" '
                f'text-anchor="end" dominant-baseline="middle">{_esc(it.get("label", ""))}</text>'
            )
            out.append(
                f'<text x="{label_w + bw + 10:.1f}" y="{y + bar_h * 0.5:.1f}" '
                f'fill="{fg}" font-size="20" font-family="inherit" '
                f'dominant-baseline="middle">{_esc(it.get("value", ""))}</text>'
            )
    else:  # vertical
        bar_w = (width - 2 * pad) / max(len(items), 1)
        bar_w = min(bar_w, 100)
        for i, it in enumerate(items):
            bh = (height - 2 * pad - 40) * (it.get("value", 0) / max_val)
            x = pad + i * bar_w + bar_w * 0.15
            color = accent if i % 2 == 0 else accent_2
            out.append(
                f'<rect x="{x:.1f}" y="{height - pad - bh - 30:.1f}" '
                f'width="{bar_w * 0.7:.1f}" height="{bh:.1f}" fill="{color}" rx="4"/>'
            )
            out.append(
                f'<text x="{x + bar_w * 0.35:.1f}" y="{height - pad:.1f}" '
                f'fill="{fg}" font-size="20" font-family="inherit" text-anchor="middle">'
                f'{_esc(it.get("label", ""))}</text>'
            )
    out.append("</svg>")
    return "".join(out)


# ─── 2. donut ───────────────────────────────────────────────────────────────


def donut(data: dict, brand: dict, width: int = 400, height: int = 400) -> str:
    """data = {"percent": 0..100, "label":"...", "sublabel":"..."}"""
    percent = max(0.0, min(100.0, float(data.get("percent", 0))))
    label = data.get("label", f"{percent:.0f}%")
    sublabel = data.get("sublabel", "")
    accent = _color(brand, "accent", "#5b8def")
    track = _color(brand, "card_border", "rgba(255,255,255,0.15)")
    fg = _color(brand, "text_primary", "#fff")
    cx, cy = width / 2, height / 2
    r = min(cx, cy) - 30
    stroke_w = 28
    circ = 2 * math.pi * r
    dash = circ * (percent / 100.0)
    out = [
        _svg_open(width, height),
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{track}" stroke-width="{stroke_w}"/>',
        (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{accent}" '
            f'stroke-width="{stroke_w}" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.1f} {circ:.1f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        ),
        (
            f'<text x="{cx}" y="{cy - 8}" fill="{fg}" font-size="62" '
            f'font-family="inherit" text-anchor="middle" font-weight="600">{_esc(label)}</text>'
        ),
    ]
    if sublabel:
        out.append(
            f'<text x="{cx}" y="{cy + 36}" fill="{fg}" font-size="22" '
            f'font-family="inherit" text-anchor="middle" opacity="0.7">{_esc(sublabel)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 3. compare (left/right vs layout) ──────────────────────────────────────


def compare(data: dict, brand: dict, width: int = 900, height: int = 500) -> str:
    """data = {"left":{"label":"...","value":"...","sub":"..."}, "right":{...}, "vs":"VS"}"""
    left = data.get("left", {})
    right = data.get("right", {})
    vs_label = data.get("vs", "VS")
    accent = _color(brand, "accent", "#5b8def")
    accent_2 = _color(brand, "accent_secondary", "#2a4a99")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    half = width / 2
    for side, x_anchor, color in (
        (left, half * 0.5, accent),
        (right, half * 1.5, accent_2),
    ):
        out.append(
            f'<text x="{x_anchor:.0f}" y="{height * 0.30:.0f}" fill="{color}" '
            f'font-size="80" font-family="inherit" font-weight="700" text-anchor="middle">'
            f'{_esc(side.get("value", ""))}</text>'
        )
        out.append(
            f'<text x="{x_anchor:.0f}" y="{height * 0.55:.0f}" fill="{fg}" '
            f'font-size="28" font-family="inherit" text-anchor="middle">'
            f'{_esc(side.get("label", ""))}</text>'
        )
        if side.get("sub"):
            out.append(
                f'<text x="{x_anchor:.0f}" y="{height * 0.70:.0f}" fill="{fg}" '
                f'font-size="20" font-family="inherit" text-anchor="middle" opacity="0.65">'
                f'{_esc(side["sub"])}</text>'
            )
    out.append(
        f'<text x="{half:.0f}" y="{height * 0.5:.0f}" fill="{fg}" font-size="36" '
        f'font-family="inherit" text-anchor="middle" opacity="0.5" font-style="italic">'
        f'{_esc(vs_label)}</text>'
    )
    out.append("</svg>")
    return "".join(out)


# ─── 4. quote_mark ──────────────────────────────────────────────────────────


def quote_mark(data: dict, brand: dict, width: int = 200, height: int = 200) -> str:
    """data = {} (no params; brand[accent] drives color)"""
    accent = _color(brand, "accent", "#5b8def")
    return (
        _svg_open(width, height, "0 0 200 200")
        + f'<path fill="{accent}" d="M40 130 Q40 70 90 60 L90 80 Q60 90 60 130 Z M120 130 '
        f'Q120 70 170 60 L170 80 Q140 90 140 130 Z"/></svg>'
    )


# ─── 5. divider ─────────────────────────────────────────────────────────────


def divider(data: dict, brand: dict, width: int = 800, height: int = 40) -> str:
    """data = {"style":"line"|"dots"|"gradient"}"""
    style = data.get("style", "line")
    accent = _color(brand, "accent", "#5b8def")
    out = [_svg_open(width, height)]
    if style == "dots":
        n = 7
        for i in range(n):
            cx = (width / (n + 1)) * (i + 1)
            out.append(f'<circle cx="{cx:.1f}" cy="{height / 2}" r="4" fill="{accent}"/>')
    elif style == "gradient":
        out.append(
            f'<defs><linearGradient id="dg" x1="0" x2="1"><stop offset="0" stop-color="{accent}" '
            f'stop-opacity="0"/><stop offset="0.5" stop-color="{accent}"/>'
            f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>'
        )
        out.append(
            f'<rect x="0" y="{height / 2 - 1:.0f}" width="{width}" height="2" fill="url(#dg)"/>'
        )
    else:  # line
        out.append(
            f'<line x1="0" y1="{height / 2}" x2="{width}" y2="{height / 2}" '
            f'stroke="{accent}" stroke-width="2" opacity="0.7"/>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 6. timeline ────────────────────────────────────────────────────────────


def timeline(data: dict, brand: dict, width: int = 1000, height: int = 300) -> str:
    """data = {"events":[{"date":"Q1 2026","label":"Hire 1"}, ...]}"""
    events = data.get("events", [])
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    if not events:
        return out[0] + "</svg>"
    pad = 60
    y = height * 0.55
    out.append(
        f'<line x1="{pad}" y1="{y:.0f}" x2="{width - pad}" y2="{y:.0f}" '
        f'stroke="{accent}" stroke-width="3" opacity="0.6"/>'
    )
    n = len(events)
    for i, ev in enumerate(events):
        x = pad + (width - 2 * pad) * (i / max(n - 1, 1))
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" fill="{accent}"/>')
        out.append(
            f'<text x="{x:.0f}" y="{y - 30:.0f}" fill="{fg}" font-size="20" '
            f'font-family="inherit" text-anchor="middle" font-weight="600" opacity="0.9">'
            f'{_esc(ev.get("date", ""))}</text>'
        )
        out.append(
            f'<text x="{x:.0f}" y="{y + 40:.0f}" fill="{fg}" font-size="22" '
            f'font-family="inherit" text-anchor="middle">{_esc(ev.get("label", ""))}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 7. funnel ──────────────────────────────────────────────────────────────


def funnel(data: dict, brand: dict, width: int = 700, height: int = 500) -> str:
    """data = {"stages":[{"label":"...","value":1000}, ...]} top->bottom narrowing"""
    stages = data.get("stages", [])
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    n = len(stages)
    if n == 0:
        return out[0] + "</svg>"
    pad = 40
    stage_h = (height - 2 * pad) / n
    max_w = width - 2 * pad
    for i, st in enumerate(stages):
        shrink = i / max(n, 1)
        w = max_w * (1 - shrink * 0.55)
        x = (width - w) / 2
        y = pad + i * stage_h
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{stage_h * 0.85:.1f}" '
            f'fill="{accent}" opacity="{1 - shrink * 0.4:.2f}" rx="6"/>'
        )
        out.append(
            f'<text x="{width / 2:.0f}" y="{y + stage_h * 0.45:.0f}" fill="{fg}" '
            f'font-size="22" font-family="inherit" text-anchor="middle" font-weight="600" '
            f'dominant-baseline="middle">{_esc(st.get("label", ""))}</text>'
        )
        out.append(
            f'<text x="{width / 2:.0f}" y="{y + stage_h * 0.65:.0f}" fill="{fg}" '
            f'font-size="18" font-family="inherit" text-anchor="middle" opacity="0.7" '
            f'dominant-baseline="middle">{_esc(st.get("value", ""))}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 8. pyramid ─────────────────────────────────────────────────────────────


def pyramid(data: dict, brand: dict, width: int = 700, height: int = 500) -> str:
    """data = {"levels":[{"label":"top"}, ..., {"label":"base"}]}"""
    levels = data.get("levels", [])
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    n = len(levels)
    if n == 0:
        return out[0] + "</svg>"
    pad = 40
    level_h = (height - 2 * pad) / n
    base_w = width - 2 * pad
    for i, lvl in enumerate(levels):
        w = base_w * ((i + 1) / n)
        x = (width - w) / 2
        y = pad + i * level_h
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{level_h * 0.85:.1f}" '
            f'fill="{accent}" opacity="{0.5 + 0.5 * (i / max(n - 1, 1)):.2f}" rx="6"/>'
        )
        out.append(
            f'<text x="{width / 2:.0f}" y="{y + level_h * 0.45:.0f}" fill="{fg}" '
            f'font-size="22" font-family="inherit" text-anchor="middle" font-weight="600" '
            f'dominant-baseline="middle">{_esc(lvl.get("label", ""))}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 9. progress_steps ──────────────────────────────────────────────────────


def progress_steps(data: dict, brand: dict, width: int = 900, height: int = 200) -> str:
    """data = {"steps":["a","b","c"], "current": 1}  # 0-indexed"""
    steps = data.get("steps", [])
    current = int(data.get("current", 0))
    accent = _color(brand, "accent", "#5b8def")
    track = _color(brand, "card_border", "rgba(255,255,255,0.18)")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    n = len(steps)
    if n == 0:
        return out[0] + "</svg>"
    pad = 60
    y = height * 0.4
    r = 28
    for i, label in enumerate(steps):
        x = pad + (width - 2 * pad) * (i / max(n - 1, 1))
        if i < n - 1:
            x_next = pad + (width - 2 * pad) * ((i + 1) / max(n - 1, 1))
            color_line = accent if i < current else track
            out.append(
                f'<line x1="{x + r:.0f}" y1="{y:.0f}" x2="{x_next - r:.0f}" y2="{y:.0f}" '
                f'stroke="{color_line}" stroke-width="3"/>'
            )
        is_done_or_current = i <= current
        fill = accent if is_done_or_current else track
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{fill}"/>')
        out.append(
            f'<text x="{x:.0f}" y="{y:.0f}" fill="{fg}" font-size="22" font-family="inherit" '
            f'text-anchor="middle" font-weight="700" dominant-baseline="middle">{i + 1}</text>'
        )
        out.append(
            f'<text x="{x:.0f}" y="{y + 60:.0f}" fill="{fg}" font-size="20" '
            f'font-family="inherit" text-anchor="middle" opacity="{1 if is_done_or_current else 0.6:.2f}">'
            f'{_esc(label)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 10. icon_grid ──────────────────────────────────────────────────────────

_ICON_PATHS = {
    "check": "M5 12 L10 17 L19 7",
    "lightning": "M13 2 L6 14 H11 L9 22 L18 10 H13 Z",
    "star": "M12 2 L15 9 L22 10 L17 15 L18 22 L12 19 L6 22 L7 15 L2 10 L9 9 Z",
    "heart": "M12 21 C-3 12 5 2 12 8 C19 2 27 12 12 21 Z",
    "rocket": "M5 19 L8 16 M19 5 L12 12 M9 15 L9 18 H6 V15 L13 8 L16 11 Z",
    "target": "M12 2 A10 10 0 1 1 12 22 A10 10 0 1 1 12 2 M12 7 A5 5 0 1 1 12 17 A5 5 0 1 1 12 7 M12 11 A1 1 0 1 1 12 13 A1 1 0 1 1 12 11",
    "shield": "M12 2 L20 6 V12 C20 17 16 21 12 22 C8 21 4 17 4 12 V6 Z",
    "bolt": "M11 2 L4 14 H10 L9 22 L20 10 H14 Z",
    "circle": "M12 2 A10 10 0 1 1 12 22 A10 10 0 1 1 12 2",
    "square": "M3 3 H21 V21 H3 Z",
}


def icon_grid(data: dict, brand: dict, width: int = 800, height: int = 600) -> str:
    """data = {"items":[{"icon":"check","label":"..."}, ...]}; up to 9 items, auto layout 2x2/3x3."""
    items = data.get("items", [])[:9]
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    n = len(items)
    if n == 0:
        return _svg_open(width, height) + "</svg>"
    cols = 3 if n > 4 else 2
    rows = math.ceil(n / cols)
    cell_w = width / cols
    cell_h = height / rows
    out = [_svg_open(width, height)]
    icon_size = 60
    for i, it in enumerate(items):
        col = i % cols
        row = i // cols
        cx = cell_w * (col + 0.5)
        cy = cell_h * (row + 0.5) - 30
        path = _ICON_PATHS.get(it.get("icon", "check"), _ICON_PATHS["check"])
        out.append(
            f'<g transform="translate({cx - icon_size / 2:.0f}, {cy - icon_size / 2:.0f}) '
            f'scale({icon_size / 24:.2f})"><path d="{path}" fill="none" stroke="{accent}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>'
        )
        out.append(
            f'<text x="{cx:.0f}" y="{cy + icon_size / 2 + 30:.0f}" fill="{fg}" '
            f'font-size="22" font-family="inherit" text-anchor="middle">'
            f'{_esc(it.get("label", ""))}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 11. callout_arrow ──────────────────────────────────────────────────────


def callout_arrow(data: dict, brand: dict, width: int = 600, height: int = 200) -> str:
    """data = {"label":"...", "value":"...", "direction":"right"|"down"}"""
    label = data.get("label", "")
    value = data.get("value", "")
    direction = data.get("direction", "right")
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    out = [_svg_open(width, height)]
    if direction == "right":
        out.append(
            f'<line x1="40" y1="{height / 2:.0f}" x2="{width - 80:.0f}" y2="{height / 2:.0f}" '
            f'stroke="{accent}" stroke-width="3"/>'
        )
        out.append(
            f'<polygon points="{width - 80},{height / 2 - 10} {width - 80},{height / 2 + 10} '
            f'{width - 50},{height / 2}" fill="{accent}"/>'
        )
        out.append(
            f'<text x="40" y="{height / 2 - 20:.0f}" fill="{fg}" font-size="22" '
            f'font-family="inherit">{_esc(label)}</text>'
        )
        out.append(
            f'<text x="{width - 50:.0f}" y="{height / 2 - 20:.0f}" fill="{accent}" '
            f'font-size="32" font-family="inherit" font-weight="700" text-anchor="end">'
            f'{_esc(value)}</text>'
        )
    else:  # down
        out.append(
            f'<line x1="{width / 2:.0f}" y1="20" x2="{width / 2:.0f}" y2="{height - 60:.0f}" '
            f'stroke="{accent}" stroke-width="3"/>'
        )
        out.append(
            f'<polygon points="{width / 2 - 10},{height - 60} {width / 2 + 10},{height - 60} '
            f'{width / 2},{height - 30}" fill="{accent}"/>'
        )
        out.append(
            f'<text x="{width / 2 + 30:.0f}" y="40" fill="{fg}" font-size="22" '
            f'font-family="inherit">{_esc(label)}</text>'
        )
        out.append(
            f'<text x="{width / 2 + 30:.0f}" y="{height - 20:.0f}" fill="{accent}" '
            f'font-size="32" font-family="inherit" font-weight="700">{_esc(value)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 12. checklist ──────────────────────────────────────────────────────────


def checklist(data: dict, brand: dict, width: int = 700, height: int = 500) -> str:
    """data = {"items":["a","b","c"]} or [{"label":"a","done":true}]"""
    raw = data.get("items", [])
    items = []
    for it in raw:
        if isinstance(it, str):
            items.append({"label": it, "done": True})
        else:
            items.append({"label": it.get("label", ""), "done": it.get("done", True)})
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    muted = _color(brand, "text_secondary", "rgba(255,255,255,0.6)")
    out = [_svg_open(width, height)]
    n = max(len(items), 1)
    pad = 30
    line_h = min((height - 2 * pad) / n, 70)
    for i, it in enumerate(items):
        y = pad + i * line_h + line_h / 2
        if it["done"]:
            out.append(
                f'<g transform="translate(20, {y - 16:.0f}) scale(1.3)">'
                f'<circle cx="12" cy="12" r="11" fill="{accent}"/>'
                f'<path d="M7 12 L11 16 L17 9" stroke="{fg}" stroke-width="2.5" '
                f'fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>'
            )
        else:
            out.append(
                f'<circle cx="36" cy="{y:.0f}" r="14" fill="none" stroke="{muted}" stroke-width="2"/>'
            )
        out.append(
            f'<text x="80" y="{y:.0f}" fill="{fg if it["done"] else muted}" font-size="24" '
            f'font-family="inherit" dominant-baseline="middle">{_esc(it["label"])}</text>'
        )
    out.append("</svg>")
    return "".join(out)


# ─── 13. comparison_table ───────────────────────────────────────────────────


def comparison_table(data: dict, brand: dict, width: int = 900, height: int = 500) -> str:
    """data = {"headers":["","Plan A","Plan B"], "rows":[["Price","$10","$20"], ...]}; max 4 cols, 5 rows."""
    headers = data.get("headers", [])[:4]
    rows = data.get("rows", [])[:5]
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    border = _color(brand, "card_border", "rgba(255,255,255,0.15)")
    n_cols = max(len(headers), max((len(r) for r in rows), default=1))
    n_rows = len(rows) + 1  # +1 for header
    col_w = width / max(n_cols, 1)
    row_h = height / max(n_rows, 1)
    out = [_svg_open(width, height)]
    # header row
    out.append(f'<rect x="0" y="0" width="{width}" height="{row_h:.0f}" fill="{accent}" opacity="0.18"/>')
    for ci, txt in enumerate(headers):
        out.append(
            f'<text x="{col_w * (ci + 0.5):.0f}" y="{row_h * 0.55:.0f}" fill="{fg}" '
            f'font-size="22" font-family="inherit" text-anchor="middle" font-weight="700">'
            f'{_esc(txt)}</text>'
        )
    # rows
    for ri, row in enumerate(rows):
        y = row_h * (ri + 1)
        out.append(
            f'<line x1="0" y1="{y:.0f}" x2="{width}" y2="{y:.0f}" stroke="{border}"/>'
        )
        for ci in range(n_cols):
            cell = row[ci] if ci < len(row) else ""
            out.append(
                f'<text x="{col_w * (ci + 0.5):.0f}" y="{y + row_h * 0.55:.0f}" '
                f'fill="{fg}" font-size="20" font-family="inherit" text-anchor="middle">'
                f'{_esc(cell)}</text>'
            )
    out.append("</svg>")
    return "".join(out)


# ─── 14. wave_decoration ────────────────────────────────────────────────────


def wave_decoration(data: dict, brand: dict, width: int = 1080, height: int = 200) -> str:
    """data = {"opacity":0.15} (background flourish, no text)"""
    accent = _color(brand, "accent", "#5b8def")
    opacity = float(data.get("opacity", 0.15))
    return (
        _svg_open(width, height)
        + f'<path d="M0 {height * 0.5:.0f} '
        f'C{width * 0.25} {height * 0.1:.0f}, {width * 0.5} {height * 0.9:.0f}, {width * 0.75} {height * 0.5:.0f} '
        f'S{width} {height * 0.3:.0f}, {width} {height * 0.5:.0f} '
        f'L{width} {height} L0 {height} Z" fill="{accent}" opacity="{opacity}"/></svg>'
    )


# ─── 15. number_badge ───────────────────────────────────────────────────────


def number_badge(data: dict, brand: dict, width: int = 400, height: int = 400) -> str:
    """data = {"number":"3.2x","label":"faster"}"""
    number = data.get("number", "")
    label = data.get("label", "")
    accent = _color(brand, "accent", "#5b8def")
    fg = _color(brand, "text_primary", "#fff")
    cx, cy = width / 2, height / 2
    return (
        _svg_open(width, height)
        + f'<defs><radialGradient id="halo"><stop offset="0" stop-color="{accent}" stop-opacity="0.35"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient></defs>'
        f'<circle cx="{cx}" cy="{cy}" r="{min(cx, cy) - 10}" fill="url(#halo)"/>'
        f'<text x="{cx}" y="{cy:.0f}" fill="{fg}" font-size="96" font-family="inherit" '
        f'text-anchor="middle" dominant-baseline="middle" font-weight="700">{_esc(number)}</text>'
        f'<text x="{cx}" y="{cy + 70:.0f}" fill="{fg}" font-size="26" font-family="inherit" '
        f'text-anchor="middle" opacity="0.75">{_esc(label)}</text>'
        + "</svg>"
    )


# ─── registry + CLI ─────────────────────────────────────────────────────────

HELPERS: dict[str, Callable[..., str]] = {
    "bar_chart": bar_chart,
    "donut": donut,
    "compare": compare,
    "quote_mark": quote_mark,
    "divider": divider,
    "timeline": timeline,
    "funnel": funnel,
    "pyramid": pyramid,
    "progress_steps": progress_steps,
    "icon_grid": icon_grid,
    "callout_arrow": callout_arrow,
    "checklist": checklist,
    "comparison_table": comparison_table,
    "wave_decoration": wave_decoration,
    "number_badge": number_badge,
}


def render(name: str, data: dict, brand: dict, width: int, height: int) -> str:
    helper = HELPERS.get(name)
    if helper is None:
        raise ValueError(f"unknown svg helper: {name} (available: {sorted(HELPERS)})")
    return helper(data, brand, width, height)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render brand-aware SVG helpers.")
    parser.add_argument("name", choices=sorted(HELPERS), help="Helper name")
    parser.add_argument("--data", default="{}", help="JSON data dict")
    parser.add_argument("--brand", default="{}", help="JSON brand dict")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=400)
    args = parser.parse_args()
    data = json.loads(args.data)
    brand = json.loads(args.brand)
    sys.stdout.write(render(args.name, data, brand, args.width, args.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
