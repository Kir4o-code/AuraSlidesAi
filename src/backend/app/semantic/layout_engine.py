from __future__ import annotations

import math
from typing import Any

from app.semantic.contracts import (
    Alignment,
    LayoutDebugInfo,
    LayoutedPresentationDocument,
    LayoutedSlide,
    LayoutElement,
    LayoutElementKind,
    PresentationDocument,
    Slide,
)
from app.semantic.icons import choose_semantic_icon

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MARGIN_X = 80
MARGIN_Y = 72
GRID_GAP = 24
TEXT_LINE_HEIGHT = 1.28
PANEL_PADDING = 24


def _scale_spacing(value: int | float, spacing_scale: float) -> int:
    return max(0, int(round(value * spacing_scale)))


def _gap(base: int | float, spacing_scale: float, minimum: int | float | None = None) -> int:
    scaled = _scale_spacing(base, spacing_scale)
    if minimum is None:
        return scaled
    return max(int(round(minimum)), scaled)


def _scale_type(value: int, typography_scale: float, minimum: int | None = None) -> int:
    scaled = int(round(value * typography_scale))
    if minimum is not None:
        return max(minimum, scaled)
    return scaled


def _fit_font_size(base: int, text: str, minimum: int, maximum: int) -> int:
    length = len(" ".join(text.split()))
    if length <= 30:
        return maximum
    if length <= 52:
        return max(minimum + 2, base - 4)
    if length <= 72:
        return max(minimum, base - 8)
    return minimum


def _available_width() -> int:
    return CANVAS_WIDTH - (MARGIN_X * 2)


def _item_field(item: Any, field_name: str, default: Any = None) -> Any:
    if hasattr(item, field_name):
        return getattr(item, field_name)
    if isinstance(item, dict):
        return item.get(field_name, default)
    return default


def _estimate_chars_per_line(width: int, font_size: int) -> int:
    if font_size <= 0:
        return 1
    # Exported PPT text, especially Cyrillic at large sizes, is wider than the
    # preview estimate. Reserve extra height so following elements never collide.
    return max(8, int(width / max(font_size * 0.58, 1)))


def _estimate_lines(text: str, width: int, font_size: int) -> int:
    cleaned = " ".join(text.split())
    if not cleaned:
        return 0
    chars_per_line = _estimate_chars_per_line(width, font_size)
    return max(1, math.ceil(len(cleaned) / chars_per_line))


def _text_height(
    text: str, width: int, font_size: int, *, min_height: int = 0, padding_y: int = 0
) -> tuple[int, int, int]:
    lines = _estimate_lines(text, width, font_size)
    estimated = int(math.ceil(lines * font_size * TEXT_LINE_HEIGHT)) + (padding_y * 2)
    return max(min_height, estimated), lines, _estimate_chars_per_line(width, font_size)


def _fit_text_block(
    text: str,
    width: int,
    font_size: int,
    *,
    min_font_size: int,
    max_height: int | None = None,
    min_height: int = 0,
    padding_y: int = 0,
) -> tuple[int, int]:
    current = font_size
    height, _, _ = _text_height(text, width, current, min_height=min_height, padding_y=padding_y)
    while max_height is not None and current > min_font_size and height > max_height:
        current -= 1
        height, _, _ = _text_height(text, width, current, min_height=min_height, padding_y=padding_y)
    if max_height is not None:
        height = min(height, max_height)
    return current, height


def _make_debug(
    text: str, width: int, font_size: int, spacing_before: int = 0, spacing_after: int = 0, note: str | None = None
) -> LayoutDebugInfo:
    height, lines, chars_per_line = _text_height(text, width, font_size)
    return LayoutDebugInfo(
        content_length=len(text),
        estimated_lines=lines,
        estimated_chars_per_line=chars_per_line,
        spacing_before=spacing_before,
        spacing_after=spacing_after,
        note=note,
    )


def _text_element(
    *,
    element_id: str,
    region: str,
    x: int,
    y: int,
    width: int,
    text: str,
    font_size: int,
    align: Alignment = Alignment.START,
    min_height: int = 0,
    spacing_before: int = 0,
    spacing_after: int = 0,
    kind: LayoutElementKind = LayoutElementKind.TEXT,
    content: dict | None = None,
    note: str | None = None,
    max_height: int | None = None,
    min_font_size: int | None = None,
) -> LayoutElement:
    resolved_font_size = font_size
    if min_font_size is not None and max_height is not None:
        resolved_font_size, height = _fit_text_block(
            text,
            width,
            font_size,
            min_font_size=min_font_size,
            max_height=max_height,
            min_height=min_height,
        )
    else:
        height, _, _ = _text_height(text, width, font_size, min_height=min_height)
    return LayoutElement(
        id=element_id,
        kind=kind,
        region=region,
        x=x,
        y=y,
        width=width,
        height=height,
        align=align,
        wrap=True,
        font_size=resolved_font_size,
        line_height=TEXT_LINE_HEIGHT,
        text=text,
        content=content or {},
        debug=_make_debug(text, width, resolved_font_size, spacing_before, spacing_after, note),
    )


