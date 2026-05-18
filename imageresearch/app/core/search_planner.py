import json
from typing import Any

from app.config import settings
from app.schemas import ImageResearchRequest, SearchPlan


VALID_ORIENTATIONS = {"any", "landscape", "portrait", "square"}
VALID_TYPES = {"photo", "illustration", "icon", "diagram", "any"}


class SearchPlanner:
    def __init__(self) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model

    async def create_plan(self, request: ImageResearchRequest) -> tuple[SearchPlan, list[str]]:
        warnings: list[str] = []
        if self.api_key:
            try:
                return await self._create_groq_plan(request), warnings
            except Exception as exc:
                warnings.append(f"Groq planning failed; used fallback planner: {exc}")
        else:
            warnings.append("GROQ_API_KEY missing; used fallback planner.")
        return self._fallback(request), warnings

    async def _create_groq_plan(self, request: ImageResearchRequest) -> SearchPlan:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self.api_key)
        prompt = {
            "user_prompt": request.prompt,
            "style": request.style,
            "preferred_orientation": request.preferred_orientation,
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
                        "preferred_orientation, image_type. Orientation must be one of "
                        "any, landscape, portrait, square. image_type must be one of "
                        "photo, illustration, icon, diagram, any. alternative_queries, "
                        "visual_requirements, and bad_terms must always be JSON arrays of strings. "
                        "For exact people, places, events, artifacts, or historical topics, prefer "
                        "specific factual search terms over vague stock-photo wording. bad_terms "
                        "should include likely false positives such as replicas, reenactments, "
                        "memorials, fictional depictions, or modern staged results when those would "
                        "not satisfy the user's requested intent."
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
        if plan.image_type not in VALID_TYPES:
            plan.image_type = "any"
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

        return {
            "main_query": text(data.get("main_query"), request.prompt) or request.prompt,
            "alternative_queries": texts(data.get("alternative_queries")),
            "visual_requirements": texts(data.get("visual_requirements")),
            "bad_terms": texts(data.get("bad_terms")),
            "preferred_orientation": text(
                data.get("preferred_orientation"), request.preferred_orientation
            ),
            "image_type": text(data.get("image_type"), "any"),
        }

    def _fallback(self, request: ImageResearchRequest) -> SearchPlan:
        style = request.style or ""
        return SearchPlan(
            main_query=request.prompt,
            alternative_queries=[
                f"{request.prompt} {style}".strip(),
                f"{request.prompt} photograph".strip(),
                f"{request.prompt} Wikimedia Commons",
                f"{request.prompt} archival image",
            ],
            visual_requirements=[
                "The image should clearly match the user prompt",
                "The image should be visually clean and usable",
            ],
            bad_terms=[],
            preferred_orientation=request.preferred_orientation,
            image_type="any",
        )
