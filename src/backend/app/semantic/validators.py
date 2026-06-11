# Роля на модула: Последна semantic защита преди layout/rendering. Работи като контролно-пропускателен пункт и не допуска договор, който renderer-ът не разбира.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

import re

from app.semantic.catalog import LAYOUT_SPEC_REGISTRY, RENDERER_CAPABILITY_MATRIX
from app.semantic.contracts import LayoutSpec, PresentationDocument, RendererContext, ThemeDefinition


def validate_presentation_document(document: PresentationDocument) -> PresentationDocument:
    # Pydantic validation already enforces structure; this is a narrow semantic guard.
    # Роля в pipeline-а: Проверява дали всеки слайд сочи към layout, който реално съществува в каталога, преди да започне геометричното подреждане.
    # Входът идва през `document` (PresentationDocument); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ValueError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `PresentationDocument`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # Обхождаме `document.slides` като `slide`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for slide in document.slides:
        # Това условие е decision point: `slide.layout_name not in LAYOUT_SPEC_REGISTRY`.
        # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if slide.layout_name not in LAYOUT_SPEC_REGISTRY:
            raise ValueError(f"Unknown layout '{slide.layout_name}' on slide '{slide.id}'.")
    return document


def validate_theme_definition(theme: ThemeDefinition) -> ThemeDefinition:
    # Роля в pipeline-а: Пази semantic темата renderer-neutral, като забранява CSS и layout-specific стойности да изтекат в общия договор.
    # Входът идва през `theme` (ThemeDefinition); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ValueError`, `re.search`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ThemeDefinition`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # Това условие е decision point: `not theme.tokens.component_styles`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`theme`) и прескачаме ненужната останала работа.
    if not theme.tokens.component_styles:
        return theme
    # Обхождаме `theme.tokens.component_styles.items()` като `(component_name, styles)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for component_name, styles in theme.tokens.component_styles.items():
        # Това условие е decision point: `not component_name.strip()`.
        # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if not component_name.strip():
            raise ValueError("Theme component styles need a component name.")
        # Обхождаме `styles.items()` като `(key, value)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for key, value in styles.items():
            # Това условие е decision point: `key.lower() in {'layout', 'region', 'width', 'height', 'position'}`.
            # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if key.lower() in {"layout", "region", "width", "height", "position"}:
                raise ValueError("Theme component styles must not contain layout concerns.")
            # Това условие е decision point: `isinstance(value, str)`.
            # При вярно условие се активира `value.lower`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if isinstance(value, str):
                # `lowered` пази резултата от `value.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                lowered = value.lower()
                # `has_css_unit` е boolean решение, което управлява кой branch от pipeline-а ще се изпълни.
                has_css_unit = re.search(r"(^|[\s:(,])[-+]?\d*\.?\d+(px|rem|em)\b", lowered)
                # Това условие е decision point: `has_css_unit or any((marker in lowered for marker in ('rgba(', 'linear-gradient', 'font:'...`.
                # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
                if has_css_unit or any(
                    marker in lowered for marker in ("rgba(", "linear-gradient", "font:", "margin:", "padding:")
                ):
                    raise ValueError("Theme component styles must stay abstract and renderer-neutral.")
    return theme


def validate_layout_spec(layout: LayoutSpec) -> LayoutSpec:
    # Роля в pipeline-а: пази границата на pipeline-а, като отказва данни, които следващият слой не може безопасно да обработи.
    # Входът идва през `layout` (LayoutSpec); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ValueError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `LayoutSpec`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # Това условие е decision point: `layout.name not in LAYOUT_SPEC_REGISTRY`.
    # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if layout.name not in LAYOUT_SPEC_REGISTRY:
        raise ValueError(f"Unknown layout spec '{layout.name}'.")
    return layout


def validate_renderer_context(context: RendererContext) -> RendererContext:
    # Роля в pipeline-а: пази границата на pipeline-а, като отказва данни, които следващият слой не може безопасно да обработи.
    # Входът идва през `context` (RendererContext); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ValueError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `RendererContext`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # `supported` пази резултата от `RENDERER_CAPABILITY_MATRIX.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    supported = RENDERER_CAPABILITY_MATRIX.get(context.target)
    # Това условие е decision point: `supported is None`.
    # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if supported is None:
        raise ValueError(f"Unsupported renderer target '{context.target}'.")
    # Това условие е decision point: `context.capabilities != supported`.
    # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if context.capabilities != supported:
        raise ValueError(f"Renderer capabilities do not match matrix for target '{context.target}'.")
    return context