def _slide_media(slide: Slide) -> dict | None:
    media = getattr(slide, "media", None) or []
    if not media:
        return None
    first = media[0]
    if isinstance(first, dict):
        return first
    return first.model_dump(mode="json") if hasattr(first, "model_dump") else None


def _image_content(slide: Slide, media: dict | None) -> dict:
    metadata = (media or {}).get("metadata") or {}
    image_class = metadata.get("image_class")
    width = metadata.get("width")
    height = metadata.get("height")
    fit = (
        "contain"
        if image_class in {"icon", "diagram"} or (width and height and width / max(height, 1) < 0.9)
        else "cover"
    )
    return {
        "image": True,
        "src": (media or {}).get("public_url") or (media or {}).get("local_path"),
        "local_path": (media or {}).get("local_path"),
        "alt": (media or {}).get("alt") or slide.image_prompt or slide.title or slide.id,
        "prompt": (media or {}).get("prompt") or slide.image_prompt,
        "fit": fit,
    }


def _content_bottom(children: list[LayoutElement]) -> int:
    return max((child.y + child.height for child in children), default=0)


def _bullet_list_element(
    *,
    element_id: str,
    region: str,
    x: int,
    y: int,
    width: int,
    bullets: list[str],
    font_size: int,
    align: Alignment = Alignment.START,
    max_height: int | None = None,
    icon_context: str = "",
) -> LayoutElement:
    text_width = max(1, width - 64)
    row_padding = 24
    row_min_height = 56
    row_gap = 16

    def list_height(size: int) -> int:
        return sum(
            max(_text_height(bullet, text_width, size)[0] + row_padding, row_min_height) + row_gap for bullet in bullets
        )

    while font_size > 15 and max_height is not None and list_height(font_size) > max_height:
        font_size -= 1

    child_y = y
    children: list[LayoutElement] = []
    for index, bullet in enumerate(bullets):
        item_height, _, _ = _text_height(bullet, text_width, font_size)
        item_height = max(item_height + row_padding, row_min_height)
        children.append(
            LayoutElement(
                id=f"{element_id}_item_{index + 1}",
                kind=LayoutElementKind.BULLET_ITEM,
                region=f"{region}.bullet.{index + 1}",
                x=0,
                y=child_y - y,
                width=width,
                height=item_height,
                align=align,
                wrap=True,
                font_size=font_size,
                line_height=TEXT_LINE_HEIGHT,
                text=bullet,
                content={
                    "bullet": True,
                    "index": index,
                    "icon": choose_semantic_icon(f"{icon_context} {bullet}", role=region, index=index),
                },
                debug=_make_debug(bullet, text_width, font_size, 0, 0, "bullet item"),
            )
        )
        child_y += item_height + row_gap

    total_height = max(1, child_y - y)
    return LayoutElement(
        id=element_id,
        kind=LayoutElementKind.BULLET_LIST,
        region=region,
        x=x,
        y=y,
        width=width,
        height=total_height,
        align=align,
        wrap=True,
        font_size=font_size,
        line_height=TEXT_LINE_HEIGHT,
        content={"bullets": bullets},
        children=children,
        debug=LayoutDebugInfo(
            content_length=sum(len(item) for item in bullets),
            estimated_lines=sum(max(1, _estimate_lines(item, text_width, font_size)) for item in bullets),
            estimated_chars_per_line=_estimate_chars_per_line(text_width, font_size),
            spacing_before=0,
            spacing_after=0,
            note="bullet list",
        ),
    )


def _panel_element(
    *,
    element_id: str,
    region: str,
    x: int,
    y: int,
    width: int,
    height: int,
    children: list[LayoutElement],
    note: str,
) -> LayoutElement:
    def inset(child: LayoutElement) -> LayoutElement:
        available_width = max(1, width - (PANEL_PADDING * 2) - child.x)
        available_height = max(1, height - (PANEL_PADDING * 2) - child.y)
        child_width = min(child.width, available_width)
        child_height = min(child.height, available_height)
        nested = child.children
        if child.kind == LayoutElementKind.BULLET_LIST:
            nested = [item.model_copy(update={"width": min(item.width, child_width)}) for item in child.children]
        return child.model_copy(
            update={
                "x": child.x + PANEL_PADDING,
                "y": child.y + PANEL_PADDING,
                "width": child_width,
                "height": child_height,
                "children": nested,
            }
        )

    return LayoutElement(
        id=element_id,
        kind=LayoutElementKind.PANEL,
        region=region,
        x=x,
        y=y,
        width=width,
        height=height,
        align=Alignment.START,
        wrap=False,
        content={"panel": True, "padding": PANEL_PADDING},
        children=[inset(child) for child in children],
        debug=LayoutDebugInfo(
            content_length=sum(child.debug.content_length if child.debug else 0 for child in children),
            estimated_lines=sum(child.debug.estimated_lines if child.debug else 0 for child in children),
            estimated_chars_per_line=0,
            spacing_before=0,
            spacing_after=0,
            note=note,
        ),
    )


