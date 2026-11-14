"""adspec.py: load, validate and lint an ads.json; derive the visible text.

Shared by build.py, qa.py, proofread.py, package_meta.py and plates.py.
Standard library only: a small JSON Schema subset validator (type, enum,
const, required, properties, additionalProperties, items, min/maxItems,
min/maxLength, pattern, minimum/maximum, oneOf, $ref) covers
assets/ads.schema.json, so no jsonschema package is needed.

Every problem is an Issue(level, code, where, message). Nothing here raises on
a bad spec: callers report, render what they can, and let qa.py show it.

The single source of every visible word is visible_text(): build.py renders
exactly those strings, qa.py checks the DOM against them, proofread.py checks
the reviewer's transcription against them.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AGENT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = AGENT_DIR / "assets" / "ads.schema.json"

# Canvas per format. Meta feed: 1080x1080 and 1080x1350; Stories and Reels:
# 1080x1920.
FORMATS: Dict[str, Tuple[int, int]] = {"1:1": (1080, 1080), "4:5": (1080, 1350), "9:16": (1080, 1920)}

# Safe zones in px on a 1080 wide canvas: (top, right, bottom, left).
# Feed: 6 % of the width on every side (shared reviewing-renders R2), rounded
# up to 72 px so text never sits on the limit. 9:16: Meta's Reels guidance,
# "leaving roughly 14% of the top, 35% of the bottom, and 6% on each side"
# free of text, logos and key elements
# (https://www.facebook.com/business/ads-guide/update/image/instagram-reels,
# read 2026-10-12). Meta gives Instagram Stories the same zone
# (https://www.facebook.com/business/ads-guide/update/video/instagram-story,
# read 2026-10-12), so one 9:16 render serves both placements.
SAFE: Dict[str, Tuple[int, int, int, int]] = {
    "1:1": (72, 72, 72, 72),
    "4:5": (72, 72, 72, 72),
    "9:16": (269, 72, 672, 72),
}

# 9:16: lowest edge of the visual zone (media running into Meta's bottom band,
# never text), in px from the bottom. A layout margin, not a Meta figure: the
# photo stops short of the bottom edge so its base is not cut by the frame.
STORY_VISUAL_BOTTOM = 120

STYLES = [
    "ugc-text-overlay", "meme-static", "testimonial-screenshot", "before-after-asymmetric",
    "ingredient-origin-strip", "cost-reframe-card", "hybrid-2d-3d-fusion", "three-benefits-card",
    "us-vs-them-comparison", "crossed-out-problems", "social-proof-card", "feature-callout-arrows",
    "myth-vs-fact", "reply-to-comment", "bold-statement", "mini-landing-page", "benefit-timeline",
    "flowchart-decision",
]

# Meta call-to-action button types the import CSV accepts most often. An
# unknown value is a warning (the Ads Manager template of the day decides).
META_CTAS = {
    "LEARN_MORE", "SIGN_UP", "APPLY_NOW", "SHOP_NOW", "BOOK_TRAVEL", "CONTACT_US", "DOWNLOAD",
    "GET_OFFER", "GET_QUOTE", "SUBSCRIBE", "ORDER_NOW", "BUY_NOW", "REGISTER_NOW", "WATCH_MORE",
    "SEE_MENU", "SEND_MESSAGE", "GET_DIRECTIONS", "NO_BUTTON",
}

# Per style: what the layout needs to render. (field, min, max) for lists.
STYLE_NEEDS: Dict[str, Dict[str, Any]] = {
    "bold-statement": {},
    "meme-static": {},
    "three-benefits-card": {"bullets": (2, 5)},
    "crossed-out-problems": {"bullets": (2, 5)},
    "mini-landing-page": {"bullets": (2, 4), "cta": True},
    "benefit-timeline": {"bullets": (2, 5), "labels": True},
    "flowchart-decision": {"bullets": (2, 3), "labels": True},
    "us-vs-them-comparison": {"columns": (2, 5), "mirror": True},
    "myth-vs-fact": {"columns": (1, 3)},
    "before-after-asymmetric": {"columns": (1, 4)},
    "cost-reframe-card": {"columns": (1, 2)},
    "social-proof-card": {"proof": True},
    "testimonial-screenshot": {"proof": True, "attribution": True},
    "reply-to-comment": {"comment": True},
    "feature-callout-arrows": {"media": 1, "callouts": (2, 4)},
    "ugc-text-overlay": {"media": 1},
    "ingredient-origin-strip": {"media": 1},
    "hybrid-2d-3d-fusion": {"media": 1},
}


@dataclass
class Issue:
    level: str  # "error" | "warning"
    code: str
    where: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


# --------------------------------------------------------------------------
# Minimal JSON Schema validator (same subset as carousel-builder's deckspec)
# --------------------------------------------------------------------------

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


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
            if not any(not r for r in results):
                errs.extend(min(results, key=len))
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
# Loading
# --------------------------------------------------------------------------

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_spec(path: Path) -> Tuple[Optional[Dict[str, Any]], List[Issue]]:
    try:
        spec = load_json(path)
    except Exception as e:  # noqa: BLE001
        return None, [Issue("error", "json", str(path), f"ads.json does not parse: {e}")]
    issues = [Issue("error", "schema", *msg.split(": ", 1)) if ": " in msg else Issue("error", "schema", "$", msg)
              for msg in SchemaValidator(load_json(SCHEMA_PATH)).validate(spec)]
    if not isinstance(spec, dict) or not isinstance(spec.get("ads"), list):
        return None, issues
    issues += lint(spec)
    return spec, issues


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------

def ratio_tag(fmt: str) -> str:
    return fmt.replace(":", "x")


def ad_number(ad: Dict[str, Any], index: int) -> int:
    n = ad.get("n")
    return n if isinstance(n, int) and n > 0 else index + 1


TEST_VARIABLES = ("hook", "subhead", "visual", "cta", "surface")


def ad_name(spec: Dict[str, Any], ad: Dict[str, Any], index: int, fmt: str) -> str:
    """Naming convention: <project>_<NN>_<stage>_<angle>_<style>_<ratio>, plus
    _t-<variable> for a one-variable test built from a winning recipe
    (scripts/recipe_variants.py). Every token is a slug, so perf.py can split
    a name back into its parts."""
    project = spec.get("meta", {}).get("project", "ads")
    parts = [project, f"{ad_number(ad, index):02d}", ad.get("stage", "x"), ad.get("angle", "x"),
             ad.get("style", "x"), ratio_tag(fmt)]
    variable = (ad.get("test") or {}).get("variable")
    if variable:
        parts.append(f"t-{variable}")
    return "_".join(parts)


def parse_ad_name(name: str) -> Optional[Dict[str, str]]:
    """Inverse of ad_name. None when the name does not follow the convention."""
    parts = (name or "").strip().split("_")
    if len(parts) not in (6, 7) or parts[2] not in ("tofu", "mofu", "bofu") or not re.fullmatch(r"\d{2}", parts[1]):
        return None
    out = {"project": parts[0], "n": parts[1], "stage": parts[2], "angle": parts[3], "style": parts[4], "ratio": parts[5].replace("x", ":")}
    if len(parts) == 7:
        m = re.fullmatch(r"t-([a-z]+)", parts[6])
        if not m or m.group(1) not in TEST_VARIABLES:
            return None
        out["test"] = m.group(1)
    return out


# --------------------------------------------------------------------------
# Visible text
# --------------------------------------------------------------------------

def item_parts(item: Any) -> Tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("label") or ""), str(item.get("text") or "")
    return "", str(item or "")


def source_label(spec: Dict[str, Any], ref: str) -> Optional[str]:
    for s in spec.get("sources", []) or []:
        if s.get("id") == ref:
            return s.get("label")
    return None


def proof_source_line(spec: Dict[str, Any], ad: Dict[str, Any]) -> Optional[str]:
    proof = ad.get("proof") or {}
    if not proof:
        return None
    label = source_label(spec, proof.get("source", ""))
    if label and proof.get("show_source", True):
        return f"Source: {label}" if spec.get("meta", {}).get("language") != "fr" else f"Source : {label}"
    return None


def visible_text(spec: Dict[str, Any], ad: Dict[str, Any], logo_text: Optional[str] = None) -> Dict[str, List[str]]:
    """Every string that will be visible on the ad, by origin.

    dom:   set by the HTML (copy, proof, source line), in reading order
    media: printed on the supplied media (labels, packaging, UI)
    logo:  the brand wordmark when the logo is shown (an SVG, not DOM text)
    """
    c = ad.get("copy") or {}
    dom: List[str] = []

    def add(*vals: Any) -> None:
        for v in vals:
            if isinstance(v, str) and v.strip():
                dom.append(v)

    add(c.get("badge"), c.get("headline"), c.get("subhead"))
    cols = c.get("columns") or {}
    for side in ("them", "us"):
        col = cols.get(side) or {}
        add(col.get("label"), *(col.get("items") or []))
    for it in c.get("bullets") or []:
        add(*item_parts(it))
    cm = c.get("comment") or {}
    if cm:
        add(cm.get("author"), cm.get("text"), logo_text, cm.get("reply"))
    for co in c.get("callouts") or []:
        add(co.get("text"))
    proof = ad.get("proof") or {}
    if proof:
        add(proof.get("text"), proof.get("attribution"), proof_source_line(spec, ad))
    add(c.get("cta"))
    media: List[str] = []
    for m in ad.get("media") or []:
        media += [t for t in m.get("visible_text") or [] if t.strip()]
    logo = [logo_text] if (logo_text and ad.get("logo", True)) else []
    return {"dom": dom, "media": media, "logo": logo}


# --------------------------------------------------------------------------
# Tokens (word diff)
# --------------------------------------------------------------------------

# Edge punctuation a transcriber does not reliably copy; stripped from both
# sides before comparing. Inner punctuation (l'idée, 3.5, e-mail) stays.
EDGE = ".,;:!?\"'()[]{}<>" + "«»“”‘’…·*"
APOSTROPHES = {"’": "'", "‘": "'", "ʼ": "'"}
SPACES = {" ": " ", " ": " ", " ": " "}


def tokens(text: str) -> List[str]:
    """Words of a text, NFC, case and accents kept. Typographic apostrophes
    count as straight ones (a transcriber cannot tell them apart in a PNG)."""
    t = unicodedata.normalize("NFC", text or "")
    for a, b in {**APOSTROPHES, **SPACES}.items():
        t = t.replace(a, b)
    out = []
    for w in t.split():
        w = w.strip(EDGE)
        if w and re.search(r"\w", w):
            out.append(w)
    return out


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def word_diff(expected: List[str], observed: List[str]) -> Dict[str, Any]:
    """Order-free word comparison (columns and badges make reading order
    ambiguous). Returns missing, extra and the likely misspellings paired by
    similarity, with the kind of each difference."""
    import difflib
    e, o = Counter(expected), Counter(observed)
    missing = list((e - o).elements())
    extra = list((o - e).elements())
    pairs = []
    pool = list(extra)
    for m in list(missing):
        best, score = None, 0.0
        for x in pool:
            r = difflib.SequenceMatcher(a=m.lower(), b=x.lower()).ratio()
            if r > score:
                best, score = x, r
        if best is not None and score >= 0.6:
            if strip_accents(m) == strip_accents(best):
                kind = "accent"
            elif m.lower() == best.lower():
                kind = "case"
            else:
                kind = "spelling"
            pairs.append({"expected": m, "observed": best, "kind": kind})
            pool.remove(best)
            missing.remove(m)
    return {"misspelled": pairs, "missing": missing, "extra": pool,
            "ok": not pairs and not missing and not pool}


# --------------------------------------------------------------------------
# Lint
# --------------------------------------------------------------------------

DASH_RE = re.compile("[" + chr(0x2014) + chr(0x2013) + "]")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _walk_strings(node: Any, path: str):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")


def copy_strings(ad: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(path, text) of every copy string that can carry a claim: on-ad copy
    except time-step and branch labels, and the Meta ad text."""
    out: List[Tuple[str, str]] = []
    c = ad.get("copy") or {}
    for k in ("badge", "headline", "subhead", "cta"):
        if isinstance(c.get(k), str):
            out.append((f"copy.{k}", c[k]))
    for i, it in enumerate(c.get("bullets") or []):
        out.append((f"copy.bullets[{i}]", item_parts(it)[1]))
    for side in ("them", "us"):
        for i, t in enumerate(((c.get("columns") or {}).get(side) or {}).get("items") or []):
            out.append((f"copy.columns.{side}.items[{i}]", t))
    for k in ("text", "reply"):
        if isinstance((c.get("comment") or {}).get(k), str):
            out.append((f"copy.comment.{k}", c["comment"][k]))
    for i, co in enumerate(c.get("callouts") or []):
        out.append((f"copy.callouts[{i}]", co.get("text", "")))
    for k in ("primary_text", "headline", "description"):
        v = (ad.get("meta_ad") or {}).get(k)
        if isinstance(v, str):
            out.append((f"meta_ad.{k}", v))
    return out


