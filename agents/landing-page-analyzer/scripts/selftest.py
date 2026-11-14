#!/usr/bin/env python3
"""selftest.py: offline regression test of probe.py, journey.py, fixes.py, repo_patch.py
and check_evidence.py.

  python3 scripts/selftest.py [--keep DIR] [--only policy|probe|journey|fixes|repo|evidence]

Serves the fixture examples/northdock-apply-fixture/site/ with `python3 -m http.server`
on a free local port (no network needed), then:

1. policy    classify() of journey.py on 26 request cases (writes, final steps,
             payment hosts, GET forms carrying test data, allow_write, block lists;
             after a fill, a pixel, a JSONP script, a document and a beacon carrying
             the typed e-mail on a non-final step; an allowed write whose URL or
             body carries test data), the spec lint refusing a real-looking e-mail,
             an unknown verb and too-broad allow_write patterns ("/", "*", short,
             bare host), and the check_links filter skipping logout, signout,
             unsubscribe and delete links.
2. probe     probe.py on the landing and the form page; checks each planted defect
             is measured: mobile overflow 21 px from the program table, 8 targets
             failing WCAG 2.5.8 (14 under 24 px before exceptions), the primary CTA
             below the mobile fold but above the screen height and above the desktop
             fold, 2 contrast failures, observed CLS over 0.1 on mobile, 1 image without
             dimensions and lazy in the first screen, 1 image without alt, 2 H1, 3
             newsletter field issues, 6 issues on the application form.
3. journey   journey.py on the fixture journey (19 steps, desktop and mobile); checks
             every step ran, the two final sends were blocked (fetch POST /api/apply,
             document POST /subscribe) and confirmed by the browser, inline errors sit
             next to their fields, values survive the error, the button shows a loading
             state, the nav links lack a focus indicator, the dead footer link is found,
             the phone field is found by placeholder only, the captures exist; then
             a spec with a missing button exits 1 with a "-failed" capture.
4. fixes     fixes.py on the 5 fixture fixes: each applies, meets its expectations, and
             writes before, after and compare PNGs, patch.css, patch.js, the board, and
             the elements each text, attribute and insert change matched.
5. repo      repo_patch.py on the fixes of 4 against examples/northdock-apply-fixture/repo/
             (a fictional Astro source of site/): CSS rules found and edited in place
             (01, 02: ready), the H1 text found in src/i18n/en.json (03), media rules and
             #promo-slot with no rule going to a new lpa-fixes.css (03, 04:
             ready-needs-import), the form ids found in two components (05: manual, two
             candidates, no patch); every patch and all.patch pass git apply --check and
             all.patch applied on a copy gives the expected source; the fixture repo is
             byte for byte unchanged; with --exclude of the legacy form, 05 becomes
             ready; --out inside the repo exits 2. Then, without a
             browser: a text wrapped over lines in markup, a text split by an inline tag
             and disambiguated by its tag and class, a short text found in markup and in
             i18n (manual), YAML values, SCSS nesting, a rule in two files (manual), JSX
             attribute names.
6. evidence  check_evidence.py resolves every reference of audit.example.json against
             the outputs of 2 to 5 (exit 0), and flags a copy with a missing evidence
             list, a dangling reference, a manual fix announced ready, and a ready patch
             that no longer applies because the repo changed (exit 1).
Last, the server's access log must hold no POST: nothing was ever sent.

Exit 0 when all hold, 1 otherwise. Outputs go to a temporary folder (or --keep DIR).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent
S = AGENT / "scripts"
FIX = AGENT / "examples" / "northdock-apply-fixture"
sys.path.insert(0, str(S))

FAILS: list = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)
        print(f"FAIL {msg}")


def py(*args, timeout=600):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if "Traceback" in r.stderr:
        print(r.stdout[-1500:], r.stderr[-3000:])
        FAILS.append(f"crash in {Path(str(args[0])).name}")
    return r


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def part_policy() -> None:
    from journey import classify, lint
    import lpa_common as C
    tv = ["lpa-test@example.com", "Test Visitor"]
    cases = [
        (("POST", "https://acme.example/api/lead", "fetch", False, [], []), "abort", "write"),
        (("POST", "https://acme.example/cart/add.js", "fetch", False, ["/cart/add.js"], []), "continue", "allowed-write"),
        (("POST", "https://acme.example/cart/add.js", "fetch", True, ["/cart/add.js"], []), "abort", "final-step-write"),
        (("POST", "https://api.stripe.com/v1/payment_intents", "fetch", False, ["api.stripe.com"], []), "abort", "payment-write"),
        (("GET", "https://api.stripe.com/v1/elements/sessions", "fetch", False, [], []), "continue", "read"),
        (("POST", "https://www.paypal.com/v2/checkout/orders", "xhr", False, [], []), "abort", "payment-write"),
        (("GET", "https://acme.us1.list-manage.com/subscribe/post-json?u=1&EMAIL=x", "script", False, [], []), "abort", "subscribe-endpoint"),
        (("GET", "https://acme.example/thanks?email=lpa-test%40example.com", "document", True, [], []), "abort", "final-step-get-with-test-data"),
        (("GET", "https://acme.example/search?q=shoes", "document", True, [], []), "continue", "read"),
        (("GET", "https://acme.example/app.js", "script", True, [], []), "continue", "read"),
        (("GET", "https://acme.example/track?e=view", "image", False, [], ["/track"]), "abort", "spec-block"),
        (("PUT", "https://acme.example/api/profile", "fetch", False, [], []), "abort", "write"),
        (("DELETE", "https://acme.example/api/x", "fetch", True, [], []), "abort", "final-step-write"),
        (("HEAD", "https://acme.example/", "document", False, [], []), "continue", "read"),
    ]
    for (method, url, rtype, final, allow, block), action, reason in cases:
        got = classify(method, url, rtype, final, allow, block, tv)
        check(got == (action, reason), f"policy {method} {url} final={final}: got {got}, want {(action, reason)}")
    # After a fill: any GET carrying a typed value is aborted, any resource type, any step.
    typed = ["lpa-test@example.com"]
    after_fill = [
        (("GET", "https://px.ads.example/p.gif?em=lpa-test%40example.com", "image", False, [], [], typed, None), "abort", "get-with-test-data"),
        (("GET", "https://acme.example/jsonp?cb=f&email=LPA-TEST%2540example.com", "script", False, [], [], typed, None), "abort", "get-with-test-data"),
        (("GET", "https://acme.example/thanks?email=lpa-test%40example.com", "document", False, [], [], typed, None), "abort", "get-with-test-data"),
        (("GET", "https://acme.example/beacon?d=lpa-test@example.com", "ping", False, [], [], typed, None), "abort", "get-with-test-data"),
        (("GET", "https://px.ads.example/p.gif?em=lpa-test%40example.com", "image", True, [], [], [], None), "abort", "final-step-get-with-test-data"),
        (("GET", "https://px.ads.example/p.gif?em=lpa-test%40example.com", "image", False, [], [], [], None), "continue", "read"),
        (("GET", "https://acme.example/img/testimonials.jpg", "image", False, [], [], ["lpa-test@example.com", "Test"], None), "continue", "read"),
        (("GET", "https://acme.example/app.js?v=3", "script", False, [], [], typed, None), "continue", "read"),
        # allow_write never lets test data out, in the URL or in the body.
        (("POST", "https://acme.example/cart/add.js", "fetch", False, ["/cart/add.js"], [], [], '{"id": 1, "note": "lpa-test@example.com"}'), "abort", "allowed-write-with-test-data"),
        (("POST", "https://acme.example/cart/add.js", "fetch", False, ["/cart/add.js"], [], [], "email=lpa-test%40example.com&qty=1"), "abort", "allowed-write-with-test-data"),
        (("POST", "https://acme.example/cart/add.js?e=lpa-test%40example.com", "fetch", False, ["/cart/add.js"], [], [], "qty=1"), "abort", "allowed-write-with-test-data"),
        (("POST", "https://acme.example/cart/add.js", "fetch", False, ["/cart/add.js"], [], typed, '{"id": 1, "qty": 1}'), "continue", "allowed-write"),
    ]
    for (method, url, rtype, final, allow, block, typed_values, body), action, reason in after_fill:
        got = classify(method, url, rtype, final, allow, block, tv, typed_values=typed_values, body=body)
        check(got == (action, reason), f"policy {method} {url} final={final} typed={typed_values} body={body!r}: got {got}, want {(action, reason)}")
    cases = cases + after_fill
    data = dict(C.TEST_DATA_DEFAULTS)
    # example.edu is outside the reserved test domains the lint accepts (a .example address would pass it)
    bad = {"steps": [{"do": "fill", "field": "Email", "value": "jane.doe@example.edu"}, {"do": "submit", "text": "Send"}]}
    check(any("reserved test address" in e for e in lint(bad, data)), "lint must refuse a real-looking e-mail")
    bad2 = {"steps": [{"do": "hover", "text": "x"}]}
    errs = lint(bad2, data)
    check(any("unknown verb" in e for e in errs) and any("no final step" in e for e in errs), f"lint must flag unknown verb and missing final step: {errs}")
    check(any("payment" in e for e in lint({"allow_write": ["api.stripe.com"], "steps": [{"do": "submit", "text": "Pay"}]}, data)),
          "lint must refuse allow_write on a payment host")
    broad = ["/", "*", "**", "/*", "ab", "acme.example", "https://acme.example", "https://acme.example/", "*.acme.example", "acme.example/*", "https://acme.example/**"]
    for pat in broad:
        errs = lint({"allow_write": [pat], "steps": [{"do": "submit", "text": "Send"}]}, data)
        check(any("too broad" in e for e in errs), f"lint must refuse allow_write {pat!r}: {errs}")
    for pat in ["/cart/add.js", "*/api/cart", "https://acme.example/cart/add.js"]:
        errs = lint({"allow_write": [pat], "steps": [{"do": "submit", "text": "Send"}]}, data)
        check(not errs, f"lint must accept allow_write {pat!r}: {errs}")
    from journey import link_has_side_effect
    for href, skip in [("https://acme.example/logout", True), ("https://acme.example/account/sign-out?next=/", True),
                       ("https://acme.example/email/Unsubscribe?id=4", True), ("https://acme.example/api/delete_account", True),
                       ("https://acme.example/pricing", False), ("https://acme.example/blog/logo-design?q=logout", False)]:
        check(link_has_side_effect(href) is skip, f"check_links side-effect filter on {href}: want skip={skip}")
    print(f"policy: {len(cases)} request cases, {3 + len(broad) + 3} lint cases, 6 link filter cases")


def part_probe(base: str, out: Path) -> None:
    r = py(S / "probe.py", base + "index.html", "--out", out / "run", "--cta", "Apply now")
    check(r.returncode == 0, f"probe.py exit {r.returncode}: {r.stderr[-500:]}")
    pj = json.loads((out / "run" / "probe.json").read_text(encoding="utf-8"))
    m, d = pj["summary"]["mobile"], pj["summary"]["desktop"]
    expect = [
        (m["overflow_x_px"] == 21, f"mobile overflow 21 px, got {m['overflow_x_px']}"),
        (d["overflow_x_px"] == 0, f"desktop overflow 0, got {d['overflow_x_px']}"),
        (any("glance" in o["selector"] for o in pj["viewports"]["mobile"]["measures"]["overflow"]["offenders"]), "overflow offender is the program table"),
        (m["targets_under_24"] == 8, f"8 targets failing 2.5.8, got {m['targets_under_24']}"),
        (m["targets_under_24_raw"] == 14, f"14 targets under 24 px raw, got {m['targets_under_24_raw']}"),
        (m["primary_cta_above_fold"] == 0 and m["primary_cta_above_screen"] == 1, f"mobile CTA below fold, above screen: {m['primary_cta_bottom_px']} / {m['fold_px']} / {m['screen_px']}"),
        (d["primary_cta_above_fold"] == 1, "desktop CTA above fold"),
        (m["contrast_failures"] == 2, f"2 contrast failures, got {m['contrast_failures']}"),
        (m["cls_observed"] > 0.1, f"mobile CLS over 0.1, got {m['cls_observed']}"),
        (m["images_without_dimensions"] == 1 and m["lazy_images_above_fold"] == 1, "hero image without dimensions and lazy"),
        (m["img_missing_alt"] == 1, f"1 image without alt, got {m['img_missing_alt']}"),
        (m["h1_count"] == 2, f"2 H1, got {m['h1_count']}"),
        (m["form_issues"] == 3, f"3 newsletter field issues, got {m['form_issues']}"),
        (m["text_under_16"] > 0 and m["page_weight_kb"] > 0, "small text and page weight measured"),
        ((out / "run" / "probe-mobile.png").exists(), "annotated mobile capture written"),
    ]
    for ok, msg in expect:
        check(ok, "probe: " + msg)
    r = py(S / "probe.py", base + "apply.html", "--out", out / "probe-apply", "--viewports", "mobile", "--no-annotate", "--cta", "Send application")
    pa = json.loads((out / "probe-apply" / "probe.json").read_text(encoding="utf-8"))["summary"]["mobile"]
    check(pa["form_issues"] == 6, f"probe: 6 issues on the application form, got {pa['form_issues']}")
    check(pa["inputs_under_16"] == 5, f"probe: 5 inputs under 16 px, got {pa['inputs_under_16']}")
    r = py(S / "probe.py", base + "missing.html", "--out", out / "probe-404", "--viewports", "mobile", "--no-annotate")
    check(r.returncode == 1, f"probe on a 404 must exit 1, got {r.returncode}")
    print(f"probe: mobile overflow {m['overflow_x_px']} px, {m['targets_under_24']} targets failing 2.5.8, CLS {m['cls_observed']}")


def part_journey(base: str, out: Path) -> None:
    r = py(S / "journey.py", FIX / "journey.json", "--out", out / "run", "--url", base + "index.html")
    check(r.returncode == 0, f"journey.py exit {r.returncode}: {r.stdout[-800:]} {r.stderr[-500:]}")
    log = json.loads((out / "run" / "journey" / "journey-log.json").read_text(encoding="utf-8"))
    check(log["proof"]["writes_that_reached_the_network_during_final_steps"] == 0, "journey: no write during final steps")
    for vp in log["viewports"]:
        name = vp["viewport"]
        steps = {s["n"]: s for s in vp["steps"]}
        check(all(s["status"] == "ok" for s in vp["steps"]), f"journey {name}: every step ok")
        b15 = [(b["method"], b["url"].rsplit("/", 1)[-1], b["confirmed"]) for b in steps[15].get("blocked", [])]
        b19 = [(b["method"], b["url"].rsplit("/", 1)[-1], b["confirmed"], b["type"]) for b in steps[19].get("blocked", [])]
        check(("POST", "apply", True) in b15, f"journey {name}: fetch POST /api/apply blocked and confirmed, got {b15}")
        check(("POST", "subscribe", True, "document") in b19, f"journey {name}: document POST /subscribe blocked, got {b19}")
        errs = steps[7]["observations"]["errors"]["messages"]
        check(len(errs) == 2 and all(e["distance_px"] <= 8 for e in errs), f"journey {name}: 2 inline errors next to their fields, got {errs}")
        check(steps[10]["observations"].get("fields_lost") == [], f"journey {name}: values survive the error")
        ac = steps[15]["observations"].get("after_click") or {}
        check(isinstance(ac, dict) and ac.get("disabled") and "Sending" in ac.get("text", ""), f"journey {name}: loading state after click, got {ac}")
        check(any("nav" in s for s in steps[5]["observations"].get("focus_without_indicator", [])), f"journey {name}: nav link without focus indicator")
        check(any("press.html" in u for u in steps[3]["observations"].get("dead_links", [])), f"journey {name}: dead Press link found")
        check(steps[12]["observations"].get("matched_by") == "placeholder", f"journey {name}: phone field found by placeholder only")
        check(steps[2]["observations"].get("anchor", {}).get("found") is True, f"journey {name}: anchor landing measured")
        for n in (1, 6, 15, 19):
            check((out / "run" / "journey" / steps[n]["shot"]).exists(), f"journey {name}: capture of step {n}")
        check((out / "run" / "journey" / name / "19-newsletter-submit-before.png").exists(), f"journey {name}: before-send capture of the final step")
    check((out / "run" / "journey" / "journey-board.jpg").exists(), "journey: board written")
    bad = out / "journey-missing.json"
    bad.write_text(json.dumps({"steps": [{"do": "goto", "url": "{{url}}"}, {"do": "submit", "text": "This button does not exist", "timeout": 1500}],
                               "viewports": ["mobile"]}), encoding="utf-8")
    r = py(S / "journey.py", bad, "--out", out / "journey-missing", "--url", base + "index.html")
    check(r.returncode == 1, f"journey with a missing button must exit 1, got {r.returncode}")
    check(any(p.name.endswith("-failed.png") for p in (out / "journey-missing" / "journey" / "mobile").glob("*.png")), "journey: failed capture written")
    r = py(S / "journey.py", FIX / "journey.json", "--lint")
    check(r.returncode == 0, "journey: fixture spec lints clean")
    print(f"journey: {log['proof']['statement']}, {log['proof']['requests_aborted']} requests aborted")


def part_fixes(base: str, out: Path) -> None:
    r = py(S / "fixes.py", FIX / "fixes.json", "--out", out / "run", "--url", base + "index.html")
    check(r.returncode == 0, f"fixes.py exit {r.returncode}: {r.stdout[-1200:]} {r.stderr[-500:]}")
    res = json.loads((out / "run" / "fixes" / "fixes.json").read_text(encoding="utf-8"))
    for f in res["fixes"]:
        check(f["status"] == "pass", f"fix {f['id']}: {f.get('expectations')} {f.get('unmatched')} {f.get('error')}")
        for vp in f.get("viewports", {}):
            for kind in ("before", "after", "compare"):
                check((out / "run" / "fixes" / f["id"] / f"{kind}-{vp}.png").exists(), f"fix {f['id']}: {kind}-{vp}.png")
        check((out / "run" / "fixes" / f["id"] / "patch.css").exists(), f"fix {f['id']}: patch.css")
    check((out / "run" / "fixes" / "board.jpg").exists() and (out / "run" / "fixes" / "fixes.md").exists(), "fixes: board and table written")
    f03 = json.loads((out / "run" / "fixes" / "03-hero-cta" / "fix.json").read_text(encoding="utf-8"))
    f05 = json.loads((out / "run" / "fixes" / "05-apply-form" / "fix.json").read_text(encoding="utf-8"))
    t03 = (f03.get("ops") or [{}])[0].get("targets") or [{}]
    t05 = next((o.get("targets") or [{}] for o in f05.get("ops", []) if o.get("selector") == "#email"), [{}])
    check(t03[0].get("text") == "Unlock your founder potential with next-generation synergy" and t03[0].get("tag") == "h1", f"fixes: 03 records the H1 text before the change, got {t03}")
    check(t05[0].get("id") == "email" and t05[0].get("attrs", {}).get("type") == "text", f"fixes: 05 records #email type=text before the change, got {t05}")
    print(f"fixes: {sum(f['status'] == 'pass' for f in res['fixes'])}/{len(res['fixes'])} pass")


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def part_repo(out: Path) -> None:
    import repo_patch as R
    repo = FIX / "repo"
    before = tree_digest(repo)
    r = py(S / "repo_patch.py", "--repo", repo, "--fixes", out / "run" / "fixes")
    check(r.returncode == 0, f"repo_patch.py exit {r.returncode}: {r.stdout[-1500:]} {r.stderr[-800:]}")
    dest = out / "run" / "repo-patches"
    rec = json.loads((dest / "repo-patches.json").read_text(encoding="utf-8"))
    by = {f["id"]: f for f in rec["fixes"]}
    want = {"01-mobile-overflow": "ready", "02-touch-targets": "ready", "03-hero-cta": "ready-needs-import",
            "04-banner-shift": "ready-needs-import", "05-apply-form": "manual"}
    for fid, st in want.items():
        got = by.get(fid, {}).get("status")
        check(got == st, f"repo: {fid} status {got}, want {st} ({by.get(fid, {}).get('reason')})")
    check(by["01-mobile-overflow"]["locations"] == ["src/styles/global.css:47"], f"repo: 01 at global.css:47 (width: 395px), got {by['01-mobile-overflow']['locations']}")
    check("src/i18n/en.json:8" in by["03-hero-cta"]["locations"], f"repo: 03 H1 text found in en.json:8, got {by['03-hero-cta']['locations']}")
    check(any(p["kind"] == "text" and p.get("where") == "content file" for p in by["03-hero-cta"]["parts"]), "repo: 03 text part comes from a content file")
    check(rec["css_file"] == "src/styles/lpa-fixes.css", f"repo: lpa-fixes.css next to the only stylesheet, got {rec['css_file']}")
    check("src/layouts/Base.astro:2" in by["04-banner-shift"].get("reason", ""), f"repo: import hint names Base.astro:2, got {by['04-banner-shift'].get('reason')}")
    m = by["05-apply-form"]
    cands = sorted({c for p in m["parts"] for c in p.get("candidates", [])})
    check(m.get("patch") is None and not (dest / "05-apply-form.patch").exists(), "repo: no patch guessed for the ambiguous fix 05")
    check(any("ApplyForm.astro" in c for c in cands) and any("ApplyFormLegacy.astro" in c for c in cands), f"repo: 05 lists both form components, got {cands}")
    for fid in [k for k, v in want.items() if v != "manual"] + ["all"]:
        patch = dest / f"{fid}.patch"
        check(patch.exists() and R.apply_check(repo, patch) == "", f"repo: {fid}.patch exists and passes git apply --check")
    check(set(rec["all"]["fixes"]) == {k for k, v in want.items() if v != "manual"}, f"repo: all.patch holds the 4 ready fixes, got {rec['all']}")
    md = (dest / "repo-patches.md").read_text(encoding="utf-8")
    check("merge it yourself" in md and md.count("### ") == 5, "repo: report section per fix with the review-and-merge reminder")
    work = out / "repo-applied"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(repo, work)
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    a = subprocess.run(["git", "apply", str((dest / "all.patch").resolve())], cwd=work, capture_output=True, text=True)
    check(a.returncode == 0, f"repo: git apply all.patch on a copy: {a.stderr[-400:]}")
    css = (work / "src/styles/global.css").read_text(encoding="utf-8")
    new = (work / "src/styles/lpa-fixes.css").read_text(encoding="utf-8") if (work / "src/styles/lpa-fixes.css").exists() else ""
    en = json.loads((work / "src/i18n/en.json").read_text(encoding="utf-8"))
    check(".glance table {\n  width: 100%;" in css and "gap: 8px;" in css and "aspect-ratio: 800 / 760;" in css and "!important" not in css, "repo: global.css edited in place, no !important")
    check("TO IMPORT" in new and "#promo-slot {" in new and "@media (max-width: 799px)" in new, "repo: lpa-fixes.css created, marked to import, holds the rules with no home")
    check(en["hero"]["title"] == "Year-round support for early-stage founders in Paris", f"repo: en.json title replaced, got {en['hero']['title']}")
    check(tree_digest(repo) == before, "repo: the fixture repo must stay byte for byte unchanged")
    r = py(S / "repo_patch.py", "--repo", repo, "--fixes", out / "run" / "fixes", "--out", out / "repo-excluded",
           "--exclude", "src/components/ApplyFormLegacy.astro")
    ex = json.loads((out / "repo-excluded" / "repo-patches" / "repo-patches.json").read_text(encoding="utf-8"))
    e05 = next(f for f in ex["fixes"] if f["id"] == "05-apply-form")
    p05 = (out / "repo-excluded" / "repo-patches" / "05-apply-form.patch")
    check(r.returncode == 0 and e05["status"] == "ready" and p05.exists() and '<label for="phone">Phone</label>' in p05.read_text(encoding="utf-8"),
          f"repo: with the legacy form excluded, 05 is ready with the label insert: {e05.get('status')} {e05.get('reason')}")
    r = py(S / "repo_patch.py", "--repo", repo, "--fixes", out / "run" / "fixes", "--out", repo / "tmp-out")
    check(r.returncode == 2 and not (repo / "tmp-out").exists(), f"repo: --out inside the repo must exit 2, got {r.returncode}")

    def run(tree, fix):
        t = tree.fork()
        parts = R.plan_fix(t, fix, R.CSS_FILE)
        for p in parts:
            p["locations"] = [f"{m[0]}:{t.old_line(m)}" for m in p.pop("marks", [])]
        return R.fix_status(parts), parts, t

    def tg(tag, text="", id=None, classes=(), href=None):
        return {"tag": tag, "id": id, "classes": list(classes), "href": href, "text": text, "attrs": {}, "open": ""}

    def op(kind, sel, target, **kw):
        return dict(kind=kind, selector=sel, matched=1, targets=[target], **kw)
    real = R.Tree(repo)
    why = ("Founders get a place to work, people who answer their questions, and a room to test their pitch before "
           "investors see it. Applications are read by the team and every applicant gets an answer.")
    st, parts, t = run(real, {"id": "u1", "ops": [op("text", ".why p", tg("p", why), text="A desk & a room {all year}")]})
    check(st == "ready" and parts[0]["locations"] == ["src/pages/index.astro:40"], f"repo unit: wrapped markup text located, got {st} {parts}")
    check("<p>A desk &amp; a room &#123;all year&#125;</p>" in t.cur.get("src/pages/index.astro", ""), "repo unit: new text escaped for Astro, whole wrapped span replaced")
    st, parts, _ = run(real, {"id": "u2", "ops": [op("text", "footer a", tg("a", "Apply", href="/apply"), text="Apply today")]})
    check(st == "manual" and parts[0]["status"] == "ambiguous" and len(parts[0]["candidates"]) == 2,
          f"repo unit: 'Apply' in Footer.astro and en.json is ambiguous, 'Apply to Northdock' is not a match: {parts}")
    mem = R.Tree(files={
        "src/Program.jsx": 'export default () => (\n  <section>\n    <h2 className="title">Program <em>at a</em> glance</h2>\n'
                           '    <label htmlFor="x">Program at a glance</label>\n    <input id="email" type="text" />\n  </section>\n);\n',
        "content/home.yml": 'hero:\n  title: "Hello world"\n  sub: Plain value here # note\n',
        "styles/a.scss": ".hero {\n  .sub {\n    color: red;\n  }\n}\n",
        "styles/b.css": ".dup { color: red }\n", "styles/c.css": ".dup { color: blue }\n"})
    st, parts, t = run(mem, {"id": "u3", "ops": [op("text", "h2", tg("h2", "Program at a glance", classes=["title"]), text="The program")]})
    check(st == "ready" and '<h2 className="title">The program</h2>' in t.cur["src/Program.jsx"] and "<label htmlFor=\"x\">Program at a glance" in t.cur["src/Program.jsx"],
          f"repo unit: text split by <em> replaced whole, label left alone: {parts}")
    st, parts, t = run(mem, {"id": "u4", "ops": [op("text", "h1", tg("h1", "Hello world"), text="Bye"),
                                                op("text", "p", tg("p", "Plain value here"), text="Now: with a colon")]})
    check(st == "ready" and t.cur["content/home.yml"] == 'hero:\n  title: "Bye"\n  sub: "Now: with a colon" # note\n', f"repo unit: YAML values replaced, quoting kept or added: {t.cur['content/home.yml']!r}")
    st, parts, t = run(mem, {"id": "u5", "ops": [op("attributes", "#email", tg("input", id="email"), set={"type": "email", "autocomplete": "email"}, remove=[]),
                                                op("insert", "#email", tg("input", id="email"), position="beforebegin", html='<label for="email">Email</label>')]})
    check(st == "ready" and '    <label htmlFor="email">Email</label>\n    <input id="email" type="email" autoComplete="email" />' in t.cur["src/Program.jsx"],
          f"repo unit: JSX attribute names and inserted label: {t.cur['src/Program.jsx']!r}")
    st, parts, t = run(mem, {"id": "u6", "css": [{"selector": ".hero .sub", "declarations": {"color": "#fff", "margin": "0"}}]})
    check(st == "ready" and t.cur["styles/a.scss"] == ".hero {\n  .sub {\n    color: #fff;\n    margin: 0;\n  }\n}\n", f"repo unit: SCSS nested rule edited: {t.cur['styles/a.scss']!r}")
    st, parts, _ = run(mem, {"id": "u7", "css": [{"selector": ".dup", "declarations": {"color": "#fff"}}]})
    check(st == "manual" and parts[0]["status"] == "ambiguous", f"repo unit: a rule in two files is manual: {parts}")
    print(f"repo: {', '.join(f'{k} {v}' for k, v in ((f['id'], f['status']) for f in rec['fixes']))}; all.patch {len(rec['all']['fixes'])} fixes; 7 unit cases")


def part_evidence(out: Path) -> None:
    r = py(S / "check_evidence.py", FIX / "audit.example.json", "--root", out / "run")
    check(r.returncode == 0, f"check_evidence on the example must pass: {r.stdout[-1500:]}")
    side = json.loads((FIX / "audit.example.json").read_text(encoding="utf-8"))
    side["top_fixes"][0]["evidence"] = []
    side["findings"][0]["evidence"].append("fix:99-does-not-exist")
    side["repo"] = str(FIX / "repo")
    for e in side["repo_patches"]:
        if e["fix"] == "05-apply-form":
            e.update(status="ready", patch="repo-patches/05-apply-form.patch")
    bad = out / "audit-broken.json"
    bad.write_text(json.dumps(side), encoding="utf-8")
    r = py(S / "check_evidence.py", bad, "--root", out / "run")
    check(r.returncode == 1 and "no evidence" in r.stdout and "99-does-not-exist" in r.stdout, f"check_evidence must flag the broken copy: {r.stdout[-600:]}")
    check("repo_patch 05-apply-form: announced 'ready', repo_patch.py recorded 'manual'" in r.stdout, f"check_evidence must flag a manual fix announced ready: {r.stdout[-600:]}")
    print("evidence: " + r.stdout.strip().splitlines()[-1].replace("check_evidence: ", "broken copy: "))
    moved = out / "repo-moved"
    shutil.rmtree(moved, ignore_errors=True)
    shutil.copytree(FIX / "repo", moved)
    css = moved / "src/styles/global.css"
    css.write_text(css.read_text(encoding="utf-8").replace("width: 395px;", "width: 400px;"), encoding="utf-8")
    r = py(S / "check_evidence.py", FIX / "audit.example.json", "--root", out / "run", "--repo", moved)
    check(r.returncode == 1 and "01-mobile-overflow.patch does not pass git apply --check" in r.stdout and "all.patch does not pass" in r.stdout,
          f"check_evidence must flag ready patches that no longer apply: {r.stdout[-800:]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="keep outputs in this folder")
    ap.add_argument("--only", choices=["policy", "probe", "journey", "fixes", "repo", "evidence"])
    args = ap.parse_args()
    out = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="lpa-selftest-"))
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    part_policy()
    if args.only == "policy":
        return finish(out, t0)
    port = free_port()
    log = open(out / "server.log", "w")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(FIX / "site")],
                           stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(50):
            try:
                local = urllib.request.OpenerDirector()  # http only: the fixture server
                for h in (urllib.request.HTTPHandler(), urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor()):
                    local.add_handler(h)
                local.open(base + "index.html", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        parts = ["probe", "journey", "fixes", "repo", "evidence"] if not args.only else [args.only]
        if args.only == "evidence":
            parts = ["probe", "journey", "fixes", "repo", "evidence"]
        if args.only == "repo":
            parts = ["fixes", "repo"]
        for part in parts:
            if part == "probe":
                part_probe(base, out)
            elif part == "journey":
                part_journey(base, out)
            elif part == "fixes":
                part_fixes(base, out)
            elif part == "repo":
                part_repo(out)
            else:
                part_evidence(out)
    finally:
        srv.terminate()
        srv.wait(timeout=5)
        log.close()
    posts = [l for l in (out / "server.log").read_text(encoding="utf-8").splitlines() if '"POST ' in l]
    check(not posts, f"the server received a POST: {posts[:3]}")
    print(f"server: {sum(1 for l in (out / 'server.log').read_text(encoding='utf-8').splitlines() if 'GET' in l)} GET, {len(posts)} POST")
    return finish(out, t0)


def finish(out: Path, t0: float) -> int:
    ok = not FAILS
    print(f"selftest: {'PASS' if ok else 'FAIL'} in {time.time() - t0:.0f} s (outputs in {out})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
