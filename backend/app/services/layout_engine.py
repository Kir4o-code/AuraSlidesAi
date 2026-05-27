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
from app.semantic.contracts import Alignment
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
    line_height = _scaled_space(tokens, 0.72)
    gap = _scaled_space(tokens, 0.28)
    for index, bullet in enumerate(bullets):
        row_top = top + index * (line_height + gap)
        _add_textbox(
            slide,
            left,
            row_top,
            width,
            line_height,
            f"- {bullet}",
            tokens=tokens,
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 20),
            color=tokens.text_color,
        )

def create_title_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    title_size = _scaled_font(tokens, _fit_font_size(44, slide.title or "", 28, 52))
    _add_textbox(
        page,
        1.5,
        2.2,
        10.33,
        2.5,
        slide.title or "",
        font_name=_heading_font(tokens),
        font_size=title_size,
        color=tokens.text_color,
        bold=True,
        align=PP_ALIGN.CENTER,
    )
    if slide.subtitle:
        _add_textbox(
            page,
            1.5,
            4.8,
            10.33,
            1.0,
            slide.subtitle,
            font_name=_body_font(tokens),
            font_size=_scaled_font(tokens, 22),
            color=tokens.muted_text_color,
            align=PP_ALIGN.CENTER,
        )

def create_bullets_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(32, slide.title or "", 24, 38))
    _add_textbox(
        page,
        1.2,
        0.8,
        10.9,
        1.2,
        slide.title or "",
        font_name=_heading_font(tokens),
        font_size=heading_size,
        color=tokens.text_color,
        bold=True,
    )
    _add_bullet_lines(page, slide.bullets, tokens, 1.2, 2.2, 10.9)

def create_image_focus_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(30, slide.title or "", 22, 36))
    _add_textbox(page, 1.2, 0.8, 6.2, 1.2, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size, color=tokens.text_color, bold=True)
    _add_bullet_lines(page, slide.bullets, tokens, 1.2, 2.2, 6.0)

    image_path = _image_path(slide)
    if image_path and image_path.exists():
        _add_image_in_box(page, image_path, 7.8, 1.2, 4.8, 5.2)
    else:
        _add_textbox(page, 7.8, 2.8, 4.8, 0.8, slide.image_prompt or "AI Visual", font_name=_body_font(tokens), font_size=_scaled_font(tokens, 18), color=tokens.text_color, bold=True, align=PP_ALIGN.CENTER)

def create_hero_image_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    title_size = _scaled_font(tokens, _fit_font_size(36, slide.title or "", 24, 42))
    _add_textbox(page, 1.2, 1.8, 5.8, 1.8, slide.title or "", font_name=_heading_font(tokens), font_size=title_size, color=tokens.text_color, bold=True)
    if slide.subtitle:
        _add_textbox(page, 1.2, 3.8, 5.8, 0.8, slide.subtitle, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 18), color=tokens.muted_text_color)

    image_path = _image_path(slide)
    if image_path and image_path.exists():
        _add_image_in_box(page, image_path, 7.4, 1.0, 5.2, 5.5)

def create_comparison_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(30, slide.title or "", 22, 36))
    _add_textbox(page, 1.2, 0.8, 10.9, 1.0, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size, color=tokens.text_color, bold=True)
    
    _add_textbox(page, 1.2, 2.0, 5.3, 0.4, slide.left_title or "A", font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 16), color=tokens.accent_color, bold=True)
    _add_textbox(page, 6.8, 2.0, 5.3, 0.4, slide.right_title or "B", font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 16), color=tokens.accent_color, bold=True)
    
    _add_bullet_lines(page, slide.left_bullets, tokens, 1.2, 2.6, 5.3)
    _add_bullet_lines(page, slide.right_bullets, tokens, 6.8, 2.6, 5.3)

def create_timeline_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(30, slide.title or "", 22, 36))
    _add_textbox(page, 1.2, 0.8, 10.9, 1.0, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size, color=tokens.text_color, bold=True)

    top = 2.2
    for index, step in enumerate(slide.timeline):
        row_top = top + index * _scaled_space(tokens, 1.2)
        _add_textbox(page, 1.5, row_top + 0.1, 2.2, 0.4, step.label, font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 16), color=tokens.accent_color, bold=True)
        if step.detail:
            _add_textbox(page, 3.8, row_top + 0.1, 8.0, 0.4, step.detail, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.text_color)

