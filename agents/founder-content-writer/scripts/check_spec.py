#!/usr/bin/env python3
"""check_spec.py: every mechanical check of a founder-content-writer batch.

The model writes posts-spec.json; this script says whether it may ship:

  sources    each post cites passages found word for word in the ingested raw
             material (sha256 unchanged) or inside a verified market-signal quote
  claims     every number, every declared claim, quoted words, names, rankings,
             crowd claims, time markers and client mentions trace to
             positioning.proof, a sourced passage or the cited passages. Only
             the proof items shared/scripts/proof.py finds usable for posts
             count (a stale metric, a testimonial without consent is refused,
             with its reason in the report)
  network    content-publisher's own rules (limits, X weighted count, one tweet,
             no link in a body, link pointer) and the shared writing gate
  variety    hook types and angles vary inside the batch, openings do not repeat
             inside the batch nor against project memory, the publication queue
             and the founder's past posts
  voice      the project's voice pack when present, the default address form
             (French posts use vous), active decisions of project memory

Usage:
  python3 check_spec.py SPEC.json [--project DIR] [--config config.json] [--queue queue.json]
                        [--no-gate] [--json] [--out check.json]

Exit codes: 0 no error (warnings allowed), 1 at least one error, 2 usage error or
unreadable file. See assets/claims-model.md and assets/hook-types.md.
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fcw_lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "shared" / "scripts"))
import proof as proof_lib  # noqa: E402  (shared reader of positioning.proof)

PROOF_SCOPE = "posts"  # consent scope of positioning.proof items in a founder post

NEEDS_PROOF = {"customer", "testimonial", "press", "ranking", "result", "number"}

RANKING_RE = {
    "en": re.compile(r"\b(?:the (?:best|leading|fastest|cheapest|largest|biggest)|number one|no\.? ?1|world[- ]class|award[- ]winning|market leader)\b|#1\b", re.I),
    "fr": re.compile(r"\b(?:(?:le|la|les) (?:meilleure?s?|plus rapides?|moins chers?)|leader du marché|numéro 1|n° ?1)\b|#1\b", re.I),
}
CROWD_RE = {
    "en": re.compile(r"\bmost (?:founders|startups|teams|people|companies|customers|of (?:them|you|us))\b|\bthe majority of\b|\beveryone knows\b|\bstudies show\b", re.I),
    "fr": re.compile(r"\bla plupart des?\b|\bla majorité des?\b|\btout le monde sait\b|\bbeaucoup de (?:fondateurs|startups|entreprises|clients)\b|\bles études montrent\b", re.I),
}
TIME_RE = {
    "en": re.compile(r"\b(?:yesterday|today|this (?:morning|week|month)|last (?:night|week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|in (?:january|february|march|april|may|june|july|august|september|october|november|december))\b", re.I),
    "fr": re.compile(r"\b(?:hier|aujourd['’]hui|ce matin|cette semaine|ce mois-ci|la semaine dernière|le mois dernier|l['’]an dernier|l['’]année dernière|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|en (?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre))\b", re.I),
}
CLIENT_RE = {
    "en": re.compile(r"\b(?:a|an|one|our|my|this|that)(?: [^\W\d_]+)? (client|customer|user|prospect)s?\b(?! (?:list|file|base|support|service|success|data|journey|interview)s?\b)", re.I),
    "fr": re.compile(r"\b(?:un|une|mon|ma|mes|notre|nos|ce|cette)(?: (?!fichier\b|liste\b|base\b|service\b)[^\W\d_]+)? (client|cliente|utilisateur|utilisatrice|prospect)e?s?\b", re.I),
}
QUOTED_RE = re.compile(r"«\s*([^»]+?)\s*»|“([^”]+)”|\"([^\"\n]+)\"")
NAME_RE = re.compile(r"(?<![\w'’-])[A-ZÀ-Ý][\w’'-]*")
SENTENCE_START_RE = re.compile(r"(?:^|[.!?:;…]\s+|\n\s*|[«“\"(]\s*|(?:^|\n)\s*(?:[-*•→]|\d{1,2}[.)/])\s+)$")
EMAIL_RE = re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE_RE = re.compile(r"(?<![\w.,])\+?\d(?:[ .-]?\d){8,13}(?![\w])")
PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|<[a-z_ ]+>|\[(?:name|first name|prenom|your [a-z ]+)\]", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")

ALWAYS_ALLOWED = {"i", "i'm", "i've", "i'd", "i'll", "i’m", "i’ve", "i’d", "i’ll", "linkedin", "x", "ok", "okay",
                  "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                  "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
# What a sentence says when it reports something that happened, or a result: past
# tense, or a comparison of outcomes. Only read on sentences no source echoes.
EVENT_RE = {
    "en": re.compile(r"\b(?!(?:need|speed|feed|seed|indeed|embed|breed|exceed|proceed|succeed|based|hundred|red|shed|bed|wed|sacred|naked|wicked)\b)[a-z]{2,}ed\b"
                     r"|\b(?:told|said|lost|won|sold|built|made|got|went|came|saw|had|spent|quit|left|paid|bought|grew|ran|met|took|gave|fell|rose)\b"
                     r"|\b(?:fewer|faster|slower|cheaper|better|worse|saves?|cuts?|increases?|reduces?|doubles?)\b", re.I),
    "fr": re.compile(r"\b(?:j['’]ai|on a|nous avons|il a|elle a|ils ont|elles ont|on s['’]est|je suis|nous sommes)\b"
                     r"|\b(?:a|ont)\s+[a-zà-ÿ]+(?:é|i|u|is|it)(?:e|s|es)?\b"
                     r"|\b(?:moins de|plus de|plus vite|plus rapide|économise|économisent|gagne|gagnent|réduit|réduisent)\b", re.I),
}
# Common first words of a sentence. Any other capitalized first word that no
# source holds may be a name: a warning, because no dictionary backs this check.
STARTERS = {
    "after", "again", "also", "and", "because", "before", "but", "every", "everyone", "everything", "first", "for", "from", "here", "how", "if",
    "in", "instead", "it", "its", "last", "let", "like", "many", "maybe", "my", "next", "no", "nobody", "not", "nothing", "now", "of", "on",
    "once", "one", "only", "or", "our", "people", "read", "same", "second", "see", "since", "so", "some", "someone", "start", "still", "stop",
    "that", "the", "their", "then", "there", "these", "they", "this", "those", "to", "today", "until", "we", "what", "when", "where", "which",
    "while", "who", "why", "with", "without", "write", "yes", "yet", "you", "your",
    "alors", "après", "au", "aucun", "aujourd", "aussi", "avant", "avec", "ce", "cela", "ces", "cette", "chaque", "comme", "comment", "dans",
    "de", "depuis", "des", "donc", "du", "elle", "en", "ensuite", "et", "il", "ils", "je", "la", "le", "les", "leur", "mais", "maintenant",
    "mes", "mon", "ne", "nos", "notre", "nous", "on", "ou", "par", "parce", "pas", "personne", "plus", "pour", "pourquoi", "puis", "quand",
    "que", "qui", "rien", "sans", "si", "sur", "tous", "tout", "un", "une", "vos", "votre", "vous",
}
TRACE_MIN = 0.25       # share of a sentence's content words found in the passages, the proof or the context
TRACE_MIN_WORDS = 4    # shorter sentences carry too few content words to judge
DUP_RATIO = 0.8        # word-level similarity of two openings from which they count as one
DUP_WORDS = 5          # same first five words: same opening
NEAR_WORDS = 3         # same first three words: a warning
PASSAGE_MIN = 0.20     # share of a passage's content words the body must reuse, below it the post is not tied
PASSAGE_WARN = 0.35
CLAIM_MIN = 0.30       # same on a claim against its passage
ANGLE_DUP = 0.7        # stem overlap between two angles of a batch
ANGLE_REJECTED = 0.6   # stem overlap with an angle the founder rejected


class Report:
    def __init__(self) -> None:
        self.findings: List[Dict[str, str]] = []
        self.limitations: List[str] = []

    def add(self, level: str, code: str, where: str, message: str) -> None:
        self.findings.append({"level": level, "code": code, "where": where, "message": message})

    def error(self, code: str, where: str, message: str) -> None:
        self.add("error", code, where, message)

    def warn(self, code: str, where: str, message: str) -> None:
        self.add("warning", code, where, message)


# ------------------------------------------------------------------ sources

def load_sources(spec: Dict[str, Any], spec_dir: Path, rep: Report) -> Dict[str, Dict[str, Any]]:
    """The manifest's sources with their text, each one checked against its hash."""
    rel = spec.get("sources_manifest") or "sources/manifest.json"
    path = spec_dir / rel
    if not path.is_file():
        rep.error("source-manifest-missing", "spec", f"{rel} not found: add the raw material with scripts/ingest.py first")
        return {}
    manifest = L.read_json(path)
    errs = L.schema_errors(manifest, L.MANIFEST_SCHEMA)
    if errs:
        rep.error("source-manifest-invalid", "spec", f"{rel}: " + "; ".join(errs[:5]))
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    root = spec_dir.resolve()
    for s in manifest["sources"]:
        where = f"sources.{s['source_id']}"
        file = (spec_dir / s["path"]).resolve()
        if root not in file.parents:
            rep.error("source-outside-run", where, f"{s['path']} is outside the batch folder")
            continue
        if not file.is_file():
            rep.error("source-missing", where, f"{s['path']} not found")
            continue
        if L.sha256_file(file) != s["sha256"]:
            rep.error("source-changed", where, f"{s['path']} changed after ingestion: run ingest.py add --replace if the founder changed it")
            continue
        item = dict(s)
        item["text"] = file.read_text(encoding="utf-8")
        item["quotes"] = {}
        if s["origin"] == "market_signal":
            try:
                sidecar = json.loads(item["text"])
                item["quotes"] = {q["quote_id"]: q for q in sidecar.get("quotes", []) if "quote_id" in q}
                item["valid_until"] = sidecar.get("valid_until")
                item["pains"] = {p.get("pain_id"): p for p in sidecar.get("pains", [])}
            except (json.JSONDecodeError, TypeError, AttributeError):
                rep.error("source-invalid", where, "the market-signal sidecar does not parse")
                continue
            if item.get("valid_until") and spec["date"] > item["valid_until"]:
                rep.warn("market-signal-stale", where, f"past its valid_until {item['valid_until']}: treat its language as dated")
        for sig in s.get("signals", []):
            if sig["code"] == "injection":
                rep.warn("source-injection-signal", where, f"line {sig['line']}: text addressed to an AI, ignored: {sig['excerpt'][:80]}")
        out[s["source_id"]] = item
    return out


