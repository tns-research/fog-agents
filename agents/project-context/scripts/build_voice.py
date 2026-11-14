#!/usr/bin/env python3
"""build_voice.py: measure the founder's own texts and write the voice pack.

Input: texts the founder wrote (posts, about page, emails, newsletters), as
files, folders or public URLs. The script copies them verbatim to
voice/exemplars/, measures them, and writes two files under
<project-context>/voice/:

  voice.json  the voice pack (assets/voice-schema.json): measures, rules written
              as facts with their evidence, verbatim example sentences, banned
              words, and the calibration record
  rules.json  the writing-gate project pack (shared/schemas/copy-rules.schema.json)
              that enforces what can be checked mechanically: brand casing,
              form of address, exclamation marks, emoji, banned words

Measures: sentence length (median, quartiles, p90), paragraph length, share of
each grammatical person, form of address (you; tu or vous in French),
punctuation and emoji per 1000 words, contractions (English), brand casing,
most frequent content words.

Calibration: every exemplar is run through the shared writing gate
(shared/skills/writing-gate) with the generated project pack. The founder's own
texts must pass at 0 BLOCK. A generated rule that blocks the founder's text is
dropped; a shared rule that blocks it is lowered to WARN for this project (or
disabled when its repetition escalates it), and the change is recorded with
the founder's sentence. A banned word found in the founder's own text is a
conflict: nothing is changed, exit 1, ask the founder.

Usage:
    python3 build_voice.py --out <project>/project-context post.md about.md https://example.com/about
    python3 build_voice.py --out <dir> --channel email ./emails/ --ban synergy --ban "game changer"
    python3 build_voice.py --out <dir>                 # rebuild from voice/exemplars/
    python3 build_voice.py --out <dir> --check         # re-run the calibration only

Exit codes:
    0  voice pack written, the founder's texts pass at 0 BLOCK (pass or adjusted)
    1  conflict: a banned word appears in the founder's own texts (--check: a BLOCK remains)
    2  usage error, unreadable input, or a written file fails its schema
    3  not enough text: under 80 words of founder text
    4  the shared writing gate was not found next to agents/
"""

from __future__ import annotations

import argparse
import datetime as dt
import html.parser
import json
import re
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GATE = REPO / "shared" / "skills" / "writing-gate" / "scripts"
VALIDATOR = REPO / "shared" / "scripts" / "validate_json.py"
RULES_SCHEMA = REPO / "shared" / "schemas" / "copy-rules.schema.json"
VOICE_SCHEMA = HERE.parent / "assets" / "voice-schema.json"

MIN_WORDS = 80            # below this the measures mean nothing
LOW_SAMPLE_WORDS = 600    # below this (or under 3 texts) the pack is flagged low_sample
MAX_EXAMPLES = 8
MAX_EXAMPLES_PER_SOURCE = 3
CALIBRATION_ROUNDS = 6
GENERATED_CODES = {"brand-casing", "address-tu", "address-vous", "no-exclamation", "no-emoji"}
CHANNELS = ("post", "about", "email", "newsletter", "site", "talk", "other")
UA = "Mozilla/5.0 (project-context build_voice)"

EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
TOKEN_RE = re.compile(r"[a-zà-ÿœæ]+'|[a-zà-ÿœæ0-9]+(?:'[a-z]+)?", re.I)
PRONOUNS = {
    "en": {
        "first_singular": {"i", "me", "my", "mine", "myself", "i'm", "i've", "i'd", "i'll"},
        "first_plural": {"we", "us", "our", "ours", "ourselves", "we're", "we've", "we'd", "we'll"},
        "second": {"you", "your", "yours", "yourself", "yourselves", "you're", "you've", "you'd", "you'll"},
    },
    "fr": {
        "first_singular": {"je", "j'", "me", "m'", "moi", "mon", "ma", "mes"},
        "first_plural": {"nous", "notre", "nos"},
        "on": {"on"},
        "tu": {"tu", "te", "t'", "toi", "ton", "ta", "tes"},
        "vous": {"vous", "votre", "vos"},
    },
}
STOPWORDS = {
    "en": set("""the and that this with from have they them their there what when which while will would your yours
        about into over than then just also been being were here more most much some such only very each other
        could should does done doing because before after where those these ours mine itself it's isn't don't
        can't won't we're you're they're we've you've i've we'll you'll i'm we'd you'd""".split()),
    "fr": set("""les des une est pour dans que qui pas sur avec vous nous cette sont aux mais plus par leur votre
        notre vos nos ces ses elle elles ils sans tout tous toute toutes comme fait faire être avoir était sont
        aussi bien encore entre depuis quand alors donc chez dont même mêmes très peut leurs""".split()),
}


