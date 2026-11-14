#!/usr/bin/env python3
"""
topics.py

Topic registry of seo-audit: one line per subject the site covers or plans
(a live page, a brief, a draft, a proposal) in

    <your-projects-root>/<project>/seo-audit/topics.json

so that no brief, article or proposal duplicates a page the site already has,
and a subject already treated in a section of another article goes to that
article as a refresh. Standard library only; deterministic (same files, same
--today, same output).

Commands:
  build    --registry R --crawl crawl.jsonl [--state state.json] [--bands bands.json]
           [--domain URL] [--config C] [--today D]
           Fills and refreshes the registry from the crawl (200, indexable,
           self-canonical pages; home, language roots, section indexes, legal,
           privacy, contact, tag, author and pagination pages left out): one
           live line per URL with its query (first H1 normalized, else the
           title without the brand part), title, H2 and H3. Template headings
           (on most pages) are dropped. Briefs of state.json set brief_id on
           their live line, or add a brief line when their URL is not live.
           A live line whose URL now answers a redirect, an error or noindex
           becomes dropped. Running it twice changes nothing.
  check    --registry R "<subject>" [--subjects-file F] [--json] [--config C]
           Verdict per subject: duplicate (main subject of a live page, a brief
           or a draft: its URL or brief), refresh (close to a page's main
           subject, or treated in one of its H2/H3: URL and section), new.
           Score, reason and the nearest lines are printed.
  add      --registry R --query Q --status S [--url U] [--source S] [--title T]
           [--alias A]... [--h2-file F] [--h3-file F] [--brief-id B] [--notes N]
           [--id ID] [--force] [--today D]
           Adds or updates one line (found by --id, then URL, then query or
           alias). A new line that check calls a duplicate of another line is
           refused unless --force. A live line stays live when a brief or a
           draft of its refresh is added: brief_id and notes are recorded.
  propose  --registry R --out-dir D [--bands F] [--gsc F]... [--seed S]... [--expand]
           [--suggest-file F] [--offline] [--serp serp-analysis.json]
           [--competitor C]... [--competitor-sitemap F]... [--fetch-titles]
           [--config C] [--add] [--today D]
           Topic ideas from free sources, each passed through check: Search
           Console queries without a page of their own, Google autocomplete
           (public suggest endpoint, or a file), People also ask of an existing
           serp-analysis.json, competitor sitemaps (slug, or the page H1/title
           with --fetch-titles). Brand queries and duplicates are set aside and
           listed; the rest is grouped, ranked by an explained priority and
           written to propose-<YYYYMMDD>.json and .md. --add records the kept
           ideas as proposed lines; without it the registry is not touched.
  list     --registry R [--status S] [--sections] [--json]
           The registry as Markdown (or JSON).

Rules and thresholds: assets/topics-rules.json, overridden by the topics
object of the project config.json (--config). The model chooses and writes;
this script only compares, counts and records.

Exit codes: 0 done; 1 add refused (duplicate without --force, live without
URL); 2 usage error or unreadable input (check, list and propose need an
existing registry: run build first).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import (InputError, Robots, deep_merge, fetch, host_of, bare_host, is_noindex,  # noqa: E402,F401
                     load_assets_json, load_gsc, aggregate, load_json, normalize_url, origin_of,
                     parse_day, parse_html, parse_sitemap, path_of, read_jsonl, write_json, write_text)

STATUSES = ["live", "brief", "draft", "proposed", "dropped"]
SOURCES = ["crawl", "brief", "write", "propose"]
BLOCKING = ("live", "brief", "draft")
DEFAULT_SOURCE = {"live": "crawl", "brief": "brief", "draft": "write", "proposed": "propose", "dropped": "write"}
FIELD_ORDER = ["id", "query", "aliases", "url", "status", "source", "kind", "title", "h2", "h3",
               "first_seen", "updated", "brief_id", "notes"]
OPEN_BRIEF = ("open", "shipped", "verified", "tracking")
VERDICT_RANK = {"duplicate": 0, "refresh": 1, "new": 2}


class Refused(Exception):
    pass


# --------------------------------------------------------------------------
# rules and text

def load_rules(config: Optional[str]) -> Dict[str, Any]:
    rules = load_assets_json("topics-rules.json")
    if config:
        rules = deep_merge(rules, load_json(config).get("topics", {}) or {})
    return rules


def load_config(config: Optional[str]) -> Dict[str, Any]:
    return load_json(config) if config else {}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


_NON_WORD = re.compile(r"[^\w]+|_", re.UNICODE)


def normalize_query(text: Optional[str]) -> str:
    """Lowercase, accents kept, punctuation removed, spaces compacted."""
    s = unicodedata.normalize("NFC", text or "").lower()
    return " ".join(_NON_WORD.sub(" ", s).split())


def deslugify(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.rstrip("/")
    seg = path.rsplit("/", 1)[-1] if path else ""
    seg = re.sub(r"\.(html?|php|aspx?)$", "", seg, flags=re.I)
    seg = re.sub(r"[-_+]+", " ", urllib.parse.unquote(seg)).strip()
    seg = re.sub(r"\b\d{5,}\b", "", seg).strip()
    return " ".join(seg.split())


def slug(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", strip_accents(text or "").lower()).strip("-")
    return s[:max_len].rstrip("-") or "x"


class Matcher:
    """Tokens, light stemming and the similarity score, all from the rules file."""

    def __init__(self, rules: Dict[str, Any]) -> None:
        self.rules = rules
        self.stop = {strip_accents(w.lower()) for lst in rules["stopwords"].values() for w in lst}
        self.weights: Dict[str, float] = {}
        self.joins = sorted(((strip_accents(k.lower()), strip_accents(v.lower())) for k, v in (rules.get("joins") or {}).items()),
                            key=lambda kv: -len(kv[0]))
        self.suffixes = [(s["suffix"], int(s.get("min_stem", 3)), s.get("replace", "")) for s in rules["stem_suffixes"]]
        self.min_len = int(rules.get("min_token_length", 2))
        self.drop_years = bool(rules.get("drop_years", True))
        self.sub_w = float(rules.get("substring_weight", 0.5))
        self.ignore = {normalize_query(h) for h in rules.get("ignore_headings", [])}
        self._cache: Dict[str, Tuple[str, ...]] = {}

    def stem(self, tok: str) -> str:
        if tok.isdigit():
            return tok
        for sfx, min_stem, rep in self.suffixes:
            if sfx in ("s", "es") and tok.endswith("ss"):
                continue
            if tok.endswith(sfx) and len(tok) - len(sfx) >= min_stem:
                tok = tok[: len(tok) - len(sfx)] + rep
                break
        if tok.endswith("e") and len(tok) > 3:
            tok = tok[:-1]
        return tok

    def seq(self, text: Optional[str]) -> Tuple[str, ...]:
        key = text or ""
        if key in self._cache:
            return self._cache[key]
        out: List[str] = []
        flat = " " + strip_accents(normalize_query(key)) + " "
        for src, dst in self.joins:
            flat = flat.replace(f" {src} ", f" {dst} ")
        for raw in flat.split():
            if raw in self.stop:
                continue
            if self.drop_years and re.fullmatch(r"(19|20)\d\d", raw):
                continue
            if self.rules.get("drop_small_numbers") and re.fullmatch(r"\d{1,3}", raw):
                continue
            if len(raw) < self.min_len and not raw.isdigit():
                continue
            out.append(self.stem(raw))
        res = tuple(out)
        self._cache[key] = res
        return res

    def joined(self, text: Optional[str], vocab: set) -> Tuple[str, ...]:
        """Tokens of a subject where two neighbour words become one when the joined word exists in
        the registry (`lem list` -> `lemlist`, `open vc` -> `openvc`): search queries split brand
        names that the pages write as one word."""
        raw = [w for w in strip_accents(normalize_query(text or "")).split()]
        out: List[str] = []
        i = 0
        while i < len(raw):
            if i + 1 < len(raw) and raw[i] not in self.stop and raw[i + 1] not in self.stop:
                j = self.stem(raw[i] + raw[i + 1])
                if j in vocab:
                    out.append(j)
                    i += 2
                    continue
            out.extend(self.seq(raw[i]))
            i += 1
        return tuple(out)

    def score(self, a: Sequence[str], b: Sequence[str]) -> float:
        """a is the subject, b the registry text. The substring bonus applies when the subject sits
        whole inside b, or when b sits inside the subject with at least two words: a one-word
        heading (`Le prix`) contained in a longer subject is no evidence of the same topic."""
        A, B = set(a), set(b)
        if not A or not B:
            return 0.0
        inter = A & B
        if not inter:
            return 0.0
        w = self.weights
        if w:
            j = sum(w.get(t, 1.0) for t in inter) / sum(w.get(t, 1.0) for t in A | B)
        else:
            j = len(inter) / len(A | B)
        short, long_ = (a, b) if len(a) <= len(b) else (b, a)
        n = len(short)
        contiguous = any(tuple(long_[i:i + n]) == tuple(short) for i in range(len(long_) - n + 1))
        if contiguous and (len(a) <= len(b) or n >= 2):
            j = j + (1 - j) * self.sub_w
        return round(j, 3)


def clean_heading(h: str) -> str:
    h = re.sub(r"^\s*(?:\d{1,2}\s*[.):]\s*|step\s+\d+\s*[.:]?\s*|étape\s+\d+\s*[.:]?\s*)", "", h or "", flags=re.I)
    return " ".join(h.split())


def strip_brand(title: Optional[str], brand_labels: Iterable[str], separators: List[str],
                drop_short_tail: bool = False) -> Optional[str]:
    """Title without the parts that carry the brand name (`Pricing | Acme` -> `Pricing`). With
    drop_short_tail (competitor pages, brand unknown), a last part of 3 words or fewer goes too."""
    if not title:
        return title
    parts = [title]
    for sep in separators:
        parts = [p for part in parts for p in part.split(sep)]
    parts = [p.strip() for p in parts if p.strip()]
    labels = [b for b in brand_labels if b]
    keep = [p for p in parts if not any(b in re.sub(r"[^a-z0-9]", "", strip_accents(p.lower())) for b in labels)]
    if drop_short_tail and len(keep) == len(parts) and len(parts) > 1 and len(parts[-1].split()) <= 3:
        keep = parts[:-1]
    if not keep or len(parts) == 1:
        return title.strip()
    return " ".join(keep)


def brand_labels_for(domain: Optional[str], cfg: Dict[str, Any]) -> List[str]:
    labels = []
    if domain:
        host = bare_host(host_of(domain if "://" in domain else "https://" + domain))
        first = host.split(".")[0] if host else ""
        if len(first) >= 3 and not first.replace(".", "").isdigit():
            labels.append(first)
    for alias in list((cfg.get("geo") or {}).get("brand_aliases") or []) + ([cfg["brand"]] if cfg.get("brand") else []):
        a = re.sub(r"[^a-z0-9]", "", strip_accents(str(alias).lower()))
        if len(a) >= 3:
            labels.append(a)
    return sorted(set(labels))


# --------------------------------------------------------------------------
# registry

def today_str(value: Optional[str]) -> str:
    return parse_day(value).isoformat()


def load_registry(path: str, must_exist: bool = True) -> Dict[str, Any]:
    if not os.path.exists(path):
        if must_exist:
            raise InputError(f"registry not found: {path} (run `topics.py build` first)")
        return {"schema_version": "1.0", "domain": None, "updated": None, "topics": []}
    reg = load_json(path)
    if not isinstance(reg, dict) or not isinstance(reg.get("topics"), list):
        raise InputError(f"{path} is not a topic registry (no topics list)")
    return reg


def order_topic(t: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: t.get(k) for k in FIELD_ORDER}
    for k in ("aliases", "h2", "h3"):
        out[k] = list(out[k] or [])
    if out["notes"] is None:
        out["notes"] = ""
    for k in sorted(t):
        if k not in out:
            out[k] = t[k]
    return out


def save_registry(path: str, reg: Dict[str, Any]) -> None:
    reg["topics"] = [order_topic(t) for t in sorted(reg["topics"], key=lambda x: x["id"])]
    out = {"schema_version": reg.get("schema_version", "1.0"), "domain": reg.get("domain"),
           "updated": reg.get("updated"), "topics": reg["topics"]}
    write_json(path, out)


def new_id(base: str, taken: set) -> str:
    cand = "t-" + base
    n = 2
    while cand in taken:
        cand = f"t-{base}-{n}"
        n += 1
    return cand


def id_for_url(url: str, taken: set) -> str:
    segs = [s for s in path_of(url).split("?")[0].strip("/").split("/") if s]
    if not segs:
        return new_id("home", taken)
    base = slug(segs[-1])
    if "t-" + base in taken:
        base = slug("-".join(segs))
    return new_id(base, taken)


_VOCAB: Dict[int, Tuple[int, set, Dict[str, float]]] = {}


def registry_vocab(reg: Dict[str, Any], m: "Matcher") -> set:
    """Every stemmed word of the live, brief and draft lines (query, aliases, title), cached per registry.
    Also sets the word weights of the matcher: with word_weights and at least min_lines lines, a word
    weighs max(floor, 1 - slope x share of lines holding it), so a word every page uses (`startup` on
    a startup blog) counts less than a place or a product name."""
    key = id(reg)
    n = len(reg.get("topics") or [])
    if key in _VOCAB and _VOCAB[key][0] == n:
        m.weights = _VOCAB[key][2]
        return _VOCAB[key][1]
    vocab = set()
    df: Dict[str, int] = {}
    lines = 0
    for t in reg.get("topics") or []:
        if t.get("status") == "dropped":
            continue
        line = set()
        for _, _, toks in topic_fields(t, m):
            line.update(toks)
        if line:
            lines += 1
            vocab.update(line)
            for tok in line:
                df[tok] = df.get(tok, 0) + 1
    W = m.rules.get("word_weights") or {}
    weights: Dict[str, float] = {}
    if W and lines >= int(W.get("min_lines", 30)):
        floor, slope = float(W.get("floor", 0.2)), float(W.get("slope", 2.0))
        weights = {tok: round(max(floor, 1.0 - slope * n_ / lines), 3) for tok, n_ in df.items()}
    m.weights = weights
    _VOCAB[key] = (n, vocab, weights)
    return vocab


def url_lang(url: Optional[str]) -> Optional[str]:
    """Two-letter language of a /xx/ path prefix, None for the site's default language."""
    mt = re.match(r"^https?://[^/]+/([a-z]{2})(?:[-_][a-z]{2})?/", url or "")
    return mt.group(1) if mt else None


