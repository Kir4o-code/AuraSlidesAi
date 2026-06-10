from app.semantic.contracts import (
    Alignment,
    LayoutRegion,
    LayoutRegionRole,
    LayoutSpec,
    RendererCapabilities,
    RendererContext,
    RendererTarget,
)

LAYOUT_SPEC_REGISTRY: dict[str, LayoutSpec] = {
    "title.centered": LayoutSpec(
        name="title.centered",
        description="Single centered title and supporting copy.",
        alignment="center",
        emphasis="single",
        columns=1,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.CENTER, emphasis="primary", weight=1.0
            ),
            LayoutRegion(
                id="subtitle",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.CENTER,
                emphasis="secondary",
                weight=0.7,
                content_hints=["subtitle", "notes"],
            ),
            LayoutRegion(
                id="footer", role=LayoutRegionRole.FOOTER, alignment=Alignment.CENTER, emphasis="supporting", weight=0.3
            ),
        ],
    ),
    "title.left_feature": LayoutSpec(
        name="title.left_feature",
        description="Left-aligned title slide with supporting copy and footer space.",
        alignment="left",
        emphasis="primary-secondary",
        columns=1,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=1.0
            ),
            LayoutRegion(
                id="subtitle",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=0.8,
                content_hints=["subtitle", "notes"],
            ),
            LayoutRegion(
                id="footer", role=LayoutRegionRole.FOOTER, alignment=Alignment.START, emphasis="supporting", weight=0.3
            ),
        ],
    ),
    "content.bullets": LayoutSpec(
        name="content.bullets",
        description="Title with a vertical list of supporting points.",
        alignment="left",
        emphasis="primary-secondary",
        columns=1,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=1.0
            ),
            LayoutRegion(
                id="body",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=1.4,
                content_hints=["bullets", "notes"],
            ),
        ],
    ),
    "content.bullets_dense": LayoutSpec(
        name="content.bullets_dense",
        description="Title with compact bullets and denser information packing.",
        alignment="left",
        emphasis="primary-secondary",
        columns=1,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=0.8
            ),
            LayoutRegion(
                id="body",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=1.6,
                content_hints=["bullets", "notes"],
            ),
            LayoutRegion(
                id="aside",
                role=LayoutRegionRole.ASIDE,
                alignment=Alignment.START,
                emphasis="supporting",
                weight=0.4,
                content_hints=["notes"],
            ),
        ],
    ),
    "content.image_split": LayoutSpec(
        name="content.image_split",
        description="Text on one side, media on the other.",
        alignment="split",
        emphasis="primary-secondary",
        columns=2,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=0.8
            ),
            LayoutRegion(
                id="body", role=LayoutRegionRole.BODY, alignment=Alignment.START, emphasis="secondary", weight=1.1
            ),
            LayoutRegion(
                id="media",
                role=LayoutRegionRole.MEDIA,
                alignment=Alignment.CENTER,
                emphasis="primary",
                weight=1.1,
                content_hints=["image", "visual"],
            ),
        ],
    ),
    "content.image_focus_split": LayoutSpec(
        name="content.image_focus_split",
        description="Asymmetric split that gives more area to the image than the text.",
        alignment="split",
        emphasis="balanced",
        columns=2,
        regions=[
            LayoutRegion(
                id="body",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=0.9,
                content_hints=["title", "bullets", "notes"],
            ),
            LayoutRegion(
                id="media",
                role=LayoutRegionRole.MEDIA,
                alignment=Alignment.CENTER,
                emphasis="primary",
                weight=1.4,
                content_hints=["image", "visual"],
            ),
        ],
    ),
    "hero.focus": LayoutSpec(
        name="hero.focus",
        description="Large title with a single primary visual.",
        alignment="split",
        emphasis="balanced",
        columns=2,
        regions=[
            LayoutRegion(
                id="hero_text", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=1.0
            ),
            LayoutRegion(
                id="media", role=LayoutRegionRole.MEDIA, alignment=Alignment.CENTER, emphasis="primary", weight=1.2
            ),
        ],
    ),
    "comparison.split": LayoutSpec(
        name="comparison.split",
        description="Two balanced content zones for comparison slides.",
        alignment="split",
        emphasis="balanced",
        columns=2,
        regions=[
            LayoutRegion(
                id="left",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="primary",
                weight=1.0,
                content_hints=["left_title", "left_bullets"],
            ),
            LayoutRegion(
                id="right",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="primary",
                weight=1.0,
                content_hints=["right_title", "right_bullets"],
            ),
        ],
    ),
    "timeline.stacked": LayoutSpec(
        name="timeline.stacked",
        description="Sequential milestones with a single text rail.",
        alignment="left",
        emphasis="single",
        columns=1,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=0.8
            ),
            LayoutRegion(
                id="timeline",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=1.4,
                content_hints=["timeline"],
            ),
        ],
    ),
    "statistics.grid": LayoutSpec(
        name="statistics.grid",
        description="Metrics arranged as a responsive grid.",
        alignment="grid",
        emphasis="primary-secondary",
        columns=3,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=0.7
            ),
            LayoutRegion(
                id="metrics",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="primary",
                weight=1.6,
                content_hints=["statistics"],
            ),
        ],
    ),
    "statistics.featured": LayoutSpec(
        name="statistics.featured",
        description="One featured metric with supporting metrics below.",
        alignment="grid",
        emphasis="primary-secondary",
        columns=2,
        regions=[
            LayoutRegion(
                id="title", role=LayoutRegionRole.TITLE, alignment=Alignment.START, emphasis="primary", weight=0.6
            ),
            LayoutRegion(
                id="hero_metric",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="primary",
                weight=1.4,
                content_hints=["statistics"],
            ),
            LayoutRegion(
                id="metrics",
                role=LayoutRegionRole.BODY,
                alignment=Alignment.START,
                emphasis="secondary",
                weight=1.0,
                content_hints=["statistics"],
            ),
        ],
    ),
    "quote.centered": LayoutSpec(
        name="quote.centered",
        description="Centered quote and attribution with little else.",
        alignment="center",
        emphasis="single",
        columns=1,
        regions=[
            LayoutRegion(
                id="quote",
                role=LayoutRegionRole.TITLE,
                alignment=Alignment.CENTER,
                emphasis="primary",
                weight=1.2,
                content_hints=["quote"],
            ),
            LayoutRegion(
                id="attribution",
                role=LayoutRegionRole.FOOTER,
                alignment=Alignment.CENTER,
                emphasis="supporting",
                weight=0.4,
            ),
        ],
    ),
}


