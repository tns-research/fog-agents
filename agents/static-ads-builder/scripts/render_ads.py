#!/usr/bin/env python3
"""render_ads.py - Render selected static-ad briefs behind a budget gate.

Role since V2: the paid (or manual) image path for text-free photo plates
only. scripts/plates.py writes the plate briefs from ads.json; every word,
logo, product and screenshot of an ad is set by the local HTML renderer
(scripts/build.py + scripts/render.py), never by an image model.

Capability: image_gen (see shared/tools.md). Three providers, picked with
--provider (the agent passes the one resolved at Step 0):

  manual   (default)  no API, no key, no spend. Writes a render pack (one prompt
                      file per brief plus MANUAL-RENDER.md listing the copy, the
                      reference files to attach and the exact filename to use).
                      The founder generates in the tool they already use
                      (Midjourney, Canva, ChatGPT, Figma, a designer) and drops
                      the files in --out as NN-<anything>.jpg|jpeg|png|webp.
                      Re-running the same command picks the dropped files up
                      and reports them as OK, ready for the text check.
  fal                 shells the `fal` CLI. Needs the `fal` binary on PATH and
                      FAL_KEY (or FAL_API_KEY).
  openai              calls the OpenAI Images API directly over urllib (no SDK).
                      Needs OPENAI_API_KEY. Model: openai/gpt-image-2 only.

Two responsibilities, one script:

  --estimate   Compute the spend for a given model + resolution + count. No API
               call, no key needed. This feeds Gate 2 (the human budget gate):
               the founder sees model, resolution, count, per-image price, and
               total BEFORE anything is rendered. Manual provider: $0.

  --batch      Render a selected subset of briefs from a briefs JSON file. One
               attempt per brief, NO auto-retry. Image-to-image when a brief
               carries resolved local references (`_ref_paths`, e.g. a product
               packshot, the brand logo, a UI screenshot, a hero image), all
               attached together; text-to-image otherwise. Downloads each result
               locally and prints a JSON run summary on stdout.

Spend gate in code: --batch with fal or openai sends nothing without
--confirm-spend (or FOG_ALLOW_SPEND=1 in the environment for scripted runs).
Without it the script prints the Gate 2 estimate for the selection and exits 4.
The agent adds --confirm-spend only after the founder confirmed model,
resolution, count and total at Gate 2. --estimate and --provider manual never
spend and need no confirmation.

Privacy: with fal, every local reference image of a brief (`_ref_paths`:
packshot, logo, UI screenshot, hero) is uploaded to fal storage first and gets
a public URL that anyone holding it can open. Do not attach anything the
founder would not publish.

fal execution model: the script SHELLS the `fal` CLI, which owns the
fal-specific parts (endpoint routing to `/edit`, queue submit, polling, result
extraction). The script keeps only the founder-facing guardrails: the pricing
table, the two gates, the batch loop, reference upload, naming, and the run
report. The script never hand-builds a queue URL.

  nano-banana-2 / nano-banana-pro  ->  the CLI shortcut when the installed
                                       CLI has one, detected from `fal --help`
                                       (current CLI: `generate-banana |
                                       edit-banana` for nano-banana-2; older
                                       CLI: `generate | edit`, and `-old`
                                       variants for pro), references attached
                                       as repeatable `--image <url>`; else
                                       `fal run <endpoint> --input <json>`
                                       (nano-banana-pro on the current CLI).
  openai/gpt-image-2               ->  `fal run <endpoint> --input <json>`,
                                       references attached as `image_urls`.

Local references are uploaded to fal storage first (initiate + PUT), so the model
always receives a short URL. Data URIs are never put on the command line (a large
screenshot would blow the kernel argv limit and the job would fail).

openai execution model: POST /v1/images/generations (text-to-image) or
/v1/images/edits (multipart, references attached as image[] files). The result
comes back base64-encoded and is written straight to disk.

Resolution is the main cost lever. The pricing table below is the single source
of truth for both the estimate and the post-run actual spend. Update it here when
prices change; never hard-code a price anywhere else.

Pricing (USD per generated image), bundled table; check it against the
provider's pricing page before quoting it at Gate 2:

  fal-ai/nano-banana-2     1K 0.08   2K 0.12   4K 0.16     (default)
  fal-ai/nano-banana-pro   1K 0.15   2K 0.15   4K 0.30     (higher-fidelity fallback)
  openai/gpt-image-2  medium  1K 0.05   2K 0.06   4K 0.10
  openai/gpt-image-2  high    1K 0.21   2K 0.22   4K 0.40

The openai/gpt-image-2 rows are fal's resale prices; with --provider openai they
are an estimate of OpenAI's own billing, which the founder can check on their
OpenAI usage page.

Notes on resolution per model:
  - nano-banana-2 / nano-banana-pro take an enum resolution (1K/2K/4K) and an
    aspect ratio; the CLI shortcut (or the `fal run` payload) maps both.
  - gpt-image-2 takes an explicit pixel size and a `quality` tier;
    `--resolution` selects the PRICING row and `quality` maps to medium/high.

Usage:
    # Gate 2 estimate (no key, no render):
    python render_ads.py --estimate --provider fal --count 10 --model fal-ai/nano-banana-2 --resolution 1K

    # Render the selection after the founder confirmed Gate 2 (fal):
    python render_ads.py --batch briefs.json --select "1,2,4,7-10" \\
        --out images/20260604 --provider fal --model fal-ai/nano-banana-2 --resolution 1K \\
        --refs-dir refs --confirm-spend

    # Same selection through OpenAI directly:
    python render_ads.py --batch briefs.json --select "1,2,4,7-10" \\
        --out images/20260604 --provider openai --model openai/gpt-image-2 \\
        --confirm-spend

    # Default, no image API: write the manual render pack, then re-run after dropping files:
    python render_ads.py --batch briefs.json --select "1,2,4,7-10" \\
        --out images/20260604 --refs-dir refs

Exit codes:
    0  ok (estimate printed, or batch finished with at least the report written;
       manual provider: pack written, dropped files collected)
    2  the provider's key is missing (FAL_KEY / FAL_API_KEY for fal,
       OPENAI_API_KEY for openai). Nothing was sent. Switch to another provider
       or to --provider manual.
    3  bad input (unreadable briefs JSON, empty selection, unknown model,
       or the `fal` CLI is not on PATH)
    4  spend gate closed: --batch with fal or openai without --confirm-spend
       or FOG_ALLOW_SPEND=1. Nothing was sent; the estimate is printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# --- Pricing: single source of truth (USD per generated image) ---------------
# Flat models map resolution -> price. gpt-image-2 maps quality -> resolution.
PRICING: dict[str, object] = {
    "fal-ai/nano-banana-2": {"1K": 0.08, "2K": 0.12, "4K": 0.16},
    "fal-ai/nano-banana-pro": {"1K": 0.15, "2K": 0.15, "4K": 0.30},
    "openai/gpt-image-2": {
        "medium": {"1K": 0.05, "2K": 0.06, "4K": 0.10},
        "high": {"1K": 0.21, "2K": 0.22, "4K": 0.40},
    },
}
DEFAULT_MODEL = "fal-ai/nano-banana-2"
RESOLUTIONS = ("1K", "2K", "4K")

# The nano-banana family is driven through the CLI's dedicated shortcuts when the
# installed CLI has them. Each maps to a text-to-image command and an
# image-to-image (edit) command. The CLI renamed its shortcuts between releases,
# so the layout is detected from `fal --help` at run time (see _nano_shortcuts):
#   current CLI: `generate` / `edit` serve openai/gpt-image-2, nano-banana-2 is
#                `generate-banana` / `edit-banana`, nano-banana-pro has no
#                shortcut (it goes through `fal run`).
#   older CLI:   `generate` / `edit` serve nano-banana-2, `generate-old` /
#                `edit-old` serve nano-banana-pro.
# A model with no usable shortcut runs through `fal run <endpoint> --input`,
# which names the endpoint explicitly and works on every CLI version. Never call
# a bare `generate` without detection: on the current CLI it bills gpt-image-2.
NANO_MODELS = ("fal-ai/nano-banana-2", "fal-ai/nano-banana-pro")
FAL_SHORTCUT_LAYOUTS: dict[str, dict[str, dict[str, str]]] = {
    "current": {
        "fal-ai/nano-banana-2": {"gen": "generate-banana", "edit": "edit-banana"},
    },
    "legacy": {
        "fal-ai/nano-banana-2": {"gen": "generate", "edit": "edit"},
        "fal-ai/nano-banana-pro": {"gen": "generate-old", "edit": "edit-old"},
    },
}
FAL_HELP_TIMEOUT_S = 20  # `fal --help` is local, no network call
_FAL_COMMANDS_CACHE: dict[str, set[str]] = {}

# gpt-image-2 is driven through `fal run <endpoint> --input`. It takes an
# image_size object (width/height) rather than an enum resolution.
# Supported aspect ratios: 4:5 and 1:1 for the feed, 9:16 for Stories and Reels.
RATIOS = ("4:5", "1:1", "9:16")

# gpt-image-2 takes free pixel sizes as long as both sides are multiples of 16;
# 1008x1792 is exactly 9:16.
GPT_IMAGE_SIZE = {"4:5": {"width": 1024, "height": 1280},
                  "1:1": {"width": 1024, "height": 1024},
                  "9:16": {"width": 1008, "height": 1792}}

PROVIDERS = ("fal", "openai", "manual")
OPENAI_MODEL_ID = "openai/gpt-image-2"  # the only model the openai provider serves
OPENAI_API_BASE = "https://api.openai.com/v1/images"
# OpenAI pixel sizes per ratio. gpt-image-2 accepts 1024x1280 for 4:5 and
# 1008x1792 for 9:16; older gpt-image-1 only has fixed sizes, so both portrait
# ratios fall back to its closest portrait size (crop to the exact ratio after).
OPENAI_SIZE = {"gpt-image-2": {"4:5": "1024x1280", "1:1": "1024x1024", "9:16": "1008x1792"},
               "gpt-image-1": {"4:5": "1024x1536", "1:1": "1024x1024", "9:16": "1024x1536"}}
# Files the founder may drop back in manual mode.
MANUAL_EXTS = (".jpg", ".jpeg", ".png", ".webp")

FAL_STORAGE_INITIATE = "https://rest.alpha.fal.ai/storage/upload/initiate"
PER_BRIEF_TIMEOUT_S = 300  # the CLI blocks on --queue until the job completes
UPLOAD_TIMEOUT_S = 120


# --- Pricing helpers ---------------------------------------------------------
def per_image_price(model: str, resolution: str, quality: str) -> float:
    if model not in PRICING:
        raise KeyError(f"unknown model: {model}")
    table = PRICING[model]
    if model == "openai/gpt-image-2":
        return float(table[quality][resolution])  # type: ignore[index]
    return float(table[resolution])  # type: ignore[index]


def spend_confirmed(flag: bool) -> bool:
    """True when the founder's Gate 2 agreement was passed on: --confirm-spend or FOG_ALLOW_SPEND=1."""
    return bool(flag) or os.environ.get("FOG_ALLOW_SPEND", "").strip() == "1"


