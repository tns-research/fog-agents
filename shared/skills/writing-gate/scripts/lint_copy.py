#!/usr/bin/env python3
"""
lint_copy.py

Mechanical writing gate for every agent that writes copy. Standard library
only, Python 3.8+. It flags machine-writing tics with regex rules read from JSON
packs (shared packs in ../packs/, plus an optional project pack), reports each
hit with its line, its rule code, its level and a one-line fix, and exits 1 when
at least one BLOCK remains.

Usage:
    python3 lint_copy.py FILE [FILE ...]            # language detected per file
    python3 lint_copy.py --lang fr FILE
    cat draft.md | python3 lint_copy.py -
    python3 lint_copy.py --project <your-projects-root>/<project> FILE
    python3 lint_copy.py --rules path/to/rules.json --pack path/to/extra.json FILE
    python3 lint_copy.py --json FILE                # machine-readable output
    python3 lint_copy.py --with-slopcheck FILE      # also run `slopcheck` if installed
    python3 lint_copy.py --list [--lang en]         # print the loaded rules

Options:
    --lang auto|en|fr     Language of the text. auto (default) counts function words.
    --project DIR         Project folder. Loads DIR/project-context/voice/rules.json
                          and voice.banned_words from DIR/project-context/context.json
                          when they exist.
    --rules PATH          Project pack at an explicit path (same format as rules.json).
    --pack PATH           Extra pack, repeatable (for example an agent-specific pack).
    --ignore CODES        Comma-separated rule codes to skip for this run.
    --include-quotes      Also lint markdown blockquotes. By default lines starting
                          with '>' are skipped: in this stack they hold verbatim
                          quotes, which are never rewritten.
    --json                Print one JSON object instead of the text report.
    --with-slopcheck      Run `slopcheck check <file>` too when that command is on
                          PATH; its BLOCKs also fail the gate. Skipped with a note
                          when it is not installed.
    --list                Print the rules that would run, then exit.

Skipped regions: YAML frontmatter, fenced code blocks, inline code, HTML
comments, URLs, blockquotes (see --include-quotes), and anything between
<!-- writing-gate: off --> and <!-- writing-gate: on -->.

Exit codes: 0 no BLOCK, 1 at least one BLOCK, 2 usage error or unreadable pack.
Pack format: shared/schemas/copy-rules.schema.json.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PACKS_DIR = os.path.normpath(os.path.join(HERE, "..", "packs"))
LANGS = ("en", "fr")

FR_WORDS = {
    "le", "la", "les", "des", "une", "est", "et", "pour", "dans", "que", "qui",
    "pas", "sur", "avec", "vous", "nous", "ce", "cette", "sont", "du", "au", "aux",
    "mais", "ou", "on", "ne", "plus", "par", "leur", "votre", "notre",
}
EN_WORDS = {
    "the", "and", "is", "are", "for", "with", "that", "this", "you", "your", "we",
    "our", "of", "to", "in", "it", "not", "on", "be", "was", "have", "has", "but",
    "or", "they", "their", "what", "from", "will", "can",
}


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- packs

def _read_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise UsageError(f"cannot read {path}: {e}")


def _flags(spec: str) -> int:
    value = 0
    for ch in spec or "":
        value |= {"i": re.I, "m": re.M, "x": re.X}.get(ch, 0)
    return value


def _compile_rule(rule: Dict[str, Any], source: str) -> Dict[str, Any]:
    for key in ("code", "level", "pattern", "message"):
        if key not in rule:
            raise UsageError(f"{source}: rule without '{key}': {rule}")
    if rule["level"] not in ("BLOCK", "WARN"):
        raise UsageError(f"{source}: rule {rule['code']} has level {rule['level']}")
    try:
        regex = re.compile(rule["pattern"], _flags(rule.get("flags", "")))
    except re.error as e:
        raise UsageError(f"{source}: rule {rule['code']} has a bad pattern: {e}")
    out = dict(rule)
    out["regex"] = regex
    out["source"] = source
    return out


def banned_word_rule(words: List[str], source: str) -> Optional[Dict[str, Any]]:
    words = [w.strip() for w in words if isinstance(w, str) and w.strip()]
    if not words:
        return None
    alternation = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    return _compile_rule({
        "code": "banned-word",
        "family": "project-voice",
        "level": "BLOCK",
        "pattern": r"(?<!\w)(?:" + alternation + r")(?!\w)",
        "flags": "i",
        "message": "The founder banned this word: rewrite the sentence without it.",
    }, source)


def load_rules(lang: str, project: Optional[str], rules_path: Optional[str],
               extra_packs: List[str], ignore: List[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Return (compiled rules, list of loaded sources) for one language."""
    sources: List[str] = []
    rules: List[Dict[str, Any]] = []

    shared = os.path.join(PACKS_DIR, f"{lang}.json")
    pack = _read_json(shared)
    sources.append(shared)
    rules.extend(_compile_rule(r, shared) for r in pack.get("rules", []))

    for path in extra_packs:
        data = _read_json(path)
        if data.get("language", "any") in (lang, "any"):
            sources.append(path)
            rules.extend(_compile_rule(r, path) for r in data.get("rules", []))

    project_packs: List[Tuple[str, Dict[str, Any]]] = []
    banned: List[str] = []
    if project:
        voice_rules = os.path.join(project, "project-context", "voice", "rules.json")
        if os.path.isfile(voice_rules):
            project_packs.append((voice_rules, _read_json(voice_rules)))
        context = os.path.join(project, "project-context", "context.json")
        if os.path.isfile(context):
            try:
                ctx = _read_json(context)
                words = ((ctx.get("voice") or {}).get("banned_words")) or []
                if words:
                    banned.extend(words)
                    sources.append(f"{context} (voice.banned_words)")
            except UsageError:
                pass  # a broken context.json is reported by its own loader, never here
    if rules_path:
        project_packs.append((rules_path, _read_json(rules_path)))

    disabled = set(ignore)
    levels: Dict[str, str] = {}
    for path, data in project_packs:
        if data.get("language", "any") not in (lang, "any"):
            continue
        sources.append(path)
        banned.extend(data.get("banned_words", []))
        disabled.update(data.get("disable", []))
        levels.update(data.get("levels", {}))
        rules.extend(_compile_rule(r, path) for r in data.get("rules", []))

    rule = banned_word_rule(banned, "project banned words")
    if rule:
        rules.append(rule)

    final = []
    for r in rules:
        if r["code"] in disabled:
            continue
        if r["code"] in levels:
            r["level"] = levels[r["code"]]
        final.append(r)
    return final, sources