def create_statistics_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    heading_size = _scaled_font(tokens, _fit_font_size(30, slide.title or "", 22, 36))
    _add_textbox(page, 1.2, 0.8, 10.9, 1.0, slide.title or "", font_name=_heading_font(tokens), font_size=heading_size, color=tokens.text_color, bold=True)

    cols = min(3, len(slide.statistics))
    rows = (len(slide.statistics) + cols - 1) // cols
    width = 10.9 / cols - 0.2
    for i, stat in enumerate(slide.statistics):
        c, r = i % cols, i // cols
        left, top = 1.2 + c * (width + 0.3), 2.2 + r * 2.2
        _add_textbox(page, left + 0.2, top + 0.2, width - 0.4, 0.6, stat.value, font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 32), color=tokens.accent_color, bold=True, align=PP_ALIGN.CENTER)
        _add_textbox(page, left + 0.2, top + 0.8, width - 0.4, 0.4, stat.label, font_name=_heading_font(tokens), font_size=_scaled_font(tokens, 14), color=tokens.text_color, bold=True, align=PP_ALIGN.CENTER)
        if hasattr(stat, 'detail') and stat.detail:
             _add_textbox(page, left + 0.2, top + 1.2, width - 0.4, 0.4, stat.detail, font_name=_body_font(tokens), font_size=_scaled_font(tokens, 12), color=tokens.muted_text_color, align=PP_ALIGN.CENTER)

def create_quote_slide(prs: PptxPresentation, slide: Slide, tokens: ThemeTokens):
    page = _blank_slide(prs)
    _apply_base(page, tokens)
    quote_size = _scaled_font(tokens, _fit_font_size(34, slide.quote or "", 24, 46))
    _add_textbox(page, 1.5, 2.5, 10.3, 3.0, slide.quote or "", font_name=_heading_font(tokens), font_size=quote_size, color=tokens.text_color, bold=True, align=PP_ALIGN.CENTER)
    if slide.attribution:
        _add_textbox(page, 1.5, 5.5, 10.3, 0.6, f"- {slide.attribution}", font_name=_body_font(tokens), font_size=_scaled_font(tokens, 20), color=tokens.muted_text_color, align=PP_ALIGN.CENTER)

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
        if renderer is not None:
            renderer(pptx, slide, tokens)

    return pptx


from app.semantic.contracts import LayoutElement, LayoutElementKind, LayoutedPresentationDocument, ThemeDefinition


PX_TO_INCH = 1.0 / 96.0


def _px(value: int) -> float:
    return value * PX_TO_INCH


def _semantic_font_name(theme: ThemeDefinition, region: str, kind: LayoutElementKind) -> str:
    if kind in {LayoutElementKind.QUOTE, LayoutElementKind.STATISTIC}:
        return theme.tokens.fonts.heading or theme.tokens.fonts.body
    if region in {"title", "quote", "attribution"}:
        return theme.tokens.fonts.heading or theme.tokens.fonts.body
    return theme.tokens.fonts.body or theme.tokens.fonts.heading


def _export_font_name(value: str | None, fallback: str = "Aptos") -> str:
    if not value:
        return fallback
    first = value.split(",", 1)[0].strip().strip("'\"")
    return first or fallback


