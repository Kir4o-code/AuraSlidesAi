import type { CSSProperties } from "react";

import type { ThemeName } from "@/lib/api";

export interface ThemeTokens {
  name: ThemeName;
  background: string;
  backgroundAlt: string;
  surface: string;
  textColor: string;
  mutedTextColor: string;
  accentColor: string;
  accentSoftColor: string;
  borderColor: string;
  fontFamily: string;
  borderRadius: string;
  shadow: string;
  spacingScale: number;
  typographyScale: number;
}

export const THEME_REGISTRY: Record<ThemeName, ThemeTokens> = {
  modern_dark: {
    name: "modern_dark",
    background: "#0f172a",
    backgroundAlt: "#111827",
    surface: "#111c34",
    textColor: "#f8fafc",
    mutedTextColor: "#cbd5e1",
    accentColor: "#8b5cf6",
    accentSoftColor: "#c4b5fd",
    borderColor: "rgba(148, 163, 184, 0.22)",
    fontFamily: "Inter",
    borderRadius: "28px",
    shadow: "0 28px 80px rgba(15, 23, 42, 0.35)",
    spacingScale: 1,
    typographyScale: 1,
  },
  modern_light: {
    name: "modern_light",
    background: "#f8fafc",
    backgroundAlt: "#eef2ff",
    surface: "#ffffff",
    textColor: "#0f172a",
    mutedTextColor: "#475569",
    accentColor: "#2563eb",
    accentSoftColor: "#dbeafe",
    borderColor: "#cbd5e1",
    fontFamily: "Inter",
    borderRadius: "28px",
    shadow: "0 24px 70px rgba(37, 99, 235, 0.12)",
    spacingScale: 1,
    typographyScale: 1,
  },
  editorial: {
    name: "editorial",
    background: "#fffaf3",
    backgroundAlt: "#fef3c7",
    surface: "#ffffff",
    textColor: "#111827",
    mutedTextColor: "#57534e",
    accentColor: "#d97706",
    accentSoftColor: "#fde68a",
    borderColor: "#e7e5e4",
    fontFamily: "Merriweather",
    borderRadius: "24px",
    shadow: "0 26px 72px rgba(120, 53, 15, 0.12)",
    spacingScale: 1.05,
    typographyScale: 1.04,
  },
  corporate: {
    name: "corporate",
    background: "#f1f5f9",
    backgroundAlt: "#e2e8f0",
    surface: "#ffffff",
    textColor: "#0f172a",
    mutedTextColor: "#334155",
    accentColor: "#1d4ed8",
    accentSoftColor: "#bfdbfe",
    borderColor: "#cbd5e1",
    fontFamily: "Inter",
    borderRadius: "18px",
    shadow: "0 18px 42px rgba(15, 23, 42, 0.12)",
    spacingScale: 0.95,
    typographyScale: 0.98,
  },
  playful: {
    name: "playful",
    background: "#fff7fb",
    backgroundAlt: "#fdf2f8",
    surface: "#ffffff",
    textColor: "#1f2937",
    mutedTextColor: "#6b7280",
    accentColor: "#db2777",
    accentSoftColor: "#fbcfe8",
    borderColor: "#f3c4dd",
    fontFamily: "Inter",
    borderRadius: "30px",
    shadow: "0 26px 72px rgba(219, 39, 119, 0.16)",
    spacingScale: 1.08,
    typographyScale: 1.02,
  },
};

export function resolveThemeTokens(themeName: ThemeName | string | null | undefined): ThemeTokens {
  if (themeName && themeName in THEME_REGISTRY) {
    return THEME_REGISTRY[themeName as ThemeName];
  }
  return THEME_REGISTRY.modern_dark;
}

export function buildThemeStyle(tokens: ThemeTokens): CSSProperties {
  return {
    "--presentation-bg": tokens.background,
    "--presentation-bg-alt": tokens.backgroundAlt,
    "--presentation-surface": tokens.surface,
    "--presentation-text": tokens.textColor,
    "--presentation-muted": tokens.mutedTextColor,
    "--presentation-accent": tokens.accentColor,
    "--presentation-accent-soft": tokens.accentSoftColor,
    "--presentation-border": tokens.borderColor,
    "--presentation-radius": tokens.borderRadius,
    "--presentation-shadow": tokens.shadow,
    "--presentation-font": tokens.fontFamily,
    "--presentation-spacing": `${tokens.spacingScale}`,
    "--presentation-type-scale": `${tokens.typographyScale}`,
  } as CSSProperties;
}
