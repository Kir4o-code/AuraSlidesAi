# Роля на модула: Превръща свободното описание на изображение в кратък и изпълним search plan.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import importlib.util
import json
import re
from typing import Any

from app.image_research.config import settings
from app.image_research.core.image_classes import ImageClass, get_class_profile, infer_image_class
from app.image_research.schemas import ImageResearchRequest, SearchPlan

VALID_ORIENTATIONS = {"any", "landscape", "portrait", "square"}
VALID_TYPES = {"photo", "illustration", "icon", "diagram", "any"}
TYPE_ALIASES = {"graph": "diagram", "chart": "diagram", "schema": "diagram"}
QUERY_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "background",
    "captions",
    "clean",
    "deck",
    "displaying",
    "for",
    "generic",
    "grounded",
    "image",
    "keep",
    "labels",
    "logos",
    "match",
    "modern",
    "no",
    "or",
    "presentation",
    "relevant",
    "restrained",
    "setting",
    "symbols",
    "the",
    "visible",
    "visual",
    "with",
    "words",
    "и",
    "в",
    "във",
    "на",
    "за",
    "от",
    "до",
    "по",
    "под",
    "над",
    "към",
    "при",
    "през",
    "но",
    "или",
    "г",
    "година",
    "години",
    "slide",
    "context",
    "show",
    "most",
    "relevant",
    "concrete",
    "scene",
    "object",
    "person",
    "place",
    "process",
}


def canonical_image_type(value: str | None) -> str:
    # Роля в pipeline-а: уеднаквява външна стойност към вътрешния речник на приложението.
    # Входът идва през `value` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `clean` пази резултата от `(value or 'any').strip().lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    clean = (value or "any").strip().lower()
    return TYPE_ALIASES.get(clean, clean if clean in VALID_TYPES else "any")


def compact_search_query(value: str, max_length: int = 95) -> str:
    # Роля в pipeline-а: съкращава входа до размер, приемлив за външна услуга, без да губи основния смисъл.
    # Входът идва през `value` (str), `max_length` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.search`, `re.findall`, `seen.add`, `match.group`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = " ".join(value.split())
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = re.split(r"\bKeep it\b|\bMatch a\b|\bNo visible\b", text, maxsplit=1, flags=re.I)[0]
    # `match` пази резултата от `re.search`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    match = re.search(r"Presentation visual for ['\"]([^'\"]+)['\"]:\s*(.+)", text, flags=re.I)
    # Това условие е decision point: `match`.
    # При вярно условие се активира `match.group`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if match:
        # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
        text = f"{match.group(1)} {match.group(2)}"
    # `words` е думите от заглавието след Unicode нормализация; те са суровината за безопасния slug.
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    out: list[str] = []
    seen: set[str] = set()
    # Обхождаме `words` като `word`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for word in words:
        # `key` пази резултата от `word.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        key = word.lower()
        # Това условие е decision point: `key in QUERY_STOP_WORDS or key in seen`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if key in QUERY_STOP_WORDS or key in seen:
            continue
        seen.add(key)
        # `next_value` пази резултата от `' '.join`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        next_value = " ".join([*out, word])
        # Това условие е decision point: `len(next_value) > max_length`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if len(next_value) > max_length:
            break
        out.append(word)
    return " ".join(out) or value[:max_length].strip()


