import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from app.image_research.core.researcher import ImageResearcher
from app.image_research.schemas import ImageResearchRequest, SelectedImage
from app.schemas.presentation import ImageClass, ImageSource, Presentation, ResolvedImageAsset, SlideType
from app.services.gemini_service import (
    GeminiImageGenerationError,
    build_image_cache_key,
    generate_slide_image,
    get_image_model_name,
)
from app.services.image_optimizer import ImageOptimizationError, optimize_image_bytes, optimize_image_file


logger = logging.getLogger(__name__)
_image_researcher: ImageResearcher | None = None


class ImageResearchResolutionError(Exception):
    pass


def _get_image_researcher() -> ImageResearcher:
    global _image_researcher
    if _image_researcher is None:
        _image_researcher = ImageResearcher()
    return _image_researcher


def _image_slides(presentation: Presentation) -> list[Any]:
    return [
        slide
        for slide in presentation.slides
        if getattr(slide, "image_prompt", None)
        and getattr(slide, "type", None) in {
            SlideType.TITLE_BULLETS_IMAGE,
            SlideType.HERO_IMAGE,
        }
    ]


def _infer_research_image_type(prompt: str) -> str:
    text = prompt.lower()
    if any(term in text for term in ("diagram", "chart", "schema", "flow", "map", "timeline")):
        return "diagram"
    if any(term in text for term in ("icon", "symbol", "logo")):
        return "icon"
    if any(term in text for term in ("illustration", "vector", "drawing")):
        return "illustration"
    return "any"


def _research_prompt(slide: Any, presentation_title: str) -> str:
    title = (getattr(slide, "title", None) or "").strip()
    prompt = (getattr(slide, "image_prompt", None) or "").strip()
    mood = (getattr(slide, "visual_mood", None) or "").strip()
    bullets = [str(item).strip() for item in (getattr(slide, "bullets", None) or []) if str(item).strip()]
    context = " ".join([presentation_title, title, *bullets, prompt]).lower()
    intent = ""
    if any(term in context for term in ("series", "movie", "film", "episode", "character", "cast", "show")):
        intent = "official still"
    elif any(term in context for term in ("place", "town", "location", "building", "object", "artifact")):
        intent = "official image"
    parts = [title, presentation_title, *bullets[:2], prompt, mood, intent]
    unique: list[str] = []
    for part in parts:
        cleaned = " ".join(part.split()).rstrip(" .,:;")
        if cleaned and cleaned.lower() not in {value.lower() for value in unique}:
            unique.append(cleaned)
    return ". ".join(unique)[:500]


def _resolved_from_research_image(
    selected: SelectedImage,
    optimized_path: Path,
    width: int | None,
    height: int | None,
) -> ResolvedImageAsset:
    return ResolvedImageAsset(
        local_path=str(optimized_path.resolve()),
        public_url=f"/generated/optimized_images/{optimized_path.name}",
        source=selected.source,
        source_url=selected.source_url,
        image_url=selected.image_url,
        author=selected.author,
        license_name=selected.license_name,
        image_class=ImageClass(selected.image_class),
        width=width or selected.width,
        height=height or selected.height,
        clip_score=selected.clip_score,
        final_score=selected.final_score,
    )


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
            source=get_image_model_name(),
            source_url="",
            image_url=f"/generated/optimized_images/{optimized.path.name}",
            author=None,
            license_name="AI generated",
            image_class=getattr(slide, "image_class", None),
            width=optimized.width,
            height=optimized.height,
        )
        logger.info("Generated Gemini slide image. prompt=%s file=%s", image_prompt, optimized.path.name)
    except (GeminiImageGenerationError, ImageOptimizationError) as exc:
        logger.warning("Gemini image generation failed for prompt=%s error=%s", image_prompt, exc)
        raise GeminiImageGenerationError(f"{image_prompt}: {exc}") from exc


async def _resolve_one_research_image(
    slide: Any,
    presentation_title: str,
    style: str,
    used_source_urls: set[str],
    used_hashes: set[str],
) -> None:
    prompt = _research_prompt(slide, presentation_title)
    if not prompt:
        return

    try:
        response = await _get_image_researcher().research(
            ImageResearchRequest(
                prompt=prompt,
                style=style,
                preferred_orientation="landscape",
                image_type=_infer_research_image_type(prompt),
                image_class=(getattr(slide, "image_class", None) or _infer_research_image_type(prompt)),
                max_candidates=1,
                exclude_source_urls=sorted(used_source_urls),
                exclude_hashes=sorted(used_hashes),
            )
        )
        selected = response.selected_image
        if not selected:
            raise ImageResearchResolutionError("; ".join(response.warnings[:3]) or "No matching image found.")

        cache_key = f"research-{build_image_cache_key(slide, style)}"
        optimized = optimize_image_file(Path(selected.local_path), cache_key=cache_key)
        slide.resolved_image = _resolved_from_research_image(
            selected,
            optimized.path,
            optimized.width,
            optimized.height,
        )
        used_source_urls.add(selected.source_url)
        if selected.content_hash:
            used_hashes.add(selected.content_hash)
        logger.info(
            "Resolved researched slide image. prompt=%s source=%s file=%s",
            prompt,
            selected.source,
            optimized.path.name,
        )
    except (ImageResearchResolutionError, ImageOptimizationError) as exc:
        logger.warning("Image research failed for prompt=%s error=%s", prompt, exc)
        raise ImageResearchResolutionError(f"{prompt}: {exc}") from exc


async def enrich_presentation_images(
    presentation: Presentation,
    image_source: ImageSource = ImageSource.GEMINI,
) -> Presentation:
    image_slides = _image_slides(presentation)
    logger.info(
        "Image enrichment starting. image_slide_count=%s source=%s model=%s",
        len(image_slides),
        image_source.value,
        get_image_model_name(),
    )

    failures: list[str] = []
    used_source_urls: set[str] = set()
    used_hashes: set[str] = set()
    async def resolve(slide: Any) -> None:
        try:
            if image_source == ImageSource.IMAGE_RESEARCH:
                await _resolve_one_research_image(slide, presentation.title, presentation.theme, used_source_urls, used_hashes)
            else:
                await _resolve_one_slide_image(slide, presentation.theme)
        except (GeminiImageGenerationError, ImageResearchResolutionError) as exc:
            failures.append(str(exc))

    if image_source == ImageSource.GEMINI:
        concurrency = max(1, int(os.getenv("GEMINI_IMAGE_CONCURRENCY", "3")))
        semaphore = asyncio.Semaphore(concurrency)

        async def resolve_gemini(slide: Any) -> None:
            async with semaphore:
                await resolve(slide)

        await asyncio.gather(*(resolve_gemini(slide) for slide in image_slides))
    else:
        for slide in image_slides:
            await resolve(slide)

    if failures:
        logger.warning(
            "Image enrichment completed with unresolved slides. source=%s unresolved=%s errors=%s",
            image_source.value,
            len(failures),
            " | ".join(failures[:3]),
        )

    logger.info("Image enrichment complete. resolved_images=%s", sum(1 for slide in image_slides if slide.resolved_image))
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
        "image_class": getattr(getattr(slide, "image_class", None), "value", getattr(slide, "image_class", None)),
        "status": "resolved" if resolved else "missing",
        "src": resolved.public_url if resolved else None,
        "render_src": render_src,
        "alt": image_prompt,
        "source": resolved.source if resolved else None,
        "license_name": resolved.license_name if resolved else None,
        "warnings": [],
    }
