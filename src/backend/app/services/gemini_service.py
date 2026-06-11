# Роля на модула: AI planning слой. Превръща свободния prompt в стабилен Presentation модел, който останалият pipeline може да обработва детерминистично.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import asyncio
import base64
import hashlib
import json
import logging
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.image_research.core.image_classes import CLASS_KEYWORDS, ImageClass, infer_image_class
from app.schemas.presentation import GuidedSlideIntent, PlanningMode, Presentation, Slide, SlideType, ThemeName
from app.services.theme_registry import resolve_theme_name

# `BACKEND_DIR` пази резултата от `Path(__file__).resolve`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)
logger = logging.getLogger(__name__)


class GeminiSettings(BaseSettings):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    gemini_api_key: str
    gemini_planning_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_planning_timeout_seconds: int = 45
    gemini_image_timeout_seconds: int = 180
    enable_image_generation: bool = Field(default=True, validation_alias="IMAGE_GEN_SWITCH")


class GeminiServiceError(Exception):
    # Роля на класа: Този custom exception маркира конкретен тип pipeline отказ, за да може горният слой да го преведе към правилен HTTP status или fallback.
    # Отделният exception тип позволява точно `except` правило без parsing на текстово съобщение.
    pass


class GeminiConfigurationError(GeminiServiceError):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    pass


class GeminiPlanningError(GeminiServiceError):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    pass


class GeminiImageGenerationError(GeminiServiceError):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    pass


