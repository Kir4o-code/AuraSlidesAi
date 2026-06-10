import base64
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from app.schemas.presentation import GuidedSlideIntent, Slide, SlideType
from app.services.gemini_service import (
    GeminiImageGenerationError,
    GeminiPresentationPlan,
    GeminiSlidePlan,
    GeminiStatisticItem,
    GeminiTimelineStep,
    _english_only_image_prompt,
    _extract_image_bytes,
    _extract_json_text,
    _fallback_bullets_for_slide,
    _fallback_plan_from_request,
    _fallback_slide_title,
    _fallback_title_from_purpose,
    _has_cyrillic,
    _heading_from_first_bullet,
    _http_options,
    _infer_comparison_title,
    _looks_generic_title,
    _looks_truncated_json,
    _normalize_attribution,
    _normalize_bullets,
    _normalize_image_class,
    _normalize_image_prompt,
    _normalize_plan,
    _normalize_slide_plan,
    _normalize_statistics,
    _normalize_timeline,
    _planning_retry_instruction,
    _provider_message,
    _requested_topic_title,
    _resolve_slide_type,
    _trim_text,
    build_image_cache_key,
    english_visual_search_phrase,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Invalid API key", "Gemini API authentication failed"),
        ("429 resource_exhausted", "Gemini quota or rate limit reached"),
        ("Provider failed", "Provider failed"),
    ],
)
def test_provider_message_is_user_friendly(message: str, expected: str) -> None:
    assert expected in _provider_message(RuntimeError(message))


def test_http_options_converts_seconds_to_milliseconds() -> None:
    assert _http_options(2).timeout == 2000
    assert _http_options(0).timeout is None


def test_text_and_bullet_normalizers() -> None:
    assert _normalize_bullets([" first ", "", "second"], 1, ["fallback"]) == ["first"]
    assert _normalize_bullets([], 2, ["one", "two", "three"]) == ["one", "two"]
    assert _trim_text("  hello  ", 4) == "hell"
    assert _trim_text("   ", 5) is None
    assert _normalize_attribution(None, "Deck title") == "Deck title"


def test_fallback_bullets_and_titles_are_deterministic() -> None:
    assert _fallback_bullets_for_slide("Topic", "Deck", slot=1) == _fallback_bullets_for_slide("Topic", "Deck", slot=1)
    assert _fallback_slide_title("Deck", 1) != _fallback_slide_title("Deck", 2)


def test_english_visual_search_phrase_removes_non_english_and_noise() -> None:
    phrase = english_visual_search_phrase(
        "Presentation visual for DNA",
        "чиста диаграма",
        "clean modern image with labels",
        limit_words=5,
    )
    assert phrase.isascii()
    assert "presentation" not in phrase.lower()


def test_english_only_image_prompt_uses_fallback() -> None:
    assert _english_only_image_prompt("само кирилица", fallback="DNA structure") == "DNA structure"


def test_normalize_image_prompt_removes_hype_and_abstract_language() -> None:
    prompt = _normalize_image_prompt(
        "8k futuristic abstract neural network symbolizing progress",
        "Machine learning",
        "AI",
    )
    assert prompt.isascii()
    assert "8k" not in prompt.lower()
    assert "symbolizing" not in prompt.lower()


def test_normalize_image_class_and_title_helpers() -> None:
    assert _normalize_image_class("diagram", "portrait photo") == "diagram"
    assert _normalize_image_class(None, "clean chart") == "diagram"
    assert _looks_generic_title("Slide")
    assert not _looks_generic_title("Real title")
    assert _has_cyrillic("Български текст")
    assert not _has_cyrillic("English text")
    assert _heading_from_first_bullet(["Benefits: faster work"], "Fallback") == "Benefits"
    assert _infer_comparison_title("Option A", ["Manual: careful"], "Fallback") == "Manual Design"


def test_timeline_and_statistics_defaults_and_limits() -> None:
    assert len(_normalize_timeline([])) == 2
    assert len(_normalize_timeline([GeminiTimelineStep(label=str(i)) for i in range(10)])) == 6
    assert len(_normalize_statistics([])) == 1
    assert len(_normalize_statistics([GeminiStatisticItem(label=str(i), value=str(i)) for i in range(8)])) == 4


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("title", SlideType.TITLE_SLIDE),
        ("bullets_with_image", SlideType.TITLE_BULLETS_IMAGE),
        ("bad", SlideType.TITLE_BULLETS),
    ],
)
def test_resolve_slide_type_aliases(raw: str, expected: SlideType) -> None:
    assert _resolve_slide_type(raw) == expected