def _add_shape_icon(slide, left: float, top: float, size: float, icon: str, theme: ThemeDefinition) -> None:
    bg = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(_px(left)), Inches(_px(top)), Inches(_px(size)), Inches(_px(size)))
    bg.fill.solid()
    bg.fill.fore_color.rgb = _rgb(theme.tokens.accent_secondary)
    bg.line.color.rgb = _rgb(theme.tokens.accent_primary)
    inset = size * 0.24
    color = _rgb(theme.tokens.accent_primary)
    if icon == "chart":
        bar_w = size * 0.12
        for i, h in enumerate((0.22, 0.36, 0.5)):
            bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(_px(left + inset + i * bar_w * 1.8)), Inches(_px(top + size - inset - size * h)), Inches(_px(bar_w)), Inches(_px(size * h)))
            bar.fill.solid()
            bar.fill.fore_color.rgb = color
            bar.line.fill.background()
    elif icon == "bolt":
        tri = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(_px(left + inset)), Inches(_px(top + inset * 0.8)), Inches(_px(size - inset * 2)), Inches(_px(size - inset * 1.6)))
        tri.fill.solid()
        tri.fill.fore_color.rgb = color
        tri.line.fill.background()
    elif icon == "idea":
        bulb = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(_px(left + inset)), Inches(_px(top + inset)), Inches(_px(size - inset * 2)), Inches(_px(size - inset * 2.2)))
        bulb.fill.solid()
        bulb.fill.fore_color.rgb = color
        bulb.line.fill.background()
        base = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(_px(left + size * 0.4)), Inches(_px(top + size * 0.62)), Inches(_px(size * 0.2)), Inches(_px(size * 0.12)))
        base.fill.solid()
        base.fill.fore_color.rgb = color
        base.line.fill.background()
    else:
        ring = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(_px(left + inset)), Inches(_px(top + inset)), Inches(_px(size - inset * 2)), Inches(_px(size - inset * 2)))
        ring.fill.background()
        ring.line.color.rgb = color
        ring.line.width = Pt(2)
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(_px(left + size * 0.43)), Inches(_px(top + size * 0.43)), Inches(_px(size * 0.14)), Inches(_px(size * 0.14)))
        dot.fill.solid()
        dot.fill.fore_color.rgb = color
        dot.line.fill.background()


def _render_debug_label(slide, element: LayoutElement, left: float, top: float, theme: ThemeDefinition) -> None:
    box = slide.shapes.add_textbox(Inches(_px(left + 4)), Inches(_px(top + 4)), Inches(max(_px(min(element.width, 200)), 0.4)), Inches(0.22))
    frame = box.text_frame
    frame.clear()
    run = frame.paragraphs[0].add_run()
    run.text = f"{element.region} | {element.x},{element.y} {element.width}x{element.height}"
    run.font.name = _export_font_name(theme.tokens.fonts.mono or theme.tokens.fonts.body)
    run.font.size = Pt(7)
    run.font.color.rgb = _rgb(theme.tokens.accent_primary)


