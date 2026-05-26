from __future__ import annotations

from pathlib import Path
from typing import Callable

from PIL import Image
from pptx import Presentation as PptxPresentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from app.schemas.presentation import Presentation, Slide, SlideType
from app.services.image_optimizer import optimize_image_file
from app.services.theme_registry import ThemeTokens, get_theme_tokens


SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)
BLANK_LAYOUT_INDEX = 6


def _rgb(value: str) -> RGBColor:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(char * 2 for char in cleaned)
    if len(cleaned) != 6:
        return RGBColor(37, 99, 235)
    return RGBColor(*(int(cleaned[index : index + 2], 16) for index in (0, 2, 4)))


def _fit_font_size(base: int, text: str, minimum: int, maximum: int) -> int:
    length = len(text.strip())
    if length <= 30:
        return maximum
    if length <= 60:
        return base
    if length <= 90:
        return max(minimum + 2, base - 4)
    if length <= 120:
        return max(minimum, base - 8)
    return minimum


def _scaled_font(tokens: ThemeTokens, value: int) -> int:
    return max(1, round(value * tokens.typography_scale))


def _scaled_space(tokens: ThemeTokens, value: float) -> float:
    return value * tokens.spacing_scale


def _heading_font(tokens: ThemeTokens) -> str:
    return tokens.heading_font_family or tokens.font_family


def _body_font(tokens: ThemeTokens) -> str:
    return tokens.body_font_family or tokens.font_family


def _blank_slide(prs: PptxPresentation):
    return prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])


def _apply_base(slide, tokens: ThemeTokens) -> None:
    # Ensure solid background first as fallback
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(tokens.background)

    # Add a rectangle for the gradient
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), SLIDE_WIDTH, SLIDE_HEIGHT
    )
    fill = rect.fill
    fill.gradient()
    # 135 degrees is a common diagonal gradient
    fill.gradient_angle = 135
    
    # Customize stops
    stops = fill.gradient_stops
    stops[0].position = 0.0
    stops[0].color.rgb = _rgb(tokens.background)
    
    stops[1].position = 1.0
    stops[1].color.rgb = _rgb(tokens.background_alt)
    
    # Remove border from the background rectangle
    rect.line.fill.background()

    # Brand accent bar (left side)
    accent = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.12), SLIDE_HEIGHT
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = _rgb(tokens.accent_color)
    accent.line.fill.background()


def _add_textbox(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    *,
    tokens: ThemeTokens | None = None,
    font_name: str,
    font_size: int,
    color: str,
    bold: bool = False,
    italic: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    all_caps: bool = False,
):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    frame.auto_size = MSO_AUTO_SIZE.NONE
    spacing_scale = tokens.spacing_scale if tokens else 1.0
    frame.margin_left = Inches(0.07 * spacing_scale)
    frame.margin_right = Inches(0.07 * spacing_scale)
    frame.margin_top = Inches(0.05 * spacing_scale)
    frame.margin_bottom = Inches(0.05 * spacing_scale)
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(round(3 * spacing_scale))
    paragraph.line_spacing = 1.14 + ((spacing_scale - 1.0) * 0.12)
    run = paragraph.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)
    if all_caps:
        run.font.all_caps = True
    return box


def _image_path(slide: Slide) -> Path | None:
    resolved = slide.resolved_image
    if not resolved:
        return None
    source_path = Path(resolved.local_path)
    try:
        optimized = optimize_image_file(source_path, cache_key=f"pptx-{slide.id}")
        return optimized.path
    except Exception:
        return source_path if source_path.exists() else None


def _fit_image(path: Path, max_width: float, max_height: float) -> tuple[float, float]:
    with Image.open(path) as image:
        width, height = image.size
    ratio = min(max_width / width, max_height / height)
    return width * ratio, height * ratio


def _add_image_in_box(slide, path: Path, left: float, top: float, width: float, height: float) -> None:
    image_width, image_height = _fit_image(path, width, height)
    offset_left = left + (width - image_width) / 2
    offset_top = top + (height - image_height) / 2
    slide.shapes.add_picture(str(path), Inches(offset_left), Inches(offset_top), Inches(image_width), Inches(image_height))


