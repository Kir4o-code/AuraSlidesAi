from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.semantic.contracts import LayoutedPresentationDocument


class SlideType(str, Enum):
    TITLE_SLIDE = "title_slide"
    TITLE_BULLETS = "title_bullets"
    TITLE_BULLETS_IMAGE = "title_bullets_image"
    HERO_IMAGE = "hero_image"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    STATISTICS = "statistics"
    QUOTE = "quote"


class ThemeName(str, Enum):
    CLEAN_SCHOOL = "clean_school"
    MODERN_DARK_TECH = "modern_dark_tech"
    ACADEMIC_FORMAL = "academic_formal"
    STARTUP_PITCH = "startup_pitch"
    PHOTO_EDITORIAL = "photo_editorial"
    MINIMAL_CORPORATE = "minimal_corporate"
    CREATIVE_GRADIENT = "creative_gradient"
    DATA_REPORT = "data_report"
    NATURE_ORGANIC = "nature_organic"
    LUXURY_EDITORIAL = "luxury_editorial"
    PLAYFUL_LEARNING = "playful_learning"
    MONOCHROME_BOLD = "monochrome_bold"
    MODERN_DARK = "modern_dark"
    MODERN_LIGHT = "modern_light"
    EDITORIAL = "editorial"
    CORPORATE = "corporate"
    PLAYFUL = "playful"


class PlanningMode(str, Enum):
    AUTOMATIC = "automatic"
    GUIDED = "guided"


class GuidedSlideIntent(BaseModel):
    purpose: str = Field(min_length=1, max_length=500)
    requested_type: SlideType | None = None


class ImageSource(str, Enum):
    GEMINI = "gemini"
    UNSPLASH = "unsplash"


class ImageClass(str, Enum):
    ICON = "icon"
    DIAGRAM = "diagram"
    ILLUSTRATION = "illustration"
    PHOTO = "photo"


class ResolvedImageAsset(BaseModel):
    local_path: str
    public_url: str
    source: str
    source_url: str
    image_url: str
    author: str | None = None
    license_name: str
    width: int | None = None
    height: int | None = None
    clip_score: float | None = None
    final_score: float | None = None


class ImageSpec(BaseModel):
    query: str = Field(min_length=3, max_length=240)
    role: str = Field(default="hero_image", min_length=1, max_length=40)
    remove_background: bool = False
    resolved_image: ResolvedImageAsset | None = None
    research_warnings: list[str] = Field(default_factory=list)


class TimelineStep(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    detail: str | None = Field(default=None, max_length=240)


class StatisticItem(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=40)
    detail: str | None = Field(default=None, max_length=160)


class Slide(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    type: SlideType
    title: str | None = Field(default=None, max_length=140)
    subtitle: str | None = Field(default=None, max_length=220)
    bullets: list[str] = Field(default_factory=list, max_length=6)
    # layout helpers
    class TextAlign(str, Enum):
        LEFT = "left"
        CENTER = "center"
        RIGHT = "right"

    text_align: TextAlign = Field(default=TextAlign.LEFT)
    columns: int = Field(default=1, ge=1, le=3)
    image_prompt: str | None = Field(default=None, max_length=500)
    image_class: ImageClass | None = None
    visual_mood: str | None = Field(default=None, max_length=120)
    icon_intent: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    left_title: str | None = Field(default=None, max_length=120)
    right_title: str | None = Field(default=None, max_length=120)
    left_bullets: list[str] = Field(default_factory=list, max_length=6)
    right_bullets: list[str] = Field(default_factory=list, max_length=6)
    timeline: list[TimelineStep] = Field(default_factory=list)
    statistics: list[StatisticItem] = Field(default_factory=list)
    quote: str | None = Field(default=None, max_length=400)
    attribution: str | None = Field(default=None, max_length=250)
    resolved_image: ResolvedImageAsset | None = None

    @model_validator(mode="after")
    def validate_slide_payload(self) -> "Slide":
        if self.type == SlideType.TITLE_SLIDE:
            if not self.title:
                raise ValueError("Title slides need a title.")
        elif self.type == SlideType.TITLE_BULLETS:
            if not self.title or len(self.bullets) < 2:
                raise ValueError("Bullet slides need a title and at least two bullets.")
        elif self.type == SlideType.TITLE_BULLETS_IMAGE:
            if not self.title or len(self.bullets) < 2 or not self.image_prompt:
                raise ValueError("Image bullet slides need a title, bullets, and an image prompt.")
        elif self.type == SlideType.HERO_IMAGE:
            if not self.title or not self.image_prompt:
                raise ValueError("Hero image slides need a title and an image prompt.")
        elif self.type == SlideType.COMPARISON:
            if (
                not self.title
                or not self.left_title
                or not self.right_title
                or len(self.left_bullets) < 1
                or len(self.right_bullets) < 1
            ):
                raise ValueError("Comparison slides need both sides populated.")
        elif self.type == SlideType.TIMELINE:
            if not self.title or len(self.timeline) < 2:
                raise ValueError("Timeline slides need at least two milestones.")
        elif self.type == SlideType.STATISTICS:
            if not self.title or len(self.statistics) < 1:
                raise ValueError("Statistics slides need at least one statistic.")
        elif self.type == SlideType.QUOTE:
            if not self.quote:
                raise ValueError("Quote slides need quote text.")
        return self


class Presentation(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    theme: ThemeName = Field(default=ThemeName.MODERN_DARK)
    slides: list[Slide] = Field(min_length=3, max_length=12)


class GeneratePresentationRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=4000)
    slide_count: int = Field(default=5, ge=3, le=10)
    style: str = Field(default="modern", min_length=1, max_length=40)
    template: ThemeName | None = None
    image_source: ImageSource = ImageSource.GEMINI
    planning_mode: PlanningMode = PlanningMode.AUTOMATIC
    slide_outline: list[GuidedSlideIntent] | None = Field(default=None, min_length=3, max_length=10)

    @field_validator("image_source", mode="before")
    @classmethod
    def map_legacy_image_source(cls, value: object) -> object:
        if value == "image_research":
            return ImageSource.UNSPLASH
        return value

    @model_validator(mode="after")
    def validate_guided_outline(self) -> "GeneratePresentationRequest":
        if self.planning_mode == PlanningMode.GUIDED and not self.slide_outline:
            raise ValueError("Guided planning requires a slide outline.")
        return self


class GeneratePresentationResponse(BaseModel):
    presentation: Presentation
    layouted_presentation: LayoutedPresentationDocument | None = None
    pptx_url: str
    pdf_url: str | None