def subject_lang(subject: str, rules: Dict[str, Any]) -> Optional[str]:
    """Language of the subject when its words tell it, else None (the site's default language)."""
    words = re.findall(r"[a-zà-ÿ']+", (subject or "").lower())
    fr = sum(w in rules["stopwords"]["fr"] for w in words) + sum(bool(re.search(r"[àâçéèêëîïôûùüÿœ]", w)) for w in words)
    en = sum(w in rules["stopwords"]["en"] for w in words)
    default = rules.get("default_language")
    if en > fr:
        return None if default == "en" else "en"
    return None


def topic_fields(t: Dict[str, Any], m: Matcher) -> List[Tuple[str, str, Tuple[str, ...]]]:
    out = []
    for field, texts in (("query", [t.get("query")]), ("alias", t.get("aliases") or []), ("title", [t.get("title")])):
        for x in texts:
            if x:
                s = m.seq(x)
                if s:
                    out.append((field, x, s))
    return out


def section_fields(t: Dict[str, Any], m: Matcher) -> List[Tuple[str, str, Tuple[str, ...]]]:
    out = []
    for level in ("h2", "h3"):
        for h in t.get(level) or []:
            c = clean_heading(h)
            if not c or normalize_query(c) in m.ignore:
                continue
            s = m.seq(c)
            if s:
                out.append((level, h, s))
    return out


# --------------------------------------------------------------------------
# check

