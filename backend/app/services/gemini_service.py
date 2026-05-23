import asyncio
import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.presentation import (
    BulletsSlide,
    BulletsWithImageSlide,
    ConclusionSlide,
    ImageSpec,
    ImageFocusSlide,
    Presentation,
    Theme,
    TitleSlide,
)


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


class GeminiSlidePlan(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    bullets: list[str] = Field(default_factory=list, max_length=6)
    layout: Literal["title", "bullets", "bullets_with_image", "image_focus", "conclusion"]
    needs_image: bool = False
    image_prompt: str | None = Field(default=None, max_length=500)


class GeminiPresentationPlan(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    slides: list[GeminiSlidePlan] = Field(min_length=3, max_length=10)


SYSTEM_PROMPT = """
You create slide plans for a presentation generator.
Return valid JSON only.
No markdown. No prose. No code fences.

Rules:
- Output must match the provided JSON schema exactly.
- Use only these layouts: title, bullets, bullets_with_image, image_focus, conclusion.
- The first slide must be title.
- The last slide must be conclusion.
- Keep bullets concise and presentation-ready.
- If needs_image is true, image_prompt must be present.
- If needs_image is false, image_prompt must be null.
- Image prompts must describe clean, modern, presentation-ready visuals.
- Avoid asking for visible text inside generated images unless absolutely necessary.
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


def _default_theme(style: str) -> Theme:
    palettes = {
        "modern": ("#0f766e", "Inter"),
        "minimal": ("#334155", "Inter"),
        "corporate": ("#1d4ed8", "Inter"),
        "playful": ("#db2777", "Inter"),
    }
    primary_color, font = palettes.get(style.lower(), ("#0f766e", "Inter"))
    return Theme(style=style.lower(), primary_color=primary_color, font=font)


def _normalize_bullets(values: list[str], limit: int, fallback: list[str]) -> list[str]:
    cleaned = [item.strip(" -") for item in values if isinstance(item, str) and item.strip()]
    if cleaned:
        return cleaned[:limit]
    return fallback[:limit]


def _normalize_plan(plan: GeminiPresentationPlan, slide_count: int) -> GeminiPresentationPlan:
    slides = list(plan.slides[:slide_count])

    if not slides:
        slides = [
            GeminiSlidePlan(layout="title", title=plan.title, bullets=[], needs_image=False),
            GeminiSlidePlan(
                layout="bullets",
                title="Key ideas",
                bullets=["Main point one", "Main point two", "Main point three"],
                needs_image=False,
            ),
            GeminiSlidePlan(
                layout="conclusion",
                title="Wrap-up",
                bullets=["Key takeaway one", "Key takeaway two"],
                needs_image=False,
            ),
        ]

    if slides[0].layout != "title":
        slides.insert(0, GeminiSlidePlan(layout="title", title=plan.title, bullets=[], needs_image=False))
    if slides[-1].layout != "conclusion":
        slides.append(
            GeminiSlidePlan(
                layout="conclusion",
                title="Wrap-up",
                bullets=["Key takeaway one", "Key takeaway two"],
                needs_image=False,
            )
        )

    while len(slides) < slide_count:
        slides.insert(
            -1,
            GeminiSlidePlan(
                layout="bullets",
                title=f"Supporting Idea {len(slides)}",
                bullets=["Important point", "Practical implication", "Why it matters"],
                needs_image=False,
            ),
        )

    slides = slides[:slide_count]
    slides[0].layout = "title"
    slides[0].needs_image = False
    slides[0].image_prompt = None
    slides[-1].layout = "conclusion"
    slides[-1].needs_image = False
    slides[-1].image_prompt = None
    return GeminiPresentationPlan(title=plan.title, slides=slides)


def _plan_to_presentation(plan: GeminiPresentationPlan, style: str) -> Presentation:
    # Convert the lightweight Gemini planning schema into the richer
    # layout-based presentation schema used by the renderer and PDF exporter.
    slides: list[Any] = []
    for index, slide in enumerate(plan.slides):
        if slide.layout == "title":
            slides.append(
                TitleSlide(
                    layout="title",
                    title=slide.title,
                    subtitle=slide.bullets[0] if slide.bullets else "Presentation overview",
                )
            )
            continue

        if slide.layout == "image_focus":
            image_prompt = slide.image_prompt or f"Presentation image for {slide.title}"
            slides.append(
                ImageFocusSlide(
                    layout="image_focus",
                    title=slide.title,
                    caption=(slide.bullets[0] if slide.bullets else "Visual summary"),
                    image=ImageSpec(query=image_prompt, role="background_image", remove_background=False),
                )
            )
            continue

        if slide.layout == "bullets_with_image":
            image_prompt = slide.image_prompt or f"Presentation image for {slide.title}"
            slides.append(
                BulletsWithImageSlide(
                    layout="bullets_with_image",
                    title=slide.title,
                    bullets=_normalize_bullets(
                        slide.bullets,
                        limit=5,
                        fallback=["Main point one", "Main point two"],
                    ),
                    image=ImageSpec(query=image_prompt, role="background_image", remove_background=False),
                )
            )
            continue

        if slide.layout == "conclusion":
            slides.append(
                ConclusionSlide(
                    layout="conclusion",
                    title=slide.title,
                    bullets=_normalize_bullets(
                        slide.bullets,
                        limit=4,
                        fallback=["Key takeaway one", "Key takeaway two"],
                    ),
                    closing=slide.bullets[-1] if slide.bullets else "Focus on the clearest next action.",
                )
            )
            continue

        slides.append(
            BulletsSlide(
                layout="bullets",
                title=slide.title,
                bullets=_normalize_bullets(
                    slide.bullets,
                    limit=6,
                    fallback=["Main point one", "Main point two", "Main point three"],
                ),
            )
        )

    return Presentation(
        title=plan.title,
        theme=_default_theme(style),
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
Create a {slide_count}-slide presentation plan in a "{style}" visual style.

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
                "response_json_schema": GeminiPresentationPlan.model_json_schema(),
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
    presentation = _plan_to_presentation(normalized_plan, style)
    logger.info(
        "Gemini planning complete. title=%s slides=%s layouts=%s",
        presentation.title,
        len(presentation.slides),
        [slide.layout.value for slide in presentation.slides],
    )
    return presentation


def build_image_cache_key(slide: Any, style: str) -> str:
    payload = {
        "style": style,
        "layout": getattr(slide, "layout", ""),
        "title": getattr(slide, "title", ""),
        "bullets": getattr(slide, "bullets", []),
        "caption": getattr(slide, "caption", ""),
        "image_prompt": getattr(getattr(slide, "image", None), "query", ""),
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
