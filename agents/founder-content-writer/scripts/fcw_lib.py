"""fcw_lib.py: shared helpers of the founder-content-writer scripts (no CLI).

Paths, JSON, word-for-word matching, number and name detection, project files.
Standard library only, Python 3.9+. The network limits and the writing gate are
never copied here: `publisher()` loads content-publisher's own scripts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Pattern, Set, Tuple

sys.dont_write_bytecode = True  # keep the agent folders free of __pycache__

SCRIPTS = Path(__file__).resolve().parent
AGENT = SCRIPTS.parent
REPO = AGENT.parent.parent
ASSETS = AGENT / "assets"
AGENT_NAME = "founder-content-writer"

SPEC_SCHEMA = ASSETS / "posts-spec.schema.json"
MANIFEST_SCHEMA = ASSETS / "sources-manifest.schema.json"
PAST_SCHEMA = ASSETS / "past-post.schema.json"
VOICE_DEFAULTS = ASSETS / "voice-defaults.json"
RUBRIC = ASSETS / "review-rubric.md"
HARD_RULES = ASSETS / "hard-rules.md"

PUBLISHER_SCRIPTS = REPO / "agents" / "content-publisher" / "scripts"
PUBLISHER_SPEC_SCHEMA = REPO / "agents" / "content-publisher" / "assets" / "post-spec.schema.json"
SIDECAR_VALIDATOR = REPO / "agents" / "market-signal" / "scripts" / "validate_sidecar.py"
VOICE_SCHEMA = REPO / "agents" / "project-context" / "assets" / "voice-schema.json"
SHARED_VALIDATOR = REPO / "shared" / "scripts" / "validate_json.py"
RUN_RECORD_SCHEMA = REPO / "shared" / "schemas" / "run-record.schema.json"
COPY_RULES_SCHEMA = REPO / "shared" / "schemas" / "copy-rules.schema.json"
FRESH_EYES_SKILL = REPO / "shared" / "skills" / "reviewing-with-fresh-eyes" / "SKILL.md"
LINT_COPY = REPO / "shared" / "skills" / "writing-gate" / "scripts" / "lint_copy.py"

EXIT_OK = 0
EXIT_CHECK = 1   # a check failed, a command was refused on the content
EXIT_USAGE = 2   # bad arguments, unreadable or invalid file

MIN_PASSAGE_WORDS = 5  # a shorter passage proves nothing: it would match almost any text


class UsageError(Exception):
    """Bad arguments or an unreadable file (exit 2)."""


# ------------------------------------------------------------------ json

def read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UsageError(f"file not found: {path}")
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"{path}: unreadable ({e})")
    except json.JSONDecodeError as e:
        raise UsageError(f"{path}: not valid JSON (line {e.lineno}: {e.msg})")


def write_json_atomic(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def schema_errors(instance: Any, schema_path: Path) -> List[str]:
    """Validate with the stack's stdlib validator. Returns [] when it is absent
    (the agent copied without shared/): the script checks that follow still run."""
    if not SHARED_VALIDATOR.exists():
        return []
    sys.path.insert(0, str(SHARED_VALIDATOR.parent))
    try:
        from validate_json import validate  # type: ignore
    finally:
        sys.path.pop(0)
    return validate(instance, read_json(schema_path))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ content-publisher

def publisher() -> Tuple[Any, Any]:
    """content-publisher's own variants.py and common.py, or a usage error.
    Limits and link placement are read from there, never forked."""
    if not (PUBLISHER_SCRIPTS / "variants.py").is_file():
        raise UsageError(f"{PUBLISHER_SCRIPTS / 'variants.py'} not found: this agent reads the network limits and the "
                         "link rules of content-publisher. Copy agents/content-publisher next to it.")
    sys.path.insert(0, str(PUBLISHER_SCRIPTS))
    try:
        import common as pub_common  # type: ignore
        import variants as pub_variants  # type: ignore
    finally:
        sys.path.pop(0)
    return pub_variants, pub_common


def language_detector() -> Optional[Any]:
    """The writing gate's own language detection, or None without shared/."""
    if not LINT_COPY.is_file():
        return None
    sys.path.insert(0, str(LINT_COPY.parent))
    try:
        import lint_copy  # type: ignore
    finally:
        sys.path.pop(0)
    return lambda text: lint_copy.detect_lang(lint_copy.clean_text(text, False))


