#!/usr/bin/env python3
"""probe.py: measure a landing page in the DOM instead of judging a screenshot by eye.

  python3 scripts/probe.py <url> --out <dir> [--cta "Book a demo"] [--viewports desktop,mobile]
                           [--locale en-US] [--timezone UTC] [--no-annotate]

Per viewport (desktop 1280 x 900; mobile = Playwright iPhone 13: 390 x 664 visible
area, 390 x 844 screen, touch, DPR 2), after load, settle and one scroll to the
bottom (lazy content renders, late shifts happen):

  overflow    horizontal overflow in px (scrollWidth minus viewport width) and the
              outermost elements that stick out (WCAG 1.4.10 Reflow)
  targets     tap targets failing WCAG 2.2 2.5.8 (under 24 x 24 CSS px, inline links
              in a sentence and native checkboxes exempt, spacing exception applied),
              the raw count under 24 px, and the count under 44 px (Apple HIG)
  text        text under 16 px and under 12 px, share of characters under 16 px,
              inputs under 16 px
  contrast    WCAG ratio per text node against the colour really painted under it
              (elementsFromPoint): 4.5:1, 3:1 for large text; text over images is
              listed as undetermined, never guessed
  ctas        every button-like element with its destination (anchor, internal,
              external, form), the primary CTA (--cta text, else the largest
              button-like element in the first 1.5 screens) and whether it ends above
              the fold (inner height) and above the screen height
  sticky      fixed and sticky elements and the share of the first screen they cover
  cls         layout shifts observed on this load (largest session window, inputs
              excluded) with the nodes that moved; field CLS stays page_speed's job
  images      images without width and height (and no CSS aspect-ratio), lazy images
              in the first screen, broken images, missing alt, the LCP element
  forms       fields with their accessible label source (label, aria, placeholder
              only, none), type and autocomplete against the field's purpose, field
              count, single column, submit label
  meta        viewport meta, zoom disabled, H1 list, controls without a name
  weight      bytes on the wire by resource type, third-party share, heaviest files

Writes <out>/probe.json (full measures plus a flat "summary" per viewport, the keys
used by evidence refs and fixes.json) and, unless --no-annotate, one annotated
full-page PNG per viewport (<out>/probe-<viewport>.png, capped at 8 screens):
red = target failing 2.5.8, magenta = overflow offender, orange = contrast failure,
blue line = fold, dotted blue line = screen height.

Exit 0 when every viewport was measured, 1 when one failed to load or measure,
2 on a fatal error (Playwright missing, bad arguments).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpa_common as C  # noqa: E402

MAX_SCREENS = 8


def annotate(png: Path, m: dict, dpr: float, fold: int, screen_h: int) -> None:
    from PIL import Image, ImageDraw
    img = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(img)
    s = dpr

    def box(it, color, width=3):
        x, y, w, h = it.get("x", 0), it.get("y", 0), it.get("w", 0), it.get("h", 0)
        if y * s > img.height:
            return
        d.rectangle([x * s, y * s, (x + w) * s, (y + h) * s], outline=color, width=width)

    for it in (m.get("contrast") or {}).get("failures", []):
        box(it, (255, 140, 0), 2)
    for it in m["overflow"]["offenders"]:
        box(it, (210, 0, 210), 4)
    for it in m["targets"]["under_24"]:
        box(it, (230, 0, 0), 3)
    d.line([0, fold * s, img.width, fold * s], fill=(0, 90, 255), width=3)
    if screen_h != fold:
        for x in range(0, img.width, 24):
            d.line([x, screen_h * s, x + 12, screen_h * s], fill=(0, 90, 255), width=3)
    img.save(png)


def run_viewport(browser, url: str, name: str, args, out: Path) -> dict:
    ctx = C.new_context(browser, name, args.locale, args.timezone)
    page = ctx.new_page()
    weight = C.Weight(url)
    weight.attach(page)
    t0 = time.time()
    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if resp is not None and resp.status >= 400:
        ctx.close()
        raise RuntimeError(f"HTTP {resp.status} on {url}: nothing to measure")
    C.settle(page, args.settle_ms)
    C.scroll_through(page)
    m = C.measure(page, args.cta)
    w = weight.summary()
    rec = {
        "context": C.context_record(browser, name, args.locale, args.timezone),
        "status": resp.status if resp else None,
        "final_url": page.url,
        "seconds": round(time.time() - t0, 1),
        "measures": m,
        "weight": w,
        "summary": C.summarize(m, w),
    }
    if not args.no_annotate:
        png = out / f"probe-{name}.png"
        prof = C.PROFILES[name]
        total = page.evaluate("document.documentElement.scrollHeight")
        h = min(total, prof["viewport"]["height"] * MAX_SCREENS)
        page.screenshot(path=str(png), full_page=True, clip={"x": 0, "y": 0, "width": prof["viewport"]["width"], "height": h})
        annotate(png, m, prof["device_scale_factor"], m["ctas"]["fold_px"], m["ctas"]["screen_px"])
        rec["annotated"] = png.name
    ctx.close()
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", required=True, help="output folder (created)")
    ap.add_argument("--cta", help="visible text of the primary CTA (else the largest button-like element of the first 1.5 screens)")
    ap.add_argument("--viewports", default="desktop,mobile", help=f"comma list of {', '.join(C.PROFILES)}")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--timezone", default="UTC")
    ap.add_argument("--settle-ms", type=int, default=1200)
    ap.add_argument("--no-annotate", action="store_true")
    args = ap.parse_args()
    names = C.parse_viewports(args.viewports)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sync_playwright = C.need_playwright()
    result = {"tool": "probe.py", "url": args.url, "captured_at": C.now_iso(), "primary_cta_given": args.cta,
              "viewports": {}, "summary": {}, "errors": []}
    code = 0
    with sync_playwright() as p:
        browser = C.launch(p)
        for name in names:
            try:
                rec = run_viewport(browser, args.url, name, args, out)
                result["viewports"][name] = rec
                result["summary"][name] = rec["summary"]
                s = rec["summary"]
                print(f"{name}: overflow {s['overflow_x_px']} px, targets <24 {s['targets_under_24']} (raw {s['targets_under_24_raw']}), "
                      f"<44 {s['targets_under_44']}, text <16 {s['text_under_16']}, contrast fails {s['contrast_failures']}, "
                      f"primary CTA {'above' if s['primary_cta_above_fold'] else 'below'} fold ({s['primary_cta_bottom_px']} / {s['fold_px']} px), "
                      f"CLS {s['cls_observed']}, imgs w/o dims {s['images_without_dimensions']}, form issues {s['form_issues']}, "
                      f"{s.get('page_weight_kb')} KB")
            except Exception as e:  # keep the other viewport
                code = 1
                result["errors"].append({"viewport": name, "error": str(e).splitlines()[0][:300]})
                print(f"{name}: FAILED {str(e).splitlines()[0][:200]}", file=sys.stderr)
        browser.close()
    C.write_json(out / "probe.json", result)
    print(f"wrote {out / 'probe.json'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
