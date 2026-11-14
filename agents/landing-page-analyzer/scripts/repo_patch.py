#!/usr/bin/env python3
"""repo_patch.py: turn the fixes that passed the before/after of fixes.py into unified
patches against the source code of the site. The repo is only read, never written.

  python3 scripts/repo_patch.py --repo <site source> --fixes <run>/fixes [--out <run>]
                                [--css-dir <dir in repo>] [--exclude NAME_OR_PATH ...]

For every fix whose fixes/<id>/fix.json says "pass", each change is located in the
source:

  text        the text the element showed before the fix (recorded by fixes.py), searched
              in .html .htm .md .mdx .astro .jsx .tsx .vue .svelte .njk .liquid with any
              whitespace, entities and inline tags between words, then as a string value
              of the content and i18n files (.json, .yml, .yaml)
  attributes  the element's opening tag, found by id, else by all its classes, else by
              href (JSX names such as autoComplete and htmlFor in .jsx and .tsx)
  insert      the same opening tag, then the markup goes before, after or inside it
  css         a rule with exactly the same selector list and media query in .css, .scss,
              .less or a <style> block (SCSS nesting resolved); the declarations are edited
              in place, without the !important fixes.py injects
  css_raw     always goes to lpa-fixes.css

A change found in exactly one place is patched. A change found in several places, or
nowhere, is never guessed: the fix is listed "manual" with the candidates and the reason,
and gets no patch. A CSS rule with no exact rule in the repo goes to lpa-fixes.css (next
to the only stylesheet, else at the repo root, or --css-dir): the fix is then
"ready-needs-import" and the file says how to import it.

Writes <out>/repo-patches/ (default <out> is the folder holding fixes/):
  <id>.patch          one per ready fix, against the untouched repo
  all.patch           every ready fix at once (take it, or single patches, not both)
  repo-patches.json   per fix: status (ready, ready-needs-import, manual, skipped),
                      file:line of each change in the current source, candidates, reason,
                      and the result of git apply --check
  repo-patches.md     one section per fix for the report

Every patch is checked with git apply --check on a temporary copy of the files it
touches. Exit 0 when every written patch passes, 1 when one does not, 2 fatal (bad
input, or --out inside --repo).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import html as _html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MARKUP = {".html", ".htm", ".md", ".mdx", ".astro", ".jsx", ".tsx", ".vue", ".svelte", ".njk", ".liquid"}
CONTENT = {".json", ".yml", ".yaml"}
STYLE = {".css", ".scss", ".less"}
STYLE_HOSTS = {".html", ".htm", ".astro", ".vue", ".svelte"}
JSX = {".jsx", ".tsx"}
BRACES = {".jsx", ".tsx", ".astro", ".svelte", ".vue"}
EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", ".output", "out", "_site", ".astro",
                ".svelte-kit", ".vercel", ".netlify", "coverage", "vendor", ".cache", ".turbo", ".parcel-cache"}
SKIP_FILES = {"package.json", "package-lock.json", "composer.json", "composer.lock", "pnpm-lock.yaml", "yarn.lock"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
JSX_ATTRS = {"class": "className", "for": "htmlFor", "autocomplete": "autoComplete", "tabindex": "tabIndex",
             "readonly": "readOnly", "maxlength": "maxLength", "minlength": "minLength", "inputmode": "inputMode",
             "enterkeyhint": "enterKeyHint", "autofocus": "autoFocus", "spellcheck": "spellCheck"}
READY = ("ready", "ready-needs-import")
CSS_FILE = "lpa-fixes.css"
CSS_HEADER = """/* lpa-fixes.css, written by landing-page-analyzer (scripts/repo_patch.py).
   CSS fixes validated by the before/after render that have no exact rule in this repo.
   TO IMPORT: this file does nothing until the site loads it after its main stylesheet:
   a second import line right after the one that loads the main stylesheet (layout,
   entry file), or a <link rel="stylesheet"> placed after it. An @import inside the main
   stylesheet loads it first and loses the cascade. Then move each rule where it belongs. */