def check_subject(subject: str, reg: Dict[str, Any], rules: Dict[str, Any], m: Matcher,
                  exclude_id: Optional[str] = None) -> Dict[str, Any]:
    T = rules["thresholds"]
    norm = normalize_query(subject)
    vocab = registry_vocab(reg, m)
    sq = m.joined(subject, vocab) if vocab else m.seq(subject)
    base = {"subject": subject, "normalized": norm, "tokens": list(sq), "verdict": "new", "score": 0.0, "broad": None,
            "reason": "", "url": None, "section": None, "topic_id": None, "status": None, "matched_field": None,
            "matched_text": None, "already_proposed": None, "already_dropped": None,
            "thresholds": {k: T[k] for k in ("duplicate", "refresh_main", "refresh_section")}, "nearest": []}
    if not sq:
        base["reason"] = "no meaningful word left after normalization (only stop words?): rephrase the subject"
        return base
    # A heading equal to the title of another page is a link card to it (related articles), not a
    # section of this page: it never counts as this page treating the subject.
    card_titles = {normalize_query(x) for t in reg["topics"] if t.get("status") == "live"
                   for x in (t.get("title"), t.get("query")) if x}
    cands = []
    for t in reg["topics"]:
        if t["id"] == exclude_id:
            continue
        if t.get("status") == "dropped":
            if not base["already_dropped"] and any(m.score(sq, s) >= T["duplicate"] for _, _, s in topic_fields(t, m)):
                base["already_dropped"] = t["id"]
            continue
        for field, text, s in topic_fields(t, m):
            cands.append({"score": m.score(sq, s), "kind": "main", "field": field, "text": text, "topic": t})
        if t.get("status") in BLOCKING:
            for field, text, s in section_fields(t, m):
                if normalize_query(text) in card_titles:
                    continue
                cands.append({"score": m.score(sq, s), "kind": "section", "field": field, "text": text, "topic": t})
    cands = [c for c in cands if c["score"] > 0]
    sset = set(sq)
    for c in cands:
        ts = m.seq(c["text"])
        c["covers"] = bool(ts) and sset <= set(ts)
        wsum = lambda toks: sum(m.weights.get(t, 1.0) for t in toks)  # noqa: E731
        c["covers_tight"] = c["covers"] and c["kind"] == "main" and wsum(sset) / max(wsum(set(ts)), 1e-9) >= 0.5
        c["contained"] = len(sq) >= 2 and bool(ts) and sset <= set(ts) and len(sset) / len(set(ts)) >= T.get(
            "duplicate_contained", T["duplicate"])
    s_lang = subject_lang(subject, rules)
    for c in cands:
        c["lang_off"] = 0 if url_lang(c["topic"].get("url")) == s_lang else 1
    status_rank = {"live": 0, "draft": 1, "brief": 2, "proposed": 3}
    field_rank = {"query": 0, "alias": 1, "title": 2, "h2": 3, "h3": 4}
    cands.sort(key=lambda c: (c["lang_off"], -c["score"], 0 if c["kind"] == "main" else 1, status_rank.get(c["topic"]["status"], 9),
                              field_rank.get(c["field"], 9), c["topic"]["id"], c["text"]))
    nearest, seen = [], set()
    for c in cands:
        key = (c["topic"]["id"], c["field"], c["text"])
        if key in seen:
            continue
        seen.add(key)
        nearest.append({"topic_id": c["topic"]["id"], "status": c["topic"]["status"], "url": c["topic"].get("url"),
                        "field": c["field"], "text": c["text"], "score": c["score"]})
        if len(nearest) == 5:
            break
    base["nearest"] = nearest
    proposed = [c for c in cands if c["topic"]["status"] == "proposed" and c["kind"] == "main" and c["score"] >= T["duplicate"]]
    if proposed:
        base["already_proposed"] = proposed[0]["topic"]["id"]
    blocking = [c for c in cands if c["topic"]["status"] in BLOCKING]

    def fill(c: Dict[str, Any], verdict: str, reason: str) -> Dict[str, Any]:
        t = c["topic"]
        base.update(verdict=verdict, score=c["score"], reason=reason, url=t.get("url"), topic_id=t["id"],
                    status=t["status"], matched_field=c["field"], matched_text=c["text"],
                    section=({"level": c["field"], "text": c["text"]} if c["kind"] == "section" else None))
        return base

    def where(t: Dict[str, Any]) -> str:
        if t.get("url"):
            return f"{t['status']} page {t['url']}"
        return f"{t['status']} {t['id']}" + (f" (brief {t['brief_id']})" if t.get("brief_id") else "")

    dup = [c for c in blocking if c["kind"] == "main" and (c["score"] >= T["duplicate"] or (
        c["contained"]))]
    if dup:
        c = dup[0]
        return fill(c, "duplicate", f"main subject of the {where(c['topic'])}: {c['field']} `{c['text']}` scores "
                                    f"{c['score']} >= duplicate {T['duplicate']}. Work on that line, not a new page.")
    ref = [c for c in blocking if (c["kind"] == "main" and c["score"] >= T["refresh_main"])
           or (c["kind"] == "section" and c["score"] >= T["refresh_section"])]
    B = rules.get("broad") or {}
    if ref and B and not any(c["covers_tight"] for c in ref):
        top = max(c["score"] for c in ref)
        urls = []
        for c in sorted(ref, key=lambda c: -c["score"]):
            u = c["topic"].get("url") or c["topic"]["id"]
            if top - c["score"] <= float(B.get("margin", 0.03)) and u not in urls:
                urls.append(u)
        if len(urls) >= int(B.get("min_pages", 3)) and top < float(B.get("max_score", 0.8)):
            base.update(verdict="new", score=top, broad=urls,
                        reason=f"broad subject: {len(urls)} pages touch it at {top} ({', '.join(urls[:5])}) and none "
                               "owns it; a pillar page linking to them, or a refresh of the closest one, is the "
                               "founder's call")
            return base
    covering = [c for c in ref if c["kind"] == "main" and c["covers"]]
    if covering:
        ref = covering
    
    if ref:
        c = ref[0]
        if c["kind"] == "section":
            return fill(c, "refresh", f"treated in the {c['field']} `{c['text']}` of the {where(c['topic'])} "
                                      f"(score {c['score']} >= section {T['refresh_section']}): enrich that section.")
        return fill(c, "refresh", f"close to the main subject of the {where(c['topic'])}: {c['field']} `{c['text']}` "
                                  f"scores {c['score']} (refresh {T['refresh_main']} to duplicate {T['duplicate']}): "
                                  "expand that page.")
    if nearest and blocking:
        b = blocking[0]
        base["reason"] = (f"no line close enough: nearest is {b['field']} `{b['text']}` of {where(b['topic'])} "
                          f"at {b['score']} (< {min(T['refresh_main'], T['refresh_section'])})")
    else:
        base["reason"] = "no registry line shares a meaningful word"
    if base["already_proposed"]:
        base["reason"] += f"; already proposed as {base['already_proposed']}"
    if base["already_dropped"]:
        base["reason"] += f"; dropped before as {base['already_dropped']}"
    base["score"] = blocking[0]["score"] if blocking else 0.0
    return base


def format_check(r: Dict[str, Any]) -> str:
    line = f"{r['verdict']} {r['score']} `{r['subject']}`"
    if r["verdict"] != "new":
        line += f" -> {r['url'] or r['topic_id']}"
        if r["section"]:
            line += f" [{r['section']['level']}: {r['section']['text']}]"
    return line + f"\n  {r['reason']}"


# --------------------------------------------------------------------------
# build

def site_page_slugs(eeat: Dict[str, Any], keys: List[str]) -> set:
    out = set()
    for k in keys:
        out |= {s.lower() for s in eeat.get("site_pages", {}).get(k, [])}
    return out


def page_skip_reason(rec: Dict[str, Any], rules: Dict[str, Any], eeat: Dict[str, Any], excluded_slugs: set) -> Optional[str]:
    if rec.get("status") != 200 or rec.get("redirect_chain"):
        return "not 200"
    if "html" not in (rec.get("content_type") or "").lower():
        return "not HTML"
    if not rec.get("indexable"):
        return "noindex"
    if rec.get("canonical_status") not in (None, "self", "missing"):
        return "canonical elsewhere"
    url = rec.get("final_url") or rec["url"]
    p = path_of(url)
    path = p.split("?")[0]
    if path in ("", "/") or re.match(rules["language_root_pattern"], path):
        return "home"
    for pat in rules["exclude_path_patterns"]:
        if re.search(pat, p, re.I):
            return "listing or utility page"
    lang = re.match(r"^/[a-z]{2}(?:[-_][a-z]{2})?(/.*)$", path)
    bare = lang.group(1) if lang else path
    norm = bare if bare.endswith("/") else bare + "/"
    if norm in [x if x.endswith("/") else x + "/" for x in eeat["article_detection"]["path_prefixes"]]:
        return "section index"
    last = [s for s in path.strip("/").split("/") if s][-1].lower()
    last = re.sub(r"\.(html?|php)$", "", last)
    if last in excluded_slugs:
        return "site page (legal, privacy or contact)"
    return None


def page_kind(rec: Dict[str, Any], eeat: Dict[str, Any]) -> str:
    det = eeat["article_detection"]
    if set(rec.get("jsonld_types") or []) & set(det["jsonld_types"]):
        return "article"
    path = path_of(rec.get("final_url") or rec["url"])
    lang = re.match(r"^/[a-z]{2}(?:[-_][a-z]{2})?(/.*)$", path)
    bare = lang.group(1) if lang else path
    if any(bare.startswith(pref) for pref in det["path_prefixes"]):
        return "article"
    return "page"


