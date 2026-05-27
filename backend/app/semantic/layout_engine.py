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


CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
MARGIN_X = 80
MARGIN_Y = 72
GRID_GAP = 24
TEXT_LINE_HEIGHT = 1.18


def _available_width() -> int:
    return CANVAS_WIDTH - (MARGIN_X * 2)


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


def _icon_key(text: str, index: int = 0) -> str:
    value = text.lower()
    if any(term in value for term in ("growth", "increase", "scale", "trend", "revenue", "market")):
        return "chart"
    if any(term in value for term in ("secure", "risk", "trust", "protect", "safe", "privacy")):
        return "shield"
    if any(term in value for term in ("fast", "speed", "automate", "launch", "instant", "quick")):
        return "bolt"
    if any(term in value for term in ("target", "goal", "focus", "priority", "audience")):
        return "target"
    if any(term in value for term in ("idea", "insight", "strategy", "learn", "discover")):
        return "idea"
    return ("target", "chart", "bolt", "idea")[index % 4]


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
) -> LayoutElement:
    child_y = y
    children: list[LayoutElement] = []
    for index, bullet in enumerate(bullets):
        item_height, _, _ = _text_height(bullet, width - 40, font_size)
        item_height = max(item_height + 16, 42)
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
                content={"bullet": True, "index": index, "icon": _icon_key(bullet, index)},
                debug=_make_debug(bullet, width - 40, font_size, 0, 0, "bullet item"),
            )
        )
        child_y += item_height + 16

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
            estimated_lines=sum(max(1, _estimate_lines(item, width - 40, font_size)) for item in bullets),
            estimated_chars_per_line=_estimate_chars_per_line(width - 40, font_size),
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
        content={"panel": True},
        children=children,
        debug=LayoutDebugInfo(
            content_length=sum(child.debug.content_length if child.debug else 0 for child in children),
            estimated_lines=sum(child.debug.estimated_lines if child.debug else 0 for child in children),
            estimated_chars_per_line=0,
            spacing_before=0,
            spacing_after=0,
            note=note,
        ),
    )


def _layout_title_slide(slide) -> list[LayoutElement]:
    width = _available_width()
    title_font = 66
    subtitle_font = 26
    notes_font = 18
    y = 138
    elements: list[LayoutElement] = []

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=92)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=y, width=width, text=slide.title, font_size=title_font, align=Alignment.CENTER, min_height=title_height, spacing_after=24, note="title"))
        y += title_height + 24

    if slide.subtitle:
        subtitle_width = min(960, width)
        subtitle_x = (CANVAS_WIDTH - subtitle_width) // 2
        subtitle_height, _, _ = _text_height(slide.subtitle, subtitle_width, subtitle_font, min_height=40)
        elements.append(_text_element(element_id=f"{slide.id}_subtitle", region="subtitle", x=subtitle_x, y=y, width=subtitle_width, text=slide.subtitle, font_size=subtitle_font, align=Alignment.CENTER, min_height=subtitle_height, spacing_after=18, note="subtitle"))
        y += subtitle_height + 18

    if slide.notes:
        notes_width = min(840, width)
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_height, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=30)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=notes_x, y=max(y, 520), width=notes_width, text=slide.notes, font_size=notes_font, align=Alignment.CENTER, min_height=notes_height, note="notes"))

    return elements


def _layout_bullets_slide(slide) -> list[LayoutElement]:
    width = _available_width()
    title_font = 42
    bullet_font = 22
    notes_font = 16
    elements: list[LayoutElement] = []
    y = 86

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=58)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, spacing_after=28, note="title"))
        y += title_height + 28

    bullets = slide.bullets or []
    bullet_list = _bullet_list_element(element_id=f"{slide.id}_bullets", region="body", x=MARGIN_X, y=y, width=width, bullets=bullets, font_size=bullet_font)
    elements.append(bullet_list)
    y += bullet_list.height + 22

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=MARGIN_X, y=max(y, 588), width=width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))

    return elements