# ---------------------------------------------------------------- text

def _blank(match: "re.Match[str]") -> str:
    """Replace a region with spaces, keeping newlines so offsets and lines stay put."""
    return re.sub(r"[^\n]", " ", match.group(0))


def clean_text(text: str, include_quotes: bool) -> str:
    text = text.replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            stop = end + 4
            text = re.sub(r"[^\n]", " ", text[:stop]) + text[stop:]
    text = re.sub(r"<!--\s*writing-gate:\s*off\s*-->.*?(?:<!--\s*writing-gate:\s*on\s*-->|\Z)",
                  _blank, text, flags=re.S | re.I)
    text = re.sub(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", _blank, text, flags=re.S | re.M)
    text = re.sub(r"<!--.*?-->", _blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", _blank, text)
    text = re.sub(r"\]\([^)\s]+\)", lambda m: "]" + " " * (len(m.group(0)) - 1), text)
    text = re.sub(r"https?://\S+", _blank, text)
    if not include_quotes:
        text = re.sub(r"^[ \t]*>[^\n]*", _blank, text, flags=re.M)
    return text


def detect_lang(text: str) -> str:
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", text.lower())
    fr = sum(1 for w in words if w in FR_WORDS)
    en = sum(1 for w in words if w in EN_WORDS)
    return "fr" if fr > en else "en"


def line_col(text: str, offset: int) -> Tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    col = offset - (text.rfind("\n", 0, offset) + 1) + 1
    return line, col


def lint_text(raw: str, rules: List[Dict[str, Any]], include_quotes: bool = False) -> List[Dict[str, Any]]:
    text = clean_text(raw, include_quotes)
    findings: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for rule in rules:
        for m in rule["regex"].finditer(text):
            if not m.group(0).strip():
                continue
            line, col = line_col(text, m.start())
            excerpt = " ".join(m.group(0).split())
            if len(excerpt) > 80:
                excerpt = excerpt[:77] + "..."
            findings.append({
                "line": line, "col": col, "level": rule["level"], "code": rule["code"],
                "family": rule.get("family", ""), "match": excerpt,
                "message": rule["message"], "escalated": False,
            })
            counts[rule["code"]] = counts.get(rule["code"], 0) + 1
    by_code = {r["code"]: r for r in rules}
    for f in findings:
        rule = by_code.get(f["code"], {})
        threshold = rule.get("escalate_at")
        if f["level"] == "WARN" and threshold and counts[f["code"]] >= threshold:
            f["level"] = "BLOCK"
            f["escalated"] = True
            f["message"] += f" (escalated: {counts[f['code']]} hits in this text, threshold {threshold})"
    findings.sort(key=lambda f: (f["line"], f["col"], f["code"]))
    return findings


# ---------------------------------------------------------------- slopcheck

def run_slopcheck(path: str, raw: str, want_json: bool) -> Dict[str, Any]:
    exe = shutil.which("slopcheck")
    if not exe:
        return {"ran": False, "note": "slopcheck is not installed; skipped"}
    cmd = [exe, "check", "--format", "json" if want_json else "text", path]
    try:
        proc = subprocess.run(cmd, input=raw if path == "-" else None, capture_output=True,
                              text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ran": False, "note": f"slopcheck failed to run: {e}"}
    output: Any = proc.stdout
    if want_json:
        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError:
            pass
    return {"ran": True, "exit": proc.returncode, "output": output, "stderr": proc.stderr.strip()}


# ---------------------------------------------------------------- cli

def parse_args(argv: List[str]) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "lang": "auto", "project": None, "rules": None, "packs": [], "ignore": [],
        "include_quotes": False, "json": False, "slopcheck": False, "list": False, "files": [],
    }
    it = iter(argv)
    for arg in it:
        if arg in ("-h", "--help"):
            raise UsageError("help")
        elif arg == "--lang":
            opts["lang"] = next(it, "")
            if opts["lang"] not in ("auto",) + LANGS:
                raise UsageError("--lang takes auto, en or fr")
        elif arg in ("--project", "--rules", "--pack", "--ignore"):
            value = next(it, None)
            if value is None:
                raise UsageError(f"{arg} needs a value")
            if arg == "--pack":
                opts["packs"].append(value)
            elif arg == "--ignore":
                opts["ignore"].extend(c.strip() for c in value.split(",") if c.strip())
            else:
                opts[arg[2:]] = value
        elif arg == "--include-quotes":
            opts["include_quotes"] = True
        elif arg == "--json":
            opts["json"] = True
        elif arg == "--with-slopcheck":
            opts["slopcheck"] = True
        elif arg == "--list":
            opts["list"] = True
        elif arg.startswith("--"):
            raise UsageError(f"unknown option {arg}")
        else:
            opts["files"].append(arg)
    if not opts["files"] and not opts["list"]:
        raise UsageError("give at least one file, or - for stdin")
    return opts


def main(argv: List[str]) -> int:
    try:
        opts = parse_args(argv)
    except UsageError as e:
        print(__doc__.strip().split("Skipped regions:")[0].rstrip(), file=sys.stderr)
        if str(e) != "help":
            print(f"\nerror: {e}", file=sys.stderr)
        return 0 if str(e) == "help" else 2

    try:
        if opts["list"]:
            langs = LANGS if opts["lang"] == "auto" else (opts["lang"],)
            for lang in langs:
                rules, sources = load_rules(lang, opts["project"], opts["rules"], opts["packs"], opts["ignore"])
                print(f"[{lang}] {len(rules)} rules from: {', '.join(sources)}")
                for r in rules:
                    esc = f", BLOCK at {r['escalate_at']}" if r.get("escalate_at") else ""
                    print(f"  {r['level']:<5} {r['code']:<24} {r.get('family', '')}{esc}")
            return 0

        report: Dict[str, Any] = {"files": [], "status": "pass"}
        exit_code = 0
        for path in opts["files"]:
            if path == "-":
                raw = sys.stdin.read()
            else:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw = f.read()
                except (OSError, UnicodeDecodeError) as e:
                    raise UsageError(f"cannot read {path}: {e}")
            lang = opts["lang"] if opts["lang"] != "auto" else detect_lang(clean_text(raw, False))
            rules, sources = load_rules(lang, opts["project"], opts["rules"], opts["packs"], opts["ignore"])
            findings = lint_text(raw, rules, opts["include_quotes"])
            blocks = sum(1 for f in findings if f["level"] == "BLOCK")
            warns = len(findings) - blocks
            entry: Dict[str, Any] = {
                "path": path, "lang": lang, "packs": sources,
                "counts": {"BLOCK": blocks, "WARN": warns}, "findings": findings,
            }
            if opts["slopcheck"]:
                entry["slopcheck"] = run_slopcheck(path, raw, opts["json"])
                if entry["slopcheck"].get("ran") and entry["slopcheck"].get("exit") == 1:
                    blocks += 1  # slopcheck exits 1 on BLOCK
            if blocks:
                exit_code = 1
                report["status"] = "fail"
            report["files"].append(entry)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if opts["json"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return exit_code

    for entry in report["files"]:
        c = entry["counts"]
        print(f"{entry['path']} [{entry['lang']}]: {c['BLOCK']} BLOCK, {c['WARN']} WARN")
        for f in entry["findings"]:
            print(f"  {entry['path']}:{f['line']}:{f['col']}  {f['level']:<5} {f['code']}  \"{f['match']}\"")
            print(f"      fix: {f['message']}")
        sc = entry.get("slopcheck")
        if sc:
            if not sc.get("ran"):
                print(f"  slopcheck: {sc['note']}")
            else:
                print(f"  slopcheck (exit {sc['exit']}):")
                for line in str(sc["output"]).rstrip().splitlines():
                    print(f"    {line}")
    if exit_code:
        print("\nGate: FAIL. Fix every BLOCK in the copy (never in the rules), then re-run.")
    else:
        print("\nGate: PASS (0 BLOCK). Read every WARN: fix it or keep it when the sentence carries a fact.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
