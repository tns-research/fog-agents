#!/usr/bin/env python3
"""photo_edit.py: edit a real photo for an ad (mode photo_edit), text never drawn by the model.

  python3 scripts/photo_edit.py check    <photo-edits.json> [--context DIR]
  python3 scripts/photo_edit.py estimate <photo-edits.json> --select SEL [--config config.json]
  python3 scripts/photo_edit.py render   <photo-edits.json> --select SEL [--backend manual|higgsfield|fal|openai|stub]
                                         [--out DIR] [--config config.json] [--confirm-spend]
                                         [--accept-public-url]
  python3 scripts/photo_edit.py verify   <photo-edits.json> [--out DIR] [--review review.json]

The founder supplies a phone photo (founder, product in hand, team). The model
writes photo-edits.json (contract: assets/photo-edits.schema.json): per photo,
3 to 5 edit concepts at 30, 50 or 80 % of the frame, what changes, what never
changes, the text zone the HTML copy will use, and the full prompt. This
script does the measurable part:

  check     schema, lint (invariants named in never_changes and in the
            prompt's keep line, labelled prompt fields, "no text" said, at
            least two edit levels per photo, photo file present) and consent:
            a photo with people needs person_slug on every concept, each
            slug cleared for the ads scope in project-context/people.json.
            A person absent from people.json, refused, unknown or cleared for
            another scope only is a BLOCK, except the entry marked
            is_operator (the founder running the agent).
  estimate  Gate 2 figures for the selection: model, size, quality, count,
            per-image price, total. No call, no key.
  render    one image per selected concept (Gate 1 = the selection).
            manual (default): no API, 0 USD from this script. Writes a pack in
                    <out>/_manual/ (one prompt file per concept, the source
                    photo, the exact filename to drop). Whoever has an image
                    edit tool runs it: the founder in their own app, or the
                    agent through an image tool of its harness (an MCP
                    server, a built-in tool). The file is dropped as
                    <out>/<photo>--<concept>.(png|jpg|jpeg|webp); the same
                    command run again collects it, fits it to the size asked
                    and records it. Nothing is sent by this script.
            higgsfield: same as manual, plus <out>/_manual/higgsfield-plan.json:
                    for each concept the Higgsfield MCP calls the agent makes
                    (media_upload of the photo, curl PUT, media_confirm, then
                    generate_image with get_cost true first, the photo as
                    image_references, model from config higgsfield_model,
                    default gpt_image_2_5). Billed in Higgsfield credits on
                    the founder's account: the agent shows the get_cost
                    figure and waits for a yes before the real call.
            fal:    the photo is uploaded to fal storage (public URL: anyone
                    holding it can download the photo), then the fal CLI runs
                    the edit endpoint of config fal_model (default
                    fal-ai/nano-banana-2). FAL_KEY or FAL_API_KEY. A photo with
                    people also needs --accept-public-url. Spend gate as below.
            openai: POST /v1/images/edits, the photo attached, model from
                    config (default gpt-image-2), OPENAI_API_KEY. The photo
                    goes to OpenAI's API, no public link.
            stub:   tests only, explicit. A local deterministic Pillow
                    placeholder (crop to the size, regrade, a backdrop tint
                    outside the centre that grows with the edit level), 0 USD.
            fal and openai are refused without --confirm-spend (or
            FOG_ALLOW_SPEND=1): the estimate is printed and nothing is sent.
            One attempt per image, no retry. Each key is read from the
            environment and sent only to its own provider, as the
            Authorization header; it is never written to a file or a log.
            Writes <out>/<photo>--<concept>.png and <out>/photo-edit-run.json
            with a ready ads.json media entry per image (role photo, fit
            contain, visible_text, edit provenance).
  verify    every rendered file exists and has the size asked; writes the
            visual review packet (<spec dir>/review/photo-edit-packet.md and
            a template). With --review, the reviewer's answers per file:
            anything but IDENTITY_OK (face, expression, pose, hands, five
            fingers, object unchanged, no text painted) is a BLOCK.

Selection (--select): "all", or comma-separated concept ids, or
<photo-id>/<concept-id> when two photos share a concept id.

Price: config photo_edit.price_per_image_usd (default 0.17, an estimate for
one 1536x1024 high quality output of gpt-image-2, input image tokens not
included). Check it on OpenAI's pricing page before quoting it at Gate 2.

Exit codes: 0 ok, 1 spec errors or BLOCK, 2 provider key or fal CLI missing
(nothing sent), 3 bad input, 4 spend gate or public-URL gate closed (nothing
sent, estimate printed), 5 manual pack written, files still to drop.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
REPO = AGENT.parent.parent
SCHEMA_PATH = AGENT / "assets" / "photo-edits.schema.json"
sys.path.insert(0, str(HERE))
import adspec  # noqa: E402
from adspec import Issue  # noqa: E402
import render_ads  # noqa: E402

sys.path.insert(0, str(REPO / "shared" / "scripts"))
try:
    import registry as _registry  # type: ignore  # noqa: E402
except ImportError:
    _registry = None

SCOPE = "ads"
DEFAULTS: Dict[str, Any] = {"backend": "manual", "model": "gpt-image-2", "size": "1536x1024", "quality": "high",
                            "input_fidelity": "high", "price_per_image_usd": 0.17,
                            "fal_model": "fal-ai/nano-banana-2", "fal_resolution": "1K",
                            "higgsfield_model": "gpt_image_2_5", "higgsfield_resolution": "1k"}
PAID = ("fal", "openai")
DROP_BACKENDS = ("manual", "higgsfield")
MANUAL_EXTS = (".png", ".jpg", ".jpeg", ".webp")
OPENAI_EDITS = "https://api.openai.com/v1/images/edits"
TIMEOUT_S = 300
RUN_FILE = "photo-edit-run.json"

INVARIANTS = {
    "face": r"\bfaces?\b",
    "expression": r"\bexpressions?\b",
    "pose": r"\bpose\b|\bposture\b",
    "hands": r"\bhands?\b",
    "five fingers": r"\bfive fingers\b|\b5 fingers\b|\bfinger count\b",
    "held object": r"\bobject\b|\bproduct\b|\bheld\b|\bholds?\b|\bholding\b",
}
PROMPT_FIELDS = ("edit level", "keep", "transform", "text zone", "avoid")
NO_TEXT_RE = re.compile(r"\bno (text|letters|lettering|words|typography)\b", re.I)
LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]{1,20}):", re.M)


# --------------------------------------------------------------------------
# Consent: shared/scripts/registry.py when present, else the same contract
# read locally from people.json.
# --------------------------------------------------------------------------

def _local_load_people(ctx_dir: Path) -> List[Dict[str, Any]]:
    p = ctx_dir / "people.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("people") or []) if isinstance(data, dict) else []


def _local_allowed(entry: Optional[Dict[str, Any]], scope: str) -> Tuple[bool, str]:
    if not entry:
        return False, "not in people.json (consent unknown)"
    if entry.get("is_operator") is True:
        return True, "operator"
    c = entry.get("consent") or {}
    status = c.get("status", "unknown")
    if status != "granted":
        return False, f"consent {status}"
    if not c.get("date") or not c.get("source"):
        return False, "consent granted without its date or source"
    if scope not in (c.get("scope") or []):
        return False, f"consent granted for {', '.join(c.get('scope') or []) or 'no scope'}, not {scope}"
    return True, f"granted ({c.get('date', 'no date')}, {c.get('source', 'no source')})"


def _as_list(people: Any) -> List[Dict[str, Any]]:
    if isinstance(people, dict) and "people" in people:
        people = people["people"]
    if isinstance(people, dict):
        return [dict(v, slug=v.get("slug", k)) for k, v in people.items() if isinstance(v, dict)]
    return [p for p in people or [] if isinstance(p, dict)]


def load_people(ctx_dir: Optional[Path]) -> Tuple[List[Dict[str, Any]], str]:
    if ctx_dir is None:
        return [], "none"
    if _registry is not None and hasattr(_registry, "load_people"):
        try:
            return _as_list(_registry.load_people(ctx_dir)), "shared"
        except Exception:  # noqa: BLE001
            pass
    return _local_load_people(ctx_dir), "local"


def allowed(entry: Optional[Dict[str, Any]], scope: str) -> Tuple[bool, str]:
    if _registry is not None and hasattr(_registry, "allowed"):
        try:
            ok, reason = _registry.allowed(entry, scope)
            return bool(ok), str(reason)
        except Exception:  # noqa: BLE001
            pass
    return _local_allowed(entry, scope)


def find_context(spec: Dict[str, Any], spec_path: Path, cli: Optional[str]) -> Optional[Path]:
    if cli:
        return Path(cli).resolve()
    if spec.get("project_context"):
        return (spec_path.parent / spec["project_context"]).resolve()
    for up in (spec_path.parent, spec_path.parent.parent, spec_path.parent.parent.parent):
        if (up / "project-context").is_dir():
            return (up / "project-context").resolve()
    return None


def slugs_of(concept: Dict[str, Any]) -> List[str]:
    s = concept.get("person_slug")
    return [s] if isinstance(s, str) else list(s or [])


# --------------------------------------------------------------------------
# Lint
# --------------------------------------------------------------------------

def required_invariants(photo: Dict[str, Any]) -> List[str]:
    req: List[str] = []
    pp = photo.get("people_present", "none")
    if pp in ("face-visible", "group"):
        req += ["face", "expression", "pose"]
    if pp == "partial-body":
        req += ["pose"]
    if pp != "none":
        req += ["hands", "five fingers"]
    if photo.get("held_object"):
        req += ["held object"]
    return req


def prompt_field(prompt: str, name: str) -> str:
    """Text of a labelled field, up to the next label line."""
    m = re.search(rf"^\s*{re.escape(name)}\s*:(.*)$", prompt, re.I | re.M)
    if not m:
        return ""
    rest = prompt[m.end():]
    nxt = LABEL_RE.search(rest)
    return m.group(1) + (rest[:nxt.start()] if nxt else rest)


def lint(spec: Dict[str, Any], spec_path: Path, people: List[Dict[str, Any]], ctx: Optional[Path]) -> List[Issue]:
    issues: List[Issue] = []
    for path, text in adspec._walk_strings(spec, "$"):
        if adspec.DASH_RE.search(text):
            issues.append(Issue("error", "dash", path, "Em or en dash: use a comma, colon, period or parentheses."))
    by_slug = {p.get("slug"): p for p in people}
    photo_ids = set()
    for i, photo in enumerate(spec.get("photos") or []):
        w = f"$.photos[{i}]"
        if photo.get("id") in photo_ids:
            issues.append(Issue("error", "duplicate-id", w, f"photo id '{photo.get('id')}' used twice."))
        photo_ids.add(photo.get("id"))
        src = spec_path.parent / str(photo.get("src", ""))
        if not src.is_file():
            issues.append(Issue("error", "missing-photo", f"{w}.src", f"{photo.get('src')} not found next to the spec."))
        pp = photo.get("people_present", "none")
        if pp != "none" and not (photo.get("people") or "").strip():
            issues.append(Issue("error", "people-undescribed", f"{w}.people",
                                "Describe what the people do, wear and where they sit: the prompt repeats it so the model does not redraw them."))
        concepts = photo.get("concepts") or []
        if len({c.get("edit_level") for c in concepts}) < 2 and len(concepts) >= 3:
            issues.append(Issue("error", "edit-levels", f"{w}.concepts", "Spread the concepts over at least two edit levels (30, 50, 80)."))
        req = required_invariants(photo)
        ids = set()
        for j, c in enumerate(concepts):
            cw = f"{w}.concepts[{j}]"
            if c.get("id") in ids:
                issues.append(Issue("error", "duplicate-id", cw, f"concept id '{c.get('id')}' used twice in this photo."))
            ids.add(c.get("id"))
            never = " ".join(c.get("never_changes") or [])
            miss = [k for k in req if not re.search(INVARIANTS[k], never, re.I)]
            if miss:
                issues.append(Issue("error", "invariant-missing", f"{cw}.never_changes", f"never_changes must name: {', '.join(miss)}."))
            prompt = c.get("prompt") or ""
            fields = list(PROMPT_FIELDS) + (["people"] if pp != "none" else [])
            absent = [f for f in fields if not re.search(rf"^\s*{f}\s*:", prompt, re.I | re.M)]
            if absent:
                issues.append(Issue("error", "prompt-field", f"{cw}.prompt", f"Labelled field(s) missing: {', '.join(absent)}."))
            lvl = re.search(r"^\s*edit level\s*:\s*(\d+)\s*%", prompt, re.I | re.M)
            if lvl and int(lvl.group(1)) != c.get("edit_level"):
                issues.append(Issue("error", "prompt-level", f"{cw}.prompt", f"The prompt says {lvl.group(1)}%, edit_level is {c.get('edit_level')}."))
            keep = prompt_field(prompt, "keep")
            kmiss = [k for k in req if not re.search(INVARIANTS[k], keep, re.I)]
            if keep and kmiss:
                issues.append(Issue("error", "prompt-invariant", f"{cw}.prompt", f"The keep: line must name: {', '.join(kmiss)}."))
            if not NO_TEXT_RE.search(prompt):
                issues.append(Issue("error", "prompt-text", f"{cw}.prompt",
                                    "Say 'no text, no letters': the ad copy is set by the HTML renderer, never painted by the model."))
            slugs = slugs_of(c)
            if pp == "none":
                if slugs:
                    issues.append(Issue("warning", "person-slug-unused", f"{cw}.person_slug", "people_present is none: person_slug is ignored."))
                continue
            if not slugs:
                issues.append(Issue("error", "consent", f"{cw}.person_slug",
                                    "BLOCK: the photo shows a person; reference their people.json slug (person_slug)."))
                continue
            if ctx is None or not (ctx / "people.json").exists():
                issues.append(Issue("error", "consent", f"{cw}.person_slug",
                                    "BLOCK: no project-context/people.json found, consent unknown."))
                continue
            for s in slugs:
                ok, reason = allowed(by_slug.get(s), SCOPE)
                if not ok:
                    issues.append(Issue("error", "consent", f"{cw}.person_slug", f"BLOCK: '{s}' not cleared for {SCOPE}: {reason}."))
    return issues


def load(spec_path: Path, ctx_cli: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], List[Issue], Dict[str, Any]]:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return None, [Issue("error", "json", str(spec_path), f"photo-edits.json does not parse: {e}")], {}
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    issues = [Issue("error", "schema", *m.split(": ", 1)) if ": " in m else Issue("error", "schema", "$", m)
              for m in adspec.SchemaValidator(schema).validate(spec)]
    if not isinstance(spec, dict) or not isinstance(spec.get("photos"), list):
        return None, issues, {}
    ctx = find_context(spec, spec_path, ctx_cli)
    people, source = load_people(ctx)
    issues += lint(spec, spec_path, people, ctx)
    return spec, issues, {"context": str(ctx) if ctx else None, "registry": source}


# --------------------------------------------------------------------------
# Selection, config
# --------------------------------------------------------------------------

def select(spec: Dict[str, Any], sel: str) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    pairs = [(p, c) for p in spec.get("photos") or [] for c in p.get("concepts") or []]
    if sel.strip() == "all":
        return pairs
    want = [s.strip() for s in sel.split(",") if s.strip()]
    out = []
    for w in want:
        hits = [(p, c) for p, c in pairs if w in (c.get("id"), f"{p.get('id')}/{c.get('id')}")]
        if not hits:
            raise ValueError(f"'{w}' matches no concept")
        if len(hits) > 1:
            raise ValueError(f"'{w}' matches several photos: use <photo-id>/<concept-id>")
        out.append(hits[0])
    return out


def load_config(path: Optional[str]) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg.update({k: v for k, v in (data.get("photo_edit") or {}).items() if k in DEFAULTS and v is not None})
    return cfg


def size_of(concept: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[int, int]:
    w, h = (concept.get("size") or cfg["size"]).split("x")
    return int(w), int(h)


def model_of(backend: str, cfg: Dict[str, Any]) -> Optional[str]:
    return {"openai": cfg["model"], "fal": cfg["fal_model"], "higgsfield": cfg["higgsfield_model"]}.get(backend)


def ratio_of(size: Tuple[int, int]) -> str:
    w, h = size
    return "1:1" if w == h else ("3:2" if w > h else "2:3")


def estimate(pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]], cfg: Dict[str, Any], backend: str) -> Dict[str, Any]:
    sizes = sorted({"x".join(map(str, size_of(c, cfg))) for _, c in pairs})
    if backend == "openai":
        per = float(cfg["price_per_image_usd"])
        note = ("estimate: configured price per output image, input image tokens not included; check OpenAI's "
                "pricing page. The photo goes to OpenAI's API, no public link.")
    elif backend == "fal":
        try:
            per = render_ads.per_image_price(str(cfg["fal_model"]), str(cfg["fal_resolution"]), str(cfg["quality"]))
        except (KeyError, ValueError):
            per = float(cfg["price_per_image_usd"])
        note = ("estimate from render_ads.py's fal pricing table; check fal's pricing page. The photo is uploaded "
                "to fal storage under a public URL first.")
    elif backend == "higgsfield":
        per = 0.0
        note = ("0 USD from this script: the agent runs the plan through the Higgsfield MCP, billed in Higgsfield "
                "credits; generate_image with get_cost true gives the figure to show before the real call")
    else:
        per = 0.0
        note = ("0 USD, local transformation" if backend == "stub" else
                "0 USD from this script: the pack is run in the founder's tool or the harness's image tool, at its own cost")
    return {"backend": backend, "model": model_of(backend, cfg), "sizes": sizes,
            "quality": cfg["quality"] if backend in PAID else None, "count": len(pairs),
            "per_image_usd": per, "total_usd": round(per * len(pairs), 4), "note": note}


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

def stub_edit(src: Path, concept: Dict[str, Any], size: Tuple[int, int], dest: Path) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    w, h = size
    im = Image.open(src).convert("RGB")
    base = ImageOps.autocontrast(ImageOps.fit(im, (w, h), method=Image.LANCZOS), cutoff=1)
    digest = hashlib.sha256(str(concept.get("id")).encode("utf-8")).digest()
    backdrop = Image.new("RGB", (w, h), (digest[0], digest[1], digest[2]))
    outside = Image.blend(base, backdrop, float(concept.get("edit_level", 50)) / 100.0)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((int(w * 0.22), int(h * 0.12), int(w * 0.78), int(h * 0.95)), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(4, w // 60)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.composite(base, outside, mask).save(dest, format="PNG")


def openai_edit(key: str, cfg: Dict[str, Any], prompt: str, src: Path, size: Tuple[int, int], dest: Path) -> None:
    fields = {"model": str(cfg["model"]), "prompt": prompt, "n": "1", "size": f"{size[0]}x{size[1]}",
              "quality": str(cfg["quality"])}
    if cfg.get("input_fidelity"):
        fields["input_fidelity"] = str(cfg["input_fidelity"])
    body, ctype = render_ads._multipart(fields, [("image[]", src)])
    req = urllib.request.Request(OPENAI_EDITS, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    data = result.get("data") or []
    if not data or not data[0].get("b64_json"):
        raise RuntimeError(f"no image in the OpenAI result: keys={list(result.keys())}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(data[0]["b64_json"]))


def fal_edit(fal: str, key: str, cfg: Dict[str, Any], prompt: str, src: Path, size: Tuple[int, int], dest: Path) -> None:
    from PIL import Image, ImageOps
    url = render_ads.fal_upload(src, key)
    result_url = render_ads._render_one(fal, str(cfg["fal_model"]), prompt, ratio_of(size), str(cfg["fal_resolution"]),
                                        str(cfg["quality"]), [url], TIMEOUT_S)
    raw = dest.with_suffix(".download")
    render_ads._download(result_url, raw)
    with Image.open(raw) as im:
        fitted = ImageOps.fit(im.convert("RGB"), size, method=Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(dest, format="PNG")
    raw.unlink()


def find_dropped(out: Path, stem: str) -> Optional[Path]:
    for ext in MANUAL_EXTS:
        for cand in (out / f"{stem}{ext}", out / f"{stem}{ext.upper()}"):
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
    return None


def collect_dropped(found: Path, size: Tuple[int, int], dest: Path) -> None:
    from PIL import Image, ImageOps
    with Image.open(found) as im:
        fitted = ImageOps.fit(im.convert("RGB"), size, method=Image.LANCZOS)
    if found.resolve() != dest.resolve():
        keep = found.with_name(found.stem + ".dropped" + found.suffix)
        found.rename(keep)
    fitted.save(dest, format="PNG")


def write_manual_pack(spec_path: Path, out: Path, todo: List[Tuple[Dict[str, Any], Dict[str, Any], Tuple[int, int]]]) -> Path:
    pack = out / "_manual"
    pack.mkdir(parents=True, exist_ok=True)
    lines = ["# Photo edit pack", "",
             "This script sent nothing. Run each edit in an image edit tool: your own app, or the agent's",
             "image tool if its harness has one (an MCP server or a built-in tool). Attach the source photo,",
             "paste the prompt, ask for the size below, and save the result in this folder's parent with the",
             "exact filename (png, jpg, jpeg or webp). Then run the same render command again: dropped files",
             "are fitted to the size and recorded, and the visual review runs on them like on any edit.", "",
             "The model never draws text: the ad copy is set over the photo later, in HTML.", ""]
    for photo, concept, size in todo:
        stem = f"{photo['id']}--{concept['id']}"
        (pack / f"{stem}.prompt.txt").write_text(concept["prompt"].rstrip() + "\n", encoding="utf-8")
        lines += [f"## {photo['id']} / {concept['id']} ({concept.get('edit_level')} %)", "",
                  f"- Source photo: `{os.path.relpath(spec_path.parent / photo['src'], out)}`",
                  f"- Size: {size[0]}x{size[1]}",
                  f"- Save as: `{stem}.png`",
                  f"- Prompt: `_manual/{stem}.prompt.txt`", ""]
    readme = pack / "PHOTO-EDIT-PACK.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme


def write_higgsfield_plan(spec_path: Path, out: Path, cfg: Dict[str, Any],
                          todo: List[Tuple[Dict[str, Any], Dict[str, Any], Tuple[int, int]]]) -> Path:
    calls = []
    for photo, concept, size in todo:
        stem = f"{photo['id']}--{concept['id']}"
        src = spec_path.parent / photo["src"]
        params = {"model": cfg["higgsfield_model"], "prompt": concept["prompt"].rstrip(), "aspect_ratio": ratio_of(size),
                  "quality": cfg["quality"], "resolution": cfg["higgsfield_resolution"], "count": 1,
                  "medias": [{"role": "image_references", "value": "<media_id of the source photo>"}]}
        calls.append({"concept": f"{photo['id']}/{concept['id']}", "source_photo": os.path.relpath(src, out),
                      "upload": {"tool": "media_upload", "filename": src.name, "then": "curl PUT to upload_url, media_confirm type image"},
                      "cost": {"tool": "generate_image", "params": {**params, "get_cost": True}},
                      "render": {"tool": "generate_image", "params": params},
                      "save_as": f"{stem}.png", "size": f"{size[0]}x{size[1]}"})
    plan = {"backend": "higgsfield", "order": ["upload every source photo once", "cost of every concept, total shown to "
            "the founder", "after an explicit yes: render, wait for the job, download the result URL to save_as",
            "run the same photo_edit.py render command again to collect"], "calls": calls}
    path = out / "_manual" / "higgsfield-plan.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def report_issues(issues: List[Issue], meta: Dict[str, Any]) -> int:
    n = adspec.counts(issues)
    print(json.dumps({"status": "pass" if not n["errors"] else "fail", **n, **meta,
                      "issues": [i.to_dict() for i in issues]}, indent=2, ensure_ascii=False))
    for i in issues:
        print(f"{i.level.upper()} {i.code} {i.where}: {i.message}", file=sys.stderr)
    return 0 if not n["errors"] else 1


def cmd_check(a: argparse.Namespace) -> int:
    spec, issues, meta = load(Path(a.spec), a.context)
    if spec is None:
        report_issues(issues, meta)
        return 3
    return report_issues(issues, meta)


def _prepare(a: argparse.Namespace):
    spec_path = Path(a.spec).resolve()
    spec, issues, meta = load(spec_path, getattr(a, "context", None))
    if spec is None:
        report_issues(issues, meta)
        return None, 3
    if adspec.counts(issues)["errors"]:
        report_issues(issues, meta)
        print("photo_edit: fix the spec errors (consent BLOCKs included) before any render.", file=sys.stderr)
        return None, 1
    if not a.select:
        print("photo_edit: --select is required (Gate 1: the founder picks the concepts).", file=sys.stderr)
        return None, 3
    try:
        pairs = select(spec, a.select)
        cfg = load_config(a.config)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"photo_edit: {e}", file=sys.stderr)
        return None, 3
    return (spec_path, spec, pairs, cfg), 0


def cmd_estimate(a: argparse.Namespace) -> int:
    prep, rc = _prepare(a)
    if prep is None:
        return rc
    _, _, pairs, cfg = prep
    est = estimate(pairs, cfg, a.backend)
    print(json.dumps(est, indent=2))
    print(f"photo_edit: {est['count']} image(s) on {est['model'] or a.backend} {', '.join(est['sizes'])} "
          f"= about ${est['total_usd']:.2f} (${est['per_image_usd']:.2f}/image, {est['note']})", file=sys.stderr)
    return 0


def media_entry(spec_path: Path, photo: Dict[str, Any], concept: Dict[str, Any], dest: Path) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"role": "photo", "src": os.path.relpath(dest, spec_path.parent), "alt": photo.get("subject", ""),
                             "fit": "contain", "visible_text": list(photo.get("visible_text") or []),
                             "edit": {"spec": spec_path.name, "photo": photo["id"], "concept": concept["id"]}}
    if photo.get("people_present", "none") != "none":
        entry["edit"]["person_slugs"] = slugs_of(concept)
    return entry


def cmd_render(a: argparse.Namespace) -> int:
    prep, rc = _prepare(a)
    if prep is None:
        return rc
    spec_path, spec, pairs, cfg = prep
    est = estimate(pairs, cfg, a.backend)
    key = None
    fal = None
    if a.backend == "fal" and cfg["fal_model"] not in render_ads.NANO_MODELS:
        print(f"photo_edit: fal_model must be one of {', '.join(render_ads.NANO_MODELS)}; for gpt-image-2 use "
              "--backend openai.", file=sys.stderr)
        return 3
    if a.backend == "fal":
        with_people = sorted({p["id"] for p, _ in pairs if p.get("people_present", "none") != "none"})
        if with_people and not a.accept_public_url:
            print(json.dumps({"public_url_gate": "closed", "photos_with_people": with_people, **est}, indent=2))
            print(f"photo_edit: fal uploads the photo under a public URL and {', '.join(with_people)} show people; "
                  "nothing was sent. Use --backend openai (no public link) or manual, or re-run with "
                  "--accept-public-url after the founder and every person shown agree.", file=sys.stderr)
            return 4
    if a.backend in PAID:
        if not render_ads.spend_confirmed(a.confirm_spend):
            print(json.dumps({"spend_gate": "closed", **est}, indent=2))
            print(f"photo_edit: spend gate closed, nothing was sent. {est['count']} image(s) on {est['model']} "
                  f"= about ${est['total_usd']:.2f} (${est['per_image_usd']:.2f}/image, estimate). Show this at Gate 2; "
                  "after the founder's explicit yes on model, size, count and total, re-run with --confirm-spend "
                  "(or FOG_ALLOW_SPEND=1). No spend: --backend manual (nothing sent, 0 USD).",
                  file=sys.stderr)
            return 4
        if a.backend == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                print("photo_edit: OPENAI_API_KEY not set; nothing was sent. --backend manual needs no key.", file=sys.stderr)
                return 2
        else:
            key = render_ads._key()
            fal = render_ads._fal_bin()
            if not key or not fal:
                print("photo_edit: fal needs FAL_KEY (or FAL_API_KEY) and the fal CLI; nothing was sent. "
                      "--backend manual needs neither.", file=sys.stderr)
                return 2
    out = Path(a.out).resolve() if a.out else spec_path.parent / "media" / "edited"
    run_path = out / RUN_FILE
    old = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {"records": []}
    records = {(r["photo"], r["concept"]): r for r in old.get("records") or []}
    spent = 0.0
    todo: List[Tuple[Dict[str, Any], Dict[str, Any], Tuple[int, int]]] = []
    for photo, concept in pairs:
        size = size_of(concept, cfg)
        dest = out / f"{photo['id']}--{concept['id']}.png"
        rec: Dict[str, Any] = {"photo": photo["id"], "concept": concept["id"], "edit_level": concept["edit_level"],
                               "backend": a.backend, "model": model_of(a.backend, cfg),
                               "size": f"{size[0]}x{size[1]}", "file": dest.name, "source": photo["src"],
                               "est_usd": est["per_image_usd"]}
        try:
            if a.backend == "stub":
                stub_edit(spec_path.parent / photo["src"], concept, size, dest)
            elif a.backend in DROP_BACKENDS:
                found = find_dropped(out, dest.stem)
                if not found:
                    rec.update(status="AWAITING_FILE")
                    records[(photo["id"], concept["id"])] = rec
                    todo.append((photo, concept, size))
                    continue
                collect_dropped(found, size, dest)
            else:
                print(f"photo_edit: {photo['id']}/{concept['id']} on {est['model']} {rec['size']} {cfg['quality']}, "
                      f"about ${est['per_image_usd']:.2f}", file=sys.stderr)
                src = spec_path.parent / photo["src"]
                if a.backend == "openai":
                    openai_edit(key, cfg, concept["prompt"], src, size, dest)  # type: ignore[arg-type]
                else:
                    fal_edit(fal, key, cfg, concept["prompt"], src, size, dest)  # type: ignore[arg-type]
                spent += est["per_image_usd"]
            rec.update(status="OK", media_entry=media_entry(spec_path, photo, concept, dest))
        except (OSError, RuntimeError, KeyError, subprocess.SubprocessError, urllib.error.URLError, ValueError,
                json.JSONDecodeError) as e:
            rec.update(status="FAILED", error=str(e)[:300])
        records[(photo["id"], concept["id"])] = rec
    out.mkdir(parents=True, exist_ok=True)
    run = {"spec": str(os.path.relpath(spec_path, out)), "records": list(records.values()),
           "estimate": est, "actual_spend_usd_estimate": round(spent, 4)}
    run_path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [r for r in records.values() if r.get("status") == "FAILED"]
    summary: Dict[str, Any] = {"rendered": sum(1 for r in run["records"] if r["status"] == "OK"), "failed": len(failed),
                               "out": str(out), "spend_usd_estimate": run["actual_spend_usd_estimate"]}
    if todo:
        summary.update(awaiting_file=len(todo), pack=str(write_manual_pack(spec_path, out, todo)))
        if a.backend == "higgsfield":
            summary["higgsfield_plan"] = str(write_higgsfield_plan(spec_path, out, cfg, todo))
    print(json.dumps(summary, indent=2))
    if failed:
        return 1
    if todo:
        print(f"photo_edit: {len(todo)} edit(s) to run outside this script, pack {summary['pack']}. "
              "Drop the files, then run the same command again.", file=sys.stderr)
        return 5
    return 0


VERDICTS = ("IDENTITY_OK", "IDENTITY_CHANGED", "TEXT_ADDED", "NOT_REVIEWED")
REVIEW_KEYS = ("face", "expression", "pose", "hands", "fingers", "object")


def review_verdict(entry: Optional[Dict[str, Any]], photo: Dict[str, Any]) -> Tuple[str, str]:
    if not entry:
        return "NOT_REVIEWED", "no review entry"
    if entry.get("text_added"):
        return "TEXT_ADDED", "the model painted text or letters: the copy belongs to the HTML"
    changed = [k for k in REVIEW_KEYS if entry.get(k) in ("changed", "wrong")]
    if photo.get("people_present") in ("face-visible", "group") and entry.get("face") == "not_in_photo":
        changed.append("face lost")
    if photo.get("held_object") and entry.get("object") == "not_in_photo":
        changed.append("object lost")
    missing = [k for k in REVIEW_KEYS if k not in entry]
    if missing:
        return "NOT_REVIEWED", f"fields not answered: {', '.join(missing)}"
    if changed:
        return "IDENTITY_CHANGED", f"changed: {', '.join(changed)}"
    return "IDENTITY_OK", ""


def write_packet(spec_path: Path, spec: Dict[str, Any], records: List[Dict[str, Any]], out: Path) -> Path:
    review = spec_path.parent / "review"
    review.mkdir(parents=True, exist_ok=True)
    photos = {p["id"]: p for p in spec.get("photos") or []}
    lines = ["# Photo edit review", "",
             "Open each pair at full size: the original photo, then the edited one. Answer for every edited file, "
             "comparing it with the original only (not with any ad copy).", "",
             "- `face`, `expression`, `pose`, `hands`, `object`: `same`, `changed` or `not_in_photo`.",
             "- `fingers`: `five` (every visible hand has five fingers), `wrong`, or `not_in_photo`.",
             "- `text_added`: true when the edit painted any letter, word, number or logo that the original did not show.",
             "- `notes`: what changed, in one line. When unsure, answer `changed`: a guess is worse than a flag.", "",
             "| Edited file | Original | Edit level |", "|---|---|---|"]
    tpl = []
    for r in records:
        if r.get("status") != "OK":
            continue
        lines.append(f"| {os.path.relpath(out / r['file'], spec_path.parent)} | {photos.get(r['photo'], {}).get('src', '?')} | {r['edit_level']} % |")
        tpl.append({"file": r["file"], **{k: "" for k in REVIEW_KEYS}, "text_added": False, "notes": ""})
    (review / "photo-edit-packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (review / "photo-edit-review.template.json").write_text(json.dumps(tpl, indent=2) + "\n", encoding="utf-8")
    return review / "photo-edit-packet.md"


def cmd_verify(a: argparse.Namespace) -> int:
    from PIL import Image
    spec_path = Path(a.spec).resolve()
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        out = Path(a.out).resolve() if a.out else spec_path.parent / "media" / "edited"
        run = json.loads((out / RUN_FILE).read_text(encoding="utf-8"))
        reviews = None
        if a.review:
            reviews = {e.get("file"): e for e in json.loads(Path(a.review).read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError) as e:
        print(f"photo_edit: cannot read the spec, the run file or the review ({e})", file=sys.stderr)
        return 3
    photos = {p["id"]: p for p in spec.get("photos") or []}
    results = []
    for r in run.get("records") or []:
        res: Dict[str, Any] = {"file": r["file"], "photo": r["photo"], "concept": r["concept"], "size_asked": r["size"]}
        f = out / r["file"]
        if r.get("status") != "OK" or not f.is_file():
            res.update(check="MISSING", block=True)
        else:
            with Image.open(f) as im:
                got = f"{im.size[0]}x{im.size[1]}"
            res["size_got"] = got
            res.update(check="SIZE_OK" if got == r["size"] else "SIZE_MISMATCH", block=got != r["size"])
        if reviews is not None:
            v, why = review_verdict(reviews.get(r["file"]), photos.get(r["photo"], {}))
            res.update(review=v, review_why=why)
            res["block"] = res["block"] or v != "IDENTITY_OK"
        results.append(res)
    packet = write_packet(spec_path, spec, run.get("records") or [], out)
    blocks = sum(1 for x in results if x["block"])
    status = "pass" if not blocks else "fail"
    if reviews is None and not blocks:
        status = "awaiting_review"
    rep = {"status": status, "renders": len(results), "blocks": blocks, "packet": str(packet), "results": results}
    (out / "photo-edit-verify.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if status == "awaiting_review":
        print(f"photo_edit: sizes OK; visual review pending, packet {packet}. No edited photo is used before IDENTITY_OK.", file=sys.stderr)
    return 1 if blocks else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("spec")
    c.add_argument("--context", help="project-context folder holding people.json")
    for name in ("estimate", "render"):
        p = sub.add_parser(name)
        p.add_argument("spec")
        p.add_argument("--select", default="", help='"all", concept ids, or <photo-id>/<concept-id>, comma separated')
        p.add_argument("--backend", default="manual", choices=["manual", "higgsfield", "fal", "openai", "stub"],
                       help="manual (default, 0 USD, nothing sent), higgsfield, fal, openai; stub is a local placeholder for tests")
        p.add_argument("--config", help="config.json holding a photo_edit object")
        p.add_argument("--context", help="project-context folder holding people.json")
        if name == "render":
            p.add_argument("--out", help="Output folder (default <spec dir>/media/edited)")
            p.add_argument("--confirm-spend", action="store_true",
                           help="The founder confirmed Gate 2 (fal or openai backend). FOG_ALLOW_SPEND=1 does the same.")
            p.add_argument("--accept-public-url", action="store_true",
                           help="fal backend, photo with people: the founder and every person shown accept a public URL.")
    v = sub.add_parser("verify")
    v.add_argument("spec")
    v.add_argument("--out", help="Folder of the edited files (default <spec dir>/media/edited)")
    v.add_argument("--review", help="Reviewer answers (from review/photo-edit-review.template.json)")
    a = ap.parse_args()
    return {"check": cmd_check, "estimate": cmd_estimate, "render": cmd_render, "verify": cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
