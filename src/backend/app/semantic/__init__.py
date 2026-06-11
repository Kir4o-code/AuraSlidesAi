# Роля на модула: Помощен модул в backend pipeline-а; коментарите по-долу обясняват конкретните му граници и решения.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from app.semantic.catalog import LAYOUT_SPEC_REGISTRY, RENDERER_CAPABILITY_MATRIX
from app.semantic.contracts import (
    Alignment,
    LayoutRegion,
    LayoutRegionRole,
    LayoutSpec,
    PresentationDocument,
    RendererCapabilities,
    RendererContext,
    RendererTarget,
    ThemeDefinition,
    ThemeFonts,
    ThemeTokens,
)
from app.semantic.validators import (
    validate_layout_spec,
    validate_presentation_document,
    validate_renderer_context,
    validate_theme_definition,
)

__all__ = [
    "Alignment",
    "LayoutRegion",
    "LayoutRegionRole",
    "LayoutSpec",
    "PresentationDocument",
    "RendererCapabilities",
    "RendererContext",
    "RendererTarget",
    "ThemeDefinition",
    "ThemeFonts",
    "ThemeTokens",
    "validate_layout_spec",
    "validate_presentation_document",
    "validate_renderer_context",
    "validate_theme_definition",
    "LAYOUT_SPEC_REGISTRY",
    "RENDERER_CAPABILITY_MATRIX",
]