def resolve_passages(post: Dict[str, Any], sources: Dict[str, Dict[str, Any]], rep: Report) -> List[Dict[str, Any]]:
    """Check each passage word for word. Returns one entry per passage, in order,
    with its origin, url and line; found=False when it failed."""
    ref = post["ref"]
    out = []
    for i, sp in enumerate(post["source_passages"]):
        where = f"{ref}.source_passages[{i}]"
        entry = {"source_id": sp["source_id"], "passage": sp["passage"], "found": False, "origin": None, "url": None,
                 "line": None, "quote_id": sp.get("quote_id"), "date": None}
        src = sources.get(sp["source_id"])
        out.append(entry)
        if src is None:
            rep.error("source-unknown", where, f"no source {sp['source_id']!r} in the manifest (or it failed its check)")
            continue
        entry["origin"], entry["url"] = src["origin"], src.get("url")
        if L.word_count(sp["passage"]) < L.MIN_PASSAGE_WORDS:
            rep.error("passage-too-short", where, f"{L.word_count(sp['passage'])} words, at least {L.MIN_PASSAGE_WORDS}: a shorter passage proves nothing")
            continue
        if src["origin"] == "market_signal":
            q = src["quotes"].get(sp.get("quote_id") or "")
            if not sp.get("quote_id"):
                rep.error("quote-id-missing", where, "a market-signal passage names its quote_id")
                continue
            if q is None:
                rep.error("quote-unknown", where, f"no quote {sp.get('quote_id')!r} in the sidecar")
                continue
            if q.get("verified") is not True or not q.get("permalink"):
                rep.error("quote-unverified", where, f"quote {q.get('quote_id')} is not verified or has no permalink")
                continue
            status, _ = L.find_passage(q.get("text_verbatim", ""), sp["passage"])
            if status != "found":
                rep.error("quote-mismatch", where, f"the passage is not inside quote {q.get('quote_id')} word for word ({status})")
                continue
            if q.get("speaker") not in (None, "user", "practitioner"):
                rep.warn("quote-speaker", where, f"speaker {q.get('speaker')}: not the persona's voice")
            pain = (src.get("pains") or {}).get(q.get("pain_id"))
            if pain is not None and pain.get("escalated") is False:
                rep.warn("quote-weak-pain", where, "the pain of this quote did not escalate: a hypothesis, not a finding")
            entry["found"] = True
            entry["url"], entry["date"] = q.get("permalink"), q.get("date")
            continue
        status, line = L.find_passage(src["text"], sp["passage"])
        entry["line"] = line
        if status == "found":
            entry["found"] = True
        elif status == "case-changed":
            rep.error("passage-case-changed", where, f"found in {src['path']} line {line} only when ignoring case: copy it as written")
        elif status == "elided":
            rep.error("passage-elided", where, "the passage joins cut parts with an ellipsis: cite each part as its own passage")
        else:
            rep.error("passage-not-found", where, f"not found word for word in {src['path']}: copy the passage, do not rephrase it")
    return out


