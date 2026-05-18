import asyncio
from collections import Counter
import logging
import re
import time
import uuid

import httpx

from app.config import settings
from app.core.clip_scorer import ClipScorer
from app.core.downloader import DownloadError, download_image
from app.core.license_checker import is_allowed_license, license_score
from app.core.search_planner import SearchPlanner
from app.core.storage import copy_ranked_image, ensure_output_dirs, save_metadata, slugify
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


logger = logging.getLogger("image_researcher")


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
        started = time.perf_counter()

        try:
            logger.info(
                "research.start id=%s prompt=%r image_type=%s requested=%s",
                request_id,
                request.prompt,
                request.image_type,
                request.max_candidates,
            )
            search_plan, plan_warnings = await self.planner.create_plan(request)
            warnings.extend(plan_warnings)
            logger.info(
                "research.plan id=%s main=%r type=%s alternatives=%s",
                request_id,
                search_plan.main_query,
                search_plan.image_type,
                len(search_plan.alternative_queries),
            )
            candidates = await self._search(search_plan, request, warnings)
            raw_count = len(candidates)
            candidates = self._dedupe(candidates)
            candidates = [c for c in candidates if is_allowed_license(c.license_name)]
            logger.info("research.candidates id=%s raw=%s licensed=%s", request_id, raw_count, len(candidates))
            if not candidates:
                warnings.append("No candidates passed license filtering.")
                return self._empty(search_plan, warnings)

            ranked = self._rank_before_download(candidates, request, search_plan)
            download_limit = min(max(request.max_candidates * 3, 12), 32)
            downloaded = await self._download(
                ranked[:download_limit],
                request_id,
                warnings,
                max(request.max_candidates * 2, request.max_candidates + 4),
            )
            logger.info("research.downloaded id=%s downloaded=%s limit=%s", request_id, len(downloaded), download_limit)
            if not downloaded:
                warnings.append("No candidates could be downloaded and validated.")
                return self._empty(search_plan, warnings)

            clip_prompts = self._clip_prompts(request, search_plan)
            try:
                scores = self.scorer.score_images_against_texts(
                    [c.local_temp_path or "" for c in downloaded],
                    clip_prompts,
                )
            except Exception as exc:
                warnings.append(f"CLIP scoring failed; used metadata ranking only: {exc}")
                scores = [self._metadata_score(c, request, search_plan) for c in downloaded]
            scored = sorted(
                self._score(downloaded, scores, request, search_plan),
                key=lambda c: c.final_score or 0,
                reverse=True,
            )
            selected_images = self._select_images(scored, request_id, prompt_slug, request.max_candidates)
            selected = selected_images[0] if selected_images else None
            logger.info(
                "research.done id=%s selected=%s scored=%s seconds=%.2f warnings=%s",
                request_id,
                len(selected_images),
                len(scored),
                time.perf_counter() - started,
                len(warnings),
            )
            save_metadata(
                request_id,
                {
                    "original_request": request.model_dump(),
                    "search_plan": search_plan.model_dump(),
                    "selected_image": selected.model_dump() if selected else None,
                    "selected_images": [image.model_dump() for image in selected_images],
                    "scored_candidates": [c.model_dump() for c in scored],
                    "warnings": warnings,
                },
                prompt_slug,
            )
            return ImageResearchResponse(
                success=bool(selected),
                selected_image=selected,
                selected_images=selected_images,
                search_plan=search_plan,
                candidate_count=len(scored),
                warnings=warnings,
            )
        except Exception as exc:
            warnings.append(f"Research failed: {exc}")
            return ImageResearchResponse(
                success=False,
                selected_image=None,
                selected_images=[],
                search_plan=search_plan,
                candidate_count=len(scored),
                warnings=warnings,
            )

    async def _search(
        self, plan: SearchPlan, request: ImageResearchRequest, warnings: list[str]
    ) -> list[ImageCandidate]:
        queries = await self._expanded_queries(plan, request, warnings)
        per_page = max(8, min(request.max_candidates * 4, 30))
        task_specs = []
        for provider in self.providers:
            for query in queries:
                if plan.image_type in {"diagram", "illustration", "icon"} and provider.__class__.__name__ == "PexelsProvider":
                    continue
                task_specs.append(
                    (
                        provider.__class__.__name__.replace("Provider", "").lower(),
                        query,
                        provider.search(query, per_page, plan.preferred_orientation, plan.image_type),
                    )
                )
        results = await asyncio.gather(*(task for _, _, task in task_specs), return_exceptions=True)
        candidates: list[ImageCandidate] = []
        errors: Counter[str] = Counter()
        for (provider_name, _, _), result in zip(task_specs, results):
            if isinstance(result, Exception):
                errors[f"{provider_name}: {str(result).splitlines()[0]}"] += 1
            else:
                candidates.extend(result)
        for error, count in errors.items():
            warnings.append(f"Provider search failed {count} time(s): {error}")
        logger.info(
            "research.search queries=%s candidates=%s errors=%s",
            len(queries),
            len(candidates),
            sum(errors.values()),
        )
        return candidates

    async def _expanded_queries(
        self, plan: SearchPlan, request: ImageResearchRequest, warnings: list[str]
    ) -> list[str]:
        queries = [request.prompt]
        type_queries: list[str] = []
        if plan.image_type == "diagram":
            type_queries.extend(
                [
                    f"{plan.main_query} diagram",
                    f"{plan.main_query} labeled diagram",
                    f"{plan.main_query} educational illustration",
                    f"{plan.main_query} cross section",
                ]
            )
        elif plan.image_type in {"illustration", "icon"}:
            type_queries.extend([f"{plan.main_query} {plan.image_type}", f"{plan.main_query} vector"])
        wiki_queries: list[str] = []
        try:
            params = {
                "action": "opensearch",
                "format": "json",
                "search": plan.main_query,
                "limit": 5,
                "namespace": 0,
                "origin": "*",
            }
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=params,
                    headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
                )
                resp.raise_for_status()
                titles = resp.json()[1]
            wiki_queries.extend(title for title in titles if isinstance(title, str))
        except Exception as exc:
            warnings.append(f"Wikipedia query expansion failed: {exc}")
        queries.extend(await self._multilingual_wikipedia_queries(request.prompt, warnings))
        queries.append(plan.main_query)
        queries.extend(type_queries)
        queries.extend(wiki_queries)
        queries.extend(plan.alternative_queries)

        seen: set[str] = set()
        out: list[str] = []
        for query in queries:
            clean = " ".join(query.split())
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                out.append(clean)
        return out[:8]

    async def _multilingual_wikipedia_queries(self, prompt: str, warnings: list[str]) -> list[str]:
        if prompt.isascii():
            return []
        stop_words = {
            "\u0438",
            "\u043d\u0430",
            "\u0437\u0430",
            "\u0441\u044a\u0441",
            "\u0431\u0435\u0437",
            "\u043a\u0430\u0442\u043e",
            "\u043d\u0435\u0433\u043e",
            "\u043d\u0435\u0433\u043e\u0432\u043e\u0442\u043e",
            "\u043d\u0435\u0439\u043d\u043e\u0442\u043e",
            "\u0431\u0438\u043e\u043b\u043e\u0433\u0438\u044f",
            "\u0447\u043e\u0432\u0435\u0448\u043a\u043e\u0442\u043e",
            "\u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e",
        }
        words = [
            word
            for word in re.findall(r"[^\W\d_]{3,}", prompt.lower(), flags=re.UNICODE)
            if word not in stop_words
        ]
        searches = [prompt, *list(reversed(words[:5]))]
        queries: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                for search in searches:
                    resp = await client.get(
                        "https://bg.wikipedia.org/w/api.php",
                        params={
                            "action": "opensearch",
                            "format": "json",
                            "search": search,
                            "limit": 3,
                            "namespace": 0,
                            "origin": "*",
                        },
                        headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
                    )
                    resp.raise_for_status()
                    for title in resp.json()[1][:1]:
                        if isinstance(title, str):
                            queries.append(title)
                            lang = await client.get(
                                "https://bg.wikipedia.org/w/api.php",
                                params={
                                    "action": "query",
                                    "format": "json",
                                    "titles": title,
                                    "prop": "langlinks",
                                    "lllang": "en",
                                    "origin": "*",
                                },
                                headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
                            )
                            lang.raise_for_status()
                            pages = (lang.json().get("query") or {}).get("pages") or {}
                            for page in pages.values():
                                for link in page.get("langlinks") or []:
                                    if link.get("lang") == "en" and link.get("*"):
                                        queries.append(link["*"])
        except Exception as exc:
            warnings.append(f"Multilingual query expansion failed: {exc}")
        return queries

    def _dedupe(self, candidates: list[ImageCandidate]) -> list[ImageCandidate]:
        seen: set[str] = set()
        out: list[ImageCandidate] = []
        for candidate in candidates:
            key = candidate.source_url or candidate.image_url
            if candidate.image_url in seen or key in seen:
                continue
            seen.add(candidate.image_url)
            seen.add(key)
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

    def _clip_prompts(self, request: ImageResearchRequest, plan: SearchPlan) -> list[str]:
        prompts = [
            request.prompt,
            plan.main_query,
            plan.image_type,
            f"{request.prompt}. {request.style or ''}".strip(),
            f"{plan.main_query}. {' '.join(plan.visual_requirements)}".strip(),
        ]
        prompts.extend(plan.alternative_queries[:4])
        return [prompt for prompt in prompts if prompt]

    async def _download(
        self,
        candidates: list[ImageCandidate],
        request_id: str,
        warnings: list[str],
        scoring_pool_size: int,
    ) -> list[ImageCandidate]:
        downloaded: list[ImageCandidate] = []
        failures: Counter[str] = Counter()
        wikimedia_rate_limited = False

        for candidate in candidates:
            if len(downloaded) >= scoring_pool_size:
                break
            if wikimedia_rate_limited and candidate.source == "wikimedia":
                failures["wikimedia skipped after rate limit"] += 1
                continue
            try:
                if candidate.source == "wikimedia":
                    await asyncio.sleep(0.9)
                candidate.local_temp_path = await download_image(candidate.image_url, request_id)
                downloaded.append(candidate)
            except DownloadError as exc:
                failures[f"{candidate.source} HTTP {exc.status_code or 'error'}"] += 1
                if candidate.source == "wikimedia" and exc.status_code == 429:
                    wikimedia_rate_limited = True
            except Exception as exc:
                failures[f"{candidate.source} {type(exc).__name__}"] += 1

        for reason, count in failures.items():
            if "429" in reason:
                warnings.append(f"Download rate limited {count} candidate(s): {reason}. Wait briefly or request fewer images.")
            else:
                warnings.append(f"Download skipped {count} candidate(s): {reason}.")
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
                metadata * 0.46
                + normalized * 0.29
                + license_score(candidate.license_name) * 0.10
                + self._source_score(candidate.source) * 0.10
                + self._resolution_score(candidate) * 0.05,
                6,
            )
        return candidates

    def _select_images(
        self,
        candidates: list[ImageCandidate],
        request_id: str,
        prompt_slug: str,
        limit: int,
    ) -> list[SelectedImage]:
        selected: list[SelectedImage] = []
        seen_pages: set[str] = set()
        for candidate in candidates:
            if not candidate.local_temp_path:
                continue
            page_key = candidate.source_url or candidate.image_url
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            path = copy_ranked_image(candidate.local_temp_path, request_id, len(selected) + 1, prompt_slug)
            selected.append(
                SelectedImage(
                    local_path=f"output/images/{prompt_slug}/{path.name}",
                    public_url=f"/images/{prompt_slug}/{path.name}",
                    source=candidate.source,
                    source_url=candidate.source_url,
                    image_url=candidate.image_url,
                    author=candidate.author,
                    license_name=candidate.license_name,
                    width=candidate.width,
                    height=candidate.height,
                    clip_score=candidate.clip_score,
                    final_score=candidate.final_score,
                )
            )
            if len(selected) >= limit:
                break
        return selected

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
        critical_tokens = self._critical_tokens(plan.main_query if plan else core_text)
        text_tokens = self._tokens(text)
        if not query_tokens:
            return self._source_score(candidate.source) * 0.25
        matched = sum(1 for token in query_tokens if token in text_tokens)
        visual_matched = sum(1 for token in visual_tokens if token in text_tokens)
        critical_matched = sum(1 for token in critical_tokens if token in text_tokens)
        score = min(1.0, matched / max(1, len(query_tokens))) * 0.72
        score += min(1.0, visual_matched / max(1, len(visual_tokens))) * 0.12 if visual_tokens else 0
        if critical_tokens and not critical_matched:
            score -= 0.42
        elif critical_tokens:
            score += min(0.22, critical_matched / len(critical_tokens) * 0.22)
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
        if plan and plan.image_type in {"diagram", "illustration", "icon"}:
            educational_terms = {
                "diagram",
                "anatomy",
                "structure",
                "labeled",
                "labelled",
                "cross-section",
                "cross section",
                "illustration",
                "educational",
                "biology",
                "physiology",
            }
            if any(term in text for term in educational_terms):
                score += 0.22
            if candidate.source == "pexels":
                score -= 0.3
            if candidate.source == "pixabay" and not any(term in text for term in educational_terms):
                score -= 0.16
        if any(term in text for term in {"reenactment", "replica", "memorial", "statue", "costume"}):
            if plan and any(term in " ".join(plan.visual_requirements).lower() for term in {"authentic", "documentary", "historical"}):
                score -= 0.22
        return max(0.0, min(1.0, score + self._source_score(candidate.source) * 0.15))

    def _critical_tokens(self, value: str) -> set[str]:
        generic = {
            "human",
            "anatomy",
            "biology",
            "structure",
            "diagram",
            "labeled",
            "labelled",
            "educational",
            "illustration",
            "image",
            "photo",
            "cross",
            "section",
            "system",
            "official",
            "performance",
            "contest",
            "song",
        }
        return {
            token
            for token in self._tokens(value)
            if token not in generic and not token.isdigit()
        }

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
            "pexels": 0.58,
            "pixabay": 0.58,
        }.get(source, 0.0)

    def _empty(self, search_plan: SearchPlan | None, warnings: list[str]) -> ImageResearchResponse:
        return ImageResearchResponse(
            success=False,
            selected_image=None,
            selected_images=[],
            search_plan=search_plan,
            candidate_count=0,
            warnings=warnings,
        )
