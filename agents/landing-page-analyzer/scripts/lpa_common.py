"""lpa_common.py: helpers shared by probe.py, journey.py and fixes.py.

Device profiles, browser launch, page settling, the probe.js measures and
their flat summary, page weight from the network, and the Pillow helpers that
draw side-by-side boards. Not a command: import it.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
PROBE_JS = SCRIPTS / "probe.js"

# Mobile: the Playwright "iPhone 13" descriptor (390 x 664 is the area Safari leaves
# for the page under its bars; the screen is 390 x 844), at DPR 2 so captures stay
# readable without tripling their weight. Desktop: 1280 x 900, the capture-page.py size.
PROFILES: Dict[str, Dict[str, Any]] = {
    "desktop": {
        "viewport": {"width": 1280, "height": 900},
        "screen": {"width": 1280, "height": 900},
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
        "user_agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    },
    "desktop-hd": {
        "viewport": {"width": 1440, "height": 900},
        "screen": {"width": 1440, "height": 900},
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
        "user_agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    },
    "mobile": {
        "viewport": {"width": 390, "height": 664},
        "screen": {"width": 390, "height": 844},
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                       "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    },
}

# Reserved test values: example.com is reserved by RFC 2606, 555-0100 to 555-0199
# are reserved for fiction in the North American numbering plan.
TEST_DATA_DEFAULTS = {
    "email": "lpa-test@example.com",
    "first_name": "Test",
    "last_name": "Visitor",
    "full_name": "Test Visitor",
    "phone": "+1 202 555 0143",
    "company": "Example Test Co",
    "website": "https://example.com",
    "message": "Automated audit test, please ignore. No reply needed.",
    "postal_code": "75002",
    "city": "Paris",
}
TEST_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
TEST_EMAIL_TLDS = (".test", ".invalid", ".example")


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def die(msg: str, code: int = 2) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def need_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        import playwright
    except ImportError:
        die("Playwright is missing: pip install -r scripts/requirements.txt && playwright install chromium")
    from playwright.sync_api import sync_playwright
    return sync_playwright


def parse_viewports(value: str) -> List[str]:
    names = [v.strip() for v in value.split(",") if v.strip()]
    bad = [n for n in names if n not in PROFILES]
    if bad:
        die(f"unknown viewport {bad}; known: {', '.join(PROFILES)}")
    return names


def launch(p):
    return p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])


def new_context(browser, name: str, locale: str = "en-US", timezone: str = "UTC", init_js: Optional[List[str]] = None, **extra):
    prof = PROFILES[name]
    ctx = browser.new_context(
        viewport=prof["viewport"], screen=prof["screen"], device_scale_factor=prof["device_scale_factor"],
        is_mobile=prof["is_mobile"], has_touch=prof["has_touch"], user_agent=prof["user_agent"],
        locale=locale, timezone_id=timezone, service_workers="block", **extra,
    )
    ctx.add_init_script(path=str(PROBE_JS))
    for js in init_js or []:
        ctx.add_init_script(script=js)
    return ctx


def context_record(browser, name: str, locale: str, timezone: str) -> Dict[str, Any]:
    prof = PROFILES[name]
    return {
        "profile": name, "viewport": prof["viewport"], "screen": prof["screen"],
        "device_scale_factor": prof["device_scale_factor"], "is_mobile": prof["is_mobile"],
        "has_touch": prof["has_touch"], "user_agent": prof["user_agent"], "locale": locale,
        "timezone": timezone, "browser": f"chromium {browser.version}",
    }


def settle(page, ms: int = 1200) -> None:
    for state, timeout in (("load", 10000), ("networkidle", 5000)):
        try:
            page.wait_for_load_state(state, timeout=timeout)
        except Exception:
            pass
    page.wait_for_timeout(ms)


def scroll_through(page, pause_ms: int = 200) -> None:
    """Scroll one screen at a time to the bottom (lazy content loads, shifts happen), then back to the top."""
    h = page.evaluate("innerHeight")
    pos = 0
    for _ in range(80):
        total = page.evaluate("document.documentElement.scrollHeight")
        if pos >= total:
            break
        pos += h
        page.evaluate(f"window.scrollTo(0, {pos})")
        page.wait_for_timeout(pause_ms)
    page.wait_for_timeout(600)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(pause_ms)


def measure(page, primary: Optional[str] = None, contrast: bool = True) -> Dict[str, Any]:
    return page.evaluate("(cfg) => window.__lpa.measure(cfg)", {"primary": primary, "contrast": contrast})


class Weight:
    """Bytes on the wire per page load, from Playwright's request sizes."""

    def __init__(self, page_url: str):
        self.host = urlparse(page_url).hostname or ""
        self.items: List[Dict[str, Any]] = []
        self.failed = 0

    def attach(self, page) -> None:
        page.on("requestfinished", self._done)
        page.on("requestfailed", lambda r: setattr(self, "failed", self.failed + 1))

    def _done(self, req) -> None:
        try:
            s = req.sizes()
            size = int(s.get("responseBodySize", 0)) + int(s.get("responseHeadersSize", 0))
        except Exception:
            size = 0
        self.items.append({"url": req.url, "type": req.resource_type, "bytes": max(size, 0),
                           "third_party": (urlparse(req.url).hostname or "") not in ("", self.host)})

    def summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        for it in self.items:
            by_type[it["type"]] = by_type.get(it["type"], 0) + it["bytes"]
        total = sum(it["bytes"] for it in self.items)
        heavy = sorted(self.items, key=lambda i: -i["bytes"])[:5]
        return {
            "total_kb": round(total / 1024, 1), "requests": len(self.items), "failed_requests": self.failed,
            "by_type_kb": {k: round(v / 1024, 1) for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])},
            "third_party_kb": round(sum(i["bytes"] for i in self.items if i["third_party"]) / 1024, 1),
            "third_party_hosts": sorted({urlparse(i["url"]).hostname for i in self.items if i["third_party"]} - {None})[:20],
            "heaviest": [{"url": h["url"][-90:], "type": h["type"], "kb": round(h["bytes"] / 1024, 1)} for h in heavy],
        }


