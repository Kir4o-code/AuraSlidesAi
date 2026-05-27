from dataclasses import dataclass

from app.schemas.presentation import ThemeName


@dataclass(frozen=True)
class ThemeTokens:
    name: str
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
    # New tokens
    background_image: str | None = None
    background_position: str = "center"
    background_size: str = "cover"
    base_font_size: int = 18
    heading_scale: float = 2.4
    body_scale: float = 1.0
    line_height: float = 1.35
    letter_spacing: str = "normal"


THEME_REGISTRY: dict[str, ThemeTokens] = {
    ThemeName.MODERN_DARK.value: ThemeTokens(
        name=ThemeName.MODERN_DARK.value,
        background="#0f172a",
        background_alt="#1e293b",
        surface="#1e293b",
        text_color="#f8fafc",
        muted_text_color="#cbd5e1",
        accent_color="#8b5cf6",
        accent_soft_color="#c4b5fd",
        border_color="rgba(148, 163, 184, 0.22)",
        font_family="'Inter', -apple-system, sans-serif",
        heading_font_family="'Plus Jakarta Sans', sans-serif",
        body_font_family="'Inter', sans-serif",
        border_radius="28px",
        shadow="0 28px 80px rgba(15, 23, 42, 0.35)",
        spacing_scale=1.6,
        typography_scale=1.4,
        background_image=None,
        background_position="center",
        background_size="cover",
        base_font_size=20,
        heading_scale=2.6,
        body_scale=1.0,
        line_height=1.28,
        letter_spacing="normal",
    ),
    ThemeName.MODERN_LIGHT.value: ThemeTokens(
        name=ThemeName.MODERN_LIGHT.value,
        background="#f8fafc",
        background_alt="#f1f5f9",
        surface="#ffffff",
        text_color="#0f172a",
        muted_text_color="#475569",
        accent_color="#2563eb",
        accent_soft_color="#dbeafe",
        border_color="#cbd5e1",
        font_family="'Inter', -apple-system, sans-serif",
        heading_font_family="'Plus Jakarta Sans', sans-serif",
        body_font_family="'Inter', sans-serif",
        border_radius="28px",
        shadow="0 24px 70px rgba(37, 99, 235, 0.12)",
        spacing_scale=1.4,
        typography_scale=1.2,
        background_image=None,
        background_position="center",
        background_size="cover",
        base_font_size=18,
        heading_scale=2.4,
        body_scale=1.0,
        line_height=1.32,
        letter_spacing="normal",
    ),
    ThemeName.EDITORIAL.value: ThemeTokens(
        name=ThemeName.EDITORIAL.value,
        background="#fffaf3",
        background_alt="#fef3c7",
        surface="#ffffff",
        text_color="#111827",
        muted_text_color="#57534e",
        accent_color="#d97706",
        accent_soft_color="#fde68a",
        border_color="#e7e5e4",
        font_family="'Inter', -apple-system, sans-serif",
        heading_font_family="'Plus Jakarta Sans', sans-serif",
        body_font_family="'Inter', sans-serif",
        border_radius="24px",
        shadow="0 26px 72px rgba(120, 53, 15, 0.12)",
        spacing_scale=1.15,
        typography_scale=0.92,
        background_image=None,
        background_position="center",
        background_size="cover",
        base_font_size=18,
        heading_scale=2.2,
        body_scale=0.98,
        line_height=1.36,
        letter_spacing="normal",
    ),
    ThemeName.CORPORATE.value: ThemeTokens(
        name=ThemeName.CORPORATE.value,
        background="#f1f5f9",
        background_alt="#cbd5e1",
        surface="#ffffff",
        text_color="#0f172a",
        muted_text_color="#334155",
        accent_color="#1d4ed8",
        accent_soft_color="#bfdbfe",
        border_color="#cbd5e1",
        font_family="'Inter', -apple-system, sans-serif",
        heading_font_family="'Plus Jakarta Sans', sans-serif",
        body_font_family="'Inter', sans-serif",
        border_radius="18px",
        shadow="0 18px 42px rgba(15, 23, 42, 0.12)",
        spacing_scale=1.05,
        typography_scale=0.88,
        background_image=None,
        background_position="center",
        background_size="cover",
        base_font_size=17,
        heading_scale=2.2,
        body_scale=0.98,
        line_height=1.34,
        letter_spacing="normal",
    ),
    ThemeName.PLAYFUL.value: ThemeTokens(
        name=ThemeName.PLAYFUL.value,
        background="#fff7fb",
        background_alt="#fdf2f8",
        surface="#ffffff",
        text_color="#1f2937",
        muted_text_color="#6b7280",
        accent_color="#db2777",
        accent_soft_color="#fbcfe8",
        border_color="#f3c4dd",
        font_family="'Inter', -apple-system, sans-serif",
        heading_font_family="'Plus Jakarta Sans', sans-serif",
        body_font_family="'Inter', sans-serif",
        border_radius="30px",
        shadow="0 26px 72px rgba(219, 39, 119, 0.16)",
        spacing_scale=1.1,
        typography_scale=0.92,
        background_image=None,
        background_position="center",
        background_size="cover",
        base_font_size=18,
        heading_scale=2.6,
        body_scale=1.0,
        line_height=1.3,
        letter_spacing="normal",
    ),
}

THEME_ALIASES = {
    "modern": ThemeName.MODERN_DARK.value,
    "minimal": ThemeName.MODERN_LIGHT.value,
    "corporate": ThemeName.CORPORATE.value,
    "playful": ThemeName.PLAYFUL.value,
}


def resolve_theme_name(value: str | None) -> str:
    if not value:
        return ThemeName.MODERN_DARK.value

    normalized = value.strip().lower()
    normalized = THEME_ALIASES.get(normalized, normalized)
    if normalized in THEME_REGISTRY:
        return normalized
    return ThemeName.MODERN_DARK.value


def get_theme_tokens(value: str | None) -> ThemeTokens:
    return THEME_REGISTRY[resolve_theme_name(value)]