def compile_posts(spec: Dict[str, Any], source_path: str = "") -> Dict[str, Any]:
    """The posts.json content-publisher accepts: its post spec, schema 1.0.
    Nothing but the published fields leaves the batch spec."""
    posts = []
    for p in spec["posts"]:
        post: Dict[str, Any] = {"ref": p["ref"], "kind": "text", "language": spec["language"],
                                "source": {"agent": AGENT_NAME}, "link": p.get("link"),
                                "networks": list(p["networks"]), "variants": {}}
        if source_path:
            post["source"]["path"] = source_path
        if p.get("link_note"):
            post["link_note"] = p["link_note"]
        if p.get("target_slot"):
            post["target_slot"] = p["target_slot"]
        for net, var in (p.get("variants") or {}).items():
            post["variants"][net] = {k: v for k, v in var.items() if k in ("text", "first_comment")}
        posts.append(post)
    return {"schema_version": "1.0", "project": spec["project"], "posts": posts}


# ------------------------------------------------------------------ word for word

_SINGLE = "['’‘]"
_DOUBLE = "[\"“”]"


def flex_re(text: str, ignore_case: bool = False) -> Pattern[str]:
    """A regex that finds `text` word for word. Accepted differences, the same
    as market-signal's verify_quotes.py: whitespace runs, curly or straight
    quote marks of the same kind, Unicode composition. Nothing else."""
    parts = []
    for word in unicodedata.normalize("NFC", text).split():
        esc = "".join(_SINGLE if c in "'’‘" else _DOUBLE if c in '"“”' else re.escape(c) for c in word)
        parts.append(esc)
    return re.compile(r"\s+".join(parts), re.I if ignore_case else 0)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def word_count(text: str) -> int:
    return len(text.split())


ELISION_RE = re.compile(r"\.\.\.|…|\[\s*\.\.\.\s*\]|\[\s*…\s*\]")


def find_passage(source_text: str, passage: str) -> Tuple[str, Optional[int]]:
    """(status, line). status: found, case-changed, elided, not-found."""
    source = nfc(source_text)
    m = flex_re(passage).search(source)
    if m:
        return "found", source.count("\n", 0, m.start()) + 1
    if ELISION_RE.search(passage):
        return "elided", None
    m = flex_re(passage, ignore_case=True).search(source)
    if m:
        return "case-changed", source.count("\n", 0, m.start()) + 1
    return "not-found", None


# ------------------------------------------------------------------ words

STOP = {
    "about", "after", "again", "also", "because", "been", "before", "being", "between", "both", "could", "does", "doing",
    "down", "each", "even", "every", "from", "have", "having", "here", "into", "just", "like", "more", "most", "much",
    "only", "other", "over", "same", "should", "some", "still", "such", "than", "that", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "under", "very", "want", "well", "were", "what", "when", "where", "which",
    "while", "will", "with", "would", "your", "yours", "ours", "avec", "dans", "elle", "elles", "encore", "entre", "mais",
    "même", "nous", "pour", "quand", "quel", "quelle", "sans", "sont", "sous", "tout", "tous", "toute", "toutes", "très",
    "vous", "votre", "leur", "leurs", "cette", "ces", "ceux", "comme", "alors", "aussi", "donc", "avoir", "être", "fait",
    "faire", "peut", "plus", "moins", "ainsi",
}


def fold(text: str) -> str:
    """Lowercase without accents."""
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def words_of(text: str) -> List[str]:
    return re.findall(r"[^\W\d_]+", text or "")


def folded_words(text: str) -> List[str]:
    return re.findall(r"[^\W_]+", fold(text))