# --- fal access: key, CLI binary, storage upload -----------------------------
def _key() -> str | None:
    return os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")


def _fal_bin() -> str | None:
    return shutil.which("fal")


def _fal_commands(fal: str) -> set[str]:
    """Command names listed under "Available Commands:" in `fal --help`.

    Local and free (no request reaches fal). Returns an empty set when the help
    cannot be read, which makes every nano model fall back to `fal run`.
    """
    if fal in _FAL_COMMANDS_CACHE:
        return _FAL_COMMANDS_CACHE[fal]
    cmds: set[str] = set()
    try:
        proc = subprocess.run([fal, "--help"], capture_output=True, text=True,
                              timeout=FAL_HELP_TIMEOUT_S)
        in_block = False
        for line in (proc.stdout or "").splitlines():
            if line.strip().lower().startswith("available commands"):
                in_block = True
                continue
            if in_block:
                if not line.strip():
                    if cmds:
                        break
                    continue
                if not line.startswith((" ", "\t")):
                    break
                cmds.add(line.split()[0])
    except (OSError, subprocess.SubprocessError):
        cmds = set()
    _FAL_COMMANDS_CACHE[fal] = cmds
    return cmds


def _nano_shortcuts(fal: str) -> dict[str, dict[str, str]]:
    """Shortcut commands per nano model for the installed CLI.

    A model is listed only when both of its commands exist in `fal --help`;
    any other nano model runs through `fal run <endpoint>`.
    """
    cmds = _fal_commands(fal)
    layout = "current" if "generate-banana" in cmds else (
        "legacy" if "generate-old" in cmds else "")
    table = FAL_SHORTCUT_LAYOUTS.get(layout, {})
    return {m: sc for m, sc in table.items() if sc["gen"] in cmds and sc["edit"] in cmds}


