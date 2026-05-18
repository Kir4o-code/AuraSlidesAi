import asyncio
import re
import uuid

from app.config import settings
from app.core.clip_scorer import ClipScorer
from app.core.downloader import download_image
from app.core.license_checker import is_allowed_license, license_score
from app.core.search_planner import SearchPlanner
from app.core.storage import copy_best_image, ensure_output_dirs, save_metadata, slugify
from app.providers.openverse import OpenverseProvider
from app.providers.pexels import PexelsProvider
from app.providers.pixabay import PixabayProvider
from app.providers.wikimedia import WikimediaProvider
from app.schemas import (
    ImageCandidate,
    ImageResearchRequest,
    ImageResearchResponse,
    SearchPlan,
    SelectedImage,
)


class ImageResearcher:
    def __init__(self) -> None:
        ensure_output_dirs()
        self.planner = SearchPlanner()
        self.scorer = ClipScorer(settings.clip_model)
        self.providers = [WikimediaProvider(), OpenverseProvider()]
        if settings.pexels_api_key:
            self.providers.append(PexelsProvider(settings.pexels_api_key))
        if settings.pixabay_api_key:
            self.providers.append(PixabayProvider(settings.pixabay_api_key))

    async def research(self, request: ImageResearchRequest) -> ImageResearchResponse:
        request_id = f"research_{uuid.uuid4().hex[:12]}"
        prompt_slug = slugify(request.prompt)
        warnings: list[str] = []
        search_plan: SearchPlan | None = None
        scored: list[ImageCandidate] = []

        try:
            search_plan, plan_warnings = await self.planner.create_plan(request)
            warnings.extend(plan_warnings)
            candidates = await self._search(search_plan, request.max_candidates, warnings)
            candidates = self._dedupe(candidates)
            candidates = [c for c in candidates if is_allowed_license(c.license_name)]
            if not candidates:
                warnings.append("No candidates passed license filtering.")
                return self._empty(search_plan, warnings)

            ranked = self._rank_before_download(candidates, request, search_plan)
            downloaded = await self._download(ranked[: request.max_candidates], request_id, warnings)
            if not downloaded:
                warnings.append("No candidates could be downloaded and validated.")
                return self._empty(search_plan, warnings)

            clip_prompt = (
                f"An image matching this request: {request.prompt}. "
                f"Desired style: {request.style or 'any'}. "
                "The image should clearly represent the user's intent and be visually useful."
            )
            try:
                scores = self.scorer.score_images(
                    [c.local_temp_path or "" for c in downloaded],
                    clip_prompt,
                )
            except Exception as exc:
                warnings.append(f"CLIP scoring failed; used metadata ranking only: {exc}")
                scores = [self._metadata_score(c, request, search_plan) for c in downloaded]
            scored = self._score(downloaded, scores, request, search_plan)
            best = max(scored, key=lambda c: c.final_score or 0)
            best_path = copy_best_image(best.local_temp_path or "", request_id, prompt_slug)

            selected = SelectedImage(
                local_path=f"output/images/{prompt_slug}/{best_path.name}",
                public_url=f"/images/{prompt_slug}/{best_path.name}",
                source=best.source,
                source_url=best.source_url,
                image_url=best.image_url,
                author=best.author,
                license_name=best.license_name,
                width=best.width,
                height=best.height,
                clip_score=best.clip_score,
                final_score=best.final_score,
            )
            save_metadata(
                request_id,
                {
                    "original_request": request.model_dump(),
                    "search_plan": search_plan.model_dump(),
                    "selected_image": selected.model_dump(),
                    "scored_candidates": [c.model_dump() for c in scored],
                    "warnings": warnings,
                },
                prompt_slug,
            )
            return ImageResearchResponse(
                success=True,
                selected_image=selected,
                search_plan=search_plan,
                candidate_count=len(scored),
                warnings=warnings,
            )
        except Exception as exc:
            warnings.append(f"Research failed: {exc}")
            return ImageResearchResponse(
                success=False,
                selected_image=None,
                search_plan=search_plan,
                candidate_count=len(scored),
                warnings=warnings,
            )

    async def _search(
        self, plan: SearchPlan, max_candidates: int, warnings: list[str]
    ) -> list[ImageCandidate]:
        queries = [plan.main_query, *plan.alternative_queries]
        per_page = max(8, min(max_candidates * 3, 30))
        tasks = []
        for provider in self.providers:
            for query in queries:
                tasks.append(provider.search(query, per_page, plan.preferred_orientation))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        candidates: list[ImageCandidate] = []
        for result in results:
            if isinstance(result, Exception):
                warnings.append(f"Provider search failed: {result}")
            else:
                candidates.extend(result)
        return candidates

    def _dedupe(self, candidates: list[ImageCandidate]) -> list[ImageCandidate]:
        seen: set[str] = set()
        out: list[ImageCandidate] = []
        for candidate in candidates:
            if candidate.image_url in seen:
                continue
            seen.add(candidate.image_url)
            out.append(candidate)
        return out

    def _rank_before_download(
        self,
        candidates: list[ImageCandidate],
        request: ImageResearchRequest,
        plan: SearchPlan,
    ) -> list[ImageCandidate]:
        return sorted(
            candidates,
            key=lambda candidate: (
                self._metadata_score(candidate, request, plan),
                self._resolution_score(candidate),
                self._source_score(candidate.source),
            ),
            reverse=True,
        )

    async def _download(
        self, candidates: list[ImageCandidate], request_id: str, warnings: list[str]
    ) -> list[ImageCandidate]:
        async def one(candidate: ImageCandidate) -> ImageCandidate | Exception:
            try:
                candidate.local_temp_path = await download_image(candidate.image_url, request_id)
                return candidate
            except Exception as exc:
                return exc

        results = await asyncio.gather(*(one(c) for c in candidates))
        downloaded: list[ImageCandidate] = []
        for result in results:
            if isinstance(result, Exception):
                warnings.append(f"Candidate download failed: {result}")
            else:
                downloaded.append(result)
        return downloaded

    def _score(
        self,
        candidates: list[ImageCandidate],
        clip_scores: list[float],
        request: ImageResearchRequest,
        plan: SearchPlan,
    ) -> list[ImageCandidate]:
        if not candidates:
            return []
        low = min(clip_scores)
        high = max(clip_scores)
        span = high - low
        for candidate, raw in zip(candidates, clip_scores):
            normalized = 1.0 if span == 0 else (raw - low) / span
            candidate.clip_score = round(raw, 6)
            metadata = self._metadata_score(candidate, request, plan)
            candidate.final_score = round(
                normalized * 0.45
                + metadata * 0.30
                + license_score(candidate.license_name) * 0.10
                + self._source_score(candidate.source) * 0.10
                + self._resolution_score(candidate) * 0.05,
                6,
            )
        return candidates

    def _tokens(self, value: str) -> set[str]:
        stop = {
            "the",
            "and",
            "for",
            "with",
            "image",
            "photo",
            "photograph",
            "picture",
            "quality",
            "style",
        }
        out: set[str] = set()
        for token in re.findall(r"[a-z0-9]+", value.lower()):
            if token in stop:
                continue
            if len(token) > 2 or token.isdigit() or token in {"i", "ii", "iii", "iv", "v"}:
                out.add(token)
        return out

    def _metadata_score(
        self,
        candidate: ImageCandidate,
        request: ImageResearchRequest | None,
        plan: SearchPlan | None,
    ) -> float:
        text = " ".join(
            [
                candidate.title or "",
                candidate.author or "",
                candidate.source_url or "",
                " ".join(candidate.tags),
            ]
        ).lower()
        core_text = " ".join(
            [
                request.prompt if request else "",
                plan.main_query if plan else "",
                " ".join(plan.alternative_queries) if plan else "",
            ]
        )
        visual_text = " ".join(plan.visual_requirements) if plan else ""
        query_tokens = self._tokens(core_text)
        visual_tokens = self._tokens(visual_text)
        if not query_tokens:
            return self._source_score(candidate.source) * 0.25
        matched = sum(1 for token in query_tokens if token in text)
        visual_matched = sum(1 for token in visual_tokens if token in text)
        score = min(1.0, matched / max(1, len(query_tokens))) * 0.72
        score += min(1.0, visual_matched / max(1, len(visual_tokens))) * 0.12 if visual_tokens else 0
        phrases = []
        if request:
            phrases.append(request.prompt.lower().strip())
        if plan:
            phrases.extend([plan.main_query.lower().strip(), *[q.lower().strip() for q in plan.alternative_queries]])
        if any(len(phrase) > 3 and phrase in text for phrase in phrases):
            score += 0.32
        elif len(query_tokens) <= 5 and matched < max(1, len(query_tokens) - 1):
            score -= 0.25
        if plan and any(term.lower() in text for term in plan.bad_terms):
            score -= 0.35
        if any(term in text for term in {"reenactment", "replica", "memorial", "statue", "costume"}):
            if plan and any(term in " ".join(plan.visual_requirements).lower() for term in {"authentic", "documentary", "historical"}):
                score -= 0.22
        return max(0.0, min(1.0, score + self._source_score(candidate.source) * 0.15))

    def _resolution_score(self, candidate: ImageCandidate) -> float:
        if not candidate.width or not candidate.height:
            return 0.6
        if candidate.width >= 1200 and candidate.height >= 700:
            return 1.0
        if candidate.width >= 800 and candidate.height >= 500:
            return 0.75
        return 0.5

    def _source_score(self, source: str) -> float:
        return {
            "wikimedia": 1.0,
            "openverse": 0.98,
            "pexels": 0.72,
            "pixabay": 0.70,
        }.get(source, 0.0)

    def _empty(self, search_plan: SearchPlan | None, warnings: list[str]) -> ImageResearchResponse:
        return ImageResearchResponse(
            success=False,
            selected_image=None,
            search_plan=search_plan,
            candidate_count=0,
            warnings=warnings,
        )
