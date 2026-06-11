# Роля на модула: Оценява съдържанието и избира layout преди геометричното подреждане. Работи като жури, което оценява всички кандидати по еднакви критерии.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.schemas.presentation import Presentation, Slide, SlideType
from app.services.theme_registry import get_theme_tokens


@dataclass(frozen=True)
class SlideAnalysis:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    slide_id: str
    slide_type: str
    title: str
    subtitle: str
    bullet_count: int
    paragraph_length: int
    image_count: int
    chart_count: int
    table_count: int
    timeline_items: int
    comparison_items: int
    stats_count: int
    max_stat_value_length: int
    avg_stat_value_length: int
    quote_length: int
    density: str


@dataclass(frozen=True)
class LayoutMetadata:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    layout_id: str
    supported_slide_types: tuple[str, ...]
    supported_content_types: tuple[str, ...]
    min_bullet_count: int
    max_bullet_count: int
    min_text_length: int
    max_text_length: int
    supports_image: bool
    supports_chart: bool
    supports_table: bool
    supports_timeline: bool
    supports_comparison: bool
    supports_stats: bool
    supports_quote: bool
    density: str
    compatible_theme_styles: tuple[str, ...]


@dataclass(frozen=True)
class LayoutRecommendation:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    slide_id: str
    selected_layout_id: str
    score: float
    reason: str
    alternatives: list[dict[str, Any]]


