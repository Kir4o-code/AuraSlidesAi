from collections.abc import Callable

import pytest
from app.schemas.presentation import (
    Presentation,
    Slide,
    SlideType,
    StatisticItem,
    ThemeName,
    TimelineStep,
)


def build_slide(slide_type: SlideType, slide_id: str = "slide-1") -> Slide:
    common = {"id": slide_id, "type": slide_type, "title": "Test slide"}
    payloads = {
        SlideType.TITLE_SLIDE: {},
        SlideType.TITLE_BULLETS: {"bullets": ["First point", "Second point"]},
        SlideType.TITLE_BULLETS_IMAGE: {
            "bullets": ["First point", "Second point"],
            "image_prompt": "students in a classroom",
        },
        SlideType.HERO_IMAGE: {"image_prompt": "mountain landscape"},
        SlideType.COMPARISON: {
            "left_title": "Left",
            "right_title": "Right",
            "left_bullets": ["Left point"],
            "right_bullets": ["Right point"],
        },
        SlideType.TIMELINE: {
            "timeline": [
                TimelineStep(label="Start", detail="Begin"),
                TimelineStep(label="Finish", detail="Complete"),
            ]
        },
        SlideType.STATISTICS: {"statistics": [StatisticItem(label="Growth", value="25%")]},
        SlideType.QUOTE: {"quote": "A useful closing thought."},
    }
    return Slide(**common, **payloads[slide_type])


@pytest.fixture
def slide_factory() -> Callable[[SlideType, str], Slide]:
    return build_slide


@pytest.fixture
def sample_presentation() -> Presentation:
    return Presentation(
        title="Sample presentation",
        theme=ThemeName.MODERN_DARK_TECH,
        slides=[
            build_slide(SlideType.TITLE_SLIDE, "title"),
            build_slide(SlideType.TITLE_BULLETS, "bullets"),
            build_slide(SlideType.TITLE_BULLETS_IMAGE, "image"),
        ],
    )


@pytest.fixture
def full_presentation() -> Presentation:
    return Presentation(
        title="All layouts",
        theme=ThemeName.MODERN_DARK_TECH,
        slides=[build_slide(slide_type, slide_type.value) for slide_type in SlideType],
    )
