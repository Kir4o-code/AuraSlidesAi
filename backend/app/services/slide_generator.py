import logging
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.presentation import Presentation
from app.services.image_service import build_image_context
from app.services.pdf_exporter import export_pdf


APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
OUTPUT_DIR = APP_DIR.parent / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = OUTPUT_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)

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
        return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return (37, 99, 235)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(channel, 255)):02x}" for channel in rgb)


def _mix(color_a: tuple[int, int, int], color_b: tuple[int, int, int], weight: float) -> tuple[int, int, int]:
    return tuple(
        round(color_a[index] * (1 - weight) + color_b[index] * weight)
        for index in range(3)
    )


def build_theme_tokens(presentation: Presentation) -> dict[str, str]:
    primary = _hex_to_rgb(presentation.theme.primary_color)
    white = (255, 255, 255)
    dark = (15, 23, 42)
    teal = (13, 148, 136)
    coral = (244, 114, 182)
    style = presentation.theme.style.lower()

    accent = primary
    if style == "playful":
        accent = _mix(primary, coral, 0.35)
        bg_start = _mix(primary, white, 0.88)
        bg_end = _mix(coral, white, 0.9)
        panel = _mix(primary, white, 0.93)
    elif style == "corporate":
        accent = _mix(primary, dark, 0.25)
        bg_start = _mix(primary, white, 0.95)
        bg_end = _mix(dark, white, 0.96)
        panel = _mix(primary, white, 0.97)
    elif style == "minimal":
        accent = _mix(primary, dark, 0.15)
        bg_start = (255, 255, 255)
        bg_end = _mix(primary, white, 0.97)
        panel = (255, 255, 255)
    else:
        accent = _mix(primary, teal, 0.15)
        bg_start = _mix(primary, white, 0.9)
        bg_end = _mix(teal, white, 0.93)
        panel = _mix(primary, white, 0.94)

    accent_strong = _mix(accent, dark, 0.3)
    accent_soft = _mix(accent, white, 0.82)
    border = _mix(accent, white, 0.72)
    text = dark
    muted = _mix(dark, white, 0.45)

    return {
        "style_name": style,
        "font": presentation.theme.font,
        "accent": _rgb_to_hex(accent),
        "accent_strong": _rgb_to_hex(accent_strong),
        "accent_soft": _rgb_to_hex(accent_soft),
        "bg_start": _rgb_to_hex(bg_start),
        "bg_end": _rgb_to_hex(bg_end),
        "panel": _rgb_to_hex(panel),
        "border": _rgb_to_hex(border),
        "text": _rgb_to_hex(text),
        "muted": _rgb_to_hex(muted),
        "accent_rgb": ", ".join(str(channel) for channel in accent),
    }


def build_slide_context(presentation: Presentation) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for slide in presentation.slides:
        data = slide.model_dump(mode="json")
        logger.info("Preparing slide context. layout=%s title=%s", data["layout"], data["title"])
        slides.append(
            {
                **data,
                "template_name": f"{data['layout']}.html",
                "image_asset": build_image_context(getattr(slide, "image", None)),
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


def build_pdf(presentation: Presentation) -> str:
    logger.info("Starting slide rendering and PDF build.")
    html = render_presentation_html(presentation)
    asset_id = uuid4().hex
    output_name = f"{asset_id}.pdf"
    output_path = OUTPUT_DIR / output_name
    debug_html_path = DEBUG_DIR / f"{asset_id}.html"
    css_path = STATIC_DIR / "styles.css"
    debug_html_path.write_text(html, encoding="utf-8")
    logger.info("Saved debug HTML snapshot to %s", debug_html_path)
    export_pdf(
        html=html,
        css_path=css_path,
        output_path=output_path,
        base_url=APP_DIR,
    )
    return output_name
