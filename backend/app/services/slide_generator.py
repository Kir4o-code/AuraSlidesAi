import logging
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.presentation import Presentation
from app.services.image_service import build_image_context
from app.services.pdf_exporter import export_pdf
from app.services.pptx_generator import build_pptx
from app.services.theme_registry import get_theme_tokens


APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
OUTPUT_DIR = APP_DIR.parent / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = OUTPUT_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
PDF_TEXT_SCALE = 1.3

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


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
    quote = str(data.get("quote") or "")
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

    if slide_type == "title_slide":
        scale = _scale_for_length(len(title), [(120, 0.82), (85, 0.9), (60, 0.95)])
        subtitle_scale = _scale_for_length(len(subtitle), [(140, 0.82), (90, 0.9)], 1.0)
        return {
            "title_font_size": _scaled_font_size(40 * scale),
            "subtitle_font_size": _scaled_font_size(18 * subtitle_scale),
        }

    if slide_type in {"title_bullets", "title_bullets_image", "comparison", "hero_image", "timeline", "statistics"}:
        scale = _scale_for_length(len(title), [(120, 0.82), (85, 0.9), (60, 0.95)])
        body_scale = _scale_for_length(total_length, [(260, 0.85), (180, 0.92)], 1.0)
        heading_size = {
            "title_bullets": 28,
            "title_bullets_image": 26,
            "hero_image": 32,
            "comparison": 26,
            "timeline": 26,
            "statistics": 26,
        }.get(slide_type, 26)
        return {
            "heading_font_size": _scaled_font_size(heading_size * scale),
            "body_font_size": _scaled_font_size(16 * body_scale),
            "small_font_size": _scaled_font_size(12 * body_scale),
            "card_font_size": _scaled_font_size(13 * body_scale),
            "value_font_size": _scaled_font_size(26 * body_scale),
        }

    if slide_type == "quote":
        scale = _scale_for_length(len(quote), [(220, 0.72), (160, 0.82), (110, 0.9)], 1.0)
        attribution_scale = _scale_for_length(len(str(data.get("attribution") or "")), [(80, 0.9)], 1.0)
        return {
            "quote_font_size": _scaled_font_size(28 * scale),
            "attribution_font_size": _scaled_font_size(13 * attribution_scale),
            "body_font_size": _scaled_font_size(16 * scale),
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
    }


def build_slide_context(presentation: Presentation) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for slide in presentation.slides:
        data = slide.model_dump(mode="json")
        logger.info("Preparing slide context. type=%s title=%s", data["type"], data["title"])
        data.update(_slide_text_sizes(data))
        slides.append(
            {
                **data,
                "template_name": f"{data['type']}.html",
                "image_asset": build_image_context(slide),
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


def build_presentation_exports(presentation: Presentation) -> tuple[str, str]:
    logger.info("Starting PPTX-first slide rendering and PDF build.")
    html = render_presentation_html(presentation)
    asset_id = uuid4().hex
    pptx_name = build_pptx(presentation, asset_id=asset_id)
    pptx_path = OUTPUT_DIR / pptx_name
    pdf_name = f"{asset_id}.pdf"
    output_path = OUTPUT_DIR / pdf_name
    debug_html_path = DEBUG_DIR / f"{asset_id}.html"
    css_path = STATIC_DIR / "styles.css"
    debug_html_path.write_text(html, encoding="utf-8")
    logger.info("Saved debug HTML snapshot to %s", debug_html_path)
    export_pdf(
        pptx_path,
        output_path,
        html_fallback=html,
        css_path=css_path,
        base_url=APP_DIR,
    )
    return pptx_name, pdf_name


def build_pdf(presentation: Presentation) -> str:
    _, pdf_name = build_presentation_exports(presentation)
    return pdf_name