class GeminiTimelineStep(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    label: str
    detail: str | None = None


class GeminiStatisticItem(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    label: str
    value: str
    detail: str | None = None


class GeminiSlidePlan(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
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
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
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


# `SYSTEM_PROMPT` пази резултата от `'\nYou are a good public speaker thats an expert in making the most intriguing presentations that have the most relevant down to the last detail informations and topics that cover the whole theme and leave the crowd informed and interested in the topic. The shceme is to combine all of that and make structured, HIGHLY CONCISE content plans that have the best suited information for the theme and auditory.\nReturn valid JSON only. No markdown, no prose, no code fences.\n\nCRITICAL RULES:\n1. SLIDE COUNT: Use EXACTLY the requested number of slides.\n2. BREVITY: Maximum Choose the most optimal num of bullet points per slide from 3 to 5. Each bullet MUST be under 14 words. Headlines MUST be concise but alive, they must show character but not a generic one but one that connects to the audience.\n3. SPACING: Give space between elements in a way to leave the background breathe but dont make them too far a way keep them connected yet each one look as important as it is keep the whole space of the slide clean not overwhelming with breathing space\n4. QUALITY: Give every slide one clear job in the narrative. Use concrete explanations, mechanisms, examples, tradeoffs, or next actions, ensure that there is a good followed thought between slides one countinuing the another so we have a connected path of thought everything that is said is a part of the gradual lead to the next topic in the next slide so everything makes sense together.\n5. SCHEMA: Output MUST match the provided JSON schema exactly.\n6. ACCURACY: Do not invent statistics, quotations, citations, or precise factual claims. If a number is not supplied or reliably known, explain the point without a number. But still use statistics as much as possible if theyre valid or have some proof and regard that proof\'s source in other way said when you find a useful statistic use it and say from where is it and make a conclusion about it, how it connects to the topic/slide\n7. VARIETY: Do not repeat the same slide structure mechanically. Use text-only, image-backed, comparison, timeline, statistics, hero, or quote layouts only when they fit the information. Yet there is room for your creativity sometimes we have to think which is the most creative way to approach a very specific or more estetically potentialed page\n8. NO FILLER: Avoid generic phrases such as "key insights", "unlock potential", "embrace innovation", or restating the topic without adding information, use concise, rational language that follows a thought works with it and starts the next point/slide flawlessly making a visual/intuitive connection to make a beautiful thought/slide connected structure \n9. GUIDED MODE: When ordered slide briefs are provided, follow each brief in order. Do not insert, remove, merge, or reorder slides.\n10. VOICE: Match the topic emotionally and write like a presenter with a point of view. You have to be considarate of the topic and its vibe, if its something that has a more creative aproach that can leave space for a more interestign point of views make it as interesting and as thoughtful as possible, if its something that needs an exact answer like math topic or history topic or etc you need to be focused on the exact topic showing the information exactly as it is no mistakes, no space for taking your "own approach" of something that doesnt need one, even though lets say in history there are spaces for opinions but it differs\n11. OPINION: When the request asks for favorites, recommendations, or personal judgment, choose specific examples and explain why they stand out. Avoid generic praise, put some work in the actual research of the topic/asked question so you have context of the actual theme so you can make a beautiful argumented analys so people get in your place and take your point, see that youve actually put your own thought, so they wont guess an ai researched it\n12. NARRATIVE: Give slides intentional roles such as hook, context, world or mechanism, evidence, comparison, favorite examples, personal take, frequently asked questions(faq) if more technological/scientifical topic where you revise logic and explain another intuitionss\n13. METADATA: Set visual_mood to a short topic-specific art direction and icon_intent to a short semantic concept for each non-title slide.\n14. TITLE DISCIPLINE: Preserve the user\'s requested topic as the presentation title when it is short. Do not turn a simple topic like "dnk" or "DNA" into a poetic title with a colon unless the user asked for that tone.\n15. COMPARISONS: Give both sides specific names. Never leave comparison headings as "Option A", "Option B", "Alternative", "Left", or "Right".\n\nIMAGE PROMPT RULES (EXTREMELY IMPORTANT):\n- Always write image_prompt in English, even when the slide text is in another language.\n- Keep image_prompt as a simple searchable English noun phrase or short literal scene. For "dnk"/"DNA", use "DNA" or "DNA double helix", not translated or poetic slide titles.\n- Image prompts must feel like they belong in a polished presentation, not an AI art gallery.\n- Prefer grounded editorial visuals: realistic scenes, relevant objects, clean environments, charts, product/process context, or restrained diagrams.\n- Think logically about the slide: ask for the image a presenter would actually place beside that point.\n- The image must illustrate the slide\'s actual claim, mechanism, example, or comparison, not just the general topic.\n- Write image prompts as short, literal visual briefs that can be sent directly either to an image generator or an image researcher.\n- Prefer one concrete subject or scene per slide. Do not blend unrelated concepts into one image.\n- When a slide mentions a process, show the process. When it mentions a person, place, event, object, or document, show that exact thing.\n- If the slide is abstract, choose a concrete real-world scene or object that directly explains it.\n- Do not use metaphors, symbolism, allegory, poetic framing, or "representing/symbolizing" language.\n- Avoid prompts about "the feeling of" a topic. Ask for visible things only.\n- Avoid "8k", camera flex, hype words, floating icons, surreal metaphors, generic neural networks, random math symbols, and glowing abstract backgrounds.\n- Do not ask for visible text, labels, captions, UI copy, or words inside the image unless the slide truly needs a simple chart-like visual.\n- For sensitive topics, keep visuals respectful, realistic, and non-sensational.\n- For every image-backed slide, set image_class to exactly one of: photo, diagram, illustration, icon.\n- Preserve named people, characters, places, works, objects, and events inside image prompts so external image research can search precisely.\n- Do not default to decorative lab photos, random office workers, or generic technology screens unless the slide is specifically about those scenes.\n- Keep image prompts compact and searchable. Avoid long descriptive sentences when a direct noun phrase or short scene description is enough.\n- Use photo for real people, places, objects, historical/documentary topics, or editorial visuals.\n- Use diagram for explanatory structures, systems, charts, flows, anatomy, maps, and timelines.\n- Use illustration for drawn/vector educational visuals that are not strict diagrams.\n- Use icon only for simple symbolic marks.\n'.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
SYSTEM_PROMPT = """
You are a good public speaker thats an expert in making the most intriguing presentations that have the most relevant down to the last detail informations and topics that cover the whole theme and leave the crowd informed and interested in the topic. The shceme is to combine all of that and make structured, HIGHLY CONCISE content plans that have the best suited information for the theme and auditory.
Return valid JSON only. No markdown, no prose, no code fences.

CRITICAL RULES:
1. SLIDE COUNT: Use EXACTLY the requested number of slides.
2. BREVITY: Maximum Choose the most optimal num of bullet points per slide from 3 to 5. Each bullet MUST be under 14 words. Headlines MUST be concise but alive, they must show character but not a generic one but one that connects to the audience.
3. SPACING: Give space between elements in a way to leave the background breathe but dont make them too far a way keep them connected yet each one look as important as it is keep the whole space of the slide clean not overwhelming with breathing space
4. QUALITY: Give every slide one clear job in the narrative. Use concrete explanations, mechanisms, examples, tradeoffs, or next actions, ensure that there is a good followed thought between slides one countinuing the another so we have a connected path of thought everything that is said is a part of the gradual lead to the next topic in the next slide so everything makes sense together.
5. SCHEMA: Output MUST match the provided JSON schema exactly.
6. ACCURACY: Do not invent statistics, quotations, citations, or precise factual claims. If a number is not supplied or reliably known, explain the point without a number. But still use statistics as much as possible if theyre valid or have some proof and regard that proof's source in other way said when you find a useful statistic use it and say from where is it and make a conclusion about it, how it connects to the topic/slide
7. VARIETY: Do not repeat the same slide structure mechanically. Use text-only, image-backed, comparison, timeline, statistics, hero, or quote layouts only when they fit the information. Yet there is room for your creativity sometimes we have to think which is the most creative way to approach a very specific or more estetically potentialed page
8. NO FILLER: Avoid generic phrases such as "key insights", "unlock potential", "embrace innovation", or restating the topic without adding information, use concise, rational language that follows a thought works with it and starts the next point/slide flawlessly making a visual/intuitive connection to make a beautiful thought/slide connected structure 
9. GUIDED MODE: When ordered slide briefs are provided, follow each brief in order. Do not insert, remove, merge, or reorder slides.
10. VOICE: Match the topic emotionally and write like a presenter with a point of view. You have to be considarate of the topic and its vibe, if its something that has a more creative aproach that can leave space for a more interestign point of views make it as interesting and as thoughtful as possible, if its something that needs an exact answer like math topic or history topic or etc you need to be focused on the exact topic showing the information exactly as it is no mistakes, no space for taking your "own approach" of something that doesnt need one, even though lets say in history there are spaces for opinions but it differs
11. OPINION: When the request asks for favorites, recommendations, or personal judgment, choose specific examples and explain why they stand out. Avoid generic praise, put some work in the actual research of the topic/asked question so you have context of the actual theme so you can make a beautiful argumented analys so people get in your place and take your point, see that youve actually put your own thought, so they wont guess an ai researched it
12. NARRATIVE: Give slides intentional roles such as hook, context, world or mechanism, evidence, comparison, favorite examples, personal take, frequently asked questions(faq) if more technological/scientifical topic where you revise logic and explain another intuitionss
13. METADATA: Set visual_mood to a short topic-specific art direction and icon_intent to a short semantic concept for each non-title slide.
14. TITLE DISCIPLINE: Preserve the user's requested topic as the presentation title when it is short. Do not turn a simple topic like "dnk" or "DNA" into a poetic title with a colon unless the user asked for that tone.
15. COMPARISONS: Give both sides specific names. Never leave comparison headings as "Option A", "Option B", "Alternative", "Left", or "Right".

IMAGE PROMPT RULES (EXTREMELY IMPORTANT):
- Always write image_prompt in English, even when the slide text is in another language.
- Keep image_prompt as a simple searchable English noun phrase or short literal scene. For "dnk"/"DNA", use "DNA" or "DNA double helix", not translated or poetic slide titles.
- Image prompts must feel like they belong in a polished presentation, not an AI art gallery.
- Prefer grounded editorial visuals: realistic scenes, relevant objects, clean environments, charts, product/process context, or restrained diagrams.
- Think logically about the slide: ask for the image a presenter would actually place beside that point.
- The image must illustrate the slide's actual claim, mechanism, example, or comparison, not just the general topic.
- Write image prompts as short, literal visual briefs that can be sent directly either to an image generator or an image researcher.
- Prefer one concrete subject or scene per slide. Do not blend unrelated concepts into one image.
- When a slide mentions a process, show the process. When it mentions a person, place, event, object, or document, show that exact thing.
- If the slide is abstract, choose a concrete real-world scene or object that directly explains it.
- Do not use metaphors, symbolism, allegory, poetic framing, or "representing/symbolizing" language.
- Avoid prompts about "the feeling of" a topic. Ask for visible things only.
- Avoid "8k", camera flex, hype words, floating icons, surreal metaphors, generic neural networks, random math symbols, and glowing abstract backgrounds.
- Do not ask for visible text, labels, captions, UI copy, or words inside the image unless the slide truly needs a simple chart-like visual.
- For sensitive topics, keep visuals respectful, realistic, and non-sensational.
- For every image-backed slide, set image_class to exactly one of: photo, diagram, illustration, icon.
- Preserve named people, characters, places, works, objects, and events inside image prompts so external image research can search precisely.
- Do not default to decorative lab photos, random office workers, or generic technology screens unless the slide is specifically about those scenes.
- Keep image prompts compact and searchable. Avoid long descriptive sentences when a direct noun phrase or short scene description is enough.
- Use photo for real people, places, objects, historical/documentary topics, or editorial visuals.
- Use diagram for explanatory structures, systems, charts, flows, anatomy, maps, and timelines.
- Use illustration for drawn/vector educational visuals that are not strict diagrams.
- Use icon only for simple symbolic marks.
""".strip()


def _provider_message(exc: Exception) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `provider_message` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `exc` (Exception); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `message` пази резултата от `str(exc).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    message = str(exc).strip() or "Unknown Gemini error."
    # `lower` пази резултата от `message.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    lower = message.lower()
    # Това условие е decision point: `'api key' in lower or 'authentication' in lower or 'permission' in lower`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'Gemini API authentication failed. Check GEMINI_API_KEY.'`, без да проверява по-слабите правила отдолу.
    if "api key" in lower or "authentication" in lower or "permission" in lower:
        return "Gemini API authentication failed. Check GEMINI_API_KEY."
    # Това условие е decision point: `'quota' in lower or '429' in lower or 'resource_exhausted' in lower`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'Gemini quota or rate limit reached. Please try again later.'`, без да проверява по-слабите правила отдолу.
    if "quota" in lower or "429" in lower or "resource_exhausted" in lower:
        return "Gemini quota or rate limit reached. Please try again later."
    return message


@lru_cache(maxsize=1)
def get_settings() -> GeminiSettings:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Основните преходи навън са към `lru_cache`, `GeminiSettings`, `GeminiConfigurationError`; така се вижда кои отговорности функцията делегира.
    # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
    # Изходен договор: `GeminiSettings`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (ValidationError) в предвидимо поведение за горния слой.
    try:
        return GeminiSettings()
    except ValidationError as exc:
        raise GeminiConfigurationError(
            f"Missing backend configuration. Create {ENV_FILE} and set GEMINI_API_KEY."
        ) from exc


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Основните преходи навън са към `lru_cache`, `get_settings`, `genai.Client`; така се вижда кои отговорности функцията делегира.
    # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
    # Изходен договор: `genai.Client`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `settings` е конфигурацията от environment, която включва или изключва външни услуги и избира модели.
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _http_options(timeout_seconds: int | None) -> types.HttpOptions:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `http_options` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `timeout_seconds` (int | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `types.HttpOptions`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `types.HttpOptions`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    return types.HttpOptions(timeout=timeout_seconds * 1000 if timeout_seconds and timeout_seconds > 0 else None)


async def _with_optional_timeout(awaitable: Any, timeout_seconds: int | None) -> Any:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `with_optional_timeout` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `awaitable` (Any), `timeout_seconds` (int | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `asyncio.wait_for`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `Any`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Това условие е decision point: `timeout_seconds and timeout_seconds > 0`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`await asyncio.wait_for(awaitable, timeout=timeout_seconds + 5)`) и прескачаме ненужната останала работа.
    if timeout_seconds and timeout_seconds > 0:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds + 5)
    return await awaitable


def _is_timeout_like_error(message: str) -> bool:
    return bool(re.search(r"\b(timeout|timed out|deadline|504|deadline_exceeded)\b", message, re.IGNORECASE))


def _normalize_bullets(values: list[str], limit: int, fallback: list[str]) -> list[str]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `values` (list[str]), `limit` (int), `fallback` (list[str]); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[str]`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `cleaned` пази резултата от `v.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
    cleaned: list[str] = [v.strip() for v in values if v and isinstance(v, str) and v.strip()]
    # Това условие е decision point: `cleaned`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`cleaned[:limit]`) и прескачаме ненужната останала работа.
    if cleaned:
        return cleaned[:limit]
    return fallback[:limit]


def _fallback_bullets_for_slide(
    title: str, presentation_title: str, *, variant: str = "default", slot: int = 0
) -> list[str]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback_bullets_for_slide` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `title` (str), `presentation_title` (str), `variant` (str), `slot` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[str]`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    context = title or presentation_title or "this topic"
    templates = {
        "default": [
            [f"Overview of {context}", "Most important detail", "Recommended next step"],
            [f"Why {context} matters", "What changes", "Immediate takeaway"],
            [f"How {context} works", "Main constraint", "Best next action"],
        ],
        "image": [
            [f"Overview of {context}", "Visual reference or supporting idea", "Practical takeaway"],
            ["Why the image matters", "What it shows", "How to use it"],
            ["Main message", "Image support", "Next action"],
        ],
        "comparison": [
            [f"Strengths of {context}", "Tradeoffs to consider", "Best fit or next step"],
            [f"What {context} does well", "Where it falls short", "When to choose it"],
            ["Option one", "Option two", "Recommended path"],
        ],
    }
    # `choices` пази резултата от `templates.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    choices = templates.get(variant, templates["default"])
    return choices[slot % len(choices)]


def _trim_text(value: str | None, limit: int) -> str | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `trim_text` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str | None), `limit` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Това условие е decision point: `value is None`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if value is None:
        return None
    # `cleaned` пази резултата от `value.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    cleaned = value.strip()
    # Това условие е decision point: `not cleaned`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not cleaned:
        return None
    return cleaned[:limit]


def _normalize_attribution(value: str | None, presentation_title: str | None, *, limit: int = 250) -> str | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `value` (str | None), `presentation_title` (str | None), `limit` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_trim_text`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = _trim_text(value, limit)
    # Това условие е decision point: `normalized`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`normalized`) и прескачаме ненужната останала работа.
    if normalized:
        return normalized
    return _trim_text(presentation_title, limit)


ENGLISH_VISUAL_ALIAS_RULES: tuple[tuple[str, str], ...] = (
    (r"\bднк\b|\bdnk\b", "DNA"),
    (r"\bрнк\b|\brnk\b", "RNA"),
    (r"\bдвойна\s+спирала\b", "double helix"),
    (r"\bструктура(?:та)?\b", "structure"),
    (r"\bмолекул(?:а|ата)?\b", "molecule"),
    (r"\bмолекулн(?:а|ата|и)?\b", "molecular"),
    (r"\bген(?:и|ът|а)?\b", "gene"),
    (r"\bгенетик(?:а|ата|ата)?\b", "genetics"),
    (r"\bхромозом(?:а|и|ите)?\b", "chromosome"),
    (r"\bклетк(?:а|и|ите)?\b", "cell"),
    (r"\bядро(?:то)?\b", "nucleus"),
    (r"\bбиолог(?:ия|ията|ичен|ична|ични|ично)?\b", "biology"),
    (r"\bорганиз(?:ъм|ми|мите)?\b", "organism"),
    (r"\bпротеин(?:ът|и|ите)?\b", "protein"),
    (r"\bпротеинов(?:а|ата|и|о)?\b", "protein"),
    (r"\bбелтък(?:ът|ци|ците)?\b", "protein"),
    (r"\bензим(?:ът|и|ите)?\b", "enzyme"),
    (r"\bвирус(?:ът|и|ите)?\b", "virus"),
    (r"\bбактери(?:я|и|ите)?\b", "bacteria"),
    (r"\bаденин\b", "adenine"),
    (r"\bтимин\b", "thymine"),
    (r"\bгуанин\b", "guanine"),
    (r"\bцитозин\b", "cytosine"),
    (r"\bводородни\s+връзки\b", "hydrogen bonds"),
    (r"\bбългария\b", "Bulgaria"),
    (r"\bбългарски(?:ят|я|и)?\b", "Bulgarian"),
    (r"\bсъветски(?:ят|я|и)?\b", "Soviet"),
    (r"\bссср\b", "Soviet Union"),
    (r"\bтодор\s+живков\b", "Todor Zhivkov"),
    (r"\bмихаил\s+горбачов\b", "Mikhail Gorbachev"),
    (r"\bгорбачов\b", "Gorbachev"),
    (r"\bперестройка\b", "perestroika"),
    (r"\bизточна\s+европа\b", "Eastern Europe"),
    (r"\bстудената\s+война\b", "Cold War"),
    (r"\bкомуниз(?:ъм|ма)\b", "communism"),
    (r"\bсоциализ(?:ъм|ма)\b", "socialism"),
    (r"\bпланирана\s+икономика\b", "planned economy"),
    (r"\bиндустриализация\b", "industrialization"),
    (r"\bземеделие\b", "agriculture"),
    (r"\bикономик(?:а|ата|чески)\b", "economy"),
    (r"\bполитически\b", "political"),
    (r"\bреформи\b", "reforms"),
    (r"\bреволюци(?:я|ята)\b", "revolution"),
    (r"\bвойна\b", "war"),
    (r"\bучилище\b", "school"),
    (r"\bобразование\b", "education"),
    (r"\bученици\b", "students"),
)

IMAGE_PROMPT_STOPWORDS = {
    "presentation",
    "visual",
    "literal",
    "supporting",
    "editorial",
    "realistic",
    "clean",
    "modern",
    "scene",
    "object",
    "process",
    "show",
    "relevant",
    "grounded",
    "restrained",
    "style",
    "text",
    "without",
    "with",
    "for",
    "and",
    "the",
    "this",
    "that",
    "slide",
    "topic",
    "overview",
}


def english_visual_search_phrase(*parts: str | None, limit_words: int = 8, max_length: int = 80) -> str:
    # Роля в pipeline-а: обработва стъпката `english_visual_search_phrase` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `limit_words` (int), `max_length` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`, `re.sub`, `seen.add`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = " ".join(str(part).strip() for part in parts if part and str(part).strip())
    # Това условие е decision point: `not text`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `''`, без да проверява по-слабите правила отдолу.
    if not text:
        return ""
    # Обхождаме `ENGLISH_VISUAL_ALIAS_RULES` като `(pattern, replacement)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for pattern, replacement in ENGLISH_VISUAL_ALIAS_RULES:
        # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
        text = re.sub(pattern, f" {replacement} ", text, flags=re.IGNORECASE)
    # `words` е думите от заглавието след Unicode нормализация; те са суровината за безопасния slug.
    words: list[str] = []
    seen: set[str] = set()
    # Обхождаме `re.findall("[A-Za-z][A-Za-z0-9&'+-]*", text)` като `word`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for word in re.findall(r"[A-Za-z][A-Za-z0-9&'+-]*", text):
        # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
        normalized = word.lower().strip("-'+")
        # Това условие е decision point: `len(normalized) < 2 or normalized in IMAGE_PROMPT_STOPWORDS or normalized in seen`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if len(normalized) < 2 or normalized in IMAGE_PROMPT_STOPWORDS or normalized in seen:
            continue
        seen.add(normalized)
        words.append("DNA" if normalized == "dna" else "RNA" if normalized == "rna" else word)
        # Това условие е decision point: `len(words) >= limit_words`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if len(words) >= limit_words:
            break
    # `phrase` пази резултата от `' '.join(words).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    phrase = " ".join(words).strip()
    return phrase[:max_length].strip()


def _english_only_image_prompt(value: str, fallback: str = "presentation topic") -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `english_only_image_prompt` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `english_visual_search_phrase`, `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `prompt` е инструкцията, която носи визуалния или съдържателния смисъл към следващия AI/search етап.
    prompt = english_visual_search_phrase(value, limit_words=8, max_length=90)
    # Това условие е decision point: `not prompt`.
    # При вярно условие се активира `english_visual_search_phrase`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if not prompt:
        # `prompt` е инструкцията, която носи визуалния или съдържателния смисъл към следващия AI/search етап.
        prompt = english_visual_search_phrase(fallback, limit_words=8, max_length=90)
    # `prompt` е инструкцията, която носи визуалния или съдържателния смисъл към следващия AI/search етап.
    prompt = re.sub(r"[^A-Za-z0-9 &'+-]", " ", prompt)
    # `prompt` е инструкцията, която носи визуалния или съдържателния смисъл към следващия AI/search етап.
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt or "presentation topic"


def _simple_english_visual_subject(
    raw_prompt: str | None,
    title: str | None,
    presentation_title: str,
    subtitle: str | None,
    bullets: list[str] | None,
) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `simple_english_visual_subject` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `raw_prompt` (str | None), `title` (str | None), `presentation_title` (str), `subtitle` (str | None), `bullets` (list[str] | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `english_visual_search_phrase`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `joined` пази резултата от `' '.join`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    joined = " ".join(
        str(part or "") for part in [raw_prompt, title, subtitle, *(bullets or [])[:3], presentation_title]
    )
    # `phrase` пази резултата от `english_visual_search_phrase`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    phrase = english_visual_search_phrase(
        raw_prompt, title, subtitle, *((bullets or [])[:3]), presentation_title, limit_words=8, max_length=72
    )
    # `lower_phrase` пази резултата от `phrase.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    lower_phrase = phrase.lower()
    # `lower_joined` пази резултата от `joined.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    lower_joined = joined.lower()
    # Това условие е decision point: `'dna' in lower_phrase`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'DNA'`, без да проверява по-слабите правила отдолу.
    if "dna" in lower_phrase:
        # Това условие е decision point: `any((term in lower_phrase for term in ('adenine', 'thymine', 'guanine', 'cytosine', 'hydr...`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'DNA base pairs'`, без да проверява по-слабите правила отдолу.
        if any(term in lower_phrase for term in ("adenine", "thymine", "guanine", "cytosine", "hydrogen")):
            return "DNA base pairs"
        # Това условие е decision point: `'structure' in lower_phrase or 'double helix' in lower_joined or 'структура' in lower_joined`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'DNA double helix'`, без да проверява по-слабите правила отдолу.
        if "structure" in lower_phrase or "double helix" in lower_joined or "структура" in lower_joined:
            return "DNA double helix"
        return "DNA"
    # Това условие е decision point: `'rna' in lower_phrase`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'RNA molecule'`, без да проверява по-слабите правила отдолу.
    if "rna" in lower_phrase:
        return "RNA molecule"
    return phrase or "presentation topic"


def _fallback_image_prompt(title: str | None, presentation_title: str, *, slide_type: str = "supporting") -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback_image_prompt` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `title` (str | None), `presentation_title` (str), `slide_type` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `english_visual_search_phrase`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `topic` пази резултата от `english_visual_search_phrase`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    topic = (
        english_visual_search_phrase(title, presentation_title, limit_words=6, max_length=60) or "presentation topic"
    )
    return topic


def _normalize_image_prompt(
    raw_prompt: str | None,
    title: str | None,
    presentation_title: str,
    *,
    slide_type: str = "supporting",
    subtitle: str | None = None,
    bullets: list[str] | None = None,
) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `raw_prompt` (str | None), `title` (str | None), `presentation_title` (str), `slide_type` (str), `subtitle` (str | None), `bullets` (list[str] | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.search`, `re.sub`, `_simple_english_visual_subject`, `english_visual_search_phrase`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `base` пази резултата от `(raw_prompt or '').strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    base = (raw_prompt or "").strip() or _fallback_image_prompt(title, presentation_title, slide_type=slide_type)
    # Това условие е decision point: `re.search('\\b(neural networks?|glowing|floating|surreal|abstract|futuristic|random symbo...`.
    # При вярно условие се активира `_fallback_image_prompt`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if re.search(
        r"\b(neural networks?|glowing|floating|surreal|abstract|futuristic|random symbols?|ai art|conceptual visualization)\b",
        base,
        flags=re.IGNORECASE,
    ):
        # `base` пази резултата от `_fallback_image_prompt`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        base = _fallback_image_prompt(title, presentation_title, slide_type=slide_type)
    # Обхождаме `['\\bsymboli[sz]ing\\b.*', '\\brepresenting\\b.*', '\\bmetaphor(?:ical)?\\b.*', '\\balleg...` като `pattern`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for pattern in [
        r"\bsymboli[sz]ing\b.*",
        r"\brepresenting\b.*",
        r"\bmetaphor(?:ical)?\b.*",
        r"\ballegor(?:y|ical)\b.*",
        r"\bconceptual\b.*",
    ]:
        # `base` пази резултата от `re.sub`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        base = re.sub(pattern, "", base, flags=re.IGNORECASE)
    # Обхождаме `['\\b8k\\b', '\\b4k\\b', '\\bultra[- ]?high[- ]?resolution\\b', '\\bhigh[- ]?resolution\\...` като `pattern`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
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
        # `base` пази резултата от `re.sub`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        base = re.sub(pattern, "", base, flags=re.IGNORECASE)
    # `base` пази резултата от `re.sub`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    base = re.sub(r"\s+,", ",", base)
    # `base` пази резултата от `re.sub`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    base = re.sub(r",\s*,+", ",", base)
    # `base` пази резултата от `re.sub('\\s+', ' ', base).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    base = re.sub(r"\s+", " ", base).strip(" ,.")

    # `subject` пази резултата от `_simple_english_visual_subject`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    subject = _simple_english_visual_subject(base, title, presentation_title, subtitle, bullets)
    # `fallback` пази резултата от `english_visual_search_phrase`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    fallback = english_visual_search_phrase(
        title, subtitle, *((bullets or [])[:2]), presentation_title, limit_words=8, max_length=90
    )
    return _english_only_image_prompt(subject, fallback=fallback)


