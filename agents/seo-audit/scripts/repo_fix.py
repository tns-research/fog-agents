#!/usr/bin/env python3
"""
repo_fix.py

Optional repo mode of seo-audit: from a defect found in the served HTML to
the line of the site's source code that produces it, as a unified patch per
file. Runs only when the founder gives the path of the site's source
repository. The repository is read, never written: patches are checked with
`git apply --check` on a temporary copy of the touched files.

    python3 repo_fix.py plan  --crawl <run>/crawl.jsonl --repo <site-repo> --out-dir <run>/repo-fix [--config C]
    python3 repo_fix.py fill  --out-dir <run>/repo-fix --fills <run>/repo-fix/fills.json
    python3 repo_fix.py check --out-dir <run>/repo-fix [--json]

Defects (from crawl.jsonl and the E-E-A-T rules of eeat.py): title missing or
too long, meta description missing, H1 missing or multiple, image without
alt, canonical missing, dateModified or author missing in the JSON-LD of an
article, internal link to a page that answers 4xx or 5xx.

Where the source is searched: files .html .htm .md .mdx .markdown .astro
.jsx .tsx .vue .njk (frontmatter included; build folders, node_modules and
.git skipped). A page's source is the file whose path maps to the URL
(src/pages/blog/x.astro, src/content/blog/x.md, x/index.md, a frontmatter
slug or permalink); its scope adds the frontmatter layout and the imported
or included files. A value is searched in that scope first, then in the
whole repository. One location gives a patch; zero or several give an item
"to locate by hand" with the candidates, never a guessed patch.

Text the script cannot know (a new title, a meta description, an alt text,
an H1, a working URL, a JSON-LD value) is written as a placeholder
`TODO(seo-audit) pNN: <instruction>`. The model writes the values in
fills.json (null drops the fix), `fill` rebuilds the patches with them, and
`check` blocks any placeholder left, a value outside its length bounds
(assets/crawl-rules.json), a URL that is not a 200 page of the crawl, or a
patch that no longer applies.

Writes (in --out-dir):
  patches/<file>.patch   one unified patch per source file (a/ b/ paths)
  repo-fix.json          defects, fixes, manual items, placeholders, git check
  repo-fix.md            the "Source fixes" section of the report
  fills.json             the placeholders to fill (values empty)

Exit codes: plan and fill 0 written, 1 a patch failed `git apply --check`
or git is missing; check 0 clean, 1 at least one BLOCK; 2 usage or
unreadable input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from difflib import unified_diff
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_lib import InputError, deep_merge, load_assets_json, load_json, path_of, read_jsonl, write_json, write_text  # noqa: E402
import eeat  # noqa: E402

SOURCE_EXT = (".html", ".htm", ".md", ".mdx", ".markdown", ".astro", ".jsx", ".tsx", ".vue", ".njk")
YAML_FM_EXT = (".md", ".mdx", ".markdown", ".html", ".htm", ".njk")
MD_EXT = (".md", ".mdx", ".markdown")
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", ".astro", ".svelte-kit", "out", "_site", ".output",
             ".vercel", ".netlify", "coverage", "vendor", ".cache", "__pycache__"}
ROOT_DIRS = {"src", "pages", "content", "app", "site", "public", "routes", "views", "templates", "www", "docs", "_pages", "posts", "_posts"}
TITLE_SEPARATORS = (" | ", " - ", " \u00b7 ", " \u2013 ", " \u2014 ", " / ")
TAG = "TODO(seo-audit)"
MAX_FILE = 1_000_000
LIMITS = {"alt": (1, 125), "h1": (1, 70), "expression": (1, 300), "url": (1, 300)}


# --------------------------------------------------------------------------
# repository index

class Repo:
    def __init__(self, root: str) -> None:
        if not os.path.isdir(root):
            raise InputError(f"--repo {root} is not a folder")
        self.root = os.path.abspath(root)
        self.lines: Dict[str, List[str]] = {}
        for d, dirs, files in os.walk(self.root):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
            for f in sorted(files):
                if not f.lower().endswith(SOURCE_EXT):
                    continue
                full = os.path.join(d, f)
                if os.path.getsize(full) > MAX_FILE:
                    continue
                rel = os.path.relpath(full, self.root).replace(os.sep, "/")
                with open(full, "r", encoding="utf-8", errors="replace", newline="") as fh:
                    self.lines[rel] = fh.read().splitlines(keepends=True)
        self.files = sorted(self.lines)

    def text(self, rel: str) -> str:
        return "".join(self.lines[rel])

    def frontmatter(self, rel: str) -> Optional[Dict[str, Any]]:
        if not rel.lower().endswith(YAML_FM_EXT):
            return None
        L = self.lines[rel]
        if not L or L[0].strip() != "---":
            return None
        for i in range(1, len(L)):
            if L[i].strip() == "---":
                keys = {}
                for j in range(1, i):
                    m = re.match(r"([A-Za-z_][\w-]*)\s*:", L[j])
                    if m:
                        keys[m.group(1)] = j
                return {"end": i, "keys": keys}
        return None

    def fm_value(self, rel: str, key: str) -> Optional[str]:
        fm = self.frontmatter(rel)
        if not fm or key not in fm["keys"]:
            return None
        return self.lines[rel][fm["keys"][key]].split(":", 1)[1].strip().strip("'\"")

    def resolve(self, frm: str, spec: str) -> Optional[str]:
        spec = spec.strip()
        bases = []
        if spec.startswith("."):
            bases.append(os.path.normpath(os.path.join(os.path.dirname(frm), spec)).replace(os.sep, "/"))
        elif spec.startswith(("@/", "~/")):
            bases.append("src/" + spec[2:])
        elif spec.startswith("/"):
            bases.append(spec.lstrip("/"))
        else:
            bases += [os.path.normpath(os.path.join(os.path.dirname(frm), spec)).replace(os.sep, "/"), spec,
                      f"_layouts/{spec}", f"_includes/{spec}", f"src/layouts/{spec}", f"src/_includes/{spec}", f"layouts/{spec}"]
        for b in bases:
            for cand in [b] + [b + e for e in SOURCE_EXT]:
                if cand in self.lines:
                    return cand
        return None

    def refs(self, rel: str) -> List[str]:
        out = []
        layout = self.fm_value(rel, "layout")
        if layout:
            r = self.resolve(rel, layout)
            if r:
                out.append(r)
        text = self.text(rel)
        for m in re.finditer(r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|\{%-?\s*(?:extends|include|import)\s+|@include\s*\(\s*)["']([^"']+)["']""", text):
            r = self.resolve(rel, m.group(1))
            if r and r not in out:
                out.append(r)
        return out

    def scope(self, rel: str) -> List[str]:
        out, frontier = [rel], [rel]
        for _ in range(3):
            nxt = []
            for f in frontier:
                for r in self.refs(f):
                    if r not in out:
                        out.append(r)
                        nxt.append(r)
            frontier = nxt
        return out

    def find(self, rx: "re.Pattern[str]", files: List[str]) -> List[Tuple[str, int]]:
        return [(f, i) for f in files for i, line in enumerate(self.lines[f]) if rx.search(line)]


