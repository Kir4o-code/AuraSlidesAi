from __future__ import annotations

import math
from typing import Iterable

from app.semantic.contracts import (
    Alignment,
    LayoutDebugInfo,
    LayoutElement,
    LayoutElementKind,
    LayoutedPresentationDocument,
    LayoutedSlide,
    PresentationDocument,
)
from app.semantic.icons import choose_semantic_icon


CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MARGIN_X = 80
MARGIN_Y = 72
GRID_GAP = 24
TEXT_LINE_HEIGHT = 1.18
PANEL_PADDING = 18


def _scale_spacing(value: int | float, spacing_scale: float) -> int:
    return max(0, int(round(value * spacing_scale)))


def _gap(base: int | float, spacing_scale: float, minimum: int | float | None = None) -> int:
    scaled = _scale_spacing(base, spacing_scale)
    if minimum is None:
        return scaled
    return max(int(round(minimum)), scaled)


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


def _item_field(item, field_name: str, default=None):
    if hasattr(item, field_name):
        return getattr(item, field_name)
    if isinstance(item, dict):
        return item.get(field_name, default)
    return default


def _estimate_chars_per_line(width: int, font_size: int) -> int:
    if font_size <= 0:
        return 1
    # 0.56 is a stable approximation for a mixed sans-serif deck font.
    return max(12, int(width / max(font_size * 0.56, 1)))


def _estimate_lines(text: str, width: int, font_size: int) -> int:
    cleaned = " ".join(text.split())
    if not cleaned:
        return 0
    chars_per_line = _estimate_chars_per_line(width, font_size)
    return max(1, math.ceil(len(cleaned) / chars_per_line))


def _text_height(text: str, width: int, font_size: int, *, min_height: int = 0, padding_y: int = 0) -> tuple[int, int, int]:
    lines = _estimate_lines(text, width, font_size)
    estimated = int(math.ceil(lines * font_size * TEXT_LINE_HEIGHT)) + (padding_y * 2)
    return max(min_height, estimated), lines, _estimate_chars_per_line(width, font_size)


def _make_debug(text: str, width: int, font_size: int, spacing_before: int = 0, spacing_after: int = 0, note: str | None = None) -> LayoutDebugInfo:
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
) -> LayoutElement:
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
        font_size=font_size,
        line_height=TEXT_LINE_HEIGHT,
        text=text,
        content=content or {},
        debug=_make_debug(text, width, font_size, spacing_before, spacing_after, note),
    )


def _slide_media(slide) -> dict | None:
    media = getattr(slide, "media", None) or []
    if not media:
        return None
    first = media[0]
    if isinstance(first, dict):
        return first
    return first.model_dump(mode="json") if hasattr(first, "model_dump") else None


def _image_content(slide, media: dict | None) -> dict:
    metadata = (media or {}).get("metadata") or {}
    image_class = metadata.get("image_class")
    width = metadata.get("width")
    height = metadata.get("height")
    fit = "contain" if image_class in {"icon", "diagram"} or (width and height and width / max(height, 1) < 0.9) else "cover"
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
    def list_height(size: int) -> int:
        return sum(max(_text_height(bullet, width - 58, size)[0] + 14, 40) + 12 for bullet in bullets)

    while font_size > 15 and max_height is not None and list_height(font_size) > max_height:
        font_size -= 1

    child_y = y
    children: list[LayoutElement] = []
    for index, bullet in enumerate(bullets):
        item_height, _, _ = _text_height(bullet, width - 58, font_size)
        item_height = max(item_height + 14, 40)
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
                content={"bullet": True, "index": index, "icon": choose_semantic_icon(f"{icon_context} {bullet}", role=region, index=index)},
                debug=_make_debug(bullet, width - 58, font_size, 0, 0, "bullet item"),
            )
        )
        child_y += item_height + 12

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
            estimated_lines=sum(max(1, _estimate_lines(item, width - 58, font_size)) for item in bullets),
            estimated_chars_per_line=_estimate_chars_per_line(width - 58, font_size),
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
            nested = [
                item.model_copy(update={"width": min(item.width, child_width)})
                for item in child.children
            ]
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


