import asyncio
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.presentation import Presentation, Slide, SlideType, StatisticItem, ThemeName, TimelineStep
from app.services.theme_registry import resolve_theme_name


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)
logger = logging.getLogger(__name__)


class GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    gemini_api_key: str
    gemini_planning_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"


class GeminiServiceError(Exception):
    pass


class GeminiConfigurationError(GeminiServiceError):
    pass


class GeminiPlanningError(GeminiServiceError):
    pass


class GeminiImageGenerationError(GeminiServiceError):
    pass


class GeminiTimelineStep(BaseModel):
    label: str
    detail: str | None = None


class GeminiStatisticItem(BaseModel):
    label: str
    value: str
    detail: str | None = None


class GeminiSlidePlan(BaseModel):
    id: str | None = None
    type: str
    title: str | None = None
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list)
    image_prompt: str | None = None
    notes: str | None = None
    left_title: str | None = None
    right_title: str | None = None
    left_bullets: list[str] = Field(default_factory=list)
    right_bullets: list[str] = Field(default_factory=list)
    timeline: list[GeminiTimelineStep] = Field(default_factory=list)
    statistics: list[GeminiStatisticItem] = Field(default_factory=list)
    quote: str | None = None
    attribution: str | None = None


class GeminiPresentationPlan(BaseModel):
    title: str
    theme: str = ThemeName.MODERN_DARK.value
    slides: list[GeminiSlidePlan] = Field(default_factory=list)


GEMINI_PLANNING_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "theme": {"type": "string"},
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "image_prompt": {"type": "string"},
                    "notes": {"type": "string"},
                    "left_title": {"type": "string"},
                    "right_title": {"type": "string"},
                    "left_bullets": {"type": "array", "items": {"type": "string"}},
                    "right_bullets": {"type": "array", "items": {"type": "string"}},
                    "timeline": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "label": {"type": "string"},
                                "detail": {"type": ["string", "null"]},
                            },
                            "required": ["label"],
                        },
                    },
                    "statistics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "string"},
                                "detail": {"type": ["string", "null"]},
                            },
                            "required": ["label", "value"],
                        },
                    },
                    "quote": {"type": "string"},
                    "attribution": {"type": "string"},
                },
                "required": ["type"],
            },
        },
    },
    "required": ["title", "slides"],
}


SYSTEM_PROMPT = """
You create structured content plans for a presentation generator.
Return valid JSON only.
No markdown. No prose. No code fences.

Rules:
- Output must match the provided JSON schema exactly.
- Allowed themes: modern_dark, modern_light, editorial, corporate, playful.
- Choose a theme name from the allowed theme registry.
- Choose slide types from: title_slide, title_bullets, title_bullets_image, hero_image, comparison, timeline, statistics, quote.
- Never generate HTML, CSS, inline styles, positioning, spacing, colors, or fonts.
- Keep slide content concise and presentation-ready.
- Use image_prompt only for illustrations, hero images, diagrams, or backgrounds.
- Avoid visible text in generated images unless absolutely necessary.
""".strip()


def _provider_message(exc: Exception) -> str:
    message = str(exc).strip() or "Unknown Gemini error."
    lower = message.lower()
    if "api key" in lower or "authentication" in lower or "permission" in lower:
        return "Gemini API authentication failed. Check GEMINI_API_KEY."
    if "quota" in lower or "429" in lower or "resource_exhausted" in lower:
        return "Gemini quota or rate limit reached. Please try again later."
    return message


@lru_cache(maxsize=1)
def get_settings() -> GeminiSettings:
    try:
        return GeminiSettings()
    except ValidationError as exc:
        raise GeminiConfigurationError(
            f"Missing backend configuration. Create {ENV_FILE} and set GEMINI_API_KEY."
        ) from exc


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _normalize_bullets(values: list[str], limit: int, fallback: list[str]) -> list[str]:
    cleaned = [item.strip(" -") for item in values if isinstance(item, str) and item.strip()]
    if cleaned:
        return cleaned[:limit]
    return fallback[:limit]


def _trim_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _normalize_timeline(steps: list[GeminiTimelineStep]) -> list[GeminiTimelineStep]:
    if steps:
        return steps[:6]
    return [
        GeminiTimelineStep(label="Phase 1", detail="Define the problem and audience."),
        GeminiTimelineStep(label="Phase 2", detail="Build the core message and structure."),
    ]


