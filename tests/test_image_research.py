import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from app.image_research.core import storage
from app.image_research.core.image_classes import (
    ImageClass,
    canonical_image_class,
    get_class_profile,
    infer_image_class,
)
from app.image_research.core.license_checker import canonical_license, is_allowed_license, license_score
from app.image_research.core.researcher import ImageResearcher
from app.image_research.core.search_planner import SearchPlanner, canonical_image_type, compact_search_query
from app.image_research.core.source_selector import (
    _entity_query,
    _has_any,
    _looks_like_named_entity,
    _named_entity_candidates,
    select_image_source_with_reason,
)
from app.image_research.providers.unsplash import _with_referral, _with_resize_params
from app.image_research.providers.wikimedia_commons import WikimediaCommonsProvider
from app.image_research.providers.wikipedia import WikipediaProvider
from app.image_research.schemas import (
    EntityType,
    ImageCandidate,
    ImageResearchRequest,
    ResearchImageSource,
    SearchPlan,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("chart", ImageClass.DIAGRAM),
        (" icon ", ImageClass.ICON),
        ("unknown", ImageClass.PHOTO),
        (None, ImageClass.PHOTO),
    ],
)
def test_canonical_image_class(value: str | None, expected: ImageClass) -> None:
    assert canonical_image_class(value) == expected


def test_infer_image_class_uses_prompt_when_type_is_any_case_insensitively() -> None:
    assert infer_image_class("A clean process diagram", "Any") == ImageClass.DIAGRAM


def test_infer_image_class_respects_explicit_type() -> None:
    assert infer_image_class("A portrait photo", "icon") == ImageClass.ICON


def test_class_profiles_are_available_for_every_class() -> None:
    for image_class in ImageClass:
        profile = get_class_profile(image_class)
        assert profile.image_class == image_class
        assert profile.allowed_providers


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CC BY 4.0", "CC BY"),
        ("cc-by-sa 4.0", "CC BY-SA"),
        ("PDM", "Public Domain"),
        ("CC0 1.0", "CC0"),
        ("unknown", None),
        (None, None),
    ],
)
def test_license_normalization(raw: str | None, expected: str | None) -> None:
    assert canonical_license(raw) == expected
    assert is_allowed_license(raw) is (expected is not None)
    assert license_score(raw) == (1.0 if expected else 0.0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("graph", "diagram"), (" PHOTO ", "photo"), ("bad", "any"), (None, "any")],
)
def test_canonical_image_type(raw: str | None, expected: str) -> None:
    assert canonical_image_type(raw) == expected


def test_compact_search_query_removes_prompt_boilerplate_and_duplicates() -> None:
    query = compact_search_query("Presentation visual for 'DNA': DNA DNA double helix. Keep it grounded and relevant.")
    assert query == "DNA double helix"


def test_search_planner_fallback_adds_terms_for_diagram() -> None:
    planner = SearchPlanner()
    request = ImageResearchRequest(prompt="DNA structure diagram", image_type="diagram")
    plan = planner._fallback(request)
    assert plan.image_class == "diagram"
    assert plan.alternative_queries


def test_search_planner_normalizes_string_lists() -> None:
    planner = SearchPlanner()
    request = ImageResearchRequest(prompt="Bridge engineering")
    normalized = planner._normalize(
        {
            "main_query": "bridge",
            "alternative_queries": "bridge design; structural bridge",
            "visual_requirements": "clean, technical",
            "bad_terms": None,
            "image_type": "PHOTO",
        },
        request,
    )
    assert normalized["alternative_queries"] == ["bridge design", "structural bridge"]
    assert normalized["image_type"] == "photo"


def test_named_entity_helpers() -> None:
    assert "Ada Lovelace" in _named_entity_candidates("The work of Ada Lovelace")
    assert _entity_query('A portrait of "Ada Lovelace"') == "Ada Lovelace"
    assert _looks_like_named_entity("Ada Lovelace")
    assert _has_any("machine learning system", {"machine learning"})


@pytest.mark.parametrize(
    ("prompt", "entity_type", "source"),
    [
        ("portrait of scientist Ada Lovelace", EntityType.PERSON, ResearchImageSource.WIKIPEDIA),
        ("Apple company headquarters", EntityType.COMPANY, ResearchImageSource.WIKIPEDIA),
        ("Eiffel Tower landmark", EntityType.PLACE, ResearchImageSource.WIKIPEDIA),
        ("machine learning strategy", EntityType.CONCEPT, ResearchImageSource.STOCK),
        ("ДНК двойна спирала", EntityType.PRODUCT, ResearchImageSource.WIKIPEDIA),
    ],
)
def test_source_selector_routes_known_intents(
    prompt: str,
    entity_type: EntityType,
    source: ResearchImageSource,
) -> None:
    selection, reason = select_image_source_with_reason(prompt)
    assert selection.entity_type == entity_type
    assert selection.image_source == source
    assert reason