def _normalize_image_class(value: str | None, prompt: str | None, *, default: ImageClass = ImageClass.PHOTO) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `value` (str | None), `prompt` (str | None), `default` (ImageClass); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `infer_image_class`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `explicit` пази резултата от `(value or '').strip().lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    explicit = (value or "").strip().lower()
    # Това условие е decision point: `explicit in {item.value for item in ImageClass}`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`infer_image_class(prompt or '', explicit).value`) и прескачаме ненужната останала работа.
    if explicit in {item.value for item in ImageClass}:
        return infer_image_class(prompt or "", explicit).value
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = (prompt or "").lower()
    # `inferred` пази резултата от `infer_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    inferred = infer_image_class(text, None)
    # `has_explicit_keyword` е boolean решение, което управлява кой branch от pipeline-а ще се изпълни.
    has_explicit_keyword = any(term in text for terms in CLASS_KEYWORDS.values() for term in terms)
    return inferred.value if has_explicit_keyword else default.value


def _looks_generic_title(value: str | None) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `looks_generic_title` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Това условие е decision point: `not value or not value.strip()`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `True`, без да проверява по-слабите правила отдолу.
    if not value or not value.strip():
        return True
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = value.strip().lower()
    # Only block extremely short or placeholder-like titles
    return len(normalized) < 3 or normalized in {"title", "slide", "content", "untitled"}


