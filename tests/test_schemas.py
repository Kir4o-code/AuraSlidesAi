from collections.abc import Callable

import pytest
from app.schemas.presentation import (
    GeneratePresentationRequest,
    GuidedSlideIntent,
    ImageSource,
    PlanningMode,
    Slide,
    SlideType,
)
from app.semantic.contracts import (
    LayoutedPresentationDocument,
    LayoutedSlide,
    LayoutElement,
    LayoutElementKind,
    LayoutRegion,
    LayoutRegionRole,
    LayoutSpec,
    PresentationDocument,
    ThemeFonts,
    ThemeTokens,
)
from app.semantic.contracts import (
    Slide as SemanticSlide,
)
from pydantic import ValidationError


@pytest.mark.parametrize("slide_type", list(SlideType))
def test_every_slide_type_accepts_valid_payload(
    slide_factory: Callable[[SlideType, str], Slide],
    slide_type: SlideType,
) -> None:
    assert slide_factory(slide_type, slide_type.value).type == slide_type


@pytest.mark.parametrize(
    ("slide_type", "payload"),
    [
        (SlideType.TITLE_SLIDE, {}),
        (SlideType.TITLE_BULLETS, {"title": "Title", "bullets": ["Only one"]}),
        (SlideType.TITLE_BULLETS_IMAGE, {"title": "Title", "bullets": ["One", "Two"]}),
        (SlideType.HERO_IMAGE, {"title": "Title"}),
        (SlideType.COMPARISON, {"title": "Title"}),
        (SlideType.TIMELINE, {"title": "Title"}),
        (SlideType.STATISTICS, {"title": "Title"}),
        (SlideType.QUOTE, {"title": "Title"}),
    ],
)
def test_slide_types_reject_missing_required_content(slide_type: SlideType, payload: dict) -> None:
    with pytest.raises(ValidationError):
        Slide(id="invalid", type=slide_type, **payload)


def test_generate_request_maps_legacy_image_source() -> None:
    request = GeneratePresentationRequest(prompt="Create a useful deck", image_source="image_research")
    assert request.image_source == ImageSource.UNSPLASH


def test_guided_request_requires_outline() -> None:
    with pytest.raises(ValidationError, match="Guided planning requires"):
        GeneratePresentationRequest(prompt="Create a useful deck", planning_mode=PlanningMode.GUIDED)


def test_guided_request_accepts_outline() -> None:
    outline = [GuidedSlideIntent(purpose=f"Purpose {index}") for index in range(3)]
    request = GeneratePresentationRequest(
        prompt="Create a useful deck",
        planning_mode=PlanningMode.GUIDED,
        slide_outline=outline,
    )
    assert request.slide_outline == outline


def test_theme_fonts_reject_css_stack() -> None:
    with pytest.raises(ValidationError, match="semantic font families"):
        ThemeFonts(heading="Inter, sans-serif", body="Inter")


def test_theme_tokens_reject_css_declarations() -> None:
    with pytest.raises(ValidationError, match="semantic values"):
        ThemeTokens(
            background="padding: 2px",
            background_alt="#fff",
            surface="#fff",
            text_primary="#000",
            text_secondary="#333",
            accent_primary="#00f",
            accent_secondary="#ccf",
            border="#ddd",
            fonts=ThemeFonts(heading="Inter", body="Inter"),
        )


def test_layout_spec_rejects_duplicate_region_ids() -> None:
    region = LayoutRegion(id="body", role=LayoutRegionRole.BODY)
    with pytest.raises(ValidationError, match="duplicate region ids"):
        LayoutSpec(name="duplicate", regions=[region, region])


def test_presentation_document_requires_unique_order() -> None:
    slides = [
        SemanticSlide(id="a", order=1, layout_name="title.centered"),
        SemanticSlide(id="b", order=1, layout_name="title.centered"),
    ]
    with pytest.raises(ValidationError, match="order must be unique"):
        PresentationDocument(title="Test", slides=slides)


def test_presentation_document_requires_sorted_order() -> None:
    slides = [
        SemanticSlide(id="a", order=2, layout_name="title.centered"),
        SemanticSlide(id="b", order=1, layout_name="title.centered"),
    ]
    with pytest.raises(ValidationError, match="must be ordered"):
        PresentationDocument(title="Test", slides=slides)


def test_layouted_document_requires_unique_slide_ids() -> None:
    slide = LayoutedSlide(slide_id="same", layout_name="title.centered")
    with pytest.raises(ValidationError, match="slide ids must be unique"):
        LayoutedPresentationDocument(title="Test", slides=[slide, slide])


def test_layout_element_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValidationError):
        LayoutElement(
            id="element",
            kind=LayoutElementKind.TEXT,
            region="body",
            x=0,
            y=0,
            width=0,
            height=10,
        )
