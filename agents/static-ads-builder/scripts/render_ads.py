#!/usr/bin/env python3
"""render_ads.py - Render selected static-ad briefs via the fal CLI, behind a budget gate.

Two responsibilities, one script:

  --estimate   Compute the spend for a given model + resolution + count. No API
               call, no key needed. This feeds Gate 2 (the human budget gate):
               the founder sees model, resolution, count, per-image price, and
               total BEFORE anything is rendered.

  --batch      Render a selected subset of briefs from a briefs JSON file. One
               attempt per brief, NO auto-retry. Image-to-image when a brief
               carries resolved local references (`_ref_paths`, e.g. a product
               packshot, the brand logo, a UI screenshot, a hero image), all
               attached together; text-to-image otherwise. Downloads each result
               locally and prints a JSON run summary on stdout.

Execution model: this script SHELLS the `fal` CLI, which owns the fal-specific
parts (endpoint routing to `/edit`, queue submit, polling, result extraction).
The script keeps only the founder-facing guardrails: the pricing table, the two
gates, the batch loop, reference upload, naming, and the run report. This is why
the endpoint/poll class of bug cannot happen here: the script never hand-builds a
queue URL.

  nano-banana-2 / nano-banana-pro  ->  `fal generate | edit` shortcuts
                                       (`-old` variants for pro), references
                                       attached as repeatable `--image <url>`.
  openai/gpt-image-2               ->  `fal run <endpoint> --input <json>`,
                                       references attached as `image_urls`.

Local references are uploaded to fal storage first (initiate + PUT), so the model
always receives a short URL. Data URIs are never put on the command line (a large
screenshot would blow the kernel argv limit and the job would fail).

Resolution is the main cost lever. The pricing table below is the single source
of truth for both the estimate and the post-run actual spend. Update it here when
fal prices change; never hard-code a price anywhere else.

Pricing (USD per generated image), from the locked plan section 7.2.1:

  fal-ai/nano-banana-2     1K 0.08   2K 0.12   4K 0.16     (default)
  fal-ai/nano-banana-pro   1K 0.15   2K 0.15   4K 0.30     (higher-fidelity fallback)
  openai/gpt-image-2  medium  1K 0.05   2K 0.06   4K 0.10
  openai/gpt-image-2  high    1K 0.21   2K 0.22   4K 0.40

Notes on resolution per model:
  - nano-banana-2 / nano-banana-pro take an enum resolution (1K/2K/4K) and an
    aspect ratio; the CLI shortcut maps both natively.
  - gpt-image-2 takes an explicit `image_size` pixel object and a `quality`
    tier; `--resolution` selects the PRICING row and `quality` maps to
    medium/high. Pixel size is clamped to the model's supported size.

Usage:
    # Gate 2 estimate (no key, no render):
    python render_ads.py --estimate --count 10 --model fal-ai/nano-banana-2 --resolution 1K

    # Render the confirmed selection:
    python render_ads.py --batch briefs.json --select "1,2,4,7-10" \\
        --out images/20260604 --model fal-ai/nano-banana-2 --resolution 1K \\
        --refs-dir refs

Exit codes:
    0  ok (estimate printed, or batch finished with at least the report written)
    2  no FAL_API_KEY / FAL_KEY set (batch only; caller tells the user to set it)
    3  bad input (unreadable briefs JSON, empty selection, unknown model,
       or the `fal` CLI is not on PATH)
"""

from __future__ import annotations

import argparse
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

# The nano-banana family is driven through the CLI's dedicated shortcuts. Each
# maps to a text-to-image command and an image-to-image (edit) command.
NANO_SHORTCUTS: dict[str, dict[str, str]] = {
    "fal-ai/nano-banana-2": {"gen": "generate", "edit": "edit"},
    "fal-ai/nano-banana-pro": {"gen": "generate-old", "edit": "edit-old"},
}

# gpt-image-2 is driven through `fal run <endpoint> --input`. It takes an
# image_size object (width/height) rather than an enum resolution.
GPT_IMAGE_SIZE = {"4:5": {"width": 1024, "height": 1280},
                  "1:1": {"width": 1024, "height": 1024}}

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


# --- fal access: key, CLI binary, storage upload -----------------------------
def _key() -> str | None:
    return os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")


def _fal_bin() -> str | None:
    return shutil.which("fal")


