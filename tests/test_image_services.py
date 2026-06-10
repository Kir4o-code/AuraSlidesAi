import asyncio
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pytest
from app.image_research.schemas import SelectedImage
from app.schemas.presentation import ImageClass, ImageSource, Presentation, Slide, SlideType
from app.services import image_optimizer, image_service
from app.services.image_optimizer import ImageOptimizationError
from PIL import Image


def image_bytes(mode: str = "RGB", size: tuple[int, int] = (2000, 1000)) -> bytes:
    image = Image.new(mode, size, (255, 0, 0, 128) if mode == "RGBA" else (255, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_optimizer_sanitizes_keys_and_detects_transparency() -> None:
    assert image_optimizer._safe_key(" ../bad key<> ") == "bad_key"
    assert image_optimizer._detect_transparency(Image.new("RGBA", (1, 1)))
    assert not image_optimizer._detect_transparency(Image.new("RGB", (1, 1)))


def test_optimize_image_bytes_resizes_and_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_optimizer, "OPTIMIZED_IMAGES_DIR", tmp_path)
    optimized = image_optimizer.optimize_image_bytes(image_bytes(), "large image")
    cached = image_optimizer.optimize_image_bytes(image_bytes(), "large image")
    assert optimized.path == cached.path
    assert optimized.width == 1600
    assert optimized.height == 800
    assert optimized.path.suffix == ".jpg"


def test_optimize_transparent_image_keeps_png(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_optimizer, "OPTIMIZED_IMAGES_DIR", tmp_path)
    optimized = image_optimizer.optimize_image_bytes(image_bytes("RGBA", (10, 10)), "transparent")
    assert optimized.has_transparency
    assert optimized.path.suffix == ".png"


def test_optimize_image_rejects_invalid_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_optimizer, "OPTIMIZED_IMAGES_DIR", tmp_path)
    with pytest.raises(ImageOptimizationError):
        image_optimizer.optimize_image_bytes(b"not an image", "invalid")


def test_image_slide_filter_and_research_type(sample_presentation: Presentation) -> None:
    slides = image_service._image_slides(sample_presentation)
    assert [slide.id for slide in slides] == ["image"]
    assert image_service._infer_research_image_type("clean process diagram") == "diagram"
    assert image_service._infer_research_image_type("simple icon") == "icon"
    assert image_service._infer_research_image_type("real scene") == "any"


def test_research_image_class_prioritizes_scientific_structure(
    slide_factory: Callable[[SlideType, str], Slide],
) -> None:
    slide = slide_factory(SlideType.TITLE_BULLETS_IMAGE, "image")
    slide.image_class = ImageClass.PHOTO
    assert image_service._research_image_class(slide, "DNA structure", "") == "diagram"


def test_scene_and_domain_helpers() -> None:
    assert (
        image_service._extract_scene_from_image_prompt(
            "Presentation visual for 'Class': students learning. Keep it grounded."
        )
        == "students learning"
    )
    assert image_service._extract_scene_from_image_prompt("clean technical diagram of DNA") == ""
    assert image_service._slide_concept_terms("Machine learning", ["algorithm model"]) == "machine learning"
    scene, terms = image_service._primary_scene_profile("Bridge engineering", ["structural design"], "")
    assert "engineer" in scene
    assert "engineering" in terms


def test_keyword_and_entity_helpers() -> None:
    phrase = image_service._english_keyword_phrase("data data analytics software", limit_words=3)
    assert len(phrase.split()) <= 3
    assert image_service._slide_mentions_entity("Ada Lovelace", "Lovelace and computing", [])
    assert not image_service._slide_mentions_entity("", "Anything", [])


def test_research_prompt_handles_dna_and_rna(slide_factory: Callable[[SlideType, str], Slide]) -> None:
    slide = slide_factory(SlideType.TITLE_BULLETS_IMAGE, "image")
    slide.title = "DNA structure"
    slide.image_prompt = "DNA double helix"
    assert image_service._research_prompt(slide, "Biology") == "DNA double helix"
    slide.title = "RNA vaccines"
    slide.image_prompt = "RNA medicine"
    assert image_service._research_prompt(slide, "Biology") == "mRNA vaccine"


def test_research_context_is_compact_english(slide_factory: Callable[[SlideType, str], Slide]) -> None:
    slide = slide_factory(SlideType.TITLE_BULLETS_IMAGE, "image")
    context = image_service._research_context(slide, "School technology")
    assert context.isascii()
    assert len(context) <= 140


def test_resolved_research_image_maps_public_asset(tmp_path: Path) -> None:
    selected = SelectedImage(
        local_path=str(tmp_path / "source.jpg"),
        public_url="/source.jpg",
        source="unsplash",
        source_url="https://source",
        image_url="https://image",
        author="Author",
        license_name="Unsplash License",
        image_class="photo",
        width=100,
        height=50,
        clip_score=0.8,
        final_score=0.9,
    )
    resolved = image_service._resolved_from_research_image(selected, tmp_path / "optimized.jpg", 200, 100)
    assert resolved.public_url == "/generated/optimized_images/optimized.jpg"
    assert resolved.width == 200


def test_enrich_presentation_images_calls_gemini_resolver(
    sample_presentation: Presentation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_ids: list[str] = []

    async def fake_resolve(slide: Slide, style: str) -> None:
        resolved_ids.append(slide.id)

    monkeypatch.setattr(image_service, "_resolve_one_slide_image", fake_resolve)
    monkeypatch.setattr(image_service, "get_image_model_name", lambda: "test-model")
    result = asyncio.run(image_service.enrich_presentation_images(sample_presentation, ImageSource.GEMINI))
    assert result is sample_presentation
    assert resolved_ids == ["image"]