def _fallback_slide_title(presentation_title: str, index: int, *, variant: str = "default") -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback_slide_title` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `presentation_title` (str), `index` (int), `variant` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
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
    # `options` пази резултата от `titles.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    options = titles.get(variant, titles["default"])
    return options[(index - 1) % len(options)]


def _has_cyrillic(text: str) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `has_cyrillic` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `text` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.search`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    return bool(re.search(r"[А-Яа-яЁё]", text))


def _localized_label(english: str, bulgarian: str, context: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `localized_label` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `english` (str), `bulgarian` (str), `context` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_has_cyrillic`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    return bulgarian if _has_cyrillic(context) else english


def _heading_from_first_bullet(bullets: list[str], fallback: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `heading_from_first_bullet` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `bullets` (list[str]), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Обхождаме `bullets` като `bullet`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for bullet in bullets:
        # `cleaned` пази резултата от `re.sub('\\s+', ' ', bullet).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        cleaned = re.sub(r"\s+", " ", bullet).strip(" .,:;")
        # Това условие е decision point: `not cleaned`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if not cleaned:
            continue
        # Това условие е decision point: `':' in cleaned`.
        # При вярно условие се активира `cleaned.split(':', 1)[0].strip`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if ":" in cleaned:
            # `left` пази резултата от `cleaned.split(':', 1)[0].strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            left = cleaned.split(":", 1)[0].strip()
            # Това условие е decision point: `3 <= len(left) <= 42`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`left`) и прескачаме ненужната останала работа.
            if 3 <= len(left) <= 42:
                return left
        # `words` е думите от заглавието след Unicode нормализация; те са суровината за безопасния slug.
        words = cleaned.split()
        # Това условие е decision point: `1 <= len(words) <= 4 and len(cleaned) <= 42`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`cleaned`) и прескачаме ненужната останала работа.
        if 1 <= len(words) <= 4 and len(cleaned) <= 42:
            return cleaned
    return fallback


def _infer_comparison_title(existing: str | None, bullets: list[str], fallback: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: извежда липсваща класификация от наличните текстови сигнали.
    # Входът идва през `existing` (str | None), `bullets` (list[str]), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_trim_text`, `_heading_from_first_bullet`, `_localized_label`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = _trim_text(existing, 120)
    placeholders = {
        "option a",
        "option b",
        "option one",
        "option two",
        "alternative",
        "variant a",
        "variant b",
        "choice a",
        "choice b",
        "left",
        "right",
        "first",
        "second",
    }
    # Това условие е decision point: `normalized and normalized.lower() not in placeholders`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`normalized`) и прескачаме ненужната останала работа.
    if normalized and normalized.lower() not in placeholders:
        return normalized

    # `combined` пази резултата от `' '.join(bullets).lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    combined = " ".join(bullets).lower()
    keyword_map = [
        (
            ("adenine", "thymine", "аденин", "тимин", "two hydrogen", "две водородни"),
            ("Adenine and Thymine", "Аденин и Тимин"),
        ),
        (
            ("guanine", "cytosine", "гуанин", "цитозин", "three hydrogen", "три водородни", "стабилност"),
            ("Guanine and Cytosine", "Гуанин и Цитозин"),
        ),
        (("gemini", "generated", "generate", "ai", "custom", "unique", "генерира"), ("AI Generation", "AI генериране")),
        (
            ("unsplash", "stock", "editorial", "realistic scene", "photography", "photo library", "стокови"),
            ("Stock Images", "Стокови изображения"),
        ),
        (("manual", "designer", "handmade", "curated"), ("Manual Design", "Ръчен дизайн")),
        (("diagram", "chart", "structured", "explain", "диаграма"), ("Diagrams", "Диаграми")),
        (("photo", "photos", "real world", "documentary", "снимки"), ("Photography", "Фотография")),
    ]
    # Обхождаме `keyword_map` като `(terms, labels)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for terms, labels in keyword_map:
        # Това условие е decision point: `any((term in combined for term in terms))`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`_localized_label(labels[0], labels[1], combined)`) и прескачаме ненужната останала работа.
        if any(term in combined for term in terms):
            return _localized_label(labels[0], labels[1], combined)
    return _heading_from_first_bullet(bullets, fallback)


def _normalize_timeline(steps: list[GeminiTimelineStep]) -> list[GeminiTimelineStep]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `steps` (list[GeminiTimelineStep]); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `GeminiTimelineStep`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[GeminiTimelineStep]`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Това условие е decision point: `steps`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`steps[:6]`) и прескачаме ненужната останала работа.
    if steps:
        return steps[:6]
    return [
        GeminiTimelineStep(label="Phase 1", detail="Define the problem and audience."),
        GeminiTimelineStep(label="Phase 2", detail="Build the core message and structure."),
    ]


def _normalize_statistics(items: list[GeminiStatisticItem]) -> list[GeminiStatisticItem]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
    # Входът идва през `items` (list[GeminiStatisticItem]); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `GeminiStatisticItem`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[GeminiStatisticItem]`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Това условие е decision point: `items`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`items[:4]`) и прескачаме ненужната останала работа.
    if items:
        return items[:4]
    return [GeminiStatisticItem(label="Impact", value="3x", detail="Faster turnaround")]


def _resolve_slide_type(raw_type: str) -> SlideType:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: взима решение между няколко възможни източника или стратегии и връща готов резултат.
    # Входът идва през `raw_type` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `SlideType`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `SlideType`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `value` пази резултата от `raw_type.strip().lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    value = raw_type.strip().lower()
    aliases = {
        "title": SlideType.TITLE_SLIDE,
        "bullets": SlideType.TITLE_BULLETS,
        "bullets_with_image": SlideType.TITLE_BULLETS_IMAGE,
        "image_focus": SlideType.HERO_IMAGE,
        "conclusion": SlideType.QUOTE,
    }
    # Това условие е decision point: `value in aliases`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`aliases[value]`) и прескачаме ненужната останала работа.
    if value in aliases:
        return aliases[value]
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (ValueError) в предвидимо поведение за горния слой.
    try:
        return SlideType(value)
    except ValueError:
        return SlideType.TITLE_BULLETS


def _normalize_slide_plan(slide: GeminiSlidePlan, presentation_title: str, index: int) -> GeminiSlidePlan:
    # Роля в pipeline-а: Изчиства един AI-generated slide plan до ограниченията на конкретния SlideType преди Pydantic валидацията.
    # Входът идва през `slide` (GeminiSlidePlan), `presentation_title` (str), `index` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `GeminiSlidePlan.model_validate`, `_trim_text`, `_normalize_attribution`, `slide.model_dump`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `GeminiSlidePlan`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `slide` пази резултата от `GeminiSlidePlan.model_validate`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    slide = GeminiSlidePlan.model_validate(slide.model_dump())
    slide.id = slide.id or f"slide_{index}"
    # `slide.type` пази резултата от `_resolve_slide_type`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    slide.type = _resolve_slide_type(slide.type).value
    # `slide.visual_mood` пази резултата от `_trim_text`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    slide.visual_mood = _trim_text(slide.visual_mood, 120)
    # `slide.icon_intent` пази резултата от `_trim_text`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    slide.icon_intent = _trim_text(slide.icon_intent, 120) or slide.title

    # Това условие е decision point: `slide.type == SlideType.TITLE_SLIDE.value`.
    # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
    if slide.type == SlideType.TITLE_SLIDE.value:
        slide.title = slide.title or presentation_title
        slide.subtitle = slide.subtitle or "Presentation overview"
        slide.bullets = []
        slide.image_prompt = None
        slide.image_class = None
    # Това условие е decision point: `slide.type == SlideType.TITLE_BULLETS.value`.
    # При вярно условие се активира `_normalize_bullets`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.TITLE_BULLETS.value:
        # `slide.title` пази резултата от `_fallback_slide_title`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide.title = (
            slide.title if not _looks_generic_title(slide.title) else _fallback_slide_title(presentation_title, index)
        )
        # `slide.bullets` пази резултата от `_normalize_bullets`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=5,
            fallback=_fallback_bullets_for_slide(slide.title or presentation_title, presentation_title, slot=index),
        )
        slide.image_prompt = None
        slide.image_class = None
    # Това условие е decision point: `slide.type == SlideType.TITLE_BULLETS_IMAGE.value`.
    # При вярно условие се активира `_normalize_bullets`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.TITLE_BULLETS_IMAGE.value:
        # `slide.title` пази резултата от `_fallback_slide_title`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide.title = (
            slide.title
            if not _looks_generic_title(slide.title)
            else _fallback_slide_title(presentation_title, index, variant="image")
        )
        # `slide.bullets` пази резултата от `_normalize_bullets`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide.bullets = _normalize_bullets(
            slide.bullets,
            limit=5,
            fallback=_fallback_bullets_for_slide(
                slide.title or presentation_title, presentation_title, variant="image", slot=index
            ),
        )
        raw_image_prompt = slide.image_prompt
        # `slide.image_class` пази резултата от `_normalize_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide.image_class = _normalize_image_class(
            slide.image_class, " ".join(filter(None, [slide.title, raw_image_prompt])), default=ImageClass.PHOTO
        )
        slide.image_prompt = _normalize_image_prompt(
            raw_image_prompt,
            slide.title,
            presentation_title,
            subtitle=slide.subtitle,
            bullets=slide.bullets,
        )
    # Това условие е decision point: `slide.type == SlideType.HERO_IMAGE.value`.
    # При вярно условие се активира `_normalize_image_class`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.HERO_IMAGE.value:
        slide.title = slide.title or "Visual focus"
        raw_image_prompt = slide.image_prompt
        slide.image_class = _normalize_image_class(
            slide.image_class, " ".join(filter(None, [slide.title, raw_image_prompt])), default=ImageClass.PHOTO
        )
        slide.image_prompt = _normalize_image_prompt(
            raw_image_prompt,
            slide.title,
            presentation_title,
            slide_type=SlideType.HERO_IMAGE.value,
            subtitle=slide.subtitle,
            bullets=slide.bullets,
        )
        slide.subtitle = slide.subtitle or ""
    # Това условие е decision point: `slide.type == SlideType.COMPARISON.value`.
    # При вярно условие се активира `_infer_comparison_title`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.COMPARISON.value:
        slide.title = slide.title or "Comparison"
        slide.left_title = _infer_comparison_title(slide.left_title, slide.left_bullets, "Option A")
        slide.right_title = _infer_comparison_title(slide.right_title, slide.right_bullets, "Alternative")
        slide.left_bullets = _normalize_bullets(
            slide.left_bullets,
            limit=4,
            fallback=_fallback_bullets_for_slide(
                slide.left_title or slide.title or presentation_title,
                presentation_title,
                variant="comparison",
                slot=index,
            )[:2],
        )
        slide.right_bullets = _normalize_bullets(
            slide.right_bullets,
            limit=4,
            fallback=_fallback_bullets_for_slide(
                slide.right_title or slide.title or presentation_title,
                presentation_title,
                variant="comparison",
                slot=index + 1,
            )[1:],
        )
        slide.left_title = _infer_comparison_title(slide.left_title, slide.left_bullets, "Option A")
        slide.right_title = _infer_comparison_title(slide.right_title, slide.right_bullets, "Alternative")
    # Това условие е decision point: `slide.type == SlideType.TIMELINE.value`.
    # При вярно условие се активира `_normalize_timeline`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.TIMELINE.value:
        slide.title = slide.title or "Timeline"
        slide.timeline = _normalize_timeline(slide.timeline)
    # Това условие е decision point: `slide.type == SlideType.STATISTICS.value`.
    # При вярно условие се активира `_normalize_statistics`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    elif slide.type == SlideType.STATISTICS.value:
        slide.title = slide.title or "Statistics"
        slide.statistics = _normalize_statistics(slide.statistics)
    elif slide.type == SlideType.QUOTE.value:
        slide.title = _trim_text(slide.title, 140) or "Closing thought"
        slide.quote = _trim_text(slide.quote, 260) or "Keep the message focused and repeat the core idea."

    # `slide.attribution` пази резултата от `_normalize_attribution`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    slide.attribution = _normalize_attribution(slide.attribution, presentation_title)

    return slide