def _layout_title_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    width = _available_width()
    title_font = _scale_type(_fit_font_size(66, slide.title or "", 38, 66), typography_scale, 34)
    subtitle_font = _scale_type(_fit_font_size(28, slide.subtitle or "", 18, 28), typography_scale, 18)
    notes_font = _scale_type(19, typography_scale, 16)
    y = 112
    elements: list[LayoutElement] = []

    if slide.title:
        title_font, title_height = _fit_text_block(
            slide.title, width, title_font, min_font_size=34, max_height=260, min_height=92, padding_y=8
        )
        title_gap = _gap(30, spacing_scale, 22)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.CENTER,
                min_height=title_height,
                spacing_after=title_gap,
                note="title",
            )
        )
        y += title_height + title_gap

    if slide.subtitle:
        subtitle_width = min(960, width)
        subtitle_x = (CANVAS_WIDTH - subtitle_width) // 2
        subtitle_font, subtitle_height = _fit_text_block(
            slide.subtitle, subtitle_width, subtitle_font, min_font_size=16, max_height=96, min_height=44, padding_y=4
        )
        subtitle_gap = _gap(18, spacing_scale, 14)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_subtitle",
                region="subtitle",
                x=subtitle_x,
                y=y,
                width=subtitle_width,
                text=slide.subtitle,
                font_size=subtitle_font,
                align=Alignment.CENTER,
                min_height=subtitle_height,
                spacing_after=subtitle_gap,
                note="subtitle",
            )
        )
        y += subtitle_height + subtitle_gap

    if slide.notes:
        notes_width = min(840, width)
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_height, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=30)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=notes_x,
                y=max(y, 520),
                width=notes_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.CENTER,
                min_height=notes_height,
                note="notes",
            )
        )

    return elements


def _layout_title_left_feature_slide(
    slide: Slide, spacing_scale: float, typography_scale: float
) -> list[LayoutElement]:
    width = _available_width()
    title_font = _scale_type(_fit_font_size(62, slide.title or "", 34, 62), typography_scale, 32)
    subtitle_font = _scale_type(_fit_font_size(26, slide.subtitle or "", 17, 26), typography_scale, 17)
    notes_font = _scale_type(18, typography_scale, 16)
    y = 104
    elements: list[LayoutElement] = []

    if slide.title:
        title_width = min(760, width)
        title_font, title_height = _fit_text_block(
            slide.title, title_width, title_font, min_font_size=32, max_height=260, min_height=96, padding_y=8
        )
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=y,
                width=title_width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="title",
            )
        )
        y += title_height + _gap(30, spacing_scale, 22)

    if slide.subtitle:
        subtitle_width = min(640, width)
        subtitle_font, subtitle_height = _fit_text_block(
            slide.subtitle, subtitle_width, subtitle_font, min_font_size=16, max_height=112, min_height=44, padding_y=4
        )
        elements.append(
            _text_element(
                element_id=f"{slide.id}_subtitle",
                region="subtitle",
                x=MARGIN_X,
                y=y,
                width=subtitle_width,
                text=slide.subtitle,
                font_size=subtitle_font,
                align=Alignment.START,
                min_height=subtitle_height,
                note="subtitle",
            )
        )
        y += subtitle_height + _gap(18, spacing_scale, 14)

    if slide.notes:
        notes_width = min(620, width)
        notes_height, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=26)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=MARGIN_X,
                y=max(y, 560),
                width=notes_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )

    return elements


def _layout_bullets_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    width = _available_width()
    title_font = _scale_type(_fit_font_size(46, slide.title or "", 34, 46), typography_scale, 32)
    bullet_font = _scale_type(24, typography_scale, 20)
    notes_font = _scale_type(17, typography_scale, 15)
    elements: list[LayoutElement] = []
    y = 86

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=72, padding_y=6)
        title_gap = _gap(34, spacing_scale, 24)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                spacing_after=title_gap,
                note="title",
            )
        )
        y += title_height + title_gap

    bullets = slide.bullets or []
    body_y = max(y + _gap(12, spacing_scale, 8), 224)
    bullet_list = _bullet_list_element(
        element_id=f"{slide.id}_bullets",
        region="body",
        x=MARGIN_X,
        y=body_y,
        width=width,
        bullets=bullets,
        font_size=bullet_font,
        max_height=CANVAS_HEIGHT - body_y - 54,
        icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}",
    )
    elements.append(bullet_list)
    y = body_y + bullet_list.height + _gap(22, spacing_scale, 16)

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=MARGIN_X,
                y=max(y, 588),
                width=width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )

    return elements


def _layout_bullets_dense_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    width = _available_width()
    title_font = _scale_type(_fit_font_size(40, slide.title or "", 28, 40), typography_scale, 28)
    bullet_font = _scale_type(20, typography_scale, 17)
    notes_font = _scale_type(16, typography_scale, 14)
    elements: list[LayoutElement] = []
    y = 82

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=58, padding_y=4)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="dense title",
            )
        )
        y += title_height + _gap(20, spacing_scale, 14)

    bullet_list = _bullet_list_element(
        element_id=f"{slide.id}_bullets",
        region="body",
        x=MARGIN_X,
        y=y,
        width=width,
        bullets=slide.bullets or [],
        font_size=bullet_font,
        max_height=CANVAS_HEIGHT - y - 80,
        icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}",
    )
    elements.append(bullet_list)
    y += bullet_list.height + _gap(14, spacing_scale, 10)

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=24)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=MARGIN_X,
                y=max(y, 614),
                width=width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="dense notes",
            )
        )
    return elements


