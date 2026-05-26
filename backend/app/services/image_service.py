import logging
from pathlib import Path
from typing import Any

from app.schemas.presentation import Presentation, ResolvedImageAsset, SlideType
from app.services.feature_flags import is_image_generation_enabled
from app.services.gemini_service import (
    GeminiImageGenerationError,
    build_image_cache_key,
    generate_slide_image,
)
from app.services.image_optimizer import ImageOptimizationError, optimize_image_bytes


logger = logging.getLogger(__name__)
GENERATED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated" / "gemini_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def _resolve_one_slide_image(slide: Any, style: str) -> None:
    image_prompt = getattr(slide, "image_prompt", None)
    if not image_prompt:
        return

    cache_key = build_image_cache_key(slide, style)
    public_key = f"gemini-{cache_key}"

    try:
        image_bytes = await generate_slide_image(image_prompt)
        optimized = optimize_image_bytes(image_bytes, cache_key=public_key)
        slide.resolved_image = ResolvedImageAsset(
            local_path=str(optimized.path.resolve()),
            public_url=f"/generated/optimized_images/{optimized.path.name}",
            source="gemini-2.5-flash-image",
            source_url="",
            image_url=f"/generated/optimized_images/{optimized.path.name}",
            author=None,
            license_name="AI generated",
        )
        logger.info("Generated Gemini slide image. prompt=%s file=%s", image_prompt, optimized.path.name)
    except (GeminiImageGenerationError, ImageOptimizationError) as exc:
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