def _fallback_title_from_purpose(purpose: str, presentation_title: str, index: int) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback_title_from_purpose` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `purpose` (str), `presentation_title` (str), `index` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_fallback_slide_title`, `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `cleaned` пази резултата от `re.sub('\\s+', ' ', purpose).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    cleaned = re.sub(r"\s+", " ", purpose).strip(" -:;,.")
    # Това условие е decision point: `not cleaned`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`_fallback_slide_title(presentation_title, index)`) и прескачаме ненужната останала работа.
    if not cleaned:
        return _fallback_slide_title(presentation_title, index)
    # `first_sentence` пази резултата от `re.split('(?<=[.!?])\\s+', cleaned, maxsplit=1)[0].strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    first_sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0].strip(" -:;,.")
    return (first_sentence or cleaned)[:100]


def _fallback_plan_from_request(
    prompt: str,
    slide_count: int,
    style: str,
    slide_outline: list[GuidedSlideIntent] | None = None,
) -> GeminiPresentationPlan:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback_plan_from_request` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `prompt` (str), `slide_count` (int), `style` (str), `slide_outline` (list[GuidedSlideIntent] | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_normalize_plan`, `_trim_text`, `_fallback_title_from_purpose`, `GeminiPresentationPlan`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `GeminiPresentationPlan`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `title` пази резултата от `_trim_text`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    title = _trim_text(prompt, 140) or "Generated presentation"
    intents = list(slide_outline or [])
    slides: list[GeminiSlidePlan] = []

    # Обхождаме `range(slide_count)` като `index`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for index in range(slide_count):
        intent = intents[index] if index < len(intents) else None
        # `purpose` пази резултата от `_fallback_slide_title`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        purpose = intent.purpose if intent else _fallback_slide_title(title, index + 1)
        # `slide_title` пази резултата от `_fallback_title_from_purpose`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        slide_title = _fallback_title_from_purpose(purpose, title, index + 1)
        slide_type = intent.requested_type.value if intent and intent.requested_type else SlideType.TITLE_BULLETS.value
        slides.append(
            GeminiSlidePlan(
                type=slide_type,
                title=slide_title,
                subtitle=_trim_text(purpose, 220) if slide_type == SlideType.TITLE_SLIDE.value else None,
                bullets=_fallback_bullets_for_slide(slide_title, title, slot=index),
                image_prompt=_fallback_image_prompt(slide_title, title),
                visual_mood=f"{style} presentation visual",
                icon_intent=slide_title,
                notes=purpose if purpose != slide_title else None,
            )
        )

    return _normalize_plan(
        GeminiPresentationPlan(title=title, theme=style, slides=slides),
        slide_count,
        slide_outline,
        source_prompt=prompt,
    )