def fal_upload(path: Path, key: str, timeout: int = UPLOAD_TIMEOUT_S) -> str:
    """Upload one local file to fal storage and return its public URL.

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

    nano-banana uses the dedicated shortcut commands; gpt-image-2 uses `fal run`
    with a JSON payload. Either way the CLI does the submit, the polling, and the
    result extraction, so the script never touches a queue URL.
    """
    # The CLI's queue poll builds a wrong status URL for any `/edit` endpoint and
    # returns HTTP 405, so image-to-image (refs present) must run sync. Plain
    # text-to-image uses `--queue` to avoid a long-held sync connection.
    queue = not ref_urls
    if model in NANO_SHORTCUTS:
        sc = NANO_SHORTCUTS[model]
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
    elif model == "openai/gpt-image-2":
        payload: dict = {
            "prompt": prompt,
            "num_images": 1,
            "output_format": "jpeg",
            "image_size": GPT_IMAGE_SIZE["1:1" if ratio == "1:1" else "4:5"],
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


# --- Prompt composition ------------------------------------------------------
def _compose_prompt(brief: dict) -> str:
    """Combine the scene prompt with on-image text rendering instructions."""
    prompt = (brief.get("image_prompt") or "").strip()
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
    parts.append("Spell every word correctly. Do not add any other text, no watermark.")
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
    try:
        per = per_image_price(args.model, args.resolution, quality)
    except KeyError as e:
        sys.stderr.write(f"render_ads: {e}\n")
        return 3
    total = round(per * args.count, 4)
    out = {
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


def cmd_batch(args) -> int:
    fal = _fal_bin()
    if not fal:
        sys.stderr.write("render_ads: `fal` CLI not found on PATH; cannot render. "
                         "Install it (skills-cli/fal-cli) and re-run. Briefs are saved.\n")
        return 3

    key = _key()
    if not key:
        sys.stderr.write("render_ads: FAL_KEY (or FAL_API_KEY) not set; cannot render. "
                         "Briefs are saved; set the key and re-run the batch.\n")
        return 2

    try:
        briefs = json.loads(Path(args.briefs).read_text())
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

    try:
        per = per_image_price(args.model, args.resolution, args.quality)
    except KeyError as e:
        sys.stderr.write(f"render_ads: {e}\n")
        return 3

    out_dir = Path(args.out)
    refs_dir = Path(args.refs_dir) if args.refs_dir else None
    records: list[dict] = []
    rendered = 0

    for idx, brief in enumerate(briefs, start=1):
        n = _brief_number(brief, idx)
        if n not in selection:
            continue

        concept = brief.get("_concept", "")
        slug = _slug(concept or f"brief-{n}")
        filename = f"{n:02d}-{slug}.jpg"
        dest = out_dir / filename
        rec: dict = {"brief_n": n, "concept": concept, "model": args.model,
                     "resolution": args.resolution, "file": str(dest)}

        # A brief asks for source imagery via `reference_assets` (the general
        # channel: product packshot, brand logo, UI screenshot, hero) or the
        # legacy `product_integration` object. Either way the resolved local
        # paths arrive as `_ref_paths` written by resolve-reference-assets.
        wants_refs = bool(brief.get("reference_assets")) or \
            isinstance(brief.get("product_integration"), dict)
        ref_paths: list[Path] = _resolve_ref_paths(brief, refs_dir, n)
        if wants_refs and not ref_paths:
            rec.update(mode="image-to-image", status="SKIPPED_REF_MISSING",
                       error="no resolved reference image")
            records.append(rec)
            sys.stderr.write(f"render_ads: brief {n} skipped (reference missing)\n")
            continue

        # Upload every local reference to fal storage; the model gets short URLs.
        ref_urls: list[str] = []
        try:
            for p in ref_paths:
                ref_urls.append(fal_upload(p, key))
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError,
                OSError) as e:
            rec.update(mode="image-to-image", status="FAILED",
                       error=f"reference upload failed: {str(e)[:200]}")
            records.append(rec)
            sys.stderr.write(f"render_ads: brief {n} FAILED (ref upload): {str(e)[:200]}\n")
            continue

        rec["mode"] = "image-to-image" if ref_urls else "text-to-image"
        rec["source"] = ", ".join(str(p) for p in ref_paths)
        prompt = _compose_prompt(brief)

        try:  # one attempt, no retry
            image_url = _render_one(fal, args.model, prompt, args.ratio,
                                    args.resolution, args.quality, ref_urls,
                                    PER_BRIEF_TIMEOUT_S)
            _download(image_url, dest)
        except (subprocess.TimeoutExpired, urllib.error.URLError,
                urllib.error.HTTPError, RuntimeError, OSError, KeyError,
                json.JSONDecodeError) as e:
            rec.update(status="FAILED", error=str(e)[:300])
            records.append(rec)
            sys.stderr.write(f"render_ads: brief {n} FAILED: {str(e)[:200]}\n")
            continue

        rec["status"] = "OK"
        records.append(rec)
        rendered += 1
        sys.stderr.write(f"render_ads: brief {n} -> {dest}\n")

    failed = sum(1 for r in records if r.get("status") == "FAILED")
    skipped = sum(1 for r in records if r.get("status") == "SKIPPED_REF_MISSING")
    if rendered and (failed or skipped):
        state = "PARTIAL_SUCCESS"
    elif rendered:
        state = "SUCCESS"
    else:
        state = "FAILED"

    summary = {
        "run_state": state,
        "model": args.model,
        "resolution": args.resolution,
        "per_image_usd": per,
        "rendered": rendered,
        "failed": failed,
        "skipped": skipped,
        "actual_spend_usd": round(per * rendered, 4),
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
    p.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(PRICING.keys()))
    p.add_argument("--resolution", default="1K", choices=list(RESOLUTIONS))
    p.add_argument("--quality", default="medium", choices=["medium", "high"],
                   help="gpt-image-2 quality tier (ignored by other models).")
    p.add_argument("--ratio", default="4:5", choices=["4:5", "1:1"])
    p.add_argument("--count", type=int, default=0, help="Image count (estimate).")
    args = p.parse_args()

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
