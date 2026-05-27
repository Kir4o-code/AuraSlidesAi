import importlib.util
import json
import re
from typing import Any

from app.image_research.config import settings
from app.image_research.core.image_classes import get_class_profile, infer_image_class
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
}


def canonical_image_type(value: str | None) -> str:
    clean = (value or "any").strip().lower()
    return TYPE_ALIASES.get(clean, clean if clean in VALID_TYPES else "any")


def compact_search_query(value: str, max_length: int = 95) -> str:
    text = " ".join(value.split())
    text = re.split(r"\bKeep it\b|\bMatch a\b|\bNo visible\b", text, maxsplit=1, flags=re.I)[0]
    match = re.search(r"Presentation visual for ['\"]([^'\"]+)['\"]:\s*(.+)", text, flags=re.I)
    if match:
        text = f"{match.group(1)} {match.group(2)}"
    words = re.findall(r"[A-Za-z0-9]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for word in words:
        key = word.lower()
        if key in QUERY_STOP_WORDS or key in seen:
            continue
        seen.add(key)
        next_value = " ".join([*out, word])
        if len(next_value) > max_length:
            break
        out.append(word)
    return " ".join(out) or value[:max_length].strip()


class SearchPlanner:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.groq_available = importlib.util.find_spec("groq") is not None

    async def create_plan(self, request: ImageResearchRequest) -> tuple[SearchPlan, list[str]]:
        warnings: list[str] = []
        if self.api_key and self.groq_available:
            try:
                return await self._create_groq_plan(request), warnings
            except Exception as exc:
                warnings.append(f"Groq planning failed; used fallback planner: {exc}")
        return self._fallback(request), warnings

    async def _create_groq_plan(self, request: ImageResearchRequest) -> SearchPlan:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self.api_key)
        image_class = infer_image_class(request.prompt, request.image_class or request.image_type)
        profile = get_class_profile(image_class)
        prompt = {
            "user_prompt": request.prompt,
            "style": request.style,
            "preferred_orientation": request.preferred_orientation,
            "requested_image_type": request.image_type,
            "image_class": image_class.value,
            "class_terms": list(profile.query_terms),
        }
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
        data = self._normalize(json.loads(content), request)
        plan = SearchPlan(**data)
        if plan.preferred_orientation not in VALID_ORIENTATIONS:
            plan.preferred_orientation = request.preferred_orientation
        plan.image_type = canonical_image_type(plan.image_type)
        plan.image_class = infer_image_class(plan.main_query, plan.image_class or plan.image_type).value
        return plan

    def _normalize(self, data: dict[str, Any], request: ImageResearchRequest) -> dict[str, Any]:
        def text(value: Any, fallback: str = "") -> str:
            return str(value).strip() if value is not None else fallback

        def texts(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [text(item) for item in value if text(item)]
            if isinstance(value, str):
                return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
            return [text(value)] if text(value) else []

        image_class = infer_image_class(
            " ".join([request.prompt, text(data.get("main_query"), ""), text(data.get("image_class"), "")]),
            text(data.get("image_class"), request.image_class or request.image_type or "any"),
        )
        profile = get_class_profile(image_class)
        bad_terms = [*texts(data.get("bad_terms")), *profile.bad_terms]
        visual_requirements = [*texts(data.get("visual_requirements")), *profile.clip_context]
        return {
            "main_query": text(data.get("main_query"), request.prompt) or request.prompt,
            "alternative_queries": texts(data.get("alternative_queries")),
            "visual_requirements": visual_requirements,
            "bad_terms": bad_terms,
            "preferred_orientation": text(
                data.get("preferred_orientation"), request.preferred_orientation
            ),
            "image_type": canonical_image_type(text(data.get("image_type"), request.image_type or "any")),
            "image_class": image_class.value,
        }

    def _fallback(self, request: ImageResearchRequest) -> SearchPlan:
        style = request.style or ""
        query = compact_search_query(request.prompt)
        image_class = infer_image_class(request.prompt, request.image_class or request.image_type)
        profile = get_class_profile(image_class)
        return SearchPlan(
            main_query=query,
            alternative_queries=[
                f"{query} {style}".strip(),
                *[f"{query} {term}".strip() for term in profile.query_terms[:3]],
                f"{query} Wikimedia Commons",
            ],
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