def _requested_topic_title(prompt: str | None) -> str | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `requested_topic_title` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `prompt` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.sub`, `re.search`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `cleaned` пази резултата от `re.sub('\\s+', ' ', prompt or '').strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    cleaned = re.sub(r"\s+", " ", (prompt or "")).strip(" .,:;")
    # Това условие е decision point: `not cleaned`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not cleaned:
        return None
    # Това условие е decision point: `len(cleaned) <= 40 and len(cleaned.split()) <= 4 and (not re.search('[.!?;]', cleaned))`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`cleaned`) и прескачаме ненужната останала работа.
    if len(cleaned) <= 40 and len(cleaned.split()) <= 4 and not re.search(r"[.!?;]", cleaned):
        return cleaned
    return None


def _normalize_plan(
    plan: GeminiPresentationPlan,
    slide_count: int,
    slide_outline: list[GuidedSlideIntent] | None = None,
    source_prompt: str | None = None,
) -> GeminiPresentationPlan:
    # Роля в pipeline-а: Работи като редактор след AI: поправя липсващи или прекалени стойности, пази заявения брой слайдове и гарантира валиден краен план.
    # Входът идва през `plan` (GeminiPresentationPlan), `slide_count` (int), `slide_outline` (list[GuidedSlideIntent] | None), `source_prompt` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_requested_topic_title`, `GeminiPresentationPlan`, `slides.insert`, `_normalize_slide_plan`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `GeminiPresentationPlan`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `requested_title` пази резултата от `_requested_topic_title`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    requested_title = _requested_topic_title(source_prompt)
    # Това условие е decision point: `requested_title`.
    # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
    if requested_title:
        plan.title = requested_title

    slides = list(plan.slides[:slide_count])
    guided = bool(slide_outline)

    # Това условие е decision point: `not slides`.
    # При вярно условие се активира `GeminiSlidePlan`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if not slides:
        # `slides` пази резултата от `GeminiSlidePlan`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
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

    # Това условие е decision point: `not guided and _resolve_slide_type(slides[0].type) != SlideType.TITLE_SLIDE`.
    # При вярно условие се активира `slides.insert`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if not guided and _resolve_slide_type(slides[0].type) != SlideType.TITLE_SLIDE:
        slides.insert(
            0, GeminiSlidePlan(type=SlideType.TITLE_SLIDE.value, title=plan.title, subtitle="Presentation overview")
        )

    while len(slides) < slide_count:
        slides.append(
            GeminiSlidePlan(
                type=SlideType.TITLE_BULLETS_IMAGE.value,
                title=_fallback_slide_title(plan.title, len(slides) + 1, variant="image"),
                bullets=_fallback_bullets_for_slide(plan.title, plan.title, variant="image", slot=len(slides) + 1),
                image_prompt=_fallback_image_prompt(
                    _fallback_slide_title(plan.title, len(slides) + 1, variant="image"), plan.title
                ),
            )
        )

    slides = slides[:slide_count]
    # Обхождаме `enumerate(slide_outline or [])` като `(index, intent)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for index, intent in enumerate(slide_outline or []):
        # Това условие е decision point: `intent.requested_type and index < len(slides)`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if intent.requested_type and index < len(slides):
            slides[index].type = intent.requested_type.value
    # `normalized_slides` пази резултата от `_normalize_slide_plan`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
    normalized_slides = [_normalize_slide_plan(slide, plan.title, index + 1) for index, slide in enumerate(slides)]
    # Това условие е decision point: `requested_title and normalized_slides`.
    # При вярно условие се активира `(first.title or '').strip`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if requested_title and normalized_slides:
        first = normalized_slides[0]
        # `first_title` пази резултата от `(first.title or '').strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        first_title = (first.title or "").strip()
        # Това условие е decision point: `first.type == SlideType.TITLE_SLIDE.value and first_title and (first_title.lower() != req...`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if (
            first.type == SlideType.TITLE_SLIDE.value
            and first_title
            and first_title.lower() != requested_title.lower()
            and (":" in first_title or len(first_title) > len(requested_title) + 14)
        ):
            first.title = requested_title

    seen_signatures: set[tuple[Any, ...]] = set()
    # Обхождаме `enumerate(normalized_slides, start=1)` като `(index, slide)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for index, slide in enumerate(normalized_slides, start=1):
        # `signature` пази резултата от `(slide.title or '').strip().lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        signature = (
            slide.type,
            (slide.title or "").strip().lower(),
            tuple(bullet.strip().lower() for bullet in slide.bullets),
            tuple(bullet.strip().lower() for bullet in slide.left_bullets),
            tuple(bullet.strip().lower() for bullet in slide.right_bullets),
            slide.quote or "",
            slide.attribution or "",
        )
        # Това условие е decision point: `signature in seen_signatures and slide.type == SlideType.TITLE_BULLETS_IMAGE.value`.
        # При вярно условие се активира `_fallback_slide_title`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if signature in seen_signatures and slide.type == SlideType.TITLE_BULLETS_IMAGE.value:
            # `slide.title` пази резултата от `_fallback_slide_title`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            slide.title = _fallback_slide_title(plan.title, index, variant="image")
            # `slide.bullets` пази резултата от `_fallback_bullets_for_slide`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            slide.bullets = _fallback_bullets_for_slide(plan.title, plan.title, variant="image", slot=index)
            # `slide.image_prompt` пази резултата от `_normalize_image_prompt`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            slide.image_prompt = _normalize_image_prompt(
                slide.image_prompt,
                slide.title,
                plan.title,
                subtitle=slide.subtitle,
                bullets=slide.bullets,
            )
        seen_signatures.add(signature)

    return GeminiPresentationPlan(
        title=plan.title,
        theme=resolve_theme_name(plan.theme),
        slides=normalized_slides,
    )