RENDERER_CAPABILITY_MATRIX: dict[RendererTarget, RendererCapabilities] = {
    RendererTarget.REACT: RendererCapabilities(
        supports_css=True,
        supports_web_fonts=True,
        supports_blur=True,
        supports_animations=True,
        supports_gradients=True,
        supports_shadows=True,
        supports_absolute_positioning=True,
        supports_editable_text=True,
        supports_vector_output=False,
        supports_responsive_layout=True,
    ),
    RendererTarget.PPTX: RendererCapabilities(
        supports_css=False,
        supports_web_fonts=False,
        supports_blur=False,
        supports_animations=False,
        supports_gradients=True,
        supports_shadows=False,
        supports_absolute_positioning=True,
        supports_editable_text=True,
        supports_vector_output=True,
        supports_responsive_layout=False,
    ),
    RendererTarget.PDF: RendererCapabilities(
        supports_css=False,
        supports_web_fonts=True,
        supports_blur=False,
        supports_animations=False,
        supports_gradients=True,
        supports_shadows=True,
        supports_absolute_positioning=True,
        supports_editable_text=False,
        supports_vector_output=False,
        supports_responsive_layout=False,
    ),
    RendererTarget.SCREENSHOT: RendererCapabilities(
        supports_css=True,
        supports_web_fonts=True,
        supports_blur=True,
        supports_animations=False,
        supports_gradients=True,
        supports_shadows=True,
        supports_absolute_positioning=True,
        supports_editable_text=False,
        supports_vector_output=False,
        supports_responsive_layout=True,
    ),
    RendererTarget.EDITOR: RendererCapabilities(
        supports_css=True,
        supports_web_fonts=True,
        supports_blur=True,
        supports_animations=True,
        supports_gradients=True,
        supports_shadows=True,
        supports_absolute_positioning=True,
        supports_editable_text=True,
        supports_vector_output=False,
        supports_responsive_layout=True,
    ),
}


def get_layout_spec(name: str) -> LayoutSpec:
    return LAYOUT_SPEC_REGISTRY[name]


def build_renderer_context(target: RendererTarget) -> RendererContext:
    return RendererContext(target=target, capabilities=RENDERER_CAPABILITY_MATRIX[target].model_copy(deep=True))
