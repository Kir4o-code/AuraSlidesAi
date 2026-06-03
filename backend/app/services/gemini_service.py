import asyncio
import base64
import hashlib
import json
import logging
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.image_research.core.image_classes import CLASS_KEYWORDS, ImageClass, infer_image_class
from app.schemas.presentation import GuidedSlideIntent, PlanningMode, Presentation, Slide, SlideType, StatisticItem, ThemeName, TimelineStep
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
    gemini_planning_timeout_seconds: int = 45
    gemini_image_timeout_seconds: int = 90
    enable_image_generation: bool = Field(default=True, validation_alias="IMAGE_GEN_SWITCH")


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
    image_class: str | None = None
    visual_mood: str | None = None
    icon_intent: str | None = None
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
    theme: str = ThemeName.MODERN_DARK_TECH.value
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
                    "image_class": {"type": "string"},
                    "visual_mood": {"type": "string"},
                    "icon_intent": {"type": "string"},
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
You are an expert presentation consultant that creates structured, HIGHLY CONCISE content plans.
Return valid JSON only. No markdown, no prose, no code fences.

CRITICAL RULES:
1. SLIDE COUNT: Use EXACTLY the requested number of slides.
2. BREVITY: Maximum 3-4 bullet points per slide. Each bullet MUST be under 14 words. Headlines MUST be concise.
3. SPACING: Ensure content is minimal to allow for significant white space. NEVER overload a slide.
4. QUALITY: Give every slide one clear job in the narrative. Use concrete explanations, mechanisms, examples, tradeoffs, or next actions.
5. SCHEMA: Output MUST match the provided JSON schema exactly.
6. ACCURACY: Do not invent statistics, quotations, citations, or precise factual claims. If a number is not supplied or reliably known, explain the point without a number.
7. VARIETY: Do not repeat the same slide structure mechanically. Use text-only, image-backed, comparison, timeline, statistics, hero, or quote layouts only when they fit the information.
8. NO FILLER: Avoid generic phrases such as "key insights", "unlock potential", "embrace innovation", or restating the topic without adding information.
9. GUIDED MODE: When ordered slide briefs are provided, follow each brief in order. Do not insert, remove, merge, or reorder slides.
10. VOICE: Match the topic emotionally and write like a presenter with a point of view. Use tension for mysteries, curiosity for science, confidence for proposals, and warmth for personal assignments.
11. OPINION: When the request asks for favorites, recommendations, or personal judgment, choose specific examples and explain why they stand out. Avoid generic praise.
12. NARRATIVE: Give slides intentional roles such as hook, context, world or mechanism, evidence, comparison, favorite examples, personal take, and conclusion.
13. METADATA: Set visual_mood to a short topic-specific art direction and icon_intent to a short semantic concept for each non-title slide.

IMAGE PROMPT RULES (EXTREMELY IMPORTANT):
- Image prompts must feel like they belong in a polished presentation, not an AI art gallery.
- Prefer grounded editorial visuals: realistic scenes, relevant objects, clean environments, charts, product/process context, or restrained diagrams.
- Think logically about the slide: ask for the image a presenter would actually place beside that point.
- Avoid "8k", camera flex, hype words, floating icons, surreal metaphors, generic neural networks, random math symbols, and glowing abstract backgrounds.
- Do not ask for visible text, labels, captions, UI copy, or words inside the image unless the slide truly needs a simple chart-like visual.
- For sensitive topics, keep visuals respectful, realistic, and non-sensational.
- For every image-backed slide, set image_class to exactly one of: photo, diagram, illustration, icon.
- Preserve named people, characters, places, works, objects, and events inside image prompts so external image research can search precisely.
- Use photo for real people, places, objects, historical/documentary topics, or editorial visuals.
- Use diagram for explanatory structures, systems, charts, flows, anatomy, maps, and timelines.
- Use illustration for drawn/vector educational visuals that are not strict diagrams.
- Use icon only for simple symbolic marks.
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


def _http_options(timeout_seconds: int) -> types.HttpOptions:
    return types.HttpOptions(timeout=max(1, timeout_seconds) * 1000)


