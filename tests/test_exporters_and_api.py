import json
from types import SimpleNamespace
from typing import Any

import pytest
from app.main import app
from app.routes import presentations as presentation_routes
from app.schemas.presentation import GeneratePresentationRequest, ImageSource, Presentation
from app.semantic.adapters import build_theme_definition, presentation_to_document
from app.semantic.layout_engine import build_layouted_presentation
from app.services import slide_generator
from app.services.exporters import build_presentation_exports, get_exporter
from app.services.exporters.pdf_exporter import PdfExporter
from app.services.layout_engine import _rgb, build_pptx_presentation
from fastapi.testclient import TestClient
from pptx.dml.color import RGBColor


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_exporter_rejects_disabled_screenshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLE_LEGACY_SCREENSHOT_EXPORT", raising=False)
    with pytest.raises(RuntimeError, match="disabled"):
        get_exporter("screenshot")


def test_export_orchestration_returns_pptx_when_pdf_fails(
    sample_presentation: Presentation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeExporter:
        def export_pptx(self, presentation: Any, theme: Any, asset_id: str) -> str:
            return f"{asset_id}.pptx"

        def export_pdf(self, presentation: Any, theme: Any, asset_id: str) -> str:
            raise RuntimeError("no pdf")

    document = build_layouted_presentation(presentation_to_document(sample_presentation))
    theme = build_theme_definition(sample_presentation.theme)
    monkeypatch.setattr("app.services.exporters.get_exporter", lambda exporter_type: FakeExporter())
    monkeypatch.setattr("app.services.exporters._export_pdf_with_browser", lambda *args: None)
    assert build_presentation_exports(document, theme, "asset") == ("asset.pptx", None)


def test_pdf_helpers_wrap_scale_and_fallback_color() -> None:
    exporter = PdfExporter.__new__(PdfExporter)
    exporter.page_width = 960
    exporter.page_height = 540
    assert exporter._pt(1280, 720, 0, 0, 1280, 720) == (0.0, 0.0, 960.0, 540.0)
    assert exporter._wrap("one two three", "Helvetica", 12, 35)
    assert exporter._color("invalid") == exporter._color("#2563eb")


def test_pptx_color_parser_uses_fallback_for_invalid_hex() -> None:
    assert _rgb("#fff") == RGBColor(255, 255, 255)
    assert _rgb("zzzzzz") == RGBColor(37, 99, 235)


def test_build_pptx_presentation_matches_slide_count(sample_presentation: Presentation) -> None:
    layouted = build_layouted_presentation(presentation_to_document(sample_presentation))
    deck = build_pptx_presentation(layouted, build_theme_definition(sample_presentation.theme))
    assert len(deck.slides) == len(sample_presentation.slides)


def test_prepare_export_bundle_runs_full_semantic_pipeline(sample_presentation: Presentation) -> None:
    layouted, theme = slide_generator.prepare_export_bundle(sample_presentation)
    assert layouted.title == sample_presentation.title
    assert theme.id == sample_presentation.theme.value


def test_asset_id_is_safe_and_unique() -> None:
    first = slide_generator._build_asset_id("Hello, World!")
    second = slide_generator._build_asset_id("Hello, World!")
    assert first.startswith("hello-world-")
    assert first != second


def test_generate_route_with_mocked_services(
    sample_presentation: Presentation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generate(**kwargs: Any) -> Presentation:
        return sample_presentation

    monkeypatch.setattr(presentation_routes, "generate_presentation", fake_generate)
    monkeypatch.setattr(presentation_routes, "get_settings", lambda: SimpleNamespace(enable_image_generation=False))
    monkeypatch.setattr(
        presentation_routes,
        "prepare_export_bundle",
        lambda presentation: (
            build_layouted_presentation(presentation_to_document(presentation)),
            build_theme_definition(presentation.theme),
        ),
    )
    monkeypatch.setattr(
        presentation_routes, "build_presentation_exports", lambda presentation: ("deck.pptx", "deck.pdf")
    )

    response = TestClient(app).post(
        "/presentations/generate",
        json=GeneratePresentationRequest(prompt="Create a useful presentation").model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.json()["pptx_url"].endswith("/generated/deck.pptx")


def test_generate_stream_reports_real_stage_order(
    sample_presentation: Presentation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generate(**kwargs: Any) -> Presentation:
        return sample_presentation

    async def fake_enrich(presentation: Presentation, image_source: ImageSource) -> Presentation:
        return presentation

    monkeypatch.setattr(presentation_routes, "generate_presentation", fake_generate)
    monkeypatch.setattr(presentation_routes, "enrich_presentation_images", fake_enrich)
    monkeypatch.setattr(presentation_routes, "get_settings", lambda: SimpleNamespace(enable_image_generation=True))
    monkeypatch.setattr(
        presentation_routes,
        "prepare_export_bundle",
        lambda presentation: (
            build_layouted_presentation(presentation_to_document(presentation)),
            build_theme_definition(presentation.theme),
        ),
    )
    monkeypatch.setattr(
        presentation_routes, "build_presentation_exports", lambda presentation: ("deck.pptx", "deck.pdf")
    )

    response = TestClient(app).post(
        "/presentations/generate-stream",
        json=GeneratePresentationRequest(prompt="Create a useful presentation").model_dump(mode="json"),
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["stage"] for event in events if event["type"] == "progress"] == [
        "planning",
        "validation",
        "images",
        "export",
    ]
    assert events[-1]["type"] == "result"


def test_generate_route_maps_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate(**kwargs: Any) -> None:
        raise ValueError("bad presentation")

    monkeypatch.setattr(presentation_routes, "generate_presentation", fake_generate)
    response = TestClient(app).post(
        "/presentations/generate",
        json={
            "prompt": "Create a useful presentation",
            "slide_count": 3,
            "image_source": ImageSource.GEMINI.value,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "bad presentation"


@pytest.mark.parametrize(
    ("error_name", "status_code"),
    [
        ("GeminiConfigurationError", 500),
        ("GeminiPlanningError", 502),
        ("GeminiImageGenerationError", 502),
    ],
)
def test_generate_route_maps_gemini_errors(
    error_name: str,
    status_code: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_type = getattr(presentation_routes, error_name)

    async def fake_generate(**kwargs: Any) -> None:
        raise error_type("provider failed")

    monkeypatch.setattr(presentation_routes, "generate_presentation", fake_generate)
    response = TestClient(app).post(
        "/presentations/generate",
        json={"prompt": "Create a useful presentation", "slide_count": 3},
    )
    assert response.status_code == status_code
