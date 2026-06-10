from __future__ import annotations

import re

from app.semantic.catalog import LAYOUT_SPEC_REGISTRY, RENDERER_CAPABILITY_MATRIX
from app.semantic.contracts import LayoutSpec, PresentationDocument, RendererContext, ThemeDefinition


def validate_presentation_document(document: PresentationDocument) -> PresentationDocument:
    # Pydantic validation already enforces structure; this is a narrow semantic guard.
    for slide in document.slides:
        if slide.layout_name not in LAYOUT_SPEC_REGISTRY:
            raise ValueError(f"Unknown layout '{slide.layout_name}' on slide '{slide.id}'.")
    return document


def validate_theme_definition(theme: ThemeDefinition) -> ThemeDefinition:
    if not theme.tokens.component_styles:
        return theme
    for component_name, styles in theme.tokens.component_styles.items():
        if not component_name.strip():
            raise ValueError("Theme component styles need a component name.")
        for key, value in styles.items():
            if key.lower() in {"layout", "region", "width", "height", "position"}:
                raise ValueError("Theme component styles must not contain layout concerns.")
            if isinstance(value, str):
                lowered = value.lower()
                has_css_unit = re.search(r"(^|[\s:(,])[-+]?\d*\.?\d+(px|rem|em)\b", lowered)
                if has_css_unit or any(
                    marker in lowered for marker in ("rgba(", "linear-gradient", "font:", "margin:", "padding:")
                ):
                    raise ValueError("Theme component styles must stay abstract and renderer-neutral.")
    return theme


def validate_layout_spec(layout: LayoutSpec) -> LayoutSpec:
    if layout.name not in LAYOUT_SPEC_REGISTRY:
        raise ValueError(f"Unknown layout spec '{layout.name}'.")
    return layout


def validate_renderer_context(context: RendererContext) -> RendererContext:
    supported = RENDERER_CAPABILITY_MATRIX.get(context.target)
    if supported is None:
        raise ValueError(f"Unsupported renderer target '{context.target}'.")
    if context.capabilities != supported:
        raise ValueError(f"Renderer capabilities do not match matrix for target '{context.target}'.")
    return context
