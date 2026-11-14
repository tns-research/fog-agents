#!/usr/bin/env python3
"""brand_common.py: color math and small helpers shared by the brand scripts.

Imported by extract_brand.py, logo_pipeline.py and render_brand_preview.py.
Standard library only (Pillow is imported lazily by the functions that need it).
Not a command: running it prints this help and exits 0.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple

RGB = Tuple[int, int, int]

# CSS named colors common in logo markup (fill="white")
NAMED_COLORS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "orange": (255, 165, 0), "purple": (128, 0, 128), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "navy": (0, 0, 128), "teal": (0, 128, 128),
}

# WCAG 2.x thresholds
CONTRAST_TEXT = 4.5      # body text (1.4.3)
CONTRAST_LARGE = 3.0     # large text and non-text elements such as logos (1.4.11)


def parse_css_color(s: str) -> Optional[RGB]:
    """Parse #rgb, #rrggbb(aa), rgb()/rgba() and a few names. Fully or almost
    transparent colors return None."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ("transparent", "rgba(0, 0, 0, 0)", "none"):
        return None
    if s in NAMED_COLORS:
        return NAMED_COLORS[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            try:
                rgb = tuple(int(h[i: i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
            if len(h) == 8 and int(h[6:8], 16) < 26:
                return None
            return rgb  # type: ignore[return-value]
        return None
    m = re.match(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?", s)
    if m:
        alpha = m.group(4)
        if alpha is not None:
            a = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
            if a < 0.1:
                return None
        return int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3)))
    return None


def css_alpha(s: str) -> float:
    """Alpha channel of a CSS color string (1.0 when none is given)."""
    s = (s or "").strip().lower()
    m = re.match(r"rgba?\(\s*[\d.]+[\s,]+[\d.]+[\s,]+[\d.]+\s*[,/]\s*([\d.]+%?)", s)
    if m:
        v = m.group(1)
        return float(v[:-1]) / 100 if v.endswith("%") else float(v)
    if s.startswith("#") and len(s) == 9:
        try:
            return int(s[7:9], 16) / 255
        except ValueError:
            return 1.0
    return 1.0


def flatten_on(css: str, bg: RGB) -> Optional[RGB]:
    """Parse a CSS color and blend its alpha over bg, so the result is opaque."""
    rgb = parse_css_color(css)
    if rgb is None:
        return None
    a = css_alpha(css)
    if a >= 0.999:
        return rgb
    return tuple(int(round(a * f + (1 - a) * b)) for f, b in zip(rgb, bg))  # type: ignore[return-value]


def rgb_to_hex(rgb: Sequence[int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(c))) for c in rgb[:3]])


def hex_to_rgb(s: str, default: RGB = (128, 128, 128)) -> RGB:
    return parse_css_color(s or "") or default


