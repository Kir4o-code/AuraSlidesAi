# Роля на модула: Единният източник на theme tokens. Layout и exporters четат оттук, вместо да дублират визуални решения.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from dataclasses import dataclass

from app.schemas.presentation import ThemeName

SUPPORTED_LAYOUTS = (
    "title_slide",
    "title_bullets",
    "title_bullets_image",
    "hero_image",
    "comparison",
    "timeline",
    "statistics",
    "quote",
)
DEFAULT_THEME_NAME = ThemeName.MODERN_DARK_TECH.value


@dataclass(frozen=True)
class ThemeTokens:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    name: str
    display_name: str
    description: str
    recommended_use_cases: tuple[str, ...]
    visual_tags: tuple[str, ...]
    palette: tuple[str, ...]
    background: str
    background_alt: str
    surface: str
    text_color: str
    muted_text_color: str
    accent_color: str
    accent_soft_color: str
    border_color: str
    font_family: str
    heading_font_family: str
    body_font_family: str
    border_radius: str
    shadow: str
    spacing_scale: float
    typography_scale: float
    image_style: str
    layout_style: str
    panel_style: str = "rounded"
    bullet_style: str = "cards"
    accent_position: str = "left"
    panel_radius: int = 24
    panel_padding: int = 24
    image_radius: int = 22
    image_frame_inset: int = 6
    image_fit: str = "cover"
    background_image: str | None = None
    background_position: str = "center"
    background_size: str = "cover"
    base_font_size: int = 18
    heading_scale: float = 2.4
    body_scale: float = 1.0
    line_height: float = 1.35
    letter_spacing: str = "normal"
    supported_slide_layout_types: tuple[str, ...] = SUPPORTED_LAYOUTS