def stems(text: str) -> Set[str]:
    """Content words cut to five letters: enough to match a plural or a verb
    ending in English and French without a stemmer."""
    out = set()
    for w in words_of(text):
        if len(w) >= 4 and w.lower() not in STOP:
            out.add(fold(w)[:5])
    return out


def overlap(part: str, whole: str) -> float:
    """Share of the content words of `part` found in `whole`."""
    a = stems(part)
    return len(a & stems(whole)) / len(a) if a else 1.0


def jaccard(a: str, b: str) -> float:
    x, y = stems(a), stems(b)
    return len(x & y) / len(x | y) if x | y else 0.0


# ------------------------------------------------------------------ numbers

NUM_RE = re.compile(r"(?<![\w.,])\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+(?:[.,]\d+)?|(?<![\w.,])\d+(?:[.,]\d+)?")
ENUM_RE = re.compile(r"^\s*\d{1,2}[.)/](?=\s|$)")
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")

NUM_WORDS = {
    "en": {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
           "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
           "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "hundreds": 100, "thousand": 1000, "thousands": 1000,
           "million": 1000000, "millions": 1000000, "billion": 1000000000, "billions": 1000000000, "dozen": 12, "dozens": 12,
           "half": "half", "double": "double", "doubled": "double", "triple": "triple", "tripled": "triple"},
    "fr": {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
           "onze": 11, "douze": 12, "quinze": 15, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
           "cent": 100, "cents": 100, "mille": 1000, "million": 1000000, "millions": 1000000, "milliard": 1000000000,
           "milliards": 1000000000, "dizaine": 10, "dizaines": 10, "centaine": 100, "centaines": 100, "millier": 1000,
           "milliers": 1000, "moitié": "half", "double": "double", "doublé": "double", "triple": "triple", "triplé": "triple"},
}
# "both of them" in French, the one common idiom built on a number word.
FR_BOTH_RE = re.compile(r"\b(?:tous|toutes)\s+les\s+deux\b", re.I)


UNIT_AFTER_RE = re.compile(r"[ \u00a0\u202f]?(%|percent\b|pour cent\b|€|\$|£|x\b|k\b)", re.I)
UNIT_BEFORE_RE = re.compile(r"([$€£])$")
UNIT_NAMES = {"percent": "%", "pour cent": "%"}


class Num(NamedTuple):
    raw: str
    start: int
    end: int
    value: str
    is_word: bool


def number_tokens(text: str, lang: str) -> List[Num]:
    """Digits and number words of a text, with a comparable value: separators
    removed ('1 200', '1,200' and '1200' are the same number)."""
    out: List[Num] = []
    for m in NUM_RE.finditer(text or ""):
        # The unit is part of the number: 40 workshops is not 40 %.
        after = UNIT_AFTER_RE.match(text, m.end())
        before = UNIT_BEFORE_RE.search(text[:m.start()])
        unit = (after.group(1) if after else "") or (before.group(1) if before else "")
        unit = UNIT_NAMES.get(unit.lower(), unit.lower())
        end = after.end() if after else m.end()
        out.append(Num(text[m.start():end], m.start(), end, re.sub(r"[ \u00a0\u202f.,]", "", m.group(0)) + unit, False))
    words = NUM_WORDS.get(lang) or {**NUM_WORDS["en"], **NUM_WORDS["fr"]}
    skip = [m.span() for m in FR_BOTH_RE.finditer(text or "")] if lang == "fr" else []
    for m in re.finditer(r"[^\W\d_]+", text or ""):
        v = words.get(m.group(0).lower())
        if v is None or any(a <= m.start() < b for a, b in skip):
            continue
        out.append(Num(m.group(0), m.start(), m.end(), str(v), True))
    return sorted(out, key=lambda n: n.start)


def enumeration_spans(text: str) -> List[Tuple[int, int]]:
    """List markers at the start of a line ('1.', '2)', '3/'): structure, not a claim."""
    spans, pos = [], 0
    for line in (text or "").split("\n"):
        m = ENUM_RE.match(line)
        if m:
            spans.append((pos, pos + m.end()))
        pos += len(line) + 1
    return spans