def cmd_build(a, rules: Dict[str, Any]) -> int:
    cfg = load_config(a.config)
    eeat = load_assets_json("eeat-weights.json")
    if cfg.get("eeat"):
        eeat = deep_merge(eeat, cfg["eeat"])
    m = Matcher(rules)
    day = today_str(a.today)
    reg = load_registry(a.registry, must_exist=False)
    lines = read_jsonl(a.crawl)
    if not lines:
        raise InputError(f"{a.crawl} holds no crawl line")
    state = load_json(a.state) if a.state else None
    bands = load_json(a.bands) if a.bands else None
    domain = (a.domain or cfg.get("domain") or reg.get("domain") or (state or {}).get("domain")
              or origin_of(lines[0][1].get("url", "")) + "/")
    domain = normalize_url(domain)
    labels = brand_labels_for(domain, cfg)
    excluded_slugs = site_page_slugs(eeat, rules.get("exclude_site_pages", []))
    top_query = (bands or {}).get("top_query_by_page", {}) or {}

    pages: Dict[str, Dict[str, Any]] = {}
    gone: Dict[str, str] = {}
    for _, rec in lines:
        url = rec.get("final_url") or rec.get("url")
        reason = page_skip_reason(rec, rules, eeat, excluded_slugs)
        if reason is None:
            pages.setdefault(normalize_url(url), rec)
        elif reason in ("not 200", "noindex", "canonical elsewhere"):
            u = normalize_url(rec.get("url"))
            if rec.get("redirect_chain"):
                gone[u] = f"redirects to {rec.get('final_url')}"
            elif reason == "not 200":
                gone[u] = f"answers {rec.get('status') or rec.get('error')}"
            elif reason == "noindex":
                gone[u] = "noindex"
            else:
                gone[u] = f"canonical points to {rec.get('canonical')}"
    for u in list(gone):
        if u in pages:
            del gone[u]

    # template headings: present on most content pages
    share = float(rules.get("template_heading_share", 0.5))
    min_pages = int(rules.get("template_heading_min_pages", 4))
    counts: Dict[str, int] = {}
    for rec in pages.values():
        for h in set((rec.get("h2") or []) + (rec.get("h3") or [])):
            counts[normalize_query(h)] = counts.get(normalize_query(h), 0) + 1
    template = {h for h, n in counts.items() if len(pages) >= min_pages and n / len(pages) > share}

    def dedupe(xs: Iterable[str]) -> List[str]:
        out, seen = [], set()
        for x in xs:
            x = " ".join((x or "").split())
            if x and x not in seen and normalize_query(x) not in template:
                seen.add(x)
                out.append(x)
        return out[:40]

    rank = {"live": 0, "draft": 1, "brief": 2, "proposed": 3, "dropped": 4}
    by_url: Dict[str, Dict[str, Any]] = {}
    for t in sorted(reg["topics"], key=lambda x: (rank.get(x.get("status"), 9), x["id"])):
        if t.get("url"):
            by_url.setdefault(t["url"], t)
    taken = {t["id"] for t in reg["topics"]}
    changed = False

    def touch(t: Dict[str, Any], fields: Dict[str, Any]) -> None:
        nonlocal changed
        diff = False
        for k, v in fields.items():
            if t.get(k) != v:
                t[k] = v
                diff = True
        if diff:
            t["updated"] = day
            changed = True

    for url in sorted(pages):
        rec = pages[url]
        h1 = next((h for h in (rec.get("h1") or []) if h and h.strip()), None)
        stitle = strip_brand(rec.get("title"), labels, rules["title_separators"])
        title = " ".join(h1.split()) if h1 else stitle
        query = normalize_query(h1 or stitle or deslugify(url))
        alias_cands = [normalize_query(stitle)] if stitle else []
        if top_query.get(url):
            alias_cands.append(normalize_query(top_query[url]))
        fields = {"url": url, "status": "live", "kind": page_kind(rec, eeat), "title": title,
                  "h2": dedupe(rec.get("h2") or []), "h3": dedupe(rec.get("h3") or [])}
        t = by_url.get(url)
        if t is None:
            t = {"id": id_for_url(url, taken), "query": query, "aliases": [], "source": "crawl", "first_seen": day,
                 "updated": day, "brief_id": None, "notes": ""}
            taken.add(t["id"])
            reg["topics"].append(t)
            by_url[url] = t
            changed = True
        if t.get("source", "crawl") == "crawl":
            fields["query"] = query
        elif normalize_query(t.get("query")) != query:
            alias_cands.insert(0, query)
        if t.get("status") == "dropped" and (t.get("notes") or "").startswith("crawl "):
            fields["notes"] = ""
        aliases = list(t.get("aliases") or [])
        for x in alias_cands:
            if x and x != (fields.get("query") or t.get("query")) and x not in aliases:
                aliases.append(x)
        fields["aliases"] = aliases
        touch(t, fields)

    for t in reg["topics"]:
        u = t.get("url")
        if t.get("status") == "live" and u in gone:
            touch(t, {"status": "dropped", "notes": f"crawl {day}: {gone[u]}"})

    # briefs of state.json
    if state:
        for bid in sorted((state.get("briefs") or {}).keys()):
            b = state["briefs"][bid]
            burl = normalize_url(b["url"]) if b.get("url") else None
            row = by_url.get(burl) if burl else None
            active = b.get("status") in OPEN_BRIEF
            brief_rows = [t for t in reg["topics"] if t.get("brief_id") == bid and t is not row]
            if row is not None and row.get("status") != "live":
                brief_rows = [row] + brief_rows
            if row is not None and row.get("status") == "live":
                if active:
                    touch(row, {"brief_id": bid})
                elif row.get("brief_id") == bid:
                    touch(row, {"brief_id": None})
                for t in brief_rows:  # a brief line whose page is now live merges into the live line
                    if t.get("status") == "brief":
                        q = normalize_query(t.get("query"))
                        if q and q != row.get("query") and q not in row["aliases"]:
                            touch(row, {"aliases": row["aliases"] + [q]})
                        reg["topics"].remove(t)
                        changed = True
                continue
            if not active:
                for t in brief_rows:
                    if t.get("status") == "brief":
                        touch(t, {"status": "dropped", "notes": f"brief {bid} {b.get('status')}"})
                continue
            query = normalize_query(b.get("query") or b.get("target_query") or (deslugify(burl) if burl else bid))
            t = brief_rows[0] if brief_rows else None
            if t is None:
                t = {"id": new_id(slug(query), taken), "query": query, "aliases": [], "source": "brief",
                     "first_seen": day, "updated": day, "brief_id": bid, "notes": "", "title": None, "h2": [], "h3": []}
                taken.add(t["id"])
                reg["topics"].append(t)
                changed = True
            touch(t, {"status": "draft" if t.get("status") == "draft" else "brief", "url": burl, "brief_id": bid})

    if reg.get("domain") != domain:
        reg["domain"] = domain
        changed = True
    if changed or not reg.get("updated"):
        reg["updated"] = day
    save_registry(a.registry, reg)
    st: Dict[str, int] = {}
    for t in reg["topics"]:
        st[t["status"]] = st.get(t["status"], 0) + 1
    print(f"topics: {len(reg['topics'])} lines (" + ", ".join(f"{k} {st[k]}" for k in STATUSES if k in st) + ")"
          + ("" if changed else ", unchanged") + f" -> {a.registry}")
    return 0


# --------------------------------------------------------------------------
# add

