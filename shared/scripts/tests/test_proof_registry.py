#!/usr/bin/env python3
"""
test_proof_registry.py

Tests for shared/scripts/proof.py and shared/scripts/registry.py. Standard
library only, offline:

    python3 shared/scripts/tests/test_proof_registry.py

proof.py: legacy strings accepted with a warning, objects normalized, stale
metric, future date, missing source or date, consent missing, refused, unknown
or out of scope, malformed objects and duplicate ids, file sources under
--root, the check command and its exit codes.
registry.py: the example registries, allowed() per scope, operator, absent
entry, refused and unknown consent, logo per background, the check command
(photo without consent, missing asset, granted without scope, duplicate slug,
broken JSON). Exit 0 when every test passes, 1 otherwise.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
SHARED = os.path.dirname(SCRIPTS)
EXAMPLES = os.path.join(SHARED, "schemas", "examples")
sys.path.insert(0, SCRIPTS)
import proof  # noqa: E402
import registry  # noqa: E402
from validate_json import validate  # noqa: E402

FAILURES = []
PASSED = 0
TODAY = date(2026, 11, 3)


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}")


def cli(script, args):
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)] + args, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


def context(items):
    return {"project_slug": "fixturely", "positioning": {"promise": "Invoices that chase themselves", "proof": items}}


CONSENT_OK = {"status": "granted", "scope": ["posts", "carousel"], "date": days_ago(20), "by": "the customer, email"}


def test_proof():
    legacy = proof.load_proof(context(["1 240 freelancers on the waitlist"]))
    check("legacy string kept", len(legacy) == 1 and legacy[0].legacy and legacy[0].claim == "1 240 freelancers on the waitlist")
    ok, why = proof.usable(legacy[0], "posts", TODAY)
    check("legacy string usable with a warning", ok and "legacy" in why, why)
    check("proof_text of a string, an object and a Proof",
          proof.proof_text("a") == "a" and proof.proof_text({"claim": "b"}) == "b" and proof.proof_text(legacy[0]) == legacy[0].claim)
    check("no positioning gives no item", proof.load_proof({}) == [] and proof.load_proof(None) == [])

    metric = {"id": "waitlist", "claim": "1 240 freelancers on the waitlist", "kind": "metric",
              "source": "https://fixturely.example/blog/waitlist", "date": days_ago(30)}
    items = proof.load_proof(context([metric]))
    check("fresh metric usable", proof.usable(items[0], "ads", TODAY) == (True, ""), proof.usable(items[0], "ads", TODAY))

    cases = {
        "stale metric (default 180 days)": (dict(metric, date=days_ago(200)), "stale"),
        "stale metric (own valid_days)": (dict(metric, date=days_ago(40), valid_days=30), "valid 30 days"),
        "metric dated in the future": (dict(metric, date=(TODAY + timedelta(days=3)).isoformat()), "after today"),
        "metric without source": ({k: v for k, v in metric.items() if k != "source"}, "needs a source"),
        "metric without date": ({k: v for k, v in metric.items() if k != "date"}, "needs the date"),
        "testimonial without consent": ({"id": "lena", "claim": "We get paid in a week now", "kind": "testimonial",
                                         "source": "docs/notes.md#p1", "date": days_ago(10)}, "malformed"),
        "testimonial consent unknown": ({"id": "lena", "claim": "We get paid in a week now", "kind": "testimonial",
                                         "source": "https://fixturely.example/stories/lena", "date": days_ago(10),
                                         "consent": {"status": "unknown"}}, "consent unknown"),
        "customer consent refused": ({"id": "acme", "claim": "Acme sends its invoices with Fixturely", "kind": "customer",
                                      "source": "https://fixturely.example/customers", "date": days_ago(10),
                                      "consent": {"status": "refused", "date": days_ago(5), "by": "Acme, email"}}, "refused"),
        "customer consent out of scope": ({"id": "acme", "claim": "Acme sends its invoices with Fixturely", "kind": "customer",
                                           "source": "https://fixturely.example/customers", "date": days_ago(10),
                                           "consent": dict(CONSENT_OK, scope=["site"])}, "not posts"),
        "granted consent without who": ({"id": "acme", "claim": "Acme sends its invoices with Fixturely", "kind": "customer",
                                         "source": "https://fixturely.example/customers", "date": days_ago(10),
                                         "consent": {"status": "granted", "scope": ["posts"], "date": days_ago(3)}}, "who gave it"),
        "unknown kind": (dict(metric, kind="rumor"), "malformed"),
        "unknown key": (dict(metric, url="https://x.example"), "malformed"),
        "not a calendar date": (dict(metric, date="2026-02-31"), "calendar date"),
        "absolute file source": (dict(metric, source="/home/me/deck.pdf#p2"), "malformed"),
        "climbing file source": (dict(metric, source="../deck.pdf"), "malformed"),
    }
    for name, (item, expected) in cases.items():
        p = proof.load_proof(context([item]))[0]
        ok, why = proof.usable(p, "posts", TODAY)
        check(f"refused: {name}", not ok and expected in why, why)

    testimonial = {"id": "lena", "claim": "We get paid in a week now", "kind": "testimonial",
                   "source": "https://fixturely.example/stories/lena", "date": days_ago(10), "consent": CONSENT_OK}
    p = proof.load_proof(context([testimonial]))[0]
    check("testimonial with consent for posts usable", proof.usable(p, "posts", TODAY) == (True, ""))
    check("same testimonial refused for ads", not proof.usable(p, "ads", TODAY)[0])
    feature = {"id": "reminders", "claim": "Reminders go out on the due date", "kind": "feature"}
    check("feature needs no source nor date", proof.usable(proof.load_proof(context([feature]))[0], "ads", TODAY) == (True, ""))
    press = {"id": "press", "claim": "Featured in Ledger Weekly", "kind": "press", "source": "https://ledger.example/a", "date": "2019-04-01"}
    check("press mention does not go stale", proof.usable(proof.load_proof(context([press]))[0], "ads", TODAY)[0])
    check("expires_on uses the kind default", proof.expires_on(proof.load_proof(context([metric]))[0]) == TODAY - timedelta(days=30) + timedelta(days=180))
    check("a number is a malformed legacy item", not proof.usable(proof.load_proof(context([12]))[0], "posts", TODAY)[0])

    dup = proof.load_proof(context([metric, dict(metric)]))
    check("duplicate id is an error", not dup[0].errors and any("already used" in e for e in dup[1].errors), dup[1].errors)
    usable_items, refused, warnings = proof.partition(proof.load_proof(context(["legacy", metric, dict(metric, id="old", date=days_ago(400))])), "posts", TODAY)
    check("partition splits usable, refused, warnings", [p.id for p in usable_items] == ["proof-0", "waitlist"]
          and [p.id for p, _ in refused] == ["old"] and len(warnings) == 1)

    schema = json.load(open(proof.CONTEXT_SCHEMA, encoding="utf-8"))
    check("proof_item definition accepts the full object", validate(testimonial, schema["definitions"]["proof_item"], schema) == [])
    check("schema items are oneOf string or proof_item",
          schema["properties"]["positioning"]["properties"]["proof"]["items"]["oneOf"][1] == {"$ref": "#/definitions/proof_item"})

    tmp = tempfile.mkdtemp(prefix="proof-test-")
    try:
        os.makedirs(os.path.join(tmp, "docs"))
        with open(os.path.join(tmp, "docs", "deck.pdf"), "wb") as f:
            f.write(b"%PDF-1.4\n")
        deck = dict(metric, id="deck", source="docs/deck.pdf#p3")
        missing = dict(metric, id="gone", source="docs/missing.pdf#p1")
        items = proof.load_proof(context([deck, missing]))
        check("file source found under root", proof.usable(items[0], "posts", TODAY, root=tmp) == (True, ""))
        check("file source missing under root", "not found" in proof.usable(items[1], "posts", TODAY, root=tmp)[1])
        path = os.path.join(tmp, "context.json")
        good = context(["legacy item", metric, dict(metric, id="old", date=days_ago(400)), testimonial])
        json.dump(good, open(path, "w", encoding="utf-8"))
        rc, out = cli("proof.py", ["check", path, "--scope", "posts", "--today", TODAY.isoformat(), "--json"])
        report = json.loads(out) if rc in (0, 1) else {}
        check("check exits 0 with refused items only", rc == 0, out[-300:])
        check("check counts usable, warning, refused", report.get("counts") == {"usable": 2, "warning": 1, "refused": 1}, report.get("counts"))
        json.dump(context([dict(metric, kind="rumor")]), open(path, "w", encoding="utf-8"))
        rc, out = cli("proof.py", ["check", path])
        check("check exits 1 on a malformed object", rc == 1 and "malformed" in out, out[-300:])
        rc, out = cli("proof.py", ["check", path, "--scope", "billboard"])
        check("check exits 2 on an unknown scope", rc == 2, out)
        rc, out = cli("proof.py", ["check", os.path.join(tmp, "nope.json")])
        check("check exits 2 on a missing file", rc == 2, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_ctx(tmp):
    ctx = os.path.join(tmp, "project-context")
    for sub in ("assets/people", "assets/partners"):
        os.makedirs(os.path.join(ctx, sub))
    shutil.copy(os.path.join(EXAMPLES, "people.fixturely.json"), os.path.join(ctx, "people.json"))
    shutil.copy(os.path.join(EXAMPLES, "partners.fixturely.json"), os.path.join(ctx, "partners.json"))
    for rel in ("assets/people/ana-ruiz.jpg", "assets/people/lena-park.jpg", "assets/partners/acme.svg", "assets/partners/acme-white.svg"):
        with open(os.path.join(ctx, rel), "wb") as f:
            f.write(b"fixture")
    return ctx


def edit(path, fn):
    data = json.load(open(path, encoding="utf-8"))
    fn(data)
    json.dump(data, open(path, "w", encoding="utf-8"))


def test_registry():
    for name in ("people", "partners"):
        schema = json.load(open(os.path.join(SHARED, "schemas", f"{name}.schema.json"), encoding="utf-8"))
        example = json.load(open(os.path.join(EXAMPLES, f"{name}.fixturely.json"), encoding="utf-8"))
        check(f"{name} example valid", validate(example, schema) == [], validate(example, schema))
        broken = copy.deepcopy(example)
        broken[name][0]["consent"]["status"] = "maybe"
        check(f"{name} bad consent status caught", any("consent.status" in e for e in validate(broken, schema)))

    tmp = tempfile.mkdtemp(prefix="registry-test-")
    try:
        ctx = make_ctx(tmp)
        people, partners = registry.load_people(ctx), registry.load_partners(ctx)
        check("load_people and load_partners", len(people) == 3 and len(partners) == 2)
        check("missing registry gives []", registry.load_people(tmp) == [] and registry.load_partners(tmp) == [])
        ana, lena, tom = (registry.find(people, k) for k in ("Ana Ruiz", "lena-park", "TOM WELLER"))
        check("find by name or slug, case ignored", ana and lena and tom and lena["slug"] == "lena-park")
        check("is_operator", registry.is_operator(ana) and not registry.is_operator(lena) and not registry.is_operator(None))
        check("operator allowed for every scope", all(registry.allowed(ana, s)[0] for s in registry.SCOPES))
        check("granted for carousel: allowed in carousel", registry.allowed(lena, "carousel")[0])
        ok, why = registry.allowed(lena, "ads")
        check("granted for carousel: blocked in ads", not ok and "not ads" in why, why)
        ok, why = registry.allowed(tom, "carousel")
        check("unknown consent blocked", not ok and "unknown" in why, why)
        ok, why = registry.allowed(None, "ads")
        check("absent entry blocked", not ok and "not in the registry" in why, why)
        nw = registry.find(partners, "Northwind Ledger")
        ok, why = registry.allowed(nw, "ads")
        check("refused consent blocked", not ok and "refused" in why, why)
        acme = registry.find(partners, "acme")
        check("partner granted for ads allowed", registry.allowed(acme, "ads")[0])
        check("unknown scope blocked", not registry.allowed(acme, "billboard")[0])
        check("logo per background", registry.logo_for(acme, "dark", ctx).endswith("acme-white.svg")
              and registry.logo_for(acme, "light", ctx).endswith("acme.svg"))
        check("no dark logo: no silent fallback", registry.logo_for(nw, "dark", ctx) is None)
        check("granted without source blocked",
              not registry.allowed({"name": "X", "consent": {"status": "granted", "scope": ["ads"], "date": "2026-10-01"}}, "ads")[0])

        rc, out = cli("registry.py", ["check", ctx])
        check("check passes on the examples", rc == 0, out)
        rc, out = cli("registry.py", ["allowed", ctx, "--scope", "ads", "--json"])
        rows = json.loads(out)["entries"] if rc == 0 else []
        check("allowed lists the decisions", [r["slug"] for r in rows if r["allowed"]] == ["ana-ruiz", "acme"], rows)

        people_path = os.path.join(ctx, "people.json")
        edit(people_path, lambda d: d["people"][2].update(photo="assets/people/tom-weller.jpg"))
        with open(os.path.join(ctx, "assets/people/tom-weller.jpg"), "wb") as f:
            f.write(b"fixture")
        rc, out = cli("registry.py", ["check", ctx])
        check("photo without granted consent refused", rc == 1 and "photo stored without granted consent" in out, out)
        edit(people_path, lambda d: d["people"][2].pop("photo"))
        os.remove(os.path.join(ctx, "assets/people/lena-park.jpg"))
        rc, out = cli("registry.py", ["check", ctx])
        check("missing asset file refused", rc == 1 and "lena-park.jpg not found" in out, out)
        with open(os.path.join(ctx, "assets/people/lena-park.jpg"), "wb") as f:
            f.write(b"fixture")
        edit(people_path, lambda d: d["people"][1]["consent"].update(scope=[]))
        rc, out = cli("registry.py", ["check", ctx])
        check("granted without scope refused", rc == 1 and "no scope" in out, out)
        edit(people_path, lambda d: (d["people"][1]["consent"].update(scope=["posts"]), d["people"].append(dict(d["people"][2]))))
        rc, out = cli("registry.py", ["check", ctx])
        check("duplicate slug refused", rc == 1 and "slug already used" in out, out)
        edit(people_path, lambda d: d["people"][0].update(photo="/home/me/ana.jpg"))
        rc, out = cli("registry.py", ["check", ctx])
        check("absolute photo path refused by the schema", rc == 1 and "people[0].photo" in out, out)
        with open(os.path.join(ctx, "partners.json"), "w", encoding="utf-8") as f:
            f.write("{ not json")
        rc, out = cli("registry.py", ["check", ctx])
        check("broken JSON reported", rc == 1 and "cannot read" in out, out)
        try:
            registry.load_partners(ctx)
            check("load_partners raises on broken JSON", False)
        except registry.RegistryError:
            check("load_partners raises on broken JSON", True)
        rc, out = cli("registry.py", ["check", os.path.join(tmp, "nope")])
        check("check exits 2 on a missing folder", rc == 2, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    test_proof()
    test_registry()
    for f in FAILURES:
        print(f"FAIL {f}")
    print(f"{PASSED} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
