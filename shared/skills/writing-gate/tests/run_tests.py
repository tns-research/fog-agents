#!/usr/bin/env python3
"""
run_tests.py

Regression tests for the writing gate. Standard library only. Run after any
change to scripts/lint_copy.py or to a pack:

    python3 shared/skills/writing-gate/tests/run_tests.py

Checks:
  - every pack is valid against shared/schemas/copy-rules.schema.json
  - every rule fires on each of its "bad" examples and stays silent on its "good" ones
  - bad_en.md and bad_fr.md fail the gate with the expected rule families
  - good_en.md and good_fr.md pass with 0 BLOCK
  - em dash and spaced en dash are BLOCK (tested on generated text: the repo
    forbids those characters in files)
  - language auto-detection, skipped regions (quotes, code, writing-gate off),
    project pack (banned words, disable, levels, custom rule), JSON output,
    exit codes

Exit 0 when every test passes, 1 otherwise.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO_SHARED = os.path.normpath(os.path.join(SKILL, "..", ".."))
LINT = os.path.join(SKILL, "scripts", "lint_copy.py")
SCHEMA = os.path.join(REPO_SHARED, "schemas", "copy-rules.schema.json")

sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(REPO_SHARED, "scripts"))
import lint_copy  # noqa: E402
from validate_json import validate  # noqa: E402

FAILURES = []
PASSED = 0


def check(name, condition, detail=""):
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run(args, stdin=None):
    proc = subprocess.run([sys.executable, LINT] + args, input=stdin,
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def codes_of(findings, level=None):
    return {f["code"] for f in findings if level is None or f["level"] == level}


def test_packs_schema():
    with open(SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    for lang in lint_copy.LANGS:
        path = os.path.join(lint_copy.PACKS_DIR, f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            pack = json.load(f)
        errors = validate(pack, schema)
        check(f"schema {lang}.json", not errors, "; ".join(errors[:3]))
        seen = set()
        for rule in pack["rules"]:
            check(f"{lang}.json unique code {rule['code']}", rule["code"] not in seen)
            seen.add(rule["code"])
            check(f"{lang}.json {rule['code']} has examples", rule.get("bad") and rule.get("good"))


def test_rule_examples():
    for lang in lint_copy.LANGS:
        rules, _ = lint_copy.load_rules(lang, None, None, [], [])
        for rule in rules:
            for text in rule.get("bad", []):
                hit = rule["code"] in codes_of(lint_copy.lint_text(text, [rule]))
                check(f"{lang} {rule['code']} fires on bad", hit, repr(text))
            for text in rule.get("good", []):
                hit = rule["code"] in codes_of(lint_copy.lint_text(text, [rule]))
                check(f"{lang} {rule['code']} silent on good", not hit, repr(text))


def test_fixtures():
    expected = {
        "bad_en.md": {"not-x-its-y", "not-just-but", "no-x-no-y-just-z", "buzzword", "soft-buzzword",
                      "staged-question", "fake-suspense", "length-announcement", "imagine-scene",
                      "chatbot-ritual", "trailing-participle", "grandiosity", "object-as-agent"},
        "bad_fr.md": {"correction-deux-temps", "pas-mais", "ni-ni-juste", "vrai-x", "intensificateur-creux",
                      "adverbe-creux", "question-mise-en-scene", "faux-suspense", "annonce-longueur",
                      "imaginez", "rituel", "participe-final", "grandiloquence", "objet-agent"},
    }
    for name, want in expected.items():
        code, out, err = run(["--json", os.path.join(HERE, name)])
        check(f"{name} exits 1", code == 1, f"exit {code} {err}")
        report = json.loads(out)
        entry = report["files"][0]
        check(f"{name} language", entry["lang"] == name[4:6], entry["lang"])
        missing = want - codes_of(entry["findings"], "BLOCK")
        check(f"{name} expected BLOCK codes", not missing, f"missing {sorted(missing)}")
        check(f"{name} status fail", report["status"] == "fail")
    for name in ("good_en.md", "good_fr.md"):
        code, out, err = run(["--json", os.path.join(HERE, name)])
        entry = json.loads(out)["files"][0]
        blocks = [f for f in entry["findings"] if f["level"] == "BLOCK"]
        check(f"{name} exits 0", code == 0, f"exit {code} {err}")
        check(f"{name} 0 BLOCK", not blocks, json.dumps(blocks, ensure_ascii=False)[:300])
        check(f"{name} language", entry["lang"] == name[5:7], entry["lang"])


def test_dashes():
    for lang, text in (("en", "We shipped it \u2014 finally."), ("fr", "On l'a livré \u2013 enfin.")):
        code, out, _ = run(["--json", "--lang", lang, "-"], stdin=text)
        found = codes_of(json.loads(out)["files"][0]["findings"], "BLOCK")
        check(f"{lang} dash BLOCK", code == 1 and found & {"em-dash", "spaced-en-dash"}, str(found))
    code, out, _ = run(["--json", "--lang", "en", "-"], stdin="Pages 10\u201320 hold the data.")
    check("en dash in a range passes", code == 0, out[:200])


def test_skipped_regions():
    quote = "> It's not a tool, it's a habit.\n"
    code, _, _ = run(["--lang", "en", "-"], stdin=quote)
    check("blockquote skipped by default", code == 0)
    code, _, _ = run(["--lang", "en", "--include-quotes", "-"], stdin=quote)
    check("blockquote linted with --include-quotes", code == 1)
    fenced = "Intro line.\n\n```\nIt's not a bug, it's a feature.\n```\n"
    check("code fence skipped", run(["--lang", "en", "-"], stdin=fenced)[0] == 0)
    inline = "Run `it's not X, it's Y` to see the rule.\n"
    check("inline code skipped", run(["--lang", "en", "-"], stdin=inline)[0] == 0)
    off = "<!-- writing-gate: off -->\nIt's not a tool, it's a habit.\n<!-- writing-gate: on -->\nPlain line.\n"
    check("writing-gate off region skipped", run(["--lang", "en", "-"], stdin=off)[0] == 0)
    after = off + "It's not a tool, it's a habit.\n"
    check("writing-gate on region linted", run(["--lang", "en", "-"], stdin=after)[0] == 1)
    front = "---\ntitle: It's not a tool, it's a habit\n---\nPlain line.\n"
    check("frontmatter skipped", run(["--lang", "en", "-"], stdin=front)[0] == 0)


def test_project_pack():
    with tempfile.TemporaryDirectory() as tmp:
        voice = os.path.join(tmp, "project-context", "voice")
        os.makedirs(voice)
        with open(os.path.join(voice, "rules.json"), "w", encoding="utf-8") as f:
            json.dump({
                "banned_words": ["synergize"],
                "disable": ["hollow-adverb"],
                "levels": {"crowd-claim": "BLOCK"},
                "rules": [{
                    "code": "brand-casing", "level": "BLOCK", "pattern": r"\bAcmeApp\b",
                    "message": "Write the brand as acmeapp, lowercase.",
                    "bad": ["Try AcmeApp today."], "good": ["Try acmeapp today."],
                }],
            }, f)
        with open(os.path.join(tmp, "project-context", "context.json"), "w", encoding="utf-8") as f:
            json.dump({"voice": {"banned_words": ["disrupt"]}}, f)
        with open(os.path.join(voice, "rules.json"), encoding="utf-8") as f:
            errors = validate(json.load(f), json.load(open(SCHEMA, encoding="utf-8")))
        check("project rules.json valid against schema", not errors, "; ".join(errors))

        text = "We help you synergize. Teams disrupt markets. AcmeApp is truly fast. Most founders agree.\n"
        code, out, _ = run(["--json", "--lang", "en", "--project", tmp, "-"], stdin=text)
        findings = json.loads(out)["files"][0]["findings"]
        blocks = codes_of(findings, "BLOCK")
        banned = [f["match"].lower() for f in findings if f["code"] == "banned-word"]
        check("project banned word from rules.json", "synergize" in banned, str(banned))
        check("project banned word from context.json", "disrupt" in banned, str(banned))
        check("project custom rule", "brand-casing" in blocks, str(blocks))
        check("project disable", "hollow-adverb" not in codes_of(findings), str(codes_of(findings)))
        check("project level override", "crowd-claim" in blocks, str(blocks))
        check("project pack fails gate", code == 1)

        code, out, _ = run(["--json", "--lang", "en", "-"], stdin=text)
        check("no project: banned words not applied",
              "banned-word" not in codes_of(json.loads(out)["files"][0]["findings"]))


def test_cli():
    check("unknown option exits 2", run(["--nope", "x.md"])[0] == 2)
    check("missing file exits 2", run([os.path.join(HERE, "missing.md")])[0] == 2)
    code, out, _ = run(["--list", "--lang", "fr"])
    check("--list works", code == 0 and "objet-agent" in out, out[:200])
    code, out, _ = run(["--ignore", "em-dash,spaced-en-dash", "--lang", "en", "-"], stdin="A \u2014 B.")
    check("--ignore skips codes", code == 0, out[:200])
    code, out, err = run(["--with-slopcheck", "--json", os.path.join(HERE, "good_en.md")])
    sc = json.loads(out)["files"][0]["slopcheck"]
    if not sc.get("ran"):
        check("--with-slopcheck without slopcheck keeps exit 0", code == 0, err)
        check("--with-slopcheck notes the skip", "not installed" in sc.get("note", ""), str(sc))


def main():
    for test in (test_packs_schema, test_rule_examples, test_fixtures, test_dashes,
                 test_skipped_regions, test_project_pack, test_cli):
        test()
    for failure in FAILURES:
        print(f"FAIL {failure}")
    print(f"{PASSED} passed, {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