# --- Input ------------------------------------------------------------------------

class _TextExtractor(html.parser.HTMLParser):
    """Visible text of an HTML page: paragraphs, list items, headings, quotes;
    navigation, header, footer, forms and scripts skipped."""
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button", "select", "template"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "dd", "figcaption", "td"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.block: Optional[List[str]] = None
        self.blocks: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK and not self.skip:
            self._flush()
            self.block = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.block is not None and not self.skip:
            self.block.append(data)

    def _flush(self) -> None:
        if self.block:
            text = " ".join(" ".join(self.block).split())
            if len(text.split()) >= 4:
                self.blocks.append(text)
        self.block = None


def check_fetch_url(url: str) -> None:
    """Raise ValueError unless url is http or https (never file://, ftp://, ...)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError(f"refused {url[:120]!r}: only http and https URLs are fetched")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        check_fetch_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def fetch_url_text(url: str) -> str:
    check_fetch_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    with _OPENER.open(req, timeout=30) as resp:
        raw = resp.read(4 * 1024 * 1024).decode("utf-8", errors="ignore")
    p = _TextExtractor()
    p.feed(raw)
    p._flush()
    return "\n\n".join(p.blocks)


def frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta = {}
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta, text[end + 4:].lstrip("\n")
    return {}, text


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "text"


def collect_inputs(inputs: List[str], ex_dir: Path, channel: str, today: str) -> List[Path]:
    """Copy every input into voice/exemplars/ with a frontmatter; return the paths."""
    ex_dir.mkdir(parents=True, exist_ok=True)
    out: List[Path] = []
    files: List[Tuple[str, str, Dict[str, str]]] = []  # (name, body, meta)
    for item in inputs:
        if re.match(r"^https?://", item):
            body = fetch_url_text(item)
            files.append((slug(re.sub(r"^https?://", "", item)), body, {"source": item, "channel": channel if channel != "other" else "site"}))
            continue
        p = Path(item).expanduser()
        paths = sorted(q for q in p.rglob("*") if q.suffix.lower() in (".md", ".txt")) if p.is_dir() else [p]
        for q in paths:
            if not q.is_file():
                raise FileNotFoundError(str(q))
            if q.resolve().parent == ex_dir.resolve():
                out.append(q.resolve())
                continue
            meta, body = frontmatter(q.read_text(encoding="utf-8", errors="ignore"))
            meta.setdefault("source", meta.get("source") or f"file {q.name}")
            meta.setdefault("channel", channel)
            files.append((slug(q.stem), body, meta))
    for name, body, meta in files:
        dest = ex_dir / f"{name}.md"
        n = 2
        while dest.resolve() in out:  # two inputs with the same name in one run
            dest = ex_dir / f"{name}-{n}.md"
            n += 1
        ch = meta.get("channel", channel)
        ch = ch if ch in CHANNELS else "other"
        head = f"---\nsource: {meta.get('source', 'unknown')}\nchannel: {ch}\ncaptured_at: {meta.get('captured_at', today)}\nauthor: founder\n---\n"
        dest.write_text(head + body.strip() + "\n", encoding="utf-8")
        out.append(dest.resolve())
    return out


# --- Measures --------------------------------------------------------------------------

def plain(raw: str, clean_text: Any) -> str:
    """Text the founder wrote, without frontmatter, code, URLs, quotes or markup."""
    t = clean_text(raw, False)
    t = re.sub(r"\{\{[^}]*\}\}", "", t)
    t = re.sub(r"^[ \t]*(#{1,6}|[-*+]|\d+[.)])\s+", "", t, flags=re.M)
    t = re.sub(r"[*_]{1,3}([^*_\n]+)[*_]{1,3}", r"\1", t)
    t = re.sub(r"!?\[([^\]]*)\]\s*", r"\1 ", t)
    return t.replace("’", "'")


def paragraphs(text: str) -> List[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def sentences(par: str) -> List[str]:
    parts = re.split(r"(?<=[.!?…])\s+(?=[\"'(«]?[A-ZÀ-Ý0-9])", par)
    return [s.strip() for s in parts if len(s.split()) >= 2]


def tokens(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text.replace("’", "'"))]


def pct(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def measure(texts: List[Tuple[Path, str]], lang: str, brand: str) -> Tuple[Dict[str, Any], List[Tuple[Path, str, int]]]:
    """Metrics over all texts, and every sentence as (file, sentence, words)."""
    all_sent: List[Tuple[Path, str, int]] = []
    par_words: List[int] = []
    words = 0
    toks_all: List[str] = []
    counts = Counter()
    with_excl = with_emoji = 0
    casing: Counter = Counter()
    for path, text in texts:
        pars = paragraphs(text)
        for par in pars:
            n = len(tokens(par))
            par_words.append(n)
            for s in sentences(par):
                all_sent.append((path, s, len(tokens(s))))
        tk = tokens(text)
        words += len(tk)
        toks_all.extend(tk)
        counts["exclamation"] += text.count("!")
        counts["question"] += text.count("?")
        counts["colon"] += len(re.findall(r"(?<!\d):(?!\d)", text))
        counts["semicolon"] += text.count(";")
        counts["parenthesis"] += text.count("(")
        counts["ellipsis"] += text.count("...") + text.count("…")
        counts["emoji"] += len(EMOJI_RE.findall(text))
        if lang == "en":
            counts["contraction"] += len(re.findall(r"\b\w+(?:n't|'re|'ll|'ve|'m|'d)\b", text, re.I))
        with_excl += 1 if "!" in text else 0
        with_emoji += 1 if EMOJI_RE.search(text) else 0
        if brand:
            for m in re.finditer(rf"(?<![\w.]){re.escape(brand)}(?![\w])", text, re.I):
                casing[m.group(0)] += 1
    sw = [float(n) for _p, _s, n in all_sent]
    per = {k: round(v * 1000.0 / max(words, 1), 2) for k, v in sorted(counts.items())}
    for k in ("exclamation", "question", "colon", "semicolon", "parenthesis", "ellipsis", "emoji"):
        per.setdefault(k, 0.0)
    pron = PRONOUNS[lang]
    pc = {k: sum(1 for t in toks_all if t in words_) for k, words_ in pron.items()}
    brand_n = sum(casing.values())
    if lang == "en":
        person_counts = {"first_singular": pc["first_singular"], "first_plural": pc["first_plural"], "second": pc["second"]}
        you = pc["second"]
        address = {"form": "you" if you else "none", "you": you}
    else:
        person_counts = {"first_singular": pc["first_singular"], "first_plural": pc["first_plural"], "on": pc["on"],
                         "second": pc["tu"] + pc["vous"]}
        tu, vous = pc["tu"], pc["vous"]
        form = "none" if not (tu or vous) else ("vous" if tu == 0 else ("tu" if vous <= tu * 0.1 else "mixed"))
        address = {"form": form, "tu": tu, "vous": vous}
    person_counts["brand_third_person"] = brand_n
    tot = sum(person_counts.values()) or 1
    person = {k: round(v / tot, 3) for k, v in person_counts.items()}
    stop = STOPWORDS[lang] | {brand.lower()} | set().union(*PRONOUNS[lang].values())
    content = Counter(t for t in toks_all if len(t) >= 4 and t not in stop and not t.isdigit())
    metrics = {
        "texts": len(texts), "words": words, "sentences": len(all_sent),
        "sentence_words": {"median": round(statistics.median(sw), 1) if sw else 0.0, "p25": pct(sw, 0.25),
                           "p75": pct(sw, 0.75), "p90": pct(sw, 0.9), "max": max(sw) if sw else 0.0},
        "paragraph_words_median": round(statistics.median(par_words), 1) if par_words else 0.0,
        "person": person, "address": address, "per_1000_words": per,
        "texts_with_exclamation": with_excl, "texts_with_emoji": with_emoji,
        "brand_casing": dict(casing),
        "top_words": [{"word": w, "count": c} for w, c in content.most_common(15) if c >= 2],
        "low_sample": words < LOW_SAMPLE_WORDS or len(texts) < 3,
    }
    return metrics, all_sent


# --- Rules -------------------------------------------------------------------------------

def make_rules(m: Dict[str, Any], lang: str, brand: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(voice rules, generated gate rules). Rules state facts with their evidence."""
    n = m["texts"]
    sw = m["sentence_words"]
    rules: List[Dict[str, Any]] = []
    gate: List[Dict[str, Any]] = []
    rules.append({"id": "sentence-length", "evidence": f"{m['sentences']} sentences in {n} texts",
                  "rule": f"Keep sentences near {sw['median']:g} words: a quarter of the founder's sentences are under {sw['p25']:g} words, "
                          f"three in four under {sw['p75']:g}, nine in ten under {sw['p90']:g}.", "enforced_by": None})
    if m.get("paragraph_words_median"):
        rules.append({"id": "paragraph-length", "evidence": f"median over {n} texts",
                      "rule": f"Keep paragraphs near {m['paragraph_words_median']:g} words.", "enforced_by": None})
    p = m["person"]
    top = max(("first_plural", "first_singular", "brand_third_person"), key=lambda k: p.get(k, 0))
    if p.get(top, 0) > 0:
        who = {"first_plural": "we" if lang == "en" else "nous", "first_singular": "I" if lang == "en" else "je",
               "brand_third_person": f"the brand name ({brand})"}[top]
        rules.append({"id": "speaker", "evidence": f"{int(p[top] * 100)} % of the personal references",
                      "rule": f"Speak for the company as {who}.", "enforced_by": None})
    a = m["address"]
    if lang == "en" and a.get("you"):
        rules.append({"id": "address", "evidence": f"{a['you']} forms of you", "rule": "Address the reader as you.", "enforced_by": None})
    if lang == "fr" and a["form"] == "vous":
        strong = n >= 2 and a.get("vous", 0) >= 5
        rules.append({"id": "address", "evidence": f"{a.get('vous', 0)} forms of vous, no form of tu, in {n} texts",
                      "rule": "Address the reader with vous; the founder's texts hold no form of tu.",
                      "enforced_by": "writing-gate address-tu"})
        gate.append({"code": "address-tu", "family": "project-voice", "level": "BLOCK" if strong else "WARN",
                     "pattern": r"\b(?:tu|toi|ton|ta|tes|te)\b|\bt'(?=[a-zà-ÿ])", "flags": "i",
                     "message": "The founder addresses the reader with vous: rewrite this sentence with vous.",
                     "bad": ["Tu peux réserver ta place."], "good": ["Vous pouvez réserver votre place."]})
    if lang == "fr" and a["form"] == "tu":
        rules.append({"id": "address", "evidence": f"{a.get('tu', 0)} forms of tu, {a.get('vous', 0)} of vous",
                      "rule": "Address the reader with tu.", "enforced_by": "writing-gate address-vous"})
        gate.append({"code": "address-vous", "family": "project-voice", "level": "WARN", "pattern": r"\b(?:votre|vos)\b", "flags": "i",
                     "message": "The founder addresses the reader with tu: check this sentence.",
                     "bad": ["Réservez votre place."], "good": ["Réserve ta place."]})
    casing = m.get("brand_casing") or {}
    if brand and sum(casing.values()) >= 2:
        form, cnt = Counter(casing).most_common(1)[0]
        if cnt == sum(casing.values()):
            rules.append({"id": "brand-casing", "evidence": f"{cnt} of {cnt} mentions", "rule": f"Write the brand as {form}.",
                          "enforced_by": "writing-gate brand-casing"})
            wrong = form.upper() if form != form.upper() else form.capitalize()
            gate.append({"code": "brand-casing", "family": "project-voice", "level": "BLOCK",
                         "pattern": rf"(?<![\w.])(?i:{re.escape(form)})(?!\w)(?<!{re.escape(form)})",
                         "message": f"Write the brand as {form}.", "bad": [f"Try {wrong} today."], "good": [f"Try {form} today."]})
    per = m["per_1000_words"]
    if per.get("exclamation", 0) == 0 and n >= 2:
        rules.append({"id": "exclamation", "evidence": f"none in {n} texts", "rule": "Use no exclamation mark.",
                      "enforced_by": "writing-gate no-exclamation"})
        gate.append({"code": "no-exclamation", "family": "project-voice", "level": "WARN", "escalate_at": 2,
                     "pattern": r"!(?!\[)", "message": "The founder writes no exclamation mark: end the sentence with a period.",
                     "bad": ["We shipped it!"], "good": ["We shipped it."]})
    else:
        rules.append({"id": "exclamation", "evidence": f"in {m.get('texts_with_exclamation', 0)} of {n} texts",
                      "rule": f"At most {per.get('exclamation', 0):g} exclamation marks per 1000 words.", "enforced_by": None})
    if per.get("emoji", 0) == 0 and n >= 2:
        rules.append({"id": "emoji", "evidence": f"none in {n} texts", "rule": "Use no emoji.", "enforced_by": "writing-gate no-emoji"})
        gate.append({"code": "no-emoji", "family": "project-voice", "level": "WARN",
                     "pattern": "[\\U0001F300-\\U0001FAFF\\u2600-\\u27BF]", "message": "The founder writes no emoji: remove it.",
                     "bad": ["Launch day \U0001F680"], "good": ["Launch day."]})
    else:
        rules.append({"id": "emoji", "evidence": f"in {m.get('texts_with_emoji', 0)} of {n} texts",
                      "rule": f"At most {per.get('emoji', 0):g} emoji per 1000 words, never in a title.", "enforced_by": None})
    if lang == "en":
        c = per.get("contraction", 0)
        if c >= 5:
            rules.append({"id": "contractions", "evidence": f"{c:g} per 1000 words", "rule": "Use contractions (we're, don't, you'll).",
                          "enforced_by": None})
        elif m["words"] >= 300 and c < 1:
            rules.append({"id": "contractions", "evidence": f"{c:g} per 1000 words", "rule": "Write without contractions (we are, do not).",
                          "enforced_by": None})
    q = per.get("question", 0)
    if q == 0:
        rules.append({"id": "questions", "evidence": f"no question mark in {n} texts",
                      "rule": "State things; the founder's texts ask the reader no question.", "enforced_by": None})
    else:
        rules.append({"id": "questions", "evidence": f"{q:g} per 1000 words", "rule": f"Ask at most {q:g} questions per 1000 words.",
                      "enforced_by": None})
    return rules, gate


