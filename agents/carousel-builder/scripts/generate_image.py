#!/usr/bin/env python3
"""generate_image.py: Generate a single carousel slide image (capability image_gen).

Providers, picked with --provider (the agent passes the one resolved at Step 0,
see shared/tools.md):

  fal     (default)  fal HTTP queue API, FAL_API_KEY (or FAL_KEY).
  openai             OpenAI Images API directly, OPENAI_API_KEY. Model name
                     from --openai-model (default gpt-image-2).
  manual             no API, no key: writes the brand-augmented prompt next to
                     --out as slide-NN.prompt.txt and exits 5, so the founder can
                     generate the image in Midjourney, Canva, ChatGPT or Figma
                     and drop it in the run media/ folder (AGENT_CAROUSEL_BUILDER.md, Tools).

A missing key never raises: the script exits 2 with a one-line message and the
caller routes to the manual prompt, a real photo or an SVG visual.

Spend gate: fal and openai bill per image. Without --confirm-spend (or the
environment variable FOG_ALLOW_SPEND=1 for scripted runs) the script sends
nothing, prints the provider, the model and the estimated price, and exits 6.
The agent passes --confirm-spend only after the founder agreed to that price.
--dry-run and --provider manual never spend and need no confirmation.

Default fal model: fal-ai/nano-banana-pro (Google Gemini 3 Pro Image,
~$0.15/image, strong text rendering, predictable cost).
Alternative: openai/gpt-image-2 through fal (medium quality ~$0.053).

Usage:
    python generate_image.py \\
        --prompt "minimalist illustration of a founder writing notes" \\
        --out output_dir/images/slide-04.jpg \\
        --ratio 4:5

    python generate_image.py --provider openai \\
        --prompt "..." --out output_dir/images/slide-04.jpg \\
        --brand-colors "#0b3d91,#f5a623" --tone founder

    python generate_image.py --provider manual \\
        --prompt "..." --out output_dir/images/slide-04.jpg

    # After the founder agreed to the estimated price:
    python generate_image.py --prompt "..." --out output_dir/images/slide-04.jpg \\
        --confirm-spend

fal: calls the HTTP API directly (no fal-client dep), polls until ready,
downloads the image. openai: one synchronous call, base64 result. Either way the
image is optimized via Pillow when installed (max 1500px long edge, JPEG q=85)
and written to --out.

Exit codes:
    0  success, image written to --out
    2  the provider's key is not set (caller falls back, no retry this run)
    3  provider API error (caller should fall back, log warning)
    4  download / optimization error
    5  manual provider: prompt written, waiting for the founder's image
    6  spend gate closed: no --confirm-spend and no FOG_ALLOW_SPEND=1, nothing sent
"""

from __future__ import annotations

import argparse
import base64
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

PROVIDERS = ("fal", "openai", "manual")
FAL_QUEUE_BASE = "https://queue.fal.run"
OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
OPENAI_TIMEOUT_S = 180  # a single high-quality image can take over a minute
POLL_INTERVAL_S = 2.0
POLL_MAX_ATTEMPTS = 60  # ~120s total

# Estimated USD per image, shown at the spend gate. Check the provider's pricing
# page before quoting it. A model missing here has no bundled price.
PRICE_USD = {
    "fal-ai/nano-banana-pro": 0.15,
    "openai/gpt-image-2": 0.053,  # medium quality through fal
}


def spend_confirmed(flag: bool) -> bool:
    """True when the founder's agreement was passed on: --confirm-spend or FOG_ALLOW_SPEND=1."""
    return bool(flag) or os.environ.get("FOG_ALLOW_SPEND", "").strip() == "1"


def _spend_gate_message(provider: str, model: str) -> str:
    price = PRICE_USD.get(model) if provider == "fal" else None
    cost = (f"about ${price:.3f} per image" if price is not None
            else "billed per image by the provider (price not bundled, check the pricing page)")
    return (f"generate_image: spend gate closed, nothing was sent. 1 image with {provider} "
            f"({model}): {cost}. Ask the founder, then re-run the same command with "
            "--confirm-spend (or FOG_ALLOW_SPEND=1). No spend: re-run with --provider manual.\n")


def _key(provider: str = "fal") -> str | None:
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY")
    return os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")