def _layout_image_bullets_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 560
    right_x = 708
    right_width = 484
    title_font = _scale_type(_fit_font_size(38, slide.title or "", 24, 38), typography_scale, 24)
    bullet_font = _scale_type(21, typography_scale, 18)
    notes_font = _scale_type(17, typography_scale, 15)
    title_y = 90
    left_height_limit = CANVAS_HEIGHT - title_y - 42
    inner_width = left_width - (PANEL_PADDING * 2)
    inner_height = left_height_limit - (PANEL_PADDING * 2)

    left_children: list[LayoutElement] = []
    if slide.title:
        title_font, title_height = _fit_text_block(
            slide.title, inner_width, title_font, min_font_size=20, max_height=170, min_height=72, padding_y=8
        )
        title_gap = _gap(42, spacing_scale, 32)
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=0,
                y=0,
                width=inner_width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                spacing_after=title_gap,
                note="title",
            )
        )
        offset_y = title_height + title_gap
    else:
        offset_y = 0

    bullet_y = offset_y + _gap(10, spacing_scale, 8)
    notes_height = _text_height(slide.notes or "", inner_width, notes_font, min_height=26)[0] if slide.notes else 0
    notes_reserve = notes_height + _gap(18, spacing_scale, 12) if slide.notes else 0
    bullet_list = _bullet_list_element(
        element_id=f"{slide.id}_bullets",
        region="body",
        x=0,
        y=bullet_y,
        width=inner_width,
        bullets=slide.bullets or [],
        font_size=bullet_font,
        max_height=max(120, inner_height - bullet_y - notes_reserve),
        icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}",
    )
    left_children.append(bullet_list)
    offset_y = bullet_y + bullet_list.height + _gap(24, spacing_scale, 16)

    if slide.notes:
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=0,
                y=offset_y,
                width=inner_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )

    left_height = min(CANVAS_HEIGHT - title_y - 42, max(500, _content_bottom(left_children) + (PANEL_PADDING * 2)))
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_left",
            region="body",
            x=left_x,
            y=title_y,
            width=left_width,
            height=left_height,
            children=left_children,
            note="left text column",
        )
    )

    image_height = 460
    image_y = 136
    media = _slide_media(slide)
    image_children = [
        LayoutElement(
            id=f"{slide.id}_image",
            kind=LayoutElementKind.IMAGE,
            region="media",
            x=0,
            y=0,
            width=right_width - (PANEL_PADDING * 2),
            height=image_height - (PANEL_PADDING * 2),
            align=Alignment.CENTER,
            wrap=False,
            content=_image_content(slide, media),
            debug=LayoutDebugInfo(
                content_length=len(slide.image_prompt or ""),
                estimated_lines=0,
                estimated_chars_per_line=0,
                spacing_before=0,
                spacing_after=0,
                note="image box",
            ),
        )
    ]
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_image_panel",
            region="media",
            x=right_x,
            y=image_y,
            width=right_width,
            height=image_height,
            children=image_children,
            note="image panel",
        )
    )
    return elements


def _layout_image_focus_split_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 430
    right_x = 548
    right_width = 648
    title_font = _scale_type(_fit_font_size(36, slide.title or "", 26, 36), typography_scale, 25)
    bullet_font = _scale_type(21, typography_scale, 18)
    notes_font = _scale_type(16, typography_scale, 14)
    panel_y = 92
    inner_width = left_width - (PANEL_PADDING * 2)

    left_children: list[LayoutElement] = []
    y = 0
    if slide.title:
        title_font, title_height = _fit_text_block(
            slide.title, inner_width, title_font, min_font_size=20, max_height=150, min_height=60, padding_y=6
        )
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=0,
                y=y,
                width=inner_width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="title",
            )
        )
        y += title_height + _gap(34, spacing_scale, 24)
    if slide.bullets:
        bullets = _bullet_list_element(
            element_id=f"{slide.id}_bullets",
            region="body",
            x=0,
            y=y,
            width=inner_width,
            bullets=slide.bullets or [],
            font_size=bullet_font,
            max_height=290,
            icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}",
        )
        left_children.append(bullets)
        y += bullets.height + _gap(16, spacing_scale, 10)
    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, inner_width, notes_font, min_height=24)
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=0,
                y=y,
                width=inner_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )

    left_height = max(500, _content_bottom(left_children) + (PANEL_PADDING * 2))
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_left",
            region="body",
            x=left_x,
            y=panel_y,
            width=left_width,
            height=left_height,
            children=left_children,
            note="image focus left column",
        )
    )

    media = _slide_media(slide)
    image_children = [
        LayoutElement(
            id=f"{slide.id}_image",
            kind=LayoutElementKind.IMAGE,
            region="media",
            x=0,
            y=0,
            width=right_width - (PANEL_PADDING * 2),
            height=536 - (PANEL_PADDING * 2),
            align=Alignment.CENTER,
            wrap=False,
            content=_image_content(slide, media),
            debug=LayoutDebugInfo(
                content_length=len(slide.image_prompt or ""),
                estimated_lines=0,
                estimated_chars_per_line=0,
                spacing_before=0,
                spacing_after=0,
                note="image focus panel",
            ),
        )
    ]
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_image_panel",
            region="media",
            x=right_x,
            y=112,
            width=right_width,
            height=536,
            children=image_children,
            note="image-focused panel",
        )
    )
    return elements


