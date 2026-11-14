#!/usr/bin/env python3
"""variants.py: per-network rules of content-publisher.

Checks a post spec (assets/post-spec.schema.json) network by network and
composes what each network really receives:

  - LinkedIn: the body, the link in the first comment (never in the body);
  - X: one tweet of 280 weighted characters at most (URL 23, emoji and CJK 2),
    no thread unless the queue allows it, the link in the first reply;
  - Instagram: the caption, no link, a "link in bio" pointer when the post has one;
  - Threads, Bluesky: the body, the link in the first reply.

Every text (body, first comment, reply) then goes through the shared writing
gate (shared/skills/writing-gate/scripts/lint_copy.py): a BLOCK is an error.

Usage:
  python3 variants.py lint SPEC.json [--project DIR] [--queue QUEUE.json] [--no-gate] [--json]
  python3 variants.py count --network x [TEXT | -]        # length as the network counts it
  python3 variants.py compose SPEC.json [--json]          # what each network receives

Exit codes: 0 no error, 1 at least one error, 2 usage error or unreadable spec.
Platform limits and their sources: assets/platform-limits.json.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

# Any http(s) URL, a www. host, or a bare domain followed by a path. A bare
# domain without a path ("swanbase.co") is only a warning: it is often the
# brand name.
TLDS = r"(?:com|co|io|ai|org|net|app|dev|eu|fr|de|uk|so|me|xyz|gg|ly|tech|studio|club)"
URL_RE = re.compile(r"https?://[^\s<>()]+|\bwww\.[a-z0-9-]+(?:\.[a-z0-9-]+)+[^\s<>()]*", re.I)
DOMAIN_PATH_RE = re.compile(rf"(?<![@\w.])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.{TLDS}/[^\s<>()]*", re.I)
BARE_DOMAIN_RE = re.compile(rf"(?<![@\w./])[a-z0-9-]+\.{TLDS}\b(?!/)", re.I)
THREAD_SEP_RE = re.compile(r"(?m)^\s*(?:---|\d+/\d*)\s*$")
HASHTAG_RE = re.compile(r"(?<![\w#])#\w+", re.UNICODE)
# Phrases that point the reader to where the link is. The bio patterns come
# from the queue settings (link_in_bio_patterns).
POINTER_RES = {
    "first_comment": re.compile(r"\b(?:first|1st) comment\b|\bpremier commentaire\b|\blink in (?:the )?comments?\b|\blien en commentaire\b", re.I),
    "reply": re.compile(r"\b(?:first|1st) reply\b|\bpremi[eè]re r[ée]ponse\b|\blink (?:is )?below\b|\blien ci-dessous\b|\bin the replies\b", re.I),
}
PLACE_LABEL = {"first_comment": "first comment", "reply": "first reply", "bio": "bio"}


# ------------------------------------------------------------------ counting

def _x_weight(ch: str) -> int:
    """Weight of one code point in X's count (docs.x.com, Counting Characters):
    1 for the Latin, Greek, Cyrillic and general punctuation ranges listed
    there, 0 for joiners, variation selectors and skin tone modifiers, 2 for
    everything else (emoji, CJK)."""
    o = ord(ch)
    if o in (0x200D, 0xFE0E, 0xFE0F) or 0x1F3FB <= o <= 0x1F3FF:
        return 0
    if o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037:
        return 1
    return 2


def _x_run(text: str) -> int:
    """Weighted length of a text without URLs. A zero width joiner glues the
    next code point to the emoji before it, and a pair of regional indicators
    (a flag) counts once, so an emoji sequence costs 2 as X counts it. Keycap
    sequences are slightly over-counted, which errs on the safe side."""
    n = 0
    glue = False
    flag_open = False
    for ch in text:
        o = ord(ch)
        if o == 0x200D:
            glue = True
            continue
        if glue:
            glue = False
            continue
        if 0x1F1E6 <= o <= 0x1F1FF:
            flag_open = not flag_open
            if not flag_open:
                continue
        n += _x_weight(ch)
    return n


def x_length(text: str, url_weight: int = 23) -> int:
    """Weighted X length: each URL costs url_weight whatever its length."""
    text = text or ""
    n = 0
    pos = 0
    for m in URL_RE.finditer(text):
        n += _x_run(text[pos:m.start()]) + url_weight
        pos = m.end()
    return n + _x_run(text[pos:])


def graphemes(text: str) -> int:
    """Approximate user-perceived characters with the standard library:
    combining marks, joiners, variation selectors and skin tone modifiers do
    not start a new character, and a zero width joiner glues the next one."""
    n = 0
    glue = False
    for ch in text or "":
        o = ord(ch)
        if o == 0x200D:
            glue = True
            continue
        if unicodedata.combining(ch) or o in (0xFE0E, 0xFE0F) or 0x1F3FB <= o <= 0x1F3FF or 0xE0020 <= o <= 0xE007F:
            continue
        if glue:
            glue = False
            continue
        n += 1
    return n


def length(text: str, network: str, lim: Dict[str, Any]) -> int:
    mode = lim[network]["count"]
    if mode == "x_weighted":
        return x_length(text, lim[network].get("url_weight", 23))
    if mode == "graphemes":
        return graphemes(text)
    return len(text or "")


# ------------------------------------------------------------------ findings

def finding(level: str, code: str, where: str, message: str) -> Dict[str, str]:
    return {"level": level, "code": code, "where": where, "message": message}


def links_in(text: str) -> List[str]:
    return [m.group(0) for m in URL_RE.finditer(text or "")] + [m.group(0) for m in DOMAIN_PATH_RE.finditer(text or "")]


def split_thread(text: str) -> List[str]:
    return [p.strip() for p in THREAD_SEP_RE.split(text or "") if p.strip()]


def media_for(post: Dict[str, Any], network: str) -> List[Dict[str, Any]]:
    """Media a network receives: the indexes listed in the variant, else every
    item the network accepts (documents only on LinkedIn)."""
    media = post.get("media") or []
    var = (post.get("variants") or {}).get(network) or {}
    if "media" in var:
        return [media[i] for i in var["media"] if 0 <= i < len(media)]
    lim = common.limits()[network]
    out = [m for m in media if m["type"] != "document" or lim["media"].get("document")]
    if network == "linkedin" and any(m["type"] == "document" for m in out):
        out = [m for m in out if m["type"] == "document"][:1]  # a LinkedIn document post carries the PDF only
    return out


def compose(post: Dict[str, Any], network: str) -> Dict[str, Optional[str]]:
    """What the network receives: body, and the link placed outside it."""
    var = (post.get("variants") or {}).get(network) or {}
    text = (var.get("text") or "").strip()
    link = post.get("link")
    note = (post.get("link_note") or "").strip()
    placement = common.limits()[network]["link_placement"]
    first_comment = reply = None
    if placement == "first_comment":
        if (var.get("first_comment") or "").strip():
            first_comment = var["first_comment"].strip()
        elif link:
            first_comment = f"{note} {link}".strip()
    elif placement == "reply" and link:
        reply = f"{note} {link}".strip()
    return {"text": text, "first_comment": first_comment, "reply": reply}


def lint_post(post: Dict[str, Any], spec_dir: Path, settings: Dict[str, Any]) -> List[Dict[str, str]]:
    """Platform rules for one post, every network. No writing gate here."""
    lim = common.limits()
    out: List[Dict[str, str]] = []
    ref = post.get("ref", "?")
    variants = post.get("variants") or {}
    link = post.get("link")
    bio_res = [re.compile(p, re.I) for p in settings.get("link_in_bio_patterns") or common.DEFAULT_SETTINGS["link_in_bio_patterns"]]

    for i, m in enumerate(post.get("media") or []):
        if not (spec_dir / m["path"]).is_file():
            out.append(finding("error", "missing-media-file", f"{ref}.media[{i}]", f"file not found: {m['path']}"))
        if m["type"] == "image" and not (m.get("alt") or "").strip():
            out.append(finding("warning", "missing-alt", f"{ref}.media[{i}]", "image without alt text"))
    for net in variants:
        if net not in post.get("networks", []):
            out.append(finding("warning", "unused-variant", f"{ref}.{net}", f"variant {net} is written but {net} is not in networks"))

    texts_seen: Dict[str, str] = {}
    for net in post.get("networks", []):
        where = f"{ref}.{net}"
        L = lim[net]
        var = variants.get(net)
        if not var or not (var.get("text") or "").strip():
            out.append(finding("error", "missing-variant", where, f"no text for {L['label']}: write variants.{net}.text"))
            continue
        c = compose(post, net)
        text = c["text"]
        # Links never in the body.
        found = links_in(text)
        if found:
            out.append(finding("error", "link-in-body", where,
                               f"{L['label']} body holds {found[0]!r}: move it to post.link (placed in the "
                               f"{ {'first_comment': 'first comment', 'reply': 'first reply', 'bio': 'bio'}[L['link_placement']] })"))
        for m in BARE_DOMAIN_RE.finditer(text):
            out.append(finding("warning", "bare-domain", where, f"{m.group(0)!r} may become a link on {L['label']}"))
        # Length.
        parts = split_thread(text) if net == "x" else [text]
        if net == "x" and len(parts) > 1 and not settings.get("x_allow_thread"):
            out.append(finding("error", "x-thread", where, f"X text is split in {len(parts)} posts: one tweet only (the link goes in the reply)"))
        for k, part in enumerate(parts):
            n = length(part, net, lim)
            if n > L["text_max"]:
                label = f" (part {k + 1})" if len(parts) > 1 else ""
                out.append(finding("error", "over-limit", where, f"{L['label']} body{label}: {n}/{L['text_max']} ({L['count']})"))
        if L.get("fold_hint"):
            first_line = text.split("\n", 1)[0]
            if len(first_line) > L["fold_hint"]:
                out.append(finding("warning", "hook-past-fold", where,
                                   f"first line is {len(first_line)} characters; about {L['fold_hint']} show before 'see more'"))
        if L.get("bytes_hint") and len(text.encode("utf-8")) > L["bytes_hint"]:
            out.append(finding("warning", "threads-bytes", where,
                               f"{len(text.encode('utf-8'))} UTF-8 bytes; Threads may count bytes, not characters"))
        # Link placement.
        if c["first_comment"] is not None:
            if link and link not in c["first_comment"]:
                out.append(finding("error", "first-comment-without-link", where, "the first comment must hold post.link"))
            if len(c["first_comment"]) > L.get("first_comment_max", 10 ** 6):
                out.append(finding("error", "over-limit", where, f"first comment: {len(c['first_comment'])}/{L['first_comment_max']}"))
        if c["reply"] is not None:
            n = length(c["reply"], net, lim)
            if n > L.get("reply_max", L["text_max"]):
                out.append(finding("error", "over-limit", where, f"link reply: {n}/{L.get('reply_max', L['text_max'])}"))
        pointers = dict(POINTER_RES)
        pointers["bio"] = re.compile("|".join(r.pattern for r in bio_res), re.I)
        own = L["link_placement"]
        for place, rx in pointers.items():
            if place != own and rx.search(text):
                out.append(finding("error", "wrong-link-pointer", where,
                                   f"{L['label']} body points to the {PLACE_LABEL[place]}: on {L['label']} the link is in the {PLACE_LABEL[own]}"))
        has_pointer = bool(pointers[own].search(text))
        if has_pointer and not link:
            out.append(finding("error", "pointer-without-link", where, f"the body points to the {PLACE_LABEL[own]} but post.link is empty"))
        if link and not has_pointer:
            if own == "bio":
                out.append(finding("error", "missing-bio-pointer", where, "the post has a link: say it is in the bio (for example 'Link in bio.')"))
            else:
                out.append(finding("warning", "no-link-pointer", where, f"the post has a link: the body could say it is in the {PLACE_LABEL[own]}"))
        if net == "instagram" and L.get("hashtags_max") is not None:
            tags = HASHTAG_RE.findall(text)
            if len(tags) > L["hashtags_max"]:
                out.append(finding("error", "too-many-hashtags", where, f"{len(tags)} hashtags, Instagram allows {L['hashtags_max']}"))
        # Media.
        media = media_for(post, net)
        if L["media"].get("required") and not any(m["type"] in ("image", "video") for m in media):
            out.append(finding("error", "media-required", where, f"{L['label']} needs an image or a video"))
        if any(m["type"] == "document" for m in media) and not L["media"].get("document"):
            out.append(finding("error", "document-not-supported", where, f"{L['label']} does not take a PDF document: give it images"))
        imgs = [m for m in media if m["type"] == "image"]
        if L["media"].get("images_max") and len(imgs) > L["media"]["images_max"]:
            out.append(finding("error", "too-many-images", where, f"{len(imgs)} images, {L['label']} takes {L['media']['images_max']}"))
        key = " ".join(text.split()).lower()
        if key in texts_seen:
            out.append(finding("warning", "same-text", where, f"same text as {texts_seen[key]}: write a variant per network"))
        texts_seen[key] = net
    return out


# ------------------------------------------------------------------ writing gate

def writing_gate(entries: List[Tuple[str, str, str]], project: Optional[str]) -> Dict[str, Any]:
    """Run the shared writing gate on (where, language, text) entries, one call.
    Returns {"ran": bool, "results": {where: {"block", "warn", "findings"}}}."""
    if not common.WRITING_GATE.exists():
        return {"ran": False, "note": "shared writing gate not found", "results": {}}
    results: Dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="content-publisher-gate-") as tmp:
        by_lang: Dict[str, List[Tuple[str, Path]]] = {}
        for k, (where, lang, text) in enumerate(entries):
            p = Path(tmp) / f"{k:03d}.md"
            # URLs are skipped by the gate; the text is linted exactly as published.
            p.write_text(text + "\n", encoding="utf-8")
            by_lang.setdefault(lang if lang in ("en", "fr") else "auto", []).append((where, p))
        for lang, files in by_lang.items():
            cmd = [sys.executable, str(common.WRITING_GATE), "--json", "--lang", lang]
            if project:
                cmd += ["--project", project]
            r = subprocess.run(cmd + [str(p) for _, p in files], capture_output=True, text=True)
            if r.returncode not in (0, 1):
                raise common.UsageError("writing gate failed: " + (r.stderr or r.stdout).strip()[-300:])
            data = json.loads(r.stdout)
            by_path = {f["path"]: f for f in data.get("files", [])}
            for where, p in files:
                f = by_path.get(str(p), {"counts": {"BLOCK": 0, "WARN": 0}, "findings": []})
                results[where] = {"block": f["counts"]["BLOCK"], "warn": f["counts"]["WARN"], "findings": f["findings"]}
    return {"ran": True, "results": results}


def gate_entries(post: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    out = []
    for net in post.get("networks", []):
        if not ((post.get("variants") or {}).get(net) or {}).get("text"):
            continue
        c = compose(post, net)
        for part in ("text", "first_comment", "reply"):
            if c[part]:
                out.append((f"{post['ref']}.{net}.{part}", post.get("language", "auto"), c[part]))
    return out


def lint_spec(spec: Dict[str, Any], spec_dir: Path, settings: Dict[str, Any], project: Optional[str],
              gate: bool = True) -> Dict[str, Any]:
    """Schema, platform rules and writing gate for a whole spec.
    Returns {"status", "findings", "gate": {...}, "posts": {ref: {net: {...}}}}."""
    findings: List[Dict[str, str]] = []
    for e in common.schema_errors(spec, common.SPEC_SCHEMA):
        findings.append(finding("error", "schema", "spec", e))
    if findings:
        return {"status": "fail", "findings": findings, "gate": {"ran": False}, "posts": {}}
    refs = [p["ref"] for p in spec["posts"]]
    for r in sorted({r for r in refs if refs.count(r) > 1}):
        findings.append(finding("error", "duplicate-ref", r, "two posts share this ref"))
    entries: List[Tuple[str, str, str]] = []
    for post in spec["posts"]:
        findings.extend(lint_post(post, spec_dir, settings))
        entries.extend(gate_entries(post))
    gate_info: Dict[str, Any] = {"ran": False, "note": "skipped (--no-gate)"}
    if gate:
        gate_info = writing_gate(entries, project)
        for where, res in gate_info.get("results", {}).items():
            for f in res["findings"]:
                lvl = "error" if f["level"] == "BLOCK" else "warning"
                findings.append(finding(lvl, f"writing-gate:{f['code']}", where, f"{f['match']!r}: {f['message']}"))
        if not gate_info["ran"]:
            findings.append(finding("warning", "writing-gate-missing", "spec", gate_info.get("note", "")))
    status = "fail" if any(f["level"] == "error" for f in findings) else "pass"
    return {"status": status, "findings": findings, "gate": gate_info}


def print_findings(report: Dict[str, Any]) -> None:
    for f in report["findings"]:
        print(f"  {f['level'].upper():<7} {f['code']:<34} {f['where']}: {f['message']}")
    n_err = sum(f["level"] == "error" for f in report["findings"])
    n_warn = len(report["findings"]) - n_err
    print(f"\nLint: {report['status'].upper()} ({n_err} errors, {n_warn} warnings)")


# ------------------------------------------------------------------ cli

def settings_from(queue: Optional[str]) -> Dict[str, Any]:
    if queue and Path(queue).exists():
        return common.load_queue(Path(queue))["settings"]
    return json.loads(json.dumps(common.DEFAULT_SETTINGS))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint", help="schema, platform rules and writing gate of a post spec")
    p.add_argument("spec")
    p.add_argument("--project", help="project folder: loads its voice rules into the writing gate")
    p.add_argument("--queue", help="queue.json whose settings apply (x_allow_thread, link_in_bio_patterns)")
    p.add_argument("--no-gate", action="store_true", help="platform rules only (the queue refuses specs that skipped the gate)")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("count", help="length of a text as a network counts it")
    p.add_argument("--network", required=True, choices=common.NETWORKS)
    p.add_argument("text", nargs="?", default="-")
    p = sub.add_parser("compose", help="print what each network receives")
    p.add_argument("spec")
    p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "count":
            text = sys.stdin.read() if args.text == "-" else args.text
            lim = common.limits()
            n = length(text.strip(), args.network, lim)
            print(f"{n}/{lim[args.network]['text_max']} ({lim[args.network]['count']})")
            return 0 if n <= lim[args.network]["text_max"] else 1
        spec_path = Path(args.spec)
        spec = common.read_json(spec_path)
        if args.cmd == "compose":
            out = {p["ref"]: {n: compose(p, n) for n in p.get("networks", [])} for p in spec.get("posts", [])}
            print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else
                  "\n\n".join(f"## {ref}.{n}\n{c['text']}" + (f"\n[first comment] {c['first_comment']}" if c["first_comment"] else "")
                              + (f"\n[reply] {c['reply']}" if c["reply"] else "")
                              for ref, nets in out.items() for n, c in nets.items()))
            return 0
        report = lint_spec(spec, spec_path.parent, settings_from(args.queue), args.project, gate=not args.no_gate)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"{spec_path}")
            print_findings(report)
        return 0 if report["status"] == "pass" else 1
    except common.UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