def _openai_generate(prompt: str, ratio: str, model: str, key: str, dest: Path) -> None:
    """One synchronous OpenAI Images call; writes the decoded image to dest."""
    size = "1024x1024" if ratio == "1:1" else "1024x1536"  # square or portrait
    body = json.dumps({"model": model, "prompt": prompt, "n": 1, "size": size}).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_IMAGES_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=OPENAI_TIMEOUT_S) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from None
    data = result.get("data") or []
    if not data or not isinstance(data[0], dict):
        raise RuntimeError(f"no image in OpenAI result: keys={list(result.keys())}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if data[0].get("b64_json"):
        dest.write_bytes(base64.b64decode(data[0]["b64_json"]))
    elif data[0].get("url"):
        _download(data[0]["url"], dest)
    else:
        raise RuntimeError("OpenAI result holds neither b64_json nor url")


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
    p.add_argument("--provider", default="fal", choices=list(PROVIDERS),
                   help="image_gen provider: fal (default, FAL_API_KEY), openai "
                        "(OPENAI_API_KEY), manual (write the prompt, exit 5)")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(ALLOWED_MODELS),
                   help=f"fal model id (default: {DEFAULT_MODEL}); fal provider only")
    p.add_argument("--openai-model", default="gpt-image-2",
                   help="Model name sent to OpenAI with --provider openai (default gpt-image-2)")
    p.add_argument("--ratio", default="4:5", choices=["1:1", "4:5"], help="Carousel ratio")
    p.add_argument("--brand-colors", default="",
                   help="Comma-separated hex colors to include in the prompt suffix")
    p.add_argument("--tone", default="founder", choices=["founder", "expert", "casual"])
    p.add_argument("--dry-run", action="store_true",
                   help="Print the resolved request payload and exit (no API call)")
    p.add_argument("--confirm-spend", action="store_true",
                   help="The founder agreed to the per-image price: allow the paid call. "
                        "FOG_ALLOW_SPEND=1 in the environment does the same for scripted runs.")
    args = p.parse_args()

    brand_colors = [c.strip() for c in args.brand_colors.split(",") if c.strip()]
    full_prompt = _build_prompt(args.prompt, brand_colors, args.tone)
    out_path = Path(args.out)

    if args.provider == "manual":
        prompt_path = out_path.with_suffix(".prompt.txt")
        try:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(
                f"Ratio: {args.ratio}\n"
                f"Save the image as {out_path.stem}.jpg (or .png, .webp) in this same "
                f"folder, then ask the agent to rerun the render and export steps.\n\n"
                f"{full_prompt}\n", encoding="utf-8")
        except OSError as e:
            sys.stderr.write(f"generate_image: cannot write the prompt file: {e}\n")
            return 4
        sys.stderr.write(f"generate_image: manual provider, prompt written to {prompt_path}; "
                         "generate the image in your own tool and drop it back.\n")
        print(str(prompt_path))
        return 5

    key = _key(args.provider)
    if not key and not args.dry_run:
        var = "OPENAI_API_KEY" if args.provider == "openai" else "FAL_API_KEY (or FAL_KEY)"
        sys.stderr.write(
            f"generate_image: {var} is not set. AI image generation with "
            f"{args.provider} is unavailable for this run; use --provider manual "
            "to get the prompt for your own tool.\n"
        )
        return 2

    if args.provider == "openai":
        if args.dry_run:
            print(json.dumps({"provider": "openai", "endpoint": OPENAI_IMAGES_URL,
                              "model": args.openai_model, "prompt": full_prompt,
                              "out": args.out}, indent=2))
            return 0
        if not spend_confirmed(args.confirm_spend):
            sys.stderr.write(_spend_gate_message("openai", args.openai_model))
            return 6
        try:
            _openai_generate(full_prompt, args.ratio, args.openai_model, key, out_path)  # type: ignore[arg-type]
        except (urllib.error.URLError, RuntimeError, TimeoutError, ValueError) as e:
            sys.stderr.write(f"generate_image: OpenAI API error: {e}\n")
            return 3
        except OSError as e:
            sys.stderr.write(f"generate_image: write error: {e}\n")
            return 4
        try:
            _optimize(out_path)
        except Exception as e:
            sys.stderr.write(f"generate_image: optimize error: {e}\n")
            return 4
        final_path = out_path.with_suffix(".jpg") if out_path.suffix.lower() != ".jpg" else out_path
        sys.stderr.write(f"generate_image: wrote {final_path}\n")
        print(str(final_path))
        return 0

    image_size, extra = _ratio_to_size(args.ratio, args.model)
    payload: dict = {"prompt": full_prompt, **extra}
    if image_size:
        payload["image_size"] = image_size

    if args.dry_run:
        print(json.dumps({
            "provider": "fal",
            "model": args.model,
            "endpoint": f"{FAL_QUEUE_BASE}/{args.model}",
            "payload": payload,
            "out": args.out,
        }, indent=2))
        return 0

    if not spend_confirmed(args.confirm_spend):
        sys.stderr.write(_spend_gate_message("fal", args.model))
        return 6

    try:
        request_id = _submit(args.model, payload, key)  # type: ignore[arg-type]
        sys.stderr.write(f"generate_image: submitted {args.model} request {request_id}\n")
        result = _poll(args.model, request_id, key)  # type: ignore[arg-type]
        image_url = _extract_image_url(result)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, TimeoutError,
            ValueError) as e:
        sys.stderr.write(f"generate_image: fal API error: {e}\n")
        return 3

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