def _layout_hero_image_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 468
    right_x = 616
    right_width = 580
    title_font = _scale_type(_fit_font_size(44, slide.title or "", 28, 44), typography_scale, 26)
    subtitle_font = _scale_type(_fit_font_size(24, slide.subtitle or "", 16, 24), typography_scale, 16)
    notes_font = _scale_type(17, typography_scale, 15)

    left_children: list[LayoutElement] = []
    y = 168
    title_offset = 0
    if slide.title:
        title_font, title_height = _fit_text_block(
            slide.title, left_width, title_font, min_font_size=24, max_height=180, min_height=68, padding_y=6
        )
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=0,
                y=0,
                width=left_width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="hero title",
            )
        )
        title_offset = title_height + _gap(28, spacing_scale, 20)
    if slide.subtitle:
        subtitle_font, subtitle_height = _fit_text_block(
            slide.subtitle, left_width, subtitle_font, min_font_size=15, max_height=96, min_height=42, padding_y=4
        )
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_subtitle",
                region="subtitle",
                x=0,
                y=title_offset,
                width=left_width,
                text=slide.subtitle,
                font_size=subtitle_font,
                align=Alignment.START,
                min_height=subtitle_height,
                note="hero subtitle",
            )
        )
        y += subtitle_height + _gap(16, spacing_scale, 12)
    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, left_width, notes_font, min_height=26)
        left_children.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=0,
                y=max(y, 420),
                width=left_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )

    left_height = max(460, sum(child.height + 16 for child in left_children))
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_text",
            region="body",
            x=left_x,
            y=170,
            width=left_width,
            height=left_height,
            children=left_children,
            note="hero text column",
        )
    )

    media = _slide_media(slide)
    image_children = [
        LayoutElement(
            id=f"{slide.id}_image",
            kind=LayoutElementKind.IMAGE,
            region="media",
            x=0,
            y=0,
            width=right_width - (PANEL_PADDING * 2),
            height=440 - (PANEL_PADDING * 2),
            align=Alignment.CENTER,
            wrap=False,
            content=_image_content(slide, media),
            debug=LayoutDebugInfo(
                content_length=len(slide.image_prompt or ""),
                estimated_lines=0,
                estimated_chars_per_line=0,
                spacing_before=0,
                spacing_after=0,
                note="hero image",
            ),
        )
    ]
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_image_panel",
            region="media",
            x=right_x,
            y=126,
            width=right_width,
            height=440,
            children=image_children,
            note="hero image panel",
        )
    )
    return elements


def _layout_comparison_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = _scale_type(40, typography_scale, 34)
    notes_font = _scale_type(17, typography_scale, 15)
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=title_y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="comparison title",
            )
        )
        title_y += title_height + _gap(18, spacing_scale, 14)

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=MARGIN_X,
                y=title_y,
                width=width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.START,
                min_height=notes_height,
                note="notes",
            )
        )
        title_y += notes_height + _gap(18, spacing_scale, 14)

    panel_width = 500
    left_x = 80
    right_x = 700
    panel_y = max(title_y + 8, 196)

    def panel(side: str, x: int, heading: str | None, bullets: list[str]) -> LayoutElement:
        heading_font = _scale_type(17, typography_scale, 15)
        bullet_font = _scale_type(19, typography_scale, 16)
        child_y = 0
        children: list[LayoutElement] = []
        if heading:
            heading_height, _, _ = _text_height(heading, panel_width - 40, heading_font, min_height=28)
            children.append(
                _text_element(
                    element_id=f"{slide.id}_{side}_heading",
                    region=f"{side}.heading",
                    x=0,
                    y=0,
                    width=panel_width - 40,
                    text=heading,
                    font_size=heading_font,
                    align=Alignment.START,
                    min_height=heading_height,
                    max_height=52,
                    min_font_size=14,
                    note=f"{side} heading",
                )
            )
            child_y += heading_height + _gap(14, spacing_scale, 10)
        bullet_list = _bullet_list_element(
            element_id=f"{slide.id}_{side}_bullets",
            region=f"{side}.body",
            x=0,
            y=child_y,
            width=panel_width - 40,
            bullets=bullets,
            font_size=bullet_font,
            max_height=250,
            icon_context=f"{slide.title or ''} {heading or ''}",
        )
        children.append(bullet_list)
        height = max(320, sum(child.height + _gap(14, spacing_scale, 10) for child in children))
        return _panel_element(
            element_id=f"{slide.id}_{side}_panel",
            region=side,
            x=x,
            y=panel_y,
            width=panel_width,
            height=height,
            children=children,
            note=f"{side} comparison panel",
        )

    elements.append(panel("left", left_x, slide.left_title or "Option A", slide.left_bullets or []))
    elements.append(panel("right", right_x, slide.right_title or "Option B", slide.right_bullets or []))
    return elements