# `LAYOUT_METADATA_REGISTRY` пази резултата от `LayoutMetadata`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
LAYOUT_METADATA_REGISTRY: dict[str, LayoutMetadata] = {
    "title.centered": LayoutMetadata(
        layout_id="title.centered",
        supported_slide_types=(SlideType.TITLE_SLIDE.value, SlideType.QUOTE.value),
        supported_content_types=("title", "subtitle", "notes", "quote"),
        min_bullet_count=0,
        max_bullet_count=1,
        min_text_length=0,
        max_text_length=260,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=True,
        density="low",
        compatible_theme_styles=("minimal", "academic", "corporate", "luxury", "playful"),
    ),
    "title.left_feature": LayoutMetadata(
        layout_id="title.left_feature",
        supported_slide_types=(SlideType.TITLE_SLIDE.value,),
        supported_content_types=("title", "subtitle", "notes"),
        min_bullet_count=0,
        max_bullet_count=1,
        min_text_length=10,
        max_text_length=220,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="low",
        compatible_theme_styles=("corporate", "technical", "minimal", "luxury"),
    ),
    "content.bullets": LayoutMetadata(
        layout_id="content.bullets",
        supported_slide_types=(SlideType.TITLE_BULLETS.value,),
        supported_content_types=("title", "bullets", "notes"),
        min_bullet_count=2,
        max_bullet_count=7,
        min_text_length=20,
        max_text_length=420,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="medium",
        compatible_theme_styles=("corporate", "minimal", "academic", "technical", "playful"),
    ),
    "content.bullets_dense": LayoutMetadata(
        layout_id="content.bullets_dense",
        supported_slide_types=(SlideType.TITLE_BULLETS.value,),
        supported_content_types=("title", "bullets", "notes"),
        min_bullet_count=4,
        max_bullet_count=10,
        min_text_length=80,
        max_text_length=520,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="high",
        compatible_theme_styles=("corporate", "academic", "technical", "minimal"),
    ),
    "content.image_split": LayoutMetadata(
        layout_id="content.image_split",
        supported_slide_types=(SlideType.TITLE_BULLETS_IMAGE.value,),
        supported_content_types=("title", "bullets", "image", "notes"),
        min_bullet_count=2,
        max_bullet_count=6,
        min_text_length=20,
        max_text_length=360,
        supports_image=True,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="medium",
        compatible_theme_styles=("corporate", "technical", "gradient", "academic", "minimal"),
    ),
    "content.image_focus_split": LayoutMetadata(
        layout_id="content.image_focus_split",
        supported_slide_types=(SlideType.TITLE_BULLETS_IMAGE.value, SlideType.HERO_IMAGE.value),
        supported_content_types=("title", "bullets", "image", "notes"),
        min_bullet_count=1,
        max_bullet_count=4,
        min_text_length=10,
        max_text_length=260,
        supports_image=True,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="low",
        compatible_theme_styles=("gradient", "luxury", "technical", "playful", "minimal"),
    ),
    "hero.focus": LayoutMetadata(
        layout_id="hero.focus",
        supported_slide_types=(SlideType.HERO_IMAGE.value, SlideType.TITLE_BULLETS_IMAGE.value),
        supported_content_types=("title", "subtitle", "image", "notes"),
        min_bullet_count=0,
        max_bullet_count=3,
        min_text_length=0,
        max_text_length=220,
        supports_image=True,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="low",
        compatible_theme_styles=("gradient", "playful", "technical", "luxury", "minimal"),
    ),
    "comparison.split": LayoutMetadata(
        layout_id="comparison.split",
        supported_slide_types=(SlideType.COMPARISON.value,),
        supported_content_types=("comparison", "bullets", "title"),
        min_bullet_count=2,
        max_bullet_count=10,
        min_text_length=20,
        max_text_length=360,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=True,
        supports_stats=False,
        supports_quote=False,
        density="medium",
        compatible_theme_styles=("corporate", "academic", "technical", "minimal"),
    ),
    "timeline.stacked": LayoutMetadata(
        layout_id="timeline.stacked",
        supported_slide_types=(SlideType.TIMELINE.value,),
        supported_content_types=("timeline", "title", "notes"),
        min_bullet_count=0,
        max_bullet_count=2,
        min_text_length=10,
        max_text_length=260,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=True,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=False,
        density="medium",
        compatible_theme_styles=("academic", "corporate", "minimal", "technical"),
    ),
    "statistics.grid": LayoutMetadata(
        layout_id="statistics.grid",
        supported_slide_types=(SlideType.STATISTICS.value,),
        supported_content_types=("statistics", "title", "notes"),
        min_bullet_count=0,
        max_bullet_count=2,
        min_text_length=0,
        max_text_length=220,
        supports_image=False,
        supports_chart=True,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=True,
        supports_quote=False,
        density="high",
        compatible_theme_styles=("corporate", "technical", "minimal", "academic"),
    ),
    "statistics.featured": LayoutMetadata(
        layout_id="statistics.featured",
        supported_slide_types=(SlideType.STATISTICS.value,),
        supported_content_types=("statistics", "title", "notes"),
        min_bullet_count=0,
        max_bullet_count=2,
        min_text_length=0,
        max_text_length=240,
        supports_image=False,
        supports_chart=True,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=True,
        supports_quote=False,
        density="medium",
        compatible_theme_styles=("corporate", "technical", "minimal", "gradient"),
    ),
    "quote.centered": LayoutMetadata(
        layout_id="quote.centered",
        supported_slide_types=(SlideType.QUOTE.value,),
        supported_content_types=("quote", "attribution"),
        min_bullet_count=0,
        max_bullet_count=0,
        min_text_length=10,
        max_text_length=320,
        supports_image=False,
        supports_chart=False,
        supports_table=False,
        supports_timeline=False,
        supports_comparison=False,
        supports_stats=False,
        supports_quote=True,
        density="low",
        compatible_theme_styles=("luxury", "academic", "minimal", "corporate"),
    ),
}