def _normalize_bullets(values: list[str], limit: int, fallback: list[str]) -> list[str]:
    cleaned: list[str] = [v.strip() for v in values if v and isinstance(v, str) and v.strip()]
    if cleaned:
        return cleaned[:limit]
    return fallback[:limit]


def _fallback_bullets_for_slide(title: str, presentation_title: str, *, variant: str = "default", slot: int = 0) -> list[str]:
    context = title or presentation_title or "this topic"
    templates = {
        "default": [
            [f"Overview of {context}", "Most important detail", "Recommended next step"],
            [f"Why {context} matters", "What changes", "Immediate takeaway"],
            [f"How {context} works", "Main constraint", "Best next action"],
        ],
        "image": [
            [f"Overview of {context}", "Visual reference or supporting idea", "Practical takeaway"],
            [f"Why the image matters", "What it shows", "How to use it"],
            [f"Main message", "Image support", "Next action"],
        ],
        "comparison": [
            [f"Strengths of {context}", "Tradeoffs to consider", "Best fit or next step"],
            [f"What {context} does well", "Where it falls short", "When to choose it"],
            [f"Option one", "Option two", "Recommended path"],
        ],
    }
    choices = templates.get(variant, templates["default"])
    return choices[slot % len(choices)]


def _trim_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _normalize_attribution(value: str | None, presentation_title: str | None, *, limit: int = 250) -> str | None:
    normalized = _trim_text(value, limit)
    if normalized:
        return normalized
    return _trim_text(presentation_title, limit)


def _fallback_image_prompt(title: str | None, presentation_title: str, *, slide_type: str = "supporting") -> str:
    topic = title or presentation_title or "the slide topic"
    if slide_type == SlideType.HERO_IMAGE.value:
        return f"Grounded editorial visual introducing {topic}, realistic and presentation-ready, no text."
    return f"Grounded supporting visual for {topic}, realistic or clean editorial style, no text."


def _normalize_image_prompt(raw_prompt: str | None, title: str | None, presentation_title: str, *, slide_type: str = "supporting") -> str:
    base = (raw_prompt or "").strip() or _fallback_image_prompt(title, presentation_title, slide_type=slide_type)
    if re.search(
        r"\b(neural networks?|glowing|floating|surreal|abstract|futuristic|random symbols?|ai art|conceptual visualization)\b",
        base,
        flags=re.IGNORECASE,
    ):
        base = _fallback_image_prompt(title, presentation_title, slide_type=slide_type)
    for pattern in [
        r"\b8k\b",
        r"\b4k\b",
        r"\bultra[- ]?high[- ]?resolution\b",
        r"\bhigh[- ]?resolution\b",
        r"\baward[- ]?winning\b",
        r"\btrending on artstation\b",
        r"\boctane render\b",
        r"\bhyper[- ]?realistic\b",
        r"\bfuturistic\b",
    ]:
        base = re.sub(pattern, "", base, flags=re.IGNORECASE)
    base = re.sub(r"\s+,", ",", base)
    base = re.sub(r",\s*,+", ",", base)
    base = re.sub(r"\s+", " ", base).strip(" ,.")

    topic = title or presentation_title or "this slide"
    prompt = (
        f"Presentation visual for '{topic}': {base}. "
        "Keep it grounded, relevant, and restrained. Match a clean modern deck. "
        "No visible words, labels, captions, logos, surreal symbols, or generic AI abstractions."
    )
    return prompt[:500].rstrip(" ,.")


def _normalize_image_class(value: str | None, prompt: str | None, *, default: ImageClass = ImageClass.PHOTO) -> str:
    explicit = (value or "").strip().lower()
    if explicit in {item.value for item in ImageClass}:
        return infer_image_class(prompt or "", explicit).value
    text = (prompt or "").lower()
    inferred = infer_image_class(text, None)
    has_explicit_keyword = any(term in text for terms in CLASS_KEYWORDS.values() for term in terms)
    return inferred.value if has_explicit_keyword else default.value


def _looks_generic_title(value: str | None) -> bool:
    if not value or not value.strip():
        return True
    normalized = value.strip().lower()
    # Only block extremely short or placeholder-like titles
    return len(normalized) < 3 or normalized in {"title", "slide", "content", "untitled"}


