import logging
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.presentation import Presentation
from app.semantic.adapters import build_layout_specs, build_renderer_context, build_theme_definition, presentation_to_document
from app.semantic.contracts import LayoutedPresentationDocument, RendererTarget, ThemeDefinition
from app.semantic.layout_engine import build_layouted_presentation
from app.semantic.validators import validate_layout_spec, validate_presentation_document, validate_renderer_context, validate_theme_definition
from app.services.image_service import build_image_context
from app.services.theme_registry import get_theme_tokens


APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
OUTPUT_DIR = APP_DIR.parent / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = OUTPUT_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
PDF_TEXT_SCALE = 1.0

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def prepare_export_bundle(presentation: Presentation) -> tuple[LayoutedPresentationDocument, ThemeDefinition]:
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    renderer_target = RendererTarget.SCREENSHOT if exporter_type == "screenshot" else RendererTarget.PPTX

    semantic_document = presentation_to_document(presentation)
    semantic_theme = build_theme_definition(presentation.theme)
    semantic_context = build_renderer_context(renderer_target)
    layouted_document = build_layouted_presentation(
        semantic_document,
        theme=semantic_theme,
        debug_mode=os.getenv("LAYOUT_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
    )

    validate_presentation_document(semantic_document)
    validate_theme_definition(semantic_theme)
    validate_renderer_context(semantic_context)
    for layout_spec in build_layout_specs(semantic_document):
        validate_layout_spec(layout_spec)

    return layouted_document, semantic_theme


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(char * 2 for char in cleaned)
    if len(cleaned) != 6:
        return (37, 99, 235)
    try:
        return tuple(int(cleaned[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return (37, 99, 235)


def _scale_for_length(length: int, thresholds: list[tuple[int, float]], default: float = 1.0) -> float:
    for threshold, scale in thresholds:
        if length >= threshold:
            return scale
    return default


def _scaled_font_size(value: float) -> int:
    return max(1, round(value * PDF_TEXT_SCALE))


def _slide_text_sizes(data: dict[str, Any]) -> dict[str, int]:
    slide_type = data.get("type")
    title = str(data.get("title") or "")
    subtitle = str(data.get("subtitle") or "")
    bullets = data.get("bullets") or []
    bullet_count = len(bullets)
    quote = str(data.get("quote") or "")
    
    # Calculate density based on character counts and bullet frequency
    detail_text = " ".join(
        [
            subtitle,
            str(data.get("notes") or ""),
            quote,
            " ".join(bullets),
            " ".join(data.get("left_bullets") or []),
            " ".join(data.get("right_bullets") or []),
        ]
    ).strip()
    total_length = len(detail_text)
    
    # density_scale: reduce size further if there are many bullets or characters
    density_scale = 1.0
    if bullet_count > 4:
        density_scale *= 0.85
    if total_length > 250:
        density_scale *= 0.88
    if total_length > 400:
        density_scale *= 0.82

    if slide_type == "title_slide":
        scale = _scale_for_length(len(title), [(100, 0.65), (70, 0.75), (45, 0.88), (30, 0.95)])
        subtitle_scale = _scale_for_length(len(subtitle), [(140, 0.75), (90, 0.85), (60, 0.92)], 1.0)
        return {
            "title_font_size": _scaled_font_size(64 * scale),
            "subtitle_font_size": _scaled_font_size(24 * subtitle_scale),
            "small_font_size": _scaled_font_size(16 * density_scale),
        }

    if slide_type in {"title_bullets", "title_bullets_image", "comparison", "hero_image", "timeline", "statistics"}:
        scale = _scale_for_length(len(title), [(90, 0.70), (60, 0.80), (40, 0.90)])
        body_scale = _scale_for_length(total_length, [(400, 0.72), (250, 0.82), (150, 0.90)], 1.0) * density_scale
        
        heading_size = {
            "title_bullets": 42,
            "title_bullets_image": 36,
            "hero_image": 44,
            "comparison": 34,
            "timeline": 34,
            "statistics": 34,
        }.get(slide_type, 34)
        
        return {
            "heading_font_size": _scaled_font_size(heading_size * scale),
            "body_font_size": _scaled_font_size(24 * body_scale),
            "small_font_size": _scaled_font_size(16 * body_scale),
            "card_font_size": _scaled_font_size(18 * body_scale),
            "value_font_size": _scaled_font_size(52 * body_scale),
        }

    if slide_type == "quote":
        scale = _scale_for_length(len(quote), [(250, 0.75), (180, 0.85), (120, 0.92)], 1.0)
        return {
            "quote_font_size": _scaled_font_size(46 * scale),
            "attribution_font_size": _scaled_font_size(24 * scale),
            "body_font_size": _scaled_font_size(22 * scale),
        }

    return {}


def build_theme_tokens(presentation: Presentation) -> dict[str, str]:
    tokens = get_theme_tokens(presentation.theme)
    accent_rgb = _hex_to_rgb(tokens.accent_color)

    return {
        "style_name": tokens.name,
        "font": tokens.font_family,
        "accent": tokens.accent_color,
        "accent_strong": tokens.accent_color,
        "accent_soft": tokens.accent_soft_color,
        "bg_start": tokens.background,
        "bg_end": tokens.background_alt,
        "panel": tokens.surface,
        "border": tokens.border_color,
        "text": tokens.text_color,
        "muted": tokens.muted_text_color,
        "accent_rgb": ", ".join(str(channel) for channel in accent_rgb),
        "heading_font_family": tokens.heading_font_family,
        "body_font_family": tokens.body_font_family,
        "background_position": tokens.background_position,
        "background_size": tokens.background_size,
        "base_font_size": str(tokens.base_font_size),
        "heading_scale": str(tokens.heading_scale),
        "body_scale": str(tokens.body_scale),
        "line_height": str(tokens.line_height),
        "spacing_scale": str(tokens.spacing_scale),
        "shadow": tokens.shadow,
    }


def build_slide_context(presentation: Presentation) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for slide in presentation.slides:
        data = slide.model_dump(mode="json")
        logger.info("Preparing slide context. type=%s title=%s", data["type"], data["title"])
        data.update(_slide_text_sizes(data))
        # Build classes for content alignment and columns
        align = data.get("text_align") or "left"
        cols = int(data.get("columns") or 1)
        content_classes = f"slide__content--align-{align} columns-{cols}"

        slides.append(
            {
                **data,
                "template_name": f"{data['type']}.html",
                "image_asset": build_image_context(slide),
                "content_classes": content_classes,
            }
        )
    return slides


def render_presentation_html(presentation: Presentation) -> str:
    started_at = perf_counter()
    template = env.get_template("base.html")
    slides = build_slide_context(presentation)
    theme_tokens = build_theme_tokens(presentation)
    html = template.render(
        presentation=presentation.model_dump(mode="json"),
        slides=slides,
        theme_tokens=theme_tokens,
    )
    logger.info(
        "Rendered presentation HTML in %.2fs. slides=%s html_chars=%s",
        perf_counter() - started_at,
        len(slides),
        len(html),
    )
    return html


from app.services.exporters import build_presentation_exports as run_exporters


def build_presentation_exports(presentation: Presentation) -> tuple[str, str]:
    asset_id = uuid4().hex
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    layouted_document, semantic_theme = prepare_export_bundle(presentation)

    logger.info("Starting presentation export. asset_id=%s exporter=%s", asset_id, exporter_type)
    return run_exporters(layouted_document, semantic_theme, asset_id, exporter_type=exporter_type)


def build_pdf(presentation: Presentation) -> str:
    _, pdf_name = build_presentation_exports(presentation)
    return pdf_name