class SlideAnalyzer:
    @staticmethod
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    def analyze(slide: Slide) -> SlideAnalysis:
        # Роля в pipeline-а: събира измерими характеристики, върху които следващото решение може да се базира.
        # Входът идва през `slide` (Slide); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `SlideAnalyzer._density`, `SlideAnalysis`; така се вижда кои отговорности функцията делегира.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `SlideAnalysis`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        # `paragraph_parts` пази резултата от `' '.join`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        paragraph_parts = [
            slide.subtitle or "",
            slide.notes or "",
            slide.quote or "",
            " ".join(slide.bullets or []),
            " ".join(slide.left_bullets or []),
            " ".join(slide.right_bullets or []),
            " ".join(step.detail or "" for step in (slide.timeline or [])),
            " ".join(item.detail or "" for item in (slide.statistics or [])),
        ]
        # `paragraph_length` пази резултата от `' '.join((part for part in paragraph_parts if part)).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        paragraph_length = len(" ".join(part for part in paragraph_parts if part).strip())
        # `image_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        image_count = 1 if slide.image_prompt else 0
        # `chart_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        chart_count = 1 if slide.type == SlideType.STATISTICS else 0
        # `table_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        table_count = 0
        timeline_items = len(slide.timeline or [])
        comparison_items = int(bool(slide.left_title)) + int(bool(slide.right_title))
        # `stats_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        stats_count = len(slide.statistics or [])
        stat_values = [str(item.value or "") for item in (slide.statistics or [])]
        # `max_stat_value_length` пази резултата от `value.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        max_stat_value_length = max((len(value.strip()) for value in stat_values), default=0)
        # `avg_stat_value_length` пази резултата от `value.strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        avg_stat_value_length = (
            int(sum(len(value.strip()) for value in stat_values) / len(stat_values)) if stat_values else 0
        )
        # `bullet_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        bullet_count = len(slide.bullets or []) + len(slide.left_bullets or []) + len(slide.right_bullets or [])
        # `quote_length` пази резултата от `(slide.quote or '').strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        quote_length = len((slide.quote or "").strip())
        density = SlideAnalyzer._density(
            bullet_count=bullet_count,
            paragraph_length=paragraph_length,
            timeline_items=timeline_items,
            comparison_items=comparison_items,
            stats_count=stats_count,
            image_count=image_count,
        )
        return SlideAnalysis(
            slide_id=slide.id,
            slide_type=slide.type.value if isinstance(slide.type, SlideType) else str(slide.type),
            title=slide.title or "",
            subtitle=slide.subtitle or "",
            bullet_count=bullet_count,
            paragraph_length=paragraph_length,
            image_count=image_count,
            chart_count=chart_count,
            table_count=table_count,
            timeline_items=timeline_items,
            comparison_items=comparison_items,
            stats_count=stats_count,
            max_stat_value_length=max_stat_value_length,
            avg_stat_value_length=avg_stat_value_length,
            quote_length=quote_length,
            density=density,
        )

    @staticmethod
    def _density(
        *,
        bullet_count: int,
        paragraph_length: int,
        timeline_items: int,
        comparison_items: int,
        stats_count: int,
        image_count: int,
    ) -> str:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `density` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `bullet_count` (int), `paragraph_length` (int), `timeline_items` (int), `comparison_items` (int), `stats_count` (int), `image_count` (int); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `str`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        # `score` е числова оценка за сравнение; тя позволява различни сигнали да участват в един ranking.
        score = (
            bullet_count * 1.5
            + paragraph_length / 80
            + timeline_items * 2
            + comparison_items * 1.5
            + stats_count * 2
            - image_count * 0.5
        )
        # Това условие е decision point: `score >= 10`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'high'`, без да проверява по-слабите правила отдолу.
        if score >= 10:
            return "high"
        # Това условие е decision point: `score >= 4`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'medium'`, без да проверява по-слабите правила отдолу.
        if score >= 4:
            return "medium"
        return "low"