def read_headings(path: str) -> Tuple[List[str], List[str]]:
    """H2 and H3 from a file: Markdown (## and ###), a JSON list or object {h2, h3}, or one heading per line."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    if path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise InputError(f"{path} is not valid JSON: {e}")
        if isinstance(data, list):
            return [str(x) for x in data], []
        if isinstance(data, dict):
            return [str(x) for x in data.get("h2", [])], [str(x) for x in data.get("h3", [])]
        raise InputError(f"{path}: expected a list or an object with h2 and h3")
    lines = [l.rstrip() for l in text.splitlines()]
    if any(re.match(r"^#{2,3}\s", l) for l in lines):
        h2 = [l[3:].strip() for l in lines if re.match(r"^##\s", l)]
        h3 = [l[4:].strip() for l in lines if re.match(r"^###\s", l)]
        return h2, h3
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")], []


def cmd_add(a, rules: Dict[str, Any]) -> int:
    m = Matcher(rules)
    day = today_str(a.today)
    reg = load_registry(a.registry, must_exist=False)
    status = a.status
    url = normalize_url(a.url) if a.url else None
    if status == "live" and not url:
        raise Refused("a live line needs --url")
    query = normalize_query(a.query)
    if not m.seq(query):
        raise InputError(f"--query `{a.query}` has no meaningful word")
    h2 = h3 = None
    if a.h2_file:
        h2, h3f = read_headings(a.h2_file)
        h3 = h3f or None
    if a.h3_file:
        h3 = read_headings(a.h3_file)[0]
    row = None
    if a.id:
        row = next((t for t in reg["topics"] if t["id"] == a.id), None)
    if row is None and url:
        row = next((t for t in reg["topics"] if t.get("url") == url and t.get("status") != "dropped"), None) \
            or next((t for t in reg["topics"] if t.get("url") == url), None)
    if row is None:
        row = next((t for t in reg["topics"] if t.get("status") != "dropped" and
                    (normalize_query(t.get("query")) == query or query in [normalize_query(x) for x in t.get("aliases") or []])), None)
    created = row is None
    if created:
        verdict = check_subject(query, reg, rules, m)
        if verdict["verdict"] == "duplicate" and not a.force and status != "dropped":
            raise Refused(f"`{query}` duplicates {verdict['url'] or verdict['topic_id']} ({verdict['reason']}) "
                          f"Update that line with --id {verdict['topic_id']}, or pass --force.")
        taken = {t["id"] for t in reg["topics"]}
        row = {"id": a.id or (id_for_url(url, taken) if url and status == "live" else new_id(slug(query), taken)),
               "query": query, "aliases": [], "url": None, "status": status, "source": a.source or DEFAULT_SOURCE[status],
               "kind": None, "title": None, "h2": [], "h3": [], "first_seen": day, "updated": day, "brief_id": None, "notes": ""}
        reg["topics"].append(row)
    kept_live = False
    before = json.dumps(order_topic(row), sort_keys=True)
    if not created:
        if row.get("status") == "live" and status in ("brief", "draft"):
            kept_live = True
        else:
            row["status"] = status
        q_old = normalize_query(row.get("query"))
        if query != q_old and query not in row.get("aliases", []):
            row.setdefault("aliases", []).append(query)
        if a.source and not kept_live:
            row["source"] = a.source
    if url and not (status in ("proposed",) and created):
        row["url"] = url
    if status == "proposed" and created:
        row["url"] = None
    for al in a.alias or []:
        al = normalize_query(al)
        if al and al != row["query"] and al not in row["aliases"]:
            row["aliases"].append(al)
    if a.title is not None and not kept_live:
        row["title"] = a.title
    if h2 is not None and not kept_live:
        row["h2"] = h2[:40]
    if h3 is not None and not kept_live:
        row["h3"] = h3[:40]
    if a.brief_id is not None:
        row["brief_id"] = a.brief_id or None
    if a.notes is not None:
        row["notes"] = a.notes
    if kept_live:
        note = f"{status} of its refresh recorded on {day}"
        if note not in (row.get("notes") or ""):
            row["notes"] = ((row.get("notes") or "") + ("; " if row.get("notes") else "") + note)
    changed = created or json.dumps(order_topic(row), sort_keys=True) != before
    if changed:
        row["updated"] = day
        reg["updated"] = day
    if not reg.get("domain") and url:
        reg["domain"] = origin_of(url) + "/"
    save_registry(a.registry, reg)
    what = "added" if created else ("kept live, updated" if kept_live else ("updated" if changed else "unchanged"))
    print(f"{what} {row['id']} ({row['status']}) `{row['query']}`" + (f" {row['url']}" if row.get("url") else ""))
    return 0


# --------------------------------------------------------------------------
# propose

def http_text(url: str, timeout: float) -> Optional[str]:
    res = fetch(url, timeout=timeout)
    if res.get("status") == 200 and res.get("text"):
        return res["text"]
    return None


def suggest_online(q: str, hl: str, gl: str, timeout: float) -> List[str]:
    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {"client": "firefox", "q": q, "hl": hl, "gl": gl})
    text = http_text(url, timeout)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s for s in data[1] if isinstance(s, str) and s.strip()]
    return []


def resolve_country(a, cfg: Dict[str, Any], hl: str) -> str:
    for c in (a.country, cfg.get("serp_country"), cfg.get("country")):
        if c and re.fullmatch(r"[A-Za-z]{2}", str(c)) and str(c).lower() not in ("en",):
            return str(c).lower()
    return {"en": "us", "fr": "fr", "de": "de", "es": "es", "it": "it", "pt": "br", "nl": "nl"}.get(hl, "us")


def competitor_article(url: str, host: str, rules: Dict[str, Any], eeat: Dict[str, Any], excluded: set) -> bool:
    if bare_host(host_of(url)) != bare_host(host):
        return False
    p = path_of(url)
    path = p.split("?")[0]
    if path in ("", "/") or re.match(rules["language_root_pattern"], path):
        return False
    for pat in rules["exclude_path_patterns"]:
        if re.search(pat, p, re.I):
            return False
    segs = [s for s in path.strip("/").split("/") if s]
    if not segs:
        return False
    norm = "/" + "/".join(segs) + "/"
    if norm in [x if x.endswith("/") else x + "/" for x in eeat["article_detection"]["path_prefixes"]]:
        return False
    last = re.sub(r"\.(html?|php|aspx?)$", "", segs[-1].lower())
    if last in excluded:
        return False
    return "-" in last or "_" in last or len(segs) >= 2


def sitemap_urls(origin: str, extra: List[str], offline: bool, rules: Dict[str, Any], warnings: List[str]) -> List[str]:
    P = rules["propose"]
    queue: List[str] = list(extra)
    if origin and not offline:
        robots = http_text(origin + "/robots.txt", P["timeout_s"])
        if robots:
            queue += Robots(robots).sitemaps
        queue += [origin + "/sitemap.xml", origin + "/sitemap_index.xml"]
    seen, urls, files = set(), [], 0
    while queue and files < P["competitor_max_sitemaps"] and len(urls) < P["competitor_max_urls"]:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        files += 1
        if os.path.exists(sm):
            with open(sm, encoding="utf-8", errors="replace") as f:
                text = f.read()
        elif offline:
            warnings.append(f"offline: sitemap {sm} not fetched")
            continue
        else:
            text = http_text(sm, P["timeout_s"])
        if not text:
            continue
        parsed = parse_sitemap(text)
        if parsed["kind"] == "sitemapindex":
            queue += parsed["locs"]
        elif parsed["kind"] == "urlset":
            for loc in parsed["locs"]:
                u = normalize_url(loc)
                if u not in urls:
                    urls.append(u)
    return urls[: P["competitor_max_urls"]]


class Ideas:
    def __init__(self, m: Matcher, max_tokens: int) -> None:
        self.m = m
        self.max_tokens = max_tokens
        self.items: Dict[str, Dict[str, Any]] = {}
        self.too_long = 0

    def add(self, phrase: str, source: str, **ev: Any) -> None:
        q = normalize_query(phrase)
        s = self.m.seq(q)
        if not s:
            return
        if len(s) > self.max_tokens:
            self.too_long += 1
            return
        it = self.items.setdefault(q, {"query": q, "seq": s, "sources": set(), "gsc": None, "seeds": set(),
                                       "paa": set(), "competitors": {}, "hits": 0})
        it["sources"].add(source)
        it["hits"] += 1
        if source == "gsc":
            g = ev["gsc"]
            if it["gsc"] is None or g["impressions"] > it["gsc"]["impressions"]:
                it["gsc"] = g
        elif source == "autocomplete":
            it["seeds"].add(ev["seed"])
        elif source == "paa":
            it["paa"].add(ev["serp_query"])
        elif source == "competitor":
            it["competitors"].setdefault(ev["domain"], ev["url"])


def merge_gsc(acc: Dict[str, Dict[str, Any]], query: str, rec: Dict[str, Any]) -> None:
    """Keep the file with the most impressions for a query (two exports of one period are not summed)."""
    old = acc.get(query)
    if old is None or rec["impressions"] > old["impressions"]:
        if old is not None and not rec.get("top_page"):
            rec = dict(rec, top_page=old.get("top_page"))
        acc[query] = rec
    elif not old.get("top_page") and rec.get("top_page"):
        old["top_page"] = rec["top_page"]


def cmd_propose(a, rules: Dict[str, Any]) -> int:
    cfg = load_config(a.config)
    P = rules["propose"]
    m = Matcher(rules)
    day = today_str(a.today)
    stamp = day.replace("-", "")
    reg = load_registry(a.registry, must_exist=True)
    eeat = load_assets_json("eeat-weights.json")
    excluded_slugs = site_page_slugs(eeat, rules.get("exclude_site_pages", []) + ["about_page"])
    domain = reg.get("domain") or cfg.get("domain")
    labels = brand_labels_for(domain, cfg)
    ideas = Ideas(m, int(P["max_idea_tokens"]))
    report: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    def rel(p: str) -> str:
        """Path as seen from the output folder, or the file name when it lives outside the project."""
        ap_, ao = os.path.abspath(p), os.path.abspath(a.out_dir)
        try:
            common = os.path.commonpath([ap_, ao])
        except ValueError:  # another drive
            return os.path.basename(p)
        depth = len([x for x in common.replace(os.sep, "/").split("/") if x and not x.endswith(":")])
        r = os.path.relpath(ap_, ao).replace(os.sep, "/")
        return r if depth >= 2 and r.split("/").count("..") <= 3 else os.path.basename(p)

    # (a) Search Console
    gsc_q: Dict[str, Dict[str, Any]] = {}
    gin = []
    if a.bands:
        b = load_json(a.bands)
        gin.append(rel(a.bands))
        for q in b.get("queries", []) or []:
            cur = q.get("cur") or {}
            rec = {"impressions": int(cur.get("impressions") or 0), "clicks": int(cur.get("clicks") or 0),
                   "position": cur.get("position"), "top_page": q.get("top_page")}
            k = q.get("query")
            if k:
                merge_gsc(gsc_q, k, rec)
    for gp in a.gsc or []:
        d = load_gsc(gp)
        gin.append(rel(gp))
        if "query" not in d["dimensions"]:
            warnings.append(f"{os.path.basename(gp)} has no query column: skipped")
            continue
        agg = aggregate(d["rows"], "query")
        top: Dict[str, Tuple[int, str]] = {}
        for r in d["rows"]:
            if r.get("query") and r.get("page"):
                imp = int((r.get("cur") or {}).get("impressions") or 0)
                pg = normalize_url(r["page"])
                best = top.get(r["query"])
                if best is None or imp > best[0] or (imp == best[0] and pg < best[1]):
                    top[r["query"]] = (imp, pg)
        for k, v in agg.items():
            rec = {"impressions": v["impressions"], "clicks": v["clicks"], "position": v["position"],
                   "top_page": top.get(k, (0, None))[1]}
            merge_gsc(gsc_q, k, rec)
    brand_skipped: List[str] = []

    def is_brand(q: str) -> bool:
        flat = re.sub(r"[^a-z0-9]", "", strip_accents(q.lower()))
        return any(lb in flat for lb in labels)

    if gin:
        n = 0
        for k in sorted(gsc_q):
            v = gsc_q[k]
            if v["impressions"] < P["gsc_min_impressions"]:
                continue
            if is_brand(k):
                brand_skipped.append(normalize_query(k))
                continue
            ideas.add(k, "gsc", gsc=v)
            n += 1
        report["gsc"] = {"status": "used", "inputs": gin, "queries": len(gsc_q), "ideas": n,
                         "min_impressions": P["gsc_min_impressions"]}
    else:
        report["gsc"] = {"status": "skipped", "why": "no --bands or --gsc file"}

    # (b) autocomplete
    seeds = list(dict.fromkeys([s.strip() for s in (a.seed or []) if s.strip()]
                               or [s for s in (cfg.get("target_queries") or []) if isinstance(s, str) and s.strip()
                                   and not s.startswith("primary query") and not s.endswith("query")]))
    seeds = seeds[: P["suggest_max_seeds"]]
    hl = (a.language or cfg.get("language") or "en").lower()[:2]
    gl = resolve_country(a, cfg, hl)
    if not seeds:
        report["autocomplete"] = {"status": "skipped", "why": "no --seed and no target_queries in the config"}
    elif not a.suggest_file and a.offline:
        report["autocomplete"] = {"status": "skipped", "why": "--offline without --suggest-file", "seeds": seeds}
    else:
        table = None
        if a.suggest_file:
            table = load_json(a.suggest_file)
            if not isinstance(table, dict):
                raise InputError(f"{a.suggest_file}: expected an object {{\"query sent\": [suggestions]}}")
        sent, got = 0, 0
        for seed in seeds:
            terms = [seed] + ([f"{seed} {c}" for c in "abcdefghijklmnopqrstuvwxyz"] if a.expand else [])
            for term in terms:
                if table is not None:
                    sugg = [s for s in table.get(term, []) if isinstance(s, str)]
                else:
                    if sent:
                        time.sleep(float(P["suggest_delay_s"]))
                    sugg = suggest_online(term, hl, gl, P["timeout_s"])
                sent += 1
                for s in sugg:
                    if normalize_query(s) == normalize_query(seed):
                        continue
                    if is_brand(s):
                        if normalize_query(s) not in brand_skipped:
                            brand_skipped.append(normalize_query(s))
                        continue
                    ideas.add(s, "autocomplete", seed=seed)
                    got += 1
        report["autocomplete"] = {"status": "used", "from": rel(a.suggest_file) if a.suggest_file else "suggestqueries.google.com",
                                  "seeds": seeds, "expand": bool(a.expand), "requests": sent, "suggestions": got,
                                  "hl": hl, "gl": gl}

    # (c) People also ask
    if a.serp:
        sd = load_json(a.serp)
        n = 0
        for rec in sd.get("data", []) if isinstance(sd, dict) else []:
            feats = rec.get("features") or {}
            if feats.get("paa_status") not in (None, "captured"):
                continue
            for qq in feats.get("paa") or []:
                if isinstance(qq, str) and qq.strip():
                    ideas.add(qq, "paa", serp_query=rec.get("query") or "")
                    n += 1
        report["paa"] = {"status": "used", "input": rel(a.serp), "questions": n}
    else:
        report["paa"] = {"status": "skipped", "why": "no --serp file (serp-analysis.json of the run)"}

    # (d) competitor sitemaps
    comps: List[Tuple[str, List[str]]] = []
    for c in a.competitor or []:
        c = c.strip().rstrip("/")
        origin = c if "://" in c else "https://" + c
        comps.append((origin_of(origin), []))
    if not a.competitor:
        for c in (cfg.get("competitors") or []) + [d for x in ((cfg.get("geo") or {}).get("competitors") or [])
                                                     if isinstance(x, dict) for d in (x.get("domains") or [])]:
            if isinstance(c, str) and c.strip():
                origin = c.strip().rstrip("/")
                comps.append((origin_of(origin if "://" in origin else "https://" + origin), []))
    for sm in a.competitor_sitemap or []:
        if os.path.exists(sm):
            locs = parse_sitemap(open(sm, encoding="utf-8", errors="replace").read())["locs"]
            host = host_of(normalize_url(locs[0])) if locs else ""
            comps.append(("https://" + host if host else "", [sm]))
        else:
            comps.append((origin_of(sm), [sm]))
    seen_c = set()
    comp_report = []
    fetched_titles = 0
    for origin, extra in comps:
        key = (origin, tuple(extra))
        if key in seen_c:
            continue
        seen_c.add(key)
        host = host_of(origin) if origin else ""
        only_files = extra and all(os.path.exists(x) for x in extra)
        if a.offline and not only_files:
            comp_report.append({"competitor": bare_host(host), "status": "skipped", "why": "--offline"})
            continue
        urls = sitemap_urls("" if extra else origin, extra, a.offline, rules, warnings)
        kept = news = 0
        for u in urls:
            uh = host_of(u)
            if not competitor_article(u, uh if not host else host, rules, eeat, excluded_slugs):
                continue
            phrase = deslugify(u)
            if re.search(P["news_slug_pattern"], strip_accents(phrase.lower())):
                news += 1
                continue
            label = bare_host(uh)
            if a.fetch_titles and not a.offline and fetched_titles < P["fetch_titles_max"]:
                fetched_titles += 1
                text = http_text(u, P["timeout_s"])
                if text:
                    sig = parse_html(text, u)
                    h1 = next((h for h in sig["h1"] if h.strip()), None)
                    comp_labels = brand_labels_for(u, {})
                    better = h1 or strip_brand(sig["title"], comp_labels, rules["title_separators"], drop_short_tail=True)
                    if better and m.seq(better):
                        phrase = better
            ideas.add(phrase, "competitor", domain=label, url=u)
            kept += 1
        comp_report.append({"competitor": bare_host(host) if host else "file", "status": "used", "sitemap_urls": len(urls),
                            "articles": kept, "news_dropped": news,
                            "from": [rel(x) if os.path.exists(x) else x for x in extra] or [origin]})
    if comps:
        report["competitors"] = {"status": "used" if any(c["status"] == "used" for c in comp_report) else "skipped",
                                 "fetch_titles": bool(a.fetch_titles), "titles_fetched": fetched_titles,
                                 "list": comp_report}
    else:
        report["competitors"] = {"status": "skipped", "why": "no --competitor, --competitor-sitemap or competitors in the config"}

    # group the ideas
    items = sorted(ideas.items.values(), key=lambda it: (-len(it["sources"]), -((it["gsc"] or {}).get("impressions") or 0),
                                                         len(it["seq"]), it["query"]))
    clusters: List[Dict[str, Any]] = []
    for it in items:
        target = None
        for cl in clusters:
            if any(m.score(it["seq"], mem["seq"]) >= rules["thresholds"]["cluster"] for mem in cl["members"]):
                target = cl
                break
        if target is None:
            clusters.append({"members": [it]})
        else:
            target["members"].append(it)

    W = P["priority"]
    out_ideas, excluded, dropped_before = [], [], []
    for cl in clusters:
        mem = cl["members"]
        rep = sorted(mem, key=lambda x: (-((x["gsc"] or {}).get("impressions") or 0), -len(x["sources"]),
                                         len(x["query"]), x["query"]))[0]
        sources = sorted(set().union(*[x["sources"] for x in mem]))
        gsc_rows = [dict(x["gsc"], query=x["query"]) for x in mem if x["gsc"]]
        impressions = sum(g["impressions"] for g in gsc_rows)
        comps_all: Dict[str, str] = {}
        for x in mem:
            for d, u in x["competitors"].items():
                comps_all.setdefault(d, u)
        hits = sum(x["hits"] for x in mem)
        checks = [check_subject(x["query"], reg, rules, m) for x in sorted(mem, key=lambda x: x["query"])]
        main = next(c for c in checks if c["subject"] == rep["query"])
        strongest = sorted(checks, key=lambda c: (VERDICT_RANK[c["verdict"]], -c["score"], c["subject"]))[0]
        verdict = strongest if VERDICT_RANK[strongest["verdict"]] < VERDICT_RANK[main["verdict"]] else main
        prio = (W["per_source"] * len(sources) + W["per_competitor"] * len(comps_all)
                + W["per_extra_hit"] * max(0, hits - 1) + W["impressions_log10"] * math.log10(1 + impressions))
        why = [f"{len(sources)} source{'s' if len(sources) > 1 else ''} ({', '.join(sources)}) x {W['per_source']}"]
        if impressions:
            why.append(f"{impressions} Search Console impressions: log10(1 + {impressions}) x {W['impressions_log10']}")
        if comps_all:
            why.append(f"{len(comps_all)} competitor{'s' if len(comps_all) > 1 else ''} x {W['per_competitor']}")
        if hits > 1:
            why.append(f"{hits - 1} more hit{'s' if hits > 2 else ''} x {W['per_extra_hit']}")
        rec = {
            "topic": rep["query"],
            "variants": sorted({x["query"] for x in mem} - {rep["query"]})[:10],
            "sources": sources,
            "priority": round(prio, 1),
            "priority_why": "; ".join(why),
            "evidence": {
                "gsc": sorted(gsc_rows, key=lambda g: (-g["impressions"], g["query"]))[:5],
                "autocomplete_seeds": sorted(set().union(*[x["seeds"] for x in mem])),
                "paa_from": sorted(set().union(*[x["paa"] for x in mem])),
                "competitors": [{"domain": d, "url": comps_all[d]} for d in sorted(comps_all)],
            },
            "check": {k: verdict[k] for k in ("verdict", "score", "reason", "url", "section", "topic_id", "status",
                                              "matched_field", "matched_text", "already_proposed", "already_dropped")},
        }
        if verdict["subject"] != rep["query"]:
            rec["check"]["subject"] = verdict["subject"]
        if verdict["verdict"] == "duplicate":
            excluded.append(rec)
        elif verdict["verdict"] == "new" and verdict.get("already_dropped"):
            dropped_before.append(rec)
        else:
            out_ideas.append(rec)
    out_ideas.sort(key=lambda r: (-r["priority"], VERDICT_RANK[r["check"]["verdict"]], r["topic"]))
    excluded.sort(key=lambda r: (-r["priority"], r["topic"]))
    top = int(a.top or P["max_ideas"])
    kept, over = out_ideas[:top], out_ideas[top:]
    quota = int(P.get("min_per_source", 0))
    if quota and over:
        # Every source that produced ideas keeps at least `quota` of them in the list: Search
        # Console impressions would otherwise push autocomplete, People also ask and competitor
        # ideas (no impressions yet) out of every report.
        for src in sorted({x for r in out_ideas for x in r["sources"]}):
            have = sum(src in r["sources"] for r in kept)
            extra = [r for r in over if src in r["sources"]][:max(0, quota - have)]
            for r in extra:
                counts = {x: sum(x in k["sources"] for k in kept) for x in {y for k in kept for y in k["sources"]}}
                drop = next((k for k in reversed(kept) if all(counts.get(x, 0) > quota for x in k["sources"])), None)
                if drop is None:
                    break
                kept.remove(drop)
                over.append(drop)
                kept.append(r)
                over.remove(r)
        kept.sort(key=lambda r: (-r["priority"], VERDICT_RANK[r["check"]["verdict"]], r["topic"]))
        over.sort(key=lambda r: (-r["priority"], VERDICT_RANK[r["check"]["verdict"]], r["topic"]))
    for i, r in enumerate(kept, 1):
        r["rank"] = i

    added = []
    if a.add:
        for r in kept:
            c = r["check"]
            prop_id = c.get("already_proposed")
            row = next((t for t in reg["topics"] if t["id"] == prop_id), None) if prop_id else None
            note = f"propose {day}: {', '.join(r['sources'])}; priority {r['priority']}"
            if c["verdict"] == "refresh":
                note += f"; refresh of {c['url'] or c['topic_id']}" + (f" [{c['section']['level']}: {c['section']['text']}]" if c["section"] else "")
            if row is None:
                taken = {t["id"] for t in reg["topics"]}
                row = {"id": new_id(slug(r["topic"]), taken), "query": r["topic"], "aliases": list(r["variants"]), "url": None,
                       "status": "proposed", "source": "propose", "kind": None, "title": None, "h2": [], "h3": [],
                       "first_seen": day, "updated": day, "brief_id": None, "notes": note}
                reg["topics"].append(row)
            else:
                before = json.dumps(order_topic(row), sort_keys=True)
                row["notes"] = note
                for v in r["variants"]:
                    if v != row["query"] and v not in row["aliases"]:
                        row["aliases"].append(v)
                if json.dumps(order_topic(row), sort_keys=True) != before:
                    row["updated"] = day
            r["registry_id"] = row["id"]
            added.append(row["id"])
        reg["updated"] = day
        save_registry(a.registry, reg)

    doc = {
        "schema_version": "1.0",
        "generated_by": "topics.py propose",
        "generated_on": day,
        "registry": rel(a.registry),
        "domain": domain,
        "thresholds": rules["thresholds"],
        "priority_weights": W,
        "sources": report,
        "totals": {"candidates": len(ideas.items), "groups": len(clusters), "kept": len(kept), "over_limit": len(over),
                   "duplicates": len(excluded), "brand_queries": len(brand_skipped), "dropped_before": len(dropped_before),
                   "too_long": ideas.too_long},
        "ideas": kept,
        "excluded_duplicates": excluded,
        "excluded_brand": sorted(brand_skipped),
        "excluded_dropped_before": [{"topic": r["topic"], "topic_id": r["check"]["already_dropped"]}
                                    for r in sorted(dropped_before, key=lambda x: x["topic"])],
        "added_to_registry": added,
        "warnings": warnings,
    }
    jpath = os.path.join(a.out_dir, f"propose-{stamp}.json")
    write_json(jpath, doc)
    write_text(os.path.join(a.out_dir, f"propose-{stamp}.md"), render_propose(doc))
    print(f"propose: {len(kept)} ideas ({sum(1 for r in kept if r['check']['verdict'] == 'new')} new, "
          f"{sum(1 for r in kept if r['check']['verdict'] == 'refresh')} refresh), {len(excluded)} duplicates set aside"
          + (f", {len(added)} added as proposed" if a.add else ", registry untouched") + f" -> {jpath}")
    return 0


def md_cell(s: Any) -> str:
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ")


def render_propose(doc: Dict[str, Any]) -> str:
    L = [f"# Topic proposals ({doc['generated_on']})", "",
         f"Registry `{doc['registry']}`. Every idea went through `topics.py check`: `new` needs a page, "
         "`refresh` goes into the URL and section shown, duplicates are set aside below. The founder picks; "
         "a picked idea is added as `proposed`, then checked again before its brief or its draft.", "",
         "## Sources", "", "| Source | Status | Detail |", "|---|---|---|"]
    for name in ("gsc", "autocomplete", "paa", "competitors"):
        s = doc["sources"].get(name, {})
        if s.get("status") == "skipped":
            detail = s.get("why", "")
        elif name == "gsc":
            detail = f"{s['queries']} queries read, {s['ideas']} with {s['min_impressions']}+ impressions"
        elif name == "autocomplete":
            detail = f"{s['requests']} requests from {len(s['seeds'])} seeds ({s['from']}), {s['suggestions']} suggestions"
        elif name == "paa":
            detail = f"{s['questions']} questions from `{s['input']}`"
        else:
            detail = "; ".join(f"{c['competitor']}: " + (f"{c['articles']} articles of {c['sitemap_urls']} URLs"
                                                           if c["status"] == "used" else c.get("why", "")) for c in s["list"])
        L.append(f"| {name} | {s.get('status')} | {md_cell(detail)} |")
    t = doc["totals"]
    L += ["", f"{t['candidates']} candidates, {t['groups']} groups: {t['kept']} kept, {t['duplicates']} duplicates, "
              f"{t['brand_queries']} brand queries, {t['over_limit']} over the limit.", "",
          "## Ideas", ""]
    if doc["ideas"]:
        L += ["| # | Topic | Verdict | Where | Sources | Priority | Why |", "|---:|---|---|---|---|---:|---|"]
        for r in doc["ideas"]:
            c = r["check"]
            where = ""
            if c["verdict"] == "refresh":
                where = (c["url"] or c["topic_id"] or "") + (f" ({c['section']['level']}: {c['section']['text']})" if c["section"] else " (main subject)")
            elif c.get("already_proposed"):
                where = f"already proposed: {c['already_proposed']}"
            L.append(f"| {r['rank']} | `{md_cell(r['topic'])}` | {c['verdict']} {c['score']} | {md_cell(where)} | "
                     f"{', '.join(r['sources'])} | {r['priority']} | {md_cell(r['priority_why'])} |")
    else:
        L.append("No idea left after the checks.")
    if doc["excluded_duplicates"]:
        L += ["", "## Set aside: already covered", "", "| Topic | Covered by | Score |", "|---|---|---:|"]
        for r in doc["excluded_duplicates"]:
            c = r["check"]
            L.append(f"| `{md_cell(r['topic'])}` | {md_cell(c['url'] or c['topic_id'])} | {c['score']} |")
    if doc["excluded_brand"]:
        L += ["", "## Set aside: brand queries", "", ", ".join(f"`{q}`" for q in doc["excluded_brand"])]
    if doc["excluded_dropped_before"]:
        L += ["", "## Set aside: refused before", "", ", ".join(f"`{r['topic']}` ({r['topic_id']})" for r in doc["excluded_dropped_before"])]
    if doc["added_to_registry"]:
        L += ["", "## Added to the registry as proposed", "", ", ".join(f"`{i}`" for i in doc["added_to_registry"])]
    if doc["warnings"]:
        L += ["", "## Warnings", ""] + [f"- {w}" for w in doc["warnings"]]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# list

def cmd_list(a, rules: Dict[str, Any]) -> int:
    reg = load_registry(a.registry, must_exist=True)
    topics = [t for t in reg["topics"] if not a.status or t.get("status") == a.status]
    if a.json:
        print(json.dumps(topics, ensure_ascii=False, indent=2))
        return 0
    counts: Dict[str, int] = {}
    for t in reg["topics"]:
        counts[t.get("status")] = counts.get(t.get("status"), 0) + 1
    L = [f"# Topic registry: {reg.get('domain') or ''}", "",
         f"Updated {reg.get('updated')}. " + ", ".join(f"{k} {counts[k]}" for k in STATUSES if k in counts) + ".", ""]
    for st in STATUSES:
        rows = [t for t in topics if t.get("status") == st]
        if not rows:
            continue
        L += [f"## {st} ({len(rows)})", "", "| Id | Query | URL | Title | H2 | H3 | Brief | Updated |",
              "|---|---|---|---|---:|---:|---|---|"]
        for t in sorted(rows, key=lambda x: (x.get("url") or "", x["id"])):
            L.append(f"| {t['id']} | `{md_cell(t.get('query'))}` | {md_cell(t.get('url') or '')} | {md_cell(t.get('title') or '')} | "
                     f"{len(t.get('h2') or [])} | {len(t.get('h3') or [])} | {md_cell(t.get('brief_id') or '')} | {t.get('updated')} |")
            if a.sections:
                for h in t.get("h2") or []:
                    L.append(f"|  | h2: {md_cell(h)} |  |  |  |  |  |  |")
                for h in t.get("h3") or []:
                    L.append(f"|  | h3: {md_cell(h)} |  |  |  |  |  |  |")
        L.append("")
    print("\n".join(L).rstrip() + "\n")
    return 0


# --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Topic registry of seo-audit: build from the crawl, check a subject "
                                             "(new, refresh, duplicate), add a line, propose topics, list.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_, description=help_)
        p.add_argument("--registry", required=True, help="<project>/seo-audit/topics.json")
        p.add_argument("--config", help="project config.json (its topics object overrides assets/topics-rules.json)")
        return p

    p = add("build", "Fill and refresh the registry from crawl.jsonl and the briefs of state.json.")
    p.add_argument("--crawl", required=True, help="crawl.jsonl of the run")
    p.add_argument("--state", help="state.json (briefs)")
    p.add_argument("--bands", help="bands.json: the top Search Console query of each page becomes an alias")
    p.add_argument("--domain", help="site home URL (default: config, registry, state, then the crawl)")
    p.add_argument("--today", help="YYYY-MM-DD (default: today)")

    p = add("check", "Verdict for a subject: new, refresh (URL and section) or duplicate, with score and reason.")
    p.add_argument("subject", nargs="?", help="the subject, quoted")
    p.add_argument("--subjects-file", help="one subject per line (prints a JSON list with --json)")
    p.add_argument("--json", action="store_true")

    p = add("add", "Add or update one registry line.")
    p.add_argument("--query", required=True)
    p.add_argument("--status", required=True, choices=STATUSES)
    p.add_argument("--url")
    p.add_argument("--source", choices=SOURCES)
    p.add_argument("--title")
    p.add_argument("--alias", action="append", help="variant query (repeatable)")
    p.add_argument("--h2-file", help="Markdown (## and ### lines), JSON list or {h2, h3}, or one heading per line")
    p.add_argument("--h3-file", help="one H3 per line, or a JSON list")
    p.add_argument("--brief-id")
    p.add_argument("--notes")
    p.add_argument("--id", help="update this line")
    p.add_argument("--force", action="store_true", help="add even when check calls it a duplicate")
    p.add_argument("--today")

    p = add("propose", "Topic ideas from free sources, each passed through check, ranked with an explained priority.")
    p.add_argument("--out-dir", required=True, help="receives propose-<YYYYMMDD>.json and .md")
    p.add_argument("--bands", help="bands.json of the run (Search Console queries)")
    p.add_argument("--gsc", action="append", help="Search Console export with a query column, API JSON or UI CSV (repeatable)")
    p.add_argument("--seed", action="append", help="autocomplete seed (repeatable; default: target_queries of the config)")
    p.add_argument("--expand", action="store_true", help="also query each seed followed by a to z")
    p.add_argument("--suggest-file", help="JSON {\"query sent\": [suggestions]} read instead of the network")
    p.add_argument("--offline", action="store_true", help="no network at all (autocomplete, competitor sitemaps and titles)")
    p.add_argument("--language", help="autocomplete hl (default: config language, else en)")
    p.add_argument("--country", help="autocomplete gl, two letters (default: config serp_country or country, else from the language)")
    p.add_argument("--serp", help="serp-analysis.json of the run (People also ask, no new call)")
    p.add_argument("--competitor", action="append", help="competitor domain or URL: its robots.txt and sitemaps (repeatable; default: competitors of the config)")
    p.add_argument("--competitor-sitemap", action="append", help="competitor sitemap, URL or local file (repeatable)")
    p.add_argument("--fetch-titles", action="store_true", help="read the H1 or title of competitor articles (plain HTTP, capped by fetch_titles_max)")
    p.add_argument("--top", type=int, help="ideas kept (default: propose.max_ideas)")
    p.add_argument("--add", action="store_true", help="record the kept ideas as proposed lines in the registry")
    p.add_argument("--today")

    p = add("list", "The registry as Markdown.")
    p.add_argument("--status", choices=STATUSES)
    p.add_argument("--sections", action="store_true", help="list the H2 and H3 under each line")
    p.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    try:
        rules = load_rules(a.config)
        if a.cmd == "build":
            return cmd_build(a, rules)
        if a.cmd == "add":
            return cmd_add(a, rules)
        if a.cmd == "propose":
            return cmd_propose(a, rules)
        if a.cmd == "list":
            return cmd_list(a, rules)
        # check
        subjects = []
        if a.subject:
            subjects.append(a.subject)
        if a.subjects_file:
            try:
                with open(a.subjects_file, encoding="utf-8") as f:
                    subjects += [l.strip() for l in f if l.strip() and not l.startswith("#")]
            except FileNotFoundError:
                raise InputError(f"file not found: {a.subjects_file}")
        if not subjects:
            ap.error("check needs a subject or --subjects-file")
        reg = load_registry(a.registry, must_exist=True)
        m = Matcher(rules)
        res = [check_subject(s, reg, rules, m) for s in subjects]
        if a.json:
            print(json.dumps(res[0] if len(res) == 1 and not a.subjects_file else res, ensure_ascii=False, indent=2))
        else:
            print("\n".join(format_check(r) for r in res))
        return 0
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
