import asyncio
from collections import Counter
import hashlib
import logging
from pathlib import Path
import re
import time
import uuid

import httpx

from app.image_research.config import PUBLIC_IMAGES_PREFIX, settings
from app.image_research.core.clip_scorer import ClipScorer
from app.image_research.core.downloader import DownloadError, download_image, track_remote_download
from app.image_research.core.image_classes import get_class_profile, infer_image_class
from app.image_research.core.license_checker import is_allowed_license, license_score
from app.image_research.core.search_planner import SearchPlanner
from app.image_research.core.search_planner import compact_search_query
from app.image_research.core.source_selector import select_image_source_with_reason
from app.image_research.core.storage import (
    copy_ranked_image,
    ensure_output_dirs,
    save_metadata,
    slugify,
)
from app.image_research.providers.wikipedia import WikipediaProvider
from app.image_research.providers.wikimedia_commons import WikimediaCommonsProvider
from app.image_research.providers.unsplash import UnsplashProvider
from app.image_research.schemas import (
    ImageCandidate,
    ImageResearchRequest,
    ImageResearchResponse,
    ImageSourceSelection,
    ResearchImageSource,
    SearchPlan,
    SelectedImage,
)


logger = logging.getLogger("image_researcher")
STOCK_PROVIDER_NAMES = {"unsplash"}
WIKIMEDIA_HEADERS = {
    "User-Agent": "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)",
    "Accept": "application/json; charset=utf-8",
}