def cited_text(passages: List[Dict[str, Any]]) -> str:
    return "\n".join(p["passage"] for p in passages if p["found"])


# ------------------------------------------------------------------ claims

def check_claims(post: Dict[str, Any], passages: List[Dict[str, Any]], proof: List[str], lang: str, texts: Dict[str, str],
                 rep: Report, refused: Optional[Dict[int, Tuple[str, str]]] = None) -> Tuple[Dict[str, List[Tuple[int, int]]], List[Dict[str, Any]]]:
    """Each declared claim against its source. Returns the spans of the bodies
    the claims cover, per network, and the ledger rows."""
    ref = post["ref"]
    spans: Dict[str, List[Tuple[int, int]]] = {net: [] for net in texts}
    ledger: List[Dict[str, Any]] = []
    for i, c in enumerate(post.get("claims") or []):
        where = f"{ref}.claims[{i}]"
        rx = L.flex_re(c["text"], ignore_case=True)
        used_in = []
        for net, body in texts.items():
            found = [m.span() for m in rx.finditer(L.nfc(body))]
            if found:
                spans[net].extend(found)
                used_in.append(net)
        if not used_in:
            rep.error("claim-not-in-post", where, f"{c['text']!r} is not in any body: a claim is written as the post writes it")
        tokens = L.number_tokens(c["text"], lang)
        src, kind = c["source"], c["kind"]
        label = src
        if src == "proof":
            idx = c.get("proof_index")
            if idx is None or not 0 <= idx < len(proof):
                rep.error("proof-index", where, f"proof_index {idx} is not in positioning.proof ({len(proof)} items)")
                continue
            if refused and idx in refused:
                pid, why = refused[idx]
                rep.error("proof-not-usable", where, f"positioning.proof[{idx}] ({pid}) is refused: {why}. Take the claim out or list it under dropped")
                continue
            values = L.number_values(proof[idx])
            for t in tokens:
                if t.value not in values:
                    rep.error("number-differs-from-proof", where, f"{t.raw!r} is not in positioning.proof[{idx}]: use it as written, no rounding, no extrapolation")
            if L.overlap(c["text"], proof[idx]) < 0.5:
                rep.warn("claim-far-from-proof", where, f"reads far from positioning.proof[{idx}]: {proof[idx]!r}")
            label = f"positioning.proof[{idx}]"
        elif src in ("quote", "url", "passage"):
            idx = c.get("passage_index")
            if idx is None or not 0 <= idx < len(passages):
                rep.error("passage-index", where, f"passage_index {idx} is not in source_passages ({len(passages)} items)")
                continue
            p = passages[idx]
            if not p["found"]:
                continue  # already reported on the passage
            want = {"quote": "market_signal", "url": "third_party", "passage": "founder"}[src]
            if p["origin"] != want:
                rep.error("claim-source-mismatch", where, f"source {src} needs a {want} passage, passage {idx} is {p['origin']}")
                continue
            values = L.number_values(p["passage"])
            if src == "passage":
                for t in tokens:
                    if t.value in values and L.YEAR_RE.match(t.value):
                        continue
                    rep.error("number-needs-proof", where, f"{t.raw!r} comes from the founder's notes only: a number goes in the post through positioning.proof or a source URL. List it under dropped")
                if kind in NEEDS_PROOF:
                    rep.error("claim-needs-proof", where, f"a {kind} claim cannot rest on notes: it needs positioning.proof or a source URL")
                if L.overlap(c["text"], p["passage"]) < CLAIM_MIN:
                    rep.error("claim-not-in-passage", where, "the claim shares too few words with its passage: write what the founder said")
                label = f"{p['source_id']}, line {p['line']} (user-provided, qualitative)"
            else:
                for t in tokens:
                    if t.value not in values:
                        rep.error("number-differs-from-source", where, f"{t.raw!r} is not in the cited passage")
                if src == "quote" and kind in ("customer", "testimonial", "result", "press", "ranking"):
                    rep.error("quote-as-testimonial", where, "a market-signal quote is a stranger's words about a problem, never proof of the product")
                label = f"{p['source_id']}: {p['url']}" + (f" ({p['date']})" if p.get("date") else "")
        elif src == "structure":
            if kind != "post_count":
                rep.error("claim-source-mismatch", where, "source structure is for kind post_count")
            items = max((L.list_items(b) for net, b in texts.items() if net in used_in), default=0)
            for t in tokens:
                if t.value != str(items):
                    rep.error("list-count-mismatch", where, f"{t.raw!r} announces a list, the body has {items} items")
            label = "the post's own list"
        else:  # none
            if kind != "idiom" or not (c.get("reason") or "").strip():
                rep.error("claim-unsourced", where, "source none is only for a number word used as an idiom, with a reason")
            for t in tokens:
                if not t.is_word:
                    rep.error("idiom-digit", where, f"{t.raw!r} is a digit: a digit is never an idiom")
            rep.warn("idiom-number", where, f"{c['text']!r} declared as an idiom: {c.get('reason', '')}")
            label = f"not a claim: {c.get('reason', '')}"
        ledger.append({"ref": ref, "claim": c["text"], "kind": kind, "used_in": used_in, "source": label})
    return spans, ledger


def covered(pos: Tuple[int, int], spans: List[Tuple[int, int]]) -> bool:
    return any(a <= pos[0] and pos[1] <= b for a, b in spans)