def _layout_timeline_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = _scale_type(40, typography_scale, 34)
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=title_y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="timeline title",
            )
        )
        title_y += title_height + _gap(24, spacing_scale, 18)

    rows: list[LayoutElement] = []
    y = max(title_y, 168)
    label_width = 220
    row_width = width
    for index, step in enumerate(slide.timeline or []):
        row_children: list[LayoutElement] = []
        label_font = _scale_type(18, typography_scale, 15)
        detail_font = _scale_type(18, typography_scale, 15)
        step_label = _item_field(step, "label", "")
        step_detail = _item_field(step, "detail")
        detail_w = row_width - label_width - _gap(40, spacing_scale, 28)
        label_h, _, _ = _text_height(step_label, label_width, label_font, min_height=28)
        detail_h, _, _ = _text_height(step_detail or "", detail_w, detail_font, min_height=28)
        row_h = max(label_h, detail_h) + _gap(48, spacing_scale, 34)
        row_children.append(
            _text_element(
                element_id=f"{slide.id}_step_{index + 1}_label",
                region=f"timeline.{index + 1}.label",
                x=0,
                y=0,
                width=label_width,
                text=step_label,
                font_size=label_font,
                align=Alignment.START,
                min_height=label_h,
                max_height=row_h - 24,
                min_font_size=14,
                note="timeline label",
            )
        )
        if step_detail:
            row_children.append(
                _text_element(
                    element_id=f"{slide.id}_step_{index + 1}_detail",
                    region=f"timeline.{index + 1}.detail",
                    x=label_width + _gap(40, spacing_scale, 28),
                    y=0,
                    width=detail_w,
                    text=step_detail,
                    font_size=detail_font,
                    align=Alignment.START,
                    min_height=detail_h,
                    max_height=row_h - 24,
                    min_font_size=14,
                    note="timeline detail",
                )
            )
        rows.append(
            _panel_element(
                element_id=f"{slide.id}_step_{index + 1}",
                region="timeline",
                x=MARGIN_X,
                y=y,
                width=row_width,
                height=row_h,
                children=row_children,
                note="timeline step",
            )
        )
        y += row_h + _gap(20, spacing_scale, 14)

    elements.extend(rows)
    return elements


def _layout_statistics_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = _scale_type(40, typography_scale, 34)
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=title_y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="statistics title",
            )
        )
        title_y += title_height + _gap(24, spacing_scale, 18)

    cards = slide.statistics or []
    columns = 3 if len(cards) > 2 else max(1, len(cards))
    grid_gap = _gap(GRID_GAP, spacing_scale, 16)
    card_width = int((width - (grid_gap * (columns - 1))) / columns)
    card_height = 208
    x0 = MARGIN_X
    y0 = max(title_y, 192)
    for index, stat in enumerate(cards):
        col = index % columns
        row = index // columns
        x = x0 + (col * (card_width + grid_gap))
        y = y0 + (row * (card_height + grid_gap))
        inner_width = card_width - (PANEL_PADDING * 2)
        inner_height = card_height - (PANEL_PADDING * 2)
        value_font = _scale_type(36, typography_scale, 26)
        label_font = _scale_type(16, typography_scale, 13)
        detail_font = _scale_type(15, typography_scale, 12)
        child_elements: list[LayoutElement] = []
        stat_value = _item_field(stat, "value", "")
        stat_label = _item_field(stat, "label", "")
        stat_detail = _item_field(stat, "detail")
        value_font, value_h = _fit_text_block(
            stat_value, inner_width, value_font, min_font_size=22, max_height=54, min_height=38
        )
        label_gap = _gap(8, spacing_scale, 6)
        detail_gap = _gap(10, spacing_scale, 8)
        detail_budget = 58 if stat_detail else 0
        label_budget = max(28, inner_height - value_h - label_gap - detail_budget - (detail_gap if stat_detail else 0))
        label_font, label_h = _fit_text_block(
            stat_label, inner_width, label_font, min_font_size=11, max_height=label_budget, min_height=22
        )
        child_elements.append(
            _text_element(
                element_id=f"{slide.id}_stat_{index + 1}_value",
                region=f"stat.{index + 1}.value",
                x=0,
                y=0,
                width=inner_width,
                text=stat_value,
                font_size=value_font,
                align=Alignment.CENTER,
                min_height=value_h,
                max_height=54,
                min_font_size=22,
                note="stat value",
            )
        )
        child_elements.append(
            _text_element(
                element_id=f"{slide.id}_stat_{index + 1}_label",
                region=f"stat.{index + 1}.label",
                x=0,
                y=value_h + label_gap,
                width=inner_width,
                text=stat_label,
                font_size=label_font,
                align=Alignment.CENTER,
                min_height=label_h,
                max_height=label_budget,
                min_font_size=11,
                note="stat label",
            )
        )
        if stat_detail:
            detail_y = value_h + label_gap + label_h + detail_gap
            detail_height = max(22, inner_height - detail_y)
            child_elements.append(
                _text_element(
                    element_id=f"{slide.id}_stat_{index + 1}_detail",
                    region=f"stat.{index + 1}.detail",
                    x=0,
                    y=detail_y,
                    width=inner_width,
                    text=stat_detail,
                    font_size=detail_font,
                    align=Alignment.CENTER,
                    min_height=22,
                    max_height=detail_height,
                    min_font_size=10,
                    note="stat detail",
                )
            )
        elements.append(
            _panel_element(
                element_id=f"{slide.id}_stat_{index + 1}",
                region="statistics",
                x=x,
                y=y,
                width=card_width,
                height=card_height,
                children=child_elements,
                note="stat card",
            )
        )
    return elements