class SearchPlanner:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    def __init__(self) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `importlib.util.find_spec`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        # `self.groq_available` пази резултата от `importlib.util.find_spec`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.groq_available = importlib.util.find_spec("groq") is not None

    async def create_plan(self, request: ImageResearchRequest) -> tuple[SearchPlan, list[str]]:
        # Роля в pipeline-а: Превежда свободния image prompt към структуриран SearchPlan и използва deterministic fallback, ако AI planner-ът не е наличен.
        # Входът идва през `self` (неуточнен тип), `request` (ImageResearchRequest); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._fallback`, `self._create_groq_plan`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `tuple[SearchPlan, list[str]]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        warnings: list[str] = []
        # Това условие е decision point: `self.api_key and self.groq_available`.
        # При вярно условие се активира `warnings.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if self.api_key and self.groq_available:
            # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
            # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
            try:
                return await self._create_groq_plan(request), warnings
            except Exception as exc:
                warnings.append(f"Groq planning failed; used fallback planner: {exc}")
        return self._fallback(request), warnings

    async def _create_groq_plan(self, request: ImageResearchRequest) -> SearchPlan:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `create_groq_plan` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `request` (ImageResearchRequest); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `AsyncGroq`, `infer_image_class`, `get_class_profile`, `self._normalize`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `SearchPlan`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        from groq import AsyncGroq

        # `client` е клиентът към външния provider; държим го отделно, за да не смесваме transport логика с domain решения.
        client = AsyncGroq(api_key=self.api_key)
        # `image_class` пази резултата от `infer_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        image_class = infer_image_class(request.prompt, request.image_class or request.image_type)
        # `profile` пази резултата от `get_class_profile`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        profile = get_class_profile(image_class)
        # `prompt` е инструкцията, която носи визуалния или съдържателния смисъл към следващия AI/search етап.
        prompt = {
            "user_prompt": request.prompt,
            "style": request.style,
            "preferred_orientation": request.preferred_orientation,
            "requested_image_type": request.image_type,
            "image_class": image_class.value,
            "class_terms": list(profile.query_terms),
        }
        # `response` е суровият отговор от външна услуга, който още трябва да бъде валидиран и нормализиран.
        # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
        response = await client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Create a generic image search strategy. Return strict JSON only. "
                        "Do not choose images. Do not judge copyright. Include keys: "
                        "main_query, alternative_queries, visual_requirements, bad_terms, "
                        "preferred_orientation, image_type, image_class. Orientation must be one of "
                        "any, landscape, portrait, square. image_type must be one of "
                        "photo, illustration, icon, diagram, any. image_class must be one of "
                        "photo, illustration, icon, diagram. alternative_queries, "
                        "visual_requirements, and bad_terms must always be JSON arrays of strings. "
                        "For exact people, places, events, artifacts, or historical topics, prefer "
                        "specific factual search terms over vague stock-photo wording. bad_terms "
                        "should include likely false positives such as replicas, reenactments, "
                        "memorials, fictional depictions, or modern staged results when those would "
                        "not satisfy the user's requested intent."
                        " If the prompt names a country, person, event, song, team, place, or era, "
                        "include factual aliases, official names, relevant years, and named entities "
                        "that are likely to produce exact media. Do not invent years or names. "
                        "If the prompt is not English, create English search queries while preserving "
                        "original named entities. For education or biology structure requests, prefer "
                        "diagram, anatomy, labeled illustration, cross section, and educational terms."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        # `data` пази резултата от `self._normalize`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        data = self._normalize(json.loads(content), request)
        # `plan` е изпълнимият план, който превежда свободния вход към конкретни следващи стъпки.
        plan = SearchPlan(**data)
        # Това условие е decision point: `plan.preferred_orientation not in VALID_ORIENTATIONS`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if plan.preferred_orientation not in VALID_ORIENTATIONS:
            plan.preferred_orientation = request.preferred_orientation
        # `plan.image_type` пази резултата от `canonical_image_type`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        plan.image_type = canonical_image_type(plan.image_type)
        # `plan.image_class` пази резултата от `infer_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        plan.image_class = infer_image_class(plan.main_query, plan.image_class or plan.image_type).value
        return plan

    def _normalize(self, data: dict[str, Any], request: ImageResearchRequest) -> dict[str, Any]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
        # Входът идва през `self` (неуточнен тип), `data` (dict[str, Any]), `request` (ImageResearchRequest); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `infer_image_class`, `get_class_profile`, `text`, `texts`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `dict[str, Any]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        def text(value: Any, fallback: str = "") -> str:
            # Роля в pipeline-а: обработва стъпката `text` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
            # Входът идва през `value` (Any), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
            # Функцията работи основно с локални стойности и не делегира към други services.
            # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
            # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
            return str(value).strip() if value is not None else fallback

        def texts(value: Any) -> list[str]:
            # Това условие е decision point: `value is None`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
            # Роля в pipeline-а: обработва стъпката `texts` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
            # Входът идва през `value` (Any); имената показват каква част от контекста е собственост на тази стъпка.
            # Основните преходи навън са към `text`, `value.replace`; така се вижда кои отговорности функцията делегира.
            # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
            # Изходен договор: `list[str]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
            if value is None:
                return []
            # Това условие е decision point: `isinstance(value, list)`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[text(item) for item in value if text(item)]`) и прескачаме ненужната останала работа.
            if isinstance(value, list):
                return [text(item) for item in value if text(item)]
            # Това условие е decision point: `isinstance(value, str)`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[part.strip() for part in value.replace(';', ',').split(',') if part.strip()]`) и прескачаме ненужната останала работа.
            if isinstance(value, str):
                return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
            return [text(value)] if text(value) else []

        # `image_class` пази резултата от `infer_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        image_class = infer_image_class(
            " ".join([request.prompt, text(data.get("main_query"), ""), text(data.get("image_class"), "")]),
            text(data.get("image_class"), request.image_class or request.image_type or "any"),
        )
        # `profile` пази резултата от `get_class_profile`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        profile = get_class_profile(image_class)
        # `bad_terms` пази резултата от `texts`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        bad_terms = [*texts(data.get("bad_terms")), *profile.bad_terms]
        # `visual_requirements` пази резултата от `texts`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        visual_requirements = [*texts(data.get("visual_requirements")), *profile.clip_context]
        return {
            "main_query": text(data.get("main_query"), request.prompt) or request.prompt,
            "alternative_queries": texts(data.get("alternative_queries")),
            "visual_requirements": visual_requirements,
            "bad_terms": bad_terms,
            "preferred_orientation": text(data.get("preferred_orientation"), request.preferred_orientation),
            "image_type": canonical_image_type(text(data.get("image_type"), request.image_type or "any")),
            "image_class": image_class.value,
        }

    def _fallback(self, request: ImageResearchRequest) -> SearchPlan:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `fallback` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `request` (ImageResearchRequest); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `compact_search_query`, `infer_image_class`, `get_class_profile`, `SearchPlan`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `SearchPlan`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        # `query` пази резултата от `compact_search_query`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        query = compact_search_query(request.prompt)
        # `image_class` пази резултата от `infer_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        image_class = infer_image_class(request.prompt, request.image_class or request.image_type)
        # `profile` пази резултата от `get_class_profile`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        profile = get_class_profile(image_class)
        alternative_queries: list[str] = []
        # Това условие е decision point: `image_class != ImageClass.PHOTO`.
        # При вярно условие се активира `f'{query} {term}'.strip`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if image_class != ImageClass.PHOTO:
            # `alternative_queries` пази резултата от `f'{query} {term}'.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            alternative_queries = [
                *[f"{query} {term}".strip() for term in profile.query_terms[:2]],
            ]
        return SearchPlan(
            main_query=query,
            alternative_queries=alternative_queries,
            visual_requirements=[
                "The image should clearly match the user prompt",
                "The image should be visually clean and usable",
                *profile.clip_context,
            ],
            bad_terms=list(profile.bad_terms),
            preferred_orientation=request.preferred_orientation,
            image_type=canonical_image_type(request.image_type),
            image_class=image_class.value,
        )