# `THEME_REGISTRY` пази резултата от `ThemeTokens`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
THEME_REGISTRY: dict[str, ThemeTokens] = {
    ThemeName.CLEAN_SCHOOL.value: ThemeTokens(
        name=ThemeName.CLEAN_SCHOOL.value,
        display_name="Clean School",
        description="Bright, friendly structure with calm educational accents.",
        recommended_use_cases=("school projects", "classroom explainers", "general learning"),
        visual_tags=("bright", "readable", "friendly"),
        palette=("#F8FBFF", "#FFFFFF", "#2563EB", "#BFDBFE"),
        background="#F8FBFF",
        background_alt="#EAF3FF",
        surface="#FFFFFF",
        text_color="#172033",
        muted_text_color="#526176",
        accent_color="#2563EB",
        accent_soft_color="#BFDBFE",
        border_color="#C9DCF5",
        font_family="'Inter', 'Aptos', sans-serif",
        heading_font_family="'Nunito', 'Aptos Display', sans-serif",
        body_font_family="'Inter', 'Aptos', sans-serif",
        border_radius="26px",
        shadow="0 18px 48px rgba(37, 99, 235, 0.12)",
        spacing_scale=1.08,
        typography_scale=1.0,
        image_style="soft_frame",
        layout_style="airy",
        panel_padding=28,
        image_radius=22,
        image_frame_inset=8,
    ),
    ThemeName.MODERN_DARK_TECH.value: ThemeTokens(
        name=ThemeName.MODERN_DARK_TECH.value,
        display_name="Modern Dark Tech",
        description="High-contrast panels and cool accents for technical ideas.",
        recommended_use_cases=("AI", "apps", "hackathons", "software"),
        visual_tags=("dark", "technical", "high contrast"),
        palette=("#07111F", "#10243E", "#67E8F9", "#8B5CF6"),
        background="#07111F",
        background_alt="#10243E",
        surface="#132A46",
        text_color="#F8FAFC",
        muted_text_color="#B8C8DB",
        accent_color="#67E8F9",
        accent_soft_color="#8B5CF6",
        border_color="#31506F",
        font_family="'Inter', 'Aptos', sans-serif",
        heading_font_family="'Space Grotesk', 'Aptos Display', sans-serif",
        body_font_family="'Inter', 'Aptos', sans-serif",
        border_radius="22px",
        shadow="0 24px 64px rgba(2, 8, 23, 0.42)",
        spacing_scale=1.02,
        typography_scale=1.0,
        image_style="dark_panel",
        layout_style="panel_grid",
        panel_radius=18,
        image_radius=16,
        image_frame_inset=8,
    ),
    ThemeName.ACADEMIC_FORMAL.value: ThemeTokens(
        name=ThemeName.ACADEMIC_FORMAL.value,
        display_name="Academic Formal",
        description="Restrained scholarly styling with comfortable reading rhythm.",
        recommended_use_cases=("research", "history", "literature", "formal reports"),
        visual_tags=("formal", "serif", "structured"),
        palette=("#F7F4ED", "#FFFCF7", "#243B53", "#B08D57"),
        background="#F7F4ED",
        background_alt="#ECE5D8",
        surface="#FFFCF7",
        text_color="#24313F",
        muted_text_color="#617080",
        accent_color="#8A653A",
        accent_soft_color="#D8C3A5",
        border_color="#D7CDBE",
        font_family="'Source Sans 3', 'Aptos', sans-serif",
        heading_font_family="'Merriweather', 'Georgia', serif",
        body_font_family="'Source Sans 3', 'Aptos', sans-serif",
        border_radius="10px",
        shadow="0 14px 30px rgba(65, 48, 32, 0.08)",
        spacing_scale=1.12,
        typography_scale=0.96,
        image_style="caption_frame",
        layout_style="editorial",
        panel_style="square",
        bullet_style="lines",
        panel_radius=8,
        panel_padding=30,
        image_radius=4,
        image_frame_inset=10,
    ),
    ThemeName.STARTUP_PITCH.value: ThemeTokens(
        name=ThemeName.STARTUP_PITCH.value,
        display_name="Startup Pitch",
        description="Bold statements, crisp cards, and confident product energy.",
        recommended_use_cases=("product ideas", "pitch decks", "startups", "hackathons"),
        visual_tags=("bold", "card based", "confident"),
        palette=("#F7F8FF", "#FFFFFF", "#5B21B6", "#F97316"),
        background="#F7F8FF",
        background_alt="#ECE9FF",
        surface="#FFFFFF",
        text_color="#19152D",
        muted_text_color="#625C75",
        accent_color="#5B21B6",
        accent_soft_color="#F97316",
        border_color="#D9D2F3",
        font_family="'Inter', 'Aptos', sans-serif",
        heading_font_family="'Sora', 'Aptos Display', sans-serif",
        body_font_family="'Inter', 'Aptos', sans-serif",
        border_radius="22px",
        shadow="0 20px 54px rgba(91, 33, 182, 0.16)",
        spacing_scale=1.0,
        typography_scale=1.04,
        image_style="accent_frame",
        layout_style="statement",
        accent_position="top",
        panel_radius=18,
        image_radius=18,
    ),
    ThemeName.PHOTO_EDITORIAL.value: ThemeTokens(
        name=ThemeName.PHOTO_EDITORIAL.value,
        display_name="Photo Editorial",
        description="Image-led storytelling with cinematic neutral typography.",
        recommended_use_cases=("travel", "culture", "geography", "history"),
        visual_tags=("cinematic", "image first", "editorial"),
        palette=("#171717", "#34312D", "#F8F1E7", "#D59B62"),
        background="#171717",
        background_alt="#34312D",
        surface="#2A2825",
        text_color="#FFF9F0",
        muted_text_color="#D8CFC3",
        accent_color="#D59B62",
        accent_soft_color="#F0D4B7",
        border_color="#5B5148",
        font_family="'Inter', 'Aptos', sans-serif",
        heading_font_family="'DM Serif Display', 'Georgia', serif",
        body_font_family="'Inter', 'Aptos', sans-serif",
        border_radius="12px",
        shadow="0 24px 70px rgba(0, 0, 0, 0.32)",
        spacing_scale=1.06,
        typography_scale=1.02,
        image_style="cinematic",
        layout_style="image_led",
        panel_style="square",
        bullet_style="lines",
        panel_radius=8,
        image_radius=2,
        image_frame_inset=4,
    ),
    ThemeName.MINIMAL_CORPORATE.value: ThemeTokens(
        name=ThemeName.MINIMAL_CORPORATE.value,
        display_name="Minimal Corporate",
        description="Quiet neutral space with understated professional structure.",
        recommended_use_cases=("business", "reports", "strategy", "operations"),
        visual_tags=("neutral", "spacious", "professional"),
        palette=("#F4F1EB", "#FFFEFC", "#1F2937", "#9B7B5A"),
        background="#F4F1EB",
        background_alt="#E8E1D7",
        surface="#FFFEFC",
        text_color="#1F2937",
        muted_text_color="#667085",
        accent_color="#826445",
        accent_soft_color="#D9C9B7",
        border_color="#D7D0C6",
        font_family="'Inter', 'Helvetica', sans-serif",
        heading_font_family="'Manrope', 'Aptos Display', sans-serif",
        body_font_family="'Inter', 'Helvetica', sans-serif",
        border_radius="14px",
        shadow="0 12px 34px rgba(31, 41, 55, 0.08)",
        spacing_scale=1.14,
        typography_scale=0.98,
        image_style="subtle_frame",
        layout_style="minimal",
        panel_style="square",
        bullet_style="lines",
        panel_radius=10,
        panel_padding=30,
        image_radius=8,
    ),
    ThemeName.CREATIVE_GRADIENT.value: ThemeTokens(
        name=ThemeName.CREATIVE_GRADIENT.value,
        display_name="Creative Gradient",
        description="Expressive color transitions anchored by clean components.",
        recommended_use_cases=("innovation", "creative projects", "youth topics"),
        visual_tags=("colorful", "gradient", "modern"),
        palette=("#1E1B4B", "#312E81", "#A78BFA", "#22D3EE"),
        background="#1E1B4B",
        background_alt="#312E81",
        surface="#37308A",
        text_color="#FFFFFF",
        muted_text_color="#DDD6FE",
        accent_color="#22D3EE",
        accent_soft_color="#A78BFA",
        border_color="#665FB8",
        font_family="'Plus Jakarta Sans', 'Aptos', sans-serif",
        heading_font_family="'Outfit', 'Aptos Display', sans-serif",
        body_font_family="'Plus Jakarta Sans', 'Aptos', sans-serif",
        border_radius="28px",
        shadow="0 24px 68px rgba(15, 10, 65, 0.38)",
        spacing_scale=1.04,
        typography_scale=1.02,
        image_style="gradient_frame",
        layout_style="expressive",
        accent_position="top",
        panel_radius=24,
        image_radius=22,
    ),
    ThemeName.DATA_REPORT.value: ThemeTokens(
        name=ThemeName.DATA_REPORT.value,
        display_name="Data Report",
        description="Analytical grid system optimized for evidence and metrics.",
        recommended_use_cases=("statistics", "science", "comparisons", "analytics"),
        visual_tags=("analytical", "dashboard", "grid"),
        palette=("#F5F8FA", "#FFFFFF", "#0F766E", "#99F6E4"),
        background="#F5F8FA",
        background_alt="#E6F2F1",
        surface="#FFFFFF",
        text_color="#16323A",
        muted_text_color="#57717A",
        accent_color="#0F766E",
        accent_soft_color="#99F6E4",
        border_color="#C9DDDF",
        font_family="'IBM Plex Sans', 'Aptos', sans-serif",
        heading_font_family="'IBM Plex Sans', 'Aptos Display', sans-serif",
        body_font_family="'IBM Plex Sans', 'Aptos', sans-serif",
        border_radius="14px",
        shadow="0 14px 34px rgba(15, 118, 110, 0.10)",
        spacing_scale=0.98,
        typography_scale=0.96,
        image_style="evidence_frame",
        layout_style="dashboard",
        panel_radius=10,
        image_radius=8,
        image_frame_inset=8,
    ),
    ThemeName.NATURE_ORGANIC.value: ThemeTokens(
        name=ThemeName.NATURE_ORGANIC.value,
        display_name="Nature Organic",
        description="Earth-toned cards and calm visual pacing for natural topics.",
        recommended_use_cases=("ecology", "biology", "agriculture", "geography"),
        visual_tags=("earth tones", "soft", "organic"),
        palette=("#F5F4EA", "#FFFEF7", "#4D7C5B", "#C8D5B9"),
        background="#F5F4EA",
        background_alt="#E6E8D4",
        surface="#FFFEF7",
        text_color="#26362B",
        muted_text_color="#657566",
        accent_color="#4D7C5B",
        accent_soft_color="#C8D5B9",
        border_color="#D2D8C5",
        font_family="'Nunito', 'Aptos', sans-serif",
        heading_font_family="'Fraunces', 'Georgia', serif",
        body_font_family="'Nunito', 'Aptos', sans-serif",
        border_radius="28px",
        shadow="0 18px 44px rgba(77, 124, 91, 0.12)",
        spacing_scale=1.1,
        typography_scale=1.0,
        image_style="organic_frame",
        layout_style="organic",
        panel_radius=28,
        panel_padding=28,
        image_radius=28,
        image_frame_inset=8,
    ),
    ThemeName.LUXURY_EDITORIAL.value: ThemeTokens(
        name=ThemeName.LUXURY_EDITORIAL.value,
        display_name="Luxury Editorial",
        description="Premium serif hierarchy with high whitespace and restraint.",
        recommended_use_cases=("art", "fashion", "architecture", "culture"),
        visual_tags=("premium", "serif", "whitespace"),
        palette=("#FAF7F2", "#FFFFFF", "#1C1B1A", "#A98352"),
        background="#FAF7F2",
        background_alt="#EEE7DE",
        surface="#FFFFFF",
        text_color="#1C1B1A",
        muted_text_color="#746B62",
        accent_color="#A98352",
        accent_soft_color="#E2D0B6",
        border_color="#DED5CA",
        font_family="'Inter', 'Helvetica', sans-serif",
        heading_font_family="'Cormorant Garamond', 'Georgia', serif",
        body_font_family="'Inter', 'Helvetica', sans-serif",
        border_radius="6px",
        shadow="0 12px 30px rgba(40, 31, 24, 0.08)",
        spacing_scale=1.18,
        typography_scale=1.04,
        image_style="gallery_frame",
        layout_style="luxury",
        panel_style="square",
        bullet_style="lines",
        panel_radius=4,
        panel_padding=32,
        image_radius=2,
        image_frame_inset=10,
    ),
    ThemeName.PLAYFUL_LEARNING.value: ThemeTokens(
        name=ThemeName.PLAYFUL_LEARNING.value,
        display_name="Playful Learning",
        description="Colorful rounded cards that stay classroom-safe and clear.",
        recommended_use_cases=("younger learners", "classroom activities", "explainers"),
        visual_tags=("colorful", "rounded", "friendly"),
        palette=("#FFF8EE", "#FFFFFF", "#EA580C", "#FDE68A"),
        background="#FFF8EE",
        background_alt="#FEF3C7",
        surface="#FFFFFF",
        text_color="#3F2B20",
        muted_text_color="#7C6254",
        accent_color="#EA580C",
        accent_soft_color="#FDE68A",
        border_color="#F2D6B6",
        font_family="'Nunito', 'Aptos', sans-serif",
        heading_font_family="'Nunito', 'Aptos Display', sans-serif",
        body_font_family="'Nunito', 'Aptos', sans-serif",
        border_radius="30px",
        shadow="0 18px 44px rgba(234, 88, 12, 0.12)",
        spacing_scale=1.04,
        typography_scale=1.0,
        image_style="soft_frame",
        layout_style="friendly",
        panel_radius=28,
        panel_padding=26,
        image_radius=26,
    ),
    ThemeName.MONOCHROME_BOLD.value: ThemeTokens(
        name=ThemeName.MONOCHROME_BOLD.value,
        display_name="Monochrome Bold",
        description="Graphic black-and-white hierarchy with one decisive accent.",
        recommended_use_cases=("editorial", "keynotes", "brand concepts", "portfolios"),
        visual_tags=("monochrome", "graphic", "export safe"),
        palette=("#F7F7F5", "#FFFFFF", "#111111", "#E11D48"),
        background="#F7F7F5",
        background_alt="#E8E8E4",
        surface="#FFFFFF",
        text_color="#111111",
        muted_text_color="#595959",
        accent_color="#E11D48",
        accent_soft_color="#FECDD3",
        border_color="#CFCFCA",
        font_family="'Inter', 'Helvetica', sans-serif",
        heading_font_family="'Archivo', 'Arial', sans-serif",
        body_font_family="'Inter', 'Helvetica', sans-serif",
        border_radius="4px",
        shadow="0 12px 28px rgba(17, 17, 17, 0.10)",
        spacing_scale=1.02,
        typography_scale=1.06,
        image_style="graphic_frame",
        layout_style="graphic",
        panel_style="square",
        bullet_style="lines",
        accent_position="top",
        panel_radius=2,
        image_radius=0,
        image_frame_inset=6,
    ),
}

THEME_ALIASES = {
    "modern": ThemeName.MODERN_DARK_TECH.value,
    "modern_dark": ThemeName.MODERN_DARK_TECH.value,
    "minimal": ThemeName.CLEAN_SCHOOL.value,
    "modern_light": ThemeName.CLEAN_SCHOOL.value,
    "editorial": ThemeName.PHOTO_EDITORIAL.value,
    "corporate": ThemeName.MINIMAL_CORPORATE.value,
    "playful": ThemeName.PLAYFUL_LEARNING.value,
}


def resolve_theme_name(value: str | None) -> str:
    # Роля в pipeline-а: взима решение между няколко възможни източника или стратегии и връща готов резултат.
    # Входът идва през `value` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # Това условие е decision point: `not value`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`DEFAULT_THEME_NAME`) и прескачаме ненужната останала работа.
    if not value:
        return DEFAULT_THEME_NAME
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = THEME_ALIASES.get(value.strip().lower(), value.strip().lower())
    return normalized if normalized in THEME_REGISTRY else DEFAULT_THEME_NAME


def get_theme_tokens(value: str | None) -> ThemeTokens:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Входът идва през `value` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `resolve_theme_name`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ThemeTokens`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    return THEME_REGISTRY[resolve_theme_name(value)]
