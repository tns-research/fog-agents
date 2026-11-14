"""blocks.py: deck.json blocks -> HTML fragments.

One function per block type. The markup is the same for every direction: a
direction changes the look through its style.css and the layout class set on
the slide, never through different HTML. That keeps a deck portable: switch
meta.direction and rebuild.

Stable class names a direction styles (see directions/README.md):
  .b .b-<type>              block wrapper, data-b = block index
  .t .sub .hl .nw           title, standfirst, accent span, no-wrap span
  .body                     body paragraphs
  .list .li-n .li-t .li-s   list, marker, item text, item sub-line
  .stat-v .stat-l .stat-c   stat value, label, context
  .c-title .c-box .c-note   chart heading, SVG box, note (SVG classes: charts.py)
  .ph-box .ph-img .ph-mat .ph-cap .ph-credit
  .shot-wrap .shot-frame .shot-bar .shot-url .shot-img .shot-ann .shot-legend
  .q-t .q-a .q-name .q-role .q-tr
  .lr-label .lr .lr-item
  .vis .vis-cap
  .cta-t .cta-url .cta-sub
"""

from __future__ import annotations

import html
import re
from typing import Any, Callable, Dict, List, Optional

import charts

I18N = {
    "fr": {"source": "Source", "sources": "Sources", "translated": "traduit de l'anglais", "missing": "Image manquante"},
    "en": {"source": "Source", "sources": "Sources", "translated": "translated", "missing": "Missing image"},
    "es": {"source": "Fuente", "sources": "Fuentes", "translated": "traducido", "missing": "Imagen ausente"},
    "de": {"source": "Quelle", "sources": "Quellen", "translated": "übersetzt", "missing": "Bild fehlt"},
}

NNBSP = " "  # narrow no-break space (French punctuation)
NBSP = " "


def t(lang: str, key: str) -> str:
    return I18N.get(lang[:2], I18N["en"]).get(key, I18N["en"][key])


def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def typo(text: str, lang: str, protect_hyphens: bool = False) -> str:
    """Escape, then apply non-breaking rules so the browser never strands a
    unit, a French punctuation mark or half of a hyphenated word."""
    s = text.strip()
    if lang.startswith("fr"):
        s = re.sub(r"\s+([:;!?»])", NNBSP + r"\1", s)
        s = re.sub(r"«\s+", "«" + NNBSP, s)
    # Number + short unit stay together: "58 %", "64 s", "3 min 44", "30 k€".
    s = re.sub(r"(\d)\s+(%|s|min|h|k€|M€|€|\$|ans?|mois|pages?|x)(?=[\s.,;:!?)]|$)", r"\1" + NBSP + r"\2", s)
    s = re.sub(r"(\d)\s+(min)\s+(\d)", r"\1" + NBSP + r"\2" + NBSP + r"\3", s)
    out = esc(s)
    if protect_hyphens:
        out = re.sub(r"(\S+-\S+)", r'<span class="nw">\1</span>', out)
    out = out.replace("\n", "<br>")
    return out


def with_accent(text: str, accent: Optional[str], lang: str, protect_hyphens: bool = False) -> str:
    if accent and accent in text:
        i = text.index(accent)
        before, mid, after = text[:i], text[i:i + len(accent)], text[i + len(accent):]
        # Keep the spaces outside the span so the highlight hugs the words.
        return (typo(before, lang, protect_hyphens) + (" " if before.endswith(" ") else "")
                + f'<span class="hl">{typo(mid, lang, protect_hyphens)}</span>'
                + (" " if after.startswith(" ") else "") + typo(after, lang, protect_hyphens))
    return typo(text, lang, protect_hyphens)


