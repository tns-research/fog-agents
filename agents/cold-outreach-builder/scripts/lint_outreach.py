#!/usr/bin/env python3
"""
lint_outreach.py

Mechanical gate on the sequencer export of cold-outreach-builder. Every
subject and body of every prospect goes through the shared writing gate
engine (shared/skills/writing-gate/scripts/lint_copy.py, imported, not
copied) with its EN/FR packs, the project pack and the outreach packs of
assets/patterns/, then through checks no single-text linter can make:
duplicates and near-duplicates between prospects, unfilled variables,
length, links, subject, sourced fact in the first message, signature.
Standard library only, Python 3.9+.

Usage:
    python3 lint_outreach.py <run>/sequence-export.csv \
        [--dossiers <run>/dossiers [--verify verify.json]] [--project <your-projects-root>/<project>] \
        [--sequence <run>/cold-outreach-output.json | --channel email|linkedin] \
        [--limits <project>/cold-outreach-builder/limits.json] \
        [--lang auto|en|fr] [--sender-first-name NAME] [--with-slopcheck] \
        [--json] [--out <run>/lint.json]

Checks (codes), on top of the writing gate and outreach pack codes:
  duplicate-address     the same email (or LinkedIn URL) on two rows             BLOCK
  duplicate-hook        two prospects get the same hook                          BLOCK
  near-duplicate-hook   hooks too similar (word 3-gram Jaccard, limits.json)     BLOCK / WARN
  unfilled-variable     {{token}}, {token}, [First name], <company>, %NAME%,
                        TODO left in a subject or body ({{sender_first_name}}
                        is the one token allowed to stay)                        BLOCK
  too-long, too-long-chars  words (signature excluded) or characters over
                        limits.json for the channel and step                     BLOCK / WARN
  too-many-links, url-shortener  links over the step's limit, shortened links    BLOCK
  missing-subject, subject-too-long, fake-reply-subject, subject-caps,
  subject-exclamation   subject rules (email)                                    BLOCK / WARN
  no-sourced-fact       message 1 does not carry a hook built on a verified,
                        dated, sourced fact of the prospect's dossier            BLOCK
  unsourced-number      a number that is in no verified fact of the prospect,
                        in no usable positioning.proof item (shared/scripts/
                        proof.py, scope outreach: a stale metric or a customer
                        without consent does not count, listed under
                        proof_refused with its reason), and is not a date,
                        time or duration                                         BLOCK
  signature             the body does not end with {{sender_first_name}} (or
                        the --sender-first-name value), or ends with another
                        hard-coded first name                                    BLOCK
  hardcoded-sender      "I'm <Name>" / "je suis <Name>" with a name that is not
                        the sender token                                         WARN
  equity-percentage     an equity percentage                                     BLOCK
  bullets, label-line   list items or "Label:" lines in a cold message           BLOCK / WARN
  emoji                 emoji (email BLOCK, LinkedIn WARN)

Loop: fix every BLOCK in messages.json or the templates, rebuild the export,
run again until 0 BLOCK. Never edit a pack, limits.json or this script to
make a run pass.

Exit codes: 0 no BLOCK, 1 at least one BLOCK, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from outreach_lib import (ASSETS, SHARED_SCRIPTS, WRITING_GATE_SCRIPTS, InputError, load_json,  # noqa: E402
                          merged_config, norm_text, normalize_email, normalize_linkedin,
                          read_csv, words)

sys.path.insert(0, SHARED_SCRIPTS)
import proof as proof_lib  # noqa: E402  (shared reader of positioning.proof)

sys.path.insert(0, WRITING_GATE_SCRIPTS)
import lint_copy  # noqa: E402  (shared writing gate engine)

LIMITS = os.path.join(ASSETS, "limits.json")
PROOF_SCOPE = "outreach"  # consent scope of positioning.proof items read by this gate
PACKS = {lang: os.path.join(ASSETS, "patterns", f"outreach.{lang}.json") for lang in ("en", "fr")}

TOKEN_RE = re.compile(r"\{\{\s*\??\s*([A-Za-z0-9_]+)\s*\}\}")
PLACEHOLDER_RES = [
    re.compile(r"(?<!\{)\{[A-Za-z_][A-Za-z0-9_ ]{1,30}\}(?!\})"),
    re.compile(r"\[(?:first[ _-]?name|last[ _-]?name|full[ _-]?name|name|company|company name|role|title|your name|sender|"
               r"pr[ée]nom|nom|entreprise|soci[ée]t[ée]|poste)\]", re.I),
    re.compile(r"\[[A-Z][A-Za-z _-]{1,30}\](?!\()"),
    re.compile(r"<(?:first[_ ]?name|last[_ ]?name|name|company|role|pr[ée]nom|nom|entreprise)>", re.I),
    re.compile(r"%[A-Z_]{3,}%"),
    re.compile(r"\bTODO\b|\bTBD\b|\bXXX+\b|\blorem ipsum\b", re.I),
]
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\"']+", re.I)
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27bf\ufe0f\u2b50\u2b55\u231a-\u23ff]")
EQUITY_RE = re.compile(r"\d+(?:[.,]\d+)?\s?%\s*(?:d['\u2019]\s*|of\s+)?(?:equity|capital)"
                       r"|equity\s+(?:of\s+|stake\s+of\s+)?\d+(?:[.,]\d+)?\s?%", re.I)
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
BULLET_RE = re.compile(r"^\s*(?:[-*\u2022\u25aa\u25cf]|\d{1,2}[.)])\s+\S", re.M)
LABEL_RE = re.compile(r"^\s*[A-ZÀ-Ý][^:\n.!?]{2,40}:\s*(?:\S.*)?$", re.M)
SENDER_INTRO_RE = re.compile(r"\b(?:I'm|I am|my name is|je suis|je m'appelle|moi c'est)\s+([A-ZÀ-Ý][a-zà-ÿ]+(?:-[A-ZÀ-Ý][a-zà-ÿ]+)?)\b")
LONE_NAME_RE = re.compile(r"^[-\s]*([A-ZÀ-Ý][a-zà-ÿ]+(?:[- ][A-ZÀ-Ý][a-zà-ÿ]+)?)\.?\s*$")
SUBJECT_PRONOUNS = {
    "en": {"i", "we", "you", "he", "she", "they", "it", "i'm", "we're", "you're"},
    "fr": {"je", "j'ai", "nous", "on", "vous", "tu", "il", "elle", "ils", "elles", "c'est"},
}
GREETING_WORDS = {"hi", "hello", "hey", "bonjour", "salut", "thanks", "merci", "best", "cheers", "regards",
                  "cordialement", "bien", "bonne", "belle", "a", "to"}


class Linter:
    def __init__(self, limits: Dict[str, Any], channel: str, project: Optional[str], lang: str,
                 sender: Optional[str], dossiers: Optional[str], verify_path: Optional[str] = None) -> None:
        self.limits = limits
        self.channel = channel
        self.ch = limits["channels"][channel]
        self.project = project
        self.lang = lang
        self.sender = sender
        self.dossiers = dossiers
        self.verify_path = verify_path or (os.path.join(dossiers, "verify.json") if dossiers else None)
        self.rules_cache: Dict[str, Tuple[List[Dict[str, Any]], List[str]]] = {}
        self.findings: List[Dict[str, Any]] = []
        self.token = limits["tokens"]["signature_token"]
        self.allowed_tokens = set(limits["tokens"].get("allowed_unfilled", []))
        self.allow_number_res = [re.compile(p, re.I) for p in limits["numbers"]["allow_patterns"]]
        self.proof_refused: List[Dict[str, Any]] = []
        self.proof_numbers = self._proof_numbers()
        self.verify = self._load_verify()

    # ------------------------------------------------------------ inputs

    def _proof_numbers(self) -> Set[str]:
        nums: Set[str] = set()
        if not self.project:
            return nums
        path = os.path.join(self.project, "project-context", "context.json")
        if os.path.isfile(path):
            try:
                ctx = load_json(path)
            except InputError:
                return nums
            root = os.path.dirname(path)
            for item in proof_lib.load_proof(ctx):
                ok, reason = proof_lib.usable(item, PROOF_SCOPE, None, root)
                if ok:
                    nums |= numbers_in(proof_lib.proof_text(item))
                else:
                    self.proof_refused.append({"index": item.index, "id": item.id, "reason": reason})
        return nums

    def _load_verify(self) -> Dict[str, Any]:
        if not self.dossiers:
            return {}
        path = self.verify_path
        if not os.path.isfile(path):
            raise InputError(f"{path} not found: run verify_dossiers.py before the lint")
        return load_json(path).get("prospects", {})

    def dossier(self, pid: str) -> Dict[str, Any]:
        if not self.dossiers or not pid:
            return {}
        path = os.path.join(self.dossiers, pid, "prospect.json")
        try:
            return load_json(path) if os.path.isfile(path) else {}
        except InputError:
            return {}

    def rules(self, lang: str) -> List[Dict[str, Any]]:
        if lang not in self.rules_cache:
            packs = [p for p in PACKS.values() if os.path.isfile(p)]
            self.rules_cache[lang] = lint_copy.load_rules(lang, self.project, None, packs, [])
        return self.rules_cache[lang][0]

    def sources(self) -> List[str]:
        out: List[str] = []
        for rules, src in self.rules_cache.values():
            out += [s for s in src if s not in out]
        return out

    # ------------------------------------------------------------ helpers

    def add(self, row: Dict[str, Any], level: str, code: str, message: str, step: Optional[int] = None,
            field: str = "row", line: int = 0, match: str = "") -> None:
        self.findings.append({
            "row": row["_row"], "prospect_id": row.get("prospect_id", ""),
            "contact": row.get("email") or row.get("linkedin_url") or row.get("first_name", ""),
            "step": step, "field": field, "line": line, "level": level, "code": code,
            "match": match[:80], "message": message,
        })

    # ------------------------------------------------------------ per text

    def lint_engine(self, row, step, field, text, lang) -> None:
        for f in lint_copy.lint_text(text, self.rules(lang)):
            self.add(row, f["level"], f["code"], f["message"], step, field, f["line"], f["match"])
        for m in EQUITY_RE.finditer(text):
            self.add(row, "BLOCK", "equity-percentage", "Never write an equity percentage in outreach copy.",
                     step, field, line_of(text, m.start()), m.group(0))

    def lint_placeholders(self, row, step, field, text) -> None:
        for m in TOKEN_RE.finditer(text):
            if m.group(1) not in self.allowed_tokens:
                self.add(row, "BLOCK", "unfilled-variable", "A variable was never filled: write the value or drop the line.",
                         step, field, line_of(text, m.start()), m.group(0))
        stripped = TOKEN_RE.sub(lambda m: " " * len(m.group(0)), text)
        stripped = URL_RE.sub(lambda m: " " * len(m.group(0)), stripped)
        seen_at: Set[int] = set()
        for rx in PLACEHOLDER_RES:
            for m in rx.finditer(stripped):
                if m.start() in seen_at:
                    continue
                seen_at.add(m.start())
                self.add(row, "BLOCK", "unfilled-variable", "A placeholder is left in the copy: write the value or drop the line.",
                         step, field, line_of(text, m.start()), m.group(0))

    def lint_subject(self, row, n, subject, lang) -> None:
        ch = self.ch
        if not subject:
            if n == 1 and ch.get("subject_required_on_step_1"):
                self.add(row, "BLOCK", "missing-subject", "Message 1 needs a subject.", n, "subject")
            return
        self.lint_engine(row, n, "subject", subject, lang)
        self.lint_placeholders(row, n, "subject", subject)
        mx = ch.get("subject_max_chars")
        shown = TOKEN_RE.sub("Xxxxxxx", subject)
        if mx and len(shown) > mx:
            self.add(row, "BLOCK", "subject-too-long", f"Subject is {len(shown)} characters, limit {mx}.", n, "subject", 1, subject)
        if n == 1 and re.match(r"^\s*(?:re|fwd?|tr)\s*:", subject, re.I):
            self.add(row, "BLOCK", "fake-reply-subject", "A first message cannot pretend to be a reply or a forward.", n, "subject", 1, subject)
        caps = [w for w in re.findall(r"\b[A-ZÀ-Ý]{4,}\b", subject)]
        if caps:
            self.add(row, "WARN", "subject-caps", "Write the subject in sentence case.", n, "subject", 1, " ".join(caps))
        if "!" in subject:
            self.add(row, "WARN", "subject-exclamation", "Drop the exclamation mark from the subject.", n, "subject", 1, subject)
        if EMOJI_RE.search(subject):
            self.add(row, "BLOCK", "emoji", "No emoji in a cold subject.", n, "subject", 1, subject)

    def lint_body(self, row, n, body, lang, allowed_numbers: Set[str]) -> None:
        if not body.strip():
            return
        ch = self.ch
        self.lint_engine(row, n, "body", body, lang)
        self.lint_placeholders(row, n, "body", body)

        lines = [ln for ln in body.split("\n")]
        nonempty = [ln.strip() for ln in lines if ln.strip()]
        last = nonempty[-1] if nonempty else ""
        signer = self.sender
        signs = bool(last) and (last.endswith(self.token) or (signer and last.endswith(signer)))
        if ch.get("signature_required") and not signs:
            self.add(row, "BLOCK", "signature", f"End the message with {self.token} on its own line (never a real first name in a template).",
                     n, "body", len(lines), last)
        elif not signs:
            m = LONE_NAME_RE.match(last)
            if m and m.group(1).split()[0].lower() not in GREETING_WORDS and m.group(1) not in (row.get("first_name"), signer):
                self.add(row, "BLOCK", "signature", f"Hard-coded name as signature: use {self.token}.", n, "body", len(lines), last)
        for m in SENDER_INTRO_RE.finditer(body):
            if m.group(1) != signer:
                self.add(row, "WARN", "hardcoded-sender", f"A sender name is written in the copy: use {self.token}.",
                         n, "body", line_of(body, m.start()), m.group(0))

        text_wo_sig = "\n".join(nonempty[:-1]) if signs else "\n".join(nonempty)
        count = len(words(TOKEN_RE.sub("x", URL_RE.sub("", text_wo_sig))))
        key = "step_1" if n == 1 else "follow_up"
        wl = (ch.get("words") or {}).get(key) or {}
        if wl.get("max") and count > wl["max"]:
            self.add(row, "BLOCK", "too-long", f"{count} words, limit {wl['max']} for {key.replace('_', ' ')} on {self.channel}.", n, "body")
        elif wl.get("warn") and count > wl["warn"]:
            self.add(row, "WARN", "too-long", f"{count} words, target under {wl['warn']}.", n, "body")
        mc = (ch.get("max_chars") or {}).get(key)
        if mc and len(body) > mc:
            self.add(row, "BLOCK", "too-long-chars", f"{len(body)} characters, limit {mc} (LinkedIn connection note).", n, "body")

        urls = URL_RE.findall(body)
        links = ch.get("links") or {}
        lmax = links.get("step_1_max" if n == 1 else "follow_up_max")
        if lmax is not None and len(urls) > lmax:
            self.add(row, "BLOCK", "too-many-links", f"{len(urls)} link(s), limit {lmax} for this step.", n, "body", 0, " ".join(urls))
        for u in urls:
            host = re.sub(r"^(?:https?://)?(?:www\.)?", "", u.lower()).split("/")[0]
            if host in self.limits["links"]["shorteners"]:
                self.add(row, "BLOCK", "url-shortener", "Use the full link on a domain you own, never a shortener.", n, "body", line_of(body, body.find(u)), u)
        lvl = ch.get("emoji", "BLOCK")
        for m in EMOJI_RE.finditer(body):
            self.add(row, lvl, "emoji", "No emoji in a cold message.", n, "body", line_of(body, m.start()), m.group(0))
            break
        for m in BULLET_RE.finditer(body):
            ln = line_of(body, m.start())
            self.add(row, "BLOCK", "bullets", "Write full sentences: no list items in a cold message.", n, "body", ln, lines[ln - 1].strip())
        pronouns = SUBJECT_PRONOUNS.get(lang, set())
        for m in LABEL_RE.finditer(body):
            txt = m.group(0).strip()
            label = txt.split(":", 1)[0]
            if txt.split()[0].lower().rstrip(",:") in GREETING_WORDS or "{{" in txt or URL_RE.search(txt):
                continue
            if len(words(label)) > 6 or any(w.lower() in pronouns for w in words(label)):
                continue  # a sentence with a subject, not a label
            self.add(row, "WARN", "label-line", "Turn the 'Label:' line into a sentence (subject, verb, object).", n, "body", line_of(body, m.start()), txt)

        clean = TOKEN_RE.sub(" ", URL_RE.sub(" ", body))
        for rx in self.allow_number_res:
            clean = rx.sub(lambda m: " " * len(m.group(0)), clean)
        for m in NUMBER_RE.finditer(clean):
            if digits(m.group(0)) not in allowed_numbers:
                self.add(row, "BLOCK", "unsourced-number",
                         "This number is in no verified fact of the prospect and no positioning.proof item: source it or remove it.",
                         n, "body", line_of(body, m.start()), context(body, m.start(), m.end()))

    # ------------------------------------------------------------ per row

    def lint_row(self, row: Dict[str, Any], steps: List[int]) -> None:
        pid = row.get("prospect_id", "")
        sample = "\n".join(row.get(f"step_{n}_body", "") for n in steps)
        lang = self.lang if self.lang != "auto" else lint_copy.detect_lang(lint_copy.clean_text(sample, False))
        row["_lang"] = lang

        allowed = set(self.proof_numbers)
        data = self.dossier(pid)
        ver = (self.verify.get(pid) or {}).get("facts", {})
        facts = {f.get("id"): f for f in data.get("facts", []) if isinstance(f, dict)}
        for fid, f in facts.items():
            if ver.get(fid, {}).get("status") == "verified":
                allowed |= numbers_in(f.get("excerpt", "") + " " + f.get("claim", ""))

        for n in steps:
            self.lint_subject(row, n, row.get(f"step_{n}_subject", ""), lang)
            self.lint_body(row, n, row.get(f"step_{n}_body", ""), lang, allowed)

        if self.limits["hooks"].get("require_sourced_fact_in_step_1", True):
            self.check_sourced_fact(row, facts, ver)

    def check_sourced_fact(self, row, facts, ver) -> None:
        hook = (row.get("hook") or row.get("specific_observation") or "").strip()
        fid = (row.get("hook_fact_id") or "").strip()
        body1 = row.get("step_1_body", "")
        if not hook or not fid:
            self.add(row, "BLOCK", "no-sourced-fact",
                     "Message 1 has no hook tied to a fact of the dossier (hook and hook_fact_id are empty).", 1, "body")
            return
        if norm_text(hook) not in norm_text(body1):
            self.add(row, "BLOCK", "no-sourced-fact", "The hook is not in message 1: put the hook sentence in the first message.", 1, "body", 0, hook)
        if self.dossiers:
            if fid not in facts:
                self.add(row, "BLOCK", "no-sourced-fact", f"hook_fact_id {fid} is not a fact of dossiers/{row.get('prospect_id')}/prospect.json.", 1, "body")
            else:
                st = ver.get(fid, {}).get("status", "unchecked")
                if st != "verified":
                    self.add(row, "BLOCK", "no-sourced-fact", f"Fact {fid} is {st} in verify.json: a hook needs a verified fact inside the freshness window.", 1, "body")
        elif not (row.get("hook_source_url") or row.get("source_url")):
            self.add(row, "BLOCK", "no-sourced-fact", "The hook has no source URL. Pass --dossiers to check it against the verified dossier.", 1, "body")

    # ------------------------------------------------------------ cross rows

    def lint_duplicates(self, rows: List[Dict[str, Any]]) -> None:
        seen: Dict[str, int] = {}
        for r in rows:
            keys = []
            if r.get("email"):
                keys.append("email:" + normalize_email(r["email"]))
            if r.get("linkedin_url") and (self.channel == "linkedin" or not r.get("email")):
                keys.append("linkedin:" + normalize_linkedin(r["linkedin_url"]))
            for k in keys:
                if k in seen:
                    self.add(r, "BLOCK", "duplicate-address", f"Same address as row {seen[k]}: one person, one row.", None, "row", 0, k.split(":", 1)[1])
                else:
                    seen[k] = r["_row"]

    def lint_hooks(self, rows: List[Dict[str, Any]]) -> None:
        cfg = self.limits["hooks"]
        size = int(cfg.get("shingle_size", 3))
        prepared = []
        for r in rows:
            hook = (r.get("hook") or r.get("specific_observation") or first_sentence(strip_greeting(r.get("step_1_body", "")))).strip()
            if not hook:
                continue
            masked = norm_text(hook)
            for v in (r.get("first_name"), r.get("last_name"), r.get("company")):
                if v and len(v) > 1:
                    masked = masked.replace(norm_text(v), "x")
            prepared.append((r, hook, masked, shingles(masked, size)))
        for i in range(len(prepared)):
            for j in range(i):
                r, hook, masked, sh = prepared[i]
                r0, _, masked0, sh0 = prepared[j]
                if masked == masked0:
                    self.add(r, "BLOCK", "duplicate-hook", f"Same hook as row {r0['_row']}: every hook is about one person.", 1, "hook", 0, hook)
                    break
                sim = jaccard(sh, sh0)
                if sim >= cfg["similarity_block"]:
                    self.add(r, "BLOCK", "near-duplicate-hook", f"Hook {sim:.2f} similar to row {r0['_row']} (limit {cfg['similarity_block']}).", 1, "hook", 0, hook)
                    break
                if sim >= cfg["similarity_warn"]:
                    self.add(r, "WARN", "near-duplicate-hook", f"Hook {sim:.2f} similar to row {r0['_row']}.", 1, "hook", 0, hook)
                    break


# ---------------------------------------------------------------- utils

def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(offset, 0)) + 1


def context(text: str, start: int, end: int) -> str:
    return " ".join(text[max(0, start - 25):min(len(text), end + 25)].split())


def digits(s: str) -> str:
    return re.sub(r"[^\d]", "", s).lstrip("0") or "0"


def numbers_in(text: str) -> Set[str]:
    return {digits(m.group(0)) for m in NUMBER_RE.finditer(text or "")}


def strip_greeting(body: str) -> str:
    lines = [ln for ln in body.split("\n") if ln.strip()]
    if lines and len(words(lines[0])) <= 4 and lines[0].rstrip().endswith((",", "!")):
        lines = lines[1:]
    return " ".join(lines)


def first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()


def shingles(text: str, size: int) -> Set[Tuple[str, ...]]:
    w = [x.lower() for x in words(text)]
    if len(w) < size * 2:
        return {(x,) for x in w}
    return {tuple(w[i:i + size]) for i in range(len(w) - size + 1)}


def jaccard(a: Set[Any], b: Set[Any]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detect_channel(seq_path: Optional[str], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if seq_path:
        data = load_json(seq_path)
        ch = data.get("channel") if isinstance(data, dict) else None
        if ch in ("email", "linkedin"):
            return ch
    return "email"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="sequence-export.csv")
    ap.add_argument("--dossiers", help="Dossiers folder with verify.json: checks hooks and numbers against verified facts")
    ap.add_argument("--verify", help="verify.json path (default: <dossiers>/verify.json)")
    ap.add_argument("--project", help="<your-projects-root>/<project>: project voice pack, banned words, positioning.proof")
    ap.add_argument("--sequence", help="cold-outreach-output.json, to read the channel")
    ap.add_argument("--channel", choices=["email", "linkedin"])
    ap.add_argument("--limits", help="Project limits.json merged over assets/limits.json")
    ap.add_argument("--lang", default="auto", choices=["auto", "en", "fr"])
    ap.add_argument("--sender-first-name", help="Value used when the export was rendered with it")
    ap.add_argument("--with-slopcheck", action="store_true", help="Also run slopcheck when installed")
    ap.add_argument("--json", action="store_true", help="Print one JSON object")
    ap.add_argument("--out", help="Also write the JSON report to this path")
    a = ap.parse_args(argv)

    try:
        limits = merged_config(LIMITS, a.limits)
        channel = detect_channel(a.sequence, a.channel)
        header, rows = read_csv(a.export)
        linter = Linter(limits, channel, a.project, a.lang, a.sender_first_name, a.dossiers, a.verify)
    except (InputError, lint_copy.UsageError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    steps = sorted({int(m.group(1)) for h in header for m in [re.match(r"^step_(\d+)_body$", h)] if m})
    if not steps:
        print("error: no step_N_body column: is this a sequence-export.csv?", file=sys.stderr)
        return 2
    for i, r in enumerate(rows, start=2):
        r["_row"] = i
    try:
        for r in rows:
            linter.lint_row(r, steps)
        linter.lint_duplicates(rows)
        linter.lint_hooks(rows)
    except lint_copy.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    slop = None
    if a.with_slopcheck:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            for r in rows:
                for n in steps:
                    tmp.write(r.get(f"step_{n}_body", "") + "\n\n")
        slop = lint_copy.run_slopcheck(tmp.name, "", a.json)
        os.unlink(tmp.name)

    findings = sorted(linter.findings, key=lambda f: (f["row"], f["step"] or 0, f["field"], f["line"], f["code"]))
    blocks = sum(1 for f in findings if f["level"] == "BLOCK")
    if slop and slop.get("ran") and slop.get("exit") == 1:
        blocks += 1
    report = {
        "status": "fail" if blocks else "pass",
        "export": a.export, "channel": channel, "rows": len(rows), "steps": len(steps),
        "packs": linter.sources(),
        "counts": {"BLOCK": blocks, "WARN": sum(1 for f in findings if f["level"] == "WARN")},
        "by_code": {}, "findings": findings,
        "proof_refused": linter.proof_refused,
    }
    for f in findings:
        k = f"{f['level']} {f['code']}"
        report["by_code"][k] = report["by_code"].get(k, 0) + 1
    if slop:
        report["slopcheck"] = slop
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if blocks else 0

    for r in linter.proof_refused:
        print(f"positioning.proof[{r['index']}] {r['id']} refused, its numbers are not allowed: {r['reason']}")
    current = None
    for f in findings:
        if f["row"] != current:
            current = f["row"]
            print(f"\nrow {f['row']} {f['prospect_id']} <{f['contact']}>")
        where = f"step {f['step']} {f['field']}" if f["step"] else f["field"]
        where += f":{f['line']}" if f["line"] else ""
        quoted = f'  "{f["match"]}"' if f["match"] else ""
        print(f"  {f['level']:<5} {f['code']:<20} {where}{quoted}")
        print(f"        fix: {f['message']}")
    if slop:
        print(f"\nslopcheck: {slop.get('note') or 'exit ' + str(slop.get('exit'))}")
    print(f"\n{len(rows)} row(s) x {len(steps)} step(s), channel {channel}: {report['counts']['BLOCK']} BLOCK, {report['counts']['WARN']} WARN")
    if blocks:
        print("Gate: FAIL. Fix every BLOCK in messages.json or the templates, rebuild the export, run again.")
    else:
        print("Gate: PASS (0 BLOCK). Read every WARN: fix it or keep it with a reason in the report.")
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