def _layout_image_bullets_slide(slide) -> list[LayoutElement]:
    if getattr(slide, "image_class", None) == "icon":
        return _layout_icon_cards_slide(slide)

    elements: list[LayoutElement] = []
    left_x = 88
    left_width = 560
    right_x = 708
    right_width = 484
    title_font = 38
    bullet_font = 20
    notes_font = 16
    title_y = 90

    left_children: list[LayoutElement] = []
    if slide.title:
        title_height, _, _ = _text_height(slide.title, left_width, title_font, min_height=52)
        left_children.append(_text_element(element_id=f"{slide.id}_title", region="title", x=0, y=0, width=left_width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, spacing_after=18, note="title"))
        offset_y = title_height + 18
    else:
        offset_y = 0

    bullet_list = _bullet_list_element(element_id=f"{slide.id}_bullets", region="body", x=0, y=offset_y, width=left_width, bullets=slide.bullets or [], font_size=bullet_font)
    left_children.append(bullet_list)
    offset_y += bullet_list.height + 14

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, left_width, notes_font, min_height=26)
        left_children.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=0, y=max(offset_y, 450), width=left_width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))

    left_height = max(520, sum(child.height + 18 for child in left_children))
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
            width=right_width,
            height=image_height,
            align=Alignment.CENTER,
            wrap=False,
            content={
                "image": True,
                "src": (media or {}).get("public_url") or (media or {}).get("local_path"),
                "local_path": (media or {}).get("local_path"),
                "alt": (media or {}).get("alt") or slide.image_prompt or slide.title or slide.id,
                "prompt": (media or {}).get("prompt") or slide.image_prompt,
            },
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


def _layout_icon_cards_slide(slide) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 38
    bullet_font = 19
    y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, spacing_after=26, note="icon card title"))
        y += title_height + 28

    bullets = slide.bullets or []
    columns = 2 if len(bullets) <= 4 else 3
    card_width = int((width - (GRID_GAP * (columns - 1))) / columns)
    card_height = 138
    for index, bullet in enumerate(bullets):
        col = index % columns
        row = index // columns
        x = MARGIN_X + col * (card_width + GRID_GAP)
        card_y = y + row * (card_height + GRID_GAP)
        text_width = card_width - 112
        text_height, _, _ = _text_height(bullet, text_width, bullet_font, min_height=54)
        children = [
            LayoutElement(
                id=f"{slide.id}_icon_{index + 1}",
                kind=LayoutElementKind.TEXT,
                region=f"card.{index + 1}.icon",
                x=0,
                y=0,
                width=64,
                height=64,
                align=Alignment.CENTER,
                wrap=False,
                content={"icon": _icon_key(bullet, index), "decorative_icon": True},
                debug=_make_debug("", 64, 1, note="card icon"),
            ),
            _text_element(element_id=f"{slide.id}_card_{index + 1}_text", region=f"card.{index + 1}.text", x=84, y=4, width=text_width, text=bullet, font_size=bullet_font, align=Alignment.START, min_height=text_height, note="card text"),
        ]
        elements.append(_panel_element(element_id=f"{slide.id}_card_{index + 1}", region=f"card.{index + 1}", x=x, y=card_y, width=card_width, height=card_height, children=children, note="icon card"))

    return elements


def _layout_hero_image_slide(slide) -> list[LayoutElement]:
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
        title_offset = title_height + 20
    if slide.subtitle:
        subtitle_height, _, _ = _text_height(slide.subtitle, left_width, subtitle_font, min_height=40)
        left_children.append(_text_element(element_id=f"{slide.id}_subtitle", region="subtitle", x=0, y=title_offset, width=left_width, text=slide.subtitle, font_size=subtitle_font, align=Alignment.START, min_height=subtitle_height, note="hero subtitle"))
        y += subtitle_height + 16
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
            width=right_width,
            height=440,
            align=Alignment.CENTER,
            wrap=False,
            content={
                "image": True,
                "src": (media or {}).get("public_url") or (media or {}).get("local_path"),
                "local_path": (media or {}).get("local_path"),
                "alt": (media or {}).get("alt") or slide.image_prompt or slide.title or slide.id,
                "prompt": (media or {}).get("prompt") or slide.image_prompt,
            },
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


