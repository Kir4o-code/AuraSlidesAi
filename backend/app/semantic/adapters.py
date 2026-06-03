from __future__ import annotations

from app.schemas.presentation import Presentation, Slide, SlideType
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
from app.semantic.layout_selector import LayoutSelector
from app.services.theme_registry import get_theme_tokens


def _short_alt_text(slide: Slide) -> str | None:
    if slide.title:
        return slide.title[:120]
    if not slide.image_prompt:
        return None

    cleaned = slide.image_prompt.strip()
    if len(cleaned) <= 220:
        return cleaned

    return f"{cleaned[:217].rstrip()}..."


def _slide_media(slide: Slide) -> list[SlideMediaRef]:
    media: list[SlideMediaRef] = []
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
    selector = LayoutSelector()
    recommendations = selector.select_for_presentation(presentation)
    recommended_by_slide_id = {item.slide_id: item for item in recommendations}
    semantic_slides = []
    for index, slide in enumerate(presentation.slides, start=1):
        recommendation = recommended_by_slide_id.get(slide.id)
        layout_name = recommendation.selected_layout_id if recommendation else "content.bullets"
        semantic_slides.append(
            {
                "id": slide.id,
                "order": index,
                "layout_name": layout_name,
                "title": slide.title,
                "subtitle": slide.subtitle,
                "bullets": list(slide.bullets),
                "image_prompt": slide.image_prompt,
                "visual_mood": slide.visual_mood,
                "icon_intent": slide.icon_intent,
                "notes": slide.notes,
                "left_title": slide.left_title,
                "right_title": slide.right_title,
                "left_bullets": list(slide.left_bullets),
                "right_bullets": list(slide.right_bullets),
                "timeline": [step.model_dump(mode="json") for step in slide.timeline],
                "statistics": [item.model_dump(mode="json") for item in slide.statistics],
                "quote": slide.quote,
                "attribution": slide.attribution,
                "media": [media.model_dump(mode="json") for media in _slide_media(slide)],
            }
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
    tokens = get_theme_tokens(theme_name)

    def _font_family_name(value: str) -> str:
        first_token = value.split(",", 1)[0].strip()
        first_token = first_token.strip("'")
        return first_token or value

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
    specs: list[LayoutSpec] = []
    for slide in document.slides:
        try:
            specs.append(get_layout_spec(slide.layout_name))
        except KeyError as exc:
            raise KeyError(f"Unknown layout '{slide.layout_name}' for slide '{slide.id}'.") from exc
    return specs


def build_renderer_context(target: RendererTarget | str) -> RendererContext:
    normalized = RendererTarget(target)
    from app.semantic.catalog import build_renderer_context as _build_renderer_context

    return _build_renderer_context(normalized)