"""

ENT = {"&": r"(?:&|&amp;|&#38;)", "<": r"(?:<|&lt;)", ">": r"(?:>|&gt;)", '"': r'(?:"|&quot;|&#34;)',
       "'": r"(?:'|&#39;|&apos;|&#x27;|&rsquo;)", "’": r"(?:’|&rsquo;|')", " ": r"(?: |&nbsp;|&#160;)"}
SEP = r"(?:\s|&nbsp;|&#160;|<[^<>]*>|\{\s*[\"'`]\s*[\"'`]\s*\})+"
TAG = re.compile(r"<(/?)([a-zA-Z][\w.:-]*)\b[^<>]*?(/?)>")
OPEN = re.compile(r"<([a-zA-Z][\w.:-]*)((?:\s+(?:[^<>\"'{}]|\"[^\"]*\"|'[^']*'|\{[^{}]*\})*?)?)\s*(/?)>")
ATTR = re.compile(r"([^\s\"'<>/=]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|\{[^{}]*\}|[^\s\"'<>=`]+))?")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(s or "")).strip()


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


class Tree:
    """The repo files the search reads, with edits kept in memory and marks that follow them."""

    def __init__(self, root: Optional[Path] = None, files: Optional[Dict[str, str]] = None, exclude=()):
        self.root = root
        self.orig: Dict[str, Optional[str]] = {}
        if files is not None:
            self.orig = dict(files)
        else:
            names = EXCLUDE_DIRS | {e for e in exclude if "/" not in e.strip("/")}
            paths = {e.strip("/") for e in exclude}

            def out(rel: str) -> bool:
                return any(rel == x or rel.startswith(x + "/") for x in paths)
            for dirpath, dirnames, filenames in os.walk(root):
                base = Path(dirpath).relative_to(root).as_posix()
                dirnames[:] = sorted(d for d in dirnames if d not in names and not out(f"{base}/{d}".lstrip("./")))
                for name in sorted(filenames):
                    p = Path(dirpath) / name
                    if p.suffix.lower() not in MARKUP | CONTENT | STYLE or name in SKIP_FILES or ".min." in name:
                        continue
                    if out(p.relative_to(root).as_posix()):
                        continue
                    if p.is_symlink() or p.stat().st_size > 1_500_000:
                        continue
                    try:
                        self.orig[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
        self.cur: Dict[str, str] = {k: v for k, v in self.orig.items() if v is not None}
        self.marks: List[List[Any]] = []

    def fork(self) -> "Tree":
        t = Tree.__new__(Tree)
        t.root, t.orig, t.cur, t.marks = self.root, self.orig, dict(self.cur), []
        return t

    def paths(self, exts) -> List[str]:
        return sorted(p for p in self.cur if Path(p).suffix.lower() in exts)

    def edit(self, rel: str, start: int, end: int, new: str) -> None:
        old = self.cur.get(rel, "")
        self.cur[rel] = old[:start] + new + old[end:]
        delta = len(new) - (end - start)
        for m in self.marks:
            if m[0] == rel and m[1] >= end:
                m[1] += delta
            elif m[0] == rel and m[1] > start:
                m[1] = start

    def mark(self, rel: str, offset: int) -> List[Any]:
        m = [rel, offset]
        self.marks.append(m)
        return m

    def changed(self) -> List[str]:
        return sorted(p for p, v in self.cur.items() if self.orig.get(p) != v)

    def old_line(self, m: List[Any]) -> int:
        rel, off = m
        new = self.cur[rel]
        n = line_of(new, off)
        old = self.orig.get(rel)
        if old is None:
            return n
        a, b = old.splitlines(), new.splitlines()
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if j1 <= n - 1 < j2:
                return min(i1 + min(n - 1 - j1, max(0, i2 - i1 - 1)) + 1, max(1, len(a)))
        return min(n, max(1, len(a)))


def unified(rel: str, old: Optional[str], new: str) -> str:
    a = old.splitlines(keepends=True) if old is not None else []
    b = new.splitlines(keepends=True)
    out = [f"diff --git a/{rel} b/{rel}\n"]
    if old is None:
        out.append("new file mode 100644\n")
    for i, line in enumerate(difflib.unified_diff(a, b, f"a/{rel}" if old is not None else "/dev/null", f"b/{rel}", n=3)):
        if i < 2:
            out.append(line if line.endswith("\n") else line + "\n")
        elif line.endswith("\n"):
            out.append(line)
        else:
            out.append(line + "\n\\ No newline at end of file\n")
    return "".join(out)


def patch_paths(patch_text: str) -> List[Tuple[str, bool]]:
    files = []
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)\n(new file mode)?", patch_text, re.M):
        files.append((m.group(2), bool(m.group(3))))
    return files


def apply_check(repo: Path, patch: Path) -> str:
    """'' when git apply --check accepts the patch on a temporary copy of the files it touches."""
    try:
        text = patch.read_text(encoding="utf-8")
    except OSError as e:
        return f"cannot read {patch}: {e}"
    files = patch_paths(text)
    if not files:
        return "no file in the patch"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    with tempfile.TemporaryDirectory(prefix="lpa-apply-") as d:
        for rel, _new in files:
            if rel.startswith("/") or ".." in Path(rel).parts:
                return f"unsafe path {rel}"
            src = repo / rel
            if src.exists():
                (Path(d) / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, Path(d) / rel)
        try:
            subprocess.run(["git", "init", "-q"], cwd=d, env=env, capture_output=True, check=True)
            r = subprocess.run(["git", "apply", "--check", str(patch.resolve())], cwd=d, env=env, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as e:
            return f"git not available: {e}"
        return "" if r.returncode == 0 else (r.stderr.strip() or f"git apply exit {r.returncode}").splitlines()[0][:300]


def text_regex(t: str):
    words = t.split()
    if not words:
        return None
    w = ["".join(ENT.get(ch, re.escape(ch)) for ch in word) for word in words]
    return re.compile(r"(?<![\w])" + SEP.join(w) + r"(?![\w])")


def unbalanced(span: str):
    stack, stray = [], []
    for m in TAG.finditer(span):
        close, name, selfc = m.groups()
        if selfc or name.lower() in VOID:
            continue
        if not close:
            stack.append(name)
        elif stack and stack[-1] == name:
            stack.pop()
        else:
            stray.append(name)
    return stack, stray


def widen(content: str, start: int, end: int):
    for _ in range(8):
        opens, stray = unbalanced(content[start:end])
        if not opens and not stray:
            return start, end
        moved = False
        if opens:
            m = re.match(r"\s*</%s\s*>" % re.escape(opens[-1]), content[end:])
            if m:
                end += m.end()
                moved = True
        if stray:
            m = re.search(r"<%s\b[^<>]*>\s*$" % re.escape(stray[0]), content[:start])
            if m:
                start = m.start()
                moved = True
        if not moved:
            return None
    return None


def escape_for(text: str, ext: str, quote: str = "") -> str:
    s = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if ext in BRACES:
        s = s.replace("{", "&#123;").replace("}", "&#125;")
    if quote == '"':
        s = s.replace('"', "&quot;")
    elif quote == "'":
        s = s.replace("'", "&#39;")
    return s


def enclosing_open(content: str, start: int):
    last = None
    for m in OPEN.finditer(content, max(0, start - 3000), start):
        last = m
    return last


def tag_fits(m, target: Dict[str, Any]) -> bool:
    if not m or m.group(1).lower() != (target.get("tag") or "").lower():
        return False
    attrs = parse_attrs(m.group(2) or "")
    if target.get("id"):
        return static(attrs.get("id")) == target["id"]
    cls = set((static(attrs.get("class")) or static(attrs.get("className")) or "").split())
    return set(target.get("classes") or []) <= cls


MD_LEAD = re.compile(r"(?:^|\n)[ \t]*(?:#{1,6}|[-*+]|\d+\.|>)?[ \t]*[*_\[]*$")
MD_TAIL = re.compile(r"^[*_\]]*[ \t]*(?:\n|$)")


def whole_text(s: str, start: int, end: int, md: bool) -> bool:
    """The match is the whole text of a node, not a phrase inside a longer one."""
    before, after = s[:start].rstrip(), s[end:].lstrip()
    ok_b = not before or before[-1] in ">\"'`}:"
    ok_a = not after or after[0] in "<\"'`{"
    if md and not ok_b and MD_LEAD.search(s[max(0, start - 200):start]):
        prev = s[:start].rsplit("\n", 2)
        ok_b = bool(re.fullmatch(r"[ \t]*(?:#{1,6}|[-*+]|\d+\.|>)[ \t]+[*_\[]*", prev[-1])) or \
            (prev[-1].strip(" \t*_[") == "" and (len(prev) < 2 or prev[-2].strip() == ""))
    if md and not ok_a and MD_TAIL.match(s[end:]):
        nxt = s[end:].lstrip(" \t*_]").split("\n", 2)
        ok_a = len(nxt) < 2 or nxt[1].strip() == "" or bool(re.match(r"[ \t]*(?:#{1,6}|[-*+]|\d+\.|>|<)", nxt[1]))
    return ok_b and ok_a


def text_candidates(tree: Tree, t: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    rx = text_regex(t)
    if rx is None:
        return out
    for rel in tree.paths(MARKUP):
        s = tree.cur[rel]
        md = Path(rel).suffix.lower() in (".md", ".mdx")
        for m in rx.finditer(s):
            if not whole_text(s, m.start(), m.end(), md):
                continue
            span = widen(s, m.start(), m.end())
            c = {"kind": "markup", "path": rel, "start": m.start(), "end": m.end(), "line": line_of(s, m.start())}
            if span is None:
                c["problem"] = "the text is split by inline markup that does not close inside it"
            else:
                c["start"], c["end"] = span
            out.append(c)
    for rel in tree.paths({".json"}):
        s = tree.cur[rel]
        try:
            data = json.loads(s)
        except ValueError:
            continue
        values = set()

        def walk(v):
            if isinstance(v, str) and norm(v) == t:
                values.add(v)
            elif isinstance(v, dict):
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)
        walk(data)
        for v in sorted(values):
            for ascii_only in (False, True):
                enc = json.dumps(v, ensure_ascii=ascii_only)
                if ascii_only and enc == json.dumps(v, ensure_ascii=False):
                    continue
                for m in re.finditer(re.escape(enc), s):
                    if KEY_AFTER.match(s, m.end()):
                        continue
                    out.append({"kind": "json", "path": rel, "start": m.start(), "end": m.end(), "line": line_of(s, m.start()), "ascii": ascii_only})
    for rel in tree.paths({".yml", ".yaml"}):
        s = tree.cur[rel]
        pos = 0
        for raw in s.splitlines(keepends=True):
            line = raw.rstrip("\r\n")
            y = yaml_value(line)
            if y and norm(y[1]) == t:
                out.append({"kind": "yaml", "path": rel, "start": pos, "end": pos + len(line), "line": line_of(s, pos), "yaml": y})
            pos += len(raw)
    return out


KEY_AFTER = re.compile(r"\s*:")
YKEY = re.compile(r"^(\s*(?:-\s+)?(?:[\w.\-]+|\"[^\"]*\"|'[^']*')\s*:[ \t]+|\s*-[ \t]+)(.*?)\s*$")


def yaml_value(line: str):
    m = YKEY.match(line)
    if not m or line.lstrip().startswith("#"):
        return None
    pre, val = m.group(1), m.group(2)
    comment = ""
    if val[:1] == '"':
        mm = re.match(r'^("(?:[^"\\]|\\.)*")(\s+#.*)?$', val)
        if not mm:
            return None
        try:
            return pre, json.loads(mm.group(1)), '"', mm.group(2) or ""
        except ValueError:
            return None
    if val[:1] == "'":
        mm = re.match(r"^'((?:[^']|'')*)'(\s+#.*)?$", val)
        return (pre, mm.group(1).replace("''", "'"), "'", mm.group(2) or "") if mm else None
    if not val or val[:1] in "|>&*!{[":
        return None
    if " #" in val:
        val, comment = val.split(" #", 1)
        comment = " #" + comment
    return pre, val.rstrip(), "", comment


def yaml_line(y, new: str) -> str:
    pre, _old, quote, comment = y
    if quote == "'":
        v = "'" + new.replace("'", "''") + "'"
    elif quote == '"' or re.search(r"[:#]\s|^[-?:,\[\]{}#&*!|>'\"%@`]|\s$|^\s|:$", new):
        v = json.dumps(new, ensure_ascii=False)
    else:
        v = new
    return pre + v + comment


def replace_text(tree: Tree, c: Dict[str, Any], new: str) -> None:
    rel = c["path"]
    s = tree.cur[rel]
    ext = Path(rel).suffix.lower()
    if c["kind"] == "markup":
        before, after = s[c["start"] - 1:c["start"]], s[c["end"]:c["end"] + 1]
        quote = before if before in "\"'" and before == after and before else ""
        rep = escape_for(new, ext, quote)
    elif c["kind"] == "json":
        rep = json.dumps(new, ensure_ascii=c.get("ascii", False))
    else:
        rep = yaml_line(c["yaml"], new)
    tree.edit(rel, c["start"], c["end"], rep)


def parse_attrs(s: str) -> Dict[str, str]:
    out = {}
    for m in ATTR.finditer(s or ""):
        out[m.group(1)] = m.group(2) if m.group(2) is not None else ""
    return out


def static(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    if v[:1] in "\"'" and v[-1:] == v[:1]:
        return _html.unescape(v[1:-1])
    if v[:1] == "{":
        inner = v[1:-1].strip()
        mm = re.fullmatch(r"([\"'`])(.*)\1", inner)
        return mm.group(2) if mm else None
    return v


def element_candidates(tree: Tree, target: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    tag = (target.get("tag") or "").lower()
    if not (target.get("id") or target.get("classes") or target.get("href")):
        return [], f"the <{tag}> element has no id, class or href to find it by"
    out = []
    for rel in tree.paths(MARKUP):
        s = tree.cur[rel]
        for m in OPEN.finditer(s):
            if m.group(1).lower() != tag:
                continue
            attrs = parse_attrs(m.group(2) or "")
            if target.get("id"):
                ok = static(attrs.get("id")) == target["id"]
            elif target.get("classes"):
                cls = set((static(attrs.get("class")) or static(attrs.get("className")) or "").split())
                ok = set(target["classes"]) <= cls
            else:
                ok = static(attrs.get("href")) == target["href"]
            if ok:
                out.append({"kind": "element", "path": rel, "start": m.start(), "end": m.end(), "line": line_of(s, m.start())})
    return out, ""


def attr_name(name: str, ext: str) -> str:
    return JSX_ATTRS.get(name.lower(), name) if ext in JSX else name


def edit_attributes(tree: Tree, c: Dict[str, Any], op: Dict[str, Any]) -> str:
    rel = c["path"]
    ext = Path(rel).suffix.lower()
    tag = tree.cur[rel][c["start"]:c["end"]]
    m = OPEN.match(tag)
    body_start = m.start(2)
    for k, v in (op.get("set") or {}).items():
        name = attr_name(k, ext)
        found = None
        for am in ATTR.finditer(tag, body_start, m.end(2)):
            if am.group(1) in (k, name):
                found = am
        value = str(v)
        if found and found.group(2) and found.group(2)[:1] == "{" and static(found.group(2)) is None:
            return f"{name} is bound to an expression in {rel}:{c['line']}"
        new_attr = name if value == "" and k.lower() in ("required", "disabled", "readonly", "autofocus", "multiple", "hidden") \
            else f'{name}="{_html.escape(value, quote=True)}"'
        if found:
            tag = tag[:found.start()] + new_attr + tag[found.end():]
        else:
            selfclose = tag.endswith("/>")
            close = len(tag) - (2 if selfclose else 1)
            tag = tag[:close].rstrip() + " " + new_attr + (" " if selfclose else "") + tag[close:]
        m = OPEN.match(tag)
    for k in op.get("remove") or []:
        name = attr_name(k, ext)
        for am in reversed(list(ATTR.finditer(tag, m.start(2), m.end(2)))):
            if am.group(1) in (k, name):
                s0 = am.start()
                while s0 > 0 and tag[s0 - 1].isspace():
                    s0 -= 1
                tag = tag[:s0] + tag[am.end():]
        m = OPEN.match(tag)
    tree.edit(rel, c["start"], c["end"], tag)
    return ""


def jsxify(markup: str) -> str:
    def fix_tag(m):
        return re.sub(r"(\s)([\w-]+)(\s*=)", lambda a: a.group(1) + JSX_ATTRS.get(a.group(2).lower(), a.group(2)) + a.group(3), m.group(0))
    return re.sub(r"<[a-zA-Z][^<>]*>", fix_tag, markup)


def closing_of(s: str, name: str, from_: int) -> Optional[Tuple[int, int]]:
    depth = 1
    rx = re.compile(r"<(/?)%s\b[^<>]*?(/?)>" % re.escape(name), re.I)
    for m in rx.finditer(s, from_):
        if m.group(2):
            continue
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.start(), m.end()
    return None


def insert_markup(tree: Tree, c: Dict[str, Any], op: Dict[str, Any]) -> str:
    rel = c["path"]
    s = tree.cur[rel]
    ext = Path(rel).suffix.lower()
    markup = jsxify(op["html"]) if ext in JSX else op["html"]
    m = OPEN.match(s, c["start"])
    name = m.group(1)
    void = m.group(3) == "/" or name.lower() in VOID
    pos = op.get("position") or "afterend"
    line_start = s.rfind("\n", 0, c["start"]) + 1
    indent = s[line_start:c["start"]]
    own_line = indent.strip() == ""
    if pos == "beforebegin":
        tree.edit(rel, c["start"], c["start"], markup + ("\n" + indent if own_line else ""))
        return ""
    if pos == "afterbegin":
        if void:
            return f"cannot insert inside the void element <{name}> in {rel}:{c['line']}"
        tree.edit(rel, c["end"], c["end"], markup)
        return ""
    if void:
        at = c["end"]
    else:
        close = closing_of(s, name, c["end"])
        if not close:
            return f"no closing </{name}> found after {rel}:{c['line']}"
        at = close[0] if pos == "beforeend" else close[1]
    if pos == "afterend" and own_line and s[at:at + 1] in ("\n", "\r"):
        tree.edit(rel, at, at, "\n" + indent + markup)
    else:
        tree.edit(rel, at, at, markup)
    return ""


def blank_comments(s: str, ext: str) -> str:
    out = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), s, flags=re.S)
    if ext in (".scss", ".less"):
        out = re.sub(r"(^|[\s;{}])//[^\n]*", lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), out)
    return re.sub(r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'", lambda m: m.group(0)[0] + "_" * (len(m.group(0)) - 2) + m.group(0)[0], out)


def norm_sel(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    return re.sub(r"\s*([>+~])\s*", r"\1", s)


def split_top(s: str, sep: str = ",") -> List[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        depth += ch in "([" and 1 or 0
        depth -= ch in ")]" and 1 or 0
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p for p in parts if p.strip()]


def norm_media(m: str) -> str:
    m = re.sub(r"\s+", " ", m.strip().lower())
    return re.sub(r"\s*([:(),])\s*", r"\1", m)


def match_brace(s: str, i: int) -> int:
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return len(s) - 1


def css_blocks(clean: str, base: int = 0) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []

    def rec(i: int, end: int, parents: List[str], ctx: Tuple[str, ...]):
        pre = i
        while i < end:
            ch = clean[i]
            if ch == "{":
                prelude = clean[pre:i].strip()
                j = match_brace(clean, i)
                if prelude.startswith("@media"):
                    rec(i + 1, j, parents, ctx + ("@media " + norm_media(prelude[6:]),))
                elif prelude.startswith(("@supports", "@layer", "@container")):
                    rec(i + 1, j, parents, ctx + (norm_media(prelude),))
                elif not prelude.startswith("@"):
                    sels = []
                    for sel in split_top(prelude):
                        sel = sel.strip()
                        if parents:
                            sels += [sel.replace("&", p) if "&" in sel else f"{p} {sel}" for p in parents]
                        else:
                            sels.append(sel)
                    sels = [norm_sel(x) for x in sels]
                    blocks.append({"sels": frozenset(sels), "ctx": ctx, "open": base + i, "close": base + j, "list": sels})
                    rec(i + 1, j, sels, ctx)
                i = j + 1
                pre = i
            elif ch in ";}":
                i += 1
                pre = i
            else:
                i += 1
    rec(0, len(clean), [], ())
    return blocks


def style_regions(rel: str, s: str) -> List[Tuple[int, str, str]]:
    ext = Path(rel).suffix.lower()
    if ext in STYLE:
        return [(0, s, ext)]
    out = []
    if ext in STYLE_HOSTS:
        for m in re.finditer(r"<style\b([^>]*)>(.*?)</style>", s, re.S | re.I):
            lang = re.search(r"lang=[\"']?(scss|less)", m.group(1))
            out.append((m.start(2), m.group(2), "." + lang.group(1) if lang else ".css"))
    return out


def all_blocks(tree: Tree, rel: str) -> List[Dict[str, Any]]:
    s = tree.cur[rel]
    out = []
    for base, text, ext in style_regions(rel, s):
        for b in css_blocks(blank_comments(text, ext), base):
            b["path"] = rel
            out.append(b)
    return out


def rule_candidates(tree: Tree, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    want = frozenset(norm_sel(x) for x in split_top(rule["selector"]))
    ctx = ("@media " + norm_media(rule["media"]),) if rule.get("media") else ()
    out = []
    for rel in tree.paths(STYLE | STYLE_HOSTS):
        for b in all_blocks(tree, rel):
            if b["sels"] == want and b["ctx"] == ctx:
                b["line"] = line_of(tree.cur[rel], b["open"])
                out.append(b)
    return out


def find_decl(clean: str, open_: int, close: int, prop: str):
    i, seg = open_ + 1, open_ + 1
    hit = None
    while i < close:
        ch = clean[i]
        if ch == "{":
            i = match_brace(clean, i) + 1
            seg = i
            continue
        if ch == ";" or i == close - 1:
            end = i if ch == ";" else i + 1
            m = re.match(r"\s*([-\w]+)\s*:\s*", clean[seg:end])
            if m and m.group(1).lower() == prop.lower():
                vs = seg + m.end()
                ve = end
                while ve > vs and clean[ve - 1].isspace():
                    ve -= 1
                hit = (seg + m.start(1), vs, ve)
            seg = i + 1
        i += 1
    return hit


def edit_rule(tree: Tree, block: Dict[str, Any], declarations: Dict[str, Any]) -> List[Any]:
    rel = block["path"]
    first = None
    for prop, value in declarations.items():
        value = str(value).replace("!important", "").strip()
        s = tree.cur[rel]
        b = [x for x in all_blocks(tree, rel) if x["sels"] == block["sels"] and x["ctx"] == block["ctx"]][-1]
        clean = s[:b["open"]] + blank_comments(s[b["open"]:b["close"] + 1], Path(rel).suffix.lower()) + s[b["close"] + 1:]
        hit = find_decl(clean, b["open"], b["close"], prop)
        if hit:
            tree.edit(rel, hit[1], hit[2], value)
            mk = tree.mark(rel, hit[0])
        else:
            body = s[b["open"] + 1:b["close"]]
            k = b["close"]
            while k > b["open"] + 1 and s[k - 1].isspace():
                k -= 1
            semi = "" if s[k - 1] in ";{}" else ";"
            if "\n" in body:
                lines = [ln for ln in body.splitlines() if ln.strip()]
                if lines:
                    indent = re.match(r"\s*", lines[-1]).group(0)
                else:
                    ls = s.rfind("\n", 0, b["open"]) + 1
                    indent = re.match(r"\s*", s[ls:]).group(0) + "  "
                text = f"{semi}\n{indent}{prop}: {value};"
                tree.edit(rel, k, k, text)
                mk = tree.mark(rel, k + len(semi) + 1)
            else:
                text = f"{semi} {prop}: {value};" if s[k - 1] != "{" else f" {prop}: {value};"
                tree.edit(rel, k, k, text)
                mk = tree.mark(rel, k)
        first = first or mk
    return first


def css_text(rule: Dict[str, Any]) -> str:
    decl = "".join(f"  {k}: {str(v).replace('!important', '').strip()};\n" for k, v in rule["declarations"].items())
    block = f"{rule['selector']} {{\n{decl}}}\n"
    if rule.get("media"):
        block = f"@media {rule['media']} {{\n" + "".join("  " + ln + "\n" for ln in block.splitlines()) + "}\n"
    return block


def pick_css_dir(tree: Tree, css_dir: Optional[str]) -> str:
    if css_dir is not None:
        return css_dir.strip("/")
    sheets = [p for p in tree.paths({".css", ".scss", ".less"}) if Path(p).name != CSS_FILE]
    return str(Path(sheets[0]).parent.as_posix()) if len(sheets) == 1 and Path(sheets[0]).parent.as_posix() != "." else ""


def import_hint(tree: Tree, css_rel: str) -> str:
    sheets = [p for p in tree.paths(STYLE) if Path(p).name != CSS_FILE and Path(p).parent.as_posix() == (Path(css_rel).parent.as_posix())]
    hits = []
    for sheet in sheets:
        rx = re.compile(r"(?:import\s+|@import\s+|href=)[\"'][^\"']*\b%s[\"']" % re.escape(Path(sheet).name))
        for rel in tree.paths(MARKUP | {".js", ".ts", ".mjs"} | STYLE):
            m = rx.search(tree.cur.get(rel, ""))
            if m and rel != sheet:
                hits.append(f"{sheet} is loaded in {rel}:{line_of(tree.cur[rel], m.start())}")
    return hits[0] if len(hits) == 1 else ""


def describe(c: Dict[str, Any]) -> str:
    return f"{c['path']}:{c['line']}"


def plan_fix(tree: Tree, fix: Dict[str, Any], css_rel: str) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = []
    for op in fix.get("ops") or []:
        kind, sel = op["kind"], op["selector"]
        part: Dict[str, Any] = {"kind": kind, "selector": sel}
        parts.append(part)
        targets = op.get("targets") or []
        matched = op.get("matched", len(targets))
        if not targets:
            part.update(status="not-found", reason="fix.json records no element for this change (re-run fixes.py)")
            continue
        if matched and matched > len(targets):
            part.update(status="unsupported", reason=f"the selector matched {matched} elements, only {len(targets)} recorded")
            continue
        found: Dict[Tuple[str, int], Dict[str, Any]] = {}
        why, status = "", "not-found"
        for tg in targets:
            cands = []
            if kind == "text":
                t = norm(tg.get("text", ""))
                if not t:
                    why = f"the <{tg.get('tag')}> element had no text before the fix"
                    break
                cands = text_candidates(tree, t)
                if len(cands) > 1 and all(c["kind"] == "markup" for c in cands):
                    fit = [c for c in cands if tag_fits(enclosing_open(tree.cur[c["path"]], c["start"]), tg)]
                    if len(fit) == 1:
                        part["note"] = f"{len(cands)} places hold the text, one inside a <{tg.get('tag')}> with the same id and classes"
                        cands = fit
                if not cands:
                    frag = text_fragments(tree, t)
                    why = (f"text {t[:60]!r} not found in the source as one string (built from variables or split across files?)"
                           + (f"; files holding parts of it: {', '.join(frag)}" if frag else ""))
                    part["candidates"] = frag
                    break
            else:
                cands, why = element_candidates(tree, tg)
                if why:
                    break
                if not cands:
                    key = f"#{tg['id']}" if tg.get("id") else ("." + ".".join(tg["classes"])) if tg.get("classes") else f"href={tg.get('href')}"
                    why = f"no <{tg.get('tag')}> with {key} in the source (rendered by a component or a script?)"
                    break
            if len(cands) > 1:
                part["candidates"] = [describe(c) for c in cands]
                what = repr(norm(tg.get("text", ""))[:60]) if kind == "text" else (f"#{tg['id']}" if tg.get("id") else sel)
                why, status = f"{len(cands)} places hold {what}: " + ", ".join(part["candidates"]), "ambiguous"
                break
            if cands[0].get("problem"):
                part["candidates"] = [describe(cands[0])]
                why, status = f"{describe(cands[0])}: {cands[0]['problem']}", "unsupported"
                break
            found[(cands[0]["path"], cands[0]["start"])] = cands[0]
        if why:
            part.update(status=status, reason=why)
            continue
        part["status"] = "located"
        marks = []
        for c in sorted(found.values(), key=lambda c: (c["path"], -c["start"])):
            marks.append(tree.mark(c["path"], c["start"]))
            if kind == "text":
                replace_text(tree, c, op["text"])
            elif kind == "attributes":
                err = edit_attributes(tree, c, op)
                if err:
                    part.update(status="unsupported", reason=err)
            else:
                err = insert_markup(tree, c, op)
                if err:
                    part.update(status="unsupported", reason=err)
            if part["status"] != "located":
                break
        part["marks"] = marks
        part["where"] = "content file" if any(c["kind"] in ("json", "yaml") for c in found.values()) else "markup"
    extra: List[str] = []
    for rule in fix.get("css") or []:
        part = {"kind": "css", "selector": rule["selector"] + (f" @media {rule['media']}" if rule.get("media") else "")}
        parts.append(part)
        cands = rule_candidates(tree, rule)
        files = sorted({c["path"] for c in cands})
        if len(files) > 1:
            part.update(status="ambiguous", candidates=[describe(c) for c in cands],
                        reason=f"the rule {part['selector']} is defined in {len(files)} files: " + ", ".join(describe(c) for c in cands))
            continue
        if not cands:
            part.update(status="new-file", reason=f"no rule with exactly this selector{' and media query' if rule.get('media') else ''} in the repo")
            extra.append(css_text(rule))
            continue
        block = cands[-1]
        part.update(status="located", marks=[edit_rule(tree, block, rule["declarations"])])
        if len(cands) > 1:
            part["note"] = f"{len(cands)} rules with this selector in {files[0]}, the last one edited (it wins the cascade)"
    if fix.get("css_raw"):
        parts.append({"kind": "css_raw", "selector": "(raw CSS)", "status": "new-file", "reason": "raw CSS always goes to " + CSS_FILE})
        extra.append(fix["css_raw"].rstrip() + "\n")
    if extra:
        cur = tree.cur.get(css_rel)
        if cur is None:
            cur = CSS_HEADER
            tree.cur[css_rel] = ""
            tree.edit(css_rel, 0, 0, cur)
        start = len(tree.cur[css_rel])
        tree.edit(css_rel, start, start, ("" if tree.cur[css_rel].endswith("\n\n") else "\n") + f"/* {fix['id']}: {fix.get('title', '')} */\n" + "".join(extra))
        mk = tree.mark(css_rel, start + 1)
        for p in parts:
            if p["status"] == "new-file":
                p["marks"] = [mk]
    return parts


def text_fragments(tree: Tree, t: str) -> List[str]:
    words = t.split()
    hits = set()
    n = min(4, len(words))
    if n < 2:
        return []
    starts = range(0, len(words) - n + 1)
    for i in list(starts)[::max(1, len(starts) // 12)]:
        rx = text_regex(" ".join(words[i:i + n]))
        for rel in tree.paths(MARKUP | CONTENT):
            m = rx.search(tree.cur[rel])
            if m:
                hits.add(f"{rel}:{line_of(tree.cur[rel], m.start())}")
    return sorted(hits)[:8]


def fix_status(parts: List[Dict[str, Any]]) -> str:
    if any(p["status"] not in ("located", "new-file") for p in parts):
        return "manual"
    return "ready-needs-import" if any(p["status"] == "new-file" for p in parts) else "ready"


def write_patch(tree: Tree, path: Path) -> str:
    text = "".join(unified(rel, tree.orig.get(rel), tree.cur[rel]) for rel in tree.changed())
    path.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="the site source code (read only)")
    ap.add_argument("--fixes", required=True, help="the fixes/ folder written by fixes.py")
    ap.add_argument("--out", help="folder that receives repo-patches/ (default: the parent of --fixes)")
    ap.add_argument("--css-dir", help="folder of the repo where lpa-fixes.css goes (default: next to the only stylesheet, else the root)")
    ap.add_argument("--exclude", action="append", default=[], help="folder name, or path relative to the repo (file or folder), to skip; repeatable")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    fixes_dir = Path(args.fixes).resolve()
    out = Path(args.out).resolve() if args.out else fixes_dir.parent
    if not repo.is_dir():
        print(f"error: --repo {repo} is not a folder", file=sys.stderr)
        return 2
    if out == repo or repo in out.parents:
        print(f"error: --out {out} is inside the repo; the repo is never written, pick a folder outside it", file=sys.stderr)
        return 2
    try:
        results = json.loads((fixes_dir / "fixes.json").read_text(encoding="utf-8"))["fixes"]
    except Exception as e:
        print(f"error: cannot read {fixes_dir / 'fixes.json'}: {e}", file=sys.stderr)
        return 2
    tree = Tree(repo, exclude=args.exclude)
    css_dir = pick_css_dir(tree, args.css_dir)
    css_rel = f"{css_dir}/{CSS_FILE}" if css_dir else CSS_FILE
    tailwind = any((repo / n).exists() for n in ("tailwind.config.js", "tailwind.config.cjs", "tailwind.config.mjs", "tailwind.config.ts")) \
        or any(re.search(r"@tailwind\b|@import\s+[\"']tailwindcss", tree.cur[p]) for p in tree.paths(STYLE))
    dest = out / "repo-patches"
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.patch"):
        old.unlink()
    entries, bad = [], 0
    ready_fixes = []
    for r in results:
        if r.get("id") == "all":
            continue
        e: Dict[str, Any] = {"id": r["id"], "title": r.get("title", ""), "patch": None, "locations": [], "parts": []}
        entries.append(e)
        fj = fixes_dir / r["id"] / "fix.json"
        fix = json.loads(fj.read_text(encoding="utf-8")) if fj.exists() else None
        if r.get("status") != "pass" or not fix or fix.get("status") != "pass":
            e.update(status="skipped", reason="the fix did not pass the before/after of fixes.py: nothing to carry over")
            continue
        t = tree.fork()
        parts = plan_fix(t, fix, css_rel)
        e["status"] = fix_status(parts)
        for p in parts:
            p["locations"] = [f"{m[0]}:{t.old_line(m)}" for m in p.pop("marks", [])]
        e["parts"] = parts
        e["locations"] = list(dict.fromkeys(loc for p in parts for loc in p["locations"]))
        if e["status"] == "manual":
            e["reason"] = "; ".join(f"{p['kind']} {p['selector']}: {p['reason']}" for p in parts if p["status"] not in ("located", "new-file"))
            continue
        if e["status"] == "ready-needs-import":
            hint = import_hint(tree, css_rel)
            e["reason"] = f"creates or extends {css_rel}: import it after the main stylesheet" + (f" ({hint}, add the import on the next line)" if hint else "")
        patch = dest / f"{r['id']}.patch"
        write_patch(t, patch)
        e["patch"] = f"repo-patches/{patch.name}"
        why = apply_check(repo, patch)
        e["apply_check"] = why or "ok"
        if why:
            bad += 1
            e.update(status="manual", reason=f"the generated patch fails git apply --check: {why}", patch=None)
            patch.unlink()
            continue
        ready_fixes.append(fix)
    combined = tree.fork()
    included, excluded = [], []
    for fix in ready_fixes:
        trial = combined.fork()
        parts = plan_fix(trial, fix, css_rel)
        if fix_status(parts) == "manual":
            excluded.append({"id": fix["id"], "reason": "no longer found once the earlier fixes are applied"})
            continue
        combined = trial
        included.append(fix["id"])
    all_entry: Dict[str, Any] = {"patch": None, "fixes": included, "excluded": excluded}
    if included:
        write_patch(combined, dest / "all.patch")
        why = apply_check(repo, dest / "all.patch")
        all_entry.update(patch="repo-patches/all.patch", apply_check=why or "ok")
        if why:
            bad += 1
    record = {"tool": "repo_patch.py", "repo": str(repo), "fixes_dir": str(fixes_dir),
              "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
              "css_file": css_rel, "tailwind": bool(tailwind), "fixes": entries, "all": all_entry}
    (dest / "repo-patches.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (dest / "repo-patches.md").write_text(report_md(record), encoding="utf-8")
    for e in entries:
        print(f"{e['id']}: {e['status']}" + (f" {e['patch']}" if e.get("patch") else "") + (f" ({e['reason']})" if e.get("reason") else ""))
    print(f"all.patch: {len(included)} fixes" + (f", {len(excluded)} left out" if excluded else ""))
    print(f"wrote {dest / 'repo-patches.json'}")
    return 1 if bad else 0


LABEL = {"ready": "ready", "ready-needs-import": f"ready, creates {CSS_FILE} to import", "manual": "to carry over by hand",
         "skipped": "skipped (fix not validated)"}


def report_md(rec: Dict[str, Any]) -> str:
    lines = ["## Repo patches", "",
             "Patches against the site source, one per fix validated by the before/after. Nothing was applied: "
             "review each patch, apply it on a branch (`git apply <patch>`), run the site, and merge it yourself. "
             "Take either the single patches or `repo-patches/all.patch`, not both.", ""]
    if rec.get("tailwind"):
        lines += ["Tailwind project: utility classes are not rewritten. CSS without an exact rule goes to "
                  f"`{rec['css_file']}`; translate it to classes or import the file.", ""]
    for e in rec["fixes"]:
        lines.append(f"### {e['id']} {e['title']}")
        lines.append("")
        lines.append(f"- Status: {LABEL.get(e['status'], e['status'])}")
        if e.get("locations"):
            lines.append(("- Where: " if e["status"] in READY else "- Parts found: ") + ", ".join(f"`{x}`" for x in e["locations"]))
        if e.get("patch"):
            lines.append(f"- Patch: `{e['patch']}` (git apply --check: {e.get('apply_check', 'not run')})")
        if e["status"] == "ready-needs-import":
            lines.append(f"- To do after applying: {e.get('reason', '')}. Then move its rules where they belong.")
        if e["status"] == "manual":
            lines.append(f"- Why by hand: {e.get('reason', '')}")
            cands = [c for p in e.get("parts", []) for c in p.get("candidates", [])]
            if cands:
                lines.append("- Candidates: " + ", ".join(f"`{c}`" for c in dict.fromkeys(cands)))
            lines.append(f"- What to change: `fixes/{e['id']}/patch.css` and `fixes/{e['id']}/patch.js`")
        if e["status"] == "skipped":
            lines.append(f"- {e.get('reason', '')}")
        lines.append("")
    a = rec.get("all") or {}
    if a.get("patch"):
        lines.append(f"All ready fixes at once: `{a['patch']}` ({', '.join(a['fixes'])}; git apply --check: {a.get('apply_check')})."
                     + (" Left out: " + ", ".join(f"{x['id']} ({x['reason']})" for x in a["excluded"]) if a.get("excluded") else ""))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
