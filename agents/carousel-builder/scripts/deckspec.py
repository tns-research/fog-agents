"""deckspec.py: load, validate and lint a deck.json.

Used by build.py. Standard library only: a small JSON Schema subset validator
(type, enum, const, required, properties, additionalProperties, items,
min/maxItems, min/maxLength, pattern, minimum/maximum, oneOf, anyOf, $ref) so
the agent runs without the jsonschema package. When jsonschema is installed it
is not needed either: the subset covers assets/deck.schema.json entirely.

Every problem is an Issue(level, code, where, message). build.py never raises
on a bad spec: it reports, renders what it can, and lets qa.py show the result.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

AGENT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = AGENT_DIR / "assets" / "deck.schema.json"

FORMATS = {
    "linkedin": (1080, 1350),
    "instagram": (1080, 1350),
    "square": (1080, 1080),
}

MAX_SLIDES = 20  # Instagram publishes 20 images per carousel at most
MIN_SLIDES = 3


@dataclass
class Issue:
    level: str  # "error" | "warning"
    code: str
    where: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


# --------------------------------------------------------------------------
# Minimal JSON Schema validator
# --------------------------------------------------------------------------

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _is_type(value: Any, t: str) -> bool:
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


class SchemaValidator:
    def __init__(self, schema: Dict[str, Any]):
        self.root = schema

    def _resolve(self, ref: str) -> Dict[str, Any]:
        node: Any = self.root
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        return node

    def validate(self, inst: Any, schema: Optional[Dict[str, Any]] = None, path: str = "$") -> List[str]:
        s = self.root if schema is None else schema
        if "$ref" in s:
            return self.validate(inst, self._resolve(s["$ref"]), path)
        errs: List[str] = []
        if "const" in s and inst != s["const"]:
            return [f"{path}: expected {s['const']!r}"]
        if "enum" in s and inst not in s["enum"]:
            errs.append(f"{path}: {inst!r} not one of {s['enum']}")
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_is_type(inst, t) for t in types):
                return errs + [f"{path}: expected {'/'.join(types)}, got {type(inst).__name__}"]
        if "oneOf" in s or "anyOf" in s:
            branches = s.get("oneOf") or s.get("anyOf")
            results = [self.validate(inst, b, path) for b in branches]
            ok = [r for r in results if not r]
            if not ok:
                # Pick the branch whose 'type' const matches, else the closest.
                pick = None
                if isinstance(inst, dict) and "type" in inst:
                    for b, r in zip(branches, results):
                        bb = self._resolve(b["$ref"]) if "$ref" in b else b
                        const = bb.get("properties", {}).get("type", {}).get("const")
                        if const == inst["type"]:
                            pick = r
                    if pick is None:
                        consts = []
                        for b in branches:
                            bb = self._resolve(b["$ref"]) if "$ref" in b else b
                            c = bb.get("properties", {}).get("type", {}).get("const")
                            if c:
                                consts.append(c)
                        if consts:
                            return errs + [f"{path}.type: {inst['type']!r} is not a block type ({', '.join(consts)})"]
                if pick is None:
                    pick = min(results, key=len)
                errs.extend(pick)
        if isinstance(inst, str):
            if "minLength" in s and len(inst.strip()) < s["minLength"]:
                errs.append(f"{path}: empty or shorter than {s['minLength']} characters")
            if "maxLength" in s and len(inst) > s["maxLength"]:
                errs.append(f"{path}: {len(inst)} characters, max {s['maxLength']}")
            if "pattern" in s and not re.search(s["pattern"], inst):
                errs.append(f"{path}: {inst!r} does not match {s['pattern']}")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool):
            if "minimum" in s and inst < s["minimum"]:
                errs.append(f"{path}: {inst} < {s['minimum']}")
            if "maximum" in s and inst > s["maximum"]:
                errs.append(f"{path}: {inst} > {s['maximum']}")
        if isinstance(inst, list):
            if "minItems" in s and len(inst) < s["minItems"]:
                errs.append(f"{path}: {len(inst)} items, min {s['minItems']}")
            if "maxItems" in s and len(inst) > s["maxItems"]:
                errs.append(f"{path}: {len(inst)} items, max {s['maxItems']}")
            if "items" in s:
                for i, item in enumerate(inst):
                    errs.extend(self.validate(item, s["items"], f"{path}[{i}]"))
        if isinstance(inst, dict):
            for key in s.get("required", []):
                if key not in inst:
                    errs.append(f"{path}: missing '{key}'")
            props = s.get("properties", {})
            for key, val in inst.items():
                if key in props:
                    errs.extend(self.validate(val, props[key], f"{path}.{key}"))
                elif s.get("additionalProperties") is False:
                    errs.append(f"{path}: unknown field '{key}'")
        return errs


# --------------------------------------------------------------------------
# Copy lint (local minimum; the shared writing gate runs on top when present)
# --------------------------------------------------------------------------

DASH_RE = re.compile("[" + chr(0x2014) + chr(0x2013) + "]")
NUMBER_RE = re.compile(r"\d")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def iter_texts(block: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("text", "sub", "label", "context", "value", "caption", "title", "note", "author", "role", "url"):
        v = block.get(key)
        if isinstance(v, str):
            out.append(v)
    for item in block.get("items", []) or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.extend(x for x in (item.get("text"), item.get("sub")) if isinstance(x, str))
    for ann in block.get("annotations", []) or []:
        out.append(ann.get("label", ""))
    return out


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema() -> Dict[str, Any]:
    return load_json(SCHEMA_PATH)


def validate_deck(deck: Any) -> List[Issue]:
    issues: List[Issue] = []
    for msg in SchemaValidator(load_schema()).validate(deck):
        where, _, text = msg.partition(": ")
        issues.append(Issue("error", "schema", where, text))
    return issues


def source_ok(src: Any, registry: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Return an error message when a source cannot back a number, else None."""
    if src is None:
        return "no source"
    if isinstance(src, str):
        entry = registry.get(src)
        if entry is None:
            return f"source id '{src}' is not in sources[]"
        src = entry
    if not isinstance(src, dict):
        return "malformed source"
    if not (src.get("url") or src.get("proof_ref")):
        return f"source '{src.get('label', '?')}' has neither url nor proof_ref"
    return None