def luminance(rgb: Sequence[int]) -> float:
    def chan(c: float) -> float:
        c2 = c / 255.0
        return c2 / 12.92 if c2 <= 0.03928 else ((c2 + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    la, lb = luminance(a) + 0.05, luminance(b) + 0.05
    return max(la, lb) / min(la, lb)


def saturation(rgb: Sequence[int]) -> float:
    r, g, b = (c / 255 for c in rgb[:3])
    cmax, cmin = max(r, g, b), min(r, g, b)
    if cmax == 0:
        return 0.0
    return (cmax - cmin) / cmax


def vividness(rgb: Sequence[int]) -> float:
    """Saturated AND bright wins: the lit stop of a gradient beats its shadow stop."""
    cmax, cmin = max(rgb[:3]), min(rgb[:3])
    light = (cmax + cmin) / 510.0
    return saturation(rgb) * (0.2 + 0.8 * light)


def is_neutralish(rgb: Sequence[int]) -> bool:
    """White, black or grey: not a brand accent."""
    return saturation(rgb) < 0.18 or min(rgb[:3]) > 235 or max(rgb[:3]) < 18


def is_dark(rgb: Sequence[int]) -> bool:
    """True when white text contrasts more than black text on this color."""
    return contrast_ratio(rgb, (255, 255, 255)) > contrast_ratio(rgb, (0, 0, 0))


def color_distance(a: Sequence[int], b: Sequence[int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


def darken(rgb: Sequence[int], factor: float = 0.7) -> RGB:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb[:3])  # type: ignore[return-value]


def better_on(bg: Sequence[int]) -> RGB:
    """#ffffff or #000000, whichever contrasts more with bg."""
    return (255, 255, 255) if is_dark(bg) else (0, 0, 0)


def px_value(css_len: Any) -> Optional[float]:
    """'14px' -> 14.0; anything that is not a plain px length -> None."""
    m = re.match(r"^\s*([\d.]+)px\s*$", str(css_len or ""))
    return float(m.group(1)) if m else None


def css_length(px: float) -> str:
    """14.0 -> '14px', 0 -> '0' (the brand schema's radius format)."""
    if px <= 0:
        return "0"
    return f"{int(px)}px" if float(px).is_integer() else f"{round(px, 1)}px"


def weighted_mode(items: Iterable[Tuple[Any, float]]) -> Optional[Any]:
    """Key with the largest total weight."""
    acc: dict = {}
    for k, w in items:
        acc[k] = acc.get(k, 0.0) + w
    if not acc:
        return None
    return max(acc.items(), key=lambda kv: kv[1])[0]


def cluster_colors(items: Iterable[Tuple[RGB, float]], radius: float = 18.0) -> list:
    """Greedy weighted clustering of colors. Returns [(representative, weight)],
    heaviest first; the representative is the heaviest member."""
    clusters: list = []  # [rep, weight, best_member_weight]
    for rgb, w in sorted(items, key=lambda kv: -kv[1]):
        for c in clusters:
            if color_distance(c[0], rgb) <= radius:
                c[1] += w
                break
        else:
            clusters.append([rgb, w])
    return [(tuple(c[0]), c[1]) for c in sorted(clusters, key=lambda c: -c[1])]


# --- pixel helpers (Pillow) --------------------------------------------------

def region_pixels(img: Any, box: Sequence[float], inset: float = 0.0, max_side: int = 480) -> list:
    """RGB pixels of img inside box=(x, y, w, h), inset on each side. Large boxes
    are subsampled with nearest-neighbour (never averaged: averaging would blend
    thin glyphs into their background). Empty list when the box is outside."""
    x, y, w, h = box
    x0, y0 = int(max(0, x + inset)), int(max(0, y + inset))
    x1, y1 = int(min(img.width, x + w - inset)), int(min(img.height, y + h - inset))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return []
    crop = img.crop((x0, y0, x1, y1)).convert("RGB")
    if max(crop.size) > max_side:
        from PIL import Image
        k = max_side / float(max(crop.size))
        crop = crop.resize((max(1, int(crop.width * k)), max(1, int(crop.height * k))), Image.NEAREST)
    data = crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata()
    return list(data)


def mode_color(pixels: Sequence[RGB], quant: int = 8) -> Optional[RGB]:
    """Most frequent exact color when it covers 20 % of the pixels, else the
    mean of the most frequent bucket after quantizing each channel to `quant`."""
    if not pixels:
        return None
    exact = Counter(tuple(p[:3]) for p in pixels).most_common(1)[0]
    if exact[1] >= 0.2 * len(pixels):
        return exact[0]  # type: ignore[return-value]
    buckets: dict = {}
    for p in pixels:
        key = (p[0] // quant, p[1] // quant, p[2] // quant)
        b = buckets.setdefault(key, [0, 0, 0, 0])
        b[0] += p[0]; b[1] += p[1]; b[2] += p[2]; b[3] += 1
    best = max(buckets.values(), key=lambda b: b[3])
    n = best[3]
    return (best[0] // n, best[1] // n, best[2] // n)


def foreground_color(pixels: Sequence[RGB], share: float = 0.02) -> Optional[RGB]:
    """Rendered text color inside a text box: the median of the pixels farthest
    from the box's background (its mode color). Antialiased edges sit between the
    two, so only the farthest 2 % (the glyph cores) are kept."""
    bg = mode_color(pixels)
    if bg is None:
        return None
    ranked = sorted(pixels, key=lambda p: color_distance(p, bg), reverse=True)
    top = ranked[: max(3, int(len(ranked) * share))]
    if color_distance(top[0], bg) < 20:
        return None  # nothing drawn on this box
    top.sort(key=lambda p: sum(p))
    return tuple(top[len(top) // 2])  # type: ignore[return-value]


def between(c: Sequence[int], a: Sequence[int], b: Sequence[int], slack: float = 0.12) -> bool:
    """True when c lies on the segment from a to b (an antialiased mix of the two)."""
    ab = color_distance(a, b)
    return ab > 0 and color_distance(a, c) + color_distance(c, b) <= ab * (1 + slack)


def most_common(values: Iterable[Any]) -> Optional[Any]:
    c = Counter(v for v in values if v not in (None, ""))
    return c.most_common(1)[0][0] if c else None


def load_json_safe(path: Path) -> Optional[Any]:
    import json
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    print(__doc__.strip())
    sys.exit(0)