def _layout_comparison_slide(slide) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    notes_font = 16
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="comparison title"))
        title_y += title_height + 18

    if slide.notes:
        notes_height, _, _ = _text_height(slide.notes, width, notes_font, min_height=26)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=MARGIN_X, y=title_y, width=width, text=slide.notes, font_size=notes_font, align=Alignment.START, min_height=notes_height, note="notes"))
        title_y += notes_height + 18

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
            child_y += heading_height + 14
        bullet_list = _bullet_list_element(element_id=f"{slide.id}_{side}_bullets", region=f"{side}.body", x=0, y=child_y, width=panel_width - 40, bullets=bullets, font_size=bullet_font)
        children.append(bullet_list)
        height = max(320, sum(child.height + 14 for child in children))
        return _panel_element(element_id=f"{slide.id}_{side}_panel", region=side, x=x, y=panel_y, width=panel_width, height=height, children=children, note=f"{side} comparison panel")

    elements.append(panel("left", left_x, slide.left_title or "Option A", slide.left_bullets or []))
    elements.append(panel("right", right_x, slide.right_title or "Option B", slide.right_bullets or []))
    return elements


def _layout_timeline_slide(slide) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="timeline title"))
        title_y += title_height + 24

    rows: list[LayoutElement] = []
    y = title_y
    label_width = 160
    row_width = width
    for index, step in enumerate(slide.timeline or []):
        row_children: list[LayoutElement] = []
        label_font = 16
        detail_font = 16
        label_h, _, _ = _text_height(step.label, label_width, label_font, min_height=24)
        detail_w = row_width - label_width - 28
        detail_h, _, _ = _text_height(step.detail or "", detail_w, detail_font, min_height=24)
        row_h = max(label_h, detail_h) + 28
        row_children.append(_text_element(element_id=f"{slide.id}_step_{index + 1}_label", region=f"timeline.{index + 1}.label", x=0, y=0, width=label_width, text=step.label, font_size=label_font, align=Alignment.START, min_height=label_h, note="timeline label"))
        if step.detail:
            row_children.append(_text_element(element_id=f"{slide.id}_step_{index + 1}_detail", region=f"timeline.{index + 1}.detail", x=label_width + 28, y=0, width=detail_w, text=step.detail, font_size=detail_font, align=Alignment.START, min_height=detail_h, note="timeline detail"))
        rows.append(_panel_element(element_id=f"{slide.id}_step_{index + 1}", region="timeline", x=MARGIN_X, y=y, width=row_width, height=row_h, children=row_children, note="timeline step"))
        y += row_h + 16

    elements.extend(rows)
    return elements


