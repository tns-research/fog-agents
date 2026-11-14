#!/usr/bin/env python3
"""ingest_docs.py: read a founder's deck or notes, page by page, so the
context Q&A asks fewer questions, and check every proof the model draws from it.

Three commands, in workflow order:

  extract   copies each document into <project-context>/docs/ and writes the
            text of every page to docs/<file>.pages.json. PDF: poppler's
            pdftotext when installed, else pypdf when importable, else exit 3
            with the install line. .md and .txt: one page, or one per form
            feed. Nothing is sent anywhere.
  check     reads the candidates the model wrote (doc-candidates.json, schema
            assets/doc-candidates.schema.json): proposed context.json fields
            with the excerpt they rest on, and proof candidates with source
            "docs/<file>#p<N>". A proof candidate whose claim is not on the cited
            page word for word (numbers included) is refused, as is a field whose
            excerpt is not on its page, a page that does not exist or a document
            changed since extract. Also reports, per candidate, whether
            shared/scripts/proof.py would let a copy use it today.
  apply     after the founder's yes: writes only the approved candidates
            (--approve ids, --approve-fields paths) into a context JSON (default
            brand-debug/context-draft.json; context.json itself is written at the
            checkpoint). Runs check first and writes nothing when an approved
            candidate fails.

Usage:
  python3 ingest_docs.py extract --out <project-context> FILE [FILE ...] [--extractor auto|pdftotext|pypdf]
  python3 ingest_docs.py check --out <project-context> CANDIDATES.json [--json]
  python3 ingest_docs.py apply --out <project-context> CANDIDATES.json --approve ID[,ID] [--approve-fields PATH[,PATH]]
                         [--context FILE]

Exit codes: 0 ok, 1 at least one candidate refused (check, apply), 2 usage
error, unreadable or unsupported file, 3 no PDF text extractor available.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
REPO = AGENT.parents[1]
CANDIDATES_SCHEMA = AGENT / "assets" / "doc-candidates.schema.json"
sys.path.insert(0, str(REPO / "shared" / "scripts"))
import proof as proof_lib  # noqa: E402
from validate_json import validate  # noqa: E402

TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
SOURCE_RE = re.compile(r"^(docs/[A-Za-z0-9._/-]+)#p([1-9][0-9]*)$")
NUMBER_RE = re.compile(r"\d+(?:[ .,]\d+)*")
SPACES = {" ": " ", " ": " ", " ": " ", " ": " "}
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "«": '"', "»": '"'}
FIELDS = {
    "url": "string", "one_liner": "string", "what_it_is": "string", "category": "string",
    "geography.country": "string", "geography.notes": "string",
    "icp.who": "string", "icp.pains": "list", "icp.jobs": "list",
    "offer.core": "string", "offer.price_model": "string", "offer.differentiators": "list",
    "positioning.against": "string", "positioning.promise": "string",
}


class UsageError(Exception):
    pass


class NoExtractor(Exception):
    pass


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for a, b in {**SPACES, **QUOTES}.items():
        text = text.replace(a, b)
    return " ".join(text.split())


def digits(token: str) -> str:
    return re.sub(r"\D", "", token)


def safe_name(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    if not stem:
        raise UsageError(f"cannot make a file name from {name!r}")
    return stem


# ------------------------------------------------------------------ extract

def pdf_pages(path: Path, extractor: str) -> Tuple[List[str], str]:
    if extractor in ("auto", "pdftotext") and which("pdftotext"):
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True)
        if r.returncode != 0:
            raise UsageError(f"{path.name}: pdftotext failed: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
        pages = r.stdout.decode("utf-8", "replace").split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return pages, "pdftotext"
    if extractor == "pdftotext":
        raise NoExtractor("pdftotext is not installed")
    if extractor in ("auto", "pypdf"):
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            PdfReader = None
        if PdfReader is not None:
            try:
                reader = PdfReader(str(path))
                return [(page.extract_text() or "") for page in reader.pages], "pypdf"
            except Exception as e:  # noqa: BLE001  (pypdf raises many types on a broken file)
                raise UsageError(f"{path.name}: pypdf cannot read it: {e}")
    raise NoExtractor("no PDF text extractor")


def text_pages(path: Path) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise UsageError(f"{path}: cannot read as UTF-8 text: {e}")
    pages = text.split("\f")
    return pages if any(p.strip() for p in pages) else [text]


def extract(ctx: Path, files: List[str], extractor: str) -> List[Dict[str, Any]]:
    docs = ctx / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    out = []
    for name in files:
        src = Path(name)
        if not src.is_file():
            raise UsageError(f"{name}: not a file")
        suffix = src.suffix.lower()
        if suffix != ".pdf" and suffix not in TEXT_SUFFIXES:
            raise UsageError(f"{src.name}: unsupported type {suffix or '(none)'}. Export the deck to PDF, or the notes to .md or .txt")
        target = docs / safe_name(src.name)
        if src.resolve() != target.resolve():
            if target.exists() and sha256(target) != sha256(src):
                raise UsageError(f"docs/{target.name} already holds another file: rename the new one")
            shutil.copyfile(src, target)
        pages, used = (pdf_pages(target, extractor) if suffix == ".pdf" else (text_pages(target), "text"))
        record = {"version": 1, "source": f"docs/{target.name}", "sha256": sha256(target), "extractor": used,
                  "pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages)]}
        (docs / f"{target.name}.pages.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        empty = [p["page"] for p in record["pages"] if not p["text"].strip()]
        out.append({"source": record["source"], "pages": len(pages), "extractor": used, "empty_pages": empty})
    return out


# ------------------------------------------------------------------ check

def load_doc(ctx: Path, rel: str, cache: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    if rel in cache:
        return cache[rel]
    doc_path, pages_path = ctx / rel, ctx / f"{rel}.pages.json"
    if not doc_path.is_file() or not pages_path.is_file():
        result: Tuple[Optional[Dict[str, Any]], str] = (None, f"{rel} was not ingested: run ingest_docs.py extract on it first")
    else:
        data = json.loads(pages_path.read_text(encoding="utf-8"))
        if data.get("sha256") != sha256(doc_path):
            result = (None, f"{rel} changed since extract: run ingest_docs.py extract again")
        else:
            result = (data, "")
    cache[rel] = result
    return result


def page_text(ctx: Path, source: Any, cache: Dict[str, Any]) -> Tuple[Optional[str], str]:
    m = SOURCE_RE.match(str(source or ""))
    if not m:
        return None, f"source {source!r} does not cite a page of an ingested document (docs/<file>#p<N>)"
    doc, why = load_doc(ctx, m.group(1), cache)
    if doc is None:
        return None, why
    n = int(m.group(2))
    if n > len(doc["pages"]):
        return None, f"{m.group(1)} has {len(doc['pages'])} pages, not {n}"
    text = doc["pages"][n - 1]["text"]
    if not text.strip():
        return None, f"page {n} of {m.group(1)} has no text layer (a scanned page?): type the fact in with another source"
    return text, ""


def closest(needle: str, haystack: str) -> str:
    lines = [normalize(x) for x in re.split(r"(?<=[.!?])\s+|\n", haystack) if x.strip()]
    best = difflib.get_close_matches(needle, lines, n=1, cutoff=0.3)
    return best[0] if best else ""


def verbatim(claim: str, page: str) -> str:
    """'' when claim is on the page word for word, else the reason."""
    want, have = normalize(claim), normalize(page)
    start = have.find(want) if want else -1
    while start >= 0:
        end = start + len(want)
        if not (start and have[start - 1].isalnum() and want[0].isalnum()) and not (end < len(have) and have[end].isalnum() and want[-1].isalnum()):
            return ""
        start = have.find(want, start + 1)
    page_numbers = {digits(t) for t in NUMBER_RE.findall(have)}
    missing = [t for t in NUMBER_RE.findall(want) if digits(t) not in page_numbers]
    if missing:
        return f"{', '.join(repr(t) for t in missing)} is not on the cited page: no rounding, no other page's number"
    near = closest(want, page)
    return "not on the cited page word for word" + (f" (closest line: {near!r})" if near else "")


def check(ctx: Path, cand_path: Path, today: Any = None) -> Dict[str, Any]:
    try:
        cand = json.loads(cand_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise UsageError(f"{cand_path}: cannot read: {e}")
    schema = json.loads(CANDIDATES_SCHEMA.read_text(encoding="utf-8"))
    errors = validate(cand, schema)
    if errors:
        return {"status": "fail", "schema": errors, "fields": [], "proof": []}
    cache: Dict[str, Any] = {}
    fields = []
    for i, f in enumerate(cand.get("fields") or []):
        row = {"index": i, "field": f["field"], "status": "ok", "reason": ""}
        text, why = page_text(ctx, f.get("source"), cache)
        if f["field"] not in FIELDS:
            row.update(status="refused", reason=f"{f['field']} is not a context.json field a document can fill")
        elif (FIELDS[f["field"]] == "list") != isinstance(f["value"], list):
            row.update(status="refused", reason=f"{f['field']} takes {'a list of strings' if FIELDS[f['field']] == 'list' else 'a string'}")
        elif text is None:
            row.update(status="refused", reason=why)
        else:
            miss = verbatim(f["excerpt"], text)
            if miss:
                row.update(status="refused", reason=f"excerpt {miss}")
        fields.append(row)
    items = proof_lib.load_proof({"positioning": {"proof": cand.get("proof") or []}})
    proofs = []
    for p in items:
        row = {"index": p.index, "id": p.id, "status": "ok", "reason": "", "warnings": []}
        text, why = page_text(ctx, p.source, cache)
        if p.errors:
            row.update(status="refused", reason="malformed: " + "; ".join(p.errors))
        elif text is None:
            row.update(status="refused", reason=why)
        else:
            miss = verbatim(p.claim, text)
            if miss:
                row.update(status="refused", reason=f"claim {miss}")
        if row["status"] == "ok":
            if not p.date:
                row["warnings"].append("no date: ask the founder the date of the fact (never today's date by default)")
            granted = (p.consent or {}).get("scope") or []
            ok, use_why = proof_lib.usable(p, granted[0] if granted else "posts", today, str(ctx))
            row["usable_in_copy"] = ok and not use_why
            if not ok:
                row["warnings"].append(f"accepted as a candidate, refused in copy until fixed: {use_why}")
        proofs.append(row)
    failed = any(r["status"] != "ok" for r in fields + proofs)
    return {"status": "fail" if failed else "pass", "schema": [], "fields": fields, "proof": proofs}


# ------------------------------------------------------------------ apply

def set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for key in parts[:-1]:
        node = node.setdefault(key, {})
    if isinstance(value, list):
        current = node.get(parts[-1]) if isinstance(node.get(parts[-1]), list) else []
        node[parts[-1]] = current + [v for v in value if v not in current]
    else:
        node[parts[-1]] = value


def apply(ctx: Path, cand_path: Path, approve: List[str], approve_fields: List[str], target: Path) -> Tuple[int, List[str]]:
    report = check(ctx, cand_path)
    if report["schema"]:
        return 1, [f"schema: {e}" for e in report["schema"]]
    cand = json.loads(cand_path.read_text(encoding="utf-8"))
    by_id = {r["id"]: (r, cand["proof"][r["index"]]) for r in report["proof"]}
    by_field = {r["field"]: (r, cand["fields"][r["index"]]) for r in report["fields"]}
    problems = [f"{k}: not among the candidates" for k in approve if k not in by_id]
    problems += [f"{k}: not among the candidate fields" for k in approve_fields if k not in by_field]
    problems += [f"{k}: refused, {by_id[k][0]['reason']}" for k in approve if k in by_id and by_id[k][0]["status"] != "ok"]
    problems += [f"{k}: refused, {by_field[k][0]['reason']}" for k in approve_fields if k in by_field and by_field[k][0]["status"] != "ok"]
    if problems:
        return 1, problems
    data: Dict[str, Any] = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise UsageError(f"{target}: not JSON: {e}")
    for k in approve_fields:
        set_path(data, k, by_field[k][1]["value"])
    proof = data.setdefault("positioning", {}).setdefault("proof", [])
    existing = {p.get("id") for p in proof if isinstance(p, dict)}
    written = []
    for k in approve:
        if k in existing:
            continue
        proof.append(by_id[k][1])
        written.append(k)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return 0, [f"wrote {len(approve_fields)} fields and {len(written)} proof items to {target}"]


def split_list(value: Optional[str]) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="Copy documents into docs/ and extract the text of each page")
    e.add_argument("--out", required=True, help="project-context folder")
    e.add_argument("--extractor", choices=("auto", "pdftotext", "pypdf"), default="auto")
    e.add_argument("files", nargs="+")
    c = sub.add_parser("check", help="Check the candidates against the extracted pages")
    c.add_argument("--out", required=True, help="project-context folder")
    c.add_argument("candidates")
    c.add_argument("--json", action="store_true")
    a2 = sub.add_parser("apply", help="Write the approved candidates")
    a2.add_argument("--out", required=True, help="project-context folder")
    a2.add_argument("candidates")
    a2.add_argument("--approve", default="", help="Comma-separated proof candidate ids the founder approved")
    a2.add_argument("--approve-fields", default="", help="Comma-separated field paths the founder approved, e.g. one_liner,icp.who")
    a2.add_argument("--context", help="Target JSON (default: <out>/brand-debug/context-draft.json)")
    a = ap.parse_args(argv)
    ctx = Path(a.out)
    try:
        if a.cmd == "extract":
            for row in extract(ctx, a.files, a.extractor):
                note = f", pages without text: {row['empty_pages']}" if row["empty_pages"] else ""
                print(f"{row['source']}: {row['pages']} page{'s' if row['pages'] != 1 else ''} ({row['extractor']}){note} -> {row['source']}.pages.json")
            return 0
        if not ctx.is_dir():
            raise UsageError(f"{ctx} is not a folder")
        if a.cmd == "check":
            report = check(ctx, Path(a.candidates))
            if a.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                for err in report["schema"]:
                    print(f"schema: {err}")
                for r in report["fields"]:
                    print(f"field {r['field']}: {r['status']}" + (f": {r['reason']}" if r["reason"] else ""))
                for r in report["proof"]:
                    print(f"proof {r['id']}: {r['status']}" + (f": {r['reason']}" if r["reason"] else ""))
                    for w in r["warnings"]:
                        print(f"  warning: {w}")
                print(f"Check: {report['status'].upper()}")
            return 0 if report["status"] == "pass" else 1
        approve, fields = split_list(a.approve), split_list(a.approve_fields)
        if not approve and not fields:
            raise UsageError("nothing approved: pass --approve and/or --approve-fields with what the founder said yes to")
        target = Path(a.context) if a.context else ctx / "brand-debug" / "context-draft.json"
        rc, lines = apply(ctx, Path(a.candidates), approve, fields, target)
        for line in lines:
            print(line if rc == 0 else f"refused: {line}")
        if rc:
            print("Nothing written.")
        return rc
    except NoExtractor as e:
        print(f"error: {e}. Install poppler (pdftotext: apt install poppler-utils, brew install poppler) "
              "or pypdf (pip install pypdf), or export the deck to text and pass the .txt", file=sys.stderr)
        return 3
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