def _add_bullet_lines(slide, bullets: list[str], tokens: ThemeTokens, left: float, top: float, width: float) -> None:
    line_height = _scaled_space(tokens, 0.62 if len(bullets) <= 3 else 0.56)
    gap = _scaled_space(tokens, 0.18)
    for index, bullet in enumerate(bullets):
        row_top = top + index * (line_height + gap)
        _add_textbox(
            slide,
            left,
            row_top,
            width,
            line_height,
            f"• {bullet}",
            tokens=tokens,
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 17),
            color=tokens.text_color,
        )


def create_title_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    title_size = _scaled_font(tokens, _fit_font_size(38, slide.title or "", 24, 40))
    _add_textbox(
        page,
        1.5,
        1.85,
        10.33,
        2.2,
        slide.title or "",
        font_name=_heading_font(tokens),
        font_size=title_size + 4,
        color=tokens.text_color,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    if slide.subtitle:
        _add_textbox(
            page,
            1.3,
            3.2,
            10.65,
            0.78,
            slide.subtitle,
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 21),
            color=tokens.muted_text_color,
            align=PP_ALIGN.CENTER,
        )
    if slide.notes:
        _add_textbox(
            page,
            1.5,
            4.2,
            10.25,
            0.6,
            slide.notes,
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 13),
            color=tokens.muted_text_color,
            align=PP_ALIGN.CENTER,
        )


def create_bullets_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(30, slide.title or "", 22, 34))
    _add_textbox(
        page,
        1.2,
        1.0,
        10.9,
        1.0,
        slide.title or "",
        font_name=_heading_font(tokens),
        font_size=heading_size + 2,
        color=tokens.text_color,
        bold=True,
    )
    _add_bullet_lines(page, slide.bullets, tokens, 1.4, 2.6, 10.5)
    if slide.notes:
        _add_textbox(page, 1.2, 6.4, 10.8, 0.42, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)


def create_image_focus_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(28, slide.title or "", 22, 32))
    _add_textbox(page, 1.2, 1.0, 5.8, 0.98, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size + 2, color=tokens.text_color, bold=True)
    _add_bullet_lines(page, slide.bullets, tokens, 1.3, 2.45, 5.3)
    if slide.notes:
        _add_textbox(page, 1.2, 6.4, 5.7, 0.44, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)

    image_path = _image_path(slide)
    if image_path and image_path.exists():
        _add_image_in_box(page, image_path, 7.1, 1.2, 5.0, 5.2)
    else:
        _add_textbox(
            page,
            7.1,
            2.75,
            5.0,
            0.8,
            slide.image_prompt or "Image will be generated from the prompt",
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 18),
            color=tokens.text_color,
            bold=True,
            align=PP_ALIGN.CENTER,
        )


def create_hero_image_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    title_size = _scaled_font(tokens, _fit_font_size(34, slide.title or "", 22, 38))
    _add_textbox(page, 1.2, 1.2, 5.9, 1.34, slide.title or "", font_name=_heading_font(tokens), font_size=title_size + 2, color=tokens.text_color, bold=True)
    if slide.subtitle:
        _add_textbox(page, 1.2, 2.8, 5.7, 0.58, slide.subtitle, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.muted_text_color)
    if slide.notes:
        _add_textbox(page, 1.2, 3.6, 5.7, 0.78, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)

    image_path = _image_path(slide)
    if image_path and image_path.exists():
        _add_image_in_box(page, image_path, 7.5, 1.2, 5.2, 5.5)
    else:
        _add_textbox(
            page,
            7.5,
            2.7,
            5.2,
            0.8,
            slide.image_prompt or "Image will be generated from the prompt",
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 18),
            color=tokens.text_color,
            bold=True,
            align=PP_ALIGN.CENTER,
        )


def create_comparison_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(28, slide.title or "", 22, 32))
    _add_textbox(page, 1.2, 1.0, 10.9, 0.96, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size + 2, color=tokens.text_color, bold=True)
    if slide.notes:
        _add_textbox(page, 1.2, 2.0, 10.9, 0.46, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)

    _add_textbox(page, 1.2, 2.7, 5.4, 0.32, slide.left_title or "Option A", font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.accent_color, bold=True)
    _add_textbox(page, 7.2, 2.7, 5.4, 0.32, slide.right_title or "Option B", font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.accent_color, bold=True)
    _add_bullet_lines(page, slide.left_bullets, tokens, 1.2, 3.2, 5.0)
    _add_bullet_lines(page, slide.right_bullets, tokens, 7.2, 3.2, 5.0)