def lint_deck(deck: Dict[str, Any], direction: Dict[str, Any]) -> List[Issue]:
    """Spec-level checks that do not need a browser."""
    issues: List[Issue] = []
    slides = deck.get("slides", []) or []
    registry = {s.get("id"): s for s in deck.get("sources", []) or [] if isinstance(s, dict)}
    budgets = direction.get("budgets", {})

    n = len(slides)
    if n > MAX_SLIDES:
        issues.append(Issue("error", "too-many-slides", "$.slides", f"{n} slides, max {MAX_SLIDES}: Instagram publishes 20 images per carousel at most. Merge or cut slides, or split into two carousels."))
    if n < MIN_SLIDES:
        issues.append(Issue("warning", "short-deck", "$.slides", f"{n} slides. A carousel needs at least {MIN_SLIDES}."))

    roles = [s.get("role") for s in slides if isinstance(s, dict)]
    if roles and roles[0] != "cover":
        issues.append(Issue("warning", "no-cover", "$.slides[0]", "The first slide is not role=cover."))
    if roles.count("cover") > 1:
        issues.append(Issue("error", "two-covers", "$.slides", "More than one cover slide."))

    tones: List[str] = []
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        where = f"$.slides[{i}]"
        blocks = [b for b in slide.get("blocks", []) or [] if isinstance(b, dict)]
        types = [b.get("type") for b in blocks]
        if types.count("title") > 1:
            issues.append(Issue("error", "two-titles", where, "One title per slide: one idea per slide."))
        if types.count("chart") > 1:
            issues.append(Issue("error", "two-charts", where, "One chart per slide."))
        for j, b in enumerate(blocks):
            bw = f"{where}.blocks[{j}]"
            texts = iter_texts(b)
            for t in texts:
                if DASH_RE.search(t):
                    issues.append(Issue("error", "dash", bw, f"Em or en dash in '{t[:60]}'. Use a comma, colon, period or parentheses."))
            accent = b.get("accent")
            if accent and accent not in (b.get("text") or ""):
                issues.append(Issue("error", "accent-not-found", bw, f"accent '{accent}' is not a substring of the text."))
            # Claims: data blocks are required to carry a source by the schema;
            # here we check the source resolves to a URL or an approved proof.
            if b.get("type") in ("stat", "chart", "quote"):
                err = source_ok(b.get("source"), registry)
                if err:
                    issues.append(Issue("error", "unsourced", bw, f"{b.get('type')} block: {err}."))
            elif b.get("type") in ("title", "body", "list"):
                joined = " ".join(texts)
                digits = NUMBER_RE.findall(YEAR_RE.sub("", joined))
                slide_has_source = any(x.get("source") for x in blocks)
                if digits and not b.get("source") and not slide_has_source:
                    issues.append(Issue("warning", "number-without-source", bw, "Text holds a number and the slide has no source. Add source, or remove the number if it is a claim."))
            # Word budgets from the direction.
            t = b.get("type")
            if t == "title" and b.get("text"):
                lim = budgets.get("title_words", 14) if slide.get("role") != "cover" else budgets.get("cover_title_words", 16)
                wc = word_count(b["text"])
                if wc > lim:
                    issues.append(Issue("warning", "over-budget", bw, f"title has {wc} words, budget {lim}."))
            if t == "body" and b.get("text"):
                lim = budgets.get("body_words", 50)
                wc = word_count(b["text"])
                if wc > lim:
                    issues.append(Issue("warning", "over-budget", bw, f"body has {wc} words, budget {lim}."))
            if t == "list":
                items = b.get("items", []) or []
                lim = budgets.get("list_items", 5)
                if len(items) > lim:
                    issues.append(Issue("warning", "over-budget", bw, f"list has {len(items)} items, budget {lim}."))
            if t == "photo" and b.get("fit") == "cover" and not b.get("crop_ok"):
                issues.append(Issue("error", "destructive-crop", bw, "fit=cover crops the photo. Use contain, or set crop_ok when the owner accepted a crop."))
            if t == "chart":
                issues.extend(lint_chart(b, bw))
        tones.append(slide_tone(slide))

    # Rhythm: no long run of dense slides, at least one calm slide in the middle.
    run = 0
    for i, tone in enumerate(tones):
        run = run + 1 if tone == "dense" else 0
        if run == 3:
            issues.append(Issue("warning", "rhythm", f"$.slides[{i}]", "Three dense slides in a row. Insert a calm slide (one number, one quote, one photo)."))
    if n >= 6 and "calm" not in tones[1:-1]:
        issues.append(Issue("warning", "rhythm", "$.slides", "No calm slide between cover and CTA."))
    return issues


