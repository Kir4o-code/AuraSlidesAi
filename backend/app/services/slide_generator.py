import logging
import os
import re
import unicodedata
from pathlib import Path
from uuid import uuid4

from app.schemas.presentation import Presentation
from app.semantic.adapters import build_layout_specs, build_renderer_context, build_theme_definition, presentation_to_document
from app.semantic.contracts import LayoutedPresentationDocument, RendererTarget, ThemeDefinition
from app.semantic.layout_engine import build_layouted_presentation
from app.semantic.validators import validate_layout_spec, validate_presentation_document, validate_renderer_context, validate_theme_definition


APP_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = APP_DIR.parent / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = OUTPUT_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)


def prepare_export_bundle(presentation: Presentation) -> tuple[LayoutedPresentationDocument, ThemeDefinition]:
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    renderer_target = RendererTarget.SCREENSHOT if exporter_type == "screenshot" else RendererTarget.PPTX

    semantic_document = presentation_to_document(presentation)
    semantic_theme = build_theme_definition(presentation.theme)
    semantic_context = build_renderer_context(renderer_target)
    layouted_document = build_layouted_presentation(
        semantic_document,
        debug_mode=os.getenv("LAYOUT_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
        spacing_scale=semantic_theme.tokens.spacing_scale,
        typography_scale=semantic_theme.tokens.typography_scale,
    )

    validate_presentation_document(semantic_document)
    validate_theme_definition(semantic_theme)
    validate_renderer_context(semantic_context)
    for layout_spec in build_layout_specs(semantic_document):
        validate_layout_spec(layout_spec)

    return layouted_document, semantic_theme

from app.services.exporters import build_presentation_exports as run_exporters


def _build_asset_id(title: str) -> str:
    words = re.findall(r"\w+", unicodedata.normalize("NFKD", title), flags=re.UNICODE)
    slug = "-".join(words).strip("-_").lower()[:64].strip("-_")
    return f"{slug or 'presentation'}-{uuid4().hex[:8]}"


def build_presentation_exports(presentation: Presentation) -> tuple[str, str | None]:
    asset_id = _build_asset_id(presentation.title)
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    layouted_document, semantic_theme = prepare_export_bundle(presentation)

    logger.info("Starting presentation export. asset_id=%s exporter=%s", asset_id, exporter_type)
    return run_exporters(
        layouted_document,
        semantic_theme,
        asset_id,
        exporter_type=exporter_type,
        browser_fallback_presentation=presentation,
    )


def build_pdf(presentation: Presentation) -> str | None:
    _, pdf_name = build_presentation_exports(presentation)
    return pdf_name
