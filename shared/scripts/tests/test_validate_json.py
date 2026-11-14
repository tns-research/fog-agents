#!/usr/bin/env python3
"""
test_validate_json.py

Tests for shared/scripts/validate_json.py and the shared schemas. Standard
library only:

    python3 shared/scripts/tests/test_validate_json.py

Checks that every example instance is valid, that typical producer mistakes on
brand.json are caught with a readable message, that JSONL mode reports the
failing line, and the exit codes. Exit 0 when every test passes, 1 otherwise.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
SHARED = os.path.dirname(SCRIPTS)
SCHEMAS = os.path.join(SHARED, "schemas")
VALIDATOR = os.path.join(SCRIPTS, "validate_json.py")
sys.path.insert(0, SCRIPTS)
from validate_json import validate  # noqa: E402

FAILURES = []
PASSED = 0


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}")


def load(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return json.load(f)


def cli(args):
    proc = subprocess.run([sys.executable, VALIDATOR] + args, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def test_brand():
    schema = load(SCHEMAS, "brand.schema.json")
    good = load(SCHEMAS, "examples", "brand.swanbase.json")
    check("swanbase example valid", validate(good, schema) == [], validate(good, schema))

    minimal = {"schema_version": "2.0", "name": "acme", "mode": "light",
               "colors": {"bg": "#ffffff", "text": "#111111", "accent": "#0055ff"},
               "fonts": {"display": {"family": "Inter"}, "body": {"family": "Inter"}}}
    check("minimal brand valid", validate(minimal, schema) == [], validate(minimal, schema))

    mistakes = {
        "V1 key in colors": (lambda b: b["colors"].update(text_primary="#ffffff"), "unknown property 'text_primary'"),
        "color not hex": (lambda b: b["colors"].update(accent="purple"), "colors.accent"),
        "missing required body font": (lambda b: b["fonts"].pop("body"), "missing required property 'body'"),
        "path relative to project root": (
            lambda b: b["logos"]["on_dark"]["wordmark"].update(path="project-context/assets/logo.svg"),
            "logos.on_dark.wordmark.path"),
        "absolute path": (lambda b: b["assets"].update(favicon_path="/home/me/favicon.png"), "assets.favicon_path"),
        "climbing path": (lambda b: b["assets"].update(screenshot_path="assets/../../x.png"), "assets.screenshot_path"),
        "family with fallback stack": (
            lambda b: b["fonts"]["display"].update(family="'Instrument Serif', Georgia, serif"), "fonts.display.family"),
        "radius as number": (lambda b: b.update(radius=14), "radius: expected string"),
        "contrast above 21": (lambda b: b["logo_audit"]["checks"][0].update(contrast_ratio=40), "above the maximum 21"),
        "bad mode": (lambda b: b.update(mode="night"), "mode"),
        "missing schema_version (V1 file)": (lambda b: b.pop("schema_version"), "schema_version"),
        "weight out of range": (lambda b: b["fonts"]["body"].update(weights=[1000]), "fonts.body.weights[0]"),
    }
    for name, (mutate, expected) in mistakes.items():
        broken = copy.deepcopy(good)
        mutate(broken)
        errors = validate(broken, schema)
        check(f"brand catches: {name}", any(expected in e for e in errors), errors)


def test_other_examples():
    rules_schema = load(SCHEMAS, "copy-rules.schema.json")
    packs = os.path.join(SHARED, "skills", "writing-gate", "packs")
    for name in sorted(os.listdir(packs)):
        errors = validate(load(packs, name), rules_schema)
        check(f"pack {name} valid", errors == [], errors)
    run_schema = load(SCHEMAS, "run-record.schema.json")
    line = {"ts": "2026-10-10T16:42:00+02:00", "agent": "carousel-builder", "status": "ok",
            "inputs_hash": "3f9a1c0b7d2e", "checks": {"copy_lint": "pass"}, "critic_verdict": "PASS"}
    check("run record valid", validate(line, run_schema) == [], validate(line, run_schema))
    bad = dict(line, status="done", checks={"copy_lint": "ok"})
    errors = validate(bad, run_schema)
    check("run record catches status", any("status" in e for e in errors), errors)
    check("run record catches check value", any("checks.copy_lint" in e for e in errors), errors)


def test_keywords():
    schema = {"type": "object", "properties": {
        "n": {"type": "integer", "minimum": 1, "maximum": 3},
        "b": {"type": "boolean"},
        "s": {"type": ["string", "null"], "minLength": 2},
        "c": {"const": "x"},
        "l": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "number"}},
        "o": {"type": "object", "additionalProperties": {"type": "string"}},
    }}
    check("integer rejects bool", validate({"n": True}, schema) != [])
    check("integer accepts 2.0", validate({"n": 2.0}, schema) == [])
    check("number rejects bool", validate({"l": [True]}, schema) != [])
    check("null allowed by type list", validate({"s": None}, schema) == [])
    check("minLength", validate({"s": "a"}, schema) != [])
    check("const", validate({"c": "y"}, schema) != [])
    check("maxItems", validate({"l": [1, 2, 3]}, schema) != [])
    check("additionalProperties schema", validate({"o": {"k": 1}}, schema) != [])
    check("bad $ref reported", any("does not resolve" in e for e in validate(1, {"$ref": "#/$defs/x"})))


def test_cli():
    example = os.path.join(SCHEMAS, "examples", "brand.swanbase.json")
    brand_schema = os.path.join(SCHEMAS, "brand.schema.json")
    code, out = cli([brand_schema, example])
    check("cli valid exits 0", code == 0 and "valid" in out, out)
    with tempfile.TemporaryDirectory() as tmp:
        broken = load(example)
        broken["colors"]["bg"] = "navy"
        path = os.path.join(tmp, "brand.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(broken, f)
        code, out = cli([brand_schema, path])
        check("cli invalid exits 1", code == 1 and "colors.bg" in out, out)
        notjson = os.path.join(tmp, "x.json")
        with open(notjson, "w", encoding="utf-8") as f:
            f.write("{nope")
        check("cli not JSON exits 2", cli([brand_schema, notjson])[0] == 2)
        check("cli missing file exits 2", cli([brand_schema, os.path.join(tmp, "missing.json")])[0] == 2)
        check("cli usage exits 2", cli([brand_schema])[0] == 2)
        runs = os.path.join(tmp, "runs.jsonl")
        with open(runs, "w", encoding="utf-8") as f:
            f.write('{"ts": "2026-10-10T10:00:00Z", "agent": "seo-audit", "status": "ok"}\n\n')
            f.write('{"ts": "2026-10-11", "agent": "seo-audit", "status": "ok"}\n')
        code, out = cli(["--jsonl", os.path.join(SCHEMAS, "run-record.schema.json"), runs])
        check("jsonl reports failing line", code == 1 and "runs.jsonl:3" in out and "runs.jsonl:1: valid" in out, out)


def main():
    for test in (test_brand, test_other_examples, test_keywords, test_cli):
        test()
    for failure in FAILURES:
        print(f"FAIL {failure}")
    print(f"{PASSED} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