def _fallback_slide_title(presentation_title: str, index: int, *, variant: str = "default") -> str:
    context = presentation_title or "this topic"
    titles = {
        "default": [
            f"More on {context}",
            f"A different angle on {context}",
            f"What to do next with {context}",
            f"Additional detail on {context}",
        ],
        "image": [
            f"Visual context for {context}",
            f"A closer look at {context}",
            f"Image-backed insight for {context}",
        ],
        "comparison": [
            f"Comparing options for {context}",
            f"Why this matters for {context}",
            f"Tradeoffs for {context}",
        ],
    }
    options = titles.get(variant, titles["default"])
    return options[(index - 1) % len(options)]


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
    slide.visual_mood = _trim_text(slide.visual_mood, 120)
    slide.icon_intent = _trim_text(slide.icon_intent, 120) or slide.title

    if slide.type == SlideType.TITLE_SLIDE.value:
        slide.title = slide.title or presentation_title
        slide.subtitle = slide.subtitle or "Presentation overview"
        slide.bullets = []
        slide.image_prompt = None
        slide.image_class = None
    elif slide.type == SlideType.TITLE_BULLETS.value:
        slide.title = slide.title if not _looks_generic_title(slide.title) else _fallback_slide_title(presentation_title, index)
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=5,
            fallback=_fallback_bullets_for_slide(slide.title or presentation_title, presentation_title, slot=index),
        )
        slide.image_prompt = None
        slide.image_class = None
    elif slide.type == SlideType.TITLE_BULLETS_IMAGE.value:
        slide.title = slide.title if not _looks_generic_title(slide.title) else _fallback_slide_title(presentation_title, index, variant="image")
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=5,
            fallback=_fallback_bullets_for_slide(slide.title or presentation_title, presentation_title, variant="image", slot=index),
        )
        raw_image_prompt = slide.image_prompt
        slide.image_class = _normalize_image_class(slide.image_class, " ".join(filter(None, [slide.title, raw_image_prompt])), default=ImageClass.PHOTO)
        slide.image_prompt = _normalize_image_prompt(raw_image_prompt, slide.title, presentation_title)
    elif slide.type == SlideType.HERO_IMAGE.value:
        slide.title = slide.title or "Visual focus"
        raw_image_prompt = slide.image_prompt
        slide.image_class = _normalize_image_class(slide.image_class, " ".join(filter(None, [slide.title, raw_image_prompt])), default=ImageClass.PHOTO)
        slide.image_prompt = _normalize_image_prompt(raw_image_prompt, slide.title, presentation_title, slide_type=SlideType.HERO_IMAGE.value)
        slide.subtitle = slide.subtitle or ""
    elif slide.type == SlideType.COMPARISON.value:
        slide.title = slide.title or "Comparison"
        slide.left_title = slide.left_title or "Option A"
        slide.right_title = slide.right_title or "Option B"
        slide.left_bullets = _normalize_bullets(
            slide.left_bullets,
            limit=4,
            fallback=_fallback_bullets_for_slide(slide.left_title or slide.title or presentation_title, presentation_title, variant="comparison", slot=index)[:2],
        )
        slide.right_bullets = _normalize_bullets(
            slide.right_bullets,
            limit=4,
            fallback=_fallback_bullets_for_slide(slide.right_title or slide.title or presentation_title, presentation_title, variant="comparison", slot=index + 1)[1:],
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

    slide.attribution = _normalize_attribution(slide.attribution, presentation_title)

    return slide


def _normalize_plan(
    plan: GeminiPresentationPlan,
    slide_count: int,
    slide_outline: list[GuidedSlideIntent] | None = None,
) -> GeminiPresentationPlan:
    slides = list(plan.slides[:slide_count])
    guided = bool(slide_outline)

    if not slides:
        slides = [
            GeminiSlidePlan(type=SlideType.TITLE_SLIDE.value, title=plan.title, subtitle="Presentation overview"),
            GeminiSlidePlan(
                type=SlideType.TITLE_BULLETS_IMAGE.value,
                title=_fallback_slide_title(plan.title, 2, variant="image"),
                bullets=_fallback_bullets_for_slide(plan.title, plan.title, variant="image", slot=2),
                image_prompt=_fallback_image_prompt(_fallback_slide_title(plan.title, 2, variant="image"), plan.title),
            ),
            GeminiSlidePlan(
                type=SlideType.QUOTE.value,
                title="Wrap-up",
                quote="Focus on the clearest next action.",
                attribution=plan.title,
            ),
        ]

    if not guided and _resolve_slide_type(slides[0].type) != SlideType.TITLE_SLIDE:
        slides.insert(0, GeminiSlidePlan(type=SlideType.TITLE_SLIDE.value, title=plan.title, subtitle="Presentation overview"))

    while len(slides) < slide_count:
        slides.append(
            GeminiSlidePlan(
                type=SlideType.TITLE_BULLETS_IMAGE.value,
                title=_fallback_slide_title(plan.title, len(slides) + 1, variant="image"),
                bullets=_fallback_bullets_for_slide(plan.title, plan.title, variant="image", slot=len(slides) + 1),
                image_prompt=_fallback_image_prompt(_fallback_slide_title(plan.title, len(slides) + 1, variant="image"), plan.title),
            )
        )

    slides = slides[:slide_count]
    for index, intent in enumerate(slide_outline or []):
        if intent.requested_type and index < len(slides):
            slides[index].type = intent.requested_type.value
    normalized_slides = [
        _normalize_slide_plan(slide, plan.title, index + 1)
        for index, slide in enumerate(slides)
    ]

    seen_signatures: set[tuple[Any, ...]] = set()
    for index, slide in enumerate(normalized_slides, start=1):
        signature = (
            slide.type,
            (slide.title or "").strip().lower(),
            tuple(bullet.strip().lower() for bullet in slide.bullets),
            tuple(bullet.strip().lower() for bullet in slide.left_bullets),
            tuple(bullet.strip().lower() for bullet in slide.right_bullets),
            slide.quote or "",
            slide.attribution or "",
        )
        if signature in seen_signatures and slide.type == SlideType.TITLE_BULLETS_IMAGE.value:
            slide.title = _fallback_slide_title(plan.title, index, variant="image")
            slide.bullets = _fallback_bullets_for_slide(plan.title, plan.title, variant="image", slot=index)
            slide.image_prompt = _normalize_image_prompt(slide.image_prompt, slide.title, plan.title)
        seen_signatures.add(signature)

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
    parts = []
    # Check if we have parts directly on the response (e.g. from generate_content)
    if hasattr(response, "parts") and response.parts:
        parts = list(response.parts)
    # Check candidates for parts
    elif hasattr(response, "candidates") and response.candidates:
        parts = list(getattr(response.candidates[0].content, "parts", []) or [])

    for part in parts:
        # 1. Prefer raw inline data (fastest and safest)
        if hasattr(part, "inline_data") and part.inline_data:
            data = getattr(part.inline_data, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                try:
                    return base64.b64decode(data, validate=True)
                except Exception:
                    return data.encode("latin1")

        # 2. Try as_image() helper
        as_image = getattr(part, "as_image", None)
        if callable(as_image):
            try:
                image = as_image()
                if image is not None:
                    # If it's a SDK Image type, it has .data
                    if hasattr(image, "data") and isinstance(image.data, bytes):
                        return image.data
                    # If it's a PIL Image, it has .save
                    if hasattr(image, "save"):
                        buffer = BytesIO()
                        # Some versions of save might not support format in certain contexts
                        try:
                            image.save(buffer, format="PNG")
                        except TypeError:
                            image.save(buffer)
                        return buffer.getvalue()
            except Exception as e:
                logger.warning("Failed to extract image via as_image: %s", e)

    raise GeminiImageGenerationError("Gemini did not return valid image bytes in any part.")


async def generate_presentation(
    prompt: str,
    slide_count: int,
    style: str,
    planning_mode: PlanningMode = PlanningMode.AUTOMATIC,
    slide_outline: list[GuidedSlideIntent] | None = None,
) -> Presentation:
    settings = get_settings()
    client = get_client()
    logger.info(
        "Gemini planning request starting. model=%s slide_count=%s style=%s planning_mode=%s prompt_chars=%s",
        settings.gemini_planning_model,
        slide_count,
        style,
        planning_mode,
        len(prompt),
    )

    outline_prompt = ""
    if planning_mode == PlanningMode.GUIDED:
        outline_prompt = f"""

ORDERED SLIDE BRIEFS:
Use this JSON array as a strict ordered plan. Expand each purpose into useful slide content.
If requested_type is null, choose the best allowed type for that slide.
{json.dumps([item.model_dump(mode="json") for item in slide_outline or []], ensure_ascii=False)}
""".rstrip()

    user_prompt = f"""
Create a {slide_count}-slide presentation plan.
Requirement: Generate EXACTLY {slide_count} slides. Do not stop until you have {slide_count} unique slides.

CONTENT RULES:
- Maximum 3-4 bullets per slide.
- Maximum 12-14 words per bullet.
- Headlines should be concise and informative.
- Prioritize visual breathing room.
- Make each slide add new information instead of repeating the topic.
- Prefer a varied narrative rhythm. Do not turn every slide into title_bullets_image.
- Adapt the voice to the subject and audience. Write with an intentional point of view.
- When the brief asks for favorites or opinions, choose specific examples and explain the judgment.
- For school assignments, stay clear and accurate but avoid lifeless textbook phrasing.
- Add visual_mood and icon_intent metadata for every non-title slide.
- Allowed slide types: title_slide, title_bullets, title_bullets_image, hero_image, comparison, timeline, statistics, quote.

Preferred direction:
{style}

Select a theme name from the registry, but do not describe colors, spacing, fonts, or CSS.

Topic:
{prompt}
{outline_prompt}

Return JSON only.
""".strip()

    try:
        # Structured output keeps the MVP stable by asking Gemini for JSON that
        # already matches the planning schema instead of free-form text.
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_planning_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_json_schema=GEMINI_PLANNING_JSON_SCHEMA,
                    temperature=0.3,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=_http_options(settings.gemini_planning_timeout_seconds),
                ),
            ),
            timeout=settings.gemini_planning_timeout_seconds + 5,
        )
    except asyncio.TimeoutError as exc:
        raise GeminiPlanningError(
            f"Gemini planning timed out after {settings.gemini_planning_timeout_seconds} seconds."
        ) from exc
    except Exception as exc:
        raise GeminiPlanningError(_provider_message(exc)) from exc

    try:
        plan = GeminiPresentationPlan.model_validate_json(_extract_json_text(response))
    except (ValidationError, json.JSONDecodeError, GeminiPlanningError) as exc:
        logger.exception("Gemini planning returned invalid JSON.")
        raise GeminiPlanningError("Gemini returned invalid presentation JSON.") from exc

    normalized_plan = _normalize_plan(plan, slide_count, slide_outline if planning_mode == PlanningMode.GUIDED else None)
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


def get_image_model_name() -> str:
    return get_settings().gemini_image_model


async def generate_slide_image(prompt: str) -> bytes:
    settings = get_settings()
    client = get_client()
    final_prompt = (
        "Create one grounded, presentation-ready 16:9 visual. "
        "It should feel like a real slide asset: relevant, restrained, and clean. "
        "Avoid generic AI art, glowing abstract backgrounds, floating icons, and sensational stock-photo cliches. "
        "Do not render visible text, labels, captions, logos, or UI copy. "
        f"Prompt: {prompt}"
    )

    try:
        # The image model is isolated from planning so image failures do not
        # corrupt the slide JSON generation step.
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_image_model,
                contents=final_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                        image_size="1K",
                    ),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    http_options=_http_options(settings.gemini_image_timeout_seconds),
                ),
            ),
            timeout=settings.gemini_image_timeout_seconds + 5,
        )
        return _extract_image_bytes(response)
    except GeminiImageGenerationError:
        raise
    except asyncio.TimeoutError as exc:
        raise GeminiImageGenerationError(
            f"Gemini image generation timed out after {settings.gemini_image_timeout_seconds} seconds."
        ) from exc
    except Exception as exc:
        raise GeminiImageGenerationError(_provider_message(exc)) from exc