def _render_layout_element(slide, element: LayoutElement, theme: ThemeDefinition, *, offset_x: int = 0, offset_y: int = 0, debug_mode: bool = False) -> None:
    left = offset_x + element.x
    top = offset_y + element.y
    width = element.width
    height = element.height

    if element.kind == LayoutElementKind.PANEL:
        panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
        panel.fill.solid()
        panel.fill.fore_color.rgb = _rgb(theme.tokens.surface)
        panel.line.color.rgb = _rgb(theme.tokens.border)
        panel.line.width = Pt(1)
    elif element.kind == LayoutElementKind.IMAGE:
        local_path = element.content.get("local_path") if isinstance(element.content, dict) else None
        public_url = element.content.get("src") if isinstance(element.content, dict) else None
        image_path = Path(local_path) if local_path else None
        if image_path and image_path.exists():
            slide.shapes.add_picture(str(image_path), Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
        else:
            placeholder = slide.shapes.add_textbox(Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
            frame = placeholder.text_frame
            frame.word_wrap = True
            frame.clear()
            run = frame.paragraphs[0].add_run()
            run.text = element.content.get("prompt") or element.text or "Image"
            run.font.name = _export_font_name(theme.tokens.fonts.body)
            run.font.size = Pt(max(10, (element.font_size or 18) * 0.7))
            run.font.color.rgb = _rgb(theme.tokens.text_primary)
            placeholder.fill.solid()
            placeholder.fill.fore_color.rgb = _rgb(theme.tokens.background_alt)
            placeholder.line.color.rgb = _rgb(theme.tokens.border)
    elif element.kind == LayoutElementKind.BULLET_ITEM:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
        card.fill.solid()
        card.fill.fore_color.rgb = _rgb(theme.tokens.surface)
        card.line.color.rgb = _rgb(theme.tokens.border)
        card.line.width = Pt(1)
        _add_shape_icon(slide, left + 16, top + 14, 42, str(element.content.get("icon") or "target"), theme)
        textbox = slide.shapes.add_textbox(Inches(_px(left + 72)), Inches(_px(top + 12)), Inches(_px(max(width - 88, 20))), Inches(_px(max(height - 18, 20))))
        frame = textbox.text_frame
        frame.word_wrap = True
        frame.clear()
        frame.margin_left = Inches(0.02)
        frame.margin_right = Inches(0.02)
        frame.margin_top = Inches(0.02)
        frame.margin_bottom = Inches(0.02)
        run = frame.paragraphs[0].add_run()
        run.text = element.text or ""
        run.font.name = _export_font_name(_semantic_font_name(theme, element.region, element.kind))
        run.font.size = Pt(element.font_size or 18)
        run.font.color.rgb = _rgb(theme.tokens.text_primary)
    elif element.content.get("decorative_icon"):
        _add_shape_icon(slide, left, top, min(width, height), str(element.content.get("icon") or "target"), theme)
    else:
        textbox = slide.shapes.add_textbox(Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
        frame = textbox.text_frame
        frame.word_wrap = element.wrap
        frame.clear()
        frame.margin_left = Inches(0.02)
        frame.margin_right = Inches(0.02)
        frame.margin_top = Inches(0.02)
        frame.margin_bottom = Inches(0.02)
        paragraph = frame.paragraphs[0]
        paragraph.alignment = {
            Alignment.START: PP_ALIGN.LEFT,
            Alignment.CENTER: PP_ALIGN.CENTER,
            Alignment.END: PP_ALIGN.RIGHT,
        }[element.align]
        run = paragraph.add_run()
        if element.kind == LayoutElementKind.BULLET_ITEM:
            run.text = f"- {element.text or ''}"
        else:
            run.text = element.text or ""
        run.font.name = _export_font_name(_semantic_font_name(theme, element.region, element.kind))
        if element.font_size:
            run.font.size = Pt(element.font_size)
        run.font.color.rgb = _rgb(theme.tokens.text_primary)

    if debug_mode:
        debug_box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(_px(left)), Inches(_px(top)), Inches(_px(width)), Inches(_px(height)))
        debug_box.fill.background()
        debug_box.line.color.rgb = _rgb(theme.tokens.accent_primary)
        debug_box.line.width = Pt(1)
        _render_debug_label(slide, element, left, top, theme)

    for child in element.children:
        _render_layout_element(slide, child, theme, offset_x=left, offset_y=top, debug_mode=debug_mode)


def _render_layout_slide(prs: PptxPresentation, slide_data: LayoutedSlide, theme: ThemeDefinition) -> None:
    page = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT_INDEX])
    page.background.fill.solid()
    page.background.fill.fore_color.rgb = _rgb(theme.tokens.background)

    background = page.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), SLIDE_WIDTH, SLIDE_HEIGHT)
    background.fill.gradient()
    background.fill.gradient_angle = 135
    stops = background.fill.gradient_stops
    stops[0].position = 0.0
    stops[0].color.rgb = _rgb(theme.tokens.background)
    stops[1].position = 1.0
    stops[1].color.rgb = _rgb(theme.tokens.background_alt)
    background.line.fill.background()

    accent = page.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.12), SLIDE_HEIGHT)
    accent.fill.solid()
    accent.fill.fore_color.rgb = _rgb(theme.tokens.accent_primary)
    accent.line.fill.background()

    for element in slide_data.elements:
        _render_layout_element(page, element, theme, debug_mode=slide_data.debug_mode)


def build_pptx_presentation(layouted_presentation: LayoutedPresentationDocument, theme: ThemeDefinition) -> PptxPresentation:
    pptx = PptxPresentation()
    pptx.slide_width = SLIDE_WIDTH
    pptx.slide_height = SLIDE_HEIGHT

    for slide in layouted_presentation.slides:
        _render_layout_slide(pptx, slide, theme)

    return pptx