class Ctx:
    """What a block renderer needs to know about the build."""

    def __init__(self, lang: str, scale: Dict[str, Dict[str, Any]], asset: Callable[[str], Dict[str, Any]],
                 chart_box: List[float], issue: Callable[[str, str, str, str], None], quote_marks: Optional[List[str]] = None):
        self.lang = lang
        self.scale = scale
        self.asset = asset  # path -> {"url", "w", "h", "ok"}
        self.chart_box = chart_box
        self.issue = issue
        self.quote_marks = quote_marks
        self.has_media = False
        self.layout = ""

    def fit(self, key: str, order: int, block: int) -> str:
        # A direction can give a different range when the slide carries media
        # (photo, screenshot, visual): "<key>_media" in its type_scale.
        # Lookup order: "<key>@<layout>" (layout-specific range), then
        # "<key>_media" when the slide carries a photo, screenshot or visual,
        # then "<key>".
        if f"{key}@{self.layout}" in self.scale:
            key = f"{key}@{self.layout}"
        elif self.has_media and f"{key}_media" in self.scale:
            key = f"{key}_media"
        s = self.scale.get(key)
        if not s:
            return ""
        steps = s.get("steps")
        attrs = [f'data-fit="{key}"', f'data-fit-min="{s["min"]}"', f'data-fit-max="{s["max"]}"',
                 f'data-fit-lines="{s.get("lines", 99)}"', f'data-fit-order="{order}"', f'data-fit-block="{block}"']
        if steps:
            attrs.append(f'data-fit-steps="{",".join(str(x) for x in steps)}"')
        return " ".join(attrs)


# --------------------------------------------------------------------------