# --- Calibration -------------------------------------------------------------------------

def load_gate() -> Any:
    sys.path.insert(0, str(GATE))
    import lint_copy  # type: ignore
    return lint_copy


def lint_file(lc: Any, path: Path, lang: str, rules_path: Path) -> List[Dict[str, Any]]:
    rules, _src = lc.load_rules(lang, None, str(rules_path), [], [])
    return lc.lint_text(path.read_text(encoding="utf-8"), rules)


def write_pack(path: Path, lang: str, banned: List[str], disable: List[str], levels: Dict[str, str], rules: List[Dict[str, Any]]) -> None:
    pack: Dict[str, Any] = {"pack": "project", "language": lang,
                            "description": "Project pack generated by agents/project-context/scripts/build_voice.py from the founder's own texts. "
                                           "Rebuild it with the script; rules added by hand under other codes are kept."}
    if banned:
        pack["banned_words"] = sorted(set(banned), key=str.lower)
    if disable:
        pack["disable"] = sorted(set(disable))
    if levels:
        pack["levels"] = dict(sorted(levels.items()))
    pack["rules"] = rules
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def calibrate(lc: Any, ex_paths: List[Path], lang: str, rules_path: Path, banned: List[str], manual: Dict[str, Any],
              generated: List[Dict[str, Any]], pc_dir: Path) -> Dict[str, Any]:
    disable = list(manual.get("disable", []))
    levels = dict(manual.get("levels", {}))
    gen = list(generated)
    adjustments: List[Dict[str, Any]] = []
    conflicts: List[str] = []
    before: Dict[Path, int] = {}
    for rnd in range(CALIBRATION_ROUNDS):
        write_pack(rules_path, lang, banned, disable, levels, list(manual.get("rules", [])) + gen)
        blocks: List[Tuple[Path, Dict[str, Any]]] = []
        for p in ex_paths:
            f = [x for x in lint_file(lc, p, lang, rules_path) if x["level"] == "BLOCK"]
            if rnd == 0:
                before[p] = len(f)
            blocks.extend((p, x) for x in f)
        fixable = [(p, x) for p, x in blocks if x["code"] != "banned-word"]
        for p, x in blocks:
            if x["code"] == "banned-word":
                msg = f"banned word \"{x['match']}\" in the founder's own text ({p.relative_to(pc_dir)}:{x['line']})"
                if msg not in conflicts:
                    conflicts.append(msg)
        if not fixable:
            break
        for p, x in fixable:
            code = x["code"]
            example = f"{p.relative_to(pc_dir)}:{x['line']}: \"{x['match']}\""
            if code in GENERATED_CODES and any(g["code"] == code for g in gen):
                gen = [g for g in gen if g["code"] != code]
                adjustments.append({"code": code, "change": "drop-project-rule", "example": example})
            elif x.get("escalated") and code not in disable:
                disable.append(code)
                levels.pop(code, None)
                adjustments.append({"code": code, "change": "disable", "example": example})
            elif code not in levels and code not in disable:
                levels[code] = "WARN"
                adjustments.append({"code": code, "change": "level-warn", "example": example})
            elif levels.get(code) == "WARN" and code not in disable:
                disable.append(code)
                levels.pop(code, None)
                adjustments.append({"code": code, "change": "disable", "example": example})
    write_pack(rules_path, lang, banned, disable, levels, list(manual.get("rules", [])) + gen)
    texts = []
    for p in ex_paths:
        f = lint_file(lc, p, lang, rules_path)
        texts.append({"path": str(p.relative_to(pc_dir)), "block_before": before.get(p, 0),
                      "block_after": sum(1 for x in f if x["level"] == "BLOCK"),
                      "warn_after": sum(1 for x in f if x["level"] == "WARN")})
    status = "conflict" if conflicts else ("adjusted" if adjustments else "pass")
    return {"status": status, "texts": texts, "adjustments": adjustments, "conflicts": conflicts, "generated": gen,
            "disable": disable, "levels": levels}