class LayoutScorer:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    def __init__(self, theme_styles: set[str]) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `theme_styles` (set[str]); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # `self.theme_styles` е изведените визуални характеристики, използвани при scoring на layout кандидатите.
        self.theme_styles = theme_styles

    def score(
        self,
        analysis: SlideAnalysis,
        metadata: LayoutMetadata,
        recent_layout_counts: Counter[str],
        recent_layout_id: str | None,
    ) -> tuple[float, list[str]]:
        # Роля в pipeline-а: Събира съвместимостта по content type, density, theme и повторяемост в една сравнима числова оценка.
        # Входът идва през `self` (неуточнен тип), `analysis` (SlideAnalysis), `metadata` (LayoutMetadata), `recent_layout_counts` (Counter[str]), `recent_layout_id` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self.theme_styles.intersection`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `tuple[float, list[str]]`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        # `score` е числова оценка за сравнение; тя позволява различни сигнали да участват в един ranking.
        score = 0.0
        # `reasons` е човешко обяснение защо дадено решение или score е получено.
        reasons: list[str] = []

        # Това условие е decision point: `analysis.slide_type in metadata.supported_slide_types`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if analysis.slide_type in metadata.supported_slide_types:
            score += 0.28
            reasons.append("supports slide type")
        else:
            score -= 0.6
            reasons.append("mismatched slide type")

        required_supports = [
            (analysis.image_count > 0, metadata.supports_image, "image"),
            (analysis.chart_count > 0, metadata.supports_chart, "chart"),
            (analysis.table_count > 0, metadata.supports_table, "table"),
            (analysis.timeline_items > 0, metadata.supports_timeline, "timeline"),
            (analysis.comparison_items > 0, metadata.supports_comparison, "comparison"),
            (analysis.stats_count > 0, metadata.supports_stats, "stats"),
            (analysis.quote_length > 0, metadata.supports_quote, "quote"),
        ]
        # Обхождаме `required_supports` като `(required, supported, label)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for required, supported, label in required_supports:
            if not required:
                continue
            if supported:
                score += 0.22
                reasons.append(f"supports {label}")
            else:
                score -= 0.55
                reasons.append(f"missing {label} slot")

        # Това условие е decision point: `metadata.min_bullet_count <= analysis.bullet_count <= metadata.max_bullet_count`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if metadata.min_bullet_count <= analysis.bullet_count <= metadata.max_bullet_count:
            score += 0.14
            reasons.append("bullet count fits")
        elif analysis.bullet_count > metadata.max_bullet_count:
            score -= 0.24
            reasons.append("bullet overcrowding")
        elif analysis.bullet_count < metadata.min_bullet_count:
            score -= 0.16
            reasons.append("too few bullets")

        # Това условие е decision point: `metadata.min_text_length <= analysis.paragraph_length <= metadata.max_text_length`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if metadata.min_text_length <= analysis.paragraph_length <= metadata.max_text_length:
            score += 0.12
            reasons.append("text length fits")
        elif analysis.paragraph_length > metadata.max_text_length:
            score -= 0.22
            reasons.append("text overcrowding")

        # Това условие е decision point: `analysis.density == metadata.density`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if analysis.density == metadata.density:
            score += 0.16
            reasons.append("density match")
        elif {analysis.density, metadata.density} == {"low", "medium"} or {analysis.density, metadata.density} == {
            "medium",
            "high",
        }:
            score += 0.05
            reasons.append("density close")
        else:
            score -= 0.14
            reasons.append("density mismatch")

        # `theme_overlap` пази резултата от `self.theme_styles.intersection`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        theme_overlap = self.theme_styles.intersection(metadata.compatible_theme_styles)
        # Това условие е decision point: `theme_overlap`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if theme_overlap:
            score += 0.14
            reasons.append(f"theme style match ({', '.join(sorted(theme_overlap))})")
        else:
            score -= 0.08
            reasons.append("theme style mismatch")

        # Това условие е decision point: `analysis.slide_type == SlideType.STATISTICS.value and metadata.layout_id == 'statistics.f...`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if analysis.slide_type == SlideType.STATISTICS.value and metadata.layout_id == "statistics.featured":
            if analysis.max_stat_value_length > 16:
                score -= 0.26
                reasons.append("featured stat value too long")
            elif analysis.avg_stat_value_length > 10:
                score -= 0.14
                reasons.append("featured stats too text-heavy")

        # Това условие е decision point: `analysis.slide_type == SlideType.TIMELINE.value and metadata.layout_id == 'timeline.stacked'`.
        # При вярно условие се активира `reasons.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if analysis.slide_type == SlideType.TIMELINE.value and metadata.layout_id == "timeline.stacked":
            if analysis.paragraph_length > 140 or analysis.timeline_items >= 4:
                score += 0.06
                reasons.append("timeline favors roomy rows")

        # `repeat_count` пази броя на релевантните елементи; числото после участва в условие, лимит или score.
        repeat_count = recent_layout_counts.get(metadata.layout_id, 0)
        if recent_layout_id == metadata.layout_id:
            score -= 0.06
            reasons.append("repeat layout penalty")
        if repeat_count >= 2:
            score -= min(0.03 * repeat_count, 0.12)
            reasons.append("recent reuse penalty")

        return score, reasons


