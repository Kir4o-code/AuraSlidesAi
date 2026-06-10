from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

OPTIMIZED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated" / "optimized_images"
OPTIMIZED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_SIZE = (1600, 900)
JPEG_QUALITY = 82


class ImageOptimizationError(Exception):
    pass


@dataclass(frozen=True)
class OptimizedImage:
    path: Path
    width: int | None
    height: int | None
    has_transparency: bool


def _safe_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._-")
    return cleaned[:80] or "image"


def _detect_transparency(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _output_path(cache_key: str, digest: str, has_transparency: bool) -> Path:
    suffix = ".png" if has_transparency else ".jpg"
    return OPTIMIZED_IMAGES_DIR / f"{_safe_key(cache_key)}_{digest}{suffix}"


def _save_optimized_image(image: Image.Image, output_path: Path, has_transparency: bool) -> None:
    image = ImageOps.exif_transpose(image)
    image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

    if has_transparency:
        rgba_image = image.convert("RGBA")
        rgba_image.save(
            output_path,
            format="PNG",
            optimize=True,
            compress_level=9,
        )
        return

    rgb_image = image.convert("RGB")
    rgb_image.save(
        output_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )


def optimize_image_bytes(image_bytes: bytes, cache_key: str) -> OptimizedImage:
    OPTIMIZED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(image_bytes).hexdigest()[:16]

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            has_transparency = _detect_transparency(image)
            output_path = _output_path(cache_key, digest, has_transparency)
            if not output_path.exists():
                _save_optimized_image(image, output_path, has_transparency)

            with Image.open(output_path) as optimized:
                width, height = optimized.size

            return OptimizedImage(
                path=output_path,
                width=width,
                height=height,
                has_transparency=has_transparency,
            )
    except Exception as exc:
        raise ImageOptimizationError(f"Failed to optimize image: {exc}") from exc


def optimize_image_file(source_path: Path, cache_key: str | None = None) -> OptimizedImage:
    try:
        image_bytes = source_path.read_bytes()
    except Exception as exc:
        raise ImageOptimizationError(f"Failed to read image file {source_path}: {exc}") from exc

    return optimize_image_bytes(image_bytes, cache_key=cache_key or source_path.stem)