def check_body_claims(post: Dict[str, Any], net: str, body: str, spans: List[Tuple[int, int]], passages: List[Dict[str, Any]],
                      proof: List[str], allowed: Set[str], lang: str, rep: Report) -> None:
    """What the body says and the claims did not declare."""
    where = f"{post['ref']}.{net}"
    text = L.nfc(body)
    cited = cited_text(passages)
    proof_text = "\n".join(proof)
    allowed_values = L.number_values(cited) | L.number_values(proof_text)

    enums = L.enumeration_spans(text)
    for t in L.number_tokens(text, lang):
        if covered((t.start, t.end), enums) or covered((t.start, t.end), spans):
            continue
        if L.YEAR_RE.match(t.value) and t.value in allowed_values:
            continue  # a date from a cited passage or the proof is not a metric
        rep.error("unsourced-number", where, f"{t.raw!r} has no declared claim: trace it to positioning.proof or a source URL, or take it out")

    lang_key = lang if lang in RANKING_RE else "en"
    for rx, code, hint in ((RANKING_RE, "ranking-unsourced", "a ranking or superlative needs positioning.proof"),
                           (CROWD_RE, "crowd-claim-unsourced", "a claim about a whole group needs a source URL or the founder's own passage")):
        for m in rx[lang_key].finditer(text):
            if not covered(m.span(), spans) and not fold_in(m.group(0), proof_text):
                rep.error(code, where, f"{m.group(0)!r}: {hint}")

    for m in TIME_RE[lang_key].finditer(text):
        if not fold_in(m.group(0), cited + "\n" + proof_text):
            rep.error("time-marker-not-in-source", where, f"{m.group(0)!r} is not in the cited passages: an anecdote keeps the date the founder gave")

    for m in CLIENT_RE[lang_key].finditer(text):
        stem = L.fold(m.group(1))[:5]
        if stem not in L.fold(cited + "\n" + proof_text):
            rep.error("client-not-in-source", where, f"{m.group(0)!r}: no cited passage mentions this person. Never invent a client")

    for m in QUOTED_RE.finditer(text):
        quoted = next(g for g in m.groups() if g)
        if L.word_count(quoted) < 3:
            continue
        if not any(L.flex_re(quoted, ignore_case=True).search(L.nfc(p["passage"])) for p in passages if p["found"]):
            rep.error("quote-not-in-source", where, f"{quoted[:70]!r} is in quotation marks and not in a cited passage: quoted words are real words")

    cited_words = {w.lower() for w in re.findall(r"[\w’'-]+", cited)}
    lowered_body = {w for w in re.findall(r"[\w’'-]+", text) if w == w.lower()}
    for m in NAME_RE.finditer(text):
        before = text[:m.start()]
        token = re.sub(r"(?:['’]s|['’])$", "", m.group(0)).lower()
        if not before or SENTENCE_START_RE.search(before):
            known = token in cited_words or token in allowed or token in lowered_body or token in ALWAYS_ALLOWED
            if len(token) >= 4 and not known and token not in STARTERS and token not in L.STOP:
                rep.warn("possible-name", where, f"{m.group(0)!r} opens a sentence and no source holds it: if it is a name, cite it or take it out")
            continue
        if token in ALWAYS_ALLOWED or token in allowed:
            continue
        if token in cited_words:
            rep.warn("third-party-name", where, f"{m.group(0)!r} comes from the notes and is not in project-context: a tool is fine, a client needs positioning.proof")
        else:
            rep.error("name-not-in-sources", where, f"{m.group(0)!r} is in no cited passage and not in project-context. Never invent a name")

    if PLACEHOLDER_RE.search(text):
        rep.error("unresolved-placeholder", where, "a placeholder would be published as is: a post carries no signature and no template slot")
    if EMAIL_RE.search(text) or PHONE_RE.search(text):
        rep.error("personal-data", where, "an e-mail address or a phone number in a post: take it out")


def fold_in(needle: str, haystack: str) -> bool:
    return L.fold(" ".join(needle.split())) in L.fold(" ".join(haystack.split()))


# ------------------------------------------------------------------ hooks, angles, openings

def check_traced(post: Dict[str, Any], net: str, body: str, reference: str, lang: str, rep: Report) -> None:
    """A sentence no cited passage, proof item or context field echoes. When it
    tells something that happened, it is the invention this agent exists to stop."""
    where = f"{post['ref']}.{net}"
    event = EVENT_RE.get(lang, EVENT_RE["en"])
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", strip_quoted(body)):
        stem_count = len(L.stems(sentence))
        if stem_count < TRACE_MIN_WORDS or L.overlap(sentence, reference) >= TRACE_MIN:
            continue
        if event.search(sentence):
            rep.error("untraced-event", where, f"{sentence.strip()[:90]!r} reports an event or a result, and no cited passage holds it")
        else:
            rep.warn("untraced-sentence", where, f"{sentence.strip()[:90]!r} echoes no cited passage: fine as the founder's opinion, check it is one")


def check_hook(post: Dict[str, Any], primary: str, spans: List[Tuple[int, int]], passages: List[Dict[str, Any]], lang: str, rep: Report) -> None:
    """The declared hook type has to be what the first line does."""
    where = post["ref"]
    hook = post["hook_type"]
    line = L.first_line(primary)
    start = L.nfc(primary).find(L.nfc(line))
    origins = {p["origin"] for p in passages if p["found"]}
    if hook == "question" and "?" not in line:
        rep.error("hook-type-mismatch", where, "hook_type question: the first line asks nothing")
    if hook == "number":
        toks = L.number_tokens(line, lang)
        if not toks:
            rep.error("hook-type-mismatch", where, "hook_type number: the first line holds no number")
        elif not any(covered((start + t.start, start + t.end), spans) for t in toks):
            rep.error("hook-type-mismatch", where, "hook_type number: the number of the first line has no claim")
    if hook == "customer_words" and "market_signal" not in origins:
        rep.error("hook-type-mismatch", where, "hook_type customer_words needs a verified market-signal passage")
    if hook in ("scene", "confession", "decision") and "founder" not in origins:
        rep.error("hook-type-mismatch", where, f"hook_type {hook} tells something the founder did: it needs a founder passage")