def _plan_to_presentation(plan: GeminiPresentationPlan) -> Presentation:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `plan_to_presentation` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `plan` (GeminiPresentationPlan); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `Presentation`, `Slide.model_validate`, `slide.model_dump`, `resolve_theme_name`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `Presentation`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `slides` пази резултата от `Slide.model_validate`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
    slides = [Slide.model_validate(slide.model_dump()) for slide in plan.slides]
    return Presentation(
        title=plan.title,
        theme=resolve_theme_name(plan.theme),
        slides=slides,
    )


def _extract_json_text(response: Any) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: изолира полезната част от по-широк или provider-specific резултат.
    # Входът идва през `response` (Any); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `GeminiPlanningError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = getattr(response, "text", None)
    # Това условие е decision point: `text`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`text`) и прескачаме ненужната останала работа.
    if text:
        return text
    # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
    candidates = getattr(response, "candidates", None) or []
    # Това условие е decision point: `candidates`.
    # При вярно условие се активира `getattr`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if candidates:
        parts = getattr(candidates[0].content, "parts", []) or []
        text_parts = [part.text for part in parts if getattr(part, "text", None)]
        # Това условие е decision point: `text_parts`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`''.join(text_parts)`) и прескачаме ненужната останала работа.
        if text_parts:
            return "".join(text_parts)
    raise GeminiPlanningError("Gemini returned an empty planning response.")


def _looks_truncated_json(payload: str) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `looks_truncated_json` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `payload` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `payload.rstrip`, `text.startswith`, `text.endswith`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = payload.rstrip()
    # Това условие е decision point: `not text`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `False`, без да проверява по-слабите правила отдолу.
    if not text:
        return False
    # Това условие е decision point: `not text.startswith('{')`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `False`, без да проверява по-слабите правила отдолу.
    if not text.startswith("{"):
        return False
    return not text.endswith("}")


def _planning_retry_instruction(slide_count: int) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `planning_retry_instruction` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `slide_count` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    return (
        "The previous response was invalid or truncated. "
        f"Retry and return EXACTLY {slide_count} slides as valid compact JSON only. "
        "Keep every bullet under 10 words, keep notes extremely short, and avoid long image_prompt wording. "
        "Do not include prose before or after the JSON."
    )


def _response_parts(response: Any) -> list[Any]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `response_parts` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `response` (Any); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[Any]`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    direct_parts = getattr(response, "parts", None)
    # Това условие е decision point: `direct_parts`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`list(direct_parts)`) и прескачаме ненужната останала работа.
    if direct_parts:
        return list(direct_parts)
    # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
    candidates = getattr(response, "candidates", None) or []
    # Това условие е decision point: `not candidates`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
    if not candidates:
        return []
    return list(getattr(candidates[0].content, "parts", []) or [])


def _inline_data_bytes(part: Any) -> bytes | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `inline_data_bytes` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `part` (Any); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `base64.b64decode`, `data.encode`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bytes | None`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    inline_data = getattr(part, "inline_data", None)
    data = getattr(inline_data, "data", None)
    # Това условие е decision point: `isinstance(data, bytes)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`data`) и прескачаме ненужната останала работа.
    if isinstance(data, bytes):
        return data
    # Това условие е decision point: `not isinstance(data, str)`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not isinstance(data, str):
        return None
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        return base64.b64decode(data, validate=True)
    except Exception:
        return data.encode("latin1")


def _image_helper_bytes(part: Any) -> bytes | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `image_helper_bytes` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `part` (Any); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `callable`, `as_image`, `BytesIO`, `buffer.getvalue`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bytes | None`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    as_image = getattr(part, "as_image", None)
    # Това условие е decision point: `not callable(as_image)`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not callable(as_image):
        return None
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        # `image` пази резултата от `as_image`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        image = as_image()
        # Това условие е decision point: `image is None`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
        if image is None:
            return None
        # Това условие е decision point: `isinstance(getattr(image, 'data', None), bytes)`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`image.data`) и прескачаме ненужната останала работа.
        if isinstance(getattr(image, "data", None), bytes):
            return image.data
        # Това условие е decision point: `not hasattr(image, 'save')`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
        if not hasattr(image, "save"):
            return None
        # `buffer` пази резултата от `BytesIO`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        buffer = BytesIO()
        # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
        # `try/except` превръща техническите грешки (TypeError) в предвидимо поведение за горния слой.
        try:
            image.save(buffer, format="PNG")
        except TypeError:
            image.save(buffer)
        return buffer.getvalue()
    except Exception as exc:
        logger.warning("Failed to extract image via as_image: %s", exc)
        return None


def _extract_image_bytes(response: Any) -> bytes:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: изолира полезната част от по-широк или provider-specific резултат.
    # Входът идва през `response` (Any); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_response_parts`, `GeminiImageGenerationError`, `_inline_data_bytes`, `_image_helper_bytes`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bytes`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # Обхождаме `_response_parts(response)` като `part`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for part in _response_parts(response):
        # `image_bytes` е суровото binary съдържание на изображението преди оптимизация и запис.
        image_bytes = _inline_data_bytes(part)
        # Това условие е decision point: `image_bytes is None`.
        # При вярно условие се активира `_image_helper_bytes`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if image_bytes is None:
            # `image_bytes` е суровото binary съдържание на изображението преди оптимизация и запис.
            image_bytes = _image_helper_bytes(part)
        # Това условие е decision point: `image_bytes is not None`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`image_bytes`) и прескачаме ненужната останала работа.
        if image_bytes is not None:
            return image_bytes

    raise GeminiImageGenerationError("Gemini did not return valid image bytes in any part.")


async def generate_presentation(
    prompt: str,
    slide_count: int,
    style: str,
    planning_mode: PlanningMode = PlanningMode.AUTOMATIC,
    slide_outline: list[GuidedSlideIntent] | None = None,
) -> Presentation:
    # Роля в pipeline-а: Изпраща planning заявката към Gemini, валидира provider отговора и го превръща в стабилен Presentation domain модел.
    # Входът идва през `prompt` (str), `slide_count` (int), `style` (str), `planning_mode` (PlanningMode), `slide_outline` (list[GuidedSlideIntent] | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_settings`, `get_client`, `_normalize_plan`, `_plan_to_presentation`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `Presentation`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `settings` е конфигурацията от environment, която включва или изключва външни услуги и избира модели.
    settings = get_settings()
    logger.info(
        "Gemini planning request starting. model=%s slide_count=%s style=%s planning_mode=%s prompt_chars=%s",
        settings.gemini_planning_model,
        slide_count,
        style,
        planning_mode,
        len(prompt),
    )

    # Това условие е decision point: `planning_mode == PlanningMode.GUIDED and slide_outline`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`_plan_to_presentation(_fallback_plan_from_request(prompt, slide_count, style, slide_outli...`) и прескачаме ненужната останала работа.
    if planning_mode == PlanningMode.GUIDED and slide_outline:
        logger.info("Guided planning using local slide outline. slide_count=%s", slide_count)
        return _plan_to_presentation(_fallback_plan_from_request(prompt, slide_count, style, slide_outline))

    # `client` е клиентът към външния provider; държим го отделно, за да не смесваме transport логика с domain решения.
    client = get_client()
    outline_prompt = ""
    # Това условие е decision point: `planning_mode == PlanningMode.GUIDED`.
    # При вярно условие се активира `f"\n\nORDERED SLIDE BRIEFS:\nUse this JSON array as a strict ordered plan. Expand each purpose into useful slide content.\nTreat each item as part of the same deck narrative. Avoid repeating points from earlier briefs and make each slide transition naturally from the previous one.\nIf requested_type is null, choose the best allowed type for that slide.\n{json.dumps([item.model_dump(mode='json') for item in slide_outline or []], ensure_ascii=False)}\n".rstrip`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if planning_mode == PlanningMode.GUIDED:
        # `outline_prompt` пази резултата от `f"\n\nORDERED SLIDE BRIEFS:\nUse this JSON array as a strict ordered plan. Expand each purpose into useful slide content.\nTreat each item as part of the same deck narrative. Avoid repeating points from earlier briefs and make each slide transition naturally from the previous one.\nIf requested_type is null, choose the best allowed type for that slide.\n{json.dumps([item.model_dump(mode='json') for item in slide_outline or []], ensure_ascii=False)}\n".rstrip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        outline_prompt = f"""

