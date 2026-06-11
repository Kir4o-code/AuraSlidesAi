# Роля на модула: Външният API договор. Тези модели спират невалидни данни преди да стигнат до services pipeline-а.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.semantic.contracts import LayoutedPresentationDocument


class SlideType(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    TITLE_SLIDE = "title_slide"
    TITLE_BULLETS = "title_bullets"
    TITLE_BULLETS_IMAGE = "title_bullets_image"
    HERO_IMAGE = "hero_image"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    STATISTICS = "statistics"
    QUOTE = "quote"


class ThemeName(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
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
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    AUTOMATIC = "automatic"
    GUIDED = "guided"


class GuidedSlideIntent(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    purpose: str = Field(min_length=1, max_length=500)
    requested_type: SlideType | None = None


class ImageSource(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    GEMINI = "gemini"
    UNSPLASH = "unsplash"


class ImageClass(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    ICON = "icon"
    DIAGRAM = "diagram"
    ILLUSTRATION = "illustration"
    PHOTO = "photo"


class ResolvedImageAsset(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
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


class TimelineStep(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    label: str = Field(min_length=1, max_length=120)
    detail: str | None = Field(default=None, max_length=240)


class StatisticItem(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=40)
    detail: str | None = Field(default=None, max_length=160)


class Slide(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    id: str = Field(min_length=1, max_length=40)
    type: SlideType
    title: str | None = Field(default=None, max_length=140)
    subtitle: str | None = Field(default=None, max_length=220)
    bullets: list[str] = Field(default_factory=list, max_length=6)
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
        # Роля в pipeline-а: пази границата на pipeline-а, като отказва данни, които следващият слой не може безопасно да обработи.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `ValueError`; така се вижда кои отговорности функцията делегира.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `'Slide'`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
        rules = {
            SlideType.TITLE_SLIDE: (self.title, "Title slides need a title."),
            SlideType.TITLE_BULLETS: (
                self.title and len(self.bullets) >= 2,
                "Bullet slides need a title and at least two bullets.",
            ),
            SlideType.TITLE_BULLETS_IMAGE: (
                self.title and len(self.bullets) >= 2 and self.image_prompt,
                "Image bullet slides need a title, bullets, and an image prompt.",
            ),
            SlideType.HERO_IMAGE: (
                self.title and self.image_prompt,
                "Hero image slides need a title and an image prompt.",
            ),
            SlideType.COMPARISON: (
                self.title and self.left_title and self.right_title and self.left_bullets and self.right_bullets,
                "Comparison slides need both sides populated.",
            ),
            SlideType.TIMELINE: (
                self.title and len(self.timeline) >= 2,
                "Timeline slides need at least two milestones.",
            ),
            SlideType.STATISTICS: (self.title and self.statistics, "Statistics slides need at least one statistic."),
            SlideType.QUOTE: (self.quote, "Quote slides need quote text."),
        }
        valid, message = rules[self.type]
        # Това условие е decision point: `not valid`.
        # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if not valid:
            raise ValueError(message)
        return self


class Presentation(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    title: str = Field(min_length=1, max_length=160)
    theme: ThemeName = Field(default=ThemeName.MODERN_DARK)
    slides: list[Slide] = Field(min_length=3, max_length=12)


class GeneratePresentationRequest(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
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
        # Роля в pipeline-а: валидира или описва част от договора между два pipeline слоя.
        # Входът идва през `cls` (неуточнен тип), `value` (object); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `object`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
        # Това условие е decision point: `value == 'image_research'`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`ImageSource.UNSPLASH`) и прескачаме ненужната останала работа.
        if value == "image_research":
            return ImageSource.UNSPLASH
        return value

    @model_validator(mode="after")
    def validate_guided_outline(self) -> "GeneratePresentationRequest":
        # Роля в pipeline-а: пази границата на pipeline-а, като отказва данни, които следващият слой не може безопасно да обработи.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `ValueError`; така се вижда кои отговорности функцията делегира.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `'GeneratePresentationRequest'`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
        # Това условие е decision point: `self.planning_mode == PlanningMode.GUIDED and (not self.slide_outline)`.
        # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if self.planning_mode == PlanningMode.GUIDED and not self.slide_outline:
            raise ValueError("Guided planning requires a slide outline.")
        return self


class GeneratePresentationResponse(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    presentation: Presentation
    layouted_presentation: LayoutedPresentationDocument | None = None
    pptx_url: str
    pdf_url: str | None