class ImageResearcher:
    def __init__(self) -> None:
        ensure_output_dirs()
        self.planner = SearchPlanner()
        self.scorer = ClipScorer(settings.clip_model)
        self.providers = {
            "wikipedia": WikipediaProvider(),
            "wikimedia_commons": WikimediaCommonsProvider(),
            "unsplash": UnsplashProvider(),
        }

    async def research(self, request: ImageResearchRequest) -> ImageResearchResponse:
        request_id = f"research_{uuid.uuid4().hex[:12]}"
        prompt_slug = slugify(request.prompt)
        warnings: list[str] = []
        search_plan: SearchPlan | None = None
        source_selection: ImageSourceSelection | None = None
        scored: list[ImageCandidate] = []
        started = time.perf_counter()

        try:
            logger.info(
                "research.start id=%s prompt=%r context=%r image_type=%s requested=%s prompt_ascii=%s context_ascii=%s",
                request_id,
                request.prompt,
                request.context_text,
                request.image_type,
                request.max_candidates,
                request.prompt.isascii(),
                bool(request.context_text and request.context_text.isascii()),
            )
            search_plan, plan_warnings = await self.planner.create_plan(request)
            search_plan.image_class = infer_image_class(
                " ".join([request.prompt, search_plan.main_query]),
                request.image_class or search_plan.image_class or search_plan.image_type,
            ).value
            warnings.extend(plan_warnings)
            logger.info(
                "research.plan id=%s main=%r type=%s alternatives=%s",
                request_id,
                search_plan.main_query,
                search_plan.image_class,
                len(search_plan.alternative_queries),
            )
            classification_input = request.context_text or request.prompt
            source_selection, selection_reason = select_image_source_with_reason(classification_input, request.prompt)
            logger.info(
                "research.source id=%s entity_type=%s source=%s query=%r confidence=%.2f reason=%s classifier_input=%r planner_query=%r",
                request_id,
                source_selection.entity_type.value,
                source_selection.image_source.value,
                source_selection.search_query,
                source_selection.confidence,
                selection_reason,
                classification_input,
                search_plan.main_query,
            )
            candidates = await self._search(search_plan, request, source_selection, warnings)
            raw_count = len(candidates)
            candidates = self._dedupe(candidates)
            excluded_sources = set(request.exclude_source_urls)
            candidates = [
                c for c in candidates
                if is_allowed_license(c.license_name)
                and (c.source_url or c.image_url) not in excluded_sources
            ]
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
                set(request.exclude_hashes),
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
            selected_images = self._select_images(scored, request_id, prompt_slug, request.max_candidates, search_plan)
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
                    "source_selection": source_selection.model_dump() if source_selection else None,
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
                source_selection=source_selection,
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
                source_selection=source_selection,
                candidate_count=len(scored),
                warnings=warnings,
            )

    async def _search(
        self, plan: SearchPlan, request: ImageResearchRequest, source_selection: ImageSourceSelection, warnings: list[str]
    ) -> list[ImageCandidate]:
        if source_selection.image_source == ResearchImageSource.STOCK:
            return await self._search_stock(plan, request, warnings)
        return await self._search_entity(plan, request, source_selection, warnings)

    async def _search_stock(
        self, plan: SearchPlan, request: ImageResearchRequest, warnings: list[str]
    ) -> list[ImageCandidate]:
        queries = self._stock_queries(plan, request)
        per_page = max(8, min(request.max_candidates * 4, 30))
        task_specs = []
        profile = get_class_profile(plan.image_class)
        for provider_name, provider in self.providers.items():
            if provider_name not in profile.allowed_providers or provider_name not in STOCK_PROVIDER_NAMES:
                continue
            for query in queries:
                task_specs.append(
                    (
                        provider_name,
                        query,
                        provider.search(query, per_page, plan.preferred_orientation, plan.image_class),
                    )
                )
        logger.info(
            "research.stock queries=%s providers=%s image_class=%s",
            queries,
            sorted({provider_name for provider_name, _, _ in task_specs}),
            plan.image_class,
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

    def _stock_queries(self, plan: SearchPlan, request: ImageResearchRequest) -> list[str]:
        queries = [
            compact_search_query(plan.main_query, max_length=60),
            compact_search_query(request.prompt, max_length=60),
            *[compact_search_query(query, max_length=60) for query in plan.alternative_queries[:2]],
        ]
        seen: set[str] = set()
        out: list[str] = []
        for query in queries:
            key = query.lower()
            if query and key not in seen:
                seen.add(key)
                out.append(query)
        return out[:3]

    async def _search_entity(
        self,
        plan: SearchPlan,
        request: ImageResearchRequest,
        source_selection: ImageSourceSelection,
        warnings: list[str],
    ) -> list[ImageCandidate]:
        query = source_selection.search_query or compact_search_query(plan.main_query or request.prompt, max_length=80)
        wiki_provider = self.providers["wikipedia"]
        commons_provider = self.providers["wikimedia_commons"]
        per_page = max(3, min(request.max_candidates * 2, 10))
        logger.info(
            "research.entity entity_type=%s query=%r per_page=%s product_fallback=%s",
            source_selection.entity_type.value,
            query,
            per_page,
            source_selection.entity_type.value == "PRODUCT",
        )

        wiki_candidates = await wiki_provider.search(query, per_page=per_page, orientation=plan.preferred_orientation, image_type=plan.image_class)
        commons_candidates = await commons_provider.search(query, per_page=per_page, orientation=plan.preferred_orientation, image_type=plan.image_class)
        if wiki_candidates:
            logger.info(
                "research.search entity=%s source=wikipedia+commons wikipedia=%s commons=%s",
                source_selection.entity_type.value,
                len(wiki_candidates),
                len(commons_candidates),
            )
            return [*wiki_candidates, *commons_candidates]
        if commons_candidates:
            warnings.append("Wikipedia did not provide a suitable image; Wikimedia Commons fallback used.")
            logger.info("research.search entity=%s source=wikimedia_commons candidates=%s", source_selection.entity_type.value, len(commons_candidates))
            return commons_candidates

        if source_selection.entity_type.value == "PRODUCT":
            warnings.append("Entity image not found on Wikipedia or Wikimedia Commons; falling back to stock provider.")
            return await self._search_stock(plan, request, warnings)

        warnings.append("No suitable entity image found on Wikipedia or Wikimedia Commons.")
        return []

    async def _expanded_queries(
        self, plan: SearchPlan, request: ImageResearchRequest, warnings: list[str]
    ) -> list[str]:
        profile = get_class_profile(plan.image_class)
        if plan.image_class == "photo":
            queries = [
                compact_search_query(plan.main_query, max_length=60),
                compact_search_query(request.prompt, max_length=60),
            ]
            seen: set[str] = set()
            out: list[str] = []
            for query in queries:
                key = query.lower()
                if query and key not in seen:
                    seen.add(key)
                    out.append(query)
            return out[:2]

        # Class context expands generic slide prompts into provider-specific searches.
        queries = [
            compact_search_query(request.prompt),
            compact_search_query(f"{request.prompt} {plan.image_class}"),
            plan.main_query,
        ]
        class_queries = [f"{plan.main_query} {term}" for term in profile.query_terms]
        synonym_queries = self._synonym_queries(plan.main_query, plan.image_class)
        wiki_queries = await self._wikipedia_related_queries(plan.main_query, warnings)
        queries.extend(await self._multilingual_wikipedia_queries(request.prompt, warnings))
        queries.extend(class_queries)
        queries.extend(synonym_queries)
        queries.extend(wiki_queries)
        queries.extend(plan.alternative_queries)

        seen: set[str] = set()
        out: list[str] = []
        for query in queries:
            clean = compact_search_query(query)
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                out.append(clean)
        return out[:8]

    async def _wikipedia_related_queries(self, query: str, warnings: list[str]) -> list[str]:
        queries: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "format": "json",
                        "search": query,
                        "limit": 5,
                        "namespace": 0,
                    },
                    headers=WIKIMEDIA_HEADERS,
                )
                resp.raise_for_status()
                titles = [title for title in resp.json()[1] if isinstance(title, str)]
                queries.extend(titles)
                if titles:
                    cat_resp = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={
                            "action": "query",
                            "format": "json",
                            "titles": "|".join(titles[:3]),
                            "prop": "categories|pageimages",
                            "cllimit": 10,
                            "piprop": "name|original",
                        },
                        headers=WIKIMEDIA_HEADERS,
                    )
                    cat_resp.raise_for_status()
                    pages = (cat_resp.json().get("query") or {}).get("pages") or {}
                    for page in pages.values():
                        if page.get("title"):
                            queries.append(str(page["title"]))
                        for category in page.get("categories") or []:
                            title = str(category.get("title", "")).replace("Category:", "")
                            if not title.lower().startswith(("articles ", "cs1 ", "webarchive", "pages ")):
                                queries.append(title)
        except Exception as exc:
            warnings.append(f"Wikipedia query expansion failed: {exc}")
        return queries

    def _synonym_queries(self, query: str, image_class: str) -> list[str]:
        synonyms = {
            "photo": ("photograph", "documentary image", "real image"),
            "diagram": ("schema", "chart", "educational diagram", "labeled illustration"),
            "illustration": ("drawing", "vector illustration", "educational drawing"),
            "icon": ("symbol", "pictogram", "flat icon"),
        }
        return [f"{query} {term}" for term in synonyms.get(image_class, ())]

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
                        },
                        headers=WIKIMEDIA_HEADERS,
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
                                },
                                headers=WIKIMEDIA_HEADERS,
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
                self._aspect_ratio_score(candidate, request.preferred_orientation),
                self._resolution_score(candidate),
                self._source_score(candidate.source, plan),
            ),
            reverse=True,
        )

    def _clip_prompts(self, request: ImageResearchRequest, plan: SearchPlan) -> list[str]:
        prompts = [
            request.prompt,
            plan.main_query,
            plan.image_class,
            f"{request.prompt}. {request.style or ''}".strip(),
            f"{plan.main_query}. {' '.join(plan.visual_requirements)}".strip(),
        ]
        prompts.extend(get_class_profile(plan.image_class).clip_context)
        prompts.extend(plan.alternative_queries[:4])
        return [prompt for prompt in prompts if prompt]

    async def _download(
        self,
        candidates: list[ImageCandidate],
        request_id: str,
        warnings: list[str],
        scoring_pool_size: int,
        excluded_hashes: set[str],
    ) -> list[ImageCandidate]:
        downloaded: list[ImageCandidate] = []
        failures: Counter[str] = Counter()
        seen_hashes: set[str] = set(excluded_hashes)

        for candidate in candidates:
            if len(downloaded) >= scoring_pool_size:
                break
            try:
                candidate.local_temp_path = await download_image(candidate.image_url, request_id)
                await track_remote_download(candidate.download_tracking_url)
                # Hash de-dupe prevents repeated images across slides and providers.
                candidate.content_hash = hashlib.sha256(Path(candidate.local_temp_path).read_bytes()).hexdigest()
                if candidate.content_hash in seen_hashes:
                    failures[f"{candidate.source} duplicate hash"] += 1
                    Path(candidate.local_temp_path).unlink(missing_ok=True)
                    candidate.local_temp_path = None
                    continue
                seen_hashes.add(candidate.content_hash)
                downloaded.append(candidate)
            except DownloadError as exc:
                failures[f"{candidate.source} HTTP {exc.status_code or 'error'}"] += 1
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
        profile = get_class_profile(plan.image_class)
        for candidate, raw in zip(candidates, clip_scores):
            normalized = 1.0 if span == 0 else (raw - low) / span
            candidate.clip_score = round(raw, 6)
            metadata = self._metadata_score(candidate, request, plan)
            candidate.final_score = round(
                metadata * profile.metadata_weight
                + normalized * profile.clip_weight
                + license_score(candidate.license_name) * profile.license_weight
                + self._source_score(candidate.source, plan) * profile.source_weight
                + self._resolution_score(candidate) * profile.resolution_weight
                + self._aspect_ratio_score(candidate, request.preferred_orientation) * profile.aspect_weight,
                6,
            )
        return candidates

    def _select_images(
        self,
        candidates: list[ImageCandidate],
        request_id: str,
        prompt_slug: str,
        limit: int,
        plan: SearchPlan,
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
                    local_path=str(path),
                    public_url=f"{PUBLIC_IMAGES_PREFIX}/{prompt_slug}/{path.name}",
                    source=candidate.source,
                    source_url=candidate.source_url,
                    image_url=candidate.image_url,
                    author=candidate.author,
                    license_name=candidate.license_name,
                    image_class=plan.image_class,
                    width=candidate.width,
                    height=candidate.height,
                    content_hash=candidate.content_hash,
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
                " ".join(candidate.categories),
                candidate.page_title or "",
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
        profile = get_class_profile(plan.image_class if plan else None)
        query_tokens = self._tokens(core_text)
        visual_tokens = self._tokens(visual_text)
        critical_tokens = self._critical_tokens(plan.main_query if plan else core_text)
        text_tokens = self._tokens(text)
        if not query_tokens:
            return self._source_score(candidate.source, plan) * 0.25
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
        if plan and plan.image_class in {"diagram", "illustration", "icon"}:
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
        if any(term.lower() in text for term in profile.query_terms):
            score += 0.16
        if any(term.lower() in text for term in profile.bad_terms):
            score -= 0.25
        if any(term in text for term in {"reenactment", "replica", "memorial", "statue", "costume"}):
            if plan and any(term in " ".join(plan.visual_requirements).lower() for term in {"authentic", "documentary", "historical"}):
                score -= 0.22
        return max(0.0, min(1.0, score + self._source_score(candidate.source, plan) * 0.15))

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

    def _aspect_ratio_score(self, candidate: ImageCandidate, preferred_orientation: str | None) -> float:
        if not candidate.width or not candidate.height:
            return 0.6
        ratio = candidate.width / max(candidate.height, 1)
        if preferred_orientation == "portrait":
            return 1.0 if ratio < 0.95 else 0.35
        if preferred_orientation == "square":
            return max(0.25, 1 - min(abs(ratio - 1), 1))
        if preferred_orientation == "landscape":
            return max(0.25, 1 - min(abs(ratio - (16 / 9)) / 1.2, 1))
        return 0.9 if ratio >= 1 else 0.55

    def _source_score(self, source: str, plan: SearchPlan | None = None) -> float:
        if plan:
            return get_class_profile(plan.image_class).preferred_sources.get(source, 0.0)
        return get_class_profile(None).preferred_sources.get(source, 0.0)


    def _empty(self, search_plan: SearchPlan | None, warnings: list[str]) -> ImageResearchResponse:
        return ImageResearchResponse(
            success=False,
            selected_image=None,
            selected_images=[],
            search_plan=search_plan,
            source_selection=None,
            candidate_count=0,
            warnings=warnings,
        )