ORDERED SLIDE BRIEFS:
Use this JSON array as a strict ordered plan. Expand each purpose into useful slide content.
Treat each item as part of the same deck narrative. Avoid repeating points from earlier briefs and make each slide transition naturally from the previous one.
If requested_type is null, choose the best allowed type for that slide.
{json.dumps([item.model_dump(mode="json") for item in slide_outline or []], ensure_ascii=False)}
""".rstrip()

    # `user_prompt` пази резултата от `f'\nCreate a {slide_count}-slide presentation plan.\nRequirement: Generate EXACTLY {slide_count} unique slides.\n\nCONTENT RULES:\n- Maximum 3-4 bullets per slide.\n- Maximum 12-14 words per bullet.\n- Headlines should be concise and informative.\n- Prioritize visual breathing room.\n- Make each slide add new information instead of repeating the topic.\n- Prefer a varied narrative rhythm. Do not turn every slide into title_bullets_image.\n- Adapt the voice to the subject and audience. Write with an intentional point of view.\n- When the brief asks for favorites or opinions, choose specific examples and explain the judgment.\n- For school assignments, stay clear and accurate but avoid lifeless textbook phrasing.\n- If the topic is a short phrase or acronym, keep the presentation title that short; do not add a poetic subtitle into the title.\n- Comparison slides must have real side names, not "Option B" or "Alternative".\n- image_prompt must always be short English only, even when slide titles and bullets are in another language.\n- Add visual_mood and icon_intent metadata for every non-title slide.\n- Allowed slide types: title_slide, title_bullets, title_bullets_image, hero_image, comparison, timeline, statistics, quote.\n\nPreferred direction:\n{style}\n\nSelect a theme name from the registry, but do not describe colors, spacing, fonts, or CSS.\n\nTopic:\n{prompt}\n{outline_prompt}\n\nReturn JSON only.\n'.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    user_prompt = f"""
Create a {slide_count}-slide presentation plan.
Requirement: Generate EXACTLY {slide_count} unique slides.

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
- If the topic is a short phrase or acronym, keep the presentation title that short; do not add a poetic subtitle into the title.
- Comparison slides must have real side names, not "Option B" or "Alternative".
- image_prompt must always be short English only, even when slide titles and bullets are in another language.
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

    planning_error: Exception | None = None
    response_text = ""
    # `plan` е изпълнимият план, който превежда свободния вход към конкретни следващи стъпки.
    plan: GeminiPresentationPlan | None = None
    # Обхождаме `range(2)` като `attempt`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for attempt in range(2):
        # `attempt_prompt` пази резултата от `_planning_retry_instruction`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        attempt_prompt = user_prompt if attempt == 0 else f"{user_prompt}\n\n{_planning_retry_instruction(slide_count)}"
        # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
        # `try/except` превръща техническите грешки (asyncio.TimeoutError, Exception) в предвидимо поведение за горния слой.
        try:
            # Structured output keeps the MVP stable by asking Gemini for JSON that
            # already matches the planning schema instead of free-form text.
            # `response` е суровият отговор от външна услуга, който още трябва да бъде валидиран и нормализиран.
            # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
            response = await _with_optional_timeout(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=settings.gemini_planning_model,
                    contents=attempt_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_json_schema=GEMINI_PLANNING_JSON_SCHEMA,
                        temperature=0.3 if attempt == 0 else 0.15,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        http_options=_http_options(settings.gemini_planning_timeout_seconds),
                    ),
                ),
                settings.gemini_planning_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Gemini planning timed out after %.2fs. Using local fallback plan.",
                perf_counter() - attempt_started_at,
            )
            return _plan_to_presentation(_fallback_plan_from_request(prompt, slide_count, style, slide_outline))
        except Exception as exc:
            provider_message = _provider_message(exc)
            # Това условие е decision point: `planning_mode == PlanningMode.GUIDED and re.search('\\b(timeout|timed out|deadline|504|de...`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`_plan_to_presentation(_fallback_plan_from_request(prompt, slide_count, style, slide_outli...`) и прескачаме ненужната останала работа.
            if planning_mode == PlanningMode.GUIDED and re.search(
                r"\b(timeout|timed out|deadline|504|deadline_exceeded)\b", provider_message, re.IGNORECASE
            ):
                logger.warning(
                    "Gemini planning failed with timeout-like error after %.2fs. Using local fallback plan: %s",
                    perf_counter() - attempt_started_at,
                    provider_message,
                )
                return _plan_to_presentation(_fallback_plan_from_request(prompt, slide_count, style, slide_outline))
            raise GeminiPlanningError(provider_message) from exc

        # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
        # `try/except` превръща техническите грешки ((ValidationError, json.JSONDecodeError, GeminiPlanningError)) в предвидимо поведение за горния слой.
        try:
            # `response_text` пази резултата от `_extract_json_text`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            response_text = _extract_json_text(response)
            plan = GeminiPresentationPlan.model_validate_json(response_text)
            logger.info(
                "Gemini planning response received. attempt=%s duration=%.2fs response_chars=%s",
                attempt + 1,
                perf_counter() - attempt_started_at,
                len(response_text),
            )
            break
        except (ValidationError, json.JSONDecodeError, GeminiPlanningError) as exc:
            planning_error = exc
            logger.warning(
                "Gemini planning returned invalid JSON on attempt %s/2. chars=%s truncated=%s error=%s",
                attempt + 1,
                len(response_text or ""),
                _looks_truncated_json(response_text) if response_text else False,
                exc,
            )
            # Това условие е decision point: `attempt == 1`.
            # При вярно условие се активира `GeminiPlanningError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if attempt == 1:
                logger.exception("Gemini planning failed after retry.")
                raise GeminiPlanningError("Gemini returned invalid presentation JSON.") from exc
    else:  # pragma: no cover - defensive loop guard
        raise GeminiPlanningError("Gemini returned invalid presentation JSON.") from planning_error

    # `normalized_plan` пази резултата от `_normalize_plan`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    normalized_plan = _normalize_plan(
        plan, slide_count, slide_outline if planning_mode == PlanningMode.GUIDED else None, source_prompt=prompt
    )
    # `presentation` е централният domain обект, който постепенно се обогатява със съдържание, изображения и export информация.
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
    # Роля в pipeline-а: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
    # Входът идва през `slide` (Any), `style` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest`, `hashlib.sha256`, `hasattr`, `item.model_dump`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `payload` пази резултата от `hasattr`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
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
        "timeline": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in getattr(slide, "timeline", [])
        ],
        "statistics": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in getattr(slide, "statistics", [])
        ],
        "quote": getattr(slide, "quote", ""),
        "image_prompt": getattr(slide, "image_prompt", ""),
    }
    # `digest` пази резултата от `hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:24]


def get_image_model_name() -> str:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Основните преходи навън са към `get_settings`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    return get_settings().gemini_image_model


async def generate_slide_image(prompt: str) -> bytes:
    # Роля в pipeline-а: стартира генериращ етап и нормализира резултата му преди да го предаде нататък.
    # Входът идва през `prompt` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_settings`, `get_client`, `_extract_image_bytes`, `_with_optional_timeout`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `bytes`. Резултатът се нормализира до domain модел, за да не изтичат provider-specific особености към останалия backend.
    # `settings` е конфигурацията от environment, която включва или изключва външни услуги и избира модели.
    settings = get_settings()
    # `client` е клиентът към външния provider; държим го отделно, за да не смесваме transport логика с domain решения.
    client = get_client()
    final_prompt = (
        "Create one grounded, presentation-ready 16:9 visual. "
        "It should feel like a real slide asset: relevant, restrained, and clean. "
        "Use the slide context literally and prioritize the most specific subject mentioned. "
        "Avoid generic AI art, glowing abstract backgrounds, floating icons, random labs, random office workers, and sensational stock-photo cliches. "
        "Do not render visible text, labels, captions, logos, UI copy, or unrelated decorative symbolism. "
        f"Prompt: {prompt}"
    )

    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (GeminiImageGenerationError, asyncio.TimeoutError, Exception) в предвидимо поведение за горния слой.
    try:
        # The image model is isolated from planning so image failures do not
        # corrupt the slide JSON generation step.
        # `response` е суровият отговор от външна услуга, който още трябва да бъде валидиран и нормализиран.
        # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
        response = await _with_optional_timeout(
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
            settings.gemini_image_timeout_seconds,
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