def _layout_title_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    width = _available_width()
    title_font = 66
    subtitle_font = 26
    notes_font = 18
    y = 138
    elements: list[LayoutElement] = []

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=92)
        title_gap = _gap(24, spacing_scale, 18)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=y, width=width, text=slide.title, font_size=title_font, align=Alignment.CENTER, min_height=title_height, spacing_after=title_gap, note="title"))
        y += title_height + title_gap

    if slide.subtitle:
        subtitle_width = min(960, width)
        subtitle_x = (CANVAS_WIDTH - subtitle_width) // 2
        subtitle_height, _, _ = _text_height(slide.subtitle, subtitle_width, subtitle_font, min_height=40)
        subtitle_gap = _gap(18, spacing_scale, 14)
        elements.append(_text_element(element_id=f"{slide.id}_subtitle", region="subtitle", x=subtitle_x, y=y, width=subtitle_width, text=slide.subtitle, font_size=subtitle_font, align=Alignment.CENTER, min_height=subtitle_height, spacing_after=subtitle_gap, note="subtitle"))
        y += subtitle_height + subtitle_gap

    if slide.notes:
        notes_width = min(840, width)
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_height, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=30)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=notes_x, y=max(y, 520), width=notes_width, text=slide.notes, font_size=notes_font, align=Alignment.CENTER, min_height=notes_height, note="notes"))

    return elements


def _layout_bullets_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    width = _available_width()
    title_font = _fit_font_size(42, slide.title or "", 30, 42)
    bullet_font = 22
    notes_font = 16
    elements: list[LayoutElement] = []
    y = 86

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=72, padding_y=6)
        title_gap = _gap(34, spacing_scale, 24)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, spacing_after=title_gap, note="title"))
        y += title_height + title_gap

    bullets = slide.bullets or []
    body_y = max(y, 224)
    bullet_list = _bullet_list_element(element_id=f"{slide.id}_bullets", region="body", x=MARGIN_X, y=body_y, width=width, bullets=bullets, font_size=bullet_font, max_height=CANVAS_HEIGHT - body_y - 54, icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}")
    elements.append(bullet_list)
    y = body_y + bullet_list.height + _gap(22, spacing_scale, 16)

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=MARGIN_X, y=max(y, 588), width=width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))

    return elements


def _layout_image_bullets_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 560
    right_x = 708
    right_width = 484
    title_font = _fit_font_size(38, slide.title or "", 28, 38)
    bullet_font = 20
    notes_font = 16
    title_y = 90
    inner_width = left_width - (PANEL_PADDING * 2)
    inner_height = 548 - (PANEL_PADDING * 2)

    left_children: list[LayoutElement] = []
    if slide.title:
        title_height, _, _ = _text_height(slide.title, inner_width, title_font, min_height=68, padding_y=4)
        title_gap = _gap(24, spacing_scale, 16)
        left_children.append(_text_element(element_id=f"{slide.id}_title", region="title", x=0, y=0, width=inner_width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, spacing_after=title_gap, note="title"))
        offset_y = title_height + title_gap
    else:
        offset_y = 0

    bullet_y = max(offset_y, 112)
    notes_height = _text_height(slide.notes or "", inner_width, notes_font, min_height=26)[0] if slide.notes else 0
    notes_reserve = notes_height + _gap(18, spacing_scale, 12) if slide.notes else 0
    bullet_list = _bullet_list_element(element_id=f"{slide.id}_bullets", region="body", x=0, y=bullet_y, width=inner_width, bullets=slide.bullets or [], font_size=bullet_font, max_height=max(120, inner_height - bullet_y - notes_reserve), icon_context=f"{slide.title or ''} {getattr(slide, 'icon_intent', '') or ''}")
    left_children.append(bullet_list)
    offset_y = bullet_y + bullet_list.height + _gap(18, spacing_scale, 12)

    if slide.notes:
        left_children.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=0, y=offset_y, width=inner_width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))

    left_height = min(CANVAS_HEIGHT - title_y - 42, max(500, _content_bottom(left_children) + (PANEL_PADDING * 2)))
    elements.append(_panel_element(element_id=f"{slide.id}_left", region="body", x=left_x, y=title_y, width=left_width, height=left_height, children=left_children, note="left text column"))

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
    elements.append(_panel_element(element_id=f"{slide.id}_image_panel", region="media", x=right_x, y=image_y, width=right_width, height=image_height, children=image_children, note="image panel"))
    return elements


