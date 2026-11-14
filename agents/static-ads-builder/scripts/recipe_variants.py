#!/usr/bin/env python3
"""recipe_variants.py: the winning ad's recipe, then one-variable test variants (mode winning_recipe).

  python3 scripts/recipe_variants.py seed --spec <ads.json of the winner's run> --out recipe.json
                                          (--perf ads-performance-YYYYMMDD.json | --ad-name NAME --why "...")
  python3 scripts/recipe_variants.py check-recipe recipe.json
  python3 scripts/recipe_variants.py build recipe.json --hooks hooks.json --out <run>/ads.json
                                          [--count 5 | --config config.json] [--start-n N]
  python3 scripts/recipe_variants.py check <run>/ads.json --recipe recipe.json

seed          finds the winner (first winner of the perf file whose name follows
              the convention and is in --spec, or --ad-name) and writes
              recipe.json with every measured field filled from the ad as it
              ran: angle, style, stage, formats, surface, CTA, word counts,
              the zones and reading order present, and the control ad itself.
              The judgement fields stay empty for the model: hook_type, the
              area of each zone, palette.accent_role. check-recipe fails until
              they are written.
check-recipe  schema (assets/recipe.schema.json), the control against
              assets/ads.schema.json, and the recipe against the control:
              same angle, style, stage, formats, surface, CTA, word counts,
              zones that exist on the ad.
build         recipe + hooks.json (assets/hooks.schema.json) -> ads.json with
              --count variants (default: config recipe.variants, else 5). Alternates first, one variant
              each (cta, visual, surface, subhead), then the new hooks. Each
              variant is a copy of the control with one variable changed,
              extends the winner, carries test.variable (the ad name gets
              _t-<variable>), and keeps the control's claims plus the hook's
              own. Meta, sources and brand come from the winner's run. Then
              runs check.
check         every ad with a test block changes exactly the variable it
              declares against the control, nothing else (style, stage,
              angle, formats, bullets, columns, proof, Meta text and the
              other variables stay equal); plus the ads.json schema and lint
              (claims policy: a number needs a sourced claim). A variant that
              changes two variables, none, or the structure is an error.

Exit codes: 0 ok, 1 errors (build: ads.json still written), 3 bad input.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
sys.path.insert(0, str(HERE))
import adspec  # noqa: E402
from adspec import Issue  # noqa: E402

RECIPE_SCHEMA = AGENT / "assets" / "recipe.schema.json"
HOOKS_SCHEMA = AGENT / "assets" / "hooks.schema.json"
ALT_ORDER = ("cta", "visual", "surface", "subhead")
ROLE_ORDER = ("badge", "headline", "subhead", "media", "bullets", "columns", "comment", "callouts", "proof", "cta", "logo")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_issues(inst: Any, schema_path: Path, ref: Optional[str] = None, prefix: str = "$") -> List[Issue]:
    v = adspec.SchemaValidator(read(schema_path))
    msgs = v.validate(inst, {"$ref": ref} if ref else None, prefix)
    return [Issue("error", "schema", *m.split(": ", 1)) if ": " in m else Issue("error", "schema", prefix, m) for m in msgs]


def words(text: Optional[str]) -> int:
    return len(adspec.tokens((text or "").replace("*", "")))


def band(n: int) -> str:
    return "short" if n <= 8 else ("medium" if n <= 14 else "long")


def roles(ad: Dict[str, Any]) -> List[str]:
    c = ad.get("copy") or {}
    present = {"badge": c.get("badge"), "headline": c.get("headline"), "subhead": c.get("subhead"), "media": ad.get("media"),
               "bullets": c.get("bullets"), "columns": c.get("columns"), "comment": c.get("comment"), "callouts": c.get("callouts"),
               "proof": ad.get("proof"), "cta": c.get("cta"), "logo": ad.get("logo", True)}
    return [r for r in ROLE_ORDER if present[r]]


def find_ad(spec: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    for i, ad in enumerate(spec.get("ads") or []):
        for fmt in ad.get("formats") or []:
            if adspec.ad_name(spec, ad, i, fmt) == name:
                return ad
    return None


def resolve_brand(spec: Dict[str, Any], spec_path: Path) -> Optional[Path]:
    rel = (spec.get("meta") or {}).get("brand")
    if rel:
        return (spec_path.parent / rel).resolve()
    for up in (spec_path.parent, spec_path.parent.parent, spec_path.parent.parent.parent):
        if (up / "project-context" / "brand.json").exists():
            return (up / "project-context" / "brand.json").resolve()
    return None


# --------------------------------------------------------------------------
# seed
# --------------------------------------------------------------------------

def cmd_seed(a: argparse.Namespace) -> int:
    try:
        spec_path = Path(a.spec).resolve()
        spec = read(spec_path)
        perf = read(Path(a.perf)) if a.perf else None
    except (OSError, json.JSONDecodeError) as e:
        print(f"recipe_variants: cannot read the input ({e})", file=sys.stderr)
        return 3
    out = Path(a.out).resolve()
    if a.ad_name:
        name, picked, why = a.ad_name, "manual", a.why or ""
        if perf:
            m = next((x for x in perf.get("ads") or [] if x.get("ad_name") == name), None)
            if m:
                picked, why = "perf", a.why or m.get("why", "")
    elif perf:
        ads = {m["ad_name"]: m for m in perf.get("ads") or []}
        name = next((w for w in perf.get("winners") or [] if adspec.parse_ad_name(w) and find_ad(spec, w)), None)
        if not name:
            print("recipe_variants: no winner of the perf file follows the naming convention and is in --spec; "
                  "name the ad with --ad-name and write the control by hand if it was not built by this agent.", file=sys.stderr)
            return 1
        picked, why = "perf", ads[name].get("why", "")
    else:
        print("recipe_variants: give --perf (the winner is read there) or --ad-name.", file=sys.stderr)
        return 3
    control = find_ad(spec, name)
    if control is None:
        print(f"recipe_variants: {name} is not an ad of {spec_path.name} in any of its formats.", file=sys.stderr)
        return 1
    control = copy.deepcopy(control)
    for k in ("test", "extends"):
        control.pop(k, None)
    c = control.get("copy") or {}
    hw = words(c.get("headline"))
    present = roles(control)
    recipe = {
        "schema_version": "1.0",
        "source": {"ad_name": name, "picked_by": picked, "why": why,
                   **({"perf_file": os.path.relpath(Path(a.perf).resolve(), out.parent)} if a.perf else {}),
                   "spec": os.path.relpath(spec_path, out.parent)},
        "angle": control.get("angle"), "hook_type": "",
        "text_length": {"headline_words": hw, "subhead_words": words(c.get("subhead")), "band": band(hw)},
        "layout": {"zones": [{"role": r, "area": ""} for r in present], "hierarchy": present},
        "style": control.get("style"),
        "palette": {"surface": control.get("surface") or "brand", "accent_role": ""},
        "cta": {"on_ad": c.get("cta") or "", "meta": (control.get("meta_ad") or {}).get("cta") or ""},
        "funnel_stage": control.get("stage"), "formats": list(control.get("formats") or []),
        "control": control,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"recipe": str(out), "ad_name": name, "picked_by": picked,
                      "left_for_the_model": ["hook_type", "layout.zones[].area", "palette.accent_role"]}, indent=2))
    return 0


# --------------------------------------------------------------------------
# check-recipe
# --------------------------------------------------------------------------

def recipe_issues(recipe: Dict[str, Any]) -> List[Issue]:
    issues = schema_issues(recipe, RECIPE_SCHEMA)
    control = recipe.get("control")
    if not isinstance(control, dict):
        return issues
    issues += schema_issues(control, adspec.SCHEMA_PATH, "#/$defs/ad", "$.control")
    for path, text in adspec._walk_strings(recipe, "$"):
        if adspec.DASH_RE.search(text):
            issues.append(Issue("error", "dash", path, "Em or en dash: use a comma, colon, period or parentheses."))
    c = control.get("copy") or {}

    def same(field: str, got: Any, want: Any) -> None:
        if got != want:
            issues.append(Issue("error", "recipe-mismatch", f"$.{field}", f"{got!r} in the recipe, {want!r} on the control ad."))

    same("angle", recipe.get("angle"), control.get("angle"))
    same("style", recipe.get("style"), control.get("style"))
    same("funnel_stage", recipe.get("funnel_stage"), control.get("stage"))
    same("formats", sorted(recipe.get("formats") or []), sorted(control.get("formats") or []))
    same("palette.surface", (recipe.get("palette") or {}).get("surface"), control.get("surface") or "brand")
    same("cta.on_ad", (recipe.get("cta") or {}).get("on_ad"), c.get("cta") or "")
    same("cta.meta", (recipe.get("cta") or {}).get("meta"), (control.get("meta_ad") or {}).get("cta") or "")
    tl = recipe.get("text_length") or {}
    same("text_length.headline_words", tl.get("headline_words"), words(c.get("headline")))
    same("text_length.subhead_words", tl.get("subhead_words"), words(c.get("subhead")))
    if isinstance(tl.get("headline_words"), int):
        same("text_length.band", tl.get("band"), band(tl["headline_words"]))
    present = set(roles(control))
    lay = recipe.get("layout") or {}
    for i, z in enumerate(lay.get("zones") or []):
        if z.get("role") not in present:
            issues.append(Issue("error", "recipe-zone", f"$.layout.zones[{i}]", f"'{z.get('role')}' is not on the control ad (it shows {', '.join(sorted(present))})."))
    for i, r in enumerate(lay.get("hierarchy") or []):
        if r not in present:
            issues.append(Issue("error", "recipe-zone", f"$.layout.hierarchy[{i}]", f"'{r}' is not on the control ad."))
    parsed = adspec.parse_ad_name((recipe.get("source") or {}).get("ad_name", ""))
    if not parsed:
        issues.append(Issue("warning", "name-convention", "$.source.ad_name", "The winner's name does not follow the convention: its stage, angle and style are read from the control only."))
    else:
        for k, field in (("stage", "funnel_stage"), ("angle", "angle"), ("style", "style")):
            same(f"source.ad_name ({k})", parsed[k], recipe.get(field))
    return issues


def report(issues: List[Issue], extra: Dict[str, Any]) -> int:
    n = adspec.counts(issues)
    print(json.dumps({"status": "pass" if not n["errors"] else "fail", **n, **extra,
                      "issues": [i.to_dict() for i in issues]}, indent=2, ensure_ascii=False))
    for i in issues:
        print(f"{i.level.upper()} {i.code} {i.where}: {i.message}", file=sys.stderr)
    return 0 if not n["errors"] else 1


def cmd_check_recipe(a: argparse.Namespace) -> int:
    try:
        recipe = read(Path(a.recipe))
    except (OSError, json.JSONDecodeError) as e:
        print(f"recipe_variants: cannot read the recipe ({e})", file=sys.stderr)
        return 3
    return report(recipe_issues(recipe), {"recipe": a.recipe})


# --------------------------------------------------------------------------
# One-variable diff
# --------------------------------------------------------------------------

def facets(ad: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(ad.get("copy") or {})
    ma = dict(ad.get("meta_ad") or {})
    meta_cta = ma.pop("cta", None)
    rest = {k: v for k, v in c.items() if k not in ("headline", "subhead", "cta")}
    return {
        "hook": c.get("headline"),
        "subhead": c.get("subhead"),
        "cta": [c.get("cta"), meta_cta],
        "visual": ad.get("media") or [],
        "surface": ad.get("surface") or "brand",
        "structure": {"stage": ad.get("stage"), "angle": ad.get("angle"), "style": ad.get("style"),
                      "formats": sorted(ad.get("formats") or []), "copy": rest, "proof": ad.get("proof"),
                      "logo": ad.get("logo", True), "meta_ad": ma},
    }


def changed(control: Dict[str, Any], ad: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    fa, fb = facets(control), facets(ad)
    vars_ = [k for k in fa if k != "structure" and fa[k] != fb[k]]
    struct = [k for k in fa["structure"] if fa["structure"][k] != fb["structure"][k]]
    return vars_, struct


def variant_issues(spec: Dict[str, Any], recipe: Dict[str, Any]) -> Tuple[List[Issue], List[Dict[str, Any]]]:
    issues: List[Issue] = []
    rows = []
    control = recipe.get("control") or {}
    winner = (recipe.get("source") or {}).get("ad_name")
    for i, ad in enumerate(spec.get("ads") or []):
        w = f"$.ads[{i}]"
        test = ad.get("test")
        if not test:
            issues.append(Issue("warning", "not-a-variant", w, "No test block: this ad is not checked against the recipe."))
            continue
        var = test.get("variable")
        vs, struct = changed(control, ad)
        rows.append({"id": ad.get("id"), "variable": var, "changed": vs, "structure_changed": struct,
                     "names": [adspec.ad_name(spec, ad, i, f) for f in ad.get("formats") or []]})
        if (ad.get("extends") or {}).get("ad_name") != winner:
            issues.append(Issue("error", "variant-control", f"{w}.extends", f"A recipe variant extends the winner {winner}."))
        if "visual" in vs and not control.get("media"):
            struct.append("media added to an ad without media")
        if struct:
            issues.append(Issue("error", "variant-structure", w, f"Changes the structure ({', '.join(struct)}): a variant keeps the winner's structure."))
        if len(vs) > 1:
            issues.append(Issue("error", "variant-multi", w, f"Changes {len(vs)} variables ({', '.join(vs)}): one per variant."))
        elif not vs:
            issues.append(Issue("error", "variant-none", w, "Changes nothing against the control."))
        elif vs[0] != var:
            issues.append(Issue("error", "variant-mismatch", f"{w}.test.variable", f"Declares {var}, changes {vs[0]}."))
    return issues, rows


def cmd_check(a: argparse.Namespace) -> int:
    try:
        recipe = read(Path(a.recipe))
    except (OSError, json.JSONDecodeError) as e:
        print(f"recipe_variants: cannot read the recipe ({e})", file=sys.stderr)
        return 3
    spec, issues = adspec.load_spec(Path(a.ads))
    if spec is None:
        report(issues, {"ads": a.ads})
        return 3
    vi, rows = variant_issues(spec, recipe)
    return report(issues + vi, {"ads": a.ads, "variants": rows})


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def make_id(base: str, var: str, k: int) -> str:
    suffix = f"-{var}-{k}"
    return (base[:41 - len(suffix)].rstrip("-") + suffix)[:41]


def cmd_build(a: argparse.Namespace) -> int:
    rpath = Path(a.recipe).resolve()
    out = Path(a.out).resolve()
    try:
        recipe = read(rpath)
        hooks = read(Path(a.hooks))
    except (OSError, json.JSONDecodeError) as e:
        print(f"recipe_variants: cannot read the input ({e})", file=sys.stderr)
        return 3
    ri = recipe_issues(recipe)
    hi = schema_issues(hooks, HOOKS_SCHEMA)
    if adspec.counts(ri + hi)["errors"]:
        print("recipe_variants: fix recipe.json (check-recipe) and hooks.json first.", file=sys.stderr)
        return report(ri + hi, {"recipe": a.recipe, "hooks": a.hooks})
    control = recipe["control"]
    src = recipe["source"]
    base_spec: Dict[str, Any] = {}
    meta: Dict[str, Any]
    if src.get("spec"):
        spath = (rpath.parent / src["spec"]).resolve()
        try:
            base_spec = read(spath)
        except (OSError, json.JSONDecodeError) as e:
            print(f"recipe_variants: cannot read the winner's spec {spath} ({e})", file=sys.stderr)
            return 3
        meta = copy.deepcopy(base_spec.get("meta") or {})
        brand = resolve_brand(base_spec, spath)
        if brand:
            meta["brand"] = os.path.relpath(brand, out.parent)
        else:
            meta.pop("brand", None)
    else:
        parsed = adspec.parse_ad_name(src["ad_name"]) or {}
        meta = {"project": parsed.get("project", "ads"), "language": a.language}
    meta["date"] = a.date or date.today().isoformat()
    meta.pop("input", None)
    sources = {s["id"]: s for s in base_spec.get("sources") or []}
    for s in hooks.get("sources") or []:
        if s["id"] in sources and sources[s["id"]].get("url") != s.get("url"):
            print(f"recipe_variants: source id '{s['id']}' already used with another URL.", file=sys.stderr)
            return 1
        sources[s["id"]] = s
    plan: List[Tuple[str, Any]] = []
    alts = hooks.get("alternates") or {}
    for var in ALT_ORDER:
        plan += [(var, v) for v in alts.get(var) or []]
    plan += [("hook", h) for h in hooks.get("hooks") or []]
    if len(plan) < a.count:
        print(f"recipe_variants: {len(plan)} variant(s) possible, {a.count} asked: write {a.count - len(plan)} more hook(s) or alternate(s).", file=sys.stderr)
        return 1
    unused = len(plan) - a.count
    plan = plan[:a.count]
    start = a.start_n or (max([adspec.ad_number(x, i) for i, x in enumerate(base_spec.get("ads") or [])] + [adspec.ad_number(control, 0)]) + 1)
    if start + a.count - 1 > 99:
        print("recipe_variants: ad numbers would pass 99; give --start-n.", file=sys.stderr)
        return 1
    ads = []
    for k, (var, val) in enumerate(plan, start=1):
        v = copy.deepcopy(control)
        v["id"] = make_id(control["id"], var, k)
        v["n"] = start + k - 1
        v["extends"] = {"ad_name": src["ad_name"], "why": src["why"]}
        v["test"] = {"variable": var, "recipe": os.path.relpath(rpath, out.parent)}
        c = v.setdefault("copy", {})
        if var == "hook":
            c["headline"] = val["text"]
            v["claims"] = list(control.get("claims") or []) + list(val.get("claims") or [])
            if val.get("why"):
                v["notes"] = val["why"]
        elif var == "cta":
            c["cta"] = val["on_ad"]
            if val.get("meta"):
                v.setdefault("meta_ad", {})["cta"] = val["meta"]
        elif var == "visual":
            if not control.get("media"):
                print("recipe_variants: a visual alternate needs a control with media; drop it or pick another variable.", file=sys.stderr)
                return 1
            v["media"] = [val]
        elif var == "surface":
            v["surface"] = val
        elif var == "subhead":
            c["subhead"] = val
        if not v.get("claims"):
            v.pop("claims", None)
        ads.append(v)
    spec = {"schema_version": "1.0", "meta": meta, **({"sources": list(sources.values())} if sources else {}), "ads": ads}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    loaded, issues = adspec.load_spec(out)
    vi, rows = variant_issues(loaded or spec, recipe)
    if unused:
        issues.append(Issue("warning", "unused", "$", f"{unused} hook(s) or alternate(s) left out (count {a.count})."))
    return report(issues + vi, {"ads": str(out), "variants": rows})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--spec", required=True, help="ads.json of the run that produced the winner")
    s.add_argument("--perf", help="ads-performance-YYYYMMDD.json (perf.py output)")
    s.add_argument("--ad-name", help="The winner, named by hand")
    s.add_argument("--why", help="Why it won (metric), when named by hand")
    s.add_argument("--out", required=True, help="recipe.json to write")
    cr = sub.add_parser("check-recipe")
    cr.add_argument("recipe")
    b = sub.add_parser("build")
    b.add_argument("recipe")
    b.add_argument("--hooks", required=True)
    b.add_argument("--out", required=True, help="ads.json to write")
    b.add_argument("--count", type=int, help="Variants to write (default: config recipe.variants, else 5)")
    b.add_argument("--config", help="config.json holding a recipe object")
    b.add_argument("--start-n", type=int, help="NN of the first variant (default: after the winner's run)")
    b.add_argument("--date", help="meta.date (default today)")
    b.add_argument("--language", default="en", choices=["en", "fr"], help="meta.language when the recipe has no source spec")
    c = sub.add_parser("check")
    c.add_argument("ads")
    c.add_argument("--recipe", required=True)
    a = ap.parse_args()
    if a.cmd == "build" and a.count is None:
        try:
            a.count = int(((read(Path(a.config)) if a.config else {}).get("recipe") or {}).get("variants") or 5)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"recipe_variants: config not read ({e})", file=sys.stderr)
            return 3
    if a.cmd == "build" and not 1 <= a.count <= 10:
        print("recipe_variants: --count between 1 and 10.", file=sys.stderr)
        return 3
    return {"seed": cmd_seed, "check-recipe": cmd_check_recipe, "build": cmd_build, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