@pytest.mark.parametrize("slide_type", list(SlideType))
def test_normalize_slide_plan_produces_valid_content(slide_type: SlideType) -> None:
    slide = GeminiSlidePlan(type=slide_type.value)
    normalized = _normalize_slide_plan(slide, "Deck title", 1)
    assert normalized.id == "slide_1"
    if slide_type in {SlideType.TITLE_BULLETS_IMAGE, SlideType.HERO_IMAGE}:
        assert normalized.image_prompt
        assert normalized.image_class


def test_fallback_title_from_purpose_uses_first_sentence() -> None:
    assert _fallback_title_from_purpose("Explain the system. Add details.", "Deck", 1) == "Explain the system"


def test_fallback_plan_respects_guided_types() -> None:
    outline = [
        GuidedSlideIntent(purpose="Open the topic", requested_type=SlideType.TITLE_SLIDE),
        GuidedSlideIntent(purpose="Explain it", requested_type=SlideType.TITLE_BULLETS),
        GuidedSlideIntent(purpose="Close it", requested_type=SlideType.QUOTE),
    ]
    plan = _fallback_plan_from_request("Topic", 3, "modern", outline)
    assert [slide.type for slide in plan.slides] == [item.requested_type.value for item in outline]


def test_requested_topic_title_only_accepts_short_topic() -> None:
    assert _requested_topic_title("DNA") == "DNA"
    assert _requested_topic_title("Explain DNA in detail with examples and a conclusion.") is None


def test_normalize_plan_enforces_count_title_and_theme() -> None:
    plan = GeminiPresentationPlan(title="Poetic: DNA", theme="modern", slides=[])
    normalized = _normalize_plan(plan, 3, source_prompt="DNA")
    assert normalized.title == "DNA"
    assert len(normalized.slides) == 3
    assert normalized.slides[0].type == SlideType.TITLE_SLIDE.value
    assert normalized.theme == "modern_dark_tech"


def test_extract_json_text_from_text_and_candidate_parts() -> None:
    assert _extract_json_text(SimpleNamespace(text='{"ok": true}')) == '{"ok": true}'
    response = SimpleNamespace(
        text=None,
        candidates=[
            SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="a"), SimpleNamespace(text="b")]))
        ],
    )
    assert _extract_json_text(response) == "ab"


def test_extract_json_text_rejects_empty_response() -> None:
    with pytest.raises(Exception, match="empty planning response"):
        _extract_json_text(SimpleNamespace(text=None, candidates=[]))


@pytest.mark.parametrize(
    ("payload", "expected"),
    [("", False), ("[]", False), ('{"a": 1', True), ('{"a": 1}', False)],
)
def test_looks_truncated_json(payload: str, expected: bool) -> None:
    assert _looks_truncated_json(payload) is expected


def test_retry_instruction_contains_requested_count() -> None:
    assert "EXACTLY 7 slides" in _planning_retry_instruction(7)


def test_extract_image_bytes_from_inline_bytes_and_base64() -> None:
    raw = b"image-data"
    bytes_response = SimpleNamespace(parts=[SimpleNamespace(inline_data=SimpleNamespace(data=raw))])
    encoded_response = SimpleNamespace(
        parts=[SimpleNamespace(inline_data=SimpleNamespace(data=base64.b64encode(raw).decode("ascii")))]
    )
    assert _extract_image_bytes(bytes_response) == raw
    assert _extract_image_bytes(encoded_response) == raw


def test_extract_image_bytes_rejects_empty_response() -> None:
    with pytest.raises(GeminiImageGenerationError):
        _extract_image_bytes(SimpleNamespace(parts=[]))


def test_build_image_cache_key_is_stable_and_content_sensitive(
    slide_factory: Callable[[SlideType, str], Slide],
) -> None:
    slide = slide_factory(SlideType.TITLE_BULLETS_IMAGE, "image")
    first = build_image_cache_key(slide, "modern")
    second = build_image_cache_key(slide, "modern")
    slide.title = "Changed"
    assert first == second
    assert build_image_cache_key(slide, "modern") != first