def check_tied(post: Dict[str, Any], primary: str, passages: List[Dict[str, Any]], rep: Report) -> None:
    found = [p for p in passages if p["found"]]
    if not found:
        return
    if not any(p["origin"] in ("founder", "market_signal") for p in found):
        rep.error("post-needs-founder-passage", post["ref"], "a post rests on the founder's material or a verified market-signal quote: a third-party page only backs a fact")
    best = max(L.overlap(p["passage"], primary) for p in found)
    if best < PASSAGE_MIN:
        rep.error("post-not-tied-to-passage", post["ref"], f"the body reuses {int(best * 100)} % of its best passage: cite what the post comes from")
    elif best < PASSAGE_WARN:
        rep.warn("thin-source-link", post["ref"], f"the body reuses {int(best * 100)} % of its best passage: check that the post says what the founder said")


def clash(a: List[str], b: List[str]) -> Optional[str]:
    """'dup' when two openings count as one, 'near' when they start alike."""
    if not a or not b:
        return None
    if len(a) >= DUP_WORDS and a[:DUP_WORDS] == b[:DUP_WORDS]:
        return "dup"
    if difflib.SequenceMatcher(None, a, b).ratio() >= DUP_RATIO:
        return "dup"
    if len(a) >= NEAR_WORDS and a[:NEAR_WORDS] == b[:NEAR_WORDS]:
        return "near"
    return None


def check_batch_variety(spec: Dict[str, Any], rep: Report) -> None:
    posts = spec["posts"]
    n = len(posts)
    cap = max(1, math.ceil(n / 3))
    for field, code in (("hook_type", "hook-type-overused"), ("angle_type", "angle-type-overused")):
        counts: Dict[str, int] = {}
        for p in posts:
            counts[p[field]] = counts.get(p[field], 0) + 1
        for value, count in counts.items():
            if count > cap:
                rep.error(code, "batch", f"{field} {value} is used {count} times in {n} posts, at most {cap}: vary the batch")
    for i, a in enumerate(posts):
        for b in posts[i + 1:]:
            if L.jaccard(a["angle"], b["angle"]) >= ANGLE_DUP:
                rep.error("duplicate-angle", f"{a['ref']}, {b['ref']}", "these two posts have the same angle")
            shared = {s["passage"] for s in a["source_passages"]} & {s["passage"] for s in b["source_passages"]}
            if shared:
                rep.warn("same-passage", f"{a['ref']}, {b['ref']}", "these two posts cite the same passage")
            for na, va in (a.get("variants") or {}).items():
                for nb, vb in (b.get("variants") or {}).items():
                    verdict = clash(L.opening_words(va.get("text", "")), L.opening_words(vb.get("text", "")))
                    if verdict == "dup":
                        rep.error("duplicate-opening", f"{a['ref']}.{na}, {b['ref']}.{nb}", f"same opening: {L.first_line(va.get('text', ''))[:70]!r}")
                    elif verdict == "near":
                        rep.warn("similar-opening", f"{a['ref']}.{na}, {b['ref']}.{nb}", f"openings start alike: {L.first_line(va.get('text', ''))[:70]!r}")


def load_past(project: Optional[str], refs: Set[str], voice: Optional[Dict[str, Any]], queue_path: Optional[Path],
              rep: Report) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Past openings: project memory, the publication queue, the founder's past posts."""
    paths = L.project_paths(project)
    past: List[Dict[str, Any]] = []
    origins: List[str] = []
    rows, broken = L.read_jsonl(paths["posts"])
    if broken:
        rep.warn("memory-broken-line", "memory/posts.jsonl", f"unreadable lines skipped: {broken}")
    if rows:
        origins.append(f"memory/posts.jsonl ({len(rows)} lines)")
    for r in rows:
        if r.get("ref") in refs and r.get("status") != "rejected":
            continue  # this batch's own earlier pass
        past.append({"origin": "memory", "ref": r.get("ref"), "network": r.get("network"), "opening": r.get("opening", ""),
                     "status": r.get("status"), "angle": r.get("angle", ""), "reason": r.get("reason", "")})
    queue = queue_path or paths["queue"]
    q, problem = L.read_optional_json(queue)
    if problem:
        rep.warn("queue-unreadable", "content-publisher/queue.json", problem)
    if isinstance(q, dict):
        items = [i for i in q.get("items", []) if isinstance(i, dict)]
        kept = 0
        for it in items:
            ref = str(it.get("id", "")).rsplit(".", 1)[0]
            if ref in refs or not it.get("text"):
                continue
            kept += 1
            past.append({"origin": "queue", "ref": ref, "network": it.get("network"), "opening": L.first_line(it["text"]),
                         "status": it.get("status"), "angle": "", "reason": ""})
        if kept:
            origins.append(f"content-publisher/queue.json ({kept} items)")
    if project and isinstance(voice, dict):
        count = 0
        for s in voice.get("sources", []) or []:
            if not isinstance(s, dict) or s.get("channel") != "post" or not s.get("path"):
                continue
            file = Path(project) / "project-context" / s["path"]
            if file.is_file():
                count += 1
                past.append({"origin": "voice exemplar", "ref": s["path"], "network": None,
                             "opening": L.first_line(file.read_text(encoding="utf-8", errors="replace")),
                             "status": "published", "angle": "", "reason": ""})
        if count:
            origins.append(f"voice exemplars ({count} posts)")
    return past, origins


def check_against_past(spec: Dict[str, Any], past: List[Dict[str, Any]], rep: Report) -> None:
    for p in spec["posts"]:
        for net, var in (p.get("variants") or {}).items():
            words = L.opening_words(var.get("text", ""))
            where = f"{p['ref']}.{net}"
            for old in past:
                verdict = clash(words, L.folded_words(old["opening"])[:25])
                if verdict == "dup" and old["status"] == "rejected":
                    rep.error("rejected-opening", where, f"same opening as {old['ref']}, rejected by the founder: {old['reason'][:80]}")
                elif verdict == "dup":
                    rep.error("duplicate-past-opening", where, f"same opening as {old['ref']} ({old['origin']}): {old['opening'][:70]!r}")
                elif verdict == "near":
                    rep.warn("similar-past-opening", where, f"starts like {old['ref']} ({old['origin']}): {old['opening'][:70]!r}")
        for old in past:
            if old["status"] == "rejected" and old["angle"] and L.jaccard(p["angle"], old["angle"]) >= ANGLE_REJECTED:
                rep.error("rejected-angle", p["ref"], f"same angle as {old['ref']}, rejected by the founder: {old['reason'][:80]}")
                break