def _normalize_statistics(items: list[GeminiStatisticItem]) -> list[GeminiStatisticItem]:
    if items:
        return items[:4]
    return [GeminiStatisticItem(label="Impact", value="3x", detail="Faster turnaround")]


def _resolve_slide_type(raw_type: str) -> SlideType:
    value = raw_type.strip().lower()
    aliases = {
        "title": SlideType.TITLE_SLIDE,
        "bullets": SlideType.TITLE_BULLETS,
        "bullets_with_image": SlideType.TITLE_BULLETS_IMAGE,
        "image_focus": SlideType.HERO_IMAGE,
        "conclusion": SlideType.QUOTE,
    }
    if value in aliases:
        return aliases[value]
    try:
        return SlideType(value)
    except ValueError:
        return SlideType.TITLE_BULLETS


def _normalize_slide_plan(slide: GeminiSlidePlan, presentation_title: str, index: int) -> GeminiSlidePlan:
    slide = GeminiSlidePlan.model_validate(slide.model_dump())
    slide.id = slide.id or f"slide_{index}"
    slide.type = _resolve_slide_type(slide.type).value

    if slide.type == SlideType.TITLE_SLIDE.value:
        slide.title = slide.title or presentation_title
        slide.subtitle = slide.subtitle or "Presentation overview"
        slide.bullets = []
        slide.image_prompt = None
    elif slide.type == SlideType.TITLE_BULLETS.value:
        slide.title = slide.title or "Key ideas"
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=6,
            fallback=["Core idea", "Supporting detail", "Practical takeaway"],
        )
    elif slide.type == SlideType.TITLE_BULLETS_IMAGE.value:
        slide.title = slide.title or "Key ideas"
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=5,
            fallback=["Core idea", "Supporting detail", "Practical takeaway"],
        )
        slide.image_prompt = slide.image_prompt or f"Modern presentation illustration for {slide.title}"
    elif slide.type == SlideType.HERO_IMAGE.value:
        slide.title = slide.title or "Visual focus"
        slide.image_prompt = slide.image_prompt or f"Modern presentation hero image for {slide.title}"
        slide.subtitle = slide.subtitle or ""
    elif slide.type == SlideType.COMPARISON.value:
        slide.title = slide.title or "Comparison"
        slide.left_title = slide.left_title or "Option A"
        slide.right_title = slide.right_title or "Option B"
        slide.left_bullets = _normalize_bullets(
            slide.left_bullets,
            limit=4,
            fallback=["Strong points", "Good fit"],
        )
        slide.right_bullets = _normalize_bullets(
            slide.right_bullets,
            limit=4,
            fallback=["Tradeoffs", "Considerations"],
        )
    elif slide.type == SlideType.TIMELINE.value:
        slide.title = slide.title or "Timeline"
        slide.timeline = _normalize_timeline(slide.timeline)
    elif slide.type == SlideType.STATISTICS.value:
        slide.title = slide.title or "Statistics"
        slide.statistics = _normalize_statistics(slide.statistics)
    elif slide.type == SlideType.QUOTE.value:
        slide.title = _trim_text(slide.title, 140) or "Closing thought"
        slide.quote = _trim_text(slide.quote, 260) or "Keep the message focused and repeat the core idea."
        slide.attribution = _trim_text(slide.attribution, 140) or _trim_text(presentation_title, 140)

    return slide


def _normalize_plan(plan: GeminiPresentationPlan, slide_count: int) -> GeminiPresentationPlan:
    slides = list(plan.slides[:slide_count])

    if not slides:
        slides = [
            GeminiSlidePlan(type=SlideType.TITLE_SLIDE.value, title=plan.title, subtitle="Presentation overview"),
            GeminiSlidePlan(
                type=SlideType.TITLE_BULLETS.value,
                title="Key ideas",
                bullets=["Core idea", "Supporting detail", "Practical takeaway"],
            ),
            GeminiSlidePlan(
                type=SlideType.QUOTE.value,
                title="Wrap-up",
                quote="Focus on the clearest next action.",
                attribution=plan.title,
            ),
        ]

    if _resolve_slide_type(slides[0].type) != SlideType.TITLE_SLIDE:
        slides.insert(0, GeminiSlidePlan(type=SlideType.TITLE_SLIDE.value, title=plan.title, subtitle="Presentation overview"))

    while len(slides) < slide_count:
        slides.append(
            GeminiSlidePlan(
                type=SlideType.TITLE_BULLETS.value,
                title=f"Supporting idea {len(slides)}",
                bullets=["Core idea", "Practical implication", "Why it matters"],
            )
        )

    slides = slides[:slide_count]
    normalized_slides = [
        _normalize_slide_plan(slide, plan.title, index + 1)
        for index, slide in enumerate(slides)
    ]
    return GeminiPresentationPlan(
        title=plan.title,
        theme=resolve_theme_name(plan.theme),
        slides=normalized_slides,
    )


