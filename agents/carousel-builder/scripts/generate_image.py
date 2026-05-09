#!/usr/bin/env python3
"""generate_image.py — Generate a single carousel slide image via fal.ai.

Single opt-in: if FAL_API_KEY (or FAL_KEY) is unset, the script exits
non-zero with a clear, non-fatal message. Caller (handle-assets skill)
must treat this as "AI images unavailable, route to SVG / text fallback".

Default model: fal-ai/nano-banana-pro (Google Gemini 3 Pro Image,
~$0.15/image, strong text rendering, predictable cost).
Alternative: openai/gpt-image-2 (medium quality ~$0.053).

Usage:
    python generate_image.py \\
        --prompt "minimalist illustration of a founder writing notes" \\
        --out output_dir/images/slide-04.jpg \\
        --ratio 4:5

    python generate_image.py \\
        --prompt "..." \\
        --out output_dir/images/slide-04.jpg \\
        --model openai/gpt-image-2 \\
        --brand-colors "#0b3d91,#f5a623" \\
        --tone founder

Calls the fal HTTP API directly (no fal-client dep). Polls until ready,
downloads the resulting image, optimizes via Pillow (max 1500px long edge,
JPEG q=85), and writes to --out.

Exit codes:
    0  success, image written to --out
    2  no API key set (caller should fall back silently)
    3  fal API error (caller should fall back, log warning)
    4  download / optimization error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "fal-ai/nano-banana-pro"
ALLOWED_MODELS = {
    "fal-ai/nano-banana-pro",
    "openai/gpt-image-2",
    # historical fallbacks; kept for users on tighter budgets
    "fal-ai/flux/schnell",
    "fal-ai/flux/dev",
}

FAL_QUEUE_BASE = "https://queue.fal.run"
POLL_INTERVAL_S = 2.0
POLL_MAX_ATTEMPTS = 60  # ~120s total


def _key() -> str | None:
    return os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Key {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(url: str, body: dict, key: str, timeout: int = 60) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(key), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str, key: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=_headers(key), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ratio_to_size(ratio: str, model: str) -> tuple[str | None, dict]:
    """Map carousel ratio to model-specific size param.

    Returns (image_size_keyword, extra_input_dict). Different fal models accept
    different size formats; we pick safe defaults.
    """
    if model == "openai/gpt-image-2":
        size = "1024x1024" if ratio == "1:1" else "1024x1536"  # square or portrait
        return None, {"size": size}
    if ratio == "1:1":
        return "square_hd", {}
    return "portrait_4_3", {}


def _build_prompt(base_prompt: str, brand_colors: list[str], tone: str) -> str:
    suffix_parts = []
    if brand_colors:
        suffix_parts.append("brand colors " + " and ".join(brand_colors))
    if tone == "founder":
        suffix_parts.append("clean, modern, editorial")
    elif tone == "expert":
        suffix_parts.append("professional, precise, clean")
    elif tone == "casual":
        suffix_parts.append("friendly, approachable, warm")
    suffix_parts.append("no text overlay, no watermark")
    return base_prompt.strip() + ", " + ", ".join(suffix_parts)


def _submit(model: str, payload: dict, key: str) -> str:
    url = f"{FAL_QUEUE_BASE}/{model}"
    res = _post(url, payload, key)
    request_id = res.get("request_id")
    if not request_id:
        raise RuntimeError(f"fal queue did not return a request_id: {res}")
    return request_id


def _poll(model: str, request_id: str, key: str) -> dict:
    status_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}/status"
    result_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}"
    for _ in range(POLL_MAX_ATTEMPTS):
        status = _get(status_url, key)
        s = status.get("status")
        if s == "COMPLETED":
            return _get(result_url, key)
        if s in {"FAILED", "ERROR"}:
            raise RuntimeError(f"fal job failed: {status}")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(f"fal job {request_id} did not complete after "
                       f"{POLL_INTERVAL_S * POLL_MAX_ATTEMPTS:.0f}s")


def _extract_image_url(result: dict) -> str:
    # nano-banana-pro / flux: {"images": [{"url": "..."}]}
    images = result.get("images") or []
    if images and isinstance(images, list):
        first = images[0]
        if isinstance(first, dict) and first.get("url"):
            return first["url"]
    # openai/gpt-image-2: {"image": {"url": "..."}}
    img = result.get("image")
    if isinstance(img, dict) and img.get("url"):
        return img["url"]
    raise RuntimeError(f"could not find image url in fal result: keys={list(result.keys())}")


def _download(url: str, dest: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(url, headers={"Accept": "image/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.read())


def _optimize(path: Path, max_long_edge: int = 1500, quality: int = 85) -> None:
    try:
        from PIL import Image
    except ImportError:
        return  # Pillow optional; skip optimization
    with Image.open(path) as im:
        im = im.convert("RGB") if im.mode in ("RGBA", "P", "LA") else im
        w, h = im.size
        long_edge = max(w, h)
        if long_edge > max_long_edge:
            scale = max_long_edge / long_edge
            new_size = (int(w * scale), int(h * scale))
            im = im.resize(new_size, Image.LANCZOS)
        out_path = path.with_suffix(".jpg")
        im.save(out_path, "JPEG", quality=quality, optimize=True)
        if out_path != path:
            path.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", required=True, help="Image prompt (will be augmented with brand suffix)")
    p.add_argument("--out", required=True, help="Output path, e.g. output_dir/images/slide-04.jpg")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(ALLOWED_MODELS),
                   help=f"fal model id (default: {DEFAULT_MODEL})")
    p.add_argument("--ratio", default="4:5", choices=["1:1", "4:5"], help="Carousel ratio")
    p.add_argument("--brand-colors", default="",
                   help="Comma-separated hex colors to include in the prompt suffix")
    p.add_argument("--tone", default="founder", choices=["founder", "expert", "casual"])
    p.add_argument("--dry-run", action="store_true",
                   help="Print the resolved request payload and exit (no API call)")
    args = p.parse_args()

    key = _key()
    if not key and not args.dry_run:
        sys.stderr.write(
            "generate_image: FAL_API_KEY (or FAL_KEY) is not set. "
            "AI image generation is unavailable for this run.\n"
        )
        return 2

    brand_colors = [c.strip() for c in args.brand_colors.split(",") if c.strip()]
    full_prompt = _build_prompt(args.prompt, brand_colors, args.tone)

    image_size, extra = _ratio_to_size(args.ratio, args.model)
    payload: dict = {"prompt": full_prompt, **extra}
    if image_size:
        payload["image_size"] = image_size

    if args.dry_run:
        print(json.dumps({
            "model": args.model,
            "endpoint": f"{FAL_QUEUE_BASE}/{args.model}",
            "payload": payload,
            "out": args.out,
        }, indent=2))
        return 0

    try:
        request_id = _submit(args.model, payload, key)  # type: ignore[arg-type]
        sys.stderr.write(f"generate_image: submitted {args.model} request {request_id}\n")
        result = _poll(args.model, request_id, key)  # type: ignore[arg-type]
        image_url = _extract_image_url(result)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, TimeoutError) as e:
        sys.stderr.write(f"generate_image: fal API error: {e}\n")
        return 3

    out_path = Path(args.out)
    try:
        _download(image_url, out_path)
        _optimize(out_path)
    except Exception as e:
        sys.stderr.write(f"generate_image: download/optimize error: {e}\n")
        return 4

    final_path = out_path.with_suffix(".jpg") if out_path.suffix.lower() != ".jpg" else out_path
    sys.stderr.write(f"generate_image: wrote {final_path}\n")
    print(str(final_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
