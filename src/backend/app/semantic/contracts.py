from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Alignment(str, Enum):
    START = "start"
    CENTER = "center"
    END = "end"


class LayoutRegionRole(str, Enum):
    TITLE = "title"
    BODY = "body"
    MEDIA = "media"
    FOOTER = "footer"
    ASIDE = "aside"


class RendererTarget(str, Enum):
    REACT = "react"
    PPTX = "pptx"
    PDF = "pdf"
    SCREENSHOT = "screenshot"
    EDITOR = "editor"


class MediaKind(str, Enum):
    IMAGE = "image"
    CHART = "chart"
    ICON = "icon"
    ILLUSTRATION = "illustration"
    VIDEO = "video"
    AUDIO = "audio"
    OTHER = "other"


class ThemeFonts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=80)
    mono: str | None = Field(default=None, max_length=80)
    fallbacks: list[str] = Field(default_factory=lambda: ["system-ui", "sans-serif"], min_length=1, max_length=6)

    @field_validator("heading", "body", "mono")
    @classmethod
    def _reject_css_font_stacks(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.strip().lower()
        if "," in lowered or "font-family" in lowered or lowered.startswith("var("):
            raise ValueError("Theme font names must be semantic font families, not CSS font stacks.")
        return value


class ThemeTokens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: str = Field(min_length=1, max_length=40)
    background_alt: str = Field(min_length=1, max_length=40)
    surface: str = Field(min_length=1, max_length=40)
    surface_alt: str | None = Field(default=None, max_length=40)
    text_primary: str = Field(min_length=1, max_length=40)
    text_secondary: str = Field(min_length=1, max_length=40)
    accent_primary: str = Field(min_length=1, max_length=40)
    accent_secondary: str = Field(min_length=1, max_length=40)
    border: str = Field(min_length=1, max_length=40)
    focus_ring: str | None = Field(default=None, max_length=40)
    fonts: ThemeFonts
    spacing_scale: float = Field(default=1.0, gt=0.5, le=3.0)
    typography_scale: float = Field(default=1.0, gt=0.5, le=3.0)
    radius_scale: float = Field(default=1.0, gt=0.0, le=3.0)
    shadow_scale: float = Field(default=1.0, gt=0.0, le=3.0)
    component_styles: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator(
        "background",
        "background_alt",
        "surface",
        "surface_alt",
        "text_primary",
        "text_secondary",
        "accent_primary",
        "accent_secondary",
        "border",
        "focus_ring",
    )
    @classmethod
    def _reject_css_fragments(cls, value: str | None) -> str | None:
        if value is None:
            return None
        lowered = value.strip().lower()
        if any(marker in lowered for marker in (";", "{", "}", "font:", "margin:", "padding:", "position:")):
            raise ValueError("Theme tokens must be semantic values, not CSS declarations.")
        return value


class ThemeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=240)
    version: str = Field(default="1.0.0", min_length=1, max_length=24)
    tokens: ThemeTokens
    tags: list[str] = Field(default_factory=list, max_length=12)


class SlideMediaRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MediaKind = MediaKind.IMAGE
    label: str | None = Field(default=None, max_length=120)
    prompt: str | None = Field(default=None, max_length=500)
    alt: str | None = Field(default=None, max_length=250)
    source: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    local_path: str | None = Field(default=None, max_length=500)
    public_url: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Slide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    order: int = Field(ge=1)
    layout_name: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=140)
    subtitle: str | None = Field(default=None, max_length=220)
    bullets: list[str] = Field(default_factory=list, max_length=12)
    image_prompt: str | None = Field(default=None, max_length=500)
    visual_mood: str | None = Field(default=None, max_length=120)
    icon_intent: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    left_title: str | None = Field(default=None, max_length=120)
    right_title: str | None = Field(default=None, max_length=120)
    left_bullets: list[str] = Field(default_factory=list, max_length=12)
    right_bullets: list[str] = Field(default_factory=list, max_length=12)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    statistics: list[dict[str, Any]] = Field(default_factory=list)
    quote: str | None = Field(default=None, max_length=400)
    attribution: str | None = Field(default=None, max_length=250)
    media: list[SlideMediaRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_style_fields(self) -> "Slide":
        # This model intentionally does not carry render styling.
        return self


class PresentationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    slides: list[Slide] = Field(min_length=1, max_length=60)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="1.0.0", min_length=1, max_length=24)

    @model_validator(mode="after")
    def _ensure_sequential_slide_order(self) -> "PresentationDocument":
        orders = [slide.order for slide in self.slides]
        if orders != sorted(orders):
            raise ValueError("PresentationDocument slides must be ordered.")
        if len(set(orders)) != len(orders):
            raise ValueError("PresentationDocument slide order must be unique.")
        return self


class LayoutRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    role: LayoutRegionRole
    alignment: Alignment = Alignment.START
    emphasis: Literal["primary", "secondary", "supporting"] = "supporting"
    weight: float = Field(default=1.0, gt=0.0, le=10.0)
    content_hints: list[str] = Field(default_factory=list, max_length=8)
    repeatable: bool = False


class LayoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    regions: list[LayoutRegion] = Field(default_factory=list, min_length=1, max_length=12)
    alignment: Literal["left", "center", "right", "split", "grid"] = "left"
    emphasis: Literal["single", "primary-secondary", "balanced"] = "single"
    columns: int = Field(default=1, ge=1, le=4)
    supports_media: bool = True
    supports_notes: bool = True
    supports_footer: bool = True

    @model_validator(mode="after")
    def _validate_regions(self) -> "LayoutSpec":
        region_ids = [region.id for region in self.regions]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError(f"LayoutSpec '{self.name}' has duplicate region ids.")
        return self


class LayoutElementKind(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PANEL = "panel"
    BULLET_LIST = "bullet_list"
    BULLET_ITEM = "bullet_item"
    CARD = "card"
    TIMELINE_STEP = "timeline_step"
    STATISTIC = "statistic"
    QUOTE = "quote"


class LayoutDebugInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_length: int = Field(ge=0)
    estimated_lines: int = Field(ge=0)
    estimated_chars_per_line: int = Field(ge=0)
    spacing_before: int = Field(ge=0)
    spacing_after: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=180)


class LayoutElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    kind: LayoutElementKind
    region: str = Field(min_length=1, max_length=80)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    align: Alignment = Alignment.START
    wrap: bool = True
    font_size: int | None = Field(default=None, ge=1)
    line_height: float | None = Field(default=None, gt=0.0)
    z_index: int = 0
    text: str | None = Field(default=None, max_length=2000)
    content: dict[str, Any] = Field(default_factory=dict)
    children: list["LayoutElement"] = Field(default_factory=list)
    debug: LayoutDebugInfo | None = None


class LayoutedSlide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slide_id: str = Field(min_length=1, max_length=40)
    layout_name: str = Field(min_length=1, max_length=80)
    canvas_width: int = Field(default=1280, gt=0)
    canvas_height: int = Field(default=720, gt=0)
    elements: list[LayoutElement] = Field(default_factory=list)
    debug_mode: bool = False
    debug: dict[str, Any] = Field(default_factory=dict)


class LayoutedPresentationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    version: str = Field(default="1.0.0", min_length=1, max_length=24)
    metadata: dict[str, Any] = Field(default_factory=dict)
    slides: list[LayoutedSlide] = Field(min_length=1)

    @model_validator(mode="after")
    def _ensure_layout_slide_order(self) -> "LayoutedPresentationDocument":
        slide_ids = [slide.slide_id for slide in self.slides]
        if len(set(slide_ids)) != len(slide_ids):
            raise ValueError("LayoutedPresentationDocument slide ids must be unique.")
        return self


class RendererCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supports_css: bool = False
    supports_web_fonts: bool = False
    supports_blur: bool = False
    supports_animations: bool = False
    supports_gradients: bool = False
    supports_shadows: bool = False
    supports_absolute_positioning: bool = True
    supports_editable_text: bool = True
    supports_vector_output: bool = False
    supports_responsive_layout: bool = False


class RendererConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_fallbacks: list[str] = Field(default_factory=lambda: ["system-ui", "sans-serif"], max_length=8)
    max_text_columns: int = Field(default=3, ge=1, le=6)
    max_image_count: int = Field(default=3, ge=0, le=20)
    allow_external_assets: bool = False
    allow_blur_effects: bool = False
    allow_animations: bool = False


class RendererContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: RendererTarget
    capabilities: RendererCapabilities
    constraints: RendererConstraints = Field(default_factory=RendererConstraints)


LayoutElement.model_rebuild()
