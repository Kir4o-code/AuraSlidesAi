from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class LayoutName(str, Enum):
    TITLE = "title"
    BULLETS = "bullets"
    BULLETS_WITH_IMAGE = "bullets_with_image"
    IMAGE_FOCUS = "image_focus"
    CONCLUSION = "conclusion"


class ImageRole(str, Enum):
    BACKGROUND_IMAGE = "background_image"
    MAIN_OBJECT = "main_object"
    ICON = "icon"
    DIAGRAM = "diagram"


class Theme(BaseModel):
    style: str = Field(default="modern", min_length=1, max_length=40)
    primary_color: str = Field(default="#2563eb", pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$")
    font: str = Field(default="Inter", min_length=1, max_length=60)


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
    role: ImageRole
    remove_background: bool = False
    resolved_image: ResolvedImageAsset | None = None
    research_warnings: list[str] = []

    @field_validator("remove_background")
    @classmethod
    def validate_remove_background(cls, value: bool, info) -> bool:
        role = info.data.get("role")
        if role == ImageRole.BACKGROUND_IMAGE and value:
            raise ValueError("Background images cannot request background removal.")
        return value


class TitleSlide(BaseModel):
    layout: Literal[LayoutName.TITLE]
    title: str = Field(min_length=1, max_length=140)
    subtitle: str = Field(default="", max_length=220)


class BulletsSlide(BaseModel):
    layout: Literal[LayoutName.BULLETS]
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(min_length=2, max_length=6)


class BulletsWithImageSlide(BaseModel):
    layout: Literal[LayoutName.BULLETS_WITH_IMAGE]
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(min_length=2, max_length=5)
    image: ImageSpec


class ImageFocusSlide(BaseModel):
    layout: Literal[LayoutName.IMAGE_FOCUS]
    title: str = Field(min_length=1, max_length=120)
    caption: str = Field(min_length=1, max_length=220)
    image: ImageSpec


class ConclusionSlide(BaseModel):
    layout: Literal[LayoutName.CONCLUSION]
    title: str = Field(min_length=1, max_length=120)
    bullets: list[str] = Field(min_length=2, max_length=4)
    closing: str = Field(min_length=1, max_length=180)


Slide = Annotated[
    Union[TitleSlide, BulletsSlide, BulletsWithImageSlide, ImageFocusSlide, ConclusionSlide],
    Field(discriminator="layout"),
]


class Presentation(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    theme: Theme = Field(default_factory=Theme)
    slides: list[Slide] = Field(min_length=3, max_length=12)


class GeneratePresentationRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=4000)
    slide_count: int = Field(default=5, ge=3, le=10)
    style: str = Field(default="modern", min_length=1, max_length=40)
    generate_images: bool = True


class GeneratePresentationResponse(BaseModel):
    presentation: Presentation
    pdf_url: str