def _layout_hero_image_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 468
    right_x = 616
    right_width = 580
    title_font = 40
    subtitle_font = 22
    notes_font = 16

    left_children: list[LayoutElement] = []
    y = 168
    title_offset = 0
    if slide.title:
        title_height, _, _ = _text_height(slide.title, left_width, title_font, min_height=60)
        left_children.append(_text_element(element_id=f"{slide.id}_title", region="title", x=0, y=0, width=left_width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="hero title"))
        title_offset = title_height + _gap(20, spacing_scale, 14)
    if slide.subtitle:
        subtitle_height, _, _ = _text_height(slide.subtitle, left_width, subtitle_font, min_height=40)
        left_children.append(_text_element(element_id=f"{slide.id}_subtitle", region="subtitle", x=0, y=title_offset, width=left_width, text=slide.subtitle, font_size=subtitle_font, align=Alignment.START, min_height=subtitle_height, note="hero subtitle"))
        y += subtitle_height + _gap(16, spacing_scale, 12)
    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, left_width, notes_font, min_height=26)
        left_children.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=0, y=max(y, 420), width=left_width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))

    left_height = max(460, sum(child.height + 16 for child in left_children))
    elements.append(_panel_element(element_id=f"{slide.id}_text", region="body", x=left_x, y=170, width=left_width, height=left_height, children=left_children, note="hero text column"))

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
    elements.append(_panel_element(element_id=f"{slide.id}_image_panel", region="media", x=right_x, y=126, width=right_width, height=440, children=image_children, note="hero image panel"))
    return elements


def _layout_comparison_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    notes_font = 16
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="comparison title"))
        title_y += title_height + _gap(18, spacing_scale, 14)

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=MARGIN_X, y=title_y, width=width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))
        title_y += notes_height + _gap(18, spacing_scale, 14)

    panel_width = 500
    left_x = 80
    right_x = 700
    panel_y = max(title_y + 8, 196)

    def panel(side: str, x: int, heading: str | None, bullets: list[str]) -> LayoutElement:
        heading_font = 16
        bullet_font = 18
        child_y = 0
        children: list[LayoutElement] = []
        if heading:
            heading_height, _, _ = _text_height(heading, panel_width - 40, heading_font, min_height=28)
            children.append(_text_element(element_id=f"{slide.id}_{side}_heading", region=f"{side}.heading", x=0, y=0, width=panel_width - 40, text=heading, font_size=heading_font, align=Alignment.START, min_height=heading_height, note=f"{side} heading"))
            child_y += heading_height + _gap(14, spacing_scale, 10)
        bullet_list = _bullet_list_element(element_id=f"{slide.id}_{side}_bullets", region=f"{side}.body", x=0, y=child_y, width=panel_width - 40, bullets=bullets, font_size=bullet_font, max_height=250, icon_context=f"{slide.title or ''} {heading or ''}")
        children.append(bullet_list)
        height = max(320, sum(child.height + _gap(14, spacing_scale, 10) for child in children))
        return _panel_element(element_id=f"{slide.id}_{side}_panel", region=side, x=x, y=panel_y, width=panel_width, height=height, children=children, note=f"{side} comparison panel")

    elements.append(panel("left", left_x, slide.left_title or "Option A", slide.left_bullets or []))
    elements.append(panel("right", right_x, slide.right_title or "Option B", slide.right_bullets or []))
    return elements


def _layout_timeline_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="timeline title"))
        title_y += title_height + _gap(24, spacing_scale, 18)

    rows: list[LayoutElement] = []
    y = title_y
    label_width = 160
    row_width = width
    for index, step in enumerate(slide.timeline or []):
        row_children: list[LayoutElement] = []
        label_font = 16
        detail_font = 16
        step_label = _item_field(step, "label", "")
        step_detail = _item_field(step, "detail")
        label_h, _, _ = _text_height(step_label, label_width, label_font, min_height=24)
        detail_w = row_width - label_width - 28
        detail_h, _, _ = _text_height(step_detail or "", detail_w, detail_font, min_height=24)
        row_h = max(label_h, detail_h) + _gap(28, spacing_scale, 20)
        row_children.append(_text_element(element_id=f"{slide.id}_step_{index + 1}_label", region=f"timeline.{index + 1}.label", x=0, y=0, width=label_width, text=step_label, font_size=label_font, align=Alignment.START, min_height=label_h, note="timeline label"))
        if step_detail:
            row_children.append(_text_element(element_id=f"{slide.id}_step_{index + 1}_detail", region=f"timeline.{index + 1}.detail", x=label_width + _gap(28, spacing_scale, 18), y=0, width=detail_w, text=step_detail, font_size=detail_font, align=Alignment.START, min_height=detail_h, note="timeline detail"))
        rows.append(_panel_element(element_id=f"{slide.id}_step_{index + 1}", region="timeline", x=MARGIN_X, y=y, width=row_width, height=row_h, children=row_children, note="timeline step"))
        y += row_h + _gap(16, spacing_scale, 12)

    elements.extend(rows)
    return elements


