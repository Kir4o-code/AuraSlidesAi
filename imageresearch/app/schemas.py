from pydantic import BaseModel, Field


class ImageResearchRequest(BaseModel):
    prompt: str = Field(..., min_length=3)
    style: str | None = None
    preferred_orientation: str = "any"
    image_type: str = "any"
    max_candidates: int = Field(default=12, ge=1, le=50)


class SearchPlan(BaseModel):
    main_query: str
    alternative_queries: list[str] = []
    visual_requirements: list[str] = []
    bad_terms: list[str] = []
    preferred_orientation: str = "any"
    image_type: str = "any"


class ImageCandidate(BaseModel):
    id: str
    source: str
    title: str | None = None
    image_url: str
    preview_url: str | None = None
    source_url: str
    author: str | None = None
    license_name: str
    license_url: str | None = None
    width: int | None = None
    height: int | None = None
    tags: list[str] = []
    local_temp_path: str | None = None
    clip_score: float | None = None
    final_score: float | None = None


class SelectedImage(BaseModel):
    local_path: str
    public_url: str
    source: str
    source_url: str
    image_url: str
    author: str | None
    license_name: str
    width: int | None
    height: int | None
    clip_score: float | None
    final_score: float | None


class ImageResearchResponse(BaseModel):
    success: bool
    selected_image: SelectedImage | None
    selected_images: list[SelectedImage] = []
    search_plan: SearchPlan | None
    candidate_count: int
    warnings: list[str] = []
