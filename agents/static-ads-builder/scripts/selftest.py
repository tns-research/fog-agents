#!/usr/bin/env python3
"""selftest.py: offline regression test of the static-ads engine (0 $, no key).

  python3 scripts/selftest.py [--keep DIR] [--quick]

1. Example (examples/swanbase-mini-batch-20261012): build, render 3 ads x 3
   formats, QA must pass, the reviewer transcript stored with the example must
   be TEXT_OK on all 9 renders, the Meta package must hold 9 import rows,
   9 exports and a 9-line creative ledger, and every render carries the real
   logo (mark + wordmark lockup from brand.json, not the name in text).
2. Proofread diff: tests/fixtures/proofread/transcript-typos.json (a label
   misread on a photo, a misspelt word, an invented word, a render left out)
   must BLOCK with the expected verdict on each render.
3. Stress spec (tests/fixtures/stress): every failure it was built to trigger
   appears with the expected code, nothing crashes. Its brand copy has no
   logo file, so the name typeset as the logo must be flagged (logo-text).
4. Plates: plates.py prepare + render_ads.py --provider manual write the pack
   offline (also with no --provider: manual is the default), plates.py
   status reports the missing plate (exit 1), and a paid
   batch without --confirm-spend is refused (exit 4, nothing sent).
5. Performance loop: perf.py on the CSV fixture with the previous period
   (winners, losers, inconclusive, insufficient data, creative vs post-click,
   account post_click) and on the insights JSON fixture (pixel and omni
   purchases never added up).
6. Photo edit (tests/fixtures/photo-edit, mode photo_edit): a fictional
   photo drawn by the test (shapes, no real person), photo_edit.py check
   passes, the stub backend (passed explicitly; the CLI default is manual)
   renders every concept at the size asked,
   twice to the same bytes, each with a media entry valid against
   ads.schema.json; verify passes sizes, writes the review packet, turns
   reviewer answers into IDENTITY_OK, IDENTITY_CHANGED, TEXT_ADDED and
   NOT_REVIEWED, and catches a wrong size; consent BLOCKs a refused person,
   a person cleared for another scope, an unknown slug and a missing slug,
   and lets the operator through; the lint catches one edit level only,
   a prompt without "no text" and a missing invariant; the openai backend
   without --confirm-spend sends nothing and exits 4 with the estimate;
   with no --backend the script writes the manual pack and renders nothing.
7. Winning recipe (tests/fixtures/recipe, mode winning_recipe): seed reads
   the perf winner back from its spec and leaves the judgement fields to the
   model, the fixture recipe passes check-recipe, build writes 5 variants
   (one CTA, four hooks) named _t-<variable>, which build.py accepts with 0
   error; check refuses a variant that changes two variables, one that
   changes the structure and one that declares the wrong variable, and
   build refuses a hook with an unsourced number.
8. All 18 styles x 3 formats (tests/fixtures/all-styles), QA must pass, every
   render carries the logo lockup, and no 9:16 render has dead space in its
   text zone or an empty band (dead-space-9x16, empty-band). Skipped with
   --quick.

Exit 0 when every check holds, 1 otherwise. Outputs go to a temporary folder
(or --keep DIR); the repo is not written to.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

AGENT = Path(__file__).resolve().parent.parent
S = AGENT / "scripts"
EX = AGENT / "examples" / "swanbase-mini-batch-20261012"
FX = AGENT / "tests" / "fixtures"
FAILS: List[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)
        print(f"FAIL {msg}")


def run(*args: str) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if "Traceback" in r.stderr or "Traceback" in r.stdout:
        print(r.stdout[-1500:], r.stderr[-2500:])
        FAILS.append(f"crash: {' '.join(Path(a).name for a in args[:2])}")
    return r


def fixture_photo(path: Path) -> None:
    """A fictional 'founder holding a jar' drawn from shapes: no real person."""
    from PIL import Image, ImageDraw
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1200, 900), (205, 196, 178))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 610, 1200, 900), fill=(148, 108, 78))
    d.rectangle((90, 420, 250, 610), fill=(90, 90, 96))
    d.ellipse((530, 140, 670, 300), fill=(222, 186, 158))
    d.rectangle((470, 300, 730, 760), fill=(58, 118, 82))
    d.rectangle((575, 470, 655, 600), fill=(168, 62, 72))
    d.rectangle((582, 505, 648, 545), fill=(240, 228, 205))
    im.save(path, quality=90)


def sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", help="Keep outputs in this folder")
    ap.add_argument("--quick", action="store_true", help="Skip the 18-style render")
    a = ap.parse_args()
    base = Path(a.keep).resolve() if a.keep else Path(tempfile.mkdtemp(prefix="static-ads-selftest-"))
    base.mkdir(parents=True, exist_ok=True)

    # 1. Example end to end.
    out = base / "example"
    r = run(str(S / "pipeline.py"), str(EX / "ads.json"), "--out", str(out), "--transcript", str(EX / "transcript.json"), "--package")
    check(r.returncode == 0, f"example pipeline exit {r.returncode}: {r.stdout[-600:]}")
    qa = json.loads((out / "renders" / "qa.json").read_text(encoding="utf-8"))
    check(qa["status"] == "pass" and qa["summary"]["renders"] == 9, f"example qa {qa['summary']}")
    pr = json.loads((out / "proofread" / "proofread.json").read_text(encoding="utf-8"))
    check(pr["status"] == "pass" and pr["renders"] == 9, f"example proofread {pr['status']} {pr['blocks']} blocks")
    rows = list(csv.DictReader(open(next((out / "meta").glob("ads-import-*.csv")), encoding="utf-8")))
    check(len(rows) == 9 and all(x["Ad Status"] == "PAUSED" for x in rows), f"import csv rows {len(rows)}")
    check(all("utm_content=" + x["Ad Name"] in x["URL Tags"] for x in rows), "utm_content must carry the ad name")
    check(len(list((out / "meta" / "exports").rglob("*.jpg"))) == 9, "9 exports expected")
    check(len(json.loads((out / "meta" / "creative-ledger.json").read_text(encoding="utf-8"))) == 9, "ledger must hold 9 lines")
    logos = {s["metrics"].get("logo") for s in qa["sections"]}
    check(logos == {"lockup"}, f"example: every render must carry the logo lockup, got {logos}")
    print(f"example: qa {qa['status']}, proofread {pr['status']}, {len(rows)} import rows, logo {', '.join(sorted(logos))}")

    # 2. Proofread typos.
    r = run(str(S / "proofread.py"), "check", str(out / "html"), str(FX / "proofread" / "transcript-typos.json"), "--out", str(base / "typos.json"))
    check(r.returncode == 1, "typo transcript must exit 1")
    res = {x["file"]: x for x in json.loads((base / "typos.json").read_text(encoding="utf-8"))["results"]}
    want = json.loads((FX / "proofread" / "expected-verdicts.json").read_text(encoding="utf-8"))
    for f, v in want.items():
        got = res.get(f, {}).get("verdict")
        check(got == v, f"proofread {f}: expected {v}, got {got}")
    print(f"proofread typos: {sum(1 for x in res.values() if x['verdict'] != 'TEXT_OK')} blocks, {len(want)} expected verdicts checked")

    # 3. Stress spec.
    st = base / "stress"
    shutil.copytree(FX / "stress", st / "spec")
    shutil.copytree(FX / "media", st / "media")
    shutil.copytree(FX / "all-styles" / "project-context", st / "all-styles" / "project-context")
    sb = st / "all-styles" / "project-context" / "brand.json"
    bj = json.loads(sb.read_text(encoding="utf-8"))
    bj.pop("logos", None)
    sb.write_text(json.dumps(bj, indent=2), encoding="utf-8")
    r = run(str(S / "pipeline.py"), str(st / "spec" / "ads.json"), "--out", str(st), "--no-sheet")
    check(r.returncode == 1, "stress pipeline must exit 1")
    rep = json.loads((st / "html" / "build-report.json").read_text(encoding="utf-8"))
    codes = {(e["code"], e["where"].split(".")[0] + "." + e["where"].split(".")[1].split("]")[0] + "]" if e["where"].startswith("$.ads[") else e["where"]) for e in rep["errors"]}
    for code, where in [("schema", "$.ads[5]"), ("dash", "$.ads[2]"), ("unsourced-number", "$.ads[1]"), ("style-needs", "$.ads[1]"), ("missing-asset", "$.ads[3]")]:
        check(any(c == code and w.startswith(where) for c, w in codes), f"stress: expected build error {code} at {where}")
    warns = {w["code"] for w in rep["warnings"]}
    for code in ("media-cropped", "media-text-undeclared", "no-meta-ad", "meta-cta", "stage-cta", "logo-text"):
        check(code in warns, f"stress: expected warning {code}")
    sq = json.loads((st / "renders" / "qa.json").read_text(encoding="utf-8"))
    sec = {s["name"]: s for s in sq["sections"]}
    check(any(e["code"] == "text-too-long" for e in sec["acme_01_tofu_anti-category_bold-statement_1x1"]["errors"]), "stress: text-too-long on ad 1")
    check(any(e["code"] == "missing-asset" for e in sec["acme_04_tofu_specific-ritual_ugc-text-overlay_9x16"]["errors"]), "stress: missing-asset on the plate ad")
    print(f"stress: {sq['summary']['errors']} errors, {sq['summary']['warnings']} warnings, expected findings checked")

    # 4. Plates, manual provider (no spend, no network).
    r = run(str(S / "plates.py"), "prepare", str(st / "spec" / "ads.json"))
    check(r.returncode == 0 and (st / "spec" / "plates" / "plate-briefs-9x16.json").exists(), "plates prepare")
    r = run(str(S / "render_ads.py"), "--batch", str(st / "spec" / "plates" / "plate-briefs-9x16.json"), "--select", "4",
            "--out", str(st / "spec" / "plates"), "--ratio", "9:16", "--provider", "manual")
    check(r.returncode == 0 and (st / "spec" / "plates" / "_manual" / "MANUAL-RENDER.md").exists(), "manual plate pack")
    prompt = (st / "spec" / "plates" / "_manual" / "04-plate.prompt.txt").read_text(encoding="utf-8")
    check("No text, no letters" in prompt, "plate prompt must forbid text")
    dflt = st / "spec" / "plates-default"
    r = run(str(S / "render_ads.py"), "--batch", str(st / "spec" / "plates" / "plate-briefs-9x16.json"), "--select", "4",
            "--out", str(dflt), "--ratio", "9:16")
    check(r.returncode == 0 and (dflt / "_manual" / "MANUAL-RENDER.md").exists(), "render_ads default provider must be manual")
    # Spend gate: a paid batch with a (fake) key and no --confirm-spend sends nothing, exits 4.
    env = {k: v for k, v in os.environ.items() if k != "FOG_ALLOW_SPEND"}
    env["OPENAI_API_KEY"] = "sk-selftest-not-a-key"
    gate_out = st / "spec" / "plates-gate"
    r = subprocess.run([sys.executable, str(S / "render_ads.py"), "--batch", str(st / "spec" / "plates" / "plate-briefs-9x16.json"),
                        "--select", "4", "--out", str(gate_out), "--ratio", "9:16", "--provider", "openai"],
                       capture_output=True, text=True, env=env)
    check(r.returncode == 4 and '"spend_gate": "closed"' in r.stdout and "--confirm-spend" in r.stderr and not gate_out.exists(),
          f"render_ads spend gate must close without --confirm-spend (exit {r.returncode})")
    r = run(str(S / "plates.py"), "status", str(st / "spec" / "ads.json"))
    check(r.returncode == 1 and "MISSING" in r.stdout, "plates status must report the missing plate")
    print("plates: manual pack written, missing plate reported")

    # 5. Performance loop.
    r = run(str(S / "perf.py"), str(FX / "perf" / "meta-export-20261004.csv"), "--previous", str(FX / "perf" / "meta-export-20260920.csv"),
            "--target-cpa", "20", "--out", str(base / "perf.json"), "--md", str(base / "perf.md"))
    check(r.returncode == 0, "perf csv exit")
    p = json.loads((base / "perf.json").read_text(encoding="utf-8"))
    ads = {m["ad_name"]: m for m in p["ads"]}
    exp = json.loads((FX / "perf" / "expected.json").read_text(encoding="utf-8"))
    for name, (verdict, diag) in exp["ads"].items():
        got = ads.get(name, {})
        check(got.get("verdict") == verdict and got.get("diagnosis") == diag, f"perf {name}: expected {verdict}/{diag}, got {got.get('verdict')}/{got.get('diagnosis')}")
    check(p["account"]["diagnosis"] == exp["account"], f"perf account: expected {exp['account']}, got {p['account']['diagnosis']}")
    check(p["next_batch"]["fix_post_click_first"] is True, "perf: post-click account must ask for fixes first")
    check(p["aggregates"]["angle"]["anti-category"]["conversions"] == 11, "perf: aggregates by angle")
    r = run(str(S / "perf.py"), str(FX / "perf" / "insights-20261004.json"), "--target-cpa", "20", "--out", str(base / "perf-json.json"), "--md", str(base / "perf-json.md"))
    pj = json.loads((base / "perf-json.json").read_text(encoding="utf-8"))
    check(pj["account"]["current"]["conversions"] == 15, f"perf json: purchases must not be summed across action types, got {pj['account']['current']['conversions']}")
    print(f"perf: {len(p['winners'])} winners, {len(p['losers'])} losers, account {p['account']['diagnosis']}")

    # 6. Photo edit: stub backend, size check, review verdicts, consent, spend gate.
    sys.path.insert(0, str(S))
    import adspec
    pe = base / "photo-edit"
    shutil.copytree(FX / "photo-edit", pe)
    fixture_photo(pe / "media" / "founder-jar.jpg")
    spec_p = pe / "photo-edits.json"
    pe_spec = json.loads(spec_p.read_text(encoding="utf-8"))
    r = run(str(S / "photo_edit.py"), "check", str(spec_p))
    check(r.returncode == 0, f"photo_edit check must pass on the fixture: {r.stderr[-400:]}")
    r = run(str(S / "photo_edit.py"), "render", str(spec_p), "--select", "all", "--backend", "stub")
    check(r.returncode == 0, f"photo_edit stub render exit {r.returncode}: {r.stderr[-400:]}")
    edited = pe / "media" / "edited"
    recs = json.loads((edited / "photo-edit-run.json").read_text(encoding="utf-8"))["records"]
    check(len(recs) == 3 and all(x["status"] == "OK" for x in recs), f"photo_edit: 3 renders expected, got {[x['status'] for x in recs]}")
    from PIL import Image
    want = {c["id"]: c["size"] for c in pe_spec["photos"][0]["concepts"]}
    for x in recs:
        with Image.open(edited / x["file"]) as im:
            check(f"{im.size[0]}x{im.size[1]}" == want[x["concept"]], f"photo_edit: {x['file']} size {im.size}, asked {want[x['concept']]}")
    r = run(str(S / "photo_edit.py"), "render", str(spec_p), "--select", "all", "--backend", "stub", "--out", str(pe / "again"))
    check(all(sha(edited / x["file"]) == sha(pe / "again" / x["file"]) for x in recs), "photo_edit stub must be deterministic")
    media_schema = json.loads((AGENT / "assets" / "ads.schema.json").read_text(encoding="utf-8"))
    me = recs[0]["media_entry"]
    check(not adspec.SchemaValidator(media_schema).validate(me, {"$ref": "#/$defs/media"}) and me["edit"].get("person_slugs") == ["ana-ruiz"]
          and me["visible_text"] == ["FIG", "JAM"] and me["fit"] == "contain", f"photo_edit media entry: {me}")
    r = run(str(S / "photo_edit.py"), "verify", str(spec_p))
    vr = json.loads(r.stdout or "{}")
    check(r.returncode == 0 and vr.get("status") == "awaiting_review" and (pe / "review" / "photo-edit-packet.md").exists(),
          f"photo_edit verify without review: exit {r.returncode}, {vr.get('status')}")
    same = {"face": "same", "expression": "same", "pose": "same", "hands": "same", "fingers": "five", "object": "same", "text_added": False}
    (pe / "review-ok.json").write_text(json.dumps([dict(same, file=x["file"]) for x in recs]), encoding="utf-8")
    r = run(str(S / "photo_edit.py"), "verify", str(spec_p), "--review", str(pe / "review-ok.json"))
    check(r.returncode == 0 and json.loads(r.stdout)["status"] == "pass", "photo_edit verify with a clean review must pass")
    bad = [dict(same, file=recs[0]["file"], fingers="wrong"), dict(same, file=recs[1]["file"], text_added=True)]
    (pe / "review-bad.json").write_text(json.dumps(bad), encoding="utf-8")
    r = run(str(S / "photo_edit.py"), "verify", str(spec_p), "--review", str(pe / "review-bad.json"))
    got = [x.get("review") for x in json.loads(r.stdout)["results"]]
    check(r.returncode == 1 and got == ["IDENTITY_CHANGED", "TEXT_ADDED", "NOT_REVIEWED"], f"photo_edit review verdicts: {got}")
    Image.new("RGB", (640, 480), (0, 0, 0)).save(edited / recs[2]["file"])
    r = run(str(S / "photo_edit.py"), "verify", str(spec_p))
    check(r.returncode == 1 and json.loads(r.stdout)["results"][2]["check"] == "SIZE_MISMATCH", "photo_edit verify must catch a wrong size")

    def pe_variant(name: str, mutate) -> subprocess.CompletedProcess:
        v = json.loads(json.dumps(pe_spec))
        mutate(v)
        vp = pe / f"{name}.json"
        vp.write_text(json.dumps(v), encoding="utf-8")
        return run(str(S / "photo_edit.py"), "check", str(vp))

    def codes(r: subprocess.CompletedProcess) -> set:
        return {i["code"] for i in json.loads(r.stdout or "{}").get("issues", []) if i["level"] == "error"}

    def slug(value):
        def m(v):
            for c in v["photos"][0]["concepts"]:
                if value is None:
                    c.pop("person_slug", None)
                else:
                    c["person_slug"] = value
        return m

    for label, value in (("refused", "leo-park"), ("other-scope", "mia-chen"), ("unknown", "nobody-here"), ("missing", None)):
        r = pe_variant(f"consent-{label}", slug(value))
        check(r.returncode == 1 and codes(r) == {"consent"}, f"photo_edit consent {label}: exit {r.returncode}, {codes(r)}")
    r = pe_variant("consent-operator", slug("sam-oak"))
    check(r.returncode == 0, f"photo_edit: the operator needs no recorded consent ({codes(r)})")
    r = pe_variant("consent-group", slug(["ana-ruiz", "leo-park"]))
    check(r.returncode == 1 and codes(r) == {"consent"}, "photo_edit: one refused person in a group blocks")
    (pe / "consent-refused-render.json").write_text((pe / "consent-refused.json").read_text(encoding="utf-8"), encoding="utf-8")
    r = run(str(S / "photo_edit.py"), "render", str(pe / "consent-refused-render.json"), "--select", "all", "--backend", "stub",
            "--out", str(pe / "blocked"))
    check(r.returncode == 1 and not (pe / "blocked").exists(), "photo_edit render must refuse a consent BLOCK and write nothing")

    def one_level(v):
        for c in v["photos"][0]["concepts"]:
            c["edit_level"] = 30
            c["prompt"] = c["prompt"].replace("50%", "30%").replace("80%", "30%")

    def no_no_text(v):
        c = v["photos"][0]["concepts"][0]
        c["prompt"] = c["prompt"].replace("no text, no letters, ", "")

    def no_fingers(v):
        v["photos"][0]["concepts"][1]["never_changes"] = ["face and expression", "pose", "the jar held and its label"]

    def two_concepts(v):
        v["photos"][0]["concepts"] = v["photos"][0]["concepts"][:2]

    for label, mut, code in (("one-level", one_level, "edit-levels"), ("no-text", no_no_text, "prompt-text"),
                             ("no-fingers", no_fingers, "invariant-missing"), ("two-concepts", two_concepts, "schema")):
        r = pe_variant(f"lint-{label}", mut)
        check(r.returncode == 1 and code in codes(r), f"photo_edit lint {label}: expected {code}, got {codes(r)}")
    env = {k: v for k, v in os.environ.items() if k != "FOG_ALLOW_SPEND"}
    env["OPENAI_API_KEY"] = "sk-selftest-not-a-key"
    r = subprocess.run([sys.executable, str(S / "photo_edit.py"), "render", str(spec_p), "--select", "paper-backdrop,plaster-wall",
                        "--backend", "openai", "--config", str(AGENT / "config.example.json"), "--out", str(pe / "paid")],
                       capture_output=True, text=True, env=env)
    gate = json.loads(r.stdout or "{}")
    check(r.returncode == 4 and gate.get("spend_gate") == "closed" and gate.get("count") == 2 and gate.get("per_image_usd") == 0.17
          and gate.get("model") == "gpt-image-2" and "--confirm-spend" in r.stderr and not (pe / "paid").exists(),
          f"photo_edit openai spend gate must close without --confirm-spend (exit {r.returncode}, {gate})")
    env_fal = {k: v for k, v in env.items() if k not in ("FAL_KEY", "FAL_API_KEY")}
    env_fal["FAL_KEY"] = "fal-selftest-not-a-key"
    fal_cmd = [sys.executable, str(S / "photo_edit.py"), "render", str(spec_p), "--select", "paper-backdrop",
               "--backend", "fal", "--out", str(pe / "fal")]
    r = subprocess.run(fal_cmd, capture_output=True, text=True, env=env_fal)
    gate = json.loads(r.stdout or "{}")
    check(r.returncode == 4 and gate.get("public_url_gate") == "closed" and not (pe / "fal").exists(),
          f"photo_edit fal must refuse a public URL for a photo with people (exit {r.returncode}, {gate})")
    r = subprocess.run(fal_cmd + ["--accept-public-url"], capture_output=True, text=True, env=env_fal)
    gate = json.loads(r.stdout or "{}")
    check(r.returncode == 4 and gate.get("spend_gate") == "closed" and gate.get("model") == "fal-ai/nano-banana-2"
          and gate.get("per_image_usd", 0) > 0 and not (pe / "fal").exists(),
          f"photo_edit fal spend gate must close without --confirm-spend (exit {r.returncode}, {gate})")
    man = pe / "manual"
    man_cmd = ["render", str(spec_p), "--select", "paper-backdrop,plaster-wall", "--backend", "manual", "--out", str(man)]
    r = run(str(S / "photo_edit.py"), *man_cmd)
    mo = json.loads(r.stdout or "{}")
    check(r.returncode == 5 and mo.get("awaiting_file") == 2 and (man / "_manual" / "PHOTO-EDIT-PACK.md").is_file()
          and len(list((man / "_manual").glob("*.prompt.txt"))) == 2,
          f"photo_edit manual must write the pack and exit 5 (exit {r.returncode}, {mo})")
    from PIL import Image
    want_man = {c["id"]: c.get("size") or "1536x1024" for ph in pe_spec["photos"] for c in ph["concepts"]}
    Image.new("RGB", (640, 480), (120, 90, 60)).save(man / "founder-jar--paper-backdrop.jpg")
    r = run(str(S / "photo_edit.py"), *man_cmd)
    mo = json.loads(r.stdout or "{}")
    check(r.returncode == 5 and mo.get("rendered") == 1 and mo.get("awaiting_file") == 1,
          f"photo_edit manual must collect the dropped file and keep waiting for the other (exit {r.returncode}, {mo})")
    with Image.open(man / "founder-jar--paper-backdrop.png") as im:
        check(f"{im.size[0]}x{im.size[1]}" == want_man["paper-backdrop"], f"photo_edit manual: collected file {im.size}")
    Image.new("RGB", (800, 800), (60, 90, 120)).save(man / "founder-jar--plaster-wall.webp")
    r = run(str(S / "photo_edit.py"), *man_cmd)
    check(r.returncode == 0 and json.loads(r.stdout)["rendered"] == 2, f"photo_edit manual second drop: exit {r.returncode}")
    r = run(str(S / "photo_edit.py"), "verify", str(spec_p), "--out", str(man))
    check(r.returncode == 0 and json.loads(r.stdout)["status"] == "awaiting_review",
          f"photo_edit verify on manual drops: exit {r.returncode}, {r.stdout[-300:]}")
    dflt = pe / "default"
    r = run(str(S / "photo_edit.py"), "render", str(spec_p), "--select", "paper-backdrop", "--out", str(dflt))
    mo = json.loads(r.stdout or "{}")
    check(r.returncode == 5 and mo.get("awaiting_file") == 1 and (dflt / "_manual" / "PHOTO-EDIT-PACK.md").is_file()
          and not list(dflt.glob("*.png")), f"photo_edit default backend must be manual (exit {r.returncode}, {mo})")
    hf = pe / "higgsfield"
    r = run(str(S / "photo_edit.py"), "render", str(spec_p), "--select", "paper-backdrop", "--backend", "higgsfield", "--out", str(hf))
    plan = json.loads((hf / "_manual" / "higgsfield-plan.json").read_text(encoding="utf-8")) if (hf / "_manual" / "higgsfield-plan.json").is_file() else {}
    call = (plan.get("calls") or [{}])[0]
    check(r.returncode == 5 and call.get("cost", {}).get("params", {}).get("get_cost") is True
          and call.get("render", {}).get("params", {}).get("model") == "gpt_image_2_5"
          and call["render"]["params"]["medias"][0]["role"] == "image_references"
          and call["render"]["params"]["aspect_ratio"] in ("3:2", "2:3", "1:1") and call.get("save_as") == "founder-jar--paper-backdrop.png",
          f"photo_edit higgsfield plan (exit {r.returncode}, {call})")
    print(f"photo edit: {len(recs)} stub renders, review verdicts {got}, consent, spend, public URL and manual pack and Higgsfield plan checked")

    # 7. Winning recipe: seed from the perf winner, variants, one-variable check.
    rv = base / "recipe"
    rv.mkdir()
    r = run(str(S / "recipe_variants.py"), "seed", "--spec", str(FX / "all-styles" / "ads.json"), "--perf", str(base / "perf.json"),
            "--out", str(rv / "seed.json"))
    seed = json.loads((rv / "seed.json").read_text(encoding="utf-8")) if r.returncode == 0 else {}
    check(r.returncode == 0 and seed.get("source", {}).get("ad_name") == p["winners"][0] and seed.get("control", {}).get("id") == "compare"
          and seed.get("hook_type") == "", f"recipe seed must pick the first winner from its spec ({r.stderr[-300:]})")
    r = run(str(S / "recipe_variants.py"), "check-recipe", str(rv / "seed.json"))
    check(r.returncode == 1, "recipe check-recipe must fail while the judgement fields are empty")
    r = run(str(S / "recipe_variants.py"), "check-recipe", str(FX / "recipe" / "recipe.json"))
    check(r.returncode == 0, f"recipe fixture must pass check-recipe: {r.stderr[-300:]}")
    r = run(str(S / "recipe_variants.py"), "build", str(FX / "recipe" / "recipe.json"), "--hooks", str(FX / "recipe" / "hooks.json"),
            "--out", str(rv / "ads.json"), "--date", "2026-10-21")
    check(r.returncode == 0, f"recipe build exit {r.returncode}: {r.stderr[-400:]}")
    vs = json.loads((rv / "ads.json").read_text(encoding="utf-8"))
    variables = [a_["test"]["variable"] for a_ in vs["ads"]]
    names = [row["names"][1] for row in json.loads(r.stdout)["variants"]]
    check(variables == ["cta", "hook", "hook", "hook", "hook"], f"recipe variants: {variables}")
    check(all(adspec.parse_ad_name(nm) and adspec.parse_ad_name(nm)["test"] == var for nm, var in zip(names, variables)),
          f"recipe variant names must carry _t-<variable>: {names}")
    check(adspec.parse_ad_name("acme_20_tofu_anti-category_bold-statement_4x5_t-bogus") is None, "an unknown test token must not parse")
    r = run(str(S / "build.py"), str(rv / "ads.json"), "--out", str(rv / "html"))
    check(r.returncode == 0, f"recipe variants must build with 0 error: {r.stdout[-400:]}")

    def tamper(name: str, mutate) -> set:
        t = json.loads(json.dumps(vs))
        mutate(t["ads"])
        tp = rv / f"{name}.json"
        tp.write_text(json.dumps(t), encoding="utf-8")
        rr = run(str(S / "recipe_variants.py"), "check", str(tp), "--recipe", str(FX / "recipe" / "recipe.json"))
        return {i["code"] for i in json.loads(rr.stdout or "{}").get("issues", []) if i["level"] == "error"} if rr.returncode == 1 else set()

    check("variant-multi" in tamper("two-vars", lambda ads: ads[1]["copy"].__setitem__("cta", "Order a jar")), "check must refuse two variables")
    check("variant-structure" in tamper("structure", lambda ads: ads[2].__setitem__("formats", ["4:5"])), "check must refuse a structure change")
    check("variant-mismatch" in tamper("mismatch", lambda ads: ads[3]["test"].__setitem__("variable", "subhead")), "check must refuse a wrong declared variable")
    hk = json.loads((FX / "recipe" / "hooks.json").read_text(encoding="utf-8"))
    hk["hooks"][0]["text"] = "We cook 14 jars per pan."
    (rv / "hooks-unsourced.json").write_text(json.dumps(hk), encoding="utf-8")
    r = run(str(S / "recipe_variants.py"), "build", str(FX / "recipe" / "recipe.json"), "--hooks", str(rv / "hooks-unsourced.json"),
            "--out", str(rv / "unsourced" / "ads.json"))
    check(r.returncode == 1 and "unsourced-number" in r.stderr, "recipe build must refuse a hook with an unsourced number")
    print(f"recipe: seed {seed.get('source', {}).get('ad_name')}, {len(variables)} variants ({', '.join(variables)}), one-variable check enforced")

    # 8. All styles.
    if not a.quick:
        al = base / "all-styles"
        r = run(str(S / "pipeline.py"), str(FX / "all-styles" / "ads.json"), "--out", str(al), "--no-sheet")
        aq = json.loads((al / "renders" / "qa.json").read_text(encoding="utf-8"))
        check(aq["status"] == "pass" and aq["summary"]["renders"] == 54, f"all styles: {aq['summary']}")
        bad = [f"{s['name']}: {[e['code'] for e in s['errors']]}" for s in aq["sections"] if s["errors"]]
        story = [f"{s['name']}: {w['code']}" for s in aq["sections"] for w in s["warnings"] if w["code"] in ("dead-space-9x16", "empty-band")]
        check(not story, f"all styles 9:16 layout: {story[:6]}")
        lg = {s["metrics"].get("logo") for s in aq["sections"]}
        check(lg == {"lockup"}, f"all styles: every render must carry the logo lockup, got {lg}")
        for b in bad[:10]:
            print(f"  {b}")
        print(f"all styles: {aq['status']}, {aq['summary']['renders']} renders, {aq['summary']['warnings']} warnings, 9:16 layout warnings {len(story)}")

    print(f"selftest: {'PASS' if not FAILS else 'FAIL'} ({len(FAILS)} failures, outputs in {base})")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