def pick_examples(lc: Any, sents: List[Tuple[Path, str, int]], m: Dict[str, Any], lang: str, rules_path: Path,
                  pc_dir: Path, channels: Dict[Path, str]) -> List[Dict[str, Any]]:
    rules, _src = lc.load_rules(lang, None, str(rules_path), [], [])
    lo, hi = m["sentence_words"]["p25"], m["sentence_words"]["p90"]
    med = m["sentence_words"]["median"]
    cands = []
    for i, (p, s, n) in enumerate(sents):
        if not (lo <= n <= hi) or re.search(r"\d|https?://|\{\{", s) or not s[0].isupper():
            continue
        if lc.lint_text(s, rules):
            continue
        cands.append((abs(n - med), i, p, s))
    cands.sort()
    per: Counter = Counter()
    picked = []
    for _d, i, p, s in cands:
        if per[p] >= MAX_EXAMPLES_PER_SOURCE:
            continue
        per[p] += 1
        picked.append((i, p, s))
        if len(picked) >= MAX_EXAMPLES:
            break
    picked.sort()
    return [{"text": s, "source": str(p.relative_to(pc_dir)), "channel": channels.get(p, "other")} for _i, p, s in picked]


# --- Main --------------------------------------------------------------------------------------

def validate(schema: Path, inst: Path) -> Tuple[bool, str]:
    if not VALIDATOR.is_file() or not schema.is_file():
        return True, "validator not found, skipped"
    pr = subprocess.run([sys.executable, str(VALIDATOR), str(schema), str(inst)], capture_output=True, text=True)
    return pr.returncode == 0, (pr.stdout + pr.stderr).strip()