def _layout_statistics_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="statistics title"))
        title_y += title_height + _gap(24, spacing_scale, 18)

    cards = slide.statistics or []
    columns = 3 if len(cards) > 2 else max(1, len(cards))
    grid_gap = _gap(GRID_GAP, spacing_scale, 16)
    card_width = int((width - (grid_gap * (columns - 1))) / columns)
    card_height = 180
    x0 = MARGIN_X
    y0 = max(title_y, 192)
    for index, stat in enumerate(cards):
        col = index % columns
        row = index // columns
        x = x0 + (col * (card_width + grid_gap))
        y = y0 + (row * (card_height + grid_gap))
        value_font = 34
        label_font = 15
        detail_font = 14
        child_elements: list[LayoutElement] = []
        stat_value = _item_field(stat, "value", "")
        stat_label = _item_field(stat, "label", "")
        stat_detail = _item_field(stat, "detail")
        value_h, _, _ = _text_height(stat_value, card_width - 40, value_font, min_height=44)
        label_h, _, _ = _text_height(stat_label, card_width - 40, label_font, min_height=24)
        child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_value", region=f"stat.{index + 1}.value", x=0, y=0, width=card_width - 40, text=stat_value, font_size=value_font, align=Alignment.CENTER, min_height=value_h, note="stat value"))
        label_gap = _gap(10, spacing_scale, 8)
        child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_label", region=f"stat.{index + 1}.label", x=0, y=value_h + label_gap, width=card_width - 40, text=stat_label, font_size=label_font, align=Alignment.CENTER, min_height=label_h, note="stat label"))
        if stat_detail:
            detail_y = value_h + label_h + _gap(20, spacing_scale, 14)
            detail_h, _, _ = _text_height(stat_detail, card_width - 40, detail_font, min_height=22)
            child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_detail", region=f"stat.{index + 1}.detail", x=0, y=detail_y, width=card_width - 40, text=stat_detail, font_size=detail_font, align=Alignment.CENTER, min_height=detail_h, note="stat detail"))
        elements.append(_panel_element(element_id=f"{slide.id}_stat_{index + 1}", region="statistics", x=x, y=y, width=card_width, height=card_height, children=child_elements, note="stat card"))
    return elements


def _layout_quote_slide(slide, spacing_scale: float) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    quote_width = 960
    quote_x = (CANVAS_WIDTH - quote_width) // 2
    quote_y = 220
    quote_font = 42
    attr_font = 20
    notes_font = 16

    if slide.quote:
        quote_h, _, _ = _text_height(slide.quote, quote_width, quote_font, min_height=100)
        elements.append(_text_element(element_id=f"{slide.id}_quote", region="quote", x=quote_x, y=quote_y, width=quote_width, text=slide.quote, font_size=quote_font, align=Alignment.CENTER, min_height=quote_h, note="quote"))
        quote_y += quote_h + _gap(18, spacing_scale, 14)

    if slide.attribution:
        attr_width = min(700, quote_width)
        attr_x = (CANVAS_WIDTH - attr_width) // 2
        attr_h, _, _ = _text_height(slide.attribution, attr_width, attr_font, min_height=24)
        elements.append(_text_element(element_id=f"{slide.id}_attribution", region="attribution", x=attr_x, y=quote_y, width=attr_width, text=slide.attribution, font_size=attr_font, align=Alignment.CENTER, min_height=attr_h, note="attribution"))
        quote_y += attr_h + _gap(16, spacing_scale, 12)

    if slide.notes:
        notes_width = 760
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_h, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=22)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=notes_x, y=max(quote_y, 540), width=notes_width, text=slide.notes, font_size=notes_font, align=Alignment.CENTER, min_height=notes_h, note="notes"))
    return elements

LAYOUT_RENDERERS = {
    "title.centered": _layout_title_slide,
    "content.bullets": _layout_bullets_slide,
    "content.image_split": _layout_image_bullets_slide,
    "hero.focus": _layout_hero_image_slide,
    "comparison.split": _layout_comparison_slide,
    "timeline.stacked": _layout_timeline_slide,
    "statistics.grid": _layout_statistics_slide,
    "quote.centered": _layout_quote_slide,
}


def _layout_slide(slide, debug_mode: bool, spacing_scale: float) -> LayoutedSlide:
    layout_name = slide.layout_name
    elements = LAYOUT_RENDERERS.get(layout_name, _layout_bullets_slide)(slide, spacing_scale)

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


def build_layouted_presentation(document: PresentationDocument, *, debug_mode: bool = False, spacing_scale: float = 1.0) -> LayoutedPresentationDocument:
    return LayoutedPresentationDocument(
        title=document.title,
        version=document.version,
        metadata=document.metadata,
        slides=[_layout_slide(slide, debug_mode, spacing_scale) for slide in document.slides],
    )