class LayoutSelector:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    def __init__(self) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        self._registry = LAYOUT_METADATA_REGISTRY

    def select_for_presentation(self, presentation: Presentation) -> list[LayoutRecommendation]:
        # Роля в pipeline-а: Оценява всички позволени layouts за всеки слайд, избира победителя и пази алтернативите и причините за debugging.
        # Входът идва през `self` (неуточнен тип), `presentation` (Presentation); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._infer_theme_styles`, `LayoutScorer`, `Counter`, `SlideAnalyzer.analyze`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `list[LayoutRecommendation]`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        # `theme_styles` е изведените визуални характеристики, използвани при scoring на layout кандидатите.
        theme_styles = self._infer_theme_styles(presentation.theme)
        # `scorer` пази резултата от `LayoutScorer`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        scorer = LayoutScorer(theme_styles)
        recommendations: list[LayoutRecommendation] = []
        # `recent_layout_counts` е кратка памет за вече използваните layouts, нужна за визуално разнообразие.
        recent_layout_counts: Counter[str] = Counter()
        # `recent_layout_id` е стабилен идентификатор, чрез който този обект може да се свърже с останалите pipeline данни.
        recent_layout_id: str | None = None

        # Обхождаме `presentation.slides` като `slide`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for slide in presentation.slides:
            # `analysis` е компактното описание на съдържанието, върху което layout selector-ът взима решение.
            analysis = SlideAnalyzer.analyze(slide)
            # `ranked` е кандидатите след оценяване, подредени така, че най-подходящият да бъде първи.
            ranked: list[tuple[str, float, list[str]]] = []
            # Обхождаме `self._registry.values()` като `metadata`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
            # Цикълът държи обработката еднаква за всеки елемент.
            for metadata in self._registry.values():
                score, reasons = scorer.score(analysis, metadata, recent_layout_counts, recent_layout_id)
                ranked.append((metadata.layout_id, score, reasons))
            ranked.sort(key=lambda item: item[1], reverse=True)

            selected_layout_id, selected_score, selected_reasons = ranked[0]
            # `alternatives` пази резултата от `self._build_reason`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
            alternatives = [
                {
                    "layout_id": layout_id,
                    "score": round(self._normalize_score(score), 4),
                    "reason": self._build_reason(reasons),
                }
                for layout_id, score, reasons in ranked[1:4]
            ]
            recommendations.append(
                LayoutRecommendation(
                    slide_id=analysis.slide_id,
                    selected_layout_id=selected_layout_id,
                    score=round(self._normalize_score(selected_score), 4),
                    reason=self._build_reason(selected_reasons),
                    alternatives=alternatives,
                )
            )
            recent_layout_counts[selected_layout_id] += 1
            # `recent_layout_id` е стабилен идентификатор, чрез който този обект може да се свърже с останалите pipeline данни.
            recent_layout_id = selected_layout_id

        return recommendations

    @staticmethod
    def _normalize_score(score: float) -> float:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда различни и непредвидими входове към един стабилен вътрешен формат.
        # Входът идва през `score` (float); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `float`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        return max(0.0, min(1.0, 0.5 + score / 2.0))

    @staticmethod
    def _build_reason(reasons: list[str]) -> str:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
        # Входът идва през `reasons` (list[str]); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `str`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        return ", ".join(reasons[:4])

    @staticmethod
    def _infer_theme_styles(theme_name: str) -> set[str]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: извежда липсваща класификация от наличните текстови сигнали.
        # Входът идва през `theme_name` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `get_theme_tokens`, `styles.update`, `styles.add`; така се вижда кои отговорности функцията делегира.
        # Декораторът над функцията променя начина, по който framework-ът я регистрира или валидира, без да променя основното ѝ тяло.
        # Изходен договор: `set[str]`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
        # `tokens` е theme настройките, които държат визуалното решение последователно между layouts и exporters.
        tokens = get_theme_tokens(theme_name)
        styles = {
            "technical" if "technical" in tokens.visual_tags or tokens.name == "modern_dark_tech" else "",
            "corporate" if tokens.name in {"minimal_corporate", "data_report", "startup_pitch"} else "",
            "playful" if tokens.name in {"playful_learning", "clean_school"} else "",
            "gradient" if tokens.name in {"creative_gradient"} else "",
            "minimal" if tokens.layout_style in {"minimal", "dashboard"} or tokens.name == "minimal_corporate" else "",
            "academic" if tokens.name in {"academic_formal", "clean_school", "data_report"} else "",
            "luxury" if tokens.name in {"luxury_editorial", "photo_editorial"} else "",
        }
        styles.update(
            tag
            for tag in tokens.visual_tags
            if tag in {"technical", "corporate", "playful", "gradient", "minimal", "academic"}
        )
        styles.add(tokens.layout_style)
        return {style for style in styles if style}