def number_values(text: str) -> Set[str]:
    """Every number of a text in any language: what a claim may restate."""
    out = {n.value for n in number_tokens(text, "en")}
    out |= {n.value for n in number_tokens(text, "fr")}
    return out


LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•→▪✓✅❌]|\d{1,2}[.)/])\s+\S", re.M)


def list_items(text: str) -> int:
    return len(LIST_ITEM_RE.findall(text or ""))


# ------------------------------------------------------------------ project files

def project_paths(project: Optional[str]) -> Dict[str, Optional[Path]]:
    if not project:
        return {k: None for k in ("context", "voice", "voice_rules", "decisions", "posts", "runs", "queue")}
    root = Path(project)
    ctx = root / "project-context"
    return {"context": ctx / "context.json", "voice": ctx / "voice" / "voice.json", "voice_rules": ctx / "voice" / "rules.json",
            "decisions": ctx / "memory" / "decisions.md", "posts": ctx / "memory" / "posts.jsonl",
            "runs": ctx / "memory" / "runs.jsonl", "queue": root / "content-publisher" / "queue.json"}


def read_optional_json(path: Optional[Path]) -> Tuple[Optional[Any], Optional[str]]:
    """(data, problem). A missing file is (None, None), a broken one (None, reason)."""
    if not path or not path.is_file():
        return None, None
    try:
        return read_json(path), None
    except UsageError as e:
        return None, str(e)


def read_jsonl(path: Optional[Path]) -> Tuple[List[Dict[str, Any]], List[int]]:
    """(rows, numbers of the broken lines). A missing file is ([], [])."""
    rows: List[Dict[str, Any]] = []
    broken: List[int] = []
    if not path or not path.is_file():
        return rows, broken
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            broken.append(i)
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            broken.append(i)
    return rows, broken


def active_decisions(path: Optional[Path]) -> List[Dict[str, str]]:
    """Entries of memory/decisions.md with their id, status and enforced-by value.
    Reads what parses; a malformed file gives fewer entries, never an error."""
    if not path or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.split("## Superseded", 1)[0]
    out = []
    for chunk in re.split(r"^### ", text, flags=re.M)[1:]:
        head = chunk.split("\n", 1)[0]
        m = re.match(r"(D-\d{8}-\d+)", head)
        if not m:
            continue
        status = re.search(r"^- Status:\s*(.+)$", chunk, re.M)
        enforced = re.search(r"^- Enforced by:\s*(.+)$", chunk, re.M)
        rule = re.search(r"^- Rule:\s*(.+)$", chunk, re.M)
        out.append({"id": m.group(1), "status": (status.group(1).strip() if status else "active"),
                    "enforced_by": (enforced.group(1).strip() if enforced else ""),
                    "rule": (rule.group(1).strip() if rule else head)})
    return out


def enforced_values(decisions: Iterable[Dict[str, str]], key: str, status: str = "active") -> List[Tuple[str, str]]:
    """(value, decision id) for entries enforced by 'founder-content-writer <key>:<value>'."""
    out = []
    for d in decisions:
        if not d["status"].startswith(status):
            continue
        for m in re.finditer(AGENT_NAME + r"\s+" + re.escape(key) + r":([a-z_]+)", d["enforced_by"]):
            out.append((m.group(1), d["id"]))
    return out


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def opening_words(text: str, limit: int = 25) -> List[str]:
    return folded_words(first_line(text))[:limit]


def relative_to_project(path: Path, project: Optional[str]) -> str:
    """A path as the founder's project sees it. Never an absolute path: without
    a project folder it reads as the standard location of the batch."""
    path = Path(path).resolve()
    if project:
        try:
            return Path(os.path.relpath(path, Path(project).resolve())).as_posix()
        except ValueError:
            pass
    return f"{AGENT_NAME}/{path.parent.name}/{path.name}"