def test_storage_helpers_use_requested_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "IMAGES_DIR", tmp_path / "images")
    monkeypatch.setattr(storage, "TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr(storage, "METADATA_DIR", tmp_path / "metadata")
    source = tmp_path / "source.jpg"
    source.write_bytes(b"image")

    assert storage.slugify("Hello, World!") == "hello_world"
    metadata_path = storage.save_metadata("request", {"ok": True}, "prompt")
    copied_path = storage.copy_ranked_image(str(source), "request", 2, "prompt")

    assert json.loads(metadata_path.read_text(encoding="utf-8")) == {"ok": True}
    assert copied_path.name == "request_02.jpg"
    assert copied_path.read_bytes() == b"image"


def test_unsplash_url_helpers_preserve_and_add_query_parameters() -> None:
    resized = _with_resize_params("https://images.example/test?fit=crop", "portrait")
    referred = _with_referral("https://unsplash.com/photos/abc?existing=yes")
    assert "fit=crop" in resized and "h=1400" in resized and "fm=jpg" in resized
    assert "existing=yes" in referred and "utm_source=AuraSlidesAI" in referred


def test_wikipedia_title_candidates_are_clean_and_unique() -> None:
    provider = WikipediaProvider()
    assert provider._title_candidates("Ada Lovelace: mathematician, pioneer") == [
        "Ada Lovelace: mathematician, pioneer",
        "Ada Lovelace",
        "Ada Lovelace: mathematician",
    ]


def candidate(candidate_id: str, *, source_url: str | None = None, **overrides: Any) -> ImageCandidate:
    values = {
        "id": candidate_id,
        "source": "wikipedia",
        "title": "DNA double helix",
        "image_url": f"https://img/{candidate_id}.jpg",
        "source_url": source_url or f"https://source/{candidate_id}",
        "license_name": "CC BY",
        "width": 1600,
        "height": 900,
    }
    values.update(overrides)
    return ImageCandidate(**values)


def test_researcher_dedupes_and_scores_basic_candidate_properties() -> None:
    researcher = ImageResearcher.__new__(ImageResearcher)
    first = candidate("a")
    duplicate = candidate("b", source_url=first.source_url)
    assert researcher._dedupe([first, duplicate]) == [first]
    assert researcher._resolution_score(first) == 1.0
    assert researcher._aspect_ratio_score(first, "landscape") > 0.9
    assert researcher._source_score("wikipedia", SearchPlan(main_query="DNA", image_class="diagram")) == 1.0


def test_researcher_filters_strictly_irrelevant_candidates() -> None:
    researcher = ImageResearcher.__new__(ImageResearcher)
    request = ImageResearchRequest(prompt="DNA structure")
    plan = SearchPlan(main_query="DNA double helix", image_class="diagram")
    warnings: list[str] = []
    relevant = candidate("dna", tags=["DNA", "nucleotide"])
    irrelevant = candidate("map", title="Map of a country", tags=["territory"])
    result = researcher._filter_relevant_candidates([relevant, irrelevant], request, plan, warnings)
    assert result == [relevant]
    assert warnings


def test_researcher_builds_unique_stock_queries() -> None:
    researcher = ImageResearcher.__new__(ImageResearcher)
    request = ImageResearchRequest(prompt="Bridge design")
    plan = SearchPlan(main_query="Bridge design", alternative_queries=["Bridge design", "Structural bridge"])
    assert researcher._stock_queries(plan, request) == ["Bridge design", "Structural bridge"]


def test_researcher_empty_response_is_consistent() -> None:
    researcher = ImageResearcher.__new__(ImageResearcher)
    response = researcher._empty(SearchPlan(main_query="test"), ["nothing found"])
    assert not response.success
    assert response.candidate_count == 0
    assert response.warnings == ["nothing found"]


def test_researcher_ranks_scores_and_selects_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    researcher = ImageResearcher.__new__(ImageResearcher)
    request = ImageResearchRequest(prompt="DNA double helix", preferred_orientation="landscape")
    plan = SearchPlan(main_query="DNA double helix", image_class="diagram")
    good = candidate("good", tags=["DNA", "diagram"])
    weak = candidate("weak", title="Unrelated image", tags=["misc"], width=200, height=200)
    good.local_temp_path = str(tmp_path / "good.jpg")
    weak.local_temp_path = str(tmp_path / "weak.jpg")
    Path(good.local_temp_path).write_bytes(b"good")
    Path(weak.local_temp_path).write_bytes(b"weak")

    ranked = researcher._rank_before_download([weak, good], request, plan)
    assert ranked[0] is good
    scored = researcher._score([good, weak], [0.9, 0.1], request, plan)
    assert scored[0].final_score > scored[1].final_score
    monkeypatch.setattr(
        "app.image_research.core.researcher.copy_ranked_image",
        lambda temp_path, request_id, rank, prompt_slug: tmp_path / f"{request_id}_{rank}.jpg",
    )
    selected = researcher._select_images(scored, "request", "prompt", 1, plan)
    assert len(selected) == 1
    assert selected[0].image_class == "diagram"


def test_wikimedia_skips_unknown_license(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "query": {
            "pages": {
                "1": {
                    "title": "File:Unknown.jpg",
                    "imageinfo": [
                        {
                            "url": "https://image/unknown.jpg",
                            "width": 100,
                            "height": 100,
                            "extmetadata": {"LicenseShortName": {"value": "All rights reserved"}},
                        }
                    ],
                }
            }
        }
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        "app.image_research.providers.wikimedia_commons.httpx.AsyncClient",
        lambda *args, **kwargs: FakeClient(),
    )
    result = asyncio.run(WikimediaCommonsProvider().search("unknown", 3, None))
    assert result == []
