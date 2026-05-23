import logging
from pathlib import Path
from typing import Any

from app.schemas.presentation import ImageSpec, Presentation, ResolvedImageAsset
from app.services.gemini_service import (
    GeminiImageGenerationError,
    build_image_cache_key,
    generate_slide_image,
)


logger = logging.getLogger(__name__)
GENERATED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated" / "gemini_images"
GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def _resolve_one_slide_image(slide: Any, style: str) -> None:
    image = getattr(slide, "image", None)
    if image is None:
        return

    cache_key = build_image_cache_key(slide, style)
    image_path = GENERATED_IMAGES_DIR / f"{cache_key}.png"
    public_url = f"/generated/gemini_images/{image_path.name}"

    if image_path.exists():
        # Reuse the existing file whenever the slide content and image prompt
        # hash to the same cache key.
        image.resolved_image = ResolvedImageAsset(
            local_path=str(image_path.resolve()),
            public_url=public_url,
            source="gemini-cache",
            source_url="",
            image_url=public_url,
            author=None,
            license_name="AI generated",
        )
        image.research_warnings = ["Reused cached Gemini image."]
        logger.info("Reused cached Gemini image. prompt=%s file=%s", image.query, image_path.name)
        return

    try:
        image_bytes = await generate_slide_image(image.query)
        image_path.write_bytes(image_bytes)
        image.resolved_image = ResolvedImageAsset(
            local_path=str(image_path.resolve()),
            public_url=public_url,
            source="gemini-2.5-flash-image",
            source_url="",
            image_url=public_url,
            author=None,
            license_name="AI generated",
        )
        image.research_warnings = []
        logger.info("Generated Gemini slide image. prompt=%s file=%s", image.query, image_path.name)
    except GeminiImageGenerationError as exc:
        image.research_warnings = [str(exc)]
        logger.warning("Gemini image generation failed for prompt=%s error=%s", image.query, exc)


async def enrich_presentation_images(presentation: Presentation) -> Presentation:
    image_slides = [slide for slide in presentation.slides if getattr(slide, "image", None) is not None]
    for slide in image_slides:
        await _resolve_one_slide_image(slide, presentation.theme.style)
    return presentation


def build_image_context(image: ImageSpec | None) -> dict[str, Any] | None:
    if image is None:
        return None

    resolved = image.resolved_image
    render_src = Path(resolved.local_path).resolve().as_uri() if resolved else None
    return {
        "query": image.query,
        "role": image.role.value,
        "remove_background": image.remove_background,
        "status": "resolved" if resolved else "missing",
        "src": resolved.public_url if resolved else None,
        "render_src": render_src,
        "alt": image.query,
        "source": resolved.source if resolved else None,
        "license_name": resolved.license_name if resolved else None,
        "warnings": image.research_warnings,
    }