def title(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    key = {"cover": "cover_title", "cta": "cta_title"}.get(role, "title")
    sub_key = "cover_sub" if role == "cover" else "sub"
    tag = "h1" if role == "cover" else "h2"
    out = [f'<div class="b b-title" data-b="{i}">',
           f'<{tag} class="t" {ctx.fit(key, 1, i)}>{with_accent(b["text"], b.get("accent"), ctx.lang, True)}</{tag}>']
    if b.get("sub"):
        out.append(f'<p class="sub" {ctx.fit(sub_key, 5, i)}>{typo(b["sub"], ctx.lang)}</p>')
    out.append("</div>")
    return "".join(out)


def body(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    paras = [p for p in re.split(r"\n\s*\n", b["text"].strip()) if p.strip()]
    inner = "".join(f"<p>{with_accent(p, b.get('accent'), ctx.lang)}</p>" for p in paras)
    return f'<div class="b b-body" data-b="{i}"><div class="body" {ctx.fit("body", 6, i)}>{inner}</div></div>'


def list_(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    style = b.get("style", "bullets")
    tag = "ol" if style == "numbered" else "ul"
    items = []
    for k, it in enumerate(b["items"], 1):
        text = it if isinstance(it, str) else it.get("text", "")
        sub = None if isinstance(it, str) else it.get("sub")
        marker = {"numbered": f"{k}", "bullets": "", "checks": "", "plain": ""}[style]
        sub_html = f'<span class="li-s">{typo(sub, ctx.lang)}</span>' if sub else ""
        items.append(f'<li><span class="li-n" aria-hidden="true">{marker}</span>'
                     f'<div class="li-body"><span class="li-t">{typo(text, ctx.lang)}</span>{sub_html}</div></li>')
    cls = f"list list-{style}" + (" has-sub" if any(isinstance(x, dict) and x.get("sub") for x in b["items"]) else "")
    return (f'<div class="b b-list" data-b="{i}" data-count="{len(items)}">'
            f'<{tag} class="{cls}" {ctx.fit("list", 6, i)}>{"".join(items)}</{tag}></div>')


def stat(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    out = [f'<div class="b b-stat" data-b="{i}">',
           f'<p class="stat-v" {ctx.fit("stat_value", 2, i)}>{typo(b["value"], ctx.lang)}</p>',
           f'<p class="stat-l" {ctx.fit("stat_label", 4, i)}>{typo(b["label"], ctx.lang)}</p>']
    if b.get("context"):
        out.append(f'<p class="stat-c" {ctx.fit("stat_context", 7, i)}>{typo(b["context"], ctx.lang)}</p>')
    out.append("</div>")
    return "".join(out)


def chart(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    svg = charts.render_chart(b, ctx.chart_box, ctx.lang)
    if not svg:
        ctx.issue("error", "chart-empty", f"block {i}", "The chart has no drawable data.")
    note = f'<p class="c-note">{typo(b["note"], ctx.lang)}</p>' if b.get("note") else ""
    return (f'<figure class="b b-chart chart-{esc(b.get("kind"))}" data-b="{i}">'
            f'<figcaption class="c-title" {ctx.fit("chart_title", 3, i)}>{typo(charts.chart_title(b), ctx.lang)}</figcaption>'
            f'<div class="c-box">{svg}</div>{note}</figure>')


def _missing(src: str, ctx: Ctx, i: int) -> str:
    ctx.issue("error", "missing-asset", f"block {i}", f"File not found: {src}")
    return f'<div class="asset-missing"><span>{esc(t(ctx.lang, "missing"))}</span><code>{esc(src)}</code></div>'


def photo(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    a = ctx.asset(b["src"])
    fit = b.get("fit", "contain")
    if fit == "cover" and not b.get("crop_ok"):
        fit = "contain"
    mat = b.get("mat") or "auto"
    focus = b.get("focus") or [0.5, 0.5]
    pos = f"{focus[0] * 100:.0f}% {focus[1] * 100:.0f}%"
    cap = ""
    if b.get("caption") or b.get("credit"):
        credit = f'<span class="ph-credit">{typo(b["credit"], ctx.lang)}</span>' if b.get("credit") else ""
        cap = f'<figcaption class="ph-cap">{typo(b.get("caption", ""), ctx.lang)}{credit}</figcaption>'
    if not a["ok"]:
        inner = _missing(b["src"], ctx, i)
    else:
        mat_img = f'<img class="ph-mat" src="{esc(a["url"])}" alt="" aria-hidden="true">' if fit == "contain" else ""
        inner = (f'{mat_img}<img class="ph-img" src="{esc(a["url"])}" alt="{esc(b["alt"])}" '
                 f'style="object-position:{pos}" data-w="{a["w"]}" data-h="{a["h"]}">')
    orient = "portrait" if a.get("h", 1) > a.get("w", 1) * 1.05 else ("landscape" if a.get("w", 1) > a.get("h", 1) * 1.05 else "square")
    return (f'<figure class="b b-photo fit-{fit} mat-{mat} ph-{orient}" data-b="{i}">'
            f'<div class="ph-box">{inner}</div>{cap}</figure>')


def screenshot(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    a = ctx.asset(b["src"])
    frame = b.get("frame", "browser")
    anns = b.get("annotations") or []
    if not a["ok"]:
        body_html = _missing(b["src"], ctx, i)
        return f'<figure class="b b-shot frame-{frame}" data-b="{i}"><div class="shot-wrap">{body_html}</div></figure>'
    w, h = a["w"], a["h"]
    marks = []
    for k, an in enumerate(anns, 1):
        x, y, bw, bh = an["box"]
        X, Y, BW, BH = x * w, y * h, bw * w, bh * h
        r = max(w, h) * 0.022
        marks.append(f'<rect class="ann-box" x="{X:.1f}" y="{Y:.1f}" width="{BW:.1f}" height="{BH:.1f}" rx="{r * 0.25:.1f}" '
                     f'vector-effect="non-scaling-stroke"/>'
                     f'<g class="ann-pin"><circle cx="{X:.1f}" cy="{Y:.1f}" r="{r:.1f}"/>'
                     f'<text x="{X:.1f}" y="{Y:.1f}" font-size="{r * 1.2:.1f}" text-anchor="middle" dominant-baseline="central">{k}</text></g>')
    ann_svg = (f'<svg class="shot-ann" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{"".join(marks)}</svg>'
               if marks else "")
    bar = ""
    if frame == "browser":
        bar = f'<div class="shot-bar"><span class="shot-url">{esc(b.get("url", ""))}</span></div>'
    legend = ""
    if anns:
        legend = '<ol class="shot-legend">' + "".join(
            f'<li><span class="ann-n">{k}</span><span class="ann-t">{typo(an["label"], ctx.lang)}</span></li>' for k, an in enumerate(anns, 1)) + "</ol>"
    cap = f'<figcaption class="shot-cap">{typo(b["caption"], ctx.lang)}</figcaption>' if b.get("caption") else ""
    return (f'<figure class="b b-shot frame-{frame}" data-b="{i}" style="--shot-ar:{w}/{h};--shot-w:{w};--shot-h:{h}">'
            f'<div class="shot-wrap"><div class="shot-frame">{bar}<div class="shot-img">'
            f'<img src="{esc(a["url"])}" alt="{esc(b["alt"])}">{ann_svg}</div></div></div>{legend}{cap}</figure>')


def quote(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    if ctx.lang.startswith("fr"):
        open_q, close_q = "«" + NNBSP, NNBSP + "»"
    elif ctx.lang.startswith("de"):
        open_q, close_q = "„", "“"
    else:
        open_q, close_q = "“", "”"
    meta = [f'<span class="q-name">{typo(b["author"], ctx.lang)}</span>']
    if b.get("role"):
        meta.append(f'<span class="q-role">{typo(b["role"], ctx.lang)}</span>')
    if b.get("translated"):
        meta.append(f'<span class="q-tr">{esc(t(ctx.lang, "translated"))}</span>')
    return (f'<blockquote class="b b-quote" data-b="{i}">'
            f'<p class="q-t" {ctx.fit("quote", 2, i)}><span class="q-mark q-open">{open_q}</span>{typo(b["text"], ctx.lang)}<span class="q-mark q-close">{close_q}</span></p>'
            f'<footer class="q-a">{"".join(meta)}</footer></blockquote>')


def logo_row(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    items = []
    for lg in b["logos"]:
        a = ctx.asset(lg["src"])
        if not a["ok"]:
            items.append(f'<li class="lr-item">{_missing(lg["src"], ctx, i)}</li>')
            continue
        ink = " ink" if lg.get("ink") else ""
        items.append(f'<li class="lr-item"><img class="lr-img{ink}" src="{esc(a["url"])}" alt="{esc(lg["name"])}"></li>')
    label = f'<p class="lr-label">{typo(b["label"], ctx.lang)}</p>' if b.get("label") else ""
    return f'<div class="b b-logos" data-b="{i}" data-count="{len(items)}">{label}<ul class="lr">{"".join(items)}</ul></div>'


def visual(b: Dict[str, Any], i: int, role: str, ctx: Ctx, read_text: Callable[[str], Optional[str]]) -> str:
    svg = b.get("svg")
    if not svg and b.get("file"):
        svg = read_text(b["file"])
        if svg is None:
            return f'<figure class="b b-visual" data-b="{i}">{_missing(b["file"], ctx, i)}</figure>'
    if not svg or "<svg" not in svg:
        ctx.issue("error", "visual-empty", f"block {i}", "visual needs 'svg' (an <svg> element) or 'file'.")
        return f'<figure class="b b-visual" data-b="{i}"><div class="vis"></div></figure>'
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    svg = svg.replace("<svg", f'<svg role="img" aria-label="{esc(b["alt"])}"', 1)
    cap = f'<figcaption class="vis-cap">{typo(b["caption"], ctx.lang)}</figcaption>' if b.get("caption") else ""
    return f'<figure class="b b-visual" data-b="{i}"><div class="vis">{svg}</div>{cap}</figure>'


def cta(b: Dict[str, Any], i: int, role: str, ctx: Ctx) -> str:
    out = [f'<div class="b b-cta" data-b="{i}">', f'<p class="cta-t" {ctx.fit("cta", 1, i)}>{typo(b["text"], ctx.lang, True)}</p>']
    if b.get("url"):
        out.append(f'<p class="cta-url">{esc(b["url"])}</p>')
    if b.get("sub"):
        out.append(f'<p class="cta-sub" {ctx.fit("cta_sub", 5, i)}>{typo(b["sub"], ctx.lang)}</p>')
    out.append("</div>")
    return "".join(out)


RENDERERS = {
    "title": title,
    "body": body,
    "list": list_,
    "stat": stat,
    "chart": chart,
    "photo": photo,
    "screenshot": screenshot,
    "quote": quote,
    "logo-row": logo_row,
    "cta": cta,
}