# ------------------------------------------------------------------ voice

def resolve_address(lang: str, config: Dict[str, Any], decisions: List[Dict[str, str]]) -> Tuple[Optional[str], str]:
    defaults = L.read_json(L.VOICE_DEFAULTS)["address"].get(lang)
    if not defaults:
        return None, "no default for this language"
    if config.get("address"):
        return config["address"], "config.json"
    chosen = L.enforced_values(decisions, "address")
    if chosen:
        return chosen[-1][0], f"decision {chosen[-1][1]}"
    return defaults["form"], "default"


def strip_quoted(text: str) -> str:
    return QUOTED_RE.sub(" ", text)


def check_address(spec: Dict[str, Any], form: Optional[str], voice: Optional[Dict[str, Any]], origin: str, rep: Report) -> None:
    if not form:
        return
    rule = L.read_json(L.VOICE_DEFAULTS)["address"][spec["language"]]
    pattern = rule["patterns"].get(form)
    if not pattern:
        return
    rx = re.compile(pattern, re.I)
    for p in spec["posts"]:
        for net, var in (p.get("variants") or {}).items():
            m = rx.search(strip_quoted(var.get("text", "")))
            if m:
                rep.error(f"address-{'tu' if form == 'vous' else 'vous'}", f"{p['ref']}.{net}", f"{m.group(0)!r}: {rule['messages'][form]}")
    measured = (((voice or {}).get("metrics") or {}).get("address") or {}).get("form")
    if isinstance(voice, dict) and measured in ("tu", "vous") and measured != form and origin == "default":
        rep.warn("address-differs-from-voice", "voice", f"the founder's texts use {measured}; posts stay on {form} until address is set in config.json")


def sentence_lengths(text: str) -> List[int]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text)
    return [n for n in (len(L.words_of(s)) for s in parts) if n]