def _layout_statistics_featured_slide(
    slide: Slide, spacing_scale: float, typography_scale: float
) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = _scale_type(38, typography_scale, 32)
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=52)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_title",
                region="title",
                x=MARGIN_X,
                y=title_y,
                width=width,
                text=slide.title,
                font_size=title_font,
                align=Alignment.START,
                min_height=title_height,
                note="featured statistics title",
            )
        )
        title_y += title_height + _gap(22, spacing_scale, 16)

    cards = slide.statistics or []
    if not cards:
        return elements

    hero = cards[0]
    hero_width = 388
    hero_height = 300
    hero_children: list[LayoutElement] = []
    hero_value = _item_field(hero, "value", "")
    hero_label = _item_field(hero, "label", "")
    hero_detail = _item_field(hero, "detail")
    hero_value_font = _scale_type(_fit_font_size(42, hero_value, 24, 42), typography_scale, 24)
    hero_label_font = _scale_type(17, typography_scale, 14)
    hero_detail_font = _scale_type(15, typography_scale, 12)
    value_h, _, _ = _text_height(hero_value, hero_width - 40, hero_value_font, min_height=52)
    label_h, _, _ = _text_height(hero_label, hero_width - 40, hero_label_font, min_height=24)
    hero_children.append(
        _text_element(
            element_id=f"{slide.id}_hero_stat_value",
            region="hero_metric.value",
            x=0,
            y=0,
            width=hero_width - 40,
            text=hero_value,
            font_size=hero_value_font,
            align=Alignment.START,
            min_height=value_h,
            max_height=132,
            min_font_size=22,
            note="hero stat value",
        )
    )
    hero_children.append(
        _text_element(
            element_id=f"{slide.id}_hero_stat_label",
            region="hero_metric.label",
            x=0,
            y=value_h + 14,
            width=hero_width - 40,
            text=hero_label,
            font_size=hero_label_font,
            align=Alignment.START,
            min_height=label_h,
            max_height=60,
            min_font_size=13,
            note="hero stat label",
        )
    )
    if hero_detail:
        detail_h, _, _ = _text_height(hero_detail, hero_width - 40, hero_detail_font, min_height=22)
        hero_children.append(
            _text_element(
                element_id=f"{slide.id}_hero_stat_detail",
                region="hero_metric.detail",
                x=0,
                y=value_h + label_h + 32,
                width=hero_width - 40,
                text=hero_detail,
                font_size=hero_detail_font,
                align=Alignment.START,
                min_height=detail_h,
                max_height=96,
                min_font_size=12,
                note="hero stat detail",
            )
        )
    elements.append(
        _panel_element(
            element_id=f"{slide.id}_hero_stat",
            region="hero_metric",
            x=MARGIN_X,
            y=max(title_y, 176),
            width=hero_width,
            height=hero_height,
            children=hero_children,
            note="featured statistic",
        )
    )

    secondary = cards[1:]
    grid_x = MARGIN_X + hero_width + 28
    grid_width = CANVAS_WIDTH - grid_x - MARGIN_X
    card_width = int((grid_width - 24) / 2)
    card_height = 196
    for index, stat in enumerate(secondary[:4]):
        col = index % 2
        row = index // 2
        x = grid_x + col * (card_width + 24)
        y = max(title_y, 176) + row * (card_height + 24)
        value = _item_field(stat, "value", "")
        label = _item_field(stat, "label", "")
        detail = _item_field(stat, "detail")
        inner_width = card_width - (PANEL_PADDING * 2)
        inner_height = card_height - (PANEL_PADDING * 2)
        value_font, value_h = _fit_text_block(
            value,
            inner_width,
            _scale_type(_fit_font_size(28, value, 18, 28), typography_scale, 18),
            min_font_size=16,
            max_height=48,
            min_height=32,
        )
        label_y = value_h + 8
        label_font, label_h = _fit_text_block(
            label,
            inner_width,
            _scale_type(15, typography_scale, 12),
            min_font_size=11,
            max_height=38,
            min_height=20,
        )
        child_elements = [
            _text_element(
                element_id=f"{slide.id}_stat_{index + 2}_value",
                region=f"stat.{index + 2}.value",
                x=0,
                y=0,
                width=inner_width,
                text=value,
                font_size=value_font,
                align=Alignment.START,
                min_height=value_h,
                max_height=48,
                min_font_size=16,
                note="stat value",
            ),
            _text_element(
                element_id=f"{slide.id}_stat_{index + 2}_label",
                region=f"stat.{index + 2}.label",
                x=0,
                y=label_y,
                width=inner_width,
                text=label,
                font_size=label_font,
                align=Alignment.START,
                min_height=label_h,
                max_height=38,
                min_font_size=11,
                note="stat label",
            ),
        ]
        if detail:
            detail_y = label_y + label_h + 8
            child_elements.append(
                _text_element(
                    element_id=f"{slide.id}_stat_{index + 2}_detail",
                    region=f"stat.{index + 2}.detail",
                    x=0,
                    y=detail_y,
                    width=inner_width,
                    text=detail,
                    font_size=_scale_type(14, typography_scale, 12),
                    align=Alignment.START,
                    min_height=22,
                    max_height=max(22, inner_height - detail_y),
                    min_font_size=10,
                    note="stat detail",
                )
            )
        elements.append(
            _panel_element(
                element_id=f"{slide.id}_stat_{index + 2}",
                region="metrics",
                x=x,
                y=y,
                width=card_width,
                height=card_height,
                children=child_elements,
                note="secondary statistic",
            )
        )
    return elements


