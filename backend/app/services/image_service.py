import asyncio
import logging
import os
from pathlib import Path
import re
from typing import Any

from app.image_research.core.researcher import ImageResearcher
from app.image_research.core.search_planner import compact_search_query
from app.image_research.core.source_selector import _named_entity_candidates
from app.image_research.schemas import ImageResearchRequest, SelectedImage
from app.schemas.presentation import ImageClass, ImageSource, Presentation, ResolvedImageAsset, SlideType
from app.services.gemini_service import (
    GeminiImageGenerationError,
    build_image_cache_key,
    english_visual_search_phrase,
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


def _research_image_class(slide: Any, prompt: str, context_text: str) -> str:
    explicit = getattr(getattr(slide, "image_class", None), "value", getattr(slide, "image_class", None))
    text = " ".join([prompt, context_text, str(getattr(slide, "image_prompt", "") or "")]).lower()
    if any(term in text for term in ("dna", "rna", "base pairs", "double helix", "nucleotide", "molecule", "structure")):
        return ImageClass.DIAGRAM.value
    if explicit in {item.value for item in ImageClass}:
        return explicit
    inferred = _infer_research_image_type(text)
    if inferred in {ImageClass.DIAGRAM.value, ImageClass.ICON.value, ImageClass.ILLUSTRATION.value}:
        return inferred
    return ImageClass.PHOTO.value


def _extract_scene_from_image_prompt(prompt: str) -> str:
    text = " ".join(prompt.split())
    match = re.search(r"Presentation visual for ['\"]([^'\"]+)['\"]:\s*(.+)", text, flags=re.I)
    if match:
        text = match.group(2)
    text = re.split(r"\bKeep it\b|\bMatch a\b|\bNo visible\b|\bNo text\b", text, maxsplit=1, flags=re.I)[0]
    if re.search(r"\b(illustration|diagram|icon|vector|drawing|cross[- ]section|anatomy)\b", text, flags=re.I):
        return ""
    text = re.sub(r"\b(grounded|relevant|restrained|modern|clean|editorial|cinematic|professional)\b", " ", text, flags=re.I)
    return " ".join(text.split(" ,.:;"))[:220].strip()


def _slide_concept_terms(title: str, bullets: list[str]) -> str:
    combined = " ".join([title, *bullets]).lower()
    concept_rules = [
        (("population", "growth", "demographic"), "population health"),
        (("drug", "dosage", "absorption", "pharmacology"), "drug dosage"),
        (("disease", "spread", "epidemic", "infection"), "disease spread"),
        (("cells", "biology", "lab", "laboratory"), "cell biology"),
        (("bridge", "structural", "construction"), "structural engineering"),
        (("fluid", "dynamics", "mechanics"), "fluid dynamics"),
        (("machine learning", "algorithm", "model"), "machine learning"),
        (("network", "routing", "systems"), "computer networks"),
        (("climate", "weather", "environment"), "climate research"),
        (("students", "classroom", "learning"), "classroom learning"),
    ]
    matched: list[str] = []
    for terms, label in concept_rules:
        if any(term in combined for term in terms):
            matched.append(label)
    return " ".join(matched[:2]).strip()


def _domain_signal_counts(title: str, bullets: list[str], prompt: str) -> dict[str, int]:
    english_text = english_visual_search_phrase(title, *bullets, prompt, limit_words=18, max_length=180)
    text = " ".join([title, *bullets, prompt, english_text]).lower()
    domain_rules = {
        "medical": ("disease", "drug", "dosage", "health", "medical", "patient", "population", "epidemic", "cells", "biology", "pharmacology", "laboratory"),
        "engineering": ("engineering", "bridge", "structural", "fluid", "design", "construction", "manufacturing", "mechanics"),
        "technology": ("machine learning", "data", "algorithm", "network", "software", "computer", "code", "analytics", "digital", "ai"),
        "environment": ("climate", "weather", "environment", "energy", "solar", "wind", "sustainability"),
        "education": ("education", "students", "classroom", "teacher", "school", "learning"),
    }
    return {
        domain: sum(1 for term in terms if term in text)
        for domain, terms in domain_rules.items()
    }


def _primary_scene_profile(title: str, bullets: list[str], prompt: str) -> tuple[str, tuple[str, ...]]:
    scores = _domain_signal_counts(title, bullets, prompt)
    if not any(scores.values()):
        return "", ()

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    domain, score = ordered[0]
    if score <= 0:
        return "", ()

    if domain == "medical":
        return "medical researcher in laboratory", ("medical", "research", "laboratory", "public health", "drug")
    if domain == "engineering":
        return "engineer reviewing technical design", ("engineering", "structural", "design", "mechanics", "industrial")
    if domain == "technology":
        return "data analyst at computer monitors", ("data", "analytics", "software", "machine learning", "technology")
    if domain == "environment":
        return "environmental research team", ("climate", "environment", "energy", "sustainability", "research")
    if domain == "education":
        return "students in classroom with laptop", ("education", "students", "classroom", "learning", "school")
    return "", ()


def _photo_scene_hint(title: str, bullets: list[str], prompt: str) -> str:
    scene, _ = _primary_scene_profile(title, bullets, prompt)
    return scene


def _domain_concept_terms(title: str, bullets: list[str], prompt: str) -> str:
    _, preferred_terms = _primary_scene_profile(title, bullets, prompt)
    if not preferred_terms:
        return _slide_concept_terms(title, bullets)

    text = " ".join([title, *bullets, prompt]).lower()
    matched = [term for term in preferred_terms if term in text]
    if matched:
        return " ".join(matched[:2]).strip()

    return ""


def _english_keyword_phrase(*parts: str, limit_words: int = 5, max_length: int = 40, exclude: set[str] | None = None) -> str:
    phrase = english_visual_search_phrase(*parts, limit_words=limit_words + 3, max_length=max_length + 24)
    if not phrase:
        return ""
    exclude = {item.lower() for item in (exclude or set())}
    words: list[str] = []
    seen: set[str] = set()
    for word in re.findall(r"[A-Za-z][A-Za-z0-9&'+-]*", phrase):
        key = word.lower()
        if key in exclude or key in seen:
            continue
        seen.add(key)
        words.append(word)
        if len(words) >= limit_words:
            break
    return compact_search_query(" ".join(words), max_length=max_length) if words else ""


def _presentation_entity(presentation_title: str) -> str:
    candidates = _named_entity_candidates(presentation_title)
    return candidates[0] if candidates else ""


def _english_entity_query(entity: str) -> str:
    return english_visual_search_phrase(entity, limit_words=4, max_length=42) or entity


def _slide_mentions_entity(entity: str, title: str, bullets: list[str]) -> bool:
    if not entity:
        return False
    text = " ".join([title, *bullets]).lower()
    tokens = [token.lower() for token in re.findall(r"[^\W\d_]+", entity, flags=re.UNICODE)]
    if not tokens:
        return False
    surname = tokens[-1]
    return entity.lower() in text or surname in text


def _research_prompt(slide: Any, presentation_title: str) -> str:
    title = (getattr(slide, "title", None) or "").strip()
    prompt = (getattr(slide, "image_prompt", None) or "").strip()
    bullets = [str(item).strip() for item in (getattr(slide, "bullets", None) or []) if str(item).strip()]
    english_subject = english_visual_search_phrase(prompt, title, presentation_title, *bullets[:2], limit_words=8, max_length=72)
    lower_subject = english_subject.lower()
    lower_slide = " ".join([title, prompt, presentation_title, *bullets[:4]]).lower()
    if "dna" in lower_subject:
        if any(term in lower_subject for term in ("adenine", "thymine", "guanine", "cytosine", "hydrogen")):
            return "DNA base pairs"
        if "structure" in lower_subject or "double helix" in lower_subject:
            return "DNA double helix"
        return "DNA"
    if "rna" in lower_subject:
        if any(term in lower_slide for term in ("vaccine", "vaccines", "medicine", "therapy", "therapies", "therapeutic")):
            return "mRNA vaccine"
        if any(term in lower_slide for term in ("gene editing", "crispr")):
            return "guide RNA CRISPR"
        if any(term in lower_slide for term in ("rrna", "ribosomal", "ribosome", "protein assembly", "protein production")):
            return "ribosome structure"
        if any(term in lower_slide for term in ("trna", "transfer rna", "protein builder")):
            return "transfer RNA ribosome"
        if any(term in lower_slide for term in ("transcription", "rna polymerase")):
            return "RNA transcription"
        if any(term in lower_slide for term in ("mirna", "sirna", "microrna", "gene regulation", "regulatory")):
            return "microRNA gene regulation"
        return "RNA molecule"

    deck_entity = _presentation_entity(presentation_title)
    local_entity_candidates = _named_entity_candidates(" | ".join([title, *bullets[:2]]))
    entity = local_entity_candidates[0] if local_entity_candidates else (deck_entity if _slide_mentions_entity(deck_entity, title, bullets) else "")

    if entity:
        entity_tokens = {token.lower() for token in re.findall(r"[^\W\d_]+", entity, flags=re.UNICODE)}
        english_entity = _english_entity_query(entity)
        qualifier = _english_keyword_phrase(title, *bullets[:2], prompt, limit_words=2, max_length=20, exclude=entity_tokens)
        query = f"{english_entity} {qualifier}".strip() if qualifier and qualifier.lower() not in english_entity.lower() else english_entity
        return compact_search_query(query, max_length=30)

    concept_terms = _domain_concept_terms(title, bullets, prompt)
    keyword_subject = _english_keyword_phrase(prompt, title, *bullets[:3], limit_words=5, max_length=32)
    scene_hint = _photo_scene_hint(title, bullets, prompt)
    prompt_scene = compact_search_query(_extract_scene_from_image_prompt(prompt), max_length=24) if prompt else ""
    prompt_scene = prompt_scene if prompt_scene and prompt_scene.lower() not in {"classroom", "learning", "students"} else ""

    for candidate in (keyword_subject, prompt_scene, concept_terms, scene_hint):
        if candidate:
            english_candidate = _english_keyword_phrase(candidate, limit_words=5, max_length=32) or candidate
            return compact_search_query(english_candidate, max_length=32)
    return ""


def _research_context(slide: Any, presentation_title: str) -> str:
    title = (getattr(slide, "title", None) or "").strip()
    subtitle = (getattr(slide, "subtitle", None) or "").strip()
    bullets = [str(item).strip() for item in (getattr(slide, "bullets", None) or []) if str(item).strip()]
    parts = [title, subtitle, *bullets[:3]]
    deck_entity = _presentation_entity(presentation_title)
    if _slide_mentions_entity(deck_entity, title, bullets):
        parts.append(deck_entity)
    return english_visual_search_phrase(*parts, presentation_title, limit_words=16, max_length=140)


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
    context_text = _research_context(slide, presentation_title)
    if not prompt:
        return
    image_class = _research_image_class(slide, prompt, context_text)
    logger.info(
        "Prepared research prompt. slide_title=%r context=%r prompt=%r image_class=%s image_prompt=%r context_ascii=%s prompt_ascii=%s",
        getattr(slide, "title", None),
        context_text,
        prompt,
        image_class,
        getattr(slide, "image_prompt", None),
        context_text.isascii() if context_text else True,
        prompt.isascii(),
    )

    try:
        response = await _get_image_researcher().research(
            ImageResearchRequest(
                prompt=prompt,
                context_text=context_text,
                style=style,
                preferred_orientation="landscape",
                image_type=image_class,
                image_class=image_class,
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
            if image_source == ImageSource.UNSPLASH:
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