def route_of(rel: str) -> List[str]:
    stem = rel.rsplit(".", 1)[0]
    segs = [s for s in stem.split("/") if s]
    if segs and segs[-1] in ("index", "page", "+page", "README"):
        segs = segs[:-1]
    return segs


def maps(segs: List[str], want: List[str]) -> bool:
    """A file route (path segments) serves the URL path: same tail, and only root folders before it."""
    if len(segs) < len(want) or segs[len(segs) - len(want):] != want:
        return False
    return all(s in ROOT_DIRS for s in segs[:len(segs) - len(want)])


def route_candidates(repo: Repo, url: str) -> List[str]:
    want = [s for s in path_of(url).split("?")[0].strip("/").split("/") if s]
    out = []
    for f in repo.files:
        segs = route_of(f)
        if want:
            hit = maps(segs, want)
        else:
            hit = maps(segs, want) and f.rsplit("/", 1)[-1].startswith("index.")
        link = repo.fm_value(f, "permalink")
        if link is not None and [x for x in link.strip("/").split("/") if x] == want:
            hit = True
        slug = repo.fm_value(f, "slug")
        if slug and want and maps(route_of(f)[:-1] + [slug.strip("/")], want):
            hit = True
        if hit:
            out.append(f)
    return out


def title_parts(title: str) -> List[str]:
    parts = [title]
    for sep in TITLE_SEPARATORS:
        for p in title.split(sep):
            p = p.strip()
            if len(p) >= 4 and p not in parts:
                parts.append(p)
    return parts


def locate_page(repo: Repo, rec: Dict[str, Any]) -> Tuple[Optional[str], List[str], str]:
    route = route_candidates(repo, rec["url"])
    if len(route) == 1:
        return route[0], route, "path maps to the URL"
    texts = [h for h in (rec.get("h1") or []) if h and len(h) >= 4][:1] + [p for p in title_parts(rec.get("title") or "") if len(p) >= 10][:2]
    pool = route or repo.files
    hits = [f for f in pool if any(t in repo.text(f) for t in texts)] if texts else []
    if len(hits) == 1:
        return hits[0], hits, ("path and text match" if route else "only file holding the H1 or title text")
    cands = hits or route
    return None, cands, ("several source files match the URL" if cands else "no source file maps to the URL or holds its H1 or title")


# --------------------------------------------------------------------------
# plan

