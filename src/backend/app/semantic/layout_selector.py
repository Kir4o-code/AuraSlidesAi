from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.schemas.presentation import Presentation, Slide, SlideType
from app.services.theme_registry import get_theme_tokens


@dataclass(frozen=True)
class SlideAnalysis:
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
    slide_id: str
    selected_layout_id: str
    score: float
    reason: str
    alternatives: list[dict[str, Any]]


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
    def analyze(slide: Slide) -> SlideAnalysis:
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
        paragraph_length = len(" ".join(part for part in paragraph_parts if part).strip())
        image_count = 1 if slide.image_prompt else 0
        chart_count = 1 if slide.type == SlideType.STATISTICS else 0
        table_count = 0
        timeline_items = len(slide.timeline or [])
        comparison_items = int(bool(slide.left_title)) + int(bool(slide.right_title))
        stats_count = len(slide.statistics or [])
        stat_values = [str(item.value or "") for item in (slide.statistics or [])]
        max_stat_value_length = max((len(value.strip()) for value in stat_values), default=0)
        avg_stat_value_length = (
            int(sum(len(value.strip()) for value in stat_values) / len(stat_values)) if stat_values else 0
        )
        bullet_count = len(slide.bullets or []) + len(slide.left_bullets or []) + len(slide.right_bullets or [])
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
        score = (
            bullet_count * 1.5
            + paragraph_length / 80
            + timeline_items * 2
            + comparison_items * 1.5
            + stats_count * 2
            - image_count * 0.5
        )
        if score >= 10:
            return "high"
        if score >= 4:
            return "medium"
        return "low"


class LayoutScorer:
    def __init__(self, theme_styles: set[str]) -> None:
        self.theme_styles = theme_styles

    def score(
        self,
        analysis: SlideAnalysis,
        metadata: LayoutMetadata,
        recent_layout_counts: Counter[str],
        recent_layout_id: str | None,
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

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
        for required, supported, label in required_supports:
            if not required:
                continue
            if supported:
                score += 0.22
                reasons.append(f"supports {label}")
            else:
                score -= 0.55
                reasons.append(f"missing {label} slot")

        if metadata.min_bullet_count <= analysis.bullet_count <= metadata.max_bullet_count:
            score += 0.14
            reasons.append("bullet count fits")
        elif analysis.bullet_count > metadata.max_bullet_count:
            score -= 0.24
            reasons.append("bullet overcrowding")
        elif analysis.bullet_count < metadata.min_bullet_count:
            score -= 0.16
            reasons.append("too few bullets")

        if metadata.min_text_length <= analysis.paragraph_length <= metadata.max_text_length:
            score += 0.12
            reasons.append("text length fits")
        elif analysis.paragraph_length > metadata.max_text_length:
            score -= 0.22
            reasons.append("text overcrowding")

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

        theme_overlap = self.theme_styles.intersection(metadata.compatible_theme_styles)
        if theme_overlap:
            score += 0.14
            reasons.append(f"theme style match ({', '.join(sorted(theme_overlap))})")
        else:
            score -= 0.08
            reasons.append("theme style mismatch")

        if analysis.slide_type == SlideType.STATISTICS.value and metadata.layout_id == "statistics.featured":
            if analysis.max_stat_value_length > 16:
                score -= 0.26
                reasons.append("featured stat value too long")
            elif analysis.avg_stat_value_length > 10:
                score -= 0.14
                reasons.append("featured stats too text-heavy")

        if analysis.slide_type == SlideType.TIMELINE.value and metadata.layout_id == "timeline.stacked":
            if analysis.paragraph_length > 140 or analysis.timeline_items >= 4:
                score += 0.06
                reasons.append("timeline favors roomy rows")

        repeat_count = recent_layout_counts.get(metadata.layout_id, 0)
        if recent_layout_id == metadata.layout_id:
            score -= 0.06
            reasons.append("repeat layout penalty")
        if repeat_count >= 2:
            score -= min(0.03 * repeat_count, 0.12)
            reasons.append("recent reuse penalty")

        return score, reasons


class LayoutSelector:
    def __init__(self) -> None:
        self._registry = LAYOUT_METADATA_REGISTRY

    def select_for_presentation(self, presentation: Presentation) -> list[LayoutRecommendation]:
        theme_styles = self._infer_theme_styles(presentation.theme)
        scorer = LayoutScorer(theme_styles)
        recommendations: list[LayoutRecommendation] = []
        recent_layout_counts: Counter[str] = Counter()
        recent_layout_id: str | None = None

        for slide in presentation.slides:
            analysis = SlideAnalyzer.analyze(slide)
            ranked: list[tuple[str, float, list[str]]] = []
            for metadata in self._registry.values():
                score, reasons = scorer.score(analysis, metadata, recent_layout_counts, recent_layout_id)
                ranked.append((metadata.layout_id, score, reasons))
            ranked.sort(key=lambda item: item[1], reverse=True)

            selected_layout_id, selected_score, selected_reasons = ranked[0]
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
            recent_layout_id = selected_layout_id

        return recommendations

    @staticmethod
    def _normalize_score(score: float) -> float:
        return max(0.0, min(1.0, 0.5 + score / 2.0))

    @staticmethod
    def _build_reason(reasons: list[str]) -> str:
        return ", ".join(reasons[:4])

    @staticmethod
    def _infer_theme_styles(theme_name: str) -> set[str]:
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
