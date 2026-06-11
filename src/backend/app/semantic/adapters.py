# Роля на модула: Адаптационната граница между API/domain моделите и renderer-neutral semantic contracts. Работи като преводач между два слоя с различен речник.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

from app.schemas.presentation import Presentation, Slide
from app.semantic.catalog import build_renderer_context as build_catalog_renderer_context
from app.semantic.catalog import get_layout_spec
from app.semantic.contracts import (
    LayoutSpec,
    MediaKind,
    PresentationDocument,
    RendererContext,
    RendererTarget,
    SlideMediaRef,
    ThemeDefinition,
    ThemeFonts,
    ThemeTokens,
)
from app.semantic.contracts import (
    Slide as SemanticSlide,
)
from app.semantic.layout_selector import LayoutSelector
from app.services.theme_registry import get_theme_tokens


def _font_family_name(value: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `font_family_name` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # `first_token` пази резултата от `value.split(',', 1)[0].strip().strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    first_token = value.split(",", 1)[0].strip().strip("'")
    return first_token or value


def _short_alt_text(slide: Slide) -> str | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `short_alt_text` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `slide` (Slide); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `cleaned[:217].rstrip`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # Това условие е decision point: `slide.title`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`slide.title[:120]`) и прескачаме ненужната останала работа.
    if slide.title:
        return slide.title[:120]
    # Това условие е decision point: `not slide.image_prompt`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not slide.image_prompt:
        return None

    # `cleaned` пази резултата от `slide.image_prompt.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    cleaned = slide.image_prompt.strip()
    # Това условие е decision point: `len(cleaned) <= 220`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`cleaned`) и прескачаме ненужната останала работа.
    if len(cleaned) <= 220:
        return cleaned

    return f"{cleaned[:217].rstrip()}..."


def _slide_media(slide: Slide) -> list[SlideMediaRef]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `slide_media` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `slide` (Slide); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `SlideMediaRef`, `_short_alt_text`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[SlideMediaRef]`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    media: list[SlideMediaRef] = []
    # Това условие е decision point: `slide.image_prompt`.
    # При вярно условие се активира `getattr`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if slide.image_prompt:
        image_class = getattr(slide.image_class, "value", slide.image_class)
        media.append(
            SlideMediaRef(
                kind=MediaKind.ICON if image_class == "icon" else MediaKind.IMAGE,
                label=slide.title or slide.id,
                prompt=slide.image_prompt,
                alt=_short_alt_text(slide),
                source=getattr(slide.resolved_image, "source", None),
                source_url=getattr(slide.resolved_image, "source_url", None),
                local_path=getattr(slide.resolved_image, "local_path", None),
                public_url=getattr(slide.resolved_image, "public_url", None),
                metadata={
                    "resolved": slide.resolved_image is not None,
                    "license_name": getattr(slide.resolved_image, "license_name", None),
                    "image_class": image_class,
                    "width": getattr(slide.resolved_image, "width", None),
                    "height": getattr(slide.resolved_image, "height", None),
                },
            )
        )
    return media


def presentation_to_document(presentation: Presentation) -> PresentationDocument:
    # Роля в pipeline-а: Превежда външния Presentation модел към renderer-neutral PresentationDocument, който semantic pipeline-ът използва.
    # Входът идва през `presentation` (Presentation); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `LayoutSelector`, `selector.select_for_presentation`, `PresentationDocument`, `SemanticSlide`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `PresentationDocument`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # `selector` пази резултата от `LayoutSelector`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    selector = LayoutSelector()
    # `recommendations` пази резултата от `selector.select_for_presentation`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    recommendations = selector.select_for_presentation(presentation)
    # `recommended_by_slide_id` е стабилен идентификатор, чрез който този обект може да се свърже с останалите pipeline данни.
    # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
    recommended_by_slide_id = {item.slide_id: item for item in recommendations}
    semantic_slides: list[SemanticSlide] = []
    # Обхождаме `enumerate(presentation.slides, start=1)` като `(index, slide)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for index, slide in enumerate(presentation.slides, start=1):
        # `recommendation` пази резултата от `recommended_by_slide_id.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        recommendation = recommended_by_slide_id.get(slide.id)
        layout_name = recommendation.selected_layout_id if recommendation else "content.bullets"
        semantic_slides.append(
            SemanticSlide(
                id=slide.id,
                order=index,
                layout_name=layout_name,
                title=slide.title,
                subtitle=slide.subtitle,
                bullets=list(slide.bullets),
                image_prompt=slide.image_prompt,
                visual_mood=slide.visual_mood,
                icon_intent=slide.icon_intent,
                notes=slide.notes,
                left_title=slide.left_title,
                right_title=slide.right_title,
                left_bullets=list(slide.left_bullets),
                right_bullets=list(slide.right_bullets),
                timeline=[step.model_dump(mode="json") for step in slide.timeline],
                statistics=[item.model_dump(mode="json") for item in slide.statistics],
                quote=slide.quote,
                attribution=slide.attribution,
                media=_slide_media(slide),
            )
        )
    return PresentationDocument(
        title=presentation.title,
        slides=semantic_slides,
        metadata={
            "layout_recommendations": [
                {
                    "slide_id": item.slide_id,
                    "selected_layout_id": item.selected_layout_id,
                    "score": item.score,
                    "reason": item.reason,
                    "alternatives": item.alternatives,
                }
                for item in recommendations
            ]
        },
    )


def build_theme_definition(theme_name: str) -> ThemeDefinition:
    # Роля в pipeline-а: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
    # Входът идва през `theme_name` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_theme_tokens`, `ThemeDefinition`, `ThemeTokens`, `ThemeFonts`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ThemeDefinition`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # `tokens` е theme настройките, които държат визуалното решение последователно между layouts и exporters.
    tokens = get_theme_tokens(theme_name)

    return ThemeDefinition(
        id=tokens.name,
        name=tokens.display_name,
        description=tokens.description,
        tags=list(tokens.visual_tags),
        tokens=ThemeTokens(
            background=tokens.background,
            background_alt=tokens.background_alt,
            surface=tokens.surface,
            surface_alt=tokens.background_alt,
            text_primary=tokens.text_color,
            text_secondary=tokens.muted_text_color,
            accent_primary=tokens.accent_color,
            accent_secondary=tokens.accent_soft_color,
            border=tokens.border_color,
            focus_ring=tokens.accent_color,
            fonts=ThemeFonts(
                heading=_font_family_name(tokens.heading_font_family),
                body=_font_family_name(tokens.body_font_family),
                mono="ui-monospace",
                fallbacks=["system-ui", "sans-serif"],
            ),
            spacing_scale=tokens.spacing_scale,
            typography_scale=tokens.typography_scale,
            radius_scale=1.0,
            shadow_scale=1.0,
            component_styles={
                "background": {
                    "accent_position": tokens.accent_position,
                    "layout_style": tokens.layout_style,
                },
                "panel": {
                    "style": tokens.panel_style,
                    "radius": tokens.panel_radius,
                    "padding": tokens.panel_padding,
                },
                "bullet": {
                    "style": tokens.bullet_style,
                },
                "image": {
                    "style": tokens.image_style,
                    "radius": tokens.image_radius,
                    "frame_inset": tokens.image_frame_inset,
                    "fit": tokens.image_fit,
                },
            },
        ),
    )


def build_layout_specs(document: PresentationDocument) -> list[LayoutSpec]:
    # Роля в pipeline-а: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
    # Входът идва през `document` (PresentationDocument); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_layout_spec`, `KeyError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[LayoutSpec]`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    specs: list[LayoutSpec] = []
    # Обхождаме `document.slides` като `slide`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for slide in document.slides:
        # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
        # `try/except` превръща техническите грешки (KeyError) в предвидимо поведение за горния слой.
        try:
            specs.append(get_layout_spec(slide.layout_name))
        except KeyError as exc:
            raise KeyError(f"Unknown layout '{slide.layout_name}' for slide '{slide.id}'.") from exc
    return specs


def build_renderer_context(target: RendererTarget | str) -> RendererContext:
    # Роля в pipeline-а: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
    # Входът идва през `target` (RendererTarget | str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `build_catalog_renderer_context`, `RendererTarget`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `RendererContext`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    return build_catalog_renderer_context(RendererTarget(target))