def check_voice(spec: Dict[str, Any], voice: Optional[Dict[str, Any]], problem: Optional[str], rep: Report) -> Dict[str, Any]:
    """Voice pack rules the script can measure. Rules enforced by the gate run
    through the project pack; the rest goes to the fresh reviewer."""
    if problem:
        rep.warn("voice-pack-unreadable", "voice", problem)
    if not isinstance(voice, dict):
        rep.limitations.append("No voice pack at project-context/voice/voice.json: the founder's voice was not measured, only the writing gate, the banned words of context.json and the default address form ran. Run project-context with the founder's own texts to add it.")
        return {"status": "none", "rules": 0}
    errs = L.schema_errors(voice, L.VOICE_SCHEMA)
    if errs:
        rep.warn("voice-pack-invalid", "voice", "voice.json does not match its schema: " + "; ".join(errs[:3]))
    metrics = voice.get("metrics") or {}
    if metrics.get("low_sample"):
        rep.limitations.append("The voice pack rests on a small sample (under 600 words or 3 texts): its rules are a first draft.")
    if (voice.get("calibration") or {}).get("status") == "conflict":
        rep.limitations.append("The voice pack holds a calibration conflict: a banned word appears in the founder's own texts. Ask the founder.")
    sw = metrics.get("sentence_words") or {}
    per = metrics.get("per_1000_words") or {}
    rules = voice.get("rules") if isinstance(voice.get("rules"), list) else []
    enforced_by_gate = [r.get("id") for r in rules if isinstance(r, dict) and r.get("enforced_by")]
    measured = {"sentence-length", "questions", "exclamation", "emoji", "speaker"}
    ids = {r.get("id") for r in rules if isinstance(r, dict)}
    banned = [b.get("text", "") for b in voice.get("banned", []) if isinstance(b, dict)]
    examples = [e.get("text", "") for e in voice.get("examples", []) if isinstance(e, dict)]
    person = metrics.get("person") or {}
    for p in spec["posts"]:
        for net, var in (p.get("variants") or {}).items():
            where = f"{p['ref']}.{net}"
            text = var.get("text", "")
            lower = L.fold(text)
            words = max(1, len(L.words_of(text)))
            for b in banned:
                if b and re.search(r"(?<!\w)" + re.escape(L.fold(b)) + r"(?!\w)", lower):
                    rep.error("voice-banned", where, f"{b!r} is banned by the voice pack")
            for ex in examples:
                if L.word_count(ex) >= 6 and L.flex_re(ex, ignore_case=True).search(L.nfc(text)):
                    rep.error("voice-example-copied", where, f"{ex[:60]!r} is an example of the register, never copy for a new post")
            lengths = sentence_lengths(text)
            if lengths and sw.get("max") and max(lengths) > sw["max"]:
                rep.warn("voice-sentence-too-long", where, f"a sentence of {max(lengths)} words, the founder's longest is {sw['max']:g}")
            if len(lengths) >= 3 and sw.get("p75"):
                median = sorted(lengths)[len(lengths) // 2]
                if median > sw["p75"]:
                    rep.warn("voice-sentences-long", where, f"median sentence of {median} words, three in four of the founder's are under {sw['p75']:g}")
            if per.get("question") == 0 and "?" in text:
                rep.warn("voice-question", where, "the founder's texts ask the reader no question")
            if per.get("exclamation", 0) and text.count("!") / words * 1000 > 3 * per["exclamation"]:
                rep.warn("voice-exclamation", where, "more exclamation marks than the founder writes")
            if per.get("emoji", 0) and len(EMOJI_RE.findall(text)) / words * 1000 > 3 * per["emoji"]:
                rep.warn("voice-emoji", where, "more emoji than the founder writes")
            singular = len(re.findall(r"\b(?:I|my|je|j['’]|mon|ma|mes)\b", text))
            plural = len(re.findall(r"\b(?:we|our|nous|notre|nos)\b", text, re.I))
            if person.get("first_plural", 0) >= 0.6 and singular > plural:
                rep.warn("voice-speaker", where, "the founder speaks as we in their texts; this post speaks as I")
            if person.get("first_singular", 0) >= 0.6 and plural > singular:
                rep.warn("voice-speaker", where, "the founder speaks as I in their texts; this post speaks as we")
    return {"status": "pack", "rules": len(rules), "by_gate": enforced_by_gate, "by_script": sorted(ids & measured),
            "by_reviewer": sorted(str(i) for i in ids - measured - set(enforced_by_gate)), "low_sample": bool(metrics.get("low_sample"))}


# ------------------------------------------------------------------ main check

def context_allowed_names(context: Dict[str, Any], voice: Optional[Dict[str, Any]], config: Dict[str, Any]) -> Set[str]:
    """Words of project-context and the config: names that need no passage."""
    bits: List[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            bits.append(value)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)

    walk({k: v for k, v in context.items() if k != "voice"})
    if isinstance(voice, dict) and voice.get("brand_name"):
        bits.append(str(voice["brand_name"]))
    names = {w.lower() for w in re.findall(r"[\w’'-]+", "\n".join(bits))}
    names |= {str(n).lower() for n in config.get("allowed_names", []) or []}
    return names


def check_link(post: Dict[str, Any], context: Dict[str, Any], sources: Dict[str, Dict[str, Any]], rep: Report) -> None:
    link = post.get("link")
    if not link:
        return
    host = (urlparse(link).hostname or "").lower()
    home = (urlparse(str(context.get("url") or "")).hostname or "").lower()
    if home and (host == home or host.endswith("." + home)):
        return
    if any(link in s["text"] for s in sources.values()):
        return
    rep.error("link-unsourced", post["ref"], f"{link} is not on the founder's site and not in the raw material: a link is never invented")


def check_body_links(post: Dict[str, Any], net: str, body: str, pub_variants: Any, rep: Report) -> None:
    rx = re.compile(rf"(?<![@\w./-])[a-z0-9-]+\.(?:{pub_variants.TLDS}|example|test)\b", re.I)
    for m in rx.finditer(body):
        rep.error("bare-domain-in-body", f"{post['ref']}.{net}", f"{m.group(0)!r} may become a link: the body holds no address, the link goes to post.link")


def check_language(spec: Dict[str, Any], expected: Optional[str], origin: str, rep: Report) -> None:
    lang = spec["language"]
    if expected and expected.split("-")[0].lower() != lang:
        rep.error("language-mismatch", "spec", f"the batch is in {lang}, the founder's language is {expected} ({origin})")
    detect = L.language_detector()
    if lang not in ("en", "fr") or detect is None:
        return
    for p in spec["posts"]:
        for net, var in (p.get("variants") or {}).items():
            text = var.get("text", "")
            if detect(text) != lang:
                where = f"{p['ref']}.{net}"
                if len(L.words_of(text)) >= 25:
                    rep.error("wrong-language", where, f"the body does not read as {lang}")
                else:
                    rep.warn("language-unsure", where, f"the body may not read as {lang}")


def check(spec_path: Path, project: Optional[str] = None, config: Optional[Dict[str, Any]] = None,
          queue: Optional[str] = None, gate: bool = True) -> Dict[str, Any]:
    pub_variants, pub_common = L.publisher()
    spec = L.read_json(spec_path)
    rep = Report()
    errs = L.schema_errors(spec, L.SPEC_SCHEMA)
    if errs:
        for e in errs:
            rep.error("schema", "spec", e)
        return finish(rep, {}, [], [], {}, {}, spec_path)
    config = config or {}
    paths = L.project_paths(project)
    context_data, problem = L.read_optional_json(paths["context"])
    if problem:
        rep.warn("context-unreadable", "project-context", problem)
    context: Dict[str, Any] = context_data if isinstance(context_data, dict) else {}
    if not context:
        rep.limitations.append("No project-context: no allowed claims, so the batch is written proof-free and names come from the cited passages only.")
    proof_items = proof_lib.load_proof(context)
    proof = [proof_lib.proof_text(p) for p in proof_items]
    refused: Dict[int, Tuple[str, str]] = {}
    for p in proof_items:
        ok, why = proof_lib.usable(p, PROOF_SCOPE, None, str(paths["context"].parent) if paths["context"] else None)
        if not ok:
            refused[p.index] = (p.id, why)
            rep.warn("proof-refused", f"positioning.proof[{p.index}]", f"{p.id}: {why}")
    usable_proof = [t for i, t in enumerate(proof) if i not in refused]
    if refused:
        context = json.loads(json.dumps(context))
        context["positioning"]["proof"] = usable_proof
    if context and not proof:
        rep.limitations.append("positioning.proof is empty: every number stays out of this batch. Add proven facts to project-context to use them.")
    voice, voice_problem = L.read_optional_json(paths["voice"])
    decisions = L.active_decisions(paths["decisions"])
    lang = spec["language"]
    allowed = context_allowed_names(context, voice if isinstance(voice, dict) else None, config)
    sources = load_sources(spec, spec_path.parent, rep)

    refs = [p["ref"] for p in spec["posts"]]
    all_ledger: List[Dict[str, Any]] = []
    passage_rows: List[Dict[str, Any]] = []
    settings = json.loads(json.dumps(pub_common.DEFAULT_SETTINGS))
    settings["x_allow_thread"] = bool(config.get("x_allow_thread"))

    refused_hooks = dict(L.enforced_values(decisions, "hook"))
    refused_angles = dict(L.enforced_values(decisions, "angle-type"))
    for hook, did in L.enforced_values(decisions, "hook", status="proposed"):
        rep.warn("decision-proposed", "memory", f"{did} proposes to avoid hook type {hook}: confirm or drop it")

    for post in spec["posts"]:
        ref = post["ref"]
        texts = {net: (post["variants"].get(net) or {}).get("text", "") for net in post["networks"]}
        texts = {net: t for net, t in texts.items() if t.strip()}
        passages = resolve_passages(post, sources, rep)
        # What else the audience reads: the first comment and the line before the link.
        published = dict(texts)
        if (post["variants"].get("linkedin") or {}).get("first_comment"):
            published["linkedin.first_comment"] = post["variants"]["linkedin"]["first_comment"]
        if post.get("link_note"):
            published["link_note"] = post["link_note"]
        spans, ledger = check_claims(post, passages, proof, lang, published, rep, refused)
        all_ledger.extend(ledger)
        for p in passages:
            passage_rows.append({"ref": ref, "source_id": p["source_id"], "line": p["line"], "url": p["url"],
                                 "date": p["date"], "passage": p["passage"], "found": p["found"]})
        reference = "\n".join([cited_text(passages)] + usable_proof + [json.dumps(context, ensure_ascii=False)])
        for net, body in published.items():
            check_body_claims(post, net, body, spans[net], passages, usable_proof, allowed, lang, rep)
        for net, body in texts.items():
            check_body_links(post, net, body, pub_variants, rep)
            check_traced(post, net, body, reference, lang, rep)
        primary_net = "linkedin" if "linkedin" in texts else (next(iter(texts), None))
        if primary_net:
            check_hook(post, texts[primary_net], spans[primary_net], passages, lang, rep)
            if primary_net == "linkedin":
                check_tied(post, texts["linkedin"], passages, rep)
        check_link(post, context, sources, rep)
        if post["hook_type"] in refused_hooks:
            rep.error("decision-hook-refused", ref, f"hook type {post['hook_type']} is refused by {refused_hooks[post['hook_type']]}")
        if post["angle_type"] in refused_angles:
            rep.error("decision-angle-refused", ref, f"angle type {post['angle_type']} is refused by {refused_angles[post['angle_type']]}")

    # Limits, link placement and the writing gate are content-publisher's own code.
    compiled = L.compile_posts(spec)
    lint = pub_variants.lint_spec(compiled, spec_path.parent, settings, project, gate=gate)
    for f in lint["findings"]:
        rep.add(f["level"], f["code"], f["where"], f["message"])
    gate_info = lint.get("gate") or {}
    if gate and gate_info.get("ran"):
        summary = pub_variants.writing_gate([("summary", lang, spec["summary"])], project)
        for res in summary.get("results", {}).values():
            for f in res["findings"]:
                rep.add("error" if f["level"] == "BLOCK" else "warning", f"writing-gate:{f['code']}", "summary", f"{f['match']!r}: {f['message']}")
    elif gate:
        rep.limitations.append("Writing gate: manual (the shared gate was not found). Check the bodies against the family table of the writing-gate skill.")
    elif not gate:
        rep.limitations.append("Writing gate: skipped by --no-gate. This spec cannot be built.")

    check_batch_variety(spec, rep)
    past, past_origins = load_past(project, set(refs), voice if isinstance(voice, dict) else None, Path(queue) if queue else None, rep)
    check_against_past(spec, past, rep)
    if not past_origins:
        rep.limitations.append("No past post on record (memory/posts.jsonl, queue.json, voice exemplars): openings were compared inside this batch only.")

    expected = config.get("language") or (voice.get("language") if isinstance(voice, dict) else None) or (context.get("voice") or {}).get("language")
    check_language(spec, expected, "config, voice pack or context.json", rep)
    form, origin = resolve_address(lang, config, decisions)
    check_address(spec, form, voice if isinstance(voice, dict) else None, origin, rep)
    voice_info = check_voice(spec, voice if isinstance(voice, dict) else None, voice_problem, rep)
    for item in spec.get("limitations", []) or []:
        rep.limitations.append(item)

    limits = {}
    lim = pub_common.limits()
    for post in spec["posts"]:
        limits[post["ref"]] = {}
        for net in post["networks"]:
            body = (post["variants"].get(net) or {}).get("text", "")
            limits[post["ref"]][net] = f"{pub_variants.length(body, net, lim)}/{lim[net]['text_max']}"
    info = {"address": {"form": form, "origin": origin}, "voice": voice_info, "past": {"compared": len(past), "origins": past_origins},
            "gate": {"ran": bool(gate_info.get("ran"))}, "decisions_applied": len([d for d in decisions if d["status"].startswith("active")]),
            "proof_items": len(proof), "project_context": bool(context),
            "proof_refused": [{"index": i, "id": pid, "reason": why} for i, (pid, why) in sorted(refused.items())]}
    return finish(rep, info, all_ledger, passage_rows, limits, sources, spec_path)


def finish(rep: Report, info: Dict[str, Any], ledger: List[Dict[str, Any]], passages: List[Dict[str, Any]],
           limits: Dict[str, Any], sources: Dict[str, Dict[str, Any]], spec_path: Path) -> Dict[str, Any]:
    errors = sum(f["level"] == "error" for f in rep.findings)
    signals = [{"source_id": sid, **sig} for sid, s in sources.items() for sig in s.get("signals", [])]
    return {"status": "fail" if errors else "pass", "spec": spec_path.name,
            "counts": {"error": errors, "warning": len(rep.findings) - errors},
            "findings": rep.findings, "info": info, "ledger": ledger, "passages": passages, "limits": limits,
            "signals": signals, "limitations": rep.limitations,
            "sources": [{k: s.get(k) for k in ("source_id", "path", "kind", "origin", "sha256", "url")} for s in sources.values()]}


def load_config(path: Optional[str], project: Optional[str]) -> Dict[str, Any]:
    if path:
        data = L.read_json(Path(path))
    elif project and (Path(project) / L.AGENT_NAME / "config.json").is_file():
        data = L.read_json(Path(project) / L.AGENT_NAME / "config.json")
    else:
        return {}
    if not isinstance(data, dict):
        raise L.UsageError(f"{path}: the config is not a JSON object")
    return data


def print_report(report: Dict[str, Any]) -> None:
    for f in report["findings"]:
        print(f"  {f['level'].upper():<7} {f['code']:<34} {f['where']}: {f['message']}")
    for item in report["limitations"]:
        print(f"  LIMIT   {item}")
    print(f"\nCheck: {report['status'].upper()} ({report['counts']['error']} errors, {report['counts']['warning']} warnings)")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="posts-spec.json")
    ap.add_argument("--project", help="project folder: context, voice pack, memory, writing-gate project pack")
    ap.add_argument("--config", help="the agent's config.json (default: <project>/founder-content-writer/config.json)")
    ap.add_argument("--queue", help="queue.json to compare openings with (default: <project>/content-publisher/queue.json)")
    ap.add_argument("--no-gate", action="store_true", help="skip the writing gate while drafting (build_batch.py never does)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--out", help="also write the JSON report to this file")
    a = ap.parse_args(argv)
    try:
        report = check(Path(a.spec), a.project, load_config(a.config, a.project), a.queue, gate=not a.no_gate)
    except L.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return L.EXIT_USAGE
    if a.out:
        L.write_json_atomic(Path(a.out), report)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(a.spec)
        print_report(report)
    return L.EXIT_OK if report["status"] == "pass" else L.EXIT_CHECK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
