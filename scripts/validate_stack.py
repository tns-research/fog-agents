#!/usr/bin/env python3
"""
validate_stack.py

Repo-wide consistency checks for the Founders Growth Agent Stack.
Python 3.8+, standard library only. Run from anywhere:

    python3 scripts/validate_stack.py
    python3 scripts/validate_stack.py --private-terms /path/to/private-terms.txt

Checks:
  1. links      Every relative markdown link ([text](path) and ![alt](path))
                resolves to a file or folder in the repo, and a #anchor on a
                markdown target matches one of its headings (GitHub slugs).
  2. paths      Every backticked repo file path in markdown prose (for example
                `skills/foo/SKILL.md`, `assets/output-template.md`,
                `../../shared/handoffs.md`) resolves. Tokens holding
                placeholders (<...>, {...}, [...], YYYY) are skipped. Paths are tried relative to
                the file, the agent folder, the agent skills/ folder, and the
                repo root.
  3. layout     Every folder under agents/ has the template files:
                AGENT_*.md, README.md, config.example.json, references/README.md,
                a non-empty assets/, and at least one skills/<name>/SKILL.md.
                A scripts/ folder holding .py files also needs README.md and
                requirements.txt.
  4. frontmatter  Every AGENT_*.md and SKILL.md starts with YAML frontmatter
                that has a non-empty name and description. A SKILL.md name
                must equal its parent folder name.
  5. json       Every .json file parses. Every config.example.json is an
                object with a top-level _comment.
  6. dashes     No em dash (U+2014) or en dash (U+2013) in .md, .json, .py
                and other text files. Use a comma, colon, period or
                parentheses instead.
  7. vendor     The stack is sequencer-agnostic: the name of the cold-email
                sequencer the stack used to push to (see BANNED_VENDOR, any
                case) must not appear in any scanned file.

  8. tools      Every AGENT_*.md has a "## Tools" section and links the
                shared resolving-tools skill, and has no "## Prerequisites"
                section: external APIs are optional (see shared/tools.md).
  9. terms      Forbidden terms. Always: an equity percentage (a number and a
                percent sign followed by "equity", in English or French, or
                "equity of" followed by a percentage). Plus every term listed in a
                private terms file, one per line, matched case-insensitively
                on word boundaries ('#' starts a comment). The file defaults to
                eng/private-terms.txt (never published, eng/ is excluded) and
                can be overridden with --private-terms PATH or the
                FOG_PRIVATE_TERMS environment variable. When the file is
                absent (public clone, CI) only the built-in patterns run.
 10. pii        Published sample data names no real person: no file under
                agents/*/examples/, agents/*/tests/fixtures/ or
                agents/*/scripts/fixtures/ holds an e-mail address outside the
                reserved test domains (example.com, example.org, example.net and
                their subdomains, the .example, .test and .invalid TLDs) or a
                noreply sender, nor a linkedin.com/in/ URL whose slug does not
                say "fictive", "fictional" or "example".

Exit code 0 when every check passes, 1 otherwise. The report lists each
failure as <check> <file>:<line> <message>.

Scanned tree: the repo minus internal or generated folders listed in
EXCLUDED_DIRS (eng/ and _archive/ are private planning folders that never ship
to the public repo).
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Folders never scanned: VCS data, private planning, archives, dependencies, caches.
EXCLUDED_DIRS = {
    ".git", "eng", "_archive", ".venv", "venv", "node_modules", "__pycache__",
    "site", ".claude", ".cursor", ".codex", ".gemini", ".idea", ".vscode",
    ".trash", "dist", "build", "out", ".next",
}

# Text file types scanned for dashes and vendor strings.
TEXT_EXTENSIONS = {".md", ".json", ".py", ".sh", ".yml", ".yaml", ".txt", ".css", ".html"}

# File types a backticked token must end with to be treated as a repo path.
PATH_EXTENSIONS = (".md", ".json", ".py", ".sh", ".txt", ".css", ".html", ".yml", ".csv")

# A backticked token is only checked when it starts with one of these prefixes,
# which name folders that exist inside this repo. Tokens such as `context.json`
# or `market-signal-20260427.md` name files in the user's project and are skipped.
REPO_PATH_PREFIXES = (
    "skills/", "assets/", "references/", "scripts/", "examples/", "templates/",
    "agents/", "shared/", "docs/", "./", "../",
)

# Placeholder markers: a link or path holding any of these is a template slot.
PLACEHOLDER_MARKERS = ("<", ">", "{", "}", "[", "]", "*", "YYYY", "NN-", "...", "$")

# Spelled in two parts so this file does not trip its own check.
BANNED_VENDOR = "insta" + "ntly"

# Built-in forbidden patterns, checked in every scanned text file.
EQUITY_PCT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s?%\s*(?:d['\u2019]\s*|of\s+)?equity"
    r"|equity\s+(?:of\s+|stake\s+of\s+)?\d+(?:[.,]\d+)?\s?%",
    re.I,
)

DEFAULT_PRIVATE_TERMS = os.path.join(ROOT, "eng", "private-terms.txt")

# Sample data checked for personal data (check 10): agents/<agent>/<one of these>/...
PII_DIRS = ("examples/", "tests/fixtures/", "scripts/fixtures/")
PII_EXTENSIONS = TEXT_EXTENSIONS | {".jsonl", ".csv", ".tsv", ".js", ".xml", ".svg"}
EMAIL_RE = re.compile(r"(?<![\w.+-])([\w.+-]+)@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
RESERVED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
RESERVED_EMAIL_TLDS = (".example", ".test", ".invalid")
ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")  # logo@2x.png is not an address
LINKEDIN_IN_RE = re.compile(r"linkedin\.com/in/[^\s\"'<>),\]]*", re.I)
FICTIVE_MARKERS = ("fictive", "fictional", "example")

EM_DASH = "\u2014"
EN_DASH = "\u2013"

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


class Report:
    def __init__(self) -> None:
        self.failures: Dict[str, List[str]] = {}

    def add(self, check: str, path: str, line: Optional[int], message: str) -> None:
        rel = os.path.relpath(path, ROOT)
        where = f"{rel}:{line}" if line else rel
        self.failures.setdefault(check, []).append(f"{where}  {message}")

    def total(self) -> int:
        return sum(len(v) for v in self.failures.values())


def walk_files() -> List[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for name in sorted(filenames):
            files.append(os.path.join(dirpath, name))
    return files


def read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def agent_root_of(path: str) -> Optional[str]:
    """Return agents/<name> (or shared/) containing path, if any."""
    rel = os.path.relpath(path, ROOT).split(os.sep)
    if len(rel) >= 2 and rel[0] == "agents":
        return os.path.join(ROOT, "agents", rel[1])
    if rel and rel[0] == "shared":
        return os.path.join(ROOT, "shared")
    return None


def is_placeholder(target: str) -> bool:
    if any(m in target for m in PLACEHOLDER_MARKERS):
        return True
    # All-caps slot such as (URL) or (LINK) in output templates.
    return re.fullmatch(r"[A-Z_]+", target) is not None


def is_external(target: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target)) or target.startswith("//")


def prose_lines(text: str) -> List[Tuple[int, str]]:
    """Yield (line_number, line) for markdown lines outside fenced code blocks."""
    out = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((i, line))
    return out


def resolve_candidates(md_path: str, target: str) -> List[str]:
    base = os.path.dirname(md_path)
    cands = [os.path.normpath(os.path.join(base, target))]
    agent = agent_root_of(md_path)
    if agent:
        cands.append(os.path.normpath(os.path.join(agent, target)))
        cands.append(os.path.normpath(os.path.join(agent, "skills", target)))
    cands.append(os.path.normpath(os.path.join(ROOT, target)))
    return cands


def heading_slugs(text: str) -> set:
    """GitHub-style anchors for every markdown heading in text."""
    slugs = set()
    for _, line in prose_lines(text):
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        title = m.group(1).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        slugs.add(slug)
    return slugs


def check_links(md_path: str, text: str, report: Report) -> None:
    for lineno, line in prose_lines(text):
        stripped = INLINE_CODE_RE.sub("", line)
        for m in LINK_RE.finditer(stripped):
            target = m.group(1).strip()
            if not target or is_external(target) or is_placeholder(target):
                continue
            path_part = target.split("#", 1)[0].split("?", 1)[0]
            anchor = target.split("#", 1)[1] if "#" in target else ""
            if path_part:
                resolved = os.path.normpath(os.path.join(os.path.dirname(md_path), path_part))
                if not os.path.exists(resolved):
                    report.add("links", md_path, lineno, f"broken link -> {target}")
                    continue
            else:
                resolved = md_path
            if anchor and resolved.endswith(".md") and os.path.isfile(resolved):
                target_text = read_text(resolved) or ""
                if anchor.lower() not in heading_slugs(target_text):
                    report.add("links", md_path, lineno, f"anchor not found -> {target}")


def check_backtick_paths(md_path: str, text: str, report: Report) -> None:
    for lineno, line in prose_lines(text):
        for m in INLINE_CODE_RE.finditer(line):
            token = m.group(1).strip()
            if " " in token or is_placeholder(token) or is_external(token):
                continue
            if not token.startswith(REPO_PATH_PREFIXES):
                continue
            # Bare folder mentions (`assets/`) often name folders of the user's
            # project, so only file paths are checked.
            if not token.endswith(PATH_EXTENSIONS):
                continue
            if not any(os.path.exists(c) for c in resolve_candidates(md_path, token)):
                report.add("paths", md_path, lineno, f"referenced path not found -> {token}")


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    fields: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return None


def check_frontmatter(path: str, text: str, report: Report) -> None:
    fm = parse_frontmatter(text)
    if fm is None:
        report.add("frontmatter", path, 1, "missing or unterminated YAML frontmatter")
        return
    for key in ("name", "description"):
        if not fm.get(key):
            report.add("frontmatter", path, 1, f"frontmatter field '{key}' missing or empty")
    if os.path.basename(path) == "SKILL.md":
        folder = os.path.basename(os.path.dirname(path))
        if fm.get("name") and fm["name"] != folder:
            report.add("frontmatter", path, 1, f"name '{fm['name']}' does not match folder '{folder}'")


def check_layout(report: Report) -> None:
    agents_dir = os.path.join(ROOT, "agents")
    for name in sorted(os.listdir(agents_dir)):
        agent = os.path.join(agents_dir, name)
        if not os.path.isdir(agent) or name in EXCLUDED_DIRS:
            continue
        entries = os.listdir(agent)
        if not [e for e in entries if e.startswith("AGENT_") and e.endswith(".md")]:
            report.add("layout", agent, None, "missing AGENT_<NAME>.md")
        for required in ("README.md", "config.example.json", os.path.join("references", "README.md")):
            if not os.path.isfile(os.path.join(agent, required)):
                report.add("layout", agent, None, f"missing {required}")
        assets = os.path.join(agent, "assets")
        if not os.path.isdir(assets) or not os.listdir(assets):
            report.add("layout", agent, None, "missing or empty assets/")
        skills = os.path.join(agent, "skills")
        has_skill = os.path.isdir(skills) and any(
            os.path.isfile(os.path.join(skills, s, "SKILL.md")) for s in os.listdir(skills)
        )
        if not has_skill:
            report.add("layout", agent, None, "missing skills/<name>/SKILL.md")
        scripts = os.path.join(agent, "scripts")
        if os.path.isdir(scripts) and any(f.endswith(".py") for f in os.listdir(scripts)):
            for required in ("README.md", "requirements.txt"):
                if not os.path.isfile(os.path.join(scripts, required)):
                    report.add("layout", scripts, None, f"scripts/ has .py files but no {required}")


def check_tools(path: str, text: str, report: Report) -> None:
    if not re.search(r"^## Tools\b", text, re.M):
        report.add("tools", path, None, 'missing "## Tools" section (see shared/tools.md)')
    if "resolving-tools" not in text:
        report.add("tools", path, None, "no link to shared/skills/resolving-tools/SKILL.md")
    match = re.search(r"^## Prerequisites\b", text, re.M)
    if match:
        line = text.count("\n", 0, match.start()) + 1
        report.add("tools", path, line, '"## Prerequisites" makes tools look mandatory, use "## Tools"')


def check_json(path: str, text: str, report: Report) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        report.add("json", path, e.lineno, f"invalid JSON: {e.msg}")
        return
    if os.path.basename(path) == "config.example.json":
        if not isinstance(data, dict) or "_comment" not in data:
            report.add("json", path, 1, "config.example.json must be an object with a _comment field")


def check_dashes_and_vendor(path: str, text: str, report: Report) -> None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        if EM_DASH in line or EN_DASH in line:
            kind = "em dash" if EM_DASH in line else "en dash"
            report.add("dashes", path, lineno, f"{kind} found: {line.strip()[:90]}")
        if BANNED_VENDOR in line.lower():
            report.add("vendor", path, lineno, f"'{BANNED_VENDOR}' found: {line.strip()[:90]}")


def load_private_terms(path: str) -> List[Tuple[str, "re.Pattern[str]"]]:
    """Read one term per line; blank lines and '#' comments are skipped."""
    if not path or not os.path.isfile(path):
        return []
    terms = []
    for raw in (read_text(path) or "").splitlines():
        term = raw.split("#", 1)[0].strip()
        if term:
            pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)
            terms.append((term, pattern))
    return terms


def check_terms(path: str, text: str, terms: List[Tuple[str, "re.Pattern[str]"]], report: Report) -> None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = EQUITY_PCT_RE.search(line)
        if m:
            report.add("terms", path, lineno, f"equity percentage found: '{m.group(0)}'")
        for term, pattern in terms:
            if pattern.search(line):
                report.add("terms", path, lineno, f"private term '{term}' found")


def is_sample_data(path: str) -> bool:
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    parts = rel.split("/", 2)
    return len(parts) == 3 and parts[0] == "agents" and parts[2].startswith(PII_DIRS)


def check_pii(path: str, text: str, report: Report) -> None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in EMAIL_RE.finditer(line):
            local, domain = m.group(1).lower(), m.group(2).lower()
            reserved = any(domain == d or domain.endswith("." + d) for d in RESERVED_EMAIL_DOMAINS) \
                or domain.endswith(RESERVED_EMAIL_TLDS) or local.startswith(("noreply", "no-reply"))
            if not reserved and not domain.endswith(ASSET_SUFFIXES):
                report.add("pii", path, lineno, f"e-mail address outside the reserved test domains: {m.group(0)}")
        for m in LINKEDIN_IN_RE.finditer(line):
            if not any(w in m.group(0).lower() for w in FICTIVE_MARKERS):
                report.add("pii", path, lineno, f"LinkedIn profile URL not marked fictive or example: {m.group(0)[:80]}")


def private_terms_path(argv: List[str]) -> str:
    if "--private-terms" in argv:
        i = argv.index("--private-terms")
        if i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get("FOG_PRIVATE_TERMS") or DEFAULT_PRIVATE_TERMS


def main() -> int:
    report = Report()
    terms_file = private_terms_path(sys.argv[1:])
    terms = load_private_terms(terms_file)
    files = walk_files()
    scanned = 0
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext in PII_EXTENSIONS and is_sample_data(path):
            text = read_text(path)
            if text is not None:
                check_pii(path, text, report)
        if ext not in TEXT_EXTENSIONS:
            continue
        text = read_text(path)
        if text is None:
            continue
        scanned += 1
        check_dashes_and_vendor(path, text, report)
        check_terms(path, text, terms, report)
        if ext == ".md":
            posix = path.replace(os.sep, "/")
            if not ("/tests/fixtures/" in posix and "/repo/" in posix):
                check_links(path, text, report)  # a fixture site repository links to site routes, not to repo files
            check_backtick_paths(path, text, report)
            base = os.path.basename(path)
            if base == "SKILL.md" or (base.startswith("AGENT_") and base.endswith(".md")):
                check_frontmatter(path, text, report)
            if base.startswith("AGENT_") and base.endswith(".md") and "/agents/" in path.replace(os.sep, "/"):
                check_tools(path, text, report)
        elif ext == ".json":
            check_json(path, text, report)
    check_layout(report)

    checks = ["links", "paths", "layout", "frontmatter", "json", "dashes", "vendor", "tools", "terms", "pii"]
    print(f"validate_stack: scanned {scanned} text files under {ROOT}")
    if terms:
        print(f"  private terms: {len(terms)} loaded from {terms_file}")
    else:
        print("  private terms: none loaded (built-in equity check only)")
    for check in checks:
        items = report.failures.get(check, [])
        status = "ok" if not items else f"FAIL ({len(items)})"
        print(f"  [{status}] {check}")
        for item in items:
            print(f"      {item}")
    if report.total():
        print(f"\n{report.total()} problem(s) found. Fix them and re-run.")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
