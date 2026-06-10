from collections.abc import Callable

import pytest
from app.schemas.presentation import Presentation, Slide, SlideType
from app.semantic.adapters import (
    _font_family_name,
    _short_alt_text,
    _slide_media,
    build_layout_specs,
    build_renderer_context,
    build_theme_definition,
    presentation_to_document,
)
from app.semantic.catalog import LAYOUT_SPEC_REGISTRY, RENDERER_CAPABILITY_MATRIX, get_layout_spec
from app.semantic.contracts import RendererTarget
from app.semantic.icons import FALLBACK_ICONS, choose_semantic_icon
from app.semantic.layout_engine import (
    _estimate_chars_per_line,
    _estimate_lines,
    _fit_font_size,
    _gap,
    _scale_spacing,
    _text_height,
    build_layouted_presentation,
)
from app.semantic.layout_selector import LAYOUT_METADATA_REGISTRY, LayoutSelector, SlideAnalyzer
from app.semantic.validators import (
    validate_layout_spec,
    validate_presentation_document,
    validate_renderer_context,
    validate_theme_definition,
)
from app.services.theme_registry import DEFAULT_THEME_NAME, THEME_REGISTRY, get_theme_tokens, resolve_theme_name


def test_theme_registry_resolves_alias_and_unknown() -> None:
    assert resolve_theme_name("modern") == "modern_dark_tech"
    assert resolve_theme_name("not-a-theme") == DEFAULT_THEME_NAME
    assert get_theme_tokens("modern").name == "modern_dark_tech"


def test_every_registered_theme_has_supported_layouts() -> None:
    for tokens in THEME_REGISTRY.values():
        assert tokens.supported_slide_layout_types
        assert tokens.background.startswith("#")


def test_semantic_icon_selection_uses_keywords_roles_and_fallback() -> None:
    assert choose_semantic_icon("data growth trend") == "chart"
    assert choose_semantic_icon("", role="timeline") == "clock"
    assert choose_semantic_icon("", index=3) == FALLBACK_ICONS[3]


def test_font_family_name_returns_first_semantic_font() -> None:
    assert _font_family_name("'Inter', Arial, sans-serif") == "Inter"


def test_short_alt_text_prefers_title_and_truncates_prompt(
    slide_factory: Callable[[SlideType, str], Slide],
) -> None:
    slide = slide_factory(SlideType.HERO_IMAGE, "hero")
    assert _short_alt_text(slide) == "Test slide"
    slide.title = None
    slide.image_prompt = "x" * 300
    assert _short_alt_text(slide) == ("x" * 217) + "..."


def test_slide_media_contains_resolution_metadata(slide_factory: Callable[[SlideType, str], Slide]) -> None:
    slide = slide_factory(SlideType.TITLE_BULLETS_IMAGE, "image")
    media = _slide_media(slide)
    assert len(media) == 1
    assert media[0].prompt == slide.image_prompt
    assert media[0].metadata["resolved"] is False


def test_presentation_to_document_and_layout_pipeline(sample_presentation: Presentation) -> None:
    document = presentation_to_document(sample_presentation)
    layouted = build_layouted_presentation(document)
    assert document.title == sample_presentation.title
    assert [slide.order for slide in document.slides] == [1, 2, 3]
    assert len(layouted.slides) == 3
    assert all(slide.elements for slide in layouted.slides)


def test_layout_pipeline_renders_every_slide_type(full_presentation: Presentation) -> None:
    document = presentation_to_document(full_presentation)
    layouted = build_layouted_presentation(document, debug_mode=True)
    assert len(layouted.slides) == len(SlideType)
    assert all(slide.debug_mode for slide in layouted.slides)
    for slide in layouted.slides:
        for element in slide.elements:
            assert element.x + element.width <= slide.canvas_width
            assert element.y + element.height <= slide.canvas_height


def test_build_theme_definition_is_renderer_neutral() -> None:
    theme = build_theme_definition("modern")
    assert theme.id == "modern_dark_tech"
    assert "," not in theme.tokens.fonts.heading
    assert validate_theme_definition(theme) is theme


def test_build_layout_specs_and_renderer_context(sample_presentation: Presentation) -> None:
    document = presentation_to_document(sample_presentation)
    specs = build_layout_specs(document)
    context = build_renderer_context(RendererTarget.PPTX)
    assert len(specs) == len(document.slides)
    assert context.capabilities == RENDERER_CAPABILITY_MATRIX[RendererTarget.PPTX]
    assert validate_renderer_context(context) is context


def test_catalog_and_semantic_validators(sample_presentation: Presentation) -> None:
    document = presentation_to_document(sample_presentation)
    assert validate_presentation_document(document) is document
    for slide in document.slides:
        spec = get_layout_spec(slide.layout_name)
        assert spec is LAYOUT_SPEC_REGISTRY[slide.layout_name]
        assert validate_layout_spec(spec) is spec


def test_validators_reject_unknown_layout_and_renderer_mismatch(sample_presentation: Presentation) -> None:
    document = presentation_to_document(sample_presentation)
    document.slides[0].layout_name = "missing.layout"
    with pytest.raises(ValueError, match="Unknown layout"):
        validate_presentation_document(document)

    context = build_renderer_context(RendererTarget.PPTX)
    context.capabilities.supports_css = True
    with pytest.raises(ValueError, match="do not match"):
        validate_renderer_context(context)


@pytest.mark.parametrize("slide_type", list(SlideType))
def test_layout_selector_recommends_compatible_layout(
    slide_factory: Callable[[SlideType, str], Slide],
    slide_type: SlideType,
) -> None:
    slide = slide_factory(slide_type, slide_type.value)
    analysis = SlideAnalyzer.analyze(slide)
    recommendation = LayoutSelector().select_for_presentation(
        type("Deck", (), {"theme": "modern_dark_tech", "slides": [slide]})()
    )[0]
    assert analysis.slide_type in LAYOUT_METADATA_REGISTRY[recommendation.selected_layout_id].supported_slide_types
    assert 0 <= recommendation.score <= 1


def test_layout_math_helpers_are_bounded() -> None:
    assert _scale_spacing(10, 1.5) == 15
    assert _gap(2, 0.5, minimum=4) == 4
    assert _fit_font_size(50, "short", 20, 60) == 60
    assert _estimate_chars_per_line(100, 0) == 1
    assert _estimate_lines("", 100, 12) == 0
    height, lines, chars = _text_height("A useful sentence", 200, 20)
    assert height > 0 and lines > 0 and chars > 0
