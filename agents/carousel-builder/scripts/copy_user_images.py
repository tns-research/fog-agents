#!/usr/bin/env python3
"""copy_user_images.py — Normalize user-supplied images for a carousel run.

Accepts a JSON list of slide image specs and copies each image into
<output_dir>/images/slide-NN.<ext>, optimizing along the way:
  - max 1500px on the long edge
  - JPEG quality 85, EXIF stripped
  - HEIC and other Pillow-readable formats converted to JPEG
  - hard cap: 5 user images per run (above the cap are skipped with a warning)

The skill `handle-assets` is the only intended caller. Per-slide spec format:
    {"slide_index": 4, "source": "/abs/path/photo.heic", "alt": "Optional"}
    {"slide_index": 7, "source": "https://example.com/img.png", "alt": "..."}

Usage (stdin):
    echo '[{"slide_index":4,"source":"/path/to/photo.heic"}]' | \\
        python copy_user_images.py --output-dir output_dir/

Usage (file):
    python copy_user_images.py --input specs.json --output-dir output_dir/

Outputs JSON to stdout: a list of {slide_index, path, ok, reason} entries that
the caller can merge back into the slide plan.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_IMAGES = 5
MAX_LONG_EDGE = 1500
JPEG_QUALITY = 85
DOWNLOAD_TIMEOUT_S = 60

# Pillow can read these natively (with `pillow-heif` registered for HEIC)
SAFE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic", ".heif"}


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "carousel-builder/1.0"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_S) as resp:
        dest.write_bytes(resp.read())


def _try_register_heif() -> None:
    """Best-effort: enable HEIC reading if pillow-heif is installed."""
    try:
        import pillow_heif  # type: ignore
        pillow_heif.register_heif_opener()
    except ImportError:
        pass


def _optimize(src: Path, dest_no_ext: Path) -> Path:
    """Open src, downscale + re-encode as JPEG, return final path."""
    from PIL import Image  # type: ignore

    with Image.open(src) as im:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
        long_edge = max(w, h)
        if long_edge > MAX_LONG_EDGE:
            scale = MAX_LONG_EDGE / long_edge
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        out = dest_no_ext.with_suffix(".jpg")
        im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return out


def _process_one(spec: dict, images_dir: Path, work_dir: Path) -> dict:
    idx = spec.get("slide_index")
    source = spec.get("source", "")
    if idx is None or not source:
        return {"slide_index": idx, "ok": False, "reason": "missing slide_index or source"}

    images_dir.mkdir(parents=True, exist_ok=True)
    dest_no_ext = images_dir / f"slide-{int(idx):02d}"

    # Step 1: get a local copy of the bytes
    if _is_url(source):
        ext = Path(source.split("?")[0]).suffix.lower() or ".bin"
        if ext not in SAFE_EXTS:
            ext = ".bin"
        tmp = work_dir / f"slide-{int(idx):02d}-src{ext}"
        try:
            _download(source, tmp)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            return {"slide_index": idx, "ok": False, "reason": f"download failed: {e}"}
    else:
        src_path = Path(source).expanduser()
        if not src_path.is_file():
            return {"slide_index": idx, "ok": False, "reason": f"file not found: {source}"}
        if src_path.suffix.lower() not in SAFE_EXTS:
            return {"slide_index": idx, "ok": False,
                    "reason": f"unsupported format: {src_path.suffix}"}
        tmp = work_dir / f"slide-{int(idx):02d}-src{src_path.suffix.lower()}"
        shutil.copy2(src_path, tmp)

    # Step 2: optimize via Pillow (HEIC handled if pillow-heif present)
    try:
        out = _optimize(tmp, dest_no_ext)
    except Exception as e:
        return {"slide_index": idx, "ok": False, "reason": f"optimize failed: {e}"}
    finally:
        tmp.unlink(missing_ok=True)

    return {
        "slide_index": idx,
        "ok": True,
        "path": str(out.relative_to(images_dir.parent)),
        "alt": spec.get("alt"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-dir", required=True,
                   help="Carousel run output directory (images/ subdir will be created)")
    p.add_argument("--input", help="Path to JSON specs file (default: stdin)")
    args = p.parse_args()

    if args.input:
        specs = json.loads(Path(args.input).read_text())
    else:
        specs = json.loads(sys.stdin.read())

    if not isinstance(specs, list):
        sys.stderr.write("copy_user_images: input must be a JSON list\n")
        return 1

    output_dir = Path(args.output_dir)
    images_dir = output_dir / "images"
    work_dir = output_dir / ".work-images"
    work_dir.mkdir(parents=True, exist_ok=True)

    _try_register_heif()
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.stderr.write("copy_user_images: Pillow not installed. "
                         "Install via scripts/requirements.txt.\n")
        return 1

    results: list[dict] = []
    for i, spec in enumerate(specs):
        if i >= MAX_IMAGES:
            results.append({
                "slide_index": spec.get("slide_index"),
                "ok": False,
                "reason": f"hard cap of {MAX_IMAGES} user images per run reached",
            })
            continue
        results.append(_process_one(spec, images_dir, work_dir))

    shutil.rmtree(work_dir, ignore_errors=True)
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