def summarize(m: Dict[str, Any], weight: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flat metrics of one viewport: the keys evidence refs and fixes.json expectations use."""
    prim = (m.get("ctas") or {}).get("primary") or {}
    contrast = m.get("contrast") or {}
    forms = m.get("forms") or {}
    s = {
        "overflow_x_px": m["overflow"]["overflow_x_px"],
        "overflow_offenders": m["overflow"]["offenders_count"],
        "targets": m["targets"]["targets"],
        "targets_under_24": m["targets"]["under_24_count"],
        "targets_under_24_raw": m["targets"]["under_24_raw_count"],
        "targets_under_44": m["targets"]["under_44_count"],
        "text_under_16": m["text"]["under_16_count"],
        "text_under_12": m["text"]["under_12_count"],
        "text_share_under_16": m["text"]["share_under_16"],
        "inputs_under_16": len(m["text"]["inputs_under_16"]),
        "contrast_checked": contrast.get("checked", 0),
        "contrast_failures": contrast.get("failures_count", 0),
        "contrast_undetermined": contrast.get("undetermined_count", 0),
        "primary_cta": prim.get("text"),
        "primary_cta_bottom_px": prim.get("bottom"),
        "primary_cta_above_fold": int(bool(prim.get("above_fold"))) if prim else 0,
        "primary_cta_above_screen": int(bool(prim.get("above_screen"))) if prim else 0,
        "fold_px": m["ctas"]["fold_px"],
        "screen_px": m["ctas"]["screen_px"],
        "ctas": m["ctas"]["ctas_count"],
        "sticky_cover_pct": m["sticky"]["cover_pct"],
        "cls_observed": m["cls"]["cls"],
        "layout_shifts": m["cls"]["shifts"],
        "images_without_dimensions": m["images"]["without_dimensions_count"],
        "lazy_images_above_fold": m["images"]["lazy_above_fold_count"],
        "broken_images": m["images"]["broken_count"],
        "img_missing_alt": m["images"]["missing_alt_count"],
        "lcp_is_lazy": int(bool((m["images"].get("lcp") or {}).get("lazy"))),
        "h1_count": m["meta"]["h1_count"],
        "viewport_meta": int(bool(m["meta"]["viewport_meta"])),
        "zoom_disabled": int(bool(m["meta"]["zoom_disabled"])),
        "unnamed_controls": m["meta"]["unnamed_controls_count"],
        "forms": forms.get("forms_count", 0),
        "form_fields": forms.get("fields_count", 0),
        "form_issues": forms.get("issues_count", 0),
    }
    if weight:
        s["page_weight_kb"] = weight["total_kb"]
        s["requests"] = weight["requests"]
        s["third_party_kb"] = weight["third_party_kb"]
    return s


# ---- expectations: "mobile.overflow_x_px <= 0" ------------------------------------------
OPS = {"<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b, "==": lambda a, b: a == b,
       "<": lambda a, b: a < b, ">": lambda a, b: a > b, "!=": lambda a, b: a != b}


def parse_expect(expr: str):
    for op in ("<=", ">=", "==", "!=", "<", ">"):
        if op in expr:
            left, right = expr.split(op, 1)
            left, right = left.strip(), right.strip()
            if "." not in left:
                raise ValueError(f"expectation {expr!r}: write <viewport>.<metric>")
            vp, metric = left.split(".", 1)
            try:
                value = float(right)
            except ValueError:
                raise ValueError(f"expectation {expr!r}: right side must be a number")
            return vp, metric, op, value
    raise ValueError(f"expectation {expr!r}: no operator (<=, >=, ==, !=, <, >)")


# ---- images ---------------------------------------------------------------------------------
def font(size: int):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def side_by_side(left: Path, right: Path, out: Path, title: str, lines: List[str], labels=("before", "after"), max_w: int = 1600) -> Path:
    """Two captures next to each other under a header (title plus measure lines)."""
    from PIL import Image, ImageDraw
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    gap, pad = 24, 24
    w = a.width + b.width + gap + 2 * pad
    scale = min(1.0, max_w / w)
    if scale < 1:
        a = a.resize((max(1, int(a.width * scale)), max(1, int(a.height * scale))))
        b = b.resize((max(1, int(b.width * scale)), max(1, int(b.height * scale))))
        w = a.width + b.width + gap + 2 * pad
    f_title, f_line = font(26), font(20)
    head = pad + 34 + 28 * len(lines) + 40
    h = head + max(a.height, b.height) + pad
    img = Image.new("RGB", (w, h), (246, 246, 244))
    d = ImageDraw.Draw(img)
    d.text((pad, pad), title, fill=(17, 17, 17), font=f_title)
    for i, line in enumerate(lines):
        d.text((pad, pad + 40 + 28 * i), line, fill=(60, 60, 60), font=f_line)
    y = head
    d.text((pad, y - 30), labels[0], fill=(150, 30, 30), font=f_line)
    d.text((pad + a.width + gap, y - 30), labels[1], fill=(20, 110, 50), font=f_line)
    img.paste(a, (pad, y))
    img.paste(b, (pad + a.width + gap, y))
    d.rectangle([pad - 1, y - 1, pad + a.width, y + a.height], outline=(190, 190, 190))
    d.rectangle([pad + a.width + gap - 1, y - 1, pad + a.width + gap + b.width, y + b.height], outline=(190, 190, 190))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def stack_board(images: List[Path], out: Path, width: int = 1200, quality: int = 80) -> Path:
    """Stack images vertically at one width, saved as JPEG (boards and previews)."""
    from PIL import Image
    tiles = []
    for p in images:
        im = Image.open(p).convert("RGB")
        if im.width != width:
            im = im.resize((width, max(1, int(im.height * width / im.width))))
        tiles.append(im)
    h = sum(t.height for t in tiles) + 12 * max(0, len(tiles) - 1)
    board = Image.new("RGB", (width, max(1, h)), (255, 255, 255))
    y = 0
    for t in tiles:
        board.paste(t, (0, y))
        y += t.height + 12
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