class Planner:
    def __init__(self, repo: Repo, crawl_path: str, rules: Dict[str, Any], W: Dict[str, Any]) -> None:
        self.repo = repo
        self.rules = rules
        self.W = W
        self.crawl_name = os.path.basename(crawl_path)
        self.lines = read_jsonl(crawl_path)
        self.by_url = {r["url"]: (n, r) for n, r in self.lines}
        self.fixes: Dict[Tuple, Dict[str, Any]] = {}
        self.manual: List[Dict[str, Any]] = []
        self.defects: List[Dict[str, Any]] = []
        self.jsonld: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.pages: Dict[str, Tuple[Optional[str], List[str], str]] = {}

    def ref(self, n: int) -> str:
        return f"{self.crawl_name}:{n}"

    def ok_paths(self) -> List[str]:
        return sorted({path_of(r["url"]) for _, r in self.lines if r.get("status") == 200 and not r.get("redirect_chain")})

    def page(self, rec: Dict[str, Any]) -> Tuple[Optional[str], List[str], str]:
        if rec["url"] not in self.pages:
            self.pages[rec["url"]] = locate_page(self.repo, rec)
        return self.pages[rec["url"]]

    def defect(self, code: str, n: int, rec: Dict[str, Any], detail: str) -> Dict[str, Any]:
        d = {"id": f"d{len(self.defects) + 1:03d}", "code": code, "url": rec["url"], "ref": self.ref(n), "detail": detail}
        self.defects.append(d)
        return d

    def hand(self, d: Dict[str, Any], reason: str, cands: List[Any]) -> None:
        d["status"] = "manual"
        loc = [c if isinstance(c, str) else f"{c[0]}:{c[1] + 1}" for c in cands]
        self.manual.append({"defect": d["id"], "code": d["code"], "url": d["url"], "ref": d["ref"], "detail": d["detail"],
                            "reason": reason, "candidates": loc[:10]})

    def add_fix(self, d: Dict[str, Any], file: str, line: int, op: str, new: List[str], placeholders: List[Dict[str, Any]], how: str) -> None:
        key = (file, line, op, tuple(new))
        f = self.fixes.get(key)
        if not f:
            f = {"file": file, "line": line + 1, "op": op, "old": self.repo.lines[file][line].rstrip("\r\n"), "new": new,
                 "placeholders": placeholders, "defects": [], "codes": [], "urls": [], "how": how}
            self.fixes[key] = f
        f["defects"].append(d["id"])
        if d["code"] not in f["codes"]:
            f["codes"].append(d["code"])
        if d["url"] not in f["urls"]:
            f["urls"].append(d["url"])
        d["status"] = "fixed"
        d["fix_line"] = f"{file}:{line + 1}"

    # -- helpers ---------------------------------------------------------
    def indent(self, file: str, i: int) -> str:
        return re.match(r"[ \t]*", self.repo.lines[file][i]).group(0)

    def ph(self, kind: str, instruction: str, lo: int, hi: int, forbid: Optional[str], quoted: bool = False) -> Dict[str, Any]:
        return {"kind": kind, "instruction": instruction, "min": lo, "max": hi, "forbid": forbid, "quoted": quoted}

    def scoped(self, rec: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        src, _, _ = self.page(rec)
        return src, (self.repo.scope(src) if src else [])

    def search(self, rx: "re.Pattern[str]", scope: List[str]) -> List[Tuple[str, int]]:
        hits = self.repo.find(rx, scope) if scope else []
        return hits or self.repo.find(rx, self.repo.files)

    # -- defects ---------------------------------------------------------
    def run(self) -> None:
        for n, rec in self.lines:
            if not eeat.html_ok(rec):
                continue
            issues = set(rec.get("issues") or [])
            if "title-missing" in issues:
                self.fix_head_text(self.defect("title-missing", n, rec, "no <title>"), rec, "title")
            if "title-long" in issues:
                self.fix_title_long(self.defect("title-long", n, rec, f"{rec['title_length']} characters"), rec)
            if "description-missing" in issues:
                self.fix_head_text(self.defect("description-missing", n, rec, "no meta description"), rec, "description")
            if "h1-missing" in issues:
                self.fix_h1_missing(self.defect("h1-missing", n, rec, "no H1"), rec)
            if "h1-multiple" in issues:
                for h in (rec.get("h1") or [])[1:]:
                    self.fix_h1_extra(self.defect("h1-multiple", n, rec, f"extra H1 `{h}`"), rec, h)
            for img in rec.get("images_no_alt_src") or []:
                self.fix_img(self.defect("img-alt-missing", n, rec, f"img `{img['src']}`"), rec, img)
            if "canonical-missing" in issues:
                self.fix_canonical(self.defect("canonical-missing", n, rec, "no rel=canonical"), rec)
            arts = eeat.article_entities(rec.get("eeat_raw") or {}, self.W)
            if arts and not any(e.get("date_modified") for e in arts):
                self.need_jsonld(self.defect("jsonld-datemodified-missing", n, rec, f"{arts[0]['path']} has no dateModified"), rec, "dateModified")
            if arts and not any(a.get("name") for e in arts for a in e.get("author", [])):
                self.need_jsonld(self.defect("jsonld-author-missing", n, rec, f"{arts[0]['path']} has no author"), rec, "author")
            for link in rec.get("internal_links") or []:
                t = self.by_url.get(link)
                if t and (t[1].get("status") or 0) >= 400:
                    self.fix_link(self.defect("broken-internal-link", n, rec, f"link to {link} answers {t[1]['status']}"), rec, link, t[1]["status"])
        self.flush_jsonld()

    def fix_head_text(self, d: Dict[str, Any], rec: Dict[str, Any], what: str) -> None:
        src, cands, reason = self.page(rec)
        if not src:
            return self.hand(d, reason, cands)
        R = self.rules
        if what == "title":
            ph = self.ph("title", f"title of at most {R['title_max_chars']} characters", 1, R["title_max_chars"], '"')
        else:
            ph = self.ph("description", f"meta description of {R['description_min_chars']} to {R['description_max_chars']} characters",
                         R["description_min_chars"], R["description_max_chars"], '"')
        fm = self.repo.frontmatter(src)
        if fm:
            if what in fm["keys"]:
                i = fm["keys"][what]
                return self.add_fix(d, src, i, "replace", [f'{what}: "\x00"'], [ph], f"frontmatter `{what}` of the page source")
            return self.add_fix(d, src, fm["end"], "insert_before", [f'{what}: "\x00"'], [ph], f"frontmatter of the page source, `{what}` added")
        L = self.repo.lines[src]
        if what == "title":
            empty = [i for i, l in enumerate(L) if re.search(r"<title>\s*</title>", l)]
            if len(empty) == 1:
                new = re.sub(r"<title>\s*</title>", "<title>\x00</title>", L[empty[0]].rstrip("\r\n"), count=1)
                return self.add_fix(d, src, empty[0], "replace", [new], [dict(ph, forbid="<")], "empty <title> of the page source")
        heads = [i for i, l in enumerate(L) if re.search(r"<head[\s>]", l)]
        if len(heads) == 1 and not re.fullmatch(r"\s*<head\b[^>]*>\s*", L[heads[0]]):
            return self.hand(d, f"the <head> of {src} is not on its own line: edit it by hand", [(src, heads[0])])
        if len(heads) == 1:
            i = heads[0]
            pad = self.indent(src, i + 1) if i + 1 < len(L) else self.indent(src, i)
            close = " />" if src.endswith((".astro", ".jsx", ".tsx", ".vue")) else ">"
            line = f"{pad}<title>\x00</title>" if what == "title" else f'{pad}<meta name="description" content="\x00"{close}'
            return self.add_fix(d, src, i, "insert_after", [line], [ph if what != "title" else dict(ph, forbid="<")], "<head> of the page source")
        self.hand(d, f"the page source {src} has no frontmatter and no <head>: the {what} comes from a layout or a data file", [src])

    def fix_title_long(self, d: Dict[str, Any], rec: Dict[str, Any]) -> None:
        src, scope = self.scoped(rec)
        served = rec.get("title") or ""
        hits: List[Tuple[str, int]] = []
        found = ""
        for part in [p for p in title_parts(served) if len(p) >= 10]:
            hits = self.search(re.compile(re.escape(part)), scope)
            if hits:
                found = part
                break
        if not hits:
            return self.hand(d, "the served title is not found in the repository", [])
        strong = [h for h in hits if re.search(r"(^\s*title\s*:|<title|\btitle\s*=|[\"']?title[\"']?\s*:)", self.repo.lines[h[0]][h[1]], re.I)]
        pick = strong or hits
        if len(pick) != 1:
            return self.hand(d, "the title text is in several places", pick)
        f, i = pick[0]
        budget = self.rules["title_max_chars"] - (len(served) - len(found))
        if budget < 10:
            return self.hand(d, f"the part added around `{found}` leaves {budget} characters", pick)
        line = self.repo.lines[f][i].rstrip("\r\n")
        extra = f" (the template adds {len(served) - len(found)})" if len(served) > len(found) else ""
        ph = self.ph("title", f"title of at most {budget} characters{extra}", 1, budget, '"')
        fm = self.repo.frontmatter(f)
        if fm and fm["keys"].get("title") == i:
            return self.add_fix(d, f, i, "replace", ['title: "\x00"'], [ph], "frontmatter `title`")
        pos = line.find(found)
        before = line[pos - 1] if pos > 0 else ""
        ph["forbid"] = before if before in "\"'`" else "<"
        self.add_fix(d, f, i, "replace", [line[:pos] + "\x00" + line[pos + len(found):]], [ph], "title text")

    def fix_h1_missing(self, d: Dict[str, Any], rec: Dict[str, Any]) -> None:
        src, cands, reason = self.page(rec)
        if not src:
            return self.hand(d, reason, cands)
        ph = self.ph("h1", "H1 of the page, one per page", *LIMITS["h1"], forbid="<")
        L = self.repo.lines[src]
        if src.endswith(MD_EXT):
            fm = self.repo.frontmatter(src)
            if fm:
                return self.add_fix(d, src, fm["end"], "insert_after", ["", "# \x00"], [ph], "first line after the frontmatter")
            return self.add_fix(d, src, 0, "insert_before", ["# \x00", ""], [ph], "first line of the page source")
        for tag in ("<main", "<article", "<body"):
            idx = [i for i, l in enumerate(L) if re.fullmatch(r"\s*" + re.escape(tag) + r"\b[^>]*>\s*", l)]
            if len(idx) == 1:
                i = idx[0]
                pad = self.indent(src, i + 1) if i + 1 < len(L) else self.indent(src, i)
                return self.add_fix(d, src, i, "insert_after", [f"{pad}<h1>\x00</h1>"], [ph], f"after {tag}> of the page source")
        self.hand(d, f"no <main>, <article> or <body> on its own line in {src}", [src])

    def fix_h1_extra(self, d: Dict[str, Any], rec: Dict[str, Any], text: str) -> None:
        _, scope = self.scoped(rec)
        t = re.escape(text)
        rx = re.compile(r"^\s{0,3}#\s+" + t + r"\s*#*\s*$|<h1\b[^>]*>\s*" + t + r"\s*</h1>")
        hits = self.search(rx, scope)
        if len(hits) != 1:
            return self.hand(d, "the extra H1 is in several places" if hits else "the extra H1 is not found as a heading line", hits)
        f, i = hits[0]
        line = self.repo.lines[f][i].rstrip("\r\n")
        if re.match(r"^\s{0,3}#\s", line):
            new = re.sub(r"#", "##", line, count=1)
        else:
            new = re.sub(r"</h1>", "</h2>", re.sub(r"<h1\b", "<h2", line, count=1), count=1)
        self.add_fix(d, f, i, "replace", [new], [], "extra H1 demoted to H2 (the first H1 of the page is kept)")

    def fix_img(self, d: Dict[str, Any], rec: Dict[str, Any], img: Dict[str, Any]) -> None:
        src_attr = img["src"]
        if img.get("alt_attr"):
            return self.hand(d, "empty alt: right for a decorative image, otherwise write the text by hand", [])
        if not src_attr:
            return self.hand(d, "image without src", [])
        _, scope = self.scoped(rec)
        tokens = [src_attr]
        p = urllib.parse.urlsplit(src_attr)
        if p.scheme in ("http", "https"):
            tokens.append(p.path)
        base = os.path.basename(p.path)
        if base and base not in tokens:
            tokens.append(base)
        hits: List[Tuple[str, int]] = []
        for tok in tokens:
            rx = re.compile(r"(src\s*=\s*[\"'{`]?[^\"'`>]*|!\[\]\([^)]*)" + re.escape(tok))
            hits = self.search(rx, scope)
            if hits:
                break
        if len(hits) != 1:
            return self.hand(d, "the image is used in several files" if hits else "the image src is not found in the repository", hits)
        f, i = hits[0]
        line = self.repo.lines[f][i].rstrip("\r\n")
        md = re.search(r"!\[\]\(([^)]*" + re.escape(tok) + r")", line)
        if md:
            new = line[:md.start()] + "![\x00](" + line[md.start() + 4:]
            ph = self.ph("alt", "alt text: what the image shows, for a reader who cannot see it", *LIMITS["alt"], forbid="]")
            return self.add_fix(d, f, i, "replace", [new], [ph], "markdown image")
        if re.search(r"\balt\s*=", line):
            return self.hand(d, "the tag has an alt attribute set elsewhere (dynamic value)", hits)
        m = re.search(r"\bsrc\s*=", line)
        new = line[:m.start()] + 'alt="\x00" ' + line[m.start():]
        ph = self.ph("alt", "alt text: what the image shows, for a reader who cannot see it", *LIMITS["alt"], forbid='"')
        self.add_fix(d, f, i, "replace", [new], [ph], "img tag")

    def fix_canonical(self, d: Dict[str, Any], rec: Dict[str, Any]) -> None:
        src, cands, reason = self.page(rec)
        if not src:
            return self.hand(d, reason, cands)
        head_files = [f for f in self.repo.scope(src) if any(re.search(r"<head[\s>]", l) for l in self.repo.lines[f])]
        if not head_files:
            return self.hand(d, f"no <head> in {src} or its layouts", [src])
        f = src if src in head_files else (head_files[0] if len(head_files) == 1 else None)
        if not f:
            return self.hand(d, "several layouts hold a <head>", head_files)
        L = self.repo.lines[f]
        close = [i for i, l in enumerate(L) if "</head>" in l]
        if len(close) != 1 or not L[close[0]].strip().startswith("</head>"):
            return self.hand(d, f"{f} has no single </head> on its own line", [f])
        i = close[0]
        pad = self.indent(f, i - 1) if i > 0 else self.indent(f, i)
        end = " />" if f.endswith((".astro", ".jsx", ".tsx", ".vue")) else ">"
        if f == src:
            url = rec.get("final_url") or rec["url"]
            return self.add_fix(d, f, i, "insert_before", [f'{pad}<link rel="canonical" href="{url}"{end}'], [],
                                "page source: canonical on the page's own URL")
        ph = self.ph("expression", "expression of this layout that prints the page's own absolute URL", *LIMITS["expression"], None, quoted=True)
        self.add_fix(d, f, i, "insert_before", [f"{pad}<link rel=\"canonical\" href=\x00{end}"], [ph], "shared layout of the page")

    def need_jsonld(self, d: Dict[str, Any], rec: Dict[str, Any], key: str) -> None:
        src, cands, reason = self.page(rec)
        if not src:
            return self.hand(d, reason, cands)
        rx = re.compile(r"[\"']?datePublished[\"']?\s*:")
        hits = self.repo.find(rx, self.repo.scope(src))
        if len(hits) != 1:
            return self.hand(d, "the JSON-LD with datePublished is in several places" if hits else "no JSON-LD with datePublished found", hits)
        f, i = hits[0]
        line = self.repo.lines[f][i]
        if line.count(":") > 1 and "{" in line:
            return self.hand(d, "the JSON-LD is written on one line: edit it by hand", hits)
        entry = self.jsonld.setdefault((f, i), {"keys": [], "defects": []})
        if key not in entry["keys"]:
            entry["keys"].append(key)
        entry["defects"].append(d)

    def flush_jsonld(self) -> None:
        for (f, i), e in sorted(self.jsonld.items()):
            line = self.repo.lines[f][i].rstrip("\r\n")
            pad = self.indent(f, i)
            quote = '"' if line.strip().startswith('"') else ("'" if line.strip().startswith("'") else "")
            comma = line.rstrip().endswith(",")
            keys = [k for k in ("dateModified", "author") if k in e["keys"]]
            phs, new = [], []
            for n, k in enumerate(keys):
                instr = ("date of the last real update (ISO 8601) or the field that holds it" if k == "dateModified"
                         else "author of the article as a Person (name, url of the author page) or the field that holds it; never an invented name")
                phs.append(self.ph("expression", instr, *LIMITS["expression"], None, quoted=True))
                last = n == len(keys) - 1
                new.append(f"{pad}{quote}{k}{quote}: \x00" + ("," if comma or not last else ""))
            base = line if comma else line.rstrip() + ","
            for d in e["defects"]:
                self.add_fix(d, f, i, "replace", [base] + new, phs, "JSON-LD of the article, after datePublished")

    def fix_link(self, d: Dict[str, Any], rec: Dict[str, Any], target: str, status: int) -> None:
        _, scope = self.scoped(rec)
        p = path_of(target)
        for tok in (target, p):
            rx = re.compile(r"(?<=[\"'(`])" + re.escape(tok) + r"(?=[\"')`#?])")
            hits = self.search(rx, scope)
            if hits:
                break
        if len(hits) != 1:
            return self.hand(d, "the link is in several files" if hits else "the link is not found in the repository", hits)
        f, i = hits[0]
        line = self.repo.lines[f][i].rstrip("\r\n")
        m = rx.search(line)
        toggled = target[:-1] if target.endswith("/") else target + "/"
        t = self.by_url.get(toggled)
        if t and t[1].get("status") == 200 and not t[1].get("redirect_chain"):
            repl = toggled if tok == target else path_of(toggled)
            return self.add_fix(d, f, i, "replace", [line[:m.start()] + repl + line[m.end():]], [],
                                f"link to the slash variant that answers 200 ({self.ref(t[0])})")
        quote = line[m.start() - 1]
        ph = self.ph("url", f"URL that answers 200 in the crawl (was {p}, answers {status}), or drop the fix", *LIMITS["url"],
                     forbid=quote if quote in "\"'`" else ")")
        self.add_fix(d, f, i, "replace", [line[:m.start()] + "\x00" + line[m.end():]], [ph], "link target")


# --------------------------------------------------------------------------
# patches

def number_placeholders(fixes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out, n = [], 0
    for fx in fixes:
        lines = list(fx["new"])
        for ph in fx["placeholders"]:
            n += 1
            ph["id"] = f"p{n:02d}"
            token = f"{TAG} {ph['id']}: {ph['instruction']}"
            ph["token"] = f'"{token}"' if ph["quoted"] else token
            for j, l in enumerate(lines):
                if "\x00" in l:
                    pos = l.index("\x00")
                    ph["prefix"], ph["suffix"] = l[:pos], l[pos + 1:]
                    lines[j] = l[:pos] + ph["token"] + l[pos + 1:]
                    break
            ph["fix"] = fx["id"]
            out.append(ph)
        fx["new"] = lines
    return out


def build_patches(repo: Repo, fixes: List[Dict[str, Any]], values: Dict[str, Optional[str]]) -> Dict[str, Tuple[str, List[str]]]:
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for fx in fixes:
        by_file.setdefault(fx["file"], []).append(fx)
    out = {}
    for f in sorted(by_file):
        old = repo.lines[f]
        eol = "\r\n" if old and old[0].endswith("\r\n") else "\n"
        before: Dict[int, List[str]] = {}
        after: Dict[int, List[str]] = {}
        repl: Dict[int, List[str]] = {}
        for fx in by_file[f]:
            lines = []
            for l in fx["new"]:
                for ph in fx["placeholders"]:
                    v = values.get(ph["id"])
                    if v:
                        l = l.replace(ph["token"], v)
                lines.append(l)
            i = fx["line"] - 1
            target = {"insert_before": before, "insert_after": after, "replace": repl}[fx["op"]]
            target.setdefault(i, []).extend(lines)
        new: List[str] = []
        for i, line in enumerate(old):
            new.extend(l + eol for l in before.get(i, []))
            if i in repl:
                end = line[len(line.rstrip("\r\n")):]
                rl = repl[i]
                new.extend(l + eol for l in rl[:-1])
                new.append(rl[-1] + end)
            else:
                new.append(line)
            new.extend(l + eol for l in after.get(i, []))
        if new == old:
            continue
        diff = []
        for l in unified_diff(old, new, f"a/{f}", f"b/{f}"):
            if l.startswith(("---", "+++", "@@")):
                diff.append(l if l.endswith("\n") else l + "\n")
            elif l.endswith("\n"):
                diff.append(l)
            else:
                diff.append(l + "\n\\ No newline at end of file\n")
        out[f] = ("".join(diff), [fx["id"] for fx in by_file[f]])
    return out


def patch_name(rel: str) -> str:
    return rel.replace("/", "__") + ".patch"


def git_check(repo_root: str, patch_files: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """git apply --check of each patch on a temporary copy of the files it touches."""
    if not shutil.which("git"):
        return {rel: {"ok": False, "message": "git not found: patch not checked"} for rel in patch_files}
    res = {}
    tmp = tempfile.mkdtemp(prefix="repo-fix-check-")
    try:
        subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
        for rel in patch_files:
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(repo_root, rel), dst)
        for rel, pf in sorted(patch_files.items()):
            r = subprocess.run(["git", "-C", tmp, "apply", "--check", "--whitespace=nowarn", os.path.abspath(pf)],
                               capture_output=True, text=True)
            res[rel] = {"ok": r.returncode == 0, "message": (r.stderr or r.stdout).strip()[:400]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return res


def write_patches(out_dir: str, repo: Repo, fixes: List[Dict[str, Any]], values: Dict[str, Optional[str]]) -> List[Dict[str, Any]]:
    pdir = os.path.join(out_dir, "patches")
    if os.path.isdir(pdir):
        for x in os.listdir(pdir):
            if x.endswith(".patch"):
                os.remove(os.path.join(pdir, x))
    os.makedirs(pdir, exist_ok=True)
    built = build_patches(repo, fixes, values)
    files = {}
    for rel, (text, _) in built.items():
        pf = os.path.join(pdir, patch_name(rel))
        with open(pf, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        files[rel] = pf
    checks = git_check(repo.root, files)
    return [{"file": rel, "patch": f"patches/{patch_name(rel)}", "fixes": built[rel][1], "git_apply_check": checks[rel]}
            for rel in sorted(built)]


# --------------------------------------------------------------------------
# value checks

def value_problems(ph: Dict[str, Any], value: Optional[str], ok_paths: List[str]) -> List[str]:
    if value is None:
        return []
    v = value
    probs = []
    if TAG in v:
        return ["placeholder left"]
    if not v.strip():
        probs.append("empty value")
    if "\n" in v or "\r" in v:
        probs.append("value on several lines")
    if ph.get("forbid") and ph["forbid"] in v:
        probs.append(f"value holds {ph['forbid']}, the character that closes it")
    n = len(v)
    if n < ph["min"] or n > ph["max"]:
        probs.append(f"{n} characters, expected {ph['min']} to {ph['max']}")
    if ph["kind"] == "url":
        if re.search(r"\s", v) or not (v.startswith("/") or re.match(r"https?://", v)):
            probs.append("not a URL or a path")
        elif v.startswith("/") and v.split("#")[0].split("?")[0] not in ok_paths:
            probs.append(f"{v} is not a 200 page of the crawl")
    return probs


# --------------------------------------------------------------------------
# outputs

def render_md(plan: Dict[str, Any]) -> str:
    L = ["## Source fixes (repo mode)", "",
         f"From `repo-fix.json` (`repo_fix.py`): {len(plan['defects'])} defect(s), {len(plan['fixes'])} fix(es) in {len(plan['patches'])} patch(es), "
         f"{len(plan['manual'])} to locate by hand. The repository is never modified: apply a patch with `git apply <patch>` "
         "once every placeholder is filled and `repo_fix.py check` exits 0.", ""]
    if plan["patches"]:
        L += ["| Patch | Fixes | git apply --check |", "|---|---|---|"]
        for p in plan["patches"]:
            st = "ok" if p["git_apply_check"]["ok"] else "FAILED: " + p["git_apply_check"]["message"].replace("|", "\\|")[:120]
            L.append(f"| `{p['patch']}` | {', '.join(p['fixes'])} | {st} |")
        L += ["", "| Fix | Defect | Pages | Source line | How |", "|---|---|---|---|---|"]
        for fx in plan["fixes"]:
            pages = ", ".join(fx["urls"][:3]) + (f" (+{len(fx['urls']) - 3})" if len(fx["urls"]) > 3 else "")
            L.append(f"| {fx['id']} | {', '.join('`' + c + '`' for c in fx['codes'])} | {pages} | `{fx['file']}:{fx['line']}` | {fx['how']} |")
    if plan["placeholders"]:
        L += ["", "Placeholders to fill in `fills.json` (null drops the fix):", "", "| Placeholder | Fix | Kind | Bounds | Instruction |", "|---|---|---|---|---|"]
        for ph in plan["placeholders"]:
            L.append(f"| {ph['id']} | {ph['fix']} | {ph['kind']} | {ph['min']} to {ph['max']} | {ph['instruction']} |")
    if plan["manual"]:
        L += ["", "### To locate by hand", "", "| Defect | Page (crawl line) | Why | Candidates |", "|---|---|---|---|"]
        for m in plan["manual"]:
            c = ", ".join(f"`{x}`" for x in m["candidates"]) or "none"
            L.append(f"| `{m['code']}` {m['detail']} | {m['url']} ({m['ref']}) | {m['reason']} | {c} |")
    L.append("")
    return "\n".join(L)


def fills_template(plan: Dict[str, Any]) -> Dict[str, Any]:
    fx = {f["id"]: f for f in plan["fixes"]}
    return {
        "_comment": "Write each value (the text that replaces the placeholder, inside its quotes for text kinds, the whole expression for kind expression). null drops the fix. Never invent a fact: an author, a date or a claim comes from the project. Then run repo_fix.py fill and repo_fix.py check.",
        "values": {ph["id"]: "" for ph in plan["placeholders"]},
        "placeholders": [{"id": ph["id"], "kind": ph["kind"], "instruction": ph["instruction"], "min": ph["min"], "max": ph["max"],
                          "file": fx[ph["fix"]]["file"], "line": fx[ph["fix"]]["line"], "pages": fx[ph["fix"]]["urls"][:5],
                          "current": fx[ph["fix"]]["old"].strip()[:200]} for ph in plan["placeholders"]],
    }


# --------------------------------------------------------------------------
# commands

def cmd_plan(a) -> int:
    rules = load_assets_json("crawl-rules.json")
    W = eeat.load_weights(a.config)
    if a.config:
        rules = deep_merge(rules, load_json(a.config).get("crawl_rules", {}))
    repo = Repo(a.repo)
    pl = Planner(repo, a.crawl, rules, W)
    pl.run()
    fixes = sorted(pl.fixes.values(), key=lambda f: (f["file"], f["line"], f["op"]))
    rewritten = set()
    kept = []
    for fx in fixes:
        k = (fx["file"], fx["line"])
        if fx["op"] == "replace" and k in rewritten:
            for did in fx["defects"]:
                d = next(x for x in pl.defects if x["id"] == did)
                d.pop("fix_line", None)
                pl.hand(d, f"another fix already rewrites {fx['file']}:{fx['line']}", [f"{fx['file']}:{fx['line']}"])
            continue
        if fx["op"] == "replace":
            rewritten.add(k)
        kept.append(fx)
    for n, fx in enumerate(kept, 1):
        fx["id"] = f"f{n:02d}"
    placeholders = number_placeholders(kept)
    os.makedirs(a.out_dir, exist_ok=True)
    patches = write_patches(a.out_dir, repo, kept, {})
    plan = {
        "schema_version": "1.0", "generated_by": "repo_fix.py", "crawl": os.path.basename(a.crawl), "repo": a.repo,
        "rules": {k: rules[k] for k in ("title_max_chars", "description_min_chars", "description_max_chars")},
        "defects": pl.defects, "fixes": kept, "placeholders": placeholders, "manual": pl.manual, "patches": patches,
        "ok_paths": pl.ok_paths(), "fill": None,
    }
    write_json(os.path.join(a.out_dir, "repo-fix.json"), plan)
    write_text(os.path.join(a.out_dir, "repo-fix.md"), render_md(plan))
    write_json(os.path.join(a.out_dir, "fills.json"), fills_template(plan))
    bad = [p for p in patches if not p["git_apply_check"]["ok"]]
    print(f"repo_fix: {len(pl.defects)} defect(s), {len(kept)} fix(es) in {len(patches)} patch(es), {len(pl.manual)} to locate by hand, "
          f"{len(placeholders)} placeholder(s) -> {a.out_dir}")
    for p in bad:
        print(f"error: {p['patch']} does not apply: {p['git_apply_check']['message']}", file=sys.stderr)
    return 1 if bad else 0


def load_plan(out_dir: str) -> Dict[str, Any]:
    return load_json(os.path.join(out_dir, "repo-fix.json"))


def cmd_fill(a) -> int:
    plan = load_plan(a.out_dir)
    values = load_json(a.fills).get("values", {})
    dropped = sorted({ph["fix"] for ph in plan["placeholders"] if ph["id"] in values and values[ph["id"]] is None})
    fixes = [fx for fx in plan["fixes"] if fx["id"] not in dropped]
    repo = Repo(a.repo or plan["repo"])
    patches = write_patches(a.out_dir, repo, fixes, {k: v for k, v in values.items() if isinstance(v, str)})
    unfilled = [ph["id"] for ph in plan["placeholders"] if ph["fix"] not in dropped and not values.get(ph["id"])]
    plan["patches"] = patches
    plan["fill"] = {"dropped_fixes": dropped, "unfilled": unfilled,
                    "values": {ph["id"]: values.get(ph["id"]) for ph in plan["placeholders"] if ph["fix"] not in dropped},
                    "filled": [ph["id"] for ph in plan["placeholders"] if ph["fix"] not in dropped and values.get(ph["id"])]}
    write_json(os.path.join(a.out_dir, "repo-fix.json"), plan)
    bad = [p for p in patches if not p["git_apply_check"]["ok"]]
    print(f"repo_fix fill: {len(plan['fill']['filled'])} value(s) written, {len(dropped)} fix(es) dropped, {len(unfilled)} placeholder(s) left, "
          f"{len(patches)} patch(es)")
    for p in bad:
        print(f"error: {p['patch']} does not apply: {p['git_apply_check']['message']}", file=sys.stderr)
    return 1 if bad else 0


def cmd_check(a) -> int:
    plan = load_plan(a.out_dir)
    dropped = set((plan.get("fill") or {}).get("dropped_fixes", []))
    filled = (plan.get("fill") or {}).get("values", {})
    findings = []
    pdir = os.path.join(a.out_dir, "patches")
    texts = {}
    for p in plan["patches"]:
        path = os.path.join(a.out_dir, p["patch"])
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                texts[p["file"]] = fh.read()
        except OSError:
            findings.append({"code": "patch-missing", "where": p["patch"], "message": "patch listed in repo-fix.json is missing"})
    fx_file = {fx["id"]: fx["file"] for fx in plan["fixes"]}
    for ph in plan["placeholders"]:
        if ph["fix"] in dropped:
            continue
        text = texts.get(fx_file[ph["fix"]], "")
        added = [l[1:].rstrip("\r\n") for l in text.splitlines(keepends=True) if l.startswith("+") and not l.startswith("+++")]
        vals = [l[len(ph["prefix"]):len(l) - len(ph["suffix"]) if ph["suffix"] else None] for l in added
                if l.startswith(ph["prefix"]) and l.endswith(ph["suffix"]) and len(l) >= len(ph["prefix"]) + len(ph["suffix"])]
        where = f"{ph['id']} ({fx_file[ph['fix']]})"
        if not vals and not filled.get(ph["id"]):
            findings.append({"code": "placeholder-line-missing", "where": where, "message": "the added line of this placeholder is not in the patch"})
            continue
        v = vals[0] if vals else filled[ph["id"]]
        for prob in value_problems(ph, v, plan["ok_paths"]):
            findings.append({"code": "placeholder-left" if prob == "placeholder left" else "value-out-of-bounds", "where": where,
                             "message": f"{ph['kind']}: {prob}"})
    for rel, text in sorted(texts.items()):
        if TAG in text and not any(f["code"] == "placeholder-left" and rel in f["where"] for f in findings):
            findings.append({"code": "placeholder-left", "where": rel, "message": f"{TAG} still in the patch"})
    repo_root = plan["repo"] if not a.repo else a.repo
    files = {p["file"]: os.path.join(a.out_dir, p["patch"]) for p in plan["patches"] if p["file"] in texts}
    if files:
        for rel, res in sorted(git_check(os.path.abspath(repo_root), files).items()):
            if not res["ok"]:
                findings.append({"code": "patch-does-not-apply", "where": rel, "message": res["message"]})
    if a.json:
        print(json.dumps({"block": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"BLOCK {f['code']} {f['where']}  {f['message']}")
        print(f"repo_fix check: {len(findings)} BLOCK in {len(texts)} patch(es) ({pdir})")
    return 1 if findings else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Repo mode: served defects traced to the source line, one checked patch per file, never applied.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="locate the defects and write the patches with placeholders")
    p.add_argument("--crawl", required=True, help="crawl.jsonl of the run")
    p.add_argument("--repo", required=True, help="source repository of the site (read only)")
    p.add_argument("--out-dir", required=True, help="folder for patches/, repo-fix.json, repo-fix.md, fills.json")
    p.add_argument("--config", help="project config.json (crawl_rules and eeat overrides)")
    p = sub.add_parser("fill", help="rebuild the patches with the values of fills.json")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--fills", required=True)
    p.add_argument("--repo", help="repository path when it moved since plan")
    p = sub.add_parser("check", help="no placeholder left, values in bounds, every patch applies")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--repo", help="repository path when it moved since plan")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"plan": cmd_plan, "fill": cmd_fill, "check": cmd_check}[a.cmd](a)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