def _layout_statistics_slide(slide) -> list[LayoutElement]:
    elements: list[LayoutElement] = []
    width = _available_width()
    title_font = 36
    title_y = 84

    if slide.title:
        title_height, _, _ = _text_height(slide.title, width, title_font, min_height=54)
        elements.append(_text_element(element_id=f"{slide.id}_title", region="title", x=MARGIN_X, y=title_y, width=width, text=slide.title, font_size=title_font, align=Alignment.START, min_height=title_height, note="statistics title"))
        title_y += title_height + 24

    cards = slide.statistics or []
    columns = 3 if len(cards) > 2 else max(1, len(cards))
    card_width = int((width - (GRID_GAP * (columns - 1))) / columns)
    card_height = 180
    x0 = MARGIN_X
    y0 = max(title_y, 192)
    for index, stat in enumerate(cards):
        col = index % columns
        row = index // columns
        x = x0 + (col * (card_width + GRID_GAP))
        y = y0 + (row * (card_height + GRID_GAP))
        value_font = 34
        label_font = 15
        detail_font = 14
        child_elements: list[LayoutElement] = []
        value_h, _, _ = _text_height(stat.value, card_width - 40, value_font, min_height=44)
        label_h, _, _ = _text_height(stat.label, card_width - 40, label_font, min_height=24)
        child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_value", region=f"stat.{index + 1}.value", x=0, y=0, width=card_width - 40, text=stat.value, font_size=value_font, align=Alignment.CENTER, min_height=value_h, note="stat value"))
        child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_label", region=f"stat.{index + 1}.label", x=0, y=value_h + 10, width=card_width - 40, text=stat.label, font_size=label_font, align=Alignment.CENTER, min_height=label_h, note="stat label"))
        if stat.detail:
            detail_y = value_h + label_h + 20
            detail_h, _, _ = _text_height(stat.detail, card_width - 40, detail_font, min_height=22)
            child_elements.append(_text_element(element_id=f"{slide.id}_stat_{index + 1}_detail", region=f"stat.{index + 1}.detail", x=0, y=detail_y, width=card_width - 40, text=stat.detail, font_size=detail_font, align=Alignment.CENTER, min_height=detail_h, note="stat detail"))
        elements.append(_panel_element(element_id=f"{slide.id}_stat_{index + 1}", region="statistics", x=x, y=y, width=card_width, height=card_height, children=child_elements, note="stat card"))
    return elements


def _layout_quote_slide(slide) -> list[LayoutElement]:
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
        quote_y += quote_h + 18

    if slide.attribution:
        attr_width = min(700, quote_width)
        attr_x = (CANVAS_WIDTH - attr_width) // 2
        attr_h, _, _ = _text_height(slide.attribution, attr_width, attr_font, min_height=24)
        elements.append(_text_element(element_id=f"{slide.id}_attribution", region="attribution", x=attr_x, y=quote_y, width=attr_width, text=slide.attribution, font_size=attr_font, align=Alignment.CENTER, min_height=attr_h, note="attribution"))
        quote_y += attr_h + 16

    if slide.notes:
        notes_width = 760
        notes_x = (CANVAS_WIDTH - notes_width) // 2
        notes_h, _, _ = _text_height(slide.notes, notes_width, notes_font, min_height=22)
        elements.append(_text_element(element_id=f"{slide.id}_notes", region="notes", x=notes_x, y=max(quote_y, 540), width=notes_width, text=slide.notes, font_size=notes_font, align=Alignment.CENTER, min_height=notes_h, note="notes"))
    return elements


def _layout_slide(slide, debug_mode: bool) -> LayoutedSlide:
    layout_name = slide.layout_name
    if layout_name == "title.centered":
        elements = _layout_title_slide(slide)
    elif layout_name == "content.bullets":
        elements = _layout_bullets_slide(slide)
    elif layout_name == "content.image_split":
        elements = _layout_image_bullets_slide(slide)
    elif layout_name == "hero.focus":
        elements = _layout_hero_image_slide(slide)
    elif layout_name == "comparison.split":
        elements = _layout_comparison_slide(slide)
    elif layout_name == "timeline.stacked":
        elements = _layout_timeline_slide(slide)
    elif layout_name == "statistics.grid":
        elements = _layout_statistics_slide(slide)
    elif layout_name == "quote.centered":
        elements = _layout_quote_slide(slide)
    else:
        elements = _layout_bullets_slide(slide)

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


def build_layouted_presentation(document: PresentationDocument, *, debug_mode: bool = False) -> LayoutedPresentationDocument:
    return LayoutedPresentationDocument(
        title=document.title,
        version=document.version,
        metadata=document.metadata,
        slides=[_layout_slide(slide, debug_mode) for slide in document.slides],
    )