def _plan_to_presentation(plan: GeminiPresentationPlan) -> Presentation:
    slides = [Slide.model_validate(slide.model_dump()) for slide in plan.slides]
    return Presentation(
        title=plan.title,
        theme=resolve_theme_name(plan.theme),
        slides=slides,
    )


def _extract_json_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        parts = getattr(candidates[0].content, "parts", []) or []
        text_parts = [part.text for part in parts if getattr(part, "text", None)]
        if text_parts:
            return "".join(text_parts)
    raise GeminiPlanningError("Gemini returned an empty planning response.")


def _extract_image_bytes(response: Any) -> bytes:
    parts = list(getattr(response, "parts", None) or [])
    if not parts:
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            parts = list(getattr(candidates[0].content, "parts", []) or [])

    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is None:
            continue
        data = getattr(inline_data, "data", None)
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("latin1")
    raise GeminiImageGenerationError("Gemini did not return image bytes.")


async def generate_presentation(prompt: str, slide_count: int, style: str) -> Presentation:
    settings = get_settings()
    client = get_client()
    logger.info(
        "Gemini planning request starting. model=%s slide_count=%s style=%s prompt_chars=%s",
        settings.gemini_planning_model,
        slide_count,
        style,
        len(prompt),
    )

    user_prompt = f"""
Create a {slide_count}-slide presentation plan.

Preferred direction:
{style}

Select a theme name from the registry, but do not describe colors, spacing, fonts, or CSS.

Topic:
{prompt}

Return JSON only.
""".strip()

    try:
        # Structured output keeps the MVP stable by asking Gemini for JSON that
        # already matches the planning schema instead of free-form text.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_planning_model,
            contents=user_prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": GEMINI_PLANNING_JSON_SCHEMA,
                "temperature": 0.3,
            },
        )
    except Exception as exc:
        raise GeminiPlanningError(_provider_message(exc)) from exc

    try:
        plan = GeminiPresentationPlan.model_validate_json(_extract_json_text(response))
    except (ValidationError, json.JSONDecodeError, GeminiPlanningError) as exc:
        logger.exception("Gemini planning returned invalid JSON.")
        raise GeminiPlanningError("Gemini returned invalid presentation JSON.") from exc

    normalized_plan = _normalize_plan(plan, slide_count)
    presentation = _plan_to_presentation(normalized_plan)
    logger.info(
        "Gemini planning complete. title=%s slides=%s types=%s theme=%s",
        presentation.title,
        len(presentation.slides),
        [slide.type.value for slide in presentation.slides],
        presentation.theme,
    )
    return presentation


def build_image_cache_key(slide: Any, style: str) -> str:
    payload = {
        "style": style,
        "type": getattr(slide, "type", ""),
        "title": getattr(slide, "title", ""),
        "bullets": getattr(slide, "bullets", []),
        "subtitle": getattr(slide, "subtitle", ""),
        "left_title": getattr(slide, "left_title", ""),
        "right_title": getattr(slide, "right_title", ""),
        "left_bullets": getattr(slide, "left_bullets", []),
        "right_bullets": getattr(slide, "right_bullets", []),
        "timeline": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in getattr(slide, "timeline", [])],
        "statistics": [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in getattr(slide, "statistics", [])],
        "quote": getattr(slide, "quote", ""),
        "image_prompt": getattr(slide, "image_prompt", ""),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:24]


async def generate_slide_image(prompt: str) -> bytes:
    settings = get_settings()
    client = get_client()
    final_prompt = (
        "Create a clean, modern, presentation-ready image for a slide deck. "
        "Use a 16:9 composition. Avoid messy text. "
        f"Prompt: {prompt}"
    )

    try:
        # The image model is isolated from planning so image failures do not
        # corrupt the slide JSON generation step.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_image_model,
            contents=[final_prompt],
            config={
                "response_modalities": ["IMAGE"],
                "response_format": {"image": {"aspect_ratio": "16:9"}},
            },
        )
        return _extract_image_bytes(response)
    except GeminiImageGenerationError:
        raise
    except Exception as exc:
        raise GeminiImageGenerationError(_provider_message(exc)) from exc