def lint_chart(b: Dict[str, Any], where: str) -> List[Issue]:
    out: List[Issue] = []
    kind = b.get("kind")
    if kind in ("bar", "donut"):
        data = b.get("data") or []
        if len(data) < 2:
            out.append(Issue("error", "chart-data", where, f"{kind} chart needs 'data' with at least 2 entries."))
        if kind == "donut":
            if any((d.get("value") or 0) < 0 for d in data):
                out.append(Issue("error", "chart-data", where, "donut values must be positive."))
            if len(data) > 4:
                out.append(Issue("error", "chart-data", where, "donut: 4 segments max. Use a bar chart."))
        labels = [d.get("label") for d in data]
        hl = b.get("highlight")
        if hl and hl not in labels:
            out.append(Issue("error", "chart-highlight", where, f"highlight '{hl}' is not a data label."))
    elif kind == "line":
        x = b.get("x") or []
        series = b.get("series") or []
        if len(x) < 2 or not series:
            out.append(Issue("error", "chart-data", where, "line chart needs 'x' (2+) and 'series'."))
        for s in series:
            if len(s.get("values") or []) != len(x):
                out.append(Issue("error", "chart-data", where, f"series '{s.get('name')}' has {len(s.get('values') or [])} values for {len(x)} x labels."))
        hl = b.get("highlight")
        if hl and hl not in [s.get("name") for s in series]:
            out.append(Issue("error", "chart-highlight", where, f"highlight '{hl}' is not a series name."))
    if not b.get("highlight"):
        out.append(Issue("warning", "chart-no-highlight", where, "No highlight: say which value carries the message, it gets the only accent."))
    return out


def slide_tone(slide: Dict[str, Any]) -> str:
    if slide.get("tone") in ("calm", "dense"):
        return slide["tone"]
    blocks = [b for b in slide.get("blocks", []) or [] if isinstance(b, dict)]
    types = {b.get("type") for b in blocks}
    if slide.get("role") in ("cover", "cta"):
        return "calm"
    if types & {"list", "chart", "screenshot", "logo-row"}:
        return "dense"
    if types & {"stat", "quote", "photo"} and "body" not in types:
        return "calm"
    words = sum(word_count(t) for b in blocks for t in iter_texts(b))
    return "calm" if words <= 30 else "dense"


def resolve_source(src: Any, registry: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if src is None:
        return None
    if isinstance(src, str):
        return registry.get(src) or {"label": src}
    if isinstance(src, dict):
        return src
    return None