def source_ok(spec: Dict[str, Any], ref: str) -> bool:
    if re.fullmatch(r"positioning\.proof\[\d+\]", ref or ""):
        return True
    return any(s.get("id") == ref for s in spec.get("sources", []) or [])


def lint(spec: Dict[str, Any]) -> List[Issue]:
    issues: List[Issue] = []
    for path, text in _walk_strings(spec, "$"):
        if DASH_RE.search(text):
            issues.append(Issue("error", "dash", path, "Em or en dash: use a comma, colon, period or parentheses."))
    ids = set()
    for i, ad in enumerate(spec.get("ads") or []):
        if not isinstance(ad, dict):
            continue
        w = f"$.ads[{i}]"
        if ad.get("id") in ids:
            issues.append(Issue("error", "duplicate-id", w, f"id '{ad.get('id')}' used twice."))
        ids.add(ad.get("id"))
        if len(set(ad.get("formats") or [])) != len(ad.get("formats") or []):
            issues.append(Issue("error", "duplicate-format", w, "A format is listed twice."))
        c = ad.get("copy") or {}
        # Claims: every number in the copy is backed by a sourced claim.
        claims = list(ad.get("claims") or [])
        proof = ad.get("proof") or {}
        if proof:
            claims.append({"text": proof.get("text", ""), "source": proof.get("source", "")})
        for j, cl in enumerate(claims):
            if not source_ok(spec, cl.get("source", "")):
                issues.append(Issue("error", "unsourced", f"{w}.claims[{j}]" if j < len(ad.get("claims") or []) else f"{w}.proof",
                                    f"Source '{cl.get('source')}' is neither a sources[].id nor positioning.proof[N]."))
        claim_text = " ".join(cl.get("text", "") for cl in claims if source_ok(spec, cl.get("source", "")))
        claim_nums = set(NUM_RE.findall(claim_text))
        for path, text in copy_strings(ad):
            for num in NUM_RE.findall(text):
                if num not in claim_nums:
                    issues.append(Issue("error", "unsourced-number", f"{w}.{path}",
                                        f"'{num}' in \"{text[:60]}\" is not in a sourced claim: add it to claims[] with its source, or remove it."))
        # Style needs.
        needs = STYLE_NEEDS.get(ad.get("style", ""), {})
        bl = c.get("bullets") or []
        if "bullets" in needs:
            lo, hi = needs["bullets"]
            if not lo <= len(bl) <= hi:
                issues.append(Issue("error", "style-needs", f"{w}.copy.bullets", f"{ad['style']} needs {lo} to {hi} bullets, got {len(bl)}."))
            if needs.get("labels") and any(not item_parts(b)[0] for b in bl):
                issues.append(Issue("error", "style-needs", f"{w}.copy.bullets", f"{ad['style']} needs a label on every bullet."))
        if "columns" in needs:
            cols = c.get("columns")
            if not cols:
                issues.append(Issue("error", "style-needs", f"{w}.copy.columns", f"{ad['style']} needs copy.columns (them, us)."))
            else:
                lo, hi = needs["columns"]
                for side in ("them", "us"):
                    n = len((cols.get(side) or {}).get("items") or [])
                    if not lo <= n <= hi:
                        issues.append(Issue("error", "style-needs", f"{w}.copy.columns.{side}", f"{ad['style']} needs {lo} to {hi} items per column, got {n}."))
                if needs.get("mirror") and len(cols["them"].get("items", [])) != len(cols["us"].get("items", [])):
                    issues.append(Issue("error", "style-needs", f"{w}.copy.columns", "Comparison rows must mirror: same item count on both sides."))
        if needs.get("cta") and not c.get("cta"):
            issues.append(Issue("error", "style-needs", f"{w}.copy.cta", f"{ad['style']} needs a CTA."))
        if needs.get("proof") and not proof:
            issues.append(Issue("error", "style-needs", f"{w}.proof", f"{ad['style']} needs a sourced proof (a real review or quote)."))
        if needs.get("attribution") and proof and not proof.get("attribution"):
            issues.append(Issue("error", "style-needs", f"{w}.proof.attribution", f"{ad['style']} needs the reviewer's attribution."))
        if needs.get("comment"):
            cm = c.get("comment")
            if not cm:
                issues.append(Issue("error", "style-needs", f"{w}.copy.comment", "reply-to-comment needs copy.comment."))
            elif not cm.get("source"):
                issues.append(Issue("error", "unsourced", f"{w}.copy.comment.source", "A comment is shown only when it was really posted: give its source."))
        if needs.get("media") and not (ad.get("media") or []):
            issues.append(Issue("error", "style-needs", f"{w}.media", f"{ad['style']} needs a photo, product, screenshot or plate."))
        if "callouts" in needs:
            lo, hi = needs["callouts"]
            if not lo <= len(c.get("callouts") or []) <= hi:
                issues.append(Issue("error", "style-needs", f"{w}.copy.callouts", f"{ad['style']} needs {lo} to {hi} callouts."))
        # Media.
        for j, m in enumerate(ad.get("media") or []):
            if m.get("role") == "plate":
                if not m.get("prompt"):
                    issues.append(Issue("error", "plate-prompt", f"{w}.media[{j}]", "A plate needs a prompt (scene only, no text)."))
                elif re.search(r"\b(text|headline|words?|letters?|typography|caption|logo)\b", m["prompt"], re.I) and not re.search(r"\bno (text|letters|logo)", m["prompt"], re.I):
                    issues.append(Issue("warning", "plate-prompt", f"{w}.media[{j}].prompt", "The plate prompt mentions text or a logo: plates are text-free, the HTML sets every word."))
            if m.get("fit") == "cover" and m.get("role") not in ("plate",):
                issues.append(Issue("warning", "media-cropped", f"{w}.media[{j}].fit", "cover crops a real photo or product: use contain (shown whole) unless the founder agreed."))
            if m.get("role") in ("photo", "product", "screenshot") and "visible_text" not in m:
                issues.append(Issue("warning", "media-text-undeclared", f"{w}.media[{j}]",
                                    "Declare visible_text (empty list when the media shows no word) so the proofread diff covers labels and packaging."))
        # Meta ad.
        ma = ad.get("meta_ad")
        if not ma:
            issues.append(Issue("warning", "no-meta-ad", w, "No meta_ad: the import CSV row will lack primary text, headline, CTA and URL."))
        else:
            if ma.get("cta") and ma["cta"] not in META_CTAS:
                issues.append(Issue("warning", "meta-cta", f"{w}.meta_ad.cta", f"'{ma['cta']}' is not a common Meta CTA type; check the Ads Manager template."))
            if len(ma.get("primary_text", "")) > 600:
                issues.append(Issue("warning", "meta-primary-long", f"{w}.meta_ad.primary_text", "Primary text over 600 characters; the feed truncates it early."))
        if ad.get("stage") == "tofu" and (ma or {}).get("cta") in ("SHOP_NOW", "BUY_NOW", "ORDER_NOW"):
            issues.append(Issue("warning", "stage-cta", f"{w}.meta_ad.cta", "A hard-sell CTA on a TOFU ad (ad-library: never Shop now at TOFU)."))
    return issues


def counts(issues: List[Issue]) -> Dict[str, int]:
    return {"errors": sum(1 for i in issues if i.level == "error"), "warnings": sum(1 for i in issues if i.level == "warning")}