def fal_upload(path: Path, key: str, timeout: int = UPLOAD_TIMEOUT_S) -> str:
    """Upload one local file to fal storage and return its public URL.

    Privacy: the returned URL is public, anyone holding it can download the file.
    Two short calls, no polling: POST initiate to get a signed upload URL plus
    the final file URL, then PUT the bytes. The model receives the file URL.
    """
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    body = json.dumps({"file_name": path.name, "content_type": mime}).encode("utf-8")
    init_req = urllib.request.Request(
        FAL_STORAGE_INITIATE, data=body, method="POST",
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    with urllib.request.urlopen(init_req, timeout=timeout) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
    upload_url = meta.get("upload_url")
    file_url = meta.get("file_url")
    if not upload_url or not file_url:
        raise RuntimeError(f"fal upload initiate returned no urls: {list(meta.keys())}")
    put_req = urllib.request.Request(
        upload_url, data=path.read_bytes(), method="PUT",
        headers={"Content-Type": mime})
    with urllib.request.urlopen(put_req, timeout=timeout) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"fal upload PUT failed: HTTP {resp.status}")
    return file_url


def _download(url: str, dest: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(url, headers={"Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.read())
    if dest.stat().st_size == 0:
        raise RuntimeError(f"downloaded file is empty: {dest}")


# --- fal CLI execution -------------------------------------------------------
def _parse_cli_json(stdout: str) -> dict:
    """Parse the result JSON the CLI prints to stdout under --json.

    `fal ... --queue --json` blocks until completion and prints the full result
    object. Fall back to the last JSON object in stdout if anything precedes it.
    """
    s = stdout.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = s.rfind("{")
        if start != -1:
            return json.loads(s[start:])
        raise


def _run_cli(cmd: list[str], timeout: int) -> dict:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"fal CLI exit {proc.returncode}: {detail[:300]}")
    return _parse_cli_json(proc.stdout)


def _extract_image_url(result: dict) -> str:
    images = result.get("images") or []
    if images and isinstance(images, list):
        first = images[0]
        if isinstance(first, dict) and first.get("url"):
            return first["url"]
    img = result.get("image")
    if isinstance(img, dict) and img.get("url"):
        return img["url"]
    raise RuntimeError(f"no image url in fal result: keys={list(result.keys())}")


def _render_one(fal: str, model: str, prompt: str, ratio: str, resolution: str,
                quality: str, ref_urls: list[str], timeout: int) -> str:
    """Render a single image through the fal CLI; return the result image URL.

    nano-banana uses the shortcut commands the installed CLI offers (detected
    from `fal --help`), else `fal run <endpoint>`; gpt-image-2 uses `fal run`
    with a JSON payload. Either way the CLI does the submit, the polling, and the
    result extraction, so the script never touches a queue URL.
    """
    # The CLI's queue poll builds a wrong status URL for any `/edit` endpoint and
    # returns HTTP 405, so image-to-image (refs present) must run sync. Plain
    # text-to-image uses `--queue` to avoid a long-held sync connection.
    queue = not ref_urls
    shortcuts = _nano_shortcuts(fal) if model in NANO_MODELS else {}
    if model in shortcuts:
        sc = shortcuts[model]
        if ref_urls:
            cmd = [fal, sc["edit"], prompt]
            for u in ref_urls:
                cmd += ["--image", u]
        else:
            cmd = [fal, sc["gen"], prompt]
        cmd += ["--aspect", ratio, "--resolution", resolution,
                "--format", "jpeg", "--json"]
        if queue:
            cmd.append("--queue")
        result = _run_cli(cmd, timeout)
    elif model in NANO_MODELS:
        # No shortcut for this model in the installed CLI: name the endpoint.
        payload_nano: dict = {
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": ratio,
            "resolution": resolution,
            "output_format": "jpeg",
        }
        endpoint = model
        if ref_urls:
            payload_nano["image_urls"] = ref_urls
            endpoint = f"{model}/edit"
        cmd = [fal, "run", endpoint, "--input", json.dumps(payload_nano), "--json"]
        if queue:
            cmd.append("--queue")
        result = _run_cli(cmd, timeout)
    elif model == "openai/gpt-image-2":
        payload: dict = {
            "prompt": prompt,
            "num_images": 1,
            "output_format": "jpeg",
            "image_size": GPT_IMAGE_SIZE[ratio],
            "quality": quality,
        }
        endpoint = model
        if ref_urls:
            payload["image_urls"] = ref_urls
            endpoint = f"{model}/edit"
        cmd = [fal, "run", endpoint, "--input", json.dumps(payload), "--json"]
        if queue:
            cmd.append("--queue")
        result = _run_cli(cmd, timeout)
    else:
        raise KeyError(f"unknown model: {model}")
    return _extract_image_url(result)


# --- OpenAI Images API (direct, --provider openai) ---------------------------
def _openai_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def _multipart(fields: dict[str, str], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    """Encode form fields and files as multipart/form-data (stdlib only)."""
    boundary = "----render-ads-" + os.urandom(8).hex()
    out = bytearray()
    for name, value in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n").encode("utf-8")
    for name, path in files:
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
                f"filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n").encode("utf-8")
        out += path.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _render_openai(key: str, openai_model: str, prompt: str, ratio: str,
                   quality: str, ref_paths: list[Path], dest: Path,
                   timeout: int) -> None:
    """Render one image with the OpenAI Images API and write it to dest."""
    sizes = OPENAI_SIZE.get(openai_model, OPENAI_SIZE["gpt-image-2"])
    size = sizes[ratio]
    fields = {"model": openai_model, "prompt": prompt, "n": "1", "size": size,
              "quality": quality, "output_format": "jpeg"}
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    if ref_paths:
        body, ctype = _multipart(fields, [("image[]", p) for p in ref_paths])
        url = f"{OPENAI_API_BASE}/edits"
    else:
        payload = dict(fields, n=1)
        body, ctype = json.dumps(payload).encode("utf-8"), "application/json"
        url = f"{OPENAI_API_BASE}/generations"
    headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from None
    data = result.get("data") or []
    if not data or not isinstance(data[0], dict):
        raise RuntimeError(f"no image in OpenAI result: keys={list(result.keys())}")
    first = data[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if first.get("b64_json"):
        dest.write_bytes(base64.b64decode(first["b64_json"]))
    elif first.get("url"):
        _download(first["url"], dest)
    else:
        raise RuntimeError("OpenAI result holds neither b64_json nor url")
    if dest.stat().st_size == 0:
        raise RuntimeError(f"written file is empty: {dest}")


# --- Manual provider (no API: render pack + founder drop-back) ---------------
def _find_dropped(out_dir: Path, n: int) -> Path | None:
    """Return a founder-dropped file for brief n (NN-<anything>.<image ext>)."""
    if not out_dir.is_dir():
        return None
    prefix = f"{n:02d}-"
    for p in sorted(out_dir.iterdir()):
        if (p.is_file() and p.name.startswith(prefix)
                and p.suffix.lower() in MANUAL_EXTS and p.stat().st_size > 0):
            return p
    return None


def _write_manual_pack(out_dir: Path, entries: list[dict], ratio: str) -> Path:
    """Write one prompt file per brief and MANUAL-RENDER.md into out_dir/_manual/."""
    pack = out_dir / "_manual"
    pack.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Manual render pack",
        "",
        "No image API was used for this run. Generate each ad in the tool you",
        "already use (Midjourney, Canva, ChatGPT, Figma, a designer), then drop",
        f"the files in `{out_dir}` with the exact filename below (any of",
        "jpg, jpeg, png, webp; only the `NN-` prefix is required).",
        "Re-run the same render_ads.py command: dropped files are picked up and",
        "the proofread (proofread-ads) runs on them like on any render.",
        "",
        f"Aspect ratio for every ad: {ratio}.",
        "",
        "If your tool renders text poorly, generate the visual without text and",
        "set the headline and subheadline yourself in Canva or Figma, character",
        "for character (accents included).",
        "",
    ]
    for e in entries:
        prompt_file = pack / f"{e['n']:02d}-{e['slug']}.prompt.txt"
        prompt_file.write_text(e["prompt"] + "\n", encoding="utf-8")
        lines += [f"## Brief {e['n']}: {e['concept'] or e['slug']}", "",
                  f"- Save as: `{e['filename']}`",
                  f"- Status: {e['status']}",
                  f"- Headline (render exactly): {e['headline'] or '(none)'}",
                  f"- Subheadline (render exactly): {e['subheadline'] or '(none)'}",
                  f"- Attach as references: "
                  f"{', '.join(e['refs']) if e['refs'] else '(none, text-to-image)'}",
                  f"- Prompt: `_manual/{prompt_file.name}`", ""]
    readme = pack / "MANUAL-RENDER.md"
    readme.write_text("\n".join(lines), encoding="utf-8")
    return readme


# --- Prompt composition ------------------------------------------------------
def _compose_prompt(brief: dict, ratio: str = "4:5") -> str:
    """Combine the scene prompt with on-image text rendering instructions.

    The scene prompt may itself ask for on-image text (benefit lines, column
    headers, labels, a CTA button, as the graphic visual styles do). Those lines
    are allowed; only text that neither the scene prompt nor the headline and
    subheadline ask for is forbidden.
    """
    prompt = (brief.get("image_prompt") or "").strip()
    if ratio == "9:16":
        prompt += ("\n\nVertical 9:16 Stories and Reels format: keep every line of text, "
                   "the logo and any CTA away from the top and bottom edges, where the "
                   "platform interface covers the image.")
    headline = (brief.get("headline") or "").strip()
    if not headline:
        return prompt
    typo = brief.get("typography") or {}
    parts = [prompt, f'\n\nRender this exact text on the image. Headline: "{headline}"']
    hp = typo.get("headline_placement")
    if hp:
        parts.append(f"(placement: {hp})")
    fs = typo.get("font_style")
    if fs:
        parts.append(f"(font: {fs})")
    col = typo.get("color")
    if col:
        parts.append(f"(color: {col})")
    sub = (brief.get("subheadline") or "").strip()
    if sub:
        sp = typo.get("subheadline_placement") or ""
        parts.append(f'Subheadline: "{sub}"' + (f" (placement: {sp})" if sp else ""))
    parts.append("Spell every word correctly. Besides the headline and subheadline, render "
                 "only the text lines the scene description above explicitly asks for "
                 "(for example benefit lines, labels or a CTA), exactly as written there. "
                 "Add no other text and no watermark.")
    return " ".join(parts)


# --- Selection parsing -------------------------------------------------------
def parse_selection(spec: str) -> list[int]:
    """'1,2,4,7-10' -> [1,2,4,7,8,9,10] (sorted, de-duplicated)."""
    out: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.fullmatch(r"(\d+)-(\d+)", chunk)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            out.update(range(min(lo, hi), max(lo, hi) + 1))
        elif chunk.isdigit():
            out.add(int(chunk))
        else:
            raise ValueError(f"bad selection token: {chunk!r}")
    return sorted(out)


def _brief_number(brief: dict, fallback_index: int) -> int:
    n = brief.get("_brief_n")
    return int(n) if isinstance(n, int) else fallback_index


def _slug(text: str, maxlen: int = 35) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "brief"


# --- Reference resolution ----------------------------------------------------
def _resolve_ref_paths(brief: dict, refs_dir: Path | None, n: int) -> list[Path]:
    """Collect every resolved local reference for a brief, in attach order.

    Channels, in priority: the pipeline-written `_ref_paths` list (the reliable
    output of resolve-reference-assets, one entry per asset role the brief asked
    for), then a single legacy `_ref_path`, then a `NN-` filename match in
    --refs-dir. Only existing, non-empty files survive, de-duplicated.
    """
    candidates: list[str] = []
    rps = brief.get("_ref_paths")
    if isinstance(rps, list):
        candidates.extend(str(x) for x in rps if x)
    elif isinstance(rps, str) and rps:
        candidates.append(rps)
    rp = brief.get("_ref_path")
    if isinstance(rp, str) and rp:
        candidates.append(rp)

    out: list[Path] = []
    seen: set[str] = set()
    for c in candidates:
        p = Path(c)
        key = str(p)
        if key not in seen and p.exists() and p.stat().st_size > 0:
            out.append(p)
            seen.add(key)
    if not out:
        fb = _find_ref(refs_dir, n)
        if fb and fb.exists() and fb.stat().st_size > 0:
            out.append(fb)
    return out


def _find_ref(refs_dir: Path | None, n: int) -> Path | None:
    """Fallback ref lookup by 'NN-' filename prefix when no _ref_path is set."""
    if refs_dir is None or not refs_dir.is_dir():
        return None
    prefix = f"{n:02d}-"
    for p in sorted(refs_dir.iterdir()):
        if p.is_file() and p.name.startswith(prefix):
            return p
    return None


# --- Commands ----------------------------------------------------------------
def cmd_estimate(args) -> int:
    quality = args.quality
    if args.provider == "manual":
        print(json.dumps({"provider": "manual", "count": args.count,
                          "per_image_usd": 0.0, "total_usd": 0.0}, indent=2))
        sys.stderr.write(f"render_ads: {args.count} image(s) via the manual render "
                         "pack = $0 (the founder generates them in their own tool)\n")
        return 0
    try:
        per = per_image_price(args.model, args.resolution, quality)
    except KeyError as e:
        sys.stderr.write(f"render_ads: {e}\n")
        return 3
    total = round(per * args.count, 4)
    out = {
        "provider": args.provider,
        "model": args.model,
        "resolution": args.resolution,
        "quality": quality if args.model == "openai/gpt-image-2" else None,
        "count": args.count,
        "per_image_usd": per,
        "total_usd": total,
    }
    print(json.dumps(out, indent=2))
    sys.stderr.write(
        f"render_ads: {args.count} image(s) on {args.model} at {args.resolution} "
        f"= about ${total:.2f} (${per:.2f}/image)\n"
    )
    return 0


def _check_provider(args) -> tuple[int, str | None, str | None]:
    """Return (exit_code, fal_bin, key). exit_code 0 means the provider is usable."""
    if args.provider == "manual":
        return 0, None, None
    if args.provider == "openai":
        key = _openai_key()
        if not key:
            sys.stderr.write("render_ads: OPENAI_API_KEY not set; nothing was sent. "
                             "Briefs are saved. Set the key, pick another provider, "
                             "or re-run with --provider manual to get the render pack.\n")
            return 2, None, None
        return 0, None, key
    fal = _fal_bin()
    if not fal:
        sys.stderr.write("render_ads: `fal` CLI not found on PATH; cannot render with fal. "
                         "Install the fal CLI, or re-run with --provider openai "
                         "or --provider manual. Briefs are saved.\n")
        return 3, None, None
    key = _key()
    if not key:
        sys.stderr.write("render_ads: FAL_KEY (or FAL_API_KEY) not set; nothing was sent. "
                         "Briefs are saved. Set the key, re-run with --provider openai "
                         "(OPENAI_API_KEY), or --provider manual to get the render pack.\n")
        return 2, None, None
    return 0, fal, key


def cmd_batch(args) -> int:
    rc, fal, key = _check_provider(args)
    if rc:
        return rc

    try:
        briefs = json.loads(Path(args.briefs).read_text(encoding="utf-8"))
        if not isinstance(briefs, list):
            raise ValueError("briefs JSON must be a top-level array")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        sys.stderr.write(f"render_ads: cannot read briefs JSON: {e}\n")
        return 3

    try:
        selection = set(parse_selection(args.select))
    except ValueError as e:
        sys.stderr.write(f"render_ads: {e}\n")
        return 3
    if not selection:
        sys.stderr.write("render_ads: empty selection.\n")
        return 3

    if args.provider == "manual":
        per = 0.0
    else:
        try:
            per = per_image_price(args.model, args.resolution, args.quality)
        except KeyError as e:
            sys.stderr.write(f"render_ads: {e}\n")
            return 3

    if args.provider != "manual" and not spend_confirmed(args.confirm_spend):
        count = sum(1 for i, b in enumerate(briefs, start=1)
                    if isinstance(b, dict) and _brief_number(b, i) in selection)
        total = round(per * count, 4)
        print(json.dumps({"spend_gate": "closed", "provider": args.provider,
                          "model": args.model, "resolution": args.resolution,
                          "quality": args.quality if args.model == OPENAI_MODEL_ID else None,
                          "count": count, "per_image_usd": per, "total_usd": total}, indent=2))
        sys.stderr.write(
            f"render_ads: spend gate closed, nothing was sent. {count} image(s) on "
            f"{args.model} at {args.resolution} = about ${total:.2f} (${per:.2f}/image). "
            "Show this to the founder at Gate 2; once they confirm model, resolution, count "
            "and total, re-run the same command with --confirm-spend (or FOG_ALLOW_SPEND=1). "
            "No spend: re-run with --provider manual.\n")
        return 4

    out_dir = Path(args.out)
    refs_dir = Path(args.refs_dir) if args.refs_dir else None
    records: list[dict] = []
    manual_entries: list[dict] = []
    rendered = 0
    model_label = "manual" if args.provider == "manual" else args.model

    for idx, brief in enumerate(briefs, start=1):
        if not isinstance(brief, dict):
            continue
        n = _brief_number(brief, idx)
        if n not in selection:
            continue

        concept = brief.get("_concept", "")
        slug = _slug(concept or f"brief-{n}")
        filename = f"{n:02d}-{slug}.jpg"
        dest = out_dir / filename
        rec: dict = {"brief_n": n, "concept": concept, "provider": args.provider,
                     "model": model_label, "resolution": args.resolution,
                     "file": str(dest)}

        # A brief asks for source imagery via `reference_assets` (the general
        # channel: product packshot, brand logo, UI screenshot, hero) or the
        # legacy `product_integration` object. Either way the resolved local
        # paths arrive as `_ref_paths` written by resolve-reference-assets.
        wants_refs = bool(brief.get("reference_assets")) or \
            isinstance(brief.get("product_integration"), dict)
        ref_paths: list[Path] = _resolve_ref_paths(brief, refs_dir, n)
        if wants_refs and not ref_paths and args.provider != "manual":
            rec.update(mode="image-to-image", status="SKIPPED_REF_MISSING",
                       error="no resolved reference image")
            records.append(rec)
            sys.stderr.write(f"render_ads: brief {n} skipped (reference missing)\n")
            continue

        rec["mode"] = "image-to-image" if ref_paths else "text-to-image"
        rec["source"] = ", ".join(str(p) for p in ref_paths)
        prompt = _compose_prompt(brief, args.ratio)

        if args.provider == "manual":
            dropped = _find_dropped(out_dir, n)
            rec["mode"] = "manual"
            if dropped:
                rec.update(status="OK", file=str(dropped))
                rendered += 1
                sys.stderr.write(f"render_ads: brief {n} founder file found -> {dropped}\n")
            else:
                rec.update(status="AWAITING_FILE",
                           error=f"drop the image as {out_dir / filename} "
                                 f"(jpg, jpeg, png or webp)")
            if wants_refs and not ref_paths:
                rec["note"] = ("reference asset not resolved: attach the founder's "
                               "real asset in the tool, never an invented one")
            records.append(rec)
            manual_entries.append({
                "n": n, "slug": slug, "concept": concept, "filename": filename,
                "status": rec["status"], "prompt": prompt,
                "headline": (brief.get("headline") or "").strip(),
                "subheadline": (brief.get("subheadline") or "").strip(),
                "refs": [str(p) for p in ref_paths] or
                        (["UNRESOLVED: attach the real asset the brief asks for"]
                         if wants_refs else []),
            })
            continue

        try:  # one attempt, no retry
            if args.provider == "openai":
                _render_openai(key, args.openai_model, prompt, args.ratio,  # type: ignore[arg-type]
                               args.quality, ref_paths, dest, PER_BRIEF_TIMEOUT_S)
            else:
                # Upload every local reference to fal storage; the model gets short URLs.
                ref_urls: list[str] = []
                try:
                    for p in ref_paths:
                        ref_urls.append(fal_upload(p, key))  # type: ignore[arg-type]
                except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError,
                        OSError) as e:
                    raise RuntimeError(f"reference upload failed: {str(e)[:200]}") from None
                image_url = _render_one(fal, args.model, prompt, args.ratio,  # type: ignore[arg-type]
                                        args.resolution, args.quality, ref_urls,
                                        PER_BRIEF_TIMEOUT_S)
                _download(image_url, dest)
        except (subprocess.TimeoutExpired, urllib.error.URLError,
                urllib.error.HTTPError, RuntimeError, OSError, KeyError,
                ValueError, json.JSONDecodeError) as e:
            rec.update(status="FAILED", error=str(e)[:300])
            records.append(rec)
            sys.stderr.write(f"render_ads: brief {n} FAILED: {str(e)[:200]}\n")
            continue

        rec["status"] = "OK"
        records.append(rec)
        rendered += 1
        sys.stderr.write(f"render_ads: brief {n} -> {dest}\n")

    manual_pack = None
    if args.provider == "manual" and manual_entries:
        try:
            manual_pack = str(_write_manual_pack(out_dir, manual_entries, args.ratio))
            sys.stderr.write(f"render_ads: manual render pack written to {manual_pack}\n")
        except OSError as e:
            sys.stderr.write(f"render_ads: cannot write the manual render pack: {e}\n")
            return 3

    failed = sum(1 for r in records if r.get("status") == "FAILED")
    skipped = sum(1 for r in records if r.get("status") == "SKIPPED_REF_MISSING")
    awaiting = sum(1 for r in records if r.get("status") == "AWAITING_FILE")
    if rendered and (failed or skipped or awaiting):
        state = "PARTIAL_SUCCESS"
    elif rendered:
        state = "SUCCESS"
    elif awaiting:
        state = "AWAITING_FILES"
    else:
        state = "FAILED"

    summary = {
        "run_state": state,
        "provider": args.provider,
        "model": model_label,
        "resolution": args.resolution,
        "per_image_usd": per,
        "rendered": rendered,
        "failed": failed,
        "skipped": skipped,
        "awaiting_file": awaiting,
        "actual_spend_usd": round(per * rendered, 4),
        "manual_pack": manual_pack,
        "records": records,
    }
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--estimate", action="store_true",
                   help="Print the spend estimate and exit (no API call, no key).")
    p.add_argument("--batch", dest="briefs", metavar="BRIEFS_JSON",
                   help="Render the selection from this briefs JSON array.")
    p.add_argument("--select", default="",
                   help='Brief numbers to render, e.g. "1,2,4,7-10".')
    p.add_argument("--out", default="images",
                   help="Output directory for downloaded images (batch).")
    p.add_argument("--refs-dir", default="",
                   help="Directory of resolved reference images (batch).")
    p.add_argument("--provider", default="manual", choices=list(PROVIDERS),
                   help="image_gen provider: manual (default, no API: writes a render "
                        "pack, collects dropped files), fal (FAL_KEY) or openai "
                        "(OPENAI_API_KEY, model openai/gpt-image-2 only).")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICING.keys()))
    p.add_argument("--openai-model", default="gpt-image-2",
                   help="Model name sent to the OpenAI API with --provider openai "
                        "(default gpt-image-2; gpt-image-1 also works).")
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--quality", default="medium", choices=["medium", "high"],
                   help="gpt-image-2 quality tier (ignored by other models).")
    p.add_argument("--ratio", default="4:5", choices=list(RATIOS),
                   help="Aspect ratio for the whole batch: 4:5 (feed, default), 1:1, "
                        "or 9:16 (Stories and Reels).")
    p.add_argument("--count", type=int, default=0, help="Image count (estimate).")
    p.add_argument("--confirm-spend", action="store_true",
                   help="The founder confirmed Gate 2: allow the paid batch (fal, openai). "
                        "FOG_ALLOW_SPEND=1 in the environment does the same for scripted runs.")
    args = p.parse_args()

    if args.provider == "openai" and args.model != OPENAI_MODEL_ID:
        sys.stderr.write(f"render_ads: --provider openai serves {OPENAI_MODEL_ID} only; "
                         f"using it instead of {args.model}.\n")
        args.model = OPENAI_MODEL_ID

    if args.estimate:
        if args.count <= 0:
            sys.stderr.write("render_ads: --estimate needs --count > 0.\n")
            return 3
        return cmd_estimate(args)
    if args.briefs:
        return cmd_batch(args)
    sys.stderr.write("render_ads: pass --estimate or --batch. See --help.\n")
    return 3


if __name__ == "__main__":
    sys.exit(main())