def _layout_quote_slide(slide: Slide, spacing_scale: float, typography_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    quote_width = 960
    quote_x = (CANVAS_WIDTH - quote_width) // 2
    quote_y = 220
    quote_font = _scale_type(46, typography_scale, 38)
    attr_font = _scale_type(22, typography_scale, 18)
    notes_font = _scale_type(17, typography_scale, 15)

    if slide.quote:
        quote_h, _, _ = _text_height(slide.quote, quote_width, quote_font, min_height=100)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_quote",
                region="quote",
                x=quote_x,
                y=quote_y,
                width=quote_width,
                text=slide.quote,
                font_size=quote_font,
                align=Alignment.CENTER,
                min_height=quote_h,
                note="quote",
            )
        )
        quote_y += quote_h + _gap(18, spacing_scale, 14)

    if slide.attribution:
        attr_width = min(700, quote_width)
        attr_x = (CANVAS_WIDTH - attr_width) // 2
        attr_h, _, _ = _text_height(slide.attribution, attr_width, attr_font, min_height=24)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_attribution",
                region="attribution",
                x=attr_x,
                y=quote_y,
                width=attr_width,
                text=slide.attribution,
                font_size=attr_font,
                align=Alignment.CENTER,
                min_height=attr_h,
                note="attribution",
            )
        )
        quote_y += attr_h + _gap(16, spacing_scale, 12)

    if slide.notes:
        notes_width = 760
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_h, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=22)
        elements.append(
            _text_element(
                element_id=f"{slide.id}_notes",
                region="notes",
                x=notes_x,
                y=max(quote_y, 540),
                width=notes_width,
                text=slide.notes,
                font_size=notes_font,
                align=Alignment.CENTER,
                min_height=notes_h,
                note="notes",
            )
        )
    return elements


def _layout_slide(slide: Slide, debug_mode: bool, spacing_scale: float, typography_scale: float) -> LayoutedSlide:
    layout_name = slide.layout_name
    layout_function = {
        "title.centered": _layout_title_slide,
        "title.left_feature": _layout_title_left_feature_slide,
        "content.bullets": _layout_bullets_slide,
        "content.bullets_dense": _layout_bullets_dense_slide,
        "content.image_split": _layout_image_bullets_slide,
        "content.image_focus_split": _layout_image_focus_split_slide,
        "hero.focus": _layout_hero_image_slide,
        "comparison.split": _layout_comparison_slide,
        "timeline.stacked": _layout_timeline_slide,
        "statistics.grid": _layout_statistics_slide,
        "statistics.featured": _layout_statistics_featured_slide,
        "quote.centered": _layout_quote_slide,
    }.get(layout_name, _layout_bullets_slide)
    elements = layout_function(slide, spacing_scale, typography_scale)

    return LayoutedSlide(
        slide_id=slide.id,
        layout_name=layout_name,
        canvas_width=CANVAS_WIDTH,
        canvas_height=CANVAS_HEIGHT,
        elements=elements,
        debug_mode=debug_mode,
        debug={
            "element_count": len(elements),
            "slide_type": getattr(slide, "type", None),
        },
    )


def build_layouted_presentation(
    document: PresentationDocument,
    *,
    debug_mode: bool = False,
    spacing_scale: float = 1.0,
    typography_scale: float = 1.0,
) -> LayoutedPresentationDocument:
    return LayoutedPresentationDocument(
        title=document.title,
        version=document.version,
        metadata=document.metadata,
        slides=[_layout_slide(slide, debug_mode, spacing_scale, typography_scale) for slide in document.slides],
    )