def create_timeline_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(28, slide.title or "", 22, 32))
    _add_textbox(page, 1.2, 1.0, 10.9, 0.85, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size + 2, color=tokens.text_color, bold=True)

    top = 2.4
    for index, step in enumerate(slide.timeline):
        row_top = top + index * _scaled_space(tokens, 1.15)
        marker = page.shapes.add_shape(MSO_SHAPE.OVAL, Inches(1.2), Inches(row_top + 0.12), Inches(0.16), Inches(0.16))
        marker.fill.solid()
        marker.fill.fore_color.rgb = _rgb(tokens.accent_color)
        marker.line.fill.background()
        _add_textbox(page, 1.5, row_top + 0.01, 2.15, 0.38, step.label, font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.accent_color, bold=True)
        if step.detail:
            _add_textbox(page, 3.8, row_top - 0.01, 8.1, 0.5, step.detail, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 13), color=tokens.text_color)


def create_statistics_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(28, slide.title or "", 22, 32))
    _add_textbox(page, 1.2, 1.0, 10.9, 0.85, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size + 2, color=tokens.text_color, bold=True)

    columns = 3 if len(slide.statistics) >= 3 else 2
    x_positions = [1.2, 5.2, 9.2] if columns == 3 else [1.2, 7.3]
    y_positions = [2.4, 4.5]
    card_width = 3.55 if columns == 3 else 5.0
    for index, stat in enumerate(slide.statistics[:6]):
        col = index % columns
        row = index // columns
        left = x_positions[col]
        top = y_positions[row]
        value_size = _scaled_font(tokens, _fit_font_size(30, stat.value, 24, 34))
        _add_textbox(page, left, top, card_width, 0.62, stat.value, font_name=_heading_font(tokens), font_size=value_size + 4, color=tokens.accent_color, bold=True)
        _add_textbox(page, left, top + 0.72, card_width, 0.32, stat.label, font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.text_color, bold=True)
        if stat.detail:
            _add_textbox(page, left, top + 1.08, card_width, 0.4, stat.detail, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)

    if slide.notes:
        _add_textbox(page, 1.2, 6.48, 11.0, 0.34, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color)


def create_quote_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    quote_size = _scaled_font(tokens, _fit_font_size(30, slide.quote or "", 24, 34))
    _add_textbox(page, 1.5, 2.0, 10.3, 2.78, slide.quote or "", font_name=_heading_font(tokens), font_size=quote_size + 4, color=tokens.text_color, bold=True, align=PP_ALIGN.CENTER)
    if slide.attribution:
        _add_textbox(page, 2.0, 4.82, 9.4, 0.44, slide.attribution, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.muted_text_color, align=PP_ALIGN.CENTER)
    if slide.notes:
        _add_textbox(page, 2.1, 5.38, 9.2, 0.7, slide.notes, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 11), color=tokens.muted_text_color, align=PP_ALIGN.CENTER)


SLIDE_RENDERERS: dict[SlideType, Callable[[PptxPresentation, Slide, ThemeTokens], None]] = {
    SlideType.TITLE_SLIDE: create_title_slide,
    SlideType.TITLE_BULLETS: create_bullets_slide,
    SlideType.TITLE_BULLETS_IMAGE: create_image_focus_slide,
    SlideType.HERO_IMAGE: create_hero_image_slide,
    SlideType.COMPARISON: create_comparison_slide,
    SlideType.TIMELINE: create_timeline_slide,
    SlideType.STATISTICS: create_statistics_slide,
    SlideType.QUOTE: create_quote_slide,
}


def build_pptx_presentation(presentation: Presentation) -> PptxPresentation:
    pptx = PptxPresentation()
    pptx.slide_width = SLIDE_WIDTH
    pptx.slide_height = SLIDE_HEIGHT
    tokens = get_theme_tokens(presentation.theme)

    for slide in presentation.slides:
        renderer = SLIDE_RENDERERS.get(slide.type)
        if renderer is None:
            continue
        renderer(pptx, slide, tokens)

    return pptx
