import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from app.schemas.presentation import Presentation, ResolvedImageAsset, SlideType
from app.services.feature_flags import is_image_generation_enabled
from app.services.gemini_service import (
    GeminiImageGenerationError,
    build_image_cache_key,
    generate_slide_image,
)


logger = logging.getLogger(__name__)
GENERATED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated" / "gemini_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_SIZE = (1600, 900)
JPEG_QUALITY = 82


def _optimize_slide_image(image_bytes: bytes) -> bytes:
    with Image.open(BytesIO(image_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
        else:
            img = img.convert("RGB")
        img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        output = BytesIO()
        img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return output.getvalue()


def _write_optimized_image(source_path: Path, target_path: Path) -> None:
    with Image.open(source_path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
        else:
            img = img.convert("RGB")
        img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        img.save(target_path, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)


async def _resolve_one_slide_image(slide: Any, style: str) -> None:
    image_prompt = getattr(slide, "image_prompt", None)
    if not image_prompt:
        return

    cache_key = build_image_cache_key(slide, style)
    image_path = GENERATED_IMAGES_DIR / f"{cache_key}.jpg"
    legacy_image_path = GENERATED_IMAGES_DIR / f"{cache_key}.png"
    public_url = f"/generated/gemini_images/{image_path.name}"

    if image_path.exists():
        # Reuse the existing file whenever the slide content and image prompt
        # hash to the same cache key.
        slide.resolved_image = ResolvedImageAsset(
            local_path=str(image_path.resolve()),
            public_url=public_url,
            source="gemini-cache",
            source_url="",
            image_url=public_url,
            author=None,
            license_name="AI generated",
        )
        logger.info("Reused cached Gemini image. prompt=%s file=%s", image_prompt, image_path.name)
        return

    if legacy_image_path.exists():
        _write_optimized_image(legacy_image_path, image_path)
        slide.resolved_image = ResolvedImageAsset(
            local_path=str(image_path.resolve()),
            public_url=public_url,
            source="gemini-cache",
            source_url="",
            image_url=public_url,
            author=None,
            license_name="AI generated",
        )
        logger.info("Migrated cached Gemini image to JPEG. prompt=%s file=%s", image_prompt, image_path.name)
        return

    try:
        image_bytes = await generate_slide_image(image_prompt)
        image_path.write_bytes(_optimize_slide_image(image_bytes))
        slide.resolved_image = ResolvedImageAsset(
            local_path=str(image_path.resolve()),
            public_url=public_url,
            source="gemini-2.5-flash-image",
            source_url="",
            image_url=public_url,
            author=None,
            license_name="AI generated",
        )
        logger.info("Generated Gemini slide image. prompt=%s file=%s", image_prompt, image_path.name)
    except GeminiImageGenerationError as exc:
        logger.warning("Gemini image generation failed for prompt=%s error=%s", image_prompt, exc)


async def enrich_presentation_images(presentation: Presentation) -> Presentation:
    if not is_image_generation_enabled():
        logger.info("Global image generation switch is off. Skipping all Gemini image calls.")
        return presentation

    image_slides = [
        slide
        for slide in presentation.slides
        if getattr(slide, "image_prompt", None)
        and getattr(slide, "type", None) in {
            SlideType.TITLE_BULLETS_IMAGE,
            SlideType.HERO_IMAGE,
        }
    ]
    for slide in image_slides:
        await _resolve_one_slide_image(slide, presentation.theme)
    return presentation


def build_image_context(slide: Any) -> dict[str, Any] | None:
    image_prompt = getattr(slide, "image_prompt", None)
    if not image_prompt:
        return None

    resolved = getattr(slide, "resolved_image", None)
    render_src = Path(resolved.local_path).resolve().as_uri() if resolved else None
    return {
        "query": image_prompt,
        "role": getattr(slide, "type", "hero_image"),
        "status": "resolved" if resolved else "missing",
        "src": resolved.public_url if resolved else None,
        "render_src": render_src,
        "alt": image_prompt,
        "source": resolved.source if resolved else None,
        "license_name": resolved.license_name if resolved else None,
        "warnings": [],
    }
