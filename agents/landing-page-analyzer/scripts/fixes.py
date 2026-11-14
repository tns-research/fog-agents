#!/usr/bin/env python3
"""fixes.py: apply the fixes the model wrote in fixes.json to the live page and render
them before and after, side by side, per viewport, with the measures that prove them.

  python3 scripts/fixes.py <fixes.json> --out <dir> [--url BASE_URL] [--only ID] [--combined]
  python3 scripts/fixes.py <fixes.json> --lint

The spec (contract in skills/proposing-fixes/SKILL.md, schema in assets/fixes.schema.json):

  {"url": "https://acme.example/", "primary_cta": "Book a demo", "viewports": ["desktop", "mobile"],
   "fixes": [
     {"id": "01-mobile-overflow", "title": "Keep the pricing table inside the screen",
      "criteria": ["U039"], "evidence": ["probe:mobile.overflow_x_px"],
      "viewports": ["mobile"], "focus": ".pricing", "url": "pricing.html",
      "css": [{"selector": ".pricing table", "media": "(max-width: 799px)",
               "declarations": {"width": "100%"}}],
      "text": [{"selector": "h1", "text": "New headline"}],
      "attributes": [{"selector": "#email", "set": {"type": "email", "autocomplete": "email"}}],
      "insert": [{"selector": "#phone", "position": "beforebegin", "html": "<label for=\\"phone\\">Phone</label>"}],
      "expect": ["mobile.overflow_x_px <= 0"]}]}

How it renders: the page loads twice per viewport in a fresh browser context, once as
is and once with the patch injected by an init script (CSS from the first byte, every
declaration !important; text, attributes and inserted HTML on DOMContentLoaded, on
load and on later DOM changes for 5 s). So "after" is a real load: the fold, the
layout shifts and every probe.js measure are taken the same way as probe.py takes
them (settle, scroll to the bottom, measure). A selector that matches nothing fails
the fix. Each "expect" line (<viewport>.<metric> <op> <number>, metric keys of the
probe summary) is checked on the after measures.

Writes, per fix, <out>/fixes/<id>/: before-<viewport>.png, after-<viewport>.png,
compare-<viewport>.png (before and after side by side, the measures above them),
patch.css and patch.js (what a developer copies), fix.json (measures before and after,
expectations, unmatched selectors, the CSS rules as written, and under "ops" each text,
attribute and insert change with the elements it matched as they were before the
change: tag, id, classes, text, opening tag, the attributes it changes; repo_patch.py
finds them in the site source with it). Plus <out>/fixes/fixes.json (all results),
<out>/fixes/fixes.md (table for the report) and <out>/fixes/board.jpg (every compare
image stacked, 1200 px wide). --combined adds the variant "all" with every patch at once.

Exit 0 when every fix applied and met its expectations, 1 when one did not, 2 fatal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lpa_common as C  # noqa: E402

PATCH_JS = r"""
(() => {
  if (window.top !== window) return;
  const P = __PATCH__;
  const report = window.__lpaFix = { css_unmatched: [], ops: [] };
  const placeStyle = () => {
    let s = document.getElementById('__lpa_fix');
    const root = document.head || document.documentElement;
    if (!root) return false;
    if (!s) { s = document.createElement('style'); s.id = '__lpa_fix'; s.textContent = P.css; }
    const parent = document.body || root;
    if (s.parentNode !== parent || s !== parent.lastElementChild) parent.appendChild(s);
    return true;
  };
  if (!placeStyle()) {
    const mo = new MutationObserver(() => { if (placeStyle()) mo.disconnect(); });
    mo.observe(document, { childList: true, subtree: true });
  }
  const seen = {};
  const targets = {};
  const described = new WeakMap();
  const sig = (el) => el ? { tag: el.tagName.toLowerCase(), id: el.id || null, classes: [...el.classList] } : null;
  const describe = (el, op) => {
    const html = el.outerHTML || '';
    const keys = op.kind === 'attributes' ? [...Object.keys(op.set || {}), ...(op.remove || [])] : [];
    return Object.assign(sig(el), {
      href: el.getAttribute('href'),
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 600),
      open: html.slice(0, html.indexOf('>') + 1).slice(0, 400),
      attrs: Object.fromEntries(keys.map(k => [k, el.getAttribute(k)])),
      parent: sig(el.parentElement),
    });
  };
  const apply = () => {
    for (const [i, op] of P.ops.entries()) {
      let els = [];
      try { els = [...document.querySelectorAll(op.selector)]; } catch (e) { report.ops[i] = { selector: op.selector, error: 'bad selector' }; continue; }
      seen[i] = Math.max(seen[i] || 0, els.length);
      for (const el of els) {
        const done = described.get(el) || {};
        if (!done[i]) {
          done[i] = 1; described.set(el, done);
          targets[i] = targets[i] || [];
          if (targets[i].length < 5) targets[i].push(describe(el, op));
        }
        if (op.kind === 'text' && el.textContent !== op.text) el.textContent = op.text;
        if (op.kind === 'attributes') {
          for (const [k, v] of Object.entries(op.set || {})) if (el.getAttribute(k) !== String(v)) el.setAttribute(k, String(v));
          for (const k of op.remove || []) el.removeAttribute(k);
        }
        if (op.kind === 'insert' && !el.dataset['lpaInserted' + i]) { el.dataset['lpaInserted' + i] = '1'; el.insertAdjacentHTML(op.position || 'afterend', op.html); }
      }
      report.ops[i] = { kind: op.kind, selector: op.selector, matched: seen[i], targets: targets[i] || [] };
    }
  };
  const run = () => { placeStyle(); apply(); };
  document.addEventListener('DOMContentLoaded', run);
  window.addEventListener('load', run);
  const t0 = Date.now();
  const mo2 = new MutationObserver(() => { if (Date.now() - t0 > 5000) { mo2.disconnect(); return; } if (document.body) apply(); });
  mo2.observe(document, { childList: true, subtree: true });
  window.__lpaFixCheck = () => {
    report.css_unmatched = P.css_selectors.filter(s => { try { return !document.querySelector(s); } catch (e) { return true; } });
    return report;
  };
})();
"""


def css_of(fix: Dict[str, Any]) -> (str, List[str]):
    rules, sels = [], []
    for r in fix.get("css", []) or []:
        decl = "; ".join(f"{k}: {str(v).replace('!important', '').strip()} !important" for k, v in r["declarations"].items())
        block = f"{r['selector']} {{ {decl}; }}"
        if r.get("media"):
            block = f"@media {r['media']} {{ {block} }}"
        rules.append(block)
        sels.append(r["selector"])
    if fix.get("css_raw"):
        rules.append(fix["css_raw"])
    return "\n".join(rules), sels


def ops_of(fix: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops = []
    for t in fix.get("text", []) or []:
        ops.append({"kind": "text", "selector": t["selector"], "text": t["text"]})
    for a in fix.get("attributes", []) or []:
        ops.append({"kind": "attributes", "selector": a["selector"], "set": a.get("set", {}), "remove": a.get("remove", [])})
    for ins in fix.get("insert", []) or []:
        ops.append({"kind": "insert", "selector": ins["selector"], "position": ins.get("position", "afterend"), "html": ins["html"]})
    return ops


def readable_js(ops: List[Dict[str, Any]]) -> str:
    lines = ["// Text, attribute and markup changes of this fix. Apply them in the page source when possible."]
    for op in ops:
        sel = json.dumps(op["selector"])
        if op["kind"] == "text":
            lines.append(f"document.querySelectorAll({sel}).forEach(el => {{ el.textContent = {json.dumps(op['text'], ensure_ascii=False)}; }});")
        elif op["kind"] == "attributes":
            for k, v in op["set"].items():
                lines.append(f"document.querySelectorAll({sel}).forEach(el => el.setAttribute({json.dumps(k)}, {json.dumps(str(v))}));")
            for k in op["remove"]:
                lines.append(f"document.querySelectorAll({sel}).forEach(el => el.removeAttribute({json.dumps(k)}));")
        else:
            lines.append(f"document.querySelectorAll({sel}).forEach(el => el.insertAdjacentHTML({json.dumps(op['position'])}, {json.dumps(op['html'], ensure_ascii=False)}));")
    return "\n".join(lines) + "\n"


def lint(spec: Dict[str, Any]) -> List[str]:
    errs = []
    fixes = spec.get("fixes")
    if not isinstance(fixes, list) or not fixes:
        return ["fixes: a non-empty list is required"]
    ids = set()
    for i, f in enumerate(fixes, 1):
        where = f"fixes[{i}]"
        if not f.get("id"):
            errs.append(f"{where}: id is required")
        elif f["id"] in ids:
            errs.append(f"{where}: duplicate id {f['id']}")
        ids.add(f.get("id"))
        if not f.get("title"):
            errs.append(f"{where}: title is required")
        if not any(f.get(k) for k in ("css", "css_raw", "text", "attributes", "insert")):
            errs.append(f"{where}: no change (css, css_raw, text, attributes or insert)")
        if not f.get("evidence"):
            errs.append(f"{where}: evidence is required (the probe measure, journey capture or finding the fix answers)")
        for r in f.get("css", []) or []:
            if not r.get("selector") or not isinstance(r.get("declarations"), dict) or not r["declarations"]:
                errs.append(f"{where}: each css rule needs selector and declarations")
        for e in f.get("expect", []) or []:
            try:
                vp, metric, op, val = C.parse_expect(e)
                if vp not in C.PROFILES:
                    errs.append(f"{where}: expectation {e!r}: unknown viewport {vp}")
            except ValueError as ex:
                errs.append(f"{where}: {ex}")
        for t in f.get("text", []) or []:
            if "\u2014" in t.get("text", "") or "\u2013" in t.get("text", ""):
                errs.append(f"{where}: text holds an em or en dash")
        for v in f.get("viewports", []) or []:
            if v not in C.PROFILES:
                errs.append(f"{where}: unknown viewport {v}")
    return errs


def load_and_measure(browser, url: str, vp: str, primary, args, init_js=None):
    ctx = C.new_context(browser, vp, args.locale, args.timezone, init_js=init_js)
    page = ctx.new_page()
    weight = C.Weight(url)
    weight.attach(page)
    resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
    if resp is not None and resp.status >= 400:
        ctx.close()
        raise RuntimeError(f"HTTP {resp.status} on {url}")
    C.settle(page, args.settle_ms)
    C.scroll_through(page)
    m = C.measure(page, primary)
    return ctx, page, C.summarize(m, weight.summary())


def capture(page, path: Path, focus, mode: str) -> None:
    page.evaluate("window.scrollTo(0, 0)")
    if focus:
        page.evaluate("""(s) => { const el = document.querySelector(s); if (el) { el.scrollIntoView({block: 'start'}); window.scrollBy(0, -24); } }""", focus)
    page.wait_for_timeout(250)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "full":
        vp = page.viewport_size
        total = page.evaluate("document.documentElement.scrollHeight")
        page.screenshot(path=str(path), full_page=True, clip={"x": 0, "y": 0, "width": vp["width"], "height": min(total, vp["height"] * 4)})
    else:
        page.screenshot(path=str(path))


def run_fix(browser, spec, fix, base: str, out: Path, run_vps: List[str], args) -> Dict[str, Any]:
    url = urljoin(base, fix["url"]) if fix.get("url") else base
    css, css_sels = css_of(fix)
    ops = ops_of(fix)
    patch = PATCH_JS.replace("__PATCH__", json.dumps({"css": css, "ops": ops, "css_selectors": css_sels}, ensure_ascii=False))
    d = out / "fixes" / fix["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "patch.css").write_text((css or "/* no CSS change */") + "\n", encoding="utf-8")
    (d / "patch.js").write_text(readable_js(ops), encoding="utf-8")
    vps = [v for v in (fix.get("viewports") or run_vps) if v in run_vps]
    expects = [C.parse_expect(e) + (e,) for e in fix.get("expect", []) or []]
    shown = []
    for e in fix.get("evidence", []):
        if e.startswith("probe:") and "." in e[6:]:
            vp, metric = e[6:].split(".", 1)
            shown.append((vp, metric))
    for vp, metric, _, _, _ in expects:
        shown.append((vp, metric))
    res: Dict[str, Any] = {"id": fix["id"], "title": fix["title"], "url": url, "criteria": fix.get("criteria", []),
                           "evidence": fix.get("evidence", []), "viewports": {}, "unmatched": [], "expectations": [], "status": "pass",
                           "css": fix.get("css", []) or [], "css_raw": fix.get("css_raw") or ""}
    primary = fix.get("primary_cta") or spec.get("primary_cta")
    for vp in vps:
        ctx, page, before = load_and_measure(browser, url, vp, primary, args)
        capture(page, d / f"before-{vp}.png", fix.get("focus"), fix.get("shot", "viewport"))
        ctx.close()
        ctx, page, after = load_and_measure(browser, url, vp, primary, args, init_js=[patch])
        check = page.evaluate("() => window.__lpaFixCheck ? window.__lpaFixCheck() : null") or {}
        capture(page, d / f"after-{vp}.png", fix.get("focus"), fix.get("shot", "viewport"))
        ctx.close()
        if "ops" not in res:
            seen_ops = check.get("ops") or []
            res["ops"] = [dict(o, targets=((seen_ops[i] if i < len(seen_ops) else None) or {}).get("targets", [])) for i, o in enumerate(ops)]
        for s in check.get("css_unmatched", []):
            res["unmatched"].append({"viewport": vp, "kind": "css", "selector": s})
        for op in check.get("ops", []):
            if op and (op.get("error") or not op.get("matched")):
                res["unmatched"].append({"viewport": vp, "kind": op.get("kind"), "selector": op.get("selector"), "error": op.get("error")})
        lines = []
        metrics = [m for v, m in shown if v == vp]
        for m in dict.fromkeys(metrics):
            lines.append(f"{m}: {before.get(m)} -> {after.get(m)}")
        for evp, metric, op, val, text in expects:
            if evp != vp:
                continue
            got = after.get(metric)
            ok = got is not None and C.OPS[op](float(got), val)
            res["expectations"].append({"expect": text, "before": before.get(metric), "after": got, "met": ok})
            lines.append(f"expect {text}: {'met' if ok else 'NOT met'}")
            if not ok:
                res["status"] = "fail"
        C.side_by_side(d / f"before-{vp}.png", d / f"after-{vp}.png", d / f"compare-{vp}.png",
                       f"{fix['id']}  |  {vp}  |  {fix['title']}", lines or ["(no measure named for this viewport)"])
        res["viewports"][vp] = {"before": before, "after": after, "compare": f"{fix['id']}/compare-{vp}.png"}
    if res["unmatched"]:
        res["status"] = "fail"
    seen = set()
    res["unmatched"] = [u for u in res["unmatched"] if not (json.dumps(u, sort_keys=True) in seen or seen.add(json.dumps(u, sort_keys=True)))]
    C.write_json(d / "fix.json", res)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="fixes.json")
    ap.add_argument("--out", help="output folder (fixes/ is created inside)")
    ap.add_argument("--url", help="base URL, overrides the spec url (a fix url resolves against it)")
    ap.add_argument("--viewports", help="comma list, overrides the spec (default desktop,mobile)")
    ap.add_argument("--only", help="run one fix id")
    ap.add_argument("--combined", action="store_true", help="also render every patch at once (variant 'all', first screen)")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--timezone", default="UTC")
    ap.add_argument("--settle-ms", type=int, default=1200)
    ap.add_argument("--preview", help="also write a light JPEG preview (900 px wide) of the mobile compare images to this path")
    ap.add_argument("--preview-ids", help="comma list of fix ids for --preview (default: every fix)")
    ap.add_argument("--lint", action="store_true")
    args = ap.parse_args()
    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except Exception as e:
        C.die(f"cannot read {args.spec}: {e}")
    errs = lint(spec)
    if errs:
        for e in errs:
            print(f"spec error: {e}", file=sys.stderr)
        return 2
    if args.lint:
        print(f"spec ok: {len(spec['fixes'])} fixes")
        return 0
    if not args.out:
        C.die("--out is required unless --lint")
    base = args.url or spec.get("url")
    if not base:
        C.die("no base URL: set url in the spec or pass --url")
    run_vps = C.parse_viewports(args.viewports or ",".join(spec.get("viewports", ["desktop", "mobile"])))
    fixes = [f for f in spec["fixes"] if not args.only or f["id"] == args.only]
    if not fixes:
        C.die(f"no fix with id {args.only}")
    if args.combined:
        same_url = [f for f in fixes if not f.get("url")]
        merged = {"id": "all", "title": "every fix of this page at once", "evidence": ["fix:" + f["id"] for f in same_url],
                  "criteria": sorted({c for f in same_url for c in f.get("criteria", [])}),
                  "css": [r for f in same_url for r in f.get("css", []) or []],
                  "css_raw": "\n".join(f["css_raw"] for f in same_url if f.get("css_raw")),
                  "text": [t for f in same_url for t in f.get("text", []) or []],
                  "attributes": [a for f in same_url for a in f.get("attributes", []) or []],
                  "insert": [i for f in same_url for i in f.get("insert", []) or []],
                  "expect": [e for f in same_url for e in f.get("expect", []) or []]}
        fixes = fixes + [merged]
    out = Path(args.out)
    sync_playwright = C.need_playwright()
    results = []
    with sync_playwright() as p:
        browser = C.launch(p)
        for fix in fixes:
            try:
                r = run_fix(browser, spec, fix, base, out, run_vps, args)
            except Exception as e:
                r = {"id": fix["id"], "title": fix.get("title"), "status": "fail", "error": str(e).splitlines()[0][:300], "viewports": {}}
            results.append(r)
            extra = f", unmatched {r.get('unmatched')}" if r.get("unmatched") else ""
            extra += f", error {r['error']}" if r.get("error") else ""
            exp = "; ".join(f"{x['expect']} ({x['before']} -> {x['after']}, {'met' if x['met'] else 'NOT met'})" for x in r.get("expectations", []))
            print(f"{r['id']}: {r['status']}{extra}{(': ' + exp) if exp else ''}")
        browser.close()
    C.write_json(out / "fixes" / "fixes.json", {"tool": "fixes.py", "spec": Path(args.spec).name, "url": base,
                                                 "rendered_at": C.now_iso(), "fixes": results})
    md = ["| Fix | Criteria | Viewport | Measures before -> after | Compare |", "|-----|----------|----------|--------------------------|---------|"]
    compares = []
    for r in results:
        for vp, v in r.get("viewports", {}).items():
            meas = "; ".join(f"{x['expect']}: {x['before']} -> {x['after']}" for x in r.get("expectations", []) if x["expect"].startswith(vp + ".")) or "visual only"
            md.append(f"| {r['id']} {r['title']} | {', '.join(r.get('criteria', []))} | {vp} | {meas} | `fixes/{v['compare']}` |")
            compares.append(out / "fixes" / v["compare"])
    (out / "fixes" / "fixes.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if compares:
        C.stack_board(compares, out / "fixes" / "board.jpg")
    if args.preview:
        want = args.preview_ids.split(",") if args.preview_ids else [r["id"] for r in results]
        imgs = [out / "fixes" / r["viewports"]["mobile"]["compare"] for rid in want for r in results
                if r["id"] == rid and "mobile" in r.get("viewports", {})]
        if imgs:
            prev = C.stack_board(imgs, Path(args.preview), width=900, quality=62)
            kb = prev.stat().st_size / 1024
            print(f"preview {prev} ({kb:.0f} KB){'  WARNING: over 150 KB, keep repo previews light' if kb > 150 else ''}")
    print(f"wrote {out / 'fixes' / 'fixes.json'}")
    return 0 if all(r["status"] == "pass" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
