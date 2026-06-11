# Роля на модула: Помощен модул в backend pipeline-а; коментарите по-долу обясняват конкретните му граници и решения.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    ORGANIZATION = "ORGANIZATION"
    PLACE = "PLACE"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    CONCEPT = "CONCEPT"


class ResearchImageSource(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    WIKIPEDIA = "WIKIPEDIA"
    WIKIMEDIA_COMMONS = "WIKIMEDIA_COMMONS"
    STOCK = "STOCK"


class ImageSourceSelection(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    entity_type: EntityType
    image_source: ResearchImageSource
    search_query: str
    confidence: float = Field(ge=0.0, le=1.0)


class ImageResearchRequest(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    prompt: str = Field(..., min_length=3)
    context_text: str | None = None
    style: str | None = None
    preferred_orientation: str = "any"
    image_type: str = "any"
    image_class: str | None = None
    max_candidates: int = Field(default=12, ge=1, le=50)
    exclude_source_urls: list[str] = Field(default_factory=list)
    exclude_hashes: list[str] = Field(default_factory=list)


class SearchPlan(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    main_query: str
    alternative_queries: list[str] = Field(default_factory=list)
    visual_requirements: list[str] = Field(default_factory=list)
    bad_terms: list[str] = Field(default_factory=list)
    preferred_orientation: str = "any"
    image_type: str = "any"
    image_class: str = "photo"


class ImageCandidate(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    id: str
    source: str
    title: str | None = None
    image_url: str
    preview_url: str | None = None
    source_url: str
    author: str | None = None
    license_name: str
    license_url: str | None = None
    download_tracking_url: str | None = None
    width: int | None = None
    height: int | None = None
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    page_title: str | None = None
    factual_score: float = 0.0
    content_hash: str | None = None
    local_temp_path: str | None = None
    clip_score: float | None = None
    final_score: float | None = None


class SelectedImage(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    local_path: str
    public_url: str
    source: str
    source_url: str
    image_url: str
    author: str | None
    license_name: str
    image_class: str = "photo"
    width: int | None
    height: int | None
    content_hash: str | None = None
    clip_score: float | None
    final_score: float | None


class ImageResearchResponse(BaseModel):
    # Роля на класа: Този Pydantic модел е договор на границата между pipeline слоеве: валидира типовете и прави сериализацията предвидима.
    # `BaseModel` използва type annotations като runtime schema, а не само като помощ за IDE.
    success: bool
    selected_image: SelectedImage | None
    selected_images: list[SelectedImage] = Field(default_factory=list)
    search_plan: SearchPlan | None
    source_selection: ImageSourceSelection | None = None
    candidate_count: int
    warnings: list[str] = Field(default_factory=list)