def brand_from(pc_dir: Path) -> str:
    for name in ("brand.json", "brand-draft.json"):
        p = pc_dir / name
        if p.is_file():
            try:
                return str(json.loads(p.read_text(encoding="utf-8")).get("name") or "")
            except (OSError, ValueError):
                pass
    return ""


def context_banned(pc_dir: Path) -> List[str]:
    p = pc_dir / "context.json"
    try:
        return list(((json.loads(p.read_text(encoding="utf-8")).get("voice") or {}).get("banned_words")) or [])
    except (OSError, ValueError, AttributeError):
        return []


def check_only(lc: Any, pc_dir: Path) -> int:
    vp, rp = pc_dir / "voice" / "voice.json", pc_dir / "voice" / "rules.json"
    try:
        voice = json.loads(vp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"build_voice: cannot read {vp}: {e}", file=sys.stderr)
        return 2
    for schema, inst in ((VOICE_SCHEMA, vp), (RULES_SCHEMA, rp)):
        ok, detail = validate(schema, inst)
        if not ok:
            print(detail, file=sys.stderr)
            return 2
    total = 0
    for s in voice.get("sources") or []:
        p = pc_dir / s["path"]
        f = lint_file(lc, p, voice["language"], rp)
        b = sum(1 for x in f if x["level"] == "BLOCK")
        total += b
        print(f"{s['path']}: {b} BLOCK, {len(f) - b} WARN")
        for x in f:
            if x["level"] == "BLOCK":
                print(f"  line {x['line']}  {x['code']}  \"{x['match']}\"")
    print("calibration: " + ("PASS (the founder's texts pass at 0 BLOCK)" if not total else f"FAIL ({total} BLOCK in the founder's own texts)"))
    return 0 if not total else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", help="Founder texts: .md/.txt files, folders, or public URLs")
    ap.add_argument("--out", required=True, help="The project-context folder (writes voice/ inside)")
    ap.add_argument("--lang", choices=("auto", "en", "fr"), default="auto")
    ap.add_argument("--brand-name", default="", help="Brand name (default: name in brand.json or brand-draft.json)")
    ap.add_argument("--channel", choices=CHANNELS, default="other", help="Channel of the inputs that do not say it in a frontmatter")
    ap.add_argument("--ban", action="append", default=[], help="A word or phrase the founder never wants (repeatable)")
    ap.add_argument("--check", action="store_true", help="Only re-run the calibration on the existing pack")
    ap.add_argument("--update-context", action="store_true", help="Write voice.pack_path, voice.address and voice.language into context.json")
    args = ap.parse_args(argv)

    pc_dir = Path(args.out).expanduser().resolve()
    try:
        lc = load_gate()
    except ImportError:
        print(f"build_voice: the shared writing gate was not found at {GATE}; copy shared/ next to agents/.", file=sys.stderr)
        return 4
    if args.check:
        return check_only(lc, pc_dir)

    today = dt.date.today().isoformat()
    voice_dir = pc_dir / "voice"
    ex_dir = voice_dir / "exemplars"
    try:
        paths = collect_inputs(args.inputs, ex_dir, args.channel, today) if args.inputs else sorted(ex_dir.glob("*.md"))
    except (OSError, ValueError) as e:
        print(f"build_voice: cannot read an input: {e}", file=sys.stderr)
        return 2
    paths = sorted(set(paths))
    if not paths:
        print("build_voice: no founder text given and voice/exemplars/ is empty.", file=sys.stderr)
        return 2
    raw = {p: p.read_text(encoding="utf-8", errors="ignore") for p in paths}
    texts = [(p, plain(raw[p], lc.clean_text)) for p in paths]
    joined = "\n".join(t for _p, t in texts)
    lang = args.lang if args.lang != "auto" else lc.detect_lang(joined)
    brand = args.brand_name or brand_from(pc_dir)
    metrics, sents = measure(texts, lang, brand)
    if metrics["words"] < MIN_WORDS:
        print(f"build_voice: {metrics['words']} words of founder text; at least {MIN_WORDS} are needed. "
              "Ask the founder for posts, an about page or emails they wrote.", file=sys.stderr)
        return 3
    voice_rules, generated = make_rules(metrics, lang, brand)

    # keep what the founder or a decision added by hand to an existing pack
    rules_path = voice_dir / "rules.json"
    old_voice: Dict[str, Any] = {}
    try:
        old_voice = json.loads((voice_dir / "voice.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    manual: Dict[str, Any] = {"rules": [], "disable": [], "levels": {}}
    if rules_path.is_file():
        try:
            old = json.loads(rules_path.read_text(encoding="utf-8"))
            prev_auto = {a["code"] for a in (old_voice.get("calibration") or {}).get("adjustments", [])}
            manual["rules"] = [r for r in old.get("rules", []) if r.get("code") not in GENERATED_CODES]
            manual["disable"] = [c for c in old.get("disable", []) if c not in prev_auto]
            manual["levels"] = {k: v for k, v in (old.get("levels") or {}).items() if k not in prev_auto}
        except (OSError, ValueError):
            pass
    banned_entries: List[Dict[str, Any]] = [b for b in old_voice.get("banned", []) if b.get("source") in ("founder", "decision")]
    for w in args.ban:
        if not any(b["text"].lower() == w.lower() for b in banned_entries):
            banned_entries.append({"text": w, "reason": "declared by the founder", "source": "founder"})
    for w in context_banned(pc_dir):
        if not any(b["text"].lower() == w.lower() for b in banned_entries):
            banned_entries.append({"text": w, "reason": "voice.banned_words in context.json", "source": "context"})

    cal = calibrate(lc, paths, lang, rules_path, [b["text"] for b in banned_entries], manual, generated, pc_dir)
    kept_codes = {g["code"] for g in cal["generated"]}
    for r in voice_rules:
        eb = r.get("enforced_by") or ""
        if eb.startswith("writing-gate ") and eb.split(" ", 1)[1] not in kept_codes:
            r["enforced_by"] = None
            r["evidence"] += "; the gate rule was dropped at calibration because the founder's own text breaks it"
    channels = {p: (frontmatter(raw[p])[0].get("channel") or "other") for p in paths}
    examples = pick_examples(lc, sents, metrics, lang, rules_path, pc_dir, channels)
    sources = []
    for p in paths:
        meta = frontmatter(raw[p])[0]
        src: Dict[str, Any] = {"path": str(p.relative_to(pc_dir)), "channel": meta.get("channel") if meta.get("channel") in CHANNELS else "other",
                               "words": len(tokens(dict(texts)[p]))}
        if meta.get("source"):
            src["source"] = meta["source"]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", meta.get("captured_at", "")):
            src["captured_at"] = meta["captured_at"]
        sources.append(src)
    voice = {
        "schema_version": "1.0", "language": lang, "as_of": today,
        **({"brand_name": brand} if brand else {}),
        "sources": sources, "metrics": metrics, "rules": voice_rules, "examples": examples, "banned": banned_entries,
        "pack_path": "voice/rules.json",
        "calibration": {"status": cal["status"], "checked_at": today, "texts": cal["texts"], "adjustments": cal["adjustments"],
                        "conflicts": cal["conflicts"]},
        "how_to_use": ("Before writing copy: apply every rule, read the examples for register (never reuse them verbatim in new copy), "
                       "never write a banned entry. After writing: python3 shared/skills/writing-gate/scripts/lint_copy.py --project "
                       "<project> <draft>, which loads rules.json; 0 BLOCK before delivery."),
    }
    vp = voice_dir / "voice.json"
    vp.write_text(json.dumps(voice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for schema, inst in ((VOICE_SCHEMA, vp), (RULES_SCHEMA, rules_path)):
        ok, detail = validate(schema, inst)
        if not ok:
            print(f"build_voice: {inst.name} fails {schema.name}:\n{detail}", file=sys.stderr)
            return 2
    if args.update_context and (pc_dir / "context.json").is_file():
        ctx = json.loads((pc_dir / "context.json").read_text(encoding="utf-8"))
        v = ctx.setdefault("voice", {})
        v["pack_path"] = "voice/voice.json"
        v["language"] = lang
        v["address"] = metrics["address"]["form"]
        (pc_dir / "context.json").write_text(json.dumps(ctx, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"voice pack: {vp}")
    print(f"gate pack:  {rules_path}")
    print(f"{metrics['texts']} texts, {metrics['words']} words, language {lang}{' (low sample: add texts)' if metrics['low_sample'] else ''}")
    for r in voice_rules:
        print(f"  - {r['rule']}  [{r['evidence']}]")
    print(f"calibration: {cal['status']}")
    for t in cal["texts"]:
        print(f"  {t['path']}: {t['block_before']} BLOCK before, {t['block_after']} after, {t.get('warn_after', 0)} WARN")
    for a in cal["adjustments"]:
        print(f"  adjusted {a['code']} ({a['change']}): {a['example']}")
        print(f"    Proposed decision for memory/decisions.md: writing-gate {a['code']} {'lowered to WARN' if a['change'] == 'level-warn' else 'switched off'} "
              f"for this project, the founder writes {a['example'].split(': ', 1)[1]}. Enforced by: voice/rules.json.")
    for c in cal["conflicts"]:
        print(f"  CONFLICT: {c}. Ask the founder whether the word stays banned or the text is no longer theirs.")
    return 1 if cal["status"] == "conflict" else 0


if __name__ == "__main__":
    sys.exit(main())
